"""猎聘 Campaign DB 本地摘要报告。

只读 campaign-local `talent.db`，不生成推荐、外联或飞书交付。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402


SUMMARY_SCHEMA = "liepin_campaign_summary_v1"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _connect_readonly(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise RuntimeError("campaign db does not exist; run import-search-apply first")
    uri = f"file:{db_path.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scalar(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0) if row is not None else 0


def _top_values(conn: sqlite3.Connection, field: str, limit: int = 10) -> list[dict[str, Any]]:
    allowed = {
        "city",
        "education",
        "current_company",
        "current_title",
        "data_level",
    }
    if field not in allowed:
        raise ValueError(f"unsupported summary field: {field}")
    rows = conn.execute(
        f"""
        SELECT COALESCE(NULLIF(TRIM({field}), ''), 'unknown') AS value, COUNT(*) AS count
        FROM candidates
        GROUP BY value
        ORDER BY count DESC, value ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{"value": row["value"], "count": int(row["count"])} for row in rows]


def _count_map(items: list[dict[str, Any]]) -> dict[str, int]:
    return {str(item["value"]): int(item["count"]) for item in items}


def _work_year_buckets(conn: sqlite3.Connection) -> dict[str, int]:
    buckets = {
        "0-3": _scalar(conn, "SELECT COUNT(*) FROM candidates WHERE work_years BETWEEN 0 AND 3"),
        "4-7": _scalar(conn, "SELECT COUNT(*) FROM candidates WHERE work_years BETWEEN 4 AND 7"),
        "8-10": _scalar(conn, "SELECT COUNT(*) FROM candidates WHERE work_years BETWEEN 8 AND 10"),
        "11+": _scalar(conn, "SELECT COUNT(*) FROM candidates WHERE work_years >= 11"),
        "unknown": _scalar(conn, "SELECT COUNT(*) FROM candidates WHERE work_years IS NULL"),
    }
    return buckets


def _detail_quality(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        "with_work_experience": _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM candidate_details
            WHERE work_experience IS NOT NULL
              AND work_experience != 'null'
              AND work_experience != '[]'
            """,
        ),
        "with_education_experience": _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM candidate_details
            WHERE education_experience IS NOT NULL
              AND education_experience != 'null'
              AND education_experience != '[]'
            """,
        ),
        "with_project_experience": _scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM candidate_details
            WHERE project_experience IS NOT NULL
              AND project_experience != 'null'
              AND project_experience != '[]'
            """,
        ),
    }


def build_campaign_summary(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    db_path = paths.root / "talent.db"
    conn = _connect_readonly(db_path)
    try:
        candidate_count = _scalar(conn, "SELECT COUNT(*) FROM candidates")
        source_profile_count = _scalar(conn, "SELECT COUNT(*) FROM source_profiles WHERE platform='liepin'")
        detail_count = _scalar(conn, "SELECT COUNT(*) FROM candidate_details")
        data_level_counts = _count_map(_top_values(conn, "data_level", limit=20))
        summary = {
            "schema": SUMMARY_SCHEMA,
            "campaign_id": paths.campaign_id,
            "campaign_db": "talent.db",
            "candidate_count": candidate_count,
            "source_profile_count": source_profile_count,
            "detail_count": detail_count,
            "detail_coverage_ratio": (detail_count / candidate_count) if candidate_count else 0,
            "data_level_counts": data_level_counts,
            "city_top": _top_values(conn, "city"),
            "education_top": _top_values(conn, "education"),
            "current_company_top": _top_values(conn, "current_company"),
            "current_title_top": _top_values(conn, "current_title"),
            "work_year_buckets": _work_year_buckets(conn),
            "detail_quality": _detail_quality(conn),
            "no_main_db_write": True,
            "no_recommendation_report": True,
            "no_outreach_queue": True,
            "no_feishu_delivery": True,
            "generatedAt": _now(),
        }
        return summary
    finally:
        conn.close()


def _format_top(items: list[dict[str, Any]]) -> str:
    if not items:
        return "- 无"
    return "\n".join(f"- {item['value']}：{item['count']}" for item in items)


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# 猎聘 Campaign DB 本地摘要",
        "",
        f"- campaign：{summary['campaign_id']}",
        f"- 候选人数：{summary['candidate_count']}",
        f"- 来源档案数：{summary['source_profile_count']}",
        f"- 详情数：{summary['detail_count']}",
        f"- 详情覆盖率：{summary['detail_coverage_ratio']:.2%}",
        "- 说明：本报告不是推荐报告，不生成外联队列，不发布飞书。",
        "",
        "## 数据层级",
        "",
    ]
    for level, count in summary["data_level_counts"].items():
        lines.append(f"- {level}：{count}")
    lines.extend([
        "",
        "## 城市分布",
        "",
        _format_top(summary["city_top"]),
        "",
        "## 学历分布",
        "",
        _format_top(summary["education_top"]),
        "",
        "## 工作年限",
        "",
    ])
    for bucket, count in summary["work_year_buckets"].items():
        lines.append(f"- {bucket}：{count}")
    lines.extend([
        "",
        "## 公司 Top",
        "",
        _format_top(summary["current_company_top"]),
        "",
        "## 职位 Top",
        "",
        _format_top(summary["current_title_top"]),
        "",
        "## 详情质量",
        "",
    ])
    for key, count in summary["detail_quality"].items():
        lines.append(f"- {key}：{count}")
    lines.append("")
    return "\n".join(lines)


def write_campaign_summary(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    summary = build_campaign_summary(paths.root)
    atomic_write_json(paths.reports_dir / "campaign-summary.json", summary)
    (paths.reports_dir / "campaign-summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成猎聘 Campaign DB 本地摘要。")
    parser.add_argument("--campaign-root", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        summary = write_campaign_summary(args.campaign_root)
    except (OSError, RuntimeError, ValueError, sqlite3.Error, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
