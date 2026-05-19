import json
import subprocess
from pathlib import Path

import pytest

import scripts.maimai_cdp_browser_bootstrap as bootstrap
from scripts.maimai_cdp_browser_bootstrap import (
    BrowserLaunchConfig,
    build_browser_args,
    build_session_manifest,
    find_browser,
    write_manifest,
)


def test_build_browser_args_uses_confirmed_profile_port_extension_and_url(tmp_path: Path):
    config = BrowserLaunchConfig(
        browser=Path("C:/Chrome/chrome.exe"),
        profile=Path("data/session/maimai-cdp-profile"),
        remote_debugging_port=9888,
        extension=Path("extensions/maimai-scraper"),
        url="https://maimai.cn/",
    )

    args = build_browser_args(config)

    assert args[0] == str(config.browser)
    assert "--remote-debugging-port=9888" in args
    assert "--user-data-dir=data/session/maimai-cdp-profile" in args
    assert "--load-extension=extensions/maimai-scraper" in args
    assert "--no-first-run" in args
    assert "--no-default-browser-check" in args
    assert args[-1] == "https://maimai.cn/"


def test_session_manifest_records_manual_handoff():
    manifest = build_session_manifest(
        profile=Path("data/session/maimai-cdp-profile"),
        remote_debugging_port=9888,
        extension=Path("extensions/maimai-scraper"),
        url="https://maimai.cn/",
    )

    assert manifest["cdp_url"] == "http://127.0.0.1:9888"
    assert manifest["manual_steps"] == ["login_maimai", "enter_talent_bank", "execute_one_search"]
    assert manifest["automation_boundary"] == "launch_only"


def test_write_manifest_writes_utf8_json(tmp_path: Path):
    manifest_path = tmp_path / "session.json"
    manifest = build_session_manifest(
        profile=Path("data/session/maimai-cdp-profile"),
        remote_debugging_port=9888,
        extension=Path("extensions/maimai-scraper"),
        url="https://maimai.cn/",
    )

    write_manifest(manifest_path, manifest)

    raw = manifest_path.read_bytes()
    assert json.loads(raw.decode("utf-8")) == manifest


def test_find_browser_rejects_missing_explicit_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        find_browser(tmp_path / "missing-chrome.exe")


def test_dry_run_writes_manifest_and_does_not_launch_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    browser = tmp_path / "chrome.exe"
    browser.write_text("", encoding="utf-8")
    manifest_path = tmp_path / "session.json"

    def fail_popen(*args, **kwargs):
        raise AssertionError("dry-run must not launch a browser")

    monkeypatch.setattr(subprocess, "Popen", fail_popen)

    result = bootstrap.main(
        [
            "--browser",
            str(browser),
            "--profile",
            str(tmp_path / "profile"),
            "--extension",
            "extensions/maimai-scraper",
            "--manifest-out",
            str(manifest_path),
            "--dry-run",
        ]
    )

    assert result == 0
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_manifest["automation_boundary"] == "launch_only"
    assert json.loads(capsys.readouterr().out)["cdp_url"] == "http://127.0.0.1:9888"


def test_cli_reports_missing_browser_without_traceback_or_session_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
):
    manifest_path = tmp_path / "session.json"

    def fail_popen(*args, **kwargs):
        raise AssertionError("browser should not launch when browser path is missing")

    monkeypatch.setattr(subprocess, "Popen", fail_popen)
    result = bootstrap.main(
        [
            "--browser",
            str(tmp_path / "missing-chrome.exe"),
            "--manifest-out",
            str(manifest_path),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert result == 2
    assert captured.out == ""
    assert "error:" in captured.err
    assert "Traceback" not in captured.out + captured.err
    assert not manifest_path.exists()
