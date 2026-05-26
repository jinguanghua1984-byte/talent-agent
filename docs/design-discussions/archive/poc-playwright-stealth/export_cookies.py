"""
从已登录的 Chrome 导出 maimai.cn cookies → 注入 Playwright → 抓取人才银行 API

步骤：
1. 用 Chrome 扩展或开发者工具导出 cookies（脚本提供指引）
2. 注入到 Playwright 无头浏览器
3. 访问人才银行页面，拦截所有 API
4. 输出 API 结构分析

用法: python capture_maimai_api.py
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

COMMON_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


async def capture_apis(cookies: list[dict]):
    """注入 cookies，访问人才银行，拦截 API"""

    api_calls: list[dict] = []
    json_responses: list[dict] = []

    async with Stealth().use_async(async_playwright()) as p:
        browser = await p.chromium.launch(headless=False)  # 有头模式，方便观察
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=COMMON_UA,
            locale="zh-CN",
        )

        # 注入 cookies
        await context.add_cookies(cookies)
        print(f"[✓] 已注入 {len(cookies)} 个 cookies")

        page = await context.new_page()

        # === 注册请求/响应拦截 ===
        async def on_request(request):
            if request.resource_type in ("xhr", "fetch"):
                url = request.url.split("?")[0]
                # 过滤掉非业务 API（监控、统计、广告）
                skip_domains = [
                    "sentry", "fclog.baidu.com", "hdaa.shuzilm.cn",
                    "hm.baidu.com", "cnzz.com", "analytics",
                ]
                if any(d in request.url for d in skip_domains):
                    return
                print(f"  [API] {request.method} {url}")
                api_calls.append({
                    "method": request.method,
                    "url": url,
                    "full_url": request.url,
                    "type": request.resource_type,
                    "post_data": request.post_data[:500] if request.post_data else None,
                })

        async def on_response(response):
            if response.request.resource_type not in ("xhr", "fetch"):
                return
            url = response.url
            skip_domains = [
                "sentry", "fclog.baidu.com", "hdaa.shuzilm.cn",
                "hm.baidu.com", "cnzz.com", "analytics",
            ]
            if any(d in url for d in skip_domains):
                return
            ct = response.headers.get("content-type", "")
            if "json" in ct:
                try:
                    body = await response.json()
                    short_url = url.split("?")[0]
                    # 截断大响应
                    body_str = json.dumps(body, ensure_ascii=False)
                    if len(body_str) > 2000:
                        body_str = body_str[:2000] + "...(truncated)"
                    json_responses.append({
                        "url": short_url,
                        "status": response.status,
                        "keys": list(body.keys()) if isinstance(body, dict) else type(body).__name__,
                        "preview": body_str,
                    })
                except Exception:
                    pass

        page.on("request", on_request)
        page.on("response", on_response)

        # === 访问人才银行搜索页 ===
        print("\n[1/3] 访问人才银行搜索页...")
        try:
            await page.goto("https://www.maimai.cn/talent/search", timeout=30000)
            await page.wait_for_timeout(5000)
            print(f"  当前 URL: {page.url}")

            # 检查是否被重定向到登录页
            if "login" in page.url.lower() or "passport" in page.url.lower():
                print("  [✗] 被重定向到登录页 — cookies 可能已过期")
                # 截图保存
                await page.screenshot(path=str(RESULTS_DIR / "login_redirect.png"))
                print("  已保存截图: results/login_redirect.png")
                await browser.close()
                return {"error": "被重定向到登录页", "final_url": page.url}

            title = await page.title()
            print(f"  页面标题: {title}")
            await page.screenshot(path=str(RESULTS_DIR / "talent_search_page.png"))
            print("  [✓] 已保存截图: results/talent_search_page.png")

        except Exception as e:
            print(f"  [✗] 页面加载失败: {e}")
            await browser.close()
            return {"error": str(e)}

        # === 模拟一次搜索（关键词搜索）===
        print("\n[2/3] 尝试在搜索框输入关键词...")

        # 等待页面完全加载
        await page.wait_for_timeout(3000)

        # 尝试找到搜索输入框
        search_selectors = [
            'input[placeholder*="搜人才"]',
            'input[placeholder*="搜索"]',
            'input[type="text"]',
            '.search-input input',
            '#search-input',
        ]

        search_box = None
        for sel in search_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    search_box = el
                    print(f"  找到搜索框: {sel}")
                    break
            except Exception:
                continue

        if search_box:
            try:
                await search_box.click()
                await page.wait_for_timeout(500)
                await search_box.fill("产品经理")
                await page.wait_for_timeout(1000)
                await page.keyboard.press("Enter")
                print("  [✓] 已输入 '产品经理' 并回车")
                await page.wait_for_timeout(8000)  # 等待搜索结果和 API 调用

                await page.screenshot(path=str(RESULTS_DIR / "search_results.png"))
                print("  [✓] 已保存搜索结果截图: results/search_results.png")
            except Exception as e:
                print(f"  [!] 搜索操作失败: {e}")
        else:
            print("  [!] 未找到搜索框，尝试用 URL 参数搜索...")
            # 尝试直接带参数访问
            try:
                await page.goto(
                    "https://www.maimai.cn/talent/search?keyword=产品经理",
                    timeout=30000,
                )
                await page.wait_for_timeout(8000)
                await page.screenshot(path=str(RESULTS_DIR / "search_results_url.png"))
                print("  [✓] URL 参数搜索截图已保存")
            except Exception as e:
                print(f"  [!] URL 搜索失败: {e}")

        # === 点击一个搜索结果查看详情页 ===
        print("\n[3/3] 尝试点击搜索结果查看详情...")
        try:
            # 等待搜索结果加载
            result_selectors = [
                '.talent-card', '.search-result-item', '.result-item',
                '[class*="result"]', '[class*="card"]', '[class*="talent"]',
                'a[href*="/talent/"]', 'a[href*="/profile/"]',
            ]

            clicked = False
            for sel in result_selectors:
                try:
                    items = page.locator(sel)
                    count = await items.count()
                    if count > 0:
                        first = items.first
                        if await first.is_visible(timeout=2000):
                            await first.click()
                            print(f"  [✓] 点击了第一个结果: {sel} (共 {count} 个)")
                            clicked = True
                            await page.wait_for_timeout(5000)
                            await page.screenshot(path=str(RESULTS_DIR / "profile_detail.png"))
                            print("  [✓] 已保存详情页截图: results/profile_detail.png")
                            break
                except Exception:
                    continue

            if not clicked:
                print("  [!] 未找到可点击的搜索结果")
        except Exception as e:
            print(f"  [!] 详情页操作失败: {e}")

        await browser.close()

    # === 汇总结果 ===
    domains = list(set(
        c["url"].split("/")[2] for c in api_calls
    )) if api_calls else []

    result = {
        "timestamp": datetime.now().isoformat(),
        "stats": {
            "total_api_calls": len(api_calls),
            "json_responses": len(json_responses),
            "unique_domains": domains,
            "unique_api_paths": list(set(c["url"] for c in api_calls)),
        },
        "api_calls": api_calls,
        "json_responses": json_responses,
    }

    # 保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = RESULTS_DIR / f"maimai_api_capture_{ts}.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"\n[✓] API 抓取结果已保存: {path}")

    return result


def print_usage():
    print("""
