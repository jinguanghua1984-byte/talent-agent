# Maimai AI Infra V2 Cold-Start Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 V2 冷启动 campaign 流水线：独立工作库、可恢复搜索单元、wave 导入 ledger、列表初筛报告、人工审核输入、详情 wave 恢复和最终寻访报告。

**Architecture:** 保持现有 `maimai_ai_infra_search_plan.py`、`maimai_ai_infra_search_runner.py`、`maimai_ai_infra_pipeline.py`、`maimai_ai_infra_rank.py` 的职责边界，新增 `maimai_ai_infra_campaign.py` 管理 campaign 目录、状态、原子写入和 ledger。真实脉脉搜索和详情动作仍受人工授权门禁保护；本计划先实现离线和可恢复基础设施，再接入长时执行参数。

**Tech Stack:** Python 3、SQLite `TalentDB`、JSON/JSONL、pytest、现有脉脉搜索 API 字段白名单、`maimai-scraper` popup 详情路径。

---

## File Structure

- Create: `scripts/maimai_ai_infra_campaign.py` — campaign 路径、manifest、原子写入、进度重建、事件日志、import/detail ledger。
- Create: `configs/maimai-ai-infra-v2-cold-start-strategy.json` — V2 搜索策略、目标 funnel、wave 配置、unit 配额。
- Create: `scripts/maimai_ai_infra_review.py` — 读取人工审核 JSON，校验 `detail_now/hold/reject` 并输出详情候选 ID。
- Modify: `.gitignore` — 忽略 `data/campaigns/`。
- Modify: `scripts/maimai_ai_infra_search_plan.py` — 支持 V2 unit/wave 输出 `search-units.jsonl`，生成显式 `search_filters`。
- Modify: `scripts/maimai_ai_infra_search_runner.py` — 支持 campaign root、page task、原子 raw、progress、resume、runtime 切片。
- Modify: `scripts/maimai_ai_infra_pipeline.py` — 支持 campaign root、wave contacts、dry-run/apply ledger、初版/最终报告编排。
- Modify: `scripts/maimai_ai_infra_rank.py` — 增加 `list` 与 `detailed` 两种评分模式。
- Modify: `scripts/maimai_detail_targets.py` — 支持从人工审核结果生成详情 wave 任务包。
- Test: `tests/test_maimai_ai_infra_campaign.py` — campaign helper、原子写入、resume 重建、ledger 幂等。
- Test: `tests/test_maimai_ai_infra_strategy.py` — V2 策略和 search unit 编译。
- Test: `tests/test_maimai_ai_infra_runner.py` — page task patch、resume、异常停止。
- Test: `tests/test_maimai_ai_infra_pipeline.py` — wave contacts、dry-run/apply ledger、报告输出。
- Test: `tests/test_maimai_ai_infra_review.py` — 人工审核输入校验。
- Test: `tests/test_maimai_detail_targets.py` — review -> detail wave targets。

## Constraints

- 不触发真实脉脉搜索，除非用户明确授权 `确认执行 AI Infra V2 列表搜索`。
- 不写入任何 DB，除非 dry-run clean 且用户明确授权对应 apply。
- 不提交 `data/campaigns/`、raw capture、campaign DB 或真实候选人数据。
- 不写 `search.age`，年龄范围仅允许 `min_age/max_age`。
- 搜索默认只抓 `24-40` 周岁；评分中 `24-35` 是最佳区间，`35-40` 是第二梯队，`40+` 必须淘汰。
- 毕业院校是硬门槛：必须命中 `985`、`211`、`QS Top500` 或海外 Top500；专科和非重点院校不进入详情任务包或最终推荐。
- Resume 必须以已落盘的 page raw 为准，不能只信任内存状态。

## Task 1: Campaign Helper 和数据安全边界

**Files:**
- Modify: `.gitignore`
- Create: `scripts/maimai_ai_infra_campaign.py`
- Create: `tests/test_maimai_ai_infra_campaign.py`

- [ ] **Step 1: 写 campaign 目录和 gitignore 红测**

Add to `tests/test_maimai_ai_infra_campaign.py`:

```python
from pathlib import Path

from scripts.maimai_ai_infra_campaign import CampaignPaths, ensure_campaign


def test_campaign_paths_create_expected_layout(tmp_path: Path):
    root = tmp_path / "ai-infra-v2-smoke"
    paths = ensure_campaign(root, campaign_id="ai-infra-v2-smoke")

    assert paths.root == root
    assert paths.db == root / "talent.db"
    assert paths.raw_search_dir == root / "raw" / "search"
    assert paths.contacts_dir == root / "raw" / "contacts"
    assert paths.state_dir == root / "state"
    assert paths.reports_dir == root / "reports"
    assert paths.review_dir == root / "review"
    assert paths.manifest.exists()


def test_gitignore_excludes_campaign_runtime_data():
    text = Path(".gitignore").read_text(encoding="utf-8")
    assert "data/campaigns/" in text
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py -q
```

