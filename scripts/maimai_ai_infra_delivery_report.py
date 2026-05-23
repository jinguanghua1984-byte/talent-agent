"""生成 AI Infra V2 交付版最终寻访报告和外联优先级。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_detail_report import build_detail_report
from scripts.maimai_url import sanitize_maimai_profile_url


RECOMMENDATION_LABELS = ("强推荐", "推荐", "观察", "不推荐")
GRADE_KEYS = ("A", "B", "C", "淘汰")
QUEUE_KEYS = ("P0", "P1", "P2")
HARD_REJECT_FLAGS = {
    "excluded_title",
    "excluded_education",
    "company_not_targeted",
    "school_not_priority",
    "age_over_40",
    "score_below_threshold",
    "missing_detail_for_detailed_score",
}
RISK_LABELS = {
    "excluded_title": "职位硬排除",
    "excluded_education": "学历/院校硬排除",
    "company_not_targeted": "公司不在目标池",
    "school_not_priority": "院校不满足硬门槛",
    "age_over_40": "年龄超过 40",
    "score_below_threshold": "评分低于门槛",
    "missing_detail_for_detailed_score": "缺少详情评分证据",
}
DIRECTION_RULES: dict[str, tuple[str, ...]] = {
    "训练框架": (
        "训练",
        "分布式训练",
        "训练框架",
        "PyTorch",
        "TensorFlow",
        "FSDP",
        "DeepSpeed",
        "Megatron",
        "Flash attention",
        "模型训练",
    ),
    "推理引擎": (
        "推理",
        "Inference",
        "Serving",
        "部署",
        "TensorRT",
        "Triton",
        "vLLM",
        "LLM",
        "Llama",
        "加速",
    ),
    "框架平台": (
        "AI Infra",
        "ML Infra",
        "大模型平台",
        "机器学习平台",
        "模型平台",
        "平台工程",
        "框架",
        "AI 平台",
    ),
    "算子/异构": (
        "算子",
        "CUDA",
        "GPU",
        "NPU",
        "异构",
        "编译",
        "kernel",
        "高性能",
        "性能优化",
    ),
    "智算平台": (
        "智算",
        "集群",
        "调度",
        "Kubernetes",
        "GPU 集群",
        "GPU集群",
        "资源调度",
        "云原生",
    ),
}


def _load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_text(path: str | Path, text: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(text, encoding="utf-8-sig")


def _json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {key: row[key] for key in row.keys()}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _shorten(text: str, limit: int = 180) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def _text_join(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, dict):
            parts.append(_text_join(list(value.values())))
        elif isinstance(value, (list, tuple, set)):
            parts.append(_text_join(list(value)))
        else:
            parts.append(str(value))
    return " ".join(part for part in parts if part)


def _contains_term(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.lower() in text.lower()
    return term in text


def _ranked_items(rank_data: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = rank_data.get("ranked")
    if isinstance(ranked, list):
        return [item for item in ranked if isinstance(item, dict)]

    items: list[dict[str, Any]] = []
    grades = rank_data.get("grades")
    if isinstance(grades, dict):
        for grade in GRADE_KEYS:
            grade_items = grades.get(grade, [])
            if isinstance(grade_items, list):
                items.extend(item for item in grade_items if isinstance(item, dict))
    return items


def _target_contacts(targets: dict[str, Any]) -> list[dict[str, Any]]:
    contacts = targets.get("contacts")
    return [item for item in contacts if isinstance(item, dict)] if isinstance(contacts, list) else []


def _target_contact_map(targets: dict[str, Any]) -> dict[int, dict[str, Any]]:
    by_candidate: dict[int, dict[str, Any]] = {}
    for contact in _target_contacts(targets):
        candidate_id = _as_int(contact.get("candidate_id"), -1)
        if candidate_id < 0 or candidate_id in by_candidate:
            continue
        by_candidate[candidate_id] = contact
    return by_candidate


def _distribution(values: list[Any], keys: tuple[str, ...] = ()) -> dict[str, int]:
    counter = Counter(str(value or "") for value in values if value not in (None, ""))
    result = {key: counter.get(key, 0) for key in keys}
    for key, value in counter.items():
        result.setdefault(key, value)
    return result


class ReadOnlyCampaignStore:
    """只读读取 campaign DB 中的候选人、详情和脉脉 source。"""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._conn: sqlite3.Connection | None = None
        if self.db_path.exists():
            uri = self.db_path.resolve().as_uri() + "?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()

    def candidate(self, candidate_id: int) -> dict[str, Any]:
        if self._conn is None:
            return {}
        row = self._conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
        data = _row_to_dict(row)
        data["skill_tags"] = _json_loads(data.get("skill_tags"), [])
        return data

    def detail(self, candidate_id: int) -> dict[str, Any]:
        if self._conn is None:
            return {}
        row = self._conn.execute(
            "SELECT * FROM candidate_details WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchone()
        data = _row_to_dict(row)
        for field in ("work_experience", "education_experience", "project_experience"):
            data[field] = _json_loads(data.get(field), [])
        data["raw_data"] = _json_loads(data.get("raw_data"), {})
        return data

    def maimai_source(self, candidate_id: int) -> dict[str, Any]:
        if self._conn is None:
            return {}
        row = self._conn.execute(
            """
            SELECT *
            FROM source_profiles
            WHERE candidate_id = ?
              AND platform = 'maimai'
            ORDER BY id
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        data = _row_to_dict(row)
        data["raw_profile"] = _json_loads(data.get("raw_profile"), {})
        return data


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


