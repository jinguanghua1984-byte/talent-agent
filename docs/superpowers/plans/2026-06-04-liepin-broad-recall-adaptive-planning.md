# Liepin Broad Recall Adaptive Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为猎聘新增 `strategy_mode=liepin_broad_recall_adaptive_v1` 离线宽召回搜索规划，生成 search units、wave plan 和公开摘要，不触发 live 请求或数据库写入。

**Architecture:** 新增 `scripts/liepin_broad_recall_adaptive.py` 作为纯离线 planner，复用 `scripts.liepin_api_contract.DEFAULT_SEARCH_PARAMS` 做参数白名单校验，复用 `scripts.liepin_campaign.ensure_campaign` 管理 campaign 目录。`scripts/liepin_campaign_orchestrator.py` 只新增 `plan-adaptive-search` 命令委托，skill/workflow 文档只声明规划边界，现有固定 `jobId` 页计划和 live search 行为保持不变。

**Tech Stack:** Python stdlib, existing Liepin campaign helpers, pytest, Markdown docs.

---

### Task 1: Planner Strategy Validation and Unit Generation

**Files:**
- Create: `tests/test_liepin_broad_recall_adaptive.py`
- Create: `scripts/liepin_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing tests for strategy detection and units**

Add `tests/test_liepin_broad_recall_adaptive.py`:

```python
import pytest

from scripts.liepin_broad_recall_adaptive import (
    STRATEGY_MODE,
    adaptive_policy_from_strategy,
    build_search_units,
    is_adaptive_strategy,
)


def _strategy() -> dict:
    return {
        "strategy_mode": STRATEGY_MODE,
        "strategy_version": "2026-06-04",
        "unit_order": "company_first",
        "company_pools": {"target": ["腾讯", "阿里云"]},
        "keyword_packages": [
            {
                "id": "ai-product",
                "priority": "P0",
                "position_terms": ["产品经理", "产品负责人"],
                "keywords": ["大模型", "AI 应用"],
                "long_tail_keywords": ["Agent"],
            }
        ],
        "condition_overrides": {
            "wantDqs": "010",
            "eduLevels": ["040"],
            "workYearsLow": "5",
            "workYearsHigh": "15",
            "sortType": "0",
            "resumetype": "0",
        },
        "adaptive_search": {
            "probe_pages": 2,
            "unit_max_pages": 15,
            "search_wave_max_pages": 50,
            "account_day_page_guardrail": 500,
        },
    }


def test_build_search_units_for_company_first_strategy() -> None:
    units = build_search_units(_strategy())

    assert len(units) == 2
    assert units[0]["schema"] == "liepin_search_unit_v1"
    assert units[0]["strategy_mode"] == STRATEGY_MODE
    assert units[0]["unit_id"] == "unit-000001"
    assert units[0]["source_company_terms"] == ["腾讯"]
    assert units[1]["source_company_terms"] == ["阿里云"]
    assert units[0]["keyword_package"] == "ai-product"
    assert units[0]["planned_pages"] == [0, 1]
    assert units[0]["probe_pages"] == 2
    assert units[0]["unit_max_pages"] == 15
    assert units[0]["search_params_overrides"]["keyword"] == "腾讯 产品经理 产品负责人 大模型 AI 应用"
    assert units[0]["search_params_overrides"]["wantDqs"] == "010"
    assert units[0]["search_params_overrides"]["pageSize"] == 30


def test_adaptive_policy_uses_safe_defaults_and_bounds() -> None:
    policy = adaptive_policy_from_strategy({"adaptive_search": {"probe_pages": 0, "unit_max_pages": 1}})

    assert policy["probe_pages"] == 1
    assert policy["unit_max_pages"] == 1
    assert policy["search_wave_max_pages"] == 50
    assert policy["account_day_page_guardrail"] == 500


def test_rejects_unknown_condition_override_key() -> None:
    strategy = _strategy()
    strategy["condition_overrides"] = {"cookie": "secret"}

    with pytest.raises(ValueError, match="unsupported condition_overrides key: cookie"):
        build_search_units(strategy)


def test_strategy_detection_is_explicit() -> None:
    assert is_adaptive_strategy({"strategy_mode": STRATEGY_MODE}) is True
    assert is_adaptive_strategy({"strategy_mode": "broad_recall_adaptive_v1"}) is False
```

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'scripts.liepin_broad_recall_adaptive'`.

- [ ] **Step 3: Implement minimal planner functions**

Create `scripts/liepin_broad_recall_adaptive.py`:

```python
"""猎聘宽召回 adaptive 搜索离线规划。

只读取 campaign strategy，不连接 CDP，不触发猎聘请求，不写数据库。
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from scripts.liepin_api_contract import DEFAULT_SEARCH_PARAMS


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


def _unique_text(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


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
    return [item for item in packages if isinstance(item, dict)]


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
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/liepin_broad_recall_adaptive.py tests/test_liepin_broad_recall_adaptive.py
git commit -m "Add Liepin adaptive search unit planning"
```

