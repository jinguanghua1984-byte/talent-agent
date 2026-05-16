"""脉脉 AI Infra 详情直连 live gate。

该脚本只连接已有 CDP 人才银行页，通过页面上下文 fetch 详情接口。
它不导航、不刷新、不点击业务页面、不写任何数据库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_search_live_gate import (  # noqa: E402
    CdpSession,
    _load_json,
    _write_json,
    find_talent_target,
    health_expression,
    is_blocking_health,
    list_targets,
)


DETAIL_BLOCK_STATUSES = {401, 403, 429, 432}
DETAIL_ENDPOINT_ORDER = ("basic", "projects", "job_preference", "contact_btn")
BASIC_DETAIL_KEYS = {
    "id",
    "uid",
    "name",
    "gender",
    "avatar",
    "work_exp",
    "work_experience",
    "edu",
    "education",
    "education_experience",
    "user_project",
    "project_experience",
}
WRAPPER_ONLY_KEYS = {
    "code",
    "msg",
    "message",
    "success",
    "status",
    "errno",
    "error",
    "data",
    "ok",
    "result",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().date().isoformat()


def _contact_id(contact: dict[str, Any]) -> str:
    return str(
        contact.get("id")
        or contact.get("uid")
        or contact.get("user_id")
        or contact.get("to_uid")
        or contact.get("platform_id")
        or ""
    )


def _contact_token(contact: dict[str, Any]) -> str:
    return str(contact.get("trackable_token") or contact.get("trackableToken") or contact.get("trackable") or "")


def _safe_file_part(value: Any) -> str:
    text = str(value or "unknown")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    return text.strip("._") or "unknown"


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    temp_path.replace(path)


def _unwrap_endpoint_data(endpoint_result: Any) -> Any:
    if isinstance(endpoint_result, dict) and isinstance(endpoint_result.get("data"), dict):
        nested = endpoint_result["data"]
        if isinstance(nested.get("data"), dict):
            return nested["data"]
        return nested
    return endpoint_result


def _looks_like_basic_detail(payload: dict[str, Any]) -> bool:
    if not payload:
        return False
    keys = set(payload)
    if keys & BASIC_DETAIL_KEYS:
        return True
    return not keys <= WRAPPER_ONLY_KEYS


def _basic_payload_from_endpoint(endpoint_result: dict[str, Any]) -> dict[str, Any] | None:
    parsed = endpoint_result.get("data")
    if not isinstance(parsed, dict):
        return None
    nested = parsed.get("data")
    if isinstance(nested, dict) and nested:
        return nested
    if _looks_like_basic_detail(parsed):
        return parsed
    return None


def _basic_payload_drift_reason(endpoint_result: dict[str, Any]) -> str | None:
    if _basic_payload_from_endpoint(endpoint_result) is not None:
        return None
    parsed = endpoint_result.get("data")
    if not isinstance(parsed, dict) or not parsed:
        return "missing_basic_payload"
    return "detail_template_drift"


def build_detail_urls(contact: dict[str, Any]) -> dict[str, str]:
    """Return the four relative maimai detail endpoint URLs for one contact."""

    uid = quote(_contact_id(contact), safe="")
    token = quote(_contact_token(contact), safe="")
    return {
        "basic": (
            "/api/ent/talent/basic?channel=www&data_version=3.1&need_ai_info=0"
            f"&resume_project_id=&show_tip=0&to_uid={uid}&trackable_token={token}&version=1.0.0"
        ),
        "projects": (
            "/api/ent/candidate/associated/project/list?channel=www&data_version=4.1"
            f"&fr=profile&to_uid={uid}&version=1.0.0"
        ),
        "job_preference": f"/api/ent/talent/job_preference?channel=www&page=0&size=20&to_uid={uid}&version=1.0.0",
        "contact_btn": f"/api/ent/v3/search/contact_btn?channel=www&to_uids={uid}&version=1.0.0",
    }


def is_detail_block(endpoint_result: dict[str, Any]) -> str | None:
    """Return a fuse reason for auth, captcha, block status, or non-JSON response."""

    http_status = endpoint_result.get("httpStatus")
    if http_status in DETAIL_BLOCK_STATUSES:
        return f"http_{http_status}"
    if endpoint_result.get("parseError"):
        return "non_json"
    parsed = endpoint_result.get("data")
    if isinstance(parsed, dict):
        block_info = parsed.get("block_info")
        if not isinstance(block_info, dict):
            nested = parsed.get("data")
            block_info = nested.get("block_info") if isinstance(nested, dict) else None
        if isinstance(block_info, dict):
            block_type = str(block_info.get("block_type") or "").lower()
            captcha_type = str(block_info.get("captcha_type") or "").lower()
            if "captcha" in block_type or captcha_type:
                return "captcha_api"
    return None


def job_capture_entry(contact: dict[str, Any], index: int, result: dict[str, Any]) -> dict[str, Any]:
    """Return one detailJobs entry compatible with maimai_detail_import."""

    endpoints = result.get("endpoints") if isinstance(result.get("endpoints"), dict) else {}
    basic = result.get("detail")
    if not isinstance(basic, dict):
        basic_endpoint = endpoints.get("basic")
        basic = _basic_payload_from_endpoint(basic_endpoint) if isinstance(basic_endpoint, dict) else None
    elif not _looks_like_basic_detail(basic):
        basic = None
    if not isinstance(basic, dict):
        basic = {}
    platform_id = _contact_id(contact) or str(basic.get("id") or "")
    if platform_id and not basic.get("id"):
        basic = dict(basic)
        basic["id"] = platform_id
    errors = result.get("errors") if isinstance(result.get("errors"), list) else []
    started_at = result.get("started_at") or result.get("startedAt") or _now()
    finished_at = result.get("finished_at") or result.get("finishedAt") or _now()
    return {
        "id": platform_id,
        "candidate_id": contact.get("candidate_id"),
        "name": contact.get("name") or basic.get("name") or "",
        "company": contact.get("company") or contact.get("current_company") or "",
        "position": contact.get("position") or contact.get("title") or contact.get("current_title") or "",
        "status": "done" if result.get("ok", True) and not errors else "failed",
        "attempts": int(result.get("attempts") or 1),
        "started_at": started_at,
        "finished_at": finished_at,
        "detail": {
            "basic": basic,
            "projects": endpoints.get("projects"),
            "job_preference": endpoints.get("job_preference"),
            "contact_btn": endpoints.get("contact_btn"),
        },
        "errors": errors,
        "source_contact": dict(contact),
        "index": index,
    }


def _job_raw_path(job_dir: Path, index: int, platform_id: str) -> Path:
    return job_dir / f"job-{index + 1:06d}-{_safe_file_part(platform_id)}.json"


def _is_successful_job_raw(path: Path, contact: dict[str, Any]) -> bool:
    if not path.exists():
        return False
    try:
        data = _load_json(path)
    except Exception:
        return False
    if not isinstance(data, dict):
        return False
    if data.get("status") == "failed":
        return False
    expected_id = _contact_id(contact)
    if expected_id and str(data.get("id") or "") != expected_id:
        return False
    detail = data.get("detail") or {}
    basic = detail.get("basic") if isinstance(detail, dict) else None
    return isinstance(basic, dict) and bool(basic)


def next_resume_index(contacts: list[dict[str, Any]], job_dir: Path) -> int:
    """Return the first contact index without a successful job raw file."""

    for index, contact in enumerate(contacts):
        platform_id = _contact_id(contact)
        if not platform_id or not _is_successful_job_raw(_job_raw_path(job_dir, index, platform_id), contact):
            return index
    return len(contacts)


def _pack_id(plan: dict[str, Any], plan_path: Path) -> str:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    return str(metadata.get("pack_id") or plan.get("pack_id") or plan_path.stem)


def _campaign_root(plan: dict[str, Any], plan_path: Path, out_path: Path) -> Path:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    for value in (metadata.get("campaign_root"), plan.get("campaign_root")):
        if value:
            return Path(value)
    for path in (out_path, plan_path):
        parts = path.parts
        if "raw" in parts:
            raw_index = parts.index("raw")
            if raw_index > 0:
                return Path(*parts[:raw_index])
    return out_path.parent.parent if out_path.parent.name == "raw" else out_path.parent


def _job_dir_for(plan: dict[str, Any], plan_path: Path, out_path: Path) -> Path:
    return _campaign_root(plan, plan_path, out_path) / "raw" / "detail-live" / _pack_id(plan, plan_path)


def _capture_from_job_dir(
    plan: dict[str, Any],
    plan_path: Path,
    job_dir: Path,
    *,
    status: str = "running",
    stop_reason: str | None = None,
    interruption_report: str | None = None,
    continuation_plan: str | None = None,
) -> dict[str, Any]:
    contacts = [item for item in (plan.get("contacts") or []) if isinstance(item, dict)]
    pack_id = _pack_id(plan, plan_path)
    jobs = []
    for index, contact in enumerate(contacts):
        platform_id = _contact_id(contact)
        if not platform_id:
            continue
        path = _job_raw_path(job_dir, index, platform_id)
        if _is_successful_job_raw(path, contact):
            jobs.append(_load_json(path))
    partial = status != "completed" or len(jobs) < len(contacts)
    metadata: dict[str, Any] = {
        "export_type": "maimai_ai_infra_direct_detail_live_gate",
        "detail_mode": "direct_page_fetch",
        "pack_id": pack_id,
        "status": status,
        "partial": partial,
        "total_contacts": len(contacts),
        "completed_jobs": len(jobs),
        "write_db": False,
        "apply": False,
        "generatedAt": _now(),
    }
    if stop_reason:
        metadata["stopReason"] = stop_reason
    if interruption_report:
        metadata["interruptionReport"] = interruption_report
    if continuation_plan:
        metadata["continuationPlan"] = continuation_plan
    return {
        "metadata": metadata,
        "detailJobs": jobs,
    }


def _write_capture(
    out_path: Path,
    plan: dict[str, Any],
    plan_path: Path,
    job_dir: Path,
    *,
    status: str = "running",
    stop_reason: str | None = None,
    interruption_report: str | None = None,
    continuation_plan: str | None = None,
) -> dict[str, Any]:
    capture = _capture_from_job_dir(
        plan,
        plan_path,
        job_dir,
        status=status,
        stop_reason=stop_reason,
        interruption_report=interruption_report,
        continuation_plan=continuation_plan,
    )
    _write_json(out_path, capture)
    return capture


def _detail_fetch_expression(contact: dict[str, Any]) -> str:
    urls_json = json.dumps(build_detail_urls(contact), ensure_ascii=False)
    order_json = json.dumps(list(DETAIL_ENDPOINT_ORDER))
    return f"""
