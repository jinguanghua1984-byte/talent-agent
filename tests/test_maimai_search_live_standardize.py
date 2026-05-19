import json
import subprocess
import sys
from pathlib import Path

from scripts.maimai_ai_infra_campaign import ensure_campaign, load_completed_pages, page_raw_path
from scripts.maimai_search_live_standardize import standardize_live_run


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
