from __future__ import annotations

import argparse
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.maimai_company_registry import expand_company_pool_terms
from scripts.talent_db import TalentDB
from scripts.talent_models import CandidateFilter, SortSpec


STRATEGY_MODE = "broad_recall_adaptive_v1"

DEFAULT_ADAPTIVE_POLICY: dict[str, Any] = {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "good_ratio_continue": 0.3,
    "good_ratio_observe": 0.1,
    "max_consecutive_low_quality_pages": 2,
    "stop_on_high_duplicate_ratio": True,
}

BROAD_RECALL_QUERY_FILTERS: dict[str, Any] = {
    "allcompanies": "",
    "positions": "",
    "cities": "",
    "provinces": "",
    "ht_cities": "",
    "ht_provinces": "",
    "region_scope": "0,1",
    "query_relation": 0,
}


def _unique_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def is_broad_recall_strategy(strategy: dict[str, Any]) -> bool:
    return str(strategy.get("strategy_mode") or "").strip() == STRATEGY_MODE


def adaptive_policy_from_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    raw_policy = strategy.get("adaptive_search") if isinstance(strategy.get("adaptive_search"), dict) else {}
    policy = dict(DEFAULT_ADAPTIVE_POLICY)
    for key in DEFAULT_ADAPTIVE_POLICY:
        if key in raw_policy:
            policy[key] = raw_policy[key]
    policy["probe_pages"] = max(1, int(policy["probe_pages"]))
    policy["unit_max_pages"] = max(policy["probe_pages"], int(policy["unit_max_pages"]))
    policy["max_consecutive_low_quality_pages"] = max(
        1,
        int(policy["max_consecutive_low_quality_pages"]),
    )
    policy["good_ratio_continue"] = float(policy["good_ratio_continue"])
    policy["good_ratio_observe"] = float(policy["good_ratio_observe"])
    return policy


