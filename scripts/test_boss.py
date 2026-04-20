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
    """BossAdapter.map_to_schema 测试（基于实际 API geekCard 结构）。"""

    def _call(self, api_data):
        from adapters.boss import BossAdapter
        return BossAdapter().map_to_schema(api_data)

    def test_full_geek_card(self):
        """完整 geekCard 数据映射。"""
        result = self._call({
            "name": "王**",
            "gender": 1,
            "city": "大连",
            "workYear": "4年",
            "salary": "15-25K",
            "highestDegreeName": "硕士",
            "ageDesc": "27岁",
            "activeDesc": "刚刚活跃",
            "geekWork": {
                "name": "百度·PSIG·产品经理",
            },
            "geekEdu": {
                "name": "英国·曼彻斯特大学·人力资源管理与产业关系",
            },
            "labelMatchList": [
                {"markWord": "QS前100院校", "type": 2},
                {"markWord": "产品经理", "type": 0},
            ],
            "workList": [
                {"name": "百度·PSIG·产品经理", "dateRange": "2024-2026"},
                {"name": "最右·产品经理", "dateRange": "2022-2024"},
            ],
            "encryptGeekId": "abc123",
            "securityId": "sec456",
        })

        self.assertEqual(result["name"], "王**")
        self.assertEqual(result["gender"], "男")
        self.assertEqual(result["city"], "大连")
        self.assertEqual(result["current_company"], "百度")
        self.assertEqual(result["current_title"], "产品经理")
        self.assertEqual(result["education"], "硕士")
        self.assertEqual(result["work_years"], 4)
        self.assertEqual(result["age"], 27)
        self.assertEqual(result["active_state"], "刚刚活跃")
        self.assertEqual(result["expected_salary"], "15-25K")
        self.assertEqual(result["skill_tags"], ["QS前100院校", "产品经理"])
        self.assertEqual(len(result["work_experience"]), 2)
        self.assertEqual(result["work_experience"][0]["company"], "百度")
        self.assertEqual(result["work_experience"][0]["title"], "产品经理")
        self.assertEqual(result["work_experience"][0]["period"], "2024-2026")
        self.assertEqual(result["work_experience"][1]["company"], "最右")
        self.assertEqual(len(result["education_experience"]), 1)
        self.assertEqual(result["education_experience"][0]["school"], "曼彻斯特大学")
        self.assertEqual(result["education_experience"][0]["major"], "人力资源管理与产业关系")
        self.assertEqual(result["_source"]["channel"], "boss")
        self.assertEqual(result["_source"]["platform_id"], "abc123")
        self.assertEqual(result["_source"]["security_id"], "sec456")

    def test_minimal_data(self):
        result = self._call({"name": "李四"})
        self.assertEqual(result["name"], "李四")
        self.assertNotIn("education", result)
        self.assertNotIn("work_experience", result)
        self.assertNotIn("_source", result)

    def test_gender_female(self):
        result = self._call({"name": "测试", "gender": 2})
        self.assertEqual(result["gender"], "女")

    def test_gender_unknown_omitted(self):
        result = self._call({"name": "测试", "gender": 0})
        self.assertNotIn("gender", result)

    def test_no_gender_omitted(self):
        result = self._call({"name": "测试"})
        self.assertNotIn("gender", result)

    def test_geek_work_two_parts(self):
        """geekWork.name 只有公司·职位两部分。"""
        result = self._call({
            "name": "测试",
            "geekWork": {"name": "字节跳动·产品经理"},
        })
        self.assertEqual(result["current_company"], "字节跳动")
        self.assertEqual(result["current_title"], "产品经理")

    def test_geek_work_missing(self):
        result = self._call({"name": "测试"})
        self.assertNotIn("current_company", result)
        self.assertNotIn("current_title", result)

    def test_geek_edu_two_parts(self):
        """geekEdu.name 只有学校·专业两部分。"""
        result = self._call({
            "name": "测试",
            "geekEdu": {"name": "清华大学·计算机"},
        })
        self.assertEqual(result["education_experience"][0]["school"], "清华大学")
        self.assertEqual(result["education_experience"][0]["major"], "计算机")

    def test_empty_label_match_list_ignored(self):
        result = self._call({"name": "测试", "labelMatchList": []})
        self.assertNotIn("skill_tags", result)

    def test_label_match_list_no_mark_word(self):
        result = self._call({
            "name": "测试",
            "labelMatchList": [{"type": 2, "markWord": "", "labelStyle": 0}],
        })
        self.assertNotIn("skill_tags", result)

    def test_work_experience_filters_empty_name(self):
        result = self._call({
            "name": "测试",
            "workList": [
                {"name": "", "dateRange": "2024-2026"},
                {"name": "A公司·工程师", "dateRange": "2020-2024"},
            ],
        })
        self.assertEqual(len(result.get("work_experience", [])), 1)
        self.assertEqual(result["work_experience"][0]["company"], "A公司")

    def test_work_experience_single_part_name(self):
        """workList[].name 只有公司名（无·分隔）。"""
        result = self._call({
            "name": "测试",
            "workList": [{"name": "某公司", "dateRange": "2020-2024"}],
        })
        self.assertEqual(result["work_experience"][0]["company"], "某公司")
        self.assertEqual(result["work_experience"][0]["title"], "")


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


class TestBossParseAge(unittest.TestCase):
    """_parse_age 年龄解析测试。"""

    def _call(self, raw):
        from adapters.boss import _parse_age
        return _parse_age(raw)

    def test_age_string(self):
        self.assertEqual(self._call("27岁"), 27)

    def test_none(self):
        self.assertIsNone(self._call(None))

    def test_empty_string(self):
        self.assertIsNone(self._call(""))


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

    def test_passthrough(self):
        self.assertEqual(self._call("2024-2026"), "2024-2026")


class TestBossParseGeekWork(unittest.TestCase):
    """_parse_geek_work 公司职位解析测试。"""

    def _call(self, geek_work):
        from adapters.boss import _parse_geek_work
        return _parse_geek_work(geek_work)

    def test_three_parts(self):
        company, title = self._call({"name": "百度·PSIG·产品经理"})
        self.assertEqual(company, "百度")
        self.assertEqual(title, "产品经理")

    def test_two_parts(self):
        company, title = self._call({"name": "字节跳动·前端"})
        self.assertEqual(company, "字节跳动")
        self.assertEqual(title, "前端")

    def test_none(self):
        company, title = self._call(None)
        self.assertEqual(company, "")
        self.assertEqual(title, "")

    def test_empty_dict(self):
        company, title = self._call({})
        self.assertEqual(company, "")
        self.assertEqual(title, "")


class TestBossParseGeekEdu(unittest.TestCase):
    """_parse_geek_edu 学校专业解析测试。"""

    def _call(self, geek_edu):
        from adapters.boss import _parse_geek_edu
        return _parse_geek_edu(geek_edu)

    def test_three_parts(self):
        school, major = self._call({"name": "英国·曼彻斯特大学·人力资源"})
        self.assertEqual(school, "曼彻斯特大学")
        self.assertEqual(major, "人力资源")

    def test_two_parts(self):
        school, major = self._call({"name": "清华大学·计算机"})
        self.assertEqual(school, "清华大学")
        self.assertEqual(major, "计算机")

    def test_none(self):
        school, major = self._call(None)
        self.assertEqual(school, "")
        self.assertEqual(major, "")


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
