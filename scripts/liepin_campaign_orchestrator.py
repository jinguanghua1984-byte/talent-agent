"""猎聘 P0 campaign 编排 CLI。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_api_contract import DEFAULT_SEARCH_PARAMS  # noqa: E402
from scripts.liepin_campaign import (  # noqa: E402
    atomic_write_json,
    ensure_campaign,
    write_continuation_plan,
)
from scripts.liepin_cdp_browser_bootstrap import (  # noqa: E402
    DEFAULT_MANIFEST,
    DEFAULT_PORT,
    DEFAULT_PROFILE,
    DEFAULT_URL,
    BrowserLaunchConfig,
    build_browser_args,
    build_session_manifest,
    find_browser,
    write_manifest,
)
from scripts.liepin_search_live_gate import run_live_search  # noqa: E402
from scripts.liepin_search_standardize import standardize_campaign  # noqa: E402


DEFAULT_RUN_POLICY: dict[str, Any] = {
    "execution_surface": "cdp_in_page_fetch",
    "allowed_hosts": ["api-h.liepin.com"],
    "allowed_endpoints": [
        "/api/com.liepin.searchfront4r.h.get-search-condition-by-job",
        "/api/com.liepin.searchfront4r.h.search-resumes",
    ],
    "request_content_type": "application/x-www-form-urlencoded",
    "default_page_limit": 1,
    "max_page_limit": 5,
    "request_interval_seconds": 3,
    "stop_on_login_or_security_page": True,
    "stop_on_captcha": True,
    "stop_on_http_403": True,
    "stop_on_http_429": True,
    "stop_on_http_432": True,
    "stop_on_non_json": True,
    "stop_on_flag_not_1": True,
    "allow_detail_fetch": False,
    "allow_campaign_db_write": False,
    "allow_main_db_write": False,
    "main_db_sync_mode": "manual_only",
}


def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def init_campaign(campaign_root: str | Path, job_id: int | str) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    resolved_job_id = int(job_id) if str(job_id).isdigit() else job_id
    requirements = {
        "campaign_id": paths.campaign_id,
        "source_input": "",
        "job_id": resolved_job_id,
        "target_role": "",
        "candidate_profile": {},
        "missing_fields": [],
        "confirmed_defaults": {},
    }
    strategy = {
        "search_scene": "job",
        "condition_source": "get-search-condition-by-job",
        "overrides": {
            "keyword": "",
            "wantDqs": "",
            "eduLevels": [],
            "workYearsLow": None,
            "workYearsHigh": None,
            "sortType": "0",
            "resumetype": "0",
        },
        "page_plan": {
            "start_cur_page": 0,
            "max_pages": DEFAULT_RUN_POLICY["default_page_limit"],
        },
        "default_search_params_keys": sorted(DEFAULT_SEARCH_PARAMS.keys()),
    }
    atomic_write_json(paths.requirements, requirements)
    atomic_write_json(paths.strategy, strategy)
    atomic_write_json(paths.run_policy, DEFAULT_RUN_POLICY)
    return {
        "status": "initialized",
        "campaign_root": paths.root.as_posix(),
        "job_id": resolved_job_id,
    }


def status(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    return {
        "campaign_root": paths.root.as_posix(),
        "campaign_id": paths.campaign_id,
        "has_requirements": paths.requirements.exists(),
        "has_strategy": paths.strategy.exists(),
        "has_run_policy": paths.run_policy.exists(),
        "has_continuation_plan": paths.continuation_plan.exists(),
        "has_search_summary": paths.search_summary_json.exists(),
    }


def plan_pages(campaign_root: str | Path, max_pages: int | None = None) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    policy = load_json(paths.run_policy, DEFAULT_RUN_POLICY)
    limit = int(max_pages if max_pages is not None else policy.get("default_page_limit", 1))
    max_limit = int(policy.get("max_page_limit", 5))
    if limit <= 0:
        raise ValueError("max pages must be positive")
    if limit > max_limit:
        raise ValueError("max pages exceeds policy limit")
    pages = list(range(limit))
    continuation = write_continuation_plan(
        paths,
        next_cur_page=pages[0],
        reason="planned",
    )
    return {
        "status": "planned",
        "campaign_root": paths.root.as_posix(),
        "pages": pages,
        "continuation_plan": continuation,
    }


def summarize(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    summary = load_json(paths.search_summary_json)
    if summary is None:
        raise ValueError("search summary does not exist; run standardize first")
    return summary


def launch_browser(
    *,
    browser: str | Path | None = None,
    profile: str | Path = DEFAULT_PROFILE,
    remote_debugging_port: int = DEFAULT_PORT,
    url: str = DEFAULT_URL,
    manifest_out: str | Path = DEFAULT_MANIFEST,
    extension: str | Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_browser = find_browser(browser)
    resolved_extension = Path(extension) if extension is not None else None
    config = BrowserLaunchConfig(
        browser=resolved_browser,
        profile=Path(profile),
        remote_debugging_port=remote_debugging_port,
        url=url,
        extension=resolved_extension,
    )
    manifest = build_session_manifest(
        profile=config.profile,
        remote_debugging_port=config.remote_debugging_port,
        url=config.url,
        extension=config.extension,
    )
    write_manifest(Path(manifest_out), manifest)
    if not dry_run:
        config.profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(build_browser_args(config), close_fds=True)
    return {
        "status": "dry_run" if dry_run else "launched",
        "cdp_url": manifest["cdp_url"],
        "manifest_out": str(manifest_out),
        "profile": manifest["profile"],
        "url": manifest["url"],
        "automation_boundary": manifest["automation_boundary"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="猎聘 campaign 编排")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--campaign-root", required=True)
    init.add_argument("--job-id", required=True)

    stat = subparsers.add_parser("status")
    stat.add_argument("--campaign-root", required=True)

    plan = subparsers.add_parser("plan-pages")
    plan.add_argument("--campaign-root", required=True)
    plan.add_argument("--max-pages", type=int)

    standardize = subparsers.add_parser("standardize")
    standardize.add_argument("--campaign-root", required=True)

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--campaign-root", required=True)

    launch = subparsers.add_parser("launch-browser")
    launch.add_argument("--browser", type=Path)
    launch.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    launch.add_argument("--remote-debugging-port", type=int, default=DEFAULT_PORT)
    launch.add_argument("--url", default=DEFAULT_URL)
    launch.add_argument("--extension", type=Path)
    launch.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    launch.add_argument("--dry-run", action="store_true")

    live = subparsers.add_parser("run-live-search")
    live.add_argument("--campaign-root", required=True)
    live.add_argument("--cdp-url", default=f"http://127.0.0.1:{DEFAULT_PORT}")
    live.add_argument("--delay-seconds", type=float, default=DEFAULT_RUN_POLICY["request_interval_seconds"])
    live.add_argument("--timeout-seconds", type=float, default=30)
    live.add_argument("--max-pages", type=int)
    live.add_argument("--run-id")

    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            result = init_campaign(args.campaign_root, args.job_id)
        elif args.command == "status":
            result = status(args.campaign_root)
        elif args.command == "plan-pages":
            result = plan_pages(args.campaign_root, args.max_pages)
        elif args.command == "standardize":
            result = standardize_campaign(args.campaign_root)
        elif args.command == "summarize":
            result = summarize(args.campaign_root)
        elif args.command == "launch-browser":
            result = launch_browser(
                browser=args.browser,
                profile=args.profile,
                remote_debugging_port=args.remote_debugging_port,
                url=args.url,
                extension=args.extension,
                manifest_out=args.manifest_out,
                dry_run=args.dry_run,
            )
        elif args.command == "run-live-search":
            result = run_live_search(
                campaign_root=args.campaign_root,
                cdp_url=args.cdp_url,
                delay_seconds=args.delay_seconds,
                timeout_seconds=args.timeout_seconds,
                max_pages=args.max_pages,
                run_id=args.run_id,
            )
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
