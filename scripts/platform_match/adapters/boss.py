"""boss.py — Boss 直聘平台适配器

通过被动拦截浏览器网络请求获取候选人数据。
使用 response listener 在用户手动搜索时捕获 API 响应，
避免 page.evaluate(fetch) 触发反爬检测。

API 调研完成于 2026-04-20，端点和字段映射已校准。
搜索机制更新于 2026-04-24：关键词选择器、职位筛选清空、滚动翻页。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

from .base import (
    CandidateData,
    PlatformAdapter,
    SearchError,
    SearchParams,
    SearchResult,
)


# ---------------------------------------------------------------------------
# Boss 直聘搜索 API 配置（已校准）
# ---------------------------------------------------------------------------

SEARCH_API_URL = (
    "https://www.zhipin.com/wapi/zpitem/web/boss/search/geeks.json"
)
# 候选人详情端点（待调研，get_detail 暂不可用）
DETAIL_API_URL = ""


# ---------------------------------------------------------------------------
# 学历枚举映射（已校准）
# ---------------------------------------------------------------------------

EDUCATION_MAP: dict[str, str] = {
    "大专": "大专",
    "本科": "本科",
    "硕士": "硕士",
    "博士": "博士",
    "MBA": "硕士",
    "EMBA": "硕士",
}

GENDER_MAP: dict[int, str] = {1: "男", 2: "女"}


def _parse_work_years(raw: str | int | None) -> int:
    """从 '4年' 提取年数。"""
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    match = re.search(r"(\d+)", str(raw))
    return int(match.group(1)) if match else 0


def _parse_age(raw: str | None) -> int | None:
    """从 '27岁' 提取年龄。"""
    if not raw:
        return None
    match = re.search(r"(\d+)", str(raw))
    return int(match.group(1)) if match else None


def _normalize_period(raw: str) -> str:
    """将 Boss 直聘日期格式转换为 schema 格式。"""
    if not raw:
        return raw
    raw = raw.strip()
    parts = raw.split("至今")
    if len(parts) == 2:
        start = parts[0].rstrip("-").rstrip(".")
        return f"{start} - 至今"
    match = re.match(r"^(\d{4}-\d{2})-(\d{4}-\d{2})$", raw)
    if match:
        return f"{match.group(1)} - {match.group(2)}"
    return raw


def _parse_geek_work(geek_work: dict | None) -> tuple[str, str]:
    """从 geekWork.name 解析公司和职位。

    geekWork.name 格式: "公司名·部门·职位名" 或 "公司名·职位名"
    """
    if not geek_work or not geek_work.get("name"):
        return "", ""
    name = geek_work["name"]
    parts = name.split("·")
    if len(parts) >= 3:
        return parts[0], parts[-1]
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, ""


def _parse_geek_edu(geek_edu: dict | None) -> tuple[str, str]:
    """从 geekEdu.name 解析学校和专业。

    geekEdu.name 格式: "国家·学校名·专业名"
    """
    if not geek_edu or not geek_edu.get("name"):
        return "", ""
    name = geek_edu["name"]
    parts = name.split("·")
    if len(parts) >= 3:
        return parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1]
    return name, ""


class BossAdapter:
    """Boss 直聘平台适配器。"""

    platform_name: str = "boss"

    def build_search_params(
        self,
        candidate: dict | None = None,
        jd: dict | None = None,
        user_input: dict | None = None,
    ) -> list[SearchParams]:
        """构建搜索参数。

        模式 1（候选丰富）：双路径搜索
          路径 A: name + current_company
          路径 B: name + current_title
        模式 2（JD 驱动）：从 JD 提取关键词 + 筛选条件
        模式 3（对话式）：从 user_input 构建
        """
        params: list[SearchParams] = []

        if candidate:
            name = candidate.get("name", "")
            company = candidate.get("current_company", "")
            title = candidate.get("current_title", "")
            city = candidate.get("city")

            if name and company:
                params.append(SearchParams(query=f"{name} {company}", city=city))
            if name and title:
                params.append(SearchParams(query=f"{name} {title}", city=city))
            if name and not params:
                params.append(SearchParams(query=name, city=city))

        elif jd:
            keywords = jd.get("keywords", [])
            city = jd.get("city")
            education = jd.get("education")
            work_years = jd.get("work_years")
            if keywords:
                query = " ".join(keywords) if isinstance(keywords, list) else str(keywords)
                params.append(SearchParams(
                    query=query,
                    city=city,
                    education=education,
                    work_years=work_years,
                ))

        if user_input and "query" in user_input:
            params.append(SearchParams(
                query=user_input["query"],
                city=user_input.get("city"),
                education=user_input.get("education"),
                work_years=user_input.get("work_years"),
            ))

        return params

    def map_to_schema(self, api_data: dict) -> dict:
        """将 Boss 直聘 API 数据映射为 candidate.schema 格式。

        接收 geekCard 层级的数据（API 返回的 geeks[].geekCard）。
        字段映射基于 2026-04-20 实际 API 响应校准。
        """
        result: dict[str, Any] = {}

        result["name"] = api_data.get("name", "")
        result["city"] = api_data.get("city", "")

        gender = api_data.get("gender")
        if gender and gender in GENDER_MAP:
            result["gender"] = GENDER_MAP[gender]

        # 当前职位: geekWork.name（列表页公司名与职位混合，无法分离）
        geek_work_name = api_data.get("geekWork", {}).get("name", "")
        if geek_work_name:
            company, title = _parse_geek_work(api_data.get("geekWork"))
            if company:
                result["current_company"] = company
            if title:
                result["current_title"] = title
            elif not company:
                result["current_title"] = geek_work_name

        degree = api_data.get("highestDegreeName")
        if degree:
            result["education"] = EDUCATION_MAP.get(degree, degree)

        work_year = api_data.get("workYear")
        if work_year is not None:
            result["work_years"] = _parse_work_years(work_year)

        age = _parse_age(api_data.get("ageDesc"))
        if age is not None:
            result["age"] = age

        active_desc = api_data.get("activeDesc")
        if active_desc:
            result["active_state"] = active_desc

        salary = api_data.get("salary")
        if salary:
            result["expected_salary"] = salary

        # 技能标签: labelMatchList[].markWord
        label_list = api_data.get("labelMatchList") or []
        skill_tags = [item["markWord"] for item in label_list if item.get("markWord")]
        if skill_tags:
            result["skill_tags"] = skill_tags

        # 工作经历: workList[].name（公司名与职位混合）, workList[].dateRange
        work_list = api_data.get("workList") or []
        if work_list:
            experiences = []
            for w in work_list:
                w_name = w.get("name", "")
                w_parts = w_name.split("·")
                if len(w_parts) >= 2:
                    w_company, w_title = w_parts[0], w_parts[-1]
                else:
                    w_company, w_title = w_name, ""
                date_range = _normalize_period(w.get("dateRange", ""))
                if w_company or w_title:
                    experiences.append({
                        "period": date_range,
                        "company": w_company,
                        "title": w_title,
                        "description": "",
                    })
            if experiences:
                result["work_experience"] = experiences

        # 教育经历: geekEdu.name = "国家·学校·专业"
        geek_edu = api_data.get("geekEdu")
        school, major = _parse_geek_edu(geek_edu)
        if school or major:
            result["education_experience"] = [{
                "period": "",
                "school": school,
                "major": major,
                "description": "",
            }]

        encrypt_id = api_data.get("encryptGeekId", "")
        security_id = api_data.get("securityId", "")
        if encrypt_id:
            result["_source"] = {
                "channel": "boss",
                "platform_id": encrypt_id,
                "security_id": security_id,
                "url": f"https://www.zhipin.com/web/geek/{encrypt_id}",
            }

        return result

    async def _find_search_frame(self, page: Any) -> Any:
        """定位搜索 iframe，超时 7.5s。"""
        import asyncio

        for _ in range(15):
            for f in page.frames:
                if "/web/frame/search/" in f.url and "about:" not in f.url:
                    return f
            await asyncio.sleep(0.5)
        return None

    async def _clear_job_filter(self, search_frame: Any) -> None:
        """清空职位筛选为'不限职位'，避免搜索结果为空。"""
        import asyncio

        job_filter = await search_frame.query_selector(".search-current-job")
        if not job_filter:
            return
        current_text = (await job_filter.inner_text()).strip()
        if current_text and current_text != "不限职位":
            await job_filter.click()
            await asyncio.sleep(0.5)
            job_items = await search_frame.query_selector_all(
                'li[ka="search_select_job"]'
            )
            if job_items:
                await job_items[0].click()
                await asyncio.sleep(0.5)

    async def _type_keyword(
        self, search_frame: Any, query: str
    ) -> bool:
        """在 .search-input 中输入关键词。返回是否成功。"""
        import asyncio

        keyword_input = await search_frame.query_selector(".search-input")
        if not keyword_input:
            return False

        await keyword_input.click()
        await asyncio.sleep(0.3)
        await keyword_input.press("Control+a")
        await asyncio.sleep(0.1)
        await keyword_input.press("Backspace")
        await asyncio.sleep(0.3)
        await keyword_input.type(query, delay=100)
        await asyncio.sleep(0.3)

        search_icon = await search_frame.query_selector(".icon-search")
        if search_icon:
            await search_icon.click()
        else:
            await keyword_input.press("Enter")
        return True

    async def search(
        self,
        page: Any,
        params: SearchParams,
    ) -> SearchResult:
        """通过被动网络拦截执行单页搜索。

        在搜索页 iframe 中清空职位筛选、填入关键词并点击搜索图标，
        通过 page.on('response') 拦截 geeks.json API 响应。
        仅返回请求的 page 对应的数据。

        前提: page 必须是已有登录页面（复用 context.pages[0]），
        且当前已处于 Boss 直聘人才搜索页。
        """
        import asyncio
        import urllib.parse

        intercepted_response: Any = None
        target_page_num = str(params.page)

        def on_response(response: Any) -> None:
            nonlocal intercepted_response
            url = response.url
            if "t.zhipin.com" in url:
                return
            if "geeks.json" not in url:
                return
            resp_params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if resp_params.get("page", ["1"])[0] != target_page_num:
                return
            if "keywords" not in resp_params:
                return
            if urllib.parse.unquote_plus(resp_params["keywords"][0]) != params.query:
                return
            intercepted_response = response

        page.on("response", on_response)

        try:
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(0.5)

            search_frame = await self._find_search_frame(page)
            if not search_frame:
                return SearchResult(
                    error=SearchError(
                        code="NO_SEARCH_FRAME",
                        message="未找到搜索 iframe，请确保页面在 Boss 直聘人才搜索页",
                        retryable=True,
                    )
                )

            logger.debug("Boss search: using frame %s", search_frame.url[:80])

            await self._clear_job_filter(search_frame)
            typed = await self._type_keyword(search_frame, params.query)
            if not typed:
                return SearchResult(
                    error=SearchError(
                        code="NO_SEARCH_INPUT",
                        message="未找到关键词输入框，请确保页面在 Boss 直聘人才搜索页",
                        retryable=True,
                    )
                )

            for _ in range(20):
                if intercepted_response is not None:
                    break
                await asyncio.sleep(0.5)
            else:
                return SearchResult(
                    error=SearchError(
                        code="INTERCEPT_TIMEOUT",
                        message="未拦截到 geeks.json 响应，可能未登录或搜索未触发",
                        retryable=True,
                    )
                )

            if intercepted_response.status != 200:
                return SearchResult(
                    error=SearchError(
                        code="API_ERROR",
                        message=f"Boss API 返回状态码 {intercepted_response.status}",
                        retryable=intercepted_response.status in (429, 502, 503, 504),
                    )
                )

            body = await intercepted_response.json()

            data = body.get("zpData", {})
            geeks = data.get("geeks", []) or []
            items = []
            for g in geeks:
                card = g.get("geekCard")
                if card:
                    items.append(card)

            total = data.get("totalCount", len(items))
            has_more = data.get("hasMore", False)

            return SearchResult(
                items=items,
                total=total,
                page=params.page,
                has_more=has_more,
            )
        except json.JSONDecodeError as e:
            return SearchResult(
                error=SearchError(
                    code="PARSE_ERROR",
                    message=f"Boss API 响应解析失败: {e}",
                    retryable=True,
                )
            )
        except Exception as e:
            is_retryable = isinstance(e, (TimeoutError, ConnectionError, OSError))
            if not is_retryable:
                logger.error("Boss 搜索执行异常: %s", e, exc_info=True)
            return SearchResult(
                error=SearchError(
                    code="SEARCH_FAILED",
                    message=str(e),
                    retryable=is_retryable,
                )
            )
        finally:
            page.remove_listener("response", on_response)

    async def search_all_pages(
        self,
        page: Any,
        params: SearchParams,
        max_stall: int = 3,
    ) -> SearchResult:
        """搜索全部页并通过滚动翻页收集所有结果。

        通过滚动搜索 iframe 和主页面到底部触发无限滚动加载，
        被动拦截每一页的 geeks.json 响应，自动去重。

        前提: 同 search()。页面需处于 /web/chat/search。
        """
        import asyncio
        import urllib.parse

        all_items: list[dict] = []
        seen_ids: set[str] = set()
        captured_pages: set[str] = set()
        total = 0
        has_more = True

        async def on_response(response: Any) -> None:
            nonlocal total, has_more
            url = response.url
            if "t.zhipin.com" in url:
                return
            if "geeks.json" not in url:
                return
            resp_params = urllib.parse.parse_qs(
                urllib.parse.urlparse(url).query
            )
            keywords = urllib.parse.unquote_plus(
                resp_params.get("keywords", [""])[0]
            )
            if keywords != params.query:
                return

            page_num = resp_params.get("page", ["1"])[0]
            key = f"p{page_num}"
            if key in captured_pages:
                return
            captured_pages.add(key)

            try:
                body = await response.json()
                zp = body.get("zpData", {})
                geeks = zp.get("geeks", []) or []
                total = zp.get("totalCount", 0)
                has_more = zp.get("hasMore", False)

                for g in geeks:
                    card = g.get("geekCard")
                    if not card:
                        continue
                    eid = card.get("encryptGeekId", "")
                    if eid and eid not in seen_ids:
                        seen_ids.add(eid)
                        all_items.append(card)

                logger.info(
                    "Boss scroll: page=%s new=%d unique=%d total=%d hasMore=%s",
                    page_num,
                    len(geeks),
                    len(all_items),
                    total,
                    has_more,
                )
            except Exception as e:
                logger.warning("Boss scroll: parse error on page %s: %s", page_num, e)

        page.on("response", on_response)

        try:
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(0.5)

            search_frame = await self._find_search_frame(page)
            if not search_frame:
                return SearchResult(
                    error=SearchError(
                        code="NO_SEARCH_FRAME",
                        message="未找到搜索 iframe，请确保页面在 Boss 直聘人才搜索页",
                        retryable=True,
                    )
                )

            await self._clear_job_filter(search_frame)
            typed = await self._type_keyword(search_frame, params.query)
            if not typed:
                return SearchResult(
                    error=SearchError(
                        code="NO_SEARCH_INPUT",
                        message="未找到关键词输入框，请确保页面在 Boss 直聘人才搜索页",
                        retryable=True,
                    )
                )

            # 等待第一页响应
            for _ in range(30):
                if captured_pages:
                    break
                await asyncio.sleep(0.5)

            if not captured_pages:
                return SearchResult(
                    error=SearchError(
                        code="INTERCEPT_TIMEOUT",
                        message="未拦截到 geeks.json 响应，可能未登录或搜索未触发",
                        retryable=True,
                    )
                )

            # 滚动翻页直到 hasMore=False 或连续 max_stall 次无新数据
            stall_count = 0
            prev_count = 0

            while has_more:
                await asyncio.sleep(2)
                await search_frame.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight)"
                )
                await asyncio.sleep(1)

                if len(all_items) == prev_count:
                    stall_count += 1
                    if stall_count >= max_stall:
                        break
                else:
                    stall_count = 0
                prev_count = len(all_items)

            return SearchResult(
                items=all_items,
                total=total,
                page=len(captured_pages),
                has_more=has_more,
            )
        except Exception as e:
            is_retryable = isinstance(e, (TimeoutError, ConnectionError, OSError))
            if not is_retryable:
                logger.error("Boss 搜索执行异常: %s", e, exc_info=True)
            return SearchResult(
                error=SearchError(
                    code="SEARCH_FAILED",
                    message=str(e),
                    retryable=is_retryable,
                )
            )
        finally:
            page.remove_listener("response", on_response)

    async def get_detail(
        self,
        page: Any,
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。

        当前不可用: Boss 直聘详情端点未调研，且 page.evaluate(fetch)
        会触发反爬检测导致强制登出。待改为被动拦截方式实现。
        """
        logger.warning(
            "Boss get_detail 暂不可用: platform_id=%s（需改为被动拦截）",
            platform_id,
        )
        return None
