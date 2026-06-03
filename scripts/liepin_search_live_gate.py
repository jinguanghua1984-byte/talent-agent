"""猎聘 CDP live gate。

只连接已打开的猎聘招聘端页面，通过页面上下文执行白名单接口请求。
不读取浏览器敏感存储或 profile 文件。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_api_contract import (  # noqa: E402
    CONDITION_BY_JOB_URL,
    SEARCH_RESUMES_URL,
    build_condition_request_body,
    build_search_request_body,
    classify_api_result,
    merge_condition_data,
)
from scripts.liepin_browser_runner import build_in_page_fetch_expression  # noqa: E402
from scripts.liepin_browser_runner import sanitize_liepin_request_headers  # noqa: E402
from scripts.liepin_campaign import (  # noqa: E402
    append_request_ledger,
    atomic_write_json,
    ensure_campaign,
    load_completed_pages,
    mark_page_completed,
    write_continuation_plan,
)


DEFAULT_CDP_URL = "http://127.0.0.1:9898"
DEFAULT_DELAY_SECONDS = 3.0
DEFAULT_TIMEOUT_SECONDS = 30.0
REQUEST_TEMPLATE_SCHEMA = "liepin_request_template_v1"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_url_json(url: str, timeout: float = 5) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_targets(cdp_url: str) -> list[dict[str, Any]]:
    data = _read_url_json(cdp_url.rstrip("/") + "/json/list")
    if not isinstance(data, list):
        raise RuntimeError("CDP /json/list did not return a list")
    return [item for item in data if isinstance(item, dict)]


def find_liepin_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    for target in targets:
        url = str(target.get("url") or "")
        if (
            target.get("type") == "page"
            and "h.liepin.com/search/getConditionItem" in url
            and target.get("webSocketDebuggerUrl")
        ):
            return target
    raise RuntimeError("未找到已打开的猎聘招聘端找简历页，请先在专用 Chrome profile 打开猎聘找简历页。")


def health_expression() -> str:
    return """
