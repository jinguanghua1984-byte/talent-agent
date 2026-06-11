# gbrain 第二大脑 P0 技术设计

日期：2026-06-12
状态：已通过 brainstorming 设计确认，待 implementation plan

## 1. 背景

`talent-agent` 当前已经有稳定的结构化事实源和业务 workflow：

- `data/talent.db` 保存候选人主数据和 source profiles。
- JD delivery run 目录保存岗位画像、scorecard、推荐结果、质量门禁、反馈和飞书交付产物。
- Campaign DB 保存脉脉、BOSS、猎聘等寻访过程中的阶段性事实和恢复状态。
- `agents/skills/` 与 `agents/workflows/` 是运行时中立的业务合同。
- `tasks/`、`docs/` 和 `agents/policies/` 保存任务记录、研究结论和安全边界。

本设计使用 `garrytan/gbrain` 构建 agent 第二大脑，但不让它取代上述事实源。P0 聚焦 JD 交付闭环：岗位分析、人岗匹配、推荐理由、顾问反馈和下一次校准。

## 2. 目标

P0 同时服务两个使用者：

- `talent-agent` workflow：在 JD delivery 前后读写长期记忆，生成历史校准、推荐理由增强、寻访策略建议和反馈学习事件。
- Eric / Codex agent：支持客户分析、岗位分析、寻访策略、人选综合评估、人岗匹配和推荐 feedback 后持续优化。

P0 主线是 JD 交付闭环：

1. 新 JD 开始前，查询历史 case 和 gbrain，生成 `historical-calibration.md/json`。
2. 根据历史偏好和反馈模式，生成 scorecard 校准建议、推荐理由建议和寻访策略建议。
3. JD delivery 完成后，采集 `consultant_decision + feedback_note`。
4. 生成 append-only 事件、public/private case page。
5. 单独导入或重建 gbrain 索引。
6. 用历史回放和新 JD shadow mode 评估建议质量。

## 3. 非目标

P0 不做以下事情：

- 不写 `data/talent.db`。
- 不启动脉脉、BOSS、猎聘等平台动作。
- 不自动发布飞书。
- 不把 gbrain 当事实源。
- 不把后续面试、offer、入职漏斗作为必需数据。
- 不做交互式 UI 或 Feishu dashboard。
- 不自动修改 `agents/skills/`、`agents/workflows/`、`scripts/`。
- 不导入联系方式、cookies、access token、平台 raw payload、token 化 profile URL。

## 4. 总体架构

采用 Repo-first + gbrain index 架构。

| 层级 | 事实源 | 说明 |
|---|---|---|
| 候选人事实 | `data/talent.db` | 姓名、公司、职位、source profile、结构化主数据仍以主库为准。 |
| 一次交付事实 | JD delivery run 目录 | `role_profile`、scorecard、推荐结果、质量门禁、outreach/feedback 文件。 |
| 第二大脑事件 | `data/second-brain/events.jsonl` | append-only 事件账本，本地运行事实源，不进 git。 |
| 公共 case 资产 | `docs/second-brain/cases/*.md` | 脱敏、可进 git，用于团队经验沉淀。 |
| 私有 case 资产 | `data/second-brain/private-cases/*.md` | 本地私有，可含候选人姓名、公司、职位、业务可读摘要。 |
| gbrain 索引 | 本机 gbrain 数据目录 | 检索、综合、历史校准、查询增强；可由 repo artifact 重建。 |

gbrain 失败时，正式 JD delivery 不阻塞。shadow/evaluation 写入 `gbrain_unavailable` 事件；可用本地 case/event fallback 做降级查询，但 fallback 结果只允许 L0 解释层，不允许 L1+ 自动采纳。

## 5. 目录与写入边界

P0 CLI 允许写入：

- `data/second-brain/events.jsonl`
- `data/second-brain/private-cases/*.md`
- `data/second-brain/evaluations/*.json`
- `data/second-brain/state/*.json`
- `docs/second-brain/cases/*.md`
- JD delivery run 目录下的 `second-brain/` 派生产物
- 本机 gbrain 数据目录

P0 CLI 不允许写入：

- `data/talent.db`
- Campaign DB
- 平台账号状态
- Feishu 云端对象
- `agents/skills/`、`agents/workflows/`、`scripts/`，除非后续进入单独 implementation plan

