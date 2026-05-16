import json
from pathlib import Path

import pytest

from scripts.maimai_detail_import import CONFIRM_TEXT, apply_capture, dry_run_capture
from scripts.talent_db import TalentDB


def _write_capture(path: Path) -> None:
    payload = {
        "exportTime": "2026-05-10T00:00:00.000Z",
        "metadata": {"detail_mode": "batch_replay"},
        "detailJobs": [
            {
                "id": "166812124",
                "status": "done",
                "detail": {
                    "basic": {
                        "id": "166812124",
                        "name": "范青",
                        "company": "OpenAI",
                        "position": "AI PM",
                        "exp": [
                            {"company": "OpenAI", "position": "AI PM", "v": "2022-01至今"}
                        ],
                        "edu": [
                            {"school": "Fudan", "major": "CS", "v": "2014-09至2018-06"}
                        ],
                        "user_project": [
                            {
                                "project_name": "Agent 平台",
                                "project_role": "负责人",
                                "v": "2023-01至今",
                            }
                        ],
                    },
                    "projects": {"data": [{"project_name": "Agent 平台"}]},
                },
            },
            {
                "id": "unmatched-1",
                "status": "done",
                "detail": {
                    "basic": {
                        "id": "unmatched-1",
                        "name": "未匹配",
                        "exp": [{"company": "Nowhere", "position": "PM"}],
                    }
                },
            },
            {
                "id": "failed-1",
                "status": "failed",
                "errors": ["403"],
            },
        ],
        "details": [],
        "requests": [],
        "contacts": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_no_work_capture(path: Path) -> None:
    payload = {
        "exportTime": "2026-05-10T00:00:00.000Z",
        "metadata": {"detail_mode": "batch_replay"},
        "detailJobs": [
            {
                "id": "166812124",
                "status": "done",
                "detail": {
                    "basic": {
                        "id": "166812124",
                        "name": "鑼冮潚",
                        "company": "OpenAI",
                        "position": "AI PM",
                        "edu": [{"school": "Fudan", "major": "CS"}],
                    }
                },
            }
        ],
        "details": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_partial_direct_capture(path: Path) -> None:
    payload = {
        "metadata": {
            "export_type": "maimai_ai_infra_direct_detail_live_gate",
            "detail_mode": "direct_page_fetch",
            "status": "completed_limited",
            "partial": True,
            "total_contacts": 2,
            "completed_jobs": 1,
        },
        "detailJobs": [
            {
                "id": "166812124",
                "status": "done",
                "detail": {
                    "basic": {
                        "id": "166812124",
                        "name": "范青",
                        "company": "OpenAI",
                        "position": "AI PM",
                        "exp": [{"company": "OpenAI", "position": "AI PM", "v": "2022-01至今"}],
                        "edu": [{"school": "Fudan", "major": "CS"}],
                    }
                },
            }
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_dry_run_matches_exact_platform_id_without_modifying_db(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    candidate_id = db.ingest(
        {
            "name": "范青",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
            "profile_url": "https://maimai.cn/u/166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "capture.json"
    report_path = tmp_path / "dry-run.md"
    _write_capture(capture_path)

    result = dry_run_capture(capture_path, db_path, report_path)

    assert result["matched"] == 1
    assert result["unmatched"] == 1
    assert result["failed_jobs"] == 1
    assert result["matches"][0]["candidate_id"] == candidate_id
    assert report_path.exists()

    db = TalentDB(db_path)
    try:
        assert db.get_detail(candidate_id) is None
    finally:
        db.close()


def test_dry_run_flags_no_work_detail_as_apply_blocker(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    db.ingest(
        {
            "name": "Alice",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "capture.json"
    report_path = tmp_path / "dry-run.md"
    _write_no_work_capture(capture_path)

    result = dry_run_capture(capture_path, db_path, report_path)

    assert result["matched"] == 1
    assert result["apply_blockers"][0]["blockers"] == ["missing_work_experience"]
    assert "Apply blockers" in report_path.read_text(encoding="utf-8-sig")


def test_dry_run_blocks_partial_direct_capture(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    db.ingest(
        {
            "name": "Alice",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "partial-capture.json"
    report_path = tmp_path / "dry-run.md"
    _write_partial_direct_capture(capture_path)

    result = dry_run_capture(capture_path, db_path, report_path)

    assert result["matched"] == 1
    assert result["capture_blockers"][0]["reason"] == "partial_detail_capture"
    assert "Capture blockers" in report_path.read_text(encoding="utf-8-sig")


def test_apply_rejects_partial_direct_capture(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    candidate_id = db.ingest(
        {
            "name": "Alice",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "partial-capture.json"
    _write_partial_direct_capture(capture_path)

    with pytest.raises(RuntimeError, match="partial or incomplete"):
        apply_capture(capture_path, db_path, confirm=CONFIRM_TEXT)

    db = TalentDB(db_path)
    try:
        assert db.get(candidate_id).data_level != "detailed"
        assert db.get_detail(candidate_id) is None
    finally:
        db.close()


def test_apply_writes_only_matched_details_with_confirmation(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    candidate_id = db.ingest(
        {
            "name": "范青",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "capture.json"
    report_path = tmp_path / "apply.md"
    result_path = tmp_path / "apply.json"
    _write_capture(capture_path)

    result = apply_capture(
        capture_path,
        db_path,
        report_path=report_path,
        result_path=result_path,
        confirm="确认写入脉脉详情",
    )

    assert result["written"] == 1
    assert result["matched"] == 1
    assert result["unmatched"] == 1
    assert result_path.exists()

    db = TalentDB(db_path)
    try:
        candidate = db.get(candidate_id)
        detail = db.get_detail(candidate_id)
        assert candidate.data_level == "detailed"
        assert detail is not None
        assert detail.work_experience
        assert detail.project_experience
        capture = detail.raw_data["maimai_detail_capture"]
        assert capture["platform_id"] == "166812124"
        assert capture["capture_file"] == str(capture_path)
        assert capture["mode"] == "batch_replay"
    finally:
        db.close()


def test_apply_rolls_back_when_detail_verification_fails(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    candidate_id = db.ingest(
        {
            "name": "鑼冮潚",
            "current_company": "OldCo",
            "current_title": "PM",
            "platform_id": "166812124",
        },
        platform="maimai",
    )
    db.close()

    capture_path = tmp_path / "capture.json"
    _write_no_work_capture(capture_path)

    with pytest.raises(RuntimeError, match="detail verification failed"):
        apply_capture(capture_path, db_path, confirm=CONFIRM_TEXT)

    db = TalentDB(db_path)
    try:
        candidate = db.get(candidate_id)
        assert candidate is not None
        assert candidate.data_level != "detailed"
        assert db.get_detail(candidate_id) is None
    finally:
        db.close()


def test_apply_requires_explicit_confirmation(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    TalentDB(db_path).close()
    capture_path = tmp_path / "capture.json"
    _write_capture(capture_path)

    try:
        apply_capture(capture_path, db_path, confirm="yes")
    except ValueError as exc:
        assert "确认写入脉脉详情" in str(exc)
    else:
        raise AssertionError("apply_capture should require explicit confirmation")
