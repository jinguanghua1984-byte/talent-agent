"""脉脉详情诊断 trace 差异比对工具。"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _extract_traces(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        raise ValueError("trace file must be a JSON object or array")

    for key in ("traces", "diagnosticTraces"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    nested = data.get("data")
    if isinstance(nested, (dict, list)):
        return _extract_traces(nested)

    trace = data.get("trace")
    if isinstance(trace, dict):
        return [trace]

    raise ValueError("trace file must contain traces or diagnosticTraces")


def load_trace_file(path: Path | str) -> list[dict[str, Any]]:
    return _extract_traces(_load_json(Path(path)))


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _path_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _unique(values: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        marker = json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker in seen:
            continue
        seen.add(marker)
        result.append(value)
    return result


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _intervals_ms(traces: list[dict[str, Any]]) -> list[int]:
    times = [_parse_time(_path_get(trace, "timing", "startedAt")) for trace in traces]
    times = [item for item in times if item is not None]
    times.sort()
    result: list[int] = []
    for left, right in zip(times, times[1:]):
        result.append(int((right - left).total_seconds() * 1000))
    return result


def _duration_summary(values: list[Any]) -> dict[str, int | None]:
    numbers = [int(value) for value in values if isinstance(value, (int, float))]
    if not numbers:
        return {"min_ms": None, "max_ms": None, "avg_ms": None}
    return {
        "min_ms": min(numbers),
        "max_ms": max(numbers),
        "avg_ms": int(sum(numbers) / len(numbers)),
    }


def summarize_traces(traces: list[dict[str, Any]]) -> dict[str, Any]:
    actions = [_string(trace.get("action") or trace.get("actionLabel")) for trace in traces]
    sender_types = [
        _string(trace.get("senderType") or trace.get("source"))
        for trace in traces
    ]
    sender_urls = [_string(_path_get(trace, "sender", "url")) for trace in traces]
    active_tab_urls = [_string(_path_get(trace, "activeTab", "url")) for trace in traces]
    active_tab_titles = [_string(_path_get(trace, "activeTab", "title")) for trace in traces]
    target_tab_urls = [_string(_path_get(trace, "targetTab", "url")) for trace in traces]
    page_urls = [_string(_path_get(trace, "pageState", "href")) for trace in traces]
    page_visibility = [_string(_path_get(trace, "pageState", "visibilityState")) for trace in traces]
    page_focus = [_path_get(trace, "pageState", "hasFocus") for trace in traces]
    window_focus = [trace.get("windowFocused") for trace in traces]
    durations = [_path_get(trace, "timing", "durationMs") for trace in traces]
    intervals = _intervals_ms(traces)

    return {
        "count": len(traces),
        "actions": actions,
        "action_counts": dict(Counter(actions)),
        "sender_types": _unique([value for value in sender_types if value]),
        "sender_urls": _unique([value for value in sender_urls if value]),
        "active_tab_urls": _unique([value for value in active_tab_urls if value]),
        "active_tab_titles": _unique([value for value in active_tab_titles if value]),
        "target_tab_urls": _unique([value for value in target_tab_urls if value]),
        "page_urls": _unique([value for value in page_urls if value]),
        "page_visibility": _unique([value for value in page_visibility if value]),
        "page_focus": _unique([value for value in page_focus if value is not None]),
        "window_focus": _unique([value for value in window_focus if value is not None]),
        "duration": _duration_summary(durations),
        "intervals_ms": intervals,
        "min_interval_ms": min(intervals) if intervals else None,
    }


COMPARE_FIELDS = [
    "sender_types",
    "sender_urls",
    "active_tab_urls",
    "target_tab_urls",
    "page_visibility",
    "page_focus",
    "window_focus",
    "action_sequence",
    "min_interval_ms",
]


def _summary_value(summary: dict[str, Any], field: str) -> Any:
    if field == "action_sequence":
        return summary.get("actions", [])
    return summary.get(field)


def _make_difference(field: str, manual_summary: dict[str, Any], automation_summary: dict[str, Any]) -> dict[str, Any] | None:
    manual_value = _summary_value(manual_summary, field)
    automation_value = _summary_value(automation_summary, field)
    if manual_value == automation_value:
        return None
    return {
        "field": field,
        "manual": manual_value,
        "automation": automation_value,
        "verdict": "diff",
    }


def _risk_hints(differences: list[dict[str, Any]], manual_summary: dict[str, Any], automation_summary: dict[str, Any]) -> list[str]:
    fields = {item["field"] for item in differences}
    hints: list[str] = []
    if "sender_types" in fields or "sender_urls" in fields:
        hints.append("sender 来源不同：优先比较 popup 手动调用与 automation/CLI 调用在扩展后台中的 sender 栈。")
    if "active_tab_urls" in fields:
        hints.append("active tab 不同：自动化可能把前台上下文切到 automation 页面，导致与手动 popup 路径不一致。")
    if {"page_visibility", "page_focus", "window_focus"} & fields:
        hints.append("页面可见性或焦点不同：平台可能把隐藏页、失焦页或非真实前台操作判为异常。")
    if "action_sequence" in fields:
        hints.append("动作序列不同：检查自动化是否额外执行 preflight、轮询、导出、清理等手动路径没有的动作。")
    auto_min_interval = automation_summary.get("min_interval_ms")
    manual_min_interval = manual_summary.get("min_interval_ms")
    if isinstance(auto_min_interval, int) and (manual_min_interval is None or auto_min_interval < manual_min_interval):
        hints.append("自动化调用间隔更短：需要拉长 import/start/status/export 的节奏，先用 probeOnly 验证。")
    return hints


def compare_trace_sets(manual_traces: list[dict[str, Any]], automation_traces: list[dict[str, Any]]) -> dict[str, Any]:
    manual_summary = summarize_traces(manual_traces)
    automation_summary = summarize_traces(automation_traces)
    differences = [
        diff
        for field in COMPARE_FIELDS
        for diff in [_make_difference(field, manual_summary, automation_summary)]
        if diff is not None
    ]
    return {
        "manual": manual_summary,
        "automation": automation_summary,
        "differences": differences,
        "risk_hints": _risk_hints(differences, manual_summary, automation_summary),
    }


def _format_value(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (list, dict)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    else:
        text = str(value)
    text = text.replace("\n", " ")
    if len(text) > 160:
        return text[:157] + "..."
    return text


def render_markdown(result: dict[str, Any], manual_path: Path, automation_path: Path) -> str:
    lines = [
        "# 脉脉详情 trace 差异比对",
        "",
        f"- 手动 trace：`{manual_path}`",
        f"- 自动化 trace：`{automation_path}`",
        f"- 手动记录数：{result['manual']['count']}",
        f"- 自动化记录数：{result['automation']['count']}",
        "",
        "## 差异矩阵",
        "",
        "| 项目 | 手动路径 | 自动化路径 | 判定 |",
        "| --- | --- | --- | --- |",
    ]

    if result["differences"]:
        for item in result["differences"]:
            lines.append(
                "| {field} | {manual} | {automation} | {verdict} |".format(
                    field=item["field"],
                    manual=_format_value(item["manual"]),
                    automation=_format_value(item["automation"]),
                    verdict=item["verdict"],
                )
            )
    else:
        lines.append("| all | 一致 | 一致 | match |")

    lines.extend(["", "## 风险提示", ""])
    if result["risk_hints"]:
        lines.extend(f"- {hint}" for hint in result["risk_hints"])
    else:
        lines.append("- 当前 trace 未发现关键上下文差异；若仍触发安全机制，应继续缩小真实详情请求本身的差异。")
    lines.append("")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="比较手动与自动化脉脉详情诊断 trace")
    parser.add_argument("manual_trace", type=Path, help="手动路径导出的 trace JSON")
    parser.add_argument("automation_trace", type=Path, help="自动化路径导出的 trace JSON")
    parser.add_argument("--out", type=Path, help="输出 Markdown 报告路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    manual_traces = load_trace_file(args.manual_trace)
    automation_traces = load_trace_file(args.automation_trace)
    result = compare_trace_sets(manual_traces, automation_traces)
    report = render_markdown(result, args.manual_trace, args.automation_trace)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report, encoding="utf-8")
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
