# 企业 / Agent 第二大脑 GitHub 项目横向对比

日期：2026-06-09
范围：推荐 GitHub 上适合作为企业 / agent 第二大脑的高星项目，重点评估内容冷启动、自主迭代、企业落地和与 `talent-agent` 的适配。
结论：如果只选一个短期试点，不建议直接从通用向量库或聊天 UI 开始。建议按目标拆分：

- 最快业务冷启动：`Mintplex-Labs/anything-llm` 或 `onyx-dot-app/onyx`。
- 最像“agent 长期记忆层”：`mem0ai/mem0`、`supermemoryai/supermemory`、`getzep/graphiti`。
- 最像 `gbrain` 的 agent-owned company brain：`garrytan/gbrain`，可补充观察 `huytieu/COG-second-brain`。
- 最适合沉淀猎头业务关系图谱：`getzep/graphiti` 或 `topoteretes/cognee`。
- 最适合从零搭自定义 RAG/评估链路：`run-llama/llama_index`、`deepset-ai/haystack`、`microsoft/graphrag`。

## 1. 快照与分层

GitHub 元数据来自本轮 GitHub API / repo README 抓取。stars 是点位数据，只用于粗略判断社区热度，不代表企业可用性。

| 项目 | Stars | 定位 | 许可证 | 直接适配度 | 说明 |
|---|---:|---|---|---|---|
| `open-webui/open-webui` | 140,639 | AI Chat UI + RAG | 未声明 | 中 | 高星、易用，但更像统一 AI 门户，不是第二大脑核心。 |
| `langchain-ai/langchain` | 138,829 | Agent/RAG 工程平台 | MIT | 中 | 生态最大，但太底层，不直接解决知识冷启动和长期记忆治理。 |
| `Mintplex-Labs/anything-llm` | 61,253 | 本地优先知识库 + agents | MIT | 高 | 最适合快速搭顾问知识库 PoC。 |
| `mem0ai/mem0` | 58,060 | AI agent 通用记忆层 | Apache-2.0 | 高 | 适合嵌入 agent，弱在企业内容冷启动。 |
| `FlowiseAI/Flowise` | 53,430 | 可视化 agent/RAG builder | 未声明 | 中 | 适合原型编排，不适合当事实源。 |
| `run-llama/llama_index` | 50,003 | Document agent / RAG 框架 | MIT | 中高 | 强在 ingestion 和自定义 pipeline，需开发集成。 |
| `milvus-io/milvus` | 44,682 | 向量数据库 | Apache-2.0 | 低 | 基础设施，不是第二大脑。 |
| `QuivrHQ/quivr` | 39,172 | RAG app / SDK | 未声明 | 中 | 历史知名，最近活跃度弱于其他选择。 |
| `khoj-ai/khoj` | 35,001 | 个人 AI second brain | AGPL-3.0 | 中高 | 个人到团队场景好，企业商用需注意 AGPL。 |
| `langchain-ai/langgraph` | 34,181 | Resilient agents | MIT | 中 | 适合 agent 状态机，不是知识库产品。 |
| `microsoft/graphrag` | 33,563 | GraphRAG pipeline | MIT | 中 | 适合离线图谱化分析，不是实时 agent memory。 |
| `qdrant/qdrant` | 31,923 | 向量数据库 | Apache-2.0 | 低 | 基础设施。 |
| `onyx-dot-app/onyx` | 30,078 | 企业 AI search / RAG 平台 | 未声明 | 高 | 连接器和企业部署强，适合公司知识库冷启动。 |
| `chroma-core/chroma` | 28,282 | AI search infra | Apache-2.0 | 低 | 本地开发友好，但不是第二大脑。 |
| `microsoft/semantic-kernel` | 28,079 | Agent SDK | MIT | 中 | 微软生态强，需自建知识层。 |
| `getzep/graphiti` | 27,178 | Temporal context graph | Apache-2.0 | 高 | 非常适合“客户-JD-候选人-反馈”关系记忆。 |
| `deepset-ai/haystack` | 25,494 | RAG/agent orchestration | Apache-2.0 | 中高 | 生产 RAG pipeline 强，业务产品层需要自建。 |
| `supermemoryai/supermemory` | 约 22.7k | Memory API / connector memory | 开源仓库 | 高 | 内容冷启动和 MCP 记忆强，需评估云/自托管边界。 |
| `garrytan/gbrain` | 21,645 | Agent/company brain | MIT | 高 | 最贴近 agent-owned brain 和技能自迭代。 |
| `topoteretes/cognee` | 约 17.5k | AI memory control plane / graph | Apache-2.0 | 中高 | 强在 ECL/图谱化记忆，适合做业务关系图谱层。 |
| `getzep/zep` | 4,650 | Zep examples/integrations | Apache-2.0 | 中 | 更像 Zep 生态示例，核心图谱能力看 Graphiti/Zep Cloud。 |

