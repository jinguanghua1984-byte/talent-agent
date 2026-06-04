import json
from pathlib import Path
from types import SimpleNamespace

import scripts.liepin_detail_api_calibrator as calibrator
from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_api_calibrator import (
    CdpNetworkSession,
    calibrate_detail_api,
    detail_calibration_health_expression,
    find_detail_calibration_target,
    summarize_detail_api_candidate,
)


def test_find_detail_calibration_target_prefers_detail_tab_and_requires_websocket():
    target = find_detail_calibration_target(
        [
            {
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem#session",
                "webSocketDebuggerUrl": "ws://search",
            },
            {
                "type": "page",
                "title": "NO.abc",
                "url": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
                "webSocketDebuggerUrl": "ws://detail",
            },
        ]
    )

    assert target["webSocketDebuggerUrl"] == "ws://detail"


def test_detail_calibration_health_expression_does_not_treat_recent_login_as_prompt():
    expression = detail_calibration_health_expression()

    assert "扫码登录|手机号登录|密码登录|立即登录|请登录|登录后" in expression
    assert "/登录|" not in expression
    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression


def test_calibrate_detail_api_uses_detail_tab_and_sanitizes_page_target(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.websocket_url = websocket_url

        def call(self, method, params=None, timeout=30):
            if method == "Runtime.evaluate":
                return {"result": {"value": {"hasLiepinDetail": True, "hasLoginPrompt": False, "hasCaptcha": False}}}
            return {}

        def recv_event(self, timeout=30):
            return None

        def close(self):
            pass

    monkeypatch.setattr(
        calibrator,
        "list_targets",
        lambda cdp_url: [
            {
                "id": "search",
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem#session",
                "webSocketDebuggerUrl": "ws://search",
            },
            {
                "id": "detail",
                "type": "page",
                "title": "NO.res-1",
                "url": "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1&ck_id=secret",
                "webSocketDebuggerUrl": "ws://detail",
            },
        ],
    )
    monkeypatch.setattr(calibrator, "CdpNetworkSession", FakeSession)

    result = calibrate_detail_api(
        campaign_root=paths.root,
        cdp_url="http://127.0.0.1:9898",
        listen_seconds=0,
        timeout_seconds=1,
        run_id="calib-detail-target",
    )

    dumped = json.dumps(result, ensure_ascii=False)
    assert result["status"] == "no_candidates"
    assert result["pageTarget"]["id"] == "detail"
    assert result["pageTarget"]["url"] == "https://h.liepin.com/resume/showresumedetail/"
    assert "res-1" not in dumped
    assert "ck_id" not in dumped
    assert "secret" not in dumped


def test_summarize_detail_api_candidate_redacts_url_headers_and_values():
    candidate = summarize_detail_api_candidate(
        request={
            "requestId": "1",
            "request": {
                "url": "https://api-h.liepin.com/api/resume/detail?res_id_encode=res-1&ck_id=secret",
                "method": "POST",
                "headers": {
                    "Accept": "application/json",
                    "Cookie": "sid=secret",
                    "X-Fscp-Trace-Id": "trace-secret",
                },
                "postData": "payload=%7B%22resIdEncode%22%3A%22res-1%22%2C%22secret%22%3A%22x%22%7D",
            },
            "type": "XHR",
        },
        response={
            "response": {
                "status": 200,
                "mimeType": "application/json",
                "url": "https://api-h.liepin.com/api/resume/detail?res_id_encode=res-1&ck_id=secret",
            }
        },
        body_text='{"flag":1,"data":{"name":"张三","workExperience":[]}}',
    )

    dumped = json.dumps(candidate, ensure_ascii=False)
    assert candidate["host"] == "api-h.liepin.com"
    assert candidate["path"] == "/api/resume/detail"
    assert candidate["queryKeys"] == ["ck_id", "res_id_encode"]
    assert candidate["method"] == "POST"
    assert candidate["requestPayloadKeys"] == ["payload"]
    assert candidate["responseTopLevelKeys"] == ["data", "flag"]
    assert candidate["responseDataKeys"] == ["name", "workExperience"]
    assert "Cookie" not in dumped
    assert "sid=secret" not in dumped
    assert "trace-secret" not in dumped
    assert "res-1" not in dumped
    assert "张三" not in dumped


def test_summarize_detail_api_candidate_reports_nested_payload_and_response_keys_without_values():
    candidate = summarize_detail_api_candidate(
        request={
            "type": "XHR",
            "request": {
                "url": "https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view",
                "method": "POST",
                "headers": {"Accept": "application/json"},
                "postData": "paramForm=%7B%22resIdEncode%22%3A%22res-1%22%2C%22usercIdEncode%22%3A%22user-1%22%7D",
            },
        },
        response={
            "type": "XHR",
            "response": {
                "status": 200,
                "mimeType": "application/json",
                "url": "https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view",
            },
        },
        body_text='{"flag":1,"data":{"resumeDetailVo":{"baseInfo":{"name":"张三"},"workExpList":[]}}}',
    )

    dumped = json.dumps(candidate, ensure_ascii=False)
    assert candidate["requestNestedPayloadKeys"] == {"paramForm": ["resIdEncode", "usercIdEncode"]}
    assert candidate["responseNestedDataKeys"] == {"resumeDetailVo": ["baseInfo", "workExpList"]}
    assert "res-1" not in dumped
    assert "user-1" not in dumped
    assert "张三" not in dumped


def test_calibrate_detail_api_passively_captures_json_candidates(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.messages = [
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "requestId": "req-1",
                        "type": "XHR",
                        "request": {
                            "url": "https://api-h.liepin.com/api/resume/detail?res_id_encode=res-1",
                            "method": "GET",
                            "headers": {"Cookie": "sid=secret", "Accept": "application/json"},
                        },
                    },
                },
                {
                    "method": "Network.responseReceived",
                    "params": {
                        "requestId": "req-1",
                        "type": "XHR",
                        "response": {
                            "url": "https://api-h.liepin.com/api/resume/detail?res_id_encode=res-1",
                            "status": 200,
                            "mimeType": "application/json",
                        },
                    },
                },
                {"method": "Network.loadingFinished", "params": {"requestId": "req-1"}},
            ]
            self.calls = []

        def call(self, method, params=None, timeout=30):
            self.calls.append(method)
            if method == "Runtime.evaluate":
                return {"result": {"value": {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}}}
            if method == "Network.getResponseBody":
                return {"body": '{"flag":1,"data":{"name":"张三","workExperience":[]}}'}
            return {}

        def recv_event(self, timeout=30):
            if self.messages:
                return self.messages.pop(0)
            return None

        def close(self):
            self.calls.append("close")

    monkeypatch.setattr(calibrator, "list_targets", lambda cdp_url: [{"type": "page", "url": "https://h.liepin.com/search/getConditionItem", "webSocketDebuggerUrl": "ws://example"}])
    monkeypatch.setattr(calibrator, "CdpNetworkSession", FakeSession)

    result = calibrate_detail_api(
        campaign_root=paths.root,
        cdp_url="http://127.0.0.1:9898",
        listen_seconds=0,
        timeout_seconds=1,
        run_id="calib-001",
    )

    assert result["status"] == "captured"
    assert result["candidate_count"] == 1
    report = json.loads((paths.reports_dir / "detail-api-calibration-calib-001.json").read_text(encoding="utf-8-sig"))
    dumped = json.dumps(report, ensure_ascii=False)
    assert report["candidates"][0]["path"] == "/api/resume/detail"
    assert "sid=secret" not in dumped
    assert "res-1" not in dumped
    assert "张三" not in dumped


