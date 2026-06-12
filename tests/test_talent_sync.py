import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path

import pytest

from scripts.talent_db import TalentDB
from scripts.talent_sync import (
    _build_import_plan,
    export_bundle,
    import_bundle,
    main as sync_main,
    plan_import,
    verify_bundle,
)
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT, canonical_json, record_hash


def _rewrite_bundle_jsonl(
    bundle_path: Path,
    target_path: Path,
    relative_path: str,
    mutate,
) -> None:
    with zipfile.ZipFile(bundle_path) as bundle:
        payloads = {
            name: bundle.read(name)
            for name in bundle.namelist()
            if name != "checksums.sha256"
        }

    rows = [
        json.loads(line)
        for line in payloads[relative_path].decode("utf-8").splitlines()
        if line
    ]
    payloads[relative_path] = (
        "".join(f"{canonical_json(row)}\n" for row in mutate(rows)).encode("utf-8")
    )
    checksum_targets = sorted(payloads)
    payloads["checksums.sha256"] = (
        "".join(
            f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}\n"
            for name in checksum_targets
        ).encode("utf-8")
    )

    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in sorted(payloads):
            bundle.writestr(name, payloads[name])


def _read_bundle_jsonl(bundle_path: Path, relative_path: str) -> list[dict]:
    with zipfile.ZipFile(bundle_path) as bundle:
        payload = bundle.read(relative_path).decode("utf-8")
    if not payload.strip():
        return []
    return [json.loads(line) for line in payload.splitlines()]


def _candidate_sync_updated_at(db_path: Path, candidate_id: int) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT sync_updated_at FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return str(row[0])


def _reset_candidate_sync_updated_at(
    db: TalentDB,
    candidate_id: int,
    value: str = "2000-01-01 00:00:00",
) -> None:
    db._conn.execute(
        "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
        (value, candidate_id),
    )
    db._conn.commit()


def test_candidate_update_refreshes_sync_updated_at(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        _reset_candidate_sync_updated_at(db, candidate_id)

        db.update_candidate(candidate_id, {"city": "Shanghai"})
    finally:
        db.close()

    assert _candidate_sync_updated_at(db_path, candidate_id) > "2000-01-01 00:00:00"


def test_candidate_child_writes_refresh_parent_sync_updated_at(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "source.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        source_profile_id = db.get_sources(candidate_id)[0].id

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss",
                "source_candidate_key": "boss-1",
                "target_platform": "maimai",
                "target_platform_id": "maimai-1",
                "target_profile_url": "https://maimai.cn/profile/detail?dstu=maimai-1",
                "query_text": "Alice Acme",
                "query_level": "person",
                "confidence": 0.95,
                "score_breakdown": {"name": 0.98},
                "match_status": "confirmed",
                "decision_reason": "same person",
            }
        )
        after_identity = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_identity > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.record_field_value(
            {
                "candidate_id": candidate_id,
                "field_name": "current_title",
                "platform": "maimai",
                "source_profile_id": source_profile_id,
                "field_value": {"value": "AI Engineer"},
                "confidence": 0.9,
                "merge_decision": "keep_primary",
            }
        )
        after_field = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_field > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice Followup",
                "markdown_path": "wechat/alice.md",
                "message_count": 3,
            },
        )
        after_wechat = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_wechat > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.save_match_score(
            candidate_id,
            "jd-1",
            "final",
            88,
            {"skill": 90},
            "strong match",
        )
        after_match = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_match > "2000-01-01 00:00:00"
    finally:
        db.close()


def test_canonical_json_is_order_stable():
    left = {"b": 2, "a": [{"y": 1, "x": 2}]}
    right = {"a": [{"x": 2, "y": 1}], "b": 2}

    assert canonical_json(left) == canonical_json(right)
    assert record_hash(left) == record_hash(right)


def test_canonical_json_rejects_non_standard_float():
    with pytest.raises(ValueError):
        canonical_json(float("nan"))


def test_export_full_bundle_contains_manifest_and_core_rows(tmp_path: Path):
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
                "work_experience": [{"company": "Acme"}],
            },
            platform="maimai",
        )
        db.save_match_score(candidate_id, "jd-1", "final", 88, {"skill": 90}, "good")
    finally:
        db.close()

    summary = export_bundle(db_path, bundle_path, mode="full")

    assert summary["tables"]["candidates"] == 1
    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        checksums = bundle.read("checksums.sha256").decode("utf-8").splitlines()
        assert "manifest.json" in names
        assert "checksums.sha256" in names
        assert "data/candidates.jsonl" in names
        assert "data/candidate_details.jsonl" in names
        assert "data/candidate_identity_matches.jsonl" in names
        assert "data/candidate_field_values.jsonl" in names
        assert "data/tombstones.jsonl" in names
        listed_paths = {line.split("  ", 1)[1] for line in checksums}
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        manifest_bytes = bundle.read("manifest.json")
        candidates_bytes = bundle.read("data/candidates.jsonl")
        candidate = json.loads(
            candidates_bytes.decode("utf-8").splitlines()[0]
        )

    assert manifest["bundle_schema_version"] == 1
    assert manifest["attachments"]["wechat_timelines"] is False
    assert candidate["sync_id"].startswith("candidate:")
    assert "id" not in candidate
    assert len(checksums) == len(names) - 1
    assert {
        "manifest.json",
        "data/candidates.jsonl",
        "data/candidate_details.jsonl",
        "data/source_profiles.jsonl",
        "data/candidate_identity_matches.jsonl",
        "data/candidate_field_values.jsonl",
        "data/tombstones.jsonl",
    }.issubset(listed_paths)
    assert any(line.endswith("  manifest.json") for line in checksums)
    assert any(line.endswith("  data/candidates.jsonl") for line in checksums)
    assert any(
        line.startswith(hashlib.sha256(manifest_bytes).hexdigest())
        and line.endswith("  manifest.json")
        for line in checksums
    )
    assert any(
        line.startswith(hashlib.sha256(candidates_bytes).hexdigest())
        and line.endswith("  data/candidates.jsonl")
        for line in checksums
    )


