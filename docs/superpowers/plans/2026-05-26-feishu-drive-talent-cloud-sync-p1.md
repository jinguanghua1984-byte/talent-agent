# Feishu Drive Talent Cloud Sync P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build P1 cloud sync for the local talent SQLite database by pushing and pulling encrypted `talent_sync.py` bundles through Feishu Drive without ever syncing the raw SQLite file.

**Architecture:** Add a new `scripts/talent_cloud_sync.py` CLI that composes the existing `scripts.talent_sync` bundle export/verify/import functions with a cloud provider abstraction. P1 implements `LocalFsProvider` for deterministic tests and `FeishuDriveProvider` through the existing `lark-cli` command surface. Remote correctness comes from immutable encrypted bundle files plus immutable `bundle-index/*.json` descriptors; `latest.json` and node heartbeats are optional caches, never the source of truth.

**Tech Stack:** Python 3.12 via `.venv`, pytest, stdlib `argparse/dataclasses/hashlib/json/pathlib/subprocess/tempfile`, `python-dotenv`, `cryptography.fernet`, existing `TalentDB`, existing `scripts.talent_sync`, Feishu Drive via `lark-cli`.

---

## File Structure

- Create: `scripts/talent_cloud_sync.py`
  - Owns config loading, encryption, local state, provider abstraction, LocalFs provider, Feishu Drive provider, push/pull/sync/doctor/init-remote CLI, and orchestration.
- Create: `tests/test_talent_cloud_sync.py`
  - Covers config, encryption, LocalFs provider, push/pull/sync behavior, conflict blocking, tombstone propagation, idempotence, Feishu command construction, and doctor failures.
- Modify: `requirements.txt`
  - Add `cryptography>=42.0.0` for authenticated encryption via Fernet.
- Modify: `docs/manual/talent-sync-guide.md`
  - Add a short Feishu Drive P1 usage section after implementation is working.
- Modify: `tasks/todo.md` and `tasks/archive/2026-05.md`
  - Track implementation progress and archive the final result when execution is complete.

The implementation deliberately keeps all cloud sync code in one script for P1 because this repository already keeps operational CLI entrypoints under `scripts/`. If `scripts/talent_cloud_sync.py` grows past roughly 700 lines during implementation, split provider code into `scripts/talent_cloud_sync_providers.py` in the same task that crosses that threshold and update imports/tests immediately.

## Shared Test Helpers

The tests in this plan reuse these helpers. Put them near the top of `tests/test_talent_cloud_sync.py` as they become needed.

```python
import json
from pathlib import Path

import pytest

from scripts.talent_cloud_sync import (
    CloudSyncConfig,
    CloudSyncError,
    FeishuDriveProvider,
    LocalFsProvider,
    decrypt_bytes,
    encrypt_bytes,
    init_remote,
    keygen,
    load_state,
    main,
    pull,
    push,
    sync,
)
from scripts.talent_db import TalentDB


def _seed_candidate(db_path: Path, name: str, platform_id: str = "maimai-1") -> int:
    db = TalentDB(db_path)
    try:
        return db.ingest(
            {
                "name": name,
                "current_company": "Acme",
                "current_title": "AI Engineer",
                "platform_id": platform_id,
                "work_experience": [{"company": "Acme", "position": "AI Engineer"}],
            },
            platform="maimai",
        )
    finally:
        db.close()


def _candidate_names(db_path: Path) -> list[str]:
    db = TalentDB(db_path)
    try:
        return [candidate.name for candidate in db.list(limit=100)]
    finally:
        db.close()


def _config(tmp_path: Path, db_path: Path, key: str | None = None) -> CloudSyncConfig:
    return CloudSyncConfig(
        provider="localfs",
        db_path=db_path,
        state_path=tmp_path / "cloud-state.json",
        work_dir=tmp_path / "work",
        localfs_root=tmp_path / "remote",
        encryption_key=key or keygen(),
        auto_apply=True,
        include_wechat_files=False,
    )
```

---

### Task 1: Config, State, and Encryption Foundation

**Files:**
- Create: `scripts/talent_cloud_sync.py`
- Create: `tests/test_talent_cloud_sync.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add the encryption dependency**

Add this line to `requirements.txt`:

```text
cryptography>=42.0.0
```

- [ ] **Step 2: Write failing config, state, and encryption tests**

Create `tests/test_talent_cloud_sync.py` with the shared imports/helpers above and these tests:

```python
def test_keygen_encrypts_and_decrypts_bytes() -> None:
    key = keygen()
    ciphertext = encrypt_bytes(b"secret bundle bytes", key)

    assert ciphertext != b"secret bundle bytes"
    assert decrypt_bytes(ciphertext, key) == b"secret bundle bytes"


def test_decrypt_rejects_wrong_key() -> None:
    ciphertext = encrypt_bytes(b"secret bundle bytes", keygen())

    with pytest.raises(CloudSyncError, match="cannot decrypt bundle"):
        decrypt_bytes(ciphertext, keygen())


