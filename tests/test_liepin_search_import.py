import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_search_import import (
    CONFIRM_TEXT,
    apply_search_import,
    dry_run_search_import,
    search_summary_to_ingest_payload,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _summary(platform_id: str, *, display_name: str = "张**", card_index: int = 0) -> dict:
    return {
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": f"user-{platform_id}",
        "display_name": display_name,
        "current_company": "示例公司",
        "current_title": "AI产品经理",
        "city": "北京",
        "education": "硕士",
        "work_years": 8,
        "expected_city": "北京",
        "expected_title": "产品经理",
        "active_status": {"code": "1", "name": "今天活跃"},
        "profile_url": (
            "https://h.liepin.com/resume/showresumedetail/"
            f"?res_id_encode={platform_id}&ck_id=secret-ck&sk_id=secret-sk&fk_id=secret-fk"
        ),
        "resume_source": "1",
        "resume_type": 0,
        "raw_ref": {
            "search_page": "raw/search/page-000.json",
            "card_index": card_index,
            "ckId": "ck-secret",
            "skId": "sk-secret",
            "fkId": "fk-secret",
        },
    }


def test_search_summary_to_ingest_payload_sanitizes_token_fields():
    payload = search_summary_to_ingest_payload(_summary("res-1"))

    assert payload["name"] == "张**（猎聘res-1）"
    assert payload["platform_id"] == "res-1"
    assert payload["current_company"] == "示例公司"
    assert payload["data_level"] == "lead"
    assert payload["raw_profile"]["liepin_search_summary"]["raw_ref"] == {
        "search_page": "raw/search/page-000.json",
        "card_index": 0,
    }
    dumped = json.dumps(payload["raw_profile"], ensure_ascii=False)
    assert "showresumedetail" not in dumped
    assert "ck_id=" not in dumped
    assert "sk_id=" not in dumped
    assert "fk_id=" not in dumped
    assert "ck-secret" not in dumped


def test_dry_run_search_import_does_not_create_campaign_db_and_writes_sanitized_report(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(paths.candidate_summaries, [_summary("res-1"), _summary("res-1"), _summary("res-2")])

    result = dry_run_search_import(paths.root)

    assert result["schema"] == "liepin_search_import_v1"
    assert result["mode"] == "dry-run"
    assert result["raw_count"] == 3
    assert result["unique_count"] == 2
    assert result["duplicates_skipped"] == 1
    assert result["result"] == {"created": 2, "merged": 0, "pending": 0, "errors": 0, "total": 2, "error_details": []}
    assert result["no_main_db_write"] is True
    assert not (paths.root / "talent.db").exists()
    report_dump = (paths.reports_dir / "search-import-dry-run.json").read_text(
        encoding="utf-8-sig"
    ) + (paths.reports_dir / "search-import-dry-run.md").read_text(encoding="utf-8")
    assert "showresumedetail" not in report_dump
    assert "ck_id=" not in report_dump
    assert "sk_id=" not in report_dump
    assert "fk_id=" not in report_dump
    assert "secret-ck" not in report_dump


def test_apply_search_import_requires_confirm_and_writes_only_campaign_db(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(paths.candidate_summaries, [_summary("res-1"), _summary("res-2", display_name="李**", card_index=1)])

    with pytest.raises(ValueError, match=CONFIRM_TEXT):
        apply_search_import(paths.root, confirm="")

    result = apply_search_import(paths.root, confirm=CONFIRM_TEXT)

    assert result["mode"] == "apply"
    assert result["result"]["created"] == 2
    assert result["campaign_db"] == "talent.db"
    db_path = paths.root / "talent.db"
    assert db_path.exists()
    conn = sqlite3.connect(str(db_path))
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM source_profiles WHERE platform='liepin'").fetchone()[0] == 2
        raw_profile = conn.execute(
            "SELECT raw_profile FROM source_profiles WHERE platform='liepin' AND platform_id='res-1'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert "showresumedetail" not in raw_profile
    assert "ck_id=" not in raw_profile
    ledger = (paths.state_dir / "import-ledger.jsonl").read_text(encoding="utf-8")
    assert '"action": "search_import_apply"' in ledger
    assert '"status": "completed"' in ledger


def test_search_import_cli_supports_dry_run_and_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(paths.candidate_summaries, [_summary("res-1")])

    dry = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_search_import",
            "dry-run",
            "--campaign-root",
            str(paths.root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(dry.stdout)["result"]["created"] == 1
    assert not (paths.root / "talent.db").exists()

    apply = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_search_import",
            "apply",
            "--campaign-root",
            str(paths.root),
            "--confirm",
            CONFIRM_TEXT,
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(apply.stdout)["mode"] == "apply"
    assert (paths.root / "talent.db").exists()
