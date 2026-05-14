import json
from pathlib import Path

from scripts.maimai_search_api_spec import build_search_api_spec, main


def _capture_payload() -> dict:
    return {
        "exportTime": "2026-05-14T10:00:00",
        "requests": [
            {
                "id": "ignore-1",
                "url": "/api/ent/talent/basic?channel=www",
                "method": "GET",
                "requestHeaders": {},
                "requestBody": None,
                "responseData": {"data": {}},
            },
            {
                "id": "search-1",
                "ts": "2026-05-14T10:01:00",
                "url": "/api/ent/v3/search/basic?channel=www&version=1.0.0",
                "method": "POST",
                "requestHeaders": {"x-csrf-token": "token-1"},
                "requestBody": json.dumps(
                    {
                        "search": {
                            "query": '"算法" "agent"',
                            "search_query": '"算法" "agent"',
                            "positions": "",
                            "allcompanies": "一线互联网公司",
                            "degrees": "2,3",
                            "worktimes": "",
                            "age": "",
                            "schools": "浙大",
                            "major": "软件工程",
                            "gender": "1",
                            "expected_min_salary": "3",
                            "expected_max_salary": "50",
                            "query_relation": 0,
                            "paginationParam": {"page": 1, "size": 30},
                            "page": 0,
                            "size": 30,
                            "sid": "pc-session-1",
                            "sessionid": "pc-session-1",
                            "data_version": "4.1",
                            "highlight_exp": 1,
                        }
                    },
                    ensure_ascii=False,
                ),
                "responseData": {"data": {"total": 173, "total_match": 173, "count": 30, "list": [{}] * 30}},
            },
            {
                "id": "search-2",
                "ts": "2026-05-14T10:04:00",
                "url": "/api/ent/v3/search/basic?channel=www&version=1.0.0",
                "method": "POST",
                "requestHeaders": {"x-csrf-token": "token-2"},
                "requestBody": json.dumps(
                    {
                        "search": {
                            "query": '"GPU" "CUDA"',
                            "search_query": '"GPU" "CUDA"',
                            "positions": "",
                            "allcompanies": "",
                            "degrees": "",
                            "worktimes": "3,5",
                            "age": "",
                            "schools": "浙大,清华大学",
                            "major": "软件工程,营销与策划",
                            "gender": "2",
                            "min_age": "16",
                            "max_age": "40",
                            "expected_min_salary": "3",
                            "expected_max_salary": "",
                            "query_relation": 1,
                            "paginationParam": {"page": 1, "size": 30},
                            "page": 0,
                            "size": 30,
                            "sid": "pc-session-2",
                            "sessionid": "pc-session-2",
                            "data_version": "4.1",
                            "highlight_exp": 1,
                        }
                    },
                    ensure_ascii=False,
                ),
                "responseData": {"data": {"total": 19, "total_match": 19, "count": 19, "list": [{}] * 19}},
            },
        ],
    }


def test_build_search_api_spec_extracts_headers_and_field_policy():
    spec = build_search_api_spec([_capture_payload()])

    assert spec["endpoint"]["path"] == "/api/ent/v3/search/basic"
    assert spec["endpoint"]["method"] == "POST"
    assert spec["samples"]["count"] == 2
    assert spec["headers"]["observed_common"] == ["x-csrf-token"]
    assert spec["headers"]["browser_managed"] == ["cookie/session via credentials=include"]
    assert "search.query" in spec["body_policy"]["generated_fields"]
    assert "search.search_query" in spec["body_policy"]["generated_fields"]
    assert "search.paginationParam.page" in spec["body_policy"]["generated_fields"]
    assert "search.allcompanies" in spec["body_policy"]["preserve_only_fields"]
    assert "search.degrees" in spec["body_policy"]["preserve_only_fields"]
    assert "search.query_relation" in spec["body_policy"]["preserve_only_fields"]
    assert spec["field_observations"]["search.degrees"]["values"] == ["", "2,3"]
    assert spec["field_observations"]["search.query_relation"]["values"] == [0, 1]


def test_cli_writes_json_and_markdown_spec(tmp_path: Path):
    capture_path = tmp_path / "capture.json"
    json_out = tmp_path / "spec.json"
    md_out = tmp_path / "spec.md"
    capture_path.write_text(json.dumps(_capture_payload(), ensure_ascii=False), encoding="utf-8")

    assert main([
        "--input",
        str(capture_path),
        "--out-json",
        str(json_out),
        "--out-md",
        str(md_out),
    ]) == 0

    data = json.loads(json_out.read_text(encoding="utf-8-sig"))
    text = md_out.read_text(encoding="utf-8-sig")
    assert data["samples"]["count"] == 2
    assert "请求头策略" in text
    assert "可生成字段" in text
    assert "待用户确认" in text


def test_build_search_api_spec_dedupes_same_record_across_capture_sections():
    record = _capture_payload()["requests"][1]
    payload = {
        "requests": [],
        "newSearchRecords": [record],
        "latestSearchRecords": [record],
    }

    spec = build_search_api_spec([payload])

    assert spec["samples"]["count"] == 1