JD delivery run 目录的派生产物：

- `second-brain/historical-calibration.md`
- `second-brain/historical-calibration.json`
- `second-brain/sourcing-strategy-suggestions.md`
- `second-brain/calibration-review.json`
- `second-brain/skill-improvement-suggestions.md`
- `second-brain/skill-improvement-suggestions.json`

## 6. 数据模型

### 6.1 Event Ledger

`data/second-brain/events.jsonl` 是 append-only ledger。每条事件必须有证据引用。

最小字段：

```json
{
  "event_id": "evt_...",
  "event_type": "consultant_feedback_received",
  "created_at": "2026-06-12T10:00:00+08:00",
  "schema_version": "second_brain_event_v1",
  "run_id": "jd-xxx-2026-06-12",
  "client_id": "client_tencent_games",
  "jd_family": "multi_modal_algorithm",
  "visibility": "private",
  "source_refs": [
    {
      "source_path": "data/output/.../feedback/outreach-feedback.csv",
      "source_type": "feedback_csv",
      "artifact_key": "candidate_id=..."
    }
  ],
  "payload": {}
}
```

P0 事件类型：

- `jd_profile_created`
- `scorecard_created`
- `candidate_recommended`
- `consultant_feedback_received`
- `batch_feedback_summarized`
- `memory_hypothesis_created`
- `memory_hypothesis_promoted`
- `memory_hypothesis_demoted`
- `memory_hypothesis_superseded`
- `memory_hypothesis_decayed`
- `calibration_suggestion_created`
- `calibration_suggestion_applied_by_agent`
- `calibration_suggestion_reviewed`
- `taxonomy_suggestion_created`
- `gbrain_imported`
- `gbrain_unavailable`
- `evaluation_replay_completed`

### 6.2 Public Case Page

路径：

```text
docs/second-brain/cases/<client>-<jd-family>-<run-id>.md
```

内容只包含脱敏经验：

- 客户和 JD 家族
- JD 画像摘要
- scorecard 摘要
- 推荐批次摘要
- 顾问认可/不认可模式
- feedback 原因分布
- 下次 scorecard、推荐理由、寻访策略建议
- 证据引用

禁止写入：

- 候选人姓名
- 候选人当前公司
- 联系方式
- `profile_url`
- cookies/access token
- 平台 raw payload
- token 化链接

### 6.3 Private Case Page

路径：

```text
data/second-brain/private-cases/<client>-<jd-family>-<run-id>.md
```

允许写入业务可读候选人摘要：

- 姓名
- 当前公司
- 职位
- 核心经历
- 推荐理由
- 顾问反馈
- 风险/亮点

仍禁止写入联系方式、cookies、access token、平台 raw payload、token 化 profile URL。

### 6.4 Feedback Schema

新增候选人级反馈字段：

```csv
consultant_decision,feedback_note
```

`consultant_decision` 枚举：

- `认可`
- `不认可`
- `待确认`

批次级反馈由系统从候选人级 feedback 自动聚合。可选支持 `batch_feedback_note`，但 P0 不要求顾问填写。

历史数据缺少 `consultant_decision` 时，从 `feedback_note` 推断，并标记：

```json
{
  "decision_source": "inferred_from_note"
}
```

后续漏斗字段预留但非必需：

- `submitted_to_client`
- `interviewed`
- `offer`
- `joined`

### 6.5 Memory Hypothesis

经验判断不写成事实，而写成 hypothesis。

```json
{
  "hypothesis_id": "hyp_...",
  "scope": {
    "client_id": "client_tencent_games",
    "jd_family": "multi_modal_algorithm",
    "team_scope": null,
    "hiring_manager_scope": null
  },
  "statement": "该客户在多模态算法岗位上更认可视频算法落地证据，而不是纯视觉研究经历。",
  "status": "provisional",
  "confidence": 0.62,
  "supporting_event_ids": ["evt_..."],
  "conflicting_event_ids": [],
  "source_refs": [],
  "lifecycle": {
    "promotion_count": 0,
    "demotion_count": 0,
    "superseded_by": null,
    "decayed_at": null
  }
}
```

状态：

- `provisional`
- `promoted`
- `demoted`
- `superseded`
- `decayed`

底层事件永远 append-only；视图层通过新事件实现 promotion、demotion、supersede 和 decay。

