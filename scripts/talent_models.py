"""人才库数据模型。

仅定义数据结构，不包含业务逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


def _normalize_skill_tags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    if isinstance(value, str):
        return (value,)
    raise TypeError("skill_tags 必须是 list/tuple/str/None")


def _normalize_experiences(value: Any) -> tuple[dict[str, Any], ...] | None:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)):
        raise TypeError("经历字段必须是 list/tuple/None")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError("经历字段中的元素必须是 dict")
        normalized.append(dict(item))
    return tuple(normalized)


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

    def __post_init__(self) -> None:
        object.__setattr__(self, "skill_tags", _normalize_skill_tags(self.skill_tags))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "age": self.age,
            "city": self.city,
            "work_years": self.work_years,
            "education": self.education,
            "current_company": self.current_company,
            "current_title": self.current_title,
            "expected_salary": self.expected_salary,
            "expected_city": self.expected_city,
            "expected_title": self.expected_title,
            "hunting_status": self.hunting_status,
            "skill_tags": list(self.skill_tags),
            "data_level": self.data_level,
            "overall_score": self.overall_score,
            "score_version": self.score_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Candidate":
        return cls(
            id=data["id"],
            name=data["name"],
            gender=data.get("gender"),
            age=data.get("age"),
            city=data.get("city"),
            work_years=data.get("work_years"),
            education=data.get("education"),
            current_company=data.get("current_company"),
            current_title=data.get("current_title"),
            expected_salary=data.get("expected_salary"),
            expected_city=data.get("expected_city"),
            expected_title=data.get("expected_title"),
            hunting_status=data.get("hunting_status"),
            skill_tags=data.get("skill_tags"),
            data_level=data.get("data_level", "lead"),
            overall_score=data.get("overall_score", 0.0),
            score_version=data.get("score_version", 0),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass(frozen=True)
class CandidateDetail:
    candidate_id: int
    work_experience: tuple[dict[str, Any], ...] | None = None
    education_experience: tuple[dict[str, Any], ...] | None = None
    project_experience: tuple[dict[str, Any], ...] | None = None
    raw_data: dict[str, Any] | None = None
    summary: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "work_experience",
            _normalize_experiences(self.work_experience),
        )
        object.__setattr__(
            self,
            "education_experience",
            _normalize_experiences(self.education_experience),
        )
        object.__setattr__(
            self,
            "project_experience",
            _normalize_experiences(self.project_experience),
        )
        if self.raw_data is not None:
            object.__setattr__(self, "raw_data", dict(self.raw_data))

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "work_experience": (
                [dict(item) for item in self.work_experience]
                if self.work_experience is not None
                else None
            ),
            "education_experience": (
                [dict(item) for item in self.education_experience]
                if self.education_experience is not None
                else None
            ),
            "project_experience": (
                [dict(item) for item in self.project_experience]
                if self.project_experience is not None
                else None
            ),
            "raw_data": dict(self.raw_data) if self.raw_data is not None else None,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateDetail":
        return cls(
            candidate_id=data["candidate_id"],
            work_experience=data.get("work_experience"),
            education_experience=data.get("education_experience"),
            project_experience=data.get("project_experience"),
            raw_data=data.get("raw_data"),
            summary=data.get("summary"),
        )


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
