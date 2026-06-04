# JD 推荐反馈自然语言解析设计（2026-06-04）

## 背景

Phase 1 反馈闭环已于 2026-05-25 落地：外联表 `reports/outreach-queue.csv` 含 8 个反馈列，`scripts/jd_delivery_feedback.py` 能校验结构化 JSON、统计指标并输出校准建议。

但业务反馈一直偏低，核心原因是填写复杂度：业务人员需要理解并选择 `feedback_label`（3 选 1）、`feedback_stage`（5 选 1）、`reason_codes`（22 个英文码中选 1-3 个）以及 4 个布尔列。

本设计把业务侧输入降到自然语言一句话，只评估猎头顾问对推荐的主观反馈。

## 目标

1. 业务只需在 `feedback_note` 列写一句中文说明。
2. LLM 自动将 `feedback_note` 解析为结构化字段（`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`）。
3. 解析结果可审计、可回退；低置信度或降级条目进 review queue。
4. 现有 `compile_feedback_summary` 和 `calibration-suggestions` 链路复用。
5. 不自动修改评分卡或主库。

非目标：

1. 不训练专属分类模型；直接用现有 LLM provider。
2. 不在飞书 Sheet 回读解析；先支持本地 CSV 输入。
3. 不追踪候选人的联系/推荐/面试/offer 全生命周期。

## 关键决策

| 决策 | 结论 |
| --- | --- |
| 解析策略 | 直接上 LLM，不搞规则层 |
| LLM 输入上下文 | 只喂 `feedback_note` 原文，不依赖候选人或 JD 上下文 |
| 非法字段处理 | 降级到安全默认值 + 进 review queue |
| 架构方案 | 独立模块 + review queue，与编译器解耦 |
| 外联表反馈列 | 从 8 列缩减为 1 列（`feedback_note`） |
| 布尔追踪列 | 取消，不追踪联系/推荐/面试/offer |
| 指标范围 | 只评估猎头主观反馈，移除 `actionable_at_30` |

## 外联表变更

`FEEDBACK_CSV_FIELDS` 从 8 列改为 1 列：

```python
FEEDBACK_CSV_FIELDS = ["feedback_note"]
```

业务只填 `feedback_note`。`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note` 由 AI 解析后写入内部 `delivery-feedback.json`，不回填外联表。`contacted`、`submitted_to_client`、`interviewed`、`offer` 四个布尔追踪列取消。

## 解析器架构

新增 `scripts/jd_feedback_note_parser.py`，职责单一：把 `feedback_note` 发给 LLM，拿回结构化字段，校验后输出。

### LLM Prompt

每次调用带完整的字段语义和枚举值说明：

```
你是一位资深猎头助理。业务同事会对一个推荐候选人写一句中文反馈，你需要把这句话解析为结构化字段。

字段说明：

1. feedback_label（必填）：总体判断
   - "认可"：方向对，值得推进
   - "待定"：有亮点但不确定，需要再确认
   - "不认可"：明显不适合，不建议继续

2. feedback_stage（必填）：问题主要出在哪个环节
   - "画像"：系统对岗位要找什么人理解偏了
   - "评分卡"：评分规则或权重不合适
   - "匹配"：候选人匹配判断不准（最常见）
   - "报告"：推荐理由或外联角度不好
   - "候选人状态"：候选人本身状态问题（不看机会、信息过期等）

3. reason_codes（可多选，可为空）：具体原因
   - jd_profile_too_broad：画像过宽
   - jd_profile_too_narrow：画像过窄
   - must_have_overloaded：硬门槛过多或过碎
   - missing_key_requirement：漏掉关键要求
   - wrong_role_type：岗位类型判断错误
   - scorecard_wrong_weight：权重不合理
   - scorecard_missing_dimension：缺少关键维度
   - scorecard_bad_threshold：阈值不合理
   - company_pool_wrong：公司池错误
   - title_alias_wrong：标题别名错误
   - keyword_hit_but_wrong_duty：词命中但职责不符
   - evidence_too_shallow：证据太浅
   - seniority_mismatch：资历不匹配
   - recent_experience_missing：近期经历不足
   - strong_candidate_ranked_low：好候选人排序过低
   - weak_candidate_ranked_high：弱候选人排序过高
   - evidence_hard_to_verify：证据难以复核
   - outreach_angle_weak：外联角度弱
   - risk_not_called_out：风险没有说明
   - candidate_unavailable：候选人不可触达
   - candidate_duplicate：重复人选
   - candidate_info_stale：信息过旧

4. hunter_note（必填）：用一句精炼中文总结反馈要点

业务反馈原文：
"{feedback_note}"

请严格按以下 JSON 格式输出，不要输出其他内容：
{"feedback_label":"...","feedback_stage":"...","reason_codes":[...],"hunter_note":"..."}
```

