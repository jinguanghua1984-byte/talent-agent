# 自然语言反馈解析方案设计（2026-06-04）

## 背景

当前 JD delivery 反馈要求业务填写 4 个结构化字段（`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`）加上 4 个布尔动作字段。反馈指南已明确枚举值和填写规范，`scripts/jd_delivery_feedback.py` 也做了完整校验。

实际使用中的核心痛点：**结构化字段填写门槛偏高**。业务需要同时理解 `feedback_label` 的三选一、`feedback_stage` 的五选一、以及 22 个 `reason_codes` 的语义区别。反馈指南 2.3 节自己都承认"如果 `reason_codes` 看不懂可以先不填，只写 `hunter_note`"。

这意味着当前最低门槛是只写 `hunter_note`，但系统只把它当备注存储，不参与编译和校准。大量有价值的自然语言判断被浪费。

## 目标

1. 新增 `feedback_note` 字段作为主要业务入口，允许用自然语言写一句反馈，系统自动解析为结构化字段。
2. 解析结果可审计、可回退、可人工覆盖；不得自动直接修改评分卡或主库。
3. 向后兼容：已填写结构化字段的反馈继续正常工作；`feedback_note` 与结构化字段冲突时以结构化字段为准。
4. 不改现有 `delivery-feedback.json` schema 版本，通过 `additionalProperties` 扩展。

## 非目标

- 不做通用 NLU 引擎或微调模型。
- 不替代现有结构化反馈入口，只新增可选入口。
- 第一版不做飞书 Sheet 回写解析结果（后续可扩展）。

## 数据模型变更

### `delivery-feedback.json` 新增字段

在 `candidate_feedback` 每条记录中新增：

```json
{
  "candidate_id": "101",
  "rank": 1,
  "original_grade": "A",
  "original_score": 88,
  "feedback_note": "方向对，但关键词命中了实际职责不对，画像太宽了",
  "feedback_label": "不认可",
  "feedback_stage": "画像",
  "reason_codes": ["jd_profile_too_broad", "keyword_hit_but_wrong_duty"],
  "hunter_note": "方向对，但关键词命中了实际职责不对，画像太宽了",
  "_parse_meta": {
    "source": "feedback_note",
    "parser": "rule_v1",
    "parsed_at": "2026-06-04T12:00:00+08:00",
    "confidence": 0.85,
    "overridden_fields": []
  }
}
```

字段说明：

| 字段 | 类型 | 必须 | 说明 |
| --- | --- | --- | --- |
| `feedback_note` | string | 否 | 自然语言反馈原文，业务主入口 |
| `_parse_meta` | object | 否 | 解析元数据，标记来源和置信度 |

`_parse_meta` 子字段：

| 子字段 | 类型 | 说明 |
| --- | --- | --- |
| `source` | string | `"feedback_note"` 或 `"manual"` |
| `parser` | string | 解析器版本标识，如 `"rule_v1"` |
| `parsed_at` | string | ISO 8601 解析时间 |
| `confidence` | float | 整体解析置信度 0-1 |
| `overridden_fields` | list | 被人工覆盖的字段名列表 |

### 优先级规则

1. 如果 `feedback_label` / `feedback_stage` / `reason_codes` 已由业务手动填写，**以手动值为准**，`feedback_note` 只作为 `hunter_note` 的补充来源。
2. 如果结构化字段为空或缺失，由 `feedback_note` 解析结果填充。
3. `_parse_meta.overridden_fields` 记录哪些字段曾被手动修改，用于后续评估解析准确率。

## 解析方案选择

### 方案 A：规则优先 + LLM 兜底（推荐）

**架构**

```text
feedback_note
  -> 规则解析器 (rule_v1)
     -> 命中 -> 结构化字段 + confidence
     -> 未命中 -> LLM 解析器 (llm_v1)
        -> 结构化字段 + confidence
        -> 仍无法确定 -> label="待定", stage="匹配", reason_codes=[], confidence=0
```

**规则解析器**

基于关键词 + 模式匹配，覆盖高频场景：

| 规则 | 模式 | 输出 |
| --- | --- | --- |
| 认可类 | 包含"匹配"/"方向对"/"可以推进"/"不错"/"合适"且无否定修饰 | `label=认可` |
| 不认可类 | 包含"不对"/"不匹配"/"偏了"/"太宽"/"太窄"/"不是" | `label=不认可` |
| 待定类 | 包含"不确定"/"待定"/"需要确认"/"再看看" | `label=待定` |
| 画像问题 | 包含"画像"/"JD理解"/"岗位方向" | `stage=画像` |
| 评分卡问题 | 包含"权重"/"评分"/"分档"/"阈值" | `stage=评分卡` |
| 匹配问题 | 包含"关键词命中"/"词命中"/"实际职责"/"名字像" | `stage=匹配` |
| 报告问题 | 包含"报告"/"推荐理由"/"外联" | `stage=报告` |
| 候选人状态 | 包含"不看机会"/"已离职"/"信息过期"/"重复" | `stage=候选人状态` |
| 原因码映射 | 以上模式 + 具体描述 -> reason_codes | 见下方映射表 |

