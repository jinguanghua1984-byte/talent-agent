import json
from pathlib import Path

import scripts.liepin_adaptive_search_live_gate as adaptive_live
from scripts.liepin_adaptive_search_live_gate import run_live_adaptive_search_wave
from scripts.liepin_campaign import atomic_write_json
from scripts.liepin_campaign_orchestrator import init_campaign


def _api_response(cards: list[dict]) -> dict:
    return {
        "status": "ok",
        "httpStatus": 200,
        "contentType": "application/json",
        "rawLength": 200,
        "rawPreview": '{"flag":1}',
        "parseError": None,
        "data": {
            "flag": 1,
            "data": {
                "ckId": "ck-1",
                "skId": "sk-1",
                "fkId": "fk-1",
                "cardResList": cards,
            },
        },
    }


def _card(platform_id: str, company: str, title: str) -> dict:
    return {
        "usercIdEncode": f"user-{platform_id}",
        "simpleResumeForm": {
            "resIdEncode": platform_id,
            "resCompany": company,
            "resTitle": title,
        },
    }


def _write_wave_plan(root: Path, *, unit_max_pages: int = 3) -> Path:
    sidecar = root / "raw" / "search-live-runs" / "search-wave-001-plan.json"
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(
        json.dumps(
            {
                "schema": "liepin_adaptive_search_live_gate_plan_v1",
                "wave_id": "search-wave-001",
                "strategy_mode": "liepin_broad_recall_adaptive_v1",
                "page_count": 2,
                "batches": [
                    {
                        "unit_id": "unit-000001",
                        "query": "腾讯 产品 大模型",
                        "pages": [0, 1],
                        "search_params_overrides": {"keyword": "腾讯 产品 大模型", "pageSize": 30},
                        "adaptive_search": {
                            "probe_pages": 2,
                            "unit_max_pages": unit_max_pages,
                            "good_ratio_continue": 0.3,
                            "good_ratio_observe": 0.1,
                            "max_consecutive_low_quality_pages": 2,
                        },
                        "unit_max_pages": unit_max_pages,
                    }
                ],
                "no_live_request": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return sidecar


def _patch_browser(monkeypatch, responses: list[dict]) -> list[str]:
    expressions = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return responses.pop(0)

        def close(self):
            pass

    monkeypatch.setattr(
        adaptive_live,
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
    monkeypatch.setattr(adaptive_live, "CdpSession", FakeSession)
    return expressions


def _write_existing_raw(root: Path, *, page: int, cards: list[dict]) -> Path:
    path = root / "raw/search-adaptive/search-wave-001/unit-000001" / f"page-{page:03d}.json"
    atomic_write_json(
        path,
        {
            "schema": "liepin_adaptive_search_page_v1",
            "wave_id": "search-wave-001",
            "unit_id": "unit-000001",
            "curPage": page,
            "payload": _api_response(cards)["data"],
            "request": {"url": "https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes"},
            "responseSummary": {"httpStatus": 200, "contentType": "application/json", "rawLength": 200},
            "run_id": "previous-run",
        },
    )
    return path


def test_adaptive_wave_continues_good_unit_to_runtime_page_three(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    wave_plan = _write_wave_plan(root, unit_max_pages=3)
    _patch_browser(
        monkeypatch,
        [
            _api_response([_card("res-1", "腾讯", "大模型产品经理")]),
            _api_response([_card("res-2", "腾讯", "AI 产品负责人")]),
            _api_response([_card("res-3", "腾讯", "产品总监")]),
        ],
    )

    result = run_live_adaptive_search_wave(
        campaign_root=root,
        wave_plan=wave_plan,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="adaptive-001",
    )

    assert result["status"] == "completed"
    assert result["pagesCompleted"] == [
        {"unit_id": "unit-000001", "page": 0},
        {"unit_id": "unit-000001", "page": 1},
        {"unit_id": "unit-000001", "page": 2},
    ]
    assert (root / "raw/search-adaptive/search-wave-001/unit-000001/page-002.json").exists()
    quality_rows = (root / "reports/page-quality-search-wave-001.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(quality_rows) == 3
    state = json.loads((root / "state/adaptive-unit-state-search-wave-001.json").read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "exhausted"


def test_adaptive_wave_stops_after_consecutive_low_quality_pages(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    wave_plan = _write_wave_plan(root, unit_max_pages=3)
    _patch_browser(
        monkeypatch,
        [
            _api_response([_card("res-1", "外包公司", "销售")]),
            _api_response([_card("res-2", "咨询公司", "行政")]),
        ],
    )

    result = run_live_adaptive_search_wave(
        campaign_root=root,
        wave_plan=wave_plan,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="adaptive-low",
    )

    assert result["status"] == "completed"
    assert result["pagesCompleted"] == [
        {"unit_id": "unit-000001", "page": 0},
        {"unit_id": "unit-000001", "page": 1},
    ]
    assert not (root / "raw/search-adaptive/search-wave-001/unit-000001/page-002.json").exists()
    state = json.loads((root / "state/adaptive-unit-state-search-wave-001.json").read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "stopped_low_quality"
    assert state["units"]["unit-000001"]["stop_reason"] == "consecutive_low_quality_pages"


def test_adaptive_wave_resume_skips_existing_raw_and_requests_next_missing_page(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    wave_plan = _write_wave_plan(root, unit_max_pages=3)
    _write_existing_raw(root, page=0, cards=[_card("res-1", "腾讯", "大模型产品经理")])
    expressions = _patch_browser(
        monkeypatch,
        [
            _api_response([_card("res-2", "腾讯", "AI 产品负责人")]),
            _api_response([_card("res-3", "腾讯", "产品总监")]),
        ],
    )

    result = run_live_adaptive_search_wave(
        campaign_root=root,
        wave_plan=wave_plan,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="adaptive-resume",
    )

    assert result["status"] == "completed"
    assert result["pagesSkipped"] == [{"unit_id": "unit-000001", "page": 0, "reason": "raw_exists"}]
    assert result["pagesCompleted"] == [
        {"unit_id": "unit-000001", "page": 1},
        {"unit_id": "unit-000001", "page": 2},
    ]
    assert len(expressions) == 3
    assert (root / "raw/search-adaptive/search-wave-001/unit-000001/page-002.json").exists()
    quality_rows = (root / "reports/page-quality-search-wave-001.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(quality_rows) == 3


def test_adaptive_wave_resume_does_not_duplicate_existing_page_quality(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    wave_plan = _write_wave_plan(root, unit_max_pages=3)
    _write_existing_raw(root, page=0, cards=[_card("res-1", "腾讯", "大模型产品经理")])
    first_quality = {
        "schema": "liepin_adaptive_page_quality_v1",
        "unit_id": "unit-000001",
        "page": 0,
        "next_page": 1,
        "candidate_count": 1,
        "new_candidate_count": 1,
        "duplicate_count": 0,
        "duplicate_ratio": 0,
        "detail_eligible_count": 1,
        "page_good_ratio": 1,
        "quality_band": "good",
        "decision": "continue",
        "candidate_scores": [],
        "generated_at": "2026-06-04T00:00:00+00:00",
    }
    (root / "reports").mkdir(exist_ok=True)
    (root / "reports/page-quality-search-wave-001.jsonl").write_text(
        json.dumps(first_quality, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _patch_browser(
        monkeypatch,
        [
            _api_response([_card("res-2", "腾讯", "AI 产品负责人")]),
            _api_response([_card("res-3", "腾讯", "产品总监")]),
        ],
    )

    run_live_adaptive_search_wave(
        campaign_root=root,
        wave_plan=wave_plan,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="adaptive-resume",
    )

    rows = [
        json.loads(line)
        for line in (root / "reports/page-quality-search-wave-001.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [row["page"] for row in rows] == [0, 1, 2]
    assert rows[0]["generated_at"] == "2026-06-04T00:00:00+00:00"


def test_adaptive_wave_completed_from_existing_raw_does_not_open_cdp(tmp_path: Path, monkeypatch):
    root = tmp_path / "liepin-demo"
    init_campaign(root, 75703601)
    wave_plan = _write_wave_plan(root, unit_max_pages=2)
    _write_existing_raw(root, page=0, cards=[_card("res-1", "腾讯", "大模型产品经理")])
    _write_existing_raw(root, page=1, cards=[_card("res-2", "腾讯", "AI 产品负责人")])

    monkeypatch.setattr(adaptive_live, "list_targets", lambda cdp_url: (_ for _ in ()).throw(AssertionError("CDP opened")))

    result = run_live_adaptive_search_wave(
        campaign_root=root,
        wave_plan=wave_plan,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        run_id="adaptive-complete",
    )

    assert result["status"] == "completed"
    assert result["pagesCompleted"] == []
    assert result["pagesSkipped"] == [
        {"unit_id": "unit-000001", "page": 0, "reason": "raw_exists"},
        {"unit_id": "unit-000001", "page": 1, "reason": "raw_exists"},
    ]
    state = json.loads((root / "state/adaptive-unit-state-search-wave-001.json").read_text(encoding="utf-8-sig"))
    assert state["units"]["unit-000001"]["status"] == "exhausted"
