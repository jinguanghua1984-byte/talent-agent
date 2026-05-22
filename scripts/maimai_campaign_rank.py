from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.maimai_company_registry import expand_company_pool_terms
from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, CandidateFilter, SortSpec


@dataclass(frozen=True)
class RankTerms:
    precision_titles: list[str]
    technical_titles: list[str]
    generic_titles: list[str]
    keywords: list[str]
    reject_terms: list[str]
    company_terms: list[str]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _text_join(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
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


def _company_terms(strategy: dict[str, Any]) -> list[str]:
    pools = strategy.get("company_pools") if isinstance(strategy.get("company_pools"), dict) else {}
    raw_terms: list[str] = []
    for value in pools.values():
        if isinstance(value, list):
            raw_terms.extend(str(item) for item in value)
    terms: list[str] = []
    for item in expand_company_pool_terms(_unique(raw_terms)):
        terms.extend([
            item.get("raw_term") or "",
            item.get("canonical_company") or "",
            *item.get("company_aliases", []),
            *item.get("org_product_terms", []),
        ])
    return _unique(terms)


def build_rank_terms(strategy: dict[str, Any]) -> RankTerms:
    position_aliases = [str(item) for item in strategy.get("position_aliases") or []]
    expanded_position_aliases = list(position_aliases)
    for alias in position_aliases:
        for prefix in ("大模型", "AI ", "AI", "后训练"):
            if alias.startswith(prefix):
                expanded_position_aliases.append(alias[len(prefix):].strip())
    keyword_terms: list[str] = []
    for package in strategy.get("keyword_packages") or []:
        if isinstance(package, dict):
            keyword_terms.extend(str(item) for item in package.get("keywords") or [])
            keyword_terms.extend(str(item) for item in package.get("position_terms") or [])
    screening_rules = strategy.get("screening_rules") if isinstance(strategy.get("screening_rules"), dict) else {}
    reject_terms = [str(item) for item in screening_rules.get("淘汰", [])]
    return RankTerms(
        precision_titles=_unique(expanded_position_aliases),
        technical_titles=_unique([term for term in keyword_terms if "平台" in term or "体系" in term]),
        generic_titles=_unique(["负责人", "专家", "Lead", "Manager"]),
        keywords=_unique(keyword_terms),
        reject_terms=_unique(reject_terms),
        company_terms=_company_terms(strategy),
    )


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.casefold() in text.casefold()
    return term in text


def title_level(title: str, terms: RankTerms) -> str:
    if any(_contains(title, term) for term in terms.precision_titles):
        return "precision"
    if any(_contains(title, term) for term in terms.technical_titles):
        return "technical"
    if any(_contains(title, term) for term in terms.generic_titles):
        return "generic"
    return "missing"


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("strategy JSON must be an object")
    return data


def _load_candidate_ids_file(path: str | Path) -> list[int]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    values: list[Any]
    if isinstance(data, dict) and isinstance(data.get("candidate_ids"), list):
        values = data["candidate_ids"]
    elif isinstance(data, dict) and isinstance(data.get("contacts"), list):
        values = [item.get("candidate_id") for item in data["contacts"] if isinstance(item, dict)]
    else:
        raise ValueError("candidate ids file must contain candidate_ids or contacts")
    result: list[int] = []
    seen: set[int] = set()
    for value in values:
        try:
            candidate_id = int(value)
        except (TypeError, ValueError):
            continue
        if candidate_id not in seen:
            seen.add(candidate_id)
            result.append(candidate_id)
    return result


def _candidate_text(candidate: Candidate, detail: CandidateDetail | None) -> str:
    return _text_join([
        candidate.name,
        candidate.current_company,
        candidate.current_title,
        candidate.education,
        list(candidate.skill_tags),
        _detail_text(detail),
    ])


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _contains(text, term)]


