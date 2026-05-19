"""生成脉脉 campaign 飞书交付包 manifest 和本地安全 source files。"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape


SCHEMA = "maimai_feishu_delivery_package_v1"
DEFAULT_CSV_FIELDS = [
    "candidate_id",
    "name",
    "priority",
    "recommendation_label",
    "profile_url",
]
MANIFEST_EXCLUDED_INPUTS = [
    {
        "kind": "local_campaign_database",
        "status": "excluded",
        "reason": "交付包只使用筛后报告、审计摘要和外联 CSV，不读取本地数据库。",
    },
    {
        "kind": "talent_sync_bundle",
        "status": "excluded",
        "reason": "同步包属于迁移产物，不进入飞书发布 manifest。",
    },
    {
        "kind": "platform_capture_payloads",
        "status": "excluded",
        "reason": "平台原始采集载荷保留在本地，不进入飞书交付包。",
    },
    {
        "kind": "live_execution_payloads",
        "status": "excluded",
        "reason": "真实执行过程载荷只用于本地审计和恢复。",
    },
]
SENSITIVE_PATH_MARKERS = (
    "raw/search",
    "raw/detail",
    "raw_capture",
    "raw capture",
    "raw_live_run",
    "raw live run",
    "database",
    "source_path",
    "sync_bundle",
    "sync.zip",
    "sync zip",
    "sync-zip",
    "raw_path",
    "sqlite",
    "talent.db",
    ".sqlite",
    ".db",
    ".zip",
)
MANIFEST_FORBIDDEN_PATH_MARKERS = (
    "raw/search",
    "raw/detail",
    "raw capture",
    "raw live run",
    "talent.db",
    ".sqlite",
    ".db",
    ".zip",
    "sync.zip",
)
SENSITIVE_FIELD_MARKERS = (
    "raw",
    "payload",
    "cookie",
    "token",
    "secret",
    "password",
    "database",
    "source_path",
    "sync_bundle",
    "sync.zip",
    "sync zip",
    "sync-zip",
    "raw_path",
    "sqlite",
    "db",
)


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [{key: value or "" for key, value in row.items()} for row in rows]


def _path_text(path: str | Path) -> str:
    return Path(path).as_posix()


def _sensitive_text(value: Any) -> bool:
    text = str(value or "").lower().replace("\\", "/")
    return any(marker in text for marker in SENSITIVE_PATH_MARKERS)


def _relative_source_arg(path: str | Path, root: Path) -> str:
    file_path = Path(path)
    try:
        relative = file_path.resolve().relative_to(root.resolve())
    except ValueError:
        try:
            relative = file_path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            relative = Path(file_path.name)
    return f"@{relative.as_posix()}"


def _xml(value: Any) -> str:
    return escape("" if value is None else str(value), {'"': "&quot;", "'": "&apos;"})


def _json_for_xml(value: Any) -> str:
    return _xml(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _campaign_id(report: dict[str, Any], root: Path) -> str:
    return str(report.get("campaign_id") or root.name or "maimai-campaign")


def _summary_value(report: dict[str, Any], key: str, default: Any = "") -> Any:
    summary = report.get("summary")
    if not isinstance(summary, dict):
        return default
    return summary.get(key, default)


def _source_counts(report: dict[str, Any], audit: dict[str, Any], outreach_rows: list[dict[str, str]]) -> dict[str, Any]:
    issue_counts = audit.get("issue_counts", {})
    if not isinstance(issue_counts, dict):
        issue_counts = {}

    counts: dict[str, Any] = {
        "outreach_rows": len(outreach_rows),
        "candidate_rows": len(outreach_rows),
        "audit_issues": issue_counts,
    }
    for key in [
        "final_recommended_count",
        "strong_recommended_count",
        "recommended_count",
        "detail_contact_count",
    ]:
        value = _summary_value(report, key, None)
        if value is not None:
            counts[key] = value
    return counts


def _safe_csv_fieldnames(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return DEFAULT_CSV_FIELDS.copy()

    fieldnames: list[str] = []
    for row in rows:
        for field in row:
            if field not in fieldnames:
                fieldnames.append(field)

    safe_fields = []
    for field in fieldnames:
        field_text = field.lower().replace("\\", "/")
        if any(marker in field_text for marker in SENSITIVE_FIELD_MARKERS):
            continue
        if any(_sensitive_text(row.get(field, "")) for row in rows):
            continue
        safe_fields.append(field)
    return safe_fields or DEFAULT_CSV_FIELDS.copy()


def _filter_row(row: dict[str, str], fieldnames: list[str]) -> dict[str, str]:
    return {field: row.get(field, "") for field in fieldnames}


def _build_commands(
    campaign_id: str,
    generated_files: dict[str, str],
    dry_run: bool,
    root: Path,
) -> list[list[str]]:
    commands = [
        [
            "lark-cli",
            "docs",
            "+create",
            "--api-version",
            "v2",
            "--parent-position",
            "my_library",
            "--title",
            f"{campaign_id} 飞书交付包",
            "--content",
            _relative_source_arg(generated_files["summary_xml"], root),
        ],
        [
            "lark-cli",
            "sheets",
            "+create",
            "--title",
            f"{campaign_id} candidates",
        ],
        [
            "lark-cli",
            "sheets",
            "+create",
            "--title",
            f"{campaign_id} outreach queue",
        ],
    ]
    if dry_run:
        for command in commands:
            command.append("--dry-run")
    return commands


def _append_command_template(source_file: str, root: Path, sheet_token_placeholder: str, sheet_id_placeholder: str) -> list[str]:
    return [
        "lark-cli",
        "sheets",
        "+append",
        "--spreadsheet-token",
        sheet_token_placeholder,
        "--range",
        sheet_id_placeholder,
        "--file",
        _relative_source_arg(source_file, root),
    ]


def _build_publish_steps(
    commands: list[list[str]],
    generated_files: dict[str, str],
    root: Path,
) -> list[dict[str, Any]]:
    return [
        {
            "kind": "docs_create",
            "status": "ready",
            "command": commands[0],
        },
        {
            "kind": "sheets_create",
            "target": "candidates",
            "status": "creates_empty_sheet_until_append",
            "command": commands[1],
        },
        {
            "kind": "sheets_append",
            "target": "candidates",
            "status": "requires_sheet_id_after_create",
            "source_file": generated_files["candidate_csv"],
            "command_template": _append_command_template(
                generated_files["candidate_csv"],
                root,
                "<candidate_spreadsheet_token>",
                "<candidate_sheet_id>",
            ),
        },
        {
            "kind": "sheets_create",
            "target": "outreach_queue",
            "status": "creates_empty_sheet_until_append",
            "command": commands[2],
        },
        {
            "kind": "sheets_append",
            "target": "outreach_queue",
            "status": "requires_sheet_id_after_create",
            "source_file": generated_files["outreach_csv"],
            "command_template": _append_command_template(
                generated_files["outreach_csv"],
                root,
                "<outreach_spreadsheet_token>",
                "<outreach_sheet_id>",
            ),
        },
    ]


def _assert_manifest_has_no_sensitive_paths(manifest: dict[str, Any]) -> None:
    serialized = json.dumps(manifest, ensure_ascii=False).lower().replace("\\", "/")
    for marker in MANIFEST_FORBIDDEN_PATH_MARKERS:
        if marker in serialized:
            raise ValueError(f"manifest contains excluded path marker: {marker}")


def build_delivery_manifest(
    campaign_root: str | Path,
    final_report: str | Path,
    outreach_csv: str | Path,
    audit_json: str | Path,
    dry_run: bool,
) -> dict[str, Any]:
    root = Path(campaign_root).resolve()
    report = _load_json(final_report)
    outreach_rows = _read_csv(outreach_csv)
    audit = _load_json(audit_json)
    generated_files = {
        "summary_xml": _path_text(root / "reports" / "feishu-delivery-summary.xml"),
        "candidate_csv": _path_text(root / "reports" / "feishu-candidates.csv"),
        "outreach_csv": _path_text(root / "reports" / "feishu-outreach-queue.csv"),
    }
    campaign_id = _campaign_id(report, root)
    commands = _build_commands(campaign_id, generated_files, bool(dry_run), root)
    manifest: dict[str, Any] = {
        "schema": SCHEMA,
        "executor_cwd": _path_text(root),
        "campaign_id": campaign_id,
        "dry_run": bool(dry_run),
        "source_counts": _source_counts(report, audit, outreach_rows),
        "generated_files": generated_files,
        "commands": commands,
        "publish_steps": _build_publish_steps(commands, generated_files, root),
        "requires_sheet_ids_after_create": True,
        "publish_ready": False,
        "excluded_inputs": MANIFEST_EXCLUDED_INPUTS,
    }
    _assert_manifest_has_no_sensitive_paths(manifest)
    return manifest


def render_summary_xml(
    report: dict[str, Any],
    audit: dict[str, Any],
    outreach_rows: list[dict[str, str]],
) -> str:
    campaign_id = str(report.get("campaign_id") or "maimai-campaign")
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    recommended = summary.get("final_recommended_count", "")
    strong_recommended = summary.get("strong_recommended_count", "")
    issue_counts = audit.get("issue_counts", {})
    duplicate_ids = audit.get("duplicate_candidate_ids", [])
    preview_rows = outreach_rows[:10]

    candidate_items = []
    for row in preview_rows:
        label = " / ".join(
            part
            for part in [
                row.get("candidate_id", ""),
                row.get("name", ""),
                row.get("priority", ""),
                row.get("recommendation_label", ""),
            ]
            if part
        )
        candidate_items.append(f"    <li>{_xml(label)}</li>")
    if not candidate_items:
        candidate_items.append("    <li>无外联候选人行</li>")

    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            "<document>",
            f"  <title>{_xml(campaign_id)} 飞书交付包</title>",
            "  <h1>交付范围</h1>",
            "  <p>本交付包包含筛选后的摘要文档、候选人 CSV source 和外联队列 CSV source。</p>",
            "  <h1>关键指标</h1>",
            f"  <p>Campaign ID：{_xml(campaign_id)}</p>",
            f"  <p>最终推荐人数：{_xml(recommended)}</p>",
            f"  <p>强推荐人数：{_xml(strong_recommended)}</p>",
            f"  <p>外联队列行数：{_xml(len(outreach_rows))}</p>",
            "  <h1>候选人预览</h1>",
            "  <ul>",
            *candidate_items,
            "  </ul>",
            "  <h1>质量审计</h1>",
            f"  <p>问题计数：{_json_for_xml(issue_counts)}</p>",
            f"  <p>重复候选人 ID：{_json_for_xml(duplicate_ids)}</p>",
            "  <h1>敏感数据边界</h1>",
            "  <p>不读取、不上传 SQLite DB、sync zip、raw/search、raw/detail、raw capture 或 raw live run；发布 manifest 只保留 reports 下生成的安全 source files。</p>",
            "</document>",
        ]
    )


def write_source_files(
    manifest: dict[str, Any],
    report: dict[str, Any],
    audit: dict[str, Any],
    outreach_rows: list[dict[str, str]],
) -> None:
    generated = manifest["generated_files"]
    summary_xml = Path(generated["summary_xml"])
    summary_xml.parent.mkdir(parents=True, exist_ok=True)
    summary_xml.write_text(render_summary_xml(report, audit, outreach_rows), encoding="utf-8-sig")

    fieldnames = _safe_csv_fieldnames(outreach_rows)
    safe_rows = [_filter_row(row, fieldnames) for row in outreach_rows]
    for key in ["candidate_csv", "outreach_csv"]:
        path = Path(generated[key])
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(safe_rows)


def run_publish_commands(commands: list[list[str]], cwd: str | Path | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        if cwd is None:
            completed = subprocess.run(command, text=True, capture_output=True, check=False)
        else:
            completed = subprocess.run(command, text=True, capture_output=True, check=False, cwd=str(cwd))
        result = {
            "argv": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
        if cwd is not None:
            result["cwd"] = str(cwd)
        results.append(result)
        if completed.returncode != 0:
            break
    return results


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成或发布脉脉 campaign 飞书交付包")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--final-report", required=True)
    parser.add_argument("--outreach-csv", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--outreach-template", default="templates/maimai-campaign/outreach-queue-fields.json")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    manifest = build_delivery_manifest(
        campaign_root=args.campaign_root,
        final_report=args.final_report,
        outreach_csv=args.outreach_csv,
        audit_json=args.audit_json,
        dry_run=args.dry_run,
    )
    report = _load_json(args.final_report)
    audit = _load_json(args.audit_json)
    outreach_rows = _read_csv(args.outreach_csv)
    write_source_files(manifest, report, audit, outreach_rows)

    returncode = 0
    if not args.dry_run:
        manifest["publish_blocked"] = {
            "reason": "requires_sheet_ids_after_create",
            "message": (
                "非 dry-run 不自动执行空 Sheet create；先按 publish_steps 创建 Sheet，"
                "取得 sheet_id 后再执行 append command_template。"
            ),
        }
        returncode = 2

    out = Path(args.manifest_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(manifest, ensure_ascii=False, indent=2)
    out.write_text(serialized, encoding="utf-8-sig")
    print(serialized)
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
