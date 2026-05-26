# JD Delivery Feedback Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add phase-one JD delivery feedback collection and compilation so Top30 recommendations can receive structured senior-hunter feedback and produce local calibration summaries.

**Architecture:** Keep the current JD delivery execution path deterministic. Add a focused feedback compiler under `scripts/`, append empty feedback columns to the existing outreach CSV, and keep publish validation compatible with the wider CSV. Feedback is collected and compiled as local artifacts; it does not write `data/talent.db` and does not automatically modify scorecards.

**Tech Stack:** Python 3.12 via the project `.venv`, pytest, stdlib `csv/json/argparse`, existing JD delivery scripts, Markdown workflow docs, Feishu Sheets through the existing publish path.

---

## File Structure

- Create: `scripts/jd_delivery_feedback.py`
  - Owns JD delivery feedback validation, reason-code taxonomy, summary metrics, calibration suggestions, and CLI output.
- Create: `schemas/jd-delivery-feedback.schema.json`
  - Documents the JSON artifact contract for `feedback/delivery-feedback.json`.
- Create: `tests/test_jd_delivery_feedback.py`
  - Unit tests for validation, summary metrics, reason distributions, and CLI output.
- Modify: `scripts/jd_talent_delivery_match.py`
  - Appends blank feedback columns to `reports/outreach-queue.csv` through `CSV_FIELDS` and `_outreach_row()`.
- Modify: `tests/test_jd_talent_delivery_match.py`
  - Locks outreach CSV feedback columns and confirms generated values are blank by default.
- Modify: `scripts/jd_talent_delivery_feishu.py`
  - Keeps delivery package validation compatible with appended feedback columns and includes the columns in Sheet writes through the existing CSV-to-Sheet path.
- Modify: `tests/test_jd_talent_delivery_feishu.py`
  - Adds a publish/readback-focused assertion that feedback headers are preserved and are not required for package validity.
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
  - Documents the optional post-delivery feedback artifacts and states that feedback import is local/dry-run by default.
- Modify: `skills/jd-talent-delivery/SKILL.md`
  - Mirrors the feedback collection contract for runtime adapters.
- Modify: `tests/test_jd_talent_delivery_workflow.py`
  - Verifies workflow text names feedback artifacts, reason-code feedback, and no main DB writes.
- Modify: `tests/test_jd_talent_delivery_skill.py`
  - Verifies skill text exposes the feedback collection contract.

---

### Task 1: Feedback Compiler Contract

**Files:**
- Create: `scripts/jd_delivery_feedback.py`
- Create: `schemas/jd-delivery-feedback.schema.json`
- Create: `tests/test_jd_delivery_feedback.py`

- [ ] **Step 1: Write the failing feedback validation and summary tests**

Create `tests/test_jd_delivery_feedback.py` with these tests:

