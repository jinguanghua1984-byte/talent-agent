"""人才库数据模型测试。"""

from dataclasses import FrozenInstanceError

import pytest

from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
    DeleteResult,
    IngestResult,
    MatchScore,
    PageResult,
    PendingMerge,
    SearchHit,
    SortSpec,
    SourceProfile,
    VectorHit,
)


class TestCandidate:
    def test_create_minimal(self):
        candidate = Candidate(id=1, name="张三")
        assert candidate.id == 1
        assert candidate.name == "张三"
        assert candidate.gender is None
        assert candidate.skill_tags == ()
        assert candidate.data_level == "lead"

    def test_create_full(self):
        candidate = Candidate(
            id=1,
            name="张三",
            gender="女",
            age=28,
            city="北京",
            work_years=5,
            education="硕士",
            current_company="字节跳动",
            current_title="高级产品经理",
            expected_salary="30-50K",
            expected_city="北京",
            expected_title="产品总监",
            hunting_status="在职-考虑机会",
            skill_tags=("AI", "产品"),
            data_level="detailed",
            overall_score=85.0,
            score_version=3,
            created_at="2026-05-08",
            updated_at="2026-05-08",
        )
        assert candidate.current_company == "字节跳动"
        assert candidate.skill_tags == ("AI", "产品")
        assert candidate.overall_score == 85.0

    def test_frozen(self):
        candidate = Candidate(id=1, name="张三")
        with pytest.raises(FrozenInstanceError):
            candidate.name = "李四"


class TestOtherModels:
    def test_create_record_models(self):
        detail = CandidateDetail(
            candidate_id=1,
            work_experience=({"company": "字节", "title": "PM"},),
            education_experience=({"school": "北大"},),
            project_experience=({"name": "搜索平台"},),
            raw_data={"source": "maimai"},
            summary="有完整项目经验",
        )
        source = SourceProfile(
            id=10,
            candidate_id=1,
            platform="maimai",
            platform_id="abc-123",
            profile_url="https://example.com/profile/abc-123",
            raw_profile={"name": "张三"},
            fetched_at="2026-05-08T12:00:00",
        )
        vector_hit = VectorHit(
            id=1,
            similarity=0.93,
            name="张三",
            current_company="字节跳动",
            current_title="产品经理",
        )
        score = MatchScore(
            id=1,
            candidate_id=1,
            jd_id="jd-001",
            match_type="llm",
            score=91.5,
            dimensions={"技能匹配": 0.9},
            reason="技能和行业都很匹配",
            created_at="2026-05-08T13:00:00",
        )
        merge = PendingMerge(
            id=1,
            existing_id=10,
            new_data={"city": "北京"},
            match_fields={"name": "张三", "company": "字节跳动"},
            status="pending",
            created_at="2026-05-08T14:00:00",
        )

        assert detail.candidate_id == 1
        assert source.platform == "maimai"
        assert vector_hit.similarity == 0.93
        assert score.jd_id == "jd-001"
        assert merge.status == "pending"


class TestCandidateFilter:
    def test_defaults(self):
        candidate_filter = CandidateFilter()
        assert candidate_filter.companies is None
        assert candidate_filter.skills_any is None
        assert candidate_filter.updated_after is None

    def test_with_values(self):
        candidate_filter = CandidateFilter(
            companies=["字节跳动"],
            cities=["北京"],
            min_work_years=3,
            max_work_years=8,
            skills_any=["AI", "Python"],
            data_level="core",
            platforms=["maimai"],
        )
        assert candidate_filter.companies == ["字节跳动"]
        assert candidate_filter.max_work_years == 8
        assert candidate_filter.platforms == ["maimai"]


class TestIngestResult:
    def test_total(self):
        result = IngestResult(created=5, merged=2, pending=1, errors=0, error_details=[])
        assert result.created == 5
        assert result.total == 8


def test_delete_result_total_related_rows():
    result = DeleteResult(
        candidate_id=42,
        candidate_deleted=True,
        details_deleted=1,
        sources_deleted=2,
        score_events_deleted=3,
        match_scores_deleted=4,
        vectors_deleted=1,
    )

    assert result.related_rows_deleted == 11
    assert result.to_dict() == {
        "candidate_id": 42,
        "candidate_deleted": True,
        "details_deleted": 1,
        "sources_deleted": 2,
        "score_events_deleted": 3,
        "match_scores_deleted": 4,
        "vectors_deleted": 1,
        "related_rows_deleted": 11,
    }


class TestPageResult:
    def test_total_pages(self):
        page = PageResult(items=[], total=100, page=1, page_size=50)
        assert page.total_pages == 2

    def test_total_pages_with_invalid_page_size(self):
        page = PageResult(items=[], total=100, page=1, page_size=0)
        assert page.total_pages == 0


class TestSearchHit:
    def test_create(self):
        hit = SearchHit(id=1, rank=-0.5, snippet="<b>字节</b>跳动")
        assert hit.id == 1
        assert hit.rank == -0.5
        assert "字节" in hit.snippet


class TestSortSpec:
    def test_defaults(self):
        sort = SortSpec(field="overall_score")
        assert sort.field == "overall_score"
        assert sort.direction == "desc"


class TestJsonCompatibility:
    def test_candidate_list_input_normalized_to_tuple(self):
        candidate = Candidate(id=2, name="Alice", skill_tags=["AI", "Python"])
        assert candidate.skill_tags == ("AI", "Python")

    def test_candidate_roundtrip(self):
        original = Candidate(
            id=3,
            name="Bob",
            city="Shanghai",
            skill_tags=("Search", "NLP"),
            data_level="core",
            overall_score=88.5,
            score_version=2,
        )
        payload = original.to_dict()
        assert isinstance(payload["skill_tags"], list)

        restored = Candidate.from_dict(payload)
        assert restored == original

    def test_candidate_detail_list_input_normalized_to_tuple(self):
        detail = CandidateDetail(
            candidate_id=10,
            work_experience=[{"company": "A", "title": "PM"}],
            education_experience=[{"school": "B"}],
            project_experience=[{"name": "X"}],
        )
        assert detail.work_experience == ({"company": "A", "title": "PM"},)
        assert detail.education_experience == ({"school": "B"},)
        assert detail.project_experience == ({"name": "X"},)

    def test_candidate_detail_roundtrip(self):
        original = CandidateDetail(
            candidate_id=11,
            work_experience=({"company": "A", "title": "Engineer"},),
            education_experience=({"school": "C", "degree": "MS"},),
            project_experience=({"name": "Platform"},),
            raw_data={"source": "db"},
            summary="test summary",
        )
        payload = original.to_dict()
        assert isinstance(payload["work_experience"], list)
        assert isinstance(payload["education_experience"], list)
        assert isinstance(payload["project_experience"], list)

        restored = CandidateDetail.from_dict(payload)
        assert restored == original
