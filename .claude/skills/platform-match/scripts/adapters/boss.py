"""boss.py — Boss 直聘平台适配器

通过 Playwright 拦截 Boss 直聘搜索 API 请求获取候选人数据。
采用 API 拦截模式（page.evaluate(fetch)）在已登录浏览器上下文中调用。

注意：API 端点和字段映射为预估，需根据阶段 1 调研结果校准。
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
# Boss 直聘搜索 API 配置（待调研校准）
# ---------------------------------------------------------------------------

SEARCH_API_URL = "https://www.zhipin.com/wapi/zpgeek/search/candidate.json"
DETAIL_API_URL = "https://www.zhipin.com/wapi/zpgeek/card/"


# ---------------------------------------------------------------------------
# 学历枚举映射（待调研校准）
# ---------------------------------------------------------------------------

EDUCATION_MAP: dict[str, str] = {
    "大专": "大专",
    "本科": "本科",
    "硕士": "硕士",
    "博士": "博士",
    "MBA": "硕士",
    "EMBA": "硕士",
}


def _parse_work_years(raw: str | int | None) -> int:
    """从工作年限字符串/数字提取年数。"""
    if raw is None:
        return 0
    if isinstance(raw, int):
        return raw
    match = re.search(r"(\d+)", str(raw))
    return int(match.group(1)) if match else 0


def _normalize_period(raw: str) -> str:
    """将 Boss 直聘日期格式转换为 schema 格式。"""
    if not raw:
        return raw
    raw = raw.strip()
    parts = raw.split("至今")
    if len(parts) == 2:
        start = parts[0].rstrip("-").rstrip(".")
        return f"{start} - 至今"
    # 尝试匹配 YYYY-MM-YYYY-MM 格式
    match = re.match(r"^(\d{4}-\d{2})-(\d{4}-\d{2})$", raw)
    if match:
        return f"{match.group(1)} - {match.group(2)}"
    return raw


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

        字段映射基于预估，需根据阶段 1 调研结果校准。
        """
        result: dict[str, Any] = {}

        result["name"] = api_data.get("name", "")
        result["city"] = api_data.get("cityName", "")
        result["current_company"] = api_data.get("brandName", "")
        result["current_title"] = api_data.get("jobName", "")

        degree = api_data.get("degree")
        if degree:
            result["education"] = EDUCATION_MAP.get(degree, degree)

        work_year = api_data.get("workYear")
        if work_year is not None:
            result["work_years"] = _parse_work_years(work_year)

        gold_hunter = api_data.get("goldHunter")
        if gold_hunter is not None:
            result["status"] = "在职-看机会" if gold_hunter else "在职-不看"

        skills = api_data.get("skills", [])
        if skills:
            result["skill_tags"] = sorted(set(s for s in skills if s))

        experiences = api_data.get("experienceList", [])
        if experiences:
            result["work_experience"] = [
                {
                    "period": _normalize_period(exp.get("period", "")),
                    "company": exp.get("company", ""),
                    "title": exp.get("job", ""),
                    "description": exp.get("description", ""),
                }
                for exp in experiences
                if exp.get("company") or exp.get("job")
            ]

        educations = api_data.get("educationList", [])
        if educations:
            result["education_experience"] = [
                {
                    "period": _normalize_period(edu.get("period", "")),
                    "school": edu.get("school", ""),
                    "major": edu.get("major", ""),
                    "description": edu.get("degree", ""),
                }
                for edu in educations
                if edu.get("school") or edu.get("major")
            ]

        encrypt_id = api_data.get("encryptUserName", "")
        if encrypt_id:
            result["_source"] = {
                "channel": "boss",
                "url": f"https://www.zhipin.com/web/chat/search?query={encrypt_id}",
                "platform_id": encrypt_id,
                "enrichment_level": "enriched",
            }

        return result

    async def search(
        self,
        page: Any,
        params: SearchParams,
    ) -> SearchResult:
        """通过 API 拦截执行搜索。

        请求方式为预估，需根据阶段 1 调研结果校准（GET/POST、参数名等）。
        """
        try:
            import urllib.parse

            query_params: dict[str, Any] = {
                "query": params.query,
                "page": params.page,
                "pageSize": params.page_size,
            }
            if params.city:
                query_params["city"] = params.city
            if params.education:
                query_params["education"] = params.education
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
            items = data.get("hitHitList", []) or []
            total = data.get("totalCount", len(items))
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
                detail_url=f"https://www.zhipin.com/web/geek/card?securityId={platform_id}",
            )
        except Exception:
            logger.error(
                "Boss 获取候选人详情失败: platform_id=%s", platform_id, exc_info=True
            )
            return None