(() => {
  const text = document.body ? String(document.body.innerText || "") : "";
  const lower = text.toLowerCase();
  const href = String(location.href || "");
  const title = String(document.title || "");
  return {
    href,
    title,
    readyState: document.readyState,
    visibilityState: document.visibilityState,
    hasLoginPrompt: href.indexOf("/login") !== -1 || /登录|扫码登录|手机号登录/.test(text),
    hasCaptcha: lower.indexOf("captcha") !== -1 || /验证码|安全验证|拖动|访问异常/.test(text),
    hasLiepinSearch: href.indexOf("h.liepin.com/search/getConditionItem") !== -1 || title.indexOf("找简历") !== -1
  };
})()
""".strip()


def is_blocking_health(health: dict[str, Any]) -> str | None:
    if health.get("hasLoginPrompt"):
        return "login"
    if health.get("hasCaptcha"):
        return "captcha"
    if not health.get("hasLiepinSearch"):
        return "not_liepin_search"
    return None


class CdpSession:
    def __init__(self, websocket_url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        import websocket

        self._websocket = websocket.create_connection(
            websocket_url,
            timeout=timeout,
            suppress_origin=True,
        )
        self._next_id = 1

    def close(self) -> None:
        self._websocket.close()

    def evaluate(self, expression: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
        message_id = self._next_id
        self._next_id += 1
        self._websocket.settimeout(timeout)
        self._websocket.send(json.dumps({
            "id": message_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
        }))
        while True:
            message = json.loads(self._websocket.recv())
            if message.get("id") != message_id:
                continue
            if message.get("error"):
                raise RuntimeError(message["error"])
            result = message.get("result", {})
            if result.get("exceptionDetails"):
                raise RuntimeError(result["exceptionDetails"])
            runtime_result = result.get("result", {})
            if "value" in runtime_result:
                return runtime_result["value"]
            return None


def _api_classification(response: dict[str, Any]) -> dict[str, Any]:
    return classify_api_result(
        http_status=response.get("httpStatus"),
        content_type=response.get("contentType"),
        raw_text=response.get("rawPreview"),
        parsed=response.get("data"),
    )


def _condition_raw_path(campaign_root: Path, job_id: int | str) -> Path:
    return campaign_root / "raw" / "condition" / f"job-{job_id}.json"


def _request_template_path(paths: Any) -> Path:
    return paths.state_dir / "request-template.json"


def _load_request_template(paths: Any) -> dict[str, Any]:
    template = _load_json(_request_template_path(paths), {})
    if template in (None, {}):
        return {}
    if not isinstance(template, dict):
        raise ValueError("request-template.json must be an object")
    if template.get("schema") not in (None, REQUEST_TEMPLATE_SCHEMA):
        raise ValueError(f"request-template.json schema must be {REQUEST_TEMPLATE_SCHEMA}")
    headers = template.get("headers")
    if headers is not None and not isinstance(headers, dict):
        raise ValueError("request-template.json headers must be an object")
    return template


def _template_headers_for_request(template: dict[str, Any]) -> dict[str, str]:
    return sanitize_liepin_request_headers(
        template.get("headers") if isinstance(template.get("headers"), dict) else {},
        refresh_trace_id=True,
    )


def _write_condition_raw(path: Path, *, response: dict[str, Any], request: dict[str, Any], run_id: str) -> None:
    atomic_write_json(
        path,
        {
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


def _write_interruption(
    *,
    paths: Any,
    reason: str,
    run_id: str,
    cur_page: int,
    stage: str,
    response: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
) -> Path:
    report_path = paths.reports_dir / f"interruption-{reason}-{_timestamp()}.json"
    payload = {
        "schema": "liepin_live_gate_interruption_v1",
        "campaign_id": paths.campaign_id,
        "run_id": run_id,
        "stage": stage,
        "reason": reason,
        "curPage": cur_page,
        "response": response or {},
        "health": health or {},
        "generatedAt": _now(),
    }
    atomic_write_json(report_path, payload)
    append_request_ledger(
        paths,
        {
            "event": "blocked",
            "reason": reason,
            "stage": stage,
            "curPage": cur_page,
            "report_path": report_path.as_posix(),
            "run_id": run_id,
        },
    )
    return report_path


def _page_plan(strategy: dict[str, Any], max_pages: int | None, completed_pages: set[int]) -> list[int]:
    page_plan = strategy.get("page_plan") if isinstance(strategy.get("page_plan"), dict) else {}
    start = int(page_plan.get("start_cur_page") or 0)
    planned = int(max_pages if max_pages is not None else page_plan.get("max_pages") or 1)
    if planned <= 0:
        raise ValueError("max_pages must be positive")
    return [page for page in range(start, start + planned) if page not in completed_pages]


def _job_id(requirements: dict[str, Any]) -> int | str:
    job_id = requirements.get("job_id")
    if job_id in (None, ""):
        raise ValueError("requirements.json must contain job_id")
    return int(job_id) if str(job_id).isdigit() else str(job_id)


def run_live_search(
    *,
    campaign_root: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    max_pages: int | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    requirements = _load_json(paths.requirements, {})
    strategy = _load_json(paths.strategy, {})
    resolved_run_id = run_id or f"liepin-live-{datetime.now().date().isoformat()}"
    resolved_job_id = _job_id(requirements)
    request_template = _load_request_template(paths)

    target = find_liepin_target(list_targets(cdp_url))
    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    result: dict[str, Any] = {
        "schema": "liepin_live_search_run_v1",
        "campaign_id": paths.campaign_id,
        "run_id": resolved_run_id,
        "generatedAt": _now(),
        "cdp_url": cdp_url,
        "pageTarget": {
            "id": target.get("id"),
            "title": target.get("title"),
            "url": target.get("url"),
        },
        "pagesCompleted": [],
        "status": "running",
    }
    try:
        health = session.evaluate(health_expression(), timeout_seconds)
        result["beforeHealth"] = health
        health_block = is_blocking_health(health or {})
        if health_block:
            result["status"] = "blocked"
            result["stopReason"] = health_block
            _write_interruption(
                paths=paths,
                reason=health_block,
                run_id=resolved_run_id,
                cur_page=int((strategy.get("page_plan") or {}).get("start_cur_page") or 0),
                stage="health",
                health=health,
            )
            write_continuation_plan(paths, next_cur_page=0, reason=health_block)
            atomic_write_json(paths.reports_dir / f"live-search-run-{resolved_run_id}.json", result)
            return result

        condition_body = build_condition_request_body(resolved_job_id)
        condition_response = session.evaluate(
            build_in_page_fetch_expression(
                CONDITION_BY_JOB_URL,
                condition_body,
                headers=_template_headers_for_request(request_template),
            ),
            timeout_seconds,
        )
        if not isinstance(condition_response, dict):
            raise RuntimeError("condition response was not an object")
        condition_status = _api_classification(condition_response)
        if not condition_status["ok"]:
            reason = str(condition_status["reason"] or "condition_failed")
            result["status"] = "blocked"
            result["stopReason"] = reason
            _write_interruption(
                paths=paths,
                reason=reason,
                run_id=resolved_run_id,
                cur_page=0,
                stage="condition",
                response=condition_response,
            )
            write_continuation_plan(paths, next_cur_page=0, reason=reason)
            atomic_write_json(paths.reports_dir / f"live-search-run-{resolved_run_id}.json", result)
            return result

        _write_condition_raw(
            _condition_raw_path(paths.root, resolved_job_id),
            response=condition_response,
            request={"url": CONDITION_BY_JOB_URL, "body": condition_body},
            run_id=resolved_run_id,
        )

        completed_pages = load_completed_pages(paths)
        planned_pages = _page_plan(strategy, max_pages, completed_pages)
        result["pagesPlanned"] = planned_pages
        condition_payload = condition_response.get("data") if isinstance(condition_response.get("data"), dict) else {}
        condition_data = condition_payload.get("data") if isinstance(condition_payload.get("data"), dict) else {}
        overrides = strategy.get("overrides") if isinstance(strategy.get("overrides"), dict) else {}
        ck_id = sk_id = fk_id = ""

        for index, cur_page in enumerate(planned_pages):
            search_params = merge_condition_data(
                condition_data,
                overrides,
                job_id=resolved_job_id,
                cur_page=cur_page,
            )
            search_body = build_search_request_body(
                search_params,
                {
                    "ckId": ck_id,
                    "skId": sk_id,
                    "fkId": fk_id,
                    "searchScene": "job",
                },
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
                raise RuntimeError("search response was not an object")
            search_status = _api_classification(search_response)
            if not search_status["ok"]:
                reason = str(search_status["reason"] or "search_failed")
                result["status"] = "blocked"
                result["stopReason"] = reason
                _write_interruption(
                    paths=paths,
                    reason=reason,
                    run_id=resolved_run_id,
                    cur_page=cur_page,
                    stage="search",
                    response=search_response,
                )
                write_continuation_plan(
                    paths,
                    next_cur_page=cur_page,
                    reason=reason,
                    ck_id=ck_id,
                    sk_id=sk_id,
                    fk_id=fk_id,
                )
                atomic_write_json(paths.reports_dir / f"live-search-run-{resolved_run_id}.json", result)
                return result

            payload = search_response.get("data")
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                ck_id = str(payload["data"].get("ckId") or ck_id)
                sk_id = str(payload["data"].get("skId") or sk_id)
                fk_id = str(payload["data"].get("fkId") or fk_id)
            mark_page_completed(
                paths,
                cur_page=cur_page,
                payload=payload,
                request={"url": SEARCH_RESUMES_URL, "body": search_body},
                run_id=resolved_run_id,
            )
            result["pagesCompleted"].append(cur_page)
            if index < len(planned_pages) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        next_page = (max(planned_pages) + 1) if planned_pages else int((strategy.get("page_plan") or {}).get("start_cur_page") or 0)
        write_continuation_plan(
            paths,
            next_cur_page=next_page,
            reason="completed",
            ck_id=ck_id,
            sk_id=sk_id,
            fk_id=fk_id,
        )
        result["status"] = "completed"
        atomic_write_json(paths.reports_dir / f"live-search-run-{resolved_run_id}.json", result)
        return result
    finally:
        session.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行猎聘 CDP live search gate。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_live_search(
            campaign_root=args.campaign_root,
            cdp_url=args.cdp_url,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            max_pages=args.max_pages,
            run_id=args.run_id,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
