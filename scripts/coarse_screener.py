"""粗筛器: 基于 JD 分析结果做关键词匹配粗筛"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from scripts.jd_analyzer import JDAnalysis
from scripts.pipeline_utils import (
    load_company_aliases,
    load_scoring_config,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CoarseScore:
    """候选人粗筛得分（不可变）。"""
    candidate_id: str
    total_score: float
    skill_hits: list[str]
    exclusion_hits: list[str]
    company_matches: list[str]
    data_quality: str = "ok"


@dataclass
class DataQualityWarning:
    """数据质量警告。"""
    severity: str
    message: str


def _match_company(
    company_text: str,
    aliases: dict[str, list[str]],
    target_companies: list[str],
) -> list[str]:
    """匹配候选人经历中的目标公司。"""
    text_lower = company_text.lower()
    matches: list[str] = []
    for company_name in target_companies:
        if company_name.lower() in text_lower:
            matches.append(company_name)
            continue
        for alias in aliases.get(company_name, []):
            if alias.lower() in text_lower:
                matches.append(company_name)
                break
    return matches


def _get_candidate_text(candidate: dict) -> str:
    """将候选人所有文本字段合并为可搜索字符串。"""
    parts: list[str] = []
    for tag in candidate.get("skill_tags", []):
        parts.append(tag.lower())
    parts.append(candidate.get("current_title", "").lower())
    parts.append(candidate.get("expected_title", "").lower())
    if "_lid_tag" in candidate:
        parts.append(candidate["_lid_tag"].lower())
    for exp in candidate.get("work_experience", []):
        parts.append(exp.get("title", "").lower())
        parts.append(exp.get("company", "").lower())
        parts.append(exp.get("description", "").lower())
    if "_desc_raw" in candidate:
        parts.append(candidate["_desc_raw"].lower())
    return " ".join(parts)


def _check_data_quality(candidate: dict) -> str:
    """检查候选人数据是否充足。"""
    skill_tags = candidate.get("skill_tags", [])
    work_exp = candidate.get("work_experience", [])
    if (not skill_tags or len(skill_tags) < 2) and not work_exp:
        return "insufficient_data"
    return "ok"


def score_candidate_coarse(
    candidate: dict,
    analysis: JDAnalysis,
    config: dict[str, Any] | None = None,
) -> CoarseScore:
    """对单个候选人进行粗筛评分。

    基于 JD 核心技能/补充技能命中数、排除条件命中数、
    目标公司匹配数计算得分，并标注数据质量。
    """
    if config is None:
        config = load_scoring_config()

    weights = config.get("coarse_weights", {
        "core_skill_hit": 3,
        "supplement_skill_hit": 1,
        "exclusion_penalty": 20,
        "company_bonus": 5,
    })

    aliases = load_company_aliases()

    text = _get_candidate_text(candidate)
    data_quality = _check_data_quality(candidate)

    # 技能命中
    skill_hits: list[str] = []
    for skill in analysis.core_skills:
        if skill.lower() in text:
            skill_hits.append(skill)
    for skill in analysis.supplement_skills:
        if skill.lower() in text:
            skill_hits.append(skill)

    core_hits = [s for s in skill_hits if s in analysis.core_skills]
    supplement_hits = [s for s in skill_hits if s in analysis.supplement_skills]

    # 排除条件命中
    exclusion_hits: list[str] = []
    for exc in analysis.exclusion_criteria:
        if exc.lower() in text:
            exclusion_hits.append(exc)

    # 公司匹配
    company_text = " ".join(
        exp.get("company", "")
        for exp in candidate.get("work_experience", [])
    )
    company_text += " " + candidate.get("current_company", "")
    target_companies = config.get("top_companies", []) + config.get("ai_companies", [])
    company_matches = _match_company(company_text, aliases, target_companies)

    # 计算得分
    base_score = (
        len(core_hits) * weights["core_skill_hit"]
        + len(supplement_hits) * weights["supplement_skill_hit"]
    )
    penalty = len(exclusion_hits) * weights["exclusion_penalty"]
    bonus = len(company_matches) * weights["company_bonus"]

    raw_score = max(0, min(100, base_score - penalty + bonus))

    # 数据不完整时降权
    if data_quality == "insufficient_data":
        raw_score *= 0.5

    return CoarseScore(
        candidate_id=candidate.get("id", "unknown"),
        total_score=round(raw_score, 1),
        skill_hits=skill_hits,
        exclusion_hits=exclusion_hits,
        company_matches=company_matches,
        data_quality=data_quality,
    )


def check_signal_quality(scores: list[CoarseScore]) -> list[DataQualityWarning]:
    """检查粗筛结果的信号质量，返回警告列表。

    主要检查：
    1. 排除条件命中率过高 -> 搜索关键词可能偏离 JD
    2. 数据不完整比例过高 -> 搜索源数据质量差
    """
    warnings: list[DataQualityWarning] = []
    if not scores:
        return warnings

    excluded_count = sum(1 for s in scores if s.exclusion_hits)
    excluded_ratio = excluded_count / len(scores)

    if excluded_ratio > 0.7:
        warnings.append(DataQualityWarning(
            severity="warning",
            message=(
                f"{excluded_ratio:.0%} 的候选人命中排除条件，"
                "建议检查搜索关键词与 JD 一致性"
            ),
        ))

    insufficient_count = sum(
        1 for s in scores if s.data_quality == "insufficient_data"
    )
    if (insufficient_ratio := insufficient_count / len(scores)) > 0.5:
        warnings.append(DataQualityWarning(
            severity="info",
            message=f"{insufficient_ratio:.0%} 的候选人数据不完整(无技能标签和工作经历)",
        ))

    return warnings


def screen_candidates(
    candidates: list[dict],
    analysis: JDAnalysis,
    coarse_limit: int = 50,
    config: dict[str, Any] | None = None,
) -> list[CoarseScore]:
    """对候选人列表执行粗筛，返回按得分排序的 Top N 结果。

    筛选策略：
    - 候选人 <= 30 人: 全部进入精排
    - 候选人 > 100 人: 取 Top 100（区分度低）
    - 其他: 取 Top coarse_limit（默认 50）
    """
    scores = [
        score_candidate_coarse(c, analysis, config)
        for c in candidates
    ]

    quality_warnings = check_signal_quality(scores)
    for w in quality_warnings:
        if w.severity == "warning":
            logger.warning("[信号质量] %s", w.message)
        else:
            logger.info("[信号质量] %s", w.message)

    scores.sort(key=lambda s: s.total_score, reverse=True)

    if len(scores) > 100:
        scores = scores[:100]
        logger.info("粗筛区分度低，取 Top 100 进入精排")
    elif len(scores) <= 30:
        logger.info("粗筛后 %d 人，全部进入精排", len(scores))
    else:
        scores = scores[:coarse_limit]
        logger.info("粗筛完成，取 Top %d 进入精排", coarse_limit)

    return scores
