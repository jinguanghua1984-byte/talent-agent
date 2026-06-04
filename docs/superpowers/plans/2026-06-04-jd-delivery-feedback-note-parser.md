# JD Delivery Feedback Note Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace complex JD delivery outreach feedback fields with one business-facing `feedback_note` column and parse it into existing structured feedback artifacts through an LLM-gated review workflow.

**Architecture:** Keep `scripts/jd_delivery_feedback.py` as the structured feedback compiler. Add `scripts/jd_feedback_note_parser.py` for prompt construction, LLM JSON extraction, enum validation, review queue routing, run-root metadata loading, CSV parsing, dry-run previews, and CLI. Shrink outreach feedback to `feedback_note`, remove lifecycle boolean metrics, and update workflow/manual docs around subjective hunter feedback only.

**Tech Stack:** Python 3.12 via `.venv`, stdlib `argparse/csv/json/re/pathlib/datetime`, existing `scripts.llm_client`, `scripts.pipeline_utils`, and pytest.

---

## File Structure

- Create: `scripts/jd_feedback_note_parser.py` — LLM prompt, JSON extraction, parsed-field validation, review queue decisions, run-root CSV parsing, output writing, dry-run, CLI.
- Create: `tests/test_jd_feedback_note_parser.py` — fake LLM client tests for parsing, invalid fields, review queue, run-root output, dry-run, CLI.
- Modify: `scripts/jd_talent_delivery_match.py` — change `FEEDBACK_CSV_FIELDS` to only `feedback_note`.
- Modify: `tests/test_jd_talent_delivery_match.py` — assert only `feedback_note` exists and old feedback fields are absent.
- Modify: `tests/test_jd_talent_delivery_feishu.py` — update package validation fixture to the single feedback column.
- Modify: `scripts/jd_delivery_feedback.py` and `tests/test_jd_delivery_feedback.py` — remove lifecycle booleans and `actionable_at_30`, add optional parse metadata validation.
- Modify: `schemas/jd-delivery-feedback.schema.json` — remove lifecycle booleans; add optional `feedback_note`, `parse_source`, `parse_confidence`.
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`, `agents/skills/jd-talent-delivery/SKILL.md`, `tests/test_jd_talent_delivery_workflow.py`, `tests/test_jd_talent_delivery_skill.py`, `docs/manual/jd-delivery-feedback-guide.md` — document the simplified feedback contract.
- Modify: `tasks/todo.md` — final completion note only after implementation and verification.

---

### Task 1: Outreach CSV Feedback Surface

**Files:**
- Modify: `scripts/jd_talent_delivery_match.py`
- Modify: `tests/test_jd_talent_delivery_match.py`
- Modify: `tests/test_jd_talent_delivery_feishu.py`

- [ ] **Step 1: Write the failing outreach CSV assertion**

In `tests/test_jd_talent_delivery_match.py`, replace the existing feedback-field assertion inside `test_run_match_writes_expected_artifacts` with:

```python
    expected_feedback_fields = ["feedback_note"]
    removed_feedback_fields = [
        "feedback_label",
        "feedback_stage",
        "reason_codes",
        "hunter_note",
        "contacted",
        "submitted_to_client",
        "interviewed",
        "offer",
    ]
    for field in expected_feedback_fields:
        assert field in rows[0]
        assert rows[0][field] == ""
    for field in removed_feedback_fields:
        assert field not in rows[0]
```

- [ ] **Step 2: Update the Feishu package validation fixture**

In `tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_allows_blank_feedback_columns`, replace the outreach CSV fixture with:

```python
        (
            "candidate_id,company,title,score,grade,suggested_outreach_angle,profile_url,"
            "feedback_note\n"
            "1,腾讯,推理工程师,88,A,建议围绕腾讯推理工程师经历沟通,"
            "https://maimai.cn/profile/detail?dstu=1&trackable_token=secret,\n"
        ),
```

- [ ] **Step 3: Run the focused tests and verify red**

```bash
.venv/bin/python -m pytest \
  tests/test_jd_talent_delivery_match.py::test_run_match_writes_expected_artifacts \
  tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_allows_blank_feedback_columns \
  -q
```

Expected: FAIL because current CSV still has old feedback columns and no `feedback_note`.

- [ ] **Step 4: Implement the CSV field change**

In `scripts/jd_talent_delivery_match.py`, replace `FEEDBACK_CSV_FIELDS` with:

```python
FEEDBACK_CSV_FIELDS = [
    "feedback_note",
]
```

In `_outreach_row()`, replace the old feedback outputs with:

```python
        "feedback_note": "",
