from scripts.maimai_ai_infra_search_live_gate import search_expression
from scripts.maimai_ai_infra_search_runner import patch_search_body


def _template_body() -> dict:
    return {
        "search": {
            "query": "old",
            "search_query": "old",
            "positions": "旧职位",
            "allcompanies": "BAT",
            "cities": "重庆",
            "provinces": "重庆",
            "ht_cities": "重庆",
            "ht_provinces": "重庆",
            "region_scope": "0",
            "paginationParam": {"page": 1, "size": 30},
            "page": 0,
            "size": 30,
        }
    }


def test_patch_search_body_clears_high_risk_template_filters_for_query_only() -> None:
    batch = {
        "query": "字节 大模型 后训练 数据策略 数据质量",
        "page_size": 30,
        "search_filters": {
            "query_relation": 0,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    }

    body = patch_search_body(_template_body(), batch, page=2)
    search = body["search"]

    assert search["query"] == "字节 大模型 后训练 数据策略 数据质量"
    assert search["search_query"] == "字节 大模型 后训练 数据策略 数据质量"
    assert search["allcompanies"] == ""
    assert search["positions"] == ""
    assert search["cities"] == ""
    assert search["provinces"] == ""
    assert search["ht_cities"] == ""
    assert search["ht_provinces"] == ""
    assert search["region_scope"] == "0,1"
    assert search["paginationParam"] == {"page": 2, "size": 30}


def test_patch_search_body_preserves_explicit_structured_filters() -> None:
    batch = {
        "query": "通义 数据策略",
        "page_size": 30,
        "search_filters": {
            "allcompanies": "阿里巴巴",
            "positions": "数据策略负责人",
            "query_relation": 1,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    }

    body = patch_search_body(_template_body(), batch, page=1)
    search = body["search"]

    assert search["allcompanies"] == "阿里巴巴"
    assert search["positions"] == "数据策略负责人"
    assert search["query_relation"] == 1


def test_live_gate_expression_contains_filter_defaults_and_explicit_empty_values() -> None:
    expression = search_expression(
        "字节 大模型 后训练 数据策略 数据质量",
        1,
        30,
        {
            "query_relation": 0,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    )

    assert "HIGH_RISK_FILTER_DEFAULTS" in expression
    assert '"allcompanies": ""' in expression
    assert '"positions": ""' in expression
    assert '"cities": ""' in expression
    assert '"region_scope": "0,1"' in expression
