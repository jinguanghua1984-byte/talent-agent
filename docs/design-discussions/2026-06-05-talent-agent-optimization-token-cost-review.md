# Talent Agent 项目优化、Claude Code + Codex 协作与 Token 成本治理审查

日期：2026-06-05

## 背景

本次审查目标有三部分：

1. 审查整个 `talent-agent` 项目，识别工程结构、脚本、工作流和协作方式中可以优化的地方。
2. 分析高频工作内容，判断哪些环节可以通过脚本化、模型调用优化、环境优化等方式降低 Claude/API 与 Codex/API/CLI 成本。
3. 明确同时使用 Claude Code 和 Codex 时的分工、隔离、成本归因和合并门禁。

整体判断：项目已经具备较强的可审计、可恢复、门禁明确的工程化意识；当前主要成本不是来自单个模型调用本身，而是来自：

- 执行任务时反复读取长 workflow、任务历史、raw/report/state 产物。
- 本地脚本中的 LLM 调用缺少统一 token 计量、usage 记录、prompt caching、batching 和结构化输出。
- 一些本可由确定性脚本完成的状态判断、恢复判断、下一步推断，仍需要模型读取上下文后判断。

优化方向不是“少用模型”，而是：确定性步骤脚本化，长上下文分层加载，LLM 只用于真正需要判断、归纳、生成和排序的部分。

## 项目结构观察

项目当前采用运行时中立的 agent 架构：

- `agents/workflows/`：运行时中立的 canonical workflow。
- `agents/skills/`：业务入口合同，定义语义触发、默认参数和 workflow 交接。
- `.claude/skills/`：Claude Code adapter。
- `scripts/`：实际可执行 Python CLI 和库模块。
- `data/`：人才库、campaign、运行产物、raw、reports、output。
- `tasks/todo.md`、`tasks/archive/`、`tasks/lessons.md`：任务工作台、历史归档和经验沉淀。

高频工作集中在：

1. BOSS / 脉脉 / 猎聘平台寻访 campaign。
2. 平台 raw 标准化、候选人摘要、身份匹配、Campaign DB 导入。
3. Campaign DB 到主库 `data/talent.db` 的 dry-run / apply 门禁。
4. JD 本地人才库匹配、评分、推荐报告、外联表和飞书发布。
5. 推荐反馈自然语言解析和评分卡校准。
6. 长任务中断恢复、质量门禁、任务归档。

真正需要 LLM 的环节通常是：JD 画像、评分卡、候选人精排理由、自然语言反馈归类、推荐报告措辞。大量其他环节是状态机、文件扫描、schema 校验、dry-run/apply 编排，应尽量由脚本完成。

## P0 优先优化项

### 1. 建立 provider-neutral LLM 成本观测层

当前 LLM 客户端和 retry 工具只是最小封装，缺少：

- input/output tokens
- cache read/write tokens
- prompt hash
- model
- max_tokens
- cost estimate
- 本地缓存命中情况
- workflow / stage 维度统计

建议新增统一 `LLMUsageLedger`，每次模型调用写入：

```text
data/token-tracker/llm-usage-YYYY-MM.jsonl
```

建议字段：

```json
{
  "timestamp": "...",
  "provider": "anthropic",
  "tool_surface": "claude_api",
  "agent_runtime": "script",
  "workflow": "jd-talent-delivery",
  "stage": "detailed-rank",
  "model": "claude-opus-4-8",
  "max_tokens": 16000,
  "input_tokens": 12345,
  "output_tokens": 678,
  "cache_read_input_tokens": 9000,
  "cache_creation_input_tokens": 0,
  "cache_ttl": "5m",
  "prompt_hash": "...",
  "input_artifact_hash": "...",
  "request_id": "req_...",
  "session_id": "...",
  "stop_reason": "end_turn",
  "artifact_root": "data/output/...",
  "api_cache_hit": true,
  "local_cache_hit": false,
  "batch_discount_applied": false,
  "usage_source": "api_usage",
  "cost_formula": "anthropic_messages_v1",
  "estimated_cost_usd": 0.1234
}
```