def test_config_from_env_requires_provider_specific_values(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "talent.db"
    monkeypatch.setenv("TALENT_SYNC_PROVIDER", "localfs")
    monkeypatch.setenv("TALENT_SYNC_LOCALFS_ROOT", str(tmp_path / "remote"))
    monkeypatch.setenv("TALENT_SYNC_ENCRYPTION_KEY", keygen())

    config = CloudSyncConfig.from_env(db_path=db_path)

    assert config.provider == "localfs"
    assert config.db_path == db_path
    assert config.localfs_root == tmp_path / "remote"
    assert config.state_path == Path("data/sync/cloud-state.json")


def test_load_state_creates_empty_state_when_missing(tmp_path: Path) -> None:
    state = load_state(tmp_path / "missing-state.json")

    assert state["schema"] == "talent_cloud_state_v1"
    assert state["applied_bundle_ids"] == []
    assert state["blocked_remote_bundles"] == []
```

- [ ] **Step 3: Run the new tests and verify they fail for missing code**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py -q
```

Expected: FAIL with import errors for `scripts.talent_cloud_sync`.

- [ ] **Step 4: Implement config, state, and encryption**

Create `scripts/talent_cloud_sync.py` with this foundation:

```python
"""人才库云端 bundle 同步工具。"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_sync import (
    export_bundle,
    import_bundle,
    plan_import,
    verify_bundle,
)
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT


STATE_SCHEMA = "talent_cloud_state_v1"
INDEX_SCHEMA = "talent_cloud_bundle_index_v1"
REMOTE_SCHEMA = "talent_cloud_remote_v1"


class CloudSyncError(RuntimeError):
    """Raised for recoverable cloud-sync failures."""


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

    @classmethod
    def from_env(cls, db_path: str | Path = "data/talent.db") -> "CloudSyncConfig":
        load_dotenv()
        provider = os.environ.get("TALENT_SYNC_PROVIDER", "localfs").strip()
        key = os.environ.get("TALENT_SYNC_ENCRYPTION_KEY", "").strip()
        if not key:
            raise CloudSyncError("TALENT_SYNC_ENCRYPTION_KEY is required")
        localfs_root = os.environ.get("TALENT_SYNC_LOCALFS_ROOT")
        feishu_root = os.environ.get("TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN")
        return cls(
            provider=provider,
            db_path=Path(db_path),
            state_path=Path(os.environ.get("TALENT_SYNC_STATE", "data/sync/cloud-state.json")),
            work_dir=Path(os.environ.get("TALENT_SYNC_WORK_DIR", "data/sync/work")),
            localfs_root=Path(localfs_root) if localfs_root else None,
            feishu_root_folder_token=feishu_root,
            feishu_root_name=os.environ.get("TALENT_SYNC_FEISHU_ROOT_NAME", "Talent Agent Sync"),
            feishu_as=os.environ.get("TALENT_SYNC_FEISHU_AS", "user"),
            encryption_key=key,
            auto_apply=os.environ.get("TALENT_SYNC_AUTO_APPLY", "1") != "0",
            include_wechat_files=os.environ.get("TALENT_SYNC_INCLUDE_WECHAT_FILES", "0") == "1",
        )


def keygen() -> str:
    return Fernet.generate_key().decode("ascii")


def _fernet(key: str) -> Fernet:
    try:
        raw = key.encode("ascii")
        base64.urlsafe_b64decode(raw)
        return Fernet(raw)
    except Exception as exc:  # noqa: BLE001 - expose a domain error to CLI users.
        raise CloudSyncError("TALENT_SYNC_ENCRYPTION_KEY must be a Fernet key") from exc


def encrypt_bytes(data: bytes, key: str) -> bytes:
    return _fernet(key).encrypt(data)


def decrypt_bytes(data: bytes, key: str) -> bytes:
    try:
        return _fernet(key).decrypt(data)
    except InvalidToken as exc:
        raise CloudSyncError("cannot decrypt bundle with configured key") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "schema": STATE_SCHEMA,
            "provider": "",
            "remote": {},
            "seen_bundle_ids": [],
            "applied_bundle_ids": [],
            "blocked_remote_bundles": [],
            "last_sync_at": None,
            "last_push_bundle_id": None,
        }
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if data.get("schema") != STATE_SCHEMA:
        raise CloudSyncError(f"unsupported cloud state schema: {data.get('schema')}")
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 5: Run the focused tests and verify Task 1 passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_keygen_encrypts_and_decrypts_bytes tests/test_talent_cloud_sync.py::test_decrypt_rejects_wrong_key tests/test_talent_cloud_sync.py::test_config_from_env_requires_provider_specific_values tests/test_talent_cloud_sync.py::test_load_state_creates_empty_state_when_missing -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add requirements.txt scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: add cloud sync config and encryption foundation"
```

---

### Task 2: Provider Interface and LocalFs Remote Layout

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing LocalFs provider tests**

Append these tests:

```python
def test_localfs_init_remote_creates_expected_layout(tmp_path: Path) -> None:
    provider = LocalFsProvider(tmp_path / "remote")

    layout = init_remote(provider)

    assert layout["root"].exists()
    for name in ["_meta", "_meta/nodes", "bundle-index", "bundles", "attachments", "locks", "tmp"]:
        assert (tmp_path / "remote" / name).is_dir()
    assert json.loads((tmp_path / "remote" / "_meta" / "schema.json").read_text())["schema"] == "talent_cloud_remote_v1"


def test_localfs_provider_upload_list_download_roundtrip(tmp_path: Path) -> None:
    provider = LocalFsProvider(tmp_path / "remote")
    init_remote(provider)
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")

    uploaded = provider.upload_file("bundles", source, "hello.txt")
    files = provider.list_files("bundles")
    target = tmp_path / "downloaded.txt"
    provider.download_file(uploaded["token"], target)

    assert files[0]["name"] == "hello.txt"
    assert files[0]["token"] == uploaded["token"]
    assert target.read_text(encoding="utf-8") == "hello"


def test_localfs_provider_rejects_duplicate_immutable_upload(tmp_path: Path) -> None:
    provider = LocalFsProvider(tmp_path / "remote")
    init_remote(provider)
    source = tmp_path / "source.txt"
    source.write_text("hello", encoding="utf-8")
    provider.upload_file("bundle-index", source, "same.json")

    with pytest.raises(CloudSyncError, match="remote file already exists"):
        provider.upload_file("bundle-index", source, "same.json")
```

- [ ] **Step 2: Run tests and verify they fail for missing provider code**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_localfs_init_remote_creates_expected_layout tests/test_talent_cloud_sync.py::test_localfs_provider_upload_list_download_roundtrip tests/test_talent_cloud_sync.py::test_localfs_provider_rejects_duplicate_immutable_upload -q
```

Expected: FAIL with missing `LocalFsProvider` or methods.

- [ ] **Step 3: Implement provider protocol and LocalFsProvider**

Append this code to `scripts/talent_cloud_sync.py`:

```python
class CloudProvider(Protocol):
    def ensure_layout(self) -> dict[str, Any]:
        ...

    def list_files(self, folder: str) -> list[dict[str, Any]]:
        ...

    def upload_file(self, folder: str, local_path: Path, name: str) -> dict[str, Any]:
        ...

    def download_file(self, token: str, output_path: Path) -> None:
        ...

    def quota(self) -> dict[str, Any]:
        ...


class LocalFsProvider:
    def __init__(self, root: str | Path):
        self.root = Path(root)

    def ensure_layout(self) -> dict[str, Any]:
        for relative in [
            "_meta",
            "_meta/nodes",
            "bundle-index",
            "bundles",
            "attachments",
            "locks",
            "tmp",
        ]:
            (self.root / relative).mkdir(parents=True, exist_ok=True)
        schema_path = self.root / "_meta" / "schema.json"
        if not schema_path.exists():
            schema_path.write_text(
                json.dumps({"schema": REMOTE_SCHEMA, "created_at": _now_utc()}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return {
            "root": self.root,
            "meta": self.root / "_meta",
            "bundle_index": self.root / "bundle-index",
            "bundles": self.root / "bundles",
            "attachments": self.root / "attachments",
        }

    def list_files(self, folder: str) -> list[dict[str, Any]]:
        directory = self.root / folder
        if not directory.exists():
            return []
        files: list[dict[str, Any]] = []
        for path in sorted(directory.iterdir()):
            if not path.is_file():
                continue
            files.append(
                {
                    "name": path.name,
                    "token": str(path),
                    "size": path.stat().st_size,
                    "modified_time": str(int(path.stat().st_mtime)),
                    "type": "file",
                }
            )
        return files

    def upload_file(self, folder: str, local_path: Path, name: str) -> dict[str, Any]:
        target_dir = self.root / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / Path(name).name
        if target.exists():
            raise CloudSyncError(f"remote file already exists: {folder}/{name}")
        target.write_bytes(Path(local_path).read_bytes())
        return {
            "name": target.name,
            "token": str(target),
            "size": target.stat().st_size,
            "modified_time": str(int(target.stat().st_mtime)),
            "type": "file",
        }

    def download_file(self, token: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(Path(token).read_bytes())

    def quota(self) -> dict[str, Any]:
        return {"ok": True, "is_tenant_quota_exceeded": False, "available": None}


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
```

- [ ] **Step 4: Run LocalFs provider tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_localfs_init_remote_creates_expected_layout tests/test_talent_cloud_sync.py::test_localfs_provider_upload_list_download_roundtrip tests/test_talent_cloud_sync.py::test_localfs_provider_rejects_duplicate_immutable_upload -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: add local cloud sync provider"
```

---

### Task 3: Push Pipeline with Encrypted Bundles and Immutable Indexes

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing push tests**

Append these tests:

```python
def test_push_exports_encrypted_bundle_and_index_without_plaintext(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_candidate(db_path, "Alice")
    config = _config(tmp_path, db_path)
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)

    result = push(config, provider=provider)

    assert result["uploaded"] is True
    index_files = provider.list_files("bundle-index")
    bundle_files = provider.list_files("bundles")
    assert len(index_files) == 1
    assert len(bundle_files) == 1
    encrypted = Path(bundle_files[0]["token"]).read_bytes()
    assert b"Alice" not in encrypted
    index_data = json.loads(Path(index_files[0]["token"]).read_text(encoding="utf-8"))
    assert index_data["schema"] == "talent_cloud_bundle_index_v1"
    assert index_data["bundle_file_token"] == bundle_files[0]["token"]
    assert index_data["bundle_sha256"] == result["bundle_sha256"]
    assert index_data["tables"]["candidates"] == 1


def test_push_refuses_when_local_conflicts_are_open(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_candidate(db_path, "Alice")
    db = TalentDB(db_path)
    try:
        db._conn.execute(
            """
            INSERT INTO sync_conflicts(entity_type, entity_sync_id, field, local_value, remote_value, source_node_id, status)
            VALUES ('candidate', 'candidate:manual', 'name', 'Alice', 'Alicia', 'remote-node', 'open')
            """
        )
        db._conn.commit()
    finally:
        db.close()
    config = _config(tmp_path, db_path)
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)

    with pytest.raises(CloudSyncError, match="open sync conflicts"):
        push(config, provider=provider)
```

- [ ] **Step 2: Run push tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_push_exports_encrypted_bundle_and_index_without_plaintext tests/test_talent_cloud_sync.py::test_push_refuses_when_local_conflicts_are_open -q
```

Expected: FAIL because `push` is not implemented.

- [ ] **Step 3: Implement push and index helpers**

Append this code:

```python
def _node_id(db_path: Path) -> str:
    db = TalentDB(db_path)
    try:
        return db._node_id()
    finally:
        db.close()


def _open_conflict_count(db_path: Path) -> int:
    db = TalentDB(db_path)
    try:
        row = db._conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE status = 'open'"
        ).fetchone()
        return int(row[0])
    finally:
        db.close()


def _remote_index_name(created_at: str, node_id: str, bundle_id: str) -> str:
    stamp = created_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
    return f"{stamp}-{node_id}-{bundle_id}.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_bundle_manifest(bundle_path: Path) -> dict[str, Any]:
    import zipfile

    with zipfile.ZipFile(bundle_path) as bundle:
        return json.loads(bundle.read("manifest.json").decode("utf-8"))


def push(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    if _open_conflict_count(config.db_path) > 0:
        raise CloudSyncError("open sync conflicts exist; resolve them before push")

    config.work_dir.mkdir(parents=True, exist_ok=True)
    plain_bundle = config.work_dir / f"talent-sync-{uuid.uuid4()}.zip"
    encrypted_bundle = plain_bundle.with_suffix(".zip.enc")
    summary = export_bundle(
        config.db_path,
        plain_bundle,
        mode="full",
        include_wechat_files=config.include_wechat_files,
    )
    verification = verify_bundle(plain_bundle)
    if not verification["ok"]:
        raise CloudSyncError("exported bundle failed verification: " + "; ".join(verification["errors"]))

    plain_bytes = plain_bundle.read_bytes()
    encrypted_bundle.write_bytes(encrypt_bytes(plain_bytes, config.encryption_key))
    encrypted_sha = _sha256_file(encrypted_bundle)
    manifest = _load_bundle_manifest(plain_bundle)
    bundle_id = str(manifest["export_id"])
    source_node_id = str(manifest["source_node_id"])
    created_at = str(manifest["created_at"])
    bundle_name = f"{created_at.replace(':', '').replace('-', '').replace('+00:00', 'Z')}-{source_node_id}-{bundle_id}.zip.enc"
    uploaded_bundle = provider.upload_file("bundles", encrypted_bundle, bundle_name)
    index = {
        "schema": INDEX_SCHEMA,
        "bundle_id": bundle_id,
        "source_node_id": source_node_id,
        "created_at": created_at,
        "bundle_name": bundle_name,
        "bundle_file_token": uploaded_bundle["token"],
        "bundle_sha256": encrypted_sha,
        "bundle_size": encrypted_bundle.stat().st_size,
        "encrypted": True,
        "talent_sync_bundle_sha256": _sha256_bytes(plain_bytes),
        "tables": summary["tables"],
    }
    index_path = config.work_dir / _remote_index_name(created_at, source_node_id, bundle_id)
    _write_json(index_path, index)
    uploaded_index = provider.upload_file("bundle-index", index_path, index_path.name)

    state = load_state(config.state_path)
    state["provider"] = config.provider
    state["last_push_bundle_id"] = bundle_id
    state["last_sync_at"] = _now_utc()
    if bundle_id not in state["seen_bundle_ids"]:
        state["seen_bundle_ids"].append(bundle_id)
    save_state(config.state_path, state)
    return {
        "uploaded": True,
        "bundle_id": bundle_id,
        "bundle_sha256": encrypted_sha,
        "bundle_file": uploaded_bundle,
        "index_file": uploaded_index,
        "tables": summary["tables"],
    }
```

- [ ] **Step 4: Run push tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_push_exports_encrypted_bundle_and_index_without_plaintext tests/test_talent_cloud_sync.py::test_push_refuses_when_local_conflicts_are_open -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: upload encrypted talent sync bundles"
```

---

### Task 4: Pull Pipeline, Wrong-Key Safety, and Conflict Blocking

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing pull tests**

Append these tests:

```python
def test_pull_imports_remote_bundle_after_dry_run(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = _config(tmp_path / "target", target_db, key=key)
    target_config = dataclasses.replace(target_config, localfs_root=source_config.localfs_root)
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    result = pull(target_config, provider=provider)

    assert result["applied"] == 1
    assert _candidate_names(target_db) == ["Alice"]


def test_pull_rejects_wrong_encryption_key_without_creating_target_db(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=keygen())
    target_config = _config(tmp_path / "target", target_db, key=keygen())
    target_config = dataclasses.replace(target_config, localfs_root=source_config.localfs_root)
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    with pytest.raises(CloudSyncError, match="cannot decrypt bundle"):
        pull(target_config, provider=provider)

    assert not target_db.exists()


def test_pull_stops_on_conflict_without_auto_apply(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice", platform_id="maimai-1")
    _seed_candidate(target_db, "Alicia", platform_id="maimai-1")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = _config(tmp_path / "target", target_db, key=key)
    target_config = dataclasses.replace(target_config, localfs_root=source_config.localfs_root)
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    result = pull(target_config, provider=provider)

    assert result["applied"] == 0
    assert result["blocked"][0]["reason"] == "conflicts"
    assert _candidate_names(target_db) == ["Alicia"]
```

Add `import dataclasses` at the top of `tests/test_talent_cloud_sync.py`.

- [ ] **Step 2: Run pull tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_pull_imports_remote_bundle_after_dry_run tests/test_talent_cloud_sync.py::test_pull_rejects_wrong_encryption_key_without_creating_target_db tests/test_talent_cloud_sync.py::test_pull_stops_on_conflict_without_auto_apply -q
```

Expected: FAIL because `pull` is not implemented.

- [ ] **Step 3: Implement pull and remote index loading**

Append this code:

```python
def _has_conflicts(plan: dict[str, Any]) -> bool:
    return any(count > 0 for count in plan.get("conflicts", {}).values())


def _download_indexes(provider: CloudProvider, work_dir: Path) -> list[dict[str, Any]]:
    indexes: list[dict[str, Any]] = []
    index_dir = work_dir / "indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
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
    db = TalentDB(db_path)
    try:
        row = db._conn.execute(
            "SELECT 1 FROM sync_imports WHERE bundle_id = ? LIMIT 1",
            (bundle_id,),
        ).fetchone()
        return row is not None
    finally:
        db.close()


def pull(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    config.work_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(config.state_path)
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
        encrypted_path = config.work_dir / "downloads" / str(index["bundle_name"])
        provider.download_file(str(index["bundle_file_token"]), encrypted_path)
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
        if config.auto_apply:
            import_bundle(plain_path, config.db_path, apply=True, confirm=CONFIRM_SYNC_TEXT)
            applied += 1
            state["applied_bundle_ids"].append(bundle_id)
        else:
            skipped += 1
        if bundle_id not in state["seen_bundle_ids"]:
            state["seen_bundle_ids"].append(bundle_id)
    state["blocked_remote_bundles"] = blocked
    state["last_sync_at"] = _now_utc()
    save_state(config.state_path, state)
    return {"applied": applied, "skipped": skipped, "blocked": blocked}
```

- [ ] **Step 4: Run pull tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_pull_imports_remote_bundle_after_dry_run tests/test_talent_cloud_sync.py::test_pull_rejects_wrong_encryption_key_without_creating_target_db tests/test_talent_cloud_sync.py::test_pull_stops_on_conflict_without_auto_apply -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: pull encrypted talent bundles safely"
```

---

### Task 5: Sync Command, Tombstones, and Idempotence

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing sync and tombstone tests**

Append these tests:

```python
def test_sync_is_idempotent_for_repeated_runs(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = _config(tmp_path / "target", target_db, key=key)
    target_config = dataclasses.replace(target_config, localfs_root=source_config.localfs_root)
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    first = sync(target_config, provider=provider)
    second = sync(target_config, provider=provider)

    assert first["pull"]["applied"] == 1
    assert second["pull"]["applied"] == 0
    assert _candidate_names(target_db) == ["Alice"]


def test_sync_propagates_tombstone_without_resurrection(tmp_path: Path) -> None:
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    key = keygen()
    candidate_id = _seed_candidate(left_db, "Alice")
    left_config = _config(tmp_path / "left", left_db, key=key)
    right_config = _config(tmp_path / "right", right_db, key=key)
    right_config = dataclasses.replace(right_config, localfs_root=left_config.localfs_root)
    provider = LocalFsProvider(left_config.localfs_root)
    init_remote(provider)
    push(left_config, provider=provider)
    pull(right_config, provider=provider)
    db = TalentDB(right_db)
    try:
        right_candidate = db.list(limit=1)[0]
        db.delete_candidate(right_candidate.id)
    finally:
        db.close()
    push(right_config, provider=provider)

    result = pull(left_config, provider=provider)

    assert result["applied"] == 1
    assert _candidate_names(left_db) == []
```

- [ ] **Step 2: Run tests and verify sync is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_sync_is_idempotent_for_repeated_runs tests/test_talent_cloud_sync.py::test_sync_propagates_tombstone_without_resurrection -q
```

Expected: FAIL because `sync` is not implemented or tombstone propagation is incomplete.

- [ ] **Step 3: Implement sync**

Append this code:

```python
def sync(config: CloudSyncConfig, provider: CloudProvider | None = None) -> dict[str, Any]:
    provider = provider or _provider(config)
    provider.ensure_layout()
    pull_result = pull(config, provider=provider)
    push_result: dict[str, Any] | None = None
    if not pull_result["blocked"]:
        push_result = push(config, provider=provider)
    return {"pull": pull_result, "push": push_result}
```

If `test_sync_is_idempotent_for_repeated_runs` now creates a new bundle on the second run, update `push` to skip exporting when there are no local changes since last push. Implement this conservative P1 check:

```python
def _db_fingerprint(db_path: Path) -> str:
    if not db_path.exists():
        return "missing"
    return _sha256_file(db_path)
```

Then at the start of `push`, after checking open conflicts:

```python
state = load_state(config.state_path)
current_fingerprint = _db_fingerprint(config.db_path)
if state.get("last_pushed_db_fingerprint") == current_fingerprint:
    return {"uploaded": False, "reason": "unchanged", "bundle_id": state.get("last_push_bundle_id")}
```

And after successful upload:

```python
state["last_pushed_db_fingerprint"] = current_fingerprint
```

- [ ] **Step 4: Run sync and tombstone tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_sync_is_idempotent_for_repeated_runs tests/test_talent_cloud_sync.py::test_sync_propagates_tombstone_without_resurrection -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: add cloud sync orchestration"
```

---

### Task 6: FeishuDriveProvider and Doctor

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing Feishu provider command tests**

Append these tests:

```python
class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, argv: list[str]) -> dict:
        self.commands.append(argv)
        if argv[:3] == ["lark-cli", "drive", "+create-folder"]:
            return {"token": "fld_child", "url": "https://feishu.cn/drive/folder/fld_child"}
        if argv[:3] == ["lark-cli", "drive", "files"] and "list" in argv:
            return {"files": [{"name": "index.json", "token": "box_index", "type": "file", "size": 1}]}
        if argv[:3] == ["lark-cli", "drive", "+upload"]:
            return {"file_token": "box_uploaded", "token": "box_uploaded", "name": "upload.bin"}
        if argv[:3] == ["lark-cli", "drive", "quota_details"]:
            return {"is_tenant_quota_exceeded": False, "user_quota": {"limit": "1000", "usage": "100"}}
        if argv[:3] == ["lark-cli", "auth", "status"]:
            return {"identities": {"user": {"available": True}}, "scope": "drive:file:upload drive:file:download drive:drive.metadata:readonly drive:quota_detail:read_one space:folder:create"}
        if argv[:2] == ["lark-cli", "--version"]:
            return {"version": "1.0.39"}
        raise AssertionError(f"unexpected command: {argv}")


def test_feishu_provider_builds_upload_and_list_commands(tmp_path: Path) -> None:
    runner = FakeRunner()
    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=runner)
    source = tmp_path / "bundle.enc"
    source.write_bytes(b"data")

    provider.list_files("bundle-index")
    provider.upload_file("bundles", source, "bundle.enc")

    assert any("files" in command and "list" in command for command in runner.commands)
    assert any("+upload" in command and "--folder-token" in command for command in runner.commands)


def test_doctor_rejects_missing_feishu_scope(tmp_path: Path) -> None:
    class MissingScopeRunner(FakeRunner):
        def __call__(self, argv: list[str]) -> dict:
            if argv[:3] == ["lark-cli", "auth", "status"]:
                return {"identities": {"user": {"available": True}}, "scope": "drive:file:upload"}
            return super().__call__(argv)

    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=MissingScopeRunner())

    with pytest.raises(CloudSyncError, match="missing Feishu scopes"):
        provider.doctor()
```

- [ ] **Step 2: Run Feishu tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_feishu_provider_builds_upload_and_list_commands tests/test_talent_cloud_sync.py::test_doctor_rejects_missing_feishu_scope -q
```

Expected: FAIL because `FeishuDriveProvider` is not implemented.

- [ ] **Step 3: Implement FeishuDriveProvider**

Append this code:

```python
def _run_lark_cli(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        argv,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise CloudSyncError(completed.stderr or completed.stdout or "lark-cli failed")
    text = completed.stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


class FeishuDriveProvider:
    REQUIRED_SCOPES = {
        "drive:file:upload",
        "drive:file:download",
        "drive:drive.metadata:readonly",
        "drive:quota_detail:read_one",
        "space:folder:create",
    }

    def __init__(self, config: CloudSyncConfig, runner=_run_lark_cli):
        if not config.feishu_root_folder_token:
            raise CloudSyncError("TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN is required for Feishu provider")
        self.config = config
        self.runner = runner
        self.folder_tokens = {
            "root": config.feishu_root_folder_token,
            "_meta": config.feishu_root_folder_token,
            "bundle-index": config.feishu_root_folder_token,
            "bundles": config.feishu_root_folder_token,
            "attachments": config.feishu_root_folder_token,
            "locks": config.feishu_root_folder_token,
            "tmp": config.feishu_root_folder_token,
        }

    def ensure_layout(self) -> dict[str, Any]:
        return {"root": self.config.feishu_root_folder_token}

    def _folder_token(self, folder: str) -> str:
        return self.folder_tokens.get(folder, self.config.feishu_root_folder_token or "")

    def list_files(self, folder: str) -> list[dict[str, Any]]:
        params = json.dumps({"folder_token": self._folder_token(folder), "page_size": 200}, ensure_ascii=False)
        result = self.runner([
            "lark-cli",
            "drive",
            "files",
            "list",
            "--as",
            self.config.feishu_as,
            "--params",
            params,
        ])
        return list(result.get("files") or [])

    def upload_file(self, folder: str, local_path: Path, name: str) -> dict[str, Any]:
        result = self.runner([
            "lark-cli",
            "drive",
            "+upload",
            "--as",
            self.config.feishu_as,
            "--folder-token",
            self._folder_token(folder),
            "--file",
            str(local_path),
            "--name",
            name,
        ])
        token = result.get("file_token") or result.get("token")
        if not token:
            raise CloudSyncError("Feishu upload response did not include file token")
        return {"name": name, "token": token, "type": "file", "size": Path(local_path).stat().st_size}

    def download_file(self, token: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self.runner([
            "lark-cli",
            "drive",
            "+download",
            "--as",
            self.config.feishu_as,
            "--file-token",
            token,
            "--output",
            str(output_path),
            "--overwrite",
        ])

    def quota(self) -> dict[str, Any]:
        return self.runner(["lark-cli", "drive", "quota_details", "get", "--as", self.config.feishu_as])

    def doctor(self) -> dict[str, Any]:
        self.runner(["lark-cli", "--version"])
        auth = self.runner(["lark-cli", "auth", "status"])
        scope_text = str(auth.get("scope") or "")
        missing = sorted(scope for scope in self.REQUIRED_SCOPES if scope not in scope_text)
        if missing:
            raise CloudSyncError("missing Feishu scopes: " + ", ".join(missing))
        quota = self.quota()
        if quota.get("is_tenant_quota_exceeded"):
            raise CloudSyncError("Feishu tenant quota is exceeded")
        return {"ok": True, "quota": quota}
```

- [ ] **Step 4: Run Feishu provider tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_feishu_provider_builds_upload_and_list_commands tests/test_talent_cloud_sync.py::test_doctor_rejects_missing_feishu_scope -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
git commit -m "feat: add Feishu Drive cloud sync provider"
```

---

### Task 7: CLI, Manual Docs, and Final Verification

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`
- Modify: `docs/manual/talent-sync-guide.md`
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-05.md`

- [ ] **Step 1: Write failing CLI tests**

Append these tests:

```python
def test_cloud_sync_cli_keygen_prints_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["keygen"]) == 0
    output = capsys.readouterr().out.strip()
    assert decrypt_bytes(encrypt_bytes(b"x", output), output) == b"x"


def test_cloud_sync_cli_status_for_missing_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    config_path = tmp_path / "state.json"
    assert main([
        "status",
        "--provider",
        "localfs",
        "--db",
        str(tmp_path / "missing.db"),
        "--state",
        str(config_path),
        "--localfs-root",
        str(tmp_path / "remote"),
        "--encryption-key",
        keygen(),
    ]) == 0
    assert "missing" in capsys.readouterr().out
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_cloud_sync_cli_keygen_prints_key tests/test_talent_cloud_sync.py::test_cloud_sync_cli_status_for_missing_db -q
```

Expected: FAIL because CLI parser is incomplete.

- [ ] **Step 3: Implement CLI parser and commands**

Append this code and ensure `if __name__ == "__main__"` calls `main()`:

```python
def _config_from_args(args: argparse.Namespace) -> CloudSyncConfig:
    if args.encryption_key:
        key = args.encryption_key
    else:
        key = os.environ.get("TALENT_SYNC_ENCRYPTION_KEY", "")
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
        result = provider.doctor()
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
    parser.add_argument("--feishu-root-folder-token", default=os.environ.get("TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN"))
    parser.add_argument("--feishu-root-name", default=os.environ.get("TALENT_SYNC_FEISHU_ROOT_NAME", "Talent Agent Sync"))
    parser.add_argument("--feishu-as", default=os.environ.get("TALENT_SYNC_FEISHU_AS", "user"))
    parser.add_argument("--encryption-key", default="")
    parser.add_argument("--no-auto-apply", action="store_true")
    parser.add_argument("--include-wechat-files", action="store_true")


def build_parser() -> argparse.ArgumentParser:
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
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_cloud_sync_cli_keygen_prints_key tests/test_talent_cloud_sync.py::test_cloud_sync_cli_status_for_missing_db -q
```

Expected: `2 passed`.

- [ ] **Step 5: Update the manual**

Add this section to `docs/manual/talent-sync-guide.md`:

```markdown
## 飞书 Drive 云同步 P1

飞书 Drive 云同步不会直接同步 `data/talent.db`。它会先用 `scripts/talent_sync.py` 导出可校验 bundle，再加密上传到飞书 Drive；另一台机器下载后先解密、校验、dry-run，只有无冲突时才自动 apply。

首次使用：

```bash
python -m scripts.talent_cloud_sync keygen
export TALENT_SYNC_PROVIDER=feishu
export TALENT_SYNC_FEISHU_AS=user
export TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN=<fld...>
export TALENT_SYNC_ENCRYPTION_KEY=<keygen 输出>
python -m scripts.talent_cloud_sync doctor
python -m scripts.talent_cloud_sync init-remote
```

日常同步：

```bash
python -m scripts.talent_cloud_sync sync
```

安全边界：

- 不把 raw SQLite 放入飞书 Drive。
- 云端只保存加密 bundle 和索引。
- `lark-cli drive +sync` 不能替代该命令。
- dry-run 有冲突时默认停止自动 apply。
```

- [ ] **Step 6: Run focused and regression tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py tests/test_talent_sync.py -q
.venv/bin/python -m py_compile scripts/talent_cloud_sync.py scripts/talent_sync.py
git diff --check -- scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py requirements.txt docs/manual/talent-sync-guide.md tasks/todo.md tasks/archive/2026-05.md
```

Expected:

- `tests/test_talent_cloud_sync.py tests/test_talent_sync.py`: all tests pass.
- `py_compile`: no output.
- `git diff --check`: no output.

- [ ] **Step 7: Run full repository tests**

Run:

```bash
.venv/bin/python -m pytest tests scripts -q
```

Expected: all tests pass, with only known existing warnings. If a new failure appears, stop and debug before marking the task complete.

- [ ] **Step 8: Update task records**

Update `tasks/todo.md` with a short Review containing:

- Commands implemented.
- Whether Feishu live APIs were touched.
- Test counts.
- Any known limitations, especially user-provided `TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN` and encryption key handling.

Append the full task record to `tasks/archive/2026-05.md`.

- [ ] **Step 9: Commit Task 7**

Run:

```bash
git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py requirements.txt docs/manual/talent-sync-guide.md tasks/todo.md tasks/archive/2026-05.md
git commit -m "feat: add Feishu Drive talent cloud sync P1"
```

---

## Plan Self-Review

Spec coverage:

- Feishu Drive provider: Task 6.
- LocalFs provider for tests: Task 2.
- Bundle export/verify/import reuse: Tasks 3 and 4.
- Encryption: Task 1 and Task 3.
- Immutable `bundle-index`: Task 3 and Task 4.
- No raw SQLite Drive sync: Task 3 encrypted payload assertion and Task 7 manual.
- Conflict blocking with confirmation path: Task 4.
- Tombstone propagation: Task 5.
- Idempotent repeated sync: Task 5.
- Wrong key safety: Task 4.
- Feishu capacity/scope doctor: Task 6.
- CLI commands `status/pull/push/sync/doctor/init-remote/keygen`: Task 7.
- Manual docs and task archive: Task 7.

Execution notes:

- Use `.venv/bin/python` for every pytest and Python command.
- Do not create real Feishu folders during tests. Feishu provider tests use a fake runner.
- Do not write `data/talent.db` in tests; every database path is under `tmp_path`.
- Do not use `lark-cli drive +sync` in the implementation.
- Do not store `TALENT_SYNC_ENCRYPTION_KEY` in tracked files.
