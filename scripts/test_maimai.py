"""maimai.py 纯函数单元测试"""

import os
import sys
import unittest

# 添加脚本路径，使 import adapters 可用
SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".claude", "skills", "platform-match", "scripts"
)
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


class TestParseWorkYears(unittest.TestCase):
    """_parse_work_years 工作年限解析测试。"""

    def _call(self, raw):
        from adapters.maimai import _parse_work_years
        return _parse_work_years(raw)

    def test_standard_format(self):
        """标准格式 '4年7个月' 应返回 4。"""
        self.assertEqual(self._call("4年7个月"), 4)

    def test_full_years_only(self):
        """仅年份 '10年' 应返回 10。"""
        self.assertEqual(self._call("10年"), 10)

    def test_one_year(self):
        """'1年0个月' 应返回 1。"""
        self.assertEqual(self._call("1年0个月"), 1)

    def test_empty_string(self):
        """空字符串应返回 0。"""
        self.assertEqual(self._call(""), 0)

    def test_none(self):
        """None 应返回 0。"""
        self.assertEqual(self._call(None), 0)

    def test_no_year_match(self):
        """不包含'年'的字符串应返回 0。"""
        self.assertEqual(self._call("半年"), 0)


class TestNormalizePeriod(unittest.TestCase):
    """_normalize_period 日期格式标准化测试。"""

    def _call(self, raw):
        from adapters.maimai import _normalize_period
        return _normalize_period(raw)

    def test_to_present_with_day(self):
        """'2021-09-01至今' → '2021-09 - 至今'"""
        self.assertEqual(self._call("2021-09-01至今"), "2021-09 - 至今")

    def test_to_present_without_day(self):
        """'2021-09至今' → '2021 - 至今'（rsplit 去掉月份）"""
        self.assertEqual(self._call("2021-09至今"), "2021 - 至今")

    def test_date_range_with_day(self):
        """'2020-01至2023-06' → '2020 - 2023'（rsplit 去掉月份）"""
        self.assertEqual(self._call("2020-01至2023-06"), "2020 - 2023")

    def test_empty_string(self):
        """空字符串应原样返回。"""
        self.assertEqual(self._call(""), "")

    def test_none(self):
        """None 应原样返回。"""
        self.assertIsNone(self._call(None))

    def test_no_match_returns_raw(self):
        """无匹配的字符串应原样返回。"""
        raw = "2021年3月-2023年6月"
        self.assertEqual(self._call(raw), raw)


