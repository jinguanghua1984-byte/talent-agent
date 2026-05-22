"""LLM inference role matching against the local talent library.

This module is read-only against ``data/talent.db``. It generates local
recommendation artifacts and deliberately does not call ``save_match_score``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, SortSpec


ROLE_ID = "llm-inference-2026-05-21"
DEFAULT_PROFILE_PATH = Path("docs/design-discussions/2026-05-21-llm-inference-role-deep-dive.md")
DEFAULT_OUTPUT_PREFIX = Path("data/output") / f"talent-match-{date.today().isoformat()}-llm-inference"


COMPANY_TIERS: dict[str, list[str]] = {
    "基模公司": [
        "DeepSeek",
        "深度求索",
        "MiniMax",
        "月之暗面",
        "Kimi",
        "Moonshot",
        "阶跃星辰",
        "智谱",
        "零一万物",
        "百川",
    ],
    "大厂AI Infra": [
        "字节",
        "火山引擎",
        "百度",
        "阿里",
        "阿里云",
        "腾讯",
        "腾讯云",
        "蚂蚁",
        "Ant Group",
    ],
    "相关AI平台": [
        "华为",
        "昆仑万维",
        "爱诗科技",
        "LoveArt",
        "生数科技",
        "硅基流动",
        "无问芯穹",
        "商汤",
        "美团",
        "拼多多",
        "京东",
        "小米",
    ],
}

PRIORITY_SCHOOLS = {
    "清华大学",
    "北京大学",
    "复旦大学",
    "上海交通大学",
    "浙江大学",
    "南京大学",
    "中国科学技术大学",
    "哈尔滨工业大学",
    "西安交通大学",
    "中国人民大学",
    "北京航空航天大学",
    "同济大学",
    "华中科技大学",
    "武汉大学",
    "中山大学",
    "电子科技大学",
    "北京理工大学",
    "北京邮电大学",
    "西安电子科技大学",
    "北京交通大学",
    "天津大学",
    "吉林大学",
    "华南理工大学",
}


ROLE_TERMS = {
    "推理框架": 16,
    "推理引擎": 16,
    "大模型推理": 16,
    "LLM serving": 16,
    "模型服务": 13,
    "大模型infra": 13,
    "AI Infra": 13,
    "训推": 12,
    "系统工程": 10,
    "GPU": 10,
    "CUDA": 10,
    "算子": 8,
    "训练框架": 6,
    "分布式训练": 5,
}

FRAMEWORK_TERMS = {
    "vllm": 8,
    "sglang": 8,
    "tensorrt-llm": 8,
    "tensorrt": 5,
    "triton": 5,
    "tgi": 4,
    "kserve": 4,
    "ray serve": 4,
    "推理框架": 8,
    "二次开发": 6,
    "源码": 5,
    "scheduler": 6,
    "调度": 5,
    "dynamic batch": 6,
    "continuous batching": 7,
    "pagedattention": 6,
    "kv cache": 8,
    "kvcache": 8,
    "prefix cache": 6,
    "prefill": 7,
    "decode": 7,
    "pd分离": 7,
    "pd 分离": 7,
    "disaggregated": 6,
}

PERFORMANCE_TERMS = {
    "量化": 5,
    "awq": 5,
    "gptq": 5,
    "fp8": 5,
    "int8": 4,
    "int4": 4,
    "cuda graph": 5,
    "torch compile": 5,
    "torch.compile": 5,
    "flash attention": 5,
    "attention": 3,
    "gemm": 4,
    "moe": 4,
    "fused": 4,
    "deepep": 5,
    "cutlass": 4,
    "nsight": 4,
    "显存": 4,
    "吞吐": 4,
    "低延迟": 4,
    "ttft": 5,
    "tpot": 5,
    "qps": 4,
    "tps": 4,
    "成本": 4,
    "gpu利用率": 4,
}

SERVING_TERMS = {
    "线上": 4,
    "在线服务": 5,
    "服务化": 5,
    "高并发": 5,
    "sla": 5,
    "slo": 5,
    "p95": 4,
    "p99": 4,
    "监控": 3,
    "可观测": 4,
    "告警": 3,
    "熔断": 4,
    "降级": 4,
    "容错": 4,
    "压测": 4,
    "扩缩容": 4,
}

APPLICATION_ONLY_TERMS = ["rag", "agent", "prompt", "mcp", "dify", "langflow", "智能体"]
EXCLUDED_TITLE_TERMS = ["运营", "HR", "人事", "招聘", "销售", "数据标注", "审核", "测试开发"]
NEGATION_TERMS = ("没有", "无", "未", "不具备", "缺少", "缺乏", "not ", "no ")


@dataclass(frozen=True)
class CandidateBundle:
    candidate: Candidate
    detail: CandidateDetail | None
    sources: list[dict[str, Any]]


def _text_join(values: Iterable[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            parts.append(_text_join(value.values()))
        elif isinstance(value, (list, tuple, set)):
            parts.append(_text_join(value))
        else:
            parts.append(str(value))
    return " ".join(part for part in parts if part)


def detail_text(detail: CandidateDetail | None) -> str:
    if detail is None:
        return ""
    return _text_join([
        detail.work_experience or (),
        detail.education_experience or (),
        detail.project_experience or (),
        detail.summary or "",
        detail.raw_data or {},
    ])


def candidate_text(candidate: Candidate, detail: CandidateDetail | None) -> str:
    return _text_join([
        candidate.name,
        candidate.current_company,
        candidate.current_title,
        candidate.education,
        list(candidate.skill_tags),
        detail_text(detail),
    ])


def company_context_text(candidate: Candidate, detail: CandidateDetail | None) -> str:
    companies: list[str] = []
    if candidate.current_company:
        companies.append(candidate.current_company)
    if detail and detail.work_experience:
        for work in detail.work_experience:
            company = work.get("company")
            if company:
                companies.append(str(company))
    return _text_join(companies)


def _contains(text: str, term: str) -> bool:
    if term.isascii():
        return term.lower() in text.lower()
    return term in text


def _is_negated_context(context: str) -> bool:
    lowered = context.lower()
    return any(negation in lowered for negation in NEGATION_TERMS)


def _has_positive_term(text: str, term: str) -> bool:
    haystack = text.lower() if term.isascii() else text
    needle = term.lower() if term.isascii() else term
    start = 0
    while True:
        index = haystack.find(needle, start)
        if index < 0:
            return False
        context = haystack[max(0, index - 12):index]
        if not _is_negated_context(context):
            return True
        start = index + len(needle)


def _matched_terms(text: str, weighted_terms: dict[str, int]) -> list[str]:
    return [term for term in weighted_terms if _has_positive_term(text, term)]


def _weighted_score(text: str, weighted_terms: dict[str, int], cap: int) -> tuple[int, list[str]]:
    matched = _matched_terms(text, weighted_terms)
    score = min(cap, sum(weighted_terms[term] for term in matched))
    return score, matched


def company_score(text: str) -> tuple[int, str, str]:
    for tier, companies in COMPANY_TIERS.items():
        for company in companies:
            if _contains(text, company):
                return {"基模公司": 16, "大厂AI Infra": 13, "相关AI平台": 9}[tier], tier, company
    return 0, "非目标公司", ""


def education_score(candidate: Candidate, detail: CandidateDetail | None) -> tuple[int, str]:
    text = _text_join([
        candidate.education,
        detail.education_experience if detail else (),
        detail.raw_data if detail else {},
    ])
    for school in PRIORITY_SCHOOLS:
        if school in text:
            return 8, school
    for label in ["985", "211", "QS Top500", "Top500", "世界前500"]:
        if label.lower() in text.lower():
            return 7, label
    if any(degree in text for degree in ["博士", "硕士", "本科"]):
        return 4, candidate.education or "本科及以上"
    return 0, candidate.education or ""


def years_score(years: int | None) -> tuple[int, str]:
    if years is None:
        return 3, "年限未知"
    if 1 <= years <= 7:
        return 8, "1-7年匹配"
    if 8 <= years <= 10:
        return 5, "8-10年偏资深"
    if years == 0:
        return 4, "应届/实习"
    if 10 < years <= 15:
        return 2, "超过目标年限"
    return 0, "年限明显偏离"


def role_score(title: str, text: str) -> tuple[int, list[str]]:
    score, matched = _weighted_score(_text_join([title, text]), ROLE_TERMS, cap=16)
    return score, matched


def availability_risk(status: str | None) -> str | None:
    if not status:
        return None
    if "不看" in status or status in {"3"}:
        return "当前求职状态偏低"
    if "观望" in status:
        return "在职观望"
    return None


def score_bundle(bundle: CandidateBundle) -> dict[str, Any]:
    candidate = bundle.candidate
    detail = bundle.detail
    text = candidate_text(candidate, detail)
    title = candidate.current_title or ""

    company_points, company_tier, company_hit = company_score(company_context_text(candidate, detail))
    role_points, role_hits = role_score(title, text)
    framework_points, framework_hits = _weighted_score(text, FRAMEWORK_TERMS, cap=22)
    performance_points, performance_hits = _weighted_score(text, PERFORMANCE_TERMS, cap=18)
    serving_points, serving_hits = _weighted_score(text, SERVING_TERMS, cap=12)
    edu_points, edu_hit = education_score(candidate, detail)
    year_points, year_label = years_score(candidate.work_years)

    raw_score = (
        company_points
        + role_points
        + framework_points
        + performance_points
        + serving_points
        + edu_points
        + year_points
    )
    risks: list[str] = []
    gaps: list[str] = []

    if any(term in title for term in EXCLUDED_TITLE_TERMS):
        risks.append("当前职位标题存在明显偏离")
        raw_score -= 10
    if framework_points < 8:
        gaps.append("推理框架二开证据不足")
    if serving_points < 4:
        gaps.append("线上服务/SLA/稳定性证据不足")
    if performance_points < 6:
        gaps.append("成本治理或性能优化证据不足")
    if company_points == 0:
        gaps.append("公司池不在优先范围")
    if edu_points < 7:
        gaps.append("学校硬门槛证据不足或需复核")
    availability = availability_risk(candidate.hunting_status)
    if availability:
        risks.append(availability)
    if candidate.work_years is not None and candidate.work_years > 10:
        risks.append("年限超过1-7年目标")
    if (
        any(_contains(text, term) for term in APPLICATION_ONLY_TERMS)
        and framework_points < 8
        and performance_points < 6
    ):
        risks.append("偏应用层/Agent/RAG，推理系统深度不足")

    score = max(0, min(100, raw_score))
    if score >= 82 and framework_points >= 12 and performance_points >= 8:
        label = "强推荐"
    elif score >= 72 and framework_points >= 8:
        label = "推荐"
    elif score >= 60:
        label = "观察"
    else:
        label = "不推荐"

    if "当前职位标题存在明显偏离" in risks and label in {"强推荐", "推荐"}:
        label = "观察"
    if candidate.work_years is not None and candidate.work_years > 10 and label in {"强推荐", "推荐"}:
        label = "观察"

    highlights = build_highlights(
        company_tier,
        company_hit,
        role_hits,
        framework_hits,
        performance_hits,
        serving_hits,
        edu_hit,
        year_label,
    )

    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "score": score,
        "recommendation_label": label,
        "current_company": candidate.current_company or "",
        "current_title": candidate.current_title or "",
        "city": candidate.city or "",
        "work_years": candidate.work_years,
        "education": candidate.education or "",
        "hunting_status": candidate.hunting_status or "",
        "data_level": candidate.data_level,
        "dimensions": {
            "company": company_points,
            "role_focus": role_points,
            "framework_depth": framework_points,
            "performance_cost": performance_points,
            "serving_stability": serving_points,
            "education": edu_points,
            "years": year_points,
        },
        "evidence": {
            "company_tier": company_tier,
            "company_hit": company_hit,
            "role_terms": role_hits,
            "framework_terms": framework_hits,
            "performance_terms": performance_hits,
            "serving_terms": serving_hits,
            "education_hit": edu_hit,
            "years_label": year_label,
        },
        "highlights": highlights,
        "gaps": gaps,
        "risks": risks,
        "work_experience": list(detail.work_experience or ()) if detail else [],
        "education_experience": list(detail.education_experience or ()) if detail else [],
        "project_experience": list(detail.project_experience or ()) if detail else [],
        "source_profiles": bundle.sources,
    }


def build_highlights(
    company_tier: str,
    company_hit: str,
    role_hits: list[str],
    framework_hits: list[str],
    performance_hits: list[str],
    serving_hits: list[str],
    edu_hit: str,
    year_label: str,
) -> list[str]:
    highlights: list[str] = []
    if company_hit:
        highlights.append(f"{company_tier}背景：{company_hit}")
    if role_hits:
        highlights.append("岗位方向命中：" + "、".join(role_hits[:4]))
    if framework_hits:
        highlights.append("推理框架/调度证据：" + "、".join(framework_hits[:6]))
    if performance_hits:
        highlights.append("性能与成本证据：" + "、".join(performance_hits[:6]))
    if serving_hits:
        highlights.append("在线服务稳定性证据：" + "、".join(serving_hits[:5]))
    if edu_hit:
        highlights.append(f"教育背景：{edu_hit}")
    highlights.append(year_label)
    return highlights[:7]


def load_bundles(db_path: str | Path, limit: int) -> list[CandidateBundle]:
    db = TalentDB(db_path)
    try:
        page = db.search(sort=SortSpec(field="updated_at", direction="desc"), page=1, page_size=limit)
        bundles: list[CandidateBundle] = []
        for candidate in page.items:
            sources = [
                {
                    "platform": source.platform,
                    "platform_id": source.platform_id,
                    "profile_url": source.profile_url,
                    "fetched_at": source.fetched_at,
                }
                for source in db.get_sources(candidate.id)
            ]
            bundles.append(
                CandidateBundle(
                    candidate=candidate,
                    detail=db.get_detail(candidate.id),
                    sources=sources,
                )
            )
        return bundles
    finally:
        db.close()


def rank_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label_order = {"强推荐": 0, "推荐": 1, "观察": 2, "不推荐": 3}
    return sorted(
        scores,
        key=lambda item: (
            label_order.get(item["recommendation_label"], 9),
            -item["score"],
            -(item["work_years"] or 0),
            item["candidate_id"],
        ),
    )


def summarize(ranked: list[dict[str, Any]]) -> dict[str, Any]:
    labels = {"强推荐": 0, "推荐": 0, "观察": 0, "不推荐": 0}
    for item in ranked:
        labels[item["recommendation_label"]] = labels.get(item["recommendation_label"], 0) + 1
    return {
        "total_scored": len(ranked),
        "labels": labels,
        "recommended_count": labels["强推荐"] + labels["推荐"],
    }


def short_work_summary(item: dict[str, Any], max_items: int = 3) -> str:
    parts: list[str] = []
    for work in item.get("work_experience", [])[:max_items]:
        company = work.get("company") or ""
        title = work.get("title") or ""
        period = work.get("period") or ""
        desc = re.sub(r"\s+", " ", str(work.get("description") or "")).strip()
        if len(desc) > 110:
            desc = desc[:107] + "..."
        parts.append(" / ".join(value for value in [period, company, title, desc] if value))
    return "；".join(parts)


def short_education_summary(item: dict[str, Any], max_items: int = 2) -> str:
    parts: list[str] = []
    for edu in item.get("education_experience", [])[:max_items]:
        parts.append(" / ".join(str(edu.get(key) or "") for key in ["school", "description"] if edu.get(key)))
    return "；".join(parts)


def source_url(item: dict[str, Any]) -> str:
    for source in item.get("source_profiles", []):
        if source.get("profile_url"):
            return source["profile_url"]
    return ""


def md_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return re.sub(r"\s+", " ", text).replace("|", r"\|").strip()


def render_markdown(
    ranked: list[dict[str, Any]],
    profile_path: Path,
    top_n: int,
    all_count: int,
) -> str:
    summary = summarize(ranked)
    top_items = ranked[:top_n]
    lines = [
        "# LLM 大模型推理岗位人才库推荐报告",
        "",
        f"- 岗位画像来源：`{profile_path.as_posix()}`",
        f"- 数据源：`data/talent.db`，只读扫描 {all_count} 人",
        "- 执行边界：未进入 `maimai-talent-search-campaign`，未触发平台搜索，未写入 `match_scores` 或候选人记录",
        f"- 评分结果：强推荐 {summary['labels'].get('强推荐', 0)}，推荐 {summary['labels'].get('推荐', 0)}，观察 {summary['labels'].get('观察', 0)}，不推荐 {summary['labels'].get('不推荐', 0)}",
        "",
        "## 评分口径",
        "",
        "| 维度 | 权重 | 说明 |",
        "| --- | ---: | --- |",
        "| 公司与业务上下文 | 16 | 基模公司、大厂 AI Infra、相关 AI 平台优先 |",
        "| 岗位方向 | 16 | 大模型推理、推理框架、模型服务、GPU/CUDA/算子等 |",
        "| 推理框架深度 | 22 | vLLM/SGLang/TensorRT-LLM、KV Cache、Prefill/Decode、调度、批处理 |",
        "| 性能与成本治理 | 18 | 量化、CUDA Graph、torch compile、MoE、显存、TTFT/TPOT、吞吐、成本 |",
        "| 在线服务稳定性 | 12 | 高并发、SLA/SLO、P95/P99、监控、熔断、降级、压测 |",
        "| 学校背景 | 8 | 985/211/QS Top500 或强校证据 |",
        "| 年限匹配 | 8 | 1-7 年优先，8-10 年降权，10 年以上标记风险 |",
        "",
        "## Top 推荐总览",
        "",
        "| 排名 | ID | 姓名 | 评分 | 推荐 | 当前公司 | 职位 | 年限 | 学校/学历 | 核心证据 | 风险 |",
        "| ---: | ---: | --- | ---: | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for rank, item in enumerate(top_items, start=1):
        evidence = "；".join(item["highlights"][:3])
        risks = "；".join(item["risks"][:2]) if item["risks"] else ""
        edu = short_education_summary(item) or item.get("education", "")
        lines.append(
            f"| {rank} | {item['candidate_id']} | {md_cell(item['name'])} | {item['score']} | "
            f"{md_cell(item['recommendation_label'])} | {md_cell(item['current_company'])} | {md_cell(item['current_title'])} | "
            f"{item.get('work_years') if item.get('work_years') is not None else ''} | {md_cell(edu)} | {md_cell(evidence)} | {md_cell(risks)} |"
        )

    lines.extend(["", "## 重点候选人详评", ""])
    for rank, item in enumerate(top_items, start=1):
        lines.extend([
            f"### {rank}. {item['name']}（ID {item['candidate_id']}）",
            "",
            f"- 推荐评级：{item['recommendation_label']}，{item['score']}/100",
            f"- 当前：{item['current_company']}｜{item['current_title']}｜{item.get('work_years') or ''} 年｜{item.get('city') or ''}",
            f"- 学历：{short_education_summary(item) or item.get('education', '')}",
            f"- 来源链接：{source_url(item) or '无'}",
            "- 核心优势：",
        ])
        for highlight in item["highlights"][:6]:
            lines.append(f"  - {highlight}")
        lines.append("- 主要差距：")
        for gap in item["gaps"][:4] or ["暂无明显硬差距，建议面试中验证实际二开深度"]:
            lines.append(f"  - {gap}")
        lines.append("- 风险点：")
        for risk in item["risks"][:4] or ["暂无明显风险，需继续确认求职意愿和薪酬预期"]:
            lines.append(f"  - {risk}")
        lines.extend([
            f"- 职业经历摘要：{short_work_summary(item) or '暂无详细经历'}",
            "",
        ])

    lines.extend([
        "## 下一步建议",
        "",
        "1. 对强推荐和推荐候选人优先做人工复核，重点验证 vLLM/SGLang/TensorRT-LLM 是否只是使用还是做过核心模块二开。",
        "2. 面试重点围绕 KV Cache、Prefill/Decode、请求调度、量化收益、TTFT/TPOT 和线上 SLA 展开。",
        "3. 对当前求职状态为“不看”的候选人，先用技术挑战和 H100/H200 真实业务负载做软触达，不建议直接强推。",
        "4. 对华为/国产卡背景候选人，单独确认是否熟悉 NVIDIA 生态和开源推理框架。",
        "",
        "## 全量分档摘要",
        "",
    ])
    for label in ["强推荐", "推荐", "观察", "不推荐"]:
        items = [item for item in ranked if item["recommendation_label"] == label]
        lines.append(f"- {label}：{len(items)} 人")
    lines.append("")
    return "\n".join(lines)


def write_outputs(
    ranked: list[dict[str, Any]],
    out_md: Path,
    out_json: Path,
    profile_path: Path,
    scanned_count: int,
    top_n: int,
) -> None:
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(
        render_markdown(ranked, profile_path=profile_path, top_n=top_n, all_count=scanned_count),
        encoding="utf-8-sig",
    )
    export = {
        "role_id": ROLE_ID,
        "profile_path": profile_path.as_posix(),
        "generated_at": date.today().isoformat(),
        "read_only": True,
        "summary": summarize(ranked),
        "top_n": ranked[:top_n],
        "ranked": [
            {
                key: value
                for key, value in item.items()
                if key not in {"work_experience", "education_experience", "project_experience", "source_profiles"}
            }
            for item in ranked
        ],
    }
    out_json.write_text(json.dumps(export, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def run(
    db_path: str | Path,
    profile_path: str | Path,
    out_md: str | Path,
    out_json: str | Path,
    limit: int,
    top_n: int,
) -> dict[str, Any]:
    profile = Path(profile_path)
    if not profile.exists():
        raise FileNotFoundError(profile)
    bundles = load_bundles(db_path, limit=limit)
    scores = rank_scores([score_bundle(bundle) for bundle in bundles])
    write_outputs(scores, Path(out_md), Path(out_json), profile, len(bundles), top_n)
    return {"scanned": len(bundles), "summary": summarize(scores), "out_md": str(out_md), "out_json": str(out_json)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从人才库匹配 LLM 大模型推理岗位候选人")
    parser.add_argument("--db", default="data/talent.db")
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE_PATH))
    parser.add_argument("--out-md", default=str(DEFAULT_OUTPUT_PREFIX.with_suffix(".md")))
    parser.add_argument("--out-json", default=str(DEFAULT_OUTPUT_PREFIX.with_suffix(".json")))
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--top-n", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run(
        db_path=args.db,
        profile_path=args.profile,
        out_md=args.out_md,
        out_json=args.out_json,
        limit=args.limit,
        top_n=args.top_n,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