### 6.6 Calibration Suggestion

给 agent 消费的建议：

```json
{
  "suggestion_id": "cal_...",
  "level": "L1",
  "target": "scorecard.dimension_weight",
  "action": "increase",
  "statement": "提高视频算法项目落地证据权重。",
  "confidence": 0.74,
  "auto_apply_decision": "applied",
  "guardrail_reason": "同客户同 JD family 有 3 条 feedback 支持，无冲突证据。",
  "source_refs": [
    {
      "source_path": "docs/second-brain/cases/client-jd-family-run.md",
      "source_type": "second_brain_case",
      "artifact_key": "feedback_patterns.video_algorithm_evidence"
    }
  ]
}
```

分级：

- L0：推荐理由/解释增强，默认自动采纳。
- L1：软权重调整，强证据可自动采纳。
- L2：维度新增、降级、删除，默认 review。
- L3：must-have / hard gate，默认 review。
- L4：敏感属性、不可证明推断、联系方式、raw/token、歧视性条件，禁止。

自动采纳策略可配置，默认保守：

- L0 自动。
- L1 仅强证据自动，否则 review。
- L2/L3 默认 review。
- L4 永远禁止。

## 7. Taxonomy 配置

新增配置：

```text
configs/second-brain-taxonomy.json
```

P0 字段：

- `jd_families`
- `company_aliases`
- `skill_neighbors`
- `feedback_reason_map`
- `candidate_type_tags`
- `sourcing_channel_tags`
- `sensitive_terms_blocklist`

JD 家族使用固定 taxonomy + 自动聚类兜底：

1. 先归类到固定 JD family。
2. 无法归类时进入 `candidate_family`。
3. 多个 `candidate_family` 稳定出现后，生成 taxonomy suggestion。
4. taxonomy suggestion 只生成 `taxonomy-suggestions.md/json`，不自动修改配置。

## 8. gbrain 组织方式

采用全局 brain + scoped views：

- 底层一个本地可重建索引。
- 查询时用 metadata scope 过滤：
  - `client_scope`
  - `jd_family`
  - `candidate_scope`
  - `visibility`
  - `source_type`
  - `source_path`
- 支持全局经验，也能收窄到客户/JD 家族。
- 未来团队化时，scoped views 可映射到权限模型。

P0 部署为本机本地 brain，服务 Eric、Codex 和 `talent-agent` workflow。schema 从第一天预留：

- `owner`
- `team`
- `client_scope`
- `source_visibility`

## 9. 查询与融合

P0 使用多路查询再融合，不使用单一文本相似度。

Query lanes：

- `client_preference`：同客户 + JD 家族偏好/拒绝模式。
- `role_family_pattern`：相似 JD 家族的岗位画像和 scorecard 经验。
- `candidate_feedback_pattern`：候选人类型被认可/不认可的模式。
- `sourcing_strategy_pattern`：目标公司池、关键词、渠道表现。
- `recommendation_narrative_pattern`：推荐理由表达方式。
- `failure_reason_pattern`：常见失败原因和规避建议。

融合优先级：

1. 客户匹配
2. JD 家族匹配
3. 最近 feedback
4. 证据强度
5. 全局经验

融合结果进入 `historical-calibration.json`，同时渲染到 `historical-calibration.md`。

## 10. Workflow 接入

P0 只在两个点接入 `jd-talent-delivery`。

### 10.1 交付前读取

新 JD 开始时运行 query：

```text
second-brain query --jd <jd-file> --client <client> --out <run-root>/second-brain/
```

输出：

- `historical-calibration.md`
- `historical-calibration.json`
- `sourcing-strategy-suggestions.md`
- `calibration-review.json`

允许影响：

- 生成 scorecard 修订建议。
- agent guardrail 自动确认低风险建议。
- L0 推荐理由增强可进入正式推荐理由。
- L1+ 必须按配置和证据分级判断。

默认不影响：

- 候选人排序。
- candidate grade。
- must-have / hard gate。

### 10.2 交付后写入

JD delivery 完成并拿到 `consultant_decision + feedback_note` 后：

```text
second-brain prepare-case --run-root <run-root>
```

生成：

- events
- public case page
- private case page
- batch feedback summary
- memory hypotheses
- calibration suggestions

