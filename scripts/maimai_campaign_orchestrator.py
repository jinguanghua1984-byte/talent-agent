from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass
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


def _command_entry(
    *,
    stage: str,
    argv: list[str],
    description: str,
    live_action: bool = False,
    requires_policy_gate: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "stage": stage,
        "argv": argv,
        "description": description,
        "live_action": live_action,
        "requires_policy_gate": requires_policy_gate,
    }
    if extra:
        entry.update(extra)
    return entry


def build_stage_command_plan(campaign_root: str, strategy: str, policy: dict[str, Any]) -> list[dict[str, Any]]:
    root = Path(campaign_root)
    pack_size = policy.get("detail_pack_max_contacts")
    if pack_size is None:
        pack_size = DEFAULT_RUN_POLICY["detail_pack_max_contacts"]

    search_plan = root / "search-plan.json"
    search_units = root / "search-units.jsonl"
    live_plan = root / "raw" / "search-live-runs" / "wave-plan.json"
    live_run = root / "raw" / "search-live-runs" / "run.json"
    campaign_db = root / "talent.db"
    continuation_plan = root / "state" / "continuation-plan.json"
    reports = root / "reports"

    commands = [
        _command_entry(
            stage="compile_search_plan",
            description="Generate search plan and search units from the confirmed strategy.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_ai_infra_search_plan",
                "--config",
                strategy,
                "--out",
                str(search_plan),
                "--out-units",
                str(search_units),
            ],
            extra={"produces": [str(search_plan), str(search_units)]},
        ),
        _command_entry(
            stage="plan_search_waves",
            description="Convert search units into the wave plan consumed by the live gate.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_campaign_orchestrator",
                "plan-waves",
                "--campaign-root",
                campaign_root,
                "--units",
                str(search_units),
                "--out",
                str(live_plan),
            ],
            extra={"consumes": [str(search_units)], "produces": [str(live_plan)]},
        ),
        _command_entry(
            stage="search_live",
            description="Run the controlled Maimai search live gate against an already-open CDP page.",
            live_action=True,
            requires_policy_gate="allow_live_search",
            argv=[
                "python",
                "-m",
                "scripts.maimai_ai_infra_search_live_gate",
                "--plan",
                str(live_plan),
                "--out",
                str(live_run),
                "--cdp-url",
                "http://127.0.0.1:9888",
            ],
            extra={"consumes": [str(live_plan)], "produces": [str(live_run)]},
        ),
        _command_entry(
            stage="standardize_search_live",
            description="Standardize the whole-run live output into canonical search raw files.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_search_live_standardize",
                "--campaign-root",
                campaign_root,
                "--run",
                str(live_run),
            ],
            extra={
                "consumes": [str(live_run)],
                "produces": [str(root / "raw" / "search" / "unit-*" / "page-*.json")],
            },
        ),
        _command_entry(
            stage="import_wave",
            description="Dry-run campaign import from canonical search raw files into the campaign DB path.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_ai_infra_pipeline",
                "run-campaign",
                "--campaign-root",
                campaign_root,
                "--config",
                strategy,
                "--wave",
                "wave-001",
                "--db",
                str(campaign_db),
            ],
        ),
        _command_entry(
            stage="list_rank",
            description="Rank list-stage candidates from the campaign DB.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_ai_infra_rank",
                "--db",
                str(campaign_db),
                "--config",
                strategy,
                "--mode",
                "list",
                "--out-json",
                str(reports / "list-rank.json"),
                "--out-md",
                str(reports / "list-rank.md"),
            ],
        ),
        _command_entry(
            stage="detail_pack",
            description="Build A/B detail target packs capped by policy.",
            argv=[
                "python",
                "-m",
                "scripts.maimai_ai_infra_detail_plan",
                "build-ab-packs",
                "--campaign-root",
                campaign_root,
                "--pack-size",
                str(pack_size),
            ],
        ),
    ]

    notify_chat_id = str(policy.get("notify_chat_id") or "").strip()
    notify_user_id = str(policy.get("notify_user_id") or "").strip()
    if notify_chat_id and notify_user_id:
        raise ValueError("notify_chat_id and notify_user_id are mutually exclusive")
    if notify_chat_id or notify_user_id:
        notify_argv = [
            "python",
            "-m",
            "scripts.campaign_notify",
            "--event",
            str(continuation_plan),
            "--identity",
            str(policy.get("notify_identity", DEFAULT_RUN_POLICY["notify_identity"])),
        ]
        if notify_chat_id:
            notify_argv.extend(["--chat-id", notify_chat_id])
        else:
            notify_argv.extend(["--user-id", notify_user_id])
        notify_argv.append("--dry-run")
        commands.append(
            _command_entry(
                stage="notify_blocked",
                description="Dry-run Feishu IM notification for blocked continuation events.",
                argv=notify_argv,
                extra={"consumes": [str(continuation_plan)]},
            )
        )
    else:
        commands.append(
            _command_entry(
                stage="notify_blocked",
                description="Notification command not constructed because policy has no notify target.",
                argv=[],
                extra={
                    "skipped": True,
                    "blocked_reason": "notify_target_missing",
                    "consumes": [str(continuation_plan)],
                },
            )
        )

    return commands


