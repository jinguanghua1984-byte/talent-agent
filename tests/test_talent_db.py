import sqlite3
import json
import struct
from pathlib import Path

import pytest

from scripts.talent_db import TalentDB
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
    MatchScore,
    SortSpec,
    SourceProfile,
)


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


@pytest.fixture
def search_db(db: TalentDB) -> tuple[TalentDB, dict[str, int]]:
    ids = {
        "alice": db.ingest(
            {
                "name": "Alice Chen",
                "age": 29,
                "city": "Shanghai",
                "current_company": "ByteDance",
                "current_title": "Product Manager",
                "work_years": 6,
                "education": "Master",
                "skill_tags": ["AI", "Python", "SQL"],
                "hunting_status": "open",
                "platform_id": "maimai-alice",
            },
            platform="maimai",
        ),
        "bob": db.ingest(
            {
                "name": "Bob Li",
                "age": 35,
                "city": "Beijing",
                "current_company": "Tencent",
                "current_title": "Backend Engineer",
                "work_years": 10,
                "education": "Bachelor",
                "skill_tags": ["Go", "Kubernetes"],
                "hunting_status": "passive",
                "platform_id": "boss-bob",
            },
            platform="boss",
        ),
        "cathy": db.ingest(
            {
                "name": "Cathy Wang",
                "age": 27,
                "city": "Shenzhen",
                "current_company": "Acme",
                "current_title": "Data Scientist",
                "work_years": 4,
                "education": "PhD",
                "skill_tags": ["Python", "NLP"],
                "hunting_status": "open",
                "platform_id": "linkedin-cathy",
                "work_experience": [{"company": "Acme", "title": "Data Scientist"}],
            },
            platform="linkedin",
        ),
        "dan": db.ingest(
            {
                "name": "Dan Zhao",
                "age": 31,
                "city": "Shanghai",
                "current_company": "ByteDance",
                "current_title": "ML Engineer",
                "work_years": 8,
                "education": "Master",
                "skill_tags": ["Python", "ML"],
                "hunting_status": "closed",
                "platform_id": "boss-dan",
            },
            platform="boss",
        ),
    }
    with db._conn:
        db._conn.execute(
            """
            UPDATE candidates
            SET overall_score = 91.5, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("2026-05-01T09:00:00", "2026-05-05T09:00:00", ids["alice"]),
        )
        db._conn.execute(
            """
            UPDATE candidates
            SET overall_score = 78.0, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("2026-05-02T09:00:00", "2026-05-06T09:00:00", ids["bob"]),
        )
        db._conn.execute(
            """
            UPDATE candidates
            SET overall_score = 88.0, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("2026-05-03T09:00:00", "2026-05-07T09:00:00", ids["cathy"]),
        )
        db._conn.execute(
            """
            UPDATE candidates
            SET overall_score = 96.0, created_at = ?, updated_at = ?
            WHERE id = ?
            """,
            ("2026-05-04T09:00:00", "2026-05-08T09:00:00", ids["dan"]),
        )
        db._conn.execute(
            """
            INSERT INTO source_profiles(candidate_id, platform, platform_id, raw_profile)
            VALUES (?, 'boss', 'boss-alice-extra', ?)
            """,
            (ids["alice"], json.dumps({"name": "Alice Chen"})),
        )
    return db, ids


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


def test_merge_detail_combines_non_empty_lists(db: TalentDB):
    first_id = db.ingest(
        {
            "name": "Detail Combine",
            "current_company": "Acme",
            "current_title": "Engineer",
            "work_experience": [
                {"company": "Acme", "title": "Engineer"},
            ],
            "project_experience": [{"name": "Search"}],
        },
        platform="maimai",
    )

    same_id = db.ingest(
        {
            "name": "Detail Combine",
            "current_company": "Acme",
            "current_title": "Engineer",
            "detail": {
                "work_experience": [
                    {"company": "Acme", "title": "Engineer"},
                    {"company": "Beta", "title": "Staff Engineer"},
                ],
                "project_experience": [{"name": "Ranking"}],
            },
        },
        platform="boss",
    )

    detail = db.get_detail(first_id)
    assert same_id == first_id
    assert detail.work_experience == (
        {"company": "Acme", "title": "Engineer"},
        {"company": "Beta", "title": "Staff Engineer"},
    )
    assert detail.project_experience == (
        {"name": "Search"},
        {"name": "Ranking"},
    )


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


def test_same_platform_id_merges_even_when_identity_fields_change(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Stable Source",
            "current_company": "Acme",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "platform_id": "stable-source-id",
            "skill_tags": ["Python"],
        },
        platform="maimai",
    )

    same_id = db.ingest(
        {
            "name": "Stable Source",
            "current_company": "OtherCo",
            "current_title": "Architect",
            "city": "Beijing",
            "education": "Master",
            "platform_id": "stable-source-id",
            "expected_salary": "70k",
            "skill_tags": ["SQL"],
        },
        platform="maimai",
    )

    candidate = db.get(candidate_id)
    sources = db.get_sources(candidate_id)
    assert same_id == candidate_id
    assert candidate.current_company == "Acme"
    assert candidate.current_title == "Engineer"
    assert candidate.city == "Shanghai"
    assert candidate.education == "Bachelor"
    assert candidate.expected_salary == "70k"
    assert candidate.skill_tags == ("Python", "SQL")
    assert len(sources) == 1
    assert sources[0].candidate_id == candidate_id
    assert sources[0].platform_id == "stable-source-id"


def test_missing_platform_id_exact_ingest_does_not_duplicate_source_profile(
    db: TalentDB,
):
    candidate_id = db.ingest(
        {
            "name": "No Platform Id",
            "current_company": "Acme",
            "current_title": "Engineer",
            "profile_url": "https://example.com/no-platform-id",
        },
        platform="maimai",
    )

    same_id = db.ingest(
        {
            "name": "No Platform Id",
            "current_company": "Acme",
            "current_title": "Engineer",
            "profile_url": "https://example.com/no-platform-id",
        },
        platform="maimai",
    )
    db.ingest(
        {
            "name": "No Platform Id",
            "current_company": "Acme",
            "current_title": "Engineer",
            "raw_profile": {"same": "source"},
        },
        platform="boss",
    )
    db.ingest(
        {
            "name": "No Platform Id",
            "current_company": "Acme",
            "current_title": "Engineer",
            "raw_profile": {"same": "source"},
        },
        platform="boss",
    )

    sources = db.get_sources(candidate_id)
    assert same_id == candidate_id
    assert [(source.platform, source.profile_url) for source in sources] == [
        ("maimai", "https://example.com/no-platform-id"),
        ("boss", None),
    ]


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


def test_batch_ingest_counts_pending_alias_matches(db: TalentDB):
    db.ingest(
        {
            "name": "Batch Pending",
            "current_company": "ByteDance",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
        },
        platform="maimai",
    )
    db.add_company_alias("ByteDance", "Toutiao")

    result = db.batch_ingest(
        [
            {
                "name": "Batch Pending",
                "current_company": "Toutiao",
                "current_title": "Engineer",
                "city": "Shanghai",
                "education": "Bachelor",
            }
        ],
        platform="boss",
    )

    assert result.created == 0
    assert result.merged == 0
    assert result.pending == 1
    assert result.errors == 0
    assert len(db.pending_merges()) == 1


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


def test_fulltext_search_by_name(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    hits = db.fulltext_search("Alice")

    assert [hit.id for hit in hits] == [ids["alice"]]
    assert hits[0].rank < 0
    assert "<b>Alice</b>" in hits[0].snippet


def test_fulltext_search_by_company(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    hits = db.fulltext_search("Tencent")

    assert [hit.id for hit in hits] == [ids["bob"]]
    assert "<b>Tencent</b>" in hits[0].snippet


def test_fulltext_search_by_skill(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    hits = db.fulltext_search("Kubernetes")

    assert [hit.id for hit in hits] == [ids["bob"]]
    assert "<b>Kubernetes</b>" in hits[0].snippet


def test_fulltext_search_multiple_words(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    hits = db.fulltext_search("Alice Python")

    assert [hit.id for hit in hits] == [ids["alice"]]


def test_fulltext_search_no_results(search_db: tuple[TalentDB, dict[str, int]]):
    db, _ = search_db

    assert db.fulltext_search("nonexistent") == []


def test_fulltext_search_limit(search_db: tuple[TalentDB, dict[str, int]]):
    db, _ = search_db

    hits = db.fulltext_search("Python", limit=2)

    assert len(hits) == 2


def test_fulltext_search_empty_query_returns_empty_list(db: TalentDB):
    assert db.fulltext_search("") == []
    assert db.fulltext_search("   ") == []


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_fulltext_search_rejects_invalid_limit(db: TalentDB, limit: object):
    with pytest.raises(ValueError):
        db.fulltext_search("Alice", limit=limit)


def test_fulltext_search_special_chars_do_not_raise(
    search_db: tuple[TalentDB, dict[str, int]],
):
    db, ids = search_db

    hits = db.fulltext_search('Alice OR "')

    assert [hit.id for hit in hits] == [ids["alice"]]


def test_fulltext_search_rebuilds_legacy_candidates_without_fts(tmp_path: Path):
    db_path = tmp_path / "legacy.db"
    legacy_db = TalentDB(db_path)
    try:
        candidate_id = legacy_db.ingest(
            {
                "name": "Legacy Candidate",
                "current_company": "OldSearch",
                "current_title": "Engineer",
            },
            platform="legacy",
        )
        with legacy_db._conn:
            legacy_db._conn.execute("DROP TABLE candidate_fts")
    finally:
        legacy_db.close()

    reopened_db = TalentDB(db_path)
    try:
        hits = reopened_db.fulltext_search("Legacy")
    finally:
        reopened_db.close()

    assert [hit.id for hit in hits] == [candidate_id]


def test_fulltext_search_raises_when_fts_table_is_missing(db_with_candidate):
    db, _ = db_with_candidate
    with db._conn:
        db._conn.execute("DROP TABLE candidate_fts")

    with pytest.raises(sqlite3.OperationalError):
        db.fulltext_search("Alice")


def test_vector_extension_availability_flag_and_schema(db: TalentDB):
    assert isinstance(db._vec_available, bool)

    row = db._conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table' AND name = 'candidate_vectors'
        """
    ).fetchone()

    if db._vec_available:
        assert row is not None
    else:
        assert row is None


