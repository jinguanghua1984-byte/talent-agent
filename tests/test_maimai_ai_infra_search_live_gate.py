import json
from types import SimpleNamespace

import scripts.maimai_ai_infra_search_live_gate as live_gate
from scripts.maimai_ai_infra_search_live_gate import (
    CdpSession,
    api_block_reason,
    extract_contacts,
    find_talent_target,
    is_blocking_health,
    run_gate,
    search_expression,
    summarize_response,
    validate_search_template_status,
)


def test_find_talent_target_prefers_talent_bank_page():
    targets = [
        {"type": "page", "title": "下载", "url": "edge://downloads"},
        {
            "type": "page",
            "title": "人才银行",
            "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
            "webSocketDebuggerUrl": "ws://127.0.0.1/page/1",
        },
    ]

    target = find_talent_target(targets)

    assert target["title"] == "人才银行"
    assert target["webSocketDebuggerUrl"].endswith("/1")


def test_is_blocking_health_flags_login_or_captcha():
    assert is_blocking_health({"hasLoginPrompt": True}) == "login"
    assert is_blocking_health({"hasCaptcha": True}) == "captcha"
    assert is_blocking_health({"hasTalentBank": False}) == "not_talent_bank"
    assert is_blocking_health({"hasTalentBank": True, "hasCaptcha": False}) is None


def test_extract_contacts_supports_root_or_nested_data_lists():
    root = {"list": [{"id": 1, "name": "Alice"}]}
    nested = {"data": {"list": [{"id": 2, "name": "Bob"}]}}

    assert extract_contacts(root) == [{"id": 1, "name": "Alice"}]
    assert extract_contacts(nested) == [{"id": 2, "name": "Bob"}]


def test_summarize_response_marks_non_json_and_counts_list_items():
    parsed = {"total": 2, "total_match": 2, "count": 2, "list": [{"id": 1}, {"id": 2}]}

    summary = summarize_response(200, "application/json", json.dumps(parsed), parsed, None)

    assert summary["httpStatus"] == 200
    assert summary["parseError"] is None
    assert summary["data"]["total"] == 2
    assert summary["data"]["listLength"] == 2

    non_json = summarize_response(200, "text/html", "<html>login</html>", None, "invalid json")

    assert non_json["parseError"] == "invalid json"
    assert non_json["data"]["isObject"] is False


def test_api_block_reason_flags_432_and_api_captcha():
    assert api_block_reason(432, {"error_code": 30000}) == "http_432"
    assert api_block_reason(
        429,
        {"block_info": {"block_type": "captcha_yd", "captcha_type": "text_click"}},
    ) == "captcha_api"
    assert api_block_reason(429, {"error": "Request too frequently."}) == "http_429"
    assert api_block_reason(200, {"data": {"list": []}}) is None


