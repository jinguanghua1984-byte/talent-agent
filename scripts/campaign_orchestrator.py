from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.campaign_status import summarize_campaign


NEXT_ACTION_SCHEMA = "campaign_next_action_v1"
CONFIRM_SYNC_TEXT = "确认同步人才库"
CONFIRM_CAMPAIGN_DB_TEXT = "确认写入 Campaign DB"


def next_action(campaign_root: str | Path) -> dict[str, Any]:
    summary = summarize_campaign(campaign_root)
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
    blocked_by = str(summary.get("blocked_by") or "")
    dry_run_apply_status = (
        summary.get("dry_run_apply_status")
        if isinstance(summary.get("dry_run_apply_status"), dict)
        else {}
    )
    artifact_status = (
        summary.get("artifact_status")
        if isinstance(summary.get("artifact_status"), dict)
        else {}
    )
    derived_stage = str(summary.get("derived_stage") or "")
    forbidden = _forbidden_commands()

    if blocked_by == "paid_search_chat_card":
        return _action(
            summary,
            next_stage="boss-executor-quota-resolution",
            blocked_by=blocked_by,
            requires_user_authorization=True,
            safe_commands=[],
            forbidden_commands=forbidden,
            required_confirm_text="",
        )

    if derived_stage == "standardize-needed":
        return _action(
            summary,
            next_stage="standardize",
            blocked_by="missing_structured_candidates",
            requires_user_authorization=False,
            safe_commands=[
                [
                    ".venv/bin/python",
                    "-m",
                    "scripts.campaign_status",
                    "summarize",
                    "--campaign-root",
                    str(campaign_root),
                ]
            ],
            forbidden_commands=forbidden,
            required_confirm_text="",
        )

    if _has_main_db_dry_run(dry_run_apply_status):
        return _action(
            summary,
            next_stage="main-db-apply-authorization",
            blocked_by="requires_user_confirm",
            requires_user_authorization=True,
            safe_commands=[],
            forbidden_commands=forbidden,
            required_confirm_text=CONFIRM_SYNC_TEXT,
        )

    if _has_campaign_db_dry_run(dry_run_apply_status):
        return _action(
            summary,
            next_stage="campaign-db-apply-authorization",
            blocked_by="requires_user_confirm",
            requires_user_authorization=True,
            safe_commands=[],
            forbidden_commands=forbidden,
            required_confirm_text=CONFIRM_CAMPAIGN_DB_TEXT,
        )

    if _has_feishu_publish_pending(dry_run_apply_status, artifact_status):
        return _action(
            summary,
            next_stage="feishu-publish-preflight",
            blocked_by="requires_feishu_publish",
            requires_user_authorization=False,
            safe_commands=[
                ["lark-cli", "doctor"],
                ["lark-cli", "auth", "status"],
            ],
            forbidden_commands=forbidden,
            required_confirm_text="",
        )

    if _has_feishu_im_pending(dry_run_apply_status, artifact_status):
        return _action(
            summary,
            next_stage="feishu-im-notification",
            blocked_by="requires_im_notification",
            requires_user_authorization=False,
            safe_commands=[
                [
                    ".venv/bin/python",
                    "-m",
                    "scripts.campaign_orchestrator",
                    "next-action",
                    "--campaign-root",
                    str(campaign_root),
                ]
            ],
            forbidden_commands=forbidden,
            required_confirm_text="",
        )

    if int(counts.get("maimai_target_count") or 0) > 0:
        bound_count = int(counts.get("maimai_identity_bound_count") or 0)
        target_count = int(counts.get("maimai_target_count") or 0)
        if bound_count < target_count:
            return _action(
                summary,
                next_stage="maimai-match-session",
                blocked_by="requires_maimai_cdp",
                requires_user_authorization=False,
                safe_commands=[
                    [
                        ".venv/bin/python",
                        "-m",
                        "scripts.platform_match.session",
                        "verify",
                        "--platform",
                        "maimai",
                    ]
                ],
                forbidden_commands=forbidden,
                required_confirm_text="",
            )

    return _action(
        summary,
        next_stage="status-review",
        blocked_by=blocked_by or "no_deterministic_next_action",
        requires_user_authorization=bool(blocked_by),
        safe_commands=[
            [
                ".venv/bin/python",
                "-m",
                "scripts.campaign_status",
                "summarize",
                "--campaign-root",
                str(campaign_root),
            ]
        ],
        forbidden_commands=forbidden,
        required_confirm_text="",
    )


def _action(
    summary: dict[str, Any],
    *,
    next_stage: str,
    blocked_by: str,
    requires_user_authorization: bool,
    safe_commands: list[list[str]],
    forbidden_commands: list[str],
    required_confirm_text: str,
) -> dict[str, Any]:
    payload = {
        "schema": NEXT_ACTION_SCHEMA,
        "campaign_root": summary.get("campaign_root"),
        "campaign_id": summary.get("campaign_id"),
        "campaign_type": summary.get("campaign_type"),
        "current_stage": summary.get("current_stage"),
        "current_status": summary.get("status"),
        "next_stage": next_stage,
        "blocked_by": blocked_by,
        "requires_user_authorization": requires_user_authorization,
        "safe_commands": safe_commands,
        "forbidden_commands": forbidden_commands,
        "summary": {
            "counts": summary.get("counts") or {},
            "continuation_plan": summary.get("continuation_plan") or {},
            "dry_run_apply_status": summary.get("dry_run_apply_status") or {},
            "artifact_status": summary.get("artifact_status") or {},
            "missing_artifacts": summary.get("missing_artifacts") or [],
            "derived_stage": summary.get("derived_stage") or "",
        },
    }
    if required_confirm_text:
        payload["required_confirm_text"] = required_confirm_text
    return payload


def _has_main_db_dry_run(dry_run_apply_status: dict[str, Any]) -> bool:
    return (
        dry_run_apply_status.get("main_db_sync_dry_run_status") == "present"
        and dry_run_apply_status.get("main_db_sync_result_status") != "present"
    )


def _has_campaign_db_dry_run(dry_run_apply_status: dict[str, Any]) -> bool:
    return (
        dry_run_apply_status.get("campaign_db_sync_dry_run_status") == "present"
        and dry_run_apply_status.get("campaign_db_sync_result_status") != "present"
    )


def _has_feishu_publish_pending(
    dry_run_apply_status: dict[str, Any],
    artifact_status: dict[str, Any],
) -> bool:
    return (
        dry_run_apply_status.get("feishu_dry_run_status") == "passed"
        and artifact_status.get("feishu_publish_results") != "present"
    )


def _has_feishu_im_pending(
    dry_run_apply_status: dict[str, Any],
    artifact_status: dict[str, Any],
) -> bool:
    return (
        artifact_status.get("feishu_publish_results") == "present"
        and dry_run_apply_status.get("im_notification_status") not in {"sent", "ok", "passed", "present"}
    )


def _forbidden_commands() -> list[str]:
    return [
        "Do not run scripts/talent_sync.py import --apply against data/talent.db without confirm text.",
        "Do not write data/talent.db from campaign next-action.",
        "Do not trigger Feishu publish or IM notification from campaign next-action.",
        "Do not execute platform live action from campaign next-action.",
    ]


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only campaign next-action helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    next_action_parser = subparsers.add_parser("next-action")
    next_action_parser.add_argument("--campaign-root", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "next-action":
            _print_json(next_action(args.campaign_root))
            return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
