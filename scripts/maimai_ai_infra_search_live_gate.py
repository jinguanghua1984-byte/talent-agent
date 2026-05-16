"""受控执行脉脉 AI Infra 搜索门禁。

该脚本只连接已有 CDP profile 中的人才银行页，不导航、不刷新、不写库。
真实请求基于页面里已被扩展被动捕获的搜索模板，只替换 query/search_query 和分页。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from urllib.parse import urlsplit
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_search_runner import (  # noqa: E402
    confirmed_search_filters_from_batch,
    normalize_confirmed_search_filters,
)


SEARCH_BLOCK_STATUSES = {403, 429, 432}
ALLOWED_SEARCH_PATHS = {"/api/ent/v3/search/basic"}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _read_url_json(url: str, timeout: float = 5) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def list_targets(cdp_url: str) -> list[dict[str, Any]]:
    data = _read_url_json(cdp_url.rstrip("/") + "/json/list")
    if not isinstance(data, list):
        raise RuntimeError("CDP /json/list did not return a list")
    return [item for item in data if isinstance(item, dict)]


def find_talent_target(targets: list[dict[str, Any]]) -> dict[str, Any]:
    for target in targets:
        url = str(target.get("url") or "")
        if (
            target.get("type") == "page"
            and "maimai.cn/ent/v41/recruit/talents" in url
            and target.get("webSocketDebuggerUrl")
        ):
            return target
    raise RuntimeError("未找到已打开的人才银行页，请先在专用 Edge profile 打开人才银行。")


def is_blocking_health(health: dict[str, Any]) -> str | None:
    if health.get("hasLoginPrompt"):
        return "login"
    if health.get("hasCaptcha"):
        return "captcha"
    if not health.get("hasTalentBank"):
        return "not_talent_bank"
    return None


def validate_search_template_status(template_status: dict[str, Any] | None) -> str | None:
    if not template_status or not template_status.get("hasSearchTemplate"):
        return "missing_search_template"
    method = str(template_status.get("method") or "").upper()
    path = urlsplit(str(template_status.get("url") or "")).path
    has_nested_shape = (
        template_status.get("hasSearchObject")
        and template_status.get("hasNestedQueryField")
        and template_status.get("hasNestedPagination")
    )
    has_top_level_shape = (
        template_status.get("hasTopLevelQueryField")
        and template_status.get("hasTopLevelPagination")
    )
    if method != "POST" or path not in ALLOWED_SEARCH_PATHS:
        return "incompatible_request_shape"
    if not template_status.get("hasBody") or not (has_nested_shape or has_top_level_shape):
        return "incompatible_request_shape"
    return None


def _data_container(parsed: Any) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}
    data = parsed.get("data")
    if isinstance(data, dict):
        return data
    return parsed


def extract_contacts(parsed: Any) -> list[dict[str, Any]]:
    data = _data_container(parsed)
    for key in ("contacts", "list", "items", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def api_block_reason(http_status: int | None, parsed: Any) -> str | None:
    if not isinstance(parsed, dict):
        return f"http_{http_status}" if http_status in SEARCH_BLOCK_STATUSES else None
    block_info = parsed.get("block_info")
    if isinstance(block_info, dict):
        block_type = str(block_info.get("block_type") or "").lower()
        captcha_type = str(block_info.get("captcha_type") or "").lower()
        if "captcha" in block_type or captcha_type:
            return "captcha_api"
    if http_status in SEARCH_BLOCK_STATUSES:
        return f"http_{http_status}"
    return None


def summarize_response(
    http_status: int | None,
    content_type: str | None,
    raw_text: str | None,
    parsed: Any,
    parse_error: str | None,
) -> dict[str, Any]:
    data = _data_container(parsed)
    contacts = extract_contacts(parsed)
    return {
        "httpStatus": http_status,
        "contentType": content_type or "",
        "rawLength": len(raw_text or ""),
        "parseError": parse_error,
        "data": {
            "isObject": isinstance(data, dict) and bool(data),
            "rootKeys": sorted(data.keys()) if isinstance(data, dict) else [],
            "total": data.get("total") if isinstance(data, dict) else None,
            "total_match": data.get("total_match") if isinstance(data, dict) else None,
            "count": data.get("count") if isinstance(data, dict) else None,
            "listLength": len(contacts),
        },
    }


def _json_for_js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


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
    cookieVisibleLength: document.cookie ? document.cookie.length : 0,
    hasLoginPrompt: href.indexOf("/login") !== -1 || /登录|扫码登录|手机号登录/.test(text),
    hasCaptcha: lower.indexOf("captcha") !== -1 || /验证码|安全验证|拖动/.test(text),
    hasTalentBank: href.indexOf("maimai.cn/ent/v41/recruit/talents") !== -1 || title.indexOf("人才银行") !== -1
  };
})()
""".strip()


