"""LLM 精排模块测试"""

import json
from pathlib import Path

import pytest

from scripts.llm_ranker import (
    RankScore,
    rank_single_batch,
    rank_candidates,
    load_or_rank,
    calibration_round,
    build_rank_prompt,
    parse_rank_response,
)


SAMPLE_JD_TEXT = "AI产品经理，5年以上经验，Agent平台方向"

SAMPLE_CANDIDATES = [
    {
        "id": "c1", "name": "张三",
        "skill_tags": ["AI", "Agent", "产品"],
        "current_title": "AI产品总监",
        "current_company": "字节跳动",
        "work_experience": [
            {"company": "字节跳动", "title": "AI产品", "description": "负责Agent平台产品"},
        ],
        "education": "硕士", "work_years": 8,
        "_desc_raw": "5年AI产品经验",
    },
    {
        "id": "c2", "name": "李四",
        "skill_tags": ["SQL", "Excel"],
        "current_title": "数据分析师",
        "current_company": "某公司",
        "work_experience": [],
        "education": "本科", "work_years": 3,
    },
]


class TestBuildRankPrompt:
    def test_includes_jd(self):
        prompt = build_rank_prompt(SAMPLE_JD_TEXT, SAMPLE_CANDIDATES)
        assert "AI产品经理" in prompt

    def test_includes_candidates(self):
        prompt = build_rank_prompt(SAMPLE_JD_TEXT, SAMPLE_CANDIDATES)
        assert "张三" in prompt
        assert "李四" in prompt

    def test_truncates_long_descriptions(self):
        long_candidate = {
            "id": "c3", "name": "王五",
            "skill_tags": [],
            "current_title": "工程师",
            "current_company": "某公司",
            "work_experience": [
                {"company": "A", "title": "工程师", "description": "工作描述 " * 200},
            ],
            "_desc_raw": "长描述 " * 500,
        }
        prompt = build_rank_prompt(SAMPLE_JD_TEXT, [long_candidate])
        assert len(prompt) < 10000


class TestParseRankResponse:
    def test_valid_json(self):
        response = json.dumps([
            {"candidate_id": "c1", "total_score": 85, "维度分": {}, "排序理由": "匹配", "差距分析": ""},
            {"candidate_id": "c2", "total_score": 40, "维度分": {}, "排序理由": "不匹配", "差距分析": ""},
        ])
        results = parse_rank_response(response, ["c1", "c2"])
        assert len(results) == 2
        assert results[0].candidate_id == "c1"
        assert results[0].total_score == 85

    def test_missing_candidate_skipped(self):
        response = json.dumps([
            {"candidate_id": "c1", "total_score": 85, "维度分": {}, "排序理由": "", "差距分析": ""},
        ])
        results = parse_rank_response(response, ["c1", "c2"])
        assert len(results) == 1
        assert results[0].candidate_id == "c1"

    def test_score_clamped(self):
        response = json.dumps([
            {"candidate_id": "c1", "total_score": 150, "维度分": {}, "排序理由": "", "差距分析": ""},
        ])
        results = parse_rank_response(response, ["c1"])
        assert results[0].total_score == 100


class TestRankSingleBatch:
    def test_ranks_batch(self, mocker):
        mock_client = mocker.MagicMock()
        response_data = [
            {"candidate_id": "c1", "total_score": 85,
             "维度分": {"岗位匹配度": 25, "技能覆盖率": 22, "经验深度": 18, "行业背景": 12, "稳定性": 8},
             "排序理由": "AI产品经验丰富", "差距分析": ""},
        ]
        mock_client.messages.create.return_value.content = [
            mocker.MagicMock(text=json.dumps(response_data))
        ]
        results = rank_single_batch(
            mock_client, SAMPLE_JD_TEXT, SAMPLE_CANDIDATES, model="test"
        )
        assert len(results) == 1
        assert results[0].candidate_id == "c1"

    def test_ranks_batch_passes_route_metadata(self, mocker):
        response_data = [
            {
                "candidate_id": "c1",
                "total_score": 85,
                "维度分": {},
                "排序理由": "AI产品经验丰富",
                "差距分析": "",
            },
        ]
        llm_call = mocker.patch(
            "scripts.llm_ranker.call_llm_with_retry",
            return_value=json.dumps(response_data),
        )

        results = rank_single_batch(
            mocker.MagicMock(), SAMPLE_JD_TEXT, SAMPLE_CANDIDATES, model="model-x"
        )

        assert len(results) == 1
        assert llm_call.call_args.kwargs["workflow"] == "jd-talent-delivery"
        assert llm_call.call_args.kwargs["stage"] == "detailed-rank"
        assert llm_call.call_args.kwargs["max_tokens"] == 16000


