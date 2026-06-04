"""猎聘宽召回寻访摘要。

只读 adaptive 搜索、标准化、导入和 Campaign DB 摘要报告，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402


SUMMARY_SCHEMA = "liepin_broad_recall_summary_v1"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    return data if isinstance(data, dict) else {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _page_quality_rows(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((root / "reports").glob("page-quality-*.jsonl")):
        rows.extend(_read_jsonl(path))
    return rows


def _page_quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bands = {"good": 0, "observe": 0, "low": 0}
    total_candidates = 0
    detail_eligible = 0
    for row in rows:
        band = str(row.get("quality_band") or "")
        if band in bands:
            bands[band] += 1
        total_candidates += int(row.get("candidate_count") or 0)
        detail_eligible += int(row.get("detail_eligible_count") or 0)
    return {
        "total_pages": len(rows),
        "quality_bands": bands,
        "total_candidates_seen": total_candidates,
        "detail_eligible_count": detail_eligible,
    }


def _import_summary(root: Path) -> dict[str, Any]:
    reports = root / "reports"
    dry = _load_json(reports / "search-import-dry-run.json")
    apply = _load_json(reports / "search-import-apply.json")
    result: dict[str, Any] = {}
    if dry:
        result["dry_run"] = dry.get("result") if isinstance(dry.get("result"), dict) else {}
    if apply:
        result["apply"] = apply.get("result") if isinstance(apply.get("result"), dict) else {}
    return result


def _campaign_db_summary(root: Path) -> dict[str, Any]:
    summary = _load_json(root / "reports" / "campaign-summary.json")
    if not summary:
        return {}
    return {
        "candidate_count": int(summary.get("candidate_count") or 0),
        "source_profile_count": int(summary.get("source_profile_count") or 0),
        "detail_count": int(summary.get("detail_count") or 0),
        "detail_coverage_ratio": float(summary.get("detail_coverage_ratio") or 0),
    }


def build_broad_recall_summary(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    search_summary = _load_json(paths.search_summary_json)
    return {
        "schema": SUMMARY_SCHEMA,
        "campaign_id": paths.campaign_id,
        "campaign_root": paths.root.as_posix(),
        "generatedAt": _now(),
        "page_quality": _page_quality_summary(_page_quality_rows(paths.root)),
        "search_summary": {
            "source": search_summary.get("source") or "",
            "candidate_count": int(search_summary.get("candidate_count") or 0),
            "pages_scanned": int(search_summary.get("pages_scanned") or 0),
        },
        "search_import": _import_summary(paths.root),
        "campaign_db": _campaign_db_summary(paths.root),
        "no_main_db_write": True,
        "no_recommendation_report": True,
        "no_outreach_queue": True,
        "no_feishu_delivery": True,
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    quality = summary["page_quality"]
    campaign_db = summary.get("campaign_db") or {}
    lines = [
        "# 猎聘宽召回寻访摘要",
        "",
        f"- campaign：{summary['campaign_id']}",
        f"- 搜索页数：{quality['total_pages']}",
        f"- 列表候选人：{quality['total_candidates_seen']}",
        f"- 详情优先候选人：{quality['detail_eligible_count']}",
        f"- 标准化候选人：{summary['search_summary']['candidate_count']}",
        f"- Campaign DB 候选人：{campaign_db.get('candidate_count', 0)}",
        f"- Campaign DB 详情数：{campaign_db.get('detail_count', 0)}",
        "- 说明：本报告不是推荐报告，不生成外联队列，不发布飞书。",
        "",
        "## 页质分布",
        "",
    ]
    for band, count in quality["quality_bands"].items():
        lines.append(f"- {band}：{count}")
    lines.append("")
    return "\n".join(lines)


def write_broad_recall_summary(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    summary = build_broad_recall_summary(paths.root)
    atomic_write_json(paths.reports_dir / "broad-recall-summary.json", summary)
    (paths.reports_dir / "broad-recall-summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成猎聘宽召回寻访摘要。")
    parser.add_argument("--campaign-root", required=True)
    args = parser.parse_args(argv)
    try:
        summary = write_broad_recall_summary(args.campaign_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