def build_stage_commands(campaign_root: str, strategy: str, policy: dict[str, Any]) -> list[list[str]]:
    return [
        list(command["argv"])
        for command in build_stage_command_plan(campaign_root, strategy, policy)
        if command.get("argv")
    ]


def _default_checkpoint_source(stage: str) -> str:
    stage_name = stage.lower()
    if "search" in stage_name:
        return "raw/search/unit-*/page-*.json"
    if "detail" in stage_name:
        return "raw/detail-live/<pack_id>/job-*.json"
    return "state/import-ledger.jsonl"


def _blocked_event_id(campaign_id: str, stage: str, reason: str, evidence_file: str) -> str:
    readable = re.sub(r"[^0-9A-Za-z_.-]+", "-", f"{campaign_id}-{stage}-{reason}").strip("-")
    digest = hashlib.sha1(f"{campaign_id}\n{stage}\n{reason}\n{evidence_file}".encode("utf-8")).hexdigest()[:8]
    return f"blocked-{readable}-{digest}"


def write_blocked_continuation(
    campaign_root: str | Path,
    stage: str,
    reason: str,
    evidence_file: str,
    *,
    checkpoint_source: str | None = None,
    resume_from: dict[str, Any] | None = None,
    completed: int = 0,
    total: int = 0,
    stage_argv: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    continuation_path = root / "state" / "continuation-plan.json"
    campaign_id = root.name
    event_id = _blocked_event_id(campaign_id, stage, reason, evidence_file)
    plan = {
        "campaign_id": campaign_id,
        "blocked_event_id": event_id,
        "blocked_stage": stage,
        "reason": reason,
        "evidence_file": evidence_file,
        "checkpoint_source": checkpoint_source or _default_checkpoint_source(stage),
        "resume_from": dict(resume_from or {}),
        "completed": max(0, int(completed)),
        "total": max(0, int(total)),
        "stage_argv": list(stage_argv or []),
        "continuation_path": continuation_path.as_posix(),
        "safe_to_resume_after": "负责人处理验证码、登录或安全页面后，回到人才银行页面并确认页面健康检查通过。",
        "resume_command": (
            "python -m scripts.maimai_campaign_orchestrator resume "
            f"--campaign-root {root.as_posix()}"
        ),
    }
    write_json(continuation_path, plan)
    write_stage_state(
        root,
        stage,
        "blocked",
        {
            "reason": reason,
            "evidence_file": evidence_file,
            "blocked_event_id": event_id,
            "checkpoint_source": plan["checkpoint_source"],
            "resume_from": plan["resume_from"],
            "completed": plan["completed"],
            "total": plan["total"],
            "stage_argv": plan["stage_argv"],
            "continuation_path": plan["continuation_path"],
        },
    )
    return plan


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def is_retriable_error(text: str) -> bool:
    lowered = text.lower()
    blocking_needles = (
        "captcha",
        "captcha_api",
        "login",
        "登录",
        "验证码",
        "安全页面",
        "security page",
    )
    if any(needle in lowered for needle in blocking_needles):
        return False

    retriable_needles = (
        "connection timed out",
        "temporarily unavailable",
        "file is being used by another process",
    )
    return any(needle in lowered for needle in retriable_needles)


def run_command(argv: list[str]) -> CommandResult:
    completed = subprocess.run(argv, text=True, capture_output=True, check=False)
    return CommandResult(
        argv=list(argv),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _cmd_status(args: argparse.Namespace) -> int:
    state = load_json(Path(args.campaign_root) / "state" / "stage-state.json", default={}) or {}
    _print_json(state)
    return 0


def _cmd_plan_waves(args: argparse.Namespace) -> int:
    try:
        units = _load_jsonl_objects(args.units)
    except ValueError as exc:
        raise ValueError(f"invalid search units JSONL: {exc}") from exc
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
    try:
        return int(args.func(args))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