def template_status_expression() -> str:
    return """
(() => {
  function normalizeCapturedSearchRecord(record) {
    if (!record || typeof record !== "object") {
      return null;
    }
    let body = record.body || null;
    if (!body && record.requestBody) {
      try {
        body = JSON.parse(record.requestBody);
      } catch (err) {
        body = null;
      }
    }
    return {
      url: record.url || "",
      method: record.method || "POST",
      headers: record.headers || record.requestHeaders || {},
      headerNames: record.headerNames || Object.keys(record.headers || record.requestHeaders || {}).sort(),
      body,
      contactCount: 0,
      pageMeta: null
    };
  }
  function isSearchTemplate(template) {
    let path = "";
    try {
      path = new URL(template && template.url || "", location.origin).pathname;
    } catch (err) {
      return false;
    }
    return String(template && template.method || "").toUpperCase() === "POST" &&
      path === "/api/ent/v3/search/basic";
  }
  function latestCapturedSearchTemplate() {
    const requests = Array.isArray(window.__maimaiData && window.__maimaiData.requests)
      ? window.__maimaiData.requests
      : [];
    for (let index = requests.length - 1; index >= 0; index -= 1) {
      const template = normalizeCapturedSearchRecord(requests[index]);
      if (template && isSearchTemplate(template)) {
        return template;
      }
    }
    return null;
  }
  const existingTpl = window.__maimaiSearchTemplate || null;
  const tpl = isSearchTemplate(existingTpl) ? existingTpl : latestCapturedSearchTemplate();
  const body = tpl && tpl.body && typeof tpl.body === "object" ? tpl.body : null;
  const search = body && body.search && typeof body.search === "object" ? body.search : null;
  const hasOwn = (target, key) => Boolean(target && Object.prototype.hasOwnProperty.call(target, key));
  return {
    hasMaimaiScraper: Boolean(window.__maimaiScraperV2),
    hasSearchTemplate: Boolean(tpl),
    url: tpl && tpl.url || "",
    method: tpl && tpl.method || "",
    headerNames: tpl && tpl.headerNames || [],
    hasBody: Boolean(body),
    bodyShape: body ? Object.keys(body).sort() : [],
    hasSearchObject: Boolean(search),
    searchShape: search ? Object.keys(search).sort() : [],
    hasNestedQueryField: hasOwn(search, "query") || hasOwn(search, "search_query"),
    hasNestedPagination: Boolean(search && search.paginationParam && typeof search.paginationParam === "object"),
    hasTopLevelQueryField: hasOwn(body, "query") || hasOwn(body, "search_query"),
    hasTopLevelPagination: Boolean(body && body.paginationParam && typeof body.paginationParam === "object"),
    contactCount: tpl && tpl.contactCount || 0,
    pageMeta: tpl && tpl.pageMeta || null
  };
})()
""".strip()


