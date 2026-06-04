import json
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_main_db_sync_handoff import write_main_db_sync_handoff
from scripts.talent_db import TalentDB


def _seed_liepin_campaign_db(root: Path) -> None:
    db = TalentDB(root / "talent.db")
    try:
        candidate_id = db.ingest(
            {
                "name": "张**（猎聘res-1）",
                "platform_id": "res-1",
                "city": "北京",
                "work_years": 8,
                "education": "硕士",
                "current_company": "示例公司",
                "current_title": "AI产品经理",
                "raw_profile": {
                    "liepin_search_summary": {
                        "raw_ref": {
                            "search_page": "raw/search-adaptive/search-wave-001/unit-000001/page-000.json",
                            "wave_id": "search-wave-001",
                            "unit_id": "unit-000001",
                        }
                    }
                },
            },
            platform="liepin",
        )
        db.enrich(
            candidate_id,
            {
                "work_experience": [{"company": "示例公司", "title": "AI产品经理"}],
                "education_experience": [{"school": "示例大学"}],
                "raw_data": {"liepin_detail_capture": {"raw_path": "raw/detail-live/pack/job-000.json"}},
            },
        )
    finally:
        db.close()


def test_write_main_db_sync_handoff_exports_verified_bundle_and_dry_run_plan(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _seed_liepin_campaign_db(paths.root)
    main_db = tmp_path / "main-talent.db"

    result = write_main_db_sync_handoff(paths.root, main_db_path=main_db)

    assert result["schema"] == "liepin_main_db_sync_handoff_v1"
    assert result["campaign_id"] == "liepin-demo"
    assert result["source_db"] == (paths.root / "talent.db").as_posix()
    assert result["target_main_db"] == main_db.as_posix()
    assert result["bundle"]["verified"] is True
    assert result["bundle"]["tables"]["candidates"] == 1
    assert result["dry_run"]["created"]["candidates"] == 1
    assert result["dry_run"]["conflicts"]["candidates"] == 0
    assert result["no_main_db_write"] is True
    assert result["apply_requires_separate_confirmation"] is True
    assert not main_db.exists()

    bundle_path = Path(result["bundle"]["path"])
    assert bundle_path.exists()
    assert bundle_path.parent == paths.root / "exports"
    report_json = paths.reports_dir / "main-db-sync-handoff.json"
    report_md = paths.reports_dir / "main-db-sync-handoff.md"
    assert report_json.exists()
    assert report_md.exists()

    report_text = report_json.read_text(encoding="utf-8-sig") + report_md.read_text(encoding="utf-8")
    assert "showresumedetail" not in report_text
    assert "ck_id" not in report_text
    assert "rawPreview" not in report_text


def test_write_main_db_sync_handoff_refuses_missing_campaign_db(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    with pytest.raises(RuntimeError, match="campaign db does not exist"):
        write_main_db_sync_handoff(paths.root, main_db_path=tmp_path / "main.db")


def test_write_main_db_sync_handoff_does_not_modify_existing_main_db(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _seed_liepin_campaign_db(paths.root)
    main_db = tmp_path / "main-talent.db"
    db = TalentDB(main_db)
    db.close()
    before_mtime = main_db.stat().st_mtime_ns

    result = write_main_db_sync_handoff(paths.root, main_db_path=main_db)

    after_mtime = main_db.stat().st_mtime_ns
    assert after_mtime == before_mtime
    assert result["no_main_db_write"] is True
    saved = json.loads((paths.reports_dir / "main-db-sync-handoff.json").read_text(encoding="utf-8-sig"))
    assert saved["target_main_db"] == main_db.as_posix()
