"""数据转换模块测试: 搜索结果 → candidate schema"""

import pytest

from scripts.data_converter import (
    convert_boss_search_result,
    batch_convert,
)


class TestConvertBossSearchResult:
    def test_basic_conversion(self):
        item = {
            "name": "张三",
            "gender": 1,
            "city": "北京",
            "workYear": "5年",
            "salary": "30-50K",
            "lowSalary": 30,
            "hightSalary": 50,
            "highestDegreeName": "硕士",
            "activeDesc": "今日活跃",
            "encryptGeekId": "abc123",
            "lidTag": "AI产品",
            "geekDesc": {"name": "5年AI产品经验，负责大模型应用"},
            "expect": {"name": "AI产品经理"},
            "workEduDesc": {"name": "字节跳动·AI产品"},
            "works": [
                {"name": "产品经理·字节跳动"},
                {"name": "高级产品·阿里巴巴"},
            ],
            "labelMatchList": [
                {"markWord": "AI"},
                {"markWord": "大模型"},
            ],
            "eduSchool": "清华大学",
            "eduMajor": "计算机",
        }
        result = convert_boss_search_result(item)
        assert result["name"] == "张三"
        assert result["gender"] == "男"
        assert result["city"] == "北京"
        assert result["work_years"] == 5
        assert result["education"] == "硕士"
        assert result["active_state"] == "今日活跃"
        assert "AI" in result["skill_tags"]
        assert "大模型" in result["skill_tags"]
        assert len(result["work_experience"]) == 2
        assert result["work_experience"][0]["company"] == "字节跳动"
        assert result["current_company"] == "字节跳动"
        assert result["current_title"] == "AI产品"
        assert result["education_experience"][0]["school"] == "清华大学"

    def test_minimal_item(self):
        item = {"name": "李四", "gender": 2}
        result = convert_boss_search_result(item)
        assert result["name"] == "李四"
        assert result["gender"] == "女"
        assert "skill_tags" not in result

    def test_missing_optional_fields(self):
        item = {
            "name": "王五",
            "gender": 0,
            "encryptGeekId": "xyz",
        }
        result = convert_boss_search_result(item)
        assert result["name"] == "王五"
        assert result.get("gender") is None
        assert "_source" in result


class TestBatchConvert:
    def test_batch_converts_all_items(self):
        items = [
            {"name": "A", "gender": 1, "encryptGeekId": "a1"},
            {"name": "B", "gender": 2, "encryptGeekId": "b2"},
        ]
        results = batch_convert(items, "boss")
        assert len(results) == 2
        assert results[0]["name"] == "A"
        assert results[1]["name"] == "B"
