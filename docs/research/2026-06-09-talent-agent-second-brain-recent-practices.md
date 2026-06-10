# Talent-Agent 第二大脑近 30 天公开讨论与落地建议

调研日期：2026-06-09
覆盖窗口：2026-05-10 至 2026-06-09，兼收少量 2026 年内的基础资料作为背景
目标：为 Talent-Agent 增加“第二大脑”，支撑行业洞察、岗位/人选匹配判断、业务反馈驱动迭代。

## 1. 结论先行

建议把 Talent-Agent 的第二大脑定义为“可审计的业务经验系统”，不是简单的向量库或聊天记录缓存。

最适合当前仓库的路线：

1. 先做 append-only 业务经验账本：记录 JD、候选人、推荐批次、评分理由、业务反馈、后续结果、人工确认和失败原因。
2. 再做三层记忆：语义记忆沉淀稳定事实，情节记忆沉淀具体执行与结果，程序记忆沉淀 workflow/scorecard/提示词/策略。
3. 匹配判断采用“混合检索 + 技能/行业图谱 + 确定性因子评分 + 受限 LLM 解释”，不要让 LLM 直接黑盒给最终排序。
4. 反馈闭环先利用现有 `feedback_note` 契约，把“为什么不合适/为什么认可”转为可统计的校准信号；低置信度和冲突记忆必须进 review queue。
5. 开源底座优先评估 Graphiti/Zep、mem0、Cognee、LangMem、Letta、MemOS；招聘匹配专用开源项目多为 demo，适合借鉴范式，不适合作为生产依赖。

## 2. 调研方法与数据边界

本次使用 `last30days` 技能运行近 30 天研究脚本；当前环境未配置 Reddit/X API key，因此脚本进入 web-only 模式。随后用 WebSearch 补充公开网页、论文、GitHub 和社区讨论。

限制：

- 没有 X/Twitter 真实互动指标。
- Reddit 仅来自公开网页检索，不是 API 全量抓取。
- Reddit 链接可由公开搜索发现，但自动链接校验被 reddit.com 返回 403 拦截；报告保留为社区讨论线索，不作为唯一证据。
- 严格近 30 天内，agent memory 资料较多；招聘匹配资料相对少，很多关键论文和项目发布于 2026 年 3-4 月，因此作为背景引用。
- GitHub star/fork 数据通过 `gh repo view` 于 2026-06-09 获取，后续会变化。

## 3. 近 30 天公开讨论信号

### 3.1 Agent memory 的主流观点正在从“召回”转向“治理”

近 30 天讨论最集中的点是：向量库只解决“相似内容召回”，不能解决事实是否过期、来源是否可靠、冲突如何处理、哪条旧事实影响了当前行动。

几个强信号：

- CloudAI 2026-06-07 的文章把问题概括为“agent memory is just a vector DB”的生产缺陷：向量召回在成本/延迟上有效，但缺少 staleness、retention、temporal reasoning 和 multi-hop 处理能力。
- Reddit/LangChain 近期讨论反复提到：生产 agent 需要 provenance、correction、deletion、time-travel/debug，而不是只把聊天记录塞进 store。
- LangChain Deep Agents 文档把长期记忆明确拆成 memory files、backend、agent/user scope、背景 consolidation，并把 skills 视为 procedural memory。

对 Talent-Agent 的含义：第二大脑不能只接一个 `candidate_notes` 向量表。需要从第一天设计来源、时间、版本、人工确认、删除/纠错、证据回放。

### 3.2 动态知识图谱重新变得重要

Graphiti/Zep、Cognee、MemOS、A-Mem 等项目都在强调一件事：agent 需要理解“关系随时间变化”。招聘场景非常贴合这个方向：

- 候选人的当前职级、求职意愿、地域偏好、薪资、可沟通状态会变化。
- 公司组织架构、业务线、融资/裁员/招聘策略会变化。
- 猎头顾问对某类 JD 的判断会随业务反馈变化。
- 同一个人选在不同客户、不同阶段的匹配结论可能不同。