成本估算必须按 provider / tool surface 分支计算，而不是用 Claude 的价格和缓存规则套所有工具：

```text
anthropic_messages_cost =
  input_tokens * anthropic_input_price
  + output_tokens * anthropic_output_price
  + cache_creation_input_tokens * anthropic_input_price * cache_write_multiplier
  + cache_read_input_tokens * anthropic_input_price * cache_read_multiplier

openai_or_codex_cost =
  provider_reported_input_tokens * provider_input_price
  + provider_reported_output_tokens * provider_output_price
  + provider_specific_cache_or_reasoning_cost
```

其中 Anthropic prompt cache read 约为基础 input 价格的 0.1x；5 分钟 TTL 的 cache write 约为 1.25x；1 小时 TTL 的 cache write 约为 2x；Message Batches API 对 token usage 约有 50% 折扣。Codex / OpenAI-compatible 路径要按其自身 usage 字段、价格表、缓存/推理 token 规则计算，不能复用 Anthropic 的 `cache_read_input_tokens` / `cache_creation_input_tokens` 口径。

`api_cache_hit` 应由 provider 原生 usage 派生；`local_cache_hit` 用于脚本层的结果缓存；`tool_surface` 用于区分 `claude_api`、`claude_code`、`codex_cli`、`openai_api`、`local_script` 等入口。若某个 CLI 只能输出汇总账单或没有逐请求 usage，`usage_source` 应标记为 `transcript_estimate` / `provider_dashboard` / `manual_estimate`，避免和 API 原生 usage 混算。

收益：后续不再凭感觉判断哪类任务贵，而是可以按 workflow、stage、model 和 prompt hash 做成本排行。

### 2. JD 交付链路改为“确定性优先、LLM 后置”

JD delivery 的岗位画像、评分卡、粗筛、精排中都有模型参与空间，但项目中已有大量规则化能力，例如公司、标题、技能、年限、学历、排除项等确定性打分。

建议默认链路改为：

1. 规则召回：公司、标题、技能、年限、学历、排除项。
2. 确定性粗筛：只保留 Top 100 / Top 200。
3. 证据压缩：每人只保留命中字段、关键经历片段和风险项。
4. LLM 精排：只处理 Top 30-60。
5. LLM 主要输出排序理由和差距分析；分数尽量由规则和校准函数控制。

当前 `llm_ranker` 已有按关键词截断候选人文本的能力，下一步应把“进入 LLM 前的候选人数”和“每人证据长度”做成硬预算。

### 3. 反馈解析从逐条 LLM 调用改为规则优先 + 批量调用

推荐反馈 `feedback_note` 通常短、类别固定，非常适合降本：

- 先用规则解析常见短语：认可、不合适、太贵、年限不符、方向不符、已联系、暂缓等。
- 低置信或长文本才调用模型。
- 多条低置信反馈合并到一次 batch prompt，一次解析 20-50 条。
- 用结构化输出替代“返回 JSON + 正则抽取”。

这类任务也适合在 API 层使用更低成本模型或 provider 批处理能力；Anthropic 路径可使用 Message Batches API，Codex / OpenAI-compatible 路径走各自批处理机制。模型选择应作为显式配置，不应在代码里偷偷降级。

### 4. 压缩长 workflow，降低每次执行的上下文加载成本

当前 token 热点主要在：

- `agents/workflows/liepin-unattended-campaign/AGENT.md`
- `agents/workflows/public-search/AGENT.md`
- `agents/workflows/jd-talent-delivery/AGENT.md`
- platform-match 相关 workflow/reference

这些文档包含大量重复的安全边界、停机条件、dry-run/apply 规则和命令模板。建议拆分为：

