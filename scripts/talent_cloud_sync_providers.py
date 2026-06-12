"""人才库云同步 provider 实现。"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from scripts.talent_cloud_sync_common import CloudSyncError, REMOTE_SCHEMA


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


def _now_utc() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _payload(result: dict[str, Any]) -> dict[str, Any]:
    data = result.get("data")
    if isinstance(data, dict):
        return data
    return result


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
            _write_json(schema_path, {"schema": REMOTE_SCHEMA, "created_at": _now_utc()})
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


def _resolve_lark_cli_argv(argv: list[str]) -> list[str]:
    if not argv or argv[0] != "lark-cli":
        return argv
    for candidate in ("lark-cli.cmd", "lark-cli.exe", "lark-cli", "lark-cli.ps1"):
        resolved = shutil.which(candidate)
        if resolved:
            return [resolved, *argv[1:]]
    return argv


def _run_lark_cli(argv: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        _resolve_lark_cli_argv(argv),
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

    def __init__(self, config: Any, runner=_run_lark_cli):
        if not config.feishu_root_folder_token:
            raise CloudSyncError(
                "TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN is required for Feishu provider"
            )
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
        root_token = self.config.feishu_root_folder_token
        meta_token = self._ensure_child_folder(root_token, "_meta")
        self.folder_tokens["_meta"] = meta_token
        self.folder_tokens["_meta/nodes"] = self._ensure_child_folder(meta_token, "nodes")
        for folder in ["bundle-index", "bundles", "attachments", "locks", "tmp"]:
            self.folder_tokens[folder] = self._ensure_child_folder(root_token, folder)
        return dict(self.folder_tokens)

    def _folder_token(self, folder: str) -> str:
        return self.folder_tokens.get(folder, self.config.feishu_root_folder_token or "")

    def _child_files(self, folder_token: str) -> list[dict[str, Any]]:
        params = json.dumps({"folder_token": folder_token, "page_size": 200}, ensure_ascii=False)
        result = self.runner(
            [
                "lark-cli",
                "drive",
                "files",
                "list",
                "--as",
                self.config.feishu_as,
                "--params",
                params,
            ]
        )
        data = _payload(result)
        return list(data.get("files") or data.get("items") or [])

    def _ensure_child_folder(self, parent_token: str, name: str) -> str:
        for item in self._child_files(parent_token):
            item_type = str(item.get("type") or "").lower()
            if item.get("name") == name and "folder" in item_type:
                token = item.get("token") or item.get("file_token") or item.get("folder_token")
                if token:
                    return str(token)
        result = self.runner(
            [
                "lark-cli",
                "drive",
                "+create-folder",
                "--as",
                self.config.feishu_as,
                "--folder-token",
                parent_token,
                "--name",
                name,
            ]
        )
        data = _payload(result)
        token = data.get("token") or data.get("file_token") or data.get("folder_token")
        if not token:
            raise CloudSyncError(f"Feishu create-folder response did not include token: {name}")
        return str(token)

    def list_files(self, folder: str) -> list[dict[str, Any]]:
        return self._child_files(self._folder_token(folder))

    def upload_file(self, folder: str, local_path: Path, name: str) -> dict[str, Any]:
        file_arg = local_path
        try:
            file_arg = local_path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            pass
        result = self.runner(
            [
                "lark-cli",
                "drive",
                "+upload",
                "--as",
                self.config.feishu_as,
                "--folder-token",
                self._folder_token(folder),
                "--file",
                str(file_arg),
                "--name",
                name,
            ]
        )
        data = _payload(result)
        token = data.get("file_token") or data.get("token")
        if not token:
            raise CloudSyncError("Feishu upload response did not include file token")
        return {"name": name, "token": token, "type": "file", "size": Path(local_path).stat().st_size}

    def download_file(self, token: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_arg = output_path
        try:
            output_arg = output_path.resolve().relative_to(Path.cwd().resolve())
        except ValueError:
            pass
        self.runner(
            [
                "lark-cli",
                "drive",
                "+download",
                "--as",
                self.config.feishu_as,
                "--file-token",
                token,
                "--output",
                str(output_arg),
                "--overwrite",
            ]
        )

    def quota(self) -> dict[str, Any]:
        auth = _payload(self.runner(["lark-cli", "auth", "status"]))
        open_id = (
            auth.get("userOpenId")
            or auth.get("openId")
            or (auth.get("identities") or {}).get("user", {}).get("openId")
        )
        if not open_id:
            raise CloudSyncError("cannot determine Feishu user open_id for quota check")
        params = json.dumps({"quota_detail_id": open_id}, ensure_ascii=False)
        return self.runner(
            [
                "lark-cli",
                "drive",
                "quota_details",
                "get",
                "--as",
                self.config.feishu_as,
                "--params",
                params,
            ]
        )

    def doctor(self) -> dict[str, Any]:
        self.runner(["lark-cli", "--version"])
        auth = self.runner(["lark-cli", "auth", "status"])
        scope_text = str(auth.get("scope") or "")
        missing = sorted(scope for scope in self.REQUIRED_SCOPES if scope not in scope_text)
        if missing:
            raise CloudSyncError("missing Feishu scopes: " + ", ".join(missing))
        try:
            quota = _payload(self.quota())
        except CloudSyncError as exc:
            quota = {"ok": False, "warning": str(exc)}
        if quota.get("is_tenant_quota_exceeded"):
            raise CloudSyncError("Feishu tenant quota is exceeded")
        return {"ok": True, "quota": quota}
