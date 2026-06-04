"""猎聘宽召回 adaptive 搜索离线规划。

只读取 campaign strategy，不连接 CDP，不触发猎聘请求，不写数据库。
"""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts.liepin_api_contract import DEFAULT_SEARCH_PARAMS
from scripts.liepin_campaign import atomic_write_json, ensure_campaign


STRATEGY_MODE = "liepin_broad_recall_adaptive_v1"

DEFAULT_ADAPTIVE_POLICY: dict[str, Any] = {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "search_wave_max_pages": 50,
    "account_day_page_guardrail": 500,
    "good_ratio_continue": 0.3,
    "good_ratio_observe": 0.1,
    "max_consecutive_low_quality_pages": 2,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _unique_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8-sig",
    )


def is_adaptive_strategy(strategy: dict[str, Any]) -> bool:
    return str(strategy.get("strategy_mode") or "").strip() == STRATEGY_MODE


def adaptive_policy_from_strategy(strategy: dict[str, Any]) -> dict[str, Any]:
    raw = strategy.get("adaptive_search") if isinstance(strategy.get("adaptive_search"), dict) else {}
    policy = dict(DEFAULT_ADAPTIVE_POLICY)
    for key in DEFAULT_ADAPTIVE_POLICY:
        if key in raw:
            policy[key] = raw[key]
    policy["probe_pages"] = max(1, int(policy["probe_pages"]))
    policy["unit_max_pages"] = max(policy["probe_pages"], int(policy["unit_max_pages"]))
    policy["search_wave_max_pages"] = max(1, int(policy["search_wave_max_pages"]))
    policy["account_day_page_guardrail"] = max(1, int(policy["account_day_page_guardrail"]))
    policy["max_consecutive_low_quality_pages"] = max(1, int(policy["max_consecutive_low_quality_pages"]))
    policy["good_ratio_continue"] = float(policy["good_ratio_continue"])
    policy["good_ratio_observe"] = float(policy["good_ratio_observe"])
    return policy


def _company_terms(strategy: dict[str, Any]) -> list[str]:
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


