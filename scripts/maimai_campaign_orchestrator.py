from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RUN_POLICY: dict[str, Any] = {
    "allow_live_search": True,
    "allow_campaign_db_auto_apply_after_clean_dry_run": True,
    "allow_detail_live_after_health_ok": True,
    "allow_detail_campaign_db_auto_apply_after_clean_dry_run": True,
    "allow_main_db_write": False,
    "allow_feishu_delivery_publish": True,
    "daily_search_request_budget": 500,
    "search_wave_max_pages": 50,
    "detail_pack_max_contacts": 100,
    "detail_target_grades": ["A", "B"],
    "delivery_outputs": ["local_md", "csv", "feishu_doc", "feishu_base"],
    "notify_channel": "feishu_im",
    "notify_identity": "bot",
    "stop_on_platform_security_signal": True,
    "max_auto_retries": 3,
}


def count_search_requests(event: dict[str, Any]) -> int:
    if event.get("stage") != "search_live":
        return 0
    pages = event.get("pages")
    if pages is None or isinstance(pages, bool):
        return 0
    try:
        return max(0, int(pages))
    except (TypeError, ValueError):
        return 0


def _unit_pages(unit: dict[str, Any]) -> int:
    unit_id = str(unit.get("unit_id") or "<unknown>")
    if "max_pages" not in unit or unit["max_pages"] is None:
        return 1

    raw_pages = unit["max_pages"]
    if isinstance(raw_pages, bool):
        raise ValueError(f"unit {unit_id} max_pages must be a positive integer")
    if isinstance(raw_pages, int):
        pages = raw_pages
    elif isinstance(raw_pages, str):
        text = raw_pages.strip()
        if not re.fullmatch(r"[+-]?\d+", text):
            raise ValueError(f"unit {unit_id} max_pages must be a positive integer")
        pages = int(text)
    else:
        raise ValueError(f"unit {unit_id} max_pages must be a positive integer")

    if pages <= 0:
        raise ValueError(f"unit {unit_id} max_pages must be a positive integer")
    return pages


def split_search_units_into_live_waves(
    units: list[dict[str, Any]],
    max_pages: int,
    daily_budget: int,
    used_today: int = 0,
) -> list[dict[str, Any]]:
    max_pages = int(max_pages)
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    remaining_budget = max(0, int(daily_budget) - max(0, int(used_today)))
    waves: list[dict[str, Any]] = []
    current_batches: list[dict[str, Any]] = []
    current_pages = 0
    planned_pages = 0

    def flush_current() -> None:
        nonlocal current_batches, current_pages
        if not current_batches:
            return
        waves.append({
            "wave_id": f"search-wave-{len(waves) + 1:03d}",
            "page_count": current_pages,
            "batches": current_batches,
        })
        current_batches = []
        current_pages = 0

    for unit in units:
        pages = _unit_pages(unit)
        if pages > max_pages:
            raise ValueError(f"single unit exceeds max_pages: {unit.get('unit_id')}")
        if planned_pages + pages > remaining_budget:
            break
        if current_batches and current_pages + pages > max_pages:
            flush_current()

        batch = dict(unit)
        batch["start_page"] = 1
        batch["max_page"] = pages
        current_batches.append(batch)
        current_pages += pages
        planned_pages += pages

    flush_current()
    return waves


def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, data: Any) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def append_event(campaign_root: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    events = Path(campaign_root) / "state" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record["at"] = datetime.now().isoformat(timespec="seconds")
    with events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def write_stage_state(
    campaign_root: str | Path,
    stage: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    if extra:
        state.update(extra)
    write_json(Path(campaign_root) / "state" / "stage-state.json", state)
    append_event(campaign_root, state)
    return state


def _load_jsonl_objects(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    items: list[dict[str, Any]] = []
    for line_number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file} line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{file} line {line_number}: must be an object")
        items.append(item)
    return items


def build_wave_plan(
    campaign_root: str | Path,
    units: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
    used_today: int = 0,
) -> dict[str, Any]:
    run_policy = dict(policy or DEFAULT_RUN_POLICY)
    waves = split_search_units_into_live_waves(
        units,
        max_pages=int(run_policy["search_wave_max_pages"]),
        daily_budget=int(run_policy["daily_search_request_budget"]),
        used_today=used_today,
    )
    return {
        "campaign_root": Path(campaign_root).as_posix(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "used_today": used_today,
        "daily_search_request_budget": run_policy["daily_search_request_budget"],
        "search_wave_max_pages": run_policy["search_wave_max_pages"],
        "wave_count": len(waves),
        "page_count": sum(int(wave["page_count"]) for wave in waves),
        "waves": waves,
    }


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _cmd_status(args: argparse.Namespace) -> int:
    state = load_json(Path(args.campaign_root) / "state" / "stage-state.json", default={}) or {}
    _print_json(state)
    return 0


def _cmd_plan_waves(args: argparse.Namespace) -> int:
    units = _load_jsonl_objects(args.units)
    plan = build_wave_plan(args.campaign_root, units, policy=DEFAULT_RUN_POLICY)
    if args.out:
        write_json(args.out, plan)
    _print_json(plan)
    return 0


def _cmd_resume(args: argparse.Namespace) -> int:
    root = Path(args.campaign_root)
    continuation = load_json(root / "state" / "continuation-plan.json", default=None)
    if continuation is not None:
        _print_json(continuation)
        return 0
    state = load_json(root / "state" / "stage-state.json", default={}) or {}
    _print_json(state)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maimai campaign orchestrator dry skeleton")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--campaign-root", required=True)
    status.set_defaults(func=_cmd_status)

    plan_waves = subparsers.add_parser("plan-waves")
    plan_waves.add_argument("--campaign-root", required=True)
    plan_waves.add_argument("--units", required=True)
    plan_waves.add_argument("--out", default="")
    plan_waves.set_defaults(func=_cmd_plan_waves)

    resume = subparsers.add_parser("resume")
    resume.add_argument("--campaign-root", required=True)
    resume.set_defaults(func=_cmd_resume)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
