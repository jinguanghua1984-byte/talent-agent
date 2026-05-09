"""pipeline_utils 共享工具模块测试"""

import json
from pathlib import Path

import pytest

from scripts.pipeline_utils import (
    compute_jd_hash,
    validate_jd_id,
    load_scoring_config,
    load_company_aliases,
    ensure_cache_dir,
    read_cache,
    write_cache,
    truncate_text_by_relevance,
)


class TestComputeJdHash:
    def test_same_text_same_hash(self):
        text = "职位描述内容"
        h1 = compute_jd_hash(text)
        h2 = compute_jd_hash(text)
        assert h1 == h2

    def test_different_text_different_hash(self):
        h1 = compute_jd_hash("内容A")
        h2 = compute_jd_hash("内容B")
        assert h1 != h2

    def test_hash_is_sha256(self):
        h = compute_jd_hash("test")
        assert len(h) == 64


class TestValidateJdId:
    def test_valid_id(self):
        assert validate_jd_id("jd-20260501-test") is True

    def test_valid_id_with_underscore(self):
        assert validate_jd_id("jd_20260501_test") is True

    def test_invalid_id_path_traversal(self):
        assert validate_jd_id("../etc/passwd") is False

    def test_invalid_id_special_chars(self):
        assert validate_jd_id("jd/test") is False
        assert validate_jd_id("jd test") is False


class TestLoadScoringConfig:
    def test_loads_config(self, tmp_path, monkeypatch):
        config_data = {"schema_version": 1, "top_companies": ["阿里巴巴"]}
        config_file = tmp_path / "scoring-config.json"
        config_file.write_text(json.dumps(config_data), encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        config = load_scoring_config()
        assert config["schema_version"] == 1
        assert config["top_companies"] == ["阿里巴巴"]


class TestCacheOperations:
    def test_write_and_read_cache(self, tmp_path):
        data = {"score": 85, "reason": "匹配度高"}
        path = write_cache(tmp_path / "test.json", data)
        assert path.exists()
        loaded = read_cache(path)
        assert loaded == data

    def test_read_missing_cache_returns_none(self, tmp_path):
        result = read_cache(tmp_path / "nonexistent.json")
        assert result is None


class TestEnsureCacheDir:
    def test_creates_directory(self, tmp_path):
        cache_dir = ensure_cache_dir(tmp_path / "cache" / "jd-123")
        assert cache_dir.exists()
        assert cache_dir.is_dir()


class TestTruncateTextByRelevance:
    def test_short_text_unchanged(self):
        text = "短文本"
        result = truncate_text_by_relevance(text, ["AI"], max_length=500)
        assert result == text

    def test_long_text_truncated_to_max(self):
        text = "工作描述 " * 200
        result = truncate_text_by_relevance(text, ["AI", "产品"], max_length=500)
        assert len(result) <= 500

    def test_relevance_priority(self):
        text = "负责数据分析报表制作。主导AI大模型产品从0到1。负责团队管理。"
        result = truncate_text_by_relevance(text, ["AI", "大模型", "产品"], max_length=30)
        assert "AI" in result or "大模型" in result


def test_load_company_aliases_does_not_depend_on_claude_private_dir(tmp_path, monkeypatch):
    """load_company_aliases 不依赖 .claude 私有目录，只从项目 rules/ 读取。"""
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "company-aliases.json").write_text(
        json.dumps({"测试公司": ["testco"]}), encoding="utf-8"
    )

    import scripts.pipeline_utils as pipeline_utils
    monkeypatch.setattr(pipeline_utils, "RULES_DIR", rules_dir)
    monkeypatch.setattr(pipeline_utils, "PROJECT_ROOT", tmp_path)

    aliases = pipeline_utils.load_company_aliases()
    assert aliases == {"测试公司": ["testco"]}
