from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

from scripts.maimai_url import is_openable_maimai_profile_url


SCHEMA = "jd_talent_delivery_feishu_manifest_v1"
PUBLISH_RESULT_SCHEMA = "jd_talent_delivery_feishu_publish_result_v1"
DRY_RUN_RESULT_SCHEMA = "jd_talent_delivery_feishu_dry_run_results_v1"
DEFAULT_WIKI_SPACE_ID = "7642607697183001542"
DEFAULT_FEISHU_BASE_URL = "https://sq8org1v4k6.feishu.cn"
DEFAULT_NOTIFY_CHAT_NAME = "JD需求协同"
SHEET_WRITE_CHUNK_SIZE = 25
ARTIFACT_MARKERS = (
    "talent.db",
    "raw/search",
    "raw/detail",
    "raw capture",
    "raw_capture",
    "raw_profile",
    "raw_payload",
    "sync_bundle",
    "trackable_token",
    "access_token",
    "authorization: bearer",
    "sessionid",
    "cookie:",
    ".sqlite",
    ".zip",
    ".db",
)
EXACT_MARKERS = ("database",)
MOJIBAKE_MARKERS = ("锛", "鐨", "�", "���", "娣峰")

REQUIRED_SOURCE_FILES: dict[str, str] = {
    "jd": "source/jd.md",
    "profile": "profile/role-deep-dive.md",
    "recommendation": "reports/talent-recommendation.md",
    "outreach": "reports/outreach-queue.csv",
}
INTERNAL_FEISHU_RESULT_FILES = {
    "feishu/dry-run-results.json",
    "feishu/publish-results.json",
    "feishu/im-notification-results.json",
}
Runner = Callable[[list[str], str | None], subprocess.CompletedProcess]


def _normalize_text(value: str | Path) -> str:
    return str(value).lower().replace("\\", "/")


def _raise_sensitive(marker: str, label: str) -> None:
    raise ValueError(f"sensitive marker found: {marker} in {label}")


def _assert_no_artifact_marker(value: str | Path, *, label: str) -> None:
    normalized = _normalize_text(value)
    for marker in ARTIFACT_MARKERS:
        if marker in normalized:
            _raise_sensitive(marker, label)


def _assert_no_exact_marker(value: str, *, label: str) -> None:
    normalized = _normalize_text(value).strip()
    for marker in EXACT_MARKERS:
        if normalized == marker:
            _raise_sensitive(marker, label)


def _marker_allowed_in_field(marker: str, field_name: str, value: str) -> bool:
    return (
        marker == "trackable_token"
        and field_name == "profile_url"
        and is_openable_maimai_profile_url(value)
    )


def _assert_safe_field_value(value: Any, *, field_name: str = "", label: str) -> None:
    text = "" if value is None else str(value)
    normalized = _normalize_text(text)
    for marker in ARTIFACT_MARKERS:
        if marker in normalized and not _marker_allowed_in_field(marker, field_name, text):
            _raise_sensitive(marker, label)
    _assert_no_exact_marker(text, label=label)


def _assert_safe_path(value: str | Path, *, label: str) -> None:
    _assert_no_artifact_marker(value, label=label)
    parts = [part.strip() for part in _normalize_text(value).split("/") if part.strip()]
    for marker in EXACT_MARKERS:
        if marker in parts:
            _raise_sensitive(marker, label)


def _assert_safe_content(value: str, *, label: str) -> None:
    _assert_no_artifact_marker(value, label=label)
    for line in value.splitlines():
        _assert_no_exact_marker(line, label=label)
    for row in csv.reader(value.splitlines()):
        for cell in row:
            _assert_no_exact_marker(cell, label=label)


def _assert_safe_csv_content(value: str, *, label: str) -> None:
    rows = list(csv.reader(value.splitlines()))
    if not rows:
        return
    headers = [str(item) for item in rows[0]]
    for header in headers:
        _assert_safe_field_value(header, label=label)
    for row in rows[1:]:
        for index, cell in enumerate(row):
            field_name = headers[index] if index < len(headers) else ""
            _assert_safe_field_value(cell, field_name=field_name, label=label)


