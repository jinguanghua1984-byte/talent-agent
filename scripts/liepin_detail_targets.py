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
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_candidate_pool_diagnostic import _score_candidate  # noqa: E402
from scripts.liepin_detail_live_gate import TERMINAL_DETAIL_JOB_STATUSES  # noqa: E402


TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
PACK_PLAN_SCHEMA = "liepin_detail_pack_plan_v1"
PACK_ID = "liepin-detail-p0-smoke-001"
DEFAULT_PRIORITY = "detail_p0"
DEFAULT_LIMIT = 10
MAX_LIMIT = 20
DEDUPE_KEY = "platform_id"
VALID_PRIORITIES = {"detail_p0", "detail_p1", "detail_p2"}
SENSITIVE_SEARCH_PAGE_MARKERS = (
    "showresumedetail",
    "liepin.com",
    "/resume/showresumedetail",
    "ckid",
    "skid",
    "fkid",
    "ck_id",
    "sk_id",
    "fk_id",
)


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
    raw_ref = {
        "search_page": _sanitize_search_page(value.get("search_page")),
        "card_index": value.get("card_index"),
    }
    for key in ("wave_id", "unit_id"):
        text = str(value.get(key) or "").strip()
        if text:
            raw_ref[key] = text
    return raw_ref


def _sanitize_search_page(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text_lower = text.lower()
    if any(marker in text_lower for marker in SENSITIVE_SEARCH_PAGE_MARKERS):
        return "redacted-search-page"
    without_query = text.split("?", 1)[0].split("#", 1)[0]
    parsed = urlparse(without_query)
    if parsed.scheme or parsed.netloc:
        return "redacted-search-page"
    path = parsed.path if parsed.scheme or parsed.netloc else without_query
    normalized = path.rstrip("/")
    if not normalized:
        return ""
    return normalized


def _required_field(row: dict[str, Any], field: str) -> str:
    return str(row.get(field) or "").strip()


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for field in ("platform_id", "user_id_encode", "profile_url"):
        if not _required_field(row, field):
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
        "platform_id": _required_field(row, "platform_id"),
        "user_id_encode": _required_field(row, "user_id_encode"),
        "profile_url": _required_field(row, "profile_url"),
        "display_name": str(row.get("display_name") or ""),
        "current_company": str(row.get("current_company") or ""),
        "current_title": str(row.get("current_title") or ""),
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "raw_ref": _raw_ref(row),
    }


def _selection_sort_key(item: dict[str, Any]) -> tuple[int, int, str]:
    return (
        -int(item["score"]),
        int(item["group_index"]),
        str(item["platform_id"]),
    )


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


def _terminal_completed_platform_ids(paths: Any) -> set[str]:
    completed: set[str] = set()
    detail_live = paths.raw_dir / "detail-live"
    for raw_path in detail_live.glob("*/job-*.json"):
        try:
            payload = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("status") not in TERMINAL_DETAIL_JOB_STATUSES:
            continue
        platform_id = _required_field(payload, "platform_id")
        if platform_id:
            completed.add(platform_id)
    return completed


def _split_csv_priorities(value: str) -> list[str]:
    priorities = [item.strip() for item in value.split(",") if item.strip()]
    if not priorities:
        raise ValueError("at least one priority is required")
    invalid = [priority for priority in priorities if priority not in VALID_PRIORITIES]
    if invalid:
        raise ValueError(f"unsupported priorities: {', '.join(invalid)}")
    return priorities


