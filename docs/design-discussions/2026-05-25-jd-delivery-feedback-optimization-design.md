# JD 推荐闭环精准度优化设计（2026-05-25）

## 背景

当前 `jd-talent-delivery` 已经形成从 JD 到推荐交付的闭环：

1. S2 读取 JD 并生成岗位画像 `profile/role-profile.json`。
2. S3 基于岗位画像生成评分卡 `scoring/scorecard.json`。
3. S4/S5 读取同一评分卡，对 `data/talent.db` 做粗筛和精排。
4. S6 产出推荐报告和外联表。
5. S7/S8 发布到飞书并通知 `JD需求协同`。

这个链路已经可执行、可解释、可发布，但精准度仍高度依赖初始规则和人工修正。最近几次交付暴露出同一类问题：JD 画像可能把过多技术词塞进 must-have，评分卡可能偏召回或偏精排，匹配阶段容易把词命中当成职责深度，Top30 中部分 C 档人选需要后续重新收紧。

本设计目标不是立刻引入黑盒模型，而是先建立一套可标注、可回放、可校准的反馈闭环，让后续优化能用历史证据验证，而不是靠临时规则和体感判断。

## 目标

第一阶段目标：

1. 推荐报告和外联表能回收资深猎头的结构化反馈。
2. 每条反馈能追溯到 JD、岗位画像版本、评分卡版本、候选人、分数、证据和推荐批次。
3. 系统能把反馈编译成原因分布、评分卡调整建议和下轮校准输入。
4. 任意画像、评分卡或匹配逻辑改动都能在历史 JD 上离线回放。
5. 优先提升 Top30 中被猎头认可的人选占比，而不是第一阶段追求更大召回。

非目标：

1. 第一阶段不训练端到端黑盒推荐模型。
2. 第一阶段不改写 `TalentDB` 主存储模型。
3. 第一阶段不要求 Web 标注后台，先复用飞书 Sheet 和本地 JSON/CSV。
4. 第一阶段不让反馈直接自动改写评分卡；所有自动建议必须先作为报告输出。
5. 不把候选人原始 payload、cookie、token、数据库文件或同步包上传到反馈产物。

## 当前系统判断

### 岗位画像

`scripts/jd_talent_delivery_profile.py` 当前主要依赖静态 `CORE_TERMS`、公司池和标题别名抽取。它的优点是确定、快速、可测试；风险是容易把 JD 中出现的词都当作核心能力，缺少“JD 原文事实”和“系统推断”的分层。

需要把画像输出拆成四类：

- `must_have`：不满足则明显不适配的硬证据。
- `nice_to_have`：增强排序但不能单独淘汰人的加分证据。
- `proxy_signal`：公司、岗位、项目、论文、业务场景等间接信号。
- `exclusion`：明确不适配、低优先级或需要人工复核的信号。

### 评分卡

`scripts/jd_talent_delivery_scorecard.py` 当前使用固定维度和固定权重。优点是每次交付可解释；风险是不同岗位类型需要不同权重，例如 AI 产品、训练推理工程、数据策略负责人、多模态算法研究并不应该共享同一套默认权重。

评分卡需要从“单一固定模板”升级为：

```text
岗位类型模板 -> JD 原文微调 -> 人工/反馈校准版本
```

每张评分卡必须有稳定版本号，且推荐报告必须记录版本号。

### 人选匹配

`scripts/jd_talent_delivery_match.py` 当前按公司、标题、must-have、nice-to-have、资历、教育和风险扣分生成分数与证据。优点是证据可追溯；风险是词命中和真实职责深度之间仍有距离。

匹配阶段应保持两段式：

1. 粗筛：偏召回，确保候选池覆盖足够多的潜在人选。
2. 精排：偏证据质量和职责深度，重点服务 Top30 可信度。

精排不应该重新解释 JD，只能读取 `role-profile.json` 和 `scorecard.json`。

### 反馈脚本

`scripts/maimai_campaign_feedback.py` 已有 `good/maybe/bad` 和 reason codes 的雏形，但它偏 campaign 策略，原因码也不足以定位 JD 画像、评分卡和匹配阶段的问题。需要新增 JD delivery 专用反馈编译器，而不是直接扩展成复杂通用脚本。

## 推荐方案

推荐先做“反馈优先 + 离线回放”的确定性闭环。

架构如下：

```text
JD 原文
  -> role-profile.json
  -> scorecard.json
  -> coarse-screen.json
  -> detailed-rank.json
  -> talent-recommendation.json / outreach-queue.csv
  -> 猎头反馈 Sheet
  -> delivery-feedback.json
  -> feedback-summary.json
  -> replay-evaluation.json
  -> 下一版画像/评分卡/匹配规则设计输入
```

这个方案的关键是先把“好不好”变成可追溯的数据，再谈自动优化。

## 反馈数据设计

### 外联表新增反馈列

