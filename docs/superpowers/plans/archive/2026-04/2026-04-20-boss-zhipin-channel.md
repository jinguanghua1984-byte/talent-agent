# FEAT-017 | Boss 直聘渠道实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 platform-match 技能中新增 Boss 直聘（`boss`）渠道，复用现有 adapter 架构，支持三种搜索模式。

**Architecture:** 新增 `BossAdapter` 实现 `PlatformAdapter` 协议，采用 API 拦截模式（`page.evaluate(fetch)`）在已登录浏览器上下文中调用 Boss 直聘搜索 API。通过 `adapters/__init__.py` 注册表统一管理适配器，最小化对现有文件的改动。

**Tech Stack:** Python 3.13, Playwright (CDP), pytest

**Spec:** `docs/superpowers/specs/FEAT-017-boss-zhipin-channel-design.md`

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| 新增 | `scripts/adapters/boss.py` | Boss 直聘适配器主体 |
| 修改 | `scripts/adapters/__init__.py` | ADAPTERS 注册表（从 search.py 移入） |
| 修改 | `scripts/adapters/base.py` | SearchParams 新增 education、work_years 字段 |
| 修改 | `scripts/search.py` | 从 adapters 导入 ADAPTERS，移除本地定义 |
| 修改 | `scripts/session.py` | PLATFORM_VERIFY_URLS 新增 boss |
| 修改 | `scripts/enrich.py` | cmd_map 从 ADAPTERS 注册表动态选择适配器 |
| 修改 | `scripts/rate_limiter.py` | DEFAULT_LIMITS 新增 boss 配额 |
| 新增 | `scripts/test_boss.py` | BossAdapter 单元测试（项目根 scripts/） |
| 新增 | `references/boss/api-reference.md` | API 调研文档占位 |
| 新增 | `references/boss/field-mapping.md` | 字段映射表占位 |
| 新增 | `references/boss/anti-detect.md` | 反检测策略占位 |

> **注意：** 所有路径相对于 `.claude/skills/platform-match/` 目录。完整路径如 `d:\workspace\talent-agent\.claude\skills\platform-match\scripts\adapters\boss.py`。

---

## Task 1: 扩展 SearchParams 数据类

**Files:**
- Modify: `scripts/adapters/base.py:12-18`

- [ ] **Step 1: 写失败测试**

在 `d:\workspace\talent-agent\scripts\test_boss.py` 中：

```python
"""boss.py 纯函数单元测试"""

import os
import sys
import unittest

SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", ".claude", "skills", "platform-match", "scripts"
)
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


class TestSearchParamsExtended(unittest.TestCase):
    """SearchParams 扩展字段测试。"""

    def test_education_default_none(self):
        """education 默认值应为 None。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.education)

    def test_work_years_default_none(self):
        """work_years 默认值应为 None。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        self.assertIsNone(params.work_years)

    def test_education_can_be_set(self):
        """education 可设置非 None 值。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试", education="本科")
        self.assertEqual(params.education, "本科")

    def test_work_years_can_be_set(self):
        """work_years 可设置非 None 值。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试", work_years="3-5")
        self.assertEqual(params.work_years, "3-5")

    def test_frozen(self):
        """SearchParams 应为不可变。"""
        from adapters.base import SearchParams
        params = SearchParams(query="测试")
        with self.assertRaises(AttributeError):
            params.query = "修改"


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestSearchParamsExtended -v`
Expected: FAIL — `education` 和 `work_years` 属性不存在

- [ ] **Step 3: 实现 SearchParams 扩展**

修改 `scripts/adapters/base.py` 第 12-18 行，将 `SearchParams` 改为：

```python
@dataclass(frozen=True)
class SearchParams:
    """搜索参数。"""
    query: str
    city: str | None = None
    education: str | None = None
    work_years: str | None = None
    page: int = 1
    page_size: int = 30
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestSearchParamsExtended -v`
Expected: PASS

