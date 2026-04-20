"""boss.py — Boss 直聘平台适配器

通过被动拦截浏览器网络请求获取候选人数据。
使用 response listener 在用户手动搜索时捕获 API 响应，
避免 page.evaluate(fetch) 触发反爬检测。

API 调研完成于 2026-04-20，端点和字段映射已校准。
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
# 候选人详情端点（需 securityId）
DETAIL_API_URL = (
    "https://www.zhipin.com/wapi/zpitem/web/boss/search/geeks.json"
)


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

        # 当前公司和职位: geekWork.name = "公司·部门·职位"
        company, title = _parse_geek_work(api_data.get("geekWork"))
        if company:
            result["current_company"] = company
        if title:
            result["current_title"] = title

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

        # 工作经历: workList[].name = "公司·职位", workList[].dateRange
        work_list = api_data.get("workList") or []
        if work_list:
            experiences = []
            for w in work_list:
                w_name = w.get("name", "")
                w_parts = w_name.split("·")
                w_company = w_parts[0] if len(w_parts) >= 2 else w_name
                w_title = w_parts[-1] if len(w_parts) >= 2 else ""
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

    async def search(
        self,
        page: Any,
        params: SearchParams,
    ) -> SearchResult:
        """通过 API 拦截执行搜索。

        注意: Boss 直聘会检测 page.evaluate(fetch)，导致强制登出。
        应使用被动拦截方式（ctx.on('response')）获取数据，
        此方法保留用于手动测试场景。
        """
        try:
            import urllib.parse

            query_params: dict[str, Any] = {
                "keywords": params.query,
                "page": params.page,
                "pageSize": params.page_size,
            }
            if params.city:
                query_params["city"] = params.city
            if params.education:
                query_params["degree"] = params.education
            if params.work_years:
                query_params["workYear"] = params.work_years

            qs = urllib.parse.urlencode(query_params)
            url = f"{SEARCH_API_URL}?{qs}"

            response = await page.evaluate(
                """async (url) => {
                    const resp = await fetch(url, {
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                url,
            )

            if response["status"] != 200:
                return SearchResult(
                    error=SearchError(
                        code="API_ERROR",
                        message=f"Boss API 返回状态码 {response['status']}",
                        retryable=response["status"] in (429, 502, 503),
                    )
                )

            body = json.loads(response["body"])

            data = body.get("zpData", {})
            geeks = data.get("geeks", []) or []
            # 提取每个 geek 的 geekCard
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

    async def get_detail(
        self,
        page: Any,
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。"""
        try:
            response = await page.evaluate(
                """async (url) => {
                    const resp = await fetch(url, {
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                f"{DETAIL_API_URL}{platform_id}",
            )

            if response["status"] != 200:
                return None

            body = json.loads(response["body"])
            data = body.get("zpData", body)

            if not data or not isinstance(data, dict):
                return None

            return CandidateData(
                raw=data,
                platform_id=platform_id,
                detail_url=f"https://www.zhipin.com/web/geek/{platform_id}",
            )
        except Exception:
            logger.error(
                "Boss 获取候选人详情失败: platform_id=%s", platform_id, exc_info=True
            )
            return None
