import json
import subprocess
import sys
from pathlib import Path

from scripts.campaign_status import summarize_campaign


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def _boss_maimai_campaign(root: Path) -> Path:
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": root.name,
            "status": "blocked_missing_computer_use",
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
    _write_json(
        root / "reports" / "interruption-executor-paid_search_chat_card-20260606T213445.json",
        {"result": "stopped", "stopped_reason": "paid_search_chat_card"},
    )
    _write_json(
        root / "reports" / "executor-validation.json",
        {"status": "passed", "issues": []},
    )
    _write_json(
        root / "reports" / "maimai-match-summary.json",
        {
            "selected_count": 7,
            "target_count": 6,
            "missing_real_name_count": 1,
        },
    )
    _append_jsonl(
        root / "raw" / "list-cards.jsonl",
        [{"candidate_key": "c1"}, {"candidate_key": "c2"}, {"candidate_key": "c3"}],
    )
    _append_jsonl(
        root / "raw" / "detail-pages.jsonl",
        [{"candidate_key": "c1"}, {"candidate_key": "c2"}],
    )
    _append_jsonl(
        root / "structured" / "candidates.jsonl",
        [
            {
                "candidate_key": "c1",
                "contact": {"would_contact": True, "contacted": True, "contact_mode": "external_executor"},
                "real_name_status": "captured",
            },
            {
                "candidate_key": "c2",
                "contact": {"would_contact": True, "contacted": False},
                "real_name_status": "not_available_dry_run",
            },
        ],
    )
    _append_jsonl(
        root / "structured" / "contact-decisions.jsonl",
        [
            {"candidate_key": "c1", "mode": "external_executor", "would_contact": True, "contacted": True},
            {"candidate_key": "c2", "mode": "dry_run", "would_contact": True, "contacted": False},
        ],
    )
    _append_jsonl(root / "structured" / "maimai-match-targets.jsonl", [{"candidate_key": "c1"}])
    _append_jsonl(
        root / "state" / "cross-channel-identity-ledger.jsonl",
        [{"boss_candidate_key": "c1", "status": "auto_bound"}],
    )
    return root


def test_summarize_campaign_reads_boss_maimai_artifacts_without_side_effects(tmp_path: Path) -> None:
    root = _boss_maimai_campaign(tmp_path / "boss-maimai-demo")

    summary = summarize_campaign(root)

    assert summary["schema"] == "campaign_status_summary_v1"
    assert summary["campaign_type"] == "boss_maimai"
    assert summary["current_stage"] == "external_executor"
    assert summary["status"] == "stopped"
    assert summary["blocked_by"] == "paid_search_chat_card"
    assert summary["counts"] == {
        "list_card_count": 3,
        "candidate_count": 2,
        "detail_count": 2,
        "would_contact_count": 2,
        "real_contact_count": 1,
        "external_executor_contact_count": 1,
        "maimai_target_count": 6,
        "maimai_missing_real_name_count": 1,
        "maimai_identity_bound_count": 1,
    }
    assert summary["latest_interruption"]["reason"] == "paid_search_chat_card"
    assert summary["continuation_plan"]["next_action"] == "wait_for_quota_or_user_resolution"
    assert summary["dry_run_apply_status"]["executor_validation_status"] == "passed"
    assert summary["requires_user_authorization"] is True
    assert summary["forbidden_actions"]

    assert not (root / "reports" / "campaign-status-summary.json").exists()


def test_summarize_campaign_reports_missing_structured_candidates_and_stage(tmp_path: Path) -> None:
    root = tmp_path / "raw-only"
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": "raw-only",
            "status": "raw_captured",
        },
    )
    _append_jsonl(
        root / "raw" / "list-cards.jsonl",
        [{"candidate_key": "c1"}, {"candidate_key": "c2"}],
    )

    summary = summarize_campaign(root)

    assert summary["artifact_status"]["raw_list_cards"] == "present"
    assert summary["artifact_status"]["structured_candidates"] == "missing"
    assert "structured/candidates.jsonl" in summary["missing_artifacts"]
    assert summary["derived_stage"] == "standardize-needed"


def test_summarize_campaign_reports_db_and_feishu_artifact_status(tmp_path: Path) -> None:
    root = tmp_path / "db-feishu-pending"
    _write_json(
        root / "campaign-manifest.json",
        {
            "schema": "boss_app_recommendation_sourcing_manifest_v1",
            "campaign_id": "db-feishu-pending",
            "status": "ready_for_sync",
        },
    )
    _append_jsonl(root / "raw" / "list-cards.jsonl", [{"candidate_key": "c1"}])
    _append_jsonl(root / "structured" / "candidates.jsonl", [{"candidate_key": "c1"}])
    _write_json(root / "reports" / "campaign-db-sync-dry-run.json", {"would_write": 1})
    _write_json(root / "reports" / "main-db-sync-dry-run.json", {"created": {"candidates": 1}})
    _write_json(root / "feishu" / "dry-run-results.json", {"status": "passed"})

    summary = summarize_campaign(root)

    assert summary["artifact_status"]["campaign_db_sync_dry_run"] == "present"
    assert summary["artifact_status"]["campaign_db_sync_result"] == "missing"
    assert summary["artifact_status"]["main_db_sync_dry_run"] == "present"
    assert summary["artifact_status"]["main_db_sync_result"] == "missing"
    assert summary["artifact_status"]["feishu_dry_run_results"] == "present"
    assert summary["artifact_status"]["feishu_publish_results"] == "missing"
    assert summary["artifact_status"]["feishu_readback_results"] == "missing"
    assert summary["artifact_status"]["im_notification_results"] == "missing"
    assert summary["dry_run_apply_status"]["campaign_db_sync_dry_run_status"] == "present"
    assert summary["dry_run_apply_status"]["feishu_dry_run_status"] == "passed"
    assert summary["derived_stage"] == "main-db-apply-authorization"
    assert "reports/main-db-sync-result.json" in summary["missing_artifacts"]


def test_campaign_status_cli_outputs_json_and_markdown(tmp_path: Path) -> None:
    root = _boss_maimai_campaign(tmp_path / "boss-maimai-demo")

    completed = subprocess.run(
        [sys.executable, "-m", "scripts.campaign_status", "summarize", "--campaign-root", str(root)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["campaign_root"] == str(root)

    md = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.campaign_status",
            "summarize",
            "--campaign-root",
            str(root),
            "--format",
            "markdown",
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert md.returncode == 0, md.stderr
    assert "## Campaign Status" in md.stdout
    assert "paid_search_chat_card" in md.stdout
