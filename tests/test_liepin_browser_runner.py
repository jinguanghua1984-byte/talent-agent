import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_api_contract import CONDITION_BY_JOB_URL, SEARCH_RESUMES_URL
from scripts.liepin_browser_runner import (
    build_in_page_fetch_expression,
    validate_allowed_url,
)


def test_validate_allowed_url_accepts_only_liepin_p0_endpoints():
    assert validate_allowed_url(CONDITION_BY_JOB_URL) == CONDITION_BY_JOB_URL
    assert validate_allowed_url(SEARCH_RESUMES_URL) == SEARCH_RESUMES_URL

    with pytest.raises(ValueError, match="not allowed"):
        validate_allowed_url("https://api-h.liepin.com/api/other")

    with pytest.raises(ValueError, match="not allowed"):
        validate_allowed_url("https://example.com/api/com.liepin.searchfront4r.h.search-resumes")


def test_fetch_expression_uses_credentials_without_sensitive_storage_reads():
    expression = build_in_page_fetch_expression(
        SEARCH_RESUMES_URL,
        "searchParamsInputVo=%7B%7D&logForm=%7B%7D",
    )

    assert 'credentials: "include"' in expression
    assert '"Content-Type": "application/x-www-form-urlencoded"' in expression
    assert SEARCH_RESUMES_URL in expression
    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression


def test_dry_run_fetch_cli_prints_expression_metadata(tmp_path: Path):
    body_file = tmp_path / "body.json"
    body_file.write_text(
        json.dumps({"body": "jobId=75703601"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_browser_runner",
            "dry-run-fetch",
            "--url",
            CONDITION_BY_JOB_URL,
            "--body-json",
            str(body_file),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["url"] == CONDITION_BY_JOB_URL
    assert payload["body"] == "jobId=75703601"
    assert payload["sensitive_storage_reads"] == []
    assert "fetch(" in payload["expression"]