```python
import json
from pathlib import Path

import pytest

from scripts.jd_delivery_feedback import (
    compile_feedback_summary,
    load_feedback,
    main,
)


def _feedback() -> dict:
    return {
        "schema": "jd_delivery_feedback_v1",
        "role_id": "training-inference-engineer",
        "run_id": "data/output/training-inference-2026-05-25",
        "profile_version": "role-profile-v1",
        "scorecard_version": "v3-recall-balanced",
        "source_report": "reports/talent-recommendation.json",
        "source_outreach_sheet": "reports/outreach-queue.csv",
        "reviewer_role": "senior_hunter",
        "candidate_feedback": [
            {
                "candidate_id": "101",
                "rank": 1,
                "original_grade": "A",
                "original_score": 88,
                "feedback_label": "认可",
                "feedback_stage": "匹配",
                "reason_codes": ["strong_candidate_ranked_low"],
                "hunter_note": "候选人方向准确，可以沟通。",
                "contacted": True,
                "submitted_to_client": True,
                "interviewed": False,
                "offer": False,
            },
            {
                "candidate_id": "102",
                "rank": 2,
                "original_grade": "A",
                "original_score": 84,
                "feedback_label": "不认可",
                "feedback_stage": "匹配",
                "reason_codes": ["keyword_hit_but_wrong_duty", "evidence_too_shallow"],
                "hunter_note": "词命中，但实际做应用层。",
                "contacted": False,
                "submitted_to_client": False,
                "interviewed": False,
                "offer": False,
            },
            {
                "candidate_id": "130",
                "rank": 30,
                "original_grade": "C",
                "original_score": 63,
                "feedback_label": "认可",
                "feedback_stage": "评分卡",
                "reason_codes": ["scorecard_bad_threshold"],
                "hunter_note": "分数偏低，但实际经历很好。",
                "contacted": True,
                "submitted_to_client": False,
                "interviewed": False,
                "offer": False,
            },
        ],
    }


def test_load_feedback_validates_and_preserves_items(tmp_path: Path) -> None:
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(_feedback(), ensure_ascii=False), encoding="utf-8")

    feedback = load_feedback(path)

    assert feedback["schema"] == "jd_delivery_feedback_v1"
    assert feedback["candidate_feedback"][0]["candidate_id"] == "101"


def test_load_feedback_rejects_unknown_reason_code(tmp_path: Path) -> None:
    data = _feedback()
    data["candidate_feedback"][0]["reason_codes"] = ["unknown_reason"]
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown feedback reason codes: unknown_reason"):
        load_feedback(path)


def test_compile_feedback_summary_calculates_topn_and_reason_metrics() -> None:
    summary = compile_feedback_summary(_feedback())

    assert summary["schema"] == "jd_delivery_feedback_summary_v1"
    assert summary["role_id"] == "training-inference-engineer"
    assert summary["metrics"]["accepted_at_10"] == 1
    assert summary["metrics"]["accepted_at_30"] == 2
    assert summary["metrics"]["actionable_at_30"] == 2
    assert summary["metrics"]["bad_at_10"] == 1
    assert summary["reason_distribution"]["evidence_too_shallow"] == 1
    assert summary["grade_acceptance_rate"]["A"]["accepted"] == 1
    assert summary["grade_acceptance_rate"]["A"]["total"] == 2
    assert summary["grade_acceptance_rate"]["C"]["accepted"] == 1
    assert "weak_candidate_ranked_high" in summary["calibration_suggestions"]
    assert "scorecard_threshold_review" in summary["calibration_suggestions"]


def test_cli_writes_summary_and_calibration_files(tmp_path: Path) -> None:
    feedback_path = tmp_path / "delivery-feedback.json"
    summary_path = tmp_path / "feedback-summary.json"
    suggestions_path = tmp_path / "calibration-suggestions.json"
    feedback_path.write_text(json.dumps(_feedback(), ensure_ascii=False), encoding="utf-8")

    exit_code = main(
        [
            "compile",
            "--feedback",
            str(feedback_path),
            "--summary-out",
            str(summary_path),
            "--suggestions-out",
            str(suggestions_path),
        ]
    )

    assert exit_code == 0
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    suggestions = json.loads(suggestions_path.read_text(encoding="utf-8-sig"))
    assert summary["metrics"]["accepted_at_30"] == 2
    assert suggestions["schema"] == "jd_delivery_calibration_suggestions_v1"
    assert "keyword_hit_but_wrong_duty" in suggestions["reason_distribution"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_delivery_feedback.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.jd_delivery_feedback'`.

- [ ] **Step 3: Create the feedback compiler module**

Create `scripts/jd_delivery_feedback.py`:

