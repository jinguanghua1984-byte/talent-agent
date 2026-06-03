import json
from pathlib import Path

import pytest

from scripts.liepin_detail_live_gate import (
    DETAIL_BLOCK_STATUSES,
    build_detail_fetch_expression,
    classify_detail_result,
    detail_job_path,
    load_completed_detail_jobs,
    sanitize_detail_result_for_report,
    validate_detail_url,
)


def test_validate_detail_url_accepts_only_liepin_detail_pages():
    detail_url = "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1"

    assert validate_detail_url(detail_url) == detail_url
    assert validate_detail_url("https://h.liepin.com/resume/showresumedetail?res_id_encode=res-1")

    with pytest.raises(ValueError, match="not allowed"):
        validate_detail_url("https://example.com/resume/showresumedetail/?res_id_encode=res-1")

    with pytest.raises(ValueError, match="not allowed"):
        validate_detail_url("https://h.liepin.com/search/getConditionItem")

    with pytest.raises(ValueError, match="not allowed"):
        validate_detail_url("https://h.liepin.com/resume/showresumedetail-extra?res_id_encode=res-1")


def test_build_detail_fetch_expression_uses_credentials_and_safe_headers():
    detail_url = "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1"

    expression = build_detail_fetch_expression(
        detail_url,
        headers={"Accept": "application/json, text/plain, */*"},
    )

    assert "fetch(" in expression
    assert 'credentials: "include"' in expression
    assert "showresumedetail" in expression
    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression
    assert '"Accept": "application/json, text/plain, */*"' in expression


def test_build_detail_fetch_expression_rejects_forbidden_auth_headers():
    detail_url = "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1"
    for header_name, header_value in (
        ("Cookie", "sid=secret"),
        ("Authorization", "Bearer secret"),
        ("Proxy-Authorization", "Bearer secret"),
    ):
        with pytest.raises(ValueError, match="forbidden"):
            build_detail_fetch_expression(
                detail_url,
                headers={header_name: header_value},
            )


def test_classify_detail_result_detects_blocks_partial_and_success():
    assert DETAIL_BLOCK_STATUSES == {401, 403, 429, 432}
    assert classify_detail_result({"httpStatus": 429, "data": {}}) == "http_429"
    assert classify_detail_result({"httpStatus": 200, "parseError": "Unexpected token <"}) == "non_json"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 0, "msg": "无权限"}}) == "business_block"
    assert classify_detail_result({"httpStatus": 200, "data": {"code": 403, "msg": "受限"}}) == "business_block"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {"name": "张三"}}}) is None
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": "1", "data": {"name": "张三", "workExperience": []}}}) is None
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {}}}) == "partial_detail"


def test_detail_job_path_and_load_completed_detail_jobs(tmp_path: Path):
    job_dir = tmp_path / "jobs"
    job_dir.mkdir()
    detail_job_path(job_dir, 12).write_text(
        json.dumps({"status": "done", "platform_id": "res-12"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (job_dir / "job-2.json").write_text(
        json.dumps({"status": "done", "platform_id": "res-noncanonical"}, ensure_ascii=False),
        encoding="utf-8",
    )
    detail_job_path(job_dir, 3).write_text(
        json.dumps({"status": "blocked", "platform_id": "res-3"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (job_dir / "job-abc.json").write_text("{}", encoding="utf-8")
    (job_dir / "job-004.json").write_text("{bad", encoding="utf-8")

    assert detail_job_path(job_dir, 2) == job_dir / "job-002.json"
    assert load_completed_detail_jobs(job_dir) == {12: "res-12"}

    with pytest.raises(ValueError, match="non-negative"):
        detail_job_path(job_dir, -1)


def test_sanitize_detail_result_for_report_removes_sensitive_fields():
    payload = {
        "status": "blocked",
        "profile_url": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
        "request": {
            "url": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
            "method": "GET",
        },
        "response": {
            "httpStatus": 403,
            "rawPreview": "https://h.liepin.com/resume/showresumedetail/?ck_id=secret",
        },
        "rawPreview": "showresumedetail ck_id=secret",
    }

    sanitized = sanitize_detail_result_for_report(payload)
    dumped = json.dumps(sanitized, ensure_ascii=False)

    assert "profile_url" not in sanitized
    assert "url" not in sanitized["request"]
    assert "rawPreview" not in sanitized["response"]
    assert "rawPreview" not in sanitized
    assert "showresumedetail" not in dumped
    assert "ck_id=secret" not in dumped
    assert sanitized["response"]["httpStatus"] == 403
