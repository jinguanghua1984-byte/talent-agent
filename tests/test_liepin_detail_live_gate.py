import json
from pathlib import Path

import pytest

import scripts.liepin_detail_live_gate as detail_gate
from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_live_gate import (
    DETAIL_BLOCK_STATUSES,
    build_detail_fetch_expression,
    classify_detail_result,
    detail_job_path,
    load_completed_detail_jobs,
    run_live_detail_smoke,
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
        "health": {
            "href": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
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
    assert "href" not in sanitized["health"]
    assert "rawPreview" not in sanitized["response"]
    assert "rawPreview" not in sanitized
    assert "showresumedetail" not in dumped
    assert "ck_id=secret" not in dumped
    assert sanitized["response"]["httpStatus"] == 403


def test_sanitize_detail_result_for_report_redacts_sensitive_string_values():
    payload = {
        "response": {
            "data": {
                "msg": "go https://h.liepin.com/resume/showresumedetail/?ck_id=secret",
                "nested": {
                    "redirect": "resume/showresumedetail/?sk_id=x",
                    "trace": "ckId=a&skId=b&fkId=c",
                },
                "plain": "正常消息",
            }
        }
    }

    sanitized = sanitize_detail_result_for_report(payload)
    dumped = json.dumps(sanitized, ensure_ascii=False)

    assert sanitized["response"]["data"]["msg"] == "[redacted]"
    assert sanitized["response"]["data"]["nested"]["redirect"] == "[redacted]"
    assert sanitized["response"]["data"]["nested"]["trace"] == "[redacted]"
    assert sanitized["response"]["data"]["plain"] == "正常消息"
    for marker in ("showresumedetail", "ck_id", "sk_id", "ckId", "skId", "fkId", "h.liepin.com/resume"):
        assert marker not in dumped


def _contact(platform_id: str, index: int) -> dict:
    return {
        "index": index,
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": f"user-{platform_id}",
        "profile_url": (
            "https://h.liepin.com/resume/showresumedetail/"
            f"?res_id_encode={platform_id}&ck_id=secret-token"
        ),
        "display_name": "张**",
        "current_company": "示例公司",
        "current_title": "AI产品经理",
        "priority": "detail_p0",
        "score": 95,
        "reasons": ["硕士及以上"],
        "raw_ref": {"search_page": "raw/search/page-000.json", "card_index": index},
    }


def _write_target_pack(root: Path, contacts: list[dict]) -> Path:
    pack_path = root / "raw" / "detail-targets" / "liepin-detail-p0-smoke-001.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_targets_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": "liepin-detail-p0-smoke-001",
                    "limit": 10,
                    "no_database_write": True,
                },
                "contacts": contacts,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_path


def _patch_liepin_target(monkeypatch, session_cls) -> None:
    monkeypatch.setattr(
        detail_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(detail_gate, "CdpSession", session_cls)


def _success_detail(platform_id: str) -> dict:
    return {
        "status": "ok",
        "httpStatus": 200,
        "contentType": "application/json",
        "rawLength": 120,
        "parseError": None,
        "rawPreview": '{"flag":1}',
        "data": {"flag": 1, "data": {"name": "张三", "workExperience": []}},
    }


def test_run_live_detail_smoke_writes_jobs_ledger_and_sanitized_summary(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])
    expressions: list[str] = []
    closed: list[bool] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "res_id_encode=res-1" in expression:
                return _success_detail("res-1")
            if "res_id_encode=res-2" in expression:
                return _success_detail("res-2")
            raise AssertionError(f"unexpected expression: {expression}")

        def close(self):
            closed.append(True)

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-001",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 2
    assert closed == [True]
    job_000 = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001" / "job-000.json"
    job_001 = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001" / "job-001.json"
    assert job_000.exists()
    assert job_001.exists()
    assert json.loads(job_000.read_text(encoding="utf-8-sig"))["platform_id"] == "res-1"
    ledger = (paths.state_dir / "detail-request-ledger.jsonl").read_text(encoding="utf-8")
    assert '"event": "detail_completed"' in ledger
    summary_json = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    summary_md = (paths.reports_dir / "detail-smoke-summary.md").read_text(encoding="utf-8")
    assert summary_json["completed"] == 2
    assert "showresumedetail" not in summary_md


def test_run_live_detail_smoke_blocks_without_writing_failed_job(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])
    closed: list[bool] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return {
                "status": "ok",
                "httpStatus": 429,
                "contentType": "application/json",
                "rawLength": 40,
                "parseError": None,
                "rawPreview": "showresumedetail secret",
                "data": {"flag": 0, "msg": "too many requests"},
            }

        def close(self):
            closed.append(True)

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-002",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "http_429"
    assert result["completed"] == 0
    assert closed == [True]
    job_000 = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001" / "job-000.json"
    assert not job_000.exists()
    continuation = json.loads(
        (paths.state_dir / "detail-live-liepin-detail-p0-smoke-001-continuation-after-http_429.json").read_text(
            encoding="utf-8-sig"
        )
    )
    assert continuation["resume_from"]["platform_id"] == "res-1"
    interruptions = sorted(paths.reports_dir.glob("interruption-detail-liepin-detail-p0-smoke-001-*.json"))
    assert len(interruptions) == 1
    assert "run-002" in interruptions[0].name or "job-000" in interruptions[0].name
    interruption_dump = interruptions[0].read_text(encoding="utf-8-sig")
    assert "showresumedetail" not in interruption_dump