```

- [ ] **Step 5: Run the focused tests and verify green**

```bash
.venv/bin/python -m pytest \
  tests/test_jd_talent_delivery_match.py::test_run_match_writes_expected_artifacts \
  tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_allows_blank_feedback_columns \
  -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/jd_talent_delivery_match.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py
git commit -m "feat: simplify JD outreach feedback column"
```

---

### Task 2: Feedback Compiler and Schema Cleanup

**Files:**
- Modify: `scripts/jd_delivery_feedback.py`
- Modify: `tests/test_jd_delivery_feedback.py`
- Modify: `schemas/jd-delivery-feedback.schema.json`

- [ ] **Step 1: Update the feedback fixture**

In `tests/test_jd_delivery_feedback.py`, remove `contacted`, `submitted_to_client`, `interviewed`, and `offer` from all `_feedback()` candidate items. Add these parser fields to the first item:

```python
                "feedback_note": "候选人方向准确，可以沟通。",
                "parse_source": "llm",
                "parse_confidence": 0.93,
```

- [ ] **Step 2: Remove lifecycle validation test and update metrics assertion**

Delete `test_load_feedback_rejects_non_boolean_action_flags`.

In `test_compile_feedback_summary_calculates_topn_and_reason_metrics`, remove the `actionable_at_30` equality assertion and add:

```python
    assert "actionable_at_30" not in summary["metrics"]
```

- [ ] **Step 3: Add parse metadata validation tests**

Append:

```python
@pytest.mark.parametrize("parse_confidence", [-0.1, 1.1, "0.9"])
def test_load_feedback_rejects_invalid_parse_confidence(
    tmp_path: Path, parse_confidence: object
) -> None:
    data = _feedback()
    data["candidate_feedback"][0]["parse_confidence"] = parse_confidence
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="parse_confidence must be a number between 0 and 1"):
        load_feedback(path)


def test_load_feedback_accepts_optional_feedback_note_and_parse_source(tmp_path: Path) -> None:
    data = _feedback()
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    feedback = load_feedback(path)

    item = feedback["candidate_feedback"][0]
    assert item["feedback_note"] == "候选人方向准确，可以沟通。"
    assert item["parse_source"] == "llm"
    assert item["parse_confidence"] == 0.93
```

- [ ] **Step 4: Run focused tests and verify red**

```bash
.venv/bin/python -m pytest tests/test_jd_delivery_feedback.py -q
```

Expected: FAIL because `actionable_at_30` still exists and `parse_confidence` is not validated.

- [ ] **Step 5: Update `scripts/jd_delivery_feedback.py`**

Remove `ACTION_FIELDS` and `_as_bool()`.

Inside `load_feedback()`, after `candidate_id` validation, add:

```python
        if "parse_confidence" in item:
            parse_confidence = item["parse_confidence"]
            if (
                not isinstance(parse_confidence, (int, float))
                or isinstance(parse_confidence, bool)
                or parse_confidence < 0
                or parse_confidence > 1
            ):
                raise ValueError(
                    f"candidate_feedback item {index} parse_confidence must be a number between 0 and 1"
                )
```

In `compile_feedback_summary()`, remove `actionable_top_30` and remove:

```python
            "actionable_at_30": len(actionable_top_30),
```

- [ ] **Step 6: Update JSON schema**

In `schemas/jd-delivery-feedback.schema.json`, remove boolean properties `contacted`, `submitted_to_client`, `interviewed`, `offer` and add:

```json
"feedback_note": { "type": "string" },
"parse_source": { "enum": ["llm", "manual"] },
"parse_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
```

- [ ] **Step 7: Run focused tests and verify green**

```bash
.venv/bin/python -m pytest tests/test_jd_delivery_feedback.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add scripts/jd_delivery_feedback.py tests/test_jd_delivery_feedback.py schemas/jd-delivery-feedback.schema.json
git commit -m "feat: focus JD feedback metrics on hunter judgment"
```

---

### Task 3: LLM Feedback Note Parser Core

**Files:**
- Create: `scripts/jd_feedback_note_parser.py`
- Create: `tests/test_jd_feedback_note_parser.py`

- [ ] **Step 1: Create parser core tests**

Create `tests/test_jd_feedback_note_parser.py` with a fake client and these test names:

```python
from __future__ import annotations

import json

import pytest

from scripts.jd_feedback_note_parser import build_feedback_prompt, extract_json_object, parse_feedback_note


