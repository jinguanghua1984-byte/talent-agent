"""猎聘详情 API 被动校准器。

连接已登录猎聘 CDP 页面，监听用户手动打开详情页时产生的 Network 事件；
只记录接口形态和字段名，不保存 Cookie、header 值、query 值或响应字段值。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qs, parse_qsl, unquote_plus, urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_search_live_gate import (  # noqa: E402
    DEFAULT_CDP_URL,
    DEFAULT_TIMEOUT_SECONDS,
    list_targets,
)


DETAIL_API_CALIBRATION_SCHEMA = "liepin_detail_api_calibration_v1"
ALLOWED_DETAIL_API_HOSTS = {"api-h.liepin.com", "h.liepin.com"}
IGNORED_PATH_MARKERS = {
    "/api/com.liepin.searchfront4r.h.get-search-condition-by-job",
    "/api/com.liepin.searchfront4r.h.search-resumes",
}
JSON_MIME_MARKERS = ("json", "javascript")
NETWORK_TYPES = {"XHR", "Fetch"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _safe_run_id(value: str | None) -> str:
    text = str(value or f"detail-api-calibration-{datetime.now().strftime('%Y%m%d%H%M%S')}")
    safe = "".join(char if char.isalnum() or char in "._-" else "-" for char in text).strip("-")
    return safe or "detail-api-calibration"


def find_detail_calibration_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    detail_target: dict[str, Any] | None = None
    search_target: dict[str, Any] | None = None
    for target in targets:
        url = str(target.get("url") or "")
        if target.get("type") != "page" or not target.get("webSocketDebuggerUrl"):
            continue
        if "h.liepin.com/resume/showresumedetail" in url:
            detail_target = target
            break
        if "h.liepin.com/search/getConditionItem" in url:
            search_target = target
    if detail_target is not None:
        return detail_target
    if search_target is not None:
        return search_target
    raise RuntimeError("未找到猎聘搜索页或详情页，请先在专用 Chrome profile 打开猎聘页面。")


def detail_calibration_health_expression() -> str:
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
    hasLoginPrompt: href.indexOf("/login") !== -1 || /扫码登录|手机号登录|密码登录|立即登录|请登录|登录后/.test(text),
    hasCaptcha: lower.indexOf("captcha") !== -1 || /验证码|安全验证|拖动|访问异常/.test(text),
    hasLiepinSearch: href.indexOf("h.liepin.com/search/getConditionItem") !== -1 || title.indexOf("找简历") !== -1,
    hasLiepinDetail: href.indexOf("h.liepin.com/resume/showresumedetail") !== -1
  };
})()
""".strip()


def _calibration_health_block(health: Mapping[str, Any]) -> str | None:
    if health.get("hasLoginPrompt"):
        return "login"
    if health.get("hasCaptcha"):
        return "captcha"
    if not (health.get("hasLiepinSearch") or health.get("hasLiepinDetail")):
        return "not_liepin_page"
    return None


def _page_target_summary(target: Mapping[str, Any]) -> dict[str, Any]:
    url = str(target.get("url") or "")
    parsed = urlsplit(url)
    safe_url = ""
    if parsed.scheme and parsed.netloc and parsed.path:
        safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    title = "liepin_detail" if "/resume/showresumedetail" in parsed.path else "liepin_search"
    return {
        "id": target.get("id"),
        "title": title,
        "url": safe_url,
    }


def _sorted_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    return []


def _request_payload_keys(post_data: Any) -> list[str]:
    text = str(post_data or "").strip()
    if not text:
        return []
    if text.startswith("{"):
        try:
            return _sorted_keys(json.loads(text))
        except json.JSONDecodeError:
            return []
    return sorted(key for key, _value in parse_qsl(text, keep_blank_values=True))