def test_calibrate_detail_api_captures_api_response_when_mime_is_plain(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.messages = [
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "requestId": "req-resume",
                        "type": "XHR",
                        "request": {
                            "url": "https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view",
                            "method": "POST",
                            "headers": {"Accept": "*/*"},
                            "postData": "resIdEncode=res-1&usercIdEncode=user-1",
                        },
                    },
                },
                {
                    "method": "Network.responseReceived",
                    "params": {
                        "requestId": "req-resume",
                        "type": "XHR",
                        "response": {
                            "url": "https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view",
                            "status": 200,
                            "mimeType": "text/plain",
                        },
                    },
                },
                {"method": "Network.loadingFinished", "params": {"requestId": "req-resume"}},
            ]

        def call(self, method, params=None, timeout=30):
            if method == "Runtime.evaluate":
                return {"result": {"value": {"hasLiepinDetail": True, "hasLoginPrompt": False, "hasCaptcha": False}}}
            if method == "Network.getResponseBody":
                return {"body": '{"flag":1,"data":{"baseInfo":{},"workExperience":[]}}'}
            return {}

        def recv_event(self, timeout=30):
            if self.messages:
                return self.messages.pop(0)
            return None

        def close(self):
            pass

    monkeypatch.setattr(calibrator, "list_targets", lambda cdp_url: [{"type": "page", "url": "https://h.liepin.com/resume/showresumedetail/", "webSocketDebuggerUrl": "ws://detail"}])
    monkeypatch.setattr(calibrator, "CdpNetworkSession", FakeSession)

    result = calibrate_detail_api(
        campaign_root=paths.root,
        cdp_url="http://127.0.0.1:9898",
        listen_seconds=0,
        timeout_seconds=1,
        run_id="calib-plain",
    )

    assert result["status"] == "captured"
    assert result["candidates"][0]["path"] == "/api/com.liepin.rresume.userh.pc.resume-view"
    assert result["candidates"][0]["requestPayloadKeys"] == ["resIdEncode", "usercIdEncode"]
    assert result["candidates"][0]["responseDataKeys"] == ["baseInfo", "workExperience"]


