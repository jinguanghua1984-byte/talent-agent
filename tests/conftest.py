"""共享测试 fixtures"""

import json
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def sample_jd_text() -> str:
    return """AI Agent平台产品经理，5年以上产品经理经验。
要求: 有AI产品经验，熟悉Agent/RAG等技术，计算机专业优先。
排除: 纯算法背景。"""


@pytest.fixture
def sample_jd_file(tmp_path, sample_jd_text) -> Path:
    jd_data = {
        "id": "jd-test-001",
        "company": "测试公司",
        "title": "AI产品经理",
        "description": sample_jd_text,
        "requirements": {"min_experience_years": 5},
        "experience": "5-10年",
        "min_education": "本科",
        "industry": "AI",
    }
    jd_file = tmp_path / "jds" / "jd-test-001.json"
    jd_file.parent.mkdir(parents=True, exist_ok=True)
    jd_file.write_text(json.dumps(jd_data, ensure_ascii=False), encoding="utf-8")
    return jd_file


@pytest.fixture
def sample_boss_search_file(tmp_path) -> Path:
    search_data = {
        "query": "AI产品经理",
        "items": [
            {
                "name": "张三", "gender": 1, "city": "北京",
                "workYear": "8年", "highestDegreeName": "硕士",
                "activeDesc": "今日活跃", "encryptGeekId": "abc123",
                "lidTag": "AI产品",
                "geekDesc": {"name": "5年AI产品经验，负责Agent平台"},
                "expect": {"name": "AI产品经理"},
                "workEduDesc": {"name": "字节跳动·AI产品"},
                "works": [{"name": "产品经理·字节跳动"}],
                "labelMatchList": [{"markWord": "AI"}, {"markWord": "Agent"}],
                "eduSchool": "清华大学", "eduMajor": "计算机",
            },
            {
                "name": "李四", "gender": 2, "city": "上海",
                "workYear": "3年", "highestDegreeName": "本科",
                "activeDesc": "本周活跃", "encryptGeekId": "xyz789",
                "lidTag": "数据",
                "geekDesc": {"name": "数据分析经验"},
                "expect": {"name": "数据分析师"},
                "workEduDesc": {"name": "某公司·数据"},
                "works": [{"name": "分析师·某公司"}],
                "labelMatchList": [{"markWord": "SQL"}],
                "eduSchool": "某大学", "eduMajor": "统计",
            },
        ],
    }
    search_file = tmp_path / "boss-search" / "search-AI产品经理.json"
    search_file.parent.mkdir(parents=True, exist_ok=True)
    search_file.write_text(json.dumps(search_data, ensure_ascii=False), encoding="utf-8")
    return search_file
