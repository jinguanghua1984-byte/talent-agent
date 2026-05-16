import json
from pathlib import Path

import scripts.maimai_ai_infra_detail_live_gate as live_gate
from scripts.maimai_ai_infra_detail_live_gate import (
    build_detail_urls,
    build_interruption_artifacts,
    is_detail_block,
    job_capture_entry,
    next_resume_index,
    run_gate,
)


def test_build_detail_urls_uses_expected_maimai_endpoints():
    urls = build_detail_urls({"id": "u123", "trackable_token": "tok"})

    assert urls["basic"].startswith("/api/ent/talent/basic?")
    assert "to_uid=u123" in urls["basic"]
    assert "trackable_token=tok" in urls["basic"]
    assert urls["projects"].startswith("/api/ent/candidate/associated/project/list?")
    assert urls["job_preference"].startswith("/api/ent/talent/job_preference?")
    assert urls["contact_btn"].startswith("/api/ent/v3/search/contact_btn?")


def test_detail_fetch_expression_uses_expected_endpoint_order_and_fetch_options():
    expression = live_gate._detail_fetch_expression({"id": "u123", "trackable_token": "tok"})

    assert 'const order = ["basic", "projects", "job_preference", "contact_btn"];' in expression
    assert 'method: "GET"' in expression
    assert 'credentials: "include"' in expression
    assert expression.index("/api/ent/talent/basic?") < expression.index("/api/ent/candidate/associated/project/list?")
    assert expression.index("/api/ent/candidate/associated/project/list?") < expression.index("/api/ent/talent/job_preference?")
    assert expression.index("/api/ent/talent/job_preference?") < expression.index("/api/ent/v3/search/contact_btn?")


def test_is_detail_block_catches_captcha_status_codes_and_non_json():
    assert is_detail_block({"httpStatus": 401, "data": {}}) == "http_401"
    assert is_detail_block({"httpStatus": 403, "data": {}}) == "http_403"
    assert is_detail_block({"httpStatus": 429, "data": {}}) == "http_429"
    assert is_detail_block({"httpStatus": 432, "data": {}}) == "http_432"
    assert is_detail_block({"httpStatus": 429, "parseError": "Unexpected token <"}) == "http_429"
    assert is_detail_block({"httpStatus": 200, "data": {"block_info": {"block_type": "captcha_yd"}}}) == "captcha_api"
    assert is_detail_block({"httpStatus": 200, "parseError": "non_json"}) == "non_json"
    assert is_detail_block({"httpStatus": 200, "data": {"data": {"id": "u1"}}}) is None


def test_job_capture_entry_matches_detail_import_contract():
    entry = job_capture_entry(
        contact={"id": "u1", "candidate_id": 1, "name": "张三"},
        index=0,
        result={
            "ok": True,
            "detail": {"id": "u1", "name": "张三"},
            "endpoints": {
                "basic": {"httpStatus": 200, "data": {"data": {"id": "u1", "name": "张三"}}},
                "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
            },
            "errors": [],
        },
    )

    assert entry["id"] == "u1"
    assert entry["status"] == "done"
    assert entry["detail"]["basic"]["id"] == "u1"
    assert entry["detail"]["projects"]["httpStatus"] == 200


def test_next_resume_index_skips_successful_job_raw(tmp_path: Path):
    contacts = [
        {"id": "u1", "candidate_id": 1},
        {"id": "u2", "candidate_id": 2},
        {"id": "u3", "candidate_id": 3},
    ]
    job_dir = tmp_path / "jobs"
    job_dir.mkdir()
    (job_dir / "job-000001-u1.json").write_text(
        json.dumps({"status": "done", "id": "u1", "detail": {"basic": {"id": "u1"}}}),
        encoding="utf-8-sig",
    )
    (job_dir / "job-000002-u2.json").write_text(
        json.dumps({"status": "failed", "id": "u2", "detail": {"basic": {"id": "u2"}}}),
        encoding="utf-8-sig",
    )

    assert next_resume_index(contacts, job_dir) == 1