不会自动调用 gbrain。gbrain 导入由单独命令执行。

## 11. CLI 设计

P0 CLI 模块建议为：

```text
scripts/second_brain.py
```

命令族：

### init

初始化目录、配置模板、taxonomy、脱敏规则。

```text
python -m scripts.second_brain init
```

### prepare-case

从 JD delivery run 生成 events 和 case pages。

```text
python -m scripts.second_brain prepare-case --run-root <run-root>
```

### export

导出 gbrain 可导入 bundle。

```text
python -m scripts.second_brain export --out data/output/second-brain-bundle.zip
```

### import

调用 gbrain CLI 导入 case pages / events。

```text
python -m scripts.second_brain import --bundle <bundle> --brain <brain-name>
```

gbrain 失败时写 `gbrain_unavailable`，不影响正式交付。

### query

针对新 JD 查询历史校准。

```text
python -m scripts.second_brain query --jd <jd-file> --client <client> --out <run-root>/second-brain/
```

### evaluate

历史回放评估。

```text
python -m scripts.second_brain evaluate --cases <case-list.json> --out data/second-brain/evaluations/<id>.json
```

### report

生成 Markdown 指标报告。

```text
python -m scripts.second_brain report --evaluation <evaluation.json> --out data/second-brain/reports/<id>.md
```

### rebuild

从 repo artifact 重建 gbrain 索引。

```text
python -m scripts.second_brain rebuild --brain <brain-name>
```

### taxonomy-suggest

生成 taxonomy 候选更新，不自动改配置。

```text
python -m scripts.second_brain taxonomy-suggest --events data/second-brain/events.jsonl --out data/second-brain/taxonomy-suggestions.json
```

## 12. 历史回放与 Shadow Mode

P0 使用两条验证线。

### 12.1 Evaluation Lane

使用最近 5-10 个已完成 JD delivery run，优先有 `consultant_decision + feedback_note`。数据量有限时不强求客户/JD 家族覆盖，但报告必须记录覆盖缺口。

回放方式：

1. 对每个历史 JD，只给 agent 交付前可见信息。
2. 查询 gbrain / fallback case events。
3. 生成 historical calibration 和推荐理由增强建议。
4. 用实际 feedback 对照。

指标：

- 来源覆盖率
- 复盘可回答率
- 校准建议命中率
- 误导率
- 推荐理由改进率
- L0/L1/L2/L3 建议分布
- gbrain 可用率

硬门槛：

- 所有建议必须有来源。
- L4 内容不得进入输出。
- 误导率必须低于配置阈值。
- gbrain 不可用不得影响正式交付。

### 12.2 Shadow Lane

新 JD delivery 旁路运行：

- 生成建议文件。
- 不阻塞正式交付。
- 初期不改排序、不改 grade。
- 交付后用 `consultant_decision + feedback_note` 回看建议质量。

达到门槛后，允许 L0/L1 进入正式输出；L2/L3 仍默认 review。

## 13. Feedback 闭环

顾问反馈采集：

- 新流程 outreach CSV/Sheet 增加 `consultant_decision`。
- 继续保留 `feedback_note`。
- 本地 import 兼容历史缺字段数据。

P0 的核心学习信号：

- 主信号：顾问认可/不认可及原因。
- 辅助信号：完整漏斗状态，预留但非必需。

系统从候选人级反馈自动聚合 batch-level 总结：

- 认可比例。
- 不认可原因分布。
- 强候选低排 / 弱候选高排信号。
- scorecard 维度缺失或权重错误信号。
- 推荐理由表达问题。

## 14. 寻访策略建议

P0 生成 `sourcing-strategy-suggestions.md`，但不自动执行平台动作。

内容：

- 目标公司池建议。
- 搜索关键词建议。
- 渠道优先级。
- 容易误召回/漏召回的候选人类型。
- 需要补充的证据。

进入真实 Maimai/BOSS/猎聘 workflow 前，仍必须遵守现有 canonical workflow 和平台安全门禁。

## 15. SkillOpt Shadow Mode

P0 纳入 gbrain `skillopt` 的 shadow mode，但不自动改文件。

产物：

- `skill-improvement-suggestions.md`
- `skill-improvement-suggestions.json`

适用对象：

- `agents/skills/jd-talent-delivery/SKILL.md`
- `agents/workflows/jd-talent-delivery/AGENT.md`
- scorecard 生成逻辑的 prompt /规则设计建议