def test_export_incremental_bundle_contains_changed_candidate_closure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "incremental.zip"
    db = TalentDB(db_path)
    try:
        old_candidate_id = db.ingest(
            {
                "name": "Old Alice",
                "current_company": "Old Co",
                "platform_id": "maimai-old",
                "work_experience": [{"company": "Old Co"}],
            },
            platform="maimai",
        )
        changed_candidate_id = db.ingest(
            {
                "name": "Changed Bob",
                "current_company": "New Co",
                "platform_id": "maimai-new",
                "work_experience": [{"company": "New Co"}],
            },
            platform="maimai",
        )
        db.save_match_score(
            changed_candidate_id,
            "jd-1",
            "final",
            91,
            {"skill": 92},
            "strong",
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", old_candidate_id),
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2030-01-01 00:00:00", changed_candidate_id),
        )
        db._conn.commit()
    finally:
        db.close()

    summary = export_bundle(
        db_path,
        bundle_path,
        mode="incremental",
        since="2029-01-01T00:00:00Z",
    )

    assert summary["mode"] == "incremental"
    assert summary["tables"]["candidates"] == 1
    candidates = _read_bundle_jsonl(bundle_path, "data/candidates.jsonl")
    details = _read_bundle_jsonl(bundle_path, "data/candidate_details.jsonl")
    sources = _read_bundle_jsonl(bundle_path, "data/source_profiles.jsonl")
    scores = _read_bundle_jsonl(bundle_path, "data/match_scores.jsonl")
    assert [row["name"] for row in candidates] == ["Changed Bob"]
    assert len(details) == 1
    assert len(sources) == 1
    assert len(scores) == 1
    assert scores[0]["candidate_sync_id"] == candidates[0]["sync_id"]


def test_export_incremental_bundle_includes_recent_tombstones(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "incremental-delete.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Deleted Alice",
                "current_company": "Acme",
                "platform_id": "maimai-delete",
            },
            platform="maimai",
        )
        db.delete_candidate(candidate_id)
    finally:
        db.close()

    summary = export_bundle(
        db_path,
        bundle_path,
        mode="incremental",
        since="2000-01-01T00:00:00Z",
    )

    assert summary["tables"]["candidates"] == 0
    assert summary["tables"]["tombstones"] == 1
    tombstones = _read_bundle_jsonl(bundle_path, "data/tombstones.jsonl")
    assert tombstones[0]["entity_type"] == "candidate"
    assert tombstones[0]["reason"] == "local_delete"


def test_sync_bundle_round_trips_cross_channel_audit_tables(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {
                "name": "Cross Channel",
                "current_company": "BOSS Co",
                "current_title": "AI PM",
                "platform_id": "boss-1",
            },
            platform="boss",
        )
        source_profile_id = source.get_sources(source_candidate_id)[0].id
        source.record_identity_match(
            {
                "candidate_id": source_candidate_id,
                "source_platform": "boss",
                "source_candidate_key": "boss-1",
                "target_platform": "maimai",
                "target_platform_id": "maimai-9",
                "target_profile_url": "https://maimai.cn/profile/detail?dstu=maimai-9",
                "query_text": "Cross Channel AI PM",
                "query_level": "person",
                "confidence": 0.93,
                "score_breakdown": {"name": 0.97, "company": 0.9},
                "match_status": "confirmed",
                "decision_reason": "same person",
                "confirmed_by": "hunter-a",
                "confirmed_at": "2026-06-04T10:00:00+08:00",
            }
        )
        source.record_field_value(
            {
                "candidate_id": source_candidate_id,
                "field_name": "current_title",
                "platform": "maimai",
                "source_profile_id": source_profile_id,
                "field_value": {"value": "AI Product Lead", "evidence": ["headline"]},
                "confidence": 0.88,
                "merge_decision": "keep_primary",
                "decision_reason": "BOSS profile is fresher",
            }
        )
    finally:
        source.close()

    summary = export_bundle(source_db, bundle_path, mode="full")
    dry_run = import_bundle(bundle_path, target_db, apply=False)
    apply_result = import_bundle(
        bundle_path,
        target_db,
        apply=True,
        confirm=CONFIRM_SYNC_TEXT,
    )

    target = TalentDB(target_db)
    try:
        identity_matches = target.identity_matches()
        field_values = target.field_values()
        target_sources = target.get_sources(field_values[0].candidate_id)
    finally:
        target.close()

    assert summary["tables"]["candidate_identity_matches"] == 1
    assert summary["tables"]["candidate_field_values"] == 1
    assert dry_run["tables"]["candidate_identity_matches"] == 1
    assert dry_run["tables"]["candidate_field_values"] == 1
    assert dry_run["created"]["candidate_identity_matches"] == 1
    assert dry_run["created"]["candidate_field_values"] == 1
    assert apply_result["created"]["candidate_identity_matches"] == 1
    assert apply_result["created"]["candidate_field_values"] == 1
    assert len(identity_matches) == 1
    assert identity_matches[0].source_platform == "boss"
    assert identity_matches[0].target_platform == "maimai"
    assert identity_matches[0].score_breakdown == {"name": 0.97, "company": 0.9}
    assert len(field_values) == 1
    assert field_values[0].field_name == "current_title"
    assert field_values[0].field_value == {
        "value": "AI Product Lead",
        "evidence": ["headline"],
    }
    assert isinstance(field_values[0].source_profile_id, int)
    assert target_sources[0].id == field_values[0].source_profile_id
    assert identity_matches[0].candidate_id == field_values[0].candidate_id


