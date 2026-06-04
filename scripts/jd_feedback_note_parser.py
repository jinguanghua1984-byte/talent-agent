from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from scripts.jd_delivery_feedback import (
    VALID_FEEDBACK_LABELS,
    VALID_FEEDBACK_STAGES,
    VALID_REASON_CODES,
    build_suggestions,
    compile_feedback_summary,
    load_feedback,
    write_json,
)
from scripts.pipeline_utils import call_llm_with_retry, create_llm_client


DEFAULT_MODEL = "intelligence"
LOW_CONFIDENCE_THRESHOLD = 0.7
FEEDBACK_SCHEMA = "jd_delivery_feedback_v1"
REVIEW_QUEUE_SCHEMA = "jd_delivery_feedback_parse_review_queue_v1"
REQUIRED_CSV_COLUMNS = {"candidate_id", "rank", "score", "grade", "feedback_note"}


def build_feedback_prompt(feedback_note: str) -> str:
    labels = "、".join(sorted(VALID_FEEDBACK_LABELS))
    stages = "、".join(sorted(VALID_FEEDBACK_STAGES))
    reason_codes = "\n".join(f"- {code}" for code in sorted(VALID_REASON_CODES))
    return f"""你是 JD 推荐反馈解析助手。请把业务人员填写的自然语言反馈解析成严格 JSON。

字段含义：
- feedback_label：总体判断，只能是 {labels}。
- feedback_stage：问题或判断所属阶段，只能是 {stages}。
- reason_codes：原因码数组，只能从下列代码中选择；没有明确原因时返回空数组。
{reason_codes}
- hunter_note：保留给人工复盘的一句中文说明，应忠实概括原反馈。
- parse_confidence：0 到 1 的数字，表示你对解析结果的置信度。

只返回 JSON 对象，不要返回 Markdown 或解释文字。JSON 形状：
{{
  "feedback_label": "认可|待定|不认可",
  "feedback_stage": "画像|评分卡|匹配|报告|候选人状态",
  "reason_codes": ["reason_code"],
  "hunter_note": "中文备注",
  "parse_confidence": 0.0
}}

原始反馈：
{feedback_note}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return _loads_object(fenced.group(1))

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return _loads_object(stripped)

    start = text.find("{")
    while start != -1:
        candidate = _balanced_json_slice(text, start)
        if candidate is not None:
            return _loads_object(candidate)
        start = text.find("{", start + 1)
    raise ValueError("LLM response did not contain a JSON object")


def parse_feedback_note(
    feedback_note: str,
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    resolved_client = client or create_llm_client(provider=provider, model=model)
    resolved_model = model or _client_model(resolved_client) or DEFAULT_MODEL
    messages = [{"role": "user", "content": build_feedback_prompt(feedback_note)}]

    try:
        response = call_llm_with_retry(
            resolved_client,
            resolved_model,
            messages,
            max_tokens=1024,
        )
        parsed = extract_json_object(response)
    except Exception:
        return _fallback_result(feedback_note)

    return _normalize_result(parsed, feedback_note)


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
    root = Path(run_root)
    paths = _output_paths(root, csv_path, out_path, review_out_path)
    metadata = _load_run_metadata(root)

    candidate_feedback: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []
    seen_candidate_ids: set[str] = set()
    seen_ranks: set[int] = set()
    rows_to_parse: list[dict[str, str | None]] = []

    with paths["csv"].open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_csv_columns(reader.fieldnames)
        for row in reader:
            note = (row.get("feedback_note") or "").strip()
            if not note:
                continue
            _validate_unique_feedback_row(row, seen_candidate_ids, seen_ranks)
            rows_to_parse.append(row)

    for row in rows_to_parse:
        note = (row.get("feedback_note") or "").strip()
        parsed = parse_feedback_note(
            note,
            client=client,
            provider=provider,
            model=model,
        )
        item = _candidate_item(row, parsed)
        if parsed["review_required"]:
            review_items.append(
                {
                    **item,
                    "review_status": "pending",
                    "review_reasons": parsed["review_reasons"],
                }
            )
        else:
            candidate_feedback.append(item)

    delivery_feedback = {
        "schema": FEEDBACK_SCHEMA,
        **metadata,
        "source_report": "reports/talent-recommendation.json",
        "source_outreach_sheet": str(paths["csv"]),
        "reviewer_role": "senior_hunter",
        "candidate_feedback": candidate_feedback,
    }
    validated_feedback = _validate_feedback_payload(delivery_feedback)
    review_queue = {
        "schema": REVIEW_QUEUE_SCHEMA,
        **metadata,
        "source_outreach_sheet": str(paths["csv"]),
        "items": review_items,
    }
    result = {
        "run_root": str(root),
        "csv_path": str(paths["csv"]),
        "out_path": str(paths["delivery"]),
        "review_out_path": str(paths["review"]),
        "parsed_count": len(rows_to_parse),
        "accepted_count": len(candidate_feedback),
        "review_count": len(review_items),
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    write_json(paths["delivery"], validated_feedback)
    write_json(paths["review"], review_queue)
    summary = compile_feedback_summary(validated_feedback)
    write_json(paths["summary"], summary)
    write_json(paths["suggestions"], build_suggestions(summary))
    return result


def main(argv: list[str] | None = None, *, client: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse JD delivery feedback notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse")
    parse_parser.add_argument("--note", required=True)
    parse_parser.add_argument("--out", required=True)
    parse_parser.add_argument("--provider")
    parse_parser.add_argument("--model")

    csv_parser = subparsers.add_parser("parse-csv")
    csv_parser.add_argument("--run-root", required=True)
    csv_parser.add_argument("--csv")
    csv_parser.add_argument("--out")
    csv_parser.add_argument("--review-out")
    csv_parser.add_argument("--provider")
    csv_parser.add_argument("--model")
    csv_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "parse":
            result = parse_feedback_note(
                args.note,
                client=client,
                provider=args.provider,
                model=args.model,
            )
            write_json(args.out, result)
            return 0
        if args.command == "parse-csv":
            result = parse_feedback_csv(
                args.run_root,
                csv_path=args.csv,
                out_path=args.out,
                review_out_path=args.review_out,
                client=client,
                provider=args.provider,
                model=args.model,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


def _loads_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON response must be an object")
    return data


def _validate_csv_columns(fieldnames: list[str] | None) -> None:
    missing = sorted(REQUIRED_CSV_COLUMNS - set(fieldnames or []))
    if missing:
        raise ValueError(
            "outreach CSV missing required columns: " + ", ".join(missing)
        )


def _validate_feedback_payload(feedback: dict[str, Any]) -> dict[str, Any]:
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "delivery-feedback.json"
        write_json(path, feedback)
        return load_feedback(path)


def _output_paths(
    run_root: Path,
    csv_path: str | Path | None,
    out_path: str | Path | None,
    review_out_path: str | Path | None,
) -> dict[str, Path]:
    feedback_dir = run_root / "feedback"
    return {
        "csv": Path(csv_path) if csv_path is not None else run_root / "reports" / "outreach-queue.csv",
        "delivery": Path(out_path) if out_path is not None else feedback_dir / "delivery-feedback.json",
        "review": Path(review_out_path)
        if review_out_path is not None
        else feedback_dir / "parse-review-queue.json",
        "summary": feedback_dir / "feedback-summary.json",
        "suggestions": feedback_dir / "calibration-suggestions.json",
    }


def _load_run_metadata(run_root: Path) -> dict[str, str]:
    manifest = _read_optional_json(run_root / "run-manifest.json")
    profile = _read_optional_json(run_root / "profile" / "role-profile.json")
    scorecard = _read_optional_json(run_root / "scoring" / "scorecard.json")
    return {
        "role_id": str(profile.get("role_id") or ""),
        "run_id": str(manifest.get("output_dir") or run_root),
        "profile_version": str(profile.get("version") or profile.get("schema") or ""),
        "scorecard_version": str(scorecard.get("version") or scorecard.get("schema") or ""),
    }


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _candidate_item(row: dict[str, str | None], parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _required_text(row, "candidate_id"),
        "rank": _required_int(row, "rank"),
        "original_grade": _required_text(row, "grade"),
        "original_score": _required_number(row, "score"),
        "feedback_label": parsed["feedback_label"],
        "feedback_stage": parsed["feedback_stage"],
        "reason_codes": parsed["reason_codes"],
        "hunter_note": parsed["hunter_note"],
        "feedback_note": parsed["feedback_note"],
        "parse_source": parsed["parse_source"],
        "parse_confidence": parsed["parse_confidence"],
    }


def _validate_unique_feedback_row(
    row: dict[str, str | None],
    seen_candidate_ids: set[str],
    seen_ranks: set[int],
) -> None:
    candidate_id = (row.get("candidate_id") or "").strip()
    if not candidate_id:
        raise ValueError("candidate_id is required")
    if candidate_id in seen_candidate_ids:
        raise ValueError(f"duplicate candidate_id: {candidate_id}")
    rank = _required_int(row, "rank")
    if rank in seen_ranks:
        raise ValueError(f"duplicate rank: {rank}")
    seen_candidate_ids.add(candidate_id)
    seen_ranks.add(rank)


def _required_text(row: dict[str, str | None], field: str) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise ValueError(f"outreach CSV missing required {field}")
    return value.strip()


def _required_int(row: dict[str, str | None], field: str) -> int:
    return _parse_int(_required_text(row, field), field)


def _parse_int(value: str, field: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"outreach CSV {field} must be an integer") from exc


def _required_number(row: dict[str, str | None], field: str) -> int | float:
    value = _required_text(row, field)
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"outreach CSV {field} must be a number") from exc
    return int(number) if number.is_integer() else number


def _balanced_json_slice(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _client_model(client: Any) -> str | None:
    settings = getattr(client, "settings", None)
    model = getattr(settings, "model", None)
    return model if isinstance(model, str) and model else None


def _fallback_result(feedback_note: str) -> dict[str, Any]:
    return {
        "feedback_label": "待定",
        "feedback_stage": "匹配",
        "reason_codes": [],
        "hunter_note": feedback_note,
        "feedback_note": feedback_note,
        "parse_source": "llm",
        "parse_confidence": 0.0,
        "review_required": True,
        "review_reasons": ["llm_error"],
    }


def _normalize_result(parsed: dict[str, Any], feedback_note: str) -> dict[str, Any]:
    review_reasons: list[str] = []

    label = parsed.get("feedback_label")
    if label not in VALID_FEEDBACK_LABELS:
        label = "待定"
        review_reasons.append("invalid_feedback_label")

    stage = parsed.get("feedback_stage")
    if stage not in VALID_FEEDBACK_STAGES:
        stage = "匹配"
        review_reasons.append("invalid_feedback_stage")

    raw_reason_codes = parsed.get("reason_codes")
    if not isinstance(raw_reason_codes, list):
        reason_codes: list[str] = []
        review_reasons.append("invalid_reason_codes")
    else:
        reason_codes = [
            code for code in raw_reason_codes if isinstance(code, str) and code in VALID_REASON_CODES
        ]
        if len(reason_codes) != len(raw_reason_codes):
            review_reasons.append("invalid_reason_codes")

    confidence = parsed.get("parse_confidence")
    confidence_is_valid = True
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or confidence < 0
        or confidence > 1
    ):
        confidence = 0.0
        confidence_is_valid = False
        review_reasons.append("invalid_parse_confidence")

    if confidence_is_valid and confidence < LOW_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_confidence")

    if "invalid_feedback_label" in review_reasons:
        confidence = 0.0

    hunter_note = parsed.get("hunter_note")
    if not isinstance(hunter_note, str) or not hunter_note.strip():
        hunter_note = feedback_note

    return {
        "feedback_label": label,
        "feedback_stage": stage,
        "reason_codes": reason_codes,
        "hunter_note": hunter_note,
        "feedback_note": feedback_note,
        "parse_source": "llm",
        "parse_confidence": confidence,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
    }


if __name__ == "__main__":
    raise SystemExit(main())