Graphiti 官方 README 强调 temporal context graph：事实有 validity window，旧事实被 supersede 而不是删除，并保留 episode provenance。这非常适合 Talent-Agent 的“候选人画像 + 客户/JD/行业上下文 + 交付结果”。

### 3.3 招聘匹配最佳实践倾向于“因子化 + 可解释 + 证据约束”

JobMatchAI 这类 2026 年论文/原型给出的方向比较明确：

- 先用 BM25/关键词召回保留强信号词。
- 再用 embedding 做语义泛化，解决技能同义词、非线性经历、隐性能力。
- 用技能知识图谱处理技能邻近、行业上下游、职能迁移。
- 用白盒 reranker 计算 skill fit、experience、location、salary、company preference 等因子分。
- LLM 只负责“基于已计算分数和证据生成解释”，不直接决定分数。

对 Talent-Agent 的含义：现有 JD delivery scorecard 可以升级为“可校准因子评分系统”。第二大脑提供行业/公司/技能关系和过往反馈证据，但最终匹配分要能拆解、能复盘、能被业务反馈校准。

### 3.4 反馈闭环的关键不是“自动学习”，而是“可控地写入经验”

AdMem 2026-06-05 提出 actor/memory/critic 多 agent 架构，用 reward 标注、合并和剪枝管理长期记忆。LongMemEval-V2 2026-05-12 则强调 memory system 要学会环境中的 workflow knowledge、gotchas、premise awareness，而不是只会答用户历史。

Talent-Agent 的可落地解释：

- 业务反馈不是直接覆盖候选人事实，而是生成“经验事件”。
- 经验事件要区分事实、判断、偏好、结果、纠错。
- 只有通过置信度、来源和人工 review 的反馈才能进入可影响排序的记忆层。
- 低置信度反馈只能进入待审队列或分析层，不能自动污染候选人画像。

### 3.5 HR/招聘 AI 的合规压力正在上升

欧洲 Commission 2026-05-19 发布 high-risk AI classification draft guidelines，明确支持 provider/deployer 判断系统是否高风险。欧盟 AI Act 页面也说明，在 2026-05-07 political agreement 后，employment 等 Annex III high-risk 领域的规则计划自 2027-12-02 适用。

这不意味着 Talent-Agent 现在要做完整合规系统，但第二大脑的设计必须预留：

- 人工监督和最终决策边界。
- 评分和推荐理由可解释。
- 数据来源、更新时间、处理过程可追溯。
- 对候选人敏感属性、歧视性推断、不可证明结论有防护。
- 可以删除、纠错、禁用某条记忆。

## 4. 最佳实践提炼

### 4.1 记忆类型不要混在一起

建议按用途拆分：

| 类型 | Talent-Agent 例子 | 写入来源 | 使用方式 |
| --- | --- | --- | --- |
| 语义记忆 Semantic | 公司业务线、岗位技能树、候选人稳定经历、行业术语 | 简历、公开资料、人工确认、研究笔记 | 匹配召回、解释、行业洞察 |
| 情节记忆 Episodic | 某次 JD 交付、候选人沟通、推荐被拒原因、客户反馈 | campaign、Feishu 交付、`feedback_note`、BOSS/脉脉动作日志 | 复盘、校准、避免重复动作 |
| 程序记忆 Procedural | 哪类 JD 如何打分、哪些 workflow 易失败、提示词/规则更新 | tests、lessons、workflow review、业务复盘 | 改进 agent 行为和流程 |
| 行动账本 Action Ledger | 已联系、已推送、已确认、已被用户授权/拒绝 | agent tool call、人工审批、外部系统回执 | 防重复触达、可审计执行 |
| 世界状态 World/Market | 行业变化、公司动态、技术趋势、竞品招聘动向 | 公开新闻、研究报告、定期采集 | 行业洞察和候选人/JD contextualization |