def _keyword_packages(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    packages = strategy.get("keyword_packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("strategy.keyword_packages must be a non-empty list")
    return [package for package in packages if isinstance(package, dict)]


def _company_pool_terms(strategy: dict[str, Any]) -> list[str]:
    pools = strategy.get("company_pools")
    if not isinstance(pools, dict):
        raise ValueError("strategy.company_pools must be an object")
    terms: list[str] = []
    for values in pools.values():
        if isinstance(values, list):
            terms.extend(values)
    terms = _unique_text(terms)
    if not terms:
        raise ValueError("strategy.company_pools must include at least one company term")
    return terms


def _wide_query_terms(company_term: str, package: dict[str, Any]) -> list[str]:
    explicit = package.get("query_terms")
    if isinstance(explicit, list) and explicit:
        terms = _unique_text(explicit)
    else:
        position_terms = _unique_text(package.get("position_terms") or [])[:2]
        keywords = _unique_text(package.get("keywords") or [])[:2]
        terms = [*position_terms, *keywords]
    return _unique_text([company_term, *terms])


def build_broad_recall_search_units(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    policy = adaptive_policy_from_strategy(strategy)
    packages = _keyword_packages(strategy)
    expanded_companies = expand_company_pool_terms(_company_pool_terms(strategy))
    unit_order = str(strategy.get("unit_order") or "keyword_first").strip()

    units: list[dict[str, Any]] = []
    if unit_order == "company_first":
        pairs = [(package, company) for company in expanded_companies for package in packages]
    else:
        pairs = [(package, company) for package in packages for company in expanded_companies]

    for package, company in pairs:
        raw_company = str(company.get("raw_term") or "").strip()
        query_terms = _wide_query_terms(raw_company, package)
        units.append(
            {
                "unit_id": f"unit-{len(units) + 1:06d}",
                "strategy_mode": STRATEGY_MODE,
                "source_company_terms": [raw_company],
                "canonical_company": company.get("canonical_company") or raw_company,
                "company_aliases": company.get("company_aliases") or [],
                "org_product_terms": company.get("org_product_terms") or [],
                "preferred_search_mode": company.get("preferred_search_mode") or "",
                "priority": package.get("priority") or "P1",
                "keyword_package": package.get("id") or "",
                "position_terms": _unique_text(package.get("position_terms") or []),
                "broad_keywords": _unique_text(package.get("keywords") or []),
                "long_tail_keywords": _unique_text(package.get("long_tail_keywords") or []),
                "query": " ".join(query_terms),
                "query_relation": 0,
                "page_size": 30,
                "max_pages": policy["probe_pages"],
                "unit_max_pages": policy["unit_max_pages"],
                "adaptive_search": deepcopy(policy),
                "search_filters": dict(BROAD_RECALL_QUERY_FILTERS),
            }
        )
    return units


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
            parts.append(str(value))
    return " ".join(part for part in parts if part)


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    return term.casefold() in text.casefold() if term.isascii() else term in text


def _strategy_terms(strategy: dict[str, Any]) -> dict[str, list[str]]:
    packages = strategy.get("keyword_packages") if isinstance(strategy.get("keyword_packages"), list) else []
    position_terms = _unique_text(strategy.get("position_aliases") or [])
    keyword_terms: list[str] = []
    for package in packages:
        if not isinstance(package, dict):
            continue
        position_terms.extend(_unique_text(package.get("position_terms") or []))
        keyword_terms.extend(_unique_text(package.get("keywords") or []))
        keyword_terms.extend(_unique_text(package.get("long_tail_keywords") or []))

    company_terms: list[str] = []
    pools = strategy.get("company_pools") if isinstance(strategy.get("company_pools"), dict) else {}
    for values in pools.values():
        if isinstance(values, list):
            company_terms.extend(values)
    for item in expand_company_pool_terms(_unique_text(company_terms)):
        company_terms.extend(
            [
                item.get("raw_term") or "",
                item.get("canonical_company") or "",
                *item.get("company_aliases", []),
                *item.get("org_product_terms", []),
            ]
        )

    return {
        "companies": _unique_text(company_terms),
        "positions": _unique_text(position_terms),
        "keywords": _unique_text(keyword_terms),
    }


def extract_page_contacts(page: dict[str, Any]) -> list[dict[str, Any]]:
    contacts = page.get("contacts")
    if isinstance(contacts, list):
        return [item for item in contacts if isinstance(item, dict)]
    data = page.get("responseData")
    if isinstance(data, dict):
        container = data.get("data") if isinstance(data.get("data"), dict) else data
        for key in ("contacts", "list", "items", "results"):
            values = container.get(key) if isinstance(container, dict) else None
            if isinstance(values, list):
                return [item for item in values if isinstance(item, dict)]
    return []


def candidate_key(contact: dict[str, Any]) -> str:
    for key in ("candidate_id", "platform_id", "id", "uid", "dstu"):
        value = contact.get(key)
        if value not in (None, ""):
            return str(value)
    for key in ("profile_url", "detail_url", "url"):
        value = contact.get(key)
        if value not in (None, ""):
            return str(value)
    return _text_join([contact.get("name"), contact.get("company"), contact.get("position")])


def score_contact_for_detail_priority(
    contact: dict[str, Any],
    strategy: dict[str, Any],
    seen_candidate_keys: set[str] | None = None,
) -> dict[str, Any]:
    seen = seen_candidate_keys or set()
    key = candidate_key(contact)
    terms = _strategy_terms(strategy)
    company_text = _text_join(
        [
            contact.get("company"),
            contact.get("current_company"),
            contact.get("corp"),
            contact.get("org"),
        ]
    )
    title_text = _text_join(
        [
            contact.get("position"),
            contact.get("title"),
            contact.get("current_title"),
            contact.get("career"),
        ]
    )
    all_text = _text_join([contact, company_text, title_text])
    company_hits = [term for term in terms["companies"] if _contains(company_text, term) or _contains(all_text, term)]
    title_hits = [term for term in terms["positions"] if _contains(title_text, term)]
    keyword_hits = [term for term in terms["keywords"] if _contains(all_text, term)]
    has_detail_url = any(contact.get(key) for key in ("detail_url", "profile_url", "url"))
    duplicate = bool(key and key in seen)

    score = 0
    score += 35 if company_hits else 0
    score += 30 if title_hits else 0
    score += min(25, len(keyword_hits) * 8)
    score += 10 if has_detail_url else 0
    if duplicate:
        score -= 20

    if score >= 70:
        label = "detail_p0"
    elif score >= 45:
        label = "detail_p1"
    elif score >= 25:
        label = "detail_p2"
    else:
        label = "skip"

    return {
        "candidate_key": key,
        "score": max(0, min(100, score)),
        "detail_priority": label,
        "detail_eligible": label in {"detail_p0", "detail_p1"},
        "duplicate": duplicate,
        "signals": {
            "company_hits": company_hits,
            "title_hits": title_hits,
            "keyword_hits": keyword_hits,
            "has_detail_url": has_detail_url,
        },
    }


def score_page_quality(
    page: dict[str, Any],
    strategy: dict[str, Any],
    seen_candidate_keys: set[str] | None = None,
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    active_policy = policy or adaptive_policy_from_strategy(strategy)
    contacts = extract_page_contacts(page)
    scores = [
        score_contact_for_detail_priority(contact, strategy, seen_candidate_keys)
        for contact in contacts
    ]
    candidate_count = len(contacts)
    duplicate_count = sum(1 for item in scores if item["duplicate"])
    detail_eligible_count = sum(1 for item in scores if item["detail_eligible"])
    new_candidate_count = candidate_count - duplicate_count
    page_good_ratio = detail_eligible_count / candidate_count if candidate_count else 0.0
    duplicate_ratio = duplicate_count / candidate_count if candidate_count else 0.0

    if page_good_ratio >= float(active_policy["good_ratio_continue"]):
        quality_band = "good"
        decision = "continue"
    elif page_good_ratio >= float(active_policy["good_ratio_observe"]):
        quality_band = "observe"
        decision = "observe"
    else:
        quality_band = "low"
        decision = "observe"

    return {
        "unit_id": page.get("unit_id") or page.get("batch_id"),
        "page": page.get("page"),
        "next_page": int(page.get("page") or 0) + 1,
        "candidate_count": candidate_count,
        "new_candidate_count": new_candidate_count,
        "duplicate_count": duplicate_count,
        "duplicate_ratio": duplicate_ratio,
        "detail_eligible_count": detail_eligible_count,
        "page_good_ratio": page_good_ratio,
        "quality_band": quality_band,
        "decision": decision,
        "candidate_scores": scores,
    }


def next_unit_status(
    state: dict[str, Any],
    page_quality: dict[str, Any],
    policy: dict[str, Any],
) -> dict[str, Any]:
    updated = dict(state)
    quality_band = str(page_quality.get("quality_band") or "")
    if quality_band == "low":
        low_count = int(updated.get("consecutive_low_quality_pages") or 0) + 1
        updated["consecutive_low_quality_pages"] = low_count
        if low_count >= int(policy["max_consecutive_low_quality_pages"]):
            updated["status"] = "stopped_low_quality"
            updated["stop_reason"] = "consecutive_low_quality_pages"
        else:
            updated["status"] = "observing"
    elif quality_band == "observe":
        updated["consecutive_low_quality_pages"] = 0
        updated["status"] = "observing"
    else:
        updated["consecutive_low_quality_pages"] = 0
        updated["status"] = "active"
    if page_quality.get("next_page") is not None:
        updated["next_page"] = page_quality["next_page"]
    return updated


def _write_json(path: str | Path, payload: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in file.read_text(encoding="utf-8-sig").splitlines():
        normalized = line.lstrip("\ufeff")
        if normalized.strip():
            item = json.loads(normalized)
            if isinstance(item, dict):
                rows.append(item)
    return rows


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8-sig",
    )


def _candidate_contact(db: TalentDB, candidate_id: int) -> dict[str, Any] | None:
    candidate = db.get(candidate_id)
    if candidate is None:
        return None
    sources = [source for source in db.get_sources(candidate_id) if source.platform == "maimai"]
    source = sources[0] if sources else None
    return {
        "candidate_id": candidate.id,
        "id": source.platform_id if source else candidate.id,
        "platform_id": source.platform_id if source else "",
        "name": candidate.name,
        "company": candidate.current_company,
        "position": candidate.current_title,
        "title": candidate.current_title,
        "education": candidate.education,
        "work_years": candidate.work_years,
        "skill_tags": list(candidate.skill_tags),
        "profile_url": source.profile_url if source else "",
        "detail_url": source.profile_url if source else "",
    }


def _priority_to_grade(priority: str) -> str:
    return {
        "detail_p0": "A",
        "detail_p1": "B",
        "detail_p2": "C",
        "skip": "淘汰",
    }.get(priority, "淘汰")


def _write_detail_priority_md(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# 脉脉宽召回详情优先级",
        "",
        f"- 生成时间：{result['generated_at']}",
        f"- 候选人总数：{result['total_candidates']}",
        "- 用途：决定详情抓取优先级，不代表最终推荐结论。",
        "",
        "## 分布",
    ]
    for label in ("detail_p0", "detail_p1", "detail_p2", "skip"):
        lines.append(f"- {label}：{result['summary'].get(label, 0)}")
    lines.extend(["", "## Top 明细", ""])
    for item in result["items"][:50]:
        lines.append(
            f"- #{item['candidate_id']} {item['name']}｜{item['detail_priority']}｜"
            f"{item.get('company', '')}｜{item.get('title', '')}｜{item['score']}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_detail_priority_outputs(
    *,
    campaign_root: str | Path,
    db_path: str | Path,
    strategy: dict[str, Any],
    out_json: str | Path,
    out_md: str | Path,
    review_out: str | Path,
    wave_id: str = "search-wave-001",
    limit: int = 10000,
) -> dict[str, Any]:
    root = Path(campaign_root)
    db = TalentDB(db_path)
    try:
        page = db.search(
            CandidateFilter(platforms=["maimai"]),
            SortSpec(field="updated_at", direction="desc"),
            page=1,
            page_size=limit,
        )
        contacts = [
            contact
            for candidate in page.items
            if (contact := _candidate_contact(db, candidate.id)) is not None
        ]
    finally:
        db.close()

    items: list[dict[str, Any]] = []
    for contact in contacts:
        scored = score_contact_for_detail_priority(contact, strategy)
        items.append(
            {
                "candidate_id": contact["candidate_id"],
                "name": contact.get("name") or "",
                "company": contact.get("company") or "",
                "title": contact.get("title") or contact.get("position") or "",
                "score": scored["score"],
                "detail_priority": scored["detail_priority"],
                "grade": _priority_to_grade(scored["detail_priority"]),
                "wave_id": wave_id,
                "profile_url": contact.get("profile_url") or contact.get("detail_url") or "",
                "signals": scored["signals"],
            }
        )
    priority_order = {"detail_p0": 0, "detail_p1": 1, "detail_p2": 2, "skip": 3}
    items.sort(key=lambda item: (priority_order.get(item["detail_priority"], 99), -item["score"], item["candidate_id"]))
    summary = {label: 0 for label in ("detail_p0", "detail_p1", "detail_p2", "skip")}
    for item in items:
        summary[item["detail_priority"]] = summary.get(item["detail_priority"], 0) + 1
    result = {
        "schema": "maimai_broad_recall_detail_priority_v1",
        "strategy_mode": STRATEGY_MODE,
        "campaign_root": root.as_posix(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_candidates": len(items),
        "summary": summary,
        "items": items,
    }
    _write_json(out_json, result)
    _write_detail_priority_md(Path(out_md), result)
    _write_json(
        review_out,
        {
            "schema": "maimai_broad_recall_detail_priority_review_v1",
            "wave_id": wave_id,
            "items": [
                {
                    "candidate_id": item["candidate_id"],
                    "name": item["name"],
                    "grade": item["grade"],
                    "score": item["score"],
                    "wave_id": wave_id,
                    "profile_url": item["profile_url"],
                }
                for item in items
            ],
        },
    )
    return result


def _page_quality_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    bands = {"good": 0, "observe": 0, "low": 0}
    total_candidates = 0
    detail_eligible = 0
    for row in rows:
        band = str(row.get("quality_band") or "")
        if band in bands:
            bands[band] += 1
        total_candidates += int(row.get("candidate_count") or 0)
        detail_eligible += int(row.get("detail_eligible_count") or 0)
    return {
        "total_pages": len(rows),
        "quality_bands": bands,
        "total_candidates_seen": total_candidates,
        "detail_eligible_count": detail_eligible,
    }


def _write_broad_summary_md(path: Path, summary: dict[str, Any]) -> None:
    quality = summary["page_quality"]
    detail = summary.get("detail_priority", {})
    lines = [
        "# 脉脉宽召回寻访摘要",
        "",
        f"- Campaign：{summary['campaign_id']}",
        f"- 生成时间：{summary['generated_at']}",
        f"- 搜索页数：{quality['total_pages']}",
        f"- 列表候选人：{quality['total_candidates_seen']}",
        f"- 详情优先候选人：{quality['detail_eligible_count']}",
        "",
        "## 页质分布",
    ]
    for band, count in quality["quality_bands"].items():
        lines.append(f"- {band}：{count}")
    if detail:
        lines.extend(["", "## 详情优先级分布"])
        for label, count in detail.items():
            lines.append(f"- {label}：{count}")
    lines.extend(["", "## 下一步", "", "- 按人工边界将 Campaign DB 同步到主库后，再使用 JD talent delivery 做精准匹配。"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_broad_recall_summary(
    campaign_root: str | Path,
    *,
    out_json: str | Path,
    out_md: str | Path,
) -> dict[str, Any]:
    root = Path(campaign_root)
    page_rows = _read_jsonl(root / "reports" / "page-quality.jsonl")
    detail_path = root / "reports" / "detail-priority.json"
    detail_summary: dict[str, Any] = {}
    if detail_path.exists():
        detail = _load_json(detail_path)
        raw_summary = detail.get("summary")
        if isinstance(raw_summary, dict):
            detail_summary = {str(key): int(value or 0) for key, value in raw_summary.items()}
    summary = {
        "schema": "maimai_broad_recall_summary_v1",
        "strategy_mode": STRATEGY_MODE,
        "campaign_id": root.name,
        "campaign_root": root.as_posix(),
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "page_quality": _page_quality_summary(page_rows),
        "detail_priority": detail_summary,
        "main_db_sync_mode": "manual_only",
    }
    _write_json(out_json, summary)
    _write_broad_summary_md(Path(out_md), summary)
    return summary


def evaluate_page_quality_run(
    *,
    campaign_root: str | Path,
    run_path: str | Path,
    strategy: dict[str, Any],
    out_jsonl: str | Path,
    state_out: str | Path,
    seen_out: str | Path,
) -> list[dict[str, Any]]:
    policy = adaptive_policy_from_strategy(strategy)
    seen = {
        str(row.get("candidate_key"))
        for row in _read_jsonl(seen_out)
        if row.get("candidate_key") not in (None, "")
    }
    run = _load_json(run_path)
    qualities: list[dict[str, Any]] = []
    unit_state: dict[str, dict[str, Any]] = {}
    for batch in run.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        unit_id = str(batch.get("batch_id") or batch.get("unit_id") or "")
        state = unit_state.get(unit_id, {"unit_id": unit_id, "status": "active", "consecutive_low_quality_pages": 0})
        for page in batch.get("pages") or []:
            if not isinstance(page, dict):
                continue
            if page.get("ok") is False:
                continue
            page_record = dict(page)
            page_record["unit_id"] = unit_id
            quality = score_page_quality(page_record, strategy, seen_candidate_keys=seen, policy=policy)
            qualities.append(quality)
            state = next_unit_status(state, quality, policy)
            for item in quality["candidate_scores"]:
                if item.get("candidate_key"):
                    seen.add(str(item["candidate_key"]))
        unit_state[unit_id] = state
    _write_jsonl(out_jsonl, qualities)
    _write_json(state_out, {"schema": "maimai_broad_recall_unit_state_v1", "units": unit_state})
    _write_jsonl(seen_out, [{"candidate_key": key} for key in sorted(seen)])
    return qualities


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="脉脉宽召回自适应寻访实验模式工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    quality = subparsers.add_parser("evaluate-page-quality")
    quality.add_argument("--campaign-root", required=True)
    quality.add_argument("--run", required=True)
    quality.add_argument("--config", required=True)
    quality.add_argument("--out-jsonl", required=True)
    quality.add_argument("--state-out", required=True)
    quality.add_argument("--seen-out", required=True)

    priority = subparsers.add_parser("build-detail-priority")
    priority.add_argument("--campaign-root", required=True)
    priority.add_argument("--db", required=True)
    priority.add_argument("--config", required=True)
    priority.add_argument("--out-json", required=True)
    priority.add_argument("--out-md", required=True)
    priority.add_argument("--review-out", required=True)
    priority.add_argument("--wave-id", default="search-wave-001")

    summary = subparsers.add_parser("summary")
    summary.add_argument("--campaign-root", required=True)
    summary.add_argument("--out-json", required=True)
    summary.add_argument("--out-md", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "evaluate-page-quality":
        rows = evaluate_page_quality_run(
            campaign_root=args.campaign_root,
            run_path=args.run,
            strategy=_load_json(args.config),
            out_jsonl=args.out_jsonl,
            state_out=args.state_out,
            seen_out=args.seen_out,
        )
        print(json.dumps({"status": "ok", "pages": len(rows), "out": args.out_jsonl}, ensure_ascii=False))
        return 0
    if args.command == "build-detail-priority":
        result = build_detail_priority_outputs(
            campaign_root=args.campaign_root,
            db_path=args.db,
            strategy=_load_json(args.config),
            out_json=args.out_json,
            out_md=args.out_md,
            review_out=args.review_out,
            wave_id=args.wave_id,
        )
        print(json.dumps({"status": "ok", "total_candidates": result["total_candidates"]}, ensure_ascii=False))
        return 0
    if args.command == "summary":
        result = build_broad_recall_summary(args.campaign_root, out_json=args.out_json, out_md=args.out_md)
        print(json.dumps({"status": "ok", "pages": result["page_quality"]["total_pages"]}, ensure_ascii=False))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