def test_next_resume_index_returns_len_when_all_raw_jobs_succeeded(tmp_path: Path):
    contacts = [{"id": "u1"}, {"id": "u2"}]
    job_dir = tmp_path / "jobs"
    job_dir.mkdir()
    for index, contact in enumerate(contacts, start=1):
        (job_dir / f"job-{index:06d}-{contact['id']}.json").write_text(
            json.dumps({"status": "done", "id": contact["id"], "detail": {"basic": {"id": contact["id"]}}}),
            encoding="utf-8-sig",
        )

    assert next_resume_index(contacts, job_dir) == 2


def test_interruption_and_continuation_artifact_structure(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "capture.json"
    job_dir = campaign_root / "raw" / "detail-live" / "detail-ab-pack-001"
    contacts = [
        {"id": "u1", "candidate_id": 1},
        {"id": "u2", "candidate_id": 2},
    ]
    plan = {"metadata": {"pack_id": "detail-ab-pack-001"}, "contacts": contacts}

    artifacts = build_interruption_artifacts(
        plan=plan,
        plan_path=plan_path,
        out_path=out_path,
        job_dir=job_dir,
        failed_index=1,
        stop_reason="captcha_api",
        before_health={"hasTalentBank": True},
        after_health={"hasCaptcha": True},
        failed_endpoint="basic",
        endpoint_result={
            "httpStatus": 429,
            "data": {"block_info": {"block_type": "captcha_yd", "captcha_type": "text_click"}},
            "rawPreview": '{"block_info":{"block_type":"captcha_yd"}}',
        },
    )

    report = artifacts["report"]
    continuation = artifacts["continuation"]
    assert report["stopReason"] == "captcha_api"
    assert report["failedIndex"] == 1
    assert report["failedCandidateId"] == 2
    assert report["lastSuccessIndex"] == 0
    assert report["standardizedJobs"] == 1
    assert report["remainingJobs"] == 1
    assert report["downstreamNotRun"]["detailWaveApply"] is True
    assert continuation["resume_from"]["platform_id"] == "u2"
    assert continuation["completed_job_dir"] == str(job_dir)
    assert artifacts["continuation_path"].name.startswith("detail-live-detail-ab-pack-001-continuation-after-captcha_api")
    assert artifacts["report_path"].name.startswith("interruption-detail-detail-ab-pack-001-")


def test_run_gate_health_check_only_does_not_fetch(tmp_path: Path, monkeypatch):
    plan_path = tmp_path / "campaign" / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = tmp_path / "campaign" / "raw" / "capture.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps({"metadata": {"pack_id": "detail-ab-pack-001"}, "contacts": [{"id": "u1"}]}),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            raise AssertionError("health-check-only should not run detail fetch")

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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1, health_check_only=True)

    assert result["status"] == "health_ok"
    assert json.loads(out_path.read_text(encoding="utf-8-sig"))["status"] == "health_ok"