```text
agents/policies/platform-safety.md
agents/policies/db-write-gates.md
agents/policies/feishu-publish-gates.md
agents/workflows/<name>/AGENT.md
agents/workflows/<name>/commands.md
```

`AGENT.md` 只保留：

- 触发入口
- 阶段状态机
- 本 workflow 特有边界
- 需要读取哪些 policy/reference

这样 skill 触发时不必一次吞完整长文档，只有进入具体阶段才读取具体片段。

## P1 脚本化与环境优化

### 5. 新增统一 campaign 状态摘要命令

目前恢复长任务时，经常需要读取 `tasks/todo.md`、campaign 目录、reports、state、ledger 等多个位置。建议新增：

```bash
python -m scripts.campaign_status summarize --campaign-root <path>
```

输出一页 JSON/Markdown：

- 当前阶段
- 已完成页数、候选人数、详情数、沟通数
- 最近 interruption
- continuation plan
- dry-run/apply 状态
- 下一步合法命令
- 是否需要人工授权
- 禁止事项

收益：长任务恢复时只需读取摘要，而不是扫描大量 raw/report/state。

### 6. 新增 `workflow doctor` / `next-action` 命令

针对 BOSS-Maimai、猎聘、脉脉 campaign，可脚本判断下一步：

```bash
python -m scripts.campaign_orchestrator next-action --campaign-root <path>
```

示例输出：

```json
{
  "next_stage": "main-db-apply-authorization",
  "blocked_by": "requires_user_confirm",
  "required_confirm_text": "确认同步人才库",
  "safe_commands": [],
  "forbidden_commands": []
}
```

这会减少模型读取长 workflow 来推断下一步的 token 成本，也能降低误操作风险。

### 7. 自动生成脚本清单

`docs/dev/script-inventory.md` 已经承担脚本边界说明，但容易滞后。建议新增：

```bash
python -m scripts.dev_inventory generate
python -m scripts.dev_inventory check
```

自动扫描：

- 有 `argparse` 的入口
- `__main__` 入口
- help 输出
- 是否有测试
- 是否在 inventory 中登记
- 是否符合 dry-run/apply 模式

收益：减少代码审查 token，防止脚本膨胀。

### 8. 清理仓库产物和缓存噪音

建议统一忽略和检查：

- `__pycache__/`
- `.pytest_cache/`
- `.DS_Store`
- `*.db-shm`
- `*.db-wal`
- 大型临时 artifacts

并增加：

```bash
python -m scripts.repo_hygiene check
```

避免 `find` / 搜索结果被运行产物污染，也减少模型读取无关内容的概率。

## P2 多 Provider / API 成本最佳实践

### 9. 模型路由与显式配置

模型选择应成为 workflow/stage 级显式配置，而不是在代码路径里隐式降级。建议先定义默认路由，再允许调用方按任务覆盖。配置维度至少包括 `provider`、`tool_surface`、`model`、`max_tokens`、是否 streaming、是否 batch eligible、结构化输出模式和 usage parser。

| 场景 | 默认模型 | 说明 |
| --- | --- | --- |
| 反馈分类、短文本标签、固定类别归因 | `claude-haiku-4-5` 或 `claude-sonnet-4-6` | 低 `max_tokens`，结构化输出，低置信再升级。 |
| JD 画像、评分卡生成、候选人证据归纳 | `claude-sonnet-4-6` | 平衡成本和质量；复杂 JD 或关键客户可升级 Opus。 |
| TopN 精排、推荐理由、差距分析 | `claude-sonnet-4-6` 起步，必要时 `claude-opus-4-8` | 先做规则召回和证据压缩，避免 Opus 处理全量候选人。 |
| 长报告、多工具任务、复杂审查 | `claude-opus-4-8` | streaming + 较大 `max_tokens`，适合长上下文和高价值判断。 |
| 大批量离线解析/摘要 | 任务适配模型 + provider 批处理 | 非实时任务优先 batch；Anthropic 可用 Message Batches API，以 50% token 成本折扣换取延迟。 |

