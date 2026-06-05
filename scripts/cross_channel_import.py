"""导入 BOSS primary + 脉脉 supplement 绑定候选到 Campaign DB。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_models import SourceProfile


BOUND_FILE = "structured/cross-channel-bound-candidates.jsonl"
CONFIRMED_STATUSES = {"auto_bound", "confirmed_bound"}
REPORT_DRY_RUN = "reports/cross-channel-import-dry-run.json"
REPORT_APPLY = "reports/cross-channel-import-result.json"
PRIMARY_FIELDS = (
    "name",
    "current_company",
    "current_title",
    "city",
    "work_years",
    "education",
)
AUDIT_FIELDS = (
    "name",
    "current_company",
    "current_title",
    "city",
    "work_years",
    "education",
    "hunting_status",
    "profile_url",
)


@dataclass(frozen=True)
class BoundRow:
    line: int
    data: dict[str, Any]


def _load_jsonl(path: Path) -> list[BoundRow]:
    if not path.exists():
        raise FileNotFoundError(path)

    rows: list[BoundRow] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8-sig").splitlines(),
        start=1,
    ):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"{path}: line {line_number}: expected JSON object")
        rows.append(BoundRow(line=line_number, data=row))
    return rows


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _object(row: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = row.get(key)
    return value if isinstance(value, dict) else None


def _candidate_key(row: dict[str, Any]) -> str | None:
    target = _object(row, "target") or {}
    decision = _object(row, "decision") or {}
    return target.get("candidate_key") or decision.get("source_candidate_key")


def _row_errors(bound: BoundRow) -> list[str]:
    row = bound.data
    errors: list[str] = []
    target = _object(row, "target")
    decision = _object(row, "decision")
    if target is None:
        errors.append("target is required")
    if decision is None:
        errors.append("decision is required")

    boss_payload = target.get("boss_payload") if target else None
    boss_payload = boss_payload if isinstance(boss_payload, dict) else {}
    boss_name = (
        boss_payload.get("name")
        or boss_payload.get("real_name")
        or (target or {}).get("real_name")
        or (target or {}).get("name")
    )
    if not boss_name:
        errors.append("boss name is required")

    if decision is not None:
        for field in (
            "source_platform",
            "source_candidate_key",
            "target_platform",
            "query_text",
            "query_level",
            "match_status",
        ):
            if _is_empty(decision.get(field)):
                errors.append(f"decision.{field} is required")
        score_breakdown = decision.get("score_breakdown")
        if score_breakdown is not None and not isinstance(score_breakdown, dict):
            errors.append("decision.score_breakdown must be an object")
        confidence = decision.get("confidence")
        if confidence is not None and (
            isinstance(confidence, bool) or not isinstance(confidence, (int, float))
        ):
            errors.append("decision.confidence must be a number")
        hit = _object(row, "maimai_hit") or {}
        if decision.get("match_status") in CONFIRMED_STATUSES and not (
            decision.get("target_platform_id")
            or decision.get("target_profile_url")
            or hit.get("platform_id")
            or hit.get("profile_url")
        ):
            errors.append("maimai platform_id or profile_url is required")

    return errors


def _boss_payload(row: dict[str, Any]) -> dict[str, Any]:
    target = _object(row, "target") or {}
    source = target.get("boss_payload")
    payload = dict(source) if isinstance(source, dict) else {}
    name = (
        payload.get("name")
        or payload.get("real_name")
        or target.get("real_name")
        or target.get("name")
    )

    normalized = {
        **payload,
        "name": name,
        "current_company": payload.get("current_company") or target.get("current_company"),
        "current_title": payload.get("current_title") or target.get("current_title"),
        "city": payload.get("city") or target.get("city"),
        "work_years": payload.get("work_years") or target.get("work_years"),
        "education": payload.get("education") or target.get("education"),
        "platform_id": (
            payload.get("platform_id")
            or payload.get("candidate_key")
            or target.get("candidate_key")
            or target.get("target_id")
        ),
        "profile_url": payload.get("profile_url") or target.get("profile_url"),
        "raw_profile": {
            "boss_app_detail_capture": payload,
            "cross_channel_target": target,
        },
    }
    normalized.pop("real_name", None)
    return normalized


def _maimai_payload(row: dict[str, Any]) -> dict[str, Any]:
    target = _object(row, "target") or {}
    decision = _object(row, "decision") or {}
    hit = _object(row, "maimai_hit") or {}
    return {
        "name": hit.get("name") or target.get("real_name") or target.get("name"),
        "current_company": hit.get("current_company") or hit.get("company"),
        "current_title": hit.get("current_title") or hit.get("title"),
        "city": hit.get("city"),
        "work_years": hit.get("work_years"),
        "education": hit.get("education"),
        "hunting_status": hit.get("hunting_status"),
        "skill_tags": hit.get("skill_tags") or [],
        "work_experience": hit.get("work_experience") or [],
        "education_experience": hit.get("education_experience") or [],
        "project_experience": hit.get("project_experience") or [],
        "platform_id": decision.get("target_platform_id") or hit.get("platform_id"),
        "profile_url": decision.get("target_profile_url") or hit.get("profile_url"),
        "raw_profile": _maimai_raw_profile({}, hit, decision),
    }


def _maimai_raw_profile(
    existing: dict[str, Any] | None,
    hit: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    raw_profile = dict(existing or {})
    raw_profile["cross_channel_maimai_search_hit"] = hit
    raw_profile["cross_channel_identity_match"] = decision
    return raw_profile


def _merge_existing_maimai_raw_profile(
    db: TalentDB,
    candidate_id: int,
    maimai: dict[str, Any],
) -> dict[str, Any]:
    existing = _matching_maimai_source(db.get_sources(candidate_id), maimai)
    if existing is None or not isinstance(existing.raw_profile, dict):
        return maimai
    merged = dict(maimai)
    incoming_raw = maimai.get("raw_profile") if isinstance(maimai.get("raw_profile"), dict) else {}
    merged["raw_profile"] = {**existing.raw_profile, **incoming_raw}
    return merged


def _record_identity_match(
    db: TalentDB,
    candidate_id: int,
    row: dict[str, Any],
) -> int:
    decision = dict(_object(row, "decision") or {})
    cursor = db._conn.execute(
        """
        INSERT INTO candidate_identity_matches (
            candidate_id, source_platform, source_candidate_key,
            target_platform, target_platform_id, target_profile_url,
            query_text, query_level, confidence, score_breakdown,
            match_status, decision_reason, confirmed_by, confirmed_at,
            sync_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            decision["source_platform"],
            decision["source_candidate_key"],
            decision["target_platform"],
            decision.get("target_platform_id"),
            decision.get("target_profile_url"),
            decision["query_text"],
            decision["query_level"],
            decision.get("confidence") if decision.get("confidence") is not None else 0,
            json.dumps(decision.get("score_breakdown") or {}, ensure_ascii=False),
            decision["match_status"],
            decision.get("decision_reason"),
            decision.get("confirmed_by"),
            decision.get("confirmed_at"),
            db._new_sync_id("identity_match"),
        ),
    )
    return int(cursor.lastrowid)