def _select_detail_contacts(
    rows: list[dict[str, Any]],
    *,
    priorities: list[str],
    completed_platform_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    skipped: list[dict[str, Any]] = []
    best_by_platform_id: dict[str, dict[str, Any]] = {}
    priority_order = {priority: index for index, priority in enumerate(priorities)}

    for row_index, row in enumerate(rows):
        scoring = _score_candidate(row)
        row_priority = str(scoring["priority"])
        platform_id = _required_field(row, "platform_id")
        missing = _missing_fields(row)
        if row_priority not in priority_order:
            skipped.append({"row_index": row_index, "platform_id": platform_id, "reason": f"priority_{row_priority}"})
            continue
        if platform_id in completed_platform_ids:
            skipped.append({"row_index": row_index, "platform_id": platform_id, "reason": "already_terminal"})
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

        contact = _contact_from_row(
            row_index,
            row,
            priority=row_priority,
            score=int(scoring["score"]),
            reasons=[str(reason) for reason in scoring["reasons"]],
        )
        contact["row_index"] = row_index
        contact["group_index"] = row_index
        existing = best_by_platform_id.get(platform_id)
        if existing is None:
            best_by_platform_id[platform_id] = contact
            continue
        contact["group_index"] = existing["group_index"]
        current_key = (
            priority_order[str(existing["priority"])],
            -int(existing["score"]),
            int(existing["row_index"]),
        )
        new_key = (
            priority_order[str(contact["priority"])],
            -int(contact["score"]),
            int(contact["row_index"]),
        )
        if new_key < current_key:
            best_by_platform_id[platform_id] = contact
            skipped.append(
                {
                    "row_index": existing["row_index"],
                    "platform_id": platform_id,
                    "reason": "duplicate_platform_id",
                    "kept_row_index": row_index,
                }
            )
        else:
            skipped.append(
                {
                    "row_index": row_index,
                    "platform_id": platform_id,
                    "reason": "duplicate_platform_id",
                    "kept_row_index": existing["row_index"],
                }
            )

    selected = sorted(
        best_by_platform_id.values(),
        key=lambda item: (
            priority_order[str(item["priority"])],
            -int(item["score"]),
            int(item["group_index"]),
            str(item["platform_id"]),
        ),
    )
    for index, contact in enumerate(selected):
        contact["index"] = index
    return selected, skipped


def _public_contact(contact: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in contact.items() if key not in {"row_index", "group_index"}}


def _write_pack(paths: Any, pack_id: str, contacts: list[dict[str, Any]], metadata: dict[str, Any]) -> Path:
    pack_path = paths.raw_dir / "detail-targets" / f"{pack_id}.json"
    atomic_write_json(
        pack_path,
        {
            "schema": PACK_PLAN_SCHEMA,
            "metadata": metadata,
            "contacts": [_public_contact(contact) for contact in contacts],
        },
    )
    return pack_path


def _pack_plan_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 猎聘 full detail pack planning",
        "",
        f"- scope：{report['scope']}",
        f"- priorities：{', '.join(report['priorities'])}",
        f"- selected：{report['selected_count']}",
        f"- excluded completed：{report['excluded_completed_count']}",
        f"- pack count：{report['pack_count']}",
        f"- no live request：{str(report['no_live_request']).lower()}",
        f"- no database write：{str(report['no_database_write']).lower()}",
        "",
        "## Priority counts",
    ]
    for priority, count in report["priority_counts"].items():
        lines.append(f"- {priority}：{count}")
    lines.extend(["", "## Packs"])
    for pack in report["packs"]:
        lines.append(f"- {pack['pack_id']}：{pack['contact_count']} -> {pack['path']}")
    lines.append("")
    return "\n".join(lines)


