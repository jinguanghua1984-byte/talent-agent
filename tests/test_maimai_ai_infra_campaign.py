from pathlib import Path
import json

import pytest

from scripts.maimai_ai_infra_campaign import (
    append_jsonl,
    append_search_event,
    atomic_write_json,
    ensure_campaign,
    load_completed_pages,
    mark_page_completed,
    page_raw_path,
    read_search_progress,
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


def test_page_raw_atomic_write_marks_completed(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    payload = {"unit_id": "unit-000001", "page": 1, "contacts": [{"id": "u1"}]}

    mark_page_completed(paths, "unit-000001", 1, payload)

    raw = page_raw_path(paths, "unit-000001", 1)
    assert raw.exists()
    assert not raw.with_name(raw.name + ".tmp").exists()
    assert json.loads(raw.read_text(encoding="utf-8-sig"))["contacts"][0]["id"] == "u1"
    progress = read_search_progress(paths)
    assert progress["units"]["unit-000001"]["pages"]["1"]["status"] == "completed"


def test_resume_rebuilds_completed_pages_from_raw_when_progress_missing(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(paths, "unit-000001", 1, {"unit_id": "unit-000001", "page": 1, "contacts": []})
    paths.search_progress.unlink()

    completed = load_completed_pages(paths)

    assert completed == {("unit-000001", 1)}


def test_load_completed_pages_ignores_malformed_raw_content(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    invalid_cases = {
        ("unit-000001", 1): "{not-json",
        ("unit-000002", 2): "[]",
        ("unit-000003", 3): json.dumps({"page": 3, "contacts": []}),
        ("unit-000004", 4): json.dumps({"unit_id": "unit-000004", "contacts": []}),
        ("unit-000005", 5): json.dumps({"unit_id": "unit-000005", "page": 5}),
        ("unit-000006", 6): json.dumps({"unit_id": "unit-000006", "page": 6, "contacts": {}}),
        ("unit-000007", 7): json.dumps({"unit_id": "unit-999999", "page": 7, "contacts": []}),
        ("unit-000008", 8): json.dumps({"unit_id": "unit-000008", "page": 9, "contacts": []}),
    }
    for (unit_id, page), content in invalid_cases.items():
        raw = page_raw_path(paths, unit_id, page)
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(content, encoding="utf-8")
    mark_page_completed(paths, "unit-000009", 9, {"unit_id": "unit-000009", "page": 9, "contacts": []})

    completed = load_completed_pages(paths)

    assert completed == {("unit-000009", 9)}


def test_load_completed_pages_ignores_malformed_raw_names(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    malformed_paths = [
        paths.raw_search_dir / "unit-backup" / "page-001.json",
        paths.raw_search_dir / "unit-abc" / "page-001.json",
        paths.raw_search_dir / "unit-000001" / "page-1.json",
        paths.raw_search_dir / "unit-000001" / "page--1.json",
        paths.raw_search_dir / "unit-000001" / "page-000.json",
    ]
    for raw in malformed_paths:
        raw.parent.mkdir(parents=True, exist_ok=True)
        raw.write_text(
            json.dumps({"unit_id": raw.parent.name, "page": 1, "contacts": []}),
            encoding="utf-8",
        )
    mark_page_completed(paths, "unit-000002", 2, {"unit_id": "unit-000002", "page": 2, "contacts": []})

    completed = load_completed_pages(paths)

    assert completed == {("unit-000002", 2)}


def test_search_events_are_append_only_jsonl(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    append_search_event(paths, {"event": "page_started", "unit_id": "unit-000001", "page": 1})
    append_search_event(paths, {"event": "page_completed", "unit_id": "unit-000001", "page": 1})

    lines = paths.search_events.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "page_started"


def test_append_search_event_caller_cannot_override_generated_ts(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    append_search_event(paths, {"event": "page_started", "ts": "caller-ts"})

    event = json.loads(paths.search_events.read_text(encoding="utf-8").splitlines()[0])
    assert event["ts"] != "caller-ts"
    assert event["event"] == "page_started"
