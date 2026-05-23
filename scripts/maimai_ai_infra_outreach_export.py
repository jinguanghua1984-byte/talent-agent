"""导出 AI Infra V2 外联执行包并生成 P0/P1 抽检报告。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.maimai_url import sanitize_maimai_profile_url


QUEUE_KEYS = ("P0", "P1", "P2")
AUDIT_PRIORITIES = ("P0", "P1")
HARD_RISK_FLAGS = {
    "excluded_title",
    "excluded_education",
    "company_not_targeted",
    "school_not_priority",
    "age_over_40",
    "score_below_threshold",
    "missing_detail_for_detailed_score",
}
CSV_FIELDS = [
    "priority",
    "rank",
    "candidate_id",
    "name",
    "platform_id",
    "company",
    "title",
    "city",
    "work_years",
    "score",
    "grade",
    "recommendation_label",
    "directions",
    "key_evidence",
    "risk_summary",
    "suggested_outreach_angle",
    "profile_url",
]


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_text(path: str | Path, text: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8-sig")


def _join(value: Any, sep: str = "、") -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return sep.join(str(item) for item in value.values() if item not in (None, ""))
    if isinstance(value, (list, tuple, set)):
        return sep.join(str(item) for item in value if item not in (None, ""))
    return str(value)


def _shorten(value: Any, limit: int = 180) -> str:
    text = " ".join(_join(value, " ").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _queue_cards(outreach: dict[str, Any]) -> list[dict[str, Any]]:
    queues = outreach.get("priority_queues") if isinstance(outreach.get("priority_queues"), dict) else {}
    cards: list[dict[str, Any]] = []
    for priority in QUEUE_KEYS:
        items = queues.get(priority) if isinstance(queues.get(priority), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            card = dict(item)
            card["priority"] = priority
            cards.append(card)
    return cards


def _csv_row(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "priority": card.get("priority") or "",
        "rank": card.get("rank") or "",
        "candidate_id": card.get("candidate_id") or "",
        "name": card.get("name") or "",
        "platform_id": card.get("platform_id") or "",
        "company": card.get("company") or "",
        "title": card.get("title") or "",
        "city": card.get("city") or "",
        "work_years": card.get("work_years") or "",
        "score": card.get("score") or "",
        "grade": card.get("grade") or "",
        "recommendation_label": card.get("recommendation_label") or "",
        "directions": _join(card.get("directions")),
        "key_evidence": _join(card.get("key_evidence"), "；"),
        "risk_summary": card.get("risk_summary") or "",
        "suggested_outreach_angle": card.get("suggested_outreach_angle") or "",
        "profile_url": sanitize_maimai_profile_url(card.get("profile_url") or ""),
    }


def _write_csv(path: str | Path, cards: list[dict[str, Any]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for card in cards:
            writer.writerow(_csv_row(card))


def _card_issues(card: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    required_fields = {
        "platform_id": "missing_platform_id",
        "profile_url": "missing_profile_url",
        "company": "missing_company",
        "title": "missing_title",
        "suggested_outreach_angle": "missing_outreach_angle",
    }
    for field, issue in required_fields.items():
        if not card.get(field):
            issues.append(issue)
    if not card.get("directions"):
        issues.append("missing_directions")
    if not card.get("key_evidence"):
        issues.append("missing_key_evidence")
    hard_risks = [flag for flag in card.get("risk_flags") or [] if flag in HARD_RISK_FLAGS]
    if hard_risks:
        issues.append("hard_risk_flags:" + ",".join(hard_risks))
    if card.get("priority") == "P0" and card.get("recommendation_label") != "强推荐":
        issues.append("p0_not_strong_recommended")
    if card.get("priority") == "P1" and card.get("recommendation_label") not in {"强推荐", "推荐"}:
        issues.append("p1_not_recommended")
    return issues


def _audit_entry(card: dict[str, Any]) -> dict[str, Any]:
    issues = _card_issues(card)
    return {
        "rank": card.get("rank"),
        "candidate_id": card.get("candidate_id"),
        "name": card.get("name") or "",
        "priority": card.get("priority") or "",
        "company": card.get("company") or "",
        "title": card.get("title") or "",
        "score": card.get("score"),
        "recommendation_label": card.get("recommendation_label") or "",
        "directions": card.get("directions") or [],
        "platform_id": card.get("platform_id") or "",
        "profile_url": card.get("profile_url") or "",
        "evidence_count": len(card.get("key_evidence") or []),
        "key_evidence_preview": [_shorten(item, 120) for item in (card.get("key_evidence") or [])[:2]],
        "risk_flags": card.get("risk_flags") or [],
        "risk_summary": card.get("risk_summary") or "",
        "suggested_outreach_angle": card.get("suggested_outreach_angle") or "",
        "issues": issues,
        "audit_status": "needs_review" if issues else "ready",
    }


def _build_audit(outreach: dict[str, Any], audit_limit: int) -> dict[str, Any]:
    queues = outreach.get("priority_queues") if isinstance(outreach.get("priority_queues"), dict) else {}
    samples: dict[str, list[dict[str, Any]]] = {}
    issue_counter: Counter[str] = Counter()
    for priority in AUDIT_PRIORITIES:
        items = queues.get(priority) if isinstance(queues.get(priority), list) else []
        entries: list[dict[str, Any]] = []
        for item in items[:audit_limit]:
            if not isinstance(item, dict):
                continue
            card = dict(item)
            card["priority"] = priority
            entry = _audit_entry(card)
            entries.append(entry)
            issue_counter.update(entry["issues"])
        samples[priority] = entries

    duplicate_ids = _duplicates(
        [
            item.get("candidate_id")
            for priority in QUEUE_KEYS
            for item in (queues.get(priority) or [])
            if isinstance(item, dict)
        ]
    )
    if duplicate_ids:
        issue_counter["duplicate_candidate_id"] += len(duplicate_ids)

    return {
        "metadata": {
            "export_type": "maimai_ai_infra_outreach_quality_audit",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "audit_priorities": list(AUDIT_PRIORITIES),
            "audit_limit_per_priority": audit_limit,
        },
        "sample_counts": {priority: len(samples.get(priority, [])) for priority in AUDIT_PRIORITIES},
        "issue_counts": dict(issue_counter),
        "duplicate_candidate_ids": duplicate_ids,
        "samples": samples,
    }


def _duplicates(values: list[Any]) -> list[Any]:
    seen: set[Any] = set()
    duplicates: list[Any] = []
    for value in values:
        if value in (None, ""):
            continue
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _md_cell(value: Any, limit: int = 120) -> str:
    return _shorten(value, limit).replace("|", "/")


def _write_queue_md(path: str | Path, cards: list[dict[str, Any]], queue_counts: dict[str, Any]) -> None:
    lines = [
        "# AI Infra V2 外联执行队列",
        "",
        f"- P0: {queue_counts.get('P0', 0)}",
        f"- P1: {queue_counts.get('P1', 0)}",
        f"- P2: {queue_counts.get('P2', 0)}",
        "",
    ]
    by_priority: dict[str, list[dict[str, Any]]] = {priority: [] for priority in QUEUE_KEYS}
    for card in cards:
        by_priority.setdefault(str(card.get("priority") or ""), []).append(card)

    for priority in QUEUE_KEYS:
        lines.extend(
            [
                f"## {priority}",
                "",
                "| Rank | ID | 姓名 | 公司 | 职位 | 分数 | 方向 | 风险 | 建议切入 | URL |",
                "|---:|---:|---|---|---|---:|---|---|---|---|",
            ]
        )
        for card in by_priority.get(priority, []):
            lines.append(
                f"| {card.get('rank', '')} | {card.get('candidate_id', '')} | "
                f"{_md_cell(card.get('name'), 40)} | {_md_cell(card.get('company'), 60)} | "
                f"{_md_cell(card.get('title'), 70)} | {card.get('score', '')} | "
                f"{_md_cell(card.get('directions'), 80)} | {_md_cell(card.get('risk_summary'), 80)} | "
                f"{_md_cell(card.get('suggested_outreach_angle'), 140)} | {card.get('profile_url') or ''} |"
            )
        lines.append("")
    _write_text(path, "\n".join(lines))


def _write_audit_md(path: str | Path, audit: dict[str, Any]) -> None:
    lines = [
        "# AI Infra V2 P0/P1 抽检报告",
        "",
        f"- P0 抽检: {audit['sample_counts'].get('P0', 0)}",
        f"- P1 抽检: {audit['sample_counts'].get('P1', 0)}",
        f"- 问题计数: {audit['issue_counts'] or {}}",
        f"- 重复 candidate_id: {audit['duplicate_candidate_ids'] or []}",
        "",
    ]
    for priority in AUDIT_PRIORITIES:
        lines.extend([
            f"## {priority}",
            "",
            "| Rank | ID | 姓名 | 公司 | 职位 | 分数 | 状态 | 问题 | 证据预览 |",
            "|---:|---:|---|---|---|---:|---|---|---|",
        ])
        for item in audit["samples"].get(priority, []):
            lines.append(
                f"| {item.get('rank', '')} | {item.get('candidate_id', '')} | "
                f"{_md_cell(item.get('name'), 40)} | {_md_cell(item.get('company'), 60)} | "
                f"{_md_cell(item.get('title'), 70)} | {item.get('score', '')} | "
                f"{item.get('audit_status', '')} | {_md_cell(item.get('issues'), 120)} | "
                f"{_md_cell(item.get('key_evidence_preview'), 160)} |"
            )
        lines.append("")
    _write_text(path, "\n".join(lines))


def export_outreach_package(
    outreach_json_path: str | Path,
    out_csv: str | Path,
    out_md: str | Path,
    out_audit_json: str | Path,
    out_audit_md: str | Path,
    audit_limit: int = 30,
) -> dict[str, Any]:
    outreach = _load_json(outreach_json_path)
    cards = _queue_cards(outreach)
    audit = _build_audit(outreach, audit_limit=audit_limit)

    _write_csv(out_csv, cards)
    _write_queue_md(out_md, cards, outreach.get("queue_counts") or {})
    _write_json(out_audit_json, audit)
    _write_audit_md(out_audit_md, audit)

    return {
        "metadata": {
            "export_type": "maimai_ai_infra_outreach_execution_package",
            "source_file": str(outreach_json_path),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "exported_rows": len(cards),
        "queue_counts": outreach.get("queue_counts") or {},
        "output_files": {
            "csv": str(out_csv),
            "markdown": str(out_md),
            "audit_json": str(out_audit_json),
            "audit_markdown": str(out_audit_md),
        },
        "audit": audit,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 AI Infra V2 外联执行包")
    parser.add_argument("--outreach-json", required=True)
    parser.add_argument("--out-csv", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--out-audit-json", required=True)
    parser.add_argument("--out-audit-md", required=True)
    parser.add_argument("--audit-limit", type=int, default=30)
    args = parser.parse_args(argv)

    result = export_outreach_package(
        outreach_json_path=args.outreach_json,
        out_csv=args.out_csv,
        out_md=args.out_md,
        out_audit_json=args.out_audit_json,
        out_audit_md=args.out_audit_md,
        audit_limit=args.audit_limit,
    )
    audit = result["audit"]
    print(
        "status=ready rows={rows} p0_sample={p0} p1_sample={p1} issues={issues}".format(
            rows=result["exported_rows"],
            p0=audit["sample_counts"].get("P0", 0),
            p1=audit["sample_counts"].get("P1", 0),
            issues=sum(audit["issue_counts"].values()),
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
