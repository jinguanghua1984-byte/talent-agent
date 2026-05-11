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
