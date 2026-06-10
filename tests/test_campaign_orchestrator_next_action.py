import json
import subprocess
import sys
from pathlib import Path

from scripts.campaign_orchestrator import next_action


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _raw_without_structured(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": root.name,
            "status": "raw_captured",
        },
    )
    _write_jsonl(root / "raw" / "list-cards.jsonl", [{"candidate_key": "c1"}])
    return root


def _campaign_db_dry_run_pending(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "liepin_campaign_manifest_v1",
            "campaign_id": root.name,
            "status": "campaign_db_dry_run_ready",
        },
    )
    _write_jsonl(root / "raw" / "list-cards.jsonl", [{"candidate_key": "c1"}])
    _write_jsonl(root / "structured" / "candidates.jsonl", [{"candidate_key": "c1"}])
    _write_json(root / "reports" / "campaign-db-sync-dry-run.json", {"would_write": 1})
    return root


def _feishu_dry_run_pending_publish(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_maimai_delivery_manifest_v1",
            "campaign_id": root.name,
            "workflow_chain": ["agents/skills/boss-maimai-cross-channel-delivery/SKILL.md"],
        },
    )
    _write_jsonl(root / "raw" / "list-cards.jsonl", [{"candidate_key": "c1"}])
    _write_jsonl(root / "structured" / "candidates.jsonl", [{"candidate_key": "c1"}])
    _write_json(root / "reports" / "main-db-sync-result.json", {"written": 1})
    _write_json(root / "feishu" / "dry-run-results.json", {"status": "passed"})
    return root


def _feishu_publish_pending_im(root: Path) -> Path:
    _feishu_dry_run_pending_publish(root)
    _write_json(root / "feishu" / "boss-maimai-delivery-publish-results.json", {"status": "published"})
    return root


def _boss_maimai_blocked_campaign(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": root.name,
            "workflow_chain": [
                "agents/skills/boss-app-recommendation-sourcing/SKILL.md",
                "agents/skills/boss-maimai-cross-channel-delivery/SKILL.md",
            ],
        },
    )
    _write_json(
        root / "state" / "continuation-plan.json",
        {
            "stage": "external_executor",
            "status": "stopped",
            "reason": "paid_search_chat_card",
            "next_action": "wait_for_quota_or_user_resolution",
        },
    )
    _write_json(root / "reports" / "executor-validation.json", {"status": "passed", "issues": []})
    _write_json(
        root / "reports" / "maimai-match-summary.json",
        {"selected_count": 7, "target_count": 6, "missing_real_name_count": 1},
    )
    _write_jsonl(root / "structured" / "maimai-match-targets.jsonl", [{"candidate_key": "c1"}])
    _write_jsonl(root / "state" / "cross-channel-identity-ledger.jsonl", [])
    return root


def _boss_maimai_ready_for_maimai(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": root.name,
            "workflow_chain": [
                "agents/skills/boss-app-recommendation-sourcing/SKILL.md",
                "agents/skills/boss-maimai-cross-channel-delivery/SKILL.md",
            ],
        },
    )
    _write_json(
        root / "state" / "continuation-plan.json",
        {
            "stage": "boss_sourcing",
            "status": "boss_stopped",
            "reason": "boss_contact_budget_reached",
            "next_action": "run_maimai_match",
        },
    )
    _write_json(root / "reports" / "executor-validation.json", {"status": "passed", "issues": []})
    _write_json(root / "reports" / "maimai-match-summary.json", {"target_count": 2, "missing_real_name_count": 0})
    _write_jsonl(root / "structured" / "maimai-match-targets.jsonl", [{"candidate_key": "c1"}, {"candidate_key": "c2"}])
    return root


def _boss_maimai_ready_for_delivery(root: Path) -> Path:
    _boss_maimai_ready_for_maimai(root)
    _write_jsonl(
        root / "state" / "cross-channel-identity-ledger.jsonl",
        [
            {"boss_candidate_key": "c1", "status": "auto_bound"},
            {"boss_candidate_key": "c2", "status": "confirmed_bound"},
        ],
    )
    _write_json(root / "reports" / "campaign-db-quality-gates.json", {"status": "passed", "blockers": []})
    _write_json(root / "reports" / "main-db-sync-dry-run.json", {"created": {"candidates": 2}, "conflicts": {"candidates": 0}})
    return root


