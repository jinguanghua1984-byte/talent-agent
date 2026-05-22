from scripts.maimai_campaign_rank import build_rank_terms, title_level


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-rank-v1",
        "position_aliases": [
            "大模型数据策略负责人",
            "数据交付负责人",
            "数据质检负责人",
            "数据运营负责人",
        ],
        "keyword_packages": [
            {
                "id": "p0-data",
                "keywords": ["大模型", "后训练", "数据策略", "数据质量", "数据标注", "数据合成"],
            }
        ],
        "screening_rules": {
            "A": ["负责后训练数据策略、数据交付、标注质检、数据合成或数据运营团队"],
            "淘汰": ["纯算法研究且无数据生产、质量体系或团队管理"],
        },
    }


def test_build_rank_terms_uses_strategy_not_ai_infra_defaults() -> None:
    terms = build_rank_terms(_strategy())

    assert "数据策略负责人" in terms.precision_titles
    assert "数据质量" in terms.keywords
    assert "AI Infra" not in terms.precision_titles
    assert "训练框架" not in terms.precision_titles
    assert "算子" not in terms.keywords


def test_title_level_matches_data_strategy_titles() -> None:
    terms = build_rank_terms(_strategy())

    assert title_level("大模型数据策略负责人", terms) == "precision"
    assert title_level("数据运营负责人", terms) == "precision"
    assert title_level("大模型算法工程师", terms) == "missing"
