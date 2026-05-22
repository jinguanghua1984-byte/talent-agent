from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_LABELS = {"good", "maybe", "bad"}
VALID_REASON_CODES = {
    "role_too_algorithmic",
    "lacks_data_team_management",
    "company_not_target",
    "seniority_too_low",
    "seniority_too_high",
    "missing_product_or_platform_scope",
    "good_target_company",
    "good_data_delivery_evidence",
}


def load_delivery_feedback(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("delivery feedback must be an object")
    items = data.get("candidate_feedback") or []
    if not isinstance(items, list):
        raise ValueError("candidate_feedback must be a list")
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"candidate_feedback item {index} must be an object")
        label = item.get("label")
        if label not in VALID_LABELS:
            raise ValueError(f"invalid feedback label: {label}")
        reason_codes = item.get("reason_codes") or []
        if not isinstance(reason_codes, list):
            raise ValueError(f"candidate_feedback item {index} reason_codes must be a list")
        unknown = sorted(set(str(code) for code in reason_codes) - VALID_REASON_CODES)
        if unknown:
            raise ValueError("unknown feedback reason codes: " + ", ".join(unknown))
    return data


def compile_strategy_adjustment(feedback: dict[str, Any]) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for item in feedback.get("candidate_feedback") or []:
        for code in item.get("reason_codes") or []:
            reason_counts[code] = reason_counts.get(code, 0) + 1

    rank_adjustments: list[str] = []
    if reason_counts.get("role_too_algorithmic"):
        rank_adjustments.append("降低纯算法/训练框架画像权重")
    if reason_counts.get("lacks_data_team_management"):
        rank_adjustments.append("提高数据团队管理证据权重")
    if reason_counts.get("seniority_too_low"):
        rank_adjustments.append("提高负责人/团队管理/Lead 职级信号权重")
    if reason_counts.get("missing_product_or_platform_scope"):
        rank_adjustments.append("提高数据平台/标注平台/质检平台产品化证据权重")

    return {
        "campaign_id": feedback.get("campaign_id") or "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_rating": feedback.get("overall_rating"),
        "reason_counts": reason_counts,
        "rank_adjustments": rank_adjustments,
        "company_adjustments": feedback.get("company_feedback") or {},
        "query_adjustments": feedback.get("query_feedback") or [],
        "missing_profiles": feedback.get("missing_profiles") or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="编译脉脉 campaign 交付反馈为下一轮策略调整")
    parser.add_argument("--feedback", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    feedback = load_delivery_feedback(args.feedback)
    adjustment = compile_strategy_adjustment(feedback)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(adjustment, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
