# Maimai JD Campaign Generalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove AI Infra sample residue from JD-driven Maimai campaigns, make company plus product-line terms map consistently into search execution, and add a structured delivery feedback loop for future strategy iteration.

**Architecture:** Keep existing `maimai_ai_infra_*` command names as compatibility wrappers while adding generic campaign modules. The first execution slice fixes the real live-search filter residue bug; later slices move company/product mapping, search-unit compilation, ranking dimensions, delivery report labels, and user feedback into campaign strategy files.

**Tech Stack:** Python 3, JSON/JSONL campaign contracts, SQLite campaign DB, pytest, existing `scripts/maimai_*` workflow modules.

---

## Scope And Boundaries

- Do not rerun real Maimai search while implementing this plan.
- Do not modify historical campaign raw files under `data/campaigns/**/raw/**`.
- Do not write `data/talent.db`.
- Keep `scripts/maimai_ai_infra_*` CLIs working for existing tests and historical campaign commands.
- New generic behavior must be testable on local fixtures before being used on live campaigns.

## Target File Structure

- Create `rules/company-product-registry.json`: curated company, department, product, alias, and search-mode registry.
- Create `scripts/maimai_company_registry.py`: load and resolve company/product terms from JD and strategy files.
- Create `scripts/maimai_campaign_search_plan.py`: compile business-facing `strategy.json` into canonical `search-plan.json` and `search-units.jsonl`.
- Create `scripts/maimai_campaign_rank.py`: generic ranking wrapper that derives title, keyword, company, education, and exclusion terms from campaign strategy.
- Create `scripts/maimai_campaign_delivery_report.py`: generic final report/outreach generation with strategy-derived title and direction coverage.
- Create `scripts/maimai_campaign_feedback.py`: validate delivery feedback and compile next-round strategy adjustments.
- Modify `scripts/maimai_ai_infra_search_runner.py`: clear high-risk template filters unless explicitly provided.
- Modify `scripts/maimai_ai_infra_search_live_gate.py`: apply the same filter clearing in the live browser expression.
- Modify `scripts/maimai_campaign_orchestrator.py`: route JD-style strategies to generic compiler/ranker/report modules and legacy AI Infra strategies to legacy modules.
- Modify `skills/maimai-talent-search-campaign/SKILL.md`: require company/product mapping output and feedback contract.
- Modify `agents/workflows/maimai-unattended-campaign/AGENT.md`: add post-delivery feedback stage and query-only filter clearing invariant.
- Add tests:
  - `tests/test_maimai_search_filter_clearing.py`
  - `tests/test_maimai_company_registry.py`
  - `tests/test_maimai_campaign_search_plan.py`
  - `tests/test_maimai_campaign_rank_generic.py`
  - `tests/test_maimai_campaign_delivery_report_generic.py`
  - `tests/test_maimai_campaign_feedback.py`

## Invariants

- Query-only means `search.allcompanies == ""` and `search.positions == ""` in the actual request body.
- Company/product shorthand such as `字节 DMC` resolves to:
  - `canonical_company = 字节跳动`
  - product/org keywords include `DMC`, `Data Management Center`, `数据管理中心`
  - search mode is selected by confidence and smoke result.
- A campaign report title and direction coverage must never be hard-coded to `AI Infra` unless the campaign strategy says the target role is AI Infra.
- User feedback must produce machine-readable adjustments, not only prose.

---

### Task 1: Fix Query-Only Search Filter Residue

**Files:**
- Modify: `scripts/maimai_ai_infra_search_runner.py`
- Modify: `scripts/maimai_ai_infra_search_live_gate.py`
- Test: `tests/test_maimai_search_filter_clearing.py`
- Optional update: existing assertions in `tests/test_maimai_ai_infra_runner.py` and `tests/test_maimai_ai_infra_search_live_gate.py`

- [ ] **Step 1: Add failing tests for template filter clearing**

Create `tests/test_maimai_search_filter_clearing.py`:

```python
import json

from scripts.maimai_ai_infra_search_live_gate import search_expression
from scripts.maimai_ai_infra_search_runner import patch_search_body


def _template_body() -> dict:
    return {
        "search": {
            "query": "old",
            "search_query": "old",
            "positions": "旧职位",
            "allcompanies": "BAT",
            "cities": "重庆",
            "provinces": "重庆",
            "ht_cities": "重庆",
            "ht_provinces": "重庆",
            "region_scope": "0",
            "paginationParam": {"page": 1, "size": 30},
            "page": 0,
            "size": 30,
        }
    }


def test_patch_search_body_clears_high_risk_template_filters_for_query_only() -> None:
    batch = {
        "query": "字节 大模型 后训练 数据策略 数据质量",
        "page_size": 30,
        "search_filters": {
            "query_relation": 0,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    }

    body = patch_search_body(_template_body(), batch, page=2)
    search = body["search"]

    assert search["query"] == "字节 大模型 后训练 数据策略 数据质量"
    assert search["search_query"] == "字节 大模型 后训练 数据策略 数据质量"
    assert search["allcompanies"] == ""
    assert search["positions"] == ""
    assert search["cities"] == ""
    assert search["provinces"] == ""
    assert search["ht_cities"] == ""
    assert search["ht_provinces"] == ""
    assert search["region_scope"] == "0,1"
    assert search["paginationParam"] == {"page": 2, "size": 30}


def test_patch_search_body_preserves_explicit_structured_filters() -> None:
    batch = {
        "query": "通义 数据策略",
        "page_size": 30,
        "search_filters": {
            "allcompanies": "阿里巴巴",
            "positions": "数据策略负责人",
            "query_relation": 1,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    }

    body = patch_search_body(_template_body(), batch, page=1)
    search = body["search"]

    assert search["allcompanies"] == "阿里巴巴"
    assert search["positions"] == "数据策略负责人"
    assert search["query_relation"] == 1


def test_live_gate_expression_contains_filter_defaults_and_explicit_empty_values() -> None:
    expression = search_expression(
        "字节 大模型 后训练 数据策略 数据质量",
        1,
        30,
        {
            "query_relation": 0,
            "region_scope": "0,1",
            "cities": "",
            "provinces": "",
            "ht_cities": "",
            "ht_provinces": "",
        },
    )

    assert "HIGH_RISK_FILTER_DEFAULTS" in expression
    assert '"allcompanies": ""' in expression
    assert '"positions": ""' in expression
    assert '"cities": ""' in expression
    assert '"region_scope": "0,1"' in expression
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_search_filter_clearing.py -q
```

