import json
from pathlib import Path

import pytest

import scripts.liepin_detail_live_gate as detail_gate
from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_live_gate import (
    DETAIL_BLOCK_STATUSES,
    build_detail_fetch_expression,
    build_resume_view_fetch_expression,
    classify_detail_result,
    detail_job_path,
    load_completed_detail_jobs,
    run_live_detail_pack,
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


def test_build_resume_view_fetch_expression_posts_param_form_from_detail_url():
    detail_url = (
        "https://h.liepin.com/resume/showresumedetail/"
        "?showsearchfeedback=1&res_id_encode=res-1&index=0&position=0&cur_page=0"
        "&pageSize=30&ck_id=ck-secret&sk_id=sk-secret&fk_id=fk-secret"
        "&sfrom=RES_SEARCH&res_source=1&type=normal&sss=sss-secret&sScene=scene&dqCode=010"
    )

    expression = build_resume_view_fetch_expression(detail_url)

    assert "api/com.liepin.rresume.userh.pc.resume-view" in expression
    assert 'method: "POST"' in expression
    assert 'credentials: "include"' in expression
    assert "paramForm=" in expression
    assert "resIdEncode" in expression
    assert "res-1" in expression
    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression


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
    assert classify_detail_result(
        {
            "httpStatus": 200,
            "contentType": "text/html;charset=UTF-8",
            "parseError": "Unexpected token <",
            "rawPreview": "<!doctype html><html><head><title>简历详情</title></head><body></body></html>",
        }
    ) == "detail_html"
    assert classify_detail_result({"httpStatus": 200, "parseError": "Unexpected token x"}) == "non_json"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 0, "msg": "无权限"}}) == "business_block"
    assert classify_detail_result(
        {"httpStatus": 200, "data": {"flag": 0, "code": "11000", "msg": "对方设置了隐私保护，暂不支持查看"}}
    ) == "privacy_protected"
    assert classify_detail_result({"httpStatus": 200, "data": {"code": 403, "msg": "受限"}}) == "business_block"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "msg": "受限"}}) == "business_block"
    assert (
        classify_detail_result(
            {
                "httpStatus": 200,
                "data": {
                    "flag": 1,
                    "data": {
                        "resumeDetailVo": {
                            "baseInfo": {},
                            "projectExperiences": [
                                {
                                    "rpdDuty": "协调量大；场地受限；项目创优目标高，对质量管理和合规性要求严苛。"
                                }
                            ],
                        }
                    },
                },
            }
        )
        is None
    )
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {"name": "张三"}}}) is None
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {"resumeDetailVo": {"baseInfo": {}}}}}) is None
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
    detail_job_path(job_dir, 5).write_text(
        json.dumps({"status": "privacy_protected", "platform_id": "res-5"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (job_dir / "job-abc.json").write_text("{}", encoding="utf-8")
    (job_dir / "job-004.json").write_text("{bad", encoding="utf-8")

    assert detail_job_path(job_dir, 2) == job_dir / "job-002.json"
    assert load_completed_detail_jobs(job_dir) == {5: "res-5", 12: "res-12"}

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
    return _write_target_pack_with_pack_id(root, contacts, "liepin-detail-p0-smoke-001")


def _write_target_pack_with_pack_id(root: Path, contacts: list[dict], pack_id: str) -> Path:
    pack_path = root / "raw" / "detail-targets" / "liepin-detail-p0-smoke-001.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_targets_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": pack_id,
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


def _write_full_target_pack(root: Path, contacts: list[dict], pack_id: str = "detail-p0-p1-pack-001") -> Path:
    pack_path = root / "raw" / "detail-targets" / f"{pack_id}.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_pack_plan_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": pack_id,
                    "scope": "p0-p1",
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
            if "resume-view" in expression and "res-1" in expression:
                return _success_detail("res-1")
            if "resume-view" in expression and "res-2" in expression:
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


def test_run_live_detail_smoke_uses_request_template_headers_for_resume_view(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack(paths.root, [_contact("res-1", 0)])
    (paths.state_dir / "request-template.json").write_text(
        json.dumps(
            {
                "schema": "liepin_request_template_v1",
                "headers": {
                    "X-XSRF-TOKEN": "xsrf-token",
                    "X-Fscp-Trace-Id": "trace-old",
                    "X-Unsupported": "must-not-pass",
                },
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
            assert "resume-view" in expression
            assert "X-XSRF-TOKEN" in expression
            assert "xsrf-token" in expression
            assert "X-Fscp-Trace-Id" in expression
            assert "trace-old" not in expression
            assert "must-not-pass" not in expression
            return _success_detail("res-1")

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-template",
    )

    assert result["status"] == "completed"


def test_run_live_detail_smoke_accepts_safe_pack_id(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack_with_pack_id(paths.root, [_contact("res-1", 0)], "liepin-detail-p0-smoke-001")

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return _success_detail("res-1")

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="run-safe-pack",
    )

    assert result["status"] == "completed"
    assert (paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001" / "job-000.json").exists()


def test_run_live_detail_smoke_rejects_unsafe_pack_id_before_cdp(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack_with_pack_id(paths.root, [_contact("res-1", 0)], "../../outside")
    monkeypatch.setattr(detail_gate, "list_targets", lambda cdp_url: (_ for _ in ()).throw(AssertionError("opened CDP")))
    monkeypatch.setattr(detail_gate, "CdpSession", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("opened session")))

    with pytest.raises(ValueError, match="pack_id"):
        run_live_detail_smoke(
            campaign_root=paths.root,
            target_pack="raw/detail-targets/liepin-detail-p0-smoke-001.json",
            cdp_url="http://127.0.0.1:9898",
            delay_seconds=0,
            timeout_seconds=1,
            run_id="run-unsafe-pack",
        )

    assert not (paths.root / "raw" / "detail-live").exists()
    assert not (paths.state_dir / "detail-request-ledger.jsonl").exists()


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


def test_run_live_detail_smoke_records_privacy_protected_and_continues(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_target_pack(paths.root, [_contact("res-private", 0), _contact("res-ok", 1)])

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            if "hasLiepinSearch" in expression:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "res-private" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 60,
                    "parseError": None,
                    "data": {
                        "flag": 0,
                        "code": "11000",
                        "msg": "对方设置了隐私保护，暂不支持查看",
                        "data": {},
                    },
                }
            if "res-ok" in expression:
                return _success_detail("res-ok")
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
        run_id="run-privacy",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 1
    assert result["privacy_protected"] == 1
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    private_job = json.loads(detail_job_path(job_dir, 0).read_text(encoding="utf-8-sig"))
    assert private_job["status"] == "privacy_protected"
    assert detail_job_path(job_dir, 1).exists()
    assert load_completed_detail_jobs(job_dir) == {0: "res-private", 1: "res-ok"}
    ledger = (paths.state_dir / "detail-request-ledger.jsonl").read_text(encoding="utf-8")
    assert '"event": "detail_privacy_protected"' in ledger
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["privacy_protected"] == 1
    assert summary["blocked"] is False


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


def test_run_live_detail_smoke_classifies_detail_html_as_calibration_needed(tmp_path: Path, monkeypatch):
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
                "contentType": "text/html;charset=UTF-8",
                "rawLength": 4913,
                "parseError": 'Unexpected token \'<\', "<!doctype "... is not valid JSON',
                "rawPreview": "<!doctype html><html><head><title>找简历</title></head><body><div id=\"app\"></div></body></html>",
                "data": None,
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
        run_id="run-html",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "detail_html"
    continuation = paths.state_dir / "detail-live-liepin-detail-p0-smoke-001-continuation-after-detail_html.json"
    assert continuation.exists()
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["stopReason"] == "detail_html"
    assert summary["next_step"] == "calibrate_detail_api"


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
            if "resume-view" in expression and "res-2" in expression:
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
    assert all("res-1" not in expression for expression in expressions)


def test_run_live_detail_pack_runs_full_pack_and_writes_pack_summary(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_full_target_pack(
        paths.root,
        [_contact("res-1", 0), _contact("res-private", 1), _contact("res-3", 2)],
    )
    expressions: list[str] = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "res-1" in expression:
                return _success_detail("res-1")
            if "res-private" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 60,
                    "parseError": None,
                    "data": {"flag": 0, "code": "11000", "msg": "隐私保护", "data": {}},
                }
            if "res-3" in expression:
                return _success_detail("res-3")
            raise AssertionError(f"unexpected expression: {expression}")

        def close(self):
            pass

    _patch_liepin_target(monkeypatch, FakeSession)

    result = run_live_detail_pack(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        limit=100,
        delay_seconds=0,
        timeout_seconds=1,
        run_id="full-pack-001",
    )

    assert result["schema"] == "liepin_detail_pack_run_v1"
    assert result["status"] == "completed"
    assert result["completed"] == 2
    assert result["privacy_protected"] == 1
    job_dir = paths.root / "raw" / "detail-live" / "detail-p0-p1-pack-001"
    assert detail_job_path(job_dir, 0).exists()
    assert json.loads(detail_job_path(job_dir, 1).read_text(encoding="utf-8-sig"))["status"] == "privacy_protected"
    summary_path = paths.reports_dir / "detail-pack-detail-p0-p1-pack-001-summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    assert summary["schema"] == "liepin_detail_pack_summary_v1"
    assert summary["targets"] == 3
    assert summary["completed"] == 2
    assert summary["privacy_protected"] == 1
    assert not (paths.reports_dir / "detail-smoke-summary.json").exists()
    ledger = (paths.state_dir / "detail-request-ledger.jsonl").read_text(encoding="utf-8")
    assert '"event": "detail_completed"' in ledger
    assert '"event": "detail_privacy_protected"' in ledger


def test_run_live_detail_pack_exits_without_cdp_when_pack_already_terminal(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_full_target_pack(paths.root, [_contact("res-1", 0), _contact("res-private", 1)])
    job_dir = paths.root / "raw" / "detail-live" / "detail-p0-p1-pack-001"
    job_dir.mkdir(parents=True)
    detail_job_path(job_dir, 0).write_text(
        json.dumps({"schema": "liepin_detail_smoke_job_v1", "status": "done", "platform_id": "res-1"}),
        encoding="utf-8",
    )
    detail_job_path(job_dir, 1).write_text(
        json.dumps(
            {"schema": "liepin_detail_smoke_job_v1", "status": "privacy_protected", "platform_id": "res-private"}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(detail_gate, "list_targets", lambda cdp_url: (_ for _ in ()).throw(AssertionError("opened CDP")))
    monkeypatch.setattr(detail_gate, "CdpSession", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("opened session")))

    result = run_live_detail_pack(
        campaign_root=paths.root,
        target_pack="raw/detail-targets/detail-p0-p1-pack-001.json",
        cdp_url="http://127.0.0.1:9898",
        limit=100,
        delay_seconds=0,
        timeout_seconds=1,
        run_id="full-pack-resume",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 0
    assert result["skipped_terminal"] == 2
    summary = json.loads(
        (paths.reports_dir / "detail-pack-detail-p0-p1-pack-001-summary.json").read_text(encoding="utf-8-sig")
    )
    assert summary["status"] == "completed"
    assert summary["skipped_terminal"] == 2
    ledger = (paths.state_dir / "detail-request-ledger.jsonl").read_text(encoding="utf-8")
    assert '"event": "detail_pack_already_terminal"' in ledger


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
