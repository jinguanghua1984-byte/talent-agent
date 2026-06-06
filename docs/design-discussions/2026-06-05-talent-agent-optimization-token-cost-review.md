# Talent Agent 项目优化与 Token 成本治理审查

日期：2026-06-05

## 背景

本次审查目标有两部分：

1. 审查整个 `talent-agent` 项目，识别工程结构、脚本、工作流和协作方式中可以优化的地方。
2. 分析高频工作内容，判断哪些环节可以通过脚本化、模型调用优化、环境优化等方式降低 Claude/API token 成本。

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

### 1. 建立统一 LLM 成本观测层

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
  "workflow": "jd-talent-delivery",
  "stage": "detailed-rank",
  "model": "claude-opus-4-8",
  "input_tokens": 12345,
  "output_tokens": 678,
  "cache_read_input_tokens": 9000,
  "cache_creation_input_tokens": 0,
  "prompt_hash": "...",
  "artifact_root": "data/output/...",
  "cache_hit": true
}
```

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

这类任务也适合在 API 层使用更低成本模型或 Batches API，但模型选择应作为显式配置，不应在代码里偷偷降级。

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

## P2 Claude/API 成本最佳实践

### 9. Prompt caching 适用点

项目中适合缓存的稳定前缀：

- 长 workflow / shared policy 文档
- JD 原文 + 岗位画像
- scorecard
- 固定评分 rubric
- 固定反馈解析 schema、label、reason code 列表

注意 prompt caching 是前缀精确匹配。应避免：

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

### 10. Batches API 用于非实时批量任务

适合用 Message Batches API 的任务：

- 批量候选人反馈解析
- 批量候选人短评生成
- 多 JD 对同一人才库的离线评分
- 多候选人画像摘要
- 夜间/无人值守报告初稿生成

Batch 非实时，但可降低 50% token 成本。项目中的离线 campaign 流水线和反馈解析非常适合。

### 11. Token counting 成为门禁

不应使用 `tiktoken` 估 Claude token。应通过 Anthropic `messages.count_tokens` 或 `ant messages count-tokens` 估算。

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

### 12. 结构化输出替代“JSON prompt + 正则解析”

当前部分脚本让模型返回 JSON，再用正则/手工解析。建议：

- Anthropic provider 路径使用 `output_config.format` / SDK parse。
- OpenAI-compatible provider 保留旧路径作为兼容 fallback。
- Claude 4.6+ 不使用 assistant prefill 强制 JSON。

收益：减少坏 JSON、减少重试、减少解析失败后的人工排查 token。

## P3 技能和 agent 使用优化

### 13. `.claude/skills` adapter 模板化

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

### 14. 子代理 / 多代理使用策略

在 Claude Code 中建议：

- 小范围单文件 / 单 grep：不要开子代理。
- 需要跨 `scripts/`、`agents/`、`tasks/` 三块读取大量文件：用 Explore/general-purpose 子代理，避免主上下文爆炸。
- 审查类任务：可并行分为脚本、技能、任务模式三个只读子代理。
- 代码修改类任务：先规划，再少量直接编辑；不要让多个写代理并行改同一目录。

“全项目审查”本身昂贵。后续应先跑本地摘要脚本，再让模型读摘要，只有热点再深入。

## 建议实施顺序

1. **LLM usage ledger + token counting**
   先把成本看清楚，为后续优化提供仪表盘。

2. **反馈解析批量化 / 规则优先**
   这是最容易省 token 的短文本批处理场景。

3. **campaign status / next-action 脚本**
   把长任务恢复和下一步判断脚本化，减少读取 `tasks/`、workflow 和 reports 的次数。

4. **压缩 workflow + shared policies**
   先处理 Liepin、JD delivery、public-search 三个大文档。

5. **结构化输出与 prompt caching**
   在 Anthropic provider 路径先做；OpenAI-compatible 保留兼容 fallback。

6. **Batch API 支持**
   用于反馈、候选人摘要、批量评分等非实时任务。

## 推荐下一步

建议先落地第 1 项：给 LLM 调用加 usage ledger、token counting dry-run 和 Anthropic usage 记录。它不会改变业务行为，但能让后续所有降本优化有可量化依据。