def test_calibrate_detail_api_keeps_listening_after_idle_event(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.messages = [
                None,
                {
                    "method": "Network.requestWillBeSent",
                    "params": {
                        "requestId": "req-1",
                        "type": "XHR",
                        "request": {
                            "url": "https://api-h.liepin.com/api/resume/detail",
                            "method": "GET",
                            "headers": {"Accept": "application/json"},
                        },
                    },
                },
                {
                    "method": "Network.responseReceived",
                    "params": {
                        "requestId": "req-1",
                        "type": "XHR",
                        "response": {
                            "url": "https://api-h.liepin.com/api/resume/detail",
                            "status": 200,
                            "mimeType": "application/json",
                        },
                    },
                },
                {"method": "Network.loadingFinished", "params": {"requestId": "req-1"}},
            ]

        def call(self, method, params=None, timeout=30):
            if method == "Runtime.evaluate":
                return {"result": {"value": {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}}}
            if method == "Network.getResponseBody":
                return {"body": '{"flag":1,"data":{"workExperience":[]}}'}
            return {}

        def recv_event(self, timeout=30):
            if self.messages:
                return self.messages.pop(0)
            return None

        def close(self):
            pass

    ticks = iter([0, 1, 1, 1, 1, 4])
    monkeypatch.setattr(calibrator.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(calibrator, "list_targets", lambda cdp_url: [{"type": "page", "url": "https://h.liepin.com/search/getConditionItem", "webSocketDebuggerUrl": "ws://example"}])
    monkeypatch.setattr(calibrator, "CdpNetworkSession", FakeSession)

    result = calibrate_detail_api(
        campaign_root=paths.root,
        cdp_url="http://127.0.0.1:9898",
        listen_seconds=3,
        timeout_seconds=1,
        run_id="calib-idle",
    )

    assert result["status"] == "captured"
    assert result["candidate_count"] == 1


def test_cdp_network_session_recv_event_returns_none_on_websocket_timeout(monkeypatch):
    class FakeTimeout(Exception):
        pass

    def fake_create_connection(url, **kwargs):
        return SimpleNamespace(
            close=lambda: None,
            settimeout=lambda timeout: None,
            send=lambda payload: None,
            recv=lambda: (_ for _ in ()).throw(FakeTimeout("timed out")),
        )

    monkeypatch.setitem(
        __import__("sys").modules,
        "websocket",
        SimpleNamespace(create_connection=fake_create_connection),
    )

    session = CdpNetworkSession("ws://127.0.0.1/devtools/page/1")
    try:
        assert session.recv_event(timeout=0) is None
    finally:
        session.close()