def _matching_maimai_source(
    sources: list[SourceProfile],
    maimai_payload: dict[str, Any],
) -> SourceProfile | None:
    platform_id = maimai_payload.get("platform_id")
    profile_url = maimai_payload.get("profile_url")
    maimai_sources = [source for source in sources if source.platform == "maimai"]
    for source in maimai_sources:
        if platform_id and source.platform_id == platform_id:
            return source
    for source in maimai_sources:
        if profile_url and source.profile_url == profile_url:
            return source
    return None


def _audit_decision(field: str, boss_value: Any, maimai_value: Any) -> str:
    if field == "profile_url":
        return "supplement_added" if not _is_empty(maimai_value) else "ignored_empty"
    if _is_empty(maimai_value):
        return "ignored_empty"
    if _is_empty(boss_value):
        return "supplement_added"
    return "primary_kept"


def _record_field_audits(
    db: TalentDB,
    candidate_id: int,
    boss: dict[str, Any],
    maimai: dict[str, Any],
) -> None:
    maimai_source = _matching_maimai_source(db.get_sources(candidate_id), maimai)
    source_profile_id = maimai_source.id if maimai_source is not None else None
    for field in AUDIT_FIELDS:
        boss_value = boss.get(field)
        maimai_value = maimai.get(field)
        decision = _audit_decision(field, boss_value, maimai_value)
        if decision == "ignored_empty":
            continue
        _record_field_value(
            db,
            candidate_id=candidate_id,
            field_name=field,
            source_profile_id=source_profile_id,
            field_value={
                "boss_primary": boss_value,
                "maimai_value": maimai_value,
            },
            merge_decision=decision,
            decision_reason="BOSS primary；脉脉仅补充缺失字段或来源证据",
        )


