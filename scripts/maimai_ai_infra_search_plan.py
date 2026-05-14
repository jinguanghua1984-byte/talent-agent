"""生成脉脉 AI Infra 搜索批次计划。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL_KEYS = {
    "strategy_version",
    "human_gates",
    "limits",
    "company_tiers",
    "company_aliases",
    "title_batches",
    "keyword_packs",
    "exclude_titles",
    "exclude_education",
}

CONFIRMED_FILTER_FIELDS = [
    "search.allcompanies",
    "search.degrees",
    "search.degrees_min",
    "search.degrees_max",
    "search.only_bachelor_degree",
    "search.min_only_bachelor_degree",
    "search.max_only_bachelor_degree",
    "search.positions",
    "search.worktimes",
    "search.worktimes_min",
    "search.worktimes_max",
    "search.min_age",
    "search.max_age",
    "search.schools",
    "search.major",
]

V2_ALLOWED_FILTERS = {
    "allcompanies",
    "degrees",
    "degrees_min",
    "degrees_max",
    "only_bachelor_degree",
    "min_only_bachelor_degree",
    "max_only_bachelor_degree",
    "positions",
    "worktimes",
    "worktimes_min",
    "worktimes_max",
    "min_age",
    "max_age",
    "schools",
    "major",
    "query_relation",
}


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("strategy config must be a JSON object")
    return data


def load_strategy(path: str | Path) -> dict[str, Any]:
    strategy = _load_json(Path(path))
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(strategy))
    if missing:
        raise ValueError("strategy config missing keys: " + ", ".join(missing))

    limits = strategy["limits"]
    for key in ("pages_per_batch", "page_size", "max_contacts_per_batch", "max_batches_per_day"):
        if not isinstance(limits.get(key), int) or limits[key] <= 0:
            raise ValueError(f"limits.{key} must be a positive integer")

    if limits["pages_per_batch"] * limits["page_size"] > limits["max_contacts_per_batch"]:
        raise ValueError("pages_per_batch * page_size must not exceed max_contacts_per_batch")

    return strategy


def _slug(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    if text:
        return text
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def _quote_terms(terms: list[str]) -> str:
    unique: list[str] = []
    seen: set[str] = set()
    for term in terms:
        normalized = str(term).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return " ".join(f'"{term}"' for term in unique)


def _company_terms(strategy: dict[str, Any], company: str) -> list[str]:
    aliases = strategy.get("company_aliases", {}).get(company, [])
    return [company, *aliases[:3]]


def _make_batch(
    strategy: dict[str, Any],
    tier: str,
    company: str,
    title_group: str,
    position: str,
    keyword_pack: str,
    priority: int,
    index: int,
) -> dict[str, Any]:
    keywords = strategy["keyword_packs"][keyword_pack]
    query_terms = [*_company_terms(strategy, company), position, *keywords[:4]]
    query = _quote_terms(query_terms)
    limits = strategy["limits"]
    batch_id = f"{tier}-{_slug(company)}-{title_group}-{index:03d}"
    return {
        "batch_id": batch_id,
        "tier": tier,
        "company": company,
        "title_group": title_group,
        "position": position,
        "keyword_pack": keyword_pack,
        "query": query,
        "query_relation": 0,
        "max_pages": limits["pages_per_batch"],
        "page_size": limits["page_size"],
        "priority": priority,
        "search_body_patch": {
            "verified_fields": [
                "search.query",
                "search.search_query",
                "search.paginationParam",
                "search.page",
                "search.size",
                "search.query_relation",
            ],
            "confirmed_filter_fields": CONFIRMED_FILTER_FIELDS,
            "local_filter_only": ["company", "position", "education", "worktime"],
        },
    }


def _v2_filters(
    strategy: dict[str, Any],
    company: str,
    position: str,
    query_relation: int,
) -> dict[str, Any]:
    filters = dict(strategy["v2"].get("default_filters", {}))
    filters.update({
        "allcompanies": company,
        "positions": position,
        "query_relation": query_relation,
    })
    unconfirmed = sorted(set(filters) - V2_ALLOWED_FILTERS)
    if unconfirmed:
        raise ValueError("unconfirmed V2 search filter fields: " + ", ".join(unconfirmed))
    return filters


def _unit(
    strategy: dict[str, Any],
    batch_type: str,
    tier: str,
    company: str,
    position: str,
    keyword_pack: str,
    query_relation: int,
    unit_index: int,
) -> dict[str, Any]:
    limits = strategy["limits"]
    wave_size = strategy.get("v2", {}).get("wave_size_units", 40) or 40
    keywords = strategy["keyword_packs"][keyword_pack]
    query = _quote_terms([*_company_terms(strategy, company), position, *keywords[:4]])
    return {
        "unit_id": f"unit-{unit_index:06d}",
        "wave_id": f"wave-{((unit_index - 1) // wave_size) + 1:03d}",
        "batch_type": batch_type,
        "tier": tier,
        "company": company,
        "position": position,
        "keyword_pack": keyword_pack,
        "search_filters": _v2_filters(strategy, company, position, query_relation),
        "query": query,
        "max_pages": min(limits["pages_per_batch"], 3),
        "page_size": limits["page_size"],
    }


def build_search_units(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    unit_index = 1
    quotas = strategy["v2"]["unit_quotas"]
    titles = strategy["title_batches"]
    companies = strategy["company_tiers"]

    def add(
        batch_type: str,
        tier: str,
        company_names: list[str],
        positions: list[str],
        packs: list[str],
        query_relation: int,
    ) -> None:
        nonlocal unit_index
        quota = quotas.get(batch_type, 0)
        start_count = len(units)
        for company in company_names:
            for position in positions:
                for pack in packs:
                    if len(units) - start_count >= quota:
                        return
                    units.append(_unit(
                        strategy,
                        batch_type,
                        tier,
                        company,
                        position,
                        pack,
                        query_relation,
                        unit_index,
                    ))
                    unit_index += 1

    add(
        "P1_core_precision",
        "tier1",
        companies.get("tier1", []),
        titles["precision"],
        ["training", "inference"],
        1,
    )
    add(
        "P2_technical",
        "tier2_priority",
        companies.get("tier2_priority", []),
        titles["technical"],
        ["inference", "training"],
        1,
    )
    add(
        "P3_generic_with_strong_query",
        "tier1",
        companies.get("tier1", []),
        titles["generic"],
        ["inference"],
        0,
    )
    return units


def generate_batches(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    batches: list[dict[str, Any]] = []
    max_batches = strategy["limits"]["max_batches_per_day"]
    index = 1

    def add(
        tier: str,
        companies: list[str],
        title_group: str,
        positions: list[str],
        packs: list[str],
        base_priority: int,
        quota: int,
    ) -> None:
        nonlocal index
        start_count = len(batches)
        for company in companies:
            for position in positions:
                for pack in packs:
                    if len(batches) - start_count >= quota:
                        return
                    batches.append(_make_batch(
                        strategy,
                        tier,
                        company,
                        title_group,
                        position,
                        pack,
                        base_priority - len(batches),
                        index,
                    ))
                    index += 1
                    if len(batches) >= max_batches:
                        return

    titles = strategy["title_batches"]
    companies = strategy["company_tiers"]
    add("tier1", companies.get("tier1", []), "precision", titles["precision"], ["framework", "training", "inference"], 100, 30)
    if len(batches) < max_batches:
        add("tier2_priority", companies.get("tier2_priority", []), "precision", titles["precision"], ["framework", "inference", "cluster"], 80, 20)
    if len(batches) < max_batches:
        add("tier1", companies.get("tier1", []), "technical", titles["technical"], ["training", "inference", "opensource"], 70, 12)
    if len(batches) < max_batches:
        add("tier2_priority", companies.get("tier2_priority", []), "technical", titles["technical"], ["inference", "cluster", "opensource"], 60, 8)
    if len(batches) < max_batches:
        add("tier1", companies.get("tier1", []), "generic", titles["generic"], ["inference", "cluster", "opensource"], 50, 6)
    if len(batches) < max_batches:
        add("tier3", companies.get("tier3", []), "technical", titles["technical"], ["inference", "cluster"], 40, max_batches - len(batches))

    return sorted(batches[:max_batches], key=lambda item: (-item["priority"], item["batch_id"]))


def build_plan(strategy: dict[str, Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_version": strategy["strategy_version"],
        "human_gates": strategy["human_gates"],
        "limits": strategy["limits"],
        "batches": generate_batches(strategy),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成脉脉 AI Infra 搜索批次计划")
    parser.add_argument("--config", default="configs/maimai-ai-infra-search-strategy.json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--out-units")
    args = parser.parse_args(argv)

    strategy = load_strategy(args.config)
    plan = build_plan(strategy)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    if args.out_units:
        units = build_search_units(strategy)
        units_path = Path(args.out_units)
        units_path.parent.mkdir(parents=True, exist_ok=True)
        units_path.write_text(
            "\n".join(json.dumps(unit, ensure_ascii=False, sort_keys=True) for unit in units) + "\n",
            encoding="utf-8-sig",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
