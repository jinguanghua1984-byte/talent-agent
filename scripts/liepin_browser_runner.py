"""猎聘页面内 fetch runner 的安全封装。

P0 只生成受控表达式和 dry-run 元数据；真实浏览器连接由后续授权流程调用。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_api_contract import (  # noqa: E402
    CONDITION_BY_JOB_PATH,
    CONDITION_BY_JOB_URL,
    SEARCH_RESUMES_PATH,
    SEARCH_RESUMES_URL,
)


ALLOWED_URLS = {
    CONDITION_BY_JOB_URL,
    SEARCH_RESUMES_URL,
}
ALLOWED_PATHS = {
    CONDITION_BY_JOB_PATH,
    SEARCH_RESUMES_PATH,
}
FORBIDDEN_STORAGE_READS = [
    "document" + ".cookie",
    "local" + "Storage",
    "session" + "Storage",
]


def validate_allowed_url(url: str) -> str:
    parsed = urlsplit(str(url))
    if (
        parsed.scheme == "https"
        and parsed.netloc == "api-h.liepin.com"
        and parsed.path in ALLOWED_PATHS
        and not parsed.query
        and not parsed.fragment
    ):
        return str(url)
    raise ValueError(f"Liepin URL is not allowed: {url}")


def build_in_page_fetch_expression(url: str, form_body: str) -> str:
    safe_url = validate_allowed_url(url)
    url_json = json.dumps(safe_url, ensure_ascii=False)
    body_json = json.dumps(str(form_body), ensure_ascii=False)
    return f"""
(async () => {{
  const response = await fetch({url_json}, {{
    method: "POST",
    headers: {{
      "Content-Type": "application/x-www-form-urlencoded"
    }},
    body: {body_json},
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


def sensitive_storage_reads(expression: str) -> list[str]:
    return [needle for needle in FORBIDDEN_STORAGE_READS if needle in expression]


def _load_body_json(path: str | Path) -> str:
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict) and isinstance(payload.get("body"), str):
        return payload["body"]
    if isinstance(payload, str):
        return payload
    raise ValueError("body JSON must be a string or object with string field 'body'")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="猎聘页面内 fetch runner dry-run")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry_run = subparsers.add_parser("dry-run-fetch")
    dry_run.add_argument("--url", required=True)
    dry_run.add_argument("--body-json", required=True)
    args = parser.parse_args(argv)

    try:
        body = _load_body_json(args.body_json)
        expression = build_in_page_fetch_expression(args.url, body)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "url": validate_allowed_url(args.url),
        "body": body,
        "expression": expression,
        "sensitive_storage_reads": sensitive_storage_reads(expression),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
