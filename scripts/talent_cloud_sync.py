"""人才库云端 bundle 同步工具。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_sync import export_bundle, import_bundle, plan_import, verify_bundle
from scripts.talent_cloud_sync_common import (
    CloudSyncError,
    INDEX_SCHEMA,
    LEGACY_STATE_SCHEMA,
    STATE_SCHEMA,
)
from scripts.talent_cloud_sync_providers import (
    CloudProvider,
    FeishuDriveProvider,
    LocalFsProvider,
)
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT, canonical_json


DEFAULT_MAX_UPLOAD_BYTES = 18 * 1024 * 1024


def _load_local_dotenv() -> None:
    load_dotenv(dotenv_path=Path(".env"), override=False)


@dataclass(frozen=True)
class CloudSyncConfig:
    provider: str
    db_path: Path = Path("data/talent.db")
    state_path: Path = Path("data/sync/cloud-state.json")
    work_dir: Path = Path("data/sync/work")
    localfs_root: Path | None = None
    feishu_root_folder_token: str | None = None
    feishu_root_name: str = "Talent Agent Sync"
    feishu_as: str = "user"
    encryption_key: str = ""
    auto_apply: bool = True
    include_wechat_files: bool = False
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    export_mode: str = "incremental"
    since: str | None = None

    @classmethod
    def from_env(cls, db_path: str | Path = "data/talent.db") -> "CloudSyncConfig":
        _load_local_dotenv()
        provider = os.environ.get("TALENT_SYNC_PROVIDER", "localfs").strip()
        key = os.environ.get("TALENT_SYNC_ENCRYPTION_KEY", "").strip()
        if not key:
            raise CloudSyncError("TALENT_SYNC_ENCRYPTION_KEY is required")
        localfs_root = os.environ.get("TALENT_SYNC_LOCALFS_ROOT")
        return cls(
            provider=provider,
            db_path=Path(db_path),
            state_path=Path(os.environ.get("TALENT_SYNC_STATE", "data/sync/cloud-state.json")),
            work_dir=Path(os.environ.get("TALENT_SYNC_WORK_DIR", "data/sync/work")),
            localfs_root=Path(localfs_root) if localfs_root else None,
            feishu_root_folder_token=os.environ.get("TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN"),
            feishu_root_name=os.environ.get(
                "TALENT_SYNC_FEISHU_ROOT_NAME",
                "Talent Agent Sync",
            ),
            feishu_as=os.environ.get("TALENT_SYNC_FEISHU_AS", "user"),
            encryption_key=key,
            auto_apply=os.environ.get("TALENT_SYNC_AUTO_APPLY", "1") != "0",
            include_wechat_files=os.environ.get("TALENT_SYNC_INCLUDE_WECHAT_FILES", "0") == "1",
            max_upload_bytes=int(
                os.environ.get("TALENT_SYNC_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
            ),
            export_mode=os.environ.get("TALENT_SYNC_EXPORT_MODE", "incremental"),
            since=os.environ.get("TALENT_SYNC_SINCE") or None,
        )

def keygen() -> str:
    return Fernet.generate_key().decode("ascii")


def _fernet(key: str) -> Fernet:
    try:
        return Fernet(key.encode("ascii"))
    except Exception as exc:  # noqa: BLE001 - convert implementation detail to domain error.
        raise CloudSyncError("TALENT_SYNC_ENCRYPTION_KEY must be a Fernet key") from exc


def encrypt_bytes(data: bytes, key: str) -> bytes:
    return _fernet(key).encrypt(data)


def decrypt_bytes(data: bytes, key: str) -> bytes:
    try:
        return _fernet(key).decrypt(data)
    except InvalidToken as exc:
        raise CloudSyncError("cannot decrypt bundle with configured key") from exc


def _empty_state() -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "provider": "",
        "remote": {},
        "seen_bundle_ids": [],
        "applied_bundle_ids": [],
        "applied_bundles": [],
        "blocked_remote_bundles": [],
        "last_sync_at": None,
        "last_push_bundle_id": None,
        "last_pushed_db_fingerprint": None,
        "last_successful_push_started_at": None,
    }


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return _empty_state()
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if data.get("schema") not in {STATE_SCHEMA, LEGACY_STATE_SCHEMA}:
        raise CloudSyncError(f"unsupported cloud state schema: {data.get('schema')}")
    defaults = _empty_state()
    defaults.update(data)
    defaults["schema"] = STATE_SCHEMA
    defaults.setdefault("seen_bundle_ids", [])
    defaults.setdefault("applied_bundle_ids", [])
    defaults.setdefault("applied_bundles", [])
    defaults.setdefault("blocked_remote_bundles", [])
    defaults.setdefault("last_successful_push_started_at", None)
    return defaults


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def init_remote(provider: CloudProvider) -> dict[str, Any]:
    return provider.ensure_layout()


def _provider(config: CloudSyncConfig) -> CloudProvider:
    if config.provider == "localfs":
        if config.localfs_root is None:
            raise CloudSyncError("TALENT_SYNC_LOCALFS_ROOT is required for localfs provider")
        return LocalFsProvider(config.localfs_root)
    if config.provider == "feishu":
        return FeishuDriveProvider(config)
    raise CloudSyncError(f"unsupported cloud sync provider: {config.provider}")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _node_id(db_path: Path) -> str:
    db = TalentDB(db_path)
    try:
        return db._node_id()
    finally:
        db.close()


def _open_conflict_count(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    db = TalentDB(db_path)
    try:
        row = db._conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE status = 'open'"
        ).fetchone()
        return int(row[0])
    finally:
        db.close()


def _db_fingerprint(db_path: Path) -> str:
    if not db_path.exists():
        return "missing"
    db = TalentDB(db_path)
    try:
        payload = {
            "schema": "talent_cloud_db_fingerprint_v1",
            "source_node_id": db._node_id(),
            "tables": db.export_sync_rows(),
        }
    finally:
        db.close()
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _load_bundle_manifest(bundle_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(bundle_path) as bundle:
        return json.loads(bundle.read("manifest.json").decode("utf-8"))


def _remote_name_timestamp(created_at: str) -> str:
    return created_at.replace(":", "").replace("-", "").replace("+00:00", "Z")


def _remote_index_name(created_at: str, node_id: str, bundle_id: str) -> str:
    return f"{_remote_name_timestamp(created_at)}-{node_id}-{bundle_id}.json"


def _upload_encrypted_bundle(
    provider: CloudProvider,
    encrypted_bundle: Path,
    bundle_name: str,
    max_upload_bytes: int,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    size = encrypted_bundle.stat().st_size
    if size <= max_upload_bytes:
        return provider.upload_file("bundles", encrypted_bundle, bundle_name), []

    parts: list[dict[str, Any]] = []
    part_dir = encrypted_bundle.parent / f"{encrypted_bundle.name}.parts"
    part_dir.mkdir(parents=True, exist_ok=True)
    with encrypted_bundle.open("rb") as source:
        part_number = 1
        while True:
            chunk = source.read(max_upload_bytes)
            if not chunk:
                break
            part_name = f"{bundle_name}.part{part_number:04d}"
            part_path = part_dir / part_name
            part_path.write_bytes(chunk)
            uploaded = provider.upload_file("bundles", part_path, part_name)
            parts.append(
                {
                    "name": part_name,
                    "token": uploaded["token"],
                    "sha256": _sha256_bytes(chunk),
                    "size": len(chunk),
                    "part_number": part_number,
                }
            )
            part_number += 1
    return None, parts


def _download_encrypted_bundle(
    provider: CloudProvider,
    index: dict[str, Any],
    encrypted_path: Path,
) -> None:
    encrypted_path.parent.mkdir(parents=True, exist_ok=True)
    parts = index.get("bundle_parts") or []
    if parts:
        with encrypted_path.open("wb") as target:
            for part in sorted(parts, key=lambda item: int(item.get("part_number", 0))):
                part_path = encrypted_path.parent / str(part["name"])
                provider.download_file(str(part["token"]), part_path)
                if _sha256_file(part_path) != part.get("sha256"):
                    raise CloudSyncError(f"bundle part sha256 mismatch: {part.get('name')}")
                target.write(part_path.read_bytes())
        return
    provider.download_file(str(index["bundle_file_token"]), encrypted_path)


def _incremental_since(config: CloudSyncConfig, state: dict[str, Any]) -> str:
    if config.since:
        return config.since
    cursor = state.get("last_successful_push_started_at")
    if not cursor:
        raise CloudSyncError(
            "incremental push requires prior bootstrap/full pull or --since"
        )
    return str(cursor)


def push(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    if _open_conflict_count(config.db_path) > 0:
        raise CloudSyncError("open sync conflicts exist; resolve them before push")

    state = load_state(config.state_path)
    config.work_dir.mkdir(parents=True, exist_ok=True)
    local_node_id = _node_id(config.db_path) if config.db_path.exists() else ""
    remote_indexes = _download_indexes(provider, config.work_dir)
    pending_remote = _unapplied_remote_indexes(
        remote_indexes,
        state,
        config.db_path,
        local_node_id,
    )
    if pending_remote:
        raise CloudSyncError("pull remote bundles before push")

    export_mode = config.export_mode
    if export_mode not in {"full", "incremental"}:
        raise CloudSyncError(f"unsupported export mode: {export_mode}")
    push_started_at = _now_utc()
    since = None
    if export_mode == "incremental":
        since = _incremental_since(config, state)

    current_fingerprint = _db_fingerprint(config.db_path)
    if (
        export_mode == "full"
        and state.get("last_pushed_db_fingerprint") == current_fingerprint
    ):
        return {
            "uploaded": False,
            "reason": "unchanged",
            "bundle_id": state.get("last_push_bundle_id"),
        }

    with tempfile.TemporaryDirectory(prefix="talent-cloud-push-", dir=str(config.work_dir)) as dirname:
        temp_dir = Path(dirname)
        plain_bundle = temp_dir / f"talent-sync-{uuid.uuid4()}.zip"
        encrypted_bundle = plain_bundle.with_suffix(".zip.enc")
        summary = export_bundle(
            config.db_path,
            plain_bundle,
            mode=export_mode,
            include_wechat_files=config.include_wechat_files,
            since=since,
        )
        verification = verify_bundle(plain_bundle)
        if not verification["ok"]:
            raise CloudSyncError(
                "exported bundle failed verification: " + "; ".join(verification["errors"])
            )
        if export_mode == "incremental" and all(
            count == 0 for count in summary["tables"].values()
        ):
            state["schema"] = STATE_SCHEMA
            state["provider"] = config.provider
            state["last_sync_at"] = _now_utc()
            save_state(config.state_path, state)
            return {"uploaded": False, "reason": "no_changes", "bundle_id": None}

        plain_bytes = plain_bundle.read_bytes()
        encrypted_bundle.write_bytes(encrypt_bytes(plain_bytes, config.encryption_key))
        encrypted_sha = _sha256_file(encrypted_bundle)
        manifest = _load_bundle_manifest(plain_bundle)
        bundle_id = str(manifest["export_id"])
        source_node_id = str(manifest["source_node_id"])
        created_at = str(manifest["created_at"])
        bundle_name = (
            f"{_remote_name_timestamp(created_at)}-{source_node_id}-{bundle_id}.zip.enc"
        )
        uploaded_bundle, bundle_parts = _upload_encrypted_bundle(
            provider,
            encrypted_bundle,
            bundle_name,
            config.max_upload_bytes,
        )
        index = {
            "schema": INDEX_SCHEMA,
            "bundle_id": bundle_id,
            "source_node_id": source_node_id,
            "created_at": created_at,
            "bundle_name": bundle_name,
            "bundle_file_token": uploaded_bundle["token"] if uploaded_bundle else None,
            "bundle_parts": bundle_parts,
            "bundle_sha256": encrypted_sha,
            "bundle_size": encrypted_bundle.stat().st_size,
            "encrypted": True,
            "talent_sync_bundle_sha256": _sha256_bytes(plain_bytes),
            "tables": summary["tables"],
            "export_mode": export_mode,
            "base_cursor": manifest.get("base_cursor"),
            "cursor_started_at": manifest.get("cursor_started_at"),
        }
        index_path = temp_dir / _remote_index_name(created_at, source_node_id, bundle_id)
        _write_json(index_path, index)
        uploaded_index = provider.upload_file("bundle-index", index_path, index_path.name)

    state["schema"] = STATE_SCHEMA
    state["provider"] = config.provider
    state["last_push_bundle_id"] = bundle_id
    state["last_pushed_db_fingerprint"] = current_fingerprint
    state["last_sync_at"] = _now_utc()
    state["last_successful_push_started_at"] = push_started_at
    if bundle_id not in state["seen_bundle_ids"]:
        state["seen_bundle_ids"].append(bundle_id)
    save_state(config.state_path, state)
    return {
        "uploaded": True,
        "bundle_id": bundle_id,
        "bundle_sha256": encrypted_sha,
        "bundle_file": uploaded_bundle,
        "bundle_parts": bundle_parts,
        "index_file": uploaded_index,
        "tables": summary["tables"],
    }


def _has_conflicts(plan: dict[str, Any]) -> bool:
    return any(count > 0 for count in plan.get("conflicts", {}).values())


def _copy_db_snapshot(source_path: Path, target_path: Path) -> None:
    if not source_path.exists():
        return
    target_path.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(str(source_path))
    try:
        target = sqlite3.connect(str(target_path))
        try:
            source.backup(target)
        finally:
            target.close()
    finally:
        source.close()


def _preview_import_bundle(bundle_path: Path, db_path: Path, work_dir: Path) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="talent-cloud-preview-", dir=str(work_dir)) as dirname:
        preview_db = Path(dirname) / "preview.db"
        _copy_db_snapshot(db_path, preview_db)
        return import_bundle(
            bundle_path,
            preview_db,
            apply=True,
            confirm=CONFIRM_SYNC_TEXT,
        )


def _download_indexes(provider: CloudProvider, work_dir: Path) -> list[dict[str, Any]]:
    indexes: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="talent-cloud-indexes-", dir=str(work_dir)) as dirname:
        index_dir = Path(dirname)
        for file in provider.list_files("bundle-index"):
            local_path = index_dir / file["name"]
            provider.download_file(file["token"], local_path)
            data = json.loads(local_path.read_text(encoding="utf-8-sig"))
            if data.get("schema") != INDEX_SCHEMA:
                raise CloudSyncError(f"unsupported bundle index schema: {data.get('schema')}")
            indexes.append(data)
    return sorted(indexes, key=lambda item: (item.get("created_at", ""), item.get("bundle_id", "")))


def _local_import_recorded(db_path: Path, bundle_id: str) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM sync_imports WHERE bundle_id = ? LIMIT 1",
            (bundle_id,),
        ).fetchone()
        return row is not None
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def _unapplied_remote_indexes(
    indexes: list[dict[str, Any]],
    state: dict[str, Any],
    db_path: Path,
    local_node_id: str,
) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for index in indexes:
        bundle_id = str(index["bundle_id"])
        if bundle_id in state["applied_bundle_ids"]:
            continue
        if _local_import_recorded(db_path, bundle_id):
            continue
        if local_node_id and index.get("source_node_id") == local_node_id:
            continue
        pending.append(index)
    return pending


def pull(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    config.work_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(config.state_path)
    pull_started_at = _now_utc()
    local_node_id = _node_id(config.db_path) if config.db_path.exists() else ""
    applied = 0
    skipped = 0
    blocked: list[dict[str, Any]] = []
    for index in _download_indexes(provider, config.work_dir):
        bundle_id = str(index["bundle_id"])
        if bundle_id in state["applied_bundle_ids"] or _local_import_recorded(config.db_path, bundle_id):
            skipped += 1
            continue
        if local_node_id and index.get("source_node_id") == local_node_id:
            skipped += 1
            continue

        with tempfile.TemporaryDirectory(prefix="talent-cloud-pull-", dir=str(config.work_dir)) as dirname:
            temp_dir = Path(dirname)
            encrypted_path = temp_dir / str(index["bundle_name"])
            _download_encrypted_bundle(provider, index, encrypted_path)
            if _sha256_file(encrypted_path) != index.get("bundle_sha256"):
                blocked.append({"bundle_id": bundle_id, "reason": "sha256_mismatch"})
                continue
            plain_path = encrypted_path.with_suffix("")
            plain_path.write_bytes(decrypt_bytes(encrypted_path.read_bytes(), config.encryption_key))
            verification = verify_bundle(plain_path)
            if not verification["ok"]:
                blocked.append({"bundle_id": bundle_id, "reason": "verify_failed", "errors": verification["errors"]})
                continue
            plan = plan_import(plain_path, config.db_path)
            if _has_conflicts(plan):
                blocked.append({"bundle_id": bundle_id, "reason": "conflicts", "plan": plan})
                continue
            preview = _preview_import_bundle(plain_path, config.db_path, temp_dir / "preview")
            if _has_conflicts(preview):
                blocked.append({"bundle_id": bundle_id, "reason": "conflicts", "plan": preview})
                continue
            if config.auto_apply:
                import_bundle(plain_path, config.db_path, apply=True, confirm=CONFIRM_SYNC_TEXT)
                applied += 1
                if bundle_id not in state["applied_bundle_ids"]:
                    state["applied_bundle_ids"].append(bundle_id)
                state["applied_bundles"].append(
                    {
                        "bundle_id": bundle_id,
                        "source_node_id": str(index.get("source_node_id") or ""),
                        "created_at": str(index.get("created_at") or ""),
                        "applied_at": _now_utc(),
                    }
                )
            else:
                skipped += 1
        if bundle_id not in state["seen_bundle_ids"]:
            state["seen_bundle_ids"].append(bundle_id)

    state["blocked_remote_bundles"] = blocked
    state["last_sync_at"] = _now_utc()
    if applied and not state.get("last_successful_push_started_at"):
        state["last_successful_push_started_at"] = pull_started_at
    save_state(config.state_path, state)
    return {"applied": applied, "skipped": skipped, "blocked": blocked}


def sync(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    pull_result = pull(config, provider=provider)
    push_result: dict[str, Any] | None = None
    if not pull_result["blocked"]:
        push_result = push(config, provider=provider)
    return {"pull": pull_result, "push": push_result}


def _config_from_args(args: argparse.Namespace) -> CloudSyncConfig:
    _load_local_dotenv()
    key = args.encryption_key or os.environ.get("TALENT_SYNC_ENCRYPTION_KEY", "")
    export_mode = (
        getattr(args, "mode", None)
        or os.environ.get("TALENT_SYNC_EXPORT_MODE")
        or "incremental"
    )
    since = getattr(args, "since", None) or os.environ.get("TALENT_SYNC_SINCE") or None
    return CloudSyncConfig(
        provider=args.provider,
        db_path=Path(args.db),
        state_path=Path(args.state),
        work_dir=Path(args.work_dir),
        localfs_root=Path(args.localfs_root) if args.localfs_root else None,
        feishu_root_folder_token=args.feishu_root_folder_token,
        feishu_root_name=args.feishu_root_name,
        feishu_as=args.feishu_as,
        encryption_key=key,
        auto_apply=not args.no_auto_apply,
        include_wechat_files=args.include_wechat_files,
        max_upload_bytes=int(
            os.environ.get("TALENT_SYNC_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))
        ),
        export_mode=export_mode,
        since=since,
    )


def cmd_keygen(args: argparse.Namespace) -> int:
    print(keygen())
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    if not config.db_path.exists():
        print(f"云同步状态：missing，db={config.db_path}")
        return 0
    state = load_state(config.state_path)
    db = TalentDB(config.db_path)
    try:
        node_id = db._node_id()
        count = db.count()
    finally:
        db.close()
    print(
        "云同步状态：provider={provider}，node_id={node_id}，候选人={count}，已应用bundle={applied}".format(
            provider=config.provider,
            node_id=node_id,
            count=count,
            applied=len(state["applied_bundle_ids"]),
        )
    )
    return 0


def cmd_init_remote(args: argparse.Namespace) -> int:
    init_remote(_provider(_config_from_args(args)))
    print("飞书/云端同步目录初始化完成")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    result = pull(_config_from_args(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["blocked"] else 2


def cmd_push(args: argparse.Namespace) -> int:
    result = push(_config_from_args(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    result = sync(_config_from_args(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not result["pull"]["blocked"] else 2


def cmd_doctor(args: argparse.Namespace) -> int:
    provider = _provider(_config_from_args(args))
    if hasattr(provider, "doctor"):
        result = provider.doctor()  # type: ignore[attr-defined]
    else:
        result = {"ok": True}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--provider", default=os.environ.get("TALENT_SYNC_PROVIDER", "localfs"))
    parser.add_argument("--db", default="data/talent.db")
    parser.add_argument("--state", default="data/sync/cloud-state.json")
    parser.add_argument("--work-dir", default="data/sync/work")
    parser.add_argument("--localfs-root")
    parser.add_argument(
        "--feishu-root-folder-token",
        default=os.environ.get("TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN"),
    )
    parser.add_argument(
        "--feishu-root-name",
        default=os.environ.get("TALENT_SYNC_FEISHU_ROOT_NAME", "Talent Agent Sync"),
    )
    parser.add_argument("--feishu-as", default=os.environ.get("TALENT_SYNC_FEISHU_AS", "user"))
    parser.add_argument("--encryption-key", default="")
    parser.add_argument("--no-auto-apply", action="store_true")
    parser.add_argument("--include-wechat-files", action="store_true")
    parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default=None,
        help="push/export 模式；默认使用 TALENT_SYNC_EXPORT_MODE 或 incremental",
    )
    parser.add_argument("--since", default=None, help="增量 push 的起始时间")


def build_parser() -> argparse.ArgumentParser:
    _load_local_dotenv()
    parser = argparse.ArgumentParser(description="人才库飞书 Drive 云同步工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    keygen_parser = subparsers.add_parser("keygen")
    keygen_parser.set_defaults(func=cmd_keygen)
    for name, func in [
        ("status", cmd_status),
        ("init-remote", cmd_init_remote),
        ("pull", cmd_pull),
        ("push", cmd_push),
        ("sync", cmd_sync),
        ("doctor", cmd_doctor),
    ]:
        child = subparsers.add_parser(name)
        _add_common_flags(child)
        child.set_defaults(func=func)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