```python
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA = "jd_delivery_feedback_v1"
SUMMARY_SCHEMA = "jd_delivery_feedback_summary_v1"
SUGGESTIONS_SCHEMA = "jd_delivery_calibration_suggestions_v1"

VALID_FEEDBACK_LABELS = {"认可", "待定", "不认可"}
VALID_FEEDBACK_STAGES = {"画像", "评分卡", "匹配", "报告", "候选人状态"}
VALID_GRADES = {"A", "B", "C", "淘汰"}
VALID_REASON_CODES = {
    "jd_profile_too_broad",
    "jd_profile_too_narrow",
    "must_have_overloaded",
    "missing_key_requirement",
    "wrong_role_type",
    "scorecard_wrong_weight",
    "scorecard_missing_dimension",
    "scorecard_bad_threshold",
    "company_pool_wrong",
    "title_alias_wrong",
    "keyword_hit_but_wrong_duty",
    "evidence_too_shallow",
    "seniority_mismatch",
    "recent_experience_missing",
    "strong_candidate_ranked_low",
    "weak_candidate_ranked_high",
    "evidence_hard_to_verify",
    "outreach_angle_weak",
    "risk_not_called_out",
    "candidate_unavailable",
    "candidate_duplicate",
    "candidate_info_stale",
}


def _read_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("feedback JSON must be an object")
    return data


def _as_bool(value: Any) -> bool:
    return value is True or str(value).strip().casefold() in {"true", "1", "yes", "y"}


def load_feedback(path: str | Path) -> dict[str, Any]:
    data = _read_json(path)
    if data.get("schema") != SCHEMA:
        raise ValueError("invalid feedback schema")
    items = data.get("candidate_feedback")
    if not isinstance(items, list):
        raise ValueError("candidate_feedback must be a list")
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"candidate_feedback item {index} must be an object")
        label = item.get("feedback_label")
        if label not in VALID_FEEDBACK_LABELS:
            raise ValueError(f"invalid feedback label: {label}")
        stage = item.get("feedback_stage")
        if stage not in VALID_FEEDBACK_STAGES:
            raise ValueError(f"invalid feedback stage: {stage}")
        grade = item.get("original_grade")
        if grade not in VALID_GRADES:
            raise ValueError(f"invalid original grade: {grade}")
        reason_codes = item.get("reason_codes") or []
        if not isinstance(reason_codes, list):
            raise ValueError(f"candidate_feedback item {index} reason_codes must be a list")
        unknown = sorted(set(str(code) for code in reason_codes) - VALID_REASON_CODES)
        if unknown:
            raise ValueError("unknown feedback reason codes: " + ", ".join(unknown))
        rank = item.get("rank")
        if not isinstance(rank, int) or rank <= 0:
            raise ValueError(f"candidate_feedback item {index} rank must be a positive integer")
        if not str(item.get("candidate_id") or "").strip():
            raise ValueError(f"candidate_feedback item {index} missing candidate_id")
    return data


def _grade_acceptance(items: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {
        grade: {"accepted": 0, "tentative": 0, "rejected": 0, "total": 0}
        for grade in ("A", "B", "C", "淘汰")
    }
    for item in items:
        grade = str(item.get("original_grade") or "")
        if grade not in result:
            continue
        result[grade]["total"] += 1
        label = str(item.get("feedback_label") or "")
        if label == "认可":
            result[grade]["accepted"] += 1
        elif label == "待定":
            result[grade]["tentative"] += 1
        elif label == "不认可":
            result[grade]["rejected"] += 1
    return result


def _calibration_suggestions(reason_counts: Counter[str]) -> list[str]:
    suggestions: list[str] = []
    if reason_counts.get("keyword_hit_but_wrong_duty") or reason_counts.get("evidence_too_shallow"):
        suggestions.append("weak_candidate_ranked_high")
    if reason_counts.get("scorecard_bad_threshold"):
        suggestions.append("scorecard_threshold_review")
    if reason_counts.get("must_have_overloaded") or reason_counts.get("jd_profile_too_broad"):
        suggestions.append("profile_must_have_review")
    if reason_counts.get("company_pool_wrong") or reason_counts.get("title_alias_wrong"):
        suggestions.append("search_signal_review")
    return suggestions


def compile_feedback_summary(feedback: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in feedback.get("candidate_feedback") or [] if isinstance(item, dict)]
    reason_counts: Counter[str] = Counter()
    for item in items:
        reason_counts.update(str(code) for code in item.get("reason_codes") or [])

    accepted_top_10 = [item for item in items if item["rank"] <= 10 and item["feedback_label"] == "认可"]
    accepted_top_30 = [item for item in items if item["rank"] <= 30 and item["feedback_label"] == "认可"]
    bad_top_10 = [item for item in items if item["rank"] <= 10 and item["feedback_label"] == "不认可"]
    actionable_top_30 = [
        item
        for item in items
        if item["rank"] <= 30
        and any(
            _as_bool(item.get(field))
            for field in ("contacted", "submitted_to_client", "interviewed", "offer")
        )
    ]

    return {
        "schema": SUMMARY_SCHEMA,
        "role_id": feedback.get("role_id") or "",
        "run_id": feedback.get("run_id") or "",
        "profile_version": feedback.get("profile_version") or "",
        "scorecard_version": feedback.get("scorecard_version") or "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "metrics": {
            "accepted_at_10": len(accepted_top_10),
            "accepted_at_30": len(accepted_top_30),
            "actionable_at_30": len(actionable_top_30),
            "bad_at_10": len(bad_top_10),
        },
        "reason_distribution": dict(sorted(reason_counts.items())),
        "grade_acceptance_rate": _grade_acceptance(items),
        "calibration_suggestions": _calibration_suggestions(reason_counts),
    }


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def build_suggestions(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": SUGGESTIONS_SCHEMA,
        "role_id": summary.get("role_id") or "",
        "run_id": summary.get("run_id") or "",
        "reason_distribution": summary.get("reason_distribution") or {},
        "calibration_suggestions": summary.get("calibration_suggestions") or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compile JD delivery feedback")
    subparsers = parser.add_subparsers(dest="command", required=True)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--feedback", required=True)
    compile_parser.add_argument("--summary-out", required=True)
    compile_parser.add_argument("--suggestions-out", required=True)
    args = parser.parse_args(argv)

    feedback = load_feedback(args.feedback)
    summary = compile_feedback_summary(feedback)
    write_json(args.summary_out, summary)
    write_json(args.suggestions_out, build_suggestions(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add the JSON schema document**

Create `schemas/jd-delivery-feedback.schema.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "JD Delivery Feedback",
  "type": "object",
  "required": ["schema", "role_id", "run_id", "profile_version", "scorecard_version", "candidate_feedback"],
  "properties": {
    "schema": { "const": "jd_delivery_feedback_v1" },
    "role_id": { "type": "string", "minLength": 1 },
    "run_id": { "type": "string", "minLength": 1 },
    "profile_version": { "type": "string", "minLength": 1 },
    "scorecard_version": { "type": "string", "minLength": 1 },
    "source_report": { "type": "string" },
    "source_outreach_sheet": { "type": "string" },
    "reviewer_role": { "type": "string" },
    "candidate_feedback": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["candidate_id", "rank", "original_grade", "original_score", "feedback_label", "feedback_stage", "reason_codes"],
        "properties": {
          "candidate_id": { "type": "string", "minLength": 1 },
          "rank": { "type": "integer", "minimum": 1 },
          "original_grade": { "enum": ["A", "B", "C", "淘汰"] },
          "original_score": { "type": "number" },
          "feedback_label": { "enum": ["认可", "待定", "不认可"] },
          "feedback_stage": { "enum": ["画像", "评分卡", "匹配", "报告", "候选人状态"] },
          "reason_codes": { "type": "array", "items": { "type": "string" } },
          "hunter_note": { "type": "string" },
          "contacted": { "type": "boolean" },
          "submitted_to_client": { "type": "boolean" },
          "interviewed": { "type": "boolean" },
          "offer": { "type": "boolean" }
        },
        "additionalProperties": true
      }
    }
  },
  "additionalProperties": true
}
```

- [ ] **Step 5: Run feedback tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_delivery_feedback.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/jd_delivery_feedback.py schemas/jd-delivery-feedback.schema.json tests/test_jd_delivery_feedback.py
git commit -m "feat: add jd delivery feedback compiler"
```

