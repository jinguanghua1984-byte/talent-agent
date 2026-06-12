import json
from pathlib import Path

import pytest

from scripts.jd_delivery_feedback import (
    compile_feedback_summary,
    load_feedback,
    main,
    write_json,
)


_MISSING = object()


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
                "feedback_note": "候选人方向准确，可以沟通。",
                "parse_source": "llm",
                "parse_confidence": 0.93,
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


@pytest.mark.parametrize("reason_codes", [_MISSING, None, "keyword_hit_but_wrong_duty"])
def test_load_feedback_rejects_missing_none_or_string_reason_codes(
    tmp_path: Path, reason_codes: object
) -> None:
    data = _feedback()
    if reason_codes is _MISSING:
        del data["candidate_feedback"][0]["reason_codes"]
    else:
        data["candidate_feedback"][0]["reason_codes"] = reason_codes
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="reason_codes must be a list"):
        load_feedback(path)


def test_load_feedback_rejects_missing_required_top_level_field(
    tmp_path: Path,
) -> None:
    data = _feedback()
    del data["role_id"]
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="required top-level field role_id"):
        load_feedback(path)


@pytest.mark.parametrize("original_score", [_MISSING, True])
def test_load_feedback_rejects_missing_original_score(
    tmp_path: Path, original_score: object
) -> None:
    data = _feedback()
    if original_score is _MISSING:
        del data["candidate_feedback"][0]["original_score"]
    else:
        data["candidate_feedback"][0]["original_score"] = original_score
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="original_score must be a number"):
        load_feedback(path)


@pytest.mark.parametrize("original_score", [float("nan"), float("inf"), float("-inf")])
def test_load_feedback_rejects_non_finite_original_score(
    tmp_path: Path, original_score: float
) -> None:
    data = _feedback()
    data["candidate_feedback"][0]["original_score"] = original_score
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="original_score must be a finite number"):
        load_feedback(path)


def test_write_json_rejects_non_standard_json_numbers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        write_json(tmp_path / "bad.json", {"score": float("nan")})

    assert not (tmp_path / "bad.json").exists()


@pytest.mark.parametrize("field", ["candidate_id", "rank"])
def test_load_feedback_rejects_duplicate_candidate_id_or_rank(
    tmp_path: Path, field: str
) -> None:
    data = _feedback()
    data["candidate_feedback"][1][field] = data["candidate_feedback"][0][field]
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match=f"duplicate {field}"):
        load_feedback(path)


def test_compile_feedback_summary_calculates_topn_and_reason_metrics() -> None:
    summary = compile_feedback_summary(_feedback())

    assert summary["schema"] == "jd_delivery_feedback_summary_v1"
    assert summary["role_id"] == "training-inference-engineer"
    assert summary["metrics"]["accepted_at_10"] == 1
    assert summary["metrics"]["accepted_at_30"] == 2
    assert "actionable_at_30" not in summary["metrics"]
    assert summary["metrics"]["bad_at_10"] == 1
    assert summary["reason_distribution"]["evidence_too_shallow"] == 1
    assert summary["grade_acceptance_rate"]["A"]["accepted"] == 1
    assert summary["grade_acceptance_rate"]["A"]["total"] == 2
    assert summary["grade_acceptance_rate"]["A"]["accepted_rate"] == 0.5
    assert summary["grade_acceptance_rate"]["C"]["accepted"] == 1
    assert "weak_candidate_ranked_high" in summary["calibration_suggestions"]
    assert "scorecard_threshold_review" in summary["calibration_suggestions"]


def test_compile_feedback_summary_counts_consultant_decisions() -> None:
    payload = {
        "role_id": "role",
        "run_id": "run",
        "profile_version": "p1",
        "scorecard_version": "s1",
        "items": [
            {
                "candidate_id": "cand-1",
                "rank": 1,
                "grade": "A",
                "original_score": 90.0,
                "feedback_label": "accepted",
                "feedback_stage": "screen",
                "reason_codes": ["strong_candidate_ranked_low"],
                "hunter_note": "认可",
                "feedback_note": "不错",
                "consultant_decision": "认可",
                "parse_source": "rule",
                "parse_confidence": 0.9,
            },
            {
                "candidate_id": "cand-2",
                "rank": 2,
                "grade": "B",
                "original_score": 80.0,
                "feedback_label": "rejected",
                "feedback_stage": "screen",
                "reason_codes": ["direction_mismatch"],
                "hunter_note": "不认可",
                "feedback_note": "方向偏",
                "consultant_decision": "不认可",
                "parse_source": "rule",
                "parse_confidence": 0.9,
            },
        ],
    }

    summary = compile_feedback_summary(payload)

    assert summary["consultant_decision_counts"] == {"不认可": 1, "认可": 1}


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


@pytest.mark.parametrize(
    "parse_confidence",
    [-0.1, 1.1, "0.9", float("nan"), float("inf"), float("-inf")],
)
def test_load_feedback_rejects_invalid_parse_confidence(
    tmp_path: Path, parse_confidence: object
) -> None:
    data = _feedback()
    data["candidate_feedback"][0]["parse_confidence"] = parse_confidence
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(
        ValueError, match="parse_confidence must be a number between 0 and 1"
    ):
        load_feedback(path)


def test_load_feedback_accepts_optional_feedback_note_and_parse_source(
    tmp_path: Path,
) -> None:
    data = _feedback()
    path = tmp_path / "delivery-feedback.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    feedback = load_feedback(path)

    item = feedback["candidate_feedback"][0]
    assert item["feedback_note"] == "候选人方向准确，可以沟通。"
    assert item["parse_source"] == "llm"
    assert item["parse_confidence"] == 0.93


def test_cli_reports_validation_errors_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    feedback_path = tmp_path / "delivery-feedback.json"
    summary_path = tmp_path / "feedback-summary.json"
    suggestions_path = tmp_path / "calibration-suggestions.json"
    data = _feedback()
    del data["role_id"]
    feedback_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

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

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err
    assert not summary_path.exists()
    assert not suggestions_path.exists()
