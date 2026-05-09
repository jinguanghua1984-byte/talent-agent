import json
import subprocess
import sys
from pathlib import Path

from scripts.talent_db import TalentDB
from scripts.talent_models import IngestResult
from scripts.talent_migrate import migrate_candidates


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _legacy_candidate(**overrides):
    payload = {
        "name": "Alice Chen",
        "gender": "female",
        "age": 29,
        "city": "Shanghai",
        "work_years": 6,
        "education": "Master",
        "current_company": "ByteDance",
        "current_title": "Product Manager",
        "expected_salary": "40-60K",
        "expected_city": "Shanghai",
        "expected_title": "Senior Product Manager",
        "skill_tags": ["AI", "Search"],
        "status": "open",
        "active_state": "active",
        "summary": "Strong product background.",
        "sources": [
            {
                "channel": "maimai",
                "platform_id": "maimai-alice",
                "url": "https://maimai.example/alice",
                "found_at": "2026-05-01T10:00:00",
                "enrichment_level": "detail",
            }
        ],
    }
    payload.update(overrides)
    return payload


def _read_db(db_path: Path) -> TalentDB:
    return TalentDB(db_path)


def test_migrates_all_candidates(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    _write_json(json_dir / "alice.json", _legacy_candidate())
    _write_json(
        json_dir / "bob.json",
        _legacy_candidate(
            name="Bob Li",
            current_company="Tencent",
            current_title="Backend Engineer",
            city="Beijing",
            education="Bachelor",
            sources=[{"channel": "boss", "platform_id": "boss-bob"}],
        ),
    )

    result = migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        alice_id = db.fulltext_search("Alice")[0].id
        alice = db.get(alice_id)
        assert result == IngestResult(created=2, merged=0, pending=0, errors=0)
        assert db.count() == 2
        assert alice.hunting_status == "open"
        assert db.fulltext_search("Bob")[0].id
    finally:
        db.close()


def test_migrates_sources_with_multiple_source_profiles(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    _write_json(
        json_dir / "alice.json",
        _legacy_candidate(
            sources=[
                {
                    "channel": "maimai",
                    "platform_id": "maimai-alice",
                    "url": "https://maimai.example/alice",
                    "found_at": "2026-05-01T10:00:00",
                    "enrichment_level": "detail",
                },
                {
                    "channel": "boss",
                    "platform_id": "boss-alice",
                    "url": "https://boss.example/alice",
                    "found_at": "2026-05-02T10:00:00",
                    "enrichment_level": "lead",
                },
            ]
        ),
    )

    result = migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        candidate = db.fulltext_search("Alice")[0]
        sources = db.get_sources(candidate.id)
        assert result.created == 1
        assert {(source.platform, source.platform_id) for source in sources} == {
            ("maimai", "maimai-alice"),
            ("boss", "boss-alice"),
        }
        assert sources[0].profile_url == "https://maimai.example/alice"
        assert sources[0].raw_profile["source"]["enrichment_level"] == "detail"
        assert sources[0].raw_profile["legacy_json"]["active_state"] == "active"
    finally:
        db.close()


def test_migrates_source_object_as_primary_source(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    payload = _legacy_candidate(sources=[])
    payload["_source"] = {
        "channel": "maimai",
        "platform_id": "source-object-id",
        "url": "https://maimai.example/source-object",
    }
    _write_json(json_dir / "alice.json", payload)

    result = migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        candidate_id = db.fulltext_search("Alice")[0].id
        sources = db.get_sources(candidate_id)
        assert result.created == 1
        assert [
            (source.platform, source.platform_id, source.profile_url)
            for source in sources
        ] == [("maimai", "source-object-id", "https://maimai.example/source-object")]
    finally:
        db.close()


def test_migrates_work_experience_and_detail(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    work = [{"company": "ByteDance", "title": "PM"}]
    education = [{"school": "Fudan", "degree": "Master"}]
    projects = [{"name": "Search platform"}]
    _write_json(
        json_dir / "alice.json",
        _legacy_candidate(
            work_experience=work,
            education_experience=education,
            project_experience=projects,
            raw_data={"legacy_id": "old-1"},
        ),
    )

    migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        candidate_id = db.fulltext_search("Alice")[0].id
        detail = db.get_detail(candidate_id)
        assert detail.work_experience == tuple(work)
        assert detail.education_experience == tuple(education)
        assert detail.project_experience == tuple(projects)
        assert detail.summary == "Strong product background."
        assert detail.raw_data["legacy"]["raw_data"] == {"legacy_id": "old-1"}
        assert detail.raw_data["legacy_json"]["name"] == "Alice Chen"
    finally:
        db.close()


def test_migrates_nested_detail_fields(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    nested_work = [{"company": "NestedCo", "title": "Architect"}]
    payload = _legacy_candidate()
    del payload["summary"]
    payload["detail"] = {
        "work_experience": nested_work,
        "summary": "Nested detail summary.",
        "raw_data": {"nested": True},
    }
    _write_json(json_dir / "alice.json", payload)

    migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        candidate_id = db.fulltext_search("Alice")[0].id
        detail = db.get_detail(candidate_id)
        assert detail.work_experience == tuple(nested_work)
        assert detail.summary == "Nested detail summary."
        assert detail.raw_data["legacy"]["raw_data"] == {"nested": True}
    finally:
        db.close()


def test_skips_merged_json_and_tmp_files(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    _write_json(json_dir / "alice.json", _legacy_candidate())
    _write_json(json_dir / "ignored.merged.json", _legacy_candidate(name="Merged Skip"))
    _write_json(json_dir / "ignored.tmp.json", _legacy_candidate(name="Tmp Skip"))

    result = migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        assert result.created == 1
        assert db.count() == 1
        assert db.fulltext_search("Alice")
        assert db.fulltext_search("Skip") == []
    finally:
        db.close()


def test_empty_dir_returns_empty_result(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()

    result = migrate_candidates(json_dir, tmp_path / "talent.db")

    assert result == IngestResult()


def test_nonexistent_dir_returns_empty_result(tmp_path: Path):
    result = migrate_candidates(tmp_path / "missing", tmp_path / "talent.db")

    assert result == IngestResult()


def test_invalid_json_increments_errors(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    bad_file = json_dir / "bad.json"
    bad_file.write_text("{bad json", encoding="utf-8")

    result = migrate_candidates(json_dir, tmp_path / "talent.db")

    assert result.errors == 1
    assert result.error_details
    assert "bad.json" in result.error_details[0]


def test_duplicate_json_exact_match_reports_merged(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    payload = _legacy_candidate(sources=[{"channel": "maimai", "platform_id": "same"}])
    _write_json(json_dir / "first.json", payload)
    _write_json(json_dir / "second.json", payload)

    result = migrate_candidates(json_dir, db_path)

    db = _read_db(db_path)
    try:
        assert result.created == 1
        assert result.merged == 1
        assert db.count() == 1
    finally:
        db.close()


def test_db_closes_on_exception_path(tmp_path: Path, monkeypatch):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    _write_json(json_dir / "alice.json", _legacy_candidate())
    closed = []

    class RaisingDB:
        _last_ingest_action = None

        def __init__(self, db_path):
            self.db_path = db_path

        def ingest(self, data, platform):
            raise RuntimeError("forced ingest failure")

        def close(self):
            closed.append(self.db_path)

    monkeypatch.setattr("scripts.talent_migrate.TalentDB", RaisingDB)

    result = migrate_candidates(json_dir, tmp_path / "talent.db")

    assert result.errors == 1
    assert "forced ingest failure" in result.error_details[0]
    assert closed == [tmp_path / "talent.db"]


def test_script_cli_runs_directly_from_project_root(tmp_path: Path):
    json_dir = tmp_path / "json"
    json_dir.mkdir()
    db_path = tmp_path / "talent.db"
    _write_json(json_dir / "alice.json", _legacy_candidate())

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/talent_migrate.py",
            "--json-dir",
            str(json_dir),
            "--db-path",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert (
        "Migration summary: created=1, merged=0, pending=0, errors=0"
        in completed.stdout
    )
