from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_PATH = PROJECT_ROOT / "rules" / "company-product-registry.json"


@dataclass(frozen=True)
class CompanyProductMapping:
    term: str
    canonical_company: str
    company_aliases: list[str]
    org_product_terms: list[str]
    preferred_search_mode: str
    confidence: str


def _norm(value: str) -> str:
    return re.sub(r"\s+", "", value).casefold()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("registry list field must be a list")
    return [str(item).strip() for item in value if str(item).strip()]


def load_company_product_registry(path: str | Path = DEFAULT_REGISTRY_PATH) -> dict[str, CompanyProductMapping]:
    registry_path = Path(path)
    if not registry_path.exists():
        return {}
    data = json.loads(registry_path.read_text(encoding="utf-8-sig"))
    entries = data.get("entries")
    if not isinstance(entries, list):
        raise ValueError("company product registry entries must be a list")

    registry: dict[str, CompanyProductMapping] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("company product registry entry must be an object")
        term = str(entry.get("term") or "").strip()
        if not term:
            raise ValueError("company product registry entry term is required")
        key = _norm(term)
        if key in registry:
            raise ValueError(f"duplicate company product term: {term}")
        registry[key] = CompanyProductMapping(
            term=term,
            canonical_company=str(entry.get("canonical_company") or "").strip(),
            company_aliases=_as_str_list(entry.get("company_aliases")),
            org_product_terms=_as_str_list(entry.get("org_product_terms")),
            preferred_search_mode=str(entry.get("preferred_search_mode") or "query_only").strip(),
            confidence=str(entry.get("confidence") or "unknown").strip(),
        )
    return registry


def resolve_company_product_term(
    term: str,
    registry: dict[str, CompanyProductMapping] | None = None,
) -> CompanyProductMapping | None:
    active_registry = registry if registry is not None else load_company_product_registry()
    return active_registry.get(_norm(term))


def expand_company_pool_terms(
    company_pool: list[str],
    registry: dict[str, CompanyProductMapping] | None = None,
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    active_registry = registry if registry is not None else load_company_product_registry()
    for raw_term in company_pool:
        term = str(raw_term).strip()
        if not term:
            continue
        mapping = resolve_company_product_term(term, active_registry)
        if mapping is None:
            expanded.append({
                "raw_term": term,
                "canonical_company": "",
                "company_aliases": [],
                "org_product_terms": [term],
                "preferred_search_mode": "query_only",
                "confidence": "unmapped",
            })
            continue
        expanded.append({
            "raw_term": mapping.term,
            "canonical_company": mapping.canonical_company,
            "company_aliases": mapping.company_aliases,
            "org_product_terms": mapping.org_product_terms,
            "preferred_search_mode": mapping.preferred_search_mode,
            "confidence": mapping.confidence,
        })
    return expanded
