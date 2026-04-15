"""rate_limiter.py 单元测试"""

import json
import os
import sys
import tempfile
import unittest

# 添加脚本路径，使 import rate_limiter 可用
SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".claude", "skills", "platform-match", "scripts"
)
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


class TestRateLimiter(unittest.TestCase):
    """限流器测试。"""

    def setUp(self):
        """每个测试使用临时目录。"""
        self.tmpdir = tempfile.mkdtemp()
        import rate_limiter
        self._original_session_dir = rate_limiter.SESSION_DIR
        self._original_state_file = rate_limiter.STATE_FILE
        rate_limiter.SESSION_DIR = self.tmpdir
        rate_limiter.STATE_FILE = os.path.join(self.tmpdir, "rate-limit-state.json")

    def tearDown(self):
        import rate_limiter
        rate_limiter.SESSION_DIR = self._original_session_dir
        rate_limiter.STATE_FILE = self._original_state_file

    def test_check_search_allowed_when_empty(self):
        """空状态时应允许搜索。"""
        from rate_limiter import check_search
        result = check_search("maimai")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["delay_seconds"], 0)

    def test_check_search_rate_limit(self):
        """连续搜索后应触发限流。"""
        from rate_limiter import check_search, record_search
        record_search("maimai")
        result = check_search("maimai")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "rate_limit")

    def test_record_search_increments_count(self):
        """记录搜索应递增计数器。"""
        from rate_limiter import record_search, _get_platform_state
        record_search("maimai")
        state = _get_platform_state("maimai")
        self.assertEqual(state.batch_count, 1)
        self.assertEqual(state.daily_count, 1)

    def test_circuit_break_triggers(self):
        """熔断触发后应阻止搜索。"""
        from rate_limiter import trigger_circuit_break, check_search
        trigger_circuit_break("maimai", "CAPTCHA")
        result = check_search("maimai")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "circuit_break")

    def test_reset_clears_state(self):
        """重置应清除所有限流状态。"""
        from rate_limiter import record_search, check_search, _save_state
        record_search("maimai")
        # 重置: 写入空状态
        _save_state({})
        result = check_search("maimai")
        self.assertTrue(result["allowed"])

    def test_headless_stricter_limits(self):
        """降级模式应使用更严格的限流。"""
        from rate_limiter import check_search, record_search
        record_search("maimai", headless=True)
        result = check_search("maimai", headless=True)
        self.assertFalse(result["allowed"])


if __name__ == "__main__":
    unittest.main()
