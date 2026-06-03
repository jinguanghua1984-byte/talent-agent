"""猎聘详情 smoke CDP live gate 的安全辅助函数。

本模块只构建受控详情 fetch 表达式、分类响应和处理本地 job 状态；
不读取浏览器敏感存储，不读取 profile 文件，也不写入数据库。
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_browser_runner import sanitize_liepin_request_headers  # noqa: E402


DETAIL_BLOCK_STATUSES = {401, 403, 429, 432}
DETAIL_TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
DETAIL_RUN_SCHEMA = "liepin_detail_smoke_run_v1"

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


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_detail_url(url: str) -> str:
    parsed = urlsplit(str(url))
    if (
        parsed.scheme == "https"
        and parsed.netloc == "h.liepin.com"
        and parsed.path.startswith("/resume/showresumedetail")
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
        if flag is not None and flag != 1:
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
        try:
            index = int(raw_path.stem.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            continue
        if index < 0:
            continue
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
        if key in {"profile_url", "url", "rawPreview"}:
            continue
        sanitized[key] = sanitize_detail_result_for_report(value)
    return sanitized