def test_import_field_value_does_not_trust_raw_source_profile_id(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    tampered_bundle = tmp_path / "tampered.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {
                "name": "Raw Source Id",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "source-boss",
            },
            platform="boss",
        )
        source_profile_id = source.get_sources(source_candidate_id)[0].id
        source.record_field_value(
            {
                "candidate_id": source_candidate_id,
                "field_name": "current_title",
                "platform": "maimai",
                "source_profile_id": source_profile_id,
                "field_value": "AI Product Lead",
                "confidence": 0.8,
            }
        )
    finally:
        source.close()

    target = TalentDB(target_db)
    try:
        target_candidate_id = target.ingest(
            {
                "name": "Raw Source Id",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "target-manual",
            },
            platform="manual",
        )
        wrong_target_source_id = target.get_sources(target_candidate_id)[0].id
    finally:
        target.close()

    export_bundle(source_db, bundle_path, mode="full")

    def remove_source_profile_sync_id(rows: list[dict]) -> list[dict]:
        for row in rows:
            row.pop("source_profile_sync_id", None)
        return rows

    _rewrite_bundle_jsonl(
        bundle_path,
        tampered_bundle,
        "data/candidate_field_values.jsonl",
        remove_source_profile_sync_id,
    )
    result = import_bundle(
        tampered_bundle,
        target_db,
        apply=True,
        confirm=CONFIRM_SYNC_TEXT,
    )

    target = TalentDB(target_db)
    try:
        field_values = target.field_values()
    finally:
        target.close()

    assert result["created"]["candidate_field_values"] == 1
    assert wrong_target_source_id == source_profile_id
    assert field_values[0].source_profile_id is None


def test_import_plan_counts_source_profile_stable_key_merge(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source.ingest(
            {
                "name": "Source Stable Key",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "shared-source",
                "profile_url": "https://example.test/source",
            },
            platform="maimai",
        )
    finally:
        source.close()

    target = TalentDB(target_db)
    try:
        target.ingest(
            {
                "name": "Source Stable Key",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "shared-source",
                "profile_url": "https://example.test/target",
            },
            platform="maimai",
        )
    finally:
        target.close()

    export_bundle(source_db, bundle_path, mode="full")
    dry_run = import_bundle(bundle_path, target_db, apply=False)
    apply_result = import_bundle(
        bundle_path,
        target_db,
        apply=True,
        confirm=CONFIRM_SYNC_TEXT,
    )

    assert dry_run["created"]["source_profiles"] == 0
    assert dry_run["merged"]["source_profiles"] == 1
    assert apply_result["created"]["source_profiles"] == 0
    assert apply_result["merged"]["source_profiles"] == 1


def test_import_rejects_invalid_identity_match_score_breakdown(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    tampered_bundle = tmp_path / "tampered.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {"name": "Invalid Score Breakdown", "platform_id": "boss-invalid"},
            platform="boss",
        )
        source.record_identity_match(
            {
                "candidate_id": source_candidate_id,
                "source_platform": "boss",
                "source_candidate_key": "boss-invalid",
                "target_platform": "maimai",
                "query_text": "Invalid Score Breakdown",
                "query_level": "person",
                "match_status": "rejected",
                "score_breakdown": {"name": 0.4},
            }
        )
    finally:
        source.close()

    export_bundle(source_db, bundle_path, mode="full")

    def break_score_shape(rows: list[dict]) -> list[dict]:
        for row in rows:
            row["score_breakdown"] = ["invalid"]
        return rows

    _rewrite_bundle_jsonl(
        bundle_path,
        tampered_bundle,
        "data/candidate_identity_matches.jsonl",
        break_score_shape,
    )

    with pytest.raises(ValueError, match="score_breakdown"):
        import_bundle(tampered_bundle, target_db, apply=True, confirm=CONFIRM_SYNC_TEXT)


def test_import_bundle_handles_unicode_line_separator_inside_json_string(
    tmp_path: Path,
):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(source_db)
    try:
        db.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "work_experience": [
                    {
                        "company": "Acme",
                        "description": "first line\\n\u2028second line",
                    }
                ],
            },
            platform="maimai",
        )
    finally:
        db.close()
    export_bundle(source_db, bundle_path, mode="full")
    with zipfile.ZipFile(bundle_path) as bundle:
        detail_payload = bundle.read("data/candidate_details.jsonl").decode("utf-8")

    result = import_bundle(bundle_path, target_db, apply=False)

    assert "\u2028" not in detail_payload
    assert "\\u2028" in detail_payload
    assert result["created"]["candidates"] == 1
    assert not target_db.exists()


def test_export_can_include_wechat_timeline_attachments(tmp_path: Path):
    db_path = tmp_path / "source.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    markdown = timeline_dir / "1-Alice-20260513000000.md"
    markdown.write_text("## 2026-05-13 10:00:00 Alice\nhello\n", encoding="utf-8")

    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice微信",
                "markdown_path": str(markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"
    export_bundle(db_path, bundle_path, mode="full", include_wechat_files=True)

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        timeline_rows = [
            json.loads(line)
            for line in bundle.read("data/candidate_wechat_timelines.jsonl")
            .decode("utf-8")
            .splitlines()
            if line
        ]
        checksums = bundle.read("checksums.sha256").decode("utf-8").splitlines()
        attachment_names = [
            name for name in names if name.startswith("attachments/wechat-timelines/")
        ]

    assert manifest["attachments"]["wechat_timelines"] is True
    assert timeline_rows[0]["markdown_path"] == str(markdown)
    assert attachment_names == ["attachments/wechat-timelines/1-Alice-20260513000000.md"]
    assert all("/" not in Path(name).name for name in attachment_names)
    assert any(
        line.endswith("  attachments/wechat-timelines/1-Alice-20260513000000.md")
        for line in checksums
    )


def test_sync_cli_export_can_include_wechat_timeline_attachments(tmp_path: Path):
    db_path = tmp_path / "source.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    markdown = timeline_dir / "1-Alice-20260513000000.md"
    markdown.write_text("## 2026-05-13 10:00:00 Alice\nhello\n", encoding="utf-8")

    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice微信",
                "markdown_path": str(markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"

    assert sync_main([
        "export",
        "--db",
        str(db_path),
        "--out",
        str(bundle_path),
        "--include-wechat-files",
    ]) == 0

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))

    assert manifest["attachments"]["wechat_timelines"] is True
    assert "attachments/wechat-timelines/1-Alice-20260513000000.md" in names


def test_export_wechat_attachments_skips_paths_outside_db_archive_dir(tmp_path: Path):
    db_path = tmp_path / "source.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    legal_markdown = timeline_dir / "legal.md"
    legal_markdown.write_text("legal archive\n", encoding="utf-8")
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    outside_markdown = outside_dir / "outside.md"
    outside_markdown.write_text("outside archive\n", encoding="utf-8")

    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice",
                "markdown_path": str(legal_markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice outside",
                "markdown_path": str(outside_markdown),
                "start_time": "2026-05-14",
                "end_time": "2026-05-14",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"
    export_bundle(db_path, bundle_path, mode="full", include_wechat_files=True)

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())

    assert "attachments/wechat-timelines/legal.md" in names
    assert "attachments/wechat-timelines/outside.md" not in names