def test_run_gate_writes_job_raw_and_rebuilds_capture(tmp_path: Path, monkeypatch):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "detail-live-detail-ab-pack-001-run.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {
                "metadata": {"pack_id": "detail-ab-pack-001"},
                "contacts": [{"id": "u1", "trackable_token": "t1", "candidate_id": 1, "name": "张三"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "detailEndpointUrls" in expression:
                return {
                    "ok": True,
                    "endpoints": {
                        "basic": {"httpStatus": 200, "data": {"data": {"id": "u1", "name": "张三"}}},
                        "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                        "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                        "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
                    },
                    "detail": {"id": "u1", "name": "张三"},
                    "errors": [],
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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1)

    assert result["status"] == "completed"
    job_raw = campaign_root / "raw" / "detail-live" / "detail-ab-pack-001" / "job-000001-u1.json"
    assert job_raw.exists()
    capture = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert capture["metadata"]["status"] == "completed"
    assert capture["metadata"]["partial"] is False
    assert capture["metadata"]["completed_jobs"] == 1
    assert capture["detailJobs"][0]["detail"]["basic"]["id"] == "u1"
    from scripts.maimai_detail_import import extract_detail_entries

    entries, failed_jobs = extract_detail_entries(capture, out_path)
    assert failed_jobs == 0
    assert len(entries) == 1
    assert entries[0].platform_id == "u1"


def test_run_gate_stops_and_writes_interruption_on_block(tmp_path: Path, monkeypatch):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "detail-live-detail-ab-pack-001-run.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {
                "metadata": {"pack_id": "detail-ab-pack-001"},
                "contacts": [
                    {"id": "u1", "trackable_token": "t1", "candidate_id": 1},
                    {"id": "u2", "trackable_token": "t2", "candidate_id": 2},
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "detailEndpointUrls" in expression:
                return {
                    "ok": False,
                    "failedEndpoint": "basic",
                    "endpoints": {
                        "basic": {
                            "httpStatus": 429,
                            "parseError": None,
                            "data": {"block_info": {"block_type": "captcha_yd"}},
                            "rawPreview": '{"block_info":{"block_type":"captcha_yd"}}',
                        }
                    },
                    "errors": ["http_429"],
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": True}

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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1)

    assert result["status"] == "stopped"
    assert result["stopReason"] == "http_429"
    report = next((campaign_root / "reports").glob("interruption-detail-detail-ab-pack-001-*.json"))
    continuation = plan_path.parent / "detail-live-detail-ab-pack-001-continuation-after-http_429-plan.json"
    assert json.loads(report.read_text(encoding="utf-8-sig"))["failedPlatformId"] == "u1"
    assert json.loads(continuation.read_text(encoding="utf-8-sig"))["resume_from"]["index"] == 0
    capture = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert capture["metadata"]["status"] == "stopped"
    assert capture["metadata"]["partial"] is True
    assert capture["metadata"]["stopReason"] == "http_429"
    assert capture["metadata"]["interruptionReport"] == str(report)
    assert capture["metadata"]["continuationPlan"] == str(continuation)


def test_run_gate_stops_on_basic_payload_drift_without_job_raw(tmp_path: Path, monkeypatch):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "detail-live-detail-ab-pack-001-run.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {
                "metadata": {"pack_id": "detail-ab-pack-001"},
                "contacts": [{"id": "u1", "trackable_token": "t1", "candidate_id": 1}],
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "detailEndpointUrls" in expression:
                return {
                    "ok": True,
                    "failedEndpoint": None,
                    "endpoints": {
                        "basic": {"httpStatus": 200, "data": {"code": 0, "msg": "ok"}},
                        "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                        "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                        "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
                    },
                    "detail": {"code": 0, "msg": "ok"},
                    "errors": [],
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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1)

    assert result["status"] == "stopped"
    assert result["stopReason"] == "detail_template_drift"
    assert Path(result["interruptionReport"]).exists()
    assert Path(result["continuationPlan"]).exists()
    job_raw = campaign_root / "raw" / "detail-live" / "detail-ab-pack-001" / "job-000001-u1.json"
    assert not job_raw.exists()
    capture = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert capture["metadata"]["status"] == "stopped"
    assert capture["metadata"]["partial"] is True
    assert capture["metadata"]["stopReason"] == "detail_template_drift"
    assert capture["metadata"]["completed_jobs"] == 0
    assert capture["detailJobs"] == []


def test_run_gate_max_jobs_returns_completed_limited_for_partial_pack(tmp_path: Path, monkeypatch):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "detail-live-detail-ab-pack-001-run.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {
                "metadata": {"pack_id": "detail-ab-pack-001"},
                "contacts": [
                    {"id": "u1", "trackable_token": "t1", "candidate_id": 1},
                    {"id": "u2", "trackable_token": "t2", "candidate_id": 2},
                ],
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "detailEndpointUrls" in expression:
                return {
                    "ok": True,
                    "endpoints": {
                        "basic": {"httpStatus": 200, "data": {"data": {"id": "u1", "name": "A"}}},
                        "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                        "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                        "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
                    },
                    "detail": {"id": "u1", "name": "A"},
                    "errors": [],
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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1, max_jobs=1)

    assert result["status"] == "completed_limited"
    assert result["completed_jobs"] == 1
    capture = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert capture["metadata"]["status"] == "completed_limited"
    assert capture["metadata"]["partial"] is True
    assert capture["metadata"]["completed_jobs"] == 1
    assert capture["metadata"]["total_contacts"] == 2


def test_run_gate_health_block_after_last_success_writes_status_and_completed_resume(tmp_path: Path, monkeypatch):
    campaign_root = tmp_path / "campaign"
    plan_path = campaign_root / "raw" / "detail-targets" / "detail-ab-pack-001.json"
    out_path = campaign_root / "raw" / "detail-live-detail-ab-pack-001-run.json"
    plan_path.parent.mkdir(parents=True)
    plan_path.write_text(
        json.dumps(
            {
                "metadata": {"pack_id": "detail-ab-pack-001"},
                "contacts": [{"id": "u1", "trackable_token": "t1", "candidate_id": 1}],
            }
        ),
        encoding="utf-8",
    )

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": False}
            if "detailEndpointUrls" in expression:
                return {
                    "ok": True,
                    "endpoints": {
                        "basic": {"httpStatus": 200, "data": {"data": {"id": "u1", "name": "A"}}},
                        "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                        "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                        "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
                    },
                    "detail": {"id": "u1", "name": "A"},
                    "errors": [],
                }
            return {"hasTalentBank": True, "hasLoginPrompt": False, "hasCaptcha": True}

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

    result = run_gate(plan_path, out_path, "http://127.0.0.1:9888", 0, 1)

    assert result["status"] == "stopped"
    assert result["stopReason"] == "captcha"
    assert result["completed_jobs"] == 1
    assert Path(result["interruptionReport"]).exists()
    assert Path(result["continuationPlan"]).exists()
    capture = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert capture["metadata"]["status"] == "stopped"
    assert capture["metadata"]["partial"] is True
    assert capture["metadata"]["interruptionReport"] == result["interruptionReport"]
    assert capture["metadata"]["continuationPlan"] == result["continuationPlan"]
    continuation = json.loads(Path(result["continuationPlan"]).read_text(encoding="utf-8-sig"))
    assert continuation["resume_from"] == {
        "index": 1,
        "candidate_id": None,
        "platform_id": "",
        "completed": True,
    }


def test_main_returns_zero_for_completed_limited(monkeypatch, tmp_path: Path):
    out_path = tmp_path / "capture.json"

    monkeypatch.setattr(
        live_gate,
        "run_gate",
        lambda **kwargs: {
            "status": "completed_limited",
            "pack_id": "detail-ab-pack-001",
            "completed_jobs": 1,
        },
    )

    assert live_gate.main(["--plan", str(tmp_path / "plan.json"), "--out", str(out_path), "--max-jobs", "1"]) == 0


def test_main_returns_two_for_stopped(monkeypatch, tmp_path: Path):
    out_path = tmp_path / "capture.json"

    monkeypatch.setattr(live_gate, "run_gate", lambda **kwargs: {"status": "stopped"})

    assert live_gate.main(["--plan", str(tmp_path / "plan.json"), "--out", str(out_path)]) == 2


def test_main_returns_two_for_blocked(monkeypatch, tmp_path: Path):
    out_path = tmp_path / "capture.json"

    monkeypatch.setattr(live_gate, "run_gate", lambda **kwargs: {"status": "blocked"})

    assert live_gate.main(["--plan", str(tmp_path / "plan.json"), "--out", str(out_path)]) == 2


def test_main_returns_one_for_unknown_status(monkeypatch, tmp_path: Path):
    out_path = tmp_path / "capture.json"

    monkeypatch.setattr(live_gate, "run_gate", lambda **kwargs: {"status": "weird"})

    assert live_gate.main(["--plan", str(tmp_path / "plan.json"), "--out", str(out_path)]) == 1
