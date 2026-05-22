from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_scorecard_v1"
DEFAULT_LABEL_THRESHOLDS = {
    "strong_recommend": 82,
    "recommend": 72,
    "observe": 60,
}

DEFAULT_DIMENSIONS = [
    {"id": "company_context", "label": "公司与业务上下文", "weight": 16},
    {"id": "title_focus", "label": "岗位方向", "weight": 16},
    {"id": "must_have", "label": "核心能力", "weight": 28},
    {"id": "nice_to_have", "label": "加分能力", "weight": 14},
    {"id": "seniority", "label": "资历匹配", "weight": 10},
    {"id": "education", "label": "教育背景", "weight": 8},
    {"id": "risk", "label": "风险扣分", "weight": 8},
]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _company_pools(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        values = _strings(items)
        if values:
            result[str(key)] = values
    return result


def build_scorecard(profile: dict[str, Any], role_id: str, version: str) -> dict[str, Any]:
    scorecard = {
        "schema": SCHEMA,
        "role_id": role_id,
        "version": version,
        "target_role": str(profile.get("target_role") or role_id),
        "dimensions": [dict(item) for item in DEFAULT_DIMENSIONS],
        "terms": {
            "must_have": _strings(profile.get("must_have")),
            "nice_to_have": _strings(profile.get("nice_to_have")),
            "title_aliases": _strings(profile.get("title_aliases")),
            "exclusion_terms": _strings(profile.get("exclusion_terms")),
            "risk_rules": _strings(profile.get("risk_rules")),
        },
        "company_pools": _company_pools(profile.get("company_pools")),
        "evidence_fields": [
            "current_company",
            "current_title",
            "skill_tags",
            "work_experience",
            "education_experience",
            "project_experience",
            "hunting_status",
        ],
        "label_thresholds": dict(DEFAULT_LABEL_THRESHOLDS),
    }
    validate_scorecard(scorecard)
    return scorecard


def validate_scorecard(scorecard: dict[str, Any]) -> None:
    if scorecard.get("schema") != SCHEMA:
        raise ValueError("invalid scorecard schema")
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("scorecard dimensions must be a non-empty list")
    weights: list[int] = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            raise ValueError("dimension must be an object")
        if "id" not in dimension:
            raise ValueError("dimension missing id")
        if "weight" not in dimension:
            raise ValueError("dimension missing weight")
        dimension_id = str(dimension["id"])
        try:
            weight = int(dimension["weight"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"dimension invalid weight: {dimension_id}") from exc
        weights.append(weight)
    total_weight = sum(weights)
    if total_weight != 100:
        raise ValueError(f"dimension weights must sum to 100, got {total_weight}")
    thresholds = scorecard.get("label_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("label_thresholds must be an object")


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("profile JSON must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build JD talent delivery scorecard")
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--role-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    profile = _load_json(args.profile_json)
    scorecard = build_scorecard(profile, role_id=args.role_id, version=args.version)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