**关键词 -> 原因码映射**

| 关键词模式 | reason_code |
| --- | --- |
| "太宽"/"什么人都进来"/"范围太大" | `jd_profile_too_broad` |
| "太窄"/"漏掉"/"应该也看" | `jd_profile_too_narrow` |
| "岗位类型错"/"当成算法"/"产品岗" | `wrong_role_type` |
| "漏了关键"/"缺少必须" | `missing_key_requirement` |
| "关键词命中但"/"词对职责不对"/"名字像实际不是" | `keyword_hit_but_wrong_duty` |
| "证据太浅"/"不够深"/"看不出" | `evidence_too_shallow` |
| "资历不匹配"/"太浅"/"太重" | `seniority_mismatch` |
| "近期经历不"/"最近没有" | `recent_experience_missing` |
| "好的人排低"/"应该排更高" | `strong_candidate_ranked_low` |
| "弱的人排高"/"不该排这么高" | `weak_candidate_ranked_high` |
| "权重不对"/"权重偏高"/"权重偏低" | `scorecard_wrong_weight` |
| "阈值不对"/"A/B/C 分档" | `scorecard_bad_threshold` |
| "不看机会"/"不考虑" | `candidate_unavailable` |
| "重复"/"已见过" | `candidate_duplicate` |
| "信息过期"/"旧信息" | `candidate_info_stale` |

规则解析器优势：确定性、可测试、零延迟、零成本。

**LLM 兜底解析器**

当规则未命中时，调用 LLM 做结构化解析。提示词模板：

```text
你是一个 JD 推荐反馈解析器。根据猎头写的自然语言反馈，解析为以下结构化字段：

feedback_label: 认可 | 待定 | 不认可
feedback_stage: 画像 | 评分卡 | 匹配 | 报告 | 候选人状态
reason_codes: 从以下列表中选 0-3 个: [全部 22 个原因码列出]

反馈原文: {feedback_note}

输出 JSON:
```

LLM 解析器控制：

- 使用仓库已有的 `.venv/bin/python` 环境 + `openai` SDK（如已配置）或 `requests` 调用本地/远程 API。
- 设定 `temperature=0`，`max_tokens=200`。
- 解析失败（格式错误、值不在枚举内）时 fallback 到 `label=待定, stage=匹配, reason_codes=[], confidence=0`。
- 每次调用记录 `_parse_meta.parser = "llm_v1"` 和 `_parse_meta.confidence`。
- **默认不调用外部 LLM**，需显式 `--enable-llm` 参数才启用；无参数时规则未命中直接 fallback。

### 方案 B：纯规则解析

只做规则解析，不引入 LLM 兜底。规则未命中的场景默认 `label=待定, stage=匹配, reason_codes=[]`。

优点：零外部依赖、零延迟、零成本、完全可测试。
缺点：自然语言覆盖面有限，无法处理"这个人背景和岗位要求不在一个频道上"这类非模板化表达。

### 方案 C：纯 LLM 解析

所有自然语言反馈直接走 LLM 解析，不维护规则。

优点：覆盖面最广。
缺点：不确定性强、有 API 成本、有延迟、难以离线回放和回归测试、过度依赖外部服务。

### 推荐

**方案 A（规则优先 + LLM 兜底）**。理由：

1. 高频场景（占比估计 70-80%）由规则确定性覆盖，测试可靠、回归稳定。
2. 低频/复杂场景由 LLM 兜底，不会因为规则遗漏丢失信息。
3. LLM 默认关闭，渐进启用：先积累规则未命中的案例，再决定是否开启 LLM。
4. 解析结果都有 `_parse_meta` 标记来源和置信度，后续可以区分评估规则 vs LLM 的准确率。

## 实现架构

```text
scripts/jd_delivery_feedback.py
  + parse-note 子命令
  + FeedbackNoteParser 类
    + rule_parse(note: str) -> ParsedFeedback
    + llm_parse(note: str) -> ParsedFeedback
    + parse(note: str, enable_llm: bool = False) -> ParsedFeedback
  + merge_parsed_feedback(feedback: dict, parsed: ParsedFeedback) -> dict

scripts/jd_delivery_feedback_parse.py（新文件，解析逻辑独立）
  + class FeedbackNoteParser
  + class ParsedFeedback(TypedDict)
  + RULE_PATTERNS: list[ParseRule]
  + KEYWORD_REASON_MAP: dict[str, str]

tests/test_jd_delivery_feedback_parse.py
  + test_rule_parse_label_recognition
  + test_rule_parse_stage_recognition
  + test_rule_parse_reason_code_mapping
  + test_rule_parse_negation_handling
  + test_rule_parse_no_match_fallback
  + test_llm_parse_structured_output
  + test_llm_parse_failure_fallback
  + test_merge_respects_manual_fields
  + test_merge_overridden_fields_tracking
  + test_confidence_scoring
```

### `ParsedFeedback` 类型

```python
class ParsedFeedback(TypedDict):
    feedback_label: str | None
    feedback_stage: str | None
    reason_codes: list[str]
    confidence: float
    parser: str
    matched_rules: list[str]  # 命中的规则 ID，便于审计
```