Expected: FAIL because helper and ignore entry do not exist.

- [ ] **Step 2: 实现 `CampaignPaths` 和 `ensure_campaign()`**

Create `scripts/maimai_ai_infra_campaign.py` with:

```python
"""AI Infra V2 campaign runtime helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CampaignPaths:
    root: Path
    campaign_id: str
    manifest: Path
    db: Path
    strategy: Path
    search_plan: Path
    search_units: Path
    state_dir: Path
    raw_dir: Path
    raw_search_dir: Path
    contacts_dir: Path
    reports_dir: Path
    review_dir: Path
    search_progress: Path
    search_events: Path
    import_ledger: Path
    detail_progress: Path


def campaign_paths(root: str | Path, campaign_id: str | None = None) -> CampaignPaths:
    root_path = Path(root)
    resolved_id = campaign_id or root_path.name
    state_dir = root_path / "state"
    raw_dir = root_path / "raw"
    return CampaignPaths(
        root=root_path,
        campaign_id=resolved_id,
        manifest=root_path / "campaign-manifest.json",
        db=root_path / "talent.db",
        strategy=root_path / "strategy.json",
        search_plan=root_path / "search-plan.json",
        search_units=root_path / "search-units.jsonl",
        state_dir=state_dir,
        raw_dir=raw_dir,
        raw_search_dir=raw_dir / "search",
        contacts_dir=raw_dir / "contacts",
        reports_dir=root_path / "reports",
        review_dir=root_path / "review",
        search_progress=state_dir / "search-progress.json",
        search_events=state_dir / "search-events.jsonl",
        import_ledger=state_dir / "import-ledger.jsonl",
        detail_progress=state_dir / "detail-progress.json",
    )


def atomic_write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    os.replace(tmp, target)


def append_jsonl(path: str | Path, item: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_campaign(root: str | Path, campaign_id: str | None = None) -> CampaignPaths:
    paths = campaign_paths(root, campaign_id)
    for directory in (
        paths.root,
        paths.state_dir,
        paths.raw_dir,
        paths.raw_search_dir,
        paths.contacts_dir,
        paths.reports_dir,
        paths.review_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if not paths.manifest.exists():
        atomic_write_json(paths.manifest, {
            "campaign_id": paths.campaign_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "schema": "maimai_ai_infra_v2_campaign",
        })
    return paths
```

Update `.gitignore`:

```gitignore
data/campaigns/
```

- [ ] **Step 3: 运行测试确认通过**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py -q
```

Expected: PASS.

## Task 2: 原子 page raw、事件日志和 resume 状态重建

**Files:**
- Modify: `scripts/maimai_ai_infra_campaign.py`
- Modify: `tests/test_maimai_ai_infra_campaign.py`

- [ ] **Step 1: 写 page raw 和 progress 红测**

Append tests:

```python
import json

from scripts.maimai_ai_infra_campaign import (
    append_search_event,
    load_completed_pages,
    mark_page_completed,
    page_raw_path,
    read_search_progress,
)