- [ ] **Step 5: 运行现有 maimai 测试确认无回归**

Run: `cd d:\workspace\talent-agent && python scripts/test_maimai.py -v`
Expected: PASS — 新增字段有默认值，不影响现有适配器

- [ ] **Step 6: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/base.py scripts/test_boss.py
git commit -m "feat(FEAT-017): 扩展 SearchParams 新增 education 和 work_years 可选字段"
```

---

## Task 2: 适配器注册表重构

**Files:**
- Modify: `scripts/adapters/__init__.py`
- Modify: `scripts/search.py:25-36`

- [ ] **Step 1: 写失败测试**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestAdapterRegistry(unittest.TestCase):
    """适配器注册表测试。"""

    def test_adapters_in_init(self):
        """ADAPTERS 应在 adapters/__init__.py 中定义。"""
        from adapters import ADAPTERS
        self.assertIsInstance(ADAPTERS, dict)
        self.assertIn("maimai", ADAPTERS)

    def test_maimai_adapter_registered(self):
        """脉脉适配器应已注册。"""
        from adapters import ADAPTERS
        adapter = ADAPTERS["maimai"]
        self.assertEqual(adapter.platform_name, "maimai")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestAdapterRegistry -v`
Expected: FAIL — `adapters` 模块无 `ADAPTERS` 导出

- [ ] **Step 3: 实现 adapters/__init__.py 注册表**

修改 `scripts/adapters/__init__.py`（当前为空文件），写入：

```python
"""adapters — 平台适配器注册表"""

from adapters.maimai import MaimaiAdapter

ADAPTERS: dict[str, object] = {
    "maimai": MaimaiAdapter(),
}
```

- [ ] **Step 4: 修改 search.py 使用注册表**

修改 `scripts/search.py` 第 25-36 行：

```python
# 删除：
# from adapters.maimai import MaimaiAdapter  # noqa: E402
#
# ADAPTERS = {
#     "maimai": MaimaiAdapter(),
# }

# 替换为：
from adapters import ADAPTERS  # noqa: E402
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestAdapterRegistry -v`
Expected: PASS

- [ ] **Step 6: 运行现有测试确认无回归**

Run: `cd d:\workspace\talent-agent && python scripts/test_maimai.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/__init__.py .claude/skills/platform-match/scripts/search.py scripts/test_boss.py
git commit -m "refactor(FEAT-017): 将 ADAPTERS 注册表从 search.py 移至 adapters/__init__.py"
```

---

## Task 3: enrich.py 动态适配器路由

**Files:**
- Modify: `scripts/enrich.py:178-199`

