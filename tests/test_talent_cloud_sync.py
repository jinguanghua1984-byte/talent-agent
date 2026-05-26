import dataclasses
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import talent_cloud_sync_providers as provider_module
from scripts.talent_db import TalentDB
from scripts.talent_cloud_sync import (
    CloudSyncConfig,
    CloudSyncError,
    FeishuDriveProvider,
    LocalFsProvider,
    _config_from_args,
    build_parser,
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
        return [candidate.name for candidate in db.search(page_size=100).items]
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


def test_keygen_encrypts_and_decrypts_bytes() -> None:
    key = keygen()
    ciphertext = encrypt_bytes(b"secret bundle bytes", key)

    assert ciphertext != b"secret bundle bytes"
    assert decrypt_bytes(ciphertext, key) == b"secret bundle bytes"


def test_decrypt_rejects_wrong_key() -> None:
    ciphertext = encrypt_bytes(b"secret bundle bytes", keygen())

    with pytest.raises(CloudSyncError, match="cannot decrypt bundle"):
        decrypt_bytes(ciphertext, keygen())


def test_config_from_env_requires_provider_specific_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_localfs_init_remote_creates_expected_layout(tmp_path: Path) -> None:
    provider = LocalFsProvider(tmp_path / "remote")

    layout = init_remote(provider)

    assert layout["root"].exists()
    for name in [
        "_meta",
        "_meta/nodes",
        "bundle-index",
        "bundles",
        "attachments",
        "locks",
        "tmp",
    ]:
        assert (tmp_path / "remote" / name).is_dir()
    schema = json.loads((tmp_path / "remote" / "_meta" / "schema.json").read_text())
    assert schema["schema"] == "talent_cloud_remote_v1"


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


def test_push_skips_when_logical_database_is_unchanged(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_candidate(db_path, "Alice")
    config = _config(tmp_path, db_path)
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)

    first = push(config, provider=provider)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO sync_meta(key, value) VALUES ('local_note', 'ignored')"
        )
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    second = push(config, provider=provider)

    assert first["uploaded"] is True
    assert second["uploaded"] is False
    assert second["reason"] == "unchanged"
    assert len(provider.list_files("bundle-index")) == 1
    assert len(provider.list_files("bundles")) == 1


