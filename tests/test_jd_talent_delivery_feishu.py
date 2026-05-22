import json
from pathlib import Path

import pytest

from scripts.jd_talent_delivery_feishu import build_publish_manifest, main


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_required_files(root: Path) -> None:
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# Role profile\n")
    _write(root / "reports" / "talent-recommendation.md", "# Recommendations\n")
    _write(root / "reports" / "outreach-queue.csv", "name,email\nA,a@example.com\n")


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