### 置信度计算

- 规则解析：每个命中规则贡献 0.3，上限 1.0。只命中 label 规则 + 无 stage/reason = 0.3；label + stage = 0.6；label + stage + reason = 0.9+。
- LLM 解析：使用 LLM 输出的 self-reported confidence（如有），否则默认 0.7。
- 未命中：confidence = 0。

### 否定处理

规则解析器需要处理否定修饰：

- "不匹配" -> `不认可`（否定 + 匹配 = 不认可）
- "不是不行" -> `认可`（双重否定）
- "方向对但不太深" -> `待定`（肯定 + 但 + 限定 = 待定）

第一版采用简化策略：**只处理明确的否定前缀**（"不"、"没"、"不是"、"不太"），不做完整语法分析。遇到歧义时 fallback 到 `待定`。

## CLI 集成

```bash
# 解析单个 feedback_note（调试用）
.venv/bin/python -m scripts.jd_delivery_feedback parse-note \
  --note "关键词命中但实际职责不对，画像太宽了" \
  --enable-llm

# 编译反馈时自动解析空的 feedback_note
.venv/bin/python -m scripts.jd_delivery_feedback compile \
  --feedback delivery-feedback.json \
  --summary-out feedback-summary.json \
  --suggestions-out calibration-suggestions.json \
  --parse-notes \
  --enable-llm
```

`compile` 子命令新增 `--parse-notes` 标志：开启后，对 `candidate_feedback` 中有 `feedback_note` 但缺少 `feedback_label` 的条目自动解析并填充。

## 安全边界

1. **解析只填充空字段，不覆盖已有手动值**。`merge_parsed_feedback` 严格检查每个字段是否已有值。
2. **解析结果标记 `_parse_meta`**，任何消费 `delivery-feedback.json` 的下游模块都可以区分手动值和解析值。
3. **LLM 默认关闭**，需显式 `--enable-llm`。不开启时规则未命中直接 fallback 到安全默认值。
4. **不自动修改评分卡或主库**。解析结果仍走现有 `compile -> summary -> calibration-suggestions` 闭环。
5. **`feedback_note` 原文保留**，不修改不截断。
6. **规则解析逻辑是纯函数**，无副作用、无 I/O、无网络调用，可离线测试和回放。
7. **LLM 调用结果需与规则解析结果做 diff 审计**：开启 `--enable-llm` 时，如果 LLM 和规则结果不一致，记录到 `_parse_meta.llm_disagreement = true`。

## 渐进落地

### Phase 1：规则解析器 + merge 逻辑

改造范围：

- 新增 `scripts/jd_delivery_feedback_parse.py`。
- 修改 `scripts/jd_delivery_feedback.py` 的 `compile` 子命令支持 `--parse-notes`。
- 新增 `tests/test_jd_delivery_feedback_parse.py`。
- 更新 `schemas/jd-delivery-feedback.schema.json` 增加 `feedback_note` 和 `_parse_meta` 定义。

验收标准：

- 规则解析覆盖 10 个以上典型反馈表达。
- merge 逻辑不覆盖手动值。
- `_parse_meta` 正确标记来源和置信度。
- 现有测试全部通过。

### Phase 2：LLM 兜底

改造范围：

- 在 `FeedbackNoteParser` 中新增 `llm_parse` 方法。
- `compile` 子命令新增 `--enable-llm`。
- 新增 LLM 调用日志和 diff 审计。

前置条件：

- Phase 1 已上线并积累至少 50 条规则未命中的 `feedback_note` 样本。
- 已确认 API key 和调用环境可用。

### Phase 3：飞书回写（可选）

改造范围：

- `scripts/jd_talent_delivery_feishu.py` 在发布 outreach 表时，如果检测到 `feedback_note` 列有值但结构化列为空，自动调用解析并回填到对应飞书单元格。

前置条件：

- Phase 1 已验证解析准确率 >= 80%（基于人工抽检）。

## 指标

| 指标 | 计算方式 | 目标 |
| --- | --- | --- |
| 规则命中率 | 规则解析产出有效 label 的比例 | >= 70% |
| 解析准确率 | 解析 label 与人工标注一致的比例 | >= 85% |
| 业务填写耗时 | 从看到候选人到完成反馈的时间 | 相比纯结构化填写降低 50% |
| 手动覆盖率 | `_parse_meta.overridden_fields` 非空的比例 | <= 10% |

## 与现有闭环的对接

```text
feedback_note (新增入口)
  -> FeedbackNoteParser.parse()
  -> ParsedFeedback
  -> merge_parsed_feedback() 填充空字段
  -> delivery-feedback.json (现有格式，新增 feedback_note + _parse_meta)
  -> compile_feedback_summary() (现有逻辑，不变)
  -> feedback-summary.json + calibration-suggestions.json (现有产物，不变)
```

所有下游模块（`compile_feedback_summary`、`jd_delivery_replay`、飞书发布）无需修改，因为解析结果最终产出与现有结构化字段完全一致的格式。