## 2. 推荐短名单

### 2.1 第一优先级：AnythingLLM

适合目标：快速把已有材料变成顾问可用知识库。

优势：

- 本地优先，业务 PoC 快。
- workspace 概念天然适合按客户、JD、团队、行业分知识域。
- 支持文档、网页、GitHub、PDF、DOCX、YouTube 等冷启动材料。
- 有 workspace agents、scheduled tasks、intelligent tool selection、MCP 相关能力。
- 企业要素比个人工具更完整，例如 SSO、权限、Docker/self-host。

短板：

- 它更像“企业知识库 + agent 工作台”，不是严格意义的长期记忆算法。
- 自主迭代能力偏 workflow/任务调度，不是自动改 skill 或自动优化检索策略。

对 `talent-agent` 的建议：

- 可作为 P0 顾问知识库门户：导入 `docs/research/`、`docs/manual/`、`tasks/archive/`、JD delivery 报告摘要、campaign final report。
- 不接 `data/talent.db` 原始候选人明细；只导入脱敏 case page。

### 2.2 第一优先级：Onyx

适合目标：企业知识库冷启动、权限、连接器、RAG search。

优势：

- README 明确定位为 open source AI platform。
- 支持 50+ indexing connectors，适合从 Feishu 之外的企业系统冷启动。
- 有 hybrid index、Agentic RAG、Actions & MCP、企业部署模式。
- 更接近企业知识搜索平台，适合多人团队。

短板：

- 对 agent 长期记忆、个体顾问偏好、跨任务经验沉淀的模型不如 mem0 / Graphiti / gbrain。
- 许可证显示未声明，需要商用前单独审查。

对 `talent-agent` 的建议：

- 如果你要做“猎头公司内部知识搜索平台”，Onyx 比 gbrain 更像企业产品底座。
- 如果你要做“每个 agent 和顾问都有长期记忆”，Onyx 不是最核心选择。

### 2.3 第一优先级：mem0

适合目标：把长期记忆嵌入 agent / workflow。

优势：

- 高星、Apache-2.0，定位清晰：Universal memory layer for AI Agents。
- README 显示支持 user / session / agent 多层记忆。
- 近期强调 multi-signal retrieval，包括 semantic、BM25、entity matching。
- 有 benchmark 和 open-sourced evaluation framework，适合严肃评估记忆质量。
- 与 agent-generated facts 的结合，比普通 RAG 更贴近“执行后沉淀经验”。

短板：

- 内容冷启动不是强项；它不是 Onyx/AnythingLLM 那种企业连接器平台。
- 若直接把 `talent-agent` 大量报告倒进去，必须先设计记忆 schema，否则会变成无边界 memory pile。

对 `talent-agent` 的建议：

- 适合嵌入 workflow：例如 `jd-talent-delivery` 每次交付后，把“客户反馈/评分误差/推荐成功原因”作为记忆写入。
- 不适合作为公司知识库门户的第一入口。

### 2.4 第一优先级：Graphiti

适合目标：构建动态、时序、可查询的业务关系图谱。

优势：

