"""enrich.py 字段合并单元测试"""

import os
import sys
import unittest

# 添加脚本路径，使 import enrich 可用
SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".claude", "skills", "platform-match", "scripts"
)
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


class TestFieldMerge(unittest.TestCase):
    """逐字段冲突合并测试。"""

    def test_latest_first_overwrites(self):
        """最新来源优先字段应被覆盖。"""
        from enrich import merge_fields
        existing = {"name": "张三", "current_company": "A公司"}
        new_data = {"current_company": "B公司"}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["current_company"], "B公司")

    def test_first_source_preserves(self):
        """首次来源优先字段，已有则不覆盖。"""
        from enrich import merge_fields
        existing = {"name": "张三", "education_experience": [{"school": "北大"}]}
        new_data = {"education_experience": [{"school": "清华"}]}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["education_experience"][0]["school"], "北大")

    def test_first_source_writes_when_empty(self):
        """首次来源优先字段，为空时写入。"""
        from enrich import merge_fields
        existing = {"name": "张三"}
        new_data = {"education_experience": [{"school": "清华"}]}
        result = merge_fields(existing, new_data)
        self.assertEqual(len(result["education_experience"]), 1)

    def test_skill_tags_merge_dedup(self):
        """技能标签应合并去重。"""
        from enrich import merge_fields
        existing = {"name": "张三", "skill_tags": ["Python", "Java"]}
        new_data = {"skill_tags": ["Java", "Go"]}
        result = merge_fields(existing, new_data)
        self.assertEqual(sorted(result["skill_tags"]), ["Go", "Java", "Python"])

    def test_skip_empty_values(self):
        """空值不应覆盖已有数据。"""
        from enrich import merge_fields
        existing = {"name": "张三", "age": 30}
        new_data = {"age": None, "city": ""}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["age"], 30)
        self.assertNotIn("city", result)

    def test_skip_internal_fields(self):
        """_ 开头的内部字段应被跳过。"""
        from enrich import merge_fields
        existing = {"name": "张三"}
        new_data = {"_source": {"channel": "maimai"}, "city": "北京"}
        result = merge_fields(existing, new_data)
        self.assertNotIn("_source", result)
        self.assertEqual(result["city"], "北京")


class TestAppendSource(unittest.TestCase):
    """Source 追加测试。"""

    def test_append_new_source(self):
        """追加新 source。"""
        from enrich import append_source
        existing = {"name": "张三", "sources": []}
        source = {"channel": "maimai", "url": "https://maimai.cn/u/123", "platform_id": "123"}
        result = append_source(existing, source)
        self.assertEqual(len(result["sources"]), 1)

    def test_dedup_same_platform_id(self):
        """相同 channel + platform_id 不应重复追加。"""
        from enrich import append_source
        source = {"channel": "maimai", "url": "https://maimai.cn/u/123", "platform_id": "123"}
        existing = {"name": "张三", "sources": [source]}
        result = append_source(existing, source)
        self.assertEqual(len(result["sources"]), 1)


class TestEnrichmentLevel(unittest.TestCase):
    """enrichment_level 提升测试。"""

    def test_level_only_goes_up(self):
        """enrichment_level 只升不降。"""
        from enrich import enrich_enrichment_level
        existing = {"enrichment_level": "partial", "sources": [
            {"enrichment_level": "raw"}
        ]}
        result = enrich_enrichment_level(existing)
        self.assertEqual(result["enrichment_level"], "partial")

    def test_level_promotes_from_sources(self):
        """从 sources 推断更高的 enrichment_level。"""
        from enrich import enrich_enrichment_level
        existing = {"enrichment_level": "raw", "sources": [
            {"enrichment_level": "enriched"}
        ]}
        result = enrich_enrichment_level(existing)
        self.assertEqual(result["enrichment_level"], "enriched")


if __name__ == "__main__":
    unittest.main()
