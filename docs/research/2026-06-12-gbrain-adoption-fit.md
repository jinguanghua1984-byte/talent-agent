# GBrain 对 Talent-Agent 第二大脑的适配判断

## 决策

状态：proposed

建议：在改变 JD 交付工作流或把 GBrain 设为优先查询路径之前，先运行一次本地 pilot。

当前判断：P0 第二大脑基础设施与 GBrain 的方向一致，但开源采用闭环尚未完成。Talent-Agent 已经有 repo-first 的 event/case/fallback 层，以及一个很薄的可选 `gbrain` wrapper；但我们还没有用当前产物真实验证 GBrain 的安装、导入、搜索、query/synthesis、MCP、引用质量或 gap analysis 行为。

## 为什么评估 GBrain

- 避免重复实现长期记忆、混合检索、综合回答、引用、gap analysis、图遍历和 MCP 接口。
- 保持 Talent-Agent repo 产物作为事实来源：event ledger、public case pages、private case pages、source refs 和 workflow output。
- 在真实 pilot 证明运营价值之前，只把 GBrain 当作可重建的 derived index。
- 保持 JD 交付可靠性：GBrain 绝不能阻断本地推荐、飞书发布、BOSS/Maimai workflow 或 `data/talent.db` 操作。

## 当前 Talent-Agent 实现

- Repo 产物已经存在：`data/second-brain/events.jsonl`、`docs/second-brain/cases/`、`data/second-brain/private-cases/`，以及 JD run 的 `second-brain/` 输出。
- `scripts/second_brain_gbrain.py` 当前会导出 zip bundle，并在存在二进制时调用 `gbrain import <bundle> --brain <name>`。
- `scripts/second_brain_query.py` 主要使用本地 public case fallback；只有调用方传入 `gbrain_results` 时才会把状态标记为 `gbrain`。
- `requirements.txt` 没有 `grain` 或 `gbrain` package 依赖。
- 当前测试只覆盖缺失二进制 fallback 和 zip bundle 创建，不覆盖真实 GBrain 行为。

## 已核对的上游事实

核对日期：2026-06-12

- `https://github.com/garrytan/gbrain`
- `https://github.com/garrytan/gbrain/blob/master/INSTALL_FOR_AGENTS.md`
- `https://github.com/garrytan/gbrain/blob/master/docs/tutorials/connect-coding-agent.md`
- `https://github.com/garrytan/gbrain/blob/master/docs/INSTALL.md`

观察到的上游形态：

- GBrain 是 Bun + TypeScript CLI，通过 `bun install -g github:garrytan/gbrain` 安装。
- 本地 setup 可使用 `gbrain init`，或使用 `gbrain init --pglite` 初始化 embedded local brain。
- Markdown 文件夹可通过 `gbrain import ~/notes/` 导入。
- Agent 连接使用 `gbrain serve` 作为 MCP stdio server；文档也描述了 remote HTTP MCP。
- CLI 查询通过 `gbrain search` 描述；面向 agent 的 synthesized answers 通过 MCP 上的 `query` 描述；部分文档也提到 `gbrain query`。
- 关键词搜索不严格要求 API key，但 embedding/reranking/synthesis 质量依赖 provider keys 和 search mode。
- Installer guide 明确要求不要静默接受默认 search mode；operator 必须确认模式，因为它涉及成本和质量取舍。

对 Talent-Agent 的含义：当前 zip import wrapper 很可能是错误抽象。更安全的 adapter 形态是导出脱敏后的 Markdown source tree，把该 tree import/sync 到 GBrain，再通过已验证的 CLI/MCP 命令查询，并保留本地 fallback。

## 可复用能力

| 能力 | 上游证据 | Talent-Agent 用途 | 采用状态 |
| --- | --- | --- | --- |
| Local PGLite brain | README / install guide / coding-agent tutorial | 隔离本地 pilot | 未验证 |
| Markdown import | coding-agent tutorial | 导入 redacted public case pages 和 event summaries | 未验证 |
| Search | README / coding-agent tutorial | 原始历史校准检索 | 未验证 |
| Query/synthesis | README / MCP protocol docs | 带引用的校准建议和缺口说明 | 未验证 |
| MCP server | install docs / coding-agent tutorial | 可选 Codex/agent memory tool | 后续 |
| Search mode controls | install guide | 防止意外成本 | 必须门禁 |
| Company-brain permissions | README / tutorials | 未来可能用于共享/团队记忆 | 后续 |
| Graph traversal / gap analysis | README claims | 更丰富的交付后学习 | 未验证 |

## 风险

