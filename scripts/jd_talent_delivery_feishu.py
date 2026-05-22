from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_feishu_manifest_v1"
PUBLISH_RESULT_SCHEMA = "jd_talent_delivery_feishu_publish_result_v1"
DRY_RUN_RESULT_SCHEMA = "jd_talent_delivery_feishu_dry_run_results_v1"
DEFAULT_WIKI_SPACE_ID = "7642607697183001542"
ARTIFACT_MARKERS = (
    "talent.db",
    "raw/search",
    "raw/detail",
    "raw capture",
    "raw_capture",
    "sync_bundle",
    ".sqlite",
    ".zip",
    ".db",
)
EXACT_MARKERS = ("database",)

REQUIRED_SOURCE_FILES: dict[str, str] = {
    "jd": "source/jd.md",
    "profile": "profile/role-deep-dive.md",
    "recommendation": "reports/talent-recommendation.md",
    "outreach": "reports/outreach-queue.csv",
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
    _assert_safe_content(path.read_text(encoding="utf-8-sig"), label=f"content {path}")


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
        "--limit",
        "20",
    ]


def _sheets_read_command(spreadsheet_token: str) -> list[str]:
    return [
        "lark-cli",
        "sheets",
        "+read",
        "--as",
        "user",
        "--spreadsheet-token",
        spreadsheet_token,
        "--range",
        "A1:Z5",
    ]


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
            "import_outreach_sheet",
            _drive_import_command(source_files["outreach"], "sheet", f"{jd_title} outreach queue", dry_run),
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
            "drive +import --type sheet",
            "wiki +move",
        ],
        "publish_ready": False,
        "notes": [
            "Preflight must run lark-cli doctor and lark-cli auth status before publish.",
            "Markdown files are imported with drive import as docx, then moved into Wiki.",
            "CSV is imported with drive import as sheet, then moved into Wiki.",
            "This manifest does not depend on sheets append file ingestion.",
        ],
    }
    _assert_safe_manifest(manifest)
    return manifest


def _resolve_lark_cli_argv(argv: list[str]) -> list[str]:
    resolved = list(argv)
    if not resolved or resolved[0] != "lark-cli":
        return resolved

    override = os.environ.get("LARK_CLI")
    if override:
        return [override, *resolved[1:]]

    for name in ("lark-cli.cmd", "lark-cli.exe", "lark-cli", "lark-cli.ps1"):
        found = shutil.which(name)
        if found:
            return [found, *resolved[1:]]
    return resolved


def default_runner(argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(_resolve_lark_cli_argv(argv), cwd=cwd, text=True, capture_output=True, check=False)


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
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = text[:120].replace("\r", "\\r").replace("\n", "\\n")
        raise ValueError(f"command stdout is not valid JSON: {snippet}") from exc
    if not isinstance(data, dict):
        raise ValueError("command stdout JSON must be an object")
    return data


def _optional_token(data: dict[str, Any], *keys: str) -> str | None:
    containers: list[dict[str, Any]] = [data]
    for nested_key in ("data", "node"):
        nested = data.get(nested_key)
        if isinstance(nested, dict):
            containers.append(nested)
    for container in containers:
        for key in keys:
            value = container.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def _token(data: dict[str, Any], *keys: str) -> str:
    token = _optional_token(data, *keys)
    if token:
        return token
    raise ValueError(f"missing token keys: {keys}")


def _without_dry_run(argv: list[str]) -> list[str]:
    if argv and argv[-1] == "--dry-run":
        return argv[:-1]
    return list(argv)


def publish_output(
    output_root: str | Path,
    jd_title: str,
    wiki_space_id: str,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    root = Path(output_root)
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

    for step in manifest["preflight"]:
        run(step["argv"])

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
            }
        )

    wiki_children = _stdout_json(run(_wiki_node_list_command(wiki_space_id, parent_node_token)))
    node_details: list[dict[str, Any]] = []
    doc_outlines: list[dict[str, Any]] = []
    sheet_previews: list[dict[str, Any]] = []
    for item in published:
        node_token = str(item.get("node_token") or item["obj_token"])
        obj_type = str(item["obj_type"])
        node_details.append(_stdout_json(run(_wiki_node_get_command(node_token, obj_type, wiki_space_id))))
        if obj_type == "docx":
            doc_outlines.append(_stdout_json(run(_docs_fetch_command(str(item["obj_token"])))))
        elif obj_type == "sheet":
            sheet_previews.append(_stdout_json(run(_sheets_read_command(str(item["obj_token"])))))

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
        "readback": {
            "wiki_children": wiki_children,
            "node_details": node_details,
            "doc_outlines": doc_outlines,
            "sheet_previews": sheet_previews,
        },
        "command_results": command_results,
    }
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
    args = parser.parse_args(argv)

    if args.publish:
        if args.dry_run:
            parser.error("--dry-run only applies to manifest generation; publish runs its own dry-run prechecks")
        publish_output(args.output_root, args.jd_title, args.wiki_space_id)
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