### Task 2: Wave Plan and Report Writers

**Files:**
- Modify: `tests/test_liepin_broad_recall_adaptive.py`
- Modify: `scripts/liepin_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing tests for output files**

Append to `tests/test_liepin_broad_recall_adaptive.py`:

```python
import json
from pathlib import Path

from scripts.liepin_broad_recall_adaptive import plan_adaptive_search


def test_plan_adaptive_search_writes_units_waves_and_reports(tmp_path: Path) -> None:
    root = tmp_path / "liepin-demo"
    root.mkdir()
    (root / "strategy.json").write_text(json.dumps(_strategy(), ensure_ascii=False), encoding="utf-8")

    result = plan_adaptive_search(root)

    assert result["schema"] == "liepin_adaptive_search_plan_v1"
    assert result["unit_count"] == 2
    assert result["probe_page_count"] == 4
    assert result["no_live_request"] is True
    assert result["no_database_write"] is True
    assert (root / "search-units.jsonl").exists()
    aggregate = json.loads((root / "raw/search-live-runs/wave-plan.json").read_text(encoding="utf-8-sig"))
    assert aggregate["schema"] == "liepin_adaptive_search_wave_plan_v1"
    assert aggregate["wave_count"] == 1
    sidecar = Path(aggregate["waves"][0]["live_gate_plan_path"])
    assert sidecar.exists()
    assert json.loads(sidecar.read_text(encoding="utf-8-sig"))["wave_id"] == "search-wave-001"
    assert (root / "reports/broad-recall-plan.json").exists()
    md = (root / "reports/broad-recall-plan.md").read_text(encoding="utf-8-sig")
    assert "不触发猎聘请求" in md
    assert "不写数据库" in md
```

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py::test_plan_adaptive_search_writes_units_waves_and_reports -q
```

Expected: fails because `plan_adaptive_search` is missing.

- [ ] **Step 3: Implement file writers and planner entrypoint**

Append to `scripts/liepin_broad_recall_adaptive.py`:

```python
import json
from datetime import datetime
from pathlib import Path

from scripts.liepin_campaign import atomic_write_json, ensure_campaign


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON must be an object: {path}")
    return data


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8-sig",
    )


def split_units_into_waves(units: list[dict[str, Any]], *, max_pages: int) -> list[dict[str, Any]]:
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
            waves.append({"wave_id": f"search-wave-{len(waves) + 1:03d}", "batches": current, "page_count": current_pages})
            current = []
            current_pages = 0
        current.append(unit)
        current_pages += pages
    if current:
        waves.append({"wave_id": f"search-wave-{len(waves) + 1:03d}", "batches": current, "page_count": current_pages})
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
    paths = ensure_campaign(campaign_root)
    strategy = _load_json(paths.strategy)
    units = build_search_units(strategy)
    policy = adaptive_policy_from_strategy(strategy)
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
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py -q
```

Expected: all tests in the file pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/liepin_broad_recall_adaptive.py tests/test_liepin_broad_recall_adaptive.py
git commit -m "Write Liepin adaptive search wave plans"
```

### Task 3: Orchestrator Command

**Files:**
- Modify: `tests/test_liepin_campaign_orchestrator.py`
- Modify: `scripts/liepin_campaign_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator test**

Append to `tests/test_liepin_campaign_orchestrator.py`:

```python
def test_plan_adaptive_search_command_delegates_without_live_side_effects(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_plan_adaptive_search(campaign_root):
        calls.append(campaign_root)
        return {
            "schema": "liepin_adaptive_search_plan_v1",
            "campaign_root": str(campaign_root),
            "unit_count": 2,
            "no_live_request": True,
            "no_database_write": True,
        }

    monkeypatch.setattr(orchestrator, "plan_adaptive_search", fake_plan_adaptive_search)

    result = orchestrator.main(["plan-adaptive-search", "--campaign-root", str(tmp_path / "liepin-demo")])

    assert result == 0
    assert calls == [str(tmp_path / "liepin-demo")]
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema"] == "liepin_adaptive_search_plan_v1"
    assert payload["no_live_request"] is True
    assert payload["no_database_write"] is True
```

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py::test_plan_adaptive_search_command_delegates_without_live_side_effects -q
```

Expected: fails because `plan-adaptive-search` is not registered.

- [ ] **Step 3: Wire command**

In `scripts/liepin_campaign_orchestrator.py`, add the import:

```python
from scripts.liepin_broad_recall_adaptive import plan_adaptive_search  # noqa: E402
```

Register the subcommand near `plan-pages`:

```python
    adaptive_plan = subparsers.add_parser("plan-adaptive-search")
    adaptive_plan.add_argument("--campaign-root", required=True)
