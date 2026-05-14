from pathlib import Path

import pytest

from scripts.maimai_ai_infra_campaign import (
    append_jsonl,
    atomic_write_json,
    ensure_campaign,
)


def test_campaign_paths_create_expected_layout(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"
    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")

    assert paths.root == root
    assert paths.db == root / "talent.db"
    assert paths.raw_search_dir == root / "raw" / "search"
    assert paths.contacts_dir == root / "raw" / "contacts"
    assert paths.state_dir == root / "state"
    assert paths.reports_dir == root / "reports"
    assert paths.review_dir == root / "review"
    assert paths.manifest.exists()


def test_atomic_write_json_writes_utf8_sig_json_and_removes_temp_files(tmp_path: Path):
    target = tmp_path / "nested" / "state.json"

    atomic_write_json(target, {"name": "张三", "rank": 1})

    assert target.read_text(encoding="utf-8-sig") == '{\n  "name": "张三",\n  "rank": 1\n}'
    assert list(target.parent.glob("state.json.*.tmp")) == []


def test_atomic_write_json_does_not_reuse_fixed_temp_path(tmp_path: Path):
    target = tmp_path / "state.json"
    fixed_temp = tmp_path / "state.json.tmp"
    fixed_temp.write_text("do not touch", encoding="utf-8")

    atomic_write_json(target, {"ok": True})

    assert target.read_text(encoding="utf-8-sig") == '{\n  "ok": true\n}'
    assert fixed_temp.read_text(encoding="utf-8") == "do not touch"


def test_append_jsonl_appends_sorted_json_objects(tmp_path: Path):
    target = tmp_path / "events" / "items.jsonl"

    append_jsonl(target, {"b": 2, "a": "甲"})
    append_jsonl(target, {"event": "done"})

    assert target.read_text(encoding="utf-8").splitlines() == [
        '{"a": "甲", "b": 2}',
        '{"event": "done"}',
    ]


def test_ensure_campaign_writes_manifest_and_keeps_existing_manifest(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"

    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")
    first_manifest = paths.manifest.read_text(encoding="utf-8-sig")
    ensure_campaign(root, campaign_id="ai-infra-v2-smoke")

    assert paths.manifest.read_text(encoding="utf-8-sig") == first_manifest
    assert '"campaign_id": "ai-infra-v2-smoke"' in first_manifest
    assert '"schema": "maimai_ai_infra_v2_campaign"' in first_manifest


def test_ensure_campaign_rejects_mismatched_manifest_campaign_id(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"
    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")
    atomic_write_json(
        paths.manifest,
        {
            "campaign_id": "other-campaign",
            "created_at": "2026-05-14T00:00:00",
            "schema": "maimai_ai_infra_v2_campaign",
        },
    )

    with pytest.raises(ValueError, match="campaign_id"):
        ensure_campaign(root, campaign_id="ai-infra-v2-smoke")


def test_ensure_campaign_rejects_mismatched_manifest_schema(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"
    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")
    atomic_write_json(
        paths.manifest,
        {
            "campaign_id": "ai-infra-v2-smoke",
            "created_at": "2026-05-14T00:00:00",
            "schema": "old_schema",
        },
    )

    with pytest.raises(ValueError, match="schema"):
        ensure_campaign(root, campaign_id="ai-infra-v2-smoke")


def test_gitignore_excludes_campaign_runtime_data():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/campaigns/" in text
