import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_campaign import ensure_campaign, load_completed_pages, mark_page_completed, page_raw_path
from scripts.maimai_search_live_standardize import standardize_live_run


def _search_event_count(campaign) -> int:
    if not campaign.search_events.exists():
        return 0
    return len([line for line in campaign.search_events.read_text(encoding="utf-8").splitlines() if line.strip()])


def test_standardize_live_run_writes_successful_pages_to_canonical_raw(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-001",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [
                            {
                                "page": 1,
                                "ok": True,
                                "request": {"url": "/api/ent/v3/search/basic"},
                                "responseSummary": {"total": 1},
                                "responseData": {"data": {"contacts": [{"id": "p1", "name": "张三"}]}},
                                "contacts": [{"id": "p1", "name": "张三"}],
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 1
    raw = page_raw_path(campaign, "unit-000001", 1)
    payload = json.loads(raw.read_text(encoding="utf-8-sig"))
    assert payload["source_run"] == str(run_path)
    assert payload["contacts"][0]["name"] == "张三"
    assert load_completed_pages(campaign) == {("unit-000001", 1)}


def test_standardize_live_run_rejects_partial_or_failed_pages(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "stopped",
                "stopReason": "captcha_api",
                "batches": [{"batch_id": "unit-000001", "pages": [{"page": 1, "ok": False, "contacts": []}]}],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert result["skipped_pages"][0]["reason"] == "page_not_ok"


def test_standardize_live_run_skips_missing_batch_id_and_invalid_contacts(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-002",
                "batches": [
                    {"pages": [{"page": 1, "ok": True, "contacts": []}]},
                    {"batch_id": "unit-000002", "pages": [{"page": 2, "ok": True, "contacts": {"id": "bad"}}]},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert [item["reason"] for item in result["skipped_pages"]] == ["missing_batch_id", "invalid_contacts"]
    assert not page_raw_path(campaign, "unit-000002", 2).exists()
    assert load_completed_pages(campaign) == set()


def test_cli_writes_summary_out(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    out_path = tmp_path / "summary.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-003",
                "wave_id": "wave-unit",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [{"page": 1, "ok": True, "contacts": [{"id": "p1"}]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.maimai_search_live_standardize",
            "--campaign-root",
            str(campaign.root),
            "--run",
            str(run_path),
            "--out",
            str(out_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_summary = json.loads(completed.stdout)
    file_summary = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout_summary["written_pages"] == 1
    assert file_summary["status"] == "standardized"
    assert file_summary["written_pages"] == 1
    assert page_raw_path(campaign, "unit-000001", 1).exists()


def test_standardize_live_run_rejects_non_canonical_batch_ids(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-004",
                "batches": [
                    {"batch_id": "abc", "pages": [{"page": 1, "ok": True, "contacts": []}]},
                    {"batch_id": "../unit-000001", "pages": [{"page": 2, "ok": True, "contacts": []}]},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert [item["reason"] for item in result["skipped_pages"]] == ["invalid_batch_id", "invalid_batch_id"]
    assert not (campaign.raw_search_dir / "abc").exists()
    assert not (campaign.raw_search_dir.parent / "unit-000001" / "page-002.json").exists()
    assert load_completed_pages(campaign) == set()


def test_standardize_live_run_is_idempotent_without_duplicate_events(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-005",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [{"page": 1, "ok": True, "contacts": [{"id": "p1"}]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    first = standardize_live_run(campaign.root, run_path)
    first_event_count = _search_event_count(campaign)
    second = standardize_live_run(campaign.root, run_path)

    assert first["written_pages"] == 1
    assert second["written_pages"] == 0
    assert second["skipped_pages"][0]["reason"] == "already_completed"
    assert _search_event_count(campaign) == first_event_count == 1


def test_standardize_live_run_skips_existing_raw_conflict(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-006",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [{"page": 1, "ok": True, "contacts": [{"id": "new"}]}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    mark_page_completed(campaign, "unit-000001", 1, {"contacts": [{"id": "existing"}]})
    initial_event_count = _search_event_count(campaign)

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert result["skipped_pages"][0]["reason"] == "conflict_existing_raw"
    raw = json.loads(page_raw_path(campaign, "unit-000001", 1).read_text(encoding="utf-8-sig"))
    assert raw["contacts"] == [{"id": "existing"}]
    assert _search_event_count(campaign) == initial_event_count


def test_standardize_live_run_skip_diagnostics_include_compact_evidence(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "stopped",
                "stopReason": "captcha_api",
                "run_id": "run-007",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "error": "batch captcha",
                        "pages": [
                            {
                                "page": 1,
                                "ok": False,
                                "error": "page captcha",
                                "responseSummary": {"httpStatus": 432, "total": 0},
                                "contacts": [],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    skipped = result["skipped_pages"][0]
    assert skipped["reason"] == "page_not_ok"
    assert skipped["run_status"] == "stopped"
    assert skipped["run_stop_reason"] == "captcha_api"
    assert skipped["batch_error"] == "batch captcha"
    assert skipped["page_error"] == "page captcha"
    assert skipped["responseSummary"] == {"httpStatus": 432, "total": 0}


def test_standardize_live_run_rejects_boolean_page_number(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-008",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [{"page": True, "ok": True, "contacts": []}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert result["skipped_pages"][0]["reason"] == "invalid_page_number"
    assert not page_raw_path(campaign, "unit-000001", 1).exists()
    assert load_completed_pages(campaign) == set()


def test_standardize_live_run_raises_for_malformed_top_level_batches(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps({"status": "completed", "run_id": "run-009", "batches": ""}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="batches must be a list"):
        standardize_live_run(campaign.root, run_path)


def test_standardize_live_run_records_invalid_pages_for_malformed_pages(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "run-010",
                "batches": [{"batch_id": "unit-000001", "pages": ""}],
            }
        ),
        encoding="utf-8",
    )

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert result["skipped_pages"][0]["reason"] == "invalid_pages"
    assert result["skipped_pages"][0]["unit_id"] == "unit-000001"
    assert not (campaign.raw_search_dir / "unit-000001").exists()
