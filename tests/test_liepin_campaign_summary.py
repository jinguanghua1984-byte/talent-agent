import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_campaign_summary import build_campaign_summary, write_campaign_summary
from scripts.talent_db import TalentDB


def _seed_campaign_db(root: Path) -> None:
    db = TalentDB(root / "talent.db")
    try:
        first = db.ingest(
            {
                "name": "张**（猎聘res-1）",
                "platform_id": "res-1",
                "profile_url": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
                "city": "北京",
                "work_years": 8,
                "education": "硕士",
                "current_company": "示例公司",
                "current_title": "AI产品经理",
                "raw_profile": {
                    "liepin_search_summary": {
                        "display_name": "张**",
                        "raw_ref": {"search_page": "raw/search/page-000.json", "ckId": "secret"},
                    }
                },
            },
            platform="liepin",
        )
        db.ingest(
            {
                "name": "李**（猎聘res-2）",
                "platform_id": "res-2",
                "city": "上海",
                "work_years": 3,
                "education": "本科",
                "current_company": "另一公司",
                "current_title": "产品经理",
            },
            platform="liepin",
        )
        db.ingest(
            {
                "name": "王**（猎聘res-3）",
                "platform_id": "res-3",
                "city": "北京",
                "work_years": 12,
                "education": "博士",
                "current_company": "示例公司",
                "current_title": "高级产品经理",
            },
            platform="liepin",
        )
        db.enrich(
            first,
            {
                "work_experience": [{"company": "示例公司", "title": "AI产品经理"}],
                "education_experience": [{"school": "示例大学"}],
                "project_experience": [],
                "raw_data": {
                    "liepin_detail_capture": {
                        "platform_id": "res-1",
                        "raw_path": "raw/detail-live/pack/job-000.json",
                    }
                },
            },
        )
    finally:
        db.close()


def test_build_campaign_summary_reads_campaign_db_without_writing(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _seed_campaign_db(paths.root)
    before_mtime = (paths.root / "talent.db").stat().st_mtime_ns

    summary = build_campaign_summary(paths.root)

    after_mtime = (paths.root / "talent.db").stat().st_mtime_ns
    assert after_mtime == before_mtime
    assert summary["schema"] == "liepin_campaign_summary_v1"
    assert summary["campaign_id"] == "liepin-demo"
    assert summary["candidate_count"] == 3
    assert summary["source_profile_count"] == 3
    assert summary["detail_count"] == 1
    assert summary["detail_coverage_ratio"] == pytest.approx(1 / 3)
    assert summary["data_level_counts"] == {"core": 2, "detailed": 1}
    assert summary["city_top"] == [{"value": "北京", "count": 2}, {"value": "上海", "count": 1}]
    assert summary["education_top"][0] == {"value": "博士", "count": 1}
    assert summary["work_year_buckets"] == {
        "0-3": 1,
        "4-7": 0,
        "8-10": 1,
        "11+": 1,
        "unknown": 0,
    }
    assert summary["no_recommendation_report"] is True
    assert summary["no_feishu_delivery"] is True


def test_write_campaign_summary_writes_sanitized_local_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _seed_campaign_db(paths.root)

    summary = write_campaign_summary(paths.root)

    assert summary["candidate_count"] == 3
    report_json = paths.reports_dir / "campaign-summary.json"
    report_md = paths.reports_dir / "campaign-summary.md"
    assert report_json.exists()
    assert report_md.exists()
    dumped = report_json.read_text(encoding="utf-8-sig") + report_md.read_text(encoding="utf-8")
    assert "showresumedetail" not in dumped
    assert "ck_id=" not in dumped
    assert "rawPreview" not in dumped
    assert "secret" not in dumped


def test_campaign_summary_requires_existing_campaign_db(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    with pytest.raises(RuntimeError, match="campaign db does not exist"):
        build_campaign_summary(paths.root)


def test_campaign_summary_cli_prints_json(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _seed_campaign_db(paths.root)

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_campaign_summary",
            "--campaign-root",
            str(paths.root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["schema"] == "liepin_campaign_summary_v1"
    assert payload["candidate_count"] == 3
    assert (paths.reports_dir / "campaign-summary.json").exists()
