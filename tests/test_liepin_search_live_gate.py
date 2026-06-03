import json
from types import SimpleNamespace
from pathlib import Path

import scripts.liepin_search_live_gate as live_gate
from scripts.liepin_search_live_gate import (
    CdpSession,
    find_liepin_target,
    health_expression,
    is_blocking_health,
    run_live_search,
)
from scripts.liepin_campaign_orchestrator import init_campaign, plan_pages


def test_find_liepin_target_prefers_resume_search_page():
    targets = [
        {"type": "page", "title": "其他页", "url": "https://h.liepin.com/home"},
        {
            "type": "page",
            "title": "找简历",
            "url": "https://h.liepin.com/search/getConditionItem#session",
            "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
        },
    ]

    target = find_liepin_target(targets)

    assert target["title"] == "找简历"
    assert target["webSocketDebuggerUrl"].endswith("/1")


def test_is_blocking_health_flags_login_captcha_or_wrong_page():
    assert is_blocking_health({"hasLoginPrompt": True}) == "login"
    assert is_blocking_health({"hasCaptcha": True}) == "captcha"
    assert is_blocking_health({"hasLiepinSearch": False}) == "not_liepin_search"
    assert is_blocking_health({"hasLiepinSearch": True, "hasCaptcha": False}) is None


def test_health_expression_does_not_read_sensitive_browser_storage():
    expression = health_expression()

    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression
    assert "document.body" in expression


def test_cdp_session_evaluates_expression_with_return_by_value(monkeypatch):
    calls = []

    def fake_create_connection(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(
            close=lambda: None,
            settimeout=lambda timeout: None,
            send=lambda payload: calls.append(("send", json.loads(payload))),
            recv=lambda: json.dumps({"id": 1, "result": {"result": {"value": {"ok": True}}}}),
        )

    monkeypatch.setitem(
        __import__("sys").modules,
        "websocket",
        SimpleNamespace(create_connection=fake_create_connection),
    )

    session = CdpSession("ws://127.0.0.1:9898/devtools/page/1")
    try:
        assert session.evaluate("1") == {"ok": True}
    finally:
        session.close()

    assert calls[0][1]["suppress_origin"] is True
    sent = calls[1][1]
    assert sent["method"] == "Runtime.evaluate"
    assert sent["params"]["awaitPromise"] is True
    assert sent["params"]["returnByValue"] is True


def test_run_live_search_writes_condition_search_raw_and_summary(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    plan_pages(root)

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "get-search-condition-by-job" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 120,
                    "rawPreview": '{"flag":1}',
                    "parseError": None,
                    "data": {
                        "flag": 1,
                        "data": {
                            "workYearsLow": 3,
                            "workYearsHigh": 99,
                            "eduLevels": ["040", "030"],
                            "eduLevelTz": True,
                            "wantDqsOut": [{"dqCode": "010"}],
                            "searchType": "1",
                            "sortType": "0",
                        },
                    },
                }
            if "search-resumes" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 200,
                    "rawPreview": '{"flag":1,"data":{"cardResList":[]}}',
                    "parseError": None,
                    "data": {
                        "flag": 1,
                        "data": {
                            "ckId": "ck-1",
                            "skId": "sk-1",
                            "fkId": "fk-1",
                            "cardResList": [],
                        },
                    },
                }
            raise AssertionError(f"unexpected expression: {expression}")

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
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
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_live_search(
        campaign_root=root,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        max_pages=1,
        run_id="run-001",
    )

    assert result["status"] == "completed"
    assert result["pagesCompleted"] == [0]
    condition = json.loads((root / "raw" / "condition" / "job-75703601.json").read_text(encoding="utf-8-sig"))
    search = json.loads((root / "raw" / "search" / "page-000.json").read_text(encoding="utf-8-sig"))
    summary = json.loads((root / "reports" / "live-search-run-run-001.json").read_text(encoding="utf-8-sig"))
    ledger = (root / "state" / "request-ledger.jsonl").read_text(encoding="utf-8")
    assert condition["payload"]["flag"] == 1
    assert search["curPage"] == 0
    assert search["payload"]["data"]["ckId"] == "ck-1"
    assert summary["status"] == "completed"
    assert '"event": "page_completed"' in ledger


def test_run_live_search_stops_on_api_block_and_writes_continuation(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    plan_pages(root)

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "get-search-condition-by-job" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 80,
                    "rawPreview": '{"flag":1}',
                    "parseError": None,
                    "data": {"flag": 1, "data": {"searchType": "1", "sortType": "0"}},
                }
            if "search-resumes" in expression:
                return {
                    "status": "ok",
                    "httpStatus": 429,
                    "contentType": "application/json",
                    "rawLength": 40,
                    "rawPreview": '{"flag":0}',
                    "parseError": None,
                    "data": {"flag": 0, "msg": "too many requests"},
                }
            raise AssertionError("unexpected expression")

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
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
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_live_search(
        campaign_root=root,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        max_pages=1,
        run_id="run-002",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "http_429"
    assert not (root / "raw" / "search" / "page-000.json").exists()
    continuation = json.loads((root / "state" / "continuation-plan.json").read_text(encoding="utf-8-sig"))
    assert continuation["next_cur_page"] == 0
    assert continuation["reason"] == "http_429"
    interruptions = sorted((root / "reports").glob("interruption-http_429-*.json"))
    assert len(interruptions) == 1
