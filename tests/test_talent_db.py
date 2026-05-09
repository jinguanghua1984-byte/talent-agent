import sqlite3
import json
from pathlib import Path

import pytest

from scripts.talent_db import TalentDB
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
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
    db, _ = search_db

    hits = db.fulltext_search('Alice OR "')

    assert isinstance(hits, list)


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
