#!/usr/bin/env python3
"""search.py — API 搜索 + 分页 + 结果解析

封装搜索流程：连接浏览器 → 执行搜索 → 分页获取 → 返回结果。

用法:
    python search.py search --platform maimai --query "张三 阿里巴巴" [--pages 3]
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("错误: 需要安装 playwright。运行: pip install playwright", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.base import SearchParams, SearchResult  # noqa: E402
from adapters.maimai import MaimaiAdapter  # noqa: E402
from rate_limiter import check_search, record_search, record_page, trigger_circuit_break  # noqa: E402


DEFAULT_CDP_URL = "http://localhost:9222"
DEFAULT_PAGES = 3
DEFAULT_PAGE_SIZE = 30

ADAPTERS = {
    "maimai": MaimaiAdapter(),
}


async def _do_search(
    platform: str,
    query: str,
    pages: int = DEFAULT_PAGES,
    headless: bool = False,
) -> dict:
    """执行搜索并返回所有页结果。"""
    adapter = ADAPTERS.get(platform)
    if not adapter:
        return {
            "status": "error",
            "code": "UNKNOWN_PLATFORM",
            "message": f"不支持的平台: {platform}",
            "retryable": False,
        }

    check = check_search(platform, headless)
    if not check["allowed"]:
        return {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": f"触发限流: {check['reason']}",
            "retryable": True,
            "wait_seconds": check.get("wait_seconds", 0),
        }

    delay = check.get("delay_seconds", 0)
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        async with async_playwright() as p:
            if headless:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
            else:
                browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
                context = browser.contexts[0]

            page = await context.new_page()
            params = SearchParams(query=query, page_size=DEFAULT_PAGE_SIZE)

            all_items = []
            total = 0

            for page_num in range(1, pages + 1):
                params = SearchParams(
                    query=query,
                    page=page_num,
                    page_size=DEFAULT_PAGE_SIZE,
                )

                result = await adapter.search(page, params)

                if result.error:
                    if result.error.code in ("CAPTCHA", "FORBIDDEN"):
                        trigger_circuit_break(platform, result.error.code, headless)
                        return {
                            "status": "error",
                            "code": "CIRCUIT_BREAK",
                            "message": f"触发熔断: {result.error.message}",
                            "retryable": False,
                            "trigger_reason": result.error.code,
                        }

                    await asyncio.sleep(2)
                    result = await adapter.search(page, params)
                    if result.error:
                        return {
                            "status": "error",
                            "code": result.error.code,
                            "message": result.error.message,
                            "retryable": result.error.retryable,
                        }

                all_items.extend(result.items)
                total = result.total

                if result.has_more and page_num < pages:
                    page_check = check_search(platform, headless)
                    if not page_check["allowed"]:
                        return {
                            "status": "error",
                            "code": "RATE_LIMITED",
                            "message": f"页间限流: {page_check['reason']}",
                            "retryable": page_check["reason"] != "daily_limit",
                            "wait_seconds": page_check.get("wait_seconds", 0),
                        }
                    page_delay = page_check.get("delay_seconds", 2)
                    await asyncio.sleep(max(page_delay, 2))
                    record_page(platform, headless)

            record_search(platform, headless)

            await browser.close()

            return {
                "status": "ok",
                "data": {
                    "items": all_items,
                    "total": total,
                    "pages_fetched": pages,
                    "query": query,
                    "platform": platform,
                },
            }

    except Exception as e:
        trigger_circuit_break(platform, str(e), headless)
        return {
            "status": "error",
            "code": "SEARCH_EXCEPTION",
            "message": str(e),
            "retryable": True,
        }


async def _cmd_search(args):
    result = await _do_search(
        platform=args.platform,
        query=args.query,
        pages=args.pages,
        headless=args.headless,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="搜索 CLI")
    subparsers = parser.add_subparsers(dest="command")

    search_p = subparsers.add_parser("search", help="执行搜索")
    search_p.add_argument("--platform", required=True, help="平台名称")
    search_p.add_argument("--query", required=True, help="搜索关键词")
    search_p.add_argument("--pages", type=int, default=DEFAULT_PAGES, help="搜索页数")
    search_p.add_argument("--headless", action="store_true")

    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {"search": lambda: _cmd_search(args)}
    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return await handler()


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
