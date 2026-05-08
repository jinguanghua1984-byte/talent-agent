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


def test_exact_match_merges_and_returns_same_id(db: TalentDB):
    candidate_data = {
        "name": "Duplicate Person",
        "current_company": "Acme",
        "current_title": "Engineer",
        "city": "Shanghai",
        "education": "Bachelor",
        "skill_tags": ["Python"],
        "platform_id": "maimai-duplicate-1",
    }

    first_id = db.ingest(candidate_data, platform="maimai")
    second_id = db.ingest(
        {
            **candidate_data,
            "skill_tags": ["Python", "SQL"],
            "platform_id": "boss-duplicate-1",
        },
        platform="boss",
    )

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
    candidate = db.get(first_id)

    assert second_id == first_id
    assert count == 1
    assert candidate.skill_tags == ("Python", "SQL")
    assert len(db.get_sources(first_id)) == 2


def test_nullable_fields_matching_works(db: TalentDB):
    candidate_data = {"name": "Name Only"}

    first_id = db.ingest(candidate_data, platform="maimai")
    second_id = db.ingest(
        {
            "name": "Name Only",
            "current_company": None,
            "current_title": None,
            "city": None,
            "education": None,
        },
        platform="boss",
    )

    count = db._conn.execute(
        "SELECT COUNT(*) FROM candidates WHERE name = ?",
        (candidate_data["name"],),
    ).fetchone()[0]

    assert second_id == first_id
    assert count == 1


def test_new_candidate(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Fresh Candidate",
            "current_company": "NewCo",
            "current_title": "Designer",
            "platform_id": "fresh-1",
        },
        platform="maimai",
    )

    candidate = db.get(candidate_id)

    assert candidate is not None
    assert candidate.name == "Fresh Candidate"
    assert candidate.current_company == "NewCo"
    assert db.get_sources(candidate_id)[0].platform_id == "fresh-1"


def test_core_and_detailed_data_level(db: TalentDB):
    core_id = db.ingest(
        {"name": "Core Person", "skill_tags": ["Go"]},
        platform="maimai",
    )
    detailed_id = db.ingest(
        {
            "name": "Detailed Person",
            "work_experience": [{"company": "Acme", "title": "Engineer"}],
        },
        platform="maimai",
    )

    assert db.get(core_id).data_level == "core"
    assert db.get(detailed_id).data_level == "detailed"
    assert db.get_detail(detailed_id).work_experience == (
        {"company": "Acme", "title": "Engineer"},
    )


def test_merge_supplements_empty_fields_only(db: TalentDB):
    first_id = db.ingest(
        {
            "name": "Field Merge",
            "current_company": "Acme",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "gender": "female",
        },
        platform="maimai",
    )

    second_id = db.ingest(
        {
            "name": "Field Merge",
            "current_company": "Acme",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "gender": "male",
            "expected_salary": "50k",
        },
        platform="boss",
    )

    candidate = db.get(first_id)
    assert second_id == first_id
    assert candidate.gender == "female"
    assert candidate.expected_salary == "50k"


def test_merge_detail_does_not_overwrite_with_empty_detail(db: TalentDB):
    first_id = db.ingest(
        {
            "name": "Detail Merge",
            "current_company": "Acme",
            "current_title": "Engineer",
            "work_experience": [{"company": "Acme"}],
        },
        platform="maimai",
    )

    same_id = db.ingest(
        {
            "name": "Detail Merge",
            "current_company": "Acme",
            "current_title": "Engineer",
            "detail": {
                "work_experience": [],
                "education_experience": [{"school": "Fudan"}],
            },
        },
        platform="boss",
    )

    detail = db.get_detail(first_id)
    assert same_id == first_id
    assert detail.work_experience == ({"company": "Acme"},)
    assert detail.education_experience == ({"school": "Fudan"},)


def test_duplicate_source_profile_does_not_break_merge(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Source Stable",
            "current_company": "Acme",
            "current_title": "Engineer",
            "platform_id": "same-source",
            "profile_url": "https://example.com/old",
        },
        platform="maimai",
    )

    same_id = db.ingest(
        {
            "name": "Source Stable",
            "current_company": "Acme",
            "current_title": "Engineer",
            "platform_id": "same-source",
            "profile_url": "https://example.com/new",
        },
        platform="maimai",
    )

    sources = db.get_sources(candidate_id)
    assert same_id == candidate_id
    assert len(sources) == 1
    assert sources[0].profile_url == "https://example.com/new"