class FakeClient:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        self.calls.append({"messages": messages, "model": model, "max_tokens": max_tokens})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_build_feedback_prompt_includes_field_meanings_and_note() -> None:
    prompt = build_feedback_prompt("这个人不适合，实际做销售支持")
    for token in ["feedback_label", "认可", "待定", "不认可", "feedback_stage", "reason_codes", "keyword_hit_but_wrong_duty", "parse_confidence", "这个人不适合，实际做销售支持"]:
        assert token in prompt


@pytest.mark.parametrize(
    "text",
    [
        '{"feedback_label":"认可","feedback_stage":"匹配","reason_codes":[],"hunter_note":"方向对","parse_confidence":0.95}',
        '```json\n{"feedback_label":"认可","feedback_stage":"匹配","reason_codes":[],"hunter_note":"方向对","parse_confidence":0.95}\n```',
        '解析结果如下：{"feedback_label":"认可","feedback_stage":"匹配","reason_codes":[],"hunter_note":"方向对","parse_confidence":0.95}',
    ],
)
def test_extract_json_object_accepts_common_llm_wrappers(text: str) -> None:
    data = extract_json_object(text)
    assert data["feedback_label"] == "认可"
    assert data["parse_confidence"] == 0.95


def test_parse_feedback_note_returns_valid_high_confidence_result() -> None:
    client = FakeClient(json.dumps({"feedback_label": "不认可", "feedback_stage": "匹配", "reason_codes": ["keyword_hit_but_wrong_duty"], "hunter_note": "实际做销售支持，不是岗位目标人选。", "parse_confidence": 0.92}, ensure_ascii=False))
    result = parse_feedback_note("这个人实际做销售支持，不是我们要找的人", client=client, model="test")
    assert result["feedback_label"] == "不认可"
    assert result["review_required"] is False
    assert result["review_reasons"] == []


def test_parse_feedback_note_downgrades_invalid_fields_to_review_queue() -> None:
    client = FakeClient(json.dumps({"feedback_label": "不合适", "feedback_stage": "未知阶段", "reason_codes": ["unknown_code", "evidence_too_shallow"], "hunter_note": "证据不够。", "parse_confidence": 0.82}, ensure_ascii=False))
    result = parse_feedback_note("证据不够", client=client, model="test")
    assert result["feedback_label"] == "待定"
    assert result["feedback_stage"] == "匹配"
    assert result["reason_codes"] == ["evidence_too_shallow"]
    assert result["parse_confidence"] == 0.0
    assert result["review_required"] is True
    assert "invalid_feedback_label" in result["review_reasons"]


def test_parse_feedback_note_low_confidence_requires_review() -> None:
    client = FakeClient(json.dumps({"feedback_label": "待定", "feedback_stage": "匹配", "reason_codes": [], "hunter_note": "这人感觉一般。", "parse_confidence": 0.4}, ensure_ascii=False))
    result = parse_feedback_note("这人感觉一般", client=client, model="test")
    assert result["review_required"] is True
    assert "low_confidence" in result["review_reasons"]


def test_parse_feedback_note_handles_llm_failure_as_review_required() -> None:
    result = parse_feedback_note("这个人不适合", client=FakeClient(RuntimeError("network down")), model="test")
    assert result["feedback_label"] == "待定"
    assert result["hunter_note"] == "这个人不适合"
    assert result["parse_confidence"] == 0.0
    assert result["review_required"] is True
    assert "llm_error" in result["review_reasons"]