外联表保留原有交付列，并追加以下列：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `feedback_label` | enum | `认可`、`待定`、`不认可` |
| `feedback_stage` | enum | `画像`、`评分卡`、`匹配`、`报告`、`候选人状态` |
| `reason_codes` | multi enum | 结构化原因码，可多选 |
| `hunter_note` | string | 一句话补充，不要求长评 |
| `contacted` | bool | 是否进入沟通 |
| `submitted_to_client` | bool | 是否推荐客户 |
| `interviewed` | bool | 是否进入面试 |
| `offer` | bool | 是否 offer |

外联表仍然不能包含 raw payload、数据库路径、同步包路径、cookie、token 或不可交付 URL。

### 原因码

原因码按环节拆分，避免所有问题都落成一个笼统“不匹配”。

画像阶段：

- `jd_profile_too_broad`：画像过宽。
- `jd_profile_too_narrow`：画像过窄。
- `must_have_overloaded`：硬门槛过多或过碎。
- `missing_key_requirement`：漏掉关键要求。
- `wrong_role_type`：岗位类型判断错误。

评分卡阶段：

- `scorecard_wrong_weight`：权重不合理。
- `scorecard_missing_dimension`：缺少关键维度。
- `scorecard_bad_threshold`：A/B/C 阈值不合理。
- `company_pool_wrong`：公司池错误。
- `title_alias_wrong`：标题别名错误。

匹配阶段：

- `keyword_hit_but_wrong_duty`：词命中但职责不符。
- `evidence_too_shallow`：证据太浅。
- `seniority_mismatch`：资历不匹配。
- `recent_experience_missing`：近期经历不足。
- `strong_candidate_ranked_low`：好候选人排序过低。
- `weak_candidate_ranked_high`：弱候选人排序过高。

报告阶段：

- `evidence_hard_to_verify`：报告证据难以复核。
- `outreach_angle_weak`：外联角度弱。
- `risk_not_called_out`：风险没有说明。

候选人状态：

- `candidate_unavailable`：候选人不可触达或暂不看机会。
- `candidate_duplicate`：重复人选。
- `candidate_info_stale`：信息过旧。

### 本地反馈 JSON

新增标准产物建议为：

```text
data/output/<run>/feedback/delivery-feedback.json
data/output/<run>/feedback/feedback-summary.json
data/output/<run>/feedback/calibration-suggestions.json
```

`delivery-feedback.json` 最小结构：

```json
{
  "schema": "jd_delivery_feedback_v1",
  "role_id": "example-role",
  "run_id": "data/output/example-run",
  "profile_version": "role-profile-v1",
  "scorecard_version": "v2-product-evaluation-balanced",
  "source_report": "reports/talent-recommendation.json",
  "source_outreach_sheet": "reports/outreach-queue.csv",
  "reviewer_role": "senior_hunter",
  "candidate_feedback": [
    {
      "candidate_id": "candidate-id",
      "rank": 1,
      "original_grade": "A",
      "original_score": 86,
      "feedback_label": "认可",
      "feedback_stage": "匹配",
      "reason_codes": ["evidence_too_shallow"],
      "hunter_note": "证据方向对，但近期项目深度还需要确认",
      "contacted": false,
      "submitted_to_client": false,
      "interviewed": false,
      "offer": false
    }
  ]
}
```

## 离线回放设计

每次 JD 交付完成后，应保存以下可回放输入：

- `source/jd.md`
- `profile/role-profile.json`
- `scoring/scorecard.json`
- `scoring/coarse-screen.json`
- `scoring/detailed-rank.json`
- `reports/talent-recommendation.json`
- `feedback/delivery-feedback.json`

新增回放命令建议：

```bash
python -m scripts.jd_delivery_feedback compile --feedback <feedback_json> --out <summary_json>
python -m scripts.jd_delivery_replay evaluate --runs data/output --out data/reports/jd-delivery-replay-<date>.json
```

回放不写 `data/talent.db`，只读取历史 run artifact 和只读人才库。它用于回答：

1. 新评分卡模板是否让被认可候选人排名更靠前。
2. 新 must-have 拆分是否减少 C 档混入 Top30。
3. 新公司池或标题别名是否减少误推荐。
4. Top10、Top30 的认可率是否提升。
5. 被否原因是否从系统性问题变成个案问题。

## 指标

第一阶段使用以下指标：

| 指标 | 解释 |
| --- | --- |
| `accepted_at_10` | Top10 中 `认可` 人数 |
| `accepted_at_30` | Top30 中 `认可` 人数 |
| `actionable_at_30` | Top30 中进入沟通、推荐客户、面试或 offer 的人数 |
| `bad_at_10` | Top10 中 `不认可` 人数 |
| `reason_distribution` | 原因码分布 |
| `grade_acceptance_rate` | A/B/C 各档认可率 |
| `rank_delta_for_accepted` | 新旧版本中认可候选人的排名变化 |
| `false_positive_reasons` | 高分但不认可的原因 |
| `false_negative_reasons` | 低分但被认可或后续推进的原因 |

