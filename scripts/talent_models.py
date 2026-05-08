"""人才库数据模型。

仅定义数据结构，不包含业务逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Candidate:
    id: int
    name: str
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    work_years: int | None = None
    education: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    expected_salary: str | None = None
    expected_city: str | None = None
    expected_title: str | None = None
    hunting_status: str | None = None
    skill_tags: tuple[str, ...] = ()
    data_level: str = "lead"
    overall_score: float = 0.0
    score_version: int = 0
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class CandidateDetail:
    candidate_id: int
    work_experience: tuple[dict[str, Any], ...] | None = None
    education_experience: tuple[dict[str, Any], ...] | None = None
    project_experience: tuple[dict[str, Any], ...] | None = None
    raw_data: dict[str, Any] | None = None
    summary: str | None = None


@dataclass(frozen=True)
class SourceProfile:
    id: int
    candidate_id: int
    platform: str
    platform_id: str | None = None
    profile_url: str | None = None
    raw_profile: dict[str, Any] | None = None
    fetched_at: str | None = None


@dataclass(frozen=True)
class SearchHit:
    id: int
    rank: float
    snippet: str


@dataclass(frozen=True)
class VectorHit:
    id: int
    similarity: float
    name: str
    current_company: str | None = None
    current_title: str | None = None


@dataclass(frozen=True)
class MatchScore:
    id: int
    candidate_id: int
    jd_id: str
    match_type: str
    score: float
    dimensions: dict[str, Any] | None = None
    reason: str | None = None
    created_at: str = ""


@dataclass(frozen=True)
class PendingMerge:
    id: int
    existing_id: int
    new_data: dict[str, Any]
    match_fields: dict[str, Any] | None = None
    status: str = "pending"
    created_at: str = ""


@dataclass
class IngestResult:
    created: int = 0
    merged: int = 0
    pending: int = 0
    errors: int = 0
    error_details: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.created + self.merged + self.pending


@dataclass
class CandidateFilter:
    companies: list[str] | None = None
    titles: list[str] | None = None
    cities: list[str] | None = None
    education_levels: list[str] | None = None
    min_work_years: int | None = None
    max_work_years: int | None = None
    skills_any: list[str] | None = None
    skills_all: list[str] | None = None
    data_level: str | None = None
    hunting_status: list[str] | None = None
    min_score: float | None = None
    max_score: float | None = None
    platforms: list[str] | None = None
    updated_after: str | None = None


@dataclass
class SortSpec:
    field: str
    direction: str = "desc"


@dataclass
class PageResult:
    items: list[Candidate]
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        if self.page_size <= 0:
            return 0
        return -(-self.total // self.page_size)
