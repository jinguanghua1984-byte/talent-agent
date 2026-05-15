"""AI Infra 候选人本地规则评分。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_search_plan import load_strategy
from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, CandidateFilter, SortSpec


PRECISION_TITLE_TERMS = ["AI Infra", "ML Infra", "LLM Infra", "大模型", "训练", "推理", "框架", "机器学习系统", "训推"]
TECHNICAL_TITLE_TERMS = ["部署", "引擎", "平台", "算子", "CUDA", "异构", "高性能", "分布式", "智算"]
GENERIC_TITLE_TERMS = ["算法工程师", "机器学习工程师", "深度学习工程师", "平台开发", "系统研发", "后端开发"]


def _text_join(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            parts.append(_text_join(list(value)))
        elif isinstance(value, dict):
            parts.append(_text_join(list(value.values())))
        else:
            parts.append(str(value))
    return " ".join(parts)


def _detail_text(detail: CandidateDetail | None) -> str:
    if detail is None:
        return ""
    return _text_join([
        detail.work_experience or (),
        detail.education_experience or (),
        detail.project_experience or (),
        detail.raw_data or {},
        detail.summary or "",
    ])


def _candidate_text(candidate: Candidate, detail: CandidateDetail | None) -> str:
    return _text_join([
        candidate.name,
        candidate.current_company,
        candidate.current_title,
        candidate.education,
        list(candidate.skill_tags),
        _detail_text(detail),
    ])


def _company_matches(strategy: dict[str, Any], text: str) -> tuple[str | None, str | None]:
    for tier, companies in strategy.get("company_tiers", {}).items():
        for company in companies:
            aliases = strategy.get("company_aliases", {}).get(company, [])
            if company and company in text:
                return tier, company
            for alias in aliases:
                if alias and alias in text:
                    return tier, company
    return None, None


def _company_score(tier: str | None) -> int:
    return {
        "tier1": 30,
        "tier2_priority": 24,
        "tier3": 16,
        "tier4": 8,
        "tier5": 4,
    }.get(tier or "", 0)


def _title_score(title: str) -> tuple[int, str]:
    if any(term.lower() in title.lower() for term in PRECISION_TITLE_TERMS):
        return 25, "precision"
    if any(term.lower() in title.lower() for term in TECHNICAL_TITLE_TERMS):
        return 20, "technical"
    if any(term.lower() in title.lower() for term in GENERIC_TITLE_TERMS):
        return 10, "generic"
    return 0, "missing"


def _tech_keywords(strategy: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    for values in strategy.get("keyword_packs", {}).values():
        for value in values:
            if value not in terms:
                terms.append(value)
    for extra in ["分布式", "训练", "推理", "框架", "算子", "异构", "智算", "加速", "GPU", "Token", "LLM"]:
        if extra not in terms:
            terms.append(extra)
    return terms


_TOP500_PHRASES = [
    "QS Top500",
    "QS Top 500",
    "QS前500",
    "世界前500",
    "海外 Top500",
    "海外 Top 500",
    "overseas Top500",
    "overseas Top 500",
    "overseas前500",
]
_SECONDARY_SCHOOL_TERMS = ["博士", "硕士", "本科"]
_EXCLUDED_EDUCATION_TERMS = {"大专", "专科", "junior college", "juniorcollege"}
_NEGATOR_RE = re.compile(r"不是|非|not\b|non(?:-|\b)", re.IGNORECASE)
_DIRECT_NEGATOR_RE = re.compile(r"(不是|非|not\b|non(?:-|\b))\s*$", re.IGNORECASE)
_STRONG_EDUCATION_BOUNDARY_RE = re.compile(r"[，,；;\n。]")
_LIST_CONNECTOR_AT_END_RE = re.compile(r"(?:[/、]|和|或|及)\s*$")
_NEGATOR_LEFT_BOUNDARIES = set("（([{、/，,；;。和或及")


def _education_text(candidate: Candidate, detail: CandidateDetail | None) -> str:
    return _text_join([candidate.education, _detail_text(detail)])


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.lower() in text.lower()
    return term in text


def _split_education_segments(education_text: str) -> list[str]:
    return [segment.strip() for segment in _STRONG_EDUCATION_BOUNDARY_RE.split(education_text) if segment.strip()]


def _negator_has_left_boundary(text: str, start: int) -> bool:
    if start == 0:
        return True
    previous = text[start - 1]
    return previous.isspace() or previous in _NEGATOR_LEFT_BOUNDARIES


def _prefix_has_applicable_negation(prefix: str) -> bool:
    if not prefix.strip():
        return False

    direct_match = _DIRECT_NEGATOR_RE.search(prefix)
    if direct_match and _negator_has_left_boundary(prefix, direct_match.start()):
        return True

    for match in _NEGATOR_RE.finditer(prefix):
        if not _negator_has_left_boundary(prefix, match.start()):
            continue
        tail = prefix[match.end():]
        if _STRONG_EDUCATION_BOUNDARY_RE.search(tail):
            continue
        if _LIST_CONNECTOR_AT_END_RE.search(tail):
            return True
    return False


def _segment_has_positive_phrase(segment: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = re.escape(phrase)
    flags = re.IGNORECASE if phrase.isascii() else 0
    for match in re.finditer(pattern, segment, flags):
        if not _prefix_has_applicable_negation(segment[: match.start()]):
            return True
    return False


def _positive_school_phrase(education_text: str, phrase: str) -> bool:
    if not phrase:
        return False
    for segment in _split_education_segments(education_text):
        if _segment_has_positive_phrase(segment, phrase):
            return True
    return False


def _matches_top500_school(education_text: str) -> bool:
    return any(_positive_school_phrase(education_text, phrase) for phrase in _TOP500_PHRASES)


def _positive_school_label_from_strategy(
    strategy: dict[str, Any],
    education_text: str,
) -> str | None:
    groups = strategy.get("education_groups", {})
    if any(_positive_school_phrase(education_text, school) for school in groups.get("c9", [])):
        return "C9"
    if any(
        _positive_school_phrase(education_text, school) for school in groups.get("top985", [])
    ) or _positive_school_phrase(education_text, "985"):
        return "985"
    if any(
        _positive_school_phrase(education_text, school) for school in groups.get("top211", [])
    ) or _positive_school_phrase(education_text, "211"):
        return "211"
    if _matches_top500_school(education_text):
        return "TOP500"
    return None


def _is_priority_school(strategy: dict[str, Any], candidate: Candidate, detail: CandidateDetail | None) -> bool:
    education_text = _education_text(candidate, detail)
    return _positive_school_label_from_strategy(strategy, education_text) is not None


def _education_score(strategy: dict[str, Any], candidate: Candidate, detail: CandidateDetail | None) -> tuple[int, str]:
    education_text = _education_text(candidate, detail)
    label = _positive_school_label_from_strategy(strategy, education_text)
    if label == "C9":
        return 10, "C9"
    if label == "985":
        return 8, "985"
    if label in {"211", "TOP500"}:
        return 6, label
    if any(_contains_term(education_text, term) for term in _SECONDARY_SCHOOL_TERMS):
        return 4, candidate.education or "本科及以上"
    return 0, candidate.education or ""


def _years_score(candidate: Candidate) -> int:
    years = candidate.work_years
    if years is None:
        return 0
    if 2 <= years <= 10:
        return 10
    if 0 <= years < 2:
        return 7
    if 10 < years <= 15:
        return 7
    return 3


def _age_band(age: int | None) -> str:
    if age is None:
        return "unknown"
    if age > 40:
        return "over_40"
    if 35 < age <= 40:
        return "secondary_35_40"
    if 24 <= age <= 35:
        return "best_24_35"
    return "other"


def _grade_rank(grade: str) -> int:
    return {"A": 3, "B": 2, "C": 1, "淘汰": 0}.get(grade, 0)


def _cap_grade(grade: str, cap: str) -> str:
    return grade if _grade_rank(grade) <= _grade_rank(cap) else cap


def score_candidate(
    candidate: Candidate,
    strategy: dict[str, Any],
    detail: CandidateDetail | None = None,
    mode: str = "list",
) -> dict[str, Any]:
    if mode not in {"list", "detailed"}:
        raise ValueError("mode must be either 'list' or 'detailed'")

    source_detail = detail if mode == "detailed" else None
    text = _candidate_text(candidate, source_detail)
    title = candidate.current_title or ""
    risk_flags: list[str] = []
    age_band = _age_band(candidate.age)

    if any(term and term.lower() in title.lower() for term in strategy.get("exclude_titles", [])):
        risk_flags.append("excluded_title")

    education_text = _education_text(candidate, source_detail)
    excluded_education_terms = set(strategy.get("exclude_education", [])) | _EXCLUDED_EDUCATION_TERMS
    if any(_contains_term(education_text, term) for term in excluded_education_terms):
        risk_flags.append("excluded_education")

    tier, company = _company_matches(strategy, _text_join([candidate.current_company, text]))
    if not tier:
        risk_flags.append("company_not_targeted")

    company_points = _company_score(tier)
    title_points, title_level = _title_score(title)
    keywords = [term for term in _tech_keywords(strategy) if term and term.lower() in text.lower()]
    tech_points = min(25, len(keywords) * 5)
    education_points, education_level = _education_score(strategy, candidate, source_detail)
    years_points = _years_score(candidate)
    score = company_points + title_points + tech_points + education_points + years_points

    if not _is_priority_school(strategy, candidate, source_detail):
        risk_flags.append("school_not_priority")
    if candidate.age is not None and candidate.age > 40:
        risk_flags.append("age_over_40")
    if score < 50:
        risk_flags.append("score_below_threshold")

    hard_reject = any(
        flag in {
            "excluded_title",
            "excluded_education",
            "company_not_targeted",
            "school_not_priority",
            "age_over_40",
            "score_below_threshold",
        }
        for flag in risk_flags
    )

    if score >= 80 and company_points and title_points and tech_points:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    else:
        grade = "淘汰"

    if mode == "detailed" and detail is None:
        risk_flags.append("missing_detail_for_detailed_score")
        grade = _cap_grade(grade, "C")

    if age_band == "secondary_35_40":
        grade = _cap_grade(grade, "B")
    elif age_band == "over_40":
        grade = "淘汰"
        hard_reject = True

    if hard_reject:
        grade = "淘汰"

    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "tier": tier,
        "grade": grade,
        "score": score,
        "score_mode": mode,
        "age_band": age_band,
        "evidence": {
            "company": company or candidate.current_company or "",
            "title": candidate.current_title or "",
            "title_level": title_level,
            "tech_keywords": keywords,
            "education": education_level,
            "work_years": candidate.work_years,
        },
        "risk_flags": risk_flags,
    }


def rank_candidates(
    db_path: str | Path,
    strategy: dict[str, Any],
    limit: int = 5000,
    mode: str = "list",
) -> dict[str, Any]:
    db = TalentDB(db_path)
    try:
        page = db.search(
            CandidateFilter(platforms=["maimai"]),
            SortSpec(field="updated_at", direction="desc"),
            page=1,
            page_size=limit,
        )
        scores = [
            score_candidate(
                candidate,
                strategy,
                db.get_detail(candidate.id) if mode == "detailed" else None,
                mode=mode,
            )
            for candidate in page.items
        ]
    finally:
        db.close()

    grade_order = {"A": 0, "B": 1, "C": 2, "淘汰": 3}
    scores.sort(key=lambda item: (grade_order.get(item["grade"], 99), -item["score"], item["candidate_id"]))
    grades: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "C": [], "淘汰": []}
    for item in scores:
        grades.setdefault(item["grade"], []).append(item)
    return {
        "strategy_version": strategy["strategy_version"],
        "total_candidates": len(scores),
        "summary": {grade: len(items) for grade, items in grades.items()},
        "grades": grades,
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# 脉脉 AI Infra 候选人 Shortlist",
        "",
        f"- 策略版本：{result['strategy_version']}",
        f"- 候选人总数：{result['total_candidates']}",
        f"- A/B/C/淘汰：{result['summary'].get('A', 0)}/{result['summary'].get('B', 0)}/{result['summary'].get('C', 0)}/{result['summary'].get('淘汰', 0)}",
        "",
    ]
    for grade in ("A", "B", "C", "淘汰"):
        lines.append(f"## {grade} 档")
        for item in result["grades"].get(grade, [])[:50]:
            evidence = item["evidence"]
            tech = "、".join(evidence.get("tech_keywords") or [])
            lines.append(
                f"- #{item['candidate_id']} {item['name']}｜{item['score']} 分｜"
                f"{evidence.get('company', '')}｜{evidence.get('title', '')}｜{tech}"
            )
            if item.get("risk_flags"):
                lines.append(f"  - 风险：{', '.join(item['risk_flags'])}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脉脉 AI Infra 本地评分")
    parser.add_argument("--db", default="data/talent.db")
    parser.add_argument("--config", default="configs/maimai-ai-infra-search-strategy.json")
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args(argv)

    strategy = load_strategy(args.config)
    result = rank_candidates(args.db, strategy, args.limit)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    _write_markdown(Path(args.out_md), result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
