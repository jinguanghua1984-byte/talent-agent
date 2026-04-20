"""boss.py 纯函数单元测试"""

import os
import sys
import unittest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".claude", "skills", "platform-match", "scripts"
)
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


class TestSearchParamsExtended(unittest.TestCase):
    """SearchParams 扩展字段测试。"""

    def test_education_default_none(self):
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.education)

    def test_work_years_default_none(self):
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.work_years)

    def test_education_can_be_set(self):
        from adapters.base import SearchParams
        params = SearchParams(query="测试", education="本科")
        self.assertEqual(params.education, "本科")

    def test_work_years_can_be_set(self):
        from adapters.base import SearchParams
        params = SearchParams(query="测试", work_years="3-5")
        self.assertEqual(params.work_years, "3-5")

    def test_frozen(self):
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        with self.assertRaises(AttributeError):
            params.query = "修改"


class TestAdapterRegistry(unittest.TestCase):
    """适配器注册表测试。"""

    def test_adapters_in_init(self):
        from adapters import ADAPTERS
        self.assertIsInstance(ADAPTERS, dict)
        self.assertIn("maimai", ADAPTERS)

    def test_maimai_adapter_registered(self):
        from adapters import ADAPTERS
        adapter = ADAPTERS["maimai"]
        self.assertEqual(adapter.platform_name, "maimai")


class TestEnrichDynamicRouting(unittest.TestCase):
    """enrich.py 动态路由测试。"""

    def test_cmd_map_looks_up_adapters_registry(self):
        from unittest.mock import patch, MagicMock
        from adapters import ADAPTERS

        mock_adapter = MagicMock()
        mock_adapter.map_to_schema.return_value = {"name": "mocked"}

        with patch.dict(ADAPTERS, {"maimai": mock_adapter}):
            from enrich import cmd_map
            args = type("Args", (), {
                "platform": "maimai",
                "api_data": '{"name": "测试"}',
            })()
            cmd_map(args)
            mock_adapter.map_to_schema.assert_called_once_with({"name": "测试"})

    def test_cmd_map_unknown_platform(self):
        from enrich import cmd_map
        args = type("Args", (), {
            "platform": "unknown_platform",
            "api_data": '{"name": "测试"}',
        })()
        result = cmd_map(args)
        self.assertEqual(result, 1)


class TestBossInfrastructureRegistration(unittest.TestCase):
    """Boss 渠道基础设施注册测试。"""

    def test_session_verify_url_registered(self):
        from session import PLATFORM_VERIFY_URLS
        self.assertIn("boss", PLATFORM_VERIFY_URLS)
        self.assertEqual(PLATFORM_VERIFY_URLS["boss"], "https://www.zhipin.com/")

    def test_rate_limiter_default_limits_registered(self):
        from rate_limiter import DEFAULT_LIMITS
        self.assertIn("boss", DEFAULT_LIMITS)
        boss_config = DEFAULT_LIMITS["boss"]
        self.assertEqual(boss_config.batch_max, 20)
        self.assertEqual(boss_config.daily_max, 150)


class TestBossAdapterBasic(unittest.TestCase):
    """BossAdapter 基础属性测试。"""

    def _make_adapter(self):
        from adapters.boss import BossAdapter
        return BossAdapter()

    def test_platform_name(self):
        adapter = self._make_adapter()
        self.assertEqual(adapter.platform_name, "boss")