- 直接面向 AI agents 的 temporal context graph。
- 强调将 structured / unstructured enterprise data / external information 组织成 coherent queryable graph。
- 支持 MCP server，适合 Claude/Cursor/Codex 等 agent 客户端。
- 适合动态上下文，而不是静态文档总结。

短板：

- 冷启动连接器不是最强；需要你先定义数据进入方式。
- 业务 schema 设计成本高，但这也是它的价值所在。

对 `talent-agent` 的建议：

- 很适合做“客户-JD-候选人-反馈-渠道-交付结果”的事实图谱。
- 例如：客户 A 多次拒绝“算法研究强但工程落地弱”的候选人，Graphiti 可以把这个偏好作为随时间演化的上下文，而不是一次性文本片段。

### 2.5 第一优先级：Supermemory

适合目标：跨工具、跨来源的 memory hub。

优势：

- 官方站点强调 Slack、Notion、Drive、Gmail、GitHub、S3 和 custom sources 自动同步。
- 支持 MCP，面向 Claude、Cursor、Codex 等 agent 工具。
- 提供 memory graph、文件索引、实时 profile 等能力，冷启动很强。

短板：

- 需要仔细评估自托管、云服务、API key、数据出境和企业隐私边界。
- 对你的猎头数据来说，不能直接接入未脱敏候选人和客户原始资料。

对 `talent-agent` 的建议：

- 若接受云/服务边界，它是最强“冷启动连接器 + agent memory”候选。
- 若必须本地只读，优先级低于 AnythingLLM / gbrain / Graphiti。

## 3. 次优但值得观察

### Khoj

定位非常接近“个人 AI second brain”，支持 docs/web/custom agents/scheduled automations/deep research，并可 self-host。它适合个人顾问或小团队，但 AGPL-3.0 对商用集成需要谨慎。若只是内部自托管试点，可以评估；若要嵌入商业产品，先做法务确认。

### Cognee

`topoteretes/cognee` 是 memory control plane for AI agents，强调 graph-RAG、cognitive memory、Neo4j/graph database。它比 Onyx/AnythingLLM 更偏“记忆建模”，比 Graphiti 更像一套可编程 memory pipeline。适合做候选人/客户/反馈的图谱化抽取，但不是最快让顾问可用的界面型产品。

### GBrain

上一轮已单独分析。它不是最强企业连接器平台，但在 agent-owned brain、MCP、company brain、skillopt、自主技能优化方面很强。对你当前 Codex/agent 工作流，`gbrain` 的心智模型最接近：agent 负责安装、查询、沉淀、优化。

### COG-second-brain

不是高星主流项目，但概念值得借鉴：Markdown + Git + Obsidian + agent skills/workers，自称 self-evolving second brain。对你的 `tasks/`、`docs/`、`agents/skills/` 架构很有启发：不一定要引入数据库，某些顾问知识完全可以先以 Markdown case page + Git 版本化沉淀。

## 4. 不建议作为“第二大脑主项目”的高星项目

### Open WebUI

优点是高星、易部署、AI 门户能力强、RAG/知识库/工具调用/MCP 生态活跃。问题是它首先是 Chat UI，不是组织记忆层。适合作为用户入口，不适合作为候选人/客户/反馈事实源。

### LlamaIndex / Haystack / LangChain / Semantic Kernel / LangGraph

这些是强工程框架，不是第二大脑产品。适合你后续需要自研 ingestion、RAG、评估、workflow orchestration 时选用。若目标是“马上让顾问用起来”，它们不是第一站。

### Chroma / Qdrant / Weaviate / Milvus

这些是向量检索基础设施。它们能支撑第二大脑，但不负责：

- 哪些内容该被记住。
- 内容如何脱敏。
- 用户/团队/客户权限。
- 反馈如何变成可复用经验。
- 记忆冲突、过期、版本和审计。

因此不应该被当成第二大脑竞品，只能作为底层组件。

## 5. 横向评分

评分是针对 `talent-agent` 和猎头企业 AI 转型场景，不是通用软件排名。