def _nested_payload_keys(post_data: Any) -> dict[str, list[str]]:
    text = str(post_data or "").strip()
    nested_keys: dict[str, list[str]] = {}
    if not text or text.startswith("{"):
        return nested_keys
    for key, value in parse_qsl(text, keep_blank_values=True):
        decoded = unquote_plus(str(value or "")).strip()
        if not decoded.startswith("{"):
            continue
        try:
            parsed = json.loads(decoded)
        except json.JSONDecodeError:
            continue
        keys = _sorted_keys(parsed)
        if keys:
            nested_keys[str(key)] = keys
    return nested_keys


def _response_keys(body_text: str) -> tuple[list[str], list[str], dict[str, list[str]]]:
    try:
        parsed = json.loads(body_text)
    except json.JSONDecodeError:
        return [], [], {}
    top_keys = _sorted_keys(parsed)
    data_keys: list[str] = []
    nested_data_keys: dict[str, list[str]] = {}
    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, dict):
            data_keys = _sorted_keys(data)
            for key, value in data.items():
                keys = _sorted_keys(value)
                if keys:
                    nested_data_keys[str(key)] = keys
    return top_keys, data_keys, nested_data_keys


def _is_candidate_response(request: Mapping[str, Any], response: Mapping[str, Any]) -> bool:
    request_type = str(request.get("type") or response.get("type") or "")
    if request_type and request_type not in NETWORK_TYPES:
        return False
    response_data = response.get("response") if isinstance(response.get("response"), Mapping) else {}
    url = str((response_data or {}).get("url") or (request.get("request") or {}).get("url") or "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in ALLOWED_DETAIL_API_HOSTS:
        return False
    if any(marker in parsed.path for marker in IGNORED_PATH_MARKERS):
        return False
    mime_type = str((response_data or {}).get("mimeType") or "").lower()
    if parsed.netloc == "api-h.liepin.com" and parsed.path.startswith("/api/"):
        return True
    if not any(marker in mime_type for marker in JSON_MIME_MARKERS):
        return False
    return True


def summarize_detail_api_candidate(
    *,
    request: Mapping[str, Any],
    response: Mapping[str, Any],
    body_text: str,
) -> dict[str, Any]:
    request_data = request.get("request") if isinstance(request.get("request"), Mapping) else {}
    response_data = response.get("response") if isinstance(response.get("response"), Mapping) else {}
    url = str(response_data.get("url") or request_data.get("url") or "")
    parsed = urlsplit(url)
    top_keys, data_keys, nested_data_keys = _response_keys(body_text)
    headers = request_data.get("headers") if isinstance(request_data.get("headers"), Mapping) else {}
    return {
        "host": parsed.netloc,
        "path": parsed.path,
        "queryKeys": sorted(parse_qs(parsed.query, keep_blank_values=True).keys()),
        "method": str(request_data.get("method") or ""),
        "resourceType": str(request.get("type") or response.get("type") or ""),
        "httpStatus": response_data.get("status"),
        "mimeType": str(response_data.get("mimeType") or ""),
        "requestHeaderNames": sorted(str(name) for name in headers.keys() if str(name).lower() != "cookie"),
        "requestPayloadKeys": _request_payload_keys(request_data.get("postData")),
        "requestNestedPayloadKeys": _nested_payload_keys(request_data.get("postData")),
        "responseTopLevelKeys": top_keys,
        "responseDataKeys": data_keys,
        "responseNestedDataKeys": nested_data_keys,
    }


class CdpNetworkSession:
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

    def call(self, method: str, params: Mapping[str, Any] | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Any:
        message_id = self._next_id
        self._next_id += 1
        self._websocket.settimeout(timeout)
        self._websocket.send(json.dumps({
            "id": message_id,
            "method": method,
            "params": dict(params or {}),
        }))
        while True:
            message = json.loads(self._websocket.recv())
            if message.get("id") != message_id:
                continue
            if message.get("error"):
                raise RuntimeError(message["error"])
            return message.get("result") or {}

    def recv_event(self, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any] | None:
        self._websocket.settimeout(timeout)
        try:
            message = json.loads(self._websocket.recv())
        except Exception:
            return None
        return message if isinstance(message, dict) and message.get("method") else None


def _evaluate_health(session: Any, timeout_seconds: float) -> dict[str, Any]:
    result = session.call(
        "Runtime.evaluate",
        {
            "expression": detail_calibration_health_expression(),
            "awaitPromise": True,
            "returnByValue": True,
        },
        timeout_seconds,
    )
    value = result.get("result", {}).get("value") if isinstance(result, dict) else None
    return value if isinstance(value, dict) else {}


def calibrate_detail_api(
    *,
    campaign_root: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    listen_seconds: float = 30.0,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    run_id: str | None = None,
) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    safe_run_id = _safe_run_id(run_id)
    target = find_detail_calibration_target(list_targets(cdp_url))
    session = CdpNetworkSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    requests: dict[str, Mapping[str, Any]] = {}
    responses: dict[str, Mapping[str, Any]] = {}
    candidates: list[dict[str, Any]] = []
    try:
        health = _evaluate_health(session, timeout_seconds)
        block = _calibration_health_block(health)
        if block:
            result = {
                "schema": DETAIL_API_CALIBRATION_SCHEMA,
                "campaign_id": paths.campaign_id,
                "run_id": safe_run_id,
                "status": "blocked",
                "stopReason": block,
                "candidate_count": 0,
                "generatedAt": _now(),
            }
            atomic_write_json(paths.reports_dir / f"detail-api-calibration-{safe_run_id}.json", result)
            return result

        session.call("Network.enable", {}, timeout_seconds)
        session.call("Network.setCacheDisabled", {"cacheDisabled": True}, timeout_seconds)
        deadline = time.monotonic() + max(0.0, float(listen_seconds))
        while True:
            if listen_seconds > 0 and time.monotonic() >= deadline:
                break
            event = session.recv_event(timeout_seconds if listen_seconds > 0 else 0)
            if event is None:
                if listen_seconds > 0:
                    continue
                break
            method = str(event.get("method") or "")
            params = event.get("params") if isinstance(event.get("params"), dict) else {}
            request_id = str(params.get("requestId") or "")
            if not request_id:
                continue
            if method == "Network.requestWillBeSent":
                requests[request_id] = params
            elif method == "Network.responseReceived":
                responses[request_id] = params
            elif method == "Network.loadingFinished" and request_id in requests and request_id in responses:
                request = requests[request_id]
                response = responses[request_id]
                if not _is_candidate_response(request, response):
                    continue
                body = session.call("Network.getResponseBody", {"requestId": request_id}, timeout_seconds)
                body_text = str(body.get("body") or "") if isinstance(body, dict) else ""
                candidates.append(summarize_detail_api_candidate(request=request, response=response, body_text=body_text))
            if listen_seconds <= 0:
                continue

        result = {
            "schema": DETAIL_API_CALIBRATION_SCHEMA,
            "campaign_id": paths.campaign_id,
            "run_id": safe_run_id,
            "status": "captured" if candidates else "no_candidates",
            "candidate_count": len(candidates),
            "candidates": candidates,
            "pageTarget": _page_target_summary(target),
            "generatedAt": _now(),
        }
        atomic_write_json(paths.reports_dir / f"detail-api-calibration-{safe_run_id}.json", result)
        atomic_write_json(paths.raw_dir / "detail-calibration" / f"{safe_run_id}.json", result)
        return result
    finally:
        session.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="监听猎聘详情页 Network 事件以校准详情 API。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--listen-seconds", type=float, default=30.0)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = calibrate_detail_api(
            campaign_root=args.campaign_root,
            cdp_url=args.cdp_url,
            listen_seconds=args.listen_seconds,
            timeout_seconds=args.timeout_seconds,
            run_id=args.run_id,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