class TestCalibrationRound:
    def test_calibrates_top_candidates(self, mocker):
        calibration_response = json.dumps([
            {"candidate_id": "c1", "total_score": 90, "维度分": {}, "排序理由": "", "差距分析": ""},
            {"candidate_id": "c2", "total_score": 82, "维度分": {}, "排序理由": "", "差距分析": ""},
            {"candidate_id": "c3", "total_score": 70, "维度分": {}, "排序理由": "", "差距分析": ""},
        ])
        mocker.patch(
            "scripts.llm_ranker.call_llm_with_retry",
            return_value=calibration_response,
        )
        ranked = [
            RankScore(candidate_id="c1", total_score=85, dimensions={}, reason="r1", gap="g1"),
            RankScore(candidate_id="c2", total_score=80, dimensions={}, reason="r2", gap="g2"),
            RankScore(candidate_id="c3", total_score=75, dimensions={}, reason="r3", gap="g3"),
        ]
        extra_candidate = {
            "id": "c3", "name": "王五",
            "skill_tags": ["AI"],
            "current_title": "产品经理",
            "current_company": "腾讯",
            "work_experience": [],
            "education": "硕士", "work_years": 6,
        }
        candidates_map = {
            "c1": SAMPLE_CANDIDATES[0],
            "c2": SAMPLE_CANDIDATES[1],
            "c3": extra_candidate,
        }
        results = calibration_round(
            mocker.MagicMock(), SAMPLE_JD_TEXT, ranked, candidates_map, model="test"
        )
        assert len(results) == 3
        assert results[0].candidate_id == "c1"
        assert results[0].total_score == 90

    def test_calibration_passes_route_metadata(self, mocker):
        calibration_response = json.dumps([
            {"candidate_id": "c1", "total_score": 90, "维度分": {}, "排序理由": "", "差距分析": ""},
            {"candidate_id": "c2", "total_score": 82, "维度分": {}, "排序理由": "", "差距分析": ""},
            {"candidate_id": "c3", "total_score": 70, "维度分": {}, "排序理由": "", "差距分析": ""},
        ])
        llm_call = mocker.patch(
            "scripts.llm_ranker.call_llm_with_retry",
            return_value=calibration_response,
        )
        ranked = [
            RankScore(candidate_id="c1", total_score=85, dimensions={}, reason="r1", gap="g1"),
            RankScore(candidate_id="c2", total_score=80, dimensions={}, reason="r2", gap="g2"),
            RankScore(candidate_id="c3", total_score=75, dimensions={}, reason="r3", gap="g3"),
        ]
        extra_candidate = {
            "id": "c3",
            "name": "王五",
            "skill_tags": ["AI"],
            "current_title": "产品经理",
            "current_company": "腾讯",
            "work_experience": [],
            "education": "硕士",
            "work_years": 6,
        }
        candidates_map = {
            "c1": SAMPLE_CANDIDATES[0],
            "c2": SAMPLE_CANDIDATES[1],
            "c3": extra_candidate,
        }

        results = calibration_round(
            mocker.MagicMock(), SAMPLE_JD_TEXT, ranked, candidates_map, model="model-x"
        )

        assert len(results) == 3
        assert llm_call.call_args.kwargs["workflow"] == "jd-talent-delivery"
        assert llm_call.call_args.kwargs["stage"] == "calibration-rank"
        assert llm_call.call_args.kwargs["max_tokens"] == 16000


class TestLoadOrRank:
    def test_uses_cache(self, tmp_path):
        cache_data = {
            "candidate_id": "c1",
            "total_score": 85,
            "dimensions": {},
            "reason": "cached",
            "gap": "",
        }
        rank_dir = tmp_path / "rank"
        rank_dir.mkdir(parents=True, exist_ok=True)
        cache_file = rank_dir / "c1.json"
        cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

        result = load_or_rank("c1", SAMPLE_CANDIDATES[0], SAMPLE_JD_TEXT, tmp_path)
        assert result is not None
        assert result.reason == "cached"