- GBrain 仍年轻且变化快；命令名和数据模型可能漂移。
- Bun/global install 和 postinstall migrations 可能失败；上游文档提到 migration recovery。
- 真实价值可能需要 embedding provider keys、reranker keys 或 model keys。
- 如果静默接受 search mode 默认值，可能产生意外成本。
- 在 access policy 明确前导入 private case pages，会违反 Talent-Agent 数据边界。
- GBrain 可能很适合 Markdown-first 的个人/团队记忆，但对 JD delivery P0 仍可能过宽或运营负担过重。
- 如果 adapter 继续围绕 zip 构建，我们可能是在错误假设上继续开发，而不是贴合上游现实。

## Pilot 验收标准

只有同时满足以下条件，pilot 才算通过：

- 安装成功，或明确 blocker 已用版本/error 证据记录。
- 捕获 `gbrain doctor --json` 或等价健康检查输出。
- 脱敏后的 Talent-Agent source tree 可导入，且不包含 private case data。
- 至少运行 3 个 calibration queries；如果无法运行，必须记录 blocker。
- 评估 query 输出的 source/citation 质量、gap analysis 质量和可执行性。
- GBrain 缺失时，本地 fallback 仍可用且有测试覆盖。
- 采用决策必须是以下之一：
  - `adopt_primary_index`：GBrain 成为优先的可选 index/synthesis 路径。
  - `keep_optional_adapter`：GBrain 保持手工/可选，本地 fallback 仍为主路径。
  - `reject_for_now`：冻结或移除 GBrain adapter 工作，并记录原因。

## 建议 Pilot Corpus

只使用 public 或 redacted source：

- `docs/second-brain/cases/*.md`
- 从 `data/second-brain/events.jsonl` 派生的 public summaries
- `docs/superpowers/specs/*gbrain*` 下的设计文档
- 不包含 `data/second-brain/private-cases/`
- 不包含 `data/talent.db`
- 不包含 campaign raw details、profile URLs、contact details、cookies 或 tokens

## 初始建议

继续推进 pilot，但保持 GBrain 可选。在 pilot 证明它能比当前本地 fallback 返回更好的历史校准，并且具备可靠 source references 之前，不要把它更深地接入 JD delivery。

下一个决策门禁是安装授权。如果 GBrain 已安装，就在隔离 `HOME` 中运行 smoke test。如果缺失，则在全局安装 Bun 或 GBrain 前先征求确认。

## 本地 Smoke 结果

- `bun --version`：`1.3.14`
- `gbrain --version`：`gbrain 0.42.40.0`
- 安装方式：`curl -fsSL https://bun.sh/install | bash`，然后 `bun install -g github:garrytan/gbrain`
- 安装说明：Bun 安装到 `~/.bun/bin/bun`，并把 `~/.bun/bin` 加入 `~/.zshrc`；GBrain 通过 Bun 全局安装。
- Bun 安装警告：一个 postinstall script 被 Bun 阻止；GBrain CLI 仍可执行。
- 隔离 smoke home：`artifacts/gbrain-pilot/smoke/home`
- `gbrain init --pglite`：因缺少 embedding provider 失败，并建议使用 `--no-embedding`；这确认上游现在对 embedding setup 有门禁。
- `gbrain init --pglite --no-embedding`：通过；在隔离 smoke home 下创建了本地 PGLite brain。
- Init 检测到 `ANTHROPIC_API_KEY`，并为 expansion/chat 选择 Anthropic models，但 embedding setup 仍 deferred。
- Schema migration：schema version 1 初始化到 115，应用了 110 个 migrations。
- `gbrain doctor --json`：可成功解析；状态为 `warnings`。
- Doctor 摘要：共 76 项检查，69 项 `ok`，7 项 `warn`。
- Doctor warnings：retrieval-reflex policy skill 未安装、pgvector check 不可用、尚无 embeddings、JSONB integrity check 不可用、configured embedding model 缺少 ZeroEntropy key、zero takes，以及存在可用的 schema pack successor。
- `gbrain stats`：在 empty brain 上通过；`Pages=0`、`Chunks=0`、`Embedded=0`、`Links=0`、`Tags=0`、`Timeline=0`。
- Search mode：由于未配置 OpenAI key，GBrain 暂设为 `conservative`。上游 installer 明确要求 operator 在继续 search mode 变更前确认。

Smoke-test 结论：本地 GBrain 可在没有 embedding keys 的情况下安装，并在隔离 PGLite home 中初始化；这足以继续做低成本 import/search pilot。下一个门禁是 search mode 选择；在 operator 确认前，不要导入 Talent-Agent 产物。
