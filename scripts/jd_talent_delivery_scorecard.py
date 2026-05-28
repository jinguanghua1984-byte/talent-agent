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
YOUNG_HIGH_POTENTIAL_DIMENSIONS = [
    {"id": "company_context", "label": "公司与业务上下文", "weight": 14},
    {"id": "title_focus", "label": "岗位方向", "weight": 16},
    {"id": "must_have", "label": "核心能力", "weight": 24},
    {"id": "nice_to_have", "label": "加分能力", "weight": 12},
    {"id": "seniority", "label": "年轻高潜资历匹配", "weight": 18},
    {"id": "education", "label": "教育与成长潜力", "weight": 10},
    {"id": "risk", "label": "风险扣分", "weight": 6},
]
YOUNG_HIGH_POTENTIAL_DESCRIPTION = (
    "优先推荐 5 年以内年轻高潜候选人；6-8 年保留观察，8 年以上仅作补位。"
)


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = value.strip()
        if item and item not in result:
            result.append(item)
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


def _seniority_policy(max_preferred_work_years: int) -> dict[str, Any]:
    if max_preferred_work_years <= 0:
        raise ValueError("max_preferred_work_years must be positive")
    return {
        "mode": "young_high_potential",
        "preferred_max_work_years": max_preferred_work_years,
        "soft_max_work_years": max(max_preferred_work_years + 3, max_preferred_work_years),
        "description": YOUNG_HIGH_POTENTIAL_DESCRIPTION.replace(
            "5 年", f"{max_preferred_work_years} 年"
        ),
    }


def build_scorecard(
    profile: dict[str, Any],
    role_id: str,
    version: str,
    *,
    young_high_potential: bool = False,
    max_preferred_work_years: int = 5,
) -> dict[str, Any]:
    risk_rules = _strings(profile.get("risk_rules"))
    dimensions = (
        YOUNG_HIGH_POTENTIAL_DIMENSIONS if young_high_potential else DEFAULT_DIMENSIONS
    )
    if young_high_potential:
        risk_rules.append(
            f"年轻高潜策略：工作年限超过 {max_preferred_work_years} 年需要降权复核"
        )
    scorecard = {
        "schema": SCHEMA,
        "role_id": role_id,
        "version": version,
        "target_role": str(profile.get("target_role") or role_id),
        "dimensions": [dict(item) for item in dimensions],
        "terms": {
            "must_have": _strings(profile.get("must_have")),
            "nice_to_have": _strings(profile.get("nice_to_have")),
            "title_aliases": _strings(profile.get("title_aliases")),
            "exclusion_terms": _strings(profile.get("exclusion_terms")),
            "risk_rules": _unique(risk_rules),
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
    if young_high_potential:
        scorecard["seniority_policy"] = _seniority_policy(max_preferred_work_years)
    validate_scorecard(scorecard)
    return scorecard


def _validate_seniority_policy(scorecard: dict[str, Any]) -> None:
    policy = scorecard.get("seniority_policy")
    if policy is None:
        return
    if not isinstance(policy, dict):
        raise ValueError("seniority_policy must be an object")
    mode = str(policy.get("mode") or "")
    if mode != "young_high_potential":
        raise ValueError(f"unsupported seniority_policy mode: {mode}")
    try:
        preferred = int(policy.get("preferred_max_work_years"))
        soft_max = int(policy.get("soft_max_work_years"))
    except (TypeError, ValueError) as exc:
        raise ValueError("seniority_policy work years must be integers") from exc
    if preferred <= 0:
        raise ValueError("seniority_policy preferred_max_work_years must be positive")
    if soft_max < preferred:
        raise ValueError("seniority_policy soft_max_work_years must be >= preferred_max_work_years")


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
    _validate_seniority_policy(scorecard)


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
    parser.add_argument("--young-high-potential", action="store_true")
    parser.add_argument("--max-preferred-work-years", type=int, default=5)
    args = parser.parse_args(argv)

    profile = _load_json(args.profile_json)
    scorecard = build_scorecard(
        profile,
        role_id=args.role_id,
        version=args.version,
        young_high_potential=args.young_high_potential,
        max_preferred_work_years=args.max_preferred_work_years,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
