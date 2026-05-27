from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from scripts.jd_talent_delivery_scorecard import validate_scorecard
from scripts.maimai_company_registry import expand_company_pool_terms
from scripts.maimai_url import (
    build_openable_maimai_profile_url,
    is_openable_maimai_profile_url,
)
from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, SortSpec

_REAL_TALENT_DB = TalentDB

CSV_FIELDS = [
    "priority",
    "rank",
    "candidate_id",
    "name",
    "platform_id",
    "company",
    "title",
    "city",
    "work_years",
    "score",
    "recommendation_label",
    "grade",
    "directions",
    "key_evidence",
    "risk_summary",
    "suggested_outreach_angle",
    "profile_url",
]

FEEDBACK_CSV_FIELDS = [
    "feedback_label",
    "feedback_stage",
    "reason_codes",
    "hunter_note",
    "contacted",
    "submitted_to_client",
    "interviewed",
    "offer",
]

HARD_RISK_FLAGS = {
    "exclusion_terms",
    "low_hunting_status",
    "missing_detail_for_detailed_score",
}

MOJIBAKE_MARKERS = ("锛", "鐨", "�", "���", "娣峰")


@dataclass(frozen=True)
class CandidateBundle:
    candidate: Candidate
    detail: CandidateDetail | None
    sources: list[Any]


@contextmanager
def _temporary_readonly_db_copy(db_path: str | Path) -> Iterator[Path]:
    source = Path(db_path).resolve()
    if not source.exists():
        raise FileNotFoundError(source)
    with TemporaryDirectory(prefix="jd-talent-match-") as temp_dir:
        copy_path = Path(temp_dir) / source.name
        source_uri = source.as_uri() + "?mode=ro"
        source_conn = sqlite3.connect(source_uri, uri=True)
        copy_conn = sqlite3.connect(copy_path)
        try:
            source_conn.backup(copy_conn)
        finally:
            copy_conn.close()
            source_conn.close()
        yield copy_path


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _text_join(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            parts.append(_text_join(list(value.values())))
        elif isinstance(value, (list, tuple, set)):
            parts.append(_text_join(list(value)))
        else:
            text = str(value).strip()
            if text:
                parts.append(text)
    return " ".join(parts)


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.casefold() in text.casefold()
    return term in text


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _contains(text, term)]