(async () => {{
  function detailEndpointUrls() {{
    return {urls_json};
  }}
  const urls = detailEndpointUrls();
  const order = {order_json};
  const endpoints = {{}};
  const errors = [];
  const startedAt = new Date().toISOString().slice(0, 19);

  async function fetchEndpoint(name, url) {{
    const response = await fetch(url, {{
      method: "GET",
      credentials: "include",
      headers: {{ Accept: "application/json, text/plain, */*" }}
    }});
    const raw = await response.text();
    let data = null;
    let parseError = null;
    try {{
      data = JSON.parse(raw);
    }} catch (err) {{
      parseError = err && err.message ? err.message : String(err);
    }}
    return {{
      name,
      url,
      ok: response.ok && !parseError,
      httpStatus: response.status,
      contentType: response.headers.get("content-type") || "",
      rawLength: raw.length,
      rawPreview: raw.slice(0, 2000),
      parseError,
      data
    }};
  }}

  for (const name of order) {{
    const endpoint = await fetchEndpoint(name, urls[name]);
    endpoints[name] = endpoint;
    if (!endpoint.ok) {{
      errors.push(endpoint.parseError ? "non_json" : (name + "_http_" + endpoint.httpStatus));
      return {{
        ok: false,
        failedEndpoint: name,
        endpoints,
        detail: null,
        errors,
        startedAt,
        finishedAt: new Date().toISOString().slice(0, 19)
      }};
    }}
  }}

  const basicData = endpoints.basic && endpoints.basic.data && endpoints.basic.data.data
    ? endpoints.basic.data.data
    : (endpoints.basic ? endpoints.basic.data : null);
  return {{
    ok: true,
    failedEndpoint: null,
    endpoints,
    detail: basicData && typeof basicData === "object" ? basicData : null,
    errors,
    startedAt,
    finishedAt: new Date().toISOString().slice(0, 19)
  }};
}})()
""".strip()


def _block_from_result(result: dict[str, Any]) -> tuple[str | None, str | None, dict[str, Any]]:
    endpoints = result.get("endpoints") if isinstance(result.get("endpoints"), dict) else {}
    for name in DETAIL_ENDPOINT_ORDER:
        endpoint_result = endpoints.get(name)
        if isinstance(endpoint_result, dict):
            reason = is_detail_block(endpoint_result)
            if reason:
                return reason, name, endpoint_result
            if endpoint_result.get("httpStatus") is not None and not (200 <= int(endpoint_result.get("httpStatus")) < 300):
                return f"{name}_http_{endpoint_result.get('httpStatus')}", name, endpoint_result
    basic_endpoint = endpoints.get("basic")
    if isinstance(basic_endpoint, dict):
        drift_reason = _basic_payload_drift_reason(basic_endpoint)
        if drift_reason:
            return drift_reason, "basic", basic_endpoint
    failed_endpoint = result.get("failedEndpoint")
    if failed_endpoint and isinstance(endpoints.get(failed_endpoint), dict):
        endpoint_result = endpoints[failed_endpoint]
        return (
            is_detail_block(endpoint_result)
            or (f"{failed_endpoint}_http_{endpoint_result.get('httpStatus')}" if endpoint_result.get("httpStatus") else "detail_fetch_failed"),
            str(failed_endpoint),
            endpoint_result,
        )
    if not result.get("ok", False):
        return "detail_fetch_failed", str(failed_endpoint or ""), {}
    return None, None, {}


def _response_summary(endpoint_result: dict[str, Any]) -> dict[str, Any]:
    data = endpoint_result.get("data")
    root_keys = sorted(data.keys()) if isinstance(data, dict) else []
    block_info = data.get("block_info") if isinstance(data, dict) else None
    if not isinstance(block_info, dict) and isinstance(data, dict) and isinstance(data.get("data"), dict):
        block_info = data["data"].get("block_info")
    return {
        "httpStatus": endpoint_result.get("httpStatus"),
        "contentType": endpoint_result.get("contentType") or "",
        "rawLength": endpoint_result.get("rawLength") or len(endpoint_result.get("rawPreview") or ""),
        "parseError": endpoint_result.get("parseError"),
        "rootKeys": root_keys,
        "block_info": block_info if isinstance(block_info, dict) else {},
    }


def build_interruption_artifacts(
    *,
    plan: dict[str, Any],
    plan_path: Path,
    out_path: Path,
    job_dir: Path,
    failed_index: int,
    stop_reason: str,
    before_health: dict[str, Any] | None,
    after_health: dict[str, Any] | None,
    failed_endpoint: str | None,
    endpoint_result: dict[str, Any] | None,
) -> dict[str, Any]:
    contacts = [item for item in (plan.get("contacts") or []) if isinstance(item, dict)]
    contact = contacts[failed_index] if 0 <= failed_index < len(contacts) else {}
    endpoint_result = endpoint_result or {}
    pack_id = _pack_id(plan, plan_path)
    campaign_root = _campaign_root(plan, plan_path, out_path)
    block_info: Any = {}
    data = endpoint_result.get("data")
    if isinstance(data, dict):
        block_info = data.get("block_info") or (data.get("data", {}) if isinstance(data.get("data"), dict) else {}).get("block_info") or {}
    report = {
        "stopReason": stop_reason,
        "pack_id": pack_id,
        "failedIndex": failed_index,
        "failedCandidateId": contact.get("candidate_id"),
        "failedPlatformId": _contact_id(contact),
        "lastSuccessIndex": failed_index - 1,
        "standardizedJobs": failed_index,
        "remainingJobs": max(0, len(contacts) - failed_index),
        "beforeHealth": before_health or {},
        "afterHealth": after_health or {},
        "failedEndpoint": failed_endpoint,
        "httpStatus": endpoint_result.get("httpStatus"),
        "stopError": endpoint_result.get("error") or endpoint_result.get("parseError"),
        "exceptionType": endpoint_result.get("exceptionType"),
        "errors": endpoint_result.get("errors") or [],
        "responseSummary": _response_summary(endpoint_result),
        "responseRawPreview": endpoint_result.get("rawPreview") or "",
        "block_info": block_info if isinstance(block_info, dict) else {},
        "captcha_type": (block_info or {}).get("captcha_type") if isinstance(block_info, dict) else None,
        "downstreamNotRun": {
            "detailWaveDryRun": True,
            "detailWaveApply": True,
            "finalReport": True,
        },
    }
    continuation = dict(plan)
    if failed_index >= len(contacts):
        continuation["resume_from"] = {
            "index": failed_index,
            "candidate_id": None,
            "platform_id": "",
            "completed": True,
        }
    else:
        continuation["resume_from"] = {
            "index": failed_index,
            "candidate_id": contact.get("candidate_id"),
            "platform_id": _contact_id(contact),
        }
    continuation["completed_job_dir"] = str(job_dir)
    continuation["previous_capture_file"] = str(out_path)
    continuation["stopReason"] = stop_reason

    reason_part = _safe_file_part(stop_reason)
    continuation_dir = plan_path.parent if plan_path.parent.exists() else campaign_root
    continuation_path = continuation_dir / f"detail-live-{pack_id}-continuation-after-{reason_part}-plan.json"
    report_path = campaign_root / "reports" / f"interruption-detail-{pack_id}-{_today()}.json"
    return {
        "report": report,
        "continuation": continuation,
        "report_path": report_path,
        "continuation_path": continuation_path,
    }


def _write_interruption_artifacts(artifacts: dict[str, Any]) -> None:
    _write_json(Path(artifacts["continuation_path"]), artifacts["continuation"])
    _write_json(Path(artifacts["report_path"]), artifacts["report"])


def run_gate(
    plan_path: Path,
    out_path: Path,
    cdp_url: str,
    delay_seconds: float,
    timeout_seconds: float,
    health_check_only: bool = False,
    max_jobs: int | None = None,
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    if not isinstance(plan, dict):
        raise ValueError("plan must be a JSON object")
    contacts = [item for item in (plan.get("contacts") or []) if isinstance(item, dict)]
    if not contacts:
        raise ValueError("plan must contain non-empty contacts")

    pack_id = _pack_id(plan, plan_path)
    job_dir = _job_dir_for(plan, plan_path, out_path)
    target = find_talent_target(list_targets(cdp_url))
    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    result: dict[str, Any] = {
        "status": "started",
        "pack_id": pack_id,
        "plan": str(plan_path),
        "out": str(out_path),
        "pageTarget": {
            "id": target.get("id"),
            "title": target.get("title"),
            "url": target.get("url"),
        },
        "total_contacts": len(contacts),
        "completed_jobs": 0,
        "write_db": False,
        "apply": False,
    }
    try:
        before_health = session.evaluate(health_expression(), timeout_seconds)
        result["beforeHealth"] = before_health
        blocking = is_blocking_health(before_health or {})
        if blocking:
            result["status"] = "blocked"
            result["stopReason"] = blocking
            artifacts = build_interruption_artifacts(
                plan=plan,
                plan_path=plan_path,
                out_path=out_path,
                job_dir=job_dir,
                failed_index=next_resume_index(contacts, job_dir),
                stop_reason=blocking,
                before_health=before_health,
                after_health=before_health,
                failed_endpoint=None,
                endpoint_result={},
            )
            _write_interruption_artifacts(artifacts)
            result["interruptionReport"] = str(artifacts["report_path"])
            result["continuationPlan"] = str(artifacts["continuation_path"])
            _write_capture(
                out_path,
                plan,
                plan_path,
                job_dir,
                status="blocked",
                stop_reason=blocking,
                interruption_report=result["interruptionReport"],
                continuation_plan=result["continuationPlan"],
            )
            return result
        if health_check_only:
            result["status"] = "health_ok"
            _write_json(out_path, result)
            print(
                f"status=health_ok hasLoginPrompt={str(bool((before_health or {}).get('hasLoginPrompt'))).lower()} "
                f"hasCaptcha={str(bool((before_health or {}).get('hasCaptcha'))).lower()} "
                f"hasTalentBank={str(bool((before_health or {}).get('hasTalentBank'))).lower()}"
            )
            return result

        start_index = next_resume_index(contacts, job_dir)
        end_index = len(contacts)
        if max_jobs is not None:
            end_index = min(end_index, start_index + max(0, max_jobs))
        if start_index >= end_index:
            status = "completed" if next_resume_index(contacts, job_dir) >= len(contacts) else "completed_limited"
            capture = _write_capture(out_path, plan, plan_path, job_dir, status=status)
            result["status"] = status
            result["completed_jobs"] = capture["metadata"]["completed_jobs"]
            return result

        for index in range(start_index, end_index):
            contact = contacts[index]
            started_at = _now()
            try:
                fetch_result = session.evaluate(_detail_fetch_expression(contact), timeout_seconds)
            except Exception as exc:  # noqa: BLE001 - 需要记录中断证据后停止。
                fetch_result = {
                    "ok": False,
                    "failedEndpoint": "",
                    "endpoints": {},
                    "errors": [str(exc)],
                }
                stop_reason, failed_endpoint, endpoint_result = "exception", "", {
                    "error": str(exc),
                    "exceptionType": type(exc).__name__,
                }
            else:
                if not isinstance(fetch_result, dict):
                    fetch_result = {"ok": False, "failedEndpoint": "", "endpoints": {}, "errors": ["non_object_result"]}
                stop_reason, failed_endpoint, endpoint_result = _block_from_result(fetch_result)

            if stop_reason:
                try:
                    after_health = session.evaluate(health_expression(), timeout_seconds)
                except Exception as exc:  # noqa: BLE001
                    after_health = {"error": str(exc)}
                result["status"] = "stopped"
                result["stopReason"] = stop_reason
                result["failedIndex"] = index
                result["failedPlatformId"] = _contact_id(contact)
                artifacts = build_interruption_artifacts(
                    plan=plan,
                    plan_path=plan_path,
                    out_path=out_path,
                    job_dir=job_dir,
                    failed_index=index,
                    stop_reason=stop_reason,
                    before_health=before_health,
                    after_health=after_health,
                    failed_endpoint=failed_endpoint,
                    endpoint_result=endpoint_result,
                )
                _write_interruption_artifacts(artifacts)
                result["interruptionReport"] = str(artifacts["report_path"])
                result["continuationPlan"] = str(artifacts["continuation_path"])
                _write_capture(
                    out_path,
                    plan,
                    plan_path,
                    job_dir,
                    status="stopped",
                    stop_reason=stop_reason,
                    interruption_report=result["interruptionReport"],
                    continuation_plan=result["continuationPlan"],
                )
                return result

            fetch_result["started_at"] = fetch_result.get("started_at") or fetch_result.get("startedAt") or started_at
            fetch_result["finished_at"] = fetch_result.get("finished_at") or fetch_result.get("finishedAt") or _now()
            entry = job_capture_entry(contact, index, fetch_result)
            if entry.get("status") == "failed":
                stop_reason = "detail_fetch_failed"
                endpoint_result = {"error": ",".join(entry.get("errors") or []), "errors": entry.get("errors") or []}
                result["status"] = "stopped"
                result["stopReason"] = stop_reason
                artifacts = build_interruption_artifacts(
                    plan=plan,
                    plan_path=plan_path,
                    out_path=out_path,
                    job_dir=job_dir,
                    failed_index=index,
                    stop_reason=stop_reason,
                    before_health=before_health,
                    after_health=before_health,
                    failed_endpoint=None,
                    endpoint_result=endpoint_result,
                )
                _write_interruption_artifacts(artifacts)
                result["interruptionReport"] = str(artifacts["report_path"])
                result["continuationPlan"] = str(artifacts["continuation_path"])
                _write_capture(
                    out_path,
                    plan,
                    plan_path,
                    job_dir,
                    status="stopped",
                    stop_reason=stop_reason,
                    interruption_report=result["interruptionReport"],
                    continuation_plan=result["continuationPlan"],
                )
                return result
            _write_json_atomic(_job_raw_path(job_dir, index, entry["id"]), entry)
            capture = _write_capture(out_path, plan, plan_path, job_dir)
            result["completed_jobs"] = capture["metadata"]["completed_jobs"]

            try:
                health_after = session.evaluate(health_expression(), timeout_seconds)
            except Exception as exc:  # noqa: BLE001
                health_after = {"error": str(exc)}
            blocking = is_blocking_health(health_after or {})
            if blocking:
                result["status"] = "stopped"
                result["stopReason"] = blocking
                result["failedIndex"] = index + 1
                artifacts = build_interruption_artifacts(
                    plan=plan,
                    plan_path=plan_path,
                    out_path=out_path,
                    job_dir=job_dir,
                    failed_index=index + 1,
                    stop_reason=blocking,
                    before_health=before_health,
                    after_health=health_after,
                    failed_endpoint=None,
                    endpoint_result={},
                )
                _write_interruption_artifacts(artifacts)
                result["interruptionReport"] = str(artifacts["report_path"])
                result["continuationPlan"] = str(artifacts["continuation_path"])
                result["completed_jobs"] = capture["metadata"]["completed_jobs"]
                _write_capture(
                    out_path,
                    plan,
                    plan_path,
                    job_dir,
                    status="stopped",
                    stop_reason=blocking,
                    interruption_report=result["interruptionReport"],
                    continuation_plan=result["continuationPlan"],
                )
                return result

            if index + 1 < end_index:
                time.sleep(delay_seconds)

        completed_jobs = next_resume_index(contacts, job_dir)
        if completed_jobs >= len(contacts):
            status = "completed"
        elif max_jobs is not None and end_index < len(contacts) and completed_jobs >= end_index:
            status = "completed_limited"
        else:
            status = "stopped"
        capture = _write_capture(
            out_path,
            plan,
            plan_path,
            job_dir,
            status=status,
            stop_reason="incomplete" if status == "stopped" else None,
        )
        result["completed_jobs"] = capture["metadata"]["completed_jobs"]
        result["status"] = status
        if status == "stopped":
            result["stopReason"] = "incomplete"
        return result
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="受控执行脉脉 AI Infra 详情直连 live gate")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9888")
    parser.add_argument("--delay-seconds", type=float, default=10)
    parser.add_argument("--timeout-seconds", type=float, default=45)
    parser.add_argument("--health-check-only", action="store_true")
    parser.add_argument("--max-jobs", type=int)
    args = parser.parse_args(argv)

    result = run_gate(
        plan_path=Path(args.plan),
        out_path=Path(args.out),
        cdp_url=args.cdp_url,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        health_check_only=args.health_check_only,
        max_jobs=args.max_jobs,
    )
    print(json.dumps({
        "status": result.get("status"),
        "stopReason": result.get("stopReason"),
        "pack_id": result.get("pack_id"),
        "completed_jobs": result.get("completed_jobs"),
        "out": args.out,
    }, ensure_ascii=False, indent=2))
    if result.get("status") in {"completed", "completed_limited", "health_ok"}:
        return 0
    if result.get("status") in {"stopped", "blocked"}:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