def _record_field_value(
    db: TalentDB,
    *,
    candidate_id: int,
    field_name: str,
    source_profile_id: int | None,
    field_value: dict[str, Any],
    merge_decision: str,
    decision_reason: str,
) -> int:
    cursor = db._conn.execute(
        """
        INSERT INTO candidate_field_values (
            candidate_id, field_name, platform, source_profile_id,
            field_value, confidence, merge_decision, decision_reason,
            sync_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_id,
            field_name,
            "maimai",
            source_profile_id,
            json.dumps(field_value, ensure_ascii=False),
            1.0,
            merge_decision,
            decision_reason,
            db._new_sync_id("field_value"),
        ),
    )
    return int(cursor.lastrowid)


def _prepare_rows(rows: list[BoundRow]) -> tuple[list[BoundRow], list[dict[str, Any]], list[dict[str, Any]]]:
    confirmed: list[BoundRow] = []
    blocked: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for bound in rows:
        row = bound.data
        row_errors = _row_errors(bound)
        if row_errors:
            errors.append(
                {
                    "line": bound.line,
                    "candidate_key": _candidate_key(row),
                    "errors": row_errors,
                }
            )
            continue

        decision = _object(row, "decision") or {}
        match_status = decision.get("match_status")
        if match_status not in CONFIRMED_STATUSES:
            blocked.append(
                {
                    "line": bound.line,
                    "candidate_key": _candidate_key(row),
                    "reason": "identity_not_confirmed",
                    "match_status": match_status,
                }
            )
            continue
        confirmed.append(bound)
    return confirmed, blocked, errors


def _empty_result(dry_run: bool, input_count: int) -> dict[str, Any]:
    return {
        "schema": "cross_channel_import_result_v1",
        "dry_run": dry_run,
        "input_count": input_count,
        "would_import": 0,
        "created": 0,
        "merged": 0,
        "pending": 0,
        "applied": 0,
        "blocked": [],
        "errors": [],
    }


def import_bound_candidates(
    campaign_root: str | Path,
    db_path: str | Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(campaign_root)
    rows = _load_jsonl(root / BOUND_FILE)
    confirmed_rows, blocked, errors = _prepare_rows(rows)
    result = _empty_result(dry_run=dry_run, input_count=len(rows))
    result["would_import"] = len(confirmed_rows)
    result["blocked"] = blocked
    result["errors"] = errors

    report_path = root / (REPORT_DRY_RUN if dry_run else REPORT_APPLY)
    if dry_run:
        TalentDB(db_path).close()
        _write_json(report_path, result)
        return result
    if blocked or errors:
        _write_json(report_path, result)
        return result

    db = TalentDB(db_path)
    try:
        with db._conn:
            for bound in confirmed_rows:
                row = bound.data
                boss = _boss_payload(row)
                maimai = _maimai_payload(row)
                candidate_id, action = db._ingest_with_result(boss, "boss_app")
                maimai = _merge_existing_maimai_raw_profile(db, candidate_id, maimai)
                db._merge_candidate(candidate_id, maimai, "maimai")
                _record_identity_match(db, candidate_id, row)
                _record_field_audits(db, candidate_id, boss, maimai)
                if action == "created":
                    result["created"] += 1
                elif action == "merged":
                    result["merged"] += 1
                elif action == "pending":
                    result["pending"] += 1
                result["applied"] += 1
    finally:
        db.close()

    _write_json(report_path, result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="导入 BOSS primary + 脉脉 supplement 绑定候选到 Campaign DB"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    import_parser = subparsers.add_parser("import")
    import_parser.add_argument("--campaign-root", required=True)
    import_parser.add_argument("--db", required=True)
    import_parser.add_argument("--dry-run", action="store_true")
    import_parser.set_defaults(
        func=lambda args: import_bound_candidates(
            args.campaign_root,
            args.db,
            dry_run=args.dry_run,
        )
    )
    return parser


def _preload_error_result(exc: Exception) -> dict[str, Any]:
    return {
        **_empty_result(dry_run=False, input_count=0),
        "errors": [
            {
                "type": type(exc).__name__,
                "message": str(exc),
            }
        ],
    }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        result = _preload_error_result(exc)
        if getattr(args, "command", None) == "import":
            report_path = Path(args.campaign_root) / REPORT_APPLY
            _write_json(report_path, result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("blocked") or result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
