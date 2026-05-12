import json
from pathlib import Path

from scripts.talent_db import TalentDB
from scripts.talent_library import main


def _seed_db(path: Path) -> int:
    db = TalentDB(path)
    try:
        return db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "166812124",
                "profile_url": "https://maimai.cn/profile/detail?dstu=166812124&trackable_token=token-alice",
            },
            platform="maimai",
        )
    finally:
        db.close()


def test_detail_entry_generates_targets_from_ids(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id = _seed_db(db_path)
    out_path = tmp_path / "targets.json"

    exit_code = main([
        "detail",
        "--ids",
        str(candidate_id),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["metadata"]["entry"] == "talent-library detail"
    assert data["contacts"][0]["id"] == "166812124"
    assert data["contacts"][0]["trackable_token"] == "token-alice"


def test_detail_entry_generates_targets_from_top10_file(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id = _seed_db(db_path)
    top10_path = tmp_path / "top10.json"
    out_path = tmp_path / "targets.json"
    top10_path.write_text(
        json.dumps({"top10": [{"candidate_id": candidate_id, "name": "Alice"}]}),
        encoding="utf-8",
    )

    exit_code = main([
        "detail",
        "--top10-file",
        str(top10_path),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    assert exit_code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["metadata"]["source_file"] == str(top10_path)
    assert data["metadata"]["total_contacts"] == 1


def test_detail_entry_requires_one_target_source(tmp_path: Path):
    out_path = tmp_path / "targets.json"

    try:
        main(["detail", "--out", str(out_path)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("detail entry should require ids or top10 file")


def _write_capture(path: Path, contacts: list[dict]) -> None:
    path.write_text(
        json.dumps({"contacts": contacts, "metadata": {"export_type": "full"}}),
        encoding="utf-8",
    )


def _maimai_contact(**overrides):
    payload = {
        "id": 166812124,
        "name": "Alice",
        "company": "Acme",
        "position": "AI PM",
        "city": "Shanghai",
        "gender_str": 2,
        "hunting_status": 5,
        "job_preferences": {
            "regions": ["Shanghai", "Beijing"],
            "positions": ["AI Product Lead"],
            "salary": "50k-70k/月",
        },
        "detail_url": (
            "https://maimai.cn/profile/detail?dstu=166812124&"
            "trackable_token=token-alice"
        ),
        "trackable_token": "token-alice",
    }
    payload.update(overrides)
    return payload


def test_import_entry_dry_run_dedupes_contacts_without_writing_db(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    out_path = tmp_path / "import-report.md"
    _write_capture(first, [_maimai_contact()])
    _write_capture(second, [_maimai_contact(position="AI PM Updated")])

    exit_code = main([
        "import",
        "--input",
        str(first),
        "--input",
        str(second),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
    ])

    db = TalentDB(db_path)
    try:
        assert exit_code == 0
        assert db.count() == 0
    finally:
        db.close()
    data = json.loads(out_path.with_suffix(".json").read_text(encoding="utf-8-sig"))
    assert data["mode"] == "dry-run"
    assert data["raw_contacts"] == 2
    assert data["unique_contacts"] == 1
    assert data["duplicates_skipped"] == 1
    assert data["result"]["created"] == 1


def test_import_entry_apply_uses_batch_ingest_with_normalized_maimai_contacts(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    capture = tmp_path / "capture.json"
    out_path = tmp_path / "import-report.md"
    _write_capture(capture, [_maimai_contact()])

    exit_code = main([
        "import",
        "--input",
        str(capture),
        "--db",
        str(db_path),
        "--out",
        str(out_path),
        "--apply",
        "--confirm",
        "确认导入人才",
    ])

    db = TalentDB(db_path)
    try:
        candidate = db.fulltext_search("Alice")[0]
        stored = db.get(candidate.id)
        sources = db.get_sources(candidate.id)
        assert exit_code == 0
        assert db.count() == 1
        assert stored.hunting_status == "在职-看机会"
        assert json.loads(stored.expected_city) == ["Shanghai", "Beijing"]
        assert sources[0].platform == "maimai"
        assert sources[0].platform_id == "166812124"
        assert sources[0].raw_profile["maimai_contact"]["trackable_token"] == "token-alice"
    finally:
        db.close()