def test_export_wechat_attachments_from_default_data_db_layout(tmp_path: Path):
    db_path = tmp_path / "data" / "talent.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    legal_markdown = timeline_dir / "legal.md"
    legal_markdown.write_text("legal archive\n", encoding="utf-8")

    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice",
                "markdown_path": str(legal_markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"
    export_bundle(db_path, bundle_path, mode="full", include_wechat_files=True)

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())

    assert "attachments/wechat-timelines/legal.md" in names


def test_import_wechat_attachment_is_idempotent_for_duplicate_bundle(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target" / "target.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    markdown = timeline_dir / "1-Alice-20260513000000.md"
    markdown.write_text("## 2026-05-13 10:00:00 Alice\nhello\n", encoding="utf-8")

    db = TalentDB(source_db)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice微信",
                "markdown_path": str(markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"
    export_bundle(source_db, bundle_path, mode="full", include_wechat_files=True)

    first = import_bundle(
        bundle_path,
        target_db,
        apply=True,
        confirm=CONFIRM_SYNC_TEXT,
    )
    db = TalentDB(target_db)
    try:
        row = db._conn.execute(
            """
            SELECT markdown_path
            FROM candidate_wechat_timelines
            ORDER BY id
            LIMIT 1
            """
        ).fetchone()
    finally:
        db.close()

    restored_path = Path(row["markdown_path"])
    assert first["created"]["candidate_wechat_timelines"] == 1
    assert restored_path.parent == target_db.parent / "data" / "wechat-timelines"
    assert restored_path.read_text(encoding="utf-8") == markdown.read_text(encoding="utf-8")

    restored_path.unlink()
    second = import_bundle(
        bundle_path,
        target_db,
        apply=True,
        confirm=CONFIRM_SYNC_TEXT,
    )

    assert second["created"]["candidate_wechat_timelines"] == 0
    assert not restored_path.exists()


def test_import_full_bundle_to_empty_db_remaps_local_ids(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    db = TalentDB(source_db)
    try:
        source_candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
                "work_experience": [{"company": "Acme"}],
            },
            platform="maimai",
        )
        source_sync_id = db._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (source_candidate_id,),
        ).fetchone()["sync_id"]
    finally:
        db.close()

    export_bundle(source_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        assert result["created"]["candidates"] == 1
        assert db.count() == 1
        target_candidate = db.fulltext_search("Alice")[0]
        target_sync_id = db._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (target_candidate.id,),
        ).fetchone()["sync_id"]
        detail = db.get_detail(target_candidate.id)
        source = db.get_sources(target_candidate.id)[0]
    finally:
        db.close()

    assert target_candidate.id != source_candidate_id or str(source_db) != str(target_db)
    assert target_sync_id == source_sync_id
    assert detail is not None
    assert source.platform_id == "maimai-1"


def test_import_merge_preserves_local_detail_and_records_alias(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "Engineer",
                "city": "Beijing",
                "education": "BS",
                "platform_id": "remote-1",
                "work_experience": [{"company": "Acme", "title": "Junior"}],
                "summary": "remote old summary",
                "raw_data": {"remote": True},
            },
            platform="maimai",
        )
        remote_sync_id = source._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (source_candidate_id,),
        ).fetchone()["sync_id"]
    finally:
        source.close()

    target = TalentDB(target_db)
    try:
        target_candidate_id = target.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "Engineer",
                "city": "Beijing",
                "education": "BS",
                "platform_id": "local-1",
                "work_experience": [{"company": "Acme", "title": "Senior"}],
                "summary": "local rich summary",
                "raw_data": {"local": True},
            },
            platform="manual",
        )
        local_sync_id = target._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (target_candidate_id,),
        ).fetchone()["sync_id"]
    finally:
        target.close()

    export_bundle(source_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    target = TalentDB(target_db)
    try:
        detail = target.get_detail(target_candidate_id)
        alias = target._conn.execute(
            """
            SELECT local_sync_id
            FROM sync_entity_aliases
            WHERE entity_type = 'candidate'
              AND remote_sync_id = ?
            """,
            (remote_sync_id,),
        ).fetchone()
    finally:
        target.close()

    assert result["merged"]["candidates"] == 1
    assert alias is not None
    assert alias["local_sync_id"] == local_sync_id
    assert detail is not None
    assert detail.summary == "local rich summary"
    assert detail.raw_data == {"local": True, "remote": True}
    assert {"company": "Acme", "title": "Senior"} in detail.work_experience
    assert {"company": "Acme", "title": "Junior"} in detail.work_experience


def test_import_candidate_detail_merges_raw_data_and_records_conflicts(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "summary": "local summary",
                "work_experience": [{"company": "Acme", "title": "Senior"}],
                "raw_data": {
                    "maimai": {"same": 1, "title": "local"},
                    "local_only": {"value": "keep"},
                },
            },
            platform="maimai",
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "summary": "remote summary",
                "work_experience": [{"company": "Acme", "title": "Principal"}],
                "raw_data": {
                    "maimai": {"same": 1, "title": "remote"},
                    "remote_only": {"value": "add"},
                },
            },
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        detail = left.get_detail(left_id)
        conflicts = left._conn.execute(
            """
            SELECT entity_type, field_name, local_value, remote_value
            FROM sync_conflicts
            WHERE entity_type = 'candidate_detail'
            ORDER BY field_name
            """
        ).fetchall()
    finally:
        left.close()

    assert detail is not None
    assert detail.summary == "local summary"
    assert detail.raw_data == {
        "maimai": {"same": 1, "title": "local"},
        "local_only": {"value": "keep"},
        "remote_only": {"value": "add"},
    }
    assert {"company": "Acme", "title": "Senior"} in detail.work_experience
    assert {"company": "Acme", "title": "Principal"} in detail.work_experience
    assert result["conflicts"]["candidate_details"] == 2
    assert {row["field_name"] for row in conflicts} == {
        "candidate_detail.raw_data.maimai",
        "candidate_detail.summary",
    }
    summary_conflict = next(
        row for row in conflicts if row["field_name"] == "candidate_detail.summary"
    )
    assert json.loads(summary_conflict["local_value"]) == "local summary"
    assert json.loads(summary_conflict["remote_value"]) == "remote summary"


