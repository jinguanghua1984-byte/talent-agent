import json
from pathlib import Path

from scripts.maimai_campaign_delivery_report import build_delivery_metadata, direction_rules_from_strategy
from scripts.maimai_campaign_rank import build_rank_terms
from scripts.maimai_campaign_search_plan import build_generic_search_plan


FIXTURE = Path("tests/fixtures/maimai/hunyuan-strategy.json")


def test_hunyuan_fixture_has_no_ai_infra_residue() -> None:
    strategy = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan = build_generic_search_plan(strategy)
    terms = build_rank_terms(strategy)
    metadata = build_delivery_metadata("hunyuan-data-strategy-lead-2026-05-21", strategy)
    direction_rules = direction_rules_from_strategy(strategy)

    encoded = json.dumps(
        {
            "plan": plan,
            "terms": terms.__dict__,
            "metadata": metadata,
            "direction_rules": direction_rules,
        },
        ensure_ascii=False,
    )

    assert "AI Infra" not in encoded
    assert "训练框架" not in encoded
    assert "推理引擎" not in encoded
    assert "混元大模型数据策略负责人最终寻访报告" in encoded
    assert any(batch["query"].startswith("字节 DMC ") for batch in plan["batches"])
    assert any(batch["query"].startswith("阿里千问 ") for batch in plan["batches"])
    assert all(batch["search_filters"]["allcompanies"] == "" for batch in plan["batches"])
    assert "数据交付负责人" in terms.precision_titles
    assert "后训练数据策略" in direction_rules