def test_build_search_api_spec_records_field_priority_and_confirmed_semantics():
    spec = build_search_api_spec([_capture_payload()])

    field_catalog = spec["field_catalog"]
    assert field_catalog["critical"] == [
        "search.query",
        "search.search_query",
        "search.query_relation",
        "search.paginationParam.page",
        "search.paginationParam.size",
        "search.page",
        "search.size",
    ]
    assert "search.allcompanies" in field_catalog["priority_filters"]
    assert "search.degrees" in field_catalog["priority_filters"]
    assert "search.positions" in field_catalog["priority_filters"]
    assert "search.worktimes" in field_catalog["priority_filters"]
    assert "search.schools" in field_catalog["priority_filters"]
    assert "search.major" in field_catalog["priority_filters"]
    assert "search.gender" in field_catalog["secondary_filters"]
    assert "search.min_age" in field_catalog["secondary_filters"]
    assert "search.max_age" in field_catalog["secondary_filters"]
    assert "search.expected_min_salary" in field_catalog["secondary_filters"]
    assert field_catalog["semantics"]["search.query_relation"] == {
        "0": "AND",
        "1": "OR",
    }
    assert field_catalog["semantics"]["search.allcompanies"]["separator"] == "OR"
    assert field_catalog["semantics"]["search.allcompanies"]["employment_scope"] == "正任职和曾任职默认全选，不区分"
    assert field_catalog["semantics"]["search.positions"]["meaning"] == "候选人职位关键词"
    assert field_catalog["semantics"]["search.positions"]["separator"] == "OR"
    assert field_catalog["semantics"]["search.worktimes"]["preferred_fields"] == [
        "search.worktimes_min",
        "search.worktimes_max",
    ]
    assert field_catalog["semantics"]["search.schools"]["separator"] == "OR"
    assert field_catalog["semantics"]["search.major"]["meaning"] == "专业名"
    assert field_catalog["semantics"]["search.degrees"]["codes"] == {
        "0": "专科",
        "1": "本科",
        "2": "硕士",
        "3": "博士",
        "100": "自定义范围",
    }
    assert field_catalog["semantics"]["search.degrees"]["presets"] == {
        "专科及以上": "0,1,2,3",
        "本科及以上": "1,2,3",
        "硕士及以上": "2,3",
        "博士": "3",
    }
    assert field_catalog["semantics"]["search.degrees"]["range_fields"] == [
        "search.degrees_min",
        "search.degrees_max",
    ]
    assert field_catalog["semantics"]["search.degrees"]["only_bachelor_degree"] == {
        "0": "不限",
        "1": "只看统招本科",
    }
    assert field_catalog["semantics"]["search.min_age"] == {
        "meaning": "年龄范围下限",
        "pair_field": "search.max_age",
        "example": "min_age=16 且 max_age=40 表示 16-40 岁",
    }
    assert field_catalog["semantics"]["search.max_age"] == {
        "meaning": "年龄范围上限",
        "pair_field": "search.min_age",
        "example": "min_age=16 且 max_age=40 表示 16-40 岁",
    }
    assert "search.query_relation" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.allcompanies" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.positions" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.worktimes" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.schools" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.major" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.degrees" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.age" not in spec["body_policy"]["confirmation_required_fields"]
    assert "search.sid" in field_catalog["template_only"]
    assert "search.data_version" in field_catalog["template_only"]


def test_cli_markdown_includes_priority_sections_and_query_relation_semantics(tmp_path: Path):
    capture_path = tmp_path / "capture.json"
    json_out = tmp_path / "spec.json"
    md_out = tmp_path / "spec.md"
    capture_path.write_text(json.dumps(_capture_payload(), ensure_ascii=False), encoding="utf-8")

    assert main([
        "--input",
        str(capture_path),
        "--out-json",
        str(json_out),
        "--out-md",
        str(md_out),
    ]) == 0

    text = md_out.read_text(encoding="utf-8-sig")
    assert "## 字段优先级" in text
    assert "### 关键字段" in text
    assert "### 优先确认筛选字段" in text
    assert "`search.query_relation`：`0` = AND，`1` = OR" in text
    assert "`search.allcompanies`：公司/公司集合筛选；正任职和曾任职默认全选，不区分；逗号代表 OR" in text
    assert "`search.worktimes`：忽略快捷档位，优先使用 `worktimes_min`/`worktimes_max` 表示具体工作年数" in text
    assert "`search.degrees`：学历筛选；`0` = 专科，`1` = 本科，`2` = 硕士，`3` = 博士，`100` = 自定义范围" in text
    assert "`search.major`：专业名；逗号代表 OR" in text
    assert "`search.min_age`：年龄范围下限" in text
    assert "`search.max_age`：年龄范围上限" in text
    assert "### 其他已观测字段" in text
