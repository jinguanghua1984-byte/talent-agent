"""从 BOSS App campaign 导出待脉脉匹配的目标候选人。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.cross_channel_identity import BossMaimaiTarget, build_query_plan


TARGET_SCHEMA = "boss_maimai_match_target_v1"
CONTACT_RECOMMENDATIONS = {"contact", "would_contact"}
BLOCKING_REAL_NAME_STATUSES = {"not_available_dry_run", "missing"}
INTERNAL_PAYLOAD_KEYS = {"_source_index"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(file)
    rows: list[dict[str, Any]] = []
    with file.open("r", encoding="utf-8-sig") as f:
        for line_no, line in enumerate(f, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                value = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{file}: line {line_no}: invalid JSON: {exc.msg}") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{file}: line {line_no}: expected object")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _latest_candidates_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        candidate_key = str(row.get("candidate_key") or "").strip()
        if not candidate_key:
            continue
        latest[candidate_key] = dict(row) | {"_source_index": index}
    return latest


def _is_contact_candidate(row: dict[str, Any]) -> bool:
    screening = row.get("screening") if isinstance(row.get("screening"), dict) else {}
    contact = row.get("contact") if isinstance(row.get("contact"), dict) else {}
    detail = row.get("detail") if isinstance(row.get("detail"), dict) else {}
    detail_decision = str(screening.get("detail_decision") or "").strip()
    screening_recommendation = str(screening.get("recommendation") or "").strip()
    top_level_detail_decision = str(row.get("detail_decision") or "").strip()
    top_level_recommendation = str(row.get("recommendation") or "").strip()
    nested_detail_decision = str(detail.get("detail_decision") or detail.get("decision") or "").strip()
    nested_detail_recommendation = str(detail.get("recommendation") or "").strip()
    return (
        detail_decision in CONTACT_RECOMMENDATIONS
        or screening_recommendation in CONTACT_RECOMMENDATIONS
        or top_level_detail_decision in CONTACT_RECOMMENDATIONS
        or top_level_recommendation in CONTACT_RECOMMENDATIONS
        or nested_detail_decision in CONTACT_RECOMMENDATIONS
        or nested_detail_recommendation in CONTACT_RECOMMENDATIONS
        or contact.get("would_contact") is True
    )


def _has_usable_real_name(row: dict[str, Any]) -> bool:
    real_name = str(row.get("real_name") or "").strip()
    status = str(row.get("real_name_status") or "").strip()
    return bool(real_name) and status not in BLOCKING_REAL_NAME_STATUSES


def _as_strings(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            if isinstance(item, dict):
                for key in ("company", "school", "name"):
                    text = str(item.get(key) or "").strip()
                    if text:
                        values.append(text)
                        break
            else:
                text = str(item or "").strip()
                if text:
                    values.append(text)
        return values
    return []


def _dedupe(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _detail_container(row: dict[str, Any], key: str) -> Any:
    container = row.get(key)
    return container if isinstance(container, dict) else {}


def _recent_companies(row: dict[str, Any]) -> list[str]:
    detail_sections = _detail_container(row, "detail_sections")
    detail = _detail_container(row, "detail")
    values = _as_strings(detail_sections.get("recent_companies"))
    values += _as_strings(detail.get("recent_companies"))
    values += _as_strings(detail_sections.get("work_experience"))
    values += _as_strings(detail.get("work_experience"))
    return _dedupe(values)


def _schools(row: dict[str, Any]) -> list[str]:
    detail_sections = _detail_container(row, "detail_sections")
    detail = _detail_container(row, "detail")
    values = _as_strings(detail_sections.get("schools"))
    values += _as_strings(detail.get("schools"))
    values += _as_strings(detail_sections.get("education_experience"))
    values += _as_strings(detail.get("education_experience"))
    return _dedupe(values)


def _clean_payload_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in INTERNAL_PAYLOAD_KEYS}


def _boss_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("boss_payload")
    if isinstance(payload, dict) and payload:
        return _clean_payload_row(payload)
    return _clean_payload_row(row)


def safe_target_id(candidate_key: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", candidate_key.strip())
    return value.strip("-") or "target"


def _target_from_candidate(row: dict[str, Any]) -> BossMaimaiTarget:
    return BossMaimaiTarget(
        target_id=safe_target_id(str(row.get("candidate_key") or "")),
        candidate_key=str(row.get("candidate_key") or ""),
        real_name=str(row.get("real_name") or "").strip(),
        current_company=str(row.get("current_company") or "").strip(),
        current_title=str(row.get("current_title") or "").strip(),
        city=str(row.get("city") or "").strip(),
        education=str(row.get("education") or "").strip(),
        recent_companies=tuple(_recent_companies(row)),
        schools=tuple(_schools(row)),
        boss_payload=_boss_payload(row),
    )


def _target_row(target: BossMaimaiTarget) -> dict[str, Any]:
    return {
        "schema": TARGET_SCHEMA,
        **target.to_dict(),
        "query_plan": [item.to_dict() for item in build_query_plan(target)],
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# BOSS-Maimai 匹配目标摘要",
            "",
            f"- selected_count: {summary['selected_count']}",
            f"- target_count: {summary['target_count']}",
            f"- missing_real_name_count: {summary['missing_real_name_count']}",
            "",
        ]
    )


def export_targets(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    source_path = root / "structured/candidates.jsonl"
    rows = load_jsonl(source_path)
    selected = [row for row in _latest_candidates_by_key(rows).values() if _is_contact_candidate(row)]
    selected.sort(key=lambda row: int(row.get("_source_index", 0)))

    target_rows: list[dict[str, Any]] = []
    missing_real_name: list[str] = []
    for row in selected:
        if not _has_usable_real_name(row):
            missing_real_name.append(str(row.get("candidate_key") or ""))
            continue
        target_rows.append(_target_row(_target_from_candidate(row)))

    targets_path = root / "structured/maimai-match-targets.jsonl"
    summary_path = root / "reports/maimai-match-summary.json"
    markdown_path = root / "reports/maimai-match-summary.md"
    summary = {
        "campaign_root": str(root),
        "source_file": str(source_path),
        "target_file": str(targets_path),
        "selected_count": len(selected),
        "target_count": len(target_rows),
        "missing_real_name_count": len(missing_real_name),
        "missing_real_name": missing_real_name,
    }
    _write_jsonl(targets_path, target_rows)
    _write_json(summary_path, summary)
    markdown_path.write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 BOSS 到脉脉匹配目标")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export_parser = subparsers.add_parser("export", help="导出 maimai-match-targets.jsonl")
    export_parser.add_argument("--campaign-root", required=True)
    args = parser.parse_args(argv)

    if args.command == "export":
        summary = export_targets(args.campaign_root)
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
