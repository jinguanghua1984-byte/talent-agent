"""粗筛模块测试"""

import pytest

from scripts.coarse_screener import (
    CoarseScore,
    score_candidate_coarse,
    screen_candidates,
    check_signal_quality,
    DataQualityWarning,
)
from scripts.jd_analyzer import JDAnalysis


SAMPLE_ANALYSIS = JDAnalysis(
    core_skills=["agent", "ai平台", "rag"],
    supplement_skills=["python", "产品管理"],
    position_type="AI产品经理",
    experience_range=(5, 10),
    education_requirement="本科以上",
    industry_preference=["AI", "互联网"],
    exclusion_criteria=["纯算法", "数据分析"],
    raw_jd="JD text",
    jd_hash="hash",
)

SAMPLE_CANDIDATE_GOOD = {
    "id": "boss-abc123",
    "name": "张三",
    "skill_tags": ["AI", "Agent", "RAG", "大模型", "产品"],
    "current_title": "AI产品总监",
    "current_company": "字节跳动",
    "work_experience": [
        {"company": "字节跳动", "title": "AI产品", "description": "负责Agent平台"},
        {"company": "阿里巴巴", "title": "产品经理", "description": "大模型应用"},
    ],
    "education": "硕士",
    "work_years": 8,
    "_desc_raw": "5年AI产品经验，主导Agent平台从0到1",
}

SAMPLE_CANDIDATE_BAD = {
    "id": "boss-xyz789",
    "name": "李四",
    "skill_tags": ["数据分析", "SQL"],
    "current_title": "数据分析师",
    "current_company": "某传统公司",
    "work_experience": [],
    "education": "本科",
    "work_years": 3,
}


class TestScoreCandidateCoarse:
    def test_good_candidate_high_score(self):
        score = score_candidate_coarse(SAMPLE_CANDIDATE_GOOD, SAMPLE_ANALYSIS)
        assert score.total_score > 10
        assert "agent" in score.skill_hits

    def test_bad_candidate_low_score(self):
        score = score_candidate_coarse(SAMPLE_CANDIDATE_BAD, SAMPLE_ANALYSIS)
        assert score.total_score < 30

    def test_exclusion_penalty(self):
        candidate = {
            "id": "c1",
            "name": "纯算法",
            "skill_tags": ["算法", "机器学习"],
            "current_title": "算法工程师",
            "current_company": "某公司",
            "work_experience": [{"company": "某公司", "title": "算法", "description": "纯算法研究"}],
        }
        score = score_candidate_coarse(candidate, SAMPLE_ANALYSIS)
        assert len(score.exclusion_hits) > 0

    def test_company_bonus(self):
        score = score_candidate_coarse(SAMPLE_CANDIDATE_GOOD, SAMPLE_ANALYSIS)
        assert len(score.company_matches) > 0

    def test_insufficient_data_flag(self):
        candidate = {"id": "c1", "name": "空数据", "skill_tags": ["AI"]}
        score = score_candidate_coarse(candidate, SAMPLE_ANALYSIS)
        assert score.data_quality == "insufficient_data"


class TestScreenCandidates:
    def test_screen_returns_top_k(self):
        # 40 个候选人 (>30)，coarse_limit=1 应只返回 Top 1
        candidates = [SAMPLE_CANDIDATE_GOOD, SAMPLE_CANDIDATE_BAD]
        candidates += [{"id": f"c{i}", "name": f"n{i}", "skill_tags": []} for i in range(38)]
        results = screen_candidates(candidates, SAMPLE_ANALYSIS, coarse_limit=1)
        assert len(results) == 1
        assert results[0].candidate_id == "boss-abc123"

    def test_screen_all_when_fewer_than_limit(self):
        candidates = [SAMPLE_CANDIDATE_BAD]
        results = screen_candidates(candidates, SAMPLE_ANALYSIS, coarse_limit=50)
        assert len(results) == 1

    def test_screen_preserves_all_when_under_30(self):
        candidates = [{"id": f"c{i}", "name": f"n{i}", "skill_tags": []} for i in range(20)]
        results = screen_candidates(candidates, SAMPLE_ANALYSIS, coarse_limit=50)
        assert len(results) == 20


class TestCheckSignalQuality:
    def test_warns_when_most_excluded(self):
        scores = [
            CoarseScore(candidate_id=f"c{i}", total_score=10,
                        skill_hits=[], exclusion_hits=["纯算法"],
                        company_matches=[], data_quality="ok")
            for i in range(8)
        ]
        scores.append(CoarseScore(
            candidate_id="good", total_score=80,
            skill_hits=["agent"], exclusion_hits=[],
            company_matches=[], data_quality="ok",
        ))
        warnings = check_signal_quality(scores)
        assert any(w.severity == "warning" for w in warnings)

    def test_no_warning_when_few_excluded(self):
        scores = [
            CoarseScore(candidate_id=f"c{i}", total_score=50,
                        skill_hits=["ai"], exclusion_hits=[],
                        company_matches=[], data_quality="ok")
            for i in range(10)
        ]
        warnings = check_signal_quality(scores)
        assert len(warnings) == 0
