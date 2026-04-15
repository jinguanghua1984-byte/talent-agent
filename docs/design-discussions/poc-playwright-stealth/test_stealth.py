"""
Playwright + Stealth PoC — platform-match 浏览器工具选型验证

三个测试：
1. 反检测能力 — 用 fingerprint 检测站验证 stealth 效果
2. API 拦截能力 — 拦截 XHR/Fetch 请求并记录
3. Session 持久化 — 保存/加载 cookies

用法: python test_stealth.py [test1|test2|test3|all]
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

SESSION_DIR = Path(__file__).parent / "session_data"
RESULTS_DIR = Path(__file__).parent / "results"
SESSION_DIR.mkdir(exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

COMMON_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
COMMON_VIEWPORT = {"width": 1920, "height": 1080}


def save_result(name: str, data: dict) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"{name}_{ts}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"[结果已保存] {path}")
    return path


async def test1_stealth_detection():
    """测试 1: 反检测能力"""
    print("=" * 60)
    print("测试 1: 反检测能力验证")
    print("=" * 60)

    results = {}
    bot_keywords = ["bot", "automation", "headless", "webdriver", "puppeteer", "playwright"]

    # === 带 stealth ===
    print("\n--- 带 stealth ---")
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=COMMON_VIEWPORT, user_agent=COMMON_UA, locale="zh-CN"
        )
        page = await context.new_page()

        try:
            print("  访问 BotD (FingerprintJS)...")
            await page.goto(
                "https://fingerprintjs.github.io/botd/main/", timeout=30000
            )
            await page.wait_for_timeout(5000)
            text = await page.inner_text("body")
            found = [kw for kw in bot_keywords if kw.lower() in text.lower()]
            results["stealth_botd"] = {
                "bot_keywords_found": found,
                "snippet": text[:600],
            }
            print(f"  关键词: {found if found else '无 (通过!)'}")
        except Exception as e:
            results["stealth_botd"] = {"error": str(e)}
            print(f"  [错误] {e}")
        await browser.close()

    # === 不带 stealth（对照组）===
    print("\n--- 不带 stealth（对照组）---")
    async with async_playwright() as p:
        browser2 = await p.chromium.launch(headless=True)
        context2 = await browser2.new_context(
            viewport=COMMON_VIEWPORT, user_agent=COMMON_UA, locale="zh-CN"
        )
        page2 = await context2.new_page()

        try:
            print("  访问 BotD (FingerprintJS)...")
            await page2.goto(
                "https://fingerprintjs.github.io/botd/main/", timeout=30000
            )
            await page2.wait_for_timeout(5000)
            text2 = await page2.inner_text("body")
            found2 = [kw for kw in bot_keywords if kw.lower() in text2.lower()]
            results["no_stealth_botd"] = {
                "bot_keywords_found": found2,
                "snippet": text2[:600],
            }
            print(f"  关键词: {found2 if found2 else '无'}")
        except Exception as e:
            results["no_stealth_botd"] = {"error": str(e)}
            print(f"  [错误] {e}")
        await browser2.close()

    save_result("test1_stealth_detection", results)
    print("\n测试 1 完成")
    return results


async def test2_api_interception():
    """测试 2: API 拦截能力"""
    print("=" * 60)
    print("测试 2: API 拦截能力验证")
    print("=" * 60)

    api_calls: list[dict] = []
    json_responses: list[dict] = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=COMMON_VIEWPORT, user_agent=COMMON_UA, locale="zh-CN"
        )
        page = await context.new_page()

        async def on_request(request):
            if request.resource_type in ("xhr", "fetch"):
                short_url = request.url.split("?")[0]
                print(f"  [API] {request.method} {short_url}")
                api_calls.append({
                    "method": request.method,
                    "url": short_url,
                    "type": request.resource_type,
                })

        async def on_response(response):
            if response.request.resource_type in ("xhr", "fetch"):
                ct = response.headers.get("content-type", "")
                if "json" in ct:
                    try:
                        body = await response.json()
                        short_url = response.url.split("?")[0]
                        json_responses.append({
                            "url": short_url,
                            "status": response.status,
                            "keys": list(body.keys()) if isinstance(body, dict) else type(body).__name__,
                            "preview": json.dumps(body, ensure_ascii=False)[:200],
                        })
                    except Exception:
                        pass

        page.on("request", on_request)
        page.on("response", on_response)

        for url_label, url in [
            ("脉脉首页", "https://www.maimai.cn/"),
            ("脉脉 web", "https://www.maimai.cn/web/"),
        ]:
            print(f"\n  访问 {url_label}...")
            try:
                await page.goto(url, timeout=30000)
                await page.wait_for_timeout(6000)
            except Exception as e:
                print(f"  [警告] {e}")

        await browser.close()

    domains = list(set(c["url"].split("/")[2] for c in api_calls)) if api_calls else []
    results = {
        "stats": {
            "total_api_calls": len(api_calls),
            "json_responses": len(json_responses),
            "unique_domains": domains,
        },
        "api_calls_sample": api_calls[:30],
        "json_responses_sample": json_responses[:10],
    }

    save_result("test2_api_interception", results)
    print(f"\n  总 API 请求: {len(api_calls)}, JSON 响应: {len(json_responses)}")
    print(f"  域名: {domains}")
    print("\n测试 2 完成")
    return results


async def test3_session_persistence():
    """测试 3: Session 持久化"""
    print("=" * 60)
    print("测试 3: Session 持久化验证")
    print("=" * 60)

    results = {}
    session_file = SESSION_DIR / "maimai_session.json"

    # === 保存 session ===
    print("\n--- 保存 session ---")
    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport=COMMON_VIEWPORT, user_agent=COMMON_UA, locale="zh-CN"
        )
        page = await context.new_page()

        print("  访问 maimai.cn...")
        try:
            await page.goto("https://www.maimai.cn/", timeout=30000)
            await page.wait_for_timeout(5000)
        except Exception as e:
            print(f"  [警告] {e}")

        cookies = await context.cookies()
        local_storage = await page.evaluate(
            "() => { const items = {}; "
            "for (let i = 0; i < localStorage.length; i++) { "
            "const key = localStorage.key(i); "
            "items[key] = localStorage.getItem(key); } "
            "return items; }"
        )

        session_data = {
            "cookies": cookies,
            "localStorage": local_storage,
            "saved_at": datetime.now().isoformat(),
        }
        session_file.write_text(json.dumps(session_data, ensure_ascii=False, indent=2))

        results["save"] = {
            "cookies_count": len(cookies),
            "localStorage_count": len(local_storage),
            "cookie_domains": list(set(c["domain"] for c in cookies)),
            "cookie_names": [c["name"] for c in cookies],
        }
        print(f"  Cookies: {len(cookies)}, localStorage: {len(local_storage)}")
        print(f"  已保存: {session_file}")

        await browser.close()

    # === 恢复 session ===
    print("\n--- 恢复 session ---")
    loaded = json.loads(session_file.read_text())

    async with Stealth().use_async(async_playwright()) as p:
        browser2 = await p.chromium.launch(headless=True)
        context2 = await browser2.new_context(
            viewport=COMMON_VIEWPORT, user_agent=COMMON_UA, locale="zh-CN"
        )

        if loaded["cookies"]:
            await context2.add_cookies(loaded["cookies"])
            print(f"  已注入 {len(loaded['cookies'])} cookies")

        page2 = await context2.new_page()

        # 先导航到域名，再注入 localStorage
        await page2.goto("https://www.maimai.cn/", timeout=30000)
        await page2.wait_for_timeout(1000)

        ls_items = loaded.get("localStorage", {})
        if ls_items:
            js = "".join(
                f'localStorage.setItem("{k}", {json.dumps(v)});' for k, v in ls_items.items()
            )
            await page2.evaluate(js)
            print(f"  已注入 {len(ls_items)} 条 localStorage")

        current_cookies = await context2.cookies()
        print(f"  当前 cookies: {len(current_cookies)}")

        # 尝试访问人才银行
        print("  尝试访问人才银行...")
        try:
            resp = await page2.goto(
                "https://www.maimai.cn/talent/search", timeout=15000
            )
            final_url = page2.url
            redirected = final_url != "https://www.maimai.cn/talent/search"
            results["restore"] = {
                "final_url": final_url,
                "was_redirected": redirected,
                "cookies_count": len(current_cookies),
            }
            print(f"  最终 URL: {final_url}")
            print(f"  被重定向: {'是' if redirected else '否'}")
        except Exception as e:
            results["restore"] = {"error": str(e)}
            print(f"  [错误] {e}")

        await browser2.close()

    save_result("test3_session_persistence", results)
    print("\n测试 3 完成")
    return results


async def main():
    tests = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    if "all" in tests:
        tests = ["test1", "test2", "test3"]

    all_results: dict = {}

    for t in tests:
        if t == "test1":
            all_results["stealth"] = await test1_stealth_detection()
        elif t == "test2":
            all_results["api"] = await test2_api_interception()
        elif t == "test3":
            all_results["session"] = await test3_session_persistence()

    # 汇总
    print("\n" + "=" * 60)
    print("PoC 汇总")
    print("=" * 60)

    if "stealth" in all_results:
        s = all_results["stealth"]
        s_found = len(s.get("stealth_botd", {}).get("bot_keywords_found", []))
        ns_found = len(s.get("no_stealth_botd", {}).get("bot_keywords_found", []))
        print(f"  反检测: stealth={s_found} 关键词, 对照组={ns_found} 关键词")

    if "api" in all_results:
        st = all_results["api"].get("stats", {})
        print(f"  API拦截: {st.get('total_api_calls', 0)} 请求, {st.get('json_responses', 0)} JSON")

    if "session" in all_results:
        sv = all_results["session"].get("save", {})
        rst = all_results["session"].get("restore", {})
        print(f"  Session: 保存 {sv.get('cookies_count', 0)} cookies, "
              f"恢复={'被重定向' if rst.get('was_redirected') else '未重定向'}")


if __name__ == "__main__":
    asyncio.run(main())