def test_push_and_pull_clean_temporary_bundle_files(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = dataclasses.replace(
        _config(tmp_path / "target", target_db, key=key),
        localfs_root=source_config.localfs_root,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)

    push(source_config, provider=provider)
    pull(target_config, provider=provider)

    for work_dir in [source_config.work_dir, target_config.work_dir]:
        leftovers = [
            path
            for path in work_dir.rglob("*")
            if path.is_file() and (".zip" in path.name or path.suffix == ".enc")
        ]
        assert leftovers == []


def test_push_can_split_large_encrypted_bundle_and_pull_reassembles_parts(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = dataclasses.replace(
        _config(tmp_path / "source", source_db, key=key),
        max_upload_bytes=64,
    )
    target_config = dataclasses.replace(
        _config(tmp_path / "target", target_db, key=key),
        localfs_root=source_config.localfs_root,
        max_upload_bytes=64,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)

    push_result = push(source_config, provider=provider)
    pull_result = pull(target_config, provider=provider)

    index_files = provider.list_files("bundle-index")
    bundle_files = provider.list_files("bundles")
    index_data = json.loads(Path(index_files[0]["token"]).read_text(encoding="utf-8"))
    assert push_result["uploaded"] is True
    assert len(index_data["bundle_parts"]) > 1
    assert len(bundle_files) == len(index_data["bundle_parts"])
    assert all(".part" in part["name"] for part in index_data["bundle_parts"])
    assert pull_result["applied"] == 1
    assert _candidate_names(target_db) == ["Alice"]


def test_push_refuses_when_local_conflicts_are_open(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_candidate(db_path, "Alice")
    db = TalentDB(db_path)
    try:
        db._conn.execute(
            """
            INSERT INTO sync_conflicts(
                entity_type, entity_sync_id, field_name,
                local_value, remote_value, source_node_id, status
            )
            VALUES ('candidate', 'candidate:manual', 'name',
                    'Alice', 'Alicia', 'remote-node', 'open')
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


def test_pull_imports_remote_bundle_after_dry_run(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = _config(tmp_path / "target", target_db, key=key)
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
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
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
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
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    result = pull(target_config, provider=provider)

    assert result["applied"] == 0
    assert result["blocked"][0]["reason"] == "conflicts"
    assert _candidate_names(target_db) == ["Alicia"]


def test_sync_is_idempotent_for_repeated_runs(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    key = keygen()
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key)
    target_config = _config(tmp_path / "target", target_db, key=key)
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    first = sync(target_config, provider=provider)
    second = sync(target_config, provider=provider)

    assert first["pull"]["applied"] == 1
    assert second["pull"]["applied"] == 0
    assert second["push"]["uploaded"] is False
    assert len(provider.list_files("bundle-index")) == 2
    assert _candidate_names(target_db) == ["Alice"]


def test_sync_propagates_tombstone_without_resurrection(tmp_path: Path) -> None:
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    key = keygen()
    _seed_candidate(left_db, "Alice")
    left_config = _config(tmp_path / "left", left_db, key=key)
    right_config = _config(tmp_path / "right", right_db, key=key)
    right_config = dataclasses.replace(
        right_config,
        localfs_root=left_config.localfs_root,
    )
    provider = LocalFsProvider(left_config.localfs_root)
    init_remote(provider)
    push(left_config, provider=provider)
    pull(right_config, provider=provider)
    db = TalentDB(right_db)
    try:
        right_candidate = db.search(page_size=1).items[0]
        db.delete_candidate(right_candidate.id)
    finally:
        db.close()
    push(right_config, provider=provider)

    result = pull(left_config, provider=provider)

    assert result["applied"] == 1
    assert _candidate_names(left_db) == []


class FakeRunner:
    def __init__(self) -> None:
        self.commands: list[list[str]] = []

    def __call__(self, argv: list[str]) -> dict:
        self.commands.append(argv)
        if argv[:3] == ["lark-cli", "drive", "+create-folder"]:
            return {"token": "fld_child", "url": "https://feishu.cn/drive/folder/fld_child"}
        if argv[:3] == ["lark-cli", "drive", "files"] and "list" in argv:
            return {
                "files": [
                    {"name": "index.json", "token": "box_index", "type": "file", "size": 1}
                ]
            }
        if argv[:3] == ["lark-cli", "drive", "+upload"]:
            return {"file_token": "box_uploaded", "token": "box_uploaded", "name": "upload.bin"}
        if argv[:3] == ["lark-cli", "drive", "quota_details"]:
            return {
                "is_tenant_quota_exceeded": False,
                "user_quota": {"limit": "1000", "usage": "100"},
            }
        if argv[:3] == ["lark-cli", "auth", "status"]:
            return {
                "identities": {"user": {"available": True}},
                "scope": (
                    "drive:file:upload drive:file:download "
                    "drive:drive.metadata:readonly drive:quota_detail:read_one "
                    "space:folder:create"
                ),
                "userOpenId": "ou_current_user",
            }
        if argv[:2] == ["lark-cli", "--version"]:
            return {"version": "1.0.39"}
        raise AssertionError(f"unexpected command: {argv}")


class WrappedFeishuRunner(FakeRunner):
    def __call__(self, argv: list[str]) -> dict:
        result = super().__call__(argv)
        if argv[:3] == ["lark-cli", "drive", "files"] and "list" in argv:
            return {"code": 0, "data": result, "msg": "success"}
        if argv[:3] == ["lark-cli", "drive", "+create-folder"]:
            return {"ok": True, "data": {"folder_token": result["token"], "name": result["url"]}}
        if argv[:3] == ["lark-cli", "drive", "+upload"]:
            return {"ok": True, "data": result}
        if argv[:3] == ["lark-cli", "drive", "quota_details"]:
            return {"code": 0, "data": result, "msg": "success"}
        return result


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


def test_feishu_init_remote_creates_p1_subfolders_without_drive_sync(tmp_path: Path) -> None:
    runner = FakeRunner()
    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=runner)

    layout = init_remote(provider)

    create_commands = [command for command in runner.commands if "+create-folder" in command]
    created_names = {command[command.index("--name") + 1] for command in create_commands}
    assert {"_meta", "nodes", "bundle-index", "bundles", "attachments", "locks", "tmp"} <= created_names
    assert "bundle-index" in layout
    assert not any("+sync" in command for command in runner.commands)


def test_feishu_provider_accepts_lark_cli_wrapped_responses(tmp_path: Path) -> None:
    runner = WrappedFeishuRunner()
    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=runner)
    source = tmp_path / "bundle.enc"
    source.write_bytes(b"data")

    layout = init_remote(provider)
    files = provider.list_files("bundle-index")
    uploaded = provider.upload_file("bundles", source, "bundle.enc")
    doctor = provider.doctor()

    assert layout["bundle-index"] == "fld_child"
    assert files[0]["token"] == "box_index"
    assert uploaded["token"] == "box_uploaded"
    assert doctor["ok"] is True
    assert any(
        "quota_details" in command
        and "--params" in command
        and "ou_current_user" in command[command.index("--params") + 1]
        for command in runner.commands
    )


def test_feishu_download_uses_relative_output_path_inside_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class DownloadRunner(FakeRunner):
        def __call__(self, argv: list[str]) -> dict:
            if argv[:3] == ["lark-cli", "drive", "+download"]:
                output = argv[argv.index("--output") + 1]
                assert not Path(output).is_absolute()
                Path(output).parent.mkdir(parents=True, exist_ok=True)
                Path(output).write_text("{}", encoding="utf-8")
                return {}
            return super().__call__(argv)

    monkeypatch.chdir(tmp_path)
    runner = DownloadRunner()
    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=runner)

    provider.download_file("box_index", tmp_path / "downloads" / "index.json")

    assert (tmp_path / "downloads" / "index.json").exists()


def test_doctor_rejects_missing_feishu_scope(tmp_path: Path) -> None:
    class MissingScopeRunner(FakeRunner):
        def __call__(self, argv: list[str]) -> dict:
            if argv[:3] == ["lark-cli", "auth", "status"]:
                return {
                    "identities": {"user": {"available": True}},
                    "scope": "drive:file:upload",
                }
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


def test_lark_cli_runner_resolves_windows_cmd_shim(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_which(name: str) -> str | None:
        if name == "lark-cli.cmd":
            return r"C:\Users\Administrator\AppData\Roaming\npm\lark-cli.cmd"
        return None

    class Completed:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    def fake_run(argv: list[str], **kwargs) -> Completed:
        calls.append(argv)
        return Completed()

    monkeypatch.setattr(provider_module.shutil, "which", fake_which)
    monkeypatch.setattr(provider_module.subprocess, "run", fake_run)

    result = provider_module._run_lark_cli(["lark-cli", "--version"])

    assert result == {"ok": True}
    assert calls[0][0] == r"C:\Users\Administrator\AppData\Roaming\npm\lark-cli.cmd"


def test_doctor_warns_when_feishu_quota_check_is_unavailable(tmp_path: Path) -> None:
    class QuotaUnavailableRunner(FakeRunner):
        def __call__(self, argv: list[str]) -> dict:
            if argv[:3] == ["lark-cli", "drive", "quota_details"]:
                raise CloudSyncError("quota API unavailable")
            return super().__call__(argv)

    config = CloudSyncConfig(
        provider="feishu",
        db_path=tmp_path / "talent.db",
        feishu_root_folder_token="fld_root",
        encryption_key=keygen(),
    )
    provider = FeishuDriveProvider(config, runner=QuotaUnavailableRunner())

    result = provider.doctor()

    assert result["ok"] is True
    assert result["quota"]["ok"] is False
    assert "quota API unavailable" in result["quota"]["warning"]


def test_cloud_sync_cli_keygen_prints_key(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["keygen"]) == 0
    output = capsys.readouterr().out.strip()
    assert decrypt_bytes(encrypt_bytes(b"x", output), output) == b"x"


def test_cloud_sync_cli_status_for_missing_db(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    config_path = tmp_path / "state.json"
    assert main(
        [
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
        ]
    ) == 0
    assert "missing" in capsys.readouterr().out


def test_cloud_sync_cli_loads_dotenv_defaults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in [
        "TALENT_SYNC_PROVIDER",
        "TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN",
        "TALENT_SYNC_ENCRYPTION_KEY",
    ]:
        monkeypatch.delenv(name, raising=False)
    key = keygen()
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "TALENT_SYNC_PROVIDER=feishu",
                "TALENT_SYNC_FEISHU_ROOT_FOLDER_TOKEN=fld_from_env",
                f"TALENT_SYNC_ENCRYPTION_KEY={key}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    args = build_parser().parse_args(["status"])
    config = _config_from_args(args)

    assert config.provider == "feishu"
    assert config.feishu_root_folder_token == "fld_from_env"
    assert config.encryption_key == key
