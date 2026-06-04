"""猎聘 adaptive search wave CDP live gate。

只执行已规划 wave sidecar，不重新生成搜索条件，不写数据库。
"""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_api_contract import (  # noqa: E402
    SEARCH_RESUMES_URL,
    build_search_request_body,
    classify_api_result,
    merge_condition_data,
)
from scripts.liepin_browser_runner import build_in_page_fetch_expression  # noqa: E402
from scripts.liepin_campaign import append_jsonl, atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_search_live_gate import (  # noqa: E402
    CdpSession,
    _load_request_template,
    _template_headers_for_request,
    find_liepin_target,
    health_expression,
    is_blocking_health,
    list_targets,
    write_continuation_plan,
)


DEFAULT_CDP_URL = "http://127.0.0.1:9898"
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 30.0


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip().lstrip("\ufeff")
        if not text:
            continue
        row = json.loads(text)
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _resolve_wave_plan(campaign_root: Path, wave_plan: str | Path) -> Path:
    path = Path(wave_plan)
    return path if path.is_absolute() else campaign_root / path


def _job_id(requirements: dict[str, Any], strategy: dict[str, Any]) -> int | str:
    value = requirements.get("job_id") or strategy.get("job_id")
    if value in (None, ""):
        raise ValueError("adaptive live search requires requirements.job_id or strategy.job_id")
    return int(value) if str(value).isdigit() else str(value)


def _api_classification(response: dict[str, Any]) -> dict[str, Any]:
    return classify_api_result(
        http_status=response.get("httpStatus"),
        content_type=response.get("contentType"),
        raw_text=response.get("rawPreview"),
        parsed=response.get("data"),
    )


def _adaptive_raw_path(root: Path, wave_id: str, unit_id: str, page: int) -> Path:
    return root / "raw" / "search-adaptive" / wave_id / unit_id / f"page-{page:03d}.json"


def _response_from_raw_page(raw: dict[str, Any]) -> dict[str, Any]:
    summary = raw.get("responseSummary") if isinstance(raw.get("responseSummary"), dict) else {}
    return {
        "status": "ok",
        "httpStatus": summary.get("httpStatus"),
        "contentType": summary.get("contentType") or "",
        "rawLength": summary.get("rawLength", 0),
        "parseError": summary.get("parseError"),
        "rawPreview": raw.get("rawPreview") or "",
        "data": raw.get("payload"),
    }