class TestBossBuildSearchParams(unittest.TestCase):
    """BossAdapter.build_search_params 测试。"""

    def _call(self, **kwargs):
        from adapters.boss import BossAdapter
        return BossAdapter().build_search_params(**kwargs)

    def test_candidate_name_and_company(self):
        params = self._call(candidate={"name": "张三", "current_company": "字节跳动"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "张三 字节跳动")

    def test_candidate_name_company_and_title(self):
        params = self._call(
            candidate={"name": "张三", "current_company": "字节跳动", "current_title": "产品经理"}
        )
        self.assertEqual(len(params), 2)
        queries = [p.query for p in params]
        self.assertIn("张三 字节跳动", queries)
        self.assertIn("张三 产品经理", queries)

    def test_candidate_name_with_city(self):
        params = self._call(
            candidate={"name": "张三", "current_company": "字节跳动", "city": "北京"}
        )
        self.assertEqual(params[0].city, "北京")

    def test_jd_keywords(self):
        params = self._call(jd={"keywords": ["Python", "后端"], "city": "上海"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "Python 后端")
        self.assertEqual(params[0].city, "上海")

    def test_jd_with_education_and_work_years(self):
        params = self._call(jd={
            "keywords": ["产品经理"],
            "education": "本科",
            "work_years": "3-5",
        })
        self.assertEqual(params[0].education, "本科")
        self.assertEqual(params[0].work_years, "3-5")

    def test_user_input(self):
        params = self._call(user_input={"query": "前端", "city": "深圳"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "前端")
        self.assertEqual(params[0].city, "深圳")

    def test_user_input_with_filters(self):
        params = self._call(user_input={
            "query": "工程师",
            "education": "硕士",
            "work_years": "5",
        })
        self.assertEqual(params[0].education, "硕士")
        self.assertEqual(params[0].work_years, "5")

    def test_empty_inputs(self):
        self.assertEqual(self._call(), [])
        self.assertEqual(self._call(candidate={}), [])
        self.assertEqual(self._call(jd={}), [])


class TestBossMapToSchema(unittest.TestCase):
    """BossAdapter.map_to_schema 测试。"""

    def _call(self, api_data):
        from adapters.boss import BossAdapter
        return BossAdapter().map_to_schema(api_data)

    def test_full_data(self):
        result = self._call({
            "name": "张三",
            "cityName": "北京",
            "brandName": "字节跳动",
            "jobName": "高级产品经理",
            "degree": "本科",
            "workYear": "5",
            "goldHunter": True,
            "skills": ["Python", "SQL"],
            "experienceList": [
                {"period": "2020-03至今", "company": "A公司", "job": "PM", "description": "负责产品"},
            ],
            "educationList": [
                {"period": "2016-09-2020-06", "school": "清华", "major": "计算机"},
            ],
            "encryptUserName": "abc123",
        })

        self.assertEqual(result["name"], "张三")
        self.assertEqual(result["city"], "北京")
        self.assertEqual(result["current_company"], "字节跳动")
        self.assertEqual(result["current_title"], "高级产品经理")
        self.assertEqual(result["education"], "本科")
        self.assertEqual(result["work_years"], 5)
        self.assertEqual(result["status"], "在职-看机会")
        self.assertEqual(result["skill_tags"], ["Python", "SQL"])
        self.assertEqual(len(result["work_experience"]), 1)
        self.assertEqual(result["work_experience"][0]["company"], "A公司")
        self.assertEqual(len(result["education_experience"]), 1)
        self.assertEqual(result["education_experience"][0]["school"], "清华")
        self.assertIsNotNone(result.get("_source"))
        self.assertEqual(result["_source"]["channel"], "boss")
        self.assertEqual(result["_source"]["platform_id"], "abc123")

    def test_minimal_data(self):
        result = self._call({"name": "李四"})
        self.assertEqual(result["name"], "李四")
        self.assertNotIn("education", result)
        self.assertNotIn("work_experience", result)
        self.assertNotIn("_source", result)

    def test_gold_hunter_false(self):
        result = self._call({"name": "测试", "goldHunter": False})
        self.assertEqual(result["status"], "在职-不看")

    def test_no_gold_hunter(self):
        result = self._call({"name": "测试"})
        self.assertNotIn("status", result)

    def test_empty_skills_ignored(self):
        result = self._call({"name": "测试", "skills": []})
        self.assertNotIn("skill_tags", result)

    def test_work_experience_filters_empty(self):
        result = self._call({
            "name": "测试",
            "experienceList": [
                {"period": "2020至今", "company": "", "job": ""},
                {"period": "2021至今", "company": "B公司", "job": ""},
            ],
        })
        self.assertEqual(len(result.get("work_experience", [])), 1)


class TestBossParseWorkYears(unittest.TestCase):
    """_parse_work_years 工作年限解析测试。"""

    def _call(self, raw):
        from adapters.boss import _parse_work_years
        return _parse_work_years(raw)

    def test_integer(self):
        self.assertEqual(self._call(5), 5)

    def test_string_with_number(self):
        self.assertEqual(self._call("5年"), 5)

    def test_none(self):
        self.assertEqual(self._call(None), 0)

    def test_plain_number_string(self):
        self.assertEqual(self._call("3"), 3)


class TestBossNormalizePeriod(unittest.TestCase):
    """_normalize_period 日期格式标准化测试。"""

    def _call(self, raw):
        from adapters.boss import _normalize_period
        return _normalize_period(raw)

    def test_to_present(self):
        self.assertEqual(self._call("2020-03至今"), "2020-03 - 至今")

    def test_date_range(self):
        self.assertEqual(self._call("2016-09-2020-06"), "2016-09 - 2020-06")

    def test_empty(self):
        self.assertEqual(self._call(""), "")

    def test_none(self):
        self.assertIsNone(self._call(None))


class TestBossAdapterRegistered(unittest.TestCase):
    """BossAdapter 注册测试。"""

    def test_boss_in_adapters_registry(self):
        from adapters import ADAPTERS
        self.assertIn("boss", ADAPTERS)

    def test_boss_adapter_platform_name(self):
        from adapters import ADAPTERS
        self.assertEqual(ADAPTERS["boss"].platform_name, "boss")

    def test_search_imports_from_adapters(self):
        from adapters import ADAPTERS as registry_adapters
        from search import ADAPTERS as search_adapters
        self.assertIs(search_adapters, registry_adapters)
        self.assertIn("boss", search_adapters)


if __name__ == "__main__":
    unittest.main()