def test_import_candidate_detail_semantically_merges_maimai_capture_noise(
    tmp_path: Path,
):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"
    local_projects = [{"project_name": "Local Project", "description": "richer"}]

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "raw_data": {
                    "maimai_detail_capture": {
                        "capture_file": "local.json",
                        "mode": "direct_page_fetch",
                        "payload": {
                            "detail_url": "https://maimai.cn/profile/detail?trackable_token=local",
                            "trackable_token": "local-token",
                            "second": "local-second",
                        },
                        "endpoints": {
                            "basic": {
                                "active_state": "今日活跃",
                                "age": 30,
                                "resume": {"tags": ["多模态", "AI产品"]},
                                "viewed": True,
                                "job_preferences": {
                                    "positions": ["AI产品经理"],
                                    "province_cities": ["深圳"],
                                    "salary": "30k-50k/月",
                                },
                                "exp": [
                                    {
                                        "company": "Acme",
                                        "position": "AI产品经理",
                                        "friends": {"mmids": [2, 1], "total": 2},
                                        "hover": {"stage": "已上市"},
                                        "id": 100,
                                        "fid": 200,
                                        "file_md5": "local-md5",
                                        "crtime": "2026-05-22",
                                        "uptime": "2026-05-22",
                                    }
                                ],
                                "user_project": local_projects,
                            },
                            "contact_btn": {
                                "contentType": "application/json",
                                "data": {
                                    "code": 0,
                                    "contact_btn_types": {"maimai-1": 6},
                                },
                                "httpStatus": 200,
                                "name": "contact_btn",
                                "ok": True,
                                "rawLength": 42,
                                "rawPreview": "{}",
                            },
                        },
                        "raw_entry": {
                            "index": 3,
                            "source_contact": {
                                "best_campaign_id": "campaign-a",
                                "grade": "B",
                                "low_confidence_only": False,
                                "priority": 2,
                                "score": 81,
                                "source_grade_counts": {"B": 1},
                                "source_role_count": 1,
                            },
                            "started_at": "2026-05-22T10:00:00",
                            "finished_at": "2026-05-22T10:00:01",
                        },
                    }
                },
            },
            platform="maimai",
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "raw_data": {
                    "maimai_detail_capture": {
                        "capture_file": "remote.json",
                        "mode": "safe",
                        "payload": {
                            "detail_url": "https://maimai.cn/profile/detail?trackable_token=remote",
                            "trackable_token": "remote-token",
                            "second": "remote-second",
                        },
                        "endpoints": {
                            "basic": {
                                "active_state": "近1周活跃",
                                "age": 31,
                                "resume": {"tags": ["AI产品", "多模态"]},
                                "viewed": False,
                                "job_preferences": {
                                    "id": "maimai-1",
                                        "job_preference": {
                                            "positions": "AI产品经理",
                                            "province_cities": "广东深圳",
                                            "salary": "30k-50k/月",
                                        },
                                        "resume_badges": [],
                                    },
                                    "exp": [
                                        {
                                            "company": "Acme",
                                            "position": "AI产品经理",
                                            "friends": {"mmids": [1, 2], "total": 1},
                                            "id": 101,
                                            "fid": 201,
                                            "file_md5": "remote-md5",
                                            "crtime": "2026-05-25",
                                            "uptime": "2026-05-25",
                                        }
                                    ],
                                    "user_project": {"total": 0},
                                },
                            "contact_btn": {
                                "authFailure": False,
                                "data": {
                                    "code": 0,
                                    "contact_btn_types": {"maimai-1": 6},
                                },
                                "error": None,
                                "httpStatus": 200,
                                "name": "contact_btn",
                                "ok": True,
                                "raw": "{}",
                            },
                        },
                        "raw_entry": {
                            "source_contact": {
                                "source_contact": {
                                    "platform": "maimai",
                                    "platform_id": "maimai-1",
                                }
                            },
                            "started_at": "2026-05-25T10:00:00Z",
                            "finished_at": "2026-05-25T10:00:01Z",
                        },
                    }
                },
            },
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        detail = left.get_detail(left_id)
        conflict_count = left._conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE entity_type = 'candidate_detail'"
        ).fetchone()[0]
    finally:
        left.close()

    assert result["conflicts"]["candidate_details"] == 0
    assert conflict_count == 0
    assert detail is not None
    capture = detail.raw_data["maimai_detail_capture"]
    assert capture["endpoints"]["basic"]["user_project"] == local_projects


def test_import_candidate_detail_keeps_maimai_capture_conflict_for_real_change(
    tmp_path: Path,
):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "raw_data": {
                    "maimai_detail_capture": {
                        "payload": {"current_title": "AI产品经理"}
                    }
                },
            },
            platform="maimai",
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {
                "name": "Alice",
                "platform_id": "maimai-1",
                "raw_data": {
                    "maimai_detail_capture": {
                        "payload": {"current_title": "算法工程师"}
                    }
                },
            },
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        conflicts = left._conn.execute(
            """
            SELECT field_name
            FROM sync_conflicts
            WHERE entity_type = 'candidate_detail'
            """
        ).fetchall()
    finally:
        left.close()

    assert result["conflicts"]["candidate_details"] == 1
    assert [row["field_name"] for row in conflicts] == [
        "candidate_detail.raw_data.maimai_detail_capture"
    ]


