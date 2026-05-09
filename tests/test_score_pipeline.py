"""Pipeline 编排入口测试"""

import json
import types
from pathlib import Path

import pytest

from scripts.score_pipeline import (
    find_jd_file,
    find_search_file,
    load_candidates_from_search,
    cmd_list_jds,
    cmd_clear_cache,
)


class TestFindJdFile:
    def test_finds_jd_by_id(self, sample_jd_file):
        result = find_jd_file("jd-test-001", sample_jd_file.parent)
        assert result == sample_jd_file

    def test_returns_none_if_not_found(self, tmp_path):
        result = find_jd_file("jd-nonexistent", tmp_path)
        assert result is None

    def test_lists_available_jds(self, sample_jd_file):
        jds = find_jd_file(None, sample_jd_file.parent)
        assert jds is not None
        assert "jd-test-001" in [j.stem for j in jds]


class TestFindSearchFile:
    def test_finds_search_file(self, sample_boss_search_file):
        result = find_search_file("AI产品经理", sample_boss_search_file.parent, "boss")
        assert result is not None

    def test_returns_none_if_not_found(self, tmp_path):
        result = find_search_file("nonexistent", tmp_path, "boss")
        assert result is None


class TestLoadCandidatesFromSearch:
    def test_loads_and_converts(self, sample_boss_search_file):
        candidates = load_candidates_from_search(sample_boss_search_file, "boss")
        assert len(candidates) == 2
        assert candidates[0]["name"] == "张三"
        assert "AI" in candidates[0].get("skill_tags", [])


class TestCmdListJds:
    def test_lists_jds(self, sample_jd_file, capsys):
        cmd_list_jds(sample_jd_file.parent)
        output = capsys.readouterr().out
        assert "jd-test-001" in output


class TestCmdClearCache:
    def test_clears_cache(self, tmp_path):
        cache_dir = tmp_path / "cache" / "pipeline" / "jd-test"
        cache_dir.mkdir(parents=True)
        (cache_dir / "analysis.json").write_text("{}", encoding="utf-8")
        args = types.SimpleNamespace(jd_id="jd-test")
        cmd_clear_cache(args, cache_dir=cache_dir)
        assert not cache_dir.exists()


def test_run_pipeline_passes_provider_to_client(mocker):
    from scripts.score_pipeline import run_pipeline
    from scripts.jd_analyzer import JDAnalysis

    fake_client = mocker.MagicMock()
    create_client = mocker.patch(
        "scripts.score_pipeline.create_llm_client", return_value=fake_client
    )
    mocker.patch(
        "scripts.score_pipeline.load_or_analyze",
        return_value=JDAnalysis(
            core_skills=["AI"],
            supplement_skills=[],
            position_type="AI产品经理",
            experience_range=(3, 10),
            education_requirement="本科",
            industry_preference=[],
            exclusion_criteria=[],
            raw_jd="jd",
            jd_hash="hash",
        ),
    )
    mocker.patch("scripts.score_pipeline.screen_candidates", return_value=[])

    result = run_pipeline(
        jd_id="jd-test",
        jd_text="jd",
        candidates=[],
        provider="openai-compatible",
        model="deepseek-chat",
    )

    create_client.assert_called_once_with(provider="openai-compatible", model="deepseek-chat")
    assert result["ranked"] == []
