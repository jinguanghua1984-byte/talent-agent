"""人才库 bundle 导出工具。"""

from __future__ import annotations

import dataclasses
import argparse
import hashlib
import json
import sqlite3
import sys
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_db import merge_candidate_payload as _merge_candidate_payload
from scripts.talent_sync_models import (
    BUNDLE_SCHEMA_VERSION,
    BundleManifest,
    CONFIRM_SYNC_TEXT,
    canonical_json,
)

_SYNC_TABLES = (
    "candidates",
    "candidate_details",
    "source_profiles",
    "candidate_wechat_timelines",
    "score_events",
    "match_scores",
    "tombstones",
)


def merge_candidate_payload(local: dict, remote: dict) -> tuple[dict, list[dict]]:
    return _merge_candidate_payload(local, remote)


def export_bundle(
    db_path: str | Path,
    bundle_path: str | Path,
    mode: str = "full",
    include_wechat_files: bool = False,
) -> dict[str, Any]:
    """导出可校验的全量 bundle。

    `include_wechat_files` 当前仅作为后续附件打包的占位参数；
    MVP 只导出 JSONL 索引，因此 manifest 只记录实际包含的附件状态。
    """
    if mode != "full":
        raise ValueError(f"Unsupported export mode: {mode}")
    target_path = Path(bundle_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    db = TalentDB(db_path)
    try:
        source_node_id = db._node_id()
        table_rows = db.export_sync_rows()
    finally:
        db.close()

    table_counts = {table: len(rows) for table, rows in table_rows.items()}
    manifest = BundleManifest(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
        export_mode=mode,
        source_node_id=source_node_id,
        export_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        tables=table_counts,
        attachments={"wechat_timelines": False},
    )

    payloads: dict[str, bytes] = {}
    for table, rows in table_rows.items():
        payloads[f"data/{table}.jsonl"] = _jsonl_bytes(rows)

    attachment_entries: list[dict[str, str]] = []
    if include_wechat_files:
        attachment_payloads, attachment_entries = _wechat_timeline_attachment_payloads(
            table_rows.get("candidate_wechat_timelines", []),
            Path(db_path),
        )
        payloads.update(attachment_payloads)
        if attachment_payloads:
            manifest.attachments["wechat_timelines"] = True

    manifest_path = "manifest.json"
    manifest_data = dataclasses.asdict(manifest)
    if attachment_entries:
        manifest_data["attachment_entries"] = attachment_entries
    payloads[manifest_path] = (canonical_json(manifest_data) + "\n").encode("utf-8")
    checksum_targets = [*sorted(name for name in payloads if name != "checksums.sha256")]
    payloads["checksums.sha256"] = _checksum_lines(payloads, checksum_targets).encode(
        "utf-8"
    )

    _write_zip(target_path, payloads)

    return {
        "bundle_path": str(target_path),
        "mode": mode,
        "source_node_id": source_node_id,
        "tables": table_counts,
        "attachments": dataclasses.asdict(manifest).get("attachments", {}),
    }


def verify_bundle(path: str | Path) -> dict[str, Any]:
    errors: list[str] = []

    try:
        with zipfile.ZipFile(path) as bundle:
            names = set(bundle.namelist())
            for required in ("manifest.json", "checksums.sha256"):
                if required not in names:
                    errors.append(f"Missing required file: {required}")

            if "checksums.sha256" not in names:
                return {"ok": False, "errors": errors}

            try:
                checksum_text = bundle.read("checksums.sha256").decode("utf-8")
            except UnicodeDecodeError:
                return {
                    "ok": False,
                    "errors": ["Cannot decode checksums.sha256 as UTF-8"],
                }

            listed_paths: set[str] = set()
            for line_number, line in enumerate(checksum_text.splitlines(), start=1):
                if not line:
                    errors.append(f"Malformed checksum line {line_number}: empty line")
                    continue
                parts = line.split("  ", 1)
                if len(parts) != 2:
                    errors.append(f"Malformed checksum line {line_number}: {line}")
                    continue

                expected_digest, relative_path = parts
                if (
                    len(expected_digest) != 64
                    or any(char not in "0123456789abcdef" for char in expected_digest)
                    or not relative_path
                ):
                    errors.append(f"Malformed checksum line {line_number}: {line}")
                    continue

                listed_paths.add(relative_path)
                if relative_path not in names:
                    errors.append(f"Missing listed file: {relative_path}")
                    continue

                actual_digest = hashlib.sha256(bundle.read(relative_path)).hexdigest()
                if actual_digest != expected_digest:
                    errors.append(f"Checksum mismatch: {relative_path}")

            if not listed_paths:
                errors.append("Checksum list is empty")
            if "manifest.json" not in listed_paths:
                errors.append("manifest.json is missing from checksum list")

            expected_paths = names - {"checksums.sha256"}
            for unlisted_path in sorted(expected_paths - listed_paths):
                errors.append(f"Unlisted file in bundle: {unlisted_path}")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append(f"Cannot open bundle: {exc}")

    return {"ok": not errors, "errors": errors}


def plan_import(bundle_path: str | Path, db_path: str | Path) -> dict[str, Any]:
    """规划 bundle 导入，不写入目标库。"""
    return _public_import_plan(_build_import_plan(bundle_path, db_path))


def import_bundle(
    bundle_path: str | Path,
    db_path: str | Path,
    apply: bool = False,
    confirm: str = "",
) -> dict[str, Any]:
    """导入 bundle；默认 dry-run，仅返回规划结果。"""
    plan = _build_import_plan(bundle_path, db_path)
    if not apply:
        return _public_import_plan(plan)

    if confirm != CONFIRM_SYNC_TEXT:
        raise ValueError("Import apply requires explicit confirmation text")

    plan["_table_rows"] = _table_rows_with_restored_wechat_attachments(
        bundle_path,
        db_path,
        plan,
    )

    db = TalentDB(db_path)
    try:
        result = db.apply_sync_import(
            manifest=plan["_manifest"],
            table_rows=plan["_table_rows"],
            plan=plan,
        )
    finally:
        db.close()
    return result


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    content = "".join(f"{canonical_json(row)}\n" for row in rows)
    return content.encode("utf-8")


def _wechat_timeline_attachment_payloads(
    rows: list[dict[str, Any]],
    db_path: Path,
) -> tuple[dict[str, bytes], list[dict[str, str]]]:
    payloads: dict[str, bytes] = {}
    entries: list[dict[str, str]] = []
    used_names: set[str] = set()
    allowed_dir = _wechat_timeline_archive_dir(db_path).resolve()
    for row in rows:
        markdown_path = str(row.get("markdown_path") or "")
        if not markdown_path:
            continue
        try:
            resolved_path = Path(markdown_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if not resolved_path.is_file():
            continue
        try:
            resolved_path.relative_to(allowed_dir)
        except ValueError:
            continue

        bundle_name = _unique_wechat_attachment_name(
            resolved_path.name,
            str(row.get("sync_id") or ""),
            used_names,
        )
        try:
            payloads[bundle_name] = resolved_path.read_bytes()
        except OSError:
            used_names.remove(bundle_name)
            continue
        entries.append(
            {
                "timeline_sync_id": str(row.get("sync_id") or ""),
                "bundle_path": bundle_name,
            }
        )
    return payloads, entries


def _unique_wechat_attachment_name(
    basename: str,
    sync_id: str,
    used_names: set[str],
) -> str:
    safe_basename = Path(basename).name
    candidate = f"attachments/wechat-timelines/{safe_basename}"
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    digest = hashlib.sha256(sync_id.encode("utf-8")).hexdigest()[:12]
    candidate = f"attachments/wechat-timelines/{digest}-{safe_basename}"
    suffix = 2
    while candidate in used_names:
        candidate = f"attachments/wechat-timelines/{digest}-{suffix}-{safe_basename}"
        suffix += 1
    used_names.add(candidate)
    return candidate


def _table_rows_with_restored_wechat_attachments(
    bundle_path: str | Path,
    db_path: str | Path,
    plan: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    manifest = plan["_manifest"]
    table_rows = plan["_table_rows"]
    if not manifest.get("attachments", {}).get("wechat_timelines"):
        return table_rows
    if _sync_import_already_recorded(db_path, manifest):
        return table_rows

    entries = manifest.get("attachment_entries")
    if not isinstance(entries, list) or not entries:
        return table_rows

    timeline_sync_ids_to_restore = _wechat_timeline_sync_ids_to_restore(db_path, plan)
    if not timeline_sync_ids_to_restore:
        return table_rows

    rows_by_sync_id = {
        str(row.get("sync_id") or ""): row
        for row in table_rows.get("candidate_wechat_timelines", [])
    }
    restored_rows = {
        table: [dict(row) for row in rows]
        for table, rows in table_rows.items()
    }
    restored_by_sync_id = {
        str(row.get("sync_id") or ""): row
        for row in restored_rows.get("candidate_wechat_timelines", [])
    }
    target_dir = _wechat_timeline_archive_dir(Path(db_path))
    target_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            timeline_sync_id = str(entry.get("timeline_sync_id") or "")
            bundle_name = str(entry.get("bundle_path") or "")
            if not timeline_sync_id or bundle_name not in names:
                continue
            if not bundle_name.startswith("attachments/wechat-timelines/"):
                continue
            if timeline_sync_id not in rows_by_sync_id:
                continue
            if timeline_sync_id not in timeline_sync_ids_to_restore:
                continue

            data = bundle.read(bundle_name)
            target_path = _safe_restore_path(
                target_dir,
                Path(bundle_name).name,
                timeline_sync_id,
                data,
            )
            target_path.write_bytes(data)
            restored_by_sync_id[timeline_sync_id]["markdown_path"] = str(target_path)

    return restored_rows


def _sync_import_already_recorded(
    db_path: str | Path,
    manifest: dict[str, Any],
) -> bool:
    bundle_id = manifest.get("export_id")
    if not bundle_id:
        return False

    conn = _connect_existing_db(db_path)
    if conn is None:
        return False
    try:
        row = conn.execute(
            "SELECT 1 FROM sync_imports WHERE bundle_id = ? LIMIT 1",
            (bundle_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()
    return row is not None


def _wechat_timeline_sync_ids_to_restore(
    db_path: str | Path,
    plan: dict[str, Any],
) -> set[str]:
    table_rows = plan["_table_rows"]
    candidate_actions = plan.get("_candidate_actions", {})
    conn = _connect_existing_db(db_path)
    try:
        sync_ids: set[str] = set()
        for row in table_rows.get("candidate_wechat_timelines", []):
            timeline_sync_id = str(row.get("sync_id") or "")
            candidate_sync_id = str(row.get("candidate_sync_id") or "")
            action = candidate_actions.get(candidate_sync_id, {}).get("action")
            if action not in {"create", "merge"}:
                continue
            if _target_has_sync_id(conn, "candidate_wechat_timelines", timeline_sync_id):
                continue
            sync_ids.add(timeline_sync_id)
        return sync_ids
    finally:
        if conn is not None:
            conn.close()


def _safe_restore_path(
    target_dir: Path,
    basename: str,
    sync_id: str,
    data: bytes,
) -> Path:
    safe_basename = Path(basename).name
    target_path = target_dir / safe_basename
    if not target_path.exists() or target_path.read_bytes() == data:
        return target_path

    digest = hashlib.sha256(sync_id.encode("utf-8")).hexdigest()[:12]
    target_path = target_dir / f"{digest}-{safe_basename}"
    suffix = 2
    while target_path.exists() and target_path.read_bytes() != data:
        target_path = target_dir / f"{digest}-{suffix}-{safe_basename}"
        suffix += 1
    return target_path


def _wechat_timeline_archive_dir(db_path: Path) -> Path:
    db_parent = db_path.parent
    if db_parent.name == "data":
        return db_parent / "wechat-timelines"
    return db_parent / "data" / "wechat-timelines"


def _checksum_lines(payloads: dict[str, bytes], names: list[str]) -> str:
    lines: list[str] = []
    for name in names:
        digest = hashlib.sha256(payloads[name]).hexdigest()
        lines.append(f"{digest}  {name}")
    return "\n".join(lines) + "\n"


def _write_zip(target_path: Path, payloads: dict[str, bytes]) -> None:
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(payloads):
            bundle.writestr(name, payloads[name])


def _build_import_plan(bundle_path: str | Path, db_path: str | Path) -> dict[str, Any]:
    verification = verify_bundle(bundle_path)
    if not verification["ok"]:
        raise ValueError("Invalid bundle: " + "; ".join(verification["errors"]))

    manifest, table_rows = _read_bundle_payloads(bundle_path)
    source_node_id = str(manifest.get("source_node_id") or "")
    plan = _empty_import_plan(manifest, table_rows)

    conn = _connect_existing_db(db_path)
    try:
        sources_by_candidate = _group_sources_by_candidate(table_rows)
        tombstoned_candidate_sync_ids = (
            _candidate_tombstone_sync_ids(table_rows)
            | _local_candidate_tombstone_sync_ids(conn)
        )
        deleted_candidate_ids: set[int] = set()
        for tombstone in table_rows.get("tombstones", []):
            match = _candidate_tombstone_match(conn, tombstone)
            if match is None:
                continue
            local_candidate_id = int(match["id"])
            if local_candidate_id in deleted_candidate_ids:
                continue
            deleted_candidate_ids.add(local_candidate_id)
            plan["deleted"]["candidates"] += 1

        for candidate in table_rows.get("candidates", []):
            sync_id = str(candidate.get("sync_id") or "")
            if not sync_id:
                plan["skipped"]["candidates"] += 1
                continue
            if sync_id in tombstoned_candidate_sync_ids:
                plan["skipped"]["candidates"] += 1
                continue

            matches = _resolve_candidate_matches(
                conn,
                candidate,
                sources_by_candidate.get(sync_id, []),
                source_node_id,
            )
            match_ids = {match["local_candidate_id"] for match in matches}
            if len(match_ids) > 1:
                plan["conflicts"]["candidates"] += 1
                plan["_candidate_actions"][sync_id] = {
                    "action": "conflict",
                    "matches": matches,
                }
                continue

            if not matches:
                plan["created"]["candidates"] += 1
                plan["_candidate_actions"][sync_id] = {
                    "action": "create",
                    "local_candidate_id": None,
                    "local_sync_id": sync_id,
                    "reason": "new",
                }
                continue

            match = matches[0]
            plan["merged"]["candidates"] += 1
            plan["_candidate_actions"][sync_id] = {
                "action": "merge",
                **match,
            }

        _plan_child_rows(conn, table_rows, plan)
    finally:
        if conn is not None:
            conn.close()

    return plan


def _read_bundle_payloads(
    bundle_path: str | Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    with zipfile.ZipFile(bundle_path) as bundle:
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        table_rows: dict[str, list[dict[str, Any]]] = {}
        for table in _SYNC_TABLES:
            path = f"data/{table}.jsonl"
            if path not in bundle.namelist():
                table_rows[table] = []
                continue
            table_rows[table] = _read_jsonl(bundle.read(path).decode("utf-8"))
    _validate_unique_sync_ids(table_rows)
    return manifest, table_rows


def _read_jsonl(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL line {line_number} is not an object")
        rows.append(value)
    return rows


def _validate_unique_sync_ids(table_rows: dict[str, list[dict[str, Any]]]) -> None:
    for table, rows in table_rows.items():
        if table == "tombstones":
            continue
        seen: set[str] = set()
        for row in rows:
            sync_id = row.get("sync_id")
            if not sync_id:
                continue
            sync_id_text = str(sync_id)
            if sync_id_text in seen:
                raise ValueError(f"Duplicate sync_id in {table}: {sync_id_text}")
            seen.add(sync_id_text)


def _empty_import_plan(
    manifest: dict[str, Any],
    table_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "bundle_id": manifest.get("export_id"),
        "source_node_id": manifest.get("source_node_id"),
        "mode": manifest.get("export_mode"),
        "created": _empty_counts(),
        "merged": _empty_counts(),
        "conflicts": _empty_counts(),
        "skipped": _empty_counts(),
        "deleted": _empty_counts(),
        "tombstoned": _empty_counts(),
        "tables": {table: len(table_rows.get(table, [])) for table in _SYNC_TABLES},
        "_manifest": manifest,
        "_table_rows": table_rows,
        "_candidate_actions": {},
    }


def _empty_counts() -> dict[str, int]:
    return {table: 0 for table in _SYNC_TABLES}


def _connect_existing_db(db_path: str | Path) -> sqlite3.Connection | None:
    path = Path(db_path)
    if not path.exists():
        return None

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _group_sources_by_candidate(
    table_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for source in table_rows.get("source_profiles", []):
        candidate_sync_id = str(source.get("candidate_sync_id") or "")
        if not candidate_sync_id:
            continue
        grouped.setdefault(candidate_sync_id, []).append(source)
    return grouped


def _candidate_tombstone_sync_ids(
    table_rows: dict[str, list[dict[str, Any]]],
) -> set[str]:
    sync_ids: set[str] = set()
    for row in table_rows.get("tombstones", []):
        if row.get("entity_type") != "candidate":
            continue
        sync_id = str(row.get("entity_sync_id") or "")
        if sync_id:
            sync_ids.add(sync_id)
    return sync_ids


def _local_candidate_tombstone_sync_ids(
    conn: sqlite3.Connection | None,
) -> set[str]:
    if conn is None:
        return set()

    try:
        rows = conn.execute(
            """
            SELECT entity_sync_id AS sync_id
            FROM sync_tombstones
            WHERE entity_type = 'candidate'

            UNION

            SELECT sync_entity_aliases.remote_sync_id AS sync_id
            FROM sync_tombstones
            JOIN sync_entity_aliases
              ON sync_entity_aliases.entity_type = 'candidate'
             AND sync_entity_aliases.local_sync_id = sync_tombstones.entity_sync_id
            WHERE sync_tombstones.entity_type = 'candidate'
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return set()

    return {str(row["sync_id"]) for row in rows if row["sync_id"]}


def _candidate_tombstone_match(
    conn: sqlite3.Connection | None,
    tombstone: dict[str, Any],
) -> sqlite3.Row | None:
    if conn is None or tombstone.get("entity_type") != "candidate":
        return None

    sync_id = str(tombstone.get("entity_sync_id") or "")
    source_node_id = str(tombstone.get("source_node_id") or "")
    return _candidate_by_sync_id(conn, sync_id) or _candidate_by_alias(
        conn,
        sync_id,
        source_node_id,
    )


def _resolve_candidate_matches(
    conn: sqlite3.Connection | None,
    candidate: dict[str, Any],
    source_rows: list[dict[str, Any]],
    source_node_id: str,
) -> list[dict[str, Any]]:
    if conn is None:
        return []

    matches: list[dict[str, Any]] = []
    sync_id = str(candidate.get("sync_id") or "")
    _append_candidate_match(matches, _candidate_by_sync_id(conn, sync_id), "sync_id")
    _append_candidate_match(
        matches,
        _candidate_by_alias(conn, sync_id, source_node_id),
        "alias",
    )

    for source in source_rows:
        platform = source.get("platform")
        platform_id = source.get("platform_id")
        if platform and platform_id:
            _append_candidate_match(
                matches,
                _candidate_by_source(conn, str(platform), str(platform_id)),
                "source",
            )

    _append_candidate_match(
        matches,
        _candidate_by_identity(conn, candidate),
        "identity",
    )
    return matches


def _append_candidate_match(
    matches: list[dict[str, Any]],
    row: sqlite3.Row | None,
    reason: str,
) -> None:
    if row is None:
        return
    local_candidate_id = int(row["id"])
    for match in matches:
        if match["local_candidate_id"] == local_candidate_id:
            match["reasons"].append(reason)
            return
    matches.append(
        {
            "local_candidate_id": local_candidate_id,
            "local_sync_id": row["sync_id"],
            "reasons": [reason],
        }
    )


def _candidate_by_sync_id(
    conn: sqlite3.Connection,
    sync_id: str,
) -> sqlite3.Row | None:
    if not sync_id:
        return None
    return _fetch_optional(
        conn,
        """
        SELECT id, sync_id
        FROM candidates
        WHERE sync_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (sync_id,),
    )


def _candidate_by_alias(
    conn: sqlite3.Connection,
    sync_id: str,
    source_node_id: str,
) -> sqlite3.Row | None:
    if not sync_id or not source_node_id:
        return None
    return _fetch_optional(
        conn,
        """
        SELECT candidates.id, candidates.sync_id
        FROM sync_entity_aliases
        JOIN candidates ON candidates.sync_id = sync_entity_aliases.local_sync_id
        WHERE sync_entity_aliases.entity_type = 'candidate'
          AND sync_entity_aliases.remote_sync_id = ?
          AND sync_entity_aliases.source_node_id = ?
        ORDER BY candidates.id
        LIMIT 1
        """,
        (sync_id, source_node_id),
    )


def _candidate_by_source(
    conn: sqlite3.Connection,
    platform: str,
    platform_id: str,
) -> sqlite3.Row | None:
    return _fetch_optional(
        conn,
        """
        SELECT candidates.id, candidates.sync_id
        FROM source_profiles
        JOIN candidates ON candidates.id = source_profiles.candidate_id
        WHERE source_profiles.platform = ?
          AND source_profiles.platform_id = ?
        ORDER BY candidates.id
        LIMIT 1
        """,
        (platform, platform_id),
    )


def _candidate_by_identity(
    conn: sqlite3.Connection,
    candidate: dict[str, Any],
) -> sqlite3.Row | None:
    name = candidate.get("name")
    if not name:
        return None
    return _fetch_optional(
        conn,
        """
        SELECT id, sync_id
        FROM candidates
        WHERE name = ?
          AND COALESCE(current_company, '') = ?
          AND COALESCE(current_title, '') = ?
          AND COALESCE(city, '') = ?
          AND COALESCE(education, '') = ?
        ORDER BY id
        LIMIT 1
        """,
        (
            name,
            _identity_value(candidate.get("current_company")),
            _identity_value(candidate.get("current_title")),
            _identity_value(candidate.get("city")),
            _identity_value(candidate.get("education")),
        ),
    )


def _fetch_optional(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple[Any, ...],
) -> sqlite3.Row | None:
    try:
        return conn.execute(sql, params).fetchone()
    except sqlite3.OperationalError:
        return None


def _plan_child_rows(
    conn: sqlite3.Connection | None,
    table_rows: dict[str, list[dict[str, Any]]],
    plan: dict[str, Any],
) -> None:
    candidate_actions = plan["_candidate_actions"]
    for table in (
        "candidate_details",
        "source_profiles",
        "candidate_wechat_timelines",
        "score_events",
        "match_scores",
    ):
        for row in table_rows.get(table, []):
            candidate_sync_id = str(row.get("candidate_sync_id") or "")
            action = candidate_actions.get(candidate_sync_id, {})
            if action.get("action") not in {"create", "merge"}:
                plan["skipped"][table] += 1
                continue

            if _target_has_sync_id(conn, table, str(row.get("sync_id") or "")):
                plan["merged"][table] += 1
            else:
                plan["created"][table] += 1

    plan["tombstoned"]["tombstones"] = len(table_rows.get("tombstones", []))


def _target_has_sync_id(
    conn: sqlite3.Connection | None,
    table: str,
    sync_id: str,
) -> bool:
    if conn is None or not sync_id:
        return False
    try:
        row = conn.execute(
            f"SELECT 1 FROM {table} WHERE sync_id = ? LIMIT 1",
            (sync_id,),
        ).fetchone()
    except sqlite3.OperationalError:
        return False
    return row is not None


def _public_import_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if not key.startswith("_")}


def _identity_value(value: Any) -> str:
    return "" if value is None else str(value)


def cmd_status(args: argparse.Namespace) -> int:
    db_path = Path(args.db)
    if not db_path.exists():
        print(f"同步状态：missing，db={db_path}")
        return 0

    db = TalentDB(db_path)
    try:
        node_id = db._node_id()
        candidate_count = db.count()
        imports_count = db._conn.execute("SELECT COUNT(*) FROM sync_imports").fetchone()[0]
    finally:
        db.close()

    print(
        "同步状态：node_id={node_id}，候选人={candidate_count}，导入记录={imports_count}".format(
            node_id=node_id,
            candidate_count=candidate_count,
            imports_count=imports_count,
        )
    )
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    summary = export_bundle(
        args.db,
        args.out,
        mode="full",
        include_wechat_files=args.include_wechat_files,
    )
    print(
        "导出完成：bundle={bundle_path}，模式={mode}，候选人={candidate_count}".format(
            bundle_path=summary["bundle_path"],
            mode=summary["mode"],
            candidate_count=summary["tables"].get("candidates", 0),
        )
    )
    return 0


def cmd_verify_bundle(args: argparse.Namespace) -> int:
    result = verify_bundle(args.bundle)
    if result["ok"]:
        print(f"bundle 校验通过：{args.bundle}")
        return 0

    print(f"bundle 校验失败：{args.bundle}")
    for error in result["errors"]:
        print(f"- {error}")
    return 1


def cmd_import(args: argparse.Namespace) -> int:
    if args.apply and args.confirm != CONFIRM_SYNC_TEXT:
        raise ValueError(f"apply requires confirm text: {CONFIRM_SYNC_TEXT}")

    result = import_bundle(
        args.bundle,
        args.db,
        apply=args.apply,
        confirm=args.confirm,
    )
    mode = "apply" if args.apply else "dry-run"
    print(
        "导入{mode}完成：新建候选人={created}，合并候选人={merged}，冲突候选人={conflicts}，跳过候选人={skipped}".format(
            mode=mode,
            created=result["created"].get("candidates", 0),
            merged=result["merged"].get("candidates", 0),
            conflicts=result["conflicts"].get("candidates", 0),
            skipped=result["skipped"].get("candidates", 0),
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="人才库同步 bundle 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="查看本地人才库同步状态")
    status.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    status.set_defaults(func=cmd_status)

    export = subparsers.add_parser("export", help="导出全量同步 bundle")
    export.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    export.add_argument("--out", required=True, help="bundle 输出路径")
    export.add_argument(
        "--include-wechat-files",
        action="store_true",
        help="将微信时间线 markdown 附件打包进 bundle",
    )
    export.set_defaults(func=cmd_export)

    verify = subparsers.add_parser("verify-bundle", help="校验同步 bundle")
    verify.add_argument("--bundle", required=True, help="bundle 文件路径")
    verify.set_defaults(func=cmd_verify_bundle)

    import_parser = subparsers.add_parser("import", help="导入同步 bundle")
    import_parser.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    import_parser.add_argument("--bundle", required=True, help="bundle 文件路径")
    import_parser.add_argument("--apply", action="store_true", help="确认后写入真实人才库")
    import_parser.add_argument("--confirm", default="", help=f"写库确认语：{CONFIRM_SYNC_TEXT}")
    import_parser.set_defaults(func=cmd_import)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
