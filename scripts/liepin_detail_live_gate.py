"""猎聘详情 smoke CDP live gate 的安全辅助函数。

本模块只构建受控详情 fetch 表达式、分类响应和处理本地 job 状态；
不读取浏览器敏感存储，不读取 profile 文件，也不写入数据库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_browser_runner import sanitize_liepin_request_headers  # noqa: E402
from scripts.liepin_campaign import append_jsonl, atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_search_live_gate import (  # noqa: E402
    CdpSession,
    DEFAULT_CDP_URL,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    find_liepin_target,
    health_expression,
    is_blocking_health,
    list_targets,
)


DETAIL_BLOCK_STATUSES = {401, 403, 429, 432}
DETAIL_TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
DETAIL_RUN_SCHEMA = "liepin_detail_smoke_run_v1"
DETAIL_JOB_SCHEMA = "liepin_detail_smoke_job_v1"
DETAIL_SUMMARY_SCHEMA = "liepin_detail_smoke_summary_v1"
DETAIL_CONTINUATION_SCHEMA = "liepin_detail_smoke_continuation_v1"

DETAIL_PAYLOAD_KEYS = {
    "name",
    "baseInfo",
    "resume",
    "workList",
    "workExperience",
    "educations",
}
BUSINESS_BLOCK_MARKERS = (
    "验证码",
    "安全验证",
    "访问异常",
    "无权限",
    "余额不足",
    "受限",
)
DETAIL_JOB_NAME_RE = re.compile(r"^job-(\d{3})\.json$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _target_pack_path(campaign_root: str | Path, target_pack: str | Path) -> Path:
    pack_path = Path(target_pack)
    if pack_path.is_absolute():
        return pack_path
    return Path(campaign_root) / pack_path


def _pack_id(plan: Mapping[str, Any], plan_path: Path) -> str:
    metadata = plan.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("pack_id"):
        return str(metadata["pack_id"])
    if plan.get("pack_id"):
        return str(plan["pack_id"])
    return plan_path.stem


def _detail_ledger_path(paths: Any) -> Path:
    return paths.state_dir / "detail-request-ledger.jsonl"


def _append_detail_ledger(paths: Any, item: dict[str, Any]) -> dict[str, Any]:
    record = {**item, "ts": _now()}
    append_jsonl(_detail_ledger_path(paths), record)
    return record


def validate_detail_url(url: str) -> str:
    parsed = urlsplit(str(url))
    if (
        parsed.scheme == "https"
        and parsed.netloc == "h.liepin.com"
        and parsed.path in {"/resume/showresumedetail", "/resume/showresumedetail/"}
        and not parsed.fragment
    ):
        return str(url)
    raise ValueError(f"Liepin detail URL is not allowed: {url}")


def build_detail_fetch_expression(url: str, headers: Mapping[str, Any] | None = None) -> str:
    safe_url = validate_detail_url(url)
    safe_headers = sanitize_liepin_request_headers(headers)
    safe_headers.setdefault("Accept", "application/json, text/plain, */*")
    url_json = json.dumps(safe_url, ensure_ascii=False)
    headers_json = json.dumps(safe_headers, ensure_ascii=False)
    return f"""
