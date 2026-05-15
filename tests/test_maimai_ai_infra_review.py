import json
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_review import load_review_decisions


def test_load_review_decisions_returns_detail_now_ids(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps(
            {
                "campaign_id": "ai-infra-v2-smoke",
                "items": [
                    {"candidate_id": 1, "decision": "detail_now", "priority": "P0"},
                    {"candidate_id": 2, "decision": "hold", "priority": "P1"},
                    {"candidate_id": 3, "decision": "detail_now", "priority": "P0"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = load_review_decisions(path)

    assert result.campaign_id == "ai-infra-v2-smoke"
    assert result.detail_candidate_ids == [1, 3]
    assert len(result.items) == 3


def test_load_review_decisions_rejects_invalid_decision(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps({"items": [{"candidate_id": 1, "decision": "maybe"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid review decision"):
        load_review_decisions(path)


def test_load_review_decisions_rejects_duplicate_candidate_id(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps(
            {
                "items": [
                    {"candidate_id": 1, "decision": "detail_now"},
                    {"candidate_id": 1, "decision": "hold"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate candidate_id"):
        load_review_decisions(path)


def test_load_review_decisions_rejects_non_integral_candidate_id(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps({"items": [{"candidate_id": 1.9, "decision": "detail_now"}]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid candidate_id"):
        load_review_decisions(path)