def _score_candidate(
    candidate: Candidate,
    detail: CandidateDetail | None,
    terms: RankTerms,
    mode: str,
) -> dict[str, Any]:
    text = _candidate_text(candidate, detail if mode == "detailed" else None)
    title = candidate.current_title or ""
    matched_company_terms = _matched_terms(_text_join([candidate.current_company, text]), terms.company_terms)
    matched_keywords = _matched_terms(text, terms.keywords)
    level = title_level(title, terms)
    risk_flags: list[str] = []

    company_points = 25 if matched_company_terms else 0
    title_points = {"precision": 25, "technical": 18, "generic": 10}.get(level, 0)
    keyword_points = min(30, len(matched_keywords) * 6)
    years_points = 10 if candidate.work_years and 3 <= candidate.work_years <= 15 else 5
    score = company_points + title_points + keyword_points + years_points

    if not matched_company_terms:
        risk_flags.append("company_not_targeted")
    if level == "missing":
        risk_flags.append("title_not_targeted")
    if not matched_keywords:
        risk_flags.append("keyword_evidence_missing")
    if any(_contains(text, term) for term in terms.reject_terms):
        risk_flags.append("strategy_reject_term")
    if mode == "detailed" and detail is None:
        risk_flags.append("missing_detail_for_detailed_score")

    if "strategy_reject_term" in risk_flags or score < 45:
        grade = "淘汰"
    elif score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    else:
        grade = "C"

    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "tier": "target" if matched_company_terms else None,
        "grade": grade,
        "score": score,
        "score_mode": mode,
        "age_band": "unknown" if candidate.age is None else str(candidate.age),
        "evidence": {
            "company": matched_company_terms[0] if matched_company_terms else candidate.current_company or "",
            "title": title,
            "title_level": level,
            "tech_keywords": matched_keywords,
            "education": candidate.education or "",
            "work_years": candidate.work_years,
        },
        "risk_flags": risk_flags,
    }


def rank_candidates(
    db_path: str | Path,
    strategy: dict[str, Any],
    limit: int = 5000,
    mode: str = "list",
    candidate_ids: list[int] | None = None,
) -> dict[str, Any]:
    if mode not in {"list", "detailed"}:
        raise ValueError("mode must be list or detailed")
    terms = build_rank_terms(strategy)
    db = TalentDB(db_path)
    try:
        if candidate_ids is None:
            page = db.search(
                CandidateFilter(platforms=["maimai"]),
                SortSpec(field="updated_at", direction="desc"),
                page=1,
                page_size=limit,
            )
            candidates = page.items
        else:
            candidates = [candidate for candidate_id in candidate_ids if (candidate := db.get(candidate_id)) is not None]
        scores = [
            _score_candidate(candidate, db.get_detail(candidate.id), terms, mode)
            for candidate in candidates
        ]
    finally:
        db.close()

    grade_order = {"A": 0, "B": 1, "C": 2, "淘汰": 3}
    scores.sort(key=lambda item: (grade_order.get(item["grade"], 99), -item["score"], item["candidate_id"]))
    scores = scores[:limit]
    grades: dict[str, list[dict[str, Any]]] = {"A": [], "B": [], "C": [], "淘汰": []}
    for item in scores:
        grades.setdefault(item["grade"], []).append(item)
    return {
        "strategy_version": strategy.get("strategy_version") or "",
        "rank_terms": {
            "precision_titles": terms.precision_titles,
            "technical_titles": terms.technical_titles,
            "keywords": terms.keywords,
            "company_terms": terms.company_terms,
        },
        "total_candidates": len(scores),
        "summary": {grade: len(items) for grade, items in grades.items()},
        "grades": grades,
        "ranked": scores,
    }


def _write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# 脉脉 JD Campaign 候选人 Shortlist",
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
            keywords = "、".join(evidence.get("tech_keywords") or [])
            lines.append(
                f"- #{item['candidate_id']} {item['name']}｜{item['score']} 分｜"
                f"{evidence.get('company', '')}｜{evidence.get('title', '')}｜{keywords}"
            )
            if item.get("risk_flags"):
                lines.append(f"  - 风险：{', '.join(item['risk_flags'])}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8-sig")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通用 JD-driven 脉脉候选人评分")
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--mode", choices=["list", "detailed"], default="list")
    parser.add_argument("--candidate-ids-file")
    args = parser.parse_args(argv)

    strategy = _load_json(args.config)
    candidate_ids = _load_candidate_ids_file(args.candidate_ids_file) if args.candidate_ids_file else None
    result = rank_candidates(args.db, strategy, args.limit, mode=args.mode, candidate_ids=candidate_ids)
    out_json = Path(args.out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    _write_markdown(Path(args.out_md), result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