@pytest.mark.parametrize(
    "bad_contact,match",
    [
        ({**_contact("res-1", 0), "profile_url": ""}, "profile_url"),
        ({**_contact("res-1", 0), "profile_url": "https://example.com/resume/showresumedetail"}, "not allowed"),
        ({**_contact("res-1", 0), "platform_id": " "}, "platform_id"),
        ({**_contact("res-1", 0), "user_id_encode": ""}, "user_id_encode"),
        ({**_contact("res-1", 0), "index": -1}, "index"),
    ],
)
def test_run_live_detail_smoke_rejects_malformed_contacts_before_cdp(
    tmp_path: Path,
    monkeypatch,
    bad_contact: dict,
    match: str,
):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [bad_contact])
    monkeypatch.setattr(detail_gate, "list_targets", lambda cdp_url: (_ for _ in ()).throw(AssertionError("opened CDP")))
    monkeypatch.setattr(detail_gate, "CdpSession", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("opened session")))

    with pytest.raises(ValueError, match=match):
        run_live_detail_smoke(
            campaign_root=paths.root,
            target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
            cdp_url="http://127.0.0.1:9898",
            delay_seconds=0,
            timeout_seconds=1,
            run_id="run-bad",
        )

    assert not (paths.state_dir / "detail-request-ledger.jsonl").exists()
    assert not (paths.reports_dir / "detail-smoke-summary.json").exists()


def test_run_live_detail_smoke_blocks_partial_detail_and_marks_template_drift(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-1", 0)])

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return {
                "status": "ok",
                "httpStatus": 200,
                "contentType": "application/json",
                "rawLength": 20,
                "parseError": None,
                "rawPreview": '{"flag":1,"data":{}}',
                "data": {"flag": 1, "data": {}},
            }

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-partial",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "partial_detail"
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["template_drift"] == 1
    assert type(summary["template_drift"]) is int
    interruptions = sorted(paths.reports_dir.glob("interruption-detail-liepin-detail-p0-smoke-001-*.json"))
    assert len(interruptions) == 1
    assert "run-partial" in interruptions[0].name or "job-000" in interruptions[0].name


def test_run_live_detail_smoke_blocks_on_resume_platform_mismatch_without_fetching_next(
    tmp_path: Path,
    monkeypatch,
):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    job_dir.mkdir(parents=True)
    detail_job_path(job_dir, 0).write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_job_v1",
                "status": "done",
                "platform_id": "other",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    expressions: list[str] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            raise AssertionError(f"unexpected fetch after mismatch: {expression}")

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-mismatch",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "resume_platform_mismatch"
    assert len(expressions) == 1
    assert all("res_id_encode=res-2" not in expression for expression in expressions)
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["status"] == "blocked"
    assert summary["stopReason"] == "resume_platform_mismatch"


def test_run_live_detail_smoke_resume_skips_completed_jobs(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    job_dir.mkdir(parents=True)
    detail_job_path(job_dir, 0).write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_job_v1",
                "status": "done",
                "platform_id": "res-1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    expressions: list[str] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "res_id_encode=res-2" in expression:
                return _success_detail("res-2")
            raise AssertionError(f"unexpected expression: {expression}")

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-003",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 1
    assert detail_job_path(job_dir, 1).exists()
    assert all("res_id_encode=res-1" not in expression for expression in expressions)


@pytest.mark.parametrize(
    "health,reason",
    [
        ({"hasLiepinSearch": True, "hasLoginPrompt": True, "hasCaptcha": False}, "login"),
        ({"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": True}, "captcha"),
        ({"hasLiepinSearch": False, "hasLoginPrompt": False, "hasCaptcha": False}, "not_liepin_search"),
    ],
)
def test_run_live_detail_smoke_health_block_writes_recovery_without_fetch(
    tmp_path: Path,
    monkeypatch,
    health: dict,
    reason: str,
):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-1", 0)])
    expressions: list[str] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            return health

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-004",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == reason
    assert len(expressions) == 1
    continuation = paths.state_dir / f"detail-live-liepin-detail-p0-smoke-001-continuation-after-{reason}.json"
    assert continuation.exists()
    interruptions = sorted(paths.reports_dir.glob("interruption-detail-liepin-detail-p0-smoke-001-*.json"))
    assert len(interruptions) == 1
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["status"] == "blocked"
    assert summary["stopReason"] == reason
