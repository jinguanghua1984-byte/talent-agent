from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


DEFAULT_DIRECTION_RULES = {
    "核心岗位匹配": ("岗位", "负责人", "Lead"),
    "公司/行业匹配": ("公司", "行业", "团队"),
    "待深审": (),
}


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("JSON file must be an object")
    return data


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_text(path: str | Path, text: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8-sig")


def direction_rules_from_strategy(strategy: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    delivery_targets = strategy.get("delivery_targets")
    if isinstance(delivery_targets, dict) and isinstance(delivery_targets.get("direction_rules"), dict):
        return {
            str(label): tuple(str(term) for term in terms)
            for label, terms in delivery_targets["direction_rules"].items()
            if isinstance(terms, list)
        }
    return DEFAULT_DIRECTION_RULES


def build_delivery_metadata(campaign_id: str, strategy: dict[str, Any]) -> dict[str, Any]:
    delivery_targets = strategy.get("delivery_targets") if isinstance(strategy.get("delivery_targets"), dict) else {}
    return {
        "export_type": "maimai_campaign_final_search_report",
        "campaign_id": campaign_id,
        "strategy_version": strategy.get("strategy_version") or "",
        "report_title": delivery_targets.get("report_title") or f"{campaign_id} 最终寻访报告",
    }


def outreach_angle(card: dict[str, Any]) -> str:
    company = card.get("company") or "当前团队"
    directions = "、".join(card.get("directions") or ["岗位匹配"])
    keywords = card.get("rank_evidence", {}).get("tech_keywords") or []
    keyword_text = "、".join(str(keyword) for keyword in keywords[:3]) or directions
    if card.get("recommendation_label") == "强推荐":
        return f"优先从 {company} 的{directions}经历切入，确认其在 {keyword_text} 上的职责边界、团队规模和近期机会意愿。"
    if card.get("recommendation_label") == "推荐":
        return f"围绕 {directions} 与 {keyword_text} 追问具体职责，确认是否符合本岗位核心画像。"
    if card.get("recommendation_label") == "观察":
        return "先做轻量深审，重点确认岗位画像、团队管理和核心业务证据是否真实匹配。"
    return "不进入外联队列；仅作为下一轮评分误判样本。"


def _md_cell(value: Any, limit: int = 120) -> str:
    if isinstance(value, (list, tuple)):
        text = "；".join(str(item) for item in value if item not in (None, ""))
    else:
        text = "" if value is None else str(value)
    text = " ".join(text.replace("|", "/").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _write_search_report_md(path: str | Path, report: dict[str, Any]) -> None:
    metadata = report["metadata"]
    funnel = report.get("funnel", {})
    lines = [
        f"# {metadata['report_title']}",
        "",
        f"- Campaign：{metadata['campaign_id']}",
        f"- 策略版本：{metadata.get('strategy_version', '')}",
        f"- 详情完成：{funnel.get('detail_completed', 0)}/{funnel.get('target_count', 0)}",
        f"- 最终推荐：强推荐 {funnel.get('strong_recommended_count', 0)}，推荐 {funnel.get('recommended_count', 0)}，观察 {funnel.get('observe_count', 0)}，不推荐 {funnel.get('not_recommended_count', 0)}。",
        "",
        "## 方向覆盖",
    ]
    for label, stats in (report.get("direction_coverage") or {}).items():
        if isinstance(stats, dict):
            lines.append(f"- {label}：{stats.get('count', 0)} 人")
    lines.extend(["", "## Top 候选人", ""])
    for card in (report.get("candidate_cards") or [])[:30]:
        lines.append(
            f"- #{card.get('rank')} {card.get('name', '')}｜{card.get('recommendation_label', '')}｜"
            f"{card.get('company', '')}｜{card.get('title', '')}｜{_md_cell(card.get('directions'))}"
        )
        if card.get("suggested_outreach_angle"):
            lines.append(f"  - 建议切入：{card['suggested_outreach_angle']}")
    _write_text(path, "\n".join(lines) + "\n")


def _write_outreach_md(path: str | Path, outreach: dict[str, Any]) -> None:
    metadata = outreach["metadata"]
    lines = [
        f"# {metadata.get('report_title', metadata.get('campaign_id', 'Campaign'))} 外联优先级队列",
        "",
    ]
    for priority, count in (outreach.get("queue_counts") or {}).items():
        lines.append(f"- {priority}：{count} 人")
    lines.extend(["", "| 优先级 | Rank | ID | 姓名 | 公司 | 职位 | 推荐 | 方向 | 建议切入 |", "|---|---:|---:|---|---|---|---|---|---|"])
    queues = outreach.get("priority_queues") if isinstance(outreach.get("priority_queues"), dict) else {}
    for priority in ("P0", "P1", "P2"):
        for card in queues.get(priority) or []:
            lines.append(
                f"| {priority} | {card.get('rank', '')} | {card.get('candidate_id', '')} | "
                f"{_md_cell(card.get('name'), 40)} | {_md_cell(card.get('company'), 60)} | "
                f"{_md_cell(card.get('title'), 70)} | {card.get('recommendation_label', '')} | "
                f"{_md_cell(card.get('directions'), 80)} | {_md_cell(card.get('suggested_outreach_angle'), 140)} |"
            )
    _write_text(path, "\n".join(lines) + "\n")


def _load_strategy(campaign_root: Path, config: str | Path | None = None) -> dict[str, Any]:
    config_path = Path(config) if config else campaign_root / "strategy.json"
    if not config_path.exists():
        return {}
    return _load_json(config_path)


def build_delivery_reports(
    campaign_root: str | Path,
    db_path: str | Path,
    targets_path: str | Path,
    rank_json_path: str | Path,
    out_report_json: str | Path | None = None,
    out_report_md: str | Path | None = None,
    out_outreach_json: str | Path | None = None,
    out_outreach_md: str | Path | None = None,
    strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from scripts import maimai_ai_infra_delivery_report as legacy

    root = Path(campaign_root)
    active_strategy = strategy if strategy is not None else _load_strategy(root)
    direction_rules = direction_rules_from_strategy(active_strategy)
    original_rules = legacy.DIRECTION_RULES
    original_outreach_angle = legacy._outreach_angle
    try:
        legacy.DIRECTION_RULES = direction_rules
        legacy._outreach_angle = outreach_angle
        result = legacy.build_delivery_reports(
            campaign_root=root,
            db_path=db_path,
            targets_path=targets_path,
            rank_json_path=rank_json_path,
        )
    finally:
        legacy.DIRECTION_RULES = original_rules
        legacy._outreach_angle = original_outreach_angle

    metadata = build_delivery_metadata(root.name, active_strategy)
    search_report = result["search_report"]
    search_report["metadata"].update(metadata)
    outreach_priority = result["outreach_priority"]
    outreach_priority["metadata"].update({
        "export_type": "maimai_campaign_outreach_priority",
        "campaign_id": metadata["campaign_id"],
        "strategy_version": metadata["strategy_version"],
        "report_title": metadata["report_title"],
    })

    if out_report_json is not None:
        _write_json(out_report_json, search_report)
    if out_report_md is not None:
        _write_search_report_md(out_report_md, search_report)
    if out_outreach_json is not None:
        _write_json(out_outreach_json, outreach_priority)
    if out_outreach_md is not None:
        _write_outreach_md(out_outreach_md, outreach_priority)
    return {
        "search_report": search_report,
        "outreach_priority": outreach_priority,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成通用 JD-driven 脉脉交付版寻访报告")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--rank-json", required=True)
    parser.add_argument("--out-report-json", required=True)
    parser.add_argument("--out-report-md", required=True)
    parser.add_argument("--out-outreach-json", required=True)
    parser.add_argument("--out-outreach-md", required=True)
    parser.add_argument("--config")
    args = parser.parse_args(argv)

    strategy = _load_strategy(Path(args.campaign_root), args.config)
    result = build_delivery_reports(
        campaign_root=args.campaign_root,
        db_path=args.db_path,
        targets_path=args.targets,
        rank_json_path=args.rank_json,
        out_report_json=args.out_report_json,
        out_report_md=args.out_report_md,
        out_outreach_json=args.out_outreach_json,
        out_outreach_md=args.out_outreach_md,
        strategy=strategy,
    )
    queues = result["outreach_priority"]["queue_counts"]
    print(
        json.dumps(
            {
                "status": "ok",
                "report": args.out_report_json,
                "outreach": args.out_outreach_json,
                "queue_counts": queues,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
