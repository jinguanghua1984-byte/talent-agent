import json
import subprocess
from pathlib import Path

import pytest

from scripts.jd_talent_delivery_feishu import (
    _stdout_json,
    _token,
    _without_dry_run,
    build_publish_manifest,
    main,
    publish_output,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_required_files(root: Path) -> None:
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(root / "reports" / "outreach-queue.csv", "name,email\nA,a@example.com\n")


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        joined = " ".join(argv)
        if argv == ["lark-cli", "doctor"]:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true}', "")
        if argv == ["lark-cli", "auth", "status"]:
            return subprocess.CompletedProcess(argv, 0, '{"tokenStatus":"valid"}', "")
        if "wiki +node-create" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +node-create" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"parent_node","obj_token":"parent_doc"}', "")
        if "drive +import" in joined and "--type docx" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "drive +import" in joined and "--type sheet" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "drive +import" in joined and "--type docx" in joined:
            token = "doc_" + str(len(self.calls))
            return subprocess.CompletedProcess(argv, 0, json.dumps({"obj_token": token}), "")
        if "drive +import" in joined and "--type sheet" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"obj_token":"sheet_token"}', "")
        if "wiki +move" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +move" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"moved_node","ready":true}', "")
        return subprocess.CompletedProcess(argv, 1, "", "unexpected command")


class FailingRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        return subprocess.CompletedProcess(argv, 1, "", "simulated failure")


def _safe_output_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-role-2026-05-23"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# 岗位画像\n")
    _write(root / "reports" / "talent-recommendation.md", "# 推荐报告\n")
    _write(root / "reports" / "outreach-queue.csv", "candidate_id,name\n1,A\n")
    return root


def test_manifest_uses_drive_import_and_wiki_move(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )

    assert manifest["schema"] == "jd_talent_delivery_feishu_manifest_v1"
    assert manifest["wiki_space_id"] == "7642607697183001542"
    assert manifest["source_files"] == {
        "jd": "source/jd.md",
        "profile": "profile/role-deep-dive.md",
        "recommendation": "reports/talent-recommendation.md",
        "outreach": "reports/outreach-queue.csv",
    }

    serialized = json.dumps(manifest, ensure_ascii=False)
    for token in ["drive", "+import", "--type", "docx", "sheet", "wiki", "+move"]:
        assert token in serialized
    assert "lark-cli doctor" in serialized
    assert "lark-cli auth status" in serialized
    assert "wiki +node-create" in serialized
    assert "sheets +append --file" not in serialized


def test_manifest_rejects_sensitive_paths(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(root / "reports" / "outreach-queue.csv", "database\nraw/search/unit-1.json\n")

    with pytest.raises(ValueError, match="sensitive marker"):
        build_publish_manifest(root, jd_title="Demo", wiki_space_id="7642607697183001542", dry_run=True)


def test_parent_create_respects_dry_run_flag(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    dry_manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )
    live_manifest = build_publish_manifest(
        root,
        jd_title="Demo JD",
        wiki_space_id="7642607697183001542",
        dry_run=False,
    )

    dry_parent = next(step["argv"] for step in dry_manifest["publish_steps"] if "+node-create" in step["argv"])
    live_parent = next(step["argv"] for step in live_manifest["publish_steps"] if "+node-create" in step["argv"])
    assert "--dry-run" in dry_parent
    assert "--dry-run" not in live_parent


def test_manifest_rejects_sensitive_title_from_final_manifest_check(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)

    with pytest.raises(ValueError, match="sensitive marker"):
        build_publish_manifest(root, jd_title="talent.db", wiki_space_id="7642607697183001542", dry_run=True)


def test_normal_database_content_is_allowed(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\nExperience with vector database systems is preferred.\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(
        root / "reports" / "talent-recommendation.md",
        "# Recommendations\nCandidate has database systems background.\n",
    )
    _write(root / "reports" / "outreach-queue.csv", "name,notes\nA,vector database systems\n")

    manifest = build_publish_manifest(
        root,
        jd_title="Database Platform Engineer",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )

    assert manifest["jd_title"] == "Database Platform Engineer"


def test_main_writes_utf8_sig_manifest_and_creates_parent_dir(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write_required_files(root)
    manifest_out = root / "feishu" / "publish-manifest.json"

    code = main(
        [
            "--output-root",
            str(root),
            "--jd-title",
            "Demo JD",
            "--manifest-out",
            str(manifest_out),
            "--dry-run",
        ]
    )

    assert code == 0
    assert manifest_out.read_bytes().startswith(b"\xef\xbb\xbf")
    stored = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    assert stored["schema"] == "jd_talent_delivery_feishu_manifest_v1"
    assert stored["wiki_space_id"] == "7642607697183001542"


def test_publish_output_runs_preflight_dry_run_then_real_publish(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = FakeRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
    )

    assert result["status"] == "published"
    assert result["parent_node_token"] == "parent_node"
    assert (root / "feishu" / "publish-results.json").exists()
    calls = [" ".join(call) for call in runner.calls]
    assert calls[0] == "lark-cli doctor"
    assert calls[1] == "lark-cli auth status"
    assert any("wiki +node-create" in call and "--dry-run" in call for call in calls)
    assert any("drive +import" in call and "--dry-run" in call for call in calls)
    assert any("wiki +move" in call and "--target-parent-token parent_node" in call for call in calls)


def test_publish_output_raises_when_command_fails(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)

    with pytest.raises(RuntimeError, match="command failed"):
        publish_output(
            output_root=root,
            jd_title="Demo Role",
            wiki_space_id="7642607697183001542",
            runner=FailingRunner(),
        )


def test_without_dry_run_removes_only_trailing_generated_flag() -> None:
    argv = ["lark-cli", "wiki", "+node-create", "--title", "--dry-run", "--dry-run"]

    assert _without_dry_run(argv) == ["lark-cli", "wiki", "+node-create", "--title", "--dry-run"]


def test_without_dry_run_preserves_middle_dry_run_value_when_no_trailing_flag() -> None:
    argv = ["lark-cli", "wiki", "+node-create", "--title", "--dry-run", "--space-id", "space"]

    assert _without_dry_run(argv) == argv
    assert _without_dry_run(argv) is not argv


def test_stdout_json_wraps_non_json_stdout_in_value_error() -> None:
    with pytest.raises(ValueError, match="command stdout is not valid JSON"):
        _stdout_json({"stdout": "not json output that should be summarized"})


def test_stdout_json_rejects_non_object_json() -> None:
    with pytest.raises(ValueError, match="command stdout JSON must be an object"):
        _stdout_json({"stdout": '["not", "object"]'})


def test_token_reads_nested_data_dict() -> None:
    assert _token({"data": {"node_token": "nested"}}, "node_token") == "nested"