禁止：

- 自动修改 canonical skill/workflow。
- 自动修改脚本。
- 未经独立设计/计划/测试流程合并。

## 16. 安全与合规

P0 必须满足：

- 每条记忆有 `source_refs`。
- 无来源内容只能作为 `untrusted_note`，不参与自动校准。
- public case page 不写候选人姓名/公司/profile URL。
- private case page 不写联系方式、raw payload、token URL。
- gbrain 本地数据目录不进 git。
- `data/second-brain/` 默认不进 git，除非明确导出脱敏报告。
- L4 禁止内容永远不自动采纳。

敏感拦截包括：

- 手机、邮箱、微信等联系方式。
- access token、cookie、session。
- 平台 raw API payload。
- token 化 profile URL。
- 歧视性或不可证明推断。
- 与岗位无关的敏感属性。

## 17. 测试策略

P0 测试分层：

### Unit Tests

- event schema validation
- source refs validation
- public/private case redaction
- consultant_decision parsing
- historical feedback inference fallback
- guardrail level decision
- taxonomy classification
- gbrain unavailable fallback

### Integration Tests

- `prepare-case` 从 fixture run 生成 events/cases。
- `query` 从 fixture cases 生成 calibration Markdown/JSON。
- `evaluate` 对历史 fixture 做 replay 并生成 metrics。
- `report` 渲染 Markdown。
- `import` 在 gbrain CLI 不存在时降级并写事件。

### Policy Tests

- public case 不包含姓名/当前公司/profile URL。
- private case 不包含联系方式/raw/token。
- L4 建议被拦截。
- fallback 查询不得触发 L1+ 自动采纳。
- `data/talent.db` 不被写入。

### Existing Regression

实现后至少运行：

```text
.venv/bin/python -m pytest tests/test_second_brain*.py -q
.venv/bin/python -m pytest tests/test_jd_*feedback*.py tests/test_jd_talent_delivery*.py -q
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
.venv/bin/python -m pytest tests -q
git diff --check
```

## 18. 分阶段落地

### P0.1 Artifact Foundation

- 创建 event schema。
- 创建 public/private case page generator。
- 创建 taxonomy 配置。
- 创建 redaction policy。
- 支持历史 5-10 个 JD run 生成 case/events。

### P0.2 Query and Calibration

- 实现多路查询和融合 policy。
- 输出 `historical-calibration.md/json`。
- 输出 `sourcing-strategy-suggestions.md`。
- 实现 gbrain unavailable fallback。

### P0.3 Feedback Loop

- 增加 `consultant_decision` 支持。
- 本地 import 兼容历史缺字段。
- 从 candidate feedback 自动聚合 batch summary。
- 生成 memory hypotheses 和 calibration suggestions。

### P0.4 Evaluation and Shadow Mode

- 历史回放评估。
- 新 JD shadow mode。
- 指标报告。
- skillopt shadow suggestions。

### P0.5 Controlled Workflow Adoption

- L0 推荐理由增强进入正式输出。
- L1 软权重建议在强证据下进入 scorecard draft。
- L2/L3 继续 review。
- P0 指标达标后再设计团队化或 Graphiti/Cognee 图谱层。

## 19. 成功标准

P0 不以短期推荐认可率作为硬成败标准，因为样本少、周期短。

硬门槛：

- 所有建议有来源。
- public/private redaction 通过。
- L4 零泄漏。
- gbrain 失败不阻塞正式交付。
- 事件账本可重建 gbrain 索引。

主指标：

- 复盘可回答率。
- 校准建议命中率。
- 误导率。
- 推荐理由改进率。
- 来源覆盖率。

观察指标：

- `consultant_decision=认可` 比例。
- 不认可原因分布变化。
- L0/L1/L2/L3 建议采纳率。
- feedback 中重复问题减少情况。

## 20. 后续可扩展方向

P0 成功后再考虑：

- Graphiti/Cognee 客户-JD-候选人-反馈关系图谱。
- 团队共享 brain 和 scoped permissions。
- Feishu/Sheet dashboard。
- 更深度的 `skillopt` 自动优化。
- 与 Maimai/BOSS/猎聘寻访策略 workflow 的正式联动。
- 候选人长期经验画像增强。
