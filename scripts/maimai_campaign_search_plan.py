from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.maimai_company_registry import expand_company_pool_terms


DEFAULT_QUERY_FILTERS = {
    "allcompanies": "",
    "positions": "",
    "cities": "",
    "provinces": "",
    "ht_cities": "",
    "ht_provinces": "",
    "region_scope": "0,1",
    "query_relation": 0,
}


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("strategy JSON must be an object")
    return data


def _write_json(path: str | Path, payload: dict[str, Any]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8-sig",
    )


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
    for value in pools.values():
        if isinstance(value, list):
            for item in value:
                text = str(item).strip()
                if text and text not in terms:
                    terms.append(text)
    if not terms:
        raise ValueError("strategy.company_pools must include at least one company term")
    return terms


def _query_terms(raw_company_term: str, package: dict[str, Any]) -> list[str]:
    keywords = [str(item).strip() for item in package.get("keywords") or [] if str(item).strip()]
    return [raw_company_term, *keywords[:4]]


def build_generic_search_units(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    packages = _keyword_packages(strategy)
    company_terms = _company_pool_terms(strategy)
    expanded = expand_company_pool_terms(company_terms)

    units: list[dict[str, Any]] = []
    for company_index, company in enumerate(expanded, start=1):
        package = packages[min(company_index - 1, len(packages) - 1)]
        query = " ".join(_query_terms(company["raw_term"], package))
        units.append({
            "unit_id": f"unit-{len(units) + 1:06d}",
            "source_company_term": company["raw_term"],
            "canonical_company": company["canonical_company"],
            "company_aliases": company["company_aliases"],
            "org_product_terms": company["org_product_terms"],
            "preferred_search_mode": company["preferred_search_mode"],
            "priority": package.get("priority") or "P1",
            "keyword_package": package.get("id") or "",
            "position_terms": package.get("position_terms") or [],
            "keywords": package.get("keywords") or [],
            "query": query,
            "query_relation": 0,
            "page_size": 30,
            "max_pages": 5 if str(package.get("priority") or "") == "P0" else 3,
            "search_filters": dict(DEFAULT_QUERY_FILTERS),
        })
    return units


def build_generic_search_plan(strategy: dict[str, Any]) -> dict[str, Any]:
    units = build_generic_search_units(strategy)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "strategy_version": strategy.get("strategy_version") or "",
        "compiler": "maimai_campaign_search_plan",
        "batches": units,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成通用 JD-driven 脉脉搜索批次计划")
    parser.add_argument("--config", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--out-units")
    args = parser.parse_args(argv)

    strategy = _load_json(args.config)
    plan = build_generic_search_plan(strategy)
    _write_json(args.out, plan)
    if args.out_units:
        _write_jsonl(args.out_units, plan["batches"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
