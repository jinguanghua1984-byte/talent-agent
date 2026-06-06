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