当前常用 Claude API 成本口径：Opus 4.8 / 4.7 / 4.6 约为 $5 input / $25 output per 1M tokens；Sonnet 4.6 约为 $3 / $15；Haiku 4.5 约为 $1 / $5。Opus / Sonnet 4.6 是 1M context；Haiku 4.5 是 200K context。Opus 最大输出 128K，Sonnet / Haiku 最大输出 64K；大输出应使用 streaming，避免非 streaming 请求超时。

Codex / OpenAI-compatible 路径应单独维护 provider price table、token 字段映射和结构化输出实现，不应默认继承 Claude 的 prompt caching、Batches API、`output_config.format` 或 token counting 规则。

### 10. Anthropic prompt caching 适用点

本节只讨论 Anthropic prompt cache。Claude Code、Codex CLI、OpenAI-compatible provider 之间不能共享 API prompt cache；跨工具可共享的是确定性压缩产物，例如 campaign 状态摘要、JD 画像、scorecard、候选人 evidence pack、workflow 摘要。

项目中适合缓存的稳定前缀：

- 长 workflow / shared policy 文档
- JD 原文 + 岗位画像
- scorecard
- 固定评分 rubric
- 固定反馈解析 schema、label、reason code 列表

注意 prompt caching 是前缀精确匹配，且不是所有稳定内容都值得缓存。应同时满足：

- 稳定前缀足够长：Opus 4.8 / 4.7 / 4.6 / Haiku 4.5 的最小可缓存前缀约 4096 tokens，Sonnet 4.6 约 2048 tokens；短 schema、label 列表、reason code 列表可能低于门槛，不会产生 cache write。
- 同一前缀会在 TTL 内复用：默认 5 分钟 TTL 的写入约 1.25x input 成本，1 小时 TTL 的写入约 2x；如果没有后续 cache read，cache write 反而增加成本。
- 稳定内容必须物理上位于 prompt 前缀：render order 是 tools -> system -> messages；工具列表或 system 前部变动会破坏后续缓存。
- 每次请求最多 4 个 cache breakpoints；应放在稳定性边界，而不是盲目放在整个 prompt 末尾。

应避免：

- 把当前日期、run id、候选人批次号放在 system prompt 前面。
- JSON 不排序导致同一内容 bytes 不同。
- 每次动态改变工具列表。
- 同一个长 system prompt 每次拼接不同任务信息。

推荐结构：

```text
稳定 system / rubric / scorecard -> cache breakpoint
本次候选人批次 / 用户问题       -> 不缓存 suffix
```

需要记录 `usage.cache_read_input_tokens` 和 `usage.cache_creation_input_tokens`，否则无法判断缓存是否真正命中。

### 11. Provider 批处理用于非实时批量任务

适合使用 provider 批处理的任务：

- 批量候选人反馈解析
- 批量候选人短评生成
- 多 JD 对同一人才库的离线评分
- 多候选人画像摘要
- 夜间/无人值守报告初稿生成

Batch 非实时，但可降低 50% token 成本。项目中的离线 campaign 流水线和反馈解析非常适合。实现时应把 batch job id、custom id、输入 prompt hash、输出 artifact 路径和 usage 写入 `LLMUsageLedger`，否则离线任务的成本会从实时调用报表中“消失”。

### 12. Token counting 成为门禁

Claude token 不应使用 `tiktoken` 估算，应通过 Anthropic `messages.count_tokens` 或 `ant messages count-tokens`，并且必须使用即将实际调用的模型 ID，因为 token 计数是模型相关的。Codex / OpenAI-compatible provider 应使用其 provider 原生 token 计量或 API usage 字段，不能与 Claude token estimator 混用。

`count_tokens` 适合作为调用前的 input 预算门禁；真实成本仍以响应 `usage` 为准，尤其要记录 output tokens、cache read/write tokens、batch 折扣和 stop reason。