def _quality_index(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    indexed: dict[tuple[str, int], dict[str, Any]] = {}
    for row in rows:
        unit_id = row.get("unit_id")
        page = row.get("page")
        if unit_id in (None, "") or page in (None, ""):
            continue
        try:
            indexed[(str(unit_id), int(page))] = row
        except (TypeError, ValueError):
            continue
    return indexed


def _quality_for_existing_raw_page(
    *,
    root: Path,
    wave_id: str,
    unit: dict[str, Any],
    page: int,
    seen: set[str],
    quality_path: Path,
    existing_quality: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any] | None:
    unit_id = str(unit.get("unit_id") or "")
    raw_path = _adaptive_raw_path(root, wave_id, unit_id, page)
    if not raw_path.exists():
        return None

    raw = _load_json(raw_path)
    response = _response_from_raw_page(raw)
    # Always replay raw through the scorer to rebuild the seen-candidate set for
    # downstream pages; preserve an existing quality row when one was already
    # written in an earlier run.
    rebuilt_quality = _score_page_quality(unit=unit, page=page, response=response, seen=seen)
    quality_key = (unit_id, page)
    if quality_key in existing_quality:
        return existing_quality[quality_key]

    append_jsonl(quality_path, rebuilt_quality)
    existing_quality[quality_key] = rebuilt_quality
    return rebuilt_quality


def _cards_from_response(response: dict[str, Any]) -> list[dict[str, Any]]:
    parsed = response.get("data")
    if not isinstance(parsed, dict):
        return []
    data = parsed.get("data")
    if not isinstance(data, dict):
        return []
    cards = data.get("cardResList") or data.get("resList") or []
    return [card for card in cards if isinstance(card, dict)]


def _card_key(card: dict[str, Any]) -> str:
    simple = card.get("simpleResumeForm") if isinstance(card.get("simpleResumeForm"), dict) else {}
    for key in ("resIdEncode", "usercIdEncode", "userIdEncode"):
        value = simple.get(key) if key in simple else card.get(key)
        if value not in (None, ""):
            return str(value)
    return json.dumps(card, ensure_ascii=False, sort_keys=True)


def _card_text(card: dict[str, Any]) -> str:
    simple = card.get("simpleResumeForm") if isinstance(card.get("simpleResumeForm"), dict) else {}
    values = [
        simple.get("resCompany"),
        simple.get("resTitle"),
        simple.get("resName"),
        card.get("dqName"),
        card.get("title"),
        card.get("company"),
    ]
    return " ".join(str(value or "") for value in values)


def _query_terms(unit: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for term in str(unit.get("query") or "").split():
        normalized = term.strip()
        if normalized and normalized not in terms:
            terms.append(normalized)
    return terms


def _score_page_quality(
    *,
    unit: dict[str, Any],
    page: int,
    response: dict[str, Any],
    seen: set[str],
) -> dict[str, Any]:
    policy = unit.get("adaptive_search") if isinstance(unit.get("adaptive_search"), dict) else {}
    good_continue = float(policy.get("good_ratio_continue", 0.3))
    good_observe = float(policy.get("good_ratio_observe", 0.1))
    terms = _query_terms(unit)
    cards = _cards_from_response(response)
    candidate_scores: list[dict[str, Any]] = []
    duplicate_count = 0
    eligible_count = 0

    for card in cards:
        key = _card_key(card)
        duplicate = key in seen
        duplicate_count += 1 if duplicate else 0
        text = _card_text(card)
        hits = [term for term in terms if term and term in text]
        eligible = bool(hits) and not duplicate
        eligible_count += 1 if eligible else 0
        candidate_scores.append(
            {
                "candidate_key": key,
                "duplicate": duplicate,
                "hits": hits,
                "detail_eligible": eligible,
            }
        )
        if key:
            seen.add(key)

    candidate_count = len(cards)
    good_ratio = eligible_count / candidate_count if candidate_count else 0.0
    duplicate_ratio = duplicate_count / candidate_count if candidate_count else 0.0
    if good_ratio >= good_continue:
        quality_band = "good"
        decision = "continue"
    elif good_ratio >= good_observe:
        quality_band = "observe"
        decision = "observe"
    else:
        quality_band = "low"
        decision = "observe"

    return {
        "schema": "liepin_adaptive_page_quality_v1",
        "unit_id": unit["unit_id"],
        "page": page,
        "next_page": page + 1,
        "candidate_count": candidate_count,
        "new_candidate_count": candidate_count - duplicate_count,
        "duplicate_count": duplicate_count,
        "duplicate_ratio": duplicate_ratio,
        "detail_eligible_count": eligible_count,
        "page_good_ratio": good_ratio,
        "quality_band": quality_band,
        "decision": decision,
        "candidate_scores": candidate_scores,
        "generated_at": _now(),
    }


def _write_search_raw(
    *,
    root: Path,
    wave_id: str,
    unit_id: str,
    page: int,
    response: dict[str, Any],
    request: dict[str, Any],
    run_id: str,
) -> Path:
    path = root / "raw" / "search-adaptive" / wave_id / unit_id / f"page-{page:03d}.json"
    atomic_write_json(
        path,
        {
            "schema": "liepin_adaptive_search_page_v1",
            "wave_id": wave_id,
            "unit_id": unit_id,
            "curPage": page,
            "payload": response.get("data"),
            "request": request,
            "responseSummary": {
                "httpStatus": response.get("httpStatus"),
                "contentType": response.get("contentType") or "",
                "rawLength": response.get("rawLength", 0),
                "parseError": response.get("parseError"),
            },
            "rawPreview": response.get("rawPreview") or "",
            "run_id": run_id,
            "completed_at": _now(),
        },
    )
    return path


def _write_state(path: Path, state: dict[str, Any]) -> None:
    atomic_write_json(path, state)


def _write_interruption(
    *,
    paths: Any,
    wave_id: str,
    unit_id: str,
    page: int,
    reason: str,
    run_id: str,
    response: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
) -> Path:
    report_path = paths.reports_dir / f"interruption-adaptive-{wave_id}-{reason}-{_timestamp()}.json"
    atomic_write_json(
        report_path,
        {
            "schema": "liepin_adaptive_search_interruption_v1",
            "campaign_id": paths.campaign_id,
            "wave_id": wave_id,
            "unit_id": unit_id,
            "page": page,
            "reason": reason,
            "run_id": run_id,
            "response": response or {},
            "health": health or {},
            "generated_at": _now(),
        },
    )
    append_jsonl(
        paths.request_ledger,
        {
            "event": "adaptive_blocked",
            "wave_id": wave_id,
            "unit_id": unit_id,
            "page": page,
            "reason": reason,
            "report_path": report_path.as_posix(),
            "run_id": run_id,
            "created_at": _now(),
        },
    )
    return report_path


def run_live_adaptive_search_wave(
    *,
    campaign_root: str | Path,
    wave_plan: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    run_id: str | None = None,
) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    root = paths.root
    plan = _load_json(_resolve_wave_plan(root, wave_plan))
    wave_id = str(plan.get("wave_id") or "")
    if not wave_id:
        raise ValueError("wave plan must include wave_id")
    batches = plan.get("batches")
    if not isinstance(batches, list):
        raise ValueError("wave plan batches must be a list")

    requirements = _load_json(paths.requirements)
    strategy = _load_json(paths.strategy)
    resolved_job_id = _job_id(requirements, strategy)
    request_template = _load_request_template(paths)
    resolved_run_id = run_id or f"liepin-adaptive-{datetime.now().date().isoformat()}"
    quality_path = paths.reports_dir / f"page-quality-{wave_id}.jsonl"
    state_path = paths.state_dir / f"adaptive-unit-state-{wave_id}.json"
    existing_quality = _quality_index(_read_jsonl(quality_path))
    seen: set[str] = set()
    state: dict[str, Any] = {
        "schema": "liepin_adaptive_unit_state_v1",
        "wave_id": wave_id,
        "run_id": resolved_run_id,
        "updated_at": _now(),
        "units": {},
    }
    result: dict[str, Any] = {
        "schema": "liepin_adaptive_search_live_run_v1",
        "campaign_id": paths.campaign_id,
        "wave_id": wave_id,
        "run_id": resolved_run_id,
        "generatedAt": _now(),
        "cdp_url": cdp_url,
        "pagesCompleted": [],
        "pagesSkipped": [],
        "status": "running",
    }

    session: CdpSession | None = None
    try:
        for raw_unit in batches:
            if not isinstance(raw_unit, dict):
                raise ValueError("wave plan batches must contain objects")
            unit = raw_unit
            unit_id = str(unit.get("unit_id") or "")
            if not unit_id:
                raise ValueError("wave unit_id is required")
            policy = unit.get("adaptive_search") if isinstance(unit.get("adaptive_search"), dict) else {}
            probe_pages = max(1, int(policy.get("probe_pages") or len(unit.get("pages") or [0])))
            unit_max_pages = max(probe_pages, int(unit.get("unit_max_pages") or policy.get("unit_max_pages") or probe_pages))
            max_low = max(1, int(policy.get("max_consecutive_low_quality_pages") or 2))
            planned_pages = [int(page) for page in unit.get("pages") or list(range(probe_pages))]
            next_page = min(planned_pages) if planned_pages else 0
            consecutive_low = 0
            status = "active"

            while next_page < unit_max_pages:
                if next_page not in planned_pages and consecutive_low >= max_low:
                    status = "stopped_low_quality"
                    break

                existing_page_quality = _quality_for_existing_raw_page(
                    root=root,
                    wave_id=wave_id,
                    unit=unit,
                    page=next_page,
                    seen=seen,
                    quality_path=quality_path,
                    existing_quality=existing_quality,
                )
                if existing_page_quality is not None:
                    result["pagesSkipped"].append({"unit_id": unit_id, "page": next_page, "reason": "raw_exists"})
                    if existing_page_quality.get("quality_band") == "low":
                        consecutive_low += 1
                    else:
                        consecutive_low = 0
                    next_page = int(existing_page_quality.get("next_page") or next_page + 1)
                    if next_page >= unit_max_pages:
                        status = "exhausted"
                        break
                    if next_page >= probe_pages and consecutive_low >= max_low:
                        status = "stopped_low_quality"
                        break
                    continue

                if session is None:
                    target = find_liepin_target(list_targets(cdp_url))
                    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
                    health = session.evaluate(health_expression(), timeout_seconds)
                    result["beforeHealth"] = health
                    health_block = is_blocking_health(health or {})
                    if health_block:
                        result["status"] = "blocked"
                        result["stopReason"] = health_block
                        _write_interruption(
                            paths=paths,
                            wave_id=wave_id,
                            unit_id=unit_id,
                            page=next_page,
                            reason=health_block,
                            run_id=resolved_run_id,
                            health=health,
                        )
                        write_continuation_plan(paths, next_cur_page=next_page, reason=health_block)
                        atomic_write_json(paths.reports_dir / f"adaptive-search-run-{resolved_run_id}.json", result)
                        return result

                overrides = unit.get("search_params_overrides") if isinstance(unit.get("search_params_overrides"), dict) else {}
                search_params = merge_condition_data(
                    {},
                    overrides,
                    job_id=resolved_job_id,
                    cur_page=next_page,
                )
                search_body = build_search_request_body(
                    search_params,
                    {"ckId": "", "skId": "", "fkId": "", "searchScene": "broad_recall"},
                )
                search_response = session.evaluate(
                    build_in_page_fetch_expression(
                        SEARCH_RESUMES_URL,
                        search_body,
                        headers=_template_headers_for_request(request_template),
                    ),
                    timeout_seconds,
                )
                if not isinstance(search_response, dict):
                    raise RuntimeError("adaptive search response was not an object")
                search_status = _api_classification(search_response)
                if not search_status["ok"]:
                    reason = str(search_status["reason"] or "search_failed")
                    result["status"] = "blocked"
                    result["stopReason"] = reason
                    _write_interruption(
                        paths=paths,
                        wave_id=wave_id,
                        unit_id=unit_id,
                        page=next_page,
                        reason=reason,
                        run_id=resolved_run_id,
                        response=search_response,
                    )
                    write_continuation_plan(paths, next_cur_page=next_page, reason=reason)
                    atomic_write_json(paths.reports_dir / f"adaptive-search-run-{resolved_run_id}.json", result)
                    return result

                search_raw_path = _write_search_raw(
                    root=root,
                    wave_id=wave_id,
                    unit_id=unit_id,
                    page=next_page,
                    response=search_response,
                    request={"url": SEARCH_RESUMES_URL, "body": search_body},
                    run_id=resolved_run_id,
                )
                quality = _score_page_quality(
                    unit=unit,
                    page=next_page,
                    response=search_response,
                    seen=seen,
                )
                append_jsonl(quality_path, quality)
                existing_quality[(unit_id, next_page)] = quality
                append_jsonl(
                    paths.request_ledger,
                    {
                        "event": "adaptive_page_completed",
                        "wave_id": wave_id,
                        "unit_id": unit_id,
                        "curPage": next_page,
                        "raw_path": search_raw_path.as_posix(),
                        "run_id": resolved_run_id,
                        "created_at": _now(),
                    },
                )
                result["pagesCompleted"].append({"unit_id": unit_id, "page": next_page})

                if quality["quality_band"] == "low":
                    consecutive_low += 1
                else:
                    consecutive_low = 0

                next_page = int(quality["next_page"])
                if next_page >= unit_max_pages:
                    status = "exhausted"
                    break
                if next_page >= probe_pages and consecutive_low >= max_low:
                    status = "stopped_low_quality"
                    break
                if delay_seconds > 0:
                    time.sleep(delay_seconds)

            state["units"][unit_id] = {
                "status": status,
                "next_page": next_page,
                "consecutive_low_quality_pages": consecutive_low,
                "stop_reason": "consecutive_low_quality_pages" if status == "stopped_low_quality" else "",
                "updated_at": _now(),
            }
            state["updated_at"] = _now()
            _write_state(state_path, state)

        result["status"] = "completed"
        atomic_write_json(paths.reports_dir / f"adaptive-search-run-{resolved_run_id}.json", result)
        return result
    finally:
        if session is not None:
            session.close()