- [ ] **Step 1: 写失败测试**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestEnrichDynamicRouting(unittest.TestCase):
    """enrich.py 动态路由测试。"""

    def test_cmd_map_looks_up_adapters_registry(self):
        """cmd_map 应通过 ADAPTERS 注册表查找适配器。"""
        from unittest.mock import patch, MagicMock
        from adapters import ADAPTERS

        # 用 mock 替换 ADAPTERS 中的 maimai 适配器
        mock_adapter = MagicMock()
        mock_adapter.map_to_schema.return_value = {"name": "mocked"}

        with patch.dict(ADAPTERS, {"maimai": mock_adapter}):
            from enrich import cmd_map
            args = type("Args", (), {
                "platform": "maimai",
                "api_data": '{"name": "测试"}',
            })()
            cmd_map(args)
            mock_adapter.map_to_schema.assert_called_once_with({"name": "测试"})

    def test_cmd_map_unknown_platform(self):
        """不支持的 platform 应返回错误。"""
        from enrich import cmd_map
        args = type("Args", (), {
            "platform": "unknown_platform",
            "api_data": '{"name": "测试"}',
        })()
        result = cmd_map(args)
        self.assertEqual(result, 1)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestEnrichDynamicRouting -v`
Expected: FAIL — `ADAPTERS` 中无法注入 mock（当前 cmd_map 硬编码了 `MaimaiAdapter()`）

- [ ] **Step 3: 实现 cmd_map 动态路由**

修改 `scripts/enrich.py` 第 178-199 行的 `cmd_map` 函数：

```python
def cmd_map(args):
    """将 API 数据映射为 schema 格式。"""
    from adapters import ADAPTERS

    adapter = ADAPTERS.get(args.platform)
    if not adapter:
        print(json.dumps({
            "status": "error",
            "code": "UNKNOWN_PLATFORM",
            "message": f"不支持的平台: {args.platform}",
        }, ensure_ascii=False, indent=2))
        return 1

    try:
        api_data = json.loads(args.api_data)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "code": "INVALID_JSON",
            "message": f"JSON 解析失败: {e}",
        }, ensure_ascii=False, indent=2))
        return 1

    mapped = adapter.map_to_schema(api_data)
    print(json.dumps({
        "status": "ok",
        "data": mapped,
    }, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestEnrichDynamicRouting -v`
Expected: PASS

- [ ] **Step 5: 运行现有 enrich 测试确认无回归**

Run: `cd d:\workspace\talent-agent && python scripts/test_enrich.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add .claude/skills/platform-match/scripts/enrich.py scripts/test_boss.py
git commit -m "refactor(FEAT-017): enrich.py cmd_map 改为从 ADAPTERS 注册表动态路由"
```

---

## Task 4: 注册 Boss 渠道基础设施

**Files:**
- Modify: `scripts/session.py:37-39`
- Modify: `scripts/rate_limiter.py:65-67`

- [ ] **Step 1: 写失败测试**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestBossInfrastructureRegistration(unittest.TestCase):
    """Boss 渠道基础设施注册测试。"""

    def test_session_verify_url_registered(self):
        """session.py 应注册 boss 平台验证 URL。"""
        from session import PLATFORM_VERIFY_URLS
        self.assertIn("boss", PLATFORM_VERIFY_URLS)
        self.assertEqual(PLATFORM_VERIFY_URLS["boss"], "https://www.zhipin.com/")

    def test_rate_limiter_default_limits_registered(self):
        """rate_limiter.py 应注册 boss 默认配额。"""
        from rate_limiter import DEFAULT_LIMITS
        self.assertIn("boss", DEFAULT_LIMITS)
        boss_config = DEFAULT_LIMITS["boss"]
        self.assertEqual(boss_config.batch_max, 20)
        self.assertEqual(boss_config.daily_max, 150)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossInfrastructureRegistration -v`
Expected: FAIL — `boss` 未在 `PLATFORM_VERIFY_URLS` 和 `DEFAULT_LIMITS` 中注册

- [ ] **Step 3: 注册 Boss 平台验证 URL**

修改 `scripts/session.py` 第 37-39 行：

```python
PLATFORM_VERIFY_URLS = {
    "maimai": "https://maimai.cn/",
    "boss": "https://www.zhipin.com/",
}
```

- [ ] **Step 4: 注册 Boss 限流配额**

修改 `scripts/rate_limiter.py` 第 65-67 行：

```python
DEFAULT_LIMITS = {
    "maimai": ElasticConfig(),
    "boss": ElasticConfig(batch_max=20, daily_max=150),
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossInfrastructureRegistration -v`
Expected: PASS

- [ ] **Step 6: 运行现有限流测试确认无回归**

Run: `cd d:\workspace\talent-agent && python scripts/test_rate_limiter.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add .claude/skills/platform-match/scripts/session.py .claude/skills/platform-match/scripts/rate_limiter.py scripts/test_boss.py
git commit -m "feat(FEAT-017): 注册 Boss 直聘基础设施（session 验证 + 限流配额）"
```

---

## Task 5: 实现 BossAdapter 核心骨架

**Files:**
- Create: `scripts/adapters/boss.py`

> **前置条件：** 阶段 1（API 调研）完成后执行。以下实现基于预估的 API 结构，最终字段映射需根据调研结果校准。

- [ ] **Step 1: 写失败测试 — platform_name**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestBossAdapterBasic(unittest.TestCase):
    """BossAdapter 基础属性测试。"""

    def _make_adapter(self):
        from adapters.boss import BossAdapter
        return BossAdapter()

    def test_platform_name(self):
        """platform_name 应为 'boss'。"""
        adapter = self._make_adapter()
        self.assertEqual(adapter.platform_name, "boss")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossAdapterBasic -v`
Expected: FAIL — `adapters.boss` 模块不存在

- [ ] **Step 3: 实现 BossAdapter 骨架**

创建 `scripts/adapters/boss.py`：

```python
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
    # '至今' → '至今'
    parts = raw.split("至今")
    if len(parts) == 2:
        start = parts[0].rstrip("-").rstrip(".")
        return f"{start} - 至今"
    parts = raw.split("-")
    if len(parts) == 2 and len(parts[0]) >= 6:
        start = parts[0].rstrip("-").rstrip(".")
        end = parts[1].rstrip("-").rstrip(".")
        return f"{start} - {end}"
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
            # 构建查询参数（预估为 GET 请求）
            query_params = {
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

            import urllib.parse
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

            # 响应结构为预估，需校准
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossAdapterBasic -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/boss.py scripts/test_boss.py
git commit -m "feat(FEAT-017): 实现 BossAdapter 核心骨架（API 端点待调研校准）"
```

---

## Task 6: BossAdapter 纯函数单元测试

**Files:**
- Modify: `scripts/test_boss.py`

- [ ] **Step 1: 写 build_search_params 测试**

在 `scripts/test_boss.py` 的 `TestBossAdapterBasic` 类末尾追加：

```python
    def _make_adapter(self):
        from adapters.boss import BossAdapter
        return BossAdapter()

    # （已存在的 test_platform_name）


class TestBossBuildSearchParams(unittest.TestCase):
    """BossAdapter.build_search_params 测试。"""

    def _call(self, **kwargs):
        from adapters.boss import BossAdapter
        return BossAdapter().build_search_params(**kwargs)

    def test_candidate_name_and_company(self):
        """姓名 + 公司应生成路径 A。"""
        params = self._call(candidate={"name": "张三", "current_company": "字节跳动"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "张三 字节跳动")

    def test_candidate_name_company_and_title(self):
        """姓名 + 公司 + 职位应生成路径 A 和 B。"""
        params = self._call(
            candidate={"name": "张三", "current_company": "字节跳动", "current_title": "产品经理"}
        )
        self.assertEqual(len(params), 2)
        queries = [p.query for p in params]
        self.assertIn("张三 字节跳动", queries)
        self.assertIn("张三 产品经理", queries)

    def test_candidate_name_with_city(self):
        """城市应传入搜索参数。"""
        params = self._call(
            candidate={"name": "张三", "current_company": "字节跳动", "city": "北京"}
        )
        self.assertEqual(params[0].city, "北京")

    def test_jd_keywords(self):
        """JD 关键词应构建搜索参数。"""
        params = self._call(jd={"keywords": ["Python", "后端"], "city": "上海"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "Python 后端")
        self.assertEqual(params[0].city, "上海")

    def test_jd_with_education_and_work_years(self):
        """JD 应支持学历和工作年限筛选。"""
        params = self._call(jd={
            "keywords": ["产品经理"],
            "education": "本科",
            "work_years": "3-5",
        })
        self.assertEqual(params[0].education, "本科")
        self.assertEqual(params[0].work_years, "3-5")

    def test_user_input(self):
        """用户输入应构建搜索参数。"""
        params = self._call(user_input={"query": "前端", "city": "深圳"})
        self.assertEqual(len(params), 1)
        self.assertEqual(params[0].query, "前端")
        self.assertEqual(params[0].city, "深圳")

    def test_user_input_with_filters(self):
        """用户输入应支持学历和工作年限筛选。"""
        params = self._call(user_input={
            "query": "工程师",
            "education": "硕士",
            "work_years": "5",
        })
        self.assertEqual(params[0].education, "硕士")
        self.assertEqual(params[0].work_years, "5")

    def test_empty_inputs(self):
        """空输入应返回空列表。"""
        self.assertEqual(self._call(), [])
        self.assertEqual(self._call(candidate={}), [])
        self.assertEqual(self._call(jd={}), [])
```

- [ ] **Step 2: 写 map_to_schema 测试**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestBossMapToSchema(unittest.TestCase):
    """BossAdapter.map_to_schema 测试。"""

    def _call(self, api_data):
        from adapters.boss import BossAdapter
        return BossAdapter().map_to_schema(api_data)

    def test_full_data(self):
        """完整 API 数据应正确映射。"""
        result = self._call({
            "name": "张三",
            "cityName": "北京",
            "brandName": "字节跳动",
            "jobName": "高级产品经理",
            "degree": "本科",
            "workYear": "5",
            "goldHunter": True,
            "skills": ["Python", "SQL"],
            "experienceList": [
                {"period": "2020-03至今", "company": "A公司", "job": "PM", "description": "负责产品"},
            ],
            "educationList": [
                {"period": "2016-09-2020-06", "school": "清华", "major": "计算机"},
            ],
            "encryptUserName": "abc123",
        })

        self.assertEqual(result["name"], "张三")
        self.assertEqual(result["city"], "北京")
        self.assertEqual(result["current_company"], "字节跳动")
        self.assertEqual(result["current_title"], "高级产品经理")
        self.assertEqual(result["education"], "本科")
        self.assertEqual(result["work_years"], 5)
        self.assertEqual(result["status"], "在职-看机会")
        self.assertEqual(result["skill_tags"], ["Python", "SQL"])
        self.assertEqual(len(result["work_experience"]), 1)
        self.assertEqual(result["work_experience"][0]["company"], "A公司")
        self.assertEqual(len(result["education_experience"]), 1)
        self.assertEqual(result["education_experience"][0]["school"], "清华")
        self.assertIsNotNone(result.get("_source"))
        self.assertEqual(result["_source"]["channel"], "boss")
        self.assertEqual(result["_source"]["platform_id"], "abc123")

    def test_minimal_data(self):
        """仅姓名应只映射基本字段。"""
        result = self._call({"name": "李四"})
        self.assertEqual(result["name"], "李四")
        self.assertNotIn("education", result)
        self.assertNotIn("work_experience", result)
        self.assertNotIn("_source", result)

    def test_gold_hunter_false(self):
        """goldHunter=False 应映射为 '在职-不看'。"""
        result = self._call({"name": "测试", "goldHunter": False})
        self.assertEqual(result["status"], "在职-不看")

    def test_no_gold_hunter(self):
        """无 goldHunter 不应生成 status。"""
        result = self._call({"name": "测试"})
        self.assertNotIn("status", result)

    def test_empty_skills_ignored(self):
        """空技能列表不应生成 skill_tags。"""
        result = self._call({"name": "测试", "skills": []})
        self.assertNotIn("skill_tags", result)

    def test_work_experience_filters_empty(self):
        """company 和 job 都空的条目应被过滤。"""
        result = self._call({
            "name": "测试",
            "experienceList": [
                {"period": "2020至今", "company": "", "job": ""},
                {"period": "2021至今", "company": "B公司", "job": ""},
            ],
        })
        self.assertEqual(len(result.get("work_experience", [])), 1)


class TestBossParseWorkYears(unittest.TestCase):
    """_parse_work_years 工作年限解析测试。"""

    def _call(self, raw):
        from adapters.boss import _parse_work_years
        return _parse_work_years(raw)

    def test_integer(self):
        """整数应直接返回。"""
        self.assertEqual(self._call(5), 5)

    def test_string_with_number(self):
        """字符串 '5年' 应返回 5。"""
        self.assertEqual(self._call("5年"), 5)

    def test_none(self):
        """None 应返回 0。"""
        self.assertEqual(self._call(None), 0)

    def test_plain_number_string(self):
        """纯数字字符串 '3' 应返回 3。"""
        self.assertEqual(self._call("3"), 3)


class TestBossNormalizePeriod(unittest.TestCase):
    """_normalize_period 日期格式标准化测试。"""

    def _call(self, raw):
        from adapters.boss import _normalize_period
        return _normalize_period(raw)

    def test_to_present(self):
        """'2020-03至今' → '2020-03 - 至今'"""
        self.assertEqual(self._call("2020-03至今"), "2020-03 - 至今")

    def test_date_range(self):
        """'2016-09-2020-06' → '2016-09 - 2020-06'"""
        self.assertEqual(self._call("2016-09-2020-06"), "2016-09 - 2020-06")

    def test_empty(self):
        """空字符串应原样返回。"""
        self.assertEqual(self._call(""), "")

    def test_none(self):
        """None 应原样返回。"""
        self.assertIsNone(self._call(None))
```

- [ ] **Step 3: 运行所有 Boss 测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py -v`
Expected: 全部 PASS

- [ ] **Step 4: 提交**

```bash
git add scripts/test_boss.py
git commit -m "test(FEAT-017): BossAdapter 纯函数完整单元测试"
```

---

## Task 7: 注册 BossAdapter 到适配器注册表

**Files:**
- Modify: `scripts/adapters/__init__.py`

- [ ] **Step 1: 写失败测试**

在 `scripts/test_boss.py` 末尾追加：

```python
class TestBossAdapterRegistered(unittest.TestCase):
    """BossAdapter 注册测试。"""

    def test_boss_in_adapters_registry(self):
        """Boss 适配器应在 ADAPTERS 注册表中。"""
        from adapters import ADAPTERS
        self.assertIn("boss", ADAPTERS)

    def test_boss_adapter_platform_name(self):
        """注册的 Boss 适配器 platform_name 应为 'boss'。"""
        from adapters import ADAPTERS
        self.assertEqual(ADAPTERS["boss"].platform_name, "boss")

    def test_search_imports_from_adapters(self):
        """search.py 的 ADAPTERS 应来自 adapters 模块。"""
        from adapters import ADAPTERS as registry_adapters
        from search import ADAPTERS as search_adapters
        # search.py 的 ADAPTERS 应是同一个对象
        self.assertIs(search_adapters, registry_adapters)
        self.assertIn("boss", search_adapters)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossAdapterRegistered -v`
Expected: FAIL — `boss` 未在 `ADAPTERS` 中

- [ ] **Step 3: 注册 BossAdapter**

修改 `scripts/adapters/__init__.py`：

```python
"""adapters — 平台适配器注册表"""

from adapters.maimai import MaimaiAdapter
from adapters.boss import BossAdapter

ADAPTERS: dict[str, object] = {
    "maimai": MaimaiAdapter(),
    "boss": BossAdapter(),
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd d:\workspace\talent-agent && python scripts/test_boss.py TestBossAdapterRegistered -v`
Expected: PASS

- [ ] **Step 5: 运行全部测试确认无回归**

Run: `cd d:\workspace\talent-agent && python scripts/test_maimai.py -v && python scripts/test_enrich.py -v && python scripts/test_rate_limiter.py -v && python scripts/test_boss.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 提交**

```bash
git add .claude/skills/platform-match/scripts/adapters/__init__.py scripts/test_boss.py
git commit -m "feat(FEAT-017): 注册 BossAdapter 到适配器注册表，全渠道可用"
```

---

## Task 8: 创建 API 调研文档占位

**Files:**
- Create: `references/boss/api-reference.md`
- Create: `references/boss/field-mapping.md`
- Create: `references/boss/anti-detect.md`

- [ ] **Step 1: 创建 references/boss/ 目录和文档**

`references/boss/api-reference.md`:

```markdown
# Boss 直聘搜索 API 参考

> 状态: 待调研（阶段 1）

## 搜索 API

- **端点**: 待确认
- **方法**: 待确认（预估 GET）
- **Content-Type**: 待确认

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| page | int | 否 | 页码 |
| pageSize | int | 否 | 每页数量 |
| city | string | 否 | 城市筛选 |
| education | string | 否 | 学历筛选 |
| workYear | string | 否 | 工作年限筛选 |

### 响应结构

待调研填写。

## 详情 API

待调研填写。

## 验收标准

- [ ] 确认搜索 API 端点 URL
- [ ] 确认请求方式（GET/POST）
- [ ] 确认请求参数结构
- [ ] 确认响应结构
- [ ] 确认是否有签名/加密机制
- [ ] 确认 encryptUserName 跨 session 稳定性
- [ ] 能用 page.evaluate(fetch) 成功获取 JSON 响应
```

`references/boss/field-mapping.md`:

```markdown
# Boss 直聘 → candidate.schema 字段映射

> 状态: 待调研校准

| Boss API 字段（预估） | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| cityName | city | 直接映射 |
| brandName | current_company | 直接映射 |
| jobName | current_title | 直接映射 |
| degree | education | 枚举映射 |
| workYear | work_years | 数字解析 |
| goldHunter | status | 布尔映射 |
| skills[] | skill_tags | 直接映射 |
| experienceList[] | work_experience[] | 结构转换 |
| educationList[] | education_experience[] | 结构转换 |
| encryptUserName | _source.platform_id | 直接映射 |

> **注意**: 所有字段名和转换逻辑需在阶段 1 调研后校准。
```

`references/boss/anti-detect.md`:

```markdown
# Boss 直聘反检测策略

> 状态: 待调研

## 频率控制

| 参数 | CDP 模式 | Headless 模式 |
|------|---------|-------------|
| 单次搜索间隔 | 5-10s | 10-20s |
| 单批搜索上限 | 20 | 10 |
| 每日搜索上限 | 150 | 60 |
| 连续操作上限 | 30 分钟暂停 60-120s | 20 分钟暂停 60-120s |
| 单页翻页间隔 | 2-5s | 5-10s |

## 反检测措施

1. 请求间隔随机化（非固定间隔）
2. User-Agent 保持与浏览器一致（page.evaluate 天然满足）
3. 单次搜索翻页不超过 3 页
4. 连续搜索 30 分钟后暂停 60-120s
5. 不在凌晨高频请求

## 待确认

- [ ] Boss 直聘是否有请求频率限制
- [ ] 是否有验证码触发机制
- [ ] 是否有 IP 封禁策略
- [ ] 是否有行为检测（鼠标移动、滚动等）
```

- [ ] **Step 2: 提交**

```bash
git add .claude/skills/platform-match/references/boss/
git commit -m "docs(FEAT-017): 创建 Boss 直聘 API 调研文档占位"
```

---

## 验证清单

全部 Task 完成后运行：

```bash
cd d:\workspace\talent-agent
python scripts/test_maimai.py -v
python scripts/test_enrich.py -v
python scripts/test_rate_limiter.py -v
python scripts/test_boss.py -v
```

全部 PASS 即为完成。

---

## 后续步骤（本计划不包含）

1. **阶段 1 — API 调研**: 用户在 Chrome DevTools 中抓取 Boss 直聘搜索 API，填写 `references/boss/api-reference.md`
2. **校准 BossAdapter**: 根据调研结果修正 API 端点、请求方式、字段映射
3. **端到端测试**: 在真实浏览器中验证 `python search.py search --platform boss --query "张三"`
4. **搜索页面 URL 确认**: 确认 Boss 直聘搜索页是否为 `/web/chat/search`