(async () => {{
  const response = await fetch({url_json}, {{
    method: "GET",
    headers: {headers_json},
    credentials: "include"
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
    status: "ok",
    httpStatus: response.status,
    contentType: response.headers.get("content-type") || "",
    rawLength: raw.length,
    parseError,
    data,
    rawPreview: raw.slice(0, 2000)
  }};
}})()
""".strip()


def _looks_like_detail_payload(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if any(key in data for key in DETAIL_PAYLOAD_KEYS):
        return True
    nested = data.get("data")
    return isinstance(nested, dict) and any(key in nested for key in DETAIL_PAYLOAD_KEYS)


def _string_blob(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def classify_detail_result(response: Mapping[str, Any]) -> str | None:
    http_status = response.get("httpStatus")
    if http_status in DETAIL_BLOCK_STATUSES:
        return f"http_{http_status}"
    if response.get("parseError"):
        return "non_json"

    data = response.get("data")
    if any(marker in _string_blob({"data": data, "rawPreview": response.get("rawPreview")}) for marker in BUSINESS_BLOCK_MARKERS):
        return "business_block"

    if isinstance(data, dict):
        code = data.get("code")
        if code in DETAIL_BLOCK_STATUSES or str(code) in {str(status) for status in DETAIL_BLOCK_STATUSES}:
            return "business_block"
        flag = data.get("flag")
        if flag is not None and flag not in {1, "1", True}:
            return "business_block"
        if _looks_like_detail_payload(data):
            return None
        return "partial_detail"

    return "partial_detail"


def detail_job_path(job_dir: str | Path, index: int) -> Path:
    if type(index) is not int or index < 0:
        raise ValueError("index must be non-negative")
    return Path(job_dir) / f"job-{index:03d}.json"


def load_completed_detail_jobs(job_dir: str | Path) -> dict[int, str]:
    completed: dict[int, str] = {}
    for raw_path in Path(job_dir).glob("job-*.json"):
        match = DETAIL_JOB_NAME_RE.fullmatch(raw_path.name)
        if not match:
            continue
        index = int(match.group(1))
        try:
            payload = _load_json(raw_path)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict) or payload.get("status") != "done":
            continue
        platform_id = str(payload.get("platform_id") or payload.get("platformId") or "")
        if platform_id:
            completed[index] = platform_id
    return completed


def sanitize_detail_result_for_report(payload: Any) -> Any:
    if isinstance(payload, list):
        return [sanitize_detail_result_for_report(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"profile_url", "url", "href", "rawPreview"}:
            continue
        sanitized[key] = sanitize_detail_result_for_report(value)
    return sanitized


def _captured_field_groups(response: Mapping[str, Any]) -> list[str]:
    data = response.get("data")
    if not isinstance(data, dict):
        return []
    detail_data = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(detail_data, dict):
        return []
    return sorted(str(key) for key in detail_data.keys() if key in DETAIL_PAYLOAD_KEYS)


def _write_detail_job(
    job_dir: str | Path,
    index: int,
    contact: Mapping[str, Any],
    response: Mapping[str, Any],
    run_id: str,
) -> Path:
    raw_path = detail_job_path(job_dir, index)
    payload = {
        "schema": DETAIL_JOB_SCHEMA,
        "status": "done",
        "run_id": run_id,
        "index": index,
        "platform": "liepin",
        "platform_id": str(contact.get("platform_id") or ""),
        "user_id_encode": str(contact.get("user_id_encode") or ""),
        "profile_url_ref": True,
        "profile_url": str(contact.get("profile_url") or ""),
        "raw_ref": contact.get("raw_ref") if isinstance(contact.get("raw_ref"), dict) else {},
        "requests": [
            {
                "type": "detail",
                "httpStatus": response.get("httpStatus"),
                "contentType": response.get("contentType") or "",
                "rawLength": response.get("rawLength", 0),
                "parseError": response.get("parseError"),
                "data": response.get("data"),
                "rawPreview": response.get("rawPreview") or "",
                "captured_at": _now(),
            }
        ],
        "completed_at": _now(),
    }
    atomic_write_json(raw_path, payload)
    return raw_path


def _write_continuation(
    paths: Any,
    pack_id: str,
    target_pack: Path,
    contact: Mapping[str, Any],
    job_index: int,
    reason: str,
    completed_job_dir: Path,
    run_id: str,
) -> Path:
    continuation_path = paths.state_dir / f"detail-live-{pack_id}-continuation-after-{reason}.json"
    payload = {
        "schema": DETAIL_CONTINUATION_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "target_pack": _relative_path(target_pack, paths.root),
        "reason": reason,
        "run_id": run_id,
        "resume_from": {
            "job_index": job_index,
            "platform_id": str(contact.get("platform_id") or ""),
        },
        "completed_job_dir": _relative_path(completed_job_dir, paths.root),
        "updated_at": _now(),
    }
    atomic_write_json(continuation_path, payload)
    return continuation_path


def _write_interruption(
    *,
    paths: Any,
    pack_id: str,
    run_id: str,
    reason: str,
    job_index: int,
    contact: Mapping[str, Any],
    response: Mapping[str, Any] | None = None,
    health: Mapping[str, Any] | None = None,
) -> Path:
    report_path = paths.reports_dir / f"interruption-detail-{pack_id}-{_timestamp()}.json"
    payload = {
        "schema": "liepin_detail_smoke_interruption_v1",
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": run_id,
        "reason": reason,
        "job_index": job_index,
        "contact": {
            "platform_id": str(contact.get("platform_id") or ""),
            "user_id_encode": str(contact.get("user_id_encode") or ""),
            "display_name": str(contact.get("display_name") or ""),
            "current_company": str(contact.get("current_company") or ""),
            "current_title": str(contact.get("current_title") or ""),
        },
        "response": sanitize_detail_result_for_report(dict(response or {})),
        "health": sanitize_detail_result_for_report(dict(health or {})),
        "downstreamNotRun": {
            "campaignDbWrite": True,
            "mainDbWrite": True,
            "recommendationReport": True,
        },
        "generatedAt": _now(),
    }
    atomic_write_json(report_path, payload)
    return report_path


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# 猎聘详情 smoke 执行摘要",
        "",
        f"- campaign：{summary['campaign_id']}",
        f"- target pack：{summary['pack_id']}",
        f"- 状态：{summary['status']}",
        f"- 目标数：{summary['targets']}",
        f"- 本次完成：{summary['completed']}",
        f"- 失败：{summary['failed']}",
        f"- 阻断：{summary['blocked']}",
        f"- 停止原因：{summary.get('stopReason') or ''}",
        f"- 下一步：{summary['next_step']}",
        "",
    ]
    return "\n".join(lines)


def _write_summary(
    *,
    paths: Any,
    pack_id: str,
    run_id: str,
    targets: int,
    completed: int,
    failed: int,
    blocked: bool,
    template_drift: bool,
    captured_field_groups: list[str],
    status: str,
    stop_reason: str | None,
    next_step: str,
) -> dict[str, Any]:
    summary = {
        "schema": DETAIL_SUMMARY_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": run_id,
        "targets": targets,
        "completed": completed,
        "failed": failed,
        "blocked": blocked,
        "template_drift": template_drift,
        "captured_field_groups": sorted(set(captured_field_groups)),
        "status": status,
        "stopReason": stop_reason,
        "next_step": next_step,
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-smoke-summary.json", summary)
    (paths.reports_dir / "detail-smoke-summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def _validate_target_pack(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("target pack must be an object")
    if plan.get("schema") != DETAIL_TARGET_SCHEMA:
        raise ValueError(f"target pack schema must be {DETAIL_TARGET_SCHEMA}")
    contacts = plan.get("contacts")
    if not isinstance(contacts, list):
        raise ValueError("target pack contacts must be a list")
    for index, contact in enumerate(contacts):
        if not isinstance(contact, dict):
            raise ValueError(f"target pack contact {index} must be an object")
    return plan


def run_live_detail_smoke(
    *,
    campaign_root: str | Path,
    target_pack: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    limit: int = 10,
    run_id: str | None = None,
) -> dict[str, Any]:
    if type(limit) is not int or limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")

    paths = ensure_campaign(campaign_root)
    plan_path = _target_pack_path(paths.root, target_pack)
    plan = _validate_target_pack(_load_json(plan_path))
    pack_id = _pack_id(plan, plan_path)
    contacts = [contact for contact in plan["contacts"][:limit] if isinstance(contact, dict)]
    resolved_run_id = run_id or f"liepin-detail-live-{datetime.now().date().isoformat()}"
    job_dir = paths.raw_dir / "detail-live" / pack_id
    completed_jobs = load_completed_detail_jobs(job_dir)
    captured_groups: list[str] = []
    newly_completed = 0
    failed = 0

    target = find_liepin_target(list_targets(cdp_url))
    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    result: dict[str, Any] = {
        "schema": DETAIL_RUN_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": resolved_run_id,
        "target_pack": _relative_path(plan_path, paths.root),
        "targets": len(contacts),
        "completed": 0,
        "failed": 0,
        "status": "running",
        "generatedAt": _now(),
    }
    try:
        health = session.evaluate(health_expression(), timeout_seconds)
        result["beforeHealth"] = health
        health_block = is_blocking_health(health or {})
        if health_block:
            first_contact = contacts[0] if contacts else {}
            result.update({"status": "blocked", "stopReason": health_block, "completed": 0, "failed": 0})
            _write_continuation(
                paths,
                pack_id,
                plan_path,
                first_contact,
                int(first_contact.get("index") or 0),
                health_block,
                job_dir,
                resolved_run_id,
            )
            _write_interruption(
                paths=paths,
                pack_id=pack_id,
                run_id=resolved_run_id,
                reason=health_block,
                job_index=int(first_contact.get("index") or 0),
                contact=first_contact,
                health=health if isinstance(health, Mapping) else {},
            )
            _write_summary(
                paths=paths,
                pack_id=pack_id,
                run_id=resolved_run_id,
                targets=len(contacts),
                completed=0,
                failed=0,
                blocked=True,
                template_drift=False,
                captured_field_groups=[],
                status="blocked",
                stop_reason=health_block,
                next_step=f"resume_after_{health_block}",
            )
            _append_detail_ledger(
                paths,
                {
                    "event": "detail_blocked",
                    "reason": health_block,
                    "stage": "health",
                    "pack_id": pack_id,
                    "run_id": resolved_run_id,
                },
            )
            return result

        for position, contact in enumerate(contacts):
            job_index = int(contact.get("index") if type(contact.get("index")) is int else position)
            if job_index in completed_jobs:
                continue

            response = session.evaluate(build_detail_fetch_expression(str(contact["profile_url"])), timeout_seconds)
            if not isinstance(response, dict):
                raise RuntimeError("detail response was not an object")
            reason = classify_detail_result(response)
            if reason:
                failed += 1
                result.update(
                    {
                        "status": "blocked",
                        "stopReason": reason,
                        "completed": newly_completed,
                        "failed": failed,
                    }
                )
                _write_continuation(
                    paths,
                    pack_id,
                    plan_path,
                    contact,
                    job_index,
                    reason,
                    job_dir,
                    resolved_run_id,
                )
                _write_interruption(
                    paths=paths,
                    pack_id=pack_id,
                    run_id=resolved_run_id,
                    reason=reason,
                    job_index=job_index,
                    contact=contact,
                    response=response,
                )
                _write_summary(
                    paths=paths,
                    pack_id=pack_id,
                    run_id=resolved_run_id,
                    targets=len(contacts),
                    completed=newly_completed,
                    failed=failed,
                    blocked=True,
                    template_drift=(reason == "partial_detail"),
                    captured_field_groups=captured_groups,
                    status="blocked",
                    stop_reason=reason,
                    next_step=f"resume_after_{reason}",
                )
                _append_detail_ledger(
                    paths,
                    {
                        "event": "detail_blocked",
                        "reason": reason,
                        "stage": "detail",
                        "pack_id": pack_id,
                        "job_index": job_index,
                        "platform_id": str(contact.get("platform_id") or ""),
                        "run_id": resolved_run_id,
                    },
                )
                return result

            raw_path = _write_detail_job(job_dir, job_index, contact, response, resolved_run_id)
            newly_completed += 1
            captured_groups.extend(_captured_field_groups(response))
            _append_detail_ledger(
                paths,
                {
                    "event": "detail_completed",
                    "pack_id": pack_id,
                    "job_index": job_index,
                    "platform_id": str(contact.get("platform_id") or ""),
                    "raw_path": _relative_path(raw_path, paths.root),
                    "run_id": resolved_run_id,
                },
            )
            if position < len(contacts) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        result.update({"status": "completed", "completed": newly_completed, "failed": failed})
        _write_summary(
            paths=paths,
            pack_id=pack_id,
            run_id=resolved_run_id,
            targets=len(contacts),
            completed=newly_completed,
            failed=failed,
            blocked=False,
            template_drift=False,
            captured_field_groups=captured_groups,
            status="completed",
            stop_reason=None,
            next_step="review_detail_smoke_summary",
        )
        return result
    finally:
        session.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行猎聘详情 CDP live smoke gate。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--target-pack", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_live_detail_smoke(
            campaign_root=args.campaign_root,
            target_pack=args.target_pack,
            cdp_url=args.cdp_url,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            limit=args.limit,
            run_id=args.run_id,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
