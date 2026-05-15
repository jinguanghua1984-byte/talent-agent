"""Human review input for AI Infra V2 campaigns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_DECISIONS = {"detail_now", "hold", "reject"}


@dataclass(frozen=True)
class ReviewDecisions:
    campaign_id: str
    detail_candidate_ids: list[int]
    items: list[dict[str, Any]]


def _load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _candidate_id(value: Any, *, item_index: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"invalid candidate_id in review item {item_index}: {value}")
    try:
        candidate_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid candidate_id in review item {item_index}: {value}") from exc
    if candidate_id <= 0:
        raise ValueError(f"invalid candidate_id in review item {item_index}: {value}")
    return candidate_id


def load_review_decisions(path: str | Path) -> ReviewDecisions:
    data = _load_json(Path(path))
    if not isinstance(data, dict):
        raise ValueError("review JSON must be an object")

    items = data.get("items")
    if not isinstance(items, list):
        raise ValueError("review JSON items must be a list")

    seen: set[int] = set()
    detail_candidate_ids: list[int] = []
    validated_items: list[dict[str, Any]] = []

    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"review item {index} must be an object")
        decision = item.get("decision")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid review decision: {decision}")
        if "candidate_id" not in item:
            raise ValueError(f"missing candidate_id in review item {index}")
        candidate_id = _candidate_id(item["candidate_id"], item_index=index)
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id in review: {candidate_id}")
        seen.add(candidate_id)
        if decision == "detail_now":
            detail_candidate_ids.append(candidate_id)
        validated_items.append(item)

    return ReviewDecisions(
        campaign_id=str(data.get("campaign_id") or ""),
        detail_candidate_ids=detail_candidate_ids,
        items=validated_items,
    )