def test_cdp_session_suppresses_origin_header(monkeypatch):
    calls = []

    def fake_create_connection(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(
            close=lambda: None,
            settimeout=lambda timeout: None,
            send=lambda payload: None,
            recv=lambda: json.dumps({"id": 1, "result": {"result": {"value": {"ok": True}}}}),
        )

    monkeypatch.setitem(
        __import__("sys").modules,
        "websocket",
        SimpleNamespace(create_connection=fake_create_connection),
    )

    session = CdpSession("ws://127.0.0.1:9888/devtools/page/1")
    try:
        assert session.evaluate("1") == {"ok": True}
    finally:
        session.close()

    assert calls[0][1]["suppress_origin"] is True


def test_validate_search_template_status_blocks_non_search_templates():
    valid = {
        "hasSearchTemplate": True,
        "url": "https://maimai.cn/api/ent/v3/search/basic?foo=1",
        "method": "POST",
        "hasBody": True,
        "hasSearchObject": True,
        "hasNestedQueryField": True,
        "hasNestedPagination": True,
    }

    assert validate_search_template_status(valid) is None

    invalid_url = dict(valid, url="https://maimai.cn/api/ent/v3/talent/detail")
    invalid_method = dict(valid, method="GET")
    invalid_body = dict(valid, hasNestedQueryField=False)

    assert validate_search_template_status(invalid_url) == "incompatible_request_shape"
    assert validate_search_template_status(invalid_method) == "incompatible_request_shape"
    assert validate_search_template_status(invalid_body) == "incompatible_request_shape"


def test_live_gate_search_expression_applies_confirmed_filters_only():
    expression = search_expression(
        "AI infra",
        1,
        30,
        {
            "positions": "模型训练,推理引擎",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
            "region_scope": "0,1",
            "schools": "浙大",
            "major": "软件工程",
            "min_age": "16",
            "max_age": "40",
            "query_relation": 1,
        },
    )

    assert "applyConfirmedSearchFilters" in expression
    assert "HIGH_RISK_FILTER_DEFAULTS" in expression
    assert '"positions": "模型训练,推理引擎"' in expression
    assert '"cities": ""' in expression
    assert '"provinces": ""' in expression
    assert '"ht_cities": ""' in expression
    assert '"ht_provinces": ""' in expression
    assert '"region_scope": "0,1"' in expression
    assert '"schools": "浙大"' in expression
    assert '"major": "软件工程"' in expression
    assert '"min_age": "16"' in expression
    assert '"max_age": "40"' in expression
    assert '"query_relation": 1' in expression
    assert "delete target.age" in expression
    assert "target[key] = value" in expression

    try:
        search_expression("AI infra", 1, 30, {"age": "32"})
    except ValueError as exc:
        assert "unconfirmed search filter field: search.age" in str(exc)
    else:
        raise AssertionError("unconfirmed filter should fail")


def test_run_gate_stops_before_fetch_when_template_shape_is_incompatible(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({"batches": [{"batch_id": "b1", "query": "AI infra", "page_size": 30}]}),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/talent/detail",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            raise AssertionError("search fetch should not be evaluated")

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "人才银行",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "incompatible_request_shape"
    assert result["batches"] == []
    saved = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert saved["stopReason"] == "incompatible_request_shape"


def test_run_gate_preserves_response_evidence(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({"batches": [{"batch_id": "b1", "query": "AI infra", "page_size": 30}]}),
        encoding="utf-8",
    )
    response_data = {"data": {"total": 1, "list": [{"id": "1", "name": "Alice"}]}}

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if self.calls == 3:
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 62,
                    "rawPreview": '{"data":{"total":1',
                    "parseError": None,
                    "data": response_data,
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "人才银行",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
    )

    batch = result["batches"][0]
    assert batch["responseData"] == response_data
    assert batch["responseRawPreview"] == '{"data":{"total":1'
    saved = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert saved["batches"][0]["responseData"]["data"]["list"][0]["name"] == "Alice"


def test_run_gate_fetches_all_pages_declared_by_batch(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({
            "gate": "S3",
            "batches": [{
                "batch_id": "b1",
                "query": "AI infra",
                "page_size": 30,
                "max_pages": 3,
            }],
        }),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0
            self.search_calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if "fetch(tpl.url" in expression:
                self.search_calls += 1
                page = self.search_calls
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 20,
                    "rawPreview": "{}",
                    "parseError": None,
                    "data": {"data": {"total": 3, "list": [{"id": str(page), "page": page}]}},
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "人才银行",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
    )

    batch = result["batches"][0]
    assert result["status"] == "completed"
    assert len(result["contacts"]) == 3
    assert len(batch["contacts"]) == 3
    assert [page["page"] for page in batch["pages"]] == [1, 2, 3]
    assert [item["page"] for item in batch["contacts"]] == [1, 2, 3]


def test_run_gate_can_continue_from_later_start_page(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({
            "gate": "S3",
            "batches": [{
                "batch_id": "b1",
                "query": "AI infra",
                "page_size": 30,
                "start_page": 2,
                "max_pages": 3,
            }],
        }),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0
            self.next_page = 2

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if "fetch(tpl.url" in expression:
                page = self.next_page
                self.next_page += 1
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 20,
                    "rawPreview": "{}",
                    "parseError": None,
                    "data": {"data": {"total": 3, "list": [{"id": str(page), "page": page}]}},
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "人才银行",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
    )

    assert [page["page"] for page in result["batches"][0]["pages"]] == [2, 3]
    assert [item["page"] for item in result["contacts"]] == [2, 3]


def test_run_gate_adaptive_quality_continues_good_unit_to_page_three(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    strategy_path = tmp_path / "strategy.json"
    page_quality_path = tmp_path / "reports" / "page-quality.jsonl"
    state_path = tmp_path / "state" / "adaptive-unit-state.json"
    seen_path = tmp_path / "state" / "seen-candidates.jsonl"
    plan_path.write_text(
        json.dumps(
            {
                "gate": "S3",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "unit_id": "unit-000001",
                        "query": "Acme AI",
                        "page_size": 30,
                        "max_pages": 2,
                        "unit_max_pages": 3,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    strategy_path.write_text(
        json.dumps(
            {
                "strategy_mode": "broad_recall_adaptive_v1",
                "company_pools": {"target": ["Acme"]},
                "position_aliases": ["AI"],
                "keyword_packages": [{"id": "p0", "keywords": ["LLM"], "position_terms": ["AI"]}],
                "adaptive_search": {"probe_pages": 2, "unit_max_pages": 3, "max_consecutive_low_quality_pages": 2},
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0
            self.search_calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if "fetch(tpl.url" in expression:
                self.search_calls += 1
                page = self.search_calls
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 20,
                    "rawPreview": "{}",
                    "parseError": None,
                    "data": {
                        "data": {
                            "total": 3,
                            "list": [
                                {
                                    "id": f"good-{page}",
                                    "company": "Acme",
                                    "title": "AI platform",
                                    "description": "LLM serving",
                                    "detail_url": f"https://maimai.cn/profile/{page}",
                                }
                            ],
                        }
                    },
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "talent bank",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
        adaptive_config_path=strategy_path,
        adaptive_state_out_path=state_path,
        seen_out_path=seen_path,
        page_quality_out_path=page_quality_path,
    )

    assert [page["page"] for page in result["batches"][0]["pages"]] == [1, 2, 3]
    assert result["batches"][0]["plannedMaxPage"] == 2
    assert result["batches"][0]["unitMaxPage"] == 3
    assert all(page["adaptiveQuality"]["quality_band"] == "good" for page in result["batches"][0]["pages"])
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "exhausted"
    assert len(page_quality_path.read_text(encoding="utf-8-sig").splitlines()) == 3


def test_run_gate_adaptive_quality_stops_low_unit_and_moves_to_next_batch(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    strategy_path = tmp_path / "strategy.json"
    state_path = tmp_path / "state" / "adaptive-unit-state.json"
    page_quality_path = tmp_path / "reports" / "page-quality.jsonl"
    plan_path.write_text(
        json.dumps(
            {
                "gate": "S3",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "unit_id": "unit-000001",
                        "query": "low",
                        "page_size": 30,
                        "max_pages": 2,
                        "unit_max_pages": 3,
                    },
                    {
                        "batch_id": "unit-000002",
                        "unit_id": "unit-000002",
                        "query": "next",
                        "page_size": 30,
                        "max_pages": 1,
                        "unit_max_pages": 1,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    strategy_path.write_text(
        json.dumps(
            {
                "strategy_mode": "broad_recall_adaptive_v1",
                "company_pools": {"target": ["Acme"]},
                "position_aliases": ["AI"],
                "keyword_packages": [{"id": "p0", "keywords": ["LLM"], "position_terms": ["AI"]}],
                "adaptive_search": {"probe_pages": 2, "unit_max_pages": 3, "max_consecutive_low_quality_pages": 2},
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0
            self.search_calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if "fetch(tpl.url" in expression:
                self.search_calls += 1
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 20,
                    "rawPreview": "{}",
                    "parseError": None,
                    "data": {
                        "data": {
                            "total": 1,
                            "list": [{"id": f"low-{self.search_calls}", "company": "Other", "title": "Sales"}],
                        }
                    },
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "talent bank",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
        adaptive_config_path=strategy_path,
        adaptive_state_out_path=state_path,
        page_quality_out_path=page_quality_path,
    )

    assert [page["page"] for page in result["batches"][0]["pages"]] == [1, 2]
    assert result["batches"][0]["plannedMaxPage"] == 2
    assert result["batches"][0]["unitMaxPage"] == 3
    assert result["batches"][0]["adaptiveStopReason"] == "stopped_low_quality"
    assert [page["page"] for page in result["batches"][1]["pages"]] == [1]
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "stopped_low_quality"
    assert state["units"]["unit-000002"]["status"] == "exhausted"


def test_run_gate_adaptive_max_live_pages_preserves_next_page_state(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    strategy_path = tmp_path / "strategy.json"
    state_path = tmp_path / "state" / "adaptive-unit-state.json"
    plan_path.write_text(
        json.dumps(
            {
                "gate": "S3",
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "unit_id": "unit-000001",
                        "query": "Acme AI",
                        "page_size": 30,
                        "max_pages": 2,
                        "unit_max_pages": 5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    strategy_path.write_text(
        json.dumps(
            {
                "strategy_mode": "broad_recall_adaptive_v1",
                "company_pools": {"target": ["Acme"]},
                "position_aliases": ["AI"],
                "keyword_packages": [{"id": "p0", "keywords": ["LLM"], "position_terms": ["AI"]}],
                "adaptive_search": {"probe_pages": 2, "unit_max_pages": 5, "max_consecutive_low_quality_pages": 2},
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0
            self.search_calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            if "fetch(tpl.url" in expression:
                self.search_calls += 1
                page = self.search_calls
                return {
                    "status": "ok",
                    "httpStatus": 200,
                    "contentType": "application/json",
                    "rawLength": 20,
                    "rawPreview": "{}",
                    "parseError": None,
                    "data": {"data": {"list": [{"id": f"good-{page}", "company": "Acme", "title": "AI"}]}},
                    "sent": {"url": "https://maimai.cn/api/ent/v3/search/basic"},
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "talent bank",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
        max_live_pages=3,
        adaptive_config_path=strategy_path,
        adaptive_state_out_path=state_path,
    )

    assert result["status"] == "completed_limited"
    assert result["stopReason"] == "max_live_pages"
    assert [page["page"] for page in result["batches"][0]["pages"]] == [1, 2, 3]
    state = json.loads(state_path.read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "active"
    assert state["units"]["unit-000001"]["next_page"] == 4


def test_run_gate_records_batch_exception_error(tmp_path, monkeypatch):
    plan_path = tmp_path / "plan.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({"batches": [{"batch_id": "b1", "query": "AI infra", "page_size": 30}]}),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if self.calls == 2:
                return {
                    "hasSearchTemplate": True,
                    "url": "https://maimai.cn/api/ent/v3/search/basic",
                    "method": "POST",
                    "hasBody": True,
                    "hasSearchObject": True,
                    "hasNestedQueryField": True,
                    "hasNestedPagination": True,
                }
            raise RuntimeError("network boom")

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "人才银行",
                "url": "https://maimai.cn/ent/v41/recruit/talents?tab=1",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_gate(
        plan_path=plan_path,
        out_path=out_path,
        cdp_url="http://127.0.0.1:9888",
        delay_seconds=0,
        timeout_seconds=1,
    )

    assert result["status"] == "stopped"
    assert result["stopReason"] == "exception"
    assert result["batches"][0]["error"] == "network boom"
    saved = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert saved["batches"][0]["error"] == "network boom"