def _key_evidence(item: dict[str, Any], candidate: dict[str, Any], detail: dict[str, Any]) -> list[str]:
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    keywords = evidence.get("tech_keywords") if isinstance(evidence.get("tech_keywords"), list) else []
    lines: list[str] = []
    company = evidence.get("company") or candidate.get("current_company") or ""
    title = evidence.get("title") or candidate.get("current_title") or ""
    if company or title or keywords:
        keyword_text = "、".join(str(keyword) for keyword in keywords[:8])
        parts = [part for part in (company, title, f"关键词：{keyword_text}" if keyword_text else "") if part]
        lines.append("评分证据：" + " / ".join(parts))

    for work in (detail.get("work_experience") or [])[:2]:
        if isinstance(work, dict):
            snippet = _experience_snippet("工作经历", work)
            if snippet:
                lines.append(snippet)
    for project in (detail.get("project_experience") or [])[:1]:
        if isinstance(project, dict):
            snippet = _experience_snippet("项目经历", project)
            if snippet:
                lines.append(snippet)
    for edu in (detail.get("education_experience") or [])[:1]:
        if isinstance(edu, dict):
            snippet = _experience_snippet("教育经历", edu, limit=120)
            if snippet:
                lines.append(snippet)

    return lines[:5]


def _direction_labels(
    item: dict[str, Any],
    candidate: dict[str, Any],
    detail: dict[str, Any],
) -> list[str]:
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    text = _text_join([
        evidence,
        candidate.get("current_company"),
        candidate.get("current_title"),
        candidate.get("skill_tags"),
        detail.get("work_experience"),
        detail.get("project_experience"),
        detail.get("summary"),
    ])
    labels = [
        label
        for label, terms in DIRECTION_RULES.items()
        if any(_contains_term(text, term) for term in terms)
    ]
    if not labels and evidence.get("title_level") in {"precision", "technical"}:
        labels.append("框架平台")
    return labels or ["待深审"]


def _risk_summary(flags: list[str]) -> str:
    if not flags:
        return "无明显硬风险"
    labels = [RISK_LABELS.get(flag, flag) for flag in flags]
    return "；".join(labels)


def _recommendation_label(item: dict[str, Any], directions: list[str], key_evidence: list[str]) -> str:
    grade = str(item.get("grade") or "")
    score = _as_float(item.get("score"))
    flags = [str(flag) for flag in item.get("risk_flags") or []]
    if grade == "淘汰" or any(flag in HARD_REJECT_FLAGS for flag in flags):
        return "不推荐"
    if (
        grade == "A"
        and score >= 85
        and directions != ["待深审"]
        and key_evidence
    ):
        return "强推荐"
    if grade in {"A", "B"} and score >= 75:
        return "推荐"
    if score >= 65 or grade == "C":
        return "观察"
    return "不推荐"