def _assert_safe_json_value(value: Any, *, field_name: str = "", label: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            _assert_safe_field_value(key_text, label=label)
            _assert_safe_json_value(item, field_name=key_text, label=label)
        return
    if isinstance(value, list):
        for item in value:
            _assert_safe_json_value(item, field_name=field_name, label=label)
        return
    _assert_safe_field_value(value, field_name=field_name, label=label)


def _assert_safe_file_content(path: Path, value: str, *, label: str) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        _assert_safe_csv_content(value, label=label)
        return
    if suffix == ".json":
        try:
            _assert_safe_json_value(json.loads(value), label=label)
            return
        except json.JSONDecodeError:
            pass
    _assert_safe_content(value, label=label)


def _iter_manifest_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        strings: list[str] = []
        for key, item in value.items():
            strings.extend(_iter_manifest_strings(key))
            strings.extend(_iter_manifest_strings(item))
        return strings
    if isinstance(value, list):
        strings = []
        for item in value:
            strings.extend(_iter_manifest_strings(item))
        return strings
    return []


def _assert_safe_manifest(manifest: dict[str, Any]) -> None:
    serialized = json.dumps(manifest, ensure_ascii=False)
    _assert_no_artifact_marker(serialized, label="serialized manifest")
    for value in _iter_manifest_strings(manifest):
        _assert_no_artifact_marker(value, label="manifest value")
        _assert_no_exact_marker(value, label="manifest value")


def _relative_to_root(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _required_files(root: Path) -> dict[str, Path]:
    return {name: root / relative_path for name, relative_path in REQUIRED_SOURCE_FILES.items()}


def _read_safe_file(path: Path, root: Path) -> None:
    _assert_safe_path(path, label=f"path {path}")
    _assert_safe_path(_relative_to_root(path, root), label=f"relative path {path}")
    _assert_safe_file_content(
        path,
        path.read_text(encoding="utf-8-sig"),
        label=f"content {path}",
    )


def _argv_step(stage: str, argv: list[str]) -> dict[str, Any]:
    return {
        "stage": stage,
        "command": " ".join(argv),
        "argv": argv,
    }


def _maybe_dry_run(argv: list[str], dry_run: bool) -> list[str]:
    if dry_run:
        return [*argv, "--dry-run"]
    return argv


def _wiki_parent_create_command(jd_title: str, wiki_space_id: str, dry_run: bool) -> list[str]:
    return _maybe_dry_run(
        [
            "lark-cli",
            "wiki",
            "+node-create",
            "--as",
            "user",
            "--space-id",
            wiki_space_id,
            "--title",
            jd_title,
        ],
        dry_run,
    )


def _drive_import_command(source_file: str, import_type: str, title: str, dry_run: bool) -> list[str]:
    return _maybe_dry_run(
        [
            "lark-cli",
            "drive",
            "+import",
            "--type",
            import_type,
            "--as",
            "user",
            "--file",
            source_file,
            "--name",
            title,
        ],
        dry_run,
    )


def _wiki_move_command(
    obj_type: str,
    obj_token: str,
    wiki_space_id: str,
    dry_run: bool,
    target_parent_token: str = "<jd_delivery_parent_node_token>",
) -> list[str]:
    return _maybe_dry_run(
        [
            "lark-cli",
            "wiki",
            "+move",
            "--as",
            "user",
            "--obj-type",
            obj_type,
            "--obj-token",
            obj_token,
            "--target-space-id",
            wiki_space_id,
            "--target-parent-token",
            target_parent_token,
        ],
        dry_run,
    )


def _wiki_node_list_command(wiki_space_id: str, parent_node_token: str) -> list[str]:
    return [
        "lark-cli",
        "wiki",
        "+node-list",
        "--as",
        "user",
        "--space-id",
        wiki_space_id,
        "--parent-node-token",
        parent_node_token,
        "--page-size",
        "50",
        "--format",
        "json",
    ]


def _wiki_node_get_command(token: str, obj_type: str, wiki_space_id: str) -> list[str]:
    return [
        "lark-cli",
        "wiki",
        "+node-get",
        "--as",
        "user",
        "--token",
        token,
        "--obj-type",
        obj_type,
        "--space-id",
        wiki_space_id,
        "--format",
        "json",
    ]


def _docs_fetch_command(doc_token: str) -> list[str]:
    return [
        "lark-cli",
        "docs",
        "+fetch",
        "--as",
        "user",
        "--api-version",
        "v2",
        "--doc",
        doc_token,
        "--format",
        "json",
        "--scope",
        "outline",
        "--max-depth",
        "3",
    ]


def _sheets_info_command(spreadsheet_token: str) -> list[str]:
    return [
        "lark-cli",
        "sheets",
        "+info",
        "--as",
        "user",
        "--spreadsheet-token",
        spreadsheet_token,
    ]


def _sheets_read_command(spreadsheet_token: str, sheet_id: str) -> list[str]:
    return [
        "lark-cli",
        "sheets",
        "+read",
        "--as",
        "user",
        "--spreadsheet-token",
        spreadsheet_token,
        "--sheet-id",
        sheet_id,
        "--range",
        "A1:Z5",
    ]


def _sheets_create_command(title: str, dry_run: bool) -> list[str]:
    return _maybe_dry_run(
        [
            "lark-cli",
            "sheets",
            "+create",
            "--as",
            "user",
            "--title",
            title,
        ],
        dry_run,
    )


def _sheets_write_command(
    spreadsheet_token: str,
    sheet_id: str,
    cell_range: str,
    values: list[list[str]],
    dry_run: bool,
) -> list[str]:
    return _maybe_dry_run(
        [
            "lark-cli",
            "sheets",
            "+write",
            "--as",
            "user",
            "--spreadsheet-token",
            spreadsheet_token,
            "--sheet-id",
            sheet_id,
            "--range",
            cell_range,
            "--values",
            json.dumps(values, ensure_ascii=False, separators=(",", ":")),
        ],
        dry_run,
    )


def _im_send_command(
    message: str,
    idempotency_key: str,
    *,
    user_id: str | None = None,
    chat_id: str | None = None,
) -> list[str]:
    if bool(user_id) == bool(chat_id):
        raise ValueError("exactly one of user_id or chat_id is required")
    argv = [
        "lark-cli",
        "im",
        "+messages-send",
        "--as",
        "user",
        "--idempotency-key",
        idempotency_key,
    ]
    if user_id:
        argv.extend(["--user-id", user_id])
    else:
        argv.extend(["--chat-id", str(chat_id)])
    return [*argv, "--text", message]


def _im_chat_search_command(query: str) -> list[str]:
    return [
        "lark-cli",
        "im",
        "+chat-search",
        "--as",
        "user",
        "--query",
        query,
        "--disable-search-by-user",
        "--search-types",
        "private,public_joined,external",
        "--page-size",
        "10",
        "--format",
        "json",
    ]


def _column_name(index: int) -> str:
    if index < 1:
        raise ValueError("column index must be >= 1")
    letters = ""
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _read_csv_values(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return [[str(cell) for cell in row] for row in reader]


def _sheet_write_chunks(
    rows: list[list[str]],
    *,
    chunk_size: int = SHEET_WRITE_CHUNK_SIZE,
) -> list[tuple[str, list[list[str]]]]:
    if not rows:
        raise ValueError("outreach CSV is empty")
    width = max(len(row) for row in rows)
    if width <= 0:
        raise ValueError("outreach CSV has no columns")
    end_column = _column_name(width)
    chunks: list[tuple[str, list[list[str]]]] = []
    for offset in range(0, len(rows), chunk_size):
        chunk = [row + [""] * (width - len(row)) for row in rows[offset : offset + chunk_size]]
        start_row = offset + 1
        end_row = start_row + len(chunk) - 1
        chunks.append((f"A{start_row}:{end_column}{end_row}", chunk))
    return chunks


def _publish_steps(
    source_files: dict[str, str],
    jd_title: str,
    wiki_space_id: str,
    dry_run: bool,
) -> list[dict[str, Any]]:
    return [
        _argv_step(
            "wiki_parent_create",
            _wiki_parent_create_command(jd_title, wiki_space_id, dry_run),
        ),
        _argv_step(
            "import_jd_doc",
            _drive_import_command(source_files["jd"], "docx", f"{jd_title} JD", dry_run),
        ),
        _argv_step("move_jd_doc", _wiki_move_command("docx", "<jd_docx_token>", wiki_space_id, dry_run)),
        _argv_step(
            "import_role_profile_doc",
            _drive_import_command(source_files["profile"], "docx", f"{jd_title} role profile", dry_run),
        ),
        _argv_step(
            "move_role_profile_doc",
            _wiki_move_command("docx", "<role_profile_docx_token>", wiki_space_id, dry_run),
        ),
        _argv_step(
            "import_recommendation_doc",
            _drive_import_command(source_files["recommendation"], "docx", f"{jd_title} recommendation report", dry_run),
        ),
        _argv_step(
            "move_recommendation_doc",
            _wiki_move_command("docx", "<recommendation_docx_token>", wiki_space_id, dry_run),
        ),
        _argv_step(
            "create_outreach_sheet",
            _sheets_create_command(f"{jd_title} outreach queue", dry_run),
        ),
        _argv_step(
            "write_outreach_sheet_utf8_json",
            _sheets_write_command(
                "<outreach_sheet_token>",
                "<first_sheet_id>",
                "A1:<last_column><last_row>",
                [["<utf8_csv_values>"]],
                dry_run,
            ),
        ),
        _argv_step(
            "move_outreach_sheet",
            _wiki_move_command("sheet", "<outreach_sheet_token>", wiki_space_id, dry_run),
        ),
    ]


def build_publish_manifest(
    output_root: str | Path,
    jd_title: str,
    wiki_space_id: str,
    dry_run: bool = True,
) -> dict[str, Any]:
    root = Path(output_root)
    _assert_safe_path(root, label=f"output root {root}")

    files = _required_files(root)
    for path in files.values():
        if not path.exists():
            raise FileNotFoundError(path)
        _read_safe_file(path, root)

    source_files = {name: _relative_to_root(path, root) for name, path in files.items()}
    preflight = [
        _argv_step("doctor", ["lark-cli", "doctor"]),
        _argv_step("auth_status", ["lark-cli", "auth", "status"]),
    ]
    publish_steps = _publish_steps(source_files, jd_title, wiki_space_id, bool(dry_run))

    manifest = {
        "schema": SCHEMA,
        "output_root": str(root),
        "jd_title": jd_title,
        "wiki_space_id": wiki_space_id,
        "dry_run": bool(dry_run),
        "source_files": source_files,
        "preflight": preflight,
        "publish_steps": publish_steps,
        "commands": [step["argv"] for step in [*preflight, *publish_steps]],
        "command_shapes": [
            "lark-cli doctor",
            "lark-cli auth status",
            "wiki +node-create",
            "drive +import --type docx",
            "sheets +create",
            "sheets +write --values",
            "wiki +move",
            "im +chat-search",
            "im +messages-send",
        ],
        "publish_ready": False,
        "notes": [
            "Preflight must run lark-cli doctor and lark-cli auth status before publish.",
            "Markdown files are imported with drive import as docx, then moved into Wiki.",
            "Outreach CSV must not be imported with drive import as sheet; create a Sheet and write UTF-8 JSON values with sheets +write.",
            "Sheet publishing uses direct cell writes so Chinese text is never parsed through CSV import encoding heuristics.",
            f"After successful readback, search the {DEFAULT_NOTIFY_CHAT_NAME} chat and send a completion notification with im +messages-send.",
        ],
    }
    _assert_safe_manifest(manifest)
    return manifest


def _load_json_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _scan_output_tree(root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".csv", ".txt", ".xml"}:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in INTERNAL_FEISHU_RESULT_FILES:
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            _assert_safe_path(path, label=relative)
            _assert_safe_file_content(path, text, label=relative)
        except ValueError as exc:
            issues.append(str(exc))
        for marker in MOJIBAKE_MARKERS:
            if marker in text:
                issues.append(f"mojibake marker found: {marker} in {relative}")
    return issues


def _ranked_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = data.get("ranked")
    if isinstance(ranked, list):
        return [item for item in ranked if isinstance(item, dict)]
    grades = data.get("grades")
    items: list[dict[str, Any]] = []
    if isinstance(grades, dict):
        for grade in ("A", "B", "C", "淘汰"):
            grade_items = grades.get(grade)
            if isinstance(grade_items, list):
                items.extend(item for item in grade_items if isinstance(item, dict))
    return items


def validate_delivery_package(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root)
    critical: list[str] = []
    warnings: list[str] = []

    required = {
        "recommendation_json": root / "reports" / "talent-recommendation.json",
        "detailed_rank_json": root / "scoring" / "detailed-rank.json",
        "outreach_csv": root / "reports" / "outreach-queue.csv",
    }
    for name, path in required.items():
        if not path.exists():
            critical.append(f"missing_required_file:{name}:{path.relative_to(root).as_posix()}")

    recommendation: dict[str, Any] = {}
    ranked: list[dict[str, Any]] = []
    if required["recommendation_json"].exists():
        try:
            recommendation = _load_json_file(required["recommendation_json"])
            ranked = _ranked_items(recommendation)
        except (json.JSONDecodeError, ValueError) as exc:
            critical.append(f"bad_recommendation_json:{exc}")
    if not ranked and required["detailed_rank_json"].exists():
        try:
            ranked = _ranked_items(_load_json_file(required["detailed_rank_json"]))
        except (json.JSONDecodeError, ValueError) as exc:
            critical.append(f"bad_detailed_rank_json:{exc}")

    top_n = int(recommendation.get("top_n") or len(ranked) or 0)
    if top_n <= 0:
        critical.append("invalid_top_n")
    if len(ranked) < top_n:
        critical.append("ranked_count_below_top_n")
    top_rows = ranked[:top_n]
    if top_rows and all(str(item.get("grade") or "") in {"C", "淘汰"} for item in top_rows):
        critical.append("top_n_all_low_confidence")
    for item in top_rows:
        missing = [
            field
            for field in ("candidate_id", "score", "grade", "recommendation_label", "profile_url")
            if item.get(field) in (None, "")
        ]
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not evidence.get("key_evidence") and not item.get("key_evidence"):
            missing.append("key_evidence")
        if missing:
            critical.append(
                f"candidate_missing_fields:{item.get('candidate_id', '<unknown>')}:{','.join(missing)}"
            )

    rows: list[dict[str, str]] = []
    if required["outreach_csv"].exists():
        try:
            rows = _read_csv_rows(required["outreach_csv"])
        except csv.Error as exc:
            critical.append(f"outreach_csv_parse_error:{exc}")
    if top_n > 0 and len(rows) != top_n:
        critical.append("outreach_csv_row_count_mismatch")
    required_csv_fields = {
        "candidate_id",
        "company",
        "title",
        "score",
        "grade",
        "suggested_outreach_angle",
        "profile_url",
    }
    for index, row in enumerate(rows, start=2):
        missing = sorted(field for field in required_csv_fields if not row.get(field))
        if missing:
            critical.append(f"outreach_row_missing_fields:{index}:{','.join(missing)}")
        company = row.get("company") or ""
        title = row.get("title") or ""
        angle = row.get("suggested_outreach_angle") or ""
        if company and title and (company not in angle or title not in angle):
            warnings.append(f"outreach_angle_missing_company_or_title:{index}")

    quality_path = root / "reports" / "quality-gates.json"
    if quality_path.exists():
        try:
            quality = _load_json_file(quality_path)
            if quality.get("status") == "blocked":
                issues = quality.get("critical_issues") if isinstance(quality.get("critical_issues"), list) else []
                suffix = ",".join(str(item) for item in issues) or "unknown"
                critical.append(f"quality_gate_blocked:{suffix}")
        except (json.JSONDecodeError, ValueError) as exc:
            critical.append(f"bad_quality_gates_json:{exc}")
    else:
        warnings.append("missing_quality_gates_json")

    critical.extend(_scan_output_tree(root))
    result = {
        "schema": "jd_talent_delivery_publish_preflight_v1",
        "status": "blocked" if critical else "passed",
        "critical_issues": sorted(dict.fromkeys(critical)),
        "warnings": sorted(dict.fromkeys(warnings)),
        "top_n": top_n,
        "outreach_rows": len(rows),
    }
    return result


def _csv_preview_values(path: Path, limit: int = 5) -> list[list[str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        return [[str(cell) for cell in row] for _, row in zip(range(limit), reader)]


def _preview_values(data: dict[str, Any]) -> list[list[str]]:
    candidates: list[Any] = [data.get("values")]
    value_range = data.get("valueRange")
    if isinstance(value_range, dict):
        candidates.append(value_range.get("values"))
    nested = data.get("data")
    if isinstance(nested, dict):
        candidates.append(nested.get("values"))
        nested_value_range = nested.get("valueRange")
        if isinstance(nested_value_range, dict):
            candidates.append(nested_value_range.get("values"))

    values = next((item for item in candidates if isinstance(item, list)), None)
    if values is None:
        raise ValueError("sheet readback missing values")
    result: list[list[str]] = []
    for row in values:
        if isinstance(row, list):
            result.append([_preview_cell_value(cell) for cell in row])
    return result


def _preview_cell_value(cell: Any) -> str:
    if isinstance(cell, bool):
        return "TRUE" if cell else "FALSE"
    if isinstance(cell, dict):
        for key in ("text", "link"):
            value = cell.get(key)
            if value not in (None, ""):
                return str(value)
        return str(cell)
    if isinstance(cell, list):
        return "".join(_preview_cell_value(item) for item in cell)
    return str(cell)


def _assert_sheet_readback_matches(source_csv: Path, preview: dict[str, Any]) -> None:
    expected = _csv_preview_values(source_csv)
    actual = _preview_values(preview)
    comparable = [row[: len(expected_row)] for row, expected_row in zip(actual, expected)]
    if comparable != expected:
        raise ValueError("sheet readback mismatch")


def _needs_direct_node_runner(argv: list[str]) -> bool:
    if len(argv) < 3 or argv[0] != "lark-cli":
        return False
    return (argv[1] == "sheets" and argv[2] in {"+create", "+write"}) or (
        argv[1] == "im" and argv[2] == "+messages-send"
    )


def _node_candidates() -> list[str]:
    candidates = []
    override = os.environ.get("LARK_CLI_NODE")
    if override:
        candidates.append(override)
    found = shutil.which("node")
    if found:
        candidates.append(found)
    candidates.append(r"D:\Program Files\nodejs\node.exe")
    return candidates


def _run_js_candidates() -> list[str]:
    candidates = []
    override = os.environ.get("LARK_CLI_RUN_JS")
    if override:
        candidates.append(override)
    appdata = os.environ.get("APPDATA")
    if appdata:
        candidates.append(str(Path(appdata) / "npm" / "node_modules" / "@larksuite" / "cli" / "scripts" / "run.js"))
    candidates.append(
        str(
            Path.home()
            / "AppData"
            / "Roaming"
            / "npm"
            / "node_modules"
            / "@larksuite"
            / "cli"
            / "scripts"
            / "run.js"
        )
    )
    return candidates


def _resolve_direct_node_lark_cli_argv(argv: list[str]) -> list[str] | None:
    node = next((candidate for candidate in _node_candidates() if Path(candidate).exists()), None)
    run_js = next((candidate for candidate in _run_js_candidates() if Path(candidate).exists()), None)
    if not node or not run_js:
        return None
    return [node, run_js, *argv[1:]]


def _resolve_lark_cli_argv(argv: list[str]) -> list[str]:
    resolved = list(argv)
    if not resolved or resolved[0] != "lark-cli":
        return resolved

    if _needs_direct_node_runner(resolved):
        direct = _resolve_direct_node_lark_cli_argv(resolved)
        if direct:
            return direct

    override = os.environ.get("LARK_CLI")
    if override:
        return [override, *resolved[1:]]

    for name in ("lark-cli.cmd", "lark-cli.exe", "lark-cli", "lark-cli.ps1"):
        found = shutil.which(name)
        if found:
            return [found, *resolved[1:]]
    return resolved


def default_runner(argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        _resolve_lark_cli_argv(argv),
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )


def _run(argv: list[str], runner: Runner, cwd: str | None = None) -> dict[str, Any]:
    completed = runner(argv, cwd)
    result = {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout or "",
        "stderr": completed.stderr or "",
    }
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(argv)}: {result['stderr']}")
    return result


def _stdout_json(result: dict[str, Any]) -> dict[str, Any]:
    text = str(result.get("stdout") or "").strip() or "{}"
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = text[:120].replace("\r", "\\r").replace("\n", "\\n")
        raise ValueError(f"command stdout is not valid JSON: {snippet}") from exc
    if not isinstance(data, dict):
        raise ValueError("command stdout JSON must be an object")
    return data


def _optional_token(data: dict[str, Any], *keys: str) -> str | None:
    wanted = {key.replace("_", "").casefold() for key in keys}

    def visit(value: Any) -> str | None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.replace("_", "").casefold() in wanted and isinstance(item, str) and item:
                    return item
            for item in value.values():
                found = visit(item)
                if found:
                    return found
        elif isinstance(value, list):
            for item in value:
                found = visit(item)
                if found:
                    return found
        return None

    return visit(data)


def _chat_search_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"chats", "items"} and isinstance(item, list):
                    items.extend(candidate for candidate in item if isinstance(candidate, dict))
                else:
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(data)
    return items


def _chat_item_text(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    return _optional_token(item, *keys)


def _resolve_chat_from_search(data: dict[str, Any], chat_name: str) -> dict[str, str]:
    matches: list[dict[str, str]] = []
    seen: set[str] = set()
    available_names: list[str] = []
    for item in _chat_search_items(data):
        chat_id = _chat_item_text(item, "chat_id", "chatId")
        name = _chat_item_text(item, "name", "chat_name", "chatName", "title")
        if name:
            available_names.append(name)
        if not chat_id or name != chat_name or chat_id in seen:
            continue
        seen.add(chat_id)
        matches.append({"chat_id": chat_id, "name": name})

    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"notification chat is ambiguous: {chat_name}")
    suffix = f"; returned: {', '.join(available_names[:5])}" if available_names else ""
    raise ValueError(f"notification chat not found: {chat_name}{suffix}")


def _wiki_nodes(data: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = []
    if isinstance(data.get("nodes"), list):
        candidates.append(data["nodes"])
    if isinstance(data.get("items"), list):
        candidates.append(data["items"])
    nested = data.get("data")
    if isinstance(nested, dict):
        if isinstance(nested.get("nodes"), list):
            candidates.append(nested["nodes"])
        if isinstance(nested.get("items"), list):
            candidates.append(nested["items"])

    nodes: list[dict[str, Any]] = []
    for candidate in candidates:
        for item in candidate:
            if isinstance(item, dict):
                nodes.append(item)
    return nodes


def _nodes_by_title(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_title: dict[str, dict[str, Any]] = {}
    for node in _wiki_nodes(data):
        title = node.get("title")
        if isinstance(title, str) and title and title not in by_title:
            by_title[title] = node
    return by_title


def _first_sheet_id(data: dict[str, Any]) -> str:
    nested = data.get("data")
    if isinstance(nested, dict):
        sheets_container = nested.get("sheets")
        if isinstance(sheets_container, dict):
            sheets = sheets_container.get("sheets")
            if isinstance(sheets, list):
                for sheet in sheets:
                    if isinstance(sheet, dict) and isinstance(sheet.get("sheet_id"), str) and sheet["sheet_id"]:
                        return str(sheet["sheet_id"])
    raise ValueError("missing sheet_id in sheets +info output")


def _token(data: dict[str, Any], *keys: str) -> str:
    token = _optional_token(data, *keys)
    if token:
        return token
    raise ValueError(f"missing token keys: {keys}")


def _without_dry_run(argv: list[str]) -> list[str]:
    if argv and argv[-1] == "--dry-run":
        return argv[:-1]
    return list(argv)


def _published_url(obj_type: str, obj_token: str, base_url: str = DEFAULT_FEISHU_BASE_URL) -> str:
    path = "sheets" if obj_type == "sheet" else obj_type
    return f"{base_url.rstrip('/')}/{path}/{obj_token}"


def _published_links(
    published: list[dict[str, Any]],
    parent_node_token: str,
    base_url: str = DEFAULT_FEISHU_BASE_URL,
) -> dict[str, str]:
    links = {"wiki": f"{base_url.rstrip('/')}/wiki/{parent_node_token}"}
    for item in published:
        name = str(item.get("name") or "")
        obj_type = str(item.get("obj_type") or "")
        obj_token = str(item.get("obj_token") or "")
        if name and obj_type and obj_token:
            links[name] = _published_url(obj_type, obj_token, base_url)
    return links


def _grade_counts(ranked: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"A": 0, "B": 0, "C": 0, "淘汰": 0}
    for item in ranked:
        grade = str(item.get("grade") or "")
        if grade in counts:
            counts[grade] += 1
    return counts


def _recommendation_report_summary(root: Path) -> dict[str, Any]:
    recommendation_path = root / "reports" / "talent-recommendation.json"
    data = _load_json_file(recommendation_path) if recommendation_path.exists() else {}
    ranked = _ranked_items(data)
    top_n = int(data.get("top_n") or len(ranked) or 0)
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    risk_flags = data.get("risk_flags") if isinstance(data.get("risk_flags"), list) else []
    confidence_note = ""
    if "low_missing_jd_body" in {str(item) for item in risk_flags}:
        confidence_note = "JD 正文待补充，本轮为低置信优先深审名单。"
    elif data.get("confidence_note"):
        confidence_note = str(data["confidence_note"])
    return {
        "top_n": top_n,
        "coarse_total": summary.get("coarse_total") or summary.get("total_candidates") or data.get("coarse_total"),
        "total_scored": summary.get("total_scored") or data.get("total_scored") or len(ranked),
        "grade_counts": _grade_counts(ranked[:top_n] if top_n else ranked),
        "confidence_note": confidence_note,
    }


def build_completion_notification_text(
    *,
    jd_title: str,
    publish_result: dict[str, Any],
    report_summary: dict[str, Any],
    links: dict[str, str],
) -> str:
    quality = publish_result.get("package_quality") if isinstance(publish_result.get("package_quality"), dict) else {}
    top_n = report_summary.get("top_n") or quality.get("top_n") or 0
    outreach_rows = quality.get("outreach_rows")
    total_scored = report_summary.get("total_scored") or "未知"
    coarse_total = report_summary.get("coarse_total") or "未知"
    counts = report_summary.get("grade_counts") if isinstance(report_summary.get("grade_counts"), dict) else {}
    count_line = (
        f"Top{top_n}：A={counts.get('A', 0)}/B={counts.get('B', 0)}/"
        f"C={counts.get('C', 0)}/淘汰={counts.get('淘汰', 0)}"
    )
    note = str(report_summary.get("confidence_note") or "无")

    lines = [
        f"{jd_title} 推荐结果已发布",
        "",
        f"任务执行结果：{publish_result.get('status', 'published')}；质量门禁 {quality.get('status', 'passed')}；外联表 {outreach_rows if outreach_rows is not None else '未知'} 行。",
        "成果物清单：",
        f"- Wiki目录：{links.get('wiki', '')}",
        f"- JD：{links.get('jd', '')}",
        f"- 岗位画像：{links.get('profile', '')}",
        f"- 推荐报告：{links.get('recommendation', '')}",
        f"- 外联表：{links.get('outreach', '')}",
        "",
        "推荐报告摘要：",
        f"- 匹配口径：本地人才库只读；粗筛 {coarse_total} 人，精排 {total_scored} 人。",
        f"- {count_line}",
        f"- 注意：{note}",
    ]
    return "\n".join(lines)


def _auth_user_id(auth_status: dict[str, Any]) -> str | None:
    for key in ("userOpenId", "user_open_id", "openId", "open_id", "userId", "user_id"):
        value = _optional_token(auth_status, key)
        if value:
            return value
    return None


def _notification_idempotency_key(output_root: Path, parent_node_token: str) -> str:
    digest = hashlib.sha1(f"{output_root.resolve()}::{parent_node_token}".encode("utf-8")).hexdigest()[:20]
    return f"jd-delivery-{digest}"


def _send_completion_notification(
    *,
    root: Path,
    message: str,
    parent_node_token: str,
    auth_status: dict[str, Any],
    runner: Runner,
    cwd: str,
    command_results: list[dict[str, Any]],
    notify_user_id: str | None,
    notify_chat_id: str | None,
) -> dict[str, Any]:
    if notify_user_id and notify_chat_id:
        raise ValueError("notify_user_id and notify_chat_id are mutually exclusive")
    target_user_id = notify_user_id
    target_chat_id = notify_chat_id
    target_chat_name: str | None = None
    if not target_user_id and not target_chat_id:
        target_chat_name = DEFAULT_NOTIFY_CHAT_NAME
        search_result = _run(_im_chat_search_command(target_chat_name), runner, cwd=cwd)
        command_results.append(search_result)
        chat = _resolve_chat_from_search(_stdout_json(search_result), target_chat_name)
        target_chat_id = chat["chat_id"]
        target_chat_name = chat["name"]
    if not target_user_id and not target_chat_id:
        raise ValueError("notification target is missing: pass --notify-user-id or --notify-chat-id")

    message_path = root / "feishu" / "im-notification-message.txt"
    message_path.parent.mkdir(parents=True, exist_ok=True)
    message_path.write_text(message, encoding="utf-8-sig")

    argv = _im_send_command(
        message,
        _notification_idempotency_key(root, parent_node_token),
        user_id=target_user_id,
        chat_id=target_chat_id,
    )
    result = _run(argv, runner, cwd=cwd)
    command_results.append(result)
    notification = {
        "status": "sent",
        "target_type": "user_id" if target_user_id else ("chat_name" if target_chat_name else "chat_id"),
        "target_id": target_user_id or target_chat_id,
        "message_file": "feishu/im-notification-message.txt",
        "send_result": result,
    }
    if target_chat_name:
        notification["target_name"] = target_chat_name
    out = root / "feishu" / "im-notification-results.json"
    out.write_text(json.dumps(notification, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return notification


def _write_outreach_sheet_from_csv(
    *,
    root: Path,
    source_file: str,
    spreadsheet_token: str,
    sheet_id: str,
    run: Callable[[list[str]], dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = _read_csv_values(root / source_file)
    write_results: list[dict[str, Any]] = []
    for cell_range, values in _sheet_write_chunks(rows):
        write_dry_run = _sheets_write_command(
            spreadsheet_token,
            sheet_id,
            cell_range,
            values,
            dry_run=True,
        )
        run(write_dry_run)
        write_real = run(_without_dry_run(write_dry_run))
        write_results.append(
            {
                "range": cell_range,
                "rows": len(values),
                "columns": len(values[0]) if values else 0,
                "result": _stdout_json(write_real),
            }
        )
    return write_results


def publish_output(
    output_root: str | Path,
    jd_title: str,
    wiki_space_id: str,
    runner: Runner = default_runner,
    parent_node_token: str | None = None,
    notify: bool = True,
    notify_user_id: str | None = None,
    notify_chat_id: str | None = None,
) -> dict[str, Any]:
    root = Path(output_root)
    package_quality = validate_delivery_package(root)
    if package_quality["status"] != "passed":
        raise ValueError(
            "delivery package is not publishable: "
            + "; ".join(package_quality["critical_issues"])
        )
    manifest = build_publish_manifest(root, jd_title=jd_title, wiki_space_id=wiki_space_id, dry_run=True)
    command_results: list[dict[str, Any]] = []
    dry_run_results: list[dict[str, Any]] = []
    cwd = str(root)

    def run(argv: list[str]) -> dict[str, Any]:
        result = _run(argv, runner, cwd=cwd)
        command_results.append(result)
        if "--dry-run" in argv:
            dry_run_results.append(result)
        return result

    auth_status: dict[str, Any] = {}
    for step in manifest["preflight"]:
        preflight_result = run(step["argv"])
        if step.get("stage") == "auth_status":
            auth_status = _stdout_json(preflight_result)

    existing_children: dict[str, dict[str, Any]] = {}
    if parent_node_token:
        existing_children = _nodes_by_title(_stdout_json(run(_wiki_node_list_command(wiki_space_id, parent_node_token))))
    else:
        parent_dry_run = _wiki_parent_create_command(jd_title, wiki_space_id, dry_run=True)
        run(parent_dry_run)
        parent_real = run(_without_dry_run(parent_dry_run))
        parent_node_token = _token(_stdout_json(parent_real), "node_token", "wiki_token")

    source_files = manifest["source_files"]
    publish_items = [
        ("jd", "docx", source_files["jd"], f"{jd_title} JD"),
        ("profile", "docx", source_files["profile"], f"{jd_title} role profile"),
        ("recommendation", "docx", source_files["recommendation"], f"{jd_title} recommendation report"),
        ("outreach", "sheet", source_files["outreach"], f"{jd_title} outreach queue"),
    ]
    published: list[dict[str, Any]] = []
    for name, obj_type, source_file, title in publish_items:
        existing = existing_children.get(title)
        if (
            isinstance(existing, dict)
            and existing.get("obj_type") == obj_type
            and isinstance(existing.get("obj_token"), str)
            and existing.get("obj_token")
        ):
            write_results: list[dict[str, Any]] = []
            if obj_type == "sheet":
                sheet_info = _stdout_json(run(_sheets_info_command(str(existing["obj_token"]))))
                sheet_id = _first_sheet_id(sheet_info)
                write_results = _write_outreach_sheet_from_csv(
                    root=root,
                    source_file=source_file,
                    spreadsheet_token=str(existing["obj_token"]),
                    sheet_id=sheet_id,
                    run=run,
                )
            published.append(
                {
                    "name": name,
                    "title": title,
                    "obj_type": obj_type,
                    "source_file": source_file,
                    "obj_token": str(existing["obj_token"]),
                    "node_token": str(existing.get("node_token") or existing["obj_token"]),
                    "reused_existing": True,
                    "move": {"status": "reused_existing", "node": existing},
                    "sheet_write_results": write_results,
                }
            )
            continue

        sheet_write_results: list[dict[str, Any]] = []
        if obj_type == "sheet":
            create_dry_run = _sheets_create_command(title, dry_run=True)
            run(create_dry_run)
            create_real = run(_without_dry_run(create_dry_run))
            obj_token = _token(
                _stdout_json(create_real),
                "spreadsheet_token",
                "obj_token",
                "token",
                "file_token",
            )
            sheet_info = _stdout_json(run(_sheets_info_command(obj_token)))
            sheet_id = _first_sheet_id(sheet_info)
            sheet_write_results = _write_outreach_sheet_from_csv(
                root=root,
                source_file=source_file,
                spreadsheet_token=obj_token,
                sheet_id=sheet_id,
                run=run,
            )
        else:
            import_dry_run = _drive_import_command(source_file, obj_type, title, dry_run=True)
            run(import_dry_run)
            import_real = run(_without_dry_run(import_dry_run))
            obj_token = _token(
                _stdout_json(import_real),
                "obj_token",
                "token",
                "file_token",
                "doc_token",
                "spreadsheet_token",
            )

        move_dry_run = _wiki_move_command(
            obj_type,
            obj_token,
            wiki_space_id,
            dry_run=True,
            target_parent_token=parent_node_token,
        )
        run(move_dry_run)
        move_real = run(_without_dry_run(move_dry_run))
        move_data = _stdout_json(move_real)
        node_token = _optional_token(move_data, "node_token", "wiki_token") or obj_token

        published.append(
            {
                "name": name,
                "title": title,
                "obj_type": obj_type,
                "source_file": source_file,
                "obj_token": obj_token,
                "node_token": node_token,
                "move": move_data,
                "sheet_write_results": sheet_write_results,
            }
        )

    wiki_children = _stdout_json(run(_wiki_node_list_command(wiki_space_id, parent_node_token)))
    node_details: list[dict[str, Any]] = []
    doc_outlines: list[dict[str, Any]] = []
    sheet_previews: list[dict[str, Any]] = []
    for item in published:
        obj_type = str(item["obj_type"])
        node_details.append(_stdout_json(run(_wiki_node_get_command(str(item["obj_token"]), obj_type, wiki_space_id))))
        if obj_type == "docx":
            doc_outlines.append(_stdout_json(run(_docs_fetch_command(str(item["obj_token"])))))
        elif obj_type == "sheet":
            sheet_info = _stdout_json(run(_sheets_info_command(str(item["obj_token"]))))
            sheet_id = _first_sheet_id(sheet_info)
            preview = _stdout_json(run(_sheets_read_command(str(item["obj_token"]), sheet_id)))
            _assert_sheet_readback_matches(root / str(item["source_file"]), preview)
            preview["_sheet_id"] = sheet_id
            preview["_sheet_info"] = sheet_info
            sheet_previews.append(preview)

    dry_run_result = {
        "schema": DRY_RUN_RESULT_SCHEMA,
        "status": "dry_run_ok",
        "results": dry_run_results,
    }
    dry_run_out = root / "feishu" / "dry-run-results.json"
    dry_run_out.parent.mkdir(parents=True, exist_ok=True)
    dry_run_out.write_text(json.dumps(dry_run_result, ensure_ascii=False, indent=2), encoding="utf-8-sig")

    result = {
        "schema": PUBLISH_RESULT_SCHEMA,
        "status": "published",
        "wiki_space_id": wiki_space_id,
        "parent_node_token": parent_node_token,
        "published": published,
        "package_quality": package_quality,
        "readback": {
            "wiki_children": wiki_children,
            "node_details": node_details,
            "doc_outlines": doc_outlines,
            "sheet_previews": sheet_previews,
        },
        "command_results": command_results,
    }
    if notify:
        links = _published_links(published, str(parent_node_token))
        report_summary = _recommendation_report_summary(root)
        message = build_completion_notification_text(
            jd_title=jd_title,
            publish_result=result,
            report_summary=report_summary,
            links=links,
        )
        result["notification"] = _send_completion_notification(
            root=root,
            message=message,
            parent_node_token=str(parent_node_token),
            auth_status=auth_status,
            runner=runner,
            cwd=cwd,
            command_results=command_results,
            notify_user_id=notify_user_id,
            notify_chat_id=notify_chat_id,
        )
    out = root / "feishu" / "publish-results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or publish a JD talent delivery Feishu package")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--jd-title", required=True)
    parser.add_argument("--wiki-space-id", default=DEFAULT_WIKI_SPACE_ID)
    parser.add_argument("--manifest-out")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publish", action="store_true", help="run lark-cli publish workflow after internal dry-runs")
    parser.add_argument("--parent-node-token", help="reuse an existing JD Wiki parent node instead of creating one")
    parser.add_argument("--no-notify", action="store_true", help="skip completion IM notification after publish")
    parser.add_argument("--notify-user-id", help="send completion notification to this user open_id")
    parser.add_argument("--notify-chat-id", help="send completion notification to this chat_id")
    args = parser.parse_args(argv)

    if args.publish:
        if args.dry_run:
            parser.error("--dry-run only applies to manifest generation; publish runs its own dry-run prechecks")
        if args.notify_user_id and args.notify_chat_id:
            parser.error("--notify-user-id and --notify-chat-id are mutually exclusive")
        publish_output(
            args.output_root,
            args.jd_title,
            args.wiki_space_id,
            parent_node_token=args.parent_node_token,
            notify=not args.no_notify,
            notify_user_id=args.notify_user_id,
            notify_chat_id=args.notify_chat_id,
        )
        return 0

    if not args.manifest_out:
        parser.error("--manifest-out is required unless --publish is set")

    manifest = build_publish_manifest(
        args.output_root,
        args.jd_title,
        args.wiki_space_id,
        dry_run=args.dry_run,
    )
    out = Path(args.manifest_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