---

### Task 2: Outreach Feedback Columns

**Files:**
- Modify: `scripts/jd_talent_delivery_match.py`
- Modify: `tests/test_jd_talent_delivery_match.py`

- [ ] **Step 1: Write the failing outreach column assertion**

In `tests/test_jd_talent_delivery_match.py`, extend `test_run_match_outputs_reports_and_outreach` after `rows = list(csv.DictReader(handle))`:

```python
    expected_feedback_fields = [
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
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_match.py::test_run_match_outputs_reports_and_outreach -q
```

Expected: FAIL because `feedback_label` is not in the generated CSV row.

- [ ] **Step 3: Add feedback columns to CSV output**

In `scripts/jd_talent_delivery_match.py`, add this constant after `CSV_FIELDS`:

```python
FEEDBACK_CSV_FIELDS = [
    "feedback_label",
    "feedback_stage",
    "reason_codes",
    "hunter_note",
    "contacted",
    "submitted_to_client",
    "interviewed",
    "offer",
]
```

Then change the `csv.DictWriter` line in `_write_outreach_csv()` from:

```python
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
```

to:

```python
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS + FEEDBACK_CSV_FIELDS)
```

Finally, extend the dictionary returned by `_outreach_row()` with blank values:

```python
        "feedback_label": "",
        "feedback_stage": "",
        "reason_codes": "",
        "hunter_note": "",
        "contacted": "",
        "submitted_to_client": "",
        "interviewed": "",
        "offer": "",
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_match.py::test_run_match_outputs_reports_and_outreach -q
```

Expected: `1 passed`.