第一版优化目标建议固定为：

> 提升 `accepted_at_30` 和 `actionable_at_30`，同时降低 `bad_at_10`。

召回覆盖率暂不作为第一优先级，避免为了多捞人牺牲 Top30 信任度。

## 评分卡模板库

建议新增模板目录：

```text
rules/jd-scorecard-templates/
  ai-product.json
  training-inference-engineering.json
  multimodal-algorithm.json
  data-strategy-lead.json
  data-platform-lead.json
```

每个模板包含：

- `role_type`
- 默认维度和权重。
- 推荐 must-have 上限。
- 常见 proxy signals。
- 常见 exclusion。
- 推荐 title aliases。
- 反馈校准记录摘要。

S3 生成评分卡时先判断岗位类型，再套模板并用 JD 原文微调。模板不能绕过 S2/S3 的产物合同；最终仍必须生成单一 `scoring/scorecard.json` 供 S4/S5 使用。

## 分阶段落地

### 阶段一：反馈采集和编译

改造范围：

- `scripts/jd_talent_delivery_feishu.py` 或报告生成入口追加外联表反馈列。
- 新增 `scripts/jd_delivery_feedback.py`。
- 新增 `schemas/jd-delivery-feedback.schema.json`。
- 新增测试覆盖反馈原因码、缺列校验和汇总统计。

验收标准：

- 外联表包含反馈列。
- 本地反馈 JSON 可校验。
- 能输出 `feedback-summary.json` 和 `calibration-suggestions.json`。
- 不影响现有发布和回读流程。

### 阶段二：历史 run 回放

改造范围：

- 新增 `scripts/jd_delivery_replay.py`。
- 读取历史 `data/output/*/` run artifact。
- 输出版本对比报告。

验收标准：

- 对至少 3 个历史 JD run 生成回放报告。
- 报告包含 Top10/Top30 认可率、原因码分布和 A/B/C 档认可率。
- 回放命令只读运行，不写主库。

### 阶段三：评分卡模板库

改造范围：

- 新增 `rules/jd-scorecard-templates/*.json`。
- 修改 `jd_talent_delivery_scorecard.py` 支持 `role_type` 模板选择。
- 更新 workflow 文档，明确模板只是 S3 输入，不替代最终评分卡。

验收标准：

- 训练推理工程、AI 产品、多模态算法至少三类岗位能选中不同模板。
- 模板权重总和校验为 100。
- 历史回放显示 Top30 认可率或误推荐原因分布有可解释改善。

### 阶段四：轻量 reranker 预研

触发条件：

- 至少积累 30 个 JD 的有效反馈。
- 每个 JD 至少有 Top30 中 10 条以上有效反馈。
- 规则回放已能稳定产出基线指标。

第一版 reranker 只用于同一候选池内排序，不负责召回、不负责淘汰、不覆盖风险规则。规则评分继续作为安全边界和解释来源。

## 安全边界

1. 反馈导入默认 dry-run，显式 `--apply` 前不得写入主库。
2. 猎头备注可能包含敏感信息，默认只保存在本地 output，不自动发布到 Wiki。
3. 飞书 Sheet 回读只用于验证反馈列和交付列，不把反馈备注回写到公开报告。
4. 回放报告不得包含 raw payload、cookie、token、DB 路径或 sync bundle 路径。
5. 自动校准只能输出建议，不自动修改评分卡模板。

## 测试策略

新增测试建议：

- `tests/test_jd_delivery_feedback.py`
  - 校验 feedback schema。
  - 校验未知 reason code 报错。
  - 校验原因码统计。
  - 校验 A/B/C 档认可率。
- `tests/test_jd_delivery_replay.py`
  - 使用 fixture run artifact 做只读回放。
  - 校验 Top10/Top30 指标。
  - 校验缺少反馈时给出明确 warning 而不是失败。
- `tests/test_jd_talent_delivery_feishu.py`
  - 校验外联表包含反馈列。
  - 校验发布包不上传反馈备注。
- `tests/test_jd_talent_delivery_scorecard.py`
  - 校验模板权重总和。
  - 校验岗位类型选择和 fallback。

全量验证仍使用仓库约定：

```bash
python -m pytest tests scripts -q
```

## 决策

本设计建议立即进入阶段一，不先做模型训练，也不先重构整个匹配引擎。原因是当前最大缺口不是算法表达能力，而是缺少稳定的反馈数据、版本追踪和回放评估。先把反馈闭环打通，后续每一次优化都能被历史 JD 验证。

第一版成功标准：

1. 每份 JD 推荐交付都能带反馈列。
2. 资深猎头能在 5 分钟内完成 Top30 结构化反馈。
3. 系统能生成按环节归因的反馈摘要。
4. 历史 run 回放能显示新旧评分策略在 Top30 上的差异。
5. 下一轮评分卡调整有数据证据，而不是只依赖人工感觉。