建议在 LLM 调用前加预算门禁：

- 单个候选人证据超过 N tokens：自动压缩。
- 单批 prompt 超过 N tokens：自动拆批。
- 本轮 workflow 预计成本超过阈值：写出 dry-run 成本报告，等待确认。
- output `max_tokens` 按任务类型设置，而不是盲目固定。

建议默认：

- 反馈分类：`max_tokens=512` 或更低。
- 单候选人短评：`max_tokens=512-1024`。
- TopN 报告：`max_tokens=8000-16000`。
- 长报告/多工具任务：streaming + 较大上限。

### 13. 结构化输出替代“JSON prompt + 正则解析”

当前部分脚本让模型返回 JSON，再用正则/手工解析。建议：

- Anthropic provider 路径使用 `output_config.format` / SDK parse。
- OpenAI-compatible provider 保留旧路径作为兼容 fallback，不复用 Anthropic-only 参数。
- Claude 4.6+ 不使用 assistant prefill 强制 JSON；结构化输出也不应和 message prefill 混用。
- schema 应保持短而稳定；如果低于 prompt cache 最小前缀门槛，不要假设它会被缓存。

收益：减少坏 JSON、减少重试、减少解析失败后的人工排查 token。

## P3 Claude Code + Codex 协作治理

### 14. 明确 Claude Code 与 Codex 的任务边界

同时使用 Claude Code 和 Codex 时，降本重点不只是“哪个模型便宜”，而是避免两个工具重复读取、重复推理、重复改同一批文件。建议采用默认分工：

| 工具 | 适合任务 | 不建议承担 |
| --- | --- | --- |
| Claude Code | 长上下文项目理解、workflow/skills/任务状态审查、跨目录规划、安全门禁、最终合并前审查 | 大量局部样板代码的盲生成、与其他 agent 并行改同一目录 |
| Codex | 局部脚本实现、单文件/少文件代码补全、测试失败修复、小范围重构草案 | 需要读取大量项目约束、涉及 dry-run/apply 授权、飞书发布、主库写入门禁的任务 |
| 确定性脚本 | 状态摘要、schema 校验、diff 检查、成本 dry-run、next-action 判断 | 需要自然语言判断、候选人推荐理由、复杂权衡的任务 |

任务启动前应先判断“主执行者”：同一轮代码修改只指定一个工具负责最终落地，另一个工具最多提供只读审查、局部 patch 草案或测试修复建议。

### 15. 并行写作隔离与合并门禁

Claude Code 和 Codex 并行工作时，应默认隔离写入面：

- 大任务使用不同 branch / worktree，避免两个 agent 在同一 working tree 互相覆盖。
- 不让两个 agent 同时改同一目录、同一 migration、同一 workflow 文档或同一 DB 写入脚本。
- Codex 产出的 patch 进入主线前，由 Claude Code 或确定性脚本统一跑格式、测试、diff review 和项目门禁。
- 涉及主库同步、Campaign DB apply、飞书发布、外部平台沟通等动作时，只认项目脚本和人工授权，不认任一 agent 的上下文判断。
- 合并前必须记录：哪个工具改了哪些文件、基于哪个任务摘要、验证命令是什么、是否有未解决风险。

### 16. 共享状态源与 artifact 协议

多工具协作时，不能把任一工具的聊天上下文当作事实源。共同事实源应是 repo 内可审计 artifact：

- `tasks/todo.md` / `tasks/archive/`：任务状态和归档。
- campaign `state` / `ledger` / `reports`：平台寻访进度和产物。
- `data/talent.db` 及 dry-run/apply 报告：人才库变更事实。
- `LLMUsageLedger`：跨 provider 的成本、usage 和 prompt hash。
- 新增的 `campaign_status summarize` / `next-action` 输出：长任务恢复入口。

