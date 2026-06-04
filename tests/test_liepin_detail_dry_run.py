import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_live_gate import detail_job_path
from scripts.liepin_detail_dry_run import (
    CONFIRM_TEXT,
    apply_detail_jobs,
    build_detail_dry_run,
    dry_run_detail_jobs,
)
from scripts.talent_db import TalentDB


def _write_target_pack(root: Path, contacts: list[dict]) -> Path:
    pack_path = root / "raw" / "detail-targets" / "liepin-detail-p0-smoke-001.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_targets_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": "liepin-detail-p0-smoke-001",
                    "limit": len(contacts),
                    "no_database_write": True,
                },
                "contacts": contacts,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_path


def _write_full_target_pack(root: Path, contacts: list[dict]) -> Path:
    pack_path = root / "raw" / "detail-targets" / "detail-p0-p1-pack-001.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_pack_plan_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": "detail-p0-p1-pack-001",
                    "scope": "p0-p1",
                    "no_database_write": True,
                },
                "contacts": contacts,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_path


def _contact(platform_id: str, index: int) -> dict:
    return {
        "index": index,
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": f"user-{platform_id}",
        "profile_url": (
            "https://h.liepin.com/resume/showresumedetail/"
            f"?res_id_encode={platform_id}&ck_id=secret-token&sk_id=secret-sk&fk_id=secret-fk"
        ),
        "display_name": "张**",
        "current_company": "示例公司",
        "current_title": "AI产品经理",
        "priority": "detail_p0",
        "raw_ref": {"search_page": "raw/search/page-000.json", "card_index": index},
    }


def _detail_response() -> dict:
    return {
        "flag": 1,
        "data": {
            "resumeDetailVo": {
                "baseInfo": {"name": "张三"},
                "workExperiences": [{"company": "示例公司", "title": "产品经理"}],
                "eduExperiences": [{"school": "示例大学"}],
                "projectExperiences": [],
                "jobWant": {"city": "北京"},
            },
            "resumeAnalysisModelVo": {},
            "operateButtonVo": {},
            "imInfoVo": {},
        },
    }


def _write_done_job(root: Path, index: int, platform_id: str, data: dict | None = None) -> None:
    _write_done_job_for_pack(root, "liepin-detail-p0-smoke-001", index, platform_id, data)


