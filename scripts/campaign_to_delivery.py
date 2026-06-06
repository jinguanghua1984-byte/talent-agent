"""Campaign DB clean 后同步主库并生成 campaign delivery handoff。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_sync import export_bundle, import_bundle, verify_bundle
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT


REPORT_GATES = "reports/campaign-db-quality-gates.json"
REPORT_SYNC_DRY_RUN = "reports/main-db-sync-dry-run.json"
REPORT_SYNC_RESULT = "reports/main-db-sync-result.json"
LEDGER_PATH = "state/main-db-sync-ledger.jsonl"
HANDOFF_PATH = "state/boss-maimai-delivery-handoff.json"
LEGACY_JD_HANDOFF_PATH = "state/jd-delivery-handoff.json"
BUNDLE_PATH = "sync/campaign-to-main.zip"
CONFIRMED_IDENTITY_STATUSES = {"auto_bound", "confirmed_bound"}


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _count(db: TalentDB, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = db._conn.execute(sql, params).fetchone()
    return int(row[0]) if row is not None else 0


def _foreign_key_violation_count(db: TalentDB) -> int:
    return len(db._conn.execute("PRAGMA foreign_key_check").fetchall())


def validate_campaign_ready(
    campaign_root: str | Path,
    db_path: str | Path,
) -> dict[str, Any]:
    root = Path(campaign_root)
    db = TalentDB(db_path)
    try:
        integrity = str(db._conn.execute("PRAGMA integrity_check").fetchone()[0])
        foreign_key_violations = _foreign_key_violation_count(db)
        pending_identity = _count(
            db,
            """
            SELECT COUNT(*)
            FROM candidate_identity_matches
            WHERE match_status = 'pending_confirmation'
            """,
        )
        unresolved_identity = _count(
            db,
            """
            SELECT COUNT(*)
            FROM candidate_identity_matches
            WHERE match_status NOT IN (?, ?)
            """,
            tuple(sorted(CONFIRMED_IDENTITY_STATUSES)),
        )
        pending_merges = _count(
            db,
            "SELECT COUNT(*) FROM pending_merges WHERE status = 'pending'",
        )
        open_conflicts = _count(
            db,
            "SELECT COUNT(*) FROM sync_conflicts WHERE status = 'open'",
        )
        candidate_count = db.count()
        source_count = _count(db, "SELECT COUNT(*) FROM source_profiles")
        identity_count = _count(db, "SELECT COUNT(*) FROM candidate_identity_matches")
        field_count = _count(db, "SELECT COUNT(*) FROM candidate_field_values")
    finally:
        db.close()

    blockers: list[str] = []
    if integrity != "ok":
        blockers.append("integrity_check")
    if foreign_key_violations:
        blockers.append("foreign_key_check")
    if candidate_count == 0:
        blockers.append("no_candidates")
    if pending_identity:
        blockers.append("pending_identity")
    if unresolved_identity:
        blockers.append("unresolved_identity")
    if pending_merges:
        blockers.append("pending_merges")
    if open_conflicts:
        blockers.append("open_sync_conflicts")

    result = {
        "schema": "campaign_db_quality_gates_v1",
        "checked_at": _now(),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "integrity_check": integrity,
        "foreign_key_violation_count": foreign_key_violations,
        "pending_identity_count": pending_identity,
        "unresolved_identity_count": unresolved_identity,
        "pending_merge_count": pending_merges,
        "open_sync_conflict_count": open_conflicts,
        "candidate_count": candidate_count,
        "source_profile_count": source_count,
        "identity_match_count": identity_count,
        "field_value_count": field_count,
    }
    _write_json(root / REPORT_GATES, result)
    return result


def _sync_plan_blockers(plan: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    conflicts = plan.get("conflicts") if isinstance(plan.get("conflicts"), dict) else {}
    skipped = plan.get("skipped") if isinstance(plan.get("skipped"), dict) else {}
    if any(int(value or 0) for value in conflicts.values()):
        blockers.append("dry_run_conflicts")
    if any(int(value or 0) for value in skipped.values()):
        blockers.append("dry_run_skipped_rows")
    if plan.get("errors"):
        blockers.append("dry_run_errors")
    return blockers


def _write_handoff(
    root: Path,
    main_db_path: Path,
    delivery_context: dict[str, Any],
) -> dict[str, Any]:
    handoff = {
        "schema": "boss_maimai_campaign_delivery_handoff_v1",
        "created_at": _now(),
        "main_db_path": str(main_db_path),
        "delivery_kind": "boss_maimai_campaign_delivery",
        "delivery_script": "scripts/boss_maimai_campaign_delivery.py",
        "delivery_context": delivery_context,
        "outputs": {
            "report_json": "reports/boss-maimai-delivery-report.json",
            "report_md": "reports/boss-maimai-delivery-report.md",
            "follow_up_csv": "reports/boss-maimai-follow-up-queue.csv",
            "follow_up_md": "reports/boss-maimai-follow-up-queue.md",
            "quality_gates": "reports/boss-maimai-delivery-quality-gates.json",
            "feishu_manifest": "feishu/boss-maimai-delivery-manifest.json",
        },
        "legacy_jd_delivery_default": False,
        "url_priority": ["maimai", "other_platforms"],
    }
    _write_json(root / HANDOFF_PATH, handoff)
    legacy_handoff_path = root / LEGACY_JD_HANDOFF_PATH
    if legacy_handoff_path.exists():
        legacy_handoff_path.unlink()
    return handoff


def sync_main_db(
    campaign_root: str | Path,
    campaign_db_path: str | Path,
    main_db_path: str | Path,
    *,
    allow_main_db_write_after_clean_campaign: bool,
    confirm: str,
    delivery_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not allow_main_db_write_after_clean_campaign:
        raise ValueError("allow_main_db_write_after_clean_campaign is required")
    if confirm != CONFIRM_SYNC_TEXT:
        raise ValueError(f"confirm must be {CONFIRM_SYNC_TEXT}")

    root = Path(campaign_root)
    campaign_db = Path(campaign_db_path)
    main_db = Path(main_db_path)
    gates = validate_campaign_ready(root, campaign_db)
    if gates["status"] != "passed":
        result = {
            "schema": "main_db_sync_result_v1",
            "created_at": _now(),
            "status": "blocked",
            "reason": "campaign_not_clean",
            "gates": gates,
        }
        _write_json(root / REPORT_SYNC_RESULT, result)
        return result

    bundle_path = root / BUNDLE_PATH
    export_summary = export_bundle(campaign_db, bundle_path, mode="full")
    verification = verify_bundle(bundle_path)
    if not verification["ok"]:
        result = {
            "schema": "main_db_sync_result_v1",
            "created_at": _now(),
            "status": "blocked",
            "reason": "bundle_verify_failed",
            "bundle_path": str(bundle_path),
            "export_summary": export_summary,
            "verification": verification,
        }
        _write_json(root / REPORT_SYNC_RESULT, result)
        return result

    dry_run = import_bundle(bundle_path, main_db, apply=False)
    _write_json(root / REPORT_SYNC_DRY_RUN, dry_run)
    dry_run_blockers = _sync_plan_blockers(dry_run)
    if dry_run_blockers:
        result = {
            "schema": "main_db_sync_result_v1",
            "created_at": _now(),
            "status": "blocked",
            "reason": "main_db_dry_run_not_clean",
            "blockers": dry_run_blockers,
            "bundle_path": str(bundle_path),
            "export_summary": export_summary,
            "verification": verification,
            "dry_run": dry_run,
        }
        _write_json(root / REPORT_SYNC_RESULT, result)
        return result

    apply_result = import_bundle(bundle_path, main_db, apply=True, confirm=confirm)
    handoff = _write_handoff(root, main_db, delivery_context or {})
    result = {
        "schema": "main_db_sync_result_v1",
        "created_at": _now(),
        "status": "applied",
        "bundle_path": str(bundle_path),
        "export_summary": export_summary,
        "verification": verification,
        "dry_run": dry_run,
        "apply_result": apply_result,
        "handoff": handoff,
    }
    _write_json(root / REPORT_SYNC_RESULT, result)
    _append_jsonl(root / LEDGER_PATH, result)
    return result


def _delivery_context_from_args(args: argparse.Namespace) -> dict[str, Any]:
    text = str(getattr(args, "delivery_context_json", "") or "").strip()
    if not text:
        return {}
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("--delivery-context-json must be a JSON object")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Campaign DB 到主库同步与 campaign 交付 handoff"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-campaign")
    validate.add_argument("--campaign-root", required=True)
    validate.add_argument("--db", required=True)
    validate.set_defaults(
        func=lambda args: validate_campaign_ready(args.campaign_root, args.db)
    )

    sync = subparsers.add_parser("sync-main")
    sync.add_argument("--campaign-root", required=True)
    sync.add_argument("--campaign-db", required=True)
    sync.add_argument("--main-db", default="data/talent.db")
    sync.add_argument("--allow-main-db-write-after-clean-campaign", action="store_true")
    sync.add_argument("--confirm", default="")
    sync.add_argument("--delivery-context-json", default="")
    sync.set_defaults(
        func=lambda args: sync_main_db(
            args.campaign_root,
            args.campaign_db,
            args.main_db,
            allow_main_db_write_after_clean_campaign=args.allow_main_db_write_after_clean_campaign,
            confirm=args.confirm,
            delivery_context=_delivery_context_from_args(args),
        )
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
