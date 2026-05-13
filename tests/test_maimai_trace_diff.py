import json
from pathlib import Path

from scripts.maimai_trace_diff import compare_trace_sets, load_trace_file, main


def _trace(
    *,
    action: str,
    sender_type: str,
    sender_url: str,
    active_url: str,
    visibility: str = "visible",
    has_focus: bool = True,
    window_focused: bool = True,
    duration_ms: int = 20,
    started_at: str = "2026-05-13T10:00:00.000Z",
) -> dict:
    return {
        "action": action,
        "senderType": sender_type,
        "sender": {"url": sender_url},
        "activeTab": {"url": active_url, "title": "人才银行"},
        "targetTab": {"url": "https://maimai.cn/ent/v41/recruit/talents?tab=1"},
        "windowFocused": window_focused,
        "pageState": {
            "ok": True,
            "href": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
            "title": "人才银行",
            "visibilityState": visibility,
            "hasFocus": has_focus,
        },
        "timing": {
            "startedAt": started_at,
            "endedAt": started_at,
            "durationMs": duration_ms,
        },
    }


def test_load_trace_file_accepts_extension_export_shapes(tmp_path: Path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps({"diagnosticTraces": [_trace(action="probeOnly", sender_type="popup", sender_url="chrome-extension://id/popup.html", active_url="https://maimai.cn/ent/v41/recruit/talents?tab=1")]}),
        encoding="utf-8",
    )

    traces = load_trace_file(path)

    assert len(traces) == 1
    assert traces[0]["action"] == "probeOnly"


def test_compare_trace_sets_flags_manual_vs_automation_context_differences():
    manual = [
        _trace(
            action="startDetailBatch",
            sender_type="popup",
            sender_url="chrome-extension://id/popup.html",
            active_url="https://maimai.cn/ent/v41/recruit/talents?tab=1",
            started_at="2026-05-13T10:00:00.000Z",
        )
    ]
    automation = [
        _trace(
            action="preflightTrace",
            sender_type="automation",
            sender_url="chrome-extension://id/automation.html",
            active_url="chrome-extension://id/automation.html",
            visibility="hidden",
            has_focus=False,
            window_focused=False,
            duration_ms=2,
            started_at="2026-05-13T10:00:00.000Z",
        ),
        _trace(
            action="probeOnly",
            sender_type="automation",
            sender_url="chrome-extension://id/automation.html",
            active_url="chrome-extension://id/automation.html",
            visibility="hidden",
            has_focus=False,
            window_focused=False,
            duration_ms=3,
            started_at="2026-05-13T10:00:00.100Z",
        ),
    ]

    result = compare_trace_sets(manual, automation)
    fields = {item["field"] for item in result["differences"]}

    assert "sender_types" in fields
    assert "active_tab_urls" in fields
    assert "page_visibility" in fields
    assert "page_focus" in fields
    assert "window_focus" in fields
    assert "action_sequence" in fields
    assert result["risk_hints"]


def test_trace_diff_cli_writes_markdown_report(tmp_path: Path):
    manual_path = tmp_path / "manual.json"
    automation_path = tmp_path / "automation.json"
    out_path = tmp_path / "diff.md"
    manual_path.write_text(
        json.dumps({"traces": [_trace(action="startDetailBatch", sender_type="popup", sender_url="chrome-extension://id/popup.html", active_url="https://maimai.cn/ent/v41/recruit/talents?tab=1")]}),
        encoding="utf-8",
    )
    automation_path.write_text(
        json.dumps({"traces": [_trace(action="probeOnly", sender_type="automation", sender_url="chrome-extension://id/automation.html", active_url="chrome-extension://id/automation.html", visibility="hidden", has_focus=False)]}),
        encoding="utf-8",
    )

    assert main([str(manual_path), str(automation_path), "--out", str(out_path)]) == 0
    report = out_path.read_text(encoding="utf-8")

    assert "# 脉脉详情 trace 差异比对" in report
    assert "| 项目 | 手动路径 | 自动化路径 | 判定 |" in report
    assert "sender_types" in report
    assert "active_tab_urls" in report