def plan_detail_packs(
    campaign_root: str | Path,
    *,
    priorities: list[str] | None = None,
    pack_size: int = 100,
    scope: str = "p0-p1",
    exclude_completed: bool = True,
) -> dict[str, Any]:
    resolved_priorities = priorities or ["detail_p0", "detail_p1"]
    invalid = [priority for priority in resolved_priorities if priority not in VALID_PRIORITIES]
    if invalid:
        raise ValueError(f"unsupported priorities: {', '.join(invalid)}")
    if type(pack_size) is not int or pack_size < 1 or pack_size > 100:
        raise ValueError("pack_size must be between 1 and 100")

    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    completed_platform_ids = _terminal_completed_platform_ids(paths) if exclude_completed else set()
    selected, skipped = _select_detail_contacts(
        rows,
        priorities=resolved_priorities,
        completed_platform_ids=completed_platform_ids,
    )
    priority_counts = {priority: 0 for priority in resolved_priorities}
    for contact in selected:
        priority_counts[str(contact["priority"])] += 1

    scope_slug = scope.strip() or "detail"
    all_pack_id = f"detail-targets-{scope_slug}"
    base_metadata = {
        "export_type": "liepin_detail_pack_plan",
        "campaign_id": paths.campaign_id,
        "scope": scope_slug,
        "priorities": resolved_priorities,
        "pack_size": pack_size,
        "dedupe_key": DEDUPE_KEY,
        "exclude_completed": exclude_completed,
        "excluded_completed_count": len([item for item in skipped if item.get("reason") == "already_terminal"]),
        "selection_order": "priority_then_score_desc_group_index_asc_platform_id_asc",
        "created_at": _now(),
        "no_live_request": True,
        "no_database_write": True,
    }
    all_targets_path = _write_pack(paths, all_pack_id, selected, {**base_metadata, "pack_id": all_pack_id})

    packs: list[dict[str, Any]] = []
    for pack_index, start in enumerate(range(0, len(selected), pack_size), start=1):
        contacts = selected[start : start + pack_size]
        pack_id = f"detail-{scope_slug}-pack-{pack_index:03d}"
        pack_path = _write_pack(
            paths,
            pack_id,
            contacts,
            {
                **base_metadata,
                "pack_id": pack_id,
                "all_targets_path": all_targets_path.relative_to(paths.root).as_posix(),
                "pack_index": pack_index,
            },
        )
        packs.append(
            {
                "pack_id": pack_id,
                "path": pack_path.relative_to(paths.root).as_posix(),
                "contact_count": len(contacts),
                "start_index": start,
                "end_index": start + len(contacts) - 1,
            }
        )

    report = {
        "schema": PACK_PLAN_SCHEMA,
        "campaign_id": paths.campaign_id,
        "scope": scope_slug,
        "priorities": resolved_priorities,
        "pack_size": pack_size,
        "selected_count": len(selected),
        "excluded_completed_count": base_metadata["excluded_completed_count"],
        "skipped_count": len(skipped),
        "priority_counts": priority_counts,
        "pack_count": len(packs),
        "all_targets_path": all_targets_path.relative_to(paths.root).as_posix(),
        "packs": packs,
        "skipped": skipped,
        "samples": [_public_sample(contact) for contact in selected[:10]],
        "no_live_request": True,
        "no_database_write": True,
        "no_main_db_write": True,
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-pack-plan.json", report)
    (paths.reports_dir / "detail-pack-plan.md").write_text(_pack_plan_markdown(report), encoding="utf-8")
    return report


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
    skipped: list[dict[str, Any]] = []
    best_by_platform_id: dict[str, dict[str, Any]] = {}

    for row_index, row in enumerate(rows):
        scoring = _score_candidate(row)
        row_priority = str(scoring["priority"])
        missing = _missing_fields(row)
        platform_id = _required_field(row, "platform_id")
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

        candidate = _contact_from_row(
            row_index,
            row,
            priority=priority,
            score=int(scoring["score"]),
            reasons=[str(reason) for reason in scoring["reasons"]],
        )
        candidate["row_index"] = row_index
        existing = best_by_platform_id.get(platform_id)
        if existing is None:
            candidate["group_index"] = row_index
            best_by_platform_id[platform_id] = candidate
            continue

        candidate["group_index"] = existing["group_index"]
        if int(candidate["score"]) > int(existing["score"]):
            best_by_platform_id[platform_id] = candidate
            skipped.append(
                {
                    "row_index": existing["row_index"],
                    "platform_id": platform_id,
                    "reason": "duplicate_platform_id",
                    "kept_row_index": row_index,
                }
            )
        else:
            skipped.append(
                {
                    "row_index": row_index,
                    "platform_id": platform_id,
                    "reason": "duplicate_platform_id",
                    "kept_row_index": existing["row_index"],
                }
            )

    ranked = sorted(best_by_platform_id.values(), key=_selection_sort_key)
    selected = ranked[:limit]
    for index, contact in enumerate(selected):
        contact["index"] = index
    for contact in ranked[limit:]:
        skipped.append(
            {
                "row_index": contact["row_index"],
                "platform_id": contact["platform_id"],
                "reason": "limit_exceeded",
            }
        )

    pack_path = paths.raw_dir / "detail-targets" / f"{PACK_ID}.json"
    pack = {
        "schema": TARGET_SCHEMA,
        "metadata": {
            "export_type": "liepin_detail_smoke_targets",
            "campaign_id": paths.campaign_id,
            "pack_id": PACK_ID,
            "source_priority": priority,
            "dedupe_key": DEDUPE_KEY,
            "selection_order": "score_desc_group_index_asc_platform_id_asc",
            "limit": limit,
            "created_at": _now(),
            "no_database_write": True,
        },
        "contacts": [
            {key: value for key, value in contact.items() if key not in {"row_index", "group_index"}}
            for contact in selected
        ],
    }
    atomic_write_json(pack_path, pack)

    report = {
        "schema": TARGET_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": PACK_ID,
        "priority": priority,
        "dedupe_key": DEDUPE_KEY,
        "selection_order": "score_desc_group_index_asc_platform_id_asc",
        "limit": limit,
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "target_pack": pack_path.relative_to(paths.root).as_posix(),
        "skipped": skipped,
        "samples": [_public_sample(contact) for contact in selected[:10]],
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-smoke-targets.json", report)
    (paths.reports_dir / "detail-smoke-targets.md").write_text(_build_markdown(report), encoding="utf-8")
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成猎聘详情目标包。")
    subparsers = parser.add_subparsers(dest="command")
    smoke = subparsers.add_parser("smoke")
    smoke.add_argument("--campaign-root", required=True)
    smoke.add_argument("--priority", default=DEFAULT_PRIORITY)
    smoke.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    packs = subparsers.add_parser("packs")
    packs.add_argument("--campaign-root", required=True)
    packs.add_argument("--priorities", default="detail_p0,detail_p1")
    packs.add_argument("--pack-size", type=int, default=100)
    packs.add_argument("--scope", default="p0-p1")
    packs.add_argument("--include-completed", action="store_true")
    parser.add_argument("--campaign-root", required=False)
    parser.add_argument("--priority", default=DEFAULT_PRIORITY)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    parsed = parser.parse_args(argv)
    if parsed.command is None:
        if not parsed.campaign_root:
            parser.error("--campaign-root is required")
        parsed.command = "smoke"
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "smoke":
            result = plan_detail_smoke_targets(
                args.campaign_root,
                priority=args.priority,
                limit=args.limit,
            )
        elif args.command == "packs":
            result = plan_detail_packs(
                args.campaign_root,
                priorities=_split_csv_priorities(args.priorities),
                pack_size=args.pack_size,
                scope=args.scope,
                exclude_completed=not args.include_completed,
            )
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