def _outreach_angle(card: dict[str, Any]) -> str:
    company = card.get("company") or "当前团队"
    directions = "、".join(card.get("directions") or ["AI Infra"])
    keywords = card.get("rank_evidence", {}).get("tech_keywords") or []
    keyword_text = "、".join(str(keyword) for keyword in keywords[:3]) or directions
    if card.get("recommendation_label") == "强推荐":
        return (
            f"优先从 {company} 的{directions}经历切入，确认其在 {keyword_text} "
            "上的角色深度、团队规模和近期机会意愿。"
        )
    if card.get("recommendation_label") == "推荐":
        return (
            f"围绕 {directions} 与 {keyword_text} 追问具体职责，先确认底层系统深度和转岗动机。"
        )
    if card.get("recommendation_label") == "观察":
        return "先做轻量深审，重点确认是否真的做过训练、推理、框架、算子或智算平台底层工作。"
    return "不进入外联队列；仅作为下一轮评分误判样本。"


def _candidate_card(
    rank_index: int,
    item: dict[str, Any],
    target: dict[str, Any],
    store: ReadOnlyCampaignStore,
) -> dict[str, Any]:
    candidate_id = _as_int(item.get("candidate_id"))
    candidate = store.candidate(candidate_id)
    detail = store.detail(candidate_id)
    source = store.maimai_source(candidate_id)
    evidence = item.get("evidence") if isinstance(item.get("evidence"), dict) else {}
    directions = _direction_labels(item, candidate, detail)
    key_evidence = _key_evidence(item, candidate, detail)
    risk_flags = [str(flag) for flag in item.get("risk_flags") or []]
    recommendation = _recommendation_label(item, directions, key_evidence)
    company = (
        candidate.get("current_company")
        or evidence.get("company")
        or target.get("company")
        or ""
    )
    title = (
        candidate.get("current_title")
        or evidence.get("title")
        or target.get("position")
        or ""
    )
    platform_id = source.get("platform_id") or target.get("id") or target.get("platform_id") or ""
    profile_url = sanitize_maimai_profile_url(
        source.get("profile_url") or target.get("detail_url") or target.get("profile_url") or ""
    )
    card = {
        "rank": rank_index,
        "candidate_id": candidate_id,
        "name": candidate.get("name") or item.get("name") or target.get("name") or "",
        "platform": "maimai",
        "platform_id": str(platform_id) if platform_id else "",
        "profile_url": profile_url,
        "company": company,
        "title": title,
        "city": candidate.get("city") or target.get("city") or "",
        "age": candidate.get("age"),
        "age_band": item.get("age_band"),
        "work_years": candidate.get("work_years") or evidence.get("work_years"),
        "education": candidate.get("education") or evidence.get("education") or "",
        "skill_tags": candidate.get("skill_tags") or [],
        "score": item.get("score"),
        "grade": item.get("grade"),
        "recommendation_label": recommendation,
        "priority": "",
        "source_grade": target.get("grade"),
        "source_score": target.get("score"),
        "source_wave": target.get("wave_id"),
        "directions": directions,
        "rank_evidence": evidence,
        "key_evidence": key_evidence,
        "risk_flags": risk_flags,
        "risk_summary": _risk_summary(risk_flags),
    }
    card["suggested_outreach_angle"] = _outreach_angle(card)
    return card


