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
from scripts.maimai_broad_recall_adaptive import (  # noqa: E402
    adaptive_policy_from_strategy,
    next_unit_status,
    score_page_quality,
)


SEARCH_BLOCK_STATUSES = {403, 429, 432}
ALLOWED_SEARCH_PATHS = {"/api/ent/v3/search/basic"}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _read_jsonl(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        normalized = line.lstrip("\ufeff")
        if not normalized.strip():
            continue
        item = json.loads(normalized)
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8-sig",
    )


def _load_seen_candidate_keys(path: Path | None) -> set[str]:
    return {
        str(row.get("candidate_key"))
        for row in _read_jsonl(path)
        if row.get("candidate_key") not in (None, "")
    }


def _load_adaptive_unit_state(path: Path | None) -> dict[str, dict[str, Any]]:
    if path is None or not path.exists():
        return {}
    data = _load_json(path)
    units = data.get("units") if isinstance(data, dict) else None
    if not isinstance(units, dict):
        return {}
    return {
        str(unit_id): dict(value)
        for unit_id, value in units.items()
        if isinstance(value, dict)
    }


def _write_adaptive_outputs(
    *,
    state_out_path: Path | None,
    seen_out_path: Path | None,
    page_quality_out_path: Path | None,
    unit_state: dict[str, dict[str, Any]],
    seen_candidate_keys: set[str],
    page_quality_rows: list[dict[str, Any]],
) -> None:
    if state_out_path is not None:
        _write_json(
            state_out_path,
            {
                "schema": "maimai_broad_recall_unit_state_v1",
                "units": unit_state,
            },
        )
    if seen_out_path is not None:
        _write_jsonl(seen_out_path, [{"candidate_key": key} for key in sorted(seen_candidate_keys)])
    if page_quality_out_path is not None:
        _write_jsonl(page_quality_out_path, page_quality_rows)


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

  const HIGH_RISK_FILTER_DEFAULTS = {{
    "allcompanies": "",
    "positions": "",
    "cities": "",
    "provinces": "",
    "ht_cities": "",
    "ht_provinces": "",
    "region_scope": "0,1"
  }};

  function applyConfirmedSearchFilters(body, filters) {{
    const target = body && body.search && typeof body.search === "object"
      ? body.search
      : body;
    for (const [key, value] of Object.entries(HIGH_RISK_FILTER_DEFAULTS)) {{
      if (!Object.prototype.hasOwnProperty.call(filters || {{}}, key)) {{
        target[key] = value;
      }}
    }}
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


def _batch_adaptive_probe_pages(batch: dict[str, Any], policy: dict[str, Any]) -> int:
    config = batch.get("adaptive_search") if isinstance(batch.get("adaptive_search"), dict) else {}
    return max(1, int(config.get("probe_pages") or policy["probe_pages"]))


def _batch_adaptive_unit_max_pages(batch: dict[str, Any], policy: dict[str, Any], planned_max_page: int) -> int:
    return max(planned_max_page, int(batch.get("unit_max_pages") or policy["unit_max_pages"]))


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
    max_live_pages: int | None = None,
    adaptive_config_path: Path | None = None,
    adaptive_state_in_path: Path | None = None,
    adaptive_state_out_path: Path | None = None,
    seen_in_path: Path | None = None,
    seen_out_path: Path | None = None,
    page_quality_out_path: Path | None = None,
) -> dict[str, Any]:
    plan = _load_json(plan_path)
    batches = plan.get("batches") or []
    if not isinstance(batches, list) or not batches:
        raise ValueError("plan must contain non-empty batches")
    batch_pages = [iter_batch_pages(batch) for batch in batches]
    max_pages_per_batch = max((len(pages) for pages in batch_pages), default=1)
    gate = str(plan.get("gate") or "S2")
    adaptive_strategy: dict[str, Any] | None = None
    adaptive_policy: dict[str, Any] | None = None
    adaptive_unit_state: dict[str, dict[str, Any]] = {}
    seen_candidate_keys: set[str] = set()
    page_quality_rows: list[dict[str, Any]] = []
    if adaptive_config_path is not None:
        adaptive_strategy = _load_json(adaptive_config_path)
        adaptive_policy = adaptive_policy_from_strategy(adaptive_strategy)
        adaptive_unit_state = _load_adaptive_unit_state(adaptive_state_in_path or adaptive_state_out_path)
        seen_candidate_keys = _load_seen_candidate_keys(seen_in_path or seen_out_path)
        page_quality_rows = _read_jsonl(page_quality_out_path)

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
            "maxLivePages": max_live_pages,
            "abortOn": ["logout", "captcha", "api_captcha", "403", "429", "432", "non_json", "incompatible_request_shape"],
            "delaySeconds": delay_seconds,
        },
        "adaptive": {
            "enabled": adaptive_strategy is not None,
            "config": str(adaptive_config_path) if adaptive_config_path is not None else None,
            "stateIn": str(adaptive_state_in_path) if adaptive_state_in_path is not None else None,
            "stateOut": str(adaptive_state_out_path) if adaptive_state_out_path is not None else None,
            "seenIn": str(seen_in_path) if seen_in_path is not None else None,
            "seenOut": str(seen_out_path) if seen_out_path is not None else None,
            "pageQualityOut": str(page_quality_out_path) if page_quality_out_path is not None else None,
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

        successful_pages = 0
        for index, batch in enumerate(batches, start=1):
            query = str(batch.get("query") or "")
            page_size = int(batch.get("page_size") or 30)
            planned_pages = batch_pages[index - 1]
            start_page = planned_pages[0] if planned_pages else max(1, int(batch.get("start_page") or 1))
            planned_max_page = planned_pages[-1] if planned_pages else start_page
            adaptive_unit_max_page = (
                _batch_adaptive_unit_max_pages(batch, adaptive_policy, planned_max_page)
                if adaptive_policy is not None
                else planned_max_page
            )
            batch_result: dict[str, Any] = {
                "batch_id": batch.get("batch_id"),
                "query": query,
                "ok": False,
                "error": None,
                "startPage": start_page,
                "maxPage": adaptive_unit_max_page if adaptive_policy is not None else planned_max_page,
                "plannedMaxPage": planned_max_page,
                "pages": [],
                "contacts": [],
            }
            if adaptive_policy is not None:
                batch_result["unitMaxPage"] = adaptive_unit_max_page
            try:
                page_index = 0
                page = start_page
                while page <= (adaptive_unit_max_page if adaptive_policy is not None else planned_max_page):
                    if max_live_pages is not None and successful_pages >= max_live_pages:
                        result["status"] = "completed_limited"
                        result["stopReason"] = "max_live_pages"
                        batch_result["adaptiveStopReason"] = "max_live_pages"
                        break

                    page_index += 1
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
                    successful_pages += 1

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

                    if adaptive_strategy is not None and adaptive_policy is not None:
                        unit_id = str(batch.get("unit_id") or batch.get("batch_id") or f"batch-{index}")
                        current_state = adaptive_unit_state.get(
                            unit_id,
                            {
                                "unit_id": unit_id,
                                "status": "active",
                                "consecutive_low_quality_pages": 0,
                            },
                        )
                        page_record = dict(page_result)
                        page_record["unit_id"] = unit_id
                        quality = score_page_quality(
                            page_record,
                            adaptive_strategy,
                            seen_candidate_keys=seen_candidate_keys,
                            policy=adaptive_policy,
                        )
                        page_result["adaptiveQuality"] = quality
                        page_quality_rows.append(quality)
                        next_state = next_unit_status(current_state, quality, adaptive_policy)
                        unit_max_pages = adaptive_unit_max_page
                        if int(quality.get("next_page") or 0) > unit_max_pages:
                            next_state["status"] = "exhausted"
                            next_state["stop_reason"] = "unit_max_pages_exhausted"
                        adaptive_unit_state[unit_id] = next_state
                        for item in quality.get("candidate_scores") or []:
                            candidate_key = item.get("candidate_key") if isinstance(item, dict) else None
                            if candidate_key not in (None, ""):
                                seen_candidate_keys.add(str(candidate_key))
                        _write_adaptive_outputs(
                            state_out_path=adaptive_state_out_path,
                            seen_out_path=seen_out_path,
                            page_quality_out_path=page_quality_out_path,
                            unit_state=adaptive_unit_state,
                            seen_candidate_keys=seen_candidate_keys,
                            page_quality_rows=page_quality_rows,
                        )

                        should_stop_unit = next_state.get("status") in {"stopped_low_quality", "exhausted"}
                        probe_pages = _batch_adaptive_probe_pages(batch, adaptive_policy)
                        if should_stop_unit:
                            if page >= probe_pages:
                                batch_result["adaptiveStopReason"] = next_state.get("status")
                                if next_state.get("stop_reason"):
                                    batch_result["adaptiveStopDetail"] = next_state["stop_reason"]
                                if index < len(batches):
                                    time.sleep(delay_seconds)
                                break

                        next_page = int(quality.get("next_page") or (page + 1))
                        if next_page <= page:
                            next_page = page + 1
                    else:
                        next_page = page + 1

                    if max_live_pages is not None and successful_pages >= max_live_pages:
                        result["status"] = "completed_limited"
                        result["stopReason"] = "max_live_pages"
                        batch_result["adaptiveStopReason"] = "max_live_pages"
                        break

                    has_more_pages = next_page <= (adaptive_unit_max_page if adaptive_policy is not None else planned_max_page)
                    has_more_batches = index < len(batches)
                    if has_more_pages or has_more_batches:
                        time.sleep(delay_seconds)
                    page = next_page

                batch_result["ok"] = not batch_result.get("error")
                result["batches"].append(batch_result)
                if result.get("status") == "stopped":
                    break
                if result.get("status") == "completed_limited":
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
    parser.add_argument("--max-live-pages", type=int)
    parser.add_argument("--adaptive-config")
    parser.add_argument("--adaptive-state-in")
    parser.add_argument("--adaptive-state-out")
    parser.add_argument("--seen-in")
    parser.add_argument("--seen-out")
    parser.add_argument("--page-quality-out")
    args = parser.parse_args(argv)

    result = run_gate(
        plan_path=Path(args.plan),
        out_path=Path(args.out),
        cdp_url=args.cdp_url,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        max_live_pages=args.max_live_pages,
        adaptive_config_path=Path(args.adaptive_config) if args.adaptive_config else None,
        adaptive_state_in_path=Path(args.adaptive_state_in) if args.adaptive_state_in else None,
        adaptive_state_out_path=Path(args.adaptive_state_out) if args.adaptive_state_out else None,
        seen_in_path=Path(args.seen_in) if args.seen_in else None,
        seen_out_path=Path(args.seen_out) if args.seen_out else None,
        page_quality_out_path=Path(args.page_quality_out) if args.page_quality_out else None,
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
