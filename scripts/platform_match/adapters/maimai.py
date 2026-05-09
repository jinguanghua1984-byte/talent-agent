"""maimai.py — 脉脉平台适配器

通过 Playwright 拦截脉脉搜索 API 请求获取候选人数据。
不使用表单填充，而是直接构造 API 请求。
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
    SearchResult,
    SearchParams,
)


# ---------------------------------------------------------------------------
# 脉脉搜索 API 配置
# ---------------------------------------------------------------------------

SEARCH_API_URL = "https://maimai.cn/api/pc/search/contacts"
DETAIL_API_URL = "https://maimai.cn/api/pc/u/"

HUNTING_STATUS_MAP = {
    5: "在职-看机会",
    0: "在职-不看",
    1: "在职-不看",
    2: "在职-不看",
    3: "在职-不看",
    4: "在职-不看",
}

EDUCATION_MAP = {
    1: "本科",
    2: "硕士",
    3: "博士",
    4: "大专",
}


def _parse_work_years(raw: str) -> int:
    """从 '4年7个月' 提取年数取整。"""
    if not raw:
        return 0
    match = re.search(r"(\d+)年", raw)
    return int(match.group(1)) if match else 0


def _normalize_period(raw: str) -> str:
    """将 '2021-09-01至今' 转换为 '2021-09 - 至今'。"""
    if not raw:
        return raw
    parts = raw.split("至今")
    if len(parts) == 2:
        start = parts[0].rsplit("-", 1)[0] if "-" in parts[0] else parts[0]
        return f"{start} - 至今"
    parts = raw.split("至")
    if len(parts) == 2:
        start = parts[0].rsplit("-", 1)[0] if "-" in parts[0] else parts[0]
        end = parts[1].rsplit("-", 1)[0] if "-" in parts[1] else parts[1]
        return f"{start} - {end}"
    return raw


class MaimaiAdapter:
    """脉脉平台适配器。"""

    platform_name: str = "maimai"

    def build_search_params(
        self,
        candidate: dict | None = None,
        jd: dict | None = None,
        user_input: dict | None = None,
    ) -> list[SearchParams]:
        """构建搜索参数。"""
        params: list[SearchParams] = []

        if candidate:
            name = candidate.get("name", "")
            company = candidate.get("current_company", "")
            title = candidate.get("current_title", "")

            if name and company:
                params.append(SearchParams(query=f"{name} {company}"))
            if name and title:
                params.append(SearchParams(query=f"{name} {title}"))
            if name and not params:
                params.append(SearchParams(query=name))

        elif jd:
            pass

        if user_input and "query" in user_input:
            params.append(SearchParams(
                query=user_input["query"],
                city=user_input.get("city"),
            ))

        return params

    def map_to_schema(self, api_data: dict) -> dict:
        """将脉脉 API 数据映射为 candidate.schema 格式。"""
        result: dict[str, Any] = {}

        result["name"] = api_data.get("name", "")
        result["gender"] = {
            1: "男", 2: "女"
        }.get(api_data.get("gender_str"), "未提及")
        result["age"] = api_data.get("age")
        result["city"] = api_data.get("city", "")
        result["current_company"] = api_data.get("company", "")
        result["current_title"] = api_data.get("position", "")

        sdegree = api_data.get("sdegree")
        if sdegree:
            result["education"] = EDUCATION_MAP.get(sdegree, "本科")

        worktime = api_data.get("worktime", "")
        result["work_years"] = _parse_work_years(worktime)

        hunting = api_data.get("hunting_status")
        if hunting is not None:
            result["status"] = HUNTING_STATUS_MAP.get(hunting, "在职-不看")

        active = api_data.get("active_state")
        if active:
            result["active_state"] = active

        experiences = api_data.get("exp", [])
        if experiences:
            result["work_experience"] = [
                {
                    "period": _normalize_period(exp.get("v", "")),
                    "company": exp.get("company", ""),
                    "title": exp.get("position", ""),
                    "description": exp.get("description", ""),
                }
                for exp in experiences
                if exp.get("company") or exp.get("position")
            ]

        educations = api_data.get("edu", [])
        if educations:
            result["education_experience"] = [
                {
                    "period": _normalize_period(edu.get("v", "")),
                    "school": edu.get("school", ""),
                    "major": edu.get("major", ""),
                    "description": edu.get("sdegree", ""),
                }
                for edu in educations
                if edu.get("school") or edu.get("major")
            ]

        tags = set()
        for tag in api_data.get("exp_tags", []) or []:
            if tag:
                tags.add(tag)
        for tag in api_data.get("tag_list", []) or []:
            if tag:
                tags.add(tag)
        if tags:
            result["skill_tags"] = sorted(tags)

        prefs = api_data.get("job_preferences", {})
        if prefs:
            regions = prefs.get("regions", [])
            if regions:
                result["expected_city"] = regions
            positions = prefs.get("positions", [])
            if positions:
                result["expected_title"] = positions[0]
            salary = prefs.get("salary", "")
            if salary:
                result["expected_salary"] = salary

        projects = api_data.get("user_project", [])
        if projects:
            result["project_experience"] = [
                {
                    "name": p.get("name", ""),
                    "period": _normalize_period(p.get("period", "")),
                    "role": p.get("role", ""),
                    "description": p.get("description", ""),
                }
                for p in projects
                if p.get("name")
            ]

        uid = api_data.get("id", "")
        detail_url = api_data.get("detail_url", "")
        if uid or detail_url:
            result["_source"] = {
                "channel": "maimai",
                "url": detail_url or f"https://maimai.cn/u/{uid}",
                "platform_id": str(uid) if uid else None,
                "enrichment_level": "enriched",
            }

        return result

    async def search(
        self,
        page: Any,
        params: SearchParams,
    ) -> SearchResult:
        """通过 API 拦截执行搜索。"""
        try:
            request_data = {
                "query": params.query,
                "page": params.page,
                "pagesize": params.page_size,
            }

            response = await page.evaluate(
                """async ({url, data}) => {
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data),
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                {"url": SEARCH_API_URL, "data": request_data},
            )

            if response["status"] != 200:
                return SearchResult(
                    error=SearchError(
                        code="API_ERROR",
                        message=f"API 返回状态码 {response['status']}",
                        retryable=response["status"] in (429, 502, 503),
                    )
                )

            body = json.loads(response["body"])
            data = body.get("data", {})

            items = data.get("contacts", []) or data.get("list", []) or []
            total = data.get("total", len(items))
            has_more = params.page * params.page_size < total

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
                    message=f"API 响应解析失败: {e}",
                    retryable=True,
                )
            )
        except Exception as e:
            is_retryable = isinstance(e, (TimeoutError, ConnectionError, OSError))
            if not is_retryable:
                logger.error("搜索执行异常（非重试）: %s", e, exc_info=True)
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
                """async ({url}) => {
                    const resp = await fetch(url, {
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                {"url": f"{DETAIL_API_URL}{platform_id}"},
            )

            if response["status"] != 200:
                return None

            body = json.loads(response["body"])
            data = body.get("data", body)

            if not data:
                return None

            return CandidateData(
                raw=data,
                platform_id=platform_id,
                detail_url=f"https://maimai.cn/u/{platform_id}",
            )
        except Exception:
            logger.error(
                "获取候选人详情失败: platform_id=%s", platform_id, exc_info=True
            )
            return None