def _assign_priorities(cards: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    queues: dict[str, list[dict[str, Any]]] = {key: [] for key in QUEUE_KEYS}
    for card in cards:
        label = card["recommendation_label"]
        if label == "不推荐":
            continue
        if label == "强推荐" and len(queues["P0"]) < 150:
            priority = "P0"
        elif label in {"强推荐", "推荐"} and len(queues["P1"]) < 300:
            priority = "P1"
        else:
            priority = "P2"
        card["priority"] = priority
        queues[priority].append(card)
    return queues


def _direction_coverage(cards: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    coverage: dict[str, dict[str, int]] = {
        label: {key: 0 for key in (*RECOMMENDATION_LABELS, *QUEUE_KEYS, "total")}
        for label in (*DIRECTION_RULES.keys(), "待深审")
    }
    for card in cards:
        if card["recommendation_label"] == "不推荐":
            continue
        for direction in card.get("directions") or ["待深审"]:
            bucket = coverage.setdefault(
                direction,
                {key: 0 for key in (*RECOMMENDATION_LABELS, *QUEUE_KEYS, "total")},
            )
            bucket["total"] += 1
            bucket[card["recommendation_label"]] += 1
            if card.get("priority"):
                bucket[card["priority"]] += 1
    return {key: value for key, value in coverage.items() if value["total"] > 0}


def _company_coverage(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "company": "",
            "total": 0,
            "强推荐": 0,
            "推荐": 0,
            "观察": 0,
            "不推荐": 0,
            "P0": 0,
            "P1": 0,
            "P2": 0,
        }
    )
    for card in cards:
        company = card.get("company") or "未知公司"
        bucket = coverage[company]
        bucket["company"] = company
        bucket["total"] += 1
        bucket[card["recommendation_label"]] += 1
        if card.get("priority"):
            bucket[card["priority"]] += 1
    return sorted(
        coverage.values(),
        key=lambda item: (
            -item["P0"],
            -item["强推荐"],
            -item["P1"],
            -item["total"],
            item["company"],
        ),
    )


def _misclassification_analysis(cards: list[dict[str, Any]]) -> dict[str, Any]:
    overruled = [
        card
        for card in cards
        if card["recommendation_label"] == "不推荐"
        and str(card.get("source_grade") or "") in {"A", "B"}
    ]
    risk_counter = Counter()
    for card in cards:
        risk_counter.update(card.get("risk_flags") or [])
    return {
        "detail_overruled_count": len(overruled),
        "risk_flag_distribution": dict(risk_counter),
        "examples": overruled[:20],
    }


def _gap_analysis(
    cards: list[dict[str, Any]],
    direction_coverage: dict[str, dict[str, int]],
    final_recommended_count: int,
    misclassification: dict[str, Any],
) -> dict[str, Any]:
    actionable_count = sum(1 for card in cards if card["recommendation_label"] != "不推荐")
    low_threshold = max(5, int(max(actionable_count, 1) * 0.05))
    low_directions = [
        direction
        for direction, bucket in direction_coverage.items()
        if bucket["total"] < low_threshold
    ]
    suggestions: list[str] = []
    if final_recommended_count >= 500:
        suggestions.append(
            "本轮强推荐/推荐已达到 500+，先停止扩池，优先消化 P0/P1 外联队列。"
        )
    elif final_recommended_count < 200:
        suggestions.append(
            "最终强推荐/推荐低于 200，需要回看详情补全覆盖和搜索方向缺口后再扩池。"
        )
    else:
        suggestions.append("最终推荐规模落在设计目标区间，下一轮只围绕明确缺口补抓。")

    if low_directions:
        suggestions.append(
            "如业务需要补齐方向，下一轮优先定向补 "
            + "、".join(low_directions)
            + "，避免重复抓取已高覆盖方向。"
        )
    if misclassification["detail_overruled_count"]:
        top_risks = list(misclassification["risk_flag_distribution"].keys())[:3]
        suggestions.append(
            "把详情推翻样本中的硬风险前置到列表评分："
            + "、".join(top_risks)
            + "。"
        )
    return {
        "actionable_count": actionable_count,
        "low_coverage_threshold": low_threshold,
        "low_coverage_directions": low_directions,
        "next_round_suggestions": suggestions,
    }


def _queue_counts(queues: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {key: len(queues.get(key, [])) for key in QUEUE_KEYS}


def _md_cell(value: Any, limit: int = 120) -> str:
    text = _shorten(_text_join([value]), limit)
    return text.replace("|", "/")


def _write_search_report_md(path: str | Path, report: dict[str, Any]) -> None:
    funnel = report["funnel"]
    lines = [
        "# AI Infra V2 A/B 最终寻访报告",
        "",
        "## 执行摘要",
        "",
        f"- 详情目标：{funnel['target_count']} 人；详情完成：{funnel['detail_completed']} 人；缺失：{funnel['detail_missing']} 人。",
        f"- 强推荐/推荐/观察/不推荐：{funnel['strong_recommended_count']}/{funnel['recommended_count']}/{funnel['observe_count']}/{funnel['not_recommended_count']}。",
        f"- 外联队列：P0 {report['outreach_queue_counts']['P0']}，P1 {report['outreach_queue_counts']['P1']}，P2 {report['outreach_queue_counts']['P2']}。",
        "",
        "## Funnel",
        "",
        "| 指标 | 数值 |",
        "|---|---:|",
        f"| 原始人工审核输入 | {funnel['raw_input_rows']} |",
        f"| A/B 详情目标 | {funnel['target_count']} |",
        f"| 详情补全成功 | {funnel['detail_completed']} |",
        f"| 详情缺失 | {funnel['detail_missing']} |",
        f"| 最终强推荐+推荐 | {funnel['final_recommended_count']} |",
        f"| 外联可用队列 | {funnel['actionable_queue_count']} |",
        "",
        "## 方向覆盖",
        "",
        "| 方向 | 总数 | 强推荐 | 推荐 | 观察 | P0 | P1 | P2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for direction, bucket in sorted(
        report["direction_coverage"].items(),
        key=lambda pair: (-pair[1]["P0"], -pair[1]["total"], pair[0]),
    ):
        lines.append(
            f"| {direction} | {bucket['total']} | {bucket['强推荐']} | {bucket['推荐']} | "
            f"{bucket['观察']} | {bucket['P0']} | {bucket['P1']} | {bucket['P2']} |"
        )

    lines.extend([
        "",
        "## 公司覆盖 Top 30",
        "",
        "| 公司 | 总数 | 强推荐 | 推荐 | 观察 | 不推荐 | P0 | P1 | P2 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for item in report["company_coverage"][:30]:
        lines.append(
            f"| {_md_cell(item['company'], 60)} | {item['total']} | {item['强推荐']} | "
            f"{item['推荐']} | {item['观察']} | {item['不推荐']} | {item['P0']} | {item['P1']} | {item['P2']} |"
        )

    lines.extend(["", "## P0 候选人卡片 Top 30", ""])
    for card in report["candidate_cards"]:
        if card.get("priority") != "P0":
            continue
        lines.extend([
            f"### #{card['candidate_id']} {card['name']}",
            "",
            f"- 当前：{card['company']} / {card['title']}",
            f"- 平台 ID：{card['platform_id']}；评分：{card['score']}；推荐级别：{card['recommendation_label']}",
            f"- 方向：{'、'.join(card['directions'])}",
            f"- 关键证据：{_md_cell(card['key_evidence'], 240)}",
            f"- 风险：{card['risk_summary']}",
            f"- 建议切入：{card['suggested_outreach_angle']}",
            "",
        ])
        if sum(1 for item in report["candidate_cards"] if item.get("priority") == "P0" and item["rank"] <= card["rank"]) >= 30:
            break

    lines.extend([
        "## 详情推翻与缺口",
        "",
        f"- 详情推翻列表 A/B 判断：{report['misclassification_analysis']['detail_overruled_count']} 人。",
        f"- 低覆盖方向阈值：{report['gap_analysis']['low_coverage_threshold']}；低覆盖方向：{', '.join(report['gap_analysis']['low_coverage_directions']) or '无'}。",
        "",
        "## 下一轮建议",
        "",
    ])
    for suggestion in report["gap_analysis"]["next_round_suggestions"]:
        lines.append(f"- {suggestion}")

    lines.extend(["", "## Source Files", ""])
    for source in report["source_files"]:
        lines.append(f"- {source}")
    lines.extend(["", report["main_db_note"], ""])
    _write_text(path, "\n".join(lines))


def _write_outreach_md(path: str | Path, outreach: dict[str, Any]) -> None:
    lines = [
        "# AI Infra V2 A/B 外联优先级队列",
        "",
        f"- P0：{outreach['queue_counts']['P0']} 人",
        f"- P1：{outreach['queue_counts']['P1']} 人",
        f"- P2：{outreach['queue_counts']['P2']} 人",
        f"- 不进入外联：{len(outreach['excluded'])} 人",
        "",
    ]
    for priority in QUEUE_KEYS:
        lines.extend([
            f"## {priority}",
            "",
            "| 排名 | ID | 姓名 | 公司 | 职位 | 分数 | 方向 | 关键证据 | 建议切入 |",
            "|---:|---:|---|---|---|---:|---|---|---|",
        ])
        for card in outreach["priority_queues"][priority]:
            lines.append(
                f"| {card['rank']} | {card['candidate_id']} | {_md_cell(card['name'], 40)} | "
                f"{_md_cell(card['company'], 60)} | {_md_cell(card['title'], 70)} | "
                f"{card['score']} | {_md_cell(card['directions'], 80)} | "
                f"{_md_cell(card['key_evidence'], 140)} | {_md_cell(card['suggested_outreach_angle'], 140)} |"
            )
        lines.append("")

    if outreach["excluded"]:
        lines.extend([
            "## 不进入外联",
            "",
            "| 排名 | ID | 姓名 | 公司 | 分数 | 风险 |",
            "|---:|---:|---|---|---:|---|",
        ])
        for card in outreach["excluded"]:
            lines.append(
                f"| {card['rank']} | {card['candidate_id']} | {_md_cell(card['name'], 40)} | "
                f"{_md_cell(card['company'], 60)} | {card['score']} | {_md_cell(card['risk_summary'], 120)} |"
            )
    lines.append("")
    _write_text(path, "\n".join(lines))


def build_delivery_reports(
    campaign_root: str | Path,
    db_path: str | Path,
    targets_path: str | Path,
    rank_json_path: str | Path,
    out_report_json: str | Path | None = None,
    out_report_md: str | Path | None = None,
    out_outreach_json: str | Path | None = None,
    out_outreach_md: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    targets_file = Path(targets_path)
    rank_file = Path(rank_json_path)
    targets = _load_json(targets_file)
    rank_data = _load_json(rank_file)
    detail_report = build_detail_report(root, targets_file, rank_file)
    target_by_candidate = _target_contact_map(targets)
    metadata = targets.get("metadata") if isinstance(targets.get("metadata"), dict) else {}
    ranked = _ranked_items(rank_data)

    store = ReadOnlyCampaignStore(db_path)
    try:
        cards = [
            _candidate_card(
                rank_index=index,
                item=item,
                target=target_by_candidate.get(_as_int(item.get("candidate_id")), {}),
                store=store,
            )
            for index, item in enumerate(ranked, start=1)
        ]
    finally:
        store.close()

    queues = _assign_priorities(cards)
    excluded = [card for card in cards if card["recommendation_label"] == "不推荐"]
    recommendation_distribution = _distribution(
        [card["recommendation_label"] for card in cards],
        RECOMMENDATION_LABELS,
    )
    direction_coverage = _direction_coverage(cards)
    company_coverage = _company_coverage(cards)
    final_recommended_count = (
        recommendation_distribution["强推荐"] + recommendation_distribution["推荐"]
    )
    misclassification = _misclassification_analysis(cards)
    gap_analysis = _gap_analysis(
        cards=cards,
        direction_coverage=direction_coverage,
        final_recommended_count=final_recommended_count,
        misclassification=misclassification,
    )
    queue_counts = _queue_counts(queues)
    source_files = [
        str(targets_file),
        str(rank_file),
        *detail_report.get("source_files", []),
    ]
    source_files = list(dict.fromkeys(source_files))
    generated_at = datetime.now().isoformat(timespec="seconds")

    search_report = {
        "metadata": {
            "export_type": "maimai_ai_infra_final_search_report",
            "campaign_root": str(root),
            "db_path": str(db_path),
            "generated_at": generated_at,
        },
        "funnel": {
            "raw_input_rows": _as_int(metadata.get("input_rows")),
            "target_count": detail_report["coverage"]["target_count"],
            "detail_completed": detail_report["coverage"]["completed_detail_count"],
            "detail_missing": detail_report["coverage"]["missing_detail_count"],
            "ranked_count": len(cards),
            "list_grade_distribution": _distribution(
                [contact.get("grade") for contact in _target_contacts(targets)],
                GRADE_KEYS,
            ),
            "detail_grade_distribution": detail_report["grade_distribution"],
            "strong_recommended_count": recommendation_distribution["强推荐"],
            "recommended_count": recommendation_distribution["推荐"],
            "observe_count": recommendation_distribution["观察"],
            "not_recommended_count": recommendation_distribution["不推荐"],
            "final_recommended_count": final_recommended_count,
            "actionable_queue_count": sum(queue_counts.values()),
        },
        "recommendation_distribution": recommendation_distribution,
        "outreach_queue_counts": queue_counts,
        "pack_statuses": detail_report["pack_statuses"],
        "direction_coverage": direction_coverage,
        "company_coverage": company_coverage,
        "misclassification_analysis": misclassification,
        "gap_analysis": gap_analysis,
        "candidate_cards": cards,
        "source_files": source_files,
        "main_db_note": "本报告只读 campaign DB 与报告产物；未读取或写入 data/talent.db。",
    }
    outreach_priority = {
        "metadata": {
            "export_type": "maimai_ai_infra_outreach_priority",
            "campaign_root": str(root),
            "generated_at": generated_at,
            "priority_rule": "P0=排名前 150 的强推荐；P1=后续 300 名强推荐/推荐；P2=其余可深审或备选候选。",
        },
        "queue_counts": queue_counts,
        "priority_queues": queues,
        "excluded": excluded,
        "source_files": source_files,
        "main_db_note": "外联队列只读 campaign DB；未读取或写入 data/talent.db。",
    }

    if out_report_json is not None:
        _write_json(out_report_json, search_report)
    if out_report_md is not None:
        _write_search_report_md(out_report_md, search_report)
    if out_outreach_json is not None:
        _write_json(out_outreach_json, outreach_priority)
    if out_outreach_md is not None:
        _write_outreach_md(out_outreach_md, outreach_priority)

    return {
        "search_report": search_report,
        "outreach_priority": outreach_priority,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 AI Infra V2 A/B 交付版寻访报告")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--db-path")
    parser.add_argument("--targets", required=True)
    parser.add_argument("--rank-json", required=True)
    parser.add_argument("--out-report-json", required=True)
    parser.add_argument("--out-report-md", required=True)
    parser.add_argument("--out-outreach-json", required=True)
    parser.add_argument("--out-outreach-md", required=True)
    args = parser.parse_args(argv)

    campaign_root = Path(args.campaign_root)
    result = build_delivery_reports(
        campaign_root=campaign_root,
        db_path=Path(args.db_path) if args.db_path else campaign_root / "talent.db",
        targets_path=args.targets,
        rank_json_path=args.rank_json,
        out_report_json=args.out_report_json,
        out_report_md=args.out_report_md,
        out_outreach_json=args.out_outreach_json,
        out_outreach_md=args.out_outreach_md,
    )
    funnel = result["search_report"]["funnel"]
    queues = result["outreach_priority"]["queue_counts"]
    print(
        "status=ready targets={targets} detail_completed={completed} "
        "strong={strong} recommended={recommended} observe={observe} "
        "not_recommended={not_recommended} p0={p0} p1={p1} p2={p2}".format(
            targets=funnel["target_count"],
            completed=funnel["detail_completed"],
            strong=funnel["strong_recommended_count"],
            recommended=funnel["recommended_count"],
            observe=funnel["observe_count"],
            not_recommended=funnel["not_recommended_count"],
            p0=queues["P0"],
            p1=queues["P1"],
            p2=queues["P2"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
