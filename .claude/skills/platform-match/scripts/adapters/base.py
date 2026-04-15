"""base.py — PlatformAdapter 协议与类型定义

所有平台适配器必须实现 PlatformAdapter 协议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any


@dataclass(frozen=True)
class SearchParams:
    """搜索参数。"""
    query: str
    city: str | None = None
    page: int = 1
    page_size: int = 30


@dataclass
class SearchError:
    """搜索错误。"""
    code: str
    message: str
    retryable: bool = False
    trigger_reason: str | None = None


@dataclass
class SearchResult:
    """搜索结果。"""
    items: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    page: int = 1
    has_more: bool = False
    error: SearchError | None = None


@dataclass
class CandidateData:
    """从 API 获取的候选人原始数据。"""
    raw: dict[str, Any]
    platform_id: str
    detail_url: str


class PlatformAdapter(Protocol):
    """平台适配器协议。

    新增平台只需创建适配器文件并实现此协议。
    """

    platform_name: str

    def build_search_params(
        self,
        candidate: dict | None = None,
        jd: dict | None = None,
        user_input: dict | None = None,
    ) -> list[SearchParams]:
        """构建搜索参数列表。

        Args:
            candidate: 已有候选人信息（模式 1）
            jd: JD 信息（模式 2）
            user_input: 用户自然语言输入（模式 3）

        Returns:
            搜索参数列表（可能有多组搜索策略）
        """
        ...

    def map_to_schema(self, api_data: dict) -> dict:
        """将 API 原始数据映射为 candidate.schema 格式。

        Args:
            api_data: API 返回的候选人数据

        Returns:
            符合 candidate.schema 的字段字典
        """
        ...

    async def search(
        self,
        page: Any,  # playwright Page
        params: SearchParams,
    ) -> SearchResult:
        """执行搜索。

        Args:
            page: Playwright Page 对象（已连接到浏览器）
            params: 搜索参数

        Returns:
            搜索结果
        """
        ...

    async def get_detail(
        self,
        page: Any,  # playwright Page
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。

        Args:
            page: Playwright Page 对象
            platform_id: 平台用户 ID

        Returns:
            候选人详情数据，不存在则返回 None
        """
        ...