关键原则：语义记忆回答“现在相信什么”，情节记忆回答“当时发生什么”，程序记忆回答“以后应该怎么做”，行动账本回答“已经做过什么”。

### 4.2 写入比检索更重要

公开讨论里反复出现一个生产经验：坏记忆比没记忆更危险。

写入策略建议：

- 每条记忆都带 `source_type`、`source_uri`、`observed_at`、`ingested_at`、`confidence`、`schema_version`。
- 区分 `fact`、`inference`、`preference`、`feedback`、`policy`、`action`。
- 对矛盾信息不覆盖，写 supersedes / invalidates 关系。
- 业务反馈只先写入 episodic event，再由离线 consolidation 产出可复用模式。
- 对 PII 和敏感推断设置 memory denylist。

### 4.3 检索要做“当前任务装配”，不是全量上下文注入

推荐 retrieval assembly：

1. 从 JD 和当前任务生成检索意图。
2. 拉取少量高置信语义记忆：行业、公司、技能、候选人稳定事实。
3. 拉取相关情节记忆：同类 JD 的成功/失败、客户偏好、过去拒绝原因。
4. 拉取程序记忆：适用 scorecard、workflow gotchas、合规约束。
5. 只把证据摘要和链接注入模型，原始证据留在可追溯存储中。

### 4.4 评分系统要可校准

Talent-Agent 不应让 LLM 直接输出“推荐/不推荐”。建议因子化：

- JD hard constraints：地域、年限、职级、必备技能、行业/公司池。
- Skill fit：技能命中、邻近技能、缺口、证据强度。
- Trajectory fit：成长路径、职能迁移、业务复杂度。
- Context fit：客户偏好、团队阶段、公司/行业背景。
- Risk flags：跳槽频率、信息缺口、敏感/不应使用信息、来源不可靠。
- Feedback calibration：该 JD/客户/行业下过往 accepted/bad/reject 的分布。

LLM 的角色：生成结构化解释、补充疑点、提出下一步验证问题；不能独立改写硬约束和最终排序。

### 4.5 评估指标要贴业务闭环

建议沿用并扩展现有 JD delivery feedback 指标：

- `accepted_at_10` / `accepted_at_30`
- `bad_at_10`
- reject reason distribution
- grade acceptance rate
- feedback parse confidence
- review queue rate
- duplicate outreach avoided
- stale memory retrieval rate
- evidence coverage：推荐理由中可追溯证据占比
- calibration delta：某类反馈进入记忆后，下一批同类 JD 的命中率是否改善

## 5. 开源项目短名单

### 5.1 可作为第二大脑底座的通用项目

GitHub 数据采集时间：2026-06-09。

| 项目 | 当前信号 | 适合 Talent-Agent 的位置 | 主要风险 |
| --- | ---: | --- | --- |
| mem0 (`mem0ai/mem0`) | 58,085 stars / 6,668 forks / Apache-2.0 | 通用语义记忆 API，候选人/用户偏好/会话摘要 | 偏 memory layer，不天然解决业务时序图谱和可审计 action ledger |
| Graphiti (`getzep/graphiti`) | 27,192 stars / 2,718 forks / Apache-2.0 | 时间感知业务关系图谱：候选人-公司-JD-反馈-证据 | 需要 Neo4j/图谱建模和运维；周边治理需自建 |
| supermemory (`supermemoryai/supermemory`) | 26,224 stars / 2,287 forks / MIT | 快速 memory API/app，适合原型和个人知识层 | 招聘 PII/自托管/治理边界需验证 |
| Letta (`letta-ai/letta`) | 23,218 stars / 2,472 forks / Apache-2.0 | 构建 stateful agents，可借鉴 agent memory/runtime 模式 | 比 memory library 更重，可能和现有 runtime-neutral 架构冲突 |
| Cognee (`topoteretes/cognee`) | 17,733 stars / 1,879 forks / Apache-2.0 | 自托管 KG memory，适合长期知识组织 | 与 Graphiti 定位重叠，需要 POC 比较 |
| MemOS (`MemTensor/MemOS`) | 9,677 stars / 883 forks / Apache-2.0 | 本地优先、混合检索、反馈驱动记忆，适合观察 | 项目较新，生态/稳定性要验证 |
| LangMem (`langchain-ai/langmem`) | 1,495 stars / 170 forks / MIT | 如果未来采用 LangGraph，可作为官方 memory 抽象 | Python 生态绑定较强，当前仓库未必需要引入 |

