# JD 推荐反馈自然语言解析设计（2026-06-04）

## 背景

Phase 1 反馈闭环已于 2026-05-25 落地：外联表 `reports/outreach-queue.csv` 已含 8 个反馈列（`feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`、`contacted`、`submitted_to_client`、`interviewed`、`offer`），`scripts/jd_delivery_feedback.py` 能校验结构化 JSON、统计 `accepted_at_30/actionable_at_30/bad_at_10` 指标并输出校准建议。

但业务反馈一直偏低，核心原因是填写复杂度：业务人员需要理解并选择 `feedback_label`（3 选 1）、`feedback_stage`（5 选 1）、`reason_codes`（22 个英文码中选 1-3 个）以及 4 个布尔列。`docs/manual/jd-delivery-feedback-guide.md` 虽然提供了场景和示例，但门槛仍然过高。

本设计目标是在不破坏已有结构化闭环的前提下，把业务侧输入降到自然语言一句话。

## 目标

1. 业务只需在 `feedback_note` 列写一句中文说明，如"这个人实际做销售支持，不是大模型平台产品负责人"。
2. 系统（AI/规则混合）自动将 `feedback_note` 解析为现有 `delivery-feedback.json` 的结构化字段。
3. 解析结果可审计、可回退、可人工覆盖；低置信度或冲突时进入 review queue，不自动进入闭环。
4. 现有 `compile_feedback_summary` 和 `calibration-suggestions` 链路完全复用，不重建。
5. 不自动修改评分卡或主库；校准建议仍只作为报告输出。

非目标：

1. 不替换现有结构化字段，只在业务侧增加自然语言入口。
2. 不在本阶段训练专属分类模型；解析器用规则 + LLM prompt，后续可替换 provider。
3. 不改动飞书 Sheet 发布流程；`feedback_note` 列作为可选列追加，不影响已有发布校验。
4. 不在本阶段做批量 Sheet 回读解析；先支持本地 JSON 输入。

## 现有系统锚点

| 组件 | 路径 | 角色 |
| --- | --- | --- |
| 反馈编译器 | `scripts/jd_delivery_feedback.py` | 校验、统计、校准建议 |
| 反馈 schema | `schemas/jd-delivery-feedback.schema.json` | JSON contract |
| 外联表生成 | `scripts/jd_talent_delivery_match.py` `_outreach_row` | 追加空反馈列 |
| 飞书发布 | `scripts/jd_talent_delivery_feishu.py` | Sheet 写入和回读 |
| 反馈业务指南 | `docs/manual/jd-delivery-feedback-guide.md` | 业务填写指南 |
| JD delivery workflow | `agents/workflows/jd-talent-delivery/AGENT.md` S9 | 可选反馈回收 |
| JD delivery skill | `agents/skills/jd-talent-delivery/SKILL.md` | 猎头反馈后续 |
| LLM 客户端 | `scripts/llm_client.py` | Anthropic / OpenAI-compatible provider |
| Pipeline 工具 | `scripts/pipeline_utils.py` | `create_llm_client`、`call_llm_with_retry` |

## 推荐方案

### 架构

```text
业务填写 feedback_note（自然语言）
  → 解析器 parse_feedback_note()
  → candidate_feedback 结构化条目（含 confidence + parse_source）
  → 现有 load_feedback / compile_feedback_summary
  → feedback-summary.json + calibration-suggestions.json
```

解析器输出与现有 `candidate_feedback` 条目兼容，只多两个字段：
- `parse_source`: `"rule"` | `"llm"` | `"manual"` — 标记字段来源
- `parse_confidence`: `0.0-1.0` — 解析置信度

### 外联表变更

`FEEDBACK_CSV_FIELDS` 新增 `feedback_note` 作为第一列：

```python
FEEDBACK_CSV_FIELDS = [
    "feedback_note",          # 新增：业务自然语言输入
    "feedback_label",         # 保留：可由系统回填或人工覆盖
    "feedback_stage",
    "reason_codes",
    "hunter_note",
    "contacted",
    "submitted_to_client",
    "interviewed",
    "offer",
]
```

`_outreach_row()` 生成时 `feedback_note` 仍为空字符串，与其他反馈列一致。

### 解析器设计