Claude Code 和 Codex 都应优先读取这些摘要 artifact，而不是各自重新扫描长 workflow、raw、report 和历史任务。若需要跨工具交接，应生成短交接包：目标、已改文件、剩余风险、验证命令、禁止事项、下一步合法命令。

### 17. 多 provider adapter 与能力差异

实现层应把 provider 差异收敛在 adapter，而不是散落在业务脚本：

- Anthropic provider：使用 `messages.count_tokens`、`usage.cache_*`、Message Batches API、`output_config.format` / SDK parse。
- Codex / OpenAI-compatible provider：维护独立 token 计量、结构化输出、批处理、缓存和价格表，不复用 Anthropic-only 参数。
- Claude Code / Codex CLI：如果无法拿到逐请求 API usage，应记录 transcript/session 级估算来源，并在报表中标记低置信。
- 本地脚本缓存：缓存的是输入 artifact hash 到输出 artifact 的确定性结果，不等同于 provider prompt cache。

收益：后续可以比较“同一 workflow/stage 在 Claude Code、Codex、脚本化路径下的成本和质量”，而不是只看单个 API 调用是否便宜。

## P4 技能和 agent 使用优化

### 18. `.claude/skills` adapter 模板化

当前测试已要求 `.claude/skills/*/SKILL.md` 是 adapter。建议改为生成：

```bash
python -m scripts.agent_adapters sync-claude-skills
python -m scripts.agent_adapters check
```

输入 canonical `agents/skills` / `agents/workflows`，输出 `.claude/skills`。

收益：

- 减少 adapter 同步 drift。
- 减少多处重复说明。
- 减少每次审查 adapter 的 token。

### 19. 子代理 / 多代理使用策略

在 Claude Code 中建议：

- 小范围单文件 / 单 grep：不要开子代理。
- 需要跨 `scripts/`、`agents/`、`tasks/` 三块读取大量文件：用 Explore/general-purpose 子代理，避免主上下文爆炸。
- 审查类任务：可并行分为脚本、技能、任务模式三个只读子代理。
- 代码修改类任务：先规划，再少量直接编辑；不要让多个写代理并行改同一目录。

“全项目审查”本身昂贵。后续应先跑本地摘要脚本，再让模型读摘要，只有热点再深入。

## 建议实施顺序

1. **provider-neutral LLM usage ledger + token counting + 模型/工具路由配置**
   先把 Claude API、Claude Code、Codex、OpenAI-compatible provider 和本地脚本的成本看清楚，并把 workflow/stage 到 provider、tool surface、model、`max_tokens`、streaming、batch eligibility 的映射外置为显式配置。

2. **Claude Code + Codex 协作门禁**
   明确主执行者、worktree/branch 隔离、共享 artifact、合并前验证命令和禁止事项，避免两个工具重复读取或互相覆盖文件。

3. **反馈解析批量化 / 规则优先**
   这是最容易省 token 的短文本批处理场景。

4. **campaign status / next-action 脚本**
   把长任务恢复和下一步判断脚本化，减少读取 `tasks/`、workflow 和 reports 的次数，也为 Claude Code / Codex 交接提供共同摘要。

5. **压缩 workflow + shared policies**
   先处理 Liepin、JD delivery、public-search 三个大文档。

6. **结构化输出与 provider adapter**
   Anthropic provider 路径使用 `output_config.format` / SDK parse；Codex / OpenAI-compatible provider 走各自 adapter，不复用 Anthropic-only 参数。

7. **Batch API / provider 批处理支持**
   用于反馈、候选人摘要、批量评分等非实时任务；Anthropic Message Batches、Codex/OpenAI 批处理能力分别按 provider 规则接入。

## 推荐下一步

建议先落地第 1 项：建立 provider-neutral `LLMUsageLedger`、token counting dry-run、Claude API usage 记录、Codex/CLI usage 估算来源标记，以及 workflow/stage 到工具和模型的显式路由配置。它不会改变业务行为，但能让后续所有降本优化和 Claude Code / Codex 分工有可量化依据。
