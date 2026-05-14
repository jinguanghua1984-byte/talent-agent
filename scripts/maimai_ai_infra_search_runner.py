"""脉脉 AI Infra 搜索执行器。

默认只执行请求模板 dry-run，不访问脉脉网络。真实浏览器执行必须先通过
Phase 0 小样本可行性门禁后再打开。
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.maimai_ai_infra_campaign import (
    CampaignPaths,
    ensure_campaign,
    load_completed_pages,
    mark_page_completed,
)


UNIT_ID_PATTERN = re.compile(r"^unit-\d{6}$")

DEFAULT_TEMPLATE = {
    "search": {
        "query": "",
        "search_query": "",
        "positions": "",
        "allcompanies": "",
        "degrees": "",
        "degrees_min": "",
        "degrees_max": "",
        "only_bachelor_degree": 0,
        "min_only_bachelor_degree": None,
        "max_only_bachelor_degree": None,
        "worktimes": "",
        "worktimes_min": "",
        "worktimes_max": "",
        "schools": "",
        "major": "",
        "min_age": "",
        "max_age": "",
        "query_relation": 0,
        "paginationParam": {"page": 1, "size": 30},
        "page": 0,
        "size": 30,
    }
}

CONFIRMED_SEARCH_FILTER_FIELDS = {
    "allcompanies",
    "degrees",
    "degrees_min",
    "degrees_max",
    "only_bachelor_degree",
    "min_only_bachelor_degree",
    "max_only_bachelor_degree",
    "positions",
    "worktimes",
    "worktimes_min",
    "worktimes_max",
    "min_age",
    "max_age",
    "schools",
    "major",
    "query_relation",
}


@dataclass(frozen=True)
class PageTask:
    unit_id: str
    page: int
    unit: dict[str, Any]


def iter_pending_page_tasks(paths: CampaignPaths, units: list[dict[str, Any]]) -> list[PageTask]:
    completed = load_completed_pages(paths)
    tasks: list[PageTask] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        for page in range(1, int(unit.get("max_pages") or 1) + 1):
            if (unit_id, page) not in completed:
                tasks.append(PageTask(unit_id=unit_id, page=page, unit=unit))
    return tasks


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _load_units_jsonl(path: Path) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    seen_unit_ids: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            unit = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"units JSONL line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(unit, dict):
            raise ValueError(f"units JSONL line {line_number}: must be an object")
        unit_id = unit.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id:
            raise ValueError(f"units JSONL line {line_number}: unit_id is required")
        if UNIT_ID_PATTERN.fullmatch(unit_id) is None:
            raise ValueError(f"units JSONL line {line_number}: unit_id must match unit-\\d{{6}}")
        if unit_id in seen_unit_ids:
            raise ValueError(f"units JSONL line {line_number}: duplicate unit_id {unit_id}")
        seen_unit_ids.add(unit_id)
        units.append(unit)
    return units


def normalize_confirmed_search_filters(filters: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(filters, dict):
        raise ValueError("search_filters must be an object")

    normalized: dict[str, Any] = {}
    for field, value in filters.items():
        field_name = str(field)
        if field_name.startswith("search."):
            field_name = field_name.removeprefix("search.")
        if field_name not in CONFIRMED_SEARCH_FILTER_FIELDS:
            raise ValueError(f"unconfirmed search filter field: search.{field_name}")
        normalized[field_name] = value
    return normalized


def confirmed_search_filters_from_batch(batch: dict[str, Any]) -> dict[str, Any]:
    filters = batch.get("search_filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("search_filters must be an object")
    if "query_relation" in batch and "query_relation" not in filters:
        filters = {**filters, "query_relation": batch["query_relation"]}
    return normalize_confirmed_search_filters(filters)


def _apply_confirmed_search_filters(search: dict[str, Any], batch: dict[str, Any]) -> None:
    for field_name, value in confirmed_search_filters_from_batch(batch).items():
        if field_name in search:
            search[field_name] = value


def patch_search_body(template: dict[str, Any], batch: dict[str, Any], page: int) -> dict[str, Any]:
    if not isinstance(template, dict):
        raise ValueError("template body must be an object")
    body = copy.deepcopy(template)
    search = body.get("search")
    if not isinstance(search, dict):
        raise ValueError("search must be an object")

    query = str(batch.get("query") or "")
    page_size = int(batch.get("page_size") or search.get("size") or 30)
    search["query"] = query
    if "search_query" in search:
        search["search_query"] = query
    if "paginationParam" not in search or not isinstance(search["paginationParam"], dict):
        search["paginationParam"] = {}
    search["paginationParam"]["page"] = page
    search["paginationParam"]["size"] = page_size
    if "page" in search:
        search["page"] = max(page - 1, 0)
    if "size" in search:
        search["size"] = page_size
    _apply_confirmed_search_filters(search, batch)
    return body


def _load_template(path: str | None) -> dict[str, Any]:
    if not path:
        return copy.deepcopy(DEFAULT_TEMPLATE)
    data = _load_json(Path(path))
    if not isinstance(data, dict):
        raise ValueError("template must be a JSON object")
    return data


def build_dry_run_result(plan: dict[str, Any], template: dict[str, Any]) -> dict[str, Any]:
    batches = []
    for batch in plan.get("batches") or []:
        max_pages = int(batch.get("max_pages") or 1)
        patched_pages = [
            {"page": page, "body": patch_search_body(template, batch, page)}
            for page in range(1, max_pages + 1)
        ]
        batches.append({
            "batch_id": batch.get("batch_id"),
            "status": "dry-run-template-only",
            "pages_fetched": 0,
            "contacts": 0,
            "ab_stop_reason": "dry_run_template_only",
            "patched_pages": patched_pages,
        })
    return {
        "run_id": plan.get("run_id") or f"maimai-ai-infra-{datetime.now().date().isoformat()}",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "status": "dry-run-template-only",
        "execution_mode": "template_patch_only",
        "phase0": {
            "live_search_verified": False,
            "default_live_path": "extension_or_ui_passive_capture",
            "direct_cdp_fetch": "disabled_until_small_sample_verification",
        },
        "batches": batches,
        "contacts": [],
    }


def _batch_from_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": unit["unit_id"],
        "query": unit.get("query", ""),
        "page_size": unit.get("page_size", 30),
        "search_filters": unit.get("search_filters", {}),
        "query_relation": unit.get("search_filters", {}).get(
            "query_relation",
            unit.get("query_relation", 1),
        ),
    }


def build_page_task_dry_run(
    paths: CampaignPaths,
    unit: dict[str, Any],
    page: int,
    template: dict[str, Any],
) -> dict[str, Any]:
    return {
        "campaign_id": paths.campaign_id,
        "unit_id": unit["unit_id"],
        "wave_id": unit.get("wave_id", ""),
        "page": page,
        "status": "dry-run-template-only",
        "body": patch_search_body(template, _batch_from_unit(unit), page),
        "contacts": [],
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _validate_non_negative_limit(value: int | None, name: str, parser: argparse.ArgumentParser) -> None:
    if value is not None and value < 0:
        parser.error(f"{name} must be >= 0")


def _run_campaign_dry_run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if not args.campaign_root or not args.units:
        parser.error("campaign mode requires --campaign-root and --units")
    _validate_non_negative_limit(args.max_units, "--max-units", parser)
    _validate_non_negative_limit(args.max_pages, "--max-pages", parser)

    paths = ensure_campaign(args.campaign_root)
    units = _load_units_jsonl(Path(args.units))
    if args.wave:
        units = [unit for unit in units if unit.get("wave_id") == args.wave]
    if args.unit:
        units = [unit for unit in units if unit.get("unit_id") == args.unit]
    if args.max_units is not None:
        units = units[: args.max_units]

    pending_tasks = iter_pending_page_tasks(paths, units)
    selected_tasks = pending_tasks
    if args.max_pages is not None:
        selected_tasks = selected_tasks[: args.max_pages]

    template = _load_template(args.template)
    for task in selected_tasks:
        payload = build_page_task_dry_run(paths, task.unit, task.page, template)
        mark_page_completed(paths, task.unit_id, task.page, payload)

    if args.out:
        summary = {
            "campaign_id": paths.campaign_id,
            "status": "dry-run-template-only",
            "pages_written": len(selected_tasks),
            "units_seen": len(units),
            "tasks_pending": len(pending_tasks),
            "tasks_written": len(selected_tasks),
        }
        if args.max_runtime_minutes is not None:
            summary["max_runtime_minutes"] = args.max_runtime_minutes
        _write_json(Path(args.out), summary)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脉脉 AI Infra 搜索执行器")
    parser.add_argument("--plan")
    parser.add_argument("--out")
    parser.add_argument("--template")
    parser.add_argument("--dry-run-template-only", action="store_true")
    parser.add_argument("--campaign-root")
    parser.add_argument("--units")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="accepted for clarity; campaign dry-run always resumes from canonical raw pages",
    )
    parser.add_argument("--wave")
    parser.add_argument("--unit")
    parser.add_argument("--max-units", type=int)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument(
        "--max-runtime-minutes",
        type=int,
        help="campaign dry-run records this as summary metadata only",
    )
    args = parser.parse_args(argv)

    if not args.dry_run_template_only:
        raise RuntimeError(
            "live search is disabled until Phase 0 verifies extension/UI execution "
            "without logout, captcha, 403 or 429"
        )

    if args.campaign_root or args.units:
        return _run_campaign_dry_run(args, parser)

    if not args.plan or not args.out:
        parser.error("legacy mode requires --plan and --out")

    plan = _load_json(Path(args.plan))
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")

    template = _load_template(args.template)
    result = build_dry_run_result(plan, template)
    _write_json(Path(args.out), result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