- [ ] **Step 5: Run package quality tests that read outreach CSV**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_blocks_bad_quality_gate -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add scripts/jd_talent_delivery_match.py tests/test_jd_talent_delivery_match.py
git commit -m "feat: add jd feedback columns to outreach csv"
```

---

### Task 3: Publish Preflight Compatibility

**Files:**
- Modify: `tests/test_jd_talent_delivery_feishu.py`
- Modify: `scripts/jd_talent_delivery_feishu.py`

- [ ] **Step 1: Add a test that feedback columns do not block publish validation**

Add this test to `tests/test_jd_talent_delivery_feishu.py` near the existing package validation tests:

```python
def test_validate_delivery_package_allows_blank_feedback_columns(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    recommendation = {
        "schema": "jd_talent_delivery_recommendation_v1",
        "top_n": 1,
        "ranked": [
            {
                "candidate_id": 1,
                "score": 88,
                "grade": "A",
                "recommendation_label": "强推荐",
                "profile_url": "https://maimai.cn/profile/detail/1",
                "evidence": {"key_evidence": ["腾讯", "推理系统"]},
            }
        ],
    }
    _write(root / "reports" / "talent-recommendation.json", json.dumps(recommendation, ensure_ascii=False))
    _write(root / "scoring" / "detailed-rank.json", json.dumps(recommendation, ensure_ascii=False))
    _write(
        root / "reports" / "outreach-queue.csv",
        (
            "candidate_id,company,title,score,grade,suggested_outreach_angle,profile_url,"
            "feedback_label,feedback_stage,reason_codes,hunter_note,contacted,"
            "submitted_to_client,interviewed,offer\n"
            "1,腾讯,推理工程师,88,A,建议围绕腾讯推理工程师经历沟通,"
            "https://maimai.cn/profile/detail/1,,,,,,,,\n"
        ),
    )

    result = validate_delivery_package(root)

    assert result["status"] == "passed"
    assert result["critical_issues"] == []
```

- [ ] **Step 2: Run the test**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_allows_blank_feedback_columns -q
```

Expected: PASS if the existing validation already tolerates extra columns. If it fails with a missing required field, inspect the row literal and fix only the test fixture typo. If it fails because validation rejects extra fields, continue to Step 3.

- [ ] **Step 3: Keep validation focused on required delivery fields**

If Step 2 fails due to extra-column handling, update `_read_csv_rows()` or the validation loop in `scripts/jd_talent_delivery_feishu.py` so it ignores columns not listed in `required_csv_fields`. Do not add feedback fields to `required_csv_fields`; feedback is optional at publish time.

The required fields remain:

```python
required_csv_fields = {
    "candidate_id",
    "company",
    "title",
    "score",
    "grade",
    "suggested_outreach_angle",
    "profile_url",
}
```

- [ ] **Step 4: Run Feishu focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_feishu.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_feishu.py
git commit -m "test: cover jd feedback columns in publish validation"
```

---

### Task 4: Workflow and Skill Documentation

**Files:**
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Modify: `skills/jd-talent-delivery/SKILL.md`
- Modify: `tests/test_jd_talent_delivery_workflow.py`
- Modify: `tests/test_jd_talent_delivery_skill.py`

- [ ] **Step 1: Add workflow documentation tests**

In `tests/test_jd_talent_delivery_workflow.py`, add:

```python
def test_workflow_documents_feedback_collection_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    for token in [
        "feedback/delivery-feedback.json",
        "feedback/feedback-summary.json",
        "feedback/calibration-suggestions.json",
        "反馈导入默认 dry-run",
        "不得写入 data/talent.db",
        "reason_codes",
        "accepted_at_30",
        "actionable_at_30",
    ]:
        assert token in text
```

- [ ] **Step 2: Add skill documentation tests**

In `tests/test_jd_talent_delivery_skill.py`, add:

```python
def test_skill_documents_feedback_followup_contract() -> None:
    text = _text()

    for token in [
        "猎头反馈",
        "feedback_label",
        "reason_codes",
        "delivery-feedback.json",
        "feedback-summary.json",
        "只生成校准建议",
    ]:
        assert token in text
```

- [ ] **Step 3: Run documentation tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_workflow.py::test_workflow_documents_feedback_collection_contract tests/test_jd_talent_delivery_skill.py::test_skill_documents_feedback_followup_contract -q
```

Expected: FAIL because the workflow and skill do not yet document the feedback follow-up contract.

- [ ] **Step 4: Update the workflow**

In `agents/workflows/jd-talent-delivery/AGENT.md`, add this section after S8:

```markdown
### S9：猎头反馈回收（可选后续）

S9 不属于默认连续执行链路，只有用户要求回收或编译猎头反馈时才执行。S9 读取已发布的外联表反馈列或本地反馈 JSON，生成本地反馈产物：

- `feedback/delivery-feedback.json`
- `feedback/feedback-summary.json`
- `feedback/calibration-suggestions.json`

反馈列至少包含 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`、`contacted`、`submitted_to_client`、`interviewed` 和 `offer`。反馈导入默认 dry-run，不得写入 `data/talent.db`，不得自动修改 `scoring/scorecard.json`，不得把猎头备注自动发布到 Wiki。

反馈编译指标至少包含 `accepted_at_30`、`actionable_at_30` 和 `bad_at_10`。输出只能作为下一轮岗位画像、评分卡和匹配策略的校准建议。
```

- [ ] **Step 5: Update the skill**

In `skills/jd-talent-delivery/SKILL.md`, add this paragraph near the output contract:

```markdown
## 猎头反馈后续

当用户要求回收或分析猎头反馈时，读取外联表反馈列或本地 `feedback/delivery-feedback.json`，编译 `feedback/feedback-summary.json` 和 `feedback/calibration-suggestions.json`。反馈列包含 `feedback_label`、`feedback_stage`、`reason_codes`、`hunter_note`、`contacted`、`submitted_to_client`、`interviewed` 和 `offer`。本步骤只生成校准建议，不写 `data/talent.db`，不自动修改评分卡，不自动发布猎头备注。
```

- [ ] **Step 6: Run documentation tests to verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_workflow.py::test_workflow_documents_feedback_collection_contract tests/test_jd_talent_delivery_skill.py::test_skill_documents_feedback_followup_contract -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit Task 4**

```bash
git add agents/workflows/jd-talent-delivery/AGENT.md skills/jd-talent-delivery/SKILL.md tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py
git commit -m "docs: document jd delivery feedback followup"
```

---

### Task 5: Final Verification

**Files:**
- Review only: all files changed in Tasks 1-4.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Compile Python files**

Run:

```bash
.venv/bin/python -m py_compile scripts/jd_delivery_feedback.py scripts/jd_talent_delivery_match.py scripts/jd_talent_delivery_feishu.py
```

Expected: no output and exit code 0.

- [ ] **Step 3: Validate JSON schema file**

Run:

```bash
.venv/bin/python -m json.tool schemas/jd-delivery-feedback.schema.json >/tmp/jd-delivery-feedback-schema.json
```

Expected: command exits 0 and `/tmp/jd-delivery-feedback-schema.json` is written.

- [ ] **Step 4: Run repository diff checks**

Run:

```bash
git diff --check -- scripts/jd_delivery_feedback.py scripts/jd_talent_delivery_match.py scripts/jd_talent_delivery_feishu.py schemas/jd-delivery-feedback.schema.json tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py agents/workflows/jd-talent-delivery/AGENT.md skills/jd-talent-delivery/SKILL.md
```

Expected: no output and exit code 0.

- [ ] **Step 5: Run full test suite if focused tests pass**

Run:

```bash
.venv/bin/python -m pytest tests scripts -q
```

Expected: all tests pass. A pre-existing `scripts/test_boss.py` event loop deprecation warning may still appear; do not fix it in this plan unless a test fails because of it.

- [ ] **Step 6: Commit verification cleanup**

If Task 5 required any small corrections, commit them:

```bash
git add scripts/jd_delivery_feedback.py scripts/jd_talent_delivery_match.py scripts/jd_talent_delivery_feishu.py schemas/jd-delivery-feedback.schema.json tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_skill.py agents/workflows/jd-talent-delivery/AGENT.md skills/jd-talent-delivery/SKILL.md
git commit -m "test: verify jd delivery feedback phase one"
```

Skip this commit if there were no additional changes after Tasks 1-4.

---

## Self-Review

Spec coverage:

- Feedback columns: covered by Task 2 and Task 3.
- `delivery-feedback.json`, `feedback-summary.json`, `calibration-suggestions.json`: covered by Task 1.
- Reason-code taxonomy: covered by Task 1.
- Top30 metrics `accepted_at_30`, `actionable_at_30`, `bad_at_10`: covered by Task 1.
- Publish compatibility and no public feedback-note publishing: covered by Task 3 and Task 4.
- Default local/dry-run safety boundary and no main DB writes: covered by Task 4.

Scope decision:

- This plan intentionally implements phase one only. Historical replay, scorecard template selection, and reranker work are excluded because the design document stages them after feedback capture and compilation.

Execution notes:

- Use `.venv/bin/python` for all test commands on this machine.
- Do not edit `data/talent.db`.
- Do not upload feedback remarks to Feishu in this phase.
