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


if __name__ == "__main__":
    unittest.main()
