import sqlite3
import json
from pathlib import Path

import pytest

from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, SourceProfile


@pytest.fixture
def db(tmp_path: Path):
    db = TalentDB(tmp_path / "nested" / "talent.db")
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def db_with_candidate(db: TalentDB) -> tuple[TalentDB, int]:
    candidate_id = db.ingest(
        {
            "name": "Alice Chen",
            "gender": "female",
            "age": 29,
            "city": "Shanghai",
            "current_company": "ByteDance",
            "current_title": "Product Manager",
            "work_years": 6,
            "education": "Master",
            "skill_tags": ["AI", "Python"],
            "hunting_status": "open",
            "platform_id": "maimai-1",
            "profile_url": "https://example.com/alice",
        },
        platform="maimai",
    )
    return db, candidate_id


def test_creates_db_file(tmp_path: Path):
    db_path = tmp_path / "data" / "talent.db"
    db = TalentDB(db_path)
    try:
        assert db_path.exists()
    finally:
        db.close()


def test_creates_all_core_tables(db: TalentDB):
    conn = sqlite3.connect(str(db._db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        conn.close()

    expected = {
        "candidates",
        "candidate_details",
        "source_profiles",
        "score_events",
        "match_scores",
        "merge_log",
        "pending_merges",
        "company_aliases",
        "candidate_fts",
    }
    assert expected.issubset(tables)


def test_init_is_idempotent(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db1 = TalentDB(db_path)
    db1.close()

    db2 = TalentDB(db_path)
    db2.close()

    assert db_path.exists()


def test_minimal_ingest_rejects_duplicate_identity_with_missing_optional_fields(
    db: TalentDB,
):
    candidate_data = {
        "name": "Duplicate Person",
        "current_company": "Acme",
        "current_title": "Engineer",
    }

    db.ingest(candidate_data, platform="maimai")

    with pytest.raises(sqlite3.IntegrityError):
        db.ingest(candidate_data, platform="boss")

    count = db._conn.execute(
        """
        SELECT COUNT(*)
        FROM candidates
        WHERE name = ? AND current_company = ? AND current_title = ?
        """,
        (
            candidate_data["name"],
            candidate_data["current_company"],
            candidate_data["current_title"],
        ),
    ).fetchone()[0]
    assert count == 1


def test_fts_trigger_indexes_ingested_candidate(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Searchable Candidate",
            "city": "Shenzhen",
            "current_company": "VectorWorks",
            "current_title": "ML Engineer",
            "skill_tags": ["ranking", "retrieval"],
        },
        platform="maimai",
    )

    row = db._conn.execute(
        """
        SELECT rowid
        FROM candidate_fts
        WHERE candidate_fts MATCH ?
        """,
        ("Searchable",),
    ).fetchone()

    assert row is not None
    assert row["rowid"] == candidate_id


def test_get_existing(db_with_candidate: tuple[TalentDB, int]):
    db, candidate_id = db_with_candidate

    candidate = db.get(candidate_id)

    assert isinstance(candidate, Candidate)
    assert candidate.name == "Alice Chen"
    assert candidate.current_company == "ByteDance"
    assert candidate.skill_tags == ("AI", "Python")


def test_get_nonexistent(db: TalentDB):
    assert db.get(999999) is None


def test_get_detail_after_enrich(db_with_candidate: tuple[TalentDB, int]):
    db, candidate_id = db_with_candidate

    db.enrich(
        candidate_id,
        {
            "work_experience": [{"company": "ByteDance", "title": "PM"}],
            "education_experience": [{"school": "Fudan"}],
            "project_experience": [{"name": "Search"}],
            "raw_data": {"source": "fixture"},
            "summary": "Strong product profile.",
        },
    )

    detail = db.get_detail(candidate_id)
    assert isinstance(detail, CandidateDetail)
    assert detail.candidate_id == candidate_id
    assert detail.work_experience == ({"company": "ByteDance", "title": "PM"},)
    assert detail.education_experience == ({"school": "Fudan"},)
    assert detail.project_experience == ({"name": "Search"},)
    assert detail.raw_data == {"source": "fixture"}
    assert detail.summary == "Strong product profile."
    assert db.get(candidate_id).data_level == "detailed"


def test_get_detail_nonexistent(db: TalentDB):
    assert db.get_detail(999999) is None


def test_get_sources_existing(db_with_candidate: tuple[TalentDB, int]):
    db, candidate_id = db_with_candidate

    sources = db.get_sources(candidate_id)

    assert len(sources) == 1
    assert isinstance(sources[0], SourceProfile)
    assert sources[0].platform == "maimai"
    assert sources[0].platform_id == "maimai-1"
    assert sources[0].raw_profile["name"] == "Alice Chen"


def test_get_sources_empty(db: TalentDB):
    assert db.get_sources(999999) == []


def test_add_company_alias_and_pending_merges_empty(db: TalentDB):
    db.add_company_alias("ByteDance", "Toutiao")

    row = db._conn.execute(
        """
        SELECT canonical_name, alias
        FROM company_aliases
        WHERE canonical_name = ? AND alias = ?
        """,
        ("ByteDance", "Toutiao"),
    ).fetchone()

    assert dict(row) == {"canonical_name": "ByteDance", "alias": "Toutiao"}
    assert db.pending_merges() == []


def test_pending_merges_returns_pending_records_only(db: TalentDB):
    existing_id = db.ingest(
        {
            "name": "Bob Li",
            "city": "Beijing",
            "current_company": "Acme",
            "current_title": "Engineer",
            "platform_id": "maimai-2",
        },
        platform="maimai",
    )
    pending_new_data = {
        "name": "Robert Li",
        "current_company": "Acme",
        "current_title": "Senior Engineer",
    }
    pending_match_fields = {"name": "similar", "current_company": "exact"}
    rejected_new_data = {
        "name": "Rejected Candidate",
        "current_company": "Other",
    }

    with db._conn:
        pending_id = db._conn.execute(
            """
            INSERT INTO pending_merges(existing_id, new_data, match_fields, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (
                existing_id,
                json.dumps(pending_new_data),
                json.dumps(pending_match_fields),
            ),
        ).lastrowid
        db._conn.execute(
            """
            INSERT INTO pending_merges(existing_id, new_data, match_fields, status)
            VALUES (?, ?, ?, 'rejected')
            """,
            (
                existing_id,
                json.dumps(rejected_new_data),
                json.dumps({"name": "different"}),
            ),
        )

    pending_merges = db.pending_merges()

    assert len(pending_merges) == 1
    pending_merge = pending_merges[0]
    assert pending_merge.id == pending_id
    assert pending_merge.existing_id == existing_id
    assert pending_merge.new_data == pending_new_data
    assert pending_merge.match_fields == pending_match_fields
    assert pending_merge.status == "pending"
    assert pending_merge.created_at