def search_expression(
    query: str,
    page: int,
    page_size: int,
    search_filters: dict[str, Any] | None = None,
) -> str:
    query_json = _json_for_js(query)
    filters_json = _json_for_js(normalize_confirmed_search_filters(search_filters or {}))
    return f"""
(async () => {{
  function normalizeCapturedSearchRecord(record) {{
    if (!record || typeof record !== "object") {{
      return null;
    }}
    let body = record.body || null;
    if (!body && record.requestBody) {{
      try {{
        body = JSON.parse(record.requestBody);
      }} catch (err) {{
        body = null;
      }}
    }}
    return {{
      url: record.url || "",
      method: record.method || "POST",
      headers: record.headers || record.requestHeaders || {{}},
      requestHeaders: record.requestHeaders || record.headers || {{}},
      headerNames: record.headerNames || Object.keys(record.headers || record.requestHeaders || {{}}).sort(),
      body
    }};
  }}

  function latestCapturedSearchTemplate() {{
    const requests = Array.isArray(window.__maimaiData && window.__maimaiData.requests)
      ? window.__maimaiData.requests
      : [];
    for (let index = requests.length - 1; index >= 0; index -= 1) {{
      const template = normalizeCapturedSearchRecord(requests[index]);
      if (template && isCompatibleSearchTemplate(template)) {{
        return template;
      }}
    }}
    return null;
  }}

  const existingTpl = window.__maimaiSearchTemplate || null;
  const tpl = isCompatibleSearchTemplate(existingTpl) ? existingTpl : latestCapturedSearchTemplate();
  if (!tpl || !tpl.body) {{
    return {{ status: "error", error: "missing_search_template" }};
  }}

  function hasOwn(target, key) {{
    return Boolean(target && Object.prototype.hasOwnProperty.call(target, key));
  }}

  function isCompatibleSearchTemplate(template) {{
    let path = "";
    try {{
      path = new URL(template.url || "", location.origin).pathname;
    }} catch (err) {{
      return false;
    }}
    const method = String(template.method || "").toUpperCase();
    const originalBody = template.body && typeof template.body === "object" ? template.body : null;
    const search = originalBody && originalBody.search && typeof originalBody.search === "object"
      ? originalBody.search
      : null;
    const hasNestedShape = Boolean(
      search &&
      (hasOwn(search, "query") || hasOwn(search, "search_query")) &&
      search.paginationParam &&
      typeof search.paginationParam === "object"
    );
    const hasTopLevelShape = Boolean(
      originalBody &&
      (hasOwn(originalBody, "query") || hasOwn(originalBody, "search_query")) &&
      originalBody.paginationParam &&
      typeof originalBody.paginationParam === "object"
    );
    return method === "POST" &&
      path === "/api/ent/v3/search/basic" &&
      Boolean(originalBody) &&
      (hasNestedShape || hasTopLevelShape);
  }}

  if (!isCompatibleSearchTemplate(tpl)) {{
    return {{ status: "error", error: "incompatible_request_shape" }};
  }}

  function setIfPresent(target, key, value) {{
    if (target && Object.prototype.hasOwnProperty.call(target, key)) {{
      target[key] = value;
    }}
  }}

  function applySearchQuery(body, value) {{
    body = body || {{}};
    if (body.search && typeof body.search === "object") {{
      body.search.query = value;
      if (Object.prototype.hasOwnProperty.call(body.search, "search_query")) {{
        body.search.search_query = value;
      }}
    }}
    setIfPresent(body, "query", value);
    setIfPresent(body, "keyword", value);
    setIfPresent(body, "keywords", value);
    setIfPresent(body, "q", value);
    return body;
  }}

  function applyPagerPage(body, nextPage, size) {{
    body = body || {{}};
    if (body.search && body.search.paginationParam) {{
      body.search.paginationParam.page = nextPage;
      body.search.paginationParam.size = size;
      setIfPresent(body.search, "page", Math.max(0, nextPage - 1));
      setIfPresent(body.search, "size", size);
    }} else if (body.paginationParam) {{
      body.paginationParam.page = nextPage;
      body.paginationParam.size = size;
    }}
    setIfPresent(body, "page", nextPage);
    setIfPresent(body, "pageNum", nextPage);
    setIfPresent(body, "pageNo", nextPage);
    setIfPresent(body, "pagesize", size);
    setIfPresent(body, "pageSize", size);
    setIfPresent(body, "limit", size);
    setIfPresent(body, "count", size);
    return body;
  }}

  function applyConfirmedSearchFilters(body, filters) {{
    const target = body && body.search && typeof body.search === "object"
      ? body.search
      : body;
    if (Object.prototype.hasOwnProperty.call(filters || {{}}, "min_age") ||
        Object.prototype.hasOwnProperty.call(filters || {{}}, "max_age")) {{
      delete target.age;
    }}
    for (const [key, value] of Object.entries(filters || {{}})) {{
      target[key] = value;
    }}
    return body;
  }}

  const confirmedFilters = {filters_json};
  const body = applyPagerPage(
    applySearchQuery(JSON.parse(JSON.stringify(tpl.body || {{}})), {query_json}),
    {int(page)},
    {int(page_size)}
  );
  applyConfirmedSearchFilters(body, confirmedFilters);
  const headers = JSON.parse(JSON.stringify(tpl.headers || tpl.requestHeaders || {{}}));
  if (!headers["Content-Type"] && !headers["content-type"]) {{
    headers["Content-Type"] = "application/json";
  }}

  const response = await fetch(tpl.url, {{
    method: tpl.method || "POST",
    headers,
    body: JSON.stringify(body),
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
    rawPreview: raw.slice(0, 2000),
    sent: {{
      url: tpl.url,
      method: tpl.method || "POST",
      headerNames: Object.keys(headers).sort(),
      bodyShape: Object.keys(body || {{}}).sort(),
      search: body && body.search ? body.search : body
    }}
  }};
}})()
""".strip()


