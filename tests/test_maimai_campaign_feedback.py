import json
from pathlib import Path

import pytest

from scripts.maimai_campaign_feedback import (
    compile_strategy_adjustment,
    load_delivery_feedback,
)


def test_load_delivery_feedback_validates_reason_codes(tmp_path: Path) -> None:
    path = tmp_path / "feedback.json"
    path.write_text(
        json.dumps(
            {
                "campaign_id": "hunyuan-data-strategy-lead-2026-05-21",
                "overall_rating": 3,
                "candidate_feedback": [
                    {
                        "candidate_id": 152,
                        "label": "bad",
                        "reason_codes": ["role_too_algorithmic", "lacks_data_team_management"],
                        "comment": "偏算法评测，不是数据策略负责人",
                    }
                ],
                "missing_profiles": ["更多真正管理数据标注/质检/交付团队的人"],
                "company_feedback": {"字节 DMC": "increase", "纯算法团队": "decrease"},
                "query_feedback": [{"unit_id": "unit-000001", "quality": "low"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    feedback = load_delivery_feedback(path)

    assert feedback["overall_rating"] == 3
    assert feedback["candidate_feedback"][0]["reason_codes"] == [
        "role_too_algorithmic",
        "lacks_data_team_management",
    ]


def test_load_delivery_feedback_rejects_unknown_label(tmp_path: Path) -> None:
    path = tmp_path / "bad-feedback.json"
    path.write_text(
        json.dumps(
            {
                "campaign_id": "c",
                "candidate_feedback": [{"candidate_id": 1, "label": "great"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid feedback label"):
        load_delivery_feedback(path)


def test_compile_strategy_adjustment_translates_feedback_to_actions(tmp_path: Path) -> None:
    feedback = {
        "campaign_id": "hunyuan-data-strategy-lead-2026-05-21",
        "overall_rating": 3,
        "candidate_feedback": [
            {
                "candidate_id": 152,
                "label": "bad",
                "reason_codes": ["role_too_algorithmic", "lacks_data_team_management"],
            }
        ],
        "missing_profiles": ["更多真正管理数据标注/质检/交付团队的人"],
        "company_feedback": {"字节 DMC": "increase", "纯算法团队": "decrease"},
        "query_feedback": [{"unit_id": "unit-000001", "quality": "low"}],
    }

    adjustment = compile_strategy_adjustment(feedback)

    assert adjustment["campaign_id"] == "hunyuan-data-strategy-lead-2026-05-21"
    assert "降低纯算法/训练框架画像权重" in adjustment["rank_adjustments"]
    assert "提高数据团队管理证据权重" in adjustment["rank_adjustments"]
    assert adjustment["company_adjustments"]["字节 DMC"] == "increase"
    assert adjustment["query_adjustments"][0]["unit_id"] == "unit-000001"
