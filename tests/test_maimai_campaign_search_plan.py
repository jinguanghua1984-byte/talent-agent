import json

from scripts.maimai_campaign_search_plan import build_generic_search_plan, build_generic_search_units


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-data-strategy-lead-v1",
        "keyword_packages": [
            {
                "id": "p0-data-strategy",
                "priority": "P0",
                "position_terms": ["大模型数据策略负责人", "数据策略负责人"],
                "keywords": ["大模型", "后训练", "数据策略", "数据质量"],
            }
        ],
        "company_pools": {
            "p0_direct": ["字节 DMC", "阿里千问", "美团", "小红书"],
        },
        "search_dimensions": {
            "search_units_file": "search-units.jsonl",
        },
        "stop_thresholds": {
            "budget": ["单个 wave 不超过 50 页"],
        },
    }


def test_build_generic_search_units_expands_each_company_pool_member() -> None:
    units = build_generic_search_units(_strategy())

    assert [unit["unit_id"] for unit in units] == [
        "unit-000001",
        "unit-000002",
        "unit-000003",
        "unit-000004",
    ]
    queries = [unit["query"] for unit in units]
    assert "字节 DMC 大模型 后训练 数据策略 数据质量" in queries
    assert "阿里千问 大模型 后训练 数据策略 数据质量" in queries
    assert "美团 大模型 后训练 数据策略 数据质量" in queries
    assert "小红书 大模型 后训练 数据策略 数据质量" in queries
    assert all(unit["search_filters"]["allcompanies"] == "" for unit in units)
    assert all(unit["search_filters"]["positions"] == "" for unit in units)
    assert all(unit["search_filters"]["region_scope"] == "0,1" for unit in units)


def test_build_generic_search_plan_does_not_emit_ai_infra_batches() -> None:
    plan = build_generic_search_plan(_strategy())

    encoded = json.dumps(plan, ensure_ascii=False)
    assert plan["strategy_version"] == "hunyuan-data-strategy-lead-v1"
    assert "AI Infra" not in encoded
    assert "训练框架" not in encoded
    assert plan["batches"][0]["query"] == "字节 DMC 大模型 后训练 数据策略 数据质量"