新增 `scripts/jd_feedback_note_parser.py`，提供：

```python
def parse_feedback_note(
    note: str,
    *,
    candidate_context: dict[str, Any] | None = None,
    jd_context: dict[str, Any] | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """将自然语言反馈解析为结构化字段。

    返回:
        {
            "feedback_label": "认可" | "待定" | "不认可",
            "feedback_stage": "画像" | "评分卡" | "匹配" | "报告" | "候选人状态",
            "reason_codes": [...],
            "hunter_note": "原文或精简",
            "parse_source": "rule" | "llm",
            "parse_confidence": 0.0-1.0,
        }
    """
```

解析策略分两层：

1. **规则层**（`parse_source="rule"`）：用关键词匹配和否定模式做快速解析。
   - 否定词（"不适合""不是""不对""没有"）→ `feedback_label="不认可"`
   - 肯定词（"匹配""合适""方向对"）→ `feedback_label="认可"`
   - 犹豫词（"待确认""不确定""再看看"）→ `feedback_label="待定"`
   - 职责不符模式 → `reason_codes` 含 `keyword_hit_but_wrong_duty`
   - 证据不足模式 → `reason_codes` 含 `evidence_too_shallow`
   - 规则层能匹配时 `parse_confidence >= 0.8`；匹配不到或冲突时返回 `confidence < 0.5`

2. **LLM 层**（`parse_source="llm"`）：规则层 `confidence < 0.7` 时，调用 LLM 做结构化解析。
   - 复用 `scripts/llm_client.py` + `scripts/pipeline_utils.py` 的 `create_llm_client` / `call_llm_with_retry`。
   - Prompt 要求输出 JSON，包含 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`。
   - LLM 层必须校验输出字段合法性；非法值降级为 `feedback_label="待定"`、`feedback_stage="匹配"`、`reason_codes=[]`。
   - LLM 调用失败时不阻塞编译流程；降级为 `feedback_label="待定"`、`parse_source="rule"`、`parse_confidence=0.0`。

### Review Queue

解析结果 `parse_confidence < 0.7` 或 `feedback_label="待定"` 且 `reason_codes` 为空时，该条目进入 `feedback/parse-review-queue.json`：

```json
{
  "schema": "jd_delivery_feedback_parse_review_queue_v1",
  "items": [
    {
      "candidate_id": "...",
      "original_note": "这人感觉一般",
      "parsed": { "feedback_label": "待定", "reason_codes": [], "parse_confidence": 0.3 },
      "review_status": "pending"
    }
  ]
}
```

Review queue 不阻塞 `compile_feedback_summary`；低置信度条目仍参与统计，但 `calibration-suggestions` 会标注 review 状态。

### CLI 入口

```bash
python -m scripts.jd_feedback_note_parser parse \
  --note "这个人实际做销售支持，不是大模型平台产品负责人" \
  --candidate-context '{"candidate_id":"101","rank":1,"original_grade":"A","original_score":88}' \
  --jd-context '{"role_id":"training-inference-engineer"}' \
  --provider openai-compatible \
  --model deepseek-chat
```

批量入口（从含 `feedback_note` 的 CSV 解析）：

```bash
python -m scripts.jd_feedback_note_parser parse-csv \
  --csv reports/outreach-queue.csv \
  --out feedback/delivery-feedback-from-notes.json \
  --provider openai-compatible \
  --model deepseek-chat
