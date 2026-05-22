from scripts.maimai_campaign_delivery_report import (
    build_delivery_metadata,
    direction_rules_from_strategy,
    outreach_angle,
)


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-delivery-v1",
        "delivery_targets": {
            "report_title": "混元大模型数据策略负责人最终寻访报告",
            "direction_rules": {
                "后训练数据策略": ["后训练", "数据策略", "Topic 数据"],
                "数据交付质量": ["数据标注", "数据质检", "数据交付", "质量评估"],
                "数据平台产品": ["标注平台", "质检平台", "数据管理"],
            },
        },
    }


def test_direction_rules_from_strategy_are_not_ai_infra_defaults() -> None:
    rules = direction_rules_from_strategy(_strategy())

    assert "后训练数据策略" in rules
    assert "训练框架" not in rules
    assert "推理引擎" not in rules


def test_build_delivery_metadata_uses_campaign_title() -> None:
    metadata = build_delivery_metadata("hunyuan-data-strategy-lead-2026-05-21", _strategy())

    assert metadata["export_type"] == "maimai_campaign_final_search_report"
    assert metadata["report_title"] == "混元大模型数据策略负责人最终寻访报告"


def test_outreach_angle_uses_role_specific_direction() -> None:
    text = outreach_angle(
        {
            "company": "字节跳动",
            "directions": ["数据交付质量"],
            "rank_evidence": {"tech_keywords": ["数据标注", "数据质检", "数据质量"]},
            "recommendation_label": "强推荐",
        }
    )

    assert "数据交付质量" in text
    assert "训练框架" not in text
    assert "底层系统深度" not in text
