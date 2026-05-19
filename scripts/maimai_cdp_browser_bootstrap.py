from __future__ import annotations

import argparse
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


MANUAL_STEPS = ["login_maimai", "enter_talent_bank", "execute_one_search"]


@dataclass(frozen=True)
class BrowserLaunchConfig:
    browser: Path
    profile: Path
    remote_debugging_port: int
    extension: Path
    url: str


def _path_flag_value(path: Path) -> str:
    return path.as_posix()


def build_browser_args(config: BrowserLaunchConfig) -> list[str]:
    return [
        str(config.browser),
        f"--remote-debugging-port={config.remote_debugging_port}",
        f"--user-data-dir={_path_flag_value(config.profile)}",
        f"--load-extension={_path_flag_value(config.extension)}",
        "--no-first-run",
        "--no-default-browser-check",
        config.url,
    ]


def build_session_manifest(
    profile: Path,
    remote_debugging_port: int,
    extension: Path,
    url: str,
) -> dict[str, Any]:
    return {
        "schema": "maimai_cdp_browser_session_v1",
        "cdp_url": f"http://127.0.0.1:{remote_debugging_port}",
        "profile": _path_flag_value(profile),
        "remote_debugging_port": remote_debugging_port,
        "extension": _path_flag_value(extension),
        "url": url,
        "manual_steps": MANUAL_STEPS.copy(),
        "automation_boundary": "launch_only",
    }


def default_browser_candidates() -> list[Path]:
    candidates: list[Path] = [
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
    raise FileNotFoundError(f"No Chrome or Edge browser found. Checked: {checked}")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a CDP browser for manual Maimai handoff.")
    parser.add_argument("--browser", type=Path, default=None)
    parser.add_argument("--profile", type=Path, default=Path("data/session/maimai-cdp-profile"))
    parser.add_argument("--remote-debugging-port", type=int, default=9888)
    parser.add_argument("--extension", type=Path, default=Path("extensions/maimai-scraper"))
    parser.add_argument("--url", default="https://maimai.cn/")
    parser.add_argument("--manifest-out", type=Path, default=Path("data/session/maimai-cdp-browser-session.json"))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    browser = find_browser(args.browser)
    config = BrowserLaunchConfig(
        browser=browser,
        profile=args.profile,
        remote_debugging_port=args.remote_debugging_port,
        extension=args.extension,
        url=args.url,
    )
    manifest = build_session_manifest(
        profile=config.profile,
        remote_debugging_port=config.remote_debugging_port,
        extension=config.extension,
        url=config.url,
    )

    write_manifest(args.manifest_out, manifest)
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0

    config.profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(build_browser_args(config), close_fds=True)
    print(f"CDP browser launched: {manifest['cdp_url']}")
    print("Manual steps: login_maimai -> enter_talent_bank -> execute_one_search")
    print("Automation boundary: launch_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
