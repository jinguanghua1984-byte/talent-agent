"""猎聘候选池离线诊断。

只读取已标准化的候选摘要，生成分布统计和详情抓取优先级预览。
不发起猎聘请求，不抓详情，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402


REPORT_SCHEMA = "liepin_candidate_pool_diagnostic_v1"
PRIORITIES = ("detail_p0", "detail_p1", "detail_p2", "skip")
REPORT_JSON_NAME = "candidate-pool-diagnostic.json"
REPORT_MD_NAME = "candidate-pool-diagnostic.md"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError("candidate summaries do not exist; run standardize first")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            value = json.loads(stripped)
            if not isinstance(value, dict):
                raise ValueError(f"candidate summary line {line_number} must be an object")
            rows.append(value)
    return rows


def _counter_dict(counter: Counter[str], limit: int | None = None) -> dict[str, int]:
    items = counter.most_common(limit)
    return {key: count for key, count in items}


def _work_year_bucket(value: Any) -> str:
    if type(value) is not int:
        return "unknown"
    if value <= 5:
        return "0-5"
    if value <= 10:
        return "6-10"
    if value <= 15:
        return "11-15"
    if value <= 20:
        return "16-20"
    return "21+"


def _active_label(row: dict[str, Any]) -> str:
    active = row.get("active_status")
    if not isinstance(active, dict):
        return ""
    return str(active.get("name") or active.get("code") or "")


def _score_candidate(row: dict[str, Any]) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    title = str(row.get("current_title") or "")
    title_lower = title.lower()
    company = str(row.get("current_company") or "")
    education = str(row.get("education") or "")
    active = _active_label(row)
    active_lower = active.lower()
    work_years = row.get("work_years")

    weak_title = title.strip() in {"", "无", "学生", "实习生"}
    weak_company = company.strip() in {"", "无", "hh", "大学", "学校"}
    if weak_title:
        reasons.append("title_low_signal")
    if weak_company:
        reasons.append("company_low_signal")

    if "今天" in active or "在线" in active or active in {"1", "online"}:
        score += 25
        reasons.append("recently_active")
    elif "30天" in active or active in {"2", "3"}:
        score += 10
        reasons.append("recently_seen")

    if education in {"博士", "硕士", "MBA/EMBA"}:
        score += 15
        reasons.append("advanced_degree")
    elif education == "本科":
        score += 8
        reasons.append("bachelor_degree")

    if type(work_years) is int:
        if 3 <= work_years <= 10:
            score += 25
            reasons.append("target_work_years")
        elif 11 <= work_years <= 15:
            score += 20
            reasons.append("senior_work_years")
        elif 16 <= work_years <= 20:
            score += 10
            reasons.append("high_seniority")
        elif work_years > 20:
            score += 5
            reasons.append("very_high_seniority")

    title_keywords = (
        "ai",
        "人工智能",
        "算法",
        "产品",
        "技术",
        "研发",
        "软件",
        "架构",
        "工程",
        "数据",
        "机器学习",
        "专家",
        "负责人",
        "总监",
        "vp",
        "cto",
        "cio",
    )
    if any(keyword in title_lower or keyword in title for keyword in title_keywords):
        score += 25
        reasons.append("title_keyword_match")

    if not weak_company:
        score += 5
        reasons.append("company_present")

    if weak_title or (type(work_years) is int and work_years <= 1):
        priority = "skip"
    elif score >= 65:
        priority = "detail_p0"
    elif score >= 45:
        priority = "detail_p1"
    elif score >= 25:
        priority = "detail_p2"
    else:
        priority = "skip"

    if active_lower == "":  # keep this branch separate so empty status remains visible.
        reasons.append("missing_active_status")

    return {
        "priority": priority,
        "score": score,
        "reasons": reasons,
    }


def _sample_from_row(row: dict[str, Any], scoring: dict[str, Any]) -> dict[str, Any]:
    raw_ref = row.get("raw_ref") if isinstance(row.get("raw_ref"), dict) else {}
    return {
        "platform_id": str(row.get("platform_id") or ""),
        "display_name": str(row.get("display_name") or ""),
        "current_company": str(row.get("current_company") or ""),
        "current_title": str(row.get("current_title") or ""),
        "city": str(row.get("city") or ""),
        "education": str(row.get("education") or ""),
        "work_years": row.get("work_years"),
        "active_status": _active_label(row),
        "search_page": str(raw_ref.get("search_page") or ""),
        "card_index": raw_ref.get("card_index"),
        "priority": scoring["priority"],
        "score": scoring["score"],
        "reasons": scoring["reasons"],
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 猎聘候选池离线诊断",
        "",
        f"- 候选总数：{report['candidate_count']}",
        f"- 唯一候选：{report['unique_candidate_count']}",
        f"- 重复候选：{report['duplicate_candidate_count']}",
        f"- 扫描页数：{len(report['page_distribution'])}",
        "",
        "## 详情优先级预览",
        "",
    ]
    for priority in PRIORITIES:
        lines.append(f"- {priority}：{report['priority_counts'].get(priority, 0)}")
    lines.extend(["", "## 分布摘要", ""])
    for title, key in (
        ("页分布", "page_distribution"),
        ("活跃度", "active_status_distribution"),
        ("学历", "education_distribution"),
        ("工龄", "work_year_distribution"),
    ):
        lines.append(f"### {title}")
        for name, count in report[key].items():
            lines.append(f"- {name or '未填'}：{count}")
        lines.append("")
    lines.append("## detail_p0 样本")
    for sample in report["samples"].get("detail_p0", [])[:10]:
        lines.append(
            "- "
            f"{sample['display_name']} | {sample['current_company']} | "
            f"{sample['current_title']} | {sample['education']} | "
            f"{sample['work_years']}年 | score={sample['score']}"
        )
    lines.append("")
    return "\n".join(lines)


def diagnose_candidate_pool(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    scoring_rows = [(row, _score_candidate(row)) for row in rows]
    platform_ids = [str(row.get("platform_id") or "") for row in rows if row.get("platform_id")]
    priority_counts = Counter(scoring["priority"] for _, scoring in scoring_rows)
    for priority in PRIORITIES:
        priority_counts.setdefault(priority, 0)

    samples: dict[str, list[dict[str, Any]]] = {priority: [] for priority in PRIORITIES}
    for row, scoring in sorted(scoring_rows, key=lambda item: item[1]["score"], reverse=True):
        bucket = scoring["priority"]
        if len(samples[bucket]) < 10:
            samples[bucket].append(_sample_from_row(row, scoring))

    report = {
        "schema": REPORT_SCHEMA,
        "campaign_root": paths.root.as_posix(),
        "generatedAt": _now(),
        "candidate_count": len(rows),
        "unique_candidate_count": len(set(platform_ids)),
        "duplicate_candidate_count": len(platform_ids) - len(set(platform_ids)),
        "priority_counts": {priority: priority_counts[priority] for priority in PRIORITIES},
        "page_distribution": _counter_dict(Counter(
            str((row.get("raw_ref") or {}).get("search_page") or "") for row in rows
        )),
        "active_status_distribution": _counter_dict(Counter(_active_label(row) for row in rows)),
        "education_distribution": _counter_dict(Counter(str(row.get("education") or "") for row in rows)),
        "work_year_distribution": _counter_dict(Counter(_work_year_bucket(row.get("work_years")) for row in rows)),
        "top_companies": _counter_dict(Counter(str(row.get("current_company") or "") for row in rows), limit=15),
        "top_titles": _counter_dict(Counter(str(row.get("current_title") or "") for row in rows), limit=15),
        "priority_rules": {
            "purpose": "detail_fetch_preview_only",
            "not_a_recommendation_report": True,
            "does_not_fetch_detail": True,
        },
        "samples": samples,
    }
    atomic_write_json(paths.reports_dir / REPORT_JSON_NAME, report)
    (paths.reports_dir / REPORT_MD_NAME).write_text(_build_markdown(report), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成猎聘候选池离线诊断报告。")
    parser.add_argument("--campaign-root", required=True)
    args = parser.parse_args(argv)
    try:
        report = diagnose_candidate_pool(args.campaign_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
