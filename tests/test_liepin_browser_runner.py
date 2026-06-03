import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_api_contract import CONDITION_BY_JOB_URL, SEARCH_RESUMES_URL
from scripts.liepin_browser_runner import (
    build_in_page_fetch_expression,
    sanitize_liepin_request_headers,
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


def test_fetch_expression_includes_only_allowed_request_headers():
    expression = build_in_page_fetch_expression(
        SEARCH_RESUMES_URL,
        "searchParamsInputVo=%7B%7D&logForm=%7B%7D",
        headers={
            "Accept": "application/json, text/plain, */*",
            "X-XSRF-TOKEN": "safe-xsrf-token",
            "X-Fscp-Trace-Id": "trace-001",
            "User-Agent": "browser-managed",
            "sec-ch-ua": "browser-managed",
        },
    )

    assert '"Accept": "application/json, text/plain, */*"' in expression
    assert '"X-XSRF-TOKEN": "safe-xsrf-token"' in expression
    assert '"X-Fscp-Trace-Id": "trace-001"' in expression
    assert "User-Agent" not in expression
    assert "sec-ch-ua" not in expression


def test_sanitize_liepin_request_headers_rejects_forbidden_auth_headers():
    with pytest.raises(ValueError, match="forbidden"):
        sanitize_liepin_request_headers({"Cookie": "sid=secret"})

    with pytest.raises(ValueError, match="forbidden"):
        sanitize_liepin_request_headers({"Authorization": "Bearer secret"})

    with pytest.raises(ValueError, match="forbidden"):
        sanitize_liepin_request_headers({"Proxy-Authorization": "Bearer secret"})


def test_sanitize_liepin_request_headers_refreshes_trace_id():
    headers = sanitize_liepin_request_headers(
        {
            "Content-Type": "text/plain",
            "X-Fscp-Trace-Id": "stale-trace-id",
        },
        refresh_trace_id=True,
    )

    assert headers["Content-Type"] == "application/x-www-form-urlencoded"
    assert headers["X-Fscp-Trace-Id"] != "stale-trace-id"
    assert len(headers["X-Fscp-Trace-Id"]) == 36


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
