"""BOSS 到脉脉跨渠道身份匹配的纯函数工具。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping


HIGH_PRECISION_LEVELS = {
    "name_company_title",
    "name_company_title_core",
    "name_recent_company_title",
    "name_school_title_core",
}

AUTO_BIND_SCORE_THRESHOLD = 95
MIN_MATCH_SCORE = 70
AUTO_BIND_MAX_RESULTS = 2
MIN_SECOND_SCORE_GAP = 10

NAME_WEIGHT = 45
COMPANY_WEIGHT = 30
TITLE_WEIGHT = 20
CITY_WEIGHT = 5
EDUCATION_WEIGHT = 4
SCHOOL_WEIGHT = 4
QUERY_LEVEL_WEIGHT = 4
RESULT_COUNT_WEIGHT = 2
SECOND_GAP_WEIGHT = 3

FALLBACK_LEVEL = "name_company_fallback"
SOURCE_PLATFORM = "boss_app"
TARGET_PLATFORM = "maimai"

SENIOR_TITLE_PREFIXES = (
    "资深",
    "高级",
    "高阶",
    "专家",
    "首席",
    "高级资深",
    "Senior",
    "Sr.",
    "Sr",
)


@dataclass(frozen=True)
class QuerySpec:
    level: str
    text: str
    allow_auto_bind: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "allow_auto_bind": self.allow_auto_bind,
        }


@dataclass(frozen=True)
class BossMaimaiTarget:
    target_id: str
    candidate_key: str
    real_name: str
    current_company: str = ""
    current_title: str = ""
    city: str = ""
    education: str = ""
    recent_companies: tuple[str, ...] = ()
    schools: tuple[str, ...] = ()
    boss_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "candidate_key": self.candidate_key,
            "real_name": self.real_name,
            "current_company": self.current_company,
            "current_title": self.current_title,
            "city": self.city,
            "education": self.education,
            "recent_companies": list(self.recent_companies),
            "schools": list(self.schools),
            "boss_payload": dict(self.boss_payload),
        }


@dataclass(frozen=True)
class MaimaiSearchHit:
    platform_id: str
    name: str
    company: str = ""
    title: str = ""
    city: str = ""
    education: str = ""
    schools: tuple[str, ...] = ()
    work_companies: tuple[str, ...] = ()
    profile_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform_id": self.platform_id,
            "name": self.name,
            "company": self.company,
            "title": self.title,
            "city": self.city,
            "education": self.education,
            "schools": list(self.schools),
            "work_companies": list(self.work_companies),
            "profile_url": self.profile_url,
            "raw": dict(self.raw),
        }


@dataclass(frozen=True)
class IdentityScore:
    total: int
    breakdown: dict[str, int]


@dataclass(frozen=True)
class IdentityDecision:
    source_platform: str
    source_candidate_key: str
    target_platform: str
    target_platform_id: str
    target_profile_url: str
    query_text: str
    query_level: str
    confidence: int
    score_breakdown: dict[str, int]
    match_status: str
    decision_reason: str
    hit: MaimaiSearchHit | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_platform": self.source_platform,
            "source_candidate_key": self.source_candidate_key,
            "target_platform": self.target_platform,
            "target_platform_id": self.target_platform_id,
            "target_profile_url": self.target_profile_url,
            "query_text": self.query_text,
            "query_level": self.query_level,
            "confidence": self.confidence,
            "score_breakdown": dict(self.score_breakdown),
            "match_status": self.match_status,
            "decision_reason": self.decision_reason,
            "hit": self.hit.to_dict() if self.hit else None,
        }


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _as_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item or "").strip())
    text = str(value).strip()
    return (text,) if text else ()


def _target_from_mapping(value: BossMaimaiTarget | Mapping[str, Any]) -> BossMaimaiTarget:
    if isinstance(value, BossMaimaiTarget):
        return value
    if not isinstance(value, Mapping):
        raise TypeError("target must be BossMaimaiTarget or mapping")
    return BossMaimaiTarget(
        target_id=_clean_text(value.get("target_id")),
        candidate_key=_clean_text(value.get("candidate_key")),
        real_name=_clean_text(value.get("real_name")),
        current_company=_clean_text(value.get("current_company")),
        current_title=_clean_text(value.get("current_title")),
        city=_clean_text(value.get("city")),
        education=_clean_text(value.get("education")),
        recent_companies=_as_tuple(value.get("recent_companies")),
        schools=_as_tuple(value.get("schools")),
        boss_payload=dict(value.get("boss_payload") or {}),
    )


def _join_query(*parts: str) -> str:
    return " ".join(part for part in (_clean_text(item) for item in parts) if part)


def _title_core(title: str) -> str:
    core = _clean_text(title)
    for prefix in SENIOR_TITLE_PREFIXES:
        core = re.sub(rf"^{re.escape(prefix)}\s*", "", core, flags=re.IGNORECASE)
    return core.strip() or _clean_text(title)


def build_query_plan(target: BossMaimaiTarget | Mapping[str, Any]) -> list[QuerySpec]:
    item = _target_from_mapping(target)
    title_core = _title_core(item.current_title)
    recent_company = next((company for company in item.recent_companies if company), "")
    school_or_education = next((school for school in item.schools if school), item.education)
    plan: list[QuerySpec] = []
    if item.current_company:
        plan.append(QuerySpec("name_company_title", _join_query(item.real_name, item.current_company, item.current_title), True))
        plan.append(QuerySpec("name_company_title_core", _join_query(item.real_name, item.current_company, title_core), True))
    if recent_company:
        plan.append(QuerySpec("name_recent_company_title", _join_query(item.real_name, recent_company, title_core), True))
    if school_or_education:
        plan.append(QuerySpec("name_school_title_core", _join_query(item.real_name, school_or_education, title_core), True))
    plan.append(QuerySpec(FALLBACK_LEVEL, _join_query(item.real_name, item.current_company), False))
    return plan


def _norm(value: Any) -> str:
    text = str(value or "").casefold()
    return re.sub(r"[\s\W_]+", "", text)


def _contains_match(left: str, right: str) -> bool:
    a = _norm(left)
    b = _norm(right)
    return bool(a and b and (a in b or b in a))


def _company_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    hit_companies = (hit.company, *hit.work_companies)
    for company in hit_companies:
        if _norm(company) and _norm(company) == _norm(target.current_company):
            return COMPANY_WEIGHT
    for company in hit_companies:
        if _contains_match(company, target.current_company):
            return COMPANY_WEIGHT - 5
    for recent in target.recent_companies:
        for company in hit_companies:
            if _norm(company) and _norm(company) == _norm(recent):
                return COMPANY_WEIGHT - 5
            if _contains_match(company, recent):
                return COMPANY_WEIGHT - 8
    return 0


def _title_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    if _norm(hit.title) and _norm(hit.title) == _norm(target.current_title):
        return TITLE_WEIGHT
    target_core = _title_core(target.current_title)
    hit_core = _title_core(hit.title)
    if _norm(hit_core) and _norm(hit_core) == _norm(target_core):
        return TITLE_WEIGHT
    if _contains_match(hit_core, target_core):
        return TITLE_WEIGHT - 4
    return 0


def _school_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    for target_school in target.schools:
        for hit_school in hit.schools:
            if _norm(target_school) and _norm(target_school) == _norm(hit_school):
                return SCHOOL_WEIGHT
            if _contains_match(target_school, hit_school):
                return SCHOOL_WEIGHT - 1
    return 0


def score_hit(
    target: BossMaimaiTarget | Mapping[str, Any],
    hit: MaimaiSearchHit,
    query_level: str,
    result_count: int,
    second_score: int | None,
) -> IdentityScore:
    item = _target_from_mapping(target)
    name_score = NAME_WEIGHT if _norm(item.real_name) and _norm(item.real_name) == _norm(hit.name) else 0
    company_score = _company_score(item, hit)
    title_score = _title_score(item, hit)
    city_score = CITY_WEIGHT if _norm(item.city) and _norm(item.city) == _norm(hit.city) else 0
    education_score = EDUCATION_WEIGHT if _contains_match(item.education, hit.education) else 0
    school_score = _school_score(item, hit)
    query_score = QUERY_LEVEL_WEIGHT if query_level in HIGH_PRECISION_LEVELS else 0
    result_score = RESULT_COUNT_WEIGHT if result_count <= AUTO_BIND_MAX_RESULTS else 0
    if second_score is None:
        second_gap_score = 0
    else:
        second_gap_score = SECOND_GAP_WEIGHT if second_score < 0 or (name_score + company_score + title_score - second_score) >= MIN_SECOND_SCORE_GAP else 0

    breakdown = {
        "name": name_score,
        "company": company_score,
        "title": title_score,
        "city": city_score,
        "education": education_score,
        "school": school_score,
        "query_level": query_score,
        "result_count": result_score,
        "second_gap": second_gap_score,
    }
    return IdentityScore(total=min(100, sum(breakdown.values())), breakdown=breakdown)


def _decision(
    target: BossMaimaiTarget,
    hit: MaimaiSearchHit | None,
    query_level: str,
    query_text: str,
    confidence: int,
    score_breakdown: dict[str, int],
    match_status: str,
    decision_reason: str,
) -> IdentityDecision:
    return IdentityDecision(
        source_platform=SOURCE_PLATFORM,
        source_candidate_key=target.candidate_key,
        target_platform=TARGET_PLATFORM,
        target_platform_id=hit.platform_id if hit else "",
        target_profile_url=hit.profile_url if hit else "",
        query_text=query_text,
        query_level=query_level,
        confidence=confidence,
        score_breakdown=score_breakdown,
        match_status=match_status,
        decision_reason=decision_reason,
        hit=hit,
    )


def decide_match(
    target: BossMaimaiTarget | Mapping[str, Any],
    hits: list[MaimaiSearchHit],
    query_level: str,
    query_text: str,
) -> IdentityDecision:
    item = _target_from_mapping(target)
    if not hits:
        return _decision(item, None, query_level, query_text, 0, {}, "not_found", "no_hits")

    provisional = [
        (hit, score_hit(item, hit, query_level=query_level, result_count=len(hits), second_score=None))
        for hit in hits
    ]
    provisional.sort(key=lambda pair: pair[1].total, reverse=True)
    best_hit, best_initial_score = provisional[0]
    second_total = provisional[1][1].total if len(provisional) > 1 else -1
    best_score = score_hit(
        item,
        best_hit,
        query_level=query_level,
        result_count=len(hits),
        second_score=second_total,
    )
    second_gap = best_initial_score.total - second_total if second_total >= 0 else 999

    if best_score.total < MIN_MATCH_SCORE:
        return _decision(
            item,
            best_hit,
            query_level,
            query_text,
            best_score.total,
            best_score.breakdown,
            "not_found",
            "score_below_threshold",
        )
    if query_level == FALLBACK_LEVEL:
        return _decision(
            item,
            best_hit,
            query_level,
            query_text,
            best_score.total,
            best_score.breakdown,
            "pending_confirmation",
            "fallback_query_requires_confirmation",
        )
    if len(hits) > AUTO_BIND_MAX_RESULTS:
        return _decision(
            item,
            best_hit,
            query_level,
            query_text,
            best_score.total,
            best_score.breakdown,
            "pending_confirmation",
            "too_many_results",
        )
    if second_total >= 0 and second_gap < MIN_SECOND_SCORE_GAP:
        return _decision(
            item,
            best_hit,
            query_level,
            query_text,
            best_score.total,
            best_score.breakdown,
            "pending_confirmation",
            "second_score_gap_too_small",
        )
    if query_level in HIGH_PRECISION_LEVELS and best_score.total >= AUTO_BIND_SCORE_THRESHOLD:
        return _decision(
            item,
            best_hit,
            query_level,
            query_text,
            best_score.total,
            best_score.breakdown,
            "auto_bound",
            "high_precision_score",
        )
    return _decision(
        item,
        best_hit,
        query_level,
        query_text,
        best_score.total,
        best_score.breakdown,
        "pending_confirmation",
        "score_requires_confirmation",
    )