def test_next_action_blocks_paid_boss_executor_without_safe_commands(tmp_path: Path) -> None:
    root = _boss_maimai_blocked_campaign(tmp_path / "blocked")

    action = next_action(root)

    assert action["schema"] == "campaign_next_action_v1"
    assert action["campaign_type"] == "boss_maimai"
    assert action["next_stage"] == "boss-executor-quota-resolution"
    assert action["blocked_by"] == "paid_search_chat_card"
    assert action["requires_user_authorization"] is True
    assert action["safe_commands"] == []
    assert "data/talent.db" in " ".join(action["forbidden_commands"])
    assert "Feishu" in " ".join(action["forbidden_commands"])
    assert "platform live action" in " ".join(action["forbidden_commands"])


def test_next_action_suggests_maimai_session_verify_when_targets_exist(tmp_path: Path) -> None:
    root = _boss_maimai_ready_for_maimai(tmp_path / "ready-maimai")

    action = next_action(root)

    assert action["next_stage"] == "maimai-match-session"
    assert action["blocked_by"] == "requires_maimai_cdp"
    assert action["requires_user_authorization"] is False
    assert action["safe_commands"] == [
        [
            ".venv/bin/python",
            "-m",
            "scripts.platform_match.session",
            "verify",
            "--platform",
            "maimai",
        ]
    ]
    assert action["forbidden_commands"]


def test_next_action_blocks_main_db_apply_until_confirm_text(tmp_path: Path) -> None:
    root = _boss_maimai_ready_for_delivery(tmp_path / "ready-delivery")

    action = next_action(root)

    assert action["next_stage"] == "main-db-apply-authorization"
    assert action["blocked_by"] == "requires_user_confirm"
    assert action["required_confirm_text"] == "确认同步人才库"
    assert action["requires_user_authorization"] is True
    assert action["safe_commands"] == []
    assert any("talent_sync.py import --apply" in command for command in action["forbidden_commands"])


def test_campaign_orchestrator_next_action_cli(tmp_path: Path) -> None:
    root = _boss_maimai_ready_for_maimai(tmp_path / "ready-maimai")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.campaign_orchestrator",
            "next-action",
            "--campaign-root",
            str(root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["next_stage"] == "maimai-match-session"
    assert payload["safe_commands"][0][2] == "scripts.platform_match.session"


def test_next_action_suggests_standardize_when_raw_exists_without_structured(tmp_path: Path) -> None:
    root = _raw_without_structured(tmp_path / "raw-only")

    action = next_action(root)

    assert action["next_stage"] == "standardize"
    assert action["blocked_by"] == "missing_structured_candidates"
    assert action["requires_user_authorization"] is False
    assert "structured/candidates.jsonl" in action["summary"]["missing_artifacts"]
    assert action["safe_commands"][0][:4] == [
        ".venv/bin/python",
        "-m",
        "scripts.campaign_status",
        "summarize",
    ]


def test_next_action_blocks_campaign_db_apply_until_confirm_text(tmp_path: Path) -> None:
    root = _campaign_db_dry_run_pending(tmp_path / "campaign-db-pending")

    action = next_action(root)

    assert action["next_stage"] == "campaign-db-apply-authorization"
    assert action["blocked_by"] == "requires_user_confirm"
    assert action["required_confirm_text"] == "确认写入 Campaign DB"
    assert action["requires_user_authorization"] is True
    assert action["safe_commands"] == []
    assert "reports/campaign-db-sync-result.json" in action["summary"]["missing_artifacts"]


def test_next_action_suggests_feishu_publish_preflight_after_dry_run(tmp_path: Path) -> None:
    root = _feishu_dry_run_pending_publish(tmp_path / "feishu-pending")

    action = next_action(root)

    assert action["next_stage"] == "feishu-publish-preflight"
    assert action["blocked_by"] == "requires_feishu_publish"
    assert action["requires_user_authorization"] is False
    assert action["safe_commands"] == [
        ["lark-cli", "doctor"],
        ["lark-cli", "auth", "status"],
    ]
    assert "feishu/boss-maimai-delivery-publish-results.json" in action["summary"]["missing_artifacts"]


def test_next_action_suggests_im_notification_after_feishu_publish(tmp_path: Path) -> None:
    root = _feishu_publish_pending_im(tmp_path / "im-pending")

    action = next_action(root)

    assert action["next_stage"] == "feishu-im-notification"
    assert action["blocked_by"] == "requires_im_notification"
    assert action["requires_user_authorization"] is False
    assert action["safe_commands"] == [
        [
            ".venv/bin/python",
            "-m",
            "scripts.campaign_orchestrator",
            "next-action",
            "--campaign-root",
            str(root),
        ]
    ]
    assert "feishu/im-notification-results.json" in action["summary"]["missing_artifacts"]
