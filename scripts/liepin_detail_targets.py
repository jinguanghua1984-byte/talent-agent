"""猎聘详情 smoke 目标包规划。

只读取已标准化的候选摘要并生成小批详情目标包。
不发起猎聘请求，不连接 CDP，不写 Campaign DB 或主库。
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
from scripts.liepin_candidate_pool_diagnostic import _score_candidate  # noqa: E402


TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
PACK_ID = "liepin-detail-p0-smoke-001"
DEFAULT_PRIORITY = "detail_p0"
DEFAULT_LIMIT = 10
MAX_LIMIT = 20


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


def _raw_ref(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("raw_ref")
    if not isinstance(value, dict):
        return {}
    return {
        "search_page": value.get("search_page"),
        "card_index": value.get("card_index"),
    }


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("platform_id", "user_id_encode", "profile_url"):
        if not str(row.get(field) or "").strip():
            missing.append(field)
    return missing


def _contact_from_row(
    index: int,
    row: dict[str, Any],
    *,
    priority: str,
    score: int,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "index": index,
        "platform": "liepin",
        "platform_id": str(row.get("platform_id") or ""),
        "user_id_encode": str(row.get("user_id_encode") or ""),
        "profile_url": str(row.get("profile_url") or ""),
        "display_name": str(row.get("display_name") or ""),
        "current_company": str(row.get("current_company") or ""),
        "current_title": str(row.get("current_title") or ""),
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "raw_ref": _raw_ref(row),
    }


def _public_sample(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform_id": contact["platform_id"],
        "display_name": contact["display_name"],
        "current_company": contact["current_company"],
        "current_title": contact["current_title"],
        "priority": contact["priority"],
        "score": contact["score"],
        "raw_ref": contact["raw_ref"],
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 猎聘详情 smoke 目标包",
        "",
        f"- 目标优先级：{report['priority']}",
        f"- 选择候选：{report['selected_count']}",
        f"- 跳过候选：{report['skipped_count']}",
        f"- target pack：{report['target_pack']}",
        "",
        "## 样本",
    ]
    for sample in report["samples"]:
        lines.append(
            "- "
            f"{sample['display_name']} | {sample['current_company']} | "
            f"{sample['current_title']} | score={sample['score']}"
        )
    lines.append("")
    return "\n".join(lines)


def plan_detail_smoke_targets(
    campaign_root: str | Path,
    *,
    priority: str = DEFAULT_PRIORITY,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    if priority != DEFAULT_PRIORITY:
        raise ValueError("only detail_p0 is supported for Liepin detail smoke")
    if type(limit) is not int or limit < 1 or limit > MAX_LIMIT:
        raise ValueError("limit must be between 1 and 20")

    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows):
        scoring = _score_candidate(row)
        row_priority = str(scoring["priority"])
        missing = _missing_fields(row)
        platform_id = str(row.get("platform_id") or "")
        if row_priority != priority:
            skipped.append(
                {
                    "row_index": row_index,
                    "platform_id": platform_id,
                    "reason": f"priority_{row_priority}",
                }
            )
            continue
        if missing:
            skipped.append(
                {
                    "row_index": row_index,
                    "platform_id": platform_id,
                    "reason": "missing_required_fields",
                    "missing_fields": missing,
                }
            )
            continue
        if len(selected) >= limit:
            skipped.append(
                {
                    "row_index": row_index,
                    "platform_id": platform_id,
                    "reason": "limit_exceeded",
                }
            )
            continue
        selected.append(
            _contact_from_row(
                len(selected),
                row,
                priority=priority,
                score=int(scoring["score"]),
                reasons=[str(reason) for reason in scoring["reasons"]],
            )
        )

    pack_path = paths.raw_dir / "detail-targets" / f"{PACK_ID}.json"
    pack = {
        "schema": TARGET_SCHEMA,
        "metadata": {
            "export_type": "liepin_detail_smoke_targets",
            "campaign_id": paths.campaign_id,
            "pack_id": PACK_ID,
            "source_priority": priority,
            "limit": limit,
            "created_at": _now(),
            "no_database_write": True,
        },
        "contacts": selected,
    }
    atomic_write_json(pack_path, pack)

    report = {
        "schema": TARGET_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": PACK_ID,
        "priority": priority,
        "limit": limit,
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "target_pack": pack_path.relative_to(paths.root).as_posix(),
        "skipped": skipped[:50],
        "samples": [_public_sample(contact) for contact in selected[:10]],
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-smoke-targets.json", report)
    (paths.reports_dir / "detail-smoke-targets.md").write_text(_build_markdown(report), encoding="utf-8")
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成猎聘详情 smoke 目标包。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--priority", default=DEFAULT_PRIORITY)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = plan_detail_smoke_targets(
            args.campaign_root,
            priority=args.priority,
            limit=args.limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
