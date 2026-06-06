import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import campaign_to_delivery
from scripts.talent_db import TalentDB
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT


def _clean_campaign_db(path: Path) -> int:
    db = TalentDB(path)
    try:
        candidate_id = db.ingest(
            {
                "name": "陶壮",
                "current_company": "华为技术有限公司",
                "current_title": "大模型推理工程师",
                "platform_id": "boss-001",
            },
            platform="boss_app",
        )
        db.merge_candidate_source(
            candidate_id,
            {
                "name": "陶壮",
                "platform_id": "mm-001",
                "profile_url": (
                    "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
                ),
            },
            platform="maimai",
        )
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:1",
                "target_platform": "maimai",
                "target_platform_id": "mm-001",
                "target_profile_url": (
                    "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
                ),
                "query_text": "陶壮 华为技术有限公司 大模型推理工程师",
                "query_level": "name_company_title",
                "confidence": 98,
                "score_breakdown": {"total": 98},
                "match_status": "auto_bound",
                "decision_reason": "高精度匹配",
            }
        )
        db.record_field_value(
            {
                "candidate_id": candidate_id,
                "field_name": "profile_url",
                "platform": "maimai",
                "field_value": (
                    "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
                ),
                "confidence": 95,
                "merge_decision": "supplement_added",
                "decision_reason": "补充脉脉主页",
            }
        )
        return candidate_id
    finally:
        db.close()


def test_validate_campaign_ready_passes_clean_campaign(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    _clean_campaign_db(root / "talent.db")

    result = campaign_to_delivery.validate_campaign_ready(root, root / "talent.db")

    assert result["status"] == "passed"
    assert result["integrity_check"] == "ok"
    assert result["foreign_key_violation_count"] == 0
    assert result["pending_identity_count"] == 0
    assert result["unresolved_identity_count"] == 0
    assert result["candidate_count"] == 1
    assert (root / "reports/campaign-db-quality-gates.json").exists()


def test_validate_campaign_ready_blocks_pending_identity(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    db_path = root / "talent.db"
    _clean_campaign_db(db_path)
    db = TalentDB(db_path)
    try:
        candidate_id = db.search().items[0].id
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:2",
                "target_platform": "maimai",
                "target_platform_id": "mm-002",
                "query_text": "陶壮 华为",
                "query_level": "name_company_fallback",
                "confidence": 88,
                "score_breakdown": {"total": 88},
                "match_status": "pending_confirmation",
                "decision_reason": "fallback",
            }
        )
    finally:
        db.close()

    result = campaign_to_delivery.validate_campaign_ready(root, db_path)

    assert result["status"] == "blocked"
    assert "pending_identity" in result["blockers"]
    assert "unresolved_identity" in result["blockers"]


def test_sync_main_requires_authorization(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)

    with pytest.raises(ValueError, match="allow_main_db_write_after_clean_campaign"):
        campaign_to_delivery.sync_main_db(
            root,
            campaign_db,
            main_db,
            allow_main_db_write_after_clean_campaign=False,
            confirm=CONFIRM_SYNC_TEXT,
        )


def test_sync_main_requires_confirm_text(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)

    with pytest.raises(ValueError, match=CONFIRM_SYNC_TEXT):
        campaign_to_delivery.sync_main_db(
            root,
            campaign_db,
            main_db,
            allow_main_db_write_after_clean_campaign=True,
            confirm="wrong",
        )


def test_sync_main_blocks_unclean_campaign_without_writing_main(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)
    db = TalentDB(campaign_db)
    try:
        candidate_id = db.search().items[0].id
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:pending",
                "target_platform": "maimai",
                "target_platform_id": "mm-pending",
                "query_text": "陶壮 华为",
                "query_level": "name_company_fallback",
                "confidence": 80,
                "score_breakdown": {"total": 80},
                "match_status": "pending_confirmation",
            }
        )
    finally:
        db.close()

    result = campaign_to_delivery.sync_main_db(
        root,
        campaign_db,
        main_db,
        allow_main_db_write_after_clean_campaign=True,
        confirm=CONFIRM_SYNC_TEXT,
    )

    assert result["status"] == "blocked"
    assert result["reason"] == "campaign_not_clean"
    assert not main_db.exists()


def test_sync_main_exports_bundle_applies_and_writes_campaign_delivery_handoff(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)
    legacy_handoff_path = root / "state/jd-delivery-handoff.json"
    legacy_handoff_path.parent.mkdir(parents=True)
    legacy_handoff_path.write_text(
        json.dumps({"schema": "jd_delivery_handoff_v1"}),
        encoding="utf-8",
    )

    result = campaign_to_delivery.sync_main_db(
        root,
        campaign_db,
        main_db,
        allow_main_db_write_after_clean_campaign=True,
        confirm=CONFIRM_SYNC_TEXT,
        delivery_context={"jd_input": "AI Infra JD", "top_n": 30, "publish_feishu": True},
    )

    assert result["status"] == "applied"
    assert result["dry_run"]["tables"]["candidates"] == 1
    assert result["dry_run"]["created"]["candidates"] == 1
    assert (root / "sync/campaign-to-main.zip").exists()
    assert (root / "reports/main-db-sync-dry-run.json").exists()
    assert (root / "reports/main-db-sync-result.json").exists()
    handoff_path = root / "state/boss-maimai-delivery-handoff.json"
    assert handoff_path.exists()
    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
    assert handoff["schema"] == "boss_maimai_campaign_delivery_handoff_v1"
    assert handoff["delivery_kind"] == "boss_maimai_campaign_delivery"
    assert handoff["delivery_script"] == "scripts/boss_maimai_campaign_delivery.py"
    assert handoff["main_db_path"] == str(main_db)
    assert handoff["delivery_context"]["jd_input"] == "AI Infra JD"
    assert handoff["delivery_context"]["top_n"] == 30
    assert handoff["legacy_jd_delivery_default"] is False
    assert handoff["outputs"] == {
        "report_json": "reports/boss-maimai-delivery-report.json",
        "report_md": "reports/boss-maimai-delivery-report.md",
        "follow_up_csv": "reports/boss-maimai-follow-up-queue.csv",
        "follow_up_md": "reports/boss-maimai-follow-up-queue.md",
        "quality_gates": "reports/boss-maimai-delivery-quality-gates.json",
        "feishu_manifest": "feishu/boss-maimai-delivery-manifest.json",
    }
    assert handoff["url_priority"][0] == "maimai"
    assert not legacy_handoff_path.exists()

    db = TalentDB(main_db)
    try:
        candidate = db.search().items[0]
        sources = db.get_sources(candidate.id)
        assert db.count() == 1
        assert any(source.platform == "maimai" for source in sources)
        assert db.identity_matches(candidate.id)[0].target_platform == "maimai"
    finally:
        db.close()


def test_validate_campaign_cli_returns_nonzero_when_blocked(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    db_path = root / "talent.db"
    _clean_campaign_db(db_path)
    db = TalentDB(db_path)
    try:
        candidate_id = db.search().items[0].id
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:pending",
                "target_platform": "maimai",
                "target_platform_id": "mm-pending",
                "query_text": "陶壮 华为",
                "query_level": "name_company_fallback",
                "confidence": 80,
                "score_breakdown": {"total": 80},
                "match_status": "pending_confirmation",
            }
        )
    finally:
        db.close()

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.campaign_to_delivery",
            "validate-campaign",
            "--campaign-root",
            str(root),
            "--db",
            str(db_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    output = json.loads(completed.stdout)
    assert output["status"] == "blocked"