=== 脉脉 Cookies 导出指南 ===

方法 1: 使用浏览器开发者工具 (推荐)
  1. 在 Chrome 打开 https://www.maimai.cn/talent/search
  2. 按 F12 打开开发者工具
  3. 切换到 Console 标签
  4. 粘贴以下代码并回车:

    copy(document.cookie.split('; ').map(c => {
      const [name, ...rest] = c.split('=');
      return { name, value: rest.join('='), domain: '.maimai.cn', path: '/' };
    }))

  5. 粘贴结果到 cookies.json 文件

方法 2: 使用 EditThisCookie 扩展
  1. 安装 EditThisCookie 扩展
  2. 打开 maimai.cn
  3. 点击扩展图标 → Export → 复制 JSON
  4. 保存到 cookies.json
""")


async def main():
    cookies_file = Path(__file__).parent / "cookies.json"

    if not cookies_file.exists():
        print_usage()
        print(f"\n请将 cookies 保存到: {cookies_file}")
        print("格式为 JSON 数组: [{name, value, domain, path}, ...]")
        print("\n示例格式:")
        print(json.dumps([
            {"name": "session", "value": "xxx", "domain": ".maimai.cn", "path": "/"},
            {"name": "guid", "value": "xxx", "domain": ".maimai.cn", "path": "/"},
        ], indent=2, ensure_ascii=False))
        return

    cookies = json.loads(cookies_file.read_text())
    print(f"从 {cookies_file} 加载了 {len(cookies)} 个 cookies")

    # 补全缺失字段
    for c in cookies:
        c.setdefault("domain", ".maimai.cn")
        c.setdefault("path", "/")

    result = await capture_apis(cookies)

    # 打印汇总
    if "error" in result:
        print(f"\n[失败] {result['error']}")
    else:
        print("\n" + "=" * 60)
        print("API 抓取汇总")
        print("=" * 60)
        stats = result["stats"]
        print(f"  API 调用: {stats['total_api_calls']}")
        print(f"  JSON 响应: {stats['json_responses']}")
        print(f"  域名: {stats['unique_domains']}")
        print(f"\n  API 路径:")
        for path in stats["unique_api_paths"]:
            print(f"    - {path}")


if __name__ == "__main__":
    asyncio.run(main())