def test_init_continues_when_sqlite_vec_load_fails(tmp_path: Path, monkeypatch):
    try:
        import sqlite_vec
    except ImportError:
        pytest.skip("sqlite-vec package is not installed")

    def fail_load(conn):
        raise sqlite3.OperationalError("forced sqlite-vec load failure")

    monkeypatch.setattr(sqlite_vec, "load", fail_load)
    db = TalentDB(tmp_path / "vec-unavailable.db")
    try:
        row = db._conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'candidate_vectors'
            """
        ).fetchone()

        assert db._vec_available is False
        assert row is None
        with pytest.raises(NotImplementedError):
            db.save_embedding(1, _embedding([1.0, 0.0, 0.0]))
        with pytest.raises(NotImplementedError):
            db.vector_search(_embedding([1.0, 0.0, 0.0]))
    finally:
        db.close()


def test_vector_search_save_and_search_self_vector_first(db: TalentDB):
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")
    alice_id = db.ingest(
        {
            "name": "Vector Alice",
            "current_company": "ByteDance",
            "current_title": "ML Engineer",
        },
        platform="maimai",
    )
    bob_id = db.ingest(
        {
            "name": "Vector Bob",
            "current_company": "Tencent",
            "current_title": "Backend Engineer",
        },
        platform="boss",
    )

    db.save_embedding(alice_id, _embedding_bytes([1.0, 0.0, 0.0]))
    db.save_embedding(bob_id, _embedding([0.0, 1.0, 0.0]))

    hits = db.vector_search(_embedding([1.0, 0.0, 0.0]), limit=2)

    assert [hit.id for hit in hits] == [alice_id, bob_id]
    assert hits[0].similarity == pytest.approx(1.0)
    assert hits[0].similarity >= hits[1].similarity
    assert hits[0].name == "Vector Alice"
    assert hits[0].current_company == "ByteDance"
    assert hits[0].current_title == "ML Engineer"


def test_save_embedding_upserts_existing_candidate_embedding(db: TalentDB):
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")
    candidate_id = db.ingest({"name": "Upsert Vector"}, platform="maimai")
    other_id = db.ingest({"name": "Other Vector"}, platform="boss")

    db.save_embedding(candidate_id, _embedding([1.0, 0.0, 0.0]))
    db.save_embedding(other_id, _embedding([0.2, 0.8, 0.0]))
    db.save_embedding(candidate_id, _embedding([0.0, 1.0, 0.0]))

    hits = db.vector_search(_embedding([0.0, 1.0, 0.0]), limit=2)
    row_count = db._conn.execute(
        "SELECT COUNT(*) FROM candidate_vectors WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()[0]

    assert hits[0].id == candidate_id
    assert row_count == 1


def test_vector_search_empty_vector_table_returns_empty_list(db: TalentDB):
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")
    db.ingest({"name": "No Vector Yet"}, platform="maimai")

    assert db.vector_search(_embedding([1.0, 0.0, 0.0]), limit=5) == []


def test_vector_search_empty_table_still_validates_query_vector(db: TalentDB):
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")

    with pytest.raises(ValueError):
        db.vector_search([1.0, 0.0, 0.0], limit=5)


@pytest.mark.parametrize("limit", [0, -1, 1.5, True])
def test_vector_search_rejects_invalid_limit(db: TalentDB, limit: object):
    with pytest.raises(ValueError):
        db.vector_search(_embedding([1.0, 0.0, 0.0]), limit=limit)


@pytest.mark.parametrize(
    ("embedding_factory", "error_type"),
    [
        (lambda: [1.0, 0.0, 0.0], ValueError),
        (lambda: _embedding([1.0, 0.0, 0.0])[:-1], ValueError),
        (lambda: _embedding([1.0, 0.0, 0.0]) + [0.0], ValueError),
        (lambda: [True, *_embedding([1.0, 0.0, 0.0])[1:]], TypeError),
        (lambda: ["1.0", *_embedding([1.0, 0.0, 0.0])[1:]], TypeError),
        (lambda: _embedding_bytes([1.0, 0.0, 0.0])[:-4], ValueError),
    ],
)
def test_vector_embedding_rejects_bad_values(
    db_with_candidate: tuple[TalentDB, int],
    embedding_factory,
    error_type: type[Exception],
):
    db, candidate_id = db_with_candidate
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")

    embedding = embedding_factory()
    with pytest.raises(error_type):
        db.save_embedding(candidate_id, embedding)
    with pytest.raises(error_type):
        db.vector_search(embedding)


def test_save_bad_embedding_after_good_embedding_preserves_existing_vector(
    db: TalentDB,
):
    if not db._vec_available:
        pytest.skip("sqlite-vec extension is not available")
    candidate_id = db.ingest({"name": "Stable Vector"}, platform="maimai")
    other_id = db.ingest({"name": "Other Stable Vector"}, platform="boss")
    good_embedding = _embedding([1.0, 0.0, 0.0])

    db.save_embedding(candidate_id, good_embedding)
    db.save_embedding(other_id, _embedding([0.0, 1.0, 0.0]))
    with pytest.raises(ValueError):
        db.save_embedding(candidate_id, [0.0, 1.0, 0.0])

    hits = db.vector_search(good_embedding, limit=2)
    row_count = db._conn.execute(
        "SELECT COUNT(*) FROM candidate_vectors WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()[0]

    assert hits[0].id == candidate_id
    assert hits[0].similarity == pytest.approx(1.0)
    assert row_count == 1


def test_vector_methods_raise_when_sqlite_vec_unavailable(db: TalentDB):
    db._vec_available = False

    with pytest.raises(NotImplementedError):
        db.save_embedding(1, _embedding([1.0, 0.0, 0.0]))
    with pytest.raises(NotImplementedError):
        db.vector_search(_embedding([1.0, 0.0, 0.0]))


def test_fulltext_search_fts_stays_synced_after_candidate_update(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Sync Candidate",
            "current_company": "OldCo",
            "current_title": "Analyst",
            "skill_tags": ["Excel"],
        },
        platform="maimai",
    )

    with db._conn:
        db._conn.execute(
            """
            UPDATE candidates
            SET current_title = ?, skill_tags = ?
            WHERE id = ?
            """,
            ("Search Architect", json.dumps(["VectorSearch"]), candidate_id),
        )

    assert db.fulltext_search("Analyst") == []
    hits = db.fulltext_search("VectorSearch")
    assert [hit.id for hit in hits] == [candidate_id]


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


def test_search_all_with_pagination(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    first_page = db.search(sort=SortSpec("name", "asc"), page=1, page_size=2)
    second_page = db.search(sort=SortSpec("name", "asc"), page=2, page_size=2)

    assert first_page.total == 4
    assert first_page.page == 1
    assert first_page.page_size == 2
    assert first_page.total_pages == 2
    assert [candidate.id for candidate in first_page.items] == [ids["alice"], ids["bob"]]
    assert [candidate.id for candidate in second_page.items] == [
        ids["cathy"],
        ids["dan"],
    ]


def test_search_filters_candidate_fields(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    result = db.search(
        CandidateFilter(
            companies=["ByteDance"],
            titles=["Product Manager"],
            cities=["Shanghai"],
            education_levels=["Master"],
            min_work_years=5,
            max_work_years=7,
            data_level="core",
            hunting_status=["open"],
            min_score=90,
            max_score=95,
            updated_after="2026-05-04T00:00:00",
        )
    )

    assert [candidate.id for candidate in result.items] == [ids["alice"]]
    assert result.total == 1


def test_search_filter_platforms_without_duplicate_candidates(
    search_db: tuple[TalentDB, dict[str, int]],
):
    db, ids = search_db

    result = db.search(
        CandidateFilter(platforms=["boss"]),
        sort=SortSpec("name", "asc"),
    )

    assert [candidate.id for candidate in result.items] == [
        ids["alice"],
        ids["bob"],
        ids["dan"],
    ]
    assert result.total == 3


def test_search_filter_skills_any_and_all(search_db: tuple[TalentDB, dict[str, int]]):
    db, ids = search_db

    any_result = db.search(
        CandidateFilter(skills_any=["NLP", "Kubernetes"]),
        sort=SortSpec("name", "asc"),
    )
    all_result = db.search(
        CandidateFilter(skills_all=["Python", "SQL"]),
        sort=SortSpec("name", "asc"),
    )

    assert [candidate.id for candidate in any_result.items] == [ids["bob"], ids["cathy"]]
    assert [candidate.id for candidate in all_result.items] == [ids["alice"]]


@pytest.mark.parametrize(
    ("sort", "expected_names"),
    [
        (SortSpec("overall_score", "desc"), ["Dan Zhao", "Alice Chen", "Cathy Wang"]),
        (SortSpec("name", "asc"), ["Alice Chen", "Bob Li", "Cathy Wang"]),
        (SortSpec("work_years", "asc"), ["Cathy Wang", "Alice Chen", "Dan Zhao"]),
    ],
)
def test_search_sort_by_score_name_work_years(
    search_db: tuple[TalentDB, dict[str, int]],
    sort: SortSpec,
    expected_names: list[str],
):
    db, _ = search_db

    result = db.search(sort=sort, page=1, page_size=3)

    assert [candidate.name for candidate in result.items] == expected_names


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sort": SortSpec("not_allowed", "asc")},
        {"sort": SortSpec("name", "sideways")},
        {"sort": SortSpec("name", "ASC")},
        {"page": 0},
        {"page_size": 0},
    ],
)
def test_search_rejects_invalid_sort_and_pagination(
    search_db: tuple[TalentDB, dict[str, int]],
    kwargs: dict[str, object],
):
    db, _ = search_db

    with pytest.raises(ValueError):
        db.search(**kwargs)


def test_count_all_and_filtered(search_db: tuple[TalentDB, dict[str, int]]):
    db, _ = search_db

    assert db.count() == 4
    assert db.count(CandidateFilter(companies=["ByteDance"], min_score=90)) == 2


def test_full_talent_db_workflow(db: TalentDB):
    batch_result = db.batch_ingest(
        [
            {
                "name": "Workflow Alice",
                "gender": "female",
                "city": "Shanghai",
                "work_years": 6,
                "education": "Master",
                "current_company": "ByteDance",
                "current_title": "Product Manager",
                "hunting_status": "open",
                "skill_tags": ["AI", "Python"],
                "platform_id": "maimai-workflow-alice-core",
                "profile_url": "https://maimai.example/workflow-alice-core",
                "work_experience": [
                    {"company": "ByteDance", "title": "Product Manager"}
                ],
                "summary": "Owns search ranking products.",
            },
            {
                "name": "Workflow Bob",
                "age": 34,
                "city": "Shanghai",
                "work_years": 9,
                "education": "Bachelor",
                "current_company": "Tencent",
                "current_title": "Backend Engineer",
                "hunting_status": "passive",
                "skill_tags": ["Go", "Kubernetes"],
                "platform_id": "maimai-workflow-bob",
            },
            {
                "name": "Workflow Cathy",
                "age": 28,
                "city": "Beijing",
                "work_years": 5,
                "education": "PhD",
                "current_company": "Acme AI",
                "current_title": "Data Scientist",
                "hunting_status": "open",
                "skill_tags": ["NLP", "Python"],
                "platform_id": "maimai-workflow-cathy",
                "detail": {
                    "project_experience": [{"name": "Dialogue Platform"}],
                    "raw_data": {"source": "maimai-cathy"},
                },
            },
            {
                "name": "Workflow Alice",
                "age": 29,
                "city": "Shanghai",
                "work_years": 6,
                "education": "Master",
                "current_company": "ByteDance",
                "current_title": "Product Manager",
                "skill_tags": ["Python", "SQL"],
                "platform_id": "maimai-workflow-alice-detail",
                "profile_url": "https://maimai.example/workflow-alice-detail",
                "detail": {
                    "education_experience": [
                        {"school": "Fudan University", "degree": "Master"}
                    ],
                    "project_experience": [{"name": "Talent Graph"}],
                    "raw_data": {"source": "maimai-alice-detail"},
                },
            },
        ],
        platform="maimai",
    )

    assert batch_result.created == 3
    assert batch_result.merged == 1
    assert batch_result.errors == 0
    assert db.count() == 3

    alice_id = db.fulltext_search("Workflow Alice")[0].id
    bob_id = db.fulltext_search("Workflow Bob")[0].id
    cathy_id = db.fulltext_search("Workflow Cathy")[0].id

    alice = db.get(alice_id)
    alice_detail = db.get_detail(alice_id)
    alice_sources = db.get_sources(alice_id)

    assert alice.age == 29
    assert alice.skill_tags == ("AI", "Python", "SQL")
    assert alice.data_level == "detailed"
    assert {
        (source.platform, source.platform_id, source.profile_url)
        for source in alice_sources
    } == {
        (
            "maimai",
            "maimai-workflow-alice-core",
            "https://maimai.example/workflow-alice-core",
        ),
        (
            "maimai",
            "maimai-workflow-alice-detail",
            "https://maimai.example/workflow-alice-detail",
        ),
    }
    assert alice_detail.work_experience == (
        {"company": "ByteDance", "title": "Product Manager"},
    )
    assert alice_detail.education_experience == (
        {"school": "Fudan University", "degree": "Master"},
    )
    assert alice_detail.project_experience == ({"name": "Talent Graph"},)
    assert alice_detail.raw_data == {"source": "maimai-alice-detail"}
    assert alice_detail.summary == "Owns search ranking products."

    db.update_overall_score(alice_id, 92.0, "workflow_test", {"stage": "overall"})
    db.update_overall_score(bob_id, 86.0, "workflow_test")
    db.update_overall_score(cathy_id, 97.0, "workflow_test")

    assert db.get(alice_id).overall_score == 92.0
    assert db.get(alice_id).score_version == 1

    db.save_match_score(
        alice_id,
        "jd-workflow",
        "coarse",
        99.0,
        dimensions={"skills": 0.99},
        reason="Broad keyword match.",
    )
    db.save_match_score(alice_id, "jd-workflow", "llm_rank", 90.0)
    db.save_match_score(alice_id, "jd-workflow", "final", 88.0)
    db.save_match_score(bob_id, "jd-workflow", "coarse", 72.0)
    db.save_match_score(bob_id, "jd-workflow", "llm_rank", 82.0)
    db.save_match_score(bob_id, "jd-workflow", "final", 93.0)
    db.save_match_score(cathy_id, "jd-workflow", "final", 84.0)

    assert {
        (score.candidate_id, score.match_type, score.score)
        for score in db.get_match_scores("jd-workflow")
    } == {
        (alice_id, "coarse", 99.0),
        (alice_id, "llm_rank", 90.0),
        (alice_id, "final", 88.0),
        (bob_id, "coarse", 72.0),
        (bob_id, "llm_rank", 82.0),
        (bob_id, "final", 93.0),
        (cathy_id, "final", 84.0),
    }

    fulltext_hits = db.fulltext_search("SQL")
    assert [hit.id for hit in fulltext_hits] == [alice_id]

    filtered = db.search(
        CandidateFilter(
            cities=["Shanghai"],
            min_work_years=5,
            skills_any=["Python", "Go"],
            min_score=80,
        ),
        sort=SortSpec("overall_score", "asc"),
    )

    assert filtered.total == 2
    assert [candidate.id for candidate in filtered.items] == [bob_id, alice_id]

    if db._vec_available:
        db.save_embedding(alice_id, _embedding([1.0, 0.0, 0.0]))
        db.save_embedding(bob_id, _embedding([0.0, 1.0, 0.0]))
        db.save_embedding(cathy_id, _embedding([0.2, 0.8, 0.0]))

        vector_hits = db.vector_search(_embedding([1.0, 0.0, 0.0]), limit=3)

        assert vector_hits[0].id == alice_id
        assert vector_hits[0].similarity == pytest.approx(1.0)

    top = db.get_top_candidates("jd-workflow", top_n=3)

    assert [candidate.id for candidate in top] == [bob_id, alice_id, cathy_id]


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
    with pytest.raises(ValueError):
        db.resolve_merge(pending_id, "merge")


def test_resolve_merge_rolls_back_when_late_step_fails(db: TalentDB, monkeypatch):
    existing_id = db.ingest(
        {
            "name": "Atomic Person",
            "current_company": "ByteDance",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "platform_id": "maimai-atomic-existing",
        },
        platform="maimai",
    )
    db.add_company_alias("ByteDance", "Toutiao")
    new_id = db.ingest(
        {
            "name": "Atomic Person",
            "current_company": "Toutiao",
            "current_title": "Engineer",
            "city": "Shanghai",
            "education": "Bachelor",
            "expected_salary": "80k",
            "platform_id": "boss-atomic-new",
            "skill_tags": ["Go"],
            "work_experience": [{"company": "Toutiao", "title": "Engineer"}],
        },
        platform="boss",
    )
    pending_id = db.pending_merges()[0].id

    def fail_move_sources(from_candidate_id, to_candidate_id):
        raise RuntimeError("forced late failure")

    monkeypatch.setattr(db, "_move_sources", fail_move_sources)

    with pytest.raises(RuntimeError, match="forced late failure"):
        db.resolve_merge(pending_id, "merge")

    pending_row = db._conn.execute(
        "SELECT status FROM pending_merges WHERE id = ?", (pending_id,)
    ).fetchone()

    assert db.get(existing_id).expected_salary is None
    assert db.get(existing_id).skill_tags == ()
    assert db.get_detail(existing_id) is None
    assert db.get(new_id) is not None
    assert pending_row["status"] == "pending"
    assert db._conn.execute("SELECT COUNT(*) FROM merge_log").fetchone()[0] == 0


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
    with pytest.raises(ValueError):
        db.resolve_merge(pending_id, "reject")


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


class TestScoring:
    def test_update_overall_score_writes_score_version_and_event(
        self, db_with_candidate: tuple[TalentDB, int]
    ):
        db, candidate_id = db_with_candidate
        with db._conn:
            db._conn.execute(
                """
                UPDATE candidates
                SET overall_score = 45.0, score_version = 2, updated_at = ?
                WHERE id = ?
                """,
                ("2026-05-01T00:00:00", candidate_id),
            )

        db.update_overall_score(
            candidate_id,
            88.5,
            "manual_review",
            {"source": "interview", "dimensions": {"skills": 90}},
        )

        candidate = db.get(candidate_id)
        event = db._conn.execute(
            """
            SELECT old_score, new_score, trigger_type, trigger_detail
            FROM score_events
            WHERE candidate_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()

        assert candidate.overall_score == 88.5
        assert candidate.score_version == 3
        assert candidate.updated_at != "2026-05-01T00:00:00"
        assert dict(event) == {
            "old_score": 45.0,
            "new_score": 88.5,
            "trigger_type": "manual_review",
            "trigger_detail": json.dumps(
                {"source": "interview", "dimensions": {"skills": 90}},
                ensure_ascii=False,
            ),
        }

    def test_update_overall_score_rejects_nonexistent_candidate(self, db: TalentDB):
        with pytest.raises(ValueError):
            db.update_overall_score(999999, 80.0, "manual_review")

    @pytest.mark.parametrize("score", [0, 100, 72.5])
    def test_update_overall_score_accepts_score_boundaries(
        self, db_with_candidate: tuple[TalentDB, int], score: float
    ):
        db, candidate_id = db_with_candidate

        db.update_overall_score(candidate_id, score, "manual_review")

        assert db.get(candidate_id).overall_score == float(score)

    @pytest.mark.parametrize(
        "score",
        [-0.01, 100.01, "90", True, float("nan"), float("inf"), float("-inf")],
    )
    def test_update_overall_score_rejects_invalid_score(
        self, db_with_candidate: tuple[TalentDB, int], score: object
    ):
        db, candidate_id = db_with_candidate

        with pytest.raises(ValueError):
            db.update_overall_score(candidate_id, score, "manual_review")

    @pytest.mark.parametrize("score", [float("nan"), float("inf"), float("-inf")])
    def test_save_match_score_rejects_non_finite_score(
        self, db_with_candidate: tuple[TalentDB, int], score: float
    ):
        db, candidate_id = db_with_candidate

        with pytest.raises(ValueError):
            db.save_match_score(candidate_id, "jd-001", "final", score)

    def test_update_overall_score_rolls_back_candidate_when_event_insert_fails(
        self, db_with_candidate: tuple[TalentDB, int]
    ):
        db, candidate_id = db_with_candidate
        with db._conn:
            db._conn.execute(
                """
                UPDATE candidates
                SET overall_score = 45.0, score_version = 2
                WHERE id = ?
                """,
                (candidate_id,),
            )
            db._conn.execute(
                """
                CREATE TRIGGER fail_score_events_insert
                BEFORE INSERT ON score_events
                BEGIN
                    SELECT RAISE(ABORT, 'forced score event failure');
                END
                """
            )

        with pytest.raises(sqlite3.IntegrityError, match="forced score event failure"):
            db.update_overall_score(candidate_id, 88.5, "manual_review")

        candidate = db.get(candidate_id)
        event_count = db._conn.execute(
            "SELECT COUNT(*) FROM score_events WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()[0]

        assert candidate.overall_score == 45.0
        assert candidate.score_version == 2
        assert event_count == 0

    def test_save_match_score_and_get_match_scores_roundtrip(
        self, db_with_candidate: tuple[TalentDB, int]
    ):
        db, candidate_id = db_with_candidate

        db.save_match_score(
            candidate_id,
            "jd-001",
            "coarse",
            76.5,
            dimensions={"skill": 0.8, "industry": {"score": 0.7}},
            reason="Skill coverage is strong.",
        )

        scores = db.get_match_scores("jd-001")

        assert len(scores) == 1
        assert isinstance(scores[0], MatchScore)
        assert scores[0].candidate_id == candidate_id
        assert scores[0].jd_id == "jd-001"
        assert scores[0].match_type == "coarse"
        assert scores[0].score == 76.5
        assert scores[0].dimensions == {"skill": 0.8, "industry": {"score": 0.7}}
        assert scores[0].reason == "Skill coverage is strong."
        assert scores[0].created_at

    def test_save_match_score_upserts_same_candidate_jd_and_type(
        self, db_with_candidate: tuple[TalentDB, int]
    ):
        db, candidate_id = db_with_candidate

        db.save_match_score(candidate_id, "jd-001", "final", 60.0, reason="old")
        db.save_match_score(
            candidate_id,
            "jd-001",
            "final",
            91.0,
            dimensions={"final": 0.91},
            reason="new",
        )

        scores = db.get_match_scores("jd-001", "final")
        row_count = db._conn.execute(
            """
            SELECT COUNT(*)
            FROM match_scores
            WHERE candidate_id = ? AND jd_id = ? AND match_type = ?
            """,
            (candidate_id, "jd-001", "final"),
        ).fetchone()[0]

        assert row_count == 1
        assert len(scores) == 1
        assert scores[0].score == 91.0
        assert scores[0].dimensions == {"final": 0.91}
        assert scores[0].reason == "new"

    def test_save_match_score_upsert_preserves_created_at(
        self, db_with_candidate: tuple[TalentDB, int]
    ):
        db, candidate_id = db_with_candidate
        original_created_at = "2026-05-01T00:00:00"

        db.save_match_score(candidate_id, "jd-001", "final", 60.0, reason="old")
        with db._conn:
            db._conn.execute(
                """
                UPDATE match_scores
                SET created_at = ?
                WHERE candidate_id = ? AND jd_id = ? AND match_type = ?
                """,
                (original_created_at, candidate_id, "jd-001", "final"),
            )
        db.save_match_score(
            candidate_id,
            "jd-001",
            "final",
            91.0,
            dimensions={"final": 0.91},
            reason="new",
        )

        score = db.get_match_scores("jd-001", "final")[0]

        assert score.created_at == original_created_at
        assert score.score == 91.0
        assert score.dimensions == {"final": 0.91}
        assert score.reason == "new"

    def test_get_match_scores_filters_by_match_type_and_orders_by_score(
        self, db: TalentDB
    ):
        low_id = db.ingest({"name": "Low Score"}, platform="boss")
        high_id = db.ingest({"name": "High Score"}, platform="boss")

        db.save_match_score(low_id, "jd-001", "final", 70.0)
        db.save_match_score(high_id, "jd-001", "final", 95.0)
        db.save_match_score(high_id, "jd-001", "coarse", 50.0)

        final_scores = db.get_match_scores("jd-001", "final")
        all_scores = db.get_match_scores("jd-001")

        assert [score.candidate_id for score in final_scores] == [high_id, low_id]
        assert {score.match_type for score in final_scores} == {"final"}
        assert [score.score for score in all_scores] == [95.0, 70.0, 50.0]

    def test_get_top_candidates_only_uses_final_scores_ordered_and_limited(
        self, db: TalentDB
    ):
        a_id = db.ingest({"name": "Candidate A"}, platform="boss")
        b_id = db.ingest({"name": "Candidate B"}, platform="boss")
        c_id = db.ingest({"name": "Candidate C"}, platform="boss")

        db.save_match_score(a_id, "jd-001", "final", 80.0)
        db.save_match_score(b_id, "jd-001", "final", 97.0)
        db.save_match_score(c_id, "jd-001", "final", 90.0)
        db.save_match_score(a_id, "jd-001", "coarse", 99.0)

        top = db.get_top_candidates("jd-001", top_n=2)

        assert [candidate.id for candidate in top] == [b_id, c_id]
        assert all(isinstance(candidate, Candidate) for candidate in top)

    def test_get_top_candidates_returns_empty_without_final_scores(self, db: TalentDB):
        candidate_id = db.ingest({"name": "Coarse Only"}, platform="boss")
        db.save_match_score(candidate_id, "jd-001", "coarse", 99.0)
        db.save_match_score(candidate_id, "jd-001", "llm", 98.0)

        assert db.get_top_candidates("jd-001") == []

    def test_save_match_score_rejects_nonexistent_candidate(self, db: TalentDB):
        with pytest.raises(ValueError):
            db.save_match_score(999999, "jd-001", "final", 90.0)

    @pytest.mark.parametrize(
        ("method_name", "args"),
        [
            ("save_match_score", ("candidate", "", "final", 90.0)),
            ("save_match_score", ("candidate", "   ", "final", 90.0)),
            ("save_match_score", ("candidate", "jd-001", "", 90.0)),
            ("save_match_score", ("candidate", "jd-001", "   ", 90.0)),
            ("get_match_scores", ("",)),
            ("get_match_scores", ("jd-001", "")),
            ("get_top_candidates", ("",)),
            ("get_top_candidates", ("jd-001", 0)),
            ("get_top_candidates", ("jd-001", -1)),
            ("get_top_candidates", ("jd-001", True)),
        ],
    )
    def test_scoring_methods_reject_invalid_inputs(
        self,
        db_with_candidate: tuple[TalentDB, int],
        method_name: str,
        args: tuple[object, ...],
    ):
        db, candidate_id = db_with_candidate
        normalized_args = tuple(
            candidate_id if arg == "candidate" else arg for arg in args
        )

        with pytest.raises(ValueError):
            getattr(db, method_name)(*normalized_args)


def _embedding(prefix: list[float]) -> list[float]:
    return [*prefix, *([0.0] * (384 - len(prefix)))]


def _embedding_bytes(prefix: list[float]) -> bytes:
    return struct.pack("<384f", *_embedding(prefix))