### 校验规则

- `feedback_label` 不合法 → 降为 `"待定"`，`parse_confidence = 0.0`
- `feedback_stage` 不合法 → 降为 `"匹配"`
- `reason_codes` 中有非法码 → 过滤掉，只保留合法码
- 全部字段非法 → `feedback_label="待定"`，`reason_codes=[]`，进 review queue
- LLM 调用失败 → 降级为 `feedback_label="待定"`，`reason_codes=[]`，`hunter_note=原文`，`parse_confidence=0.0`

### 产物

```text
feedback/delivery-feedback.json        — 结构化反馈，现有 schema 兼容
feedback/parse-review-queue.json       — 低置信度或降级条目
feedback/feedback-summary.json         — 由现有 compile_feedback_summary 生成
feedback/calibration-suggestions.json  — 由现有 build_suggestions 生成
```

## 指标体系

移除 `actionable_at_30`。保留：

| 指标 | 解释 |
| --- | --- |
| `accepted_at_10` | Top10 中 `认可` 人数 |
| `accepted_at_30` | Top30 中 `认可` 人数 |
| `bad_at_10` | Top10 中 `不认可` 人数 |
| `reason_distribution` | 原因码分布 |
| `grade_acceptance_rate` | A/B/C 各档认可率 |

## CLI 入口

单条解析：

```bash
python -m scripts.jd_feedback_note_parser parse \
  --note "这个人实际做销售支持，不是大模型平台产品负责人" \
  --out feedback/parsed-single.json
```

批量解析：

```bash
python -m scripts.jd_feedback_note_parser parse-csv \
  --csv reports/outreach-queue.csv \
  --out feedback/delivery-feedback.json \
  --review-out feedback/parse-review-queue.json \
  --provider openai-compatible \
  --model deepseek-chat
```

`--provider` 和 `--model` 可选，默认从 `LLM_PROVIDER`/`LLM_MODEL` 环境变量读取，复用 `scripts/llm_client.py`。

批量流程：
1. 读 CSV，跳过 `feedback_note` 为空的行
2. 逐行调 LLM 解析
3. 校验每条结果，降级非法字段
4. 合法条目写入 `delivery-feedback.json`
5. 降级条目写入 `parse-review-queue.json`
6. 用现有 `jd_delivery_feedback compile` 生成 summary 和 suggestions

## 现有代码影响

| 文件 | 改动 |
| --- | --- |
| `scripts/jd_talent_delivery_match.py` | `FEEDBACK_CSV_FIELDS` 缩减为 `["feedback_note"]`；`_outreach_row()` 移除旧 7 列 |
| `tests/test_jd_talent_delivery_match.py` | 空值断言改为只检查 `feedback_note` |
| `scripts/jd_talent_delivery_feishu.py` | 发布校验兼容 `feedback_note` 列 |
| `tests/test_jd_talent_delivery_feishu.py` | 反馈列测试改为只检查 `feedback_note` |
| `schemas/jd-delivery-feedback.schema.json` | 移除布尔字段；`candidate_feedback` 条目不再要求 `reason_codes` 由 CSV 填 |
| `scripts/jd_delivery_feedback.py` | 移除 `ACTION_FIELDS` 和 `actionable_at_30` |
| `tests/test_jd_delivery_feedback.py` | 移除布尔字段断言和 `actionable_at_30` |
| `agents/workflows/jd-talent-delivery/AGENT.md` S9 | 更新反馈列描述为只含 `feedback_note` |
| `agents/skills/jd-talent-delivery/SKILL.md` | 同步更新反馈列列表 |
| `docs/manual/jd-delivery-feedback-guide.md` | 更新为"只填 `feedback_note`"的最简模式 |

## 安全边界

1. 解析器不写 `data/talent.db`，不修改评分卡，不自动发布到飞书。
2. LLM 调用走现有 `create_llm_client`，API Key 由环境变量管理。
3. 低置信度解析不自动影响校准闭环；必须经 review 后人工确认。
4. 批量解析前可 dry-run，显示解析结果和置信度分布。

## 测试策略

新增 `tests/test_jd_feedback_note_parser.py`：

- LLM 层（mock）：合法 JSON 输出正确解析
- LLM 层（mock）：非法 `feedback_label` 降为 `"待定"`
- LLM 层（mock）：非法 `reason_codes` 过滤
- LLM 层（mock）：全部字段非法时安全降级
- LLM 层（mock）：调用失败时降级为原文保留
- CLI：单条解析和批量 CSV 解析输出格式正确
- Review queue：降级条目进入队列
- 集成：解析结果传入 `compile_feedback_summary`，指标计算正确

现有测试适配：移除布尔字段和 `actionable_at_30` 相关断言。