def _keyword_packages(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    packages = strategy.get("keyword_packages")
    if not isinstance(packages, list) or not packages:
        raise ValueError("strategy.keyword_packages must be a non-empty list")
    valid = [item for item in packages if isinstance(item, dict)]
    if not valid:
        raise ValueError("strategy.keyword_packages must include at least one object")
    return valid


def _condition_overrides(strategy: dict[str, Any]) -> dict[str, Any]:
    raw = strategy.get("condition_overrides") if isinstance(strategy.get("condition_overrides"), dict) else {}
    allowed = set(DEFAULT_SEARCH_PARAMS) | {"jobId"}
    overrides: dict[str, Any] = {}
    for key, value in raw.items():
        if key not in allowed:
            raise ValueError(f"unsupported condition_overrides key: {key}")
        overrides[key] = deepcopy(value)
    return overrides


def _query(company: str, package: dict[str, Any]) -> str:
    explicit = package.get("query_terms")
    if isinstance(explicit, list) and explicit:
        parts = [company, *_unique_text(explicit)]
    else:
        parts = [
            company,
            *_unique_text(package.get("position_terms") or [])[:2],
            *_unique_text(package.get("keywords") or [])[:2],
        ]
    return " ".join(_unique_text(parts))


def build_search_units(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    if not is_adaptive_strategy(strategy):
        raise ValueError(f"strategy_mode must be {STRATEGY_MODE}")
    policy = adaptive_policy_from_strategy(strategy)
    companies = _company_terms(strategy)
    packages = _keyword_packages(strategy)
    overrides = _condition_overrides(strategy)
    unit_order = str(strategy.get("unit_order") or "keyword_first").strip()
    pairs = (
        [(company, package) for company in companies for package in packages]
        if unit_order == "company_first"
        else [(company, package) for package in packages for company in companies]
    )

    units: list[dict[str, Any]] = []
    for company, package in pairs:
        query = _query(company, package)
        search_overrides = dict(overrides)
        search_overrides["keyword"] = query
        search_overrides["pageSize"] = int(search_overrides.get("pageSize") or 30)
        units.append(
            {
                "schema": "liepin_search_unit_v1",
                "unit_id": f"unit-{len(units) + 1:06d}",
                "strategy_mode": STRATEGY_MODE,
                "source_company_terms": [company],
                "keyword_package": str(package.get("id") or ""),
                "priority": str(package.get("priority") or "P1"),
                "position_terms": _unique_text(package.get("position_terms") or []),
                "broad_keywords": _unique_text(package.get("keywords") or []),
                "long_tail_keywords": _unique_text(package.get("long_tail_keywords") or []),
                "query": query,
                "search_params_overrides": search_overrides,
                "page_size": search_overrides["pageSize"],
                "probe_pages": policy["probe_pages"],
                "unit_max_pages": policy["unit_max_pages"],
                "planned_pages": list(range(policy["probe_pages"])),
                "adaptive_search": deepcopy(policy),
            }
        )
    return units


def split_units_into_waves(units: list[dict[str, Any]], *, max_pages: int) -> list[dict[str, Any]]:
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")
    waves: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_pages = 0
    for unit in units:
        pages = len(unit.get("planned_pages") or [])
        if pages <= 0:
            raise ValueError(f"unit {unit.get('unit_id')} must include planned pages")
        if pages > max_pages:
            raise ValueError(f"unit {unit.get('unit_id')} exceeds search_wave_max_pages")
        if current and current_pages + pages > max_pages:
            waves.append(
                {
                    "wave_id": f"search-wave-{len(waves) + 1:03d}",
                    "batches": current,
                    "page_count": current_pages,
                }
            )
            current = []
            current_pages = 0
        current.append(unit)
        current_pages += pages
    if current:
        waves.append(
            {
                "wave_id": f"search-wave-{len(waves) + 1:03d}",
                "batches": current,
                "page_count": current_pages,
            }
        )
    return waves


def _live_gate_sidecar(wave: dict[str, Any]) -> dict[str, Any]:
    batches: list[dict[str, Any]] = []
    for unit in wave["batches"]:
        batches.append(
            {
                "unit_id": unit["unit_id"],
                "query": unit["query"],
                "pages": unit["planned_pages"],
                "search_params_overrides": unit["search_params_overrides"],
                "adaptive_search": unit["adaptive_search"],
                "unit_max_pages": unit["unit_max_pages"],
            }
        )
    return {
        "schema": "liepin_adaptive_search_live_gate_plan_v1",
        "wave_id": wave["wave_id"],
        "strategy_mode": STRATEGY_MODE,
        "page_count": wave["page_count"],
        "batches": batches,
        "no_live_request": True,
    }


def _write_wave_plan(root: Path, units: list[dict[str, Any]], policy: dict[str, Any]) -> dict[str, Any]:
    wave_dir = root / "raw" / "search-live-runs"
    waves = split_units_into_waves(units, max_pages=int(policy["search_wave_max_pages"]))
    enriched: list[dict[str, Any]] = []
    for wave in waves:
        sidecar_path = wave_dir / f"{wave['wave_id']}-plan.json"
        atomic_write_json(sidecar_path, _live_gate_sidecar(wave))
        enriched.append({**wave, "live_gate_plan_path": sidecar_path.as_posix()})
    plan = {
        "schema": "liepin_adaptive_search_wave_plan_v1",
        "strategy_mode": STRATEGY_MODE,
        "generated_at": _now(),
        "unit_count": len(units),
        "probe_page_count": sum(len(unit["planned_pages"]) for unit in units),
        "max_potential_page_count": sum(int(unit["unit_max_pages"]) for unit in units),
        "wave_count": len(enriched),
        "waves": enriched,
        "no_live_request": True,
        "no_database_write": True,
    }
    atomic_write_json(wave_dir / "wave-plan.json", plan)
    return plan


def _write_report(root: Path, plan: dict[str, Any]) -> None:
    report = {
        "schema": "liepin_broad_recall_plan_report_v1",
        "strategy_mode": STRATEGY_MODE,
        "generated_at": plan["generated_at"],
        "unit_count": plan["unit_count"],
        "probe_page_count": plan["probe_page_count"],
        "max_potential_page_count": plan["max_potential_page_count"],
        "wave_count": plan["wave_count"],
        "no_live_request": True,
        "no_cdp_connection": True,
        "no_database_write": True,
    }
    atomic_write_json(root / "reports" / "broad-recall-plan.json", report)
    lines = [
        "# 猎聘宽召回 adaptive 搜索规划",
        "",
        f"- 生成时间：{report['generated_at']}",
        f"- Search units：{report['unit_count']}",
        f"- Probe 页数：{report['probe_page_count']}",
        f"- 最大潜在页数：{report['max_potential_page_count']}",
        f"- Waves：{report['wave_count']}",
        "- 边界：不触发猎聘请求，不连接 CDP，不写数据库。",
        "",
        "## 下一步",
        "",
        "- 经确认后再实现单 wave live runner，并继续沿用现有停机和恢复边界。",
    ]
    md_path = root / "reports" / "broad-recall-plan.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def plan_adaptive_search(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    strategy = _load_json(root / "strategy.json")
    units = build_search_units(strategy)
    policy = adaptive_policy_from_strategy(strategy)
    paths = ensure_campaign(root)
    _write_jsonl(paths.root / "search-units.jsonl", units)
    wave_plan = _write_wave_plan(paths.root, units, policy)
    _write_report(paths.root, wave_plan)
    return {
        "schema": "liepin_adaptive_search_plan_v1",
        "strategy_mode": STRATEGY_MODE,
        "campaign_root": paths.root.as_posix(),
        "unit_count": wave_plan["unit_count"],
        "probe_page_count": wave_plan["probe_page_count"],
        "max_potential_page_count": wave_plan["max_potential_page_count"],
        "wave_count": wave_plan["wave_count"],
        "search_units": (paths.root / "search-units.jsonl").as_posix(),
        "wave_plan": (paths.root / "raw" / "search-live-runs" / "wave-plan.json").as_posix(),
        "report": (paths.root / "reports" / "broad-recall-plan.json").as_posix(),
        "no_live_request": True,
        "no_cdp_connection": True,
        "no_database_write": True,
    }