class TestBuildSearchParams(unittest.TestCase):
    """build_search_params 搜索参数构建测试。"""

    def _call(self, **kwargs):
        from adapters.maimai import MaimaiAdapter
        adapter = MaimaiAdapter()
        return adapter.build_search_params(**kwargs)

    def test_name_and_company(self):
        """姓名 + 公司应生成 1 个参数。"""
        params = self._call(candidate={"name": "张三", "current_company": "阿里巴巴"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "张三 阿里巴巴")

    def test_name_company_and_title(self):
        """姓名 + 公司 + 职位应生成 2 个参数。"""
        params = self._call(
            candidate={"name": "张三", "current_company": "阿里巴巴", "current_title": "CTO"}
        )
        self.assertEqual(len(params), 2)
        queries = [p.query for p in params]
        self.assertIn("张三 阿里巴巴", queries)
        self.assertIn("张三 CTO", queries)

    def test_name_only(self):
        """仅姓名应生成 1 个参数。"""
        params = self._call(candidate={"name": "张三"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "张三")

    def test_empty_jd(self):
        """空 JD 应返回空列表。"""
        params = self._call(jd={})
        self.assertEqual(len(params), 0)

    def test_user_input_query(self):
        """user_input 中的 query 应生成参数。"""
        params = self._call(user_input={"query": "Python 工程师", "city": "北京"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "Python 工程师")
        self.assertEqual(params[0].city, "北京")

    def test_candidate_plus_user_input(self):
        """候选人 + user_input 应合并参数。"""
        params = self._call(
            candidate={"name": "张三", "current_company": "阿里巴巴"},
            user_input={"query": "Python"}
        )
        self.assertEqual(len(params), 2)
        queries = [p.query for p in params]
        self.assertIn("张三 阿里巴巴", queries)
        self.assertIn("Python", queries)


class TestMapToSchema(unittest.TestCase):
    """map_to_schema API 数据映射测试。"""

    def _call(self, api_data):
        from adapters.maimai import MaimaiAdapter
        adapter = MaimaiAdapter()
        return adapter.map_to_schema(api_data)

    def test_full_data(self):
        """完整 API 数据应正确映射所有字段。"""
        result = self._call({
            "name": "张三",
            "gender_str": 1,
            "age": 30,
            "city": "北京",
            "company": "阿里巴巴",
            "position": "高级工程师",
            "sdegree": 2,
            "worktime": "5年3个月",
            "hunting_status": 5,
            "active_state": "活跃",
            "exp": [
                {"v": "2020-03-01至今", "company": "A公司", "position": "工程师", "description": "负责后端"},
            ],
            "edu": [
                {"v": "2016-09-01至2020-06-30", "school": "北大", "major": "计算机"},
            ],
            "exp_tags": ["Python", "Java"],
            "tag_list": ["Python", "Go", "Java"],
            "job_preferences": {
                "regions": ["杭州", "北京"],
                "positions": ["技术总监"],
                "salary": "50k-80k",
            },
            "user_project": [
                {"name": "电商平台", "period": "2021-01至今", "role": "负责人"},
            ],
            "id": "12345",
            "detail_url": "https://maimai.cn/u/12345",
        })

        self.assertEqual(result["name"], "张三")
        self.assertEqual(result["gender"], "男")
        self.assertEqual(result["age"], 30)
        self.assertEqual(result["city"], "北京")
        self.assertEqual(result["current_company"], "阿里巴巴")
        self.assertEqual(result["current_title"], "高级工程师")
        self.assertEqual(result["education"], "硕士")
        self.assertEqual(result["work_years"], 5)
        self.assertEqual(result["status"], "在职-看机会")
        self.assertEqual(result["active_state"], "活跃")
        self.assertEqual(len(result["work_experience"]), 1)
        self.assertEqual(result["work_experience"][0]["period"], "2020-03 - 至今")
        self.assertEqual(result["work_experience"][0]["company"], "A公司")
        self.assertEqual(len(result["education_experience"]), 1)
        self.assertEqual(result["education_experience"][0]["school"], "北大")
        # skill_tags 应去重排序
        self.assertEqual(result["skill_tags"], ["Go", "Java", "Python"])
        self.assertEqual(result["expected_city"], ["杭州", "北京"])
        self.assertEqual(result["expected_title"], "技术总监")
        self.assertEqual(result["expected_salary"], "50k-80k")
        self.assertEqual(len(result["project_experience"]), 1)
        self.assertEqual(result["project_experience"][0]["name"], "电商平台")
        # _source 应包含正确信息
        self.assertIsNotNone(result.get("_source"))
        self.assertEqual(result["_source"]["channel"], "maimai")
        self.assertEqual(result["_source"]["platform_id"], "12345")

    def test_minimal_data(self):
        """仅姓名的 API 数据应只映射基本字段。"""
        result = self._call({"name": "李四"})
        self.assertEqual(result["name"], "李四")
        self.assertEqual(result["gender"], "未提及")
        self.assertIsNone(result.get("age"))
        self.assertEqual(result["city"], "")
        self.assertNotIn("education", result)
        self.assertNotIn("work_experience", result)
        self.assertNotIn("skill_tags", result)
        # 无 id 和 detail_url 时不应有 _source
        self.assertNotIn("_source", result)

    def test_hunting_status_unknown(self):
        """未知的 hunting_status 应映射为'在职-不看'。"""
        result = self._call({"name": "王五", "hunting_status": 99})
        self.assertEqual(result["status"], "在职-不看")

    def test_no_hunting_status(self):
        """缺失 hunting_status 时不应生成 status 字段。"""
        result = self._call({"name": "王五"})
        self.assertNotIn("status", result)

    def test_empty_tags_ignored(self):
        """空标签和 None 标签列表不应生成 skill_tags。"""
        result = self._call({"name": "测试", "exp_tags": [None, ""], "tag_list": []})
        self.assertNotIn("skill_tags", result)

    def test_work_experience_filters_empty(self):
        """exp 中 company 和 position 都为空的条目应被过滤。"""
        result = self._call({
            "name": "测试",
            "exp": [
                {"v": "2020至今", "company": "", "position": ""},
                {"v": "2021至今", "company": "B公司", "position": ""},
            ],
        })
        self.assertEqual(len(result.get("work_experience", [])), 1)
        self.assertEqual(result["work_experience"][0]["company"], "B公司")

    def test_source_uses_detail_url(self):
        """有 detail_url 时 _source.url 应使用 detail_url。"""
        result = self._call({
            "name": "测试",
            "detail_url": "https://custom.url/u/999",
        })
        self.assertEqual(result["_source"]["url"], "https://custom.url/u/999")

    def test_source_url_fallback_to_id(self):
        """无 detail_url 时 _source.url 应基于 id 生成。"""
        result = self._call({"name": "测试", "id": "777"})
        self.assertEqual(result["_source"]["url"], "https://maimai.cn/u/777")


if __name__ == "__main__":
    unittest.main()