| 项目 | 内容冷启动 | Agent 记忆 | 图谱/关系 | 自主迭代 | 企业治理 | 推荐动作 |
|---|---:|---:|---:|---:|---:|---|
| Supermemory | 5 | 5 | 4 | 4 | 3 | 若能接受云/API，做连接器 PoC。 |
| AnythingLLM | 5 | 3 | 2 | 3 | 4 | 本地顾问知识库 P0 首选。 |
| Onyx | 5 | 2 | 2 | 2 | 5 | 企业知识搜索/连接器首选。 |
| mem0 | 2 | 5 | 3 | 4 | 3 | 嵌入 agent workflow 做长期记忆。 |
| Graphiti | 2 | 5 | 5 | 3 | 3 | 做业务关系图谱和时序上下文。 |
| Cognee | 3 | 4 | 5 | 3 | 3 | 做图谱化 memory pipeline。 |
| gbrain | 3 | 4 | 4 | 5 | 3 | 做 agent-owned company brain 和 skillopt。 |
| Khoj | 4 | 3 | 2 | 3 | 3 | 个人顾问 second brain / 小团队试点。 |
| LlamaIndex | 4 | 2 | 3 | 4 | 3 | 自研 RAG/评估 pipeline。 |
| Haystack | 3 | 2 | 2 | 4 | 4 | 生产级 RAG pipeline。 |
| GraphRAG | 2 | 1 | 5 | 3 | 2 | 离线图谱总结和知识发现。 |
| Open WebUI | 4 | 2 | 1 | 2 | 4 | 做 AI 门户，不做事实源。 |

## 6. 针对 talent-agent 的组合建议

### 方案 A：最快见业务价值

组合：AnythingLLM + 当前 `talent-agent` 文档/报告导出器。

做法：

1. 导出脱敏 Markdown case page：
   - JD delivery 摘要。
   - 客户反馈总结。
   - Campaign final report。
   - `tasks/lessons.md` 和相关归档。
2. 按客户/JD/行业建 workspace。
3. 让顾问用自然语言查询历史案例。

优点：最快让顾问感知“AI 赋能”。
缺点：长期记忆和关系推理有限。

### 方案 B：最适合 agent workflow

组合：gbrain + mem0。

做法：

1. `gbrain` 负责 repo/workflow/company brain、文档检索、skillopt。
2. `mem0` 负责 agent/user/session 级事实记忆。
3. 每次 JD delivery 后，把反馈解析结果和质量门禁总结写入 memory。

优点：最贴近 Codex/Claude agent 工作方式。
缺点：企业连接器和 UI 不如 AnythingLLM/Onyx。

### 方案 C：最适合猎头业务护城河

组合：Graphiti 或 Cognee + 当前 `talent-agent`。

做法：

1. 设计业务图谱 schema：
   - Client
   - JD
   - Candidate
   - SourceProfile
   - Campaign
   - Feedback
   - RejectionReason
   - DeliveryOutcome
2. 从 `feedback_note`、JD delivery、BOSS/Maimai campaign 汇总里抽取关系。
3. 查询客户偏好、岗位演化、候选人渠道证据和失败原因。

优点：最能沉淀猎头企业独有经验资产。
缺点：不是开箱即用，需要 schema 和导出器。

### 方案 D：企业知识平台

组合：Onyx + Graphiti。

做法：

1. Onyx 做企业知识搜索、权限、连接器。
2. Graphiti 做客户/JD/反馈/候选人关系记忆。
3. `talent-agent` 继续作为结构化事实源和执行 workflow。

优点：企业化最完整。
缺点：实施复杂度最高。

## 7. 推荐路线

我建议不要一次性选一个“万能第二大脑”。对你的场景，最稳妥是三阶段：

### 第 1 阶段：业务可见 PoC

用 AnythingLLM 或 Onyx 做只读知识库：

- 导入脱敏 Markdown。
- 不接 `data/talent.db` 原始库。
- 不接平台 raw payload。
- 验证 20 个顾问真实问题。

验收标准：

