from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SUMMARY_SCHEMA = "campaign_status_summary_v1"
BOUND_IDENTITY_STATUSES = {"auto_bound", "confirmed_bound", "manual_bound", "bound"}


def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file} line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"{file} line {line_number}: must be an object")
        rows.append(payload)
    return rows


def summarize_campaign(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    manifest = _object(load_json(root / "campaign-manifest.json", default={}))
    continuation = _object(load_json(root / "state" / "continuation-plan.json", default={}))
    stage_state = _object(load_json(root / "state" / "stage-state.json", default={}))
    match_summary = _object(load_json(root / "reports" / "maimai-match-summary.json", default={}))
    executor_validation = _object(load_json(root / "reports" / "executor-validation.json", default={}))
    campaign_gates = _object(load_json(root / "reports" / "campaign-db-quality-gates.json", default={}))
    delivery_gates = _object(load_json(root / "reports" / "boss-maimai-delivery-quality-gates.json", default={}))
    feishu_publish = _object(load_json(root / "feishu" / "boss-maimai-delivery-publish-results.json", default={}))
    im_notification = _object(load_json(root / "feishu" / "im-notification-results.json", default={}))
    main_db_dry_run = _object(load_json(root / "reports" / "main-db-sync-dry-run.json", default={}))
    main_db_result = _object(load_json(root / "reports" / "main-db-sync-result.json", default={}))

    candidates = _latest_by_key(load_jsonl(root / "structured" / "candidates.jsonl"))
    identity_rows = load_jsonl(root / "state" / "cross-channel-identity-ledger.jsonl")
    blocked_by = _blocked_reason(continuation, stage_state)

    counts = {
        "list_card_count": len(load_jsonl(root / "raw" / "list-cards.jsonl")),
        "candidate_count": len(candidates),
        "detail_count": len(load_jsonl(root / "raw" / "detail-pages.jsonl")),
        "would_contact_count": sum(1 for item in candidates.values() if _contact(item).get("would_contact") is True),
        "real_contact_count": sum(1 for item in candidates.values() if _contact(item).get("contacted") is True),
        "external_executor_contact_count": sum(
            1
            for item in candidates.values()
            if _contact(item).get("contacted") is True
            and _contact(item).get("contact_mode") == "external_executor"
        ),
        "maimai_target_count": _int_or_default(
            match_summary.get("target_count"),
            len(load_jsonl(root / "structured" / "maimai-match-targets.jsonl")),
        ),
        "maimai_missing_real_name_count": _int_or_default(match_summary.get("missing_real_name_count"), 0),
        "maimai_identity_bound_count": sum(
            1 for row in identity_rows if str(row.get("status") or "") in BOUND_IDENTITY_STATUSES
        ),
    }
    dry_run_apply_status = {
        "executor_validation_status": executor_validation.get("status"),
        "campaign_db_quality_gate_status": campaign_gates.get("status"),
        "main_db_sync_dry_run_status": "present" if main_db_dry_run else None,
        "main_db_sync_result_status": "present" if main_db_result else None,
        "delivery_quality_gate_status": delivery_gates.get("status"),
        "feishu_publish_status": feishu_publish.get("status"),
        "im_notification_status": im_notification.get("status"),
    }
    dry_run_apply_status = {
        key: value for key, value in dry_run_apply_status.items() if value not in (None, "")
    }

    return {
        "schema": SUMMARY_SCHEMA,
        "campaign_root": str(root),
        "campaign_id": str(manifest.get("campaign_id") or root.name),
        "campaign_type": _detect_campaign_type(root, manifest),
        "current_stage": str(continuation.get("stage") or stage_state.get("stage") or manifest.get("status") or ""),
        "status": str(continuation.get("status") or stage_state.get("status") or manifest.get("status") or "unknown"),
        "blocked_by": blocked_by,
        "counts": counts,
        "latest_interruption": _latest_interruption(root),
        "continuation_plan": continuation,
        "dry_run_apply_status": dry_run_apply_status,
        "requires_user_authorization": _requires_user_authorization(blocked_by, dry_run_apply_status),
        "safe_commands": _safe_recovery_commands(root, counts, blocked_by),
        "forbidden_actions": _forbidden_actions(),
    }


def format_summary_markdown(summary: dict[str, Any]) -> str:
    counts = summary.get("counts") or {}
    safe_lines = ["- " + " ".join(command) for command in summary.get("safe_commands") or []] or ["- 无"]
    forbidden_lines = [f"- {item}" for item in summary.get("forbidden_actions") or []] or ["- 无"]
    return "\n".join(
        [
            "## Campaign Status",
            "",
            f"- Campaign：{summary.get('campaign_id', '')}",
            f"- Type：{summary.get('campaign_type', '')}",
            f"- Stage：{summary.get('current_stage', '')}",
            f"- Status：{summary.get('status', '')}",
            f"- Blocked by：{summary.get('blocked_by', '') or '无'}",
            f"- Candidates：{counts.get('candidate_count', 0)}",
            f"- Details：{counts.get('detail_count', 0)}",
            f"- Real contacts：{counts.get('real_contact_count', 0)}",
            f"- Maimai targets：{counts.get('maimai_target_count', 0)}",
            "",
            "### Safe Commands",
            "",
            *safe_lines,
            "",
            "### Forbidden Actions",
            "",
            *forbidden_lines,
            "",
        ]
    )


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _contact(candidate: dict[str, Any]) -> dict[str, Any]:
    contact = candidate.get("contact")
    return contact if isinstance(contact, dict) else {}


def _latest_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        key = str(row.get("candidate_key") or row.get("id") or index)
        latest[key] = row
    return latest


def _int_or_default(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _detect_campaign_type(root: Path, manifest: dict[str, Any]) -> str:
    workflow_chain = " ".join(str(item) for item in manifest.get("workflow_chain") or [])
    schema = str(manifest.get("schema") or "")
    if "boss-maimai" in workflow_chain or (root / "structured" / "maimai-match-targets.jsonl").exists():
        return "boss_maimai"
    if schema.startswith("boss_app_"):
        return "boss_app"
    if schema.startswith("liepin_"):
        return "liepin"
    if "maimai" in workflow_chain:
        return "maimai"
    return "unknown"


def _blocked_reason(continuation: dict[str, Any], stage_state: dict[str, Any]) -> str:
    status_text = " ".join(
        str(value)
        for value in [
            continuation.get("status"),
            stage_state.get("status"),
            continuation.get("reason"),
            stage_state.get("reason"),
        ]
        if value
    )
    if any(marker in status_text for marker in ["blocked", "stopped", "paid_", "验证码", "captcha", "security"]):
        return str(continuation.get("reason") or stage_state.get("reason") or continuation.get("status") or "")
    return ""


def _latest_interruption(root: Path) -> dict[str, Any]:
    reports_dir = root / "reports"
    if not reports_dir.exists():
        return {}
    files = sorted(reports_dir.glob("interruption-*.json"), key=lambda item: item.name)
    if not files:
        return {}
    latest = files[-1]
    payload = _object(load_json(latest, default={}))
    return {
        "path": latest.as_posix(),
        "reason": str(payload.get("stopped_reason") or payload.get("reason") or payload.get("stopReason") or ""),
        "status": str(payload.get("result") or payload.get("status") or ""),
    }


def _requires_user_authorization(blocked_by: str, dry_run_apply_status: dict[str, Any]) -> bool:
    if blocked_by:
        return True
    return (
        dry_run_apply_status.get("main_db_sync_dry_run_status") == "present"
        and dry_run_apply_status.get("main_db_sync_result_status") != "present"
    )


def _safe_recovery_commands(root: Path, counts: dict[str, int], blocked_by: str) -> list[list[str]]:
    if blocked_by:
        return []
    if counts.get("maimai_target_count", 0) > 0:
        return [
            [
                ".venv/bin/python",
                "-m",
                "scripts.platform_match.session",
                "verify",
                "--platform",
                "maimai",
            ]
        ]
    return [
        [
            ".venv/bin/python",
            "-m",
            "scripts.campaign_status",
            "summarize",
            "--campaign-root",
            root.as_posix(),
        ]
    ]


def _forbidden_actions() -> list[str]:
    return [
        "Do not write data/talent.db without explicit confirm text.",
        "Do not run Campaign DB apply from the status or next-action scripts.",
        "Do not trigger Feishu publish or IM notification from these read-only scripts.",
        "Do not execute platform live action: BOSS/Maimai/Liepin browsing, contact, or fetch.",
    ]


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only campaign status summary")
    subparsers = parser.add_subparsers(dest="command", required=True)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--campaign-root", required=True)
    summarize.add_argument("--format", choices=["json", "markdown"], default="json")

    args = parser.parse_args(argv)
    try:
        if args.command == "summarize":
            payload = summarize_campaign(args.campaign_root)
            if args.format == "markdown":
                print(format_summary_markdown(payload))
            else:
                _print_json(payload)
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