def test_import_uses_source_key_to_merge_independent_candidates(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "current_company": "Acme", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left_sync_id = left._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (left_id,),
        ).fetchone()["sync_id"]
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right_id = right.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        right_sync_id = right._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (right_id,),
        ).fetchone()["sync_id"]
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm="确认同步人才库")

    left = TalentDB(left_db)
    try:
        assert left.count() == 1
        candidate = left.get(left_id)
        stored_sync_id = left._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (left_id,),
        ).fetchone()["sync_id"]
        alias = left._conn.execute(
            """
            SELECT local_sync_id, source_node_id
            FROM sync_entity_aliases
            WHERE entity_type = 'candidate' AND remote_sync_id = ?
            """,
            (right_sync_id,),
        ).fetchone()
    finally:
        left.close()

    assert result["merged"]["candidates"] == 1
    assert stored_sync_id == left_sync_id
    assert candidate.current_title == "AI PM"
    assert alias is not None
    assert alias["local_sync_id"] == left_sync_id
    assert alias["source_node_id"]


def test_import_records_conflict_for_same_field_different_values(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left.ingest(
            {"name": "Alice", "city": "Shanghai", "platform_id": "maimai-1"},
            platform="maimai",
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {"name": "Alice", "city": "Beijing", "platform_id": "maimai-1"},
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm="确认同步人才库")

    left = TalentDB(left_db)
    try:
        candidate_hit = left.fulltext_search("Alice")[0]
        candidate = left.get(candidate_hit.id)
        conflict = left._conn.execute(
            """
            SELECT field_name, local_value, remote_value
            FROM sync_conflicts
            WHERE entity_type = 'candidate'
            """,
        ).fetchone()
    finally:
        left.close()

    assert candidate is not None
    assert candidate.city == "Shanghai"
    assert result["conflicts"]["candidates"] == 1
    assert conflict["field_name"] == "city"
    assert json.loads(conflict["local_value"]) == "Shanghai"
    assert json.loads(conflict["remote_value"]) == "Beijing"


def test_import_merge_preserves_local_updated_at_when_filling_field(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"
    original_updated_at = "2001-02-03 04:05:06"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "city": "Shanghai", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left._conn.execute(
            "UPDATE candidates SET updated_at = ? WHERE id = ?",
            (original_updated_at, left_id),
        )
        left._conn.commit()
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {
                "name": "Alice",
                "city": "Shanghai",
                "current_title": "AI PM",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm="确认同步人才库")

    left = TalentDB(left_db)
    try:
        candidate = left.get(left_id)
        updated_at = left._conn.execute(
            "SELECT updated_at FROM candidates WHERE id = ?",
            (left_id,),
        ).fetchone()["updated_at"]
    finally:
        left.close()

    assert result["merged"]["candidates"] == 1
    assert candidate is not None
    assert candidate.current_title == "AI PM"
    assert updated_at == original_updated_at


def test_import_null_platform_id_source_profile_is_idempotent(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source.ingest(
            {
                "name": "Bob",
                "profile_url": "https://example.test/bob",
            },
            platform="manual",
        )
        source_sync_id = source._conn.execute(
            "SELECT sync_id FROM source_profiles"
        ).fetchone()["sync_id"]
    finally:
        source.close()

    export_bundle(source_db, bundle_path, mode="full")
    import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")
    second = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    target = TalentDB(target_db)
    try:
        rows = target._conn.execute(
            """
            SELECT candidate_id, platform, platform_id, profile_url, sync_id
            FROM source_profiles
            ORDER BY id
            """
        ).fetchall()
    finally:
        target.close()

    assert second["skipped"]["already_imported"] == 1
    assert len(rows) == 1
    assert rows[0]["sync_id"] == source_sync_id
    assert rows[0]["platform_id"] is None
    assert rows[0]["profile_url"] == "https://example.test/bob"


def test_import_same_bundle_twice_is_idempotent(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    db = TalentDB(source_db)
    try:
        candidate_id = db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
        db.save_match_score(candidate_id, "jd-1", "final", 90)
    finally:
        db.close()

    export_bundle(source_db, bundle_path, mode="full")
    first = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")
    second = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        match_count = db._conn.execute("SELECT COUNT(*) FROM match_scores").fetchone()[0]
        import_count = db._conn.execute("SELECT COUNT(*) FROM sync_imports").fetchone()[0]
        candidate_count = db.count()
    finally:
        db.close()

    assert first["created"]["candidates"] == 1
    assert second["skipped"]["already_imported"] == 1
    assert candidate_count == 1
    assert match_count == 1
    assert import_count == 1


def test_apply_sync_import_duplicate_bundle_keeps_recorded_summary(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    db = TalentDB(source_db)
    try:
        candidate_id = db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
        db.save_match_score(candidate_id, "jd-1", "final", 90)
    finally:
        db.close()

    export_bundle(source_db, bundle_path, mode="full")
    first = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")
    duplicate_plan = _build_import_plan(bundle_path, target_db)

    db = TalentDB(target_db)
    try:
        before_summary = json.loads(
            db._conn.execute("SELECT summary FROM sync_imports").fetchone()["summary"]
        )
        second = db.apply_sync_import(
            manifest=duplicate_plan["_manifest"],
            table_rows=duplicate_plan["_table_rows"],
            plan=duplicate_plan,
        )
        after_summary = json.loads(
            db._conn.execute("SELECT summary FROM sync_imports").fetchone()["summary"]
        )
    finally:
        db.close()

    assert before_summary == first
    assert second["skipped"]["already_imported"] == 1
    assert after_summary == before_summary


def test_import_match_score_keeps_existing_local_score(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {
                "name": "Carol",
                "current_company": "Acme",
                "platform_id": "remote-1",
            },
            platform="maimai",
        )
        source.save_match_score(
            source_candidate_id,
            "jd-1",
            "final",
            95,
            {"remote": 95},
            "remote score",
        )
    finally:
        source.close()

    target = TalentDB(target_db)
    try:
        target_candidate_id = target.ingest(
            {
                "name": "Carol",
                "current_company": "Acme",
                "platform_id": "local-1",
            },
            platform="manual",
        )
        target.save_match_score(
            target_candidate_id,
            "jd-1",
            "final",
            72,
            {"local": 72},
            "local score",
        )
        local_score_row = target._conn.execute(
            """
            SELECT sync_id
            FROM match_scores
            WHERE candidate_id = ? AND jd_id = 'jd-1' AND match_type = 'final'
            """,
            (target_candidate_id,),
        ).fetchone()
    finally:
        target.close()

    export_bundle(source_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    target = TalentDB(target_db)
    try:
        row = target._conn.execute(
            """
            SELECT score, dimensions, reason, sync_id
            FROM match_scores
            WHERE candidate_id = ? AND jd_id = 'jd-1' AND match_type = 'final'
            """,
            (target_candidate_id,),
        ).fetchone()
    finally:
        target.close()

    assert result["merged"]["match_scores"] == 1
    assert row["score"] == 72
    assert json.loads(row["dimensions"]) == {"local": 72}
    assert row["reason"] == "local score"
    assert row["sync_id"] == local_score_row["sync_id"]


def test_import_match_score_records_conflict_for_stable_key_difference(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source_candidate_id = source.ingest(
            {"name": "Carol", "current_company": "Acme", "platform_id": "maimai-1"},
            platform="maimai",
        )
        source.save_match_score(
            source_candidate_id,
            "jd-1",
            "final",
            95,
            {"skill": 95},
            "remote reason",
        )
    finally:
        source.close()

    target = TalentDB(target_db)
    try:
        target_candidate_id = target.ingest(
            {"name": "Carol", "current_company": "Acme", "platform_id": "maimai-1"},
            platform="maimai",
        )
        target.save_match_score(
            target_candidate_id,
            "jd-1",
            "final",
            72,
            {"skill": 72},
            "local reason",
        )
    finally:
        target.close()

    export_bundle(source_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, target_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    target = TalentDB(target_db)
    try:
        row = target._conn.execute(
            """
            SELECT score, dimensions, reason
            FROM match_scores
            WHERE candidate_id = ? AND jd_id = 'jd-1' AND match_type = 'final'
            """,
            (target_candidate_id,),
        ).fetchone()
        conflicts = target._conn.execute(
            """
            SELECT entity_type, field_name, local_value, remote_value
            FROM sync_conflicts
            WHERE entity_type = 'match_score'
            """
        ).fetchall()
    finally:
        target.close()

    assert row["score"] == 72
    assert json.loads(row["dimensions"]) == {"skill": 72}
    assert row["reason"] == "local reason"
    assert result["conflicts"]["match_scores"] == 1
    assert len(conflicts) == 1
    assert conflicts[0]["field_name"] == "match_score"
    assert json.loads(conflicts[0]["local_value"])["score"] == 72
    assert json.loads(conflicts[0]["remote_value"])["score"] == 95


def test_import_wechat_timeline_dedupes_by_archive_identity_across_nodes(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"
    archive_path = "data/wechat-timelines/alice.md"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left.add_wechat_timeline(
            left_id,
            {
                "chat_name": "Alice",
                "chat_identifier": "wx-alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right_id = right.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        right.add_wechat_timeline(
            right_id,
            {
                "chat_name": "Alice",
                "chat_identifier": "wx-alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        rows = left._conn.execute(
            """
            SELECT chat_name, chat_identifier, start_time, end_time, markdown_path
            FROM candidate_wechat_timelines
            WHERE candidate_id = ?
            """,
            (left_id,),
        ).fetchall()
    finally:
        left.close()

    assert len(rows) == 1
    assert result["created"]["candidate_wechat_timelines"] == 0
    assert result["merged"]["candidate_wechat_timelines"] == 1


def test_import_wechat_timeline_matches_existing_identifier_to_incoming_chat_name(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"
    archive_path = "data/wechat-timelines/alice.md"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left.add_wechat_timeline(
            left_id,
            {
                "chat_name": "Alice",
                "chat_identifier": "wx-alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right_id = right.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        right.add_wechat_timeline(
            right_id,
            {
                "chat_name": "Alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        rows = left.get_wechat_timelines(left_id)
    finally:
        left.close()

    assert len(rows) == 1
    assert result["created"]["candidate_wechat_timelines"] == 0
    assert result["merged"]["candidate_wechat_timelines"] == 1


def test_import_wechat_timeline_matches_existing_chat_name_to_incoming_identifier(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"
    archive_path = "data/wechat-timelines/alice.md"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left.add_wechat_timeline(
            left_id,
            {
                "chat_name": "Alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right_id = right.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        right.add_wechat_timeline(
            right_id,
            {
                "chat_name": "Alice",
                "chat_identifier": "wx-alice",
                "start_time": "2026-05-13",
                "end_time": "2026-05-14",
                "markdown_path": archive_path,
            },
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm=CONFIRM_SYNC_TEXT)

    left = TalentDB(left_db)
    try:
        rows = left.get_wechat_timelines(left_id)
    finally:
        left.close()

    assert len(rows) == 1
    assert result["created"]["candidate_wechat_timelines"] == 0
    assert result["merged"]["candidate_wechat_timelines"] == 1


def test_import_tombstone_deletes_local_candidate(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    seed_bundle = tmp_path / "seed.zip"
    delete_bundle = tmp_path / "delete.zip"

    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
        source_node_id = db._node_id()
    finally:
        db.close()

    export_bundle(source_db, seed_bundle, mode="full")
    import_bundle(seed_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(source_db)
    try:
        local = db.fulltext_search("Alice")[0]
        db.delete_candidate(local.id)
    finally:
        db.close()

    export_bundle(source_db, delete_bundle, mode="full")
    result = import_bundle(delete_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        target_node_id = db._node_id()
        tombstone = db._conn.execute(
            """
            SELECT source_node_id, reason
            FROM sync_tombstones
            WHERE entity_type = 'candidate'
            """
        ).fetchone()
        assert db.count() == 0
    finally:
        db.close()

    assert tombstone is not None
    assert tombstone["reason"] == "local_delete"
    assert tombstone["source_node_id"] == source_node_id
    assert tombstone["source_node_id"] != target_node_id
    assert result["deleted"]["candidates"] == 1


def test_import_does_not_resurrect_candidate_after_tombstone(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    seed_bundle = tmp_path / "seed.zip"
    stale_bundle = tmp_path / "stale.zip"
    delete_bundle = tmp_path / "delete.zip"

    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()

    export_bundle(source_db, seed_bundle, mode="full")
    export_bundle(source_db, stale_bundle, mode="full")
    import_bundle(seed_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(source_db)
    try:
        local = db.fulltext_search("Alice")[0]
        db.delete_candidate(local.id)
    finally:
        db.close()

    export_bundle(source_db, delete_bundle, mode="full")
    import_bundle(delete_bundle, target_db, apply=True, confirm="确认同步人才库")

    plan = plan_import(stale_bundle, target_db)
    result = import_bundle(stale_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        assert db.count() == 0
        assert db._conn.execute("SELECT COUNT(*) FROM source_profiles").fetchone()[0] == 0
    finally:
        db.close()

    assert plan["created"]["candidates"] == 0
    assert plan["skipped"]["candidates"] == 1
    assert result["created"]["candidates"] == 0
    assert result["skipped"]["candidates"] == 1


def test_import_dry_run_does_not_create_target_db(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    source = TalentDB(source_db)
    try:
        source.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        source.close()
    export_bundle(source_db, bundle_path, mode="full")

    result = import_bundle(bundle_path, target_db, apply=False)

    assert result["created"]["candidates"] == 1
    assert not target_db.exists()


def test_plan_import_rejects_duplicate_sync_id_in_bundle(tmp_path: Path):
    source_db = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    duplicate_path = tmp_path / "duplicate.zip"

    source = TalentDB(source_db)
    try:
        source.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        source.close()
    export_bundle(source_db, bundle_path, mode="full")

    with zipfile.ZipFile(bundle_path) as src:
        payloads = {name: src.read(name) for name in src.namelist()}
    candidate_line = payloads["data/candidates.jsonl"].decode("utf-8").splitlines()[0]
    payloads["data/candidates.jsonl"] = (
        f"{candidate_line}\n{candidate_line}\n"
    ).encode("utf-8")
    checksum_lines = []
    for name in sorted(key for key in payloads if key != "checksums.sha256"):
        checksum_lines.append(f"{hashlib.sha256(payloads[name]).hexdigest()}  {name}")
    payloads["checksums.sha256"] = ("\n".join(checksum_lines) + "\n").encode("utf-8")
    with zipfile.ZipFile(duplicate_path, "w") as dst:
        for name in sorted(payloads):
            dst.writestr(name, payloads[name])

    with pytest.raises(ValueError, match="Duplicate sync_id"):
        plan_import(duplicate_path, tmp_path / "target.db")


def test_verify_bundle_rejects_tampered_payload(tmp_path: Path):
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(db_path)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()
    export_bundle(db_path, bundle_path, mode="full")

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle_path) as src, zipfile.ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "data/candidates.jsonl":
                data = data.replace(b"Alice", b"Alicia")
            dst.writestr(name, data)

    result = verify_bundle(tampered)

    assert result["ok"] is False
    assert "data/candidates.jsonl" in result["errors"][0]


def test_verify_bundle_accepts_exported_bundle(tmp_path: Path):
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(db_path)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()
    export_bundle(db_path, bundle_path, mode="full")

    result = verify_bundle(bundle_path)

    assert result == {"ok": True, "errors": []}


def test_verify_bundle_rejects_empty_checksums(tmp_path: Path):
    bundle_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", b"{}\n")
        bundle.writestr("checksums.sha256", b"")

    result = verify_bundle(bundle_path)

    assert result["ok"] is False
    assert any(
        "checksum" in error.lower() and "empty" in error.lower()
        for error in result["errors"]
    )


def test_verify_bundle_rejects_unlisted_file(tmp_path: Path):
    bundle_path = tmp_path / "bundle.zip"
    manifest = b"{}\n"
    checksum = f"{hashlib.sha256(manifest).hexdigest()}  manifest.json\n"
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", manifest)
        bundle.writestr("data/candidates.jsonl", b"{}\n")
        bundle.writestr("checksums.sha256", checksum.encode("utf-8"))

    result = verify_bundle(bundle_path)

    assert result["ok"] is False
    assert any("data/candidates.jsonl" in error for error in result["errors"])


def test_verify_bundle_rejects_manifest_missing_from_checksums(tmp_path: Path):
    bundle_path = tmp_path / "bundle.zip"
    candidates = b"{}\n"
    checksum = (
        f"{hashlib.sha256(candidates).hexdigest()}  data/candidates.jsonl\n"
    )
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", b"{}\n")
        bundle.writestr("data/candidates.jsonl", candidates)
        bundle.writestr("checksums.sha256", checksum.encode("utf-8"))

    result = verify_bundle(bundle_path)

    assert result["ok"] is False
    assert any("manifest.json" in error for error in result["errors"])


def test_verify_bundle_rejects_non_utf8_checksums(tmp_path: Path):
    bundle_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle_path, "w") as bundle:
        bundle.writestr("manifest.json", b"{}\n")
        bundle.writestr("checksums.sha256", b"\xff")

    result = verify_bundle(bundle_path)

    assert result["ok"] is False
    assert result["errors"] == ["Cannot decode checksums.sha256 as UTF-8"]


def test_sync_cli_export_and_dry_run_import(tmp_path: Path, capsys):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()

    assert sync_main(["export", "--db", str(source_db), "--out", str(bundle_path)]) == 0
    assert bundle_path.exists()
    assert sync_main(["import", "--db", str(target_db), "--bundle", str(bundle_path)]) == 0

    assert not target_db.exists()
    assert "dry-run" in capsys.readouterr().out


def test_sync_cli_apply_requires_confirm(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()
    export_bundle(source_db, bundle_path, mode="full")

    with pytest.raises(ValueError, match="确认同步人才库"):
        sync_main([
            "import",
            "--db",
            str(target_db),
            "--bundle",
            str(bundle_path),
            "--apply",
        ])


def test_sync_cli_status_missing_db_does_not_create_file(tmp_path: Path, capsys):
    missing_db = tmp_path / "missing.db"

    assert sync_main(["status", "--db", str(missing_db)]) == 0

    assert not missing_db.exists()
    assert "missing" in capsys.readouterr().out


def test_sync_cli_verify_bundle_failure_returns_one(tmp_path: Path, capsys):
    bundle_path = tmp_path / "bad.zip"
    bundle_path.write_bytes(b"not a zip")

    assert sync_main(["verify-bundle", "--bundle", str(bundle_path)]) == 1

    output = capsys.readouterr().out
    assert "bundle 校验失败" in output
    assert "Cannot open bundle" in output