推荐判断：

- P0/P1 优先看 Graphiti + 自建 action ledger，因为 Talent-Agent 的业务价值更依赖“关系、时间、证据和反馈”。
- mem0 可作为简单语义记忆和用户/候选人偏好层，但不应单独承担第二大脑。
- Cognee 适合作为 Graphiti 的自托管替代评估。
- Letta/LangMem 更适合作为架构参考，除非后续决定迁移 agent runtime。
- MemOS 值得观察它的本地插件、反馈驱动 retrieval 和 memory viewer，但不建议第一阶段重依赖。

### 5.2 招聘匹配相关开源/原型

| 项目/资料 | 信号 | 借鉴点 | 生产依赖判断 |
| --- | --- | --- | --- |
| JobMatchAI paper/prototype | 2026-03，hybrid retrieval + KG + deterministic scoring + LLM explanation | 匹配架构范式非常接近 Talent-Agent | 借鉴设计，不直接依赖 |
| `abram04/Hiring-Agent-Platform` | 1 star，2026-06-05 更新，LangGraph + pgvector + Gemini | 招聘 agent demo，可看数据流 | 不适合作底座 |
| `greatvivek11/skillspace` | 0 star，sentence-transformers + FAISS + skill-gap | skill gap explainability demo | 不适合作底座 |
| `Pedagogue-Systems/ai-matching-consistency-eval` | 1 star，MIT，resume-job consistency eval | 借鉴匹配一致性评估 | 可借鉴测试思想 |
| `shubhamgupta407/Gitanalyze` | 2 stars，GitHub profile evaluation | 技术候选人 GitHub 画像分析 | 只适合局部参考 |

判断：招聘专用开源项目成熟度不足。Talent-Agent 应优先复用通用 memory/KG 组件，自建招聘领域 schema、scorecard 和评估闭环。

## 6. 对 Talent-Agent 的建议架构

### 6.1 建议新增核心概念

第二大脑可以拆成 5 个内部模块：

1. `ExperienceLedger`：append-only 事件账本。
2. `BusinessMemoryStore`：结构化语义/情节/程序记忆。
3. `TalentKnowledgeGraph`：候选人、公司、JD、技能、行业、反馈、证据的关系图谱。
4. `MemoryConsolidator`：离线合并、去重、冲突检测、过期处理、经验提炼。
5. `MatchingCalibrator`：把交付反馈转成 scorecard/权重/召回策略的改进建议。

### 6.2 最小数据模型草案

```text
experience_event
  id
  event_type                 # jd_created / candidate_matched / feedback_received / outreach_sent / review_override ...
  subject_type               # jd / candidate / company / campaign / workflow
  subject_id
  source_type                # talent_db / feishu / maimai / boss / manual / research / test
  source_uri
  observed_at
  ingested_at
  actor                      # agent / user / external_system
  payload_json
  confidence
  schema_version
  supersedes_event_id

memory_item
  id
  memory_type                # semantic / episodic / procedural / action / market
  entity_type
  entity_id
  statement
  evidence_event_ids
  validity_start
  validity_end
  confidence
  status                     # active / superseded / disputed / deleted / review_required
  source_hash
  embedding_ref
  graph_ref

matching_signal
  id
  jd_id
  candidate_id
  factor                     # skill_fit / trajectory_fit / context_fit / risk / feedback_calibration
  score
  evidence_memory_ids
  explanation
  model_version
  created_at
```

