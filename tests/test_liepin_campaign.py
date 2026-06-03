import json
from pathlib import Path

import pytest

from scripts.liepin_campaign import (
    MANIFEST_SCHEMA,
    append_request_ledger,
    ensure_campaign,
    load_completed_pages,
    page_raw_path,
    write_continuation_plan,
    mark_page_completed,
)


def test_ensure_campaign_creates_liepin_directory_contract(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    assert paths.root.exists()
    assert paths.state_dir.exists()
    assert paths.raw_condition_dir.exists()
    assert paths.raw_search_dir.exists()
    assert paths.structured_dir.exists()
    assert paths.reports_dir.exists()
    manifest = json.loads(paths.manifest.read_text(encoding="utf-8-sig"))
    assert manifest["campaign_id"] == "liepin-demo"
    assert manifest["schema"] == MANIFEST_SCHEMA


def test_ensure_campaign_rejects_manifest_schema_mismatch(tmp_path: Path):
    root = tmp_path / "liepin-demo"
    root.mkdir()
    (root / "campaign-manifest.json").write_text(
        json.dumps({"campaign_id": "liepin-demo", "schema": "other"}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="schema mismatch"):
        ensure_campaign(root)


def test_mark_page_completed_writes_zero_based_raw_and_ledger(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    payload = {
        "flag": 1,
        "data": {
            "ckId": "ck-1",
            "skId": "sk-1",
            "fkId": "fk-1",
            "cardResList": [],
        },
    }

    mark_page_completed(
        paths,
        cur_page=0,
        payload=payload,
        request={"url": "https://api-h.liepin.com/api/search"},
        run_id="run-001",
    )

    raw_path = page_raw_path(paths, 0)
    saved = json.loads(raw_path.read_text(encoding="utf-8-sig"))
    assert raw_path.name == "page-000.json"
    assert saved["curPage"] == 0
    assert saved["payload"] == payload
    assert load_completed_pages(paths) == {0}
    ledger_rows = [
        json.loads(line)
        for line in paths.request_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert ledger_rows[0]["event"] == "page_completed"
    assert ledger_rows[0]["curPage"] == 0
    assert ledger_rows[0]["run_id"] == "run-001"


def test_page_helpers_reject_negative_page(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    with pytest.raises(ValueError, match="cur_page must be non-negative"):
        page_raw_path(paths, -1)


def test_write_continuation_plan_and_request_ledger(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    continuation = write_continuation_plan(
        paths,
        next_cur_page=1,
        reason="http_429",
        ck_id="ck-1",
        sk_id="sk-1",
        fk_id="fk-1",
    )
    append_request_ledger(paths, {"event": "blocked", "reason": "http_429"})

    saved = json.loads(paths.continuation_plan.read_text(encoding="utf-8-sig"))
    assert saved == continuation
    assert saved["next_cur_page"] == 1
    assert saved["reason"] == "http_429"
    assert saved["ckId"] == "ck-1"
    ledger = paths.request_ledger.read_text(encoding="utf-8")
    assert '"event": "blocked"' in ledger
