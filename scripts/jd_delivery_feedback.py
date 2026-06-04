from __future__ import annotations

import argparse
import json
import sys
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

REQUIRED_TOP_LEVEL_FIELDS = ("role_id", "run_id", "profile_version", "scorecard_version")


def _read_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("feedback JSON must be an object")
    return data


def load_feedback(path: str | Path) -> dict[str, Any]:
    data = _read_json(path)
    if data.get("schema") != SCHEMA:
        raise ValueError("invalid feedback schema")
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"required top-level field {field} must be a non-empty string")
    items = data.get("candidate_feedback")
    if not isinstance(items, list):
        raise ValueError("candidate_feedback must be a list")
    seen_candidate_ids: set[str] = set()
    seen_ranks: set[int] = set()
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
        reason_codes = item.get("reason_codes")
        if not isinstance(reason_codes, list):
            raise ValueError(f"candidate_feedback item {index} reason_codes must be a list")
        unknown = sorted(set(str(code) for code in reason_codes) - VALID_REASON_CODES)
        if unknown:
            raise ValueError("unknown feedback reason codes: " + ", ".join(unknown))
        rank = item.get("rank")
        if not isinstance(rank, int) or isinstance(rank, bool) or rank <= 0:
            raise ValueError(f"candidate_feedback item {index} rank must be a positive integer")
        if rank in seen_ranks:
            raise ValueError(f"duplicate rank: {rank}")
        seen_ranks.add(rank)
        original_score = item.get("original_score")
        if not isinstance(original_score, (int, float)) or isinstance(original_score, bool):
            raise ValueError(f"candidate_feedback item {index} original_score must be a number")
        candidate_id = item.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError(f"candidate_feedback item {index} missing candidate_id")
        if candidate_id in seen_candidate_ids:
            raise ValueError(f"duplicate candidate_id: {candidate_id}")
        seen_candidate_ids.add(candidate_id)
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
    return data


def _grade_acceptance(items: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    result: dict[str, dict[str, int | float]] = {
        grade: {
            "accepted": 0,
            "tentative": 0,
            "rejected": 0,
            "total": 0,
            "accepted_rate": 0.0,
        }
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
    for counts in result.values():
        total = counts["total"]
        counts["accepted_rate"] = counts["accepted"] / total if total else 0.0
    return result


def _calibration_suggestions(reason_counts: Counter[str]) -> list[str]:
    suggestions: list[str] = []
    if reason_counts.get("keyword_hit_but_wrong_duty") or reason_counts.get(
        "evidence_too_shallow"
    ):
        suggestions.append("weak_candidate_ranked_high")
    if reason_counts.get("scorecard_bad_threshold"):
        suggestions.append("scorecard_threshold_review")
    if reason_counts.get("must_have_overloaded") or reason_counts.get(
        "jd_profile_too_broad"
    ):
        suggestions.append("profile_must_have_review")
    if reason_counts.get("company_pool_wrong") or reason_counts.get("title_alias_wrong"):
        suggestions.append("search_signal_review")
    return suggestions


def compile_feedback_summary(feedback: dict[str, Any]) -> dict[str, Any]:
    items = [item for item in feedback.get("candidate_feedback") or [] if isinstance(item, dict)]
    reason_counts: Counter[str] = Counter()
    for item in items:
        reason_counts.update(str(code) for code in item.get("reason_codes") or [])

    accepted_top_10 = [
        item for item in items if item["rank"] <= 10 and item["feedback_label"] == "认可"
    ]
    accepted_top_30 = [
        item for item in items if item["rank"] <= 30 and item["feedback_label"] == "认可"
    ]
    bad_top_10 = [
        item for item in items if item["rank"] <= 10 and item["feedback_label"] == "不认可"
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

    try:
        feedback = load_feedback(args.feedback)
        summary = compile_feedback_summary(feedback)
        write_json(args.summary_out, summary)
        write_json(args.suggestions_out, build_suggestions(summary))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