def test_batch_ingest_mixed_created_merged_errors(db: TalentDB):
    result = db.batch_ingest(
        [
            {
                "name": "Batch New",
                "current_company": "Acme",
                "current_title": "Engineer",
            },
            {
                "name": "Batch New",
                "current_company": "Acme",
                "current_title": "Engineer",
                "skill_tags": ["Python"],
            },
            {"current_company": "Broken"},
        ],
        platform="maimai",
    )

    assert result.created == 1
    assert result.merged == 1
    assert result.pending == 0
    assert result.errors == 1
    assert result.total == 2
    assert "Broken" in result.error_details[0] or "name" in result.error_details[0]


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


def test_alias_pending_merge_create(db: TalentDB):
    existing_id = db.ingest(
        {
            "name": "Alias Person",
            "current_company": "ByteDance",
            "current_title": "Product Manager",
            "city": "Beijing",
            "education": "Master",
            "platform_id": "maimai-alias-existing",
        },
        platform="maimai",
    )
    db.add_company_alias("ByteDance", "Toutiao")

    new_id = db.ingest(
        {
            "name": "Alias Person",
            "current_company": "Toutiao",
            "current_title": "Product Manager",
            "city": "Beijing",
            "education": "Master",
            "platform_id": "boss-alias-new",
        },
        platform="boss",
    )

    pending = db.pending_merges()
    candidate_count = db._conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]

    assert new_id != existing_id
    assert candidate_count == 2
    assert len(pending) == 1
    assert pending[0].existing_id == existing_id
    assert pending[0].new_data["current_company"] == "Toutiao"
    assert "_candidate_id" not in pending[0].new_data


def test_resolve_merge_approve_deletes_merges_new_candidate_and_writes_log(
    db: TalentDB,
):
    existing_id = db.ingest(
        {
            "name": "Resolve Person",
            "current_company": "ByteDance",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "platform_id": "maimai-resolve-existing",
            "skill_tags": ["Python"],
        },
        platform="maimai",
    )
    db.add_company_alias("ByteDance", "Toutiao")
    new_id = db.ingest(
        {
            "name": "Resolve Person",
            "current_company": "Toutiao",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "expected_salary": "60k",
            "platform_id": "boss-resolve-new",
            "skill_tags": ["SQL"],
        },
        platform="boss",
    )
    pending_id = db.pending_merges()[0].id

    db.resolve_merge(pending_id, "merge")

    candidate = db.get(existing_id)
    pending_row = db._conn.execute(
        "SELECT status FROM pending_merges WHERE id = ?", (pending_id,)
    ).fetchone()
    log_row = db._conn.execute(
        """
        SELECT survivor_id, merged_id, match_type
        FROM merge_log
        WHERE survivor_id = ? AND merged_id = ?
        """,
        (existing_id, new_id),
    ).fetchone()

    assert db.get(new_id) is None
    assert candidate.expected_salary == "60k"
    assert candidate.skill_tags == ("Python", "SQL")
    assert {source.platform_id for source in db.get_sources(existing_id)} == {
        "maimai-resolve-existing",
        "boss-resolve-new",
    }
    assert pending_row["status"] == "approved"
    assert dict(log_row) == {
        "survivor_id": existing_id,
        "merged_id": new_id,
        "match_type": "company_alias",
    }


def test_resolve_merge_reject_keeps_both_candidates(db: TalentDB):
    existing_id = db.ingest(
        {
            "name": "Reject Person",
            "current_company": "ByteDance",
            "current_title": "Designer",
            "city": "Shenzhen",
            "education": "Bachelor",
        },
        platform="maimai",
    )
    db.add_company_alias("ByteDance", "Toutiao")
    new_id = db.ingest(
        {
            "name": "Reject Person",
            "current_company": "Toutiao",
            "current_title": "Designer",
            "city": "Shenzhen",
            "education": "Bachelor",
        },
        platform="boss",
    )
    pending_id = db.pending_merges()[0].id

    db.resolve_merge(pending_id, "reject")

    status = db._conn.execute(
        "SELECT status FROM pending_merges WHERE id = ?", (pending_id,)
    ).fetchone()["status"]

    assert db.get(existing_id) is not None
    assert db.get(new_id) is not None
    assert status == "rejected"
    assert db.pending_merges() == []


def test_resolve_merge_invalid_action_and_pending_id(db: TalentDB):
    with pytest.raises(ValueError):
        db.resolve_merge(123, "merge")

    existing_id = db.ingest(
        {
            "name": "Invalid Action",
            "current_company": "ByteDance",
            "current_title": "Engineer",
        },
        platform="maimai",
    )
    with db._conn:
        pending_id = db._conn.execute(
            """
            INSERT INTO pending_merges(existing_id, new_data, match_fields, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (existing_id, json.dumps({"name": "Invalid Action"}), json.dumps({})),
        ).lastrowid

    with pytest.raises(ValueError):
        db.resolve_merge(pending_id, "maybe")