def iter_batch_pages(batch: dict[str, Any]) -> list[int]:
    start_page = max(1, int(batch.get("start_page") or 1))
    max_page = max(start_page, int(batch.get("max_pages") or start_page))
    return list(range(start_page, max_page + 1))


class CdpSession:
    def __init__(self, websocket_url: str, timeout: float = 30) -> None:
        import websocket

        self._websocket = websocket.create_connection(
            websocket_url,
            timeout=timeout,
            suppress_origin=True,
        )
        self._next_id = 1

    def close(self) -> None:
        self._websocket.close()

    def evaluate(self, expression: str, timeout: float = 30) -> Any:
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


def run_gate(
    plan_path: Path,
    out_path: Path,
    cdp_url: str,
    delay_seconds: float,
    timeout_seconds: float,
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    batches = plan.get("batches") or []
    if not isinstance(batches, list) or not batches:
        raise ValueError("plan must contain non-empty batches")
    batch_pages = [iter_batch_pages(batch) for batch in batches]
    max_pages_per_batch = max((len(pages) for pages in batch_pages), default=1)
    gate = str(plan.get("gate") or "S2")

    target = find_talent_target(list_targets(cdp_url))
    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    result: dict[str, Any] = {
        "run_id": f"maimai-ai-infra-search-{gate.lower()}-" + datetime.now().date().isoformat(),
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "mode": f"gate_{gate.lower()}_live_search_dry_run_only",
        "constraints": {
            "batches": len(batches),
            "pagesPerBatch": max_pages_per_batch,
            "writeDb": False,
            "apply": False,
            "detailFetch": False,
            "abortOn": ["logout", "captcha", "api_captcha", "403", "429", "432", "non_json", "incompatible_request_shape"],
            "delaySeconds": delay_seconds,
        },
        "pageTarget": {
            "id": target.get("id"),
            "title": target.get("title"),
            "url": target.get("url"),
        },
        "batches": [],
        "contacts": [],
    }
    try:
        before_health = session.evaluate(health_expression(), timeout_seconds)
        result["beforeHealth"] = before_health
        blocking = is_blocking_health(before_health or {})
        if blocking:
            result["status"] = "blocked"
            result["stopReason"] = blocking
            _write_json(out_path, result)
            return result

        template_status = session.evaluate(template_status_expression(), timeout_seconds)
        result["templateStatus"] = template_status
        template_error = validate_search_template_status(template_status)
        if template_error:
            result["status"] = "blocked"
            result["stopReason"] = template_error
            _write_json(out_path, result)
            return result

        for index, batch in enumerate(batches, start=1):
            query = str(batch.get("query") or "")
            page_size = int(batch.get("page_size") or 30)
            batch_result: dict[str, Any] = {
                "batch_id": batch.get("batch_id"),
                "query": query,
                "ok": False,
                "error": None,
                "startPage": batch_pages[index - 1][0] if batch_pages[index - 1] else None,
                "maxPage": batch_pages[index - 1][-1] if batch_pages[index - 1] else None,
                "pages": [],
                "contacts": [],
            }
            try:
                for page_index, page in enumerate(batch_pages[index - 1], start=1):
                    response = session.evaluate(
                        search_expression(
                            query,
                            page,
                            page_size,
                            confirmed_search_filters_from_batch(batch),
                        ),
                        timeout_seconds,
                    )
                    if not isinstance(response, dict):
                        raise RuntimeError("search response was not an object")
                    if response.get("status") != "ok":
                        error = str(response.get("error") or "search_failed")
                        batch_result["error"] = error
                        result["status"] = "stopped"
                        result["stopReason"] = error
                        break

                    parsed = response.get("data")
                    summary = summarize_response(
                        response.get("httpStatus"),
                        response.get("contentType"),
                        "",
                        parsed,
                        response.get("parseError"),
                    )
                    summary["rawLength"] = response.get("rawLength", 0)
                    contacts = extract_contacts(parsed)
                    page_result = {
                        "page": page,
                        "ok": True,
                        "request": response.get("sent") or {},
                        "responseSummary": summary,
                        "responseData": parsed,
                        "responseRawPreview": response.get("rawPreview") or "",
                        "contacts": contacts,
                    }
                    batch_result["pages"].append(page_result)
                    batch_result["contacts"].extend(contacts)
                    result["contacts"].extend(contacts)

                    if "request" not in batch_result:
                        batch_result.update({
                            "request": response.get("sent") or {},
                            "responseSummary": summary,
                            "responseData": parsed,
                            "responseRawPreview": response.get("rawPreview") or "",
                        })

                    block_reason = api_block_reason(response.get("httpStatus"), parsed)
                    if block_reason:
                        batch_result["error"] = block_reason
                        page_result["ok"] = False
                        page_result["error"] = batch_result["error"]
                        result["status"] = "stopped"
                        result["stopReason"] = batch_result["error"]
                        break
                    if response.get("parseError"):
                        batch_result["error"] = "non_json"
                        page_result["ok"] = False
                        page_result["error"] = "non_json"
                        result["status"] = "stopped"
                        result["stopReason"] = "non_json"
                        break

                    health_after = session.evaluate(health_expression(), timeout_seconds)
                    page_result["healthAfter"] = health_after
                    batch_result["healthAfter"] = health_after
                    blocking = is_blocking_health(health_after or {})
                    if blocking:
                        batch_result["error"] = blocking
                        result["status"] = "stopped"
                        result["stopReason"] = blocking
                        break

                    has_more_pages = page_index < len(batch_pages[index - 1])
                    has_more_batches = index < len(batches)
                    if has_more_pages or has_more_batches:
                        time.sleep(delay_seconds)

                batch_result["ok"] = not batch_result.get("error")
                result["batches"].append(batch_result)
                if result.get("status") == "stopped":
                    break
            except Exception as exc:  # noqa: BLE001 - 门禁脚本必须记录异常后停止。
                batch_result["error"] = str(exc)
                result["batches"].append(batch_result)
                result["status"] = "stopped"
                result["stopReason"] = "exception"
                break

        if "status" not in result:
            result["status"] = "completed"
        try:
            result["afterHealth"] = session.evaluate(health_expression(), timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - 平台页异常时也要保留已采集证据。
            result["afterHealthError"] = str(exc)
            if result.get("status") == "completed":
                result["status"] = "stopped"
                result["stopReason"] = "after_health_exception"
        result["finishedAt"] = datetime.now().isoformat(timespec="seconds")
        _write_json(out_path, result)
        return result
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="受控执行脉脉 AI Infra 搜索门禁")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--cdp-url", default="http://127.0.0.1:9888")
    parser.add_argument("--delay-seconds", type=float, default=8)
    parser.add_argument("--timeout-seconds", type=float, default=30)
    args = parser.parse_args(argv)

    result = run_gate(
        plan_path=Path(args.plan),
        out_path=Path(args.out),
        cdp_url=args.cdp_url,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps({
        "status": result.get("status"),
        "stopReason": result.get("stopReason"),
        "batches": len(result.get("batches") or []),
        "contacts": len(result.get("contacts") or []),
        "out": args.out,
    }, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