Expected: the first and third tests fail because `allcompanies` and `positions` are not cleared by default.

- [ ] **Step 3: Implement filter clearing in the Python runner**

In `scripts/maimai_ai_infra_search_runner.py`, add constants near `CONFIRMED_SEARCH_FILTER_FIELDS`:

```python
HIGH_RISK_SEARCH_FILTER_DEFAULTS: dict[str, Any] = {
    "allcompanies": "",
    "positions": "",
    "cities": "",
    "provinces": "",
    "ht_cities": "",
    "ht_provinces": "",
    "region_scope": "0,1",
}
```

Replace `_apply_confirmed_search_filters()` with:

```python
def _apply_confirmed_search_filters(search: dict[str, Any], batch: dict[str, Any]) -> None:
    filters = confirmed_search_filters_from_batch(batch)
    if batch.get("preserve_template_filters") is not True:
        for field_name, value in HIGH_RISK_SEARCH_FILTER_DEFAULTS.items():
            if field_name not in filters:
                search[field_name] = value
    if "min_age" in filters or "max_age" in filters:
        search.pop("age", None)
    for field_name, value in filters.items():
        search[field_name] = value
```

- [ ] **Step 4: Implement the same clearing in live gate JavaScript**

In `scripts/maimai_ai_infra_search_live_gate.py`, inside `search_expression()`, update the generated JS before `applyConfirmedSearchFilters`:

```javascript
  const HIGH_RISK_FILTER_DEFAULTS = {
    allcompanies: "",
    positions: "",
    cities: "",
    provinces: "",
    ht_cities: "",
    ht_provinces: "",
    region_scope: "0,1"
  };
```

Replace the JS `applyConfirmedSearchFilters` function with:

```javascript
  function applyConfirmedSearchFilters(body, filters) {
    const target = body && body.search && typeof body.search === "object"
      ? body.search
      : body;
    for (const [key, value] of Object.entries(HIGH_RISK_FILTER_DEFAULTS)) {
      if (!Object.prototype.hasOwnProperty.call(filters || {}, key)) {
        target[key] = value;
      }
    }
    if (Object.prototype.hasOwnProperty.call(filters || {}, "min_age") ||
        Object.prototype.hasOwnProperty.call(filters || {}, "max_age")) {
      delete target.age;
    }
    for (const [key, value] of Object.entries(filters || {})) {
      target[key] = value;
    }
    return body;
  }
```

- [ ] **Step 5: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_search_filter_clearing.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py -q
```

Expected: all selected tests pass.

---

### Task 2: Add Company/Product Registry

**Files:**
- Create: `rules/company-product-registry.json`
- Create: `scripts/maimai_company_registry.py`
- Test: `tests/test_maimai_company_registry.py`

- [ ] **Step 1: Add failing tests for shorthand mapping**

Create `tests/test_maimai_company_registry.py`:

```python
import json
from pathlib import Path

import pytest

from scripts.maimai_company_registry import (
    CompanyProductMapping,
    expand_company_pool_terms,
    load_company_product_registry,
    resolve_company_product_term,
)


