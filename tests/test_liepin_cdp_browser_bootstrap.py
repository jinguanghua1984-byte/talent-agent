import json
import subprocess
from pathlib import Path

import pytest

import scripts.liepin_cdp_browser_bootstrap as bootstrap
from scripts.liepin_cdp_browser_bootstrap import (
    BrowserLaunchConfig,
    build_browser_args,
    build_session_manifest,
    default_browser_candidates,
    find_browser,
    write_manifest,
)


def test_build_browser_args_uses_liepin_profile_port_and_url():
    config = BrowserLaunchConfig(
        browser=Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        profile=Path("data/session/liepin-cdp-profile"),
        remote_debugging_port=9898,
        url="https://h.liepin.com/search/getConditionItem",
    )

    args = build_browser_args(config)

    assert args[0] == str(config.browser)
    assert "--remote-debugging-port=9898" in args
    assert f"--user-data-dir={Path('data/session/liepin-cdp-profile').resolve().as_posix()}" in args
    assert "--no-first-run" in args
    assert "--no-default-browser-check" in args
    assert args[-1] == "https://h.liepin.com/search/getConditionItem"
    assert not any(arg.startswith("--load-extension=") for arg in args)


def test_session_manifest_records_liepin_manual_handoff():
    manifest = build_session_manifest(
        profile=Path("data/session/liepin-cdp-profile"),
        remote_debugging_port=9898,
        url="https://h.liepin.com/search/getConditionItem",
    )

    assert manifest["schema"] == "liepin_cdp_browser_session_v1"
    assert manifest["cdp_url"] == "http://127.0.0.1:9898"
    assert manifest["manual_steps"] == ["login_liepin", "enter_resume_search", "confirm_page_ready"]
    assert manifest["automation_boundary"] == "launch_only"


def test_default_browser_candidates_include_macos_chrome():
    candidates = [candidate.as_posix() for candidate in default_browser_candidates()]

    assert "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" in candidates


def test_write_manifest_writes_utf8_json(tmp_path: Path):
    manifest_path = tmp_path / "session.json"
    manifest = build_session_manifest(
        profile=Path("data/session/liepin-cdp-profile"),
        remote_debugging_port=9898,
        url="https://h.liepin.com/search/getConditionItem",
    )

    write_manifest(manifest_path, manifest)

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


def test_find_browser_rejects_missing_explicit_path(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        find_browser(tmp_path / "missing-chrome")


def test_dry_run_writes_manifest_and_does_not_launch_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    browser = tmp_path / "chrome"
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
            "--manifest-out",
            str(manifest_path),
            "--dry-run",
        ]
    )

    assert result == 0
    saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved_manifest["automation_boundary"] == "launch_only"
    assert json.loads(capsys.readouterr().out)["cdp_url"] == "http://127.0.0.1:9898"


def test_launch_detaches_browser_from_parent_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys):
    browser = tmp_path / "chrome"
    browser.write_text("", encoding="utf-8")
    calls = []

    def fake_popen(args, **kwargs):
        calls.append((args, kwargs))
        return object()

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    result = bootstrap.main(
        [
            "--browser",
            str(browser),
            "--profile",
            str(tmp_path / "profile"),
            "--manifest-out",
            str(tmp_path / "session.json"),
        ]
    )

    assert result == 0
    assert calls
    assert calls[0][1]["close_fds"] is True
    assert calls[0][1]["start_new_session"] is True
    assert calls[0][1]["stdout"] is subprocess.DEVNULL
    assert calls[0][1]["stderr"] is subprocess.DEVNULL
    assert "CDP browser launched" in capsys.readouterr().out


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
            str(tmp_path / "missing-chrome"),
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