### 6.3 与现有仓库的衔接点

可直接承接的已有能力：

- `feedback_note`：业务只填自然语言反馈，规则优先、批量 LLM fallback、低置信进入 review queue。这是第二大脑最重要的早期训练信号。
- JD delivery scorecard：可升级为 factorized scoring，不要推倒重来。
- `tasks/lessons.md`、`memory/error-log.md`、workflow archive：可作为程序记忆来源。
- TalentDB：继续作为候选人事实库，不要把第二大脑做成替代主库。
- Campaign 输出和 Feishu readback：作为情节记忆和行动账本来源。

### 6.4 第一阶段不建议做的事

- 不建议先接全量公网行业新闻自动写库；容易噪声大、来源混乱。
- 不建议让 LLM 自动改 scorecard 权重；先产出 calibration suggestion，由人确认。
- 不建议把候选人的所有聊天/简历文本原样长期注入 prompt；需要摘要、证据引用和 PII 边界。
- 不建议把招聘专用低星 demo 当依赖；可读代码取模式。
- 不建议把“第二大脑”做成单一 vector table；后续会难以审计和纠错。

## 7. 分阶段路线

### P0：经验账本 + 反馈校准闭环

目标：先让 Agent 记得“做过什么、结果如何、业务为什么反馈好/坏”。

范围：

- 新增 append-only experience events。
- 将 JD delivery feedback summary、parse-review-queue、calibration-suggestions 统一映射到经验事件。
- 建立 `feedback_note -> reason_codes -> matching_signal` 的可追溯链路。
- 报告每次推荐时引用过去同类 JD 的正/负反馈分布。

验收：

- 能回答“这个推荐策略过去在哪些 JD 上失败过，失败原因是什么？”
- 能回答“某候选人是否已联系/已推送/被拒绝，来源是什么？”
- 能输出某个 scorecard 因子的历史校准建议。

### P1：业务关系图谱 POC

目标：验证 Graphiti/Cognee 或自建轻量图谱是否提升行业洞察和匹配解释。

范围：

- 图谱实体：Candidate、Company、JD、Skill、Industry、Campaign、FeedbackReason。
- 图谱边：has_skill、worked_at、similar_company、matched_for、rejected_for、accepted_for、requires_skill、supersedes。
- 支持 validity window 和 provenance。
- 只导入小范围已验证 campaign/JD 数据。

验收：

- 对同一 JD，能给出比纯 embedding 更清晰的“为什么这个候选人值得/不值得继续”的证据链。
- 能处理同一候选人状态变更，不把旧事实当当前事实。

### P2：行业洞察记忆

目标：让 Agent 能把行业/公司/岗位趋势接入匹配判断，但保持来源可控。

范围：

- 建立 curated research note schema。
- 每条行业洞察必须有来源、时间、适用行业/公司/岗位、置信度。
- 只在解释和扩展检索中使用，不直接作为硬性筛选。

验收：

- 对某 JD 输出“行业背景、人才稀缺点、候选人迁移路径、风险假设”。
- 能区分事实、推断和建议。

### P3：程序记忆与自我改进

目标：从业务执行反馈中持续改进 workflow 和 scorecard。

范围：

- 从 `tasks/lessons.md`、workflow review、test failures、用户纠正中生成 procedural memory。
- 每条程序记忆要可回滚、可禁用、可审查。
- calibration suggestion 只生成 PR/任务建议，不自动改业务策略。

验收：

- Agent 在同类任务中能主动引用历史 gotcha。
- 修改策略前能给出证据、影响范围和验证计划。

## 8. 风险清单

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 记忆污染 | 错误事实影响推荐 | append-only、review queue、confidence、supersede，不直接覆盖 |
| 隐性歧视 | 招聘场景高风险 | 禁用敏感属性推断，保留人类最终判断和理由审计 |
| 噪声增长 | 召回质量下降 | consolidation、recency/importance、分层存储、任务级装配 |
| 黑盒排序 | 业务无法信任 | 因子化评分、证据 ID、LLM 只解释不裁决 |
| 重复触达 | 业务风险和候选人体验差 | action ledger + approval record |
| 合规变化 | 未来接入客户系统时压力上升 | 从 P0 就保留 provenance、deletion/correction、human oversight |