```

- [ ] **Step 2: Run parser tests and verify red**

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement parser core**

Create `scripts/jd_feedback_note_parser.py` with functions `build_feedback_prompt()`, `extract_json_object()`, `normalize_parsed_feedback()`, and `parse_feedback_note()`. The implementation must:

- import `VALID_FEEDBACK_LABELS`, `VALID_FEEDBACK_STAGES`, `VALID_REASON_CODES` from `scripts.jd_delivery_feedback`
- call `scripts.pipeline_utils.call_llm_with_retry()` and `create_llm_client()`
- parse full JSON, fenced JSON, and first JSON object in text
- return fields `feedback_label`, `feedback_stage`, `reason_codes`, `hunter_note`, `feedback_note`, `parse_source`, `parse_confidence`, `review_required`, `review_reasons`
- use fallback `{label: "待定", stage: "匹配", reason_codes: [], confidence: 0.0}` on LLM or JSON errors

Use this signature:

```python
def parse_feedback_note(
    feedback_note: str,
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
```

- [ ] **Step 4: Run parser tests and verify green**

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/jd_feedback_note_parser.py tests/test_jd_feedback_note_parser.py
git commit -m "feat: add LLM feedback note parser core"
```

---

### Task 4: Run-Root CSV Parsing, Review Queue, and CLI

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `tests/test_jd_feedback_note_parser.py`

- [ ] **Step 1: Add run-root and CLI tests**

Extend `tests/test_jd_feedback_note_parser.py` with tests for:

```python
from pathlib import Path

from scripts.jd_feedback_note_parser import main, parse_feedback_csv


class QueueClient:
    def __init__(self, responses: list[str]):
        self.responses = responses

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        return self.responses.pop(0)
```

Add helper `_run_root(tmp_path)` that writes:

```text
run-manifest.json                            # {"schema":"jd_talent_delivery_run_manifest_v1","output_dir":"<root>"}
profile/role-profile.json                    # {"schema":"jd_talent_delivery_role_profile_v1","role_id":"demo-role"}
scoring/scorecard.json                       # {"schema":"jd_talent_delivery_scorecard_v1","role_id":"demo-role","version":"v1"}
reports/outreach-queue.csv                   # candidate_id,rank,name,score,grade,feedback_note
```

Write three tests:

```python
def test_parse_feedback_csv_writes_delivery_feedback_and_review_queue(tmp_path: Path) -> None: ...
def test_parse_feedback_csv_dry_run_does_not_write_outputs(tmp_path: Path) -> None: ...
def test_cli_parse_csv_uses_run_root(tmp_path: Path) -> None: ...
```

Assertions must verify:

- two non-empty notes are parsed, one accepted and one review-required
- `delivery-feedback.json` has `schema`, `role_id`, `scorecard_version`, and one accepted candidate
- `parse-review-queue.json` has one pending item
- `feedback-summary.json` exists only in non-dry-run
- CLI `main(["parse-csv", "--run-root", str(root), "--model", "test"], client=client)` returns `0`

- [ ] **Step 2: Run tests and verify red**

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py -q
```

Expected: FAIL because `parse_feedback_csv` and CLI batch handling do not exist.

- [ ] **Step 3: Implement run-root parsing and output writing**

Add to `scripts/jd_feedback_note_parser.py`:

```python
def parse_feedback_csv(
    run_root: str | Path,
    *,
    csv_path: str | Path | None = None,
    out_path: str | Path | None = None,
    review_out_path: str | Path | None = None,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
```

Implementation requirements:

- read metadata from `run-manifest.json`, `profile/role-profile.json`, `scoring/scorecard.json`
- default CSV path to `<run-root>/reports/outreach-queue.csv`
- default outputs to `<run-root>/feedback/delivery-feedback.json` and `<run-root>/feedback/parse-review-queue.json`
- skip empty `feedback_note`
- write only `review_required=false` items to `delivery-feedback.json`
- write `review_required=true` items to `parse-review-queue.json` with `review_status="pending"`
- write `feedback-summary.json` and `calibration-suggestions.json` using existing compiler helpers
- in `dry_run=True`, return counts and write no files

- [ ] **Step 4: Implement CLI**

Add `main(argv=None, *, client=None)` with subcommands:

```bash
parse --note <text> --out <json> [--provider <provider>] [--model <model>]
parse-csv --run-root <path> [--csv <path>] [--out <path>] [--review-out <path>] [--provider <provider>] [--model <model>] [--dry-run]
```

On validation or IO errors, print `error: <message>` to stderr and return `1` without traceback.

- [ ] **Step 5: Run parser tests and verify green**

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add scripts/jd_feedback_note_parser.py tests/test_jd_feedback_note_parser.py
git commit -m "feat: parse JD feedback notes from run artifacts"
```

---

### Task 5: Workflow, Skill, and Manual Documentation

**Files:**
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Modify: `agents/skills/jd-talent-delivery/SKILL.md`
- Modify: `tests/test_jd_talent_delivery_workflow.py`
- Modify: `tests/test_jd_talent_delivery_skill.py`
- Modify: `docs/manual/jd-delivery-feedback-guide.md`

- [ ] **Step 1: Update workflow and skill tests**

In `tests/test_jd_talent_delivery_workflow.py::test_workflow_documents_feedback_collection_contract`, assert these tokens exist:

```python
[
    "feedback_note",
    "feedback/delivery-feedback.json",
    "feedback/parse-review-queue.json",
    "feedback/feedback-summary.json",
    "feedback/calibration-suggestions.json",
    "python -m scripts.jd_feedback_note_parser parse-csv --run-root <run_root>",
    "不得写入 data/talent.db",
    "accepted_at_30",
    "bad_at_10",
]
```

Also assert:

```python
assert "actionable_at_30" not in text
```

In `tests/test_jd_talent_delivery_skill.py::test_skill_documents_feedback_followup_contract`, assert `feedback_note`, `jd_feedback_note_parser`, `parse-review-queue.json`, `delivery-feedback.json`, and `只生成校准建议` exist; assert `actionable_at_30` is absent.

- [ ] **Step 2: Run docs contract tests and verify red**

```bash
.venv/bin/python -m pytest \
  tests/test_jd_talent_delivery_workflow.py::test_workflow_documents_feedback_collection_contract \
  tests/test_jd_talent_delivery_skill.py::test_skill_documents_feedback_followup_contract \
  -q
```

Expected: FAIL because docs still describe old columns and old metric.

- [ ] **Step 3: Update workflow S9 and skill contract**

In both `agents/workflows/jd-talent-delivery/AGENT.md` S9 and `agents/skills/jd-talent-delivery/SKILL.md` feedback section, describe:

- external feedback column is only `feedback_note`
- parser command is `python -m scripts.jd_feedback_note_parser parse-csv --run-root <run_root>`
- AI parses into internal `feedback_label`, `feedback_stage`, `reason_codes`, `hunter_note`
- low confidence or downgraded rows go to `feedback/parse-review-queue.json` and do not enter calibration by default
- outputs are `delivery-feedback.json`, `parse-review-queue.json`, `feedback-summary.json`, `calibration-suggestions.json`
- metrics include `accepted_at_30`, `bad_at_10`, reason distribution, grade acceptance rate
- no DB write, no automatic scorecard edit, no automatic Wiki publishing of notes

- [ ] **Step 4: Rewrite the manual around one column**

In `docs/manual/jd-delivery-feedback-guide.md`, make `feedback_note` the first and primary instruction. Include this table:

```markdown
| 场景 | `feedback_note` |
| --- | --- |
| 认可 | `方向匹配，有大模型平台经验，建议优先联系。` |
| 待定 | `公司和标题相关，但看不出是否真正负责核心模块，需要再确认。` |
| 不认可 | `关键词命中了，但实际做销售支持，不是我们要找的大模型平台产品负责人。` |
```

Remove or mark old eight-column instructions as obsolete.

- [ ] **Step 5: Run docs contract tests and verify green**

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add agents/workflows/jd-talent-delivery/AGENT.md agents/skills/jd-talent-delivery/SKILL.md tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py docs/manual/jd-delivery-feedback-guide.md
git commit -m "docs: simplify JD feedback collection contract"
```

---

### Task 6: Integration Verification and Task Ledger Cleanup

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused feature tests**

```bash
.venv/bin/python -m pytest \
  tests/test_jd_feedback_note_parser.py \
  tests/test_jd_delivery_feedback.py \
  tests/test_jd_talent_delivery_match.py \
  tests/test_jd_talent_delivery_feishu.py \
  tests/test_jd_talent_delivery_workflow.py \
  tests/test_jd_talent_delivery_skill.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

```bash
.venv/bin/python -m pytest tests -q
```

Expected: PASS. Existing unrelated warnings are acceptable only if they are already present.

- [ ] **Step 3: Run diff checks**

```bash
git diff --check
git status --short
```

Expected: `git diff --check` prints no output. `git status --short` should show only intended files before final commit.

- [ ] **Step 4: Update `tasks/todo.md` with final review**

Replace stale “规则优先 + LLM 兜底” text with:

```markdown
阶段结果：
- 正式 spec：`docs/superpowers/specs/2026-06-04-jd-delivery-natural-language-feedback-design.md`。
- 实施计划：`docs/superpowers/plans/2026-06-04-jd-delivery-feedback-note-parser.md`。
- 设计决策：外联表只保留 `feedback_note`；LLM 直接解析；低置信度/降级条目进入 `parse-review-queue.json` 且默认不进入校准闭环；移除生命周期布尔列和 `actionable_at_30`。
- 验证：记录本轮聚焦测试、全量测试和 `git diff --check` 结果。
```

- [ ] **Step 5: Commit final cleanup**

```bash
git add tasks/todo.md
git commit -m "chore: record JD feedback note parser completion"
```

---

## Final Verification Commands

Run these before reporting completion:

```bash
.venv/bin/python -m pytest tests -q
git diff --check
git status --short
```

Report exact test counts, warnings, and any remaining untracked files.