def _write_done_job_for_pack(
    root: Path,
    pack_id: str,
    index: int,
    platform_id: str,
    data: dict | None = None,
) -> None:
    job_dir = root / "raw" / "detail-live" / pack_id
    job_dir.mkdir(parents=True, exist_ok=True)
    detail_job_path(job_dir, index).write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_job_v1",
                "status": "done",
                "index": index,
                "platform": "liepin",
                "platform_id": platform_id,
                "user_id_encode": f"user-{platform_id}",
                "profile_url_ref": True,
                "profile_url": (
                    "https://h.liepin.com/resume/showresumedetail/"
                    f"?res_id_encode={platform_id}&ck_id=secret-token"
                ),
                "requests": [
                    {
                        "type": "detail",
                        "httpStatus": 200,
                        "contentType": "application/json",
                        "parseError": None,
                        "rawLength": 100,
                        "rawPreview": "showresumedetail ck_id=secret-token",
                        "data": data if data is not None else _detail_response(),
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_detail_dry_run_accepts_full_pack_schema(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_full_target_pack(paths.root, [_contact("res-1", 0)])
    _write_done_job_for_pack(paths.root, "detail-p0-p1-pack-001", 0, "res-1")

    result = build_detail_dry_run(paths.root, pack)

    assert result["clean"] is True
    assert result["pack_id"] == "detail-p0-p1-pack-001"
    assert result["ready_for_campaign_db_count"] == 1


def _write_privacy_job(root: Path, index: int, platform_id: str) -> None:
    job_dir = root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    job_dir.mkdir(parents=True, exist_ok=True)
    detail_job_path(job_dir, index).write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_job_v1",
                "status": "privacy_protected",
                "index": index,
                "platform_id": platform_id,
                "user_id_encode": f"user-{platform_id}",
                "profile_url": "https://h.liepin.com/resume/showresumedetail/?ck_id=secret",
                "requests": [
                    {
                        "type": "detail",
                        "httpStatus": 200,
                        "contentType": "application/json",
                        "parseError": None,
                        "rawLength": 60,
                        "data": {
                            "flag": 0,
                            "code": "11000",
                            "msg": "对方设置了隐私保护，暂不支持查看",
                            "data": {},
                        },
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_build_detail_dry_run_accepts_done_and_privacy_protected_without_database_write(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-private", 1)])
    _write_done_job(paths.root, 0, "res-1")
    _write_privacy_job(paths.root, 1, "res-private")

    result = build_detail_dry_run(paths.root, pack)

    assert result["schema"] == "liepin_detail_dry_run_v1"
    assert result["mode"] == "dry-run"
    assert result["target_count"] == 2
    assert result["ready_for_campaign_db_count"] == 1
    assert result["privacy_protected_count"] == 1
    assert result["missing_raw_count"] == 0
    assert result["failed_jobs"] == []
    assert result["capture_blockers"] == []
    assert result["apply_blockers"] == []
    assert result["clean"] is True
    assert result["no_database_write"] is True
    assert result["matches"][0]["platform_id"] == "res-1"
    assert result["matches"][0]["detail_counts"] == {"work": 1, "education": 1, "project": 0}
    assert "resumeDetailVo" in result["matches"][0]["captured_field_groups"]


def test_build_detail_dry_run_reports_missing_raw_partial_and_platform_mismatch(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(
        paths.root,
        [_contact("res-partial", 0), _contact("res-mismatch", 1), _contact("res-missing", 2)],
    )
    _write_done_job(paths.root, 0, "res-partial", data={"flag": 1, "data": {}})
    _write_done_job(paths.root, 1, "other-res")

    result = build_detail_dry_run(paths.root, pack)

    assert result["clean"] is False
    assert result["ready_for_campaign_db_count"] == 0
    assert result["missing_raw_count"] == 1
    assert result["missing_raw"][0]["platform_id"] == "res-missing"
    assert {item["reason"] for item in result["capture_blockers"]} == {
        "partial_detail",
        "platform_id_mismatch",
    }
    assert result["apply_blockers"] == []


def test_dry_run_detail_jobs_writes_sanitized_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(paths.root, [_contact("res-1", 0)])
    _write_done_job(paths.root, 0, "res-1")

    result = dry_run_detail_jobs(paths.root, pack)

    assert result["clean"] is True
    report_json = paths.reports_dir / "detail-dry-run.json"
    report_md = paths.reports_dir / "detail-dry-run.md"
    assert report_json.exists()
    assert report_md.exists()
    dumped = report_json.read_text(encoding="utf-8-sig") + report_md.read_text(encoding="utf-8")
    assert "showresumedetail" not in dumped
    assert "ck_id=" not in dumped
    assert "sk_id=" not in dumped
    assert "fk_id=" not in dumped
    assert "secret-token" not in dumped


def test_detail_dry_run_cli_prints_json_and_does_not_touch_databases(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(paths.root, [_contact("res-1", 0)])
    _write_done_job(paths.root, 0, "res-1")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_detail_dry_run",
            "--campaign-root",
            str(paths.root),
            "--target-pack",
            str(pack),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["ready_for_campaign_db_count"] == 1
    assert payload["no_database_write"] is True
    assert not (paths.root / "talent.db").exists()


def test_apply_detail_jobs_requires_confirm_and_writes_campaign_db_only(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-private", 1)])
    _write_done_job(paths.root, 0, "res-1")
    _write_privacy_job(paths.root, 1, "res-private")
    db = TalentDB(paths.root / "talent.db")
    try:
        candidate_id = db.ingest(
            {
                "name": "张**（猎聘res-1）",
                "platform_id": "res-1",
                "current_company": "示例公司",
                "current_title": "AI产品经理",
            },
            platform="liepin",
        )
        db.ingest(
            {
                "name": "李**（猎聘vate）",
                "platform_id": "res-private",
                "current_company": "示例公司",
                "current_title": "AI产品经理",
            },
            platform="liepin",
        )
    finally:
        db.close()

    with pytest.raises(ValueError, match=CONFIRM_TEXT):
        apply_detail_jobs(paths.root, pack, confirm="")

    result = apply_detail_jobs(paths.root, pack, confirm=CONFIRM_TEXT)

    assert result["schema"] == "liepin_detail_apply_v1"
    assert result["mode"] == "apply"
    assert result["matched"] == 1
    assert result["written"] == 1
    assert result["privacy_protected_count"] == 1
    assert result["no_main_db_write"] is True
    db = TalentDB(paths.root / "talent.db")
    try:
        detail = db.get_detail(candidate_id)
        candidate = db.get(candidate_id)
        assert detail is not None
        assert candidate is not None
        assert candidate.data_level == "detailed"
        assert len(detail.work_experience or ()) == 1
        assert len(detail.education_experience or ()) == 1
        assert detail.raw_data["liepin_detail_capture"]["platform_id"] == "res-1"
        dumped = json.dumps(detail.raw_data, ensure_ascii=False)
        assert "showresumedetail" not in dumped
        assert "ck_id=" not in dumped
        assert "rawPreview" not in dumped
    finally:
        db.close()
    ledger = (paths.state_dir / "import-ledger.jsonl").read_text(encoding="utf-8")
    assert '"action": "detail_apply"' in ledger
    assert '"status": "completed"' in ledger


def test_apply_detail_jobs_rejects_blockers_and_missing_campaign_db(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack = _write_target_pack(paths.root, [_contact("res-partial", 0)])
    _write_done_job(paths.root, 0, "res-partial", data={"flag": 1, "data": {}})
    db = TalentDB(paths.root / "talent.db")
    db.close()

    with pytest.raises(RuntimeError, match="detail dry-run is not clean"):
        apply_detail_jobs(paths.root, pack, confirm=CONFIRM_TEXT)

    clean_root = tmp_path / "liepin-clean-no-db"
    clean_paths = ensure_campaign(clean_root)
    clean_pack = _write_target_pack(clean_paths.root, [_contact("res-1", 0)])
    _write_done_job(clean_paths.root, 0, "res-1")
    with pytest.raises(RuntimeError, match="campaign db does not exist"):
        apply_detail_jobs(clean_paths.root, clean_pack, confirm=CONFIRM_TEXT)