- 顾问能在 1-2 分钟内恢复某客户/JD/候选人批次上下文。
- 答案有可追溯来源。
- 没有敏感信息越界。

### 第 2 阶段：Agent 记忆试点

用 mem0 或 gbrain：

- 在 `jd-talent-delivery` 后写入“反馈总结 / 评分卡修正建议 / 交付质量结论”。
- 在下一次 JD intake 前读取历史校准。
- 不自动修改评分卡，只生成 `historical-calibration.md`。

验收标准：

- 新 JD 的评分卡人工修正次数下降。
- 反馈原因可跨 JD 聚合。
- 记忆有来源、时间、置信度和可删除机制。

### 第 3 阶段：业务关系图谱

用 Graphiti 或 Cognee：

- 建客户 / JD / 候选人 / 反馈 / 结果图谱。
- 支持问题：
  - “这个客户过去拒绝最多的原因是什么？”
  - “哪些候选人虽然当前 JD 不合适，但适合后续类似岗位？”
  - “BOSS 和脉脉证据冲突时，过去哪些信号更可靠？”

验收标准：

- 能解释关系和证据，而不是只返回相似文档。
- 能处理时间变化，例如客户偏好更新、候选人状态变化、岗位需求变更。

## 8. 最终建议

短期推荐：

1. `AnythingLLM`：最快冷启动、最容易让顾问用起来。
2. `gbrain`：最贴近你当前 agent / Codex 工作方式，适合 agent company brain。
3. `mem0`：最适合做 agent 运行时长期记忆层。
4. `Graphiti`：最适合做猎头业务关系图谱。
5. `Onyx`：如果你要企业级连接器、权限和知识搜索，应进入第一批 PoC。

暂不建议：

- 直接从 Chroma/Qdrant/Weaviate/Milvus 开始；它们只是底层检索。
- 直接从 LangChain/LlamaIndex/Haystack 开始做产品；除非你准备自研完整知识库。
- 把 Open WebUI 当第二大脑核心；它更适合作为 AI 门户。

对 `talent-agent` 的最优落地路径：

- P0：继续保留 `gbrain` 研究结论，同时用 AnythingLLM 或 Onyx 做顾问知识库冷启动对照。
- P1：在 `jd-talent-delivery` 前增加只读历史校准，候选技术为 `gbrain` 或 `mem0`。
- P2：把 `feedback_note` 解析结果导出为 case page，同时评估 Graphiti/Cognee 做关系图谱。
- P3：只有当 P0-P2 证明价值后，再考虑 Supermemory 这类跨系统 connector memory，且必须先解决候选人隐私、客户数据权限和云/本地边界。

## 9. 来源

- `garrytan/gbrain`：<https://github.com/garrytan/gbrain>
- `mem0ai/mem0`：<https://github.com/mem0ai/mem0>
- `getzep/graphiti`：<https://github.com/getzep/graphiti>
- `getzep/zep`：<https://github.com/getzep/zep>
- `khoj-ai/khoj`：<https://github.com/khoj-ai/khoj>
- `Mintplex-Labs/anything-llm`：<https://github.com/Mintplex-Labs/anything-llm>
- `onyx-dot-app/onyx`：<https://github.com/onyx-dot-app/onyx>
- `QuivrHQ/quivr`：<https://github.com/QuivrHQ/quivr>
- `open-webui/open-webui`：<https://github.com/open-webui/open-webui>
- `run-llama/llama_index`：<https://github.com/run-llama/llama_index>
- `microsoft/graphrag`：<https://github.com/microsoft/graphrag>
- `deepset-ai/haystack`：<https://github.com/deepset-ai/haystack>
- `FlowiseAI/Flowise`：<https://github.com/FlowiseAI/Flowise>
- `topoteretes/cognee`：<https://github.com/topoteretes/cognee>
- `supermemoryai/supermemory`：<https://github.com/supermemoryai/supermemory>
- `huytieu/COG-second-brain`：<https://github.com/huytieu/COG-second-brain>
- `doobidoo/mcp-memory-service`：<https://github.com/doobidoo/mcp-memory-service>