## 9. 推荐的下一步

优先级最高的是 P0：经验账本 + 反馈校准闭环。它不依赖外部 memory 框架，能最大化复用现有 Talent-Agent 反馈能力，也能为后续 Graphiti/Cognee POC 提供干净数据。

建议下一份设计文档聚焦：

- `ExperienceLedger` schema 与 TalentDB 边界。
- 现有 JD feedback 产物如何映射为 experience events。
- 推荐排序时如何读取历史反馈校准信号。
- 低置信反馈和人工 review 的写入策略。
- P0 测试计划和回滚策略。

## 10. 参考资料

### 近 30 天与近期公开讨论

- European Commission, [Draft Commission guidelines on the classification of high-risk AI systems](https://digital-strategy.ec.europa.eu/en/library/draft-commission-guidelines-classification-high-risk-ai-systems), 2026-05-19.
- European Commission, [Commission seeks feedback on the draft guidelines for the classification of high-risk artificial intelligence systems](https://digital-strategy.ec.europa.eu/en/news/commission-seeks-feedback-draft-guidelines-classification-high-risk-artificial-intelligence-systems), 2026-05-19.
- European Commission, [AI Act implementation timeline](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai), updated 2026.
- arXiv, [LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues](https://arxiv.org/abs/2605.12493), submitted 2026-05-12.
- arXiv, [AdMem: Advanced Memory for Task-solving Agents](https://arxiv.org/abs/2606.06787), submitted 2026-06-05.
- CloudAI, [Agent Memory Is Just a Vector DB. That’s the Problem.](https://cloudai.pt/agent-memory-is-just-a-vector-db-thats-the-problem/), 2026-06-07.
- IJCOPE, [AI-Based Resume Screening and Job Matching System](https://ijcope.org/article/ai-based-resume-screening-and-job-matching-system/), published 2026-05-29.
- GitHub Topics, [resume-matching](https://github.com/topics/resume-matching), crawled 2026-06.
- Reddit / r/LangChain, [How do you handle agent working memory?](https://www.reddit.com/r/LangChain/comments/1tn184k/how_do_you_handle_agent_working_memory/), 2026-05-25.
- Reddit / r/LangChain, [For production agents, I’m starting to think workspace state matters more than chat memory](https://www.reddit.com/r/LangChain/comments/1tafflp/for_production_agents_im_starting_to_think/), 2026-05-11.
- Reddit / r/LangChain, [Persistent memory debug/auditability discussion](https://www.reddit.com/r/LangChain/comments/1tmlnef/heres_a_scenario_ive_run_into_twice_now_and_i/), 2026-05-24.

### 关键架构与项目资料

- LangChain Docs, [Deep Agents Memory](https://docs.langchain.com/oss/python/deepagents/memory).
- LangChain Docs, [Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory).
- GitHub, [getzep/graphiti](https://github.com/getzep/graphiti).
- GitHub, [mem0ai/mem0](https://github.com/mem0ai/mem0).
- GitHub, [topoteretes/cognee](https://github.com/topoteretes/cognee).
- GitHub, [letta-ai/letta](https://github.com/letta-ai/letta).
- GitHub, [MemTensor/MemOS](https://github.com/MemTensor/MemOS).
- GitHub, [langchain-ai/langmem](https://github.com/langchain-ai/langmem).
- GitHub, [supermemoryai/supermemory](https://github.com/supermemoryai/supermemory).
- The Commonplace, [JobMatchAI: Knowledge Graphs, Semantic Search and Explainable AI](https://commonplace.workforcefutures.net/paper/arxiv%3A2603.14558), 2026-03.
