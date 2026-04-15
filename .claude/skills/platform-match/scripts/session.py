#!/usr/bin/env python3
"""session.py — CDP 连接 + session 管理

管理浏览器 session 的连接、验证和 cookies 备份恢复。

用法:
    python session.py status
    python session.py save [--output <path>]
    python session.py verify --platform maimai
    python session.py endpoints
    python session.py restore --platform maimai [--session-file <path>]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("错误: 需要安装 playwright。运行: pip install playwright", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DEFAULT_CDP_URL = "http://localhost:9222"
SESSION_DIR = os.path.join(os.getcwd(), "data", "session")
MAX_COOKIE_BACKUPS = 3

PLATFORM_VERIFY_URLS = {
    "maimai": "https://maimai.cn/",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _ensure_session_dir() -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    return SESSION_DIR


def _cookie_backup_path(platform: str) -> str:
    return os.path.join(_ensure_session_dir(), f"{platform}-cookies.json")


def _list_cookie_backups(platform: str) -> list[str]:
    session_dir = _ensure_session_dir()
    backups = sorted(
        Path(session_dir).glob(f"{platform}-cookies-*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return [str(p) for p in backups]


def _rotate_cookie_backups(platform: str) -> None:
    backups = _list_cookie_backups(platform)
    while len(backups) >= MAX_COOKIE_BACKUPS:
        oldest = backups.pop(0)
        os.remove(oldest)


def _save_cookie_backup(cookies: list[dict], platform: str) -> str:
    _rotate_cookie_backups(platform)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(
        _ensure_session_dir(), f"{platform}-cookies-{timestamp}.json"
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def _output_json(data: dict | list) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

async def _status() -> int:
    """检查 CDP 连接状态。"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
            contexts = browser.contexts
            result = {
                "status": "ok",
                "cdp_url": DEFAULT_CDP_URL,
                "context_count": len(contexts),
            }
            if contexts:
                pages = contexts[0].pages
                result["page_count"] = len(pages)
                if pages:
                    result["current_url"] = pages[0].url
            # CDP 模式不关闭用户浏览器
            _output_json(result)
            return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "CDP_UNREACHABLE",
            "message": f"无法连接到 Chrome CDP: {e}",
            "retryable": True,
            "hint": "请确保 Chrome 已启动: chrome --remote-debugging-port=9222",
        })
        return 1


async def _save(output: str | None) -> int:
    """导出当前浏览器 cookies。"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
            if not browser.contexts:
                _output_json({
                    "status": "error",
                    "code": "NO_CONTEXT",
                    "message": "CDP 连接成功但未找到浏览器上下文，请确保 Chrome 已打开页面",
                    "retryable": True,
                })
                return 1
            context = browser.contexts[0]
            cookies = await context.cookies()
            # CDP 模式不关闭用户浏览器

        output_path = output or _cookie_backup_path("default")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        _output_json({
            "status": "ok",
            "cookie_count": len(cookies),
            "output_path": output_path,
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "SAVE_FAILED",
            "message": str(e),
            "retryable": False,
        })
        return 1


async def _verify(platform: str, mode: str = "cdp") -> int:
    """验证平台登录态。"""
    verify_url = PLATFORM_VERIFY_URLS.get(platform)
    if not verify_url:
        _output_json({
            "status": "error",
            "code": "UNKNOWN_PLATFORM",
            "message": f"不支持的平台: {platform}",
            "retryable": False,
        })
        return 1

    try:
        async with async_playwright() as p:
            if mode == "standalone":
                cookies_path = _cookie_backup_path(platform)
                if not os.path.exists(cookies_path):
                    _output_json({
                        "status": "error",
                        "code": "NO_COOKIES",
                        "message": "未找到 cookies 备份，请先用默认模式执行一次",
                        "retryable": False,
                    })
                    return 1

                with open(cookies_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)

                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                await context.add_cookies(cookies)
            else:
                browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
                context = browser.contexts[0]

            page = await context.new_page()
            await page.goto(verify_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            current_url = page.url
            logged_in = "login" not in current_url.lower()

            browser_cookies = await context.cookies()
            has_auth_cookie = any(
                "token" in c["name"].lower() or "session" in c["name"].lower()
                for c in browser_cookies
            )

            # 仅 standalone (headless) 模式关闭浏览器，CDP 模式不关闭用户浏览器
            if mode == "standalone":
                await browser.close()

            is_valid = logged_in or has_auth_cookie
            _output_json({
                "status": "ok" if is_valid else "error",
                "platform": platform,
                "mode": mode,
                "logged_in": logged_in,
                "has_auth_cookie": has_auth_cookie,
                "current_url": current_url,
            })
            return 0 if is_valid else 1
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "VERIFY_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


async def _endpoints() -> int:
    """列出 CDP 端点信息。"""
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"{DEFAULT_CDP_URL}/json/version", timeout=5)
        data = json.loads(resp.read())
        _output_json({
            "status": "ok",
            "browser": data.get("Browser", ""),
            "user_agent": data.get("User-Agent", ""),
            "websocket_url": data.get("webSocketDebuggerUrl", ""),
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "ENDPOINTS_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


async def _restore(platform: str, session_file: str | None) -> int:
    """从 cookies 备份恢复 session。"""
    cookies_path = session_file or _cookie_backup_path(platform)

    if not os.path.exists(cookies_path):
        _output_json({
            "status": "error",
            "code": "NO_COOKIES",
            "message": f"Cookies 文件不存在: {cookies_path}",
            "retryable": False,
        })
        return 1

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

            verify_url = PLATFORM_VERIFY_URLS.get(platform, "")
            if verify_url:
                page = await context.new_page()
                await page.goto(verify_url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)
                is_valid = "login" not in page.url.lower()
                await browser.close()

                if not is_valid:
                    _output_json({
                        "status": "error",
                        "code": "COOKIES_EXPIRED",
                        "message": "Cookies 已过期，请先用默认模式重新登录",
                        "retryable": False,
                    })
                    return 1

        _output_json({
            "status": "ok",
            "platform": platform,
            "cookies_path": cookies_path,
            "cookie_count": len(cookies),
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "RESTORE_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Session 管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="检查 CDP 连接状态")

    save_p = subparsers.add_parser("save", help="导出 cookies")
    save_p.add_argument("--output", default=None, help="输出路径")

    verify_p = subparsers.add_parser("verify", help="验证平台登录态")
    verify_p.add_argument("--platform", required=True, help="平台名称")
    verify_p.add_argument("--mode", choices=["cdp", "standalone"], default="cdp")

    subparsers.add_parser("endpoints", help="列出 CDP 端点")

    restore_p = subparsers.add_parser("restore", help="从 cookies 恢复 session")
    restore_p.add_argument("--platform", required=True, help="平台名称")
    restore_p.add_argument("--session-file", default=None, help="指定 cookies 文件")

    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status": lambda: _status(),
        "save": lambda: _save(args.output),
        "verify": lambda: _verify(args.platform, args.mode),
        "endpoints": lambda: _endpoints(),
        "restore": lambda: _restore(args.platform, args.session_file),
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return await handler()


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
