"""报告生成模块测试"""

import pytest

from scripts.report_generator import generate_report, format_score_table
from scripts.llm_ranker import RankScore


SAMPLE_RANKED = [
    RankScore(
        candidate_id="c1", total_score=88.0,
        dimensions={"岗位匹配度": 26, "技能覆盖率": 22, "经验深度": 18, "行业背景": 13, "稳定性": 9},
        reason="AI Agent 产品经验丰富，字节跳动背景", gap="C端产品经验较少",
    ),
    RankScore(
        candidate_id="c2", total_score=72.0,
        dimensions={"岗位匹配度": 20, "技能覆盖率": 18, "经验深度": 15, "行业背景": 12, "稳定性": 7},
        reason="有AI产品经验但深度不够", gap="缺少Agent平台经验",
    ),
]

SAMPLE_CANDIDATES = {
    "c1": {"name": "张三", "city": "北京", "current_company": "字节跳动", "current_title": "AI产品总监"},
    "c2": {"name": "李四", "city": "上海", "current_company": "某AI公司", "current_title": "产品经理"},
}


class TestGenerateReport:
    def test_generates_markdown(self):
        report = generate_report(
            ranked=SAMPLE_RANKED,
            candidates_map=SAMPLE_CANDIDATES,
            jd_text="AI产品经理",
            jd_id="jd-test",
            top_n=10,
        )
        assert "# " in report
        assert "张三" in report
        assert "88.0" in report

    def test_respects_top_n(self):
        report = generate_report(
            ranked=SAMPLE_RANKED,
            candidates_map=SAMPLE_CANDIDATES,
            jd_text="JD",
            jd_id="jd-test",
            top_n=1,
        )
        assert "张三" in report
        assert "李四" not in report


class TestFormatScoreTable:
    def test_includes_all_dimensions(self):
        table = format_score_table(SAMPLE_RANKED[0], SAMPLE_CANDIDATES["c1"], rank=1)
        assert "岗位匹配度" in table
        assert "26" in table