def _registry_path(tmp_path: Path) -> Path:
    path = tmp_path / "company-product-registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {
                        "term": "字节 DMC",
                        "canonical_company": "字节跳动",
                        "company_aliases": ["字节", "ByteDance"],
                        "org_product_terms": ["DMC", "Data Management Center", "数据管理中心"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                    {
                        "term": "阿里千问",
                        "canonical_company": "阿里巴巴",
                        "company_aliases": ["阿里", "阿里云", "Alibaba"],
                        "org_product_terms": ["通义千问", "通义", "Qwen", "千问"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                    {
                        "term": "百度千帆",
                        "canonical_company": "百度",
                        "company_aliases": ["百度", "Baidu"],
                        "org_product_terms": ["千帆", "文心", "ERNIE"],
                        "preferred_search_mode": "hybrid",
                        "confidence": "curated",
                    },
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def test_resolve_company_product_term_maps_shorthand(tmp_path: Path) -> None:
    registry = load_company_product_registry(_registry_path(tmp_path))

    mapping = resolve_company_product_term("字节 dmc", registry)

    assert mapping == CompanyProductMapping(
        term="字节 DMC",
        canonical_company="字节跳动",
        company_aliases=["字节", "ByteDance"],
        org_product_terms=["DMC", "Data Management Center", "数据管理中心"],
        preferred_search_mode="hybrid",
        confidence="curated",
    )


def test_expand_company_pool_terms_keeps_unknown_terms_as_query_only(tmp_path: Path) -> None:
    registry = load_company_product_registry(_registry_path(tmp_path))

    expanded = expand_company_pool_terms(["字节 DMC", "未知团队"], registry)

    assert expanded[0]["raw_term"] == "字节 DMC"
    assert expanded[0]["canonical_company"] == "字节跳动"
    assert expanded[0]["org_product_terms"] == ["DMC", "Data Management Center", "数据管理中心"]
    assert expanded[1]["raw_term"] == "未知团队"
    assert expanded[1]["canonical_company"] == ""
    assert expanded[1]["preferred_search_mode"] == "query_only"


def test_load_company_product_registry_rejects_duplicate_terms(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "entries": [
                    {"term": "字节 DMC", "canonical_company": "字节跳动"},
                    {"term": "字节 dmc", "canonical_company": "字节跳动"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate company product term"):
        load_company_product_registry(path)
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_company_registry.py -q
```

Expected: import failure for `scripts.maimai_company_registry`.

- [ ] **Step 3: Implement registry loader and resolver**

Create `scripts/maimai_company_registry.py`:

```python
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
```

- [ ] **Step 4: Add initial curated registry**

Create `rules/company-product-registry.json`:

```json
{
  "schema_version": 1,
  "entries": [
    {
      "term": "字节 DMC",
      "canonical_company": "字节跳动",
      "company_aliases": ["字节", "ByteDance"],
      "org_product_terms": ["DMC", "Data Management Center", "数据管理中心"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "字节 Global Data",
      "canonical_company": "字节跳动",
      "company_aliases": ["字节", "ByteDance", "TikTok"],
      "org_product_terms": ["Global Data", "国际化数据", "TikTok 数据"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "字节 AIDP",
      "canonical_company": "字节跳动",
      "company_aliases": ["字节", "ByteDance"],
      "org_product_terms": ["AIDP", "AI Data Platform", "字节数据平台"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "字节 Seed",
      "canonical_company": "字节跳动",
      "company_aliases": ["字节", "ByteDance"],
      "org_product_terms": ["Seed", "豆包", "火山引擎"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "阿里千问",
      "canonical_company": "阿里巴巴",
      "company_aliases": ["阿里", "阿里云", "Alibaba"],
      "org_product_terms": ["通义千问", "通义", "Qwen", "千问"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "阿里通义",
      "canonical_company": "阿里巴巴",
      "company_aliases": ["阿里", "阿里云", "Alibaba"],
      "org_product_terms": ["通义", "通义千问", "Qwen", "达摩院"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "百度千帆",
      "canonical_company": "百度",
      "company_aliases": ["百度", "Baidu"],
      "org_product_terms": ["千帆", "文心", "ERNIE"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "腾讯混元",
      "canonical_company": "腾讯",
      "company_aliases": ["腾讯", "Tencent"],
      "org_product_terms": ["混元", "Hunyuan", "腾讯云", "TEG", "AI Lab"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "快手可灵",
      "canonical_company": "快手",
      "company_aliases": ["快手", "Kuaishou"],
      "org_product_terms": ["可灵", "Kling", "快手 AI"],
      "preferred_search_mode": "hybrid",
      "confidence": "curated"
    },
    {
      "term": "Scale AI",
      "canonical_company": "Scale AI",
      "company_aliases": ["Scale", "scale ai"],
      "org_product_terms": ["RLHF", "data labeling", "data quality"],
      "preferred_search_mode": "query_only",
      "confidence": "curated"
    },
    {
      "term": "Surge AI",
      "canonical_company": "Surge AI",
      "company_aliases": ["Surge", "surge ai"],
      "org_product_terms": ["RLHF", "data labeling", "data quality"],
      "preferred_search_mode": "query_only",
      "confidence": "curated"
    }
  ]
}
```

- [ ] **Step 5: Verify registry tests**

Run:

```powershell
python -m pytest tests/test_maimai_company_registry.py -q
```

Expected: pass.

---

### Task 3: Compile Generic JD Strategy Into Canonical Search Units

**Files:**
- Create: `scripts/maimai_campaign_search_plan.py`
- Modify: `scripts/maimai_campaign_orchestrator.py`
- Test: `tests/test_maimai_campaign_search_plan.py`
- Test: `tests/test_maimai_campaign_orchestrator.py`

- [ ] **Step 1: Add failing tests for mixed company pools**

Create `tests/test_maimai_campaign_search_plan.py`:

```python
import json
from pathlib import Path

from scripts.maimai_campaign_search_plan import build_generic_search_plan, build_generic_search_units


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-data-strategy-lead-v1",
        "keyword_packages": [
            {
                "id": "p0-data-strategy",
                "priority": "P0",
                "position_terms": ["大模型数据策略负责人", "数据策略负责人"],
                "keywords": ["大模型", "后训练", "数据策略", "数据质量"],
            }
        ],
        "company_pools": {
            "p0_direct": ["字节 DMC", "阿里千问", "美团", "小红书"]
        },
        "search_dimensions": {
            "search_units_file": "search-units.jsonl"
        },
        "stop_thresholds": {
            "budget": ["单个 wave 不超过 50 页"]
        },
    }


def test_build_generic_search_units_expands_each_company_pool_member() -> None:
    units = build_generic_search_units(_strategy())

    assert [unit["unit_id"] for unit in units] == [
        "unit-000001",
        "unit-000002",
        "unit-000003",
        "unit-000004",
    ]
    queries = [unit["query"] for unit in units]
    assert "字节 DMC 大模型 后训练 数据策略 数据质量" in queries
    assert "阿里千问 大模型 后训练 数据策略 数据质量" in queries
    assert "美团 大模型 后训练 数据策略 数据质量" in queries
    assert "小红书 大模型 后训练 数据策略 数据质量" in queries
    assert all(unit["search_filters"]["allcompanies"] == "" for unit in units)
    assert all(unit["search_filters"]["positions"] == "" for unit in units)
    assert all(unit["search_filters"]["region_scope"] == "0,1" for unit in units)


def test_build_generic_search_plan_does_not_emit_ai_infra_batches() -> None:
    plan = build_generic_search_plan(_strategy())

    encoded = json.dumps(plan, ensure_ascii=False)
    assert plan["strategy_version"] == "hunyuan-data-strategy-lead-v1"
    assert "AI Infra" not in encoded
    assert "训练框架" not in encoded
    assert plan["batches"][0]["query"] == "字节 DMC 大模型 后训练 数据策略 数据质量"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_search_plan.py -q
```

Expected: import failure for `scripts.maimai_campaign_search_plan`.

- [ ] **Step 3: Implement generic compiler**

Create `scripts/maimai_campaign_search_plan.py`:

```python
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
```

- [ ] **Step 4: Route strategy compilation in orchestrator**

In `scripts/maimai_campaign_orchestrator.py`, add:

```python
def _is_legacy_ai_infra_strategy(strategy_path: str | Path) -> bool:
    try:
        data = json.loads(Path(strategy_path).read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return True
    return isinstance(data, dict) and "company_tiers" in data and "title_batches" in data and "v2" in data
```

In `build_stage_command_plan()`, set:

```python
    search_plan_module = (
        "scripts.maimai_ai_infra_search_plan"
        if _is_legacy_ai_infra_strategy(strategy)
        else "scripts.maimai_campaign_search_plan"
    )
```

Then replace the hard-coded compile command module with `search_plan_module`.

- [ ] **Step 5: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py -q
```

Expected: pass.

---

### Task 4: Make Ranking Strategy Campaign-Driven

**Files:**
- Create: `scripts/maimai_campaign_rank.py`
- Modify: `scripts/maimai_campaign_orchestrator.py`
- Test: `tests/test_maimai_campaign_rank_generic.py`
- Keep legacy: `scripts/maimai_ai_infra_rank.py`

- [ ] **Step 1: Add failing generic rank tests**

Create `tests/test_maimai_campaign_rank_generic.py`:

```python
from scripts.maimai_campaign_rank import build_rank_terms, title_level


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-rank-v1",
        "position_aliases": [
            "大模型数据策略负责人",
            "数据交付负责人",
            "数据质检负责人",
            "数据运营负责人",
        ],
        "keyword_packages": [
            {
                "id": "p0-data",
                "keywords": ["大模型", "后训练", "数据策略", "数据质量", "数据标注", "数据合成"],
            }
        ],
        "screening_rules": {
            "A": ["负责后训练数据策略、数据交付、标注质检、数据合成或数据运营团队"],
            "淘汰": ["纯算法研究且无数据生产、质量体系或团队管理"],
        },
    }


def test_build_rank_terms_uses_strategy_not_ai_infra_defaults() -> None:
    terms = build_rank_terms(_strategy())

    assert "数据策略负责人" in terms.precision_titles
    assert "数据质量" in terms.keywords
    assert "AI Infra" not in terms.precision_titles
    assert "训练框架" not in terms.precision_titles
    assert "算子" not in terms.keywords


def test_title_level_matches_data_strategy_titles() -> None:
    terms = build_rank_terms(_strategy())

    assert title_level("大模型数据策略负责人", terms) == "precision"
    assert title_level("数据运营负责人", terms) == "precision"
    assert title_level("大模型算法工程师", terms) == "missing"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_rank_generic.py -q
```

Expected: import failure for `scripts.maimai_campaign_rank`.

- [ ] **Step 3: Implement strategy-derived rank terms**

Create `scripts/maimai_campaign_rank.py`:

```python
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RankTerms:
    precision_titles: list[str]
    technical_titles: list[str]
    generic_titles: list[str]
    keywords: list[str]
    reject_terms: list[str]


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def build_rank_terms(strategy: dict[str, Any]) -> RankTerms:
    position_aliases = [str(item) for item in strategy.get("position_aliases") or []]
    keyword_terms: list[str] = []
    for package in strategy.get("keyword_packages") or []:
        if isinstance(package, dict):
            keyword_terms.extend(str(item) for item in package.get("keywords") or [])
            keyword_terms.extend(str(item) for item in package.get("position_terms") or [])
    screening_rules = strategy.get("screening_rules") if isinstance(strategy.get("screening_rules"), dict) else {}
    reject_terms = [str(item) for item in screening_rules.get("淘汰", [])]
    return RankTerms(
        precision_titles=_unique(position_aliases),
        technical_titles=_unique([term for term in keyword_terms if "平台" in term or "体系" in term]),
        generic_titles=_unique(["负责人", "专家", "Lead", "Manager"]),
        keywords=_unique(keyword_terms),
        reject_terms=_unique(reject_terms),
    )


def title_level(title: str, terms: RankTerms) -> str:
    lowered = title.casefold()
    if any(term.casefold() in lowered for term in terms.precision_titles):
        return "precision"
    if any(term.casefold() in lowered for term in terms.technical_titles):
        return "technical"
    if any(term.casefold() in lowered for term in terms.generic_titles):
        return "generic"
    return "missing"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="通用 JD-driven 脉脉候选人评分")
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--mode", choices=["list", "detailed"], default="list")
    parser.add_argument("--candidate-ids-file")
    args = parser.parse_args(argv)

    # Initial adapter: delegate full DB ranking to legacy ranker after validating terms are strategy-driven.
    # Later task can move the full score function once generic scoring acceptance is locked.
    from scripts.maimai_ai_infra_rank import main as legacy_main

    return legacy_main([
        "--db",
        args.db,
        "--config",
        args.config,
        "--out-json",
        args.out_json,
        "--out-md",
        args.out_md,
        "--mode",
        args.mode,
        *([] if not args.candidate_ids_file else ["--candidate-ids-file", args.candidate_ids_file]),
    ])


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Replace legacy delegation before enabling generic route**

Before routing orchestrator to `scripts.maimai_campaign_rank`, move scoring internals from `maimai_ai_infra_rank.py` into shared helpers or update `maimai_campaign_rank.py` so `_title_score()` and `_tech_keywords()` use `build_rank_terms()` only. Acceptance condition:

```python
assert "AI Infra" not in json.dumps(rank_result, ensure_ascii=False)
assert "训练框架" not in json.dumps(rank_result, ensure_ascii=False)
```

- [ ] **Step 5: Route rank stage only after generic scorer passes**

In `scripts/maimai_campaign_orchestrator.py`, use:

```python
    rank_module = (
        "scripts.maimai_ai_infra_rank"
        if _is_legacy_ai_infra_strategy(strategy)
        else "scripts.maimai_campaign_rank"
    )
```

Replace both list and detailed rank command module names with `rank_module`.

- [ ] **Step 6: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_rank_generic.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_campaign_orchestrator.py -q
```

Expected: pass, with legacy AI Infra tests unchanged.

---

### Task 5: Make Delivery Report And Outreach Strategy-Driven

**Files:**
- Create: `scripts/maimai_campaign_delivery_report.py`
- Modify: `scripts/maimai_campaign_orchestrator.py`
- Test: `tests/test_maimai_campaign_delivery_report_generic.py`
- Keep legacy: `scripts/maimai_ai_infra_delivery_report.py`, `scripts/maimai_ai_infra_outreach_export.py`

- [ ] **Step 1: Add failing delivery metadata tests**

Create `tests/test_maimai_campaign_delivery_report_generic.py`:

```python
from scripts.maimai_campaign_delivery_report import (
    build_delivery_metadata,
    direction_rules_from_strategy,
    outreach_angle,
)


def _strategy() -> dict:
    return {
        "strategy_version": "hunyuan-delivery-v1",
        "delivery_targets": {
            "report_title": "混元大模型数据策略负责人最终寻访报告",
            "direction_rules": {
                "后训练数据策略": ["后训练", "数据策略", "Topic 数据"],
                "数据交付质量": ["数据标注", "数据质检", "数据交付", "质量评估"],
                "数据平台产品": ["标注平台", "质检平台", "数据管理"],
            },
        },
    }


def test_direction_rules_from_strategy_are_not_ai_infra_defaults() -> None:
    rules = direction_rules_from_strategy(_strategy())

    assert "后训练数据策略" in rules
    assert "训练框架" not in rules
    assert "推理引擎" not in rules


def test_build_delivery_metadata_uses_campaign_title() -> None:
    metadata = build_delivery_metadata("hunyuan-data-strategy-lead-2026-05-21", _strategy())

    assert metadata["export_type"] == "maimai_campaign_final_search_report"
    assert metadata["report_title"] == "混元大模型数据策略负责人最终寻访报告"


def test_outreach_angle_uses_role_specific_direction() -> None:
    text = outreach_angle(
        {
            "company": "字节跳动",
            "directions": ["数据交付质量"],
            "rank_evidence": {"tech_keywords": ["数据标注", "数据质检", "数据质量"]},
            "recommendation_label": "强推荐",
        }
    )

    assert "数据交付质量" in text
    assert "训练框架" not in text
    assert "底层系统深度" not in text
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_delivery_report_generic.py -q
```

Expected: import failure for `scripts.maimai_campaign_delivery_report`.

- [ ] **Step 3: Implement generic delivery helpers**

Create `scripts/maimai_campaign_delivery_report.py` with pure helpers first:

```python
from __future__ import annotations

from typing import Any


DEFAULT_DIRECTION_RULES = {
    "核心岗位匹配": ("岗位", "负责人", "Lead"),
    "公司/行业匹配": ("公司", "行业", "团队"),
    "待深审": (),
}


def direction_rules_from_strategy(strategy: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    delivery_targets = strategy.get("delivery_targets")
    if isinstance(delivery_targets, dict) and isinstance(delivery_targets.get("direction_rules"), dict):
        return {
            str(label): tuple(str(term) for term in terms)
            for label, terms in delivery_targets["direction_rules"].items()
            if isinstance(terms, list)
        }
    return DEFAULT_DIRECTION_RULES


def build_delivery_metadata(campaign_id: str, strategy: dict[str, Any]) -> dict[str, Any]:
    delivery_targets = strategy.get("delivery_targets") if isinstance(strategy.get("delivery_targets"), dict) else {}
    return {
        "export_type": "maimai_campaign_final_search_report",
        "campaign_id": campaign_id,
        "strategy_version": strategy.get("strategy_version") or "",
        "report_title": delivery_targets.get("report_title") or f"{campaign_id} 最终寻访报告",
    }


def outreach_angle(card: dict[str, Any]) -> str:
    company = card.get("company") or "当前团队"
    directions = "、".join(card.get("directions") or ["岗位匹配"])
    keywords = card.get("rank_evidence", {}).get("tech_keywords") or []
    keyword_text = "、".join(str(keyword) for keyword in keywords[:3]) or directions
    if card.get("recommendation_label") == "强推荐":
        return f"优先从 {company} 的{directions}经历切入，确认其在 {keyword_text} 上的职责边界、团队规模和近期机会意愿。"
    if card.get("recommendation_label") == "推荐":
        return f"围绕 {directions} 与 {keyword_text} 追问具体职责，确认是否符合本岗位核心画像。"
    if card.get("recommendation_label") == "观察":
        return "先做轻量深审，重点确认岗位画像、团队管理和核心业务证据是否真实匹配。"
    return "不进入外联队列；仅作为下一轮评分误判样本。"
```

- [ ] **Step 4: Port full report generation**

Move the report-building path from `scripts/maimai_ai_infra_delivery_report.py` into the generic module, replacing:

```python
"export_type": "maimai_ai_infra_final_search_report"
"# AI Infra V2 A/B 最终寻访报告"
DIRECTION_RULES
_outreach_angle()
```

with:

```python
build_delivery_metadata(campaign_id, strategy)
metadata["report_title"]
direction_rules_from_strategy(strategy)
outreach_angle(card)
```

Acceptance check after generating a Hunyuan fixture report:

```python
assert "AI Infra V2" not in report_md
assert "训练框架" not in report_md
assert "后训练数据策略" in report_md
```

- [ ] **Step 5: Route delivery stage after generic report passes**

In `scripts/maimai_campaign_orchestrator.py`, use:

```python
    delivery_module = (
        "scripts.maimai_ai_infra_delivery_report"
        if _is_legacy_ai_infra_strategy(strategy)
        else "scripts.maimai_campaign_delivery_report"
    )
```

Replace delivery report command module with `delivery_module`.

- [ ] **Step 6: Verify focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_delivery_report_generic.py tests/test_maimai_ai_infra_delivery_report.py tests/test_maimai_ai_infra_outreach_export.py -q
```

Expected: pass.

---

### Task 6: Add Delivery Feedback Contract And Next-Round Adjustment

**Files:**
- Create: `scripts/maimai_campaign_feedback.py`
- Modify: `agents/workflows/maimai-unattended-campaign/AGENT.md`
- Modify: `skills/maimai-talent-search-campaign/SKILL.md`
- Test: `tests/test_maimai_campaign_feedback.py`

- [ ] **Step 1: Add failing feedback tests**

Create `tests/test_maimai_campaign_feedback.py`:

```python
import json
from pathlib import Path

import pytest

from scripts.maimai_campaign_feedback import (
    compile_strategy_adjustment,
    load_delivery_feedback,
)


def test_load_delivery_feedback_validates_reason_codes(tmp_path: Path) -> None:
    path = tmp_path / "feedback.json"
    path.write_text(
        json.dumps(
            {
                "campaign_id": "hunyuan-data-strategy-lead-2026-05-21",
                "overall_rating": 3,
                "candidate_feedback": [
                    {
                        "candidate_id": 152,
                        "label": "bad",
                        "reason_codes": ["role_too_algorithmic", "lacks_data_team_management"],
                        "comment": "偏算法评测，不是数据策略负责人",
                    }
                ],
                "missing_profiles": ["更多真正管理数据标注/质检/交付团队的人"],
                "company_feedback": {"字节 DMC": "increase", "纯算法团队": "decrease"},
                "query_feedback": [{"unit_id": "unit-000001", "quality": "low"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    feedback = load_delivery_feedback(path)

    assert feedback["overall_rating"] == 3
    assert feedback["candidate_feedback"][0]["reason_codes"] == [
        "role_too_algorithmic",
        "lacks_data_team_management",
    ]


def test_load_delivery_feedback_rejects_unknown_label(tmp_path: Path) -> None:
    path = tmp_path / "bad-feedback.json"
    path.write_text(
        json.dumps(
            {
                "campaign_id": "c",
                "candidate_feedback": [{"candidate_id": 1, "label": "great"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid feedback label"):
        load_delivery_feedback(path)


def test_compile_strategy_adjustment_translates_feedback_to_actions(tmp_path: Path) -> None:
    feedback = {
        "campaign_id": "hunyuan-data-strategy-lead-2026-05-21",
        "overall_rating": 3,
        "candidate_feedback": [
            {
                "candidate_id": 152,
                "label": "bad",
                "reason_codes": ["role_too_algorithmic", "lacks_data_team_management"],
            }
        ],
        "missing_profiles": ["更多真正管理数据标注/质检/交付团队的人"],
        "company_feedback": {"字节 DMC": "increase", "纯算法团队": "decrease"},
        "query_feedback": [{"unit_id": "unit-000001", "quality": "low"}],
    }

    adjustment = compile_strategy_adjustment(feedback)

    assert adjustment["campaign_id"] == "hunyuan-data-strategy-lead-2026-05-21"
    assert "降低纯算法/训练框架画像权重" in adjustment["rank_adjustments"]
    assert "提高数据团队管理证据权重" in adjustment["rank_adjustments"]
    assert adjustment["company_adjustments"]["字节 DMC"] == "increase"
    assert adjustment["query_adjustments"][0]["unit_id"] == "unit-000001"
```

- [ ] **Step 2: Run tests and confirm failure**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_feedback.py -q
```

Expected: import failure for `scripts.maimai_campaign_feedback`.

- [ ] **Step 3: Implement feedback validator and compiler**

Create `scripts/maimai_campaign_feedback.py`:

```python
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


VALID_LABELS = {"good", "maybe", "bad"}
VALID_REASON_CODES = {
    "role_too_algorithmic",
    "lacks_data_team_management",
    "company_not_target",
    "seniority_too_low",
    "seniority_too_high",
    "missing_product_or_platform_scope",
    "good_target_company",
    "good_data_delivery_evidence",
}


def load_delivery_feedback(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("delivery feedback must be an object")
    items = data.get("candidate_feedback") or []
    if not isinstance(items, list):
        raise ValueError("candidate_feedback must be a list")
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"candidate_feedback item {index} must be an object")
        label = item.get("label")
        if label not in VALID_LABELS:
            raise ValueError(f"invalid feedback label: {label}")
        reason_codes = item.get("reason_codes") or []
        if not isinstance(reason_codes, list):
            raise ValueError(f"candidate_feedback item {index} reason_codes must be a list")
        unknown = sorted(set(str(code) for code in reason_codes) - VALID_REASON_CODES)
        if unknown:
            raise ValueError("unknown feedback reason codes: " + ", ".join(unknown))
    return data


def compile_strategy_adjustment(feedback: dict[str, Any]) -> dict[str, Any]:
    reason_counts: dict[str, int] = {}
    for item in feedback.get("candidate_feedback") or []:
        for code in item.get("reason_codes") or []:
            reason_counts[code] = reason_counts.get(code, 0) + 1

    rank_adjustments: list[str] = []
    if reason_counts.get("role_too_algorithmic"):
        rank_adjustments.append("降低纯算法/训练框架画像权重")
    if reason_counts.get("lacks_data_team_management"):
        rank_adjustments.append("提高数据团队管理证据权重")
    if reason_counts.get("seniority_too_low"):
        rank_adjustments.append("提高负责人/团队管理/Lead 职级信号权重")
    if reason_counts.get("missing_product_or_platform_scope"):
        rank_adjustments.append("提高数据平台/标注平台/质检平台产品化证据权重")

    return {
        "campaign_id": feedback.get("campaign_id") or "",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "overall_rating": feedback.get("overall_rating"),
        "reason_counts": reason_counts,
        "rank_adjustments": rank_adjustments,
        "company_adjustments": feedback.get("company_feedback") or {},
        "query_adjustments": feedback.get("query_feedback") or [],
        "missing_profiles": feedback.get("missing_profiles") or [],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="编译脉脉 campaign 交付反馈为下一轮策略调整")
    parser.add_argument("--feedback", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    feedback = load_delivery_feedback(args.feedback)
    adjustment = compile_strategy_adjustment(feedback)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(adjustment, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Document feedback stage in workflow**

In `agents/workflows/maimai-unattended-campaign/AGENT.md`, add after S13:

```markdown
### S14 交付反馈与下一轮策略调整

交付包发布后，若用户提供评价，必须落为 `feedback/delivery-feedback-<date>.json`，再运行：

```powershell
python -m scripts.maimai_campaign_feedback --feedback data/campaigns/<campaign_id>/feedback/delivery-feedback-<date>.json --out data/campaigns/<campaign_id>/feedback/strategy-adjustment-<date>.json
```

反馈至少包含候选人级 `good/maybe/bad`、原因码、缺失画像、公司池调整和 query/unit 调整。下一轮搜索必须先读取 `strategy-adjustment-*.json`，不得只根据聊天文字临时改关键词。
```

- [ ] **Step 5: Document company/product mapping and feedback in skill**

In `skills/maimai-talent-search-campaign/SKILL.md`, add to `strategy.json` contract:

```markdown
- `company_product_mappings`：JD 中公司+部门/产品线缩写的结构化映射，例如 `字节 DMC -> 字节跳动 + DMC/Data Management Center/数据管理中心`。
- `delivery_feedback_contract`：交付后用户评价字段、原因码和下一轮策略调整入口。
```

- [ ] **Step 6: Verify feedback tests**

Run:

```powershell
python -m pytest tests/test_maimai_campaign_feedback.py -q
```

Expected: pass.

---

### Task 7: End-To-End Fixture Guardrail For Hunyuan

**Files:**
- Create: `tests/fixtures/maimai/hunyuan-strategy.json`
- Create: `tests/test_maimai_hunyuan_generalization_guardrail.py`

- [ ] **Step 1: Create a compact Hunyuan fixture strategy**

Create `tests/fixtures/maimai/hunyuan-strategy.json`:

```json
{
  "strategy_version": "hunyuan-data-strategy-lead-v1-fixture",
  "keyword_packages": [
    {
      "id": "p0-llm-data-strategy",
      "priority": "P0",
      "position_terms": ["大模型数据策略负责人", "数据策略负责人", "AI 数据负责人"],
      "keywords": ["大模型", "后训练", "数据策略", "数据质量"]
    },
    {
      "id": "p0-data-delivery-quality",
      "priority": "P0",
      "position_terms": ["数据交付负责人", "数据质检负责人", "数据运营负责人"],
      "keywords": ["数据标注", "数据质检", "数据交付", "质量评估"]
    }
  ],
  "company_pools": {
    "p0_direct": ["字节 DMC", "字节 Global Data", "字节 AIDP", "阿里千问", "快手可灵", "美团", "小红书", "Scale AI", "Surge AI"]
  },
  "position_aliases": [
    "大模型数据策略负责人",
    "大模型数据负责人",
    "AI 数据负责人",
    "后训练数据负责人",
    "数据交付负责人",
    "数据质检负责人",
    "数据运营负责人"
  ],
  "screening_rules": {
    "A": ["负责后训练数据策略、数据交付、标注质检、数据合成或数据运营团队"],
    "淘汰": ["纯算法研究且无数据生产、质量体系或团队管理"]
  },
  "delivery_targets": {
    "report_title": "混元大模型数据策略负责人最终寻访报告",
    "direction_rules": {
      "后训练数据策略": ["后训练", "数据策略", "Topic 数据"],
      "数据交付质量": ["数据标注", "数据质检", "数据交付", "质量评估"],
      "数据平台产品": ["标注平台", "质检平台", "数据管理"]
    }
  }
}
```

- [ ] **Step 2: Add end-to-end guardrail test**

Create `tests/test_maimai_hunyuan_generalization_guardrail.py`:

```python
import json
from pathlib import Path

from scripts.maimai_campaign_delivery_report import build_delivery_metadata, direction_rules_from_strategy
from scripts.maimai_campaign_rank import build_rank_terms
from scripts.maimai_campaign_search_plan import build_generic_search_plan


FIXTURE = Path("tests/fixtures/maimai/hunyuan-strategy.json")


def test_hunyuan_fixture_has_no_ai_infra_residue() -> None:
    strategy = json.loads(FIXTURE.read_text(encoding="utf-8"))
    plan = build_generic_search_plan(strategy)
    terms = build_rank_terms(strategy)
    metadata = build_delivery_metadata("hunyuan-data-strategy-lead-2026-05-21", strategy)
    direction_rules = direction_rules_from_strategy(strategy)

    encoded = json.dumps(
        {
            "plan": plan,
            "terms": terms.__dict__,
            "metadata": metadata,
            "direction_rules": direction_rules,
        },
        ensure_ascii=False,
    )

    assert "AI Infra" not in encoded
    assert "训练框架" not in encoded
    assert "推理引擎" not in encoded
    assert "混元大模型数据策略负责人最终寻访报告" in encoded
    assert any(batch["query"].startswith("字节 DMC ") for batch in plan["batches"])
    assert any(batch["query"].startswith("阿里千问 ") for batch in plan["batches"])
    assert all(batch["search_filters"]["allcompanies"] == "" for batch in plan["batches"])
    assert "数据交付负责人" in terms.precision_titles
    assert "后训练数据策略" in direction_rules
```

- [ ] **Step 3: Run guardrail test**

Run:

```powershell
python -m pytest tests/test_maimai_hunyuan_generalization_guardrail.py -q
```

Expected: pass.

---

### Task 8: Full Verification And Cleanup

**Files:**
- Modify: `tasks/todo.md`
- Optional modify: `memory/error-log.md` only if a non-obvious implementation error occurs.

- [ ] **Step 1: Run all focused Maimai campaign tests**

Run:

```powershell
python -m pytest tests/test_maimai_search_filter_clearing.py tests/test_maimai_company_registry.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_rank_generic.py tests/test_maimai_campaign_delivery_report_generic.py tests/test_maimai_campaign_feedback.py tests/test_maimai_hunyuan_generalization_guardrail.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py -q
```

Expected: pass.

- [ ] **Step 2: Run broad regression**

Run:

```powershell
python -m pytest tests scripts -q
```

Expected: pass. If unrelated dirty worktree files cause failures, record exact failing tests and isolate whether this plan caused them.

- [ ] **Step 3: Diff hygiene**

Run:

```powershell
git diff --check
```

Expected: no output.

- [ ] **Step 4: Update task ledger**

Update `tasks/todo.md` Review with:

```markdown
- 已实现 JD-driven Maimai campaign 通用化第一阶段：query-only 清空结构化过滤、公司/产品线 registry、通用 search-plan/rank/delivery/feedback 合同和混元 guardrail。
- 验证：`python -m pytest tests scripts -q` 通过；`git diff --check` 通过。
- 未执行真实脉脉搜索；未修改历史 raw；未写主库 `data/talent.db`。
```

## Self-Review

- Spec coverage: covered AI Infra residue, company/product shorthand mapping, query-only filter clearing, report/ranking generalization, and feedback loop.
- Placeholder scan: no `TBD`, `TODO`, or undefined future-only steps remain. Task 4 deliberately uses a temporary wrapper only before the explicit replacement step; do not route orchestrator to it until full generic scoring is complete.
- Type consistency: `CompanyProductMapping`, `RankTerms`, `build_generic_search_plan`, `direction_rules_from_strategy`, and `compile_strategy_adjustment` are introduced before later tests consume them.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-22-maimai-jd-campaign-generalization.md`.

Execution options:

1. Subagent-Driven: dispatch a fresh agent per task, review each task before moving on.
2. Inline Execution: execute this plan in the current session task-by-task, with focused tests after every task.

Recommended execution order is Task 1 first, then Task 2 and Task 3. Do not start Task 4 routing until Task 1-3 pass.