def _dimension_specs(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    validate_scorecard(scorecard)
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("scorecard dimensions must be a non-empty list")
    specs: list[dict[str, Any]] = []
    for index, item in enumerate(dimensions):
        if not isinstance(item, dict):
            raise ValueError("dimension must be an object")
        if not str(item.get("id", "")).strip():
            raise ValueError(f"dimension missing id at index {index}")
        specs.append(item)
    return specs


def _dimension_ids(scorecard: dict[str, Any]) -> list[str]:
    return [str(item["id"]) for item in _dimension_specs(scorecard)]


def _dimension_weights(scorecard: dict[str, Any]) -> dict[str, int]:
    weights: dict[str, int] = {}
    for item in _dimension_specs(scorecard):
        weights[str(item["id"])] = int(item["weight"])
    return weights


def _label_thresholds(scorecard: dict[str, Any]) -> dict[str, int]:
    thresholds = scorecard.get("label_thresholds")
    if not isinstance(thresholds, dict):
        thresholds = {}
    result: dict[str, int] = {}
    for key, default in (
        ("strong_recommend", 82),
        ("recommend", 72),
        ("observe", 60),
    ):
        try:
            result[key] = int(thresholds.get(key, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid label threshold: {key}") from exc
    if not (result["strong_recommend"] > result["recommend"] > result["observe"]):
        raise ValueError("label thresholds must satisfy strong_recommend > recommend > observe")
    return result


def _terms(scorecard: dict[str, Any], key: str) -> list[str]:
    terms = scorecard.get("terms")
    if not isinstance(terms, dict):
        return []
    value = terms.get(key)
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _company_terms(scorecard: dict[str, Any]) -> list[str]:
    pools = scorecard.get("company_pools")
    if not isinstance(pools, dict):
        return []
    raw_terms: list[str] = []
    for values in pools.values():
        if isinstance(values, list):
            raw_terms.extend(str(item) for item in values if str(item))
    terms: list[str] = []
    for item in expand_company_pool_terms(list(dict.fromkeys(raw_terms))):
        terms.extend(
            [
                item.get("raw_term") or "",
                item.get("canonical_company") or "",
                *item.get("company_aliases", []),
                *item.get("org_product_terms", []),
            ]
        )
    return list(dict.fromkeys(terms))


def _candidate_text(bundle: CandidateBundle, include_detail: bool) -> str:
    candidate = bundle.candidate
    detail = bundle.detail if include_detail else None
    return _text_join(
        [
            candidate.name,
            candidate.current_company,
            candidate.current_title,
            candidate.education,
            candidate.hunting_status,
            list(candidate.skill_tags),
            detail.work_experience if detail else [],
            detail.education_experience if detail else [],
            detail.project_experience if detail else [],
            detail.summary if detail else "",
            detail.raw_data if detail else {},
        ]
    )


def _source_url(bundle: CandidateBundle) -> str:
    for source in bundle.sources:
        url = getattr(source, "profile_url", "") or ""
        if url:
            return build_openable_maimai_profile_url(str(url))
    return ""


def _platform_id(bundle: CandidateBundle) -> str:
    for source in bundle.sources:
        value = getattr(source, "platform_id", "") or ""
        if value:
            return str(value)
    return ""


def _weighted_hits(hit_count: int, total_terms: int, weight: int) -> int:
    if total_terms <= 0 or hit_count <= 0:
        return 0
    denominator = min(total_terms, 6)
    return min(weight, round(weight * hit_count / denominator))


def _title_level(title: str, title_hits: list[str], keyword_hits: list[str]) -> str:
    if title_hits:
        return "precision"
    generic_terms = ["负责人", "专家", "Lead", "Manager", "产品", "平台", "策略", "运营"]
    if any(_contains(title, term) for term in keyword_hits):
        return "technical"
    if any(_contains(title, term) for term in generic_terms):
        return "generic"
    return "missing"


def _shorten(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _experience_snippet(prefix: str, item: dict[str, Any], limit: int = 180) -> str:
    company = item.get("company") or item.get("organization") or ""
    title = item.get("title") or item.get("position") or item.get("name") or ""
    period = item.get("period") or item.get("v") or ""
    description = item.get("description") or item.get("summary") or ""
    heading = " ".join(part for part in (period, company, title) if part)
    body = _shorten(description, limit)
    if heading and body:
        return f"{prefix}：{heading} - {body}"
    if heading:
        return f"{prefix}：{heading}"
    if body:
        return f"{prefix}：{body}"
    return ""


def _detail_present(detail: CandidateDetail | None) -> bool:
    if detail is None:
        return False
    return bool(
        detail.work_experience
        or detail.education_experience
        or detail.project_experience
        or detail.summary
        or detail.raw_data
    )


def _key_evidence(
    bundle: CandidateBundle,
    company_hits: list[str],
    title: str,
    matched_terms: list[str],
) -> list[str]:
    candidate = bundle.candidate
    detail = bundle.detail
    lines: list[str] = []
    company = company_hits[0] if company_hits else candidate.current_company or ""
    keyword_text = "、".join(matched_terms[:8])
    parts = [part for part in (company, title, f"关键词：{keyword_text}" if keyword_text else "") if part]
    if parts:
        lines.append("评分证据：" + " / ".join(parts))
    if detail is not None:
        for work in (detail.work_experience or ())[:2]:
            snippet = _experience_snippet("工作经历", work)
            if snippet:
                lines.append(snippet)
        for project in (detail.project_experience or ())[:1]:
            snippet = _experience_snippet("项目经历", project)
            if snippet:
                lines.append(snippet)
        for edu in (detail.education_experience or ())[:1]:
            snippet = _experience_snippet("教育经历", edu, limit=120)
            if snippet:
                lines.append(snippet)
    return lines[:5]


def _direction_rules(scorecard: dict[str, Any]) -> dict[str, list[str]]:
    delivery = scorecard.get("delivery_targets")
    if isinstance(delivery, dict) and isinstance(delivery.get("direction_rules"), dict):
        return {
            str(label): [str(term) for term in terms if str(term)]
            for label, terms in delivery["direction_rules"].items()
            if isinstance(terms, list)
        }
    terms = scorecard.get("terms") if isinstance(scorecard.get("terms"), dict) else {}
    return {
        "核心能力": [str(item) for item in terms.get("must_have", []) if str(item)],
        "加分能力": [str(item) for item in terms.get("nice_to_have", []) if str(item)],
        "岗位匹配": [str(item) for item in terms.get("title_aliases", []) if str(item)],
    }


def _direction_labels(text: str, scorecard: dict[str, Any], title_level: str) -> list[str]:
    labels = [
        label
        for label, terms in _direction_rules(scorecard).items()
        if terms and any(_contains(text, term) for term in terms)
    ]
    if labels:
        return labels[:4]
    if title_level in {"precision", "technical"}:
        return ["岗位匹配"]
    return ["待深审"]


def _risk_summary(flags: list[str]) -> str:
    if not flags:
        return "无明显硬风险"
    labels = {
        "low_hunting_status": "求职状态偏低",
        "missing_detail_for_detailed_score": "缺少详情评分证据",
        "company_not_targeted": "公司不在目标池",
        "title_not_targeted": "职位方向不明确",
        "keyword_evidence_missing": "关键词证据不足",
    }
    result: list[str] = []
    for flag in flags:
        if flag.startswith("exclusion_terms:"):
            result.append("命中排除项：" + flag.split(":", 1)[1])
        else:
            result.append(labels.get(flag, flag))
    return "；".join(result)


def _outreach_angle(item: dict[str, Any]) -> str:
    company = item.get("current_company") or "当前团队"
    title = item.get("current_title") or "当前岗位"
    directions = "、".join(item.get("directions") or ["岗位匹配"])
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    keyword_text = "、".join(evidence.get("tech_keywords") or []) or directions
    if item.get("recommendation_label") == "强推荐":
        return f"优先从 {company} 的 {title} 经历切入，确认其在 {keyword_text} 上的角色深度、团队规模和近期机会意愿。"
    if item.get("recommendation_label") == "推荐":
        return f"围绕 {company} 的 {title} 经历追问 {keyword_text}，确认职责边界和岗位匹配深度。"
    if item.get("recommendation_label") == "观察":
        return f"先轻量深审 {company} 的 {title} 经历，重点确认核心能力证据是否真实匹配。"
    return "不进入主动外联队列；仅作为下一轮评分误判样本。"


def _education_score(education: str, weight: int) -> int:
    elite_terms = ["清华", "北京大学", "上海交通", "浙江大学", "复旦", "985", "211"]
    if any(term in education for term in elite_terms):
        return weight
    return weight // 2 if education else 0


def _risk_flags(
    candidate: Candidate,
    exclusion_hits: list[str],
    *,
    mode: str,
    detail_present: bool,
) -> list[str]:
    flags: list[str] = []
    if exclusion_hits:
        flags.append("exclusion_terms:" + ",".join(exclusion_hits))
    hunting_status = candidate.hunting_status or ""
    if any(term in hunting_status for term in ["不看", "暂不", "不考虑"]):
        flags.append("low_hunting_status")
    if mode == "detailed" and not detail_present:
        flags.append("missing_detail_for_detailed_score")
    return flags


def _recommendation_label(
    score: int,
    scorecard: dict[str, Any],
    risk_flags: list[str],
    *,
    directions: list[str] | None = None,
    key_evidence: list[str] | None = None,
) -> str:
    thresholds = _label_thresholds(scorecard)
    if any(flag.startswith("exclusion_terms:") for flag in risk_flags):
        return "不推荐"
    has_hard_risk = any(flag in HARD_RISK_FLAGS for flag in risk_flags)
    has_actionable_evidence = bool(key_evidence)
    is_pending_direction = directions == ["待深审"]
    if (
        score >= thresholds["strong_recommend"]
        and not has_hard_risk
        and has_actionable_evidence
        and not is_pending_direction
    ):
        return "强推荐"
    if score >= thresholds["recommend"]:
        return "推荐"
    if score >= thresholds["observe"]:
        return "观察"
    return "不推荐"


def _grade(recommendation_label: str) -> str:
    return {
        "强推荐": "A",
        "推荐": "B",
        "观察": "C",
        "不推荐": "淘汰",
    }.get(recommendation_label, "")


def score_candidate(
    bundle: CandidateBundle, scorecard: dict[str, Any], mode: str
) -> dict[str, Any]:
    if mode not in {"coarse", "detailed"}:
        raise ValueError("mode must be coarse or detailed")
    validate_scorecard(scorecard)
    _label_thresholds(scorecard)

    candidate = bundle.candidate
    text = _candidate_text(bundle, include_detail=mode == "detailed")
    weights = _dimension_weights(scorecard)
    dimension_scores: dict[str, int] = dict.fromkeys(_dimension_ids(scorecard), 0)

    company_hits = _matched_terms(
        _text_join([candidate.current_company, text]), _company_terms(scorecard)
    )
    title_hits = _matched_terms(candidate.current_title or "", _terms(scorecard, "title_aliases"))
    must_terms = _terms(scorecard, "must_have")
    nice_terms = _terms(scorecard, "nice_to_have")
    must_hits = _matched_terms(text, must_terms)
    nice_hits = _matched_terms(text, nice_terms)
    exclusion_hits = _matched_terms(text, _terms(scorecard, "exclusion_terms"))
    level = _title_level(candidate.current_title or "", title_hits, must_hits + nice_hits)
    detail_present = _detail_present(bundle.detail)

    if "company_context" in dimension_scores:
        dimension_scores["company_context"] = weights.get("company_context", 0) if company_hits else 0
    if "title_focus" in dimension_scores:
        dimension_scores["title_focus"] = weights.get("title_focus", 0) if title_hits else 0
    if "must_have" in dimension_scores:
        dimension_scores["must_have"] = _weighted_hits(
            len(must_hits), len(must_terms), weights.get("must_have", 0)
        )
    if "nice_to_have" in dimension_scores:
        dimension_scores["nice_to_have"] = _weighted_hits(
            len(nice_hits), len(nice_terms), weights.get("nice_to_have", 0)
        )
    if "seniority" in dimension_scores:
        seniority_weight = weights.get("seniority", 0)
        dimension_scores["seniority"] = (
            seniority_weight
            if candidate.work_years and 2 <= candidate.work_years <= 12
            else seniority_weight // 2
        )
    if "education" in dimension_scores:
        dimension_scores["education"] = _education_score(
            candidate.education or "", weights.get("education", 0)
        )
    if "risk" in dimension_scores and exclusion_hits:
        dimension_scores["risk"] = -abs(weights.get("risk", 0))

    score = max(0, min(100, sum(dimension_scores.values())))
    risks = _risk_flags(candidate, exclusion_hits, mode=mode, detail_present=detail_present)
    matched_terms = list(dict.fromkeys(company_hits + title_hits + must_hits + nice_hits))
    key_evidence = _key_evidence(bundle, company_hits, candidate.current_title or "", matched_terms)
    directions = _direction_labels(text, scorecard, level)
    label = _recommendation_label(
        score,
        scorecard,
        risks,
        directions=directions,
        key_evidence=key_evidence,
    )
    evidence = {
        "company": company_hits[0] if company_hits else candidate.current_company or "",
        "company_matches": company_hits,
        "title": candidate.current_title or "",
        "title_level": level,
        "tech_keywords": list(dict.fromkeys(must_hits + nice_hits)),
        "education": candidate.education or "",
        "work_years": candidate.work_years,
        "key_evidence": key_evidence,
        "detail_present": detail_present,
    }

    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "score": score,
        "score_mode": mode,
        "recommendation_label": label,
        "grade": _grade(label),
        "current_company": candidate.current_company or "",
        "current_title": candidate.current_title or "",
        "city": candidate.city or "",
        "work_years": candidate.work_years,
        "education": candidate.education or "",
        "dimensions": dimension_scores,
        "matched_terms_by_dimension": {
            "company_context": company_hits,
            "title_focus": title_hits,
            "must_have": must_hits,
            "nice_to_have": nice_hits,
        },
        "matched_terms": matched_terms,
        "directions": directions,
        "evidence": evidence,
        "risk_flags": risks,
        "risk_summary": _risk_summary(risks),
        "profile_url": _source_url(bundle),
        "platform_id": _platform_id(bundle),
    }


def _load_bundles_from_talentdb(db_path: str | Path, limit: int) -> list[CandidateBundle]:
    db = TalentDB(db_path)
    try:
        page = db.search(sort=SortSpec(field="updated_at", direction="desc"), page=1, page_size=limit)
        return [
            CandidateBundle(
                candidate=item,
                detail=db.get_detail(item.id),
                sources=db.get_sources(item.id),
            )
            for item in page.items
        ]
    finally:
        db.close()


def _load_bundles(db_path: str | Path, limit: int) -> list[CandidateBundle]:
    _validate_positive_int("limit", limit)
    if TalentDB is _REAL_TALENT_DB:
        with _temporary_readonly_db_copy(db_path) as copy_path:
            return _load_bundles_from_talentdb(copy_path, limit)
    return _load_bundles_from_talentdb(db_path, limit)


def _sort_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label_order = {"强推荐": 0, "推荐": 1, "观察": 2, "不推荐": 3}
    return sorted(
        scores,
        key=lambda item: (
            label_order.get(str(item["recommendation_label"]), 9),
            -int(item["score"]),
            int(item["candidate_id"]),
        ),
    )


def _priority(item: dict[str, Any]) -> str:
    if item["recommendation_label"] == "强推荐" and not item["risk_flags"]:
        return "P0"
    if item["recommendation_label"] in {"强推荐", "推荐"}:
        return "P1"
    if item["recommendation_label"] == "观察":
        return "P2"
    return "P3"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _md_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).replace("|", "/")


def _write_report(
    path: Path, ranked: list[dict[str, Any]], scorecard: dict[str, Any], top_n: int
) -> None:
    lines = [
        f"# {scorecard.get('target_role', scorecard.get('role_id', 'JD'))} 人才库推荐报告",
        "",
        f"- 评分卡：{scorecard.get('role_id', '')} / {scorecard.get('version', '')}",
        f"- TopN：{top_n}",
        "- 执行边界：只读本地人才库，未写入 `match_scores`，未触发平台搜索。",
        "",
        "## 评分维度",
        "",
        "| 维度 | 权重 |",
        "| --- | ---: |",
    ]
    for dimension in scorecard.get("dimensions", []):
        lines.append(
            f"| {dimension.get('label', dimension.get('id', ''))} | {dimension.get('weight', '')} |"
        )
    thresholds = scorecard.get("label_thresholds")
    if isinstance(thresholds, dict) and thresholds:
        threshold_labels = {
            "strong_recommend": "强推荐",
            "recommend": "推荐",
            "observe": "观察",
        }
        lines.extend(
            [
                "",
                "## 推荐阈值",
                "",
                "| 阈值 ID | 标签 | 分数线 |",
                "| --- | --- | ---: |",
            ]
        )
        for key in ("strong_recommend", "recommend", "observe"):
            if key in thresholds:
                lines.append(f"| {key} | {threshold_labels[key]} | {thresholds[key]} |")
    lines.extend(
        [
            "",
            "## Top 推荐总览",
            "",
            "| 排名 | ID | 姓名 | 评分 | 推荐 | 公司 | 职位 | 证据 | 风险 |",
            "| ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |",
        ]
    )
    for rank, item in enumerate(ranked[:top_n], start=1):
        lines.append(
            f"| {rank} | {item['candidate_id']} | {_md_cell(item['name'])} | {item['score']} | "
            f"{item['recommendation_label']} | {_md_cell(item['current_company'])} | "
            f"{_md_cell(item['current_title'])} | "
            f"{_md_cell('、'.join(item['matched_terms'][:8]))} | "
            f"{_md_cell('、'.join(item['risk_flags']) or '无明显硬风险')} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _outreach_row(rank: int, item: dict[str, Any]) -> dict[str, Any]:
    company = item.get("current_company", "")
    title = item.get("current_title", "")
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    key_evidence = evidence.get("key_evidence") or item.get("matched_terms", [])[:8]
    directions = item.get("directions") or item.get("matched_terms", [])[:4]
    return {
        "priority": _priority(item),
        "rank": rank,
        "candidate_id": item["candidate_id"],
        "name": item["name"],
        "platform_id": item.get("platform_id", ""),
        "company": company,
        "title": title,
        "city": item.get("city", ""),
        "work_years": item.get("work_years") or "",
        "score": item.get("score", ""),
        "recommendation_label": item.get("recommendation_label", ""),
        "grade": item.get("grade", ""),
        "directions": "、".join(str(item) for item in directions),
        "key_evidence": "；".join(str(item) for item in key_evidence),
        "risk_summary": item.get("risk_summary") or "无明显硬风险",
        "suggested_outreach_angle": _outreach_angle(item),
        "profile_url": item.get("profile_url", ""),
        "feedback_label": "",
        "feedback_stage": "",
        "reason_codes": "",
        "hunter_note": "",
        "contacted": "",
        "submitted_to_client": "",
        "interviewed": "",
        "offer": "",
    }


def _write_outreach_csv(path: Path, ranked: list[dict[str, Any]], top_n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS + FEEDBACK_CSV_FIELDS)
        writer.writeheader()
        for rank, item in enumerate(ranked[:top_n], start=1):
            writer.writerow(_outreach_row(rank, item))


def _write_outreach_md(path: Path, ranked: list[dict[str, Any]], top_n: int) -> None:
    lines = [
        "# 外联队列",
        "",
        "| 优先级 | 排名 | ID | 姓名 | 公司 | 职位 | 分数 | 外联角度 |",
        "| --- | ---: | ---: | --- | --- | --- | ---: | --- |",
    ]
    for rank, item in enumerate(ranked[:top_n], start=1):
        row = _outreach_row(rank, item)
        lines.append(
            f"| {row['priority']} | {rank} | {row['candidate_id']} | {_md_cell(row['name'])} | "
            f"{_md_cell(row['company'])} | {_md_cell(row['title'])} | {row['score']} | "
            f"{_md_cell(row['suggested_outreach_angle'])} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _grade_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counter = Counter(str(item.get("grade") or "") for item in items)
    return {grade: counter.get(grade, 0) for grade in ("A", "B", "C", "淘汰")}


def _read_outreach_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


SENSITIVE_OUTPUT_MARKERS = (
    "trackable_token",
    "access_token",
    "authorization: bearer",
    "sessionid",
    "raw/search",
    "raw/detail",
    "raw_capture",
    "sync_bundle",
    ".sqlite",
    ".db",
    ".zip",
)


def _marker_allowed_in_field(marker: str, field_name: str, value: str) -> bool:
    return (
        marker == "trackable_token"
        and field_name == "profile_url"
        and is_openable_maimai_profile_url(value)
    )


def _scan_value_for_delivery_issues(
    value: Any, *, field_name: str = "", label: str
) -> list[str]:
    issues: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            issues.extend(_scan_value_for_delivery_issues(str(key), label=label))
            issues.extend(
                _scan_value_for_delivery_issues(item, field_name=str(key), label=label)
            )
        return issues
    if isinstance(value, list):
        for item in value:
            issues.extend(_scan_value_for_delivery_issues(item, field_name=field_name, label=label))
        return issues
    text = str(value or "")
    normalized = text.lower().replace("\\", "/")
    for marker in SENSITIVE_OUTPUT_MARKERS:
        if marker in normalized and not _marker_allowed_in_field(marker, field_name, text):
            issues.append(f"sensitive_marker:{marker}:{label}")
    return issues


def _scan_csv_for_delivery_issues(text: str, label: str) -> list[str]:
    try:
        rows = list(csv.reader(text.splitlines()))
    except csv.Error:
        return _scan_value_for_delivery_issues(text, label=label)
    if not rows:
        return []
    headers = [str(item) for item in rows[0]]
    issues: list[str] = []
    for header in headers:
        issues.extend(_scan_value_for_delivery_issues(header, label=label))
    for row in rows[1:]:
        for index, cell in enumerate(row):
            field_name = headers[index] if index < len(headers) else ""
            issues.extend(
                _scan_value_for_delivery_issues(cell, field_name=field_name, label=label)
            )
    return issues


def _scan_file_for_delivery_issues(path: Path, root: Path) -> list[str]:
    label = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    if path.suffix.lower() == ".csv":
        issues = _scan_csv_for_delivery_issues(text, label)
    elif path.suffix.lower() == ".json":
        try:
            issues = _scan_value_for_delivery_issues(json.loads(text), label=label)
        except json.JSONDecodeError:
            issues = _scan_value_for_delivery_issues(text, label=label)
    else:
        issues = _scan_value_for_delivery_issues(text, label=label)
    for marker in MOJIBAKE_MARKERS:
        if marker in text:
            issues.append(f"mojibake_marker:{marker}:{label}")
    return issues


def _scan_text_for_delivery_issues(root: Path) -> list[str]:
    issues: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".json", ".md", ".csv", ".txt"}:
            continue
        if path.name == "quality-gates.json":
            continue
        issues.extend(_scan_file_for_delivery_issues(path, root))
    return issues


def validate_delivery_outputs(
    output_root: str | Path,
    *,
    ranked: list[dict[str, Any]],
    top_n: int,
    scorecard: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(output_root)
    critical: list[str] = []
    warnings: list[str] = []
    top_rows = ranked[:top_n]

    if len(top_rows) != top_n:
        critical.append("top_n_row_count_mismatch")
    if top_rows and all(str(item.get("grade") or "") in {"C", "淘汰"} for item in top_rows):
        critical.append("top_n_all_low_confidence")

    for item in top_rows:
        missing_fields = [
            field
            for field in ("candidate_id", "score", "grade", "recommendation_label", "profile_url")
            if item.get(field) in (None, "")
        ]
        evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
        if not evidence.get("key_evidence"):
            missing_fields.append("key_evidence")
        if missing_fields:
            critical.append(
                f"candidate_missing_fields:{item.get('candidate_id', '<unknown>')}:{','.join(missing_fields)}"
            )
        profile_url = str(item.get("profile_url") or "")
        if "trackable_token" in profile_url and not is_openable_maimai_profile_url(profile_url):
            critical.append(f"profile_url_invalid_trackable:{item.get('candidate_id', '<unknown>')}")

    outreach_path = root / "reports" / "outreach-queue.csv"
    try:
        rows = _read_outreach_rows(outreach_path)
    except FileNotFoundError:
        critical.append("missing_outreach_csv")
        rows = []
    except csv.Error as exc:
        critical.append(f"outreach_csv_parse_error:{exc}")
        rows = []

    if rows and len(rows) != top_n:
        critical.append("outreach_csv_row_count_mismatch")
    required_csv_fields = {
        "candidate_id",
        "company",
        "title",
        "score",
        "grade",
        "suggested_outreach_angle",
        "profile_url",
    }
    for index, row in enumerate(rows, start=2):
        missing = sorted(field for field in required_csv_fields if not row.get(field))
        if missing:
            critical.append(f"outreach_row_missing_fields:{index}:{','.join(missing)}")
        profile_url = str(row.get("profile_url") or "")
        if "trackable_token" in profile_url and not is_openable_maimai_profile_url(profile_url):
            critical.append(f"outreach_url_invalid_trackable:{index}")
        angle = row.get("suggested_outreach_angle") or ""
        company = row.get("company") or ""
        title = row.get("title") or ""
        if company and title and (company not in angle or title not in angle):
            warnings.append(f"outreach_angle_missing_company_or_title:{index}")

    critical.extend(_scan_text_for_delivery_issues(root))
    if scorecard is not None:
        must_have_count = len(_terms(scorecard, "must_have"))
        if must_have_count > 12:
            warnings.append(f"scorecard_many_must_have_terms:{must_have_count}")
    result = {
        "schema": "jd_talent_delivery_quality_gates_v1",
        "status": "blocked" if critical else "passed",
        "top_n": top_n,
        "ranked_count": len(ranked),
        "top_grade_counts": _grade_counts(top_rows),
        "critical_issues": sorted(dict.fromkeys(critical)),
        "warnings": sorted(dict.fromkeys(warnings)),
    }
    quality_path = root / "reports" / "quality-gates.json"
    quality_path.parent.mkdir(parents=True, exist_ok=True)
    quality_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def run_match(
    db_path: str | Path,
    scorecard_path: str | Path,
    out_dir: str | Path,
    top_n: int,
    limit: int = 5000,
) -> dict[str, Any]:
    _validate_positive_int("top_n", top_n)
    _validate_positive_int("limit", limit)
    scorecard = _load_json(scorecard_path)
    validate_scorecard(scorecard)
    _label_thresholds(scorecard)
    root = Path(out_dir)
    bundles = _load_bundles(db_path, limit=limit)

    coarse = _sort_scores(
        [score_candidate(bundle, scorecard, mode="coarse") for bundle in bundles]
    )
    detailed_candidate_ids = {
        item["candidate_id"] for item in coarse if item["recommendation_label"] != "不推荐"
    }
    detailed = _sort_scores(
        [
            score_candidate(bundle, scorecard, mode="detailed")
            for bundle in bundles
            if bundle.candidate.id in detailed_candidate_ids
        ]
    )
    result = {
        "read_only": True,
        "top_n": top_n,
        "summary": {"total_scored": len(detailed), "coarse_total": len(coarse)},
        "ranked": detailed[:top_n],
    }

    _write_json(root / "scoring" / "coarse-screen.json", {"scorecard": scorecard, "ranked": coarse})
    _write_json(root / "scoring" / "detailed-rank.json", result)
    _write_report(root / "scoring" / "coarse-screen.md", coarse, scorecard, top_n)
    _write_report(root / "scoring" / "detailed-rank.md", detailed, scorecard, top_n)
    _write_json(root / "reports" / "talent-recommendation.json", result)
    _write_report(root / "reports" / "talent-recommendation.md", detailed, scorecard, top_n)
    _write_outreach_csv(root / "reports" / "outreach-queue.csv", detailed, top_n)
    _write_outreach_md(root / "reports" / "outreach-queue.md", detailed, top_n)
    quality = validate_delivery_outputs(root, ranked=detailed[:top_n], top_n=top_n, scorecard=scorecard)
    result["quality_gates"] = quality
    _write_json(root / "reports" / "talent-recommendation.json", result)
    _write_json(root / "scoring" / "detailed-rank.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run JD talent delivery match")
    parser.add_argument("--db", required=True)
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args(argv)
    run_match(args.db, args.scorecard, args.out_dir, args.top_n, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
