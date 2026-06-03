"""启动猎聘专用 CDP Chrome profile。

该脚本只启动独立浏览器 profile 并写 session manifest，不读取浏览器登录态文件。
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


DEFAULT_PROFILE = Path("data/session/liepin-cdp-profile")
DEFAULT_PORT = 9898
DEFAULT_URL = "https://h.liepin.com/search/getConditionItem"
DEFAULT_MANIFEST = Path("data/session/liepin-cdp-browser-session.json")
MANUAL_STEPS = ["login_liepin", "enter_resume_search", "confirm_page_ready"]


@dataclass(frozen=True)
class BrowserLaunchConfig:
    browser: Path
    profile: Path = DEFAULT_PROFILE
    remote_debugging_port: int = DEFAULT_PORT
    url: str = DEFAULT_URL
    extension: Path | None = None


def _path_flag_value(path: Path) -> str:
    return path.expanduser().resolve().as_posix()


def build_browser_args(config: BrowserLaunchConfig) -> list[str]:
    args = [
        str(config.browser),
        f"--remote-debugging-port={config.remote_debugging_port}",
        f"--user-data-dir={_path_flag_value(config.profile)}",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    if config.extension is not None:
        args.append(f"--load-extension={_path_flag_value(config.extension)}")
    args.append(config.url)
    return args


def build_session_manifest(
    profile: Path,
    remote_debugging_port: int,
    url: str,
    extension: Path | None = None,
) -> dict[str, Any]:
    return {
        "schema": "liepin_cdp_browser_session_v1",
        "cdp_url": f"http://127.0.0.1:{remote_debugging_port}",
        "profile": _path_flag_value(profile),
        "remote_debugging_port": remote_debugging_port,
        "extension": _path_flag_value(extension) if extension is not None else None,
        "url": url,
        "manual_steps": MANUAL_STEPS.copy(),
        "automation_boundary": "launch_only",
    }


def default_browser_candidates() -> list[Path]:
    candidates: list[Path] = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ]

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        candidates.extend(
            [
                Path(local_app_data) / "Google/Chrome/Application/chrome.exe",
                Path(local_app_data) / "Microsoft/Edge/Application/msedge.exe",
            ]
        )
    return candidates


def find_browser(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        browser = Path(explicit)
        if browser.exists():
            return browser
        raise FileNotFoundError(f"Browser path does not exist: {browser}")

    for candidate in default_browser_candidates():
        if candidate.exists():
            return candidate

    checked = ", ".join(str(candidate) for candidate in default_browser_candidates())
    raise FileNotFoundError(f"No Chrome, Chromium, or Edge browser found. Checked: {checked}")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="启动猎聘专用 CDP Chrome profile。")
    parser.add_argument("--browser", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--remote-debugging-port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--url", default=DEFAULT_URL)
    parser.add_argument("--extension", type=Path, default=None)
    parser.add_argument("--manifest-out", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        browser = find_browser(args.browser)
        config = BrowserLaunchConfig(
            browser=browser,
            profile=args.profile,
            remote_debugging_port=args.remote_debugging_port,
            url=args.url,
            extension=args.extension,
        )
        manifest = build_session_manifest(
            profile=config.profile,
            remote_debugging_port=config.remote_debugging_port,
            url=config.url,
            extension=config.extension,
        )

        write_manifest(args.manifest_out, manifest)
        if args.dry_run:
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            return 0

        config.profile.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(build_browser_args(config), close_fds=True)
        print(f"CDP browser launched: {manifest['cdp_url']}")
        print("Manual steps: login_liepin -> enter_resume_search -> confirm_page_ready")
        print("Automation boundary: launch_only")
        return 0
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