```

Add dispatch:

```python
        elif args.command == "plan-adaptive-search":
            result = plan_adaptive_search(args.campaign_root)
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py::test_plan_adaptive_search_command_delegates_without_live_side_effects -q
```

Expected: test passes.

- [ ] **Step 5: Commit**

```bash
git add scripts/liepin_campaign_orchestrator.py tests/test_liepin_campaign_orchestrator.py
git commit -m "Wire Liepin adaptive search planning command"
```

### Task 4: CLI Smoke Test Against a Temporary Campaign

**Files:**
- Modify: `tests/test_liepin_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing CLI smoke test**

Append to `tests/test_liepin_broad_recall_adaptive.py`:

```python
import subprocess
import sys


def test_plan_adaptive_search_cli_smoke(tmp_path: Path) -> None:
    root = tmp_path / "liepin-demo"
    root.mkdir()
    (root / "strategy.json").write_text(json.dumps(_strategy(), ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_campaign_orchestrator",
            "plan-adaptive-search",
            "--campaign-root",
            str(root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["unit_count"] == 2
    assert payload["no_live_request"] is True
    assert payload["no_cdp_connection"] is True
    assert payload["no_database_write"] is True
    assert not (root / "talent.db").exists()
```

- [ ] **Step 2: Run RED or GREEN According to Task Order**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py::test_plan_adaptive_search_cli_smoke -q
```

Expected after Task 3: passes. If it fails, the error should point to command registration or output serialization.

- [ ] **Step 3: Keep CLI output stable**

If the smoke test fails because paths or JSON keys differ, update `plan_adaptive_search()` return payload to include exactly:

```python
{
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
```

- [ ] **Step 4: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py tests/test_liepin_campaign_orchestrator.py -q
```

Expected: focused tests pass.

- [ ] **Step 5: Commit**

```bash
git add scripts/liepin_broad_recall_adaptive.py tests/test_liepin_broad_recall_adaptive.py
git commit -m "Verify Liepin adaptive planning CLI"
```

### Task 5: Skill and Workflow Contract Updates

**Files:**
- Modify: `agents/skills/liepin-talent-search-campaign/SKILL.md`
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Write failing architecture test**

Append to `tests/test_agent_architecture.py`:

```python
def test_liepin_contracts_define_broad_recall_adaptive_planning_boundary():
    root = Path(__file__).resolve().parents[1]
    skill = (
        root
        / "agents"
        / "skills"
        / "liepin-talent-search-campaign"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        root
        / "agents"
        / "workflows"
        / "liepin-unattended-campaign"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    assert "liepin_broad_recall_adaptive_v1" in skill
    assert "plan-adaptive-search" in skill
    assert "不触发猎聘请求" in skill
    assert "liepin_broad_recall_adaptive_v1" in workflow
    assert "plan-adaptive-search" in workflow
    assert "不写数据库" in workflow
```

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_liepin_contracts_define_broad_recall_adaptive_planning_boundary -q
```

Expected: fails because docs do not describe the new planning boundary.

- [ ] **Step 3: Update skill contract**

In `agents/skills/liepin-talent-search-campaign/SKILL.md`, add this section before “自动交接”:

~~~markdown
## 宽召回 adaptive 规划边界

- 当用户要求扩候选池、宽召回、多公司多关键词、对标脉脉宽召回，或明确设置 `strategy_mode=liepin_broad_recall_adaptive_v1` 时，先进入离线规划阶段。
- 离线规划命令为：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-adaptive-search --campaign-root data/campaigns/<campaign_id>
```

- `plan-adaptive-search` 只读取 `strategy.json`，生成 `search-units.jsonl`、`raw/search-live-runs/wave-plan.json`、wave sidecar 和 `reports/broad-recall-plan.*`。
- 该阶段不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储，不写 Campaign DB，不写主库 `data/talent.db`。
- 后续 live 搜索必须另起确认点；不得由规划命令自动升级为 live execution。
~~~

- [ ] **Step 4: Update workflow contract**

In `agents/workflows/liepin-unattended-campaign/AGENT.md`, add a new section after S3:

~~~markdown
### S3a 宽召回 adaptive 搜索规划

当 `strategy.json` 明确设置 `strategy_mode=liepin_broad_recall_adaptive_v1` 时，先运行离线规划：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-adaptive-search --campaign-root data/campaigns/<campaign_id>
```

该阶段只读取 `strategy.json`，生成 `search-units.jsonl`、`raw/search-live-runs/wave-plan.json`、wave sidecar 和 `reports/broad-recall-plan.*`。它不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储，不写数据库。

S3a 完成后停止在确认点。后续要执行 live 搜索时，必须由用户单独确认，并继续沿用 S4 的登录、验证码、安全页、HTTP 403/429/432、非 JSON、`flag != 1` 和模板漂移停机规则。
~~~

- [ ] **Step 5: Run GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_liepin_contracts_define_broad_recall_adaptive_planning_boundary -q
```

Expected: test passes.

- [ ] **Step 6: Commit**

```bash
git add agents/skills/liepin-talent-search-campaign/SKILL.md agents/workflows/liepin-unattended-campaign/AGENT.md tests/test_agent_architecture.py
git commit -m "Document Liepin adaptive planning boundary"
```

### Task 6: Focused and Full Verification

**Files:**
- Verify only; no source edits expected.

- [ ] **Step 1: Run focused Liepin tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_broad_recall_adaptive.py tests/test_liepin_campaign_orchestrator.py tests/test_agent_architecture.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run sensitive storage scan**

Run:

```bash
rg -n "cookies\(|context\.cookies|document\.cookie|localStorage|sessionStorage|Authorization|Bearer" scripts/liepin_*.py tests/test_liepin_*.py agents/skills/liepin-talent-search-campaign agents/workflows/liepin-unattended-campaign
```

Expected: no production code reads browser sensitive storage; allowed hits are negative assertions or documentation boundaries.

- [ ] **Step 3: Run whitespace verification**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Run full suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full suite passes. Existing unrelated warnings may remain if already present before this plan.

- [ ] **Step 5: Commit verification record**

Update `tasks/todo.md` with concise Review containing exact focused/full test counts and boundary scan result, then commit:

```bash
git add tasks/todo.md
git commit -m "Record Liepin adaptive planning verification"
```

### Task 7: Implementation Completion Review

**Files:**
- Inspect Git state and produced docs.

- [ ] **Step 1: Confirm no database artifacts are staged**

Run:

```bash
git status --short
```

Expected: staged/modified files are code, tests, docs, and `tasks/todo.md`; no `data/campaigns/*/talent.db` and no `data/talent.db`.

- [ ] **Step 2: Confirm planner artifact names**

Run the CLI against a temporary directory and inspect names:

```bash
tmpdir="$(mktemp -d)"
mkdir -p "$tmpdir/campaign"
cp docs/superpowers/specs/2026-06-04-liepin-broad-recall-adaptive-planning-design.md "$tmpdir/spec-copy.md"
.venv/bin/python - <<'PY' "$tmpdir/campaign"
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
strategy = {
    "strategy_mode": "liepin_broad_recall_adaptive_v1",
    "company_pools": {"target": ["腾讯"]},
    "keyword_packages": [{"id": "ai-product", "position_terms": ["产品经理"], "keywords": ["大模型"]}],
    "condition_overrides": {"wantDqs": "010"},
}
(root / "strategy.json").write_text(json.dumps(strategy, ensure_ascii=False), encoding="utf-8")
PY
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-adaptive-search --campaign-root "$tmpdir/campaign"
test -f "$tmpdir/campaign/search-units.jsonl"
test -f "$tmpdir/campaign/raw/search-live-runs/wave-plan.json"
test -f "$tmpdir/campaign/raw/search-live-runs/search-wave-001-plan.json"
test -f "$tmpdir/campaign/reports/broad-recall-plan.json"
test -f "$tmpdir/campaign/reports/broad-recall-plan.md"
test ! -f "$tmpdir/campaign/talent.db"
```

Expected: all `test -f` checks pass and `talent.db` does not exist.

- [ ] **Step 3: Final commit**

If Task 6 did not create the final commit, commit remaining implementation files:

```bash
git add scripts/liepin_broad_recall_adaptive.py scripts/liepin_campaign_orchestrator.py tests/test_liepin_broad_recall_adaptive.py tests/test_liepin_campaign_orchestrator.py tests/test_agent_architecture.py agents/skills/liepin-talent-search-campaign/SKILL.md agents/workflows/liepin-unattended-campaign/AGENT.md tasks/todo.md
git commit -m "Complete Liepin broad recall adaptive planning"
```

Expected: commit succeeds and excludes unrelated BOSS/CodeGraph documents unless the user separately asks to include them.

---

## Self-Review

- Spec coverage: strategy mode, search unit contract, wave plan, report, skill/workflow boundary, no live request, no DB write, and validation gates are each covered by a task.
- Placeholder scan: no placeholder sections are required during execution; each code step names concrete files, functions, commands, and expected output.
- Type consistency: public names are `STRATEGY_MODE`, `is_adaptive_strategy`, `adaptive_policy_from_strategy`, `build_search_units`, `split_units_into_waves`, and `plan_adaptive_search`; orchestrator command is `plan-adaptive-search`.