def test_page_raw_atomic_write_marks_completed(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    payload = {"unit_id": "unit-000001", "page": 1, "contacts": [{"id": "u1"}]}

    mark_page_completed(paths, "unit-000001", 1, payload)

    raw = page_raw_path(paths, "unit-000001", 1)
    assert raw.exists()
    assert not raw.with_name(raw.name + ".tmp").exists()
    assert json.loads(raw.read_text(encoding="utf-8-sig"))["contacts"][0]["id"] == "u1"
    progress = read_search_progress(paths)
    assert progress["units"]["unit-000001"]["pages"]["1"]["status"] == "completed"


def test_resume_rebuilds_completed_pages_from_raw_when_progress_missing(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(paths, "unit-000001", 1, {"contacts": []})
    paths.search_progress.unlink()

    completed = load_completed_pages(paths)

    assert completed == {("unit-000001", 1)}


def test_search_events_are_append_only_jsonl(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    append_search_event(paths, {"event": "page_started", "unit_id": "unit-000001", "page": 1})
    append_search_event(paths, {"event": "page_completed", "unit_id": "unit-000001", "page": 1})

    lines = paths.search_events.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "page_started"
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py -q
```

Expected: FAIL because functions do not exist.

- [ ] **Step 2: 实现 page raw 与 progress helper**

Add to `scripts/maimai_ai_infra_campaign.py`:

```python
def page_raw_path(paths: CampaignPaths, unit_id: str, page: int) -> Path:
    return paths.raw_search_dir / unit_id / f"page-{page:03d}.json"


def read_search_progress(paths: CampaignPaths) -> dict[str, Any]:
    if not paths.search_progress.exists():
        return {"campaign_id": paths.campaign_id, "units": {}}
    return json.loads(paths.search_progress.read_text(encoding="utf-8-sig"))


def write_search_progress(paths: CampaignPaths, progress: dict[str, Any]) -> None:
    atomic_write_json(paths.search_progress, progress)


def append_search_event(paths: CampaignPaths, item: dict[str, Any]) -> None:
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **item}
    append_jsonl(paths.search_events, event)


def mark_page_completed(paths: CampaignPaths, unit_id: str, page: int, payload: dict[str, Any]) -> None:
    raw_path = page_raw_path(paths, unit_id, page)
    atomic_write_json(raw_path, payload)
    progress = read_search_progress(paths)
    unit = progress.setdefault("units", {}).setdefault(unit_id, {"pages": {}, "status": "running"})
    unit.setdefault("pages", {})[str(page)] = {
        "status": "completed",
        "raw_path": str(raw_path),
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_search_progress(paths, progress)
    append_search_event(paths, {"event": "page_completed", "unit_id": unit_id, "page": page})


def load_completed_pages(paths: CampaignPaths) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    for raw_path in paths.raw_search_dir.glob("unit-*/page-*.json"):
        try:
            page = int(raw_path.stem.removeprefix("page-"))
            completed.add((raw_path.parent.name, page))
        except ValueError:
            continue
    return completed
```

- [ ] **Step 3: 运行测试确认通过**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py -q
```

Expected: PASS.

## Task 3: V2 策略配置和 Search Unit 编译

**Files:**
- Create: `configs/maimai-ai-infra-v2-cold-start-strategy.json`
- Modify: `scripts/maimai_ai_infra_search_plan.py`
- Modify: `tests/test_maimai_ai_infra_strategy.py`

- [ ] **Step 1: 写 V2 search unit 红测**

Append to `tests/test_maimai_ai_infra_strategy.py`:

```python
from scripts.maimai_ai_infra_search_plan import build_search_units


def test_v2_strategy_builds_wave_search_units_without_unconfirmed_fields():
    strategy = {
        "strategy_version": "ai-infra-v2",
        "limits": {"pages_per_batch": 3, "page_size": 30, "max_contacts_per_batch": 90, "max_batches_per_day": 500},
        "company_tiers": {"tier1": ["字节跳动"], "tier2_priority": ["华为"]},
        "company_aliases": {"字节跳动": ["Seed", "AML"], "华为": ["昇腾", "CANN"]},
        "title_batches": {
            "precision": ["大模型训练"],
            "technical": ["异构计算"],
            "generic": ["算法工程师"],
        },
        "keyword_packs": {
            "training": ["分布式训练", "训练框架", "GPU"],
            "inference": ["推理", "算子", "加速"],
        },
        "v2": {
            "wave_size_units": 2,
            "unit_quotas": {"P1_core_precision": 1, "P2_technical": 1, "P3_generic_with_strong_query": 1},
            "default_filters": {
                "degrees": "1,2,3",
                "worktimes_min": "2",
                "worktimes_max": "10",
                "min_age": "24",
                "max_age": "40"
            },
            "school_gate": {"allow_tags": ["985", "211", "qs_top_500", "overseas_top_500"]},
            "age_bands": {"best_min": 24, "best_max": 35, "secondary_max": 40},
        },
        "human_gates": {"strategy_confirmed": False, "auto_apply_after_clean_dry_run": False},
        "exclude_titles": [],
        "exclude_education": [],
    }

    units = build_search_units(strategy)

    assert [unit["unit_id"] for unit in units] == ["unit-000001", "unit-000002", "unit-000003"]
    assert units[0]["wave_id"] == "wave-001"
    assert units[2]["wave_id"] == "wave-002"
    for unit in units:
        assert "age" not in unit["search_filters"]
        assert unit["max_pages"] <= 3
        assert unit["page_size"] == 30
        assert unit["search_filters"]["degrees"] == "1,2,3"
        assert unit["search_filters"]["min_age"] == "24"
        assert unit["search_filters"]["max_age"] == "40"
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py::test_v2_strategy_builds_wave_search_units_without_unconfirmed_fields -q
```

Expected: FAIL because `build_search_units` does not exist.

- [ ] **Step 2: 实现 `build_search_units()`**

Add to `scripts/maimai_ai_infra_search_plan.py`:

```python
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


def _v2_filters(strategy: dict[str, Any], company: str, position: str, query_relation: int) -> dict[str, Any]:
    filters = dict(strategy.get("v2", {}).get("default_filters", {}))
    filters.update({
        "allcompanies": company,
        "positions": position,
        "query_relation": query_relation,
    })
    unknown = sorted(set(filters) - V2_ALLOWED_FILTERS)
    if unknown:
        raise ValueError("unconfirmed V2 search filter fields: " + ", ".join(unknown))
    return filters


def _unit(
    strategy: dict[str, Any],
    unit_index: int,
    wave_size: int,
    batch_type: str,
    tier: str,
    company: str,
    position: str,
    keyword_pack: str,
    query_relation: int,
) -> dict[str, Any]:
    return {
        "unit_id": f"unit-{unit_index:06d}",
        "wave_id": f"wave-{((unit_index - 1) // wave_size) + 1:03d}",
        "batch_type": batch_type,
        "tier": tier,
        "company": company,
        "position": position,
        "keyword_pack": keyword_pack,
        "search_filters": _v2_filters(strategy, company, position, query_relation),
        "query": _quote_terms([*_company_terms(strategy, company), position, *strategy["keyword_packs"][keyword_pack][:4]]),
        "max_pages": min(3, int(strategy["limits"]["pages_per_batch"])),
        "page_size": int(strategy["limits"]["page_size"]),
    }


def build_search_units(strategy: dict[str, Any]) -> list[dict[str, Any]]:
    v2 = strategy.get("v2") or {}
    wave_size = int(v2.get("wave_size_units") or 40)
    quotas = v2.get("unit_quotas") or {}
    titles = strategy["title_batches"]
    tiers = strategy["company_tiers"]
    specs = [
        ("P1_core_precision", "tier1", tiers.get("tier1", []), titles.get("precision", []), ["training", "inference"], 1),
        ("P2_technical", "tier2_priority", tiers.get("tier2_priority", []), titles.get("technical", []), ["inference", "training"], 1),
        ("P3_generic_with_strong_query", "tier1", tiers.get("tier1", []), titles.get("generic", []), ["inference"], 0),
    ]
    units: list[dict[str, Any]] = []
    unit_index = 1
    for batch_type, tier, companies, positions, packs, relation in specs:
        quota = int(quotas.get(batch_type) or 0)
        made = 0
        for company in companies:
            for position in positions:
                for pack in packs:
                    if made >= quota:
                        break
                    units.append(_unit(strategy, unit_index, wave_size, batch_type, tier, company, position, pack, relation))
                    unit_index += 1
                    made += 1
                if made >= quota:
                    break
            if made >= quota:
                break
    return units
```

- [ ] **Step 3: 新增 V2 config**

Create `configs/maimai-ai-infra-v2-cold-start-strategy.json` by copying current AI Infra strategy and adding:

```json
{
  "strategy_version": "ai-infra-v2",
  "v2": {
    "target_funnel": {
      "raw_contacts_min": 15000,
      "raw_contacts_max": 30000,
      "deduped_contacts_min": 8000,
      "deduped_contacts_max": 18000,
      "list_ab_min": 2000,
      "list_ab_max": 4000,
      "detail_targets_min": 600,
      "detail_targets_max": 1200,
      "final_recommended_min": 200,
      "final_recommended_max": 500
    },
    "wave_size_units": 40,
    "unit_quotas": {
      "P1_core_precision": 140,
      "P2_technical": 150,
      "P3_generic_with_strong_query": 100,
      "P4_gap_fill": 60
    },
    "default_filters": {
      "degrees": "1,2,3",
      "only_bachelor_degree": 0,
      "worktimes_min": "2",
      "worktimes_max": "10",
      "min_age": "24",
      "max_age": "40"
    },
    "school_gate": {
      "allow_tags": ["985", "211", "qs_top_500", "overseas_top_500"],
      "reject_tags": ["junior_college", "non_priority_school", "unknown_school_quality"]
    },
    "age_bands": {
      "best_min": 24,
      "best_max": 35,
      "secondary_max": 40
    }
  }
}
```

Keep existing company tiers, aliases, title batches, keyword packs, excludes, and education groups from `configs/maimai-ai-infra-search-strategy.json`.

- [ ] **Step 4: CLI writes search units**

Extend `scripts/maimai_ai_infra_search_plan.py` CLI with optional:

```python
parser.add_argument("--out-units")
```

When provided:

```python
units = build_search_units(strategy)
Path(args.out_units).write_text(
    "\n".join(json.dumps(unit, ensure_ascii=False, sort_keys=True) for unit in units) + "\n",
    encoding="utf-8-sig",
)
```

Run:

```bash
python scripts/maimai_ai_infra_search_plan.py --config configs/maimai-ai-infra-v2-cold-start-strategy.json --out data/output/maimai-ai-infra-v2-search-plan-smoke.json --out-units data/output/maimai-ai-infra-v2-search-units-smoke.jsonl
```

Expected: both files are created; JSONL has V2 units.

- [ ] **Step 5: 运行策略测试**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py -q
```

Expected: PASS.

## Task 4: Runner page task、resume 和 runtime 切片

**Files:**
- Modify: `scripts/maimai_ai_infra_search_runner.py`
- Modify: `tests/test_maimai_ai_infra_runner.py`

- [ ] **Step 1: 写 resume 红测**

Append to `tests/test_maimai_ai_infra_runner.py`:

```python
from scripts.maimai_ai_infra_campaign import ensure_campaign, mark_page_completed
from scripts.maimai_ai_infra_search_runner import iter_pending_page_tasks


def test_iter_pending_page_tasks_skips_completed_raw_pages(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    units = [
        {"unit_id": "unit-000001", "max_pages": 3},
        {"unit_id": "unit-000002", "max_pages": 2},
    ]
    mark_page_completed(paths, "unit-000001", 1, {"contacts": []})

    tasks = list(iter_pending_page_tasks(paths, units))

    assert [(task.unit_id, task.page) for task in tasks] == [
        ("unit-000001", 2),
        ("unit-000001", 3),
        ("unit-000002", 1),
        ("unit-000002", 2),
    ]
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_runner.py::test_iter_pending_page_tasks_skips_completed_raw_pages -q
```

Expected: FAIL because iterator does not exist.

- [ ] **Step 2: 实现 `PageTask` 和 pending iterator**

Add to `scripts/maimai_ai_infra_search_runner.py`:

```python
from dataclasses import dataclass
from scripts.maimai_ai_infra_campaign import CampaignPaths, load_completed_pages


@dataclass(frozen=True)
class PageTask:
    unit_id: str
    page: int
    unit: dict[str, Any]


def iter_pending_page_tasks(paths: CampaignPaths, units: list[dict[str, Any]]) -> list[PageTask]:
    completed = load_completed_pages(paths)
    tasks: list[PageTask] = []
    for unit in units:
        unit_id = str(unit["unit_id"])
        for page in range(1, int(unit.get("max_pages") or 1) + 1):
            if (unit_id, page) not in completed:
                tasks.append(PageTask(unit_id=unit_id, page=page, unit=unit))
    return tasks
```

- [ ] **Step 3: 写 dry-run page task 输出测试**

Append:

```python
from scripts.maimai_ai_infra_search_runner import build_page_task_dry_run


def test_build_page_task_dry_run_patches_unit_filters(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    unit = {
        "unit_id": "unit-000001",
        "query": "\"大模型\" \"推理\"",
        "page_size": 30,
        "search_filters": {"allcompanies": "字节跳动", "positions": "大模型推理", "query_relation": 1},
    }

    result = build_page_task_dry_run(paths, unit, page=2, template=DEFAULT_TEMPLATE)

    search = result["body"]["search"]
    assert search["query"] == "\"大模型\" \"推理\""
    assert search["allcompanies"] == "字节跳动"
    assert search["positions"] == "大模型推理"
    assert search["paginationParam"]["page"] == 2
    assert search["page"] == 1
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_runner.py::test_build_page_task_dry_run_patches_unit_filters -q
```

Expected: FAIL because function does not exist.

- [ ] **Step 4: 实现 dry-run page task**

Add:

```python
def _batch_from_unit(unit: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": unit["unit_id"],
        "query": unit.get("query", ""),
        "page_size": unit.get("page_size", 30),
        "search_filters": unit.get("search_filters", {}),
        "query_relation": unit.get("search_filters", {}).get("query_relation", unit.get("query_relation", 1)),
    }


def build_page_task_dry_run(paths: CampaignPaths, unit: dict[str, Any], page: int, template: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": paths.campaign_id,
        "unit_id": unit["unit_id"],
        "wave_id": unit.get("wave_id", ""),
        "page": page,
        "status": "dry-run-template-only",
        "body": patch_search_body(template, _batch_from_unit(unit), page),
        "contacts": [],
    }
```

- [ ] **Step 5: CLI accepts campaign and resume parameters**

Extend CLI parser:

```python
parser.add_argument("--campaign-root")
parser.add_argument("--units")
parser.add_argument("--resume", action="store_true")
parser.add_argument("--wave")
parser.add_argument("--unit")
parser.add_argument("--max-units", type=int)
parser.add_argument("--max-pages", type=int)
parser.add_argument("--max-runtime-minutes", type=int)
```

For `--dry-run-template-only --campaign-root --units`, runner should:

1. `ensure_campaign()`.
2. Load units JSONL.
3. Filter by `--wave` and `--unit`.
4. Build pending page tasks.
5. Respect `--max-pages`.
6. Write each dry-run page raw using `mark_page_completed()`.

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_runner.py -q
```

Expected: PASS.

## Task 5: Wave contacts、import ledger 和 campaign pipeline

**Files:**
- Modify: `scripts/maimai_ai_infra_campaign.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Modify: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 写从 raw pages 生成 contacts wave 的红测**

Append to `tests/test_maimai_ai_infra_pipeline.py`:

```python
from scripts.maimai_ai_infra_campaign import ensure_campaign, mark_page_completed
from scripts.maimai_ai_infra_pipeline import extract_wave_contacts_from_pages


def test_extract_wave_contacts_from_page_raw_dedupes_platform_ids(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(paths, "unit-000001", 1, {
        "wave_id": "wave-001",
        "contacts": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
    })
    mark_page_completed(paths, "unit-000002", 1, {
        "wave_id": "wave-001",
        "contacts": [{"id": "u1", "name": "A again"}],
    })

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["wave_id"] == "wave-001"
    assert payload["metadata"]["total_contacts"] == 2
    assert [item["id"] for item in payload["contacts"]] == ["u1", "u2"]
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_pipeline.py::test_extract_wave_contacts_from_page_raw_dedupes_platform_ids -q
```

Expected: FAIL because function does not exist.

- [ ] **Step 2: 实现 wave contacts 提取**

Add to `scripts/maimai_ai_infra_pipeline.py`:

```python
def extract_wave_contacts_from_pages(paths, wave_id: str) -> dict[str, Any]:
    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_path in sorted(paths.raw_search_dir.glob("unit-*/page-*.json")):
        data = _load_json(raw_path)
        if data.get("wave_id") != wave_id:
            continue
        for contact in data.get("contacts") or []:
            key = str(contact.get("id") or contact.get("platform_id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            contacts.append(contact)
    payload = {
        "exportTime": datetime.now().isoformat(timespec="seconds"),
        "metadata": {
            "export_type": "maimai_ai_infra_v2_wave_contacts",
            "wave_id": wave_id,
            "total_contacts": len(contacts),
        },
        "contacts": contacts,
    }
    _write_json(paths.contacts_dir / f"contacts-{wave_id}.json", payload)
    return payload
```

- [ ] **Step 3: 写 import ledger 幂等红测**

Append:

```python
from scripts.maimai_ai_infra_campaign import append_import_ledger, import_ledger_has_apply


def test_import_ledger_blocks_duplicate_wave_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    append_import_ledger(paths, {"wave_id": "wave-001", "action": "apply", "status": "completed"})

    assert import_ledger_has_apply(paths, "wave-001")
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_pipeline.py::test_import_ledger_blocks_duplicate_wave_apply -q
```

Expected: FAIL because functions do not exist.

- [ ] **Step 4: 实现 import ledger helper**

Add to `scripts/maimai_ai_infra_campaign.py`:

```python
def append_import_ledger(paths: CampaignPaths, item: dict[str, Any]) -> None:
    append_jsonl(paths.import_ledger, {"ts": datetime.now().isoformat(timespec="seconds"), **item})


def import_ledger_has_apply(paths: CampaignPaths, wave_id: str) -> bool:
    if not paths.import_ledger.exists():
        return False
    for line in paths.import_ledger.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        if item.get("wave_id") == wave_id and item.get("action") == "apply" and item.get("status") == "completed":
            return True
    return False
```

- [ ] **Step 5: pipeline supports campaign root and wave**

Extend `scripts/maimai_ai_infra_pipeline.py` CLI with:

```text
run-campaign --campaign-root <path> --config <strategy> --wave wave-001 --db <campaign-db>
```

Behavior:

1. Ensure campaign layout.
2. Generate plan and search-units if missing.
3. Extract wave contacts from page raw.
4. Run import dry-run into campaign DB.
5. Write `reports/import-list-wave-001-dry-run.md`.
6. If apply is requested and ledger has prior apply, abort.

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_pipeline.py -q
```

Expected: PASS.

## Task 6: List/Detailed scoring modes and reports

**Files:**
- Modify: `scripts/maimai_ai_infra_rank.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Modify: `tests/test_maimai_ai_infra_strategy.py`
- Modify: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 写 list mode 不依赖详情的红测**

Append to `tests/test_maimai_ai_infra_strategy.py`:

```python
from scripts.maimai_ai_infra_rank import score_candidate


def test_list_mode_scores_without_detail(strategy, maimai_candidate):
    result = score_candidate(maimai_candidate, strategy, detail=None, mode="list")

    assert result["grade"] in {"A", "B", "C", "淘汰"}
    assert result["score_mode"] == "list"


def test_list_mode_rejects_non_priority_school(strategy, maimai_candidate):
    maimai_candidate.education = "普通本科"

    result = score_candidate(maimai_candidate, strategy, detail=None, mode="list")

    assert result["grade"] == "淘汰"
    assert "school_not_priority" in result["risk_flags"]


def test_list_mode_marks_age_35_to_40_as_second_tier(strategy, maimai_candidate):
    maimai_candidate.age = 37
    maimai_candidate.education = "北京邮电大学 211 本科"

    result = score_candidate(maimai_candidate, strategy, detail=None, mode="list")

    assert result["age_band"] == "secondary_35_40"
    assert result["grade"] in {"B", "C", "淘汰"}


def test_list_mode_rejects_age_over_40(strategy, maimai_candidate):
    maimai_candidate.age = 41
    maimai_candidate.education = "浙江大学 985 本科"

    result = score_candidate(maimai_candidate, strategy, detail=None, mode="list")

    assert result["grade"] == "淘汰"
    assert "age_over_40" in result["risk_flags"]
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py::test_list_mode_scores_without_detail -q
```

Expected: FAIL until `mode` is supported.

- [ ] **Step 2: 写 detailed mode 可降级红测**

Append:

```python
def test_detailed_mode_can_downgrade_when_detail_lacks_infra_evidence(strategy, maimai_candidate):
    maimai_candidate.current_title = "大模型推理工程师"
    result = score_candidate(maimai_candidate, strategy, detail=None, mode="detailed")

    assert result["score_mode"] == "detailed"
    assert "missing_detail_for_detailed_score" in result["risk_flags"]
```

- [ ] **Step 3: 实现评分 mode**

Change signature:

```python
def score_candidate(candidate: Candidate, strategy: dict[str, Any], detail: CandidateDetail | None = None, mode: str = "list") -> dict[str, Any]:
```

Rules:

- `mode="list"`: current behavior, but output includes `"score_mode": "list"`.
- `mode="detailed"` and `detail is None`: add risk `missing_detail_for_detailed_score` and cap grade at `观察` or `C`.
- `mode="detailed"` and detail exists: weight `_detail_text(detail)` more heavily than list text for technical evidence.
- School gate runs before grade assignment: text must contain one of C9/985/211/QS Top500/overseas Top500 signals; junior college, non-priority school, or unknown school quality cannot become A/B or final recommended.
- Age gate runs before grade assignment: `24-35` returns `age_band="best_24_35"`; `35-40` returns `age_band="secondary_35_40"` and caps grade at B; `>40` adds `age_over_40` and returns 淘汰.

- [ ] **Step 4: 输出 initial 和 final 报告**

Add pipeline helpers:

```python
write_initial_list_report(path, shortlist, funnel)
write_final_search_report(path, detailed_result, funnel)
```

Initial report must include:

- raw/page/wave counts.
- A/B/C/淘汰 funnel.
- A Top 100 and B Top 150.
- direction/company coverage.

Final report must include:

- detail targets/success.
- 强推荐/推荐/观察/不推荐.
- final recommended count.
- gap suggestions.

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_pipeline.py -q
```

Expected: PASS.

## Task 7: Human review input and detail wave targets

**Files:**
- Create: `scripts/maimai_ai_infra_review.py`
- Modify: `scripts/maimai_detail_targets.py`
- Create: `tests/test_maimai_ai_infra_review.py`
- Modify: `tests/test_maimai_detail_targets.py`

- [ ] **Step 1: 写 review parser 红测**

Create `tests/test_maimai_ai_infra_review.py`:

```python
import json
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_review import load_review_decisions


def test_load_review_decisions_returns_detail_now_ids(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(json.dumps({
        "campaign_id": "ai-infra-v2-smoke",
        "items": [
            {"candidate_id": 1, "decision": "detail_now", "priority": "P0"},
            {"candidate_id": 2, "decision": "hold", "priority": "P1"},
        ],
    }), encoding="utf-8")

    result = load_review_decisions(path)

    assert result.detail_candidate_ids == [1]


def test_load_review_decisions_rejects_invalid_decision(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(json.dumps({"items": [{"candidate_id": 1, "decision": "maybe"}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="invalid review decision"):
        load_review_decisions(path)
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_review.py -q
```

Expected: FAIL.

- [ ] **Step 2: 实现 review parser**

Create `scripts/maimai_ai_infra_review.py`:

```python
"""Human review input for AI Infra V2 campaigns."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VALID_DECISIONS = {"detail_now", "hold", "reject"}


@dataclass(frozen=True)
class ReviewDecisions:
    campaign_id: str
    detail_candidate_ids: list[int]
    items: list[dict[str, Any]]


def load_review_decisions(path: str | Path) -> ReviewDecisions:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    items = data.get("items") or []
    seen: set[int] = set()
    detail_ids: list[int] = []
    for item in items:
        decision = item.get("decision")
        if decision not in VALID_DECISIONS:
            raise ValueError(f"invalid review decision: {decision}")
        candidate_id = int(item["candidate_id"])
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id in review: {candidate_id}")
        seen.add(candidate_id)
        if decision == "detail_now":
            detail_ids.append(candidate_id)
    return ReviewDecisions(
        campaign_id=str(data.get("campaign_id") or ""),
        detail_candidate_ids=detail_ids,
        items=items,
    )
```

- [ ] **Step 3: detail targets from review**

Add CLI to `scripts/maimai_detail_targets.py`:

```text
from-review --review <review.json> --db <campaign.db> --out <detail-targets-waveN.json>
```

Implementation:

```python
from scripts.maimai_ai_infra_review import load_review_decisions
result = export_targets(args.db, args.out, candidate_ids=load_review_decisions(args.review).detail_candidate_ids)
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q
```

Expected: PASS.

## Task 8: Detail wave progress and duplicate apply guard

**Files:**
- Modify: `scripts/maimai_ai_infra_campaign.py`
- Modify: `scripts/maimai_ai_infra_pipeline.py`
- Modify: `tests/test_maimai_ai_infra_pipeline.py`

- [ ] **Step 1: 写 detail progress 红测**

Append to `tests/test_maimai_ai_infra_pipeline.py`:

```python
from scripts.maimai_ai_infra_campaign import mark_detail_wave_state, read_detail_progress


def test_detail_wave_progress_records_recovery_state(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    mark_detail_wave_state(paths, "wave-001", "dry_run_clean", {"matched": 100})

    progress = read_detail_progress(paths)
    assert progress["waves"]["wave-001"]["status"] == "dry_run_clean"
    assert progress["waves"]["wave-001"]["matched"] == 100
```

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_pipeline.py::test_detail_wave_progress_records_recovery_state -q
```

Expected: FAIL.

- [ ] **Step 2: 实现 detail progress helper**

Add:

```python
def read_detail_progress(paths: CampaignPaths) -> dict[str, Any]:
    if not paths.detail_progress.exists():
        return {"campaign_id": paths.campaign_id, "waves": {}}
    return json.loads(paths.detail_progress.read_text(encoding="utf-8-sig"))


def mark_detail_wave_state(paths: CampaignPaths, wave_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    progress = read_detail_progress(paths)
    payload = {"status": status, "updated_at": datetime.now().isoformat(timespec="seconds")}
    if extra:
        payload.update(extra)
    progress.setdefault("waves", {})[wave_id] = payload
    atomic_write_json(paths.detail_progress, progress)
```

- [ ] **Step 3: pipeline detail wave commands**

Add commands:

```text
detail-wave dry-run --campaign-root <root> --wave wave-001 --capture-file <capture.json>
detail-wave apply --campaign-root <root> --wave wave-001 --capture-file <capture.json> --confirm "确认写入脉脉详情"
```

Behavior:

- Dry-run updates detail progress to `dry_run_clean` only when `failed_jobs=0` and `unmatched=0`.
- Apply checks `import-ledger.jsonl`; if wave already applied, abort.
- Apply appends ledger item `{wave_id, action: "detail_apply", status: "completed"}`.

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_pipeline.py -q
```

Expected: PASS.

## Task 9: Documentation, verification, and final review

**Files:**
- Modify: `docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md`
- Modify: `tasks/todo.md`
- Modify: `memory/error-log.md` only if debugging reveals a non-obvious error

- [x] **Step 1: Update docs with implemented commands**

Add a short "Implemented CLI Map" section to the V2 design doc listing:

```text
search-plan --out-units
search-runner --campaign-root --resume
pipeline run-campaign
detail-targets from-review
pipeline detail-wave dry-run/apply
```

- [x] **Step 2: Run focused verification**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q
```

Result: PASS, `97 passed`.

- [x] **Step 3: Run related regression**

Run:

```bash
python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_detail_import.py tests/test_maimai_detail_plan_server.py -q
python -m py_compile scripts/maimai_ai_infra_campaign.py scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_review.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_import.py
git diff --check
```

Result: PASS. Related pytest returned `13 passed`; Python compile passed; `git diff --check` passed.

- [x] **Step 4: Run full regression**

Run:

```bash
python -m pytest tests scripts -q
```

Result: PASS, `591 passed, 1 warning`; warning is the already-known `scripts/test_boss.py` event loop deprecation warning.

### Task 9 Execution Review

- Updated `docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md` with an "已实现 CLI 映射" section covering search plan unit output, campaign runner dry-run/resume, campaign wave import, review-to-detail targets, and detail wave dry-run/apply.
- Read-only CLI review confirmed the documented mappings match current code. The campaign runner entry must include `--dry-run-template-only --campaign-root --units`; `--resume` is accepted for clarity while actual recovery is based on landed raw pages.
- Focused verification: `python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q` -> `97 passed`.
- Related regression: `python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_detail_import.py tests/test_maimai_detail_plan_server.py -q` -> `13 passed`.
- Syntax check: `python -m py_compile scripts/maimai_ai_infra_campaign.py scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_review.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_import.py` -> PASS.
- Diff check: `git diff --check` -> PASS.
- Full regression: `python -m pytest tests scripts -q` -> `591 passed, 1 warning`.

## Self-Review

- Spec coverage: covers campaign isolation, 10x target funnel, school/age hard gates, search unit/page task, atomic raw, resume, wave import ledger, list report, human review, detail wave, final report.
- Placeholder scan: no unresolved placeholder markers or unspecified implementation steps.
- Type consistency: uses `CampaignPaths`, `search-units.jsonl`, `wave_id`, `unit_id`, `PageTask`, `ReviewDecisions`, and ledger terms consistently.
- Safety: real search and DB apply remain behind explicit user authorization.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-14-maimai-ai-infra-v2-cold-start-campaign.md`. Two execution options:

1. Subagent-Driven (recommended) - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution - execute tasks in this session using executing-plans, batch execution with checkpoints.