```

### Schema 变更

`schemas/jd-delivery-feedback.schema.json` 的 `candidate_feedback.items` 新增可选字段：

```json
"parse_source": { "type": "string", "enum": ["rule", "llm", "manual"] },
"parse_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
```

现有 `load_feedback` 不强制这两个字段，向后兼容。

### 反馈指南更新

`docs/manual/jd-delivery-feedback-guide.md` 新增"最简模式"章节：

> 如果你时间很少，只填 `feedback_note` 一列即可。用中文写一句你对这个候选人的判断，系统会自动分析。例如："这个人实际做销售支持，不是我们要找的大模型平台产品负责人"。

原有 8 列填写方式保留为"详细模式"，供愿意精确填写的业务使用。

## 安全边界

1. 解析器不写 `data/talent.db`，不修改评分卡，不自动发布到飞书。
2. LLM 调用走现有 `create_llm_client`，API Key 由环境变量管理，不硬编码。
3. 低置信度解析不自动进入校准闭环；必须经 review 后人工确认或覆盖。
4. 外联表发布时 `feedback_note` 列内容可能含候选人评价，只保存在本地和飞书 Sheet，不上传到公开 Wiki 文档。
5. 批量解析前必须 dry-run，显示解析结果和置信度分布，确认后才写入 `delivery-feedback.json`。

## 测试策略

新增 `tests/test_jd_feedback_note_parser.py`：

- 规则层：否定/肯定/犹豫词正确映射 `feedback_label`。
- 规则层：职责不符、证据不足等模式正确映射 `reason_codes`。
- 规则层：无匹配时返回低置信度 + `feedback_label="待定"`。
- LLM 层（mock）：合法 JSON 输出正确解析。
- LLM 层（mock）：非法字段降级为安全默认值。
- LLM 层（mock）：调用失败降级为规则层兜底。
- CLI：单条解析和批量 CSV 解析输出格式正确。
- Review queue：低置信度条目进入队列，高置信度条目不进。
- 集成：解析结果直接传入 `compile_feedback_summary`，指标计算正确。

现有测试影响：
- `tests/test_jd_talent_delivery_match.py`：`FEEDBACK_CSV_FIELDS` 新增 `feedback_note`，空值断言需扩展。
- `tests/test_jd_talent_delivery_feishu.py`：`test_validate_delivery_package_allows_blank_feedback_columns` 需包含 `feedback_note`。
- `tests/test_jd_delivery_feedback.py`：`load_feedback` 仍兼容无 `parse_source`/`parse_confidence` 的旧 JSON。

## 分阶段落地

### 阶段 A：规则层解析器 + CSV 列追加

改造范围：
- 新增 `scripts/jd_feedback_note_parser.py`（规则层）
- 新增 `tests/test_jd_feedback_note_parser.py`
- 修改 `scripts/jd_talent_delivery_match.py`：`FEEDBACK_CSV_FIELDS` 追加 `feedback_note`
- 修改 `tests/test_jd_talent_delivery_match.py`、`tests/test_jd_talent_delivery_feishu.py`
- 修改 `schemas/jd-delivery-feedback.schema.json`：新增可选字段

验收标准：
- `feedback_note` 列出现在外联表
- 规则层能正确解析常见否定/肯定/犹豫模式
- 无匹配时返回低置信度 + 安全默认值
- 现有测试全部通过

### 阶段 B：LLM 层解析器 + Review Queue

改造范围：
- 扩展 `scripts/jd_feedback_note_parser.py`（LLM 层 + review queue）
- 扩展 `tests/test_jd_feedback_note_parser.py`
- 修改 `scripts/jd_delivery_feedback.py`：review queue 条目标注

验收标准：
- 规则层 `confidence < 0.7` 时自动调 LLM
- LLM 输出非法值时降级为安全默认值
- Review queue 正确收集低置信度条目
- `compile_feedback_summary` 仍正常工作

### 阶段 C：反馈指南更新 + Workflow 文档更新

改造范围：
- 更新 `docs/manual/jd-delivery-feedback-guide.md`：新增最简模式
- 更新 `agents/workflows/jd-talent-delivery/AGENT.md` S9：描述 `feedback_note` 入口
- 更新 `agents/skills/jd-talent-delivery/SKILL.md`

验收标准：
- 指南包含"只填 `feedback_note`"的最简路径
- Workflow 文档描述自然语言解析和 review queue

## 决策

本设计建议立即进入阶段 A，先落地规则层解析器和 CSV 列追加。规则层覆盖最常见的否定/肯定/犹豫模式，无需 LLM 依赖，可立即降低业务填写门槛。阶段 B 在阶段 A 验收后执行。

第一版成功标准：

1. 业务只需填 `feedback_note` 一列即可完成反馈。
2. 规则层对否定/肯定/犹豫模式解析置信度 >= 0.8。
3. 解析结果直接进入现有 `compile_feedback_summary` 闭环。
4. 低置信度条目不自动影响校准建议，进入 review queue。
5. 现有结构化填写路径完全保留，不影响已有用户。
