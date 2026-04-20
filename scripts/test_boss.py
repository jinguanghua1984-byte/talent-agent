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
        """education 默认值应为 None。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.education)

    def test_work_years_default_none(self):
        """work_years 默认值应为 None。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.work_years)

    def test_education_can_be_set(self):
        """education 可设置非 None 值。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试", education="本科")
        self.assertEqual(params.education, "本科")

    def test_work_years_can_be_set(self):
        """work_years 可设置非 None 值。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试", work_years="3-5")
        self.assertEqual(params.work_years, "3-5")

    def test_frozen(self):
        """SearchParams 应为不可变。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        with self.assertRaises(AttributeError):
            params.query = "修改"


class TestAdapterRegistry(unittest.TestCase):
    """适配器注册表测试。"""

    def test_adapters_in_init(self):
        """ADAPTERS 应在 adapters/__init__.py 中定义。"""
        from adapters import ADAPTERS
        self.assertIsInstance(ADAPTERS, dict)
        self.assertIn("maimai", ADAPTERS)

    def test_maimai_adapter_registered(self):
        """脉脉适配器应已注册。"""
        from adapters import ADAPTERS
        adapter = ADAPTERS["maimai"]
        self.assertEqual(adapter.platform_name, "maimai")


class TestEnrichDynamicRouting(unittest.TestCase):
    """enrich.py 动态路由测试。"""

    def test_cmd_map_looks_up_adapters_registry(self):
        """cmd_map 应通过 ADAPTERS 注册表查找适配器。"""
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
        """不支持的 platform 应返回错误。"""
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
        """session.py 应注册 boss 平台验证 URL。"""
        from session import PLATFORM_VERIFY_URLS
        self.assertIn("boss", PLATFORM_VERIFY_URLS)
        self.assertEqual(PLATFORM_VERIFY_URLS["boss"], "https://www.zhipin.com/")

    def test_rate_limiter_default_limits_registered(self):
        """rate_limiter.py 应注册 boss 默认配额。"""
        from rate_limiter import DEFAULT_LIMITS
        self.assertIn("boss", DEFAULT_LIMITS)
        boss_config = DEFAULT_LIMITS["boss"]
        self.assertEqual(boss_config.batch_max, 20)
        self.assertEqual(boss_config.daily_max, 150)


if __name__ == "__main__":
    unittest.main()
