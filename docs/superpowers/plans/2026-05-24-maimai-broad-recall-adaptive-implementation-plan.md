# Maimai Broad Recall Adaptive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `strategy_mode=broad_recall_adaptive_v1` as an isolated experimental Maimai sourcing mode that uses broad recall, adaptive page-quality decisions, detail-priority screening, durable recovery state, and summary-only reporting.

**Architecture:** Add a focused `scripts/maimai_broad_recall_adaptive.py` module for strategy detection, broad search unit generation, page quality scoring, detail-priority output, continuation helpers, and summary reports. Keep existing generic/legacy flows intact by routing only explicit `strategy_mode=broad_recall_adaptive_v1` through the new mode in `maimai_campaign_search_plan.py` and `maimai_campaign_orchestrator.py`.

**Tech Stack:** Python stdlib, existing `TalentDB`, existing Maimai campaign scripts, pytest.

---

### Task 1: Broad Recall Strategy Module

**Files:**
- Create: `scripts/maimai_broad_recall_adaptive.py`
- Test: `tests/test_maimai_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing tests for strategy detection and broad unit generation**

Add tests that import `is_broad_recall_strategy`, `adaptive_policy_from_strategy`, and `build_broad_recall_search_units`.

```python
def test_build_broad_recall_units_use_strategy_mode_and_probe_pages() -> None:
    strategy = _broad_strategy()

    units = build_broad_recall_search_units(strategy)

    assert units
    assert all(unit["strategy_mode"] == "broad_recall_adaptive_v1" for unit in units)
    assert all(unit["adaptive_search"]["probe_pages"] == 2 for unit in units)
    assert all(unit["max_pages"] == 2 for unit in units)
    assert all(unit["unit_max_pages"] == 15 for unit in units)
    assert all(unit["search_filters"]["cities"] == "" for unit in units)
    assert all(unit["search_filters"]["positions"] == "" for unit in units)
    assert any("腾讯混元" in unit["query"] for unit in units)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py::test_build_broad_recall_units_use_strategy_mode_and_probe_pages -q`

Expected: FAIL with import error because `scripts.maimai_broad_recall_adaptive` does not exist.

- [ ] **Step 3: Implement minimal strategy module**

Create `scripts/maimai_broad_recall_adaptive.py` with:

```python
STRATEGY_MODE = "broad_recall_adaptive_v1"

DEFAULT_ADAPTIVE_POLICY = {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "good_ratio_continue": 0.3,
    "good_ratio_observe": 0.1,
    "max_consecutive_low_quality_pages": 2,
    "stop_on_high_duplicate_ratio": True,
}

def is_broad_recall_strategy(strategy: dict[str, Any]) -> bool:
    return str(strategy.get("strategy_mode") or "") == STRATEGY_MODE
```

Implement `adaptive_policy_from_strategy()` and `build_broad_recall_search_units()` using existing company expansion and empty structured filters.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py::test_build_broad_recall_units_use_strategy_mode_and_probe_pages -q`

Expected: PASS.

### Task 2: Page Quality Scoring and Unit Decisions

**Files:**
- Modify: `scripts/maimai_broad_recall_adaptive.py`
- Test: `tests/test_maimai_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing tests for page quality and low-quality stop**

Add tests for `score_page_quality()` and `next_unit_status()`.

```python
def test_score_page_quality_uses_good_candidate_ratio_and_duplicates() -> None:
    strategy = _broad_strategy()
    page = {"contacts": [_contact("1", "腾讯", "大模型数据负责人"), _contact("2", "外包公司", "销售")]}

    quality = score_page_quality(page, strategy, seen_candidate_keys={"1"})

    assert quality["candidate_count"] == 2
    assert quality["new_candidate_count"] == 1
    assert quality["duplicate_ratio"] == 0.5
    assert quality["detail_eligible_count"] == 1
    assert quality["quality_band"] in {"observe", "good"}
```

```python
def test_next_unit_status_stops_after_consecutive_low_quality_pages() -> None:
    state = {"unit_id": "unit-000001", "status": "observing", "consecutive_low_quality_pages": 1}
    quality = {"quality_band": "low", "next_page": 4}

    updated = next_unit_status(state, quality, adaptive_policy_from_strategy({}))

    assert updated["status"] == "stopped_low_quality"
    assert updated["stop_reason"] == "consecutive_low_quality_pages"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py::test_score_page_quality_uses_good_candidate_ratio_and_duplicates tests/test_maimai_broad_recall_adaptive.py::test_next_unit_status_stops_after_consecutive_low_quality_pages -q`

Expected: FAIL because functions are missing.

- [ ] **Step 3: Implement scoring and decision functions**

Implement:

- `extract_page_contacts(page)`
- `candidate_key(contact)`
- `score_contact_for_detail_priority(contact, strategy, seen_candidate_keys)`
- `score_page_quality(page, strategy, seen_candidate_keys=None, policy=None)`
- `next_unit_status(state, page_quality, policy)`

Use labels `detail_p0/detail_p1/detail_p2/skip`; treat `detail_p0` and `detail_p1` as detail eligible.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py -q`

Expected: PASS.

### Task 3: Route Search Plan Generation by Strategy Mode

**Files:**
- Modify: `scripts/maimai_campaign_search_plan.py`
- Modify: `tests/test_maimai_campaign_search_plan.py`

- [ ] **Step 1: Write failing test for broad mode routing**

Add a test that calls `build_generic_search_plan()` with `strategy_mode=broad_recall_adaptive_v1` and asserts units contain adaptive metadata.

```python
def test_broad_recall_strategy_routes_to_adaptive_units() -> None:
    strategy = _strategy()
    strategy["strategy_mode"] = "broad_recall_adaptive_v1"
    strategy["adaptive_search"] = {"probe_pages": 2, "unit_max_pages": 15}

    plan = build_generic_search_plan(strategy)

    assert plan["strategy_mode"] == "broad_recall_adaptive_v1"
    assert plan["batches"][0]["max_pages"] == 2
    assert plan["batches"][0]["unit_max_pages"] == 15
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_campaign_search_plan.py::test_broad_recall_strategy_routes_to_adaptive_units -q`

Expected: FAIL because current plan has no `strategy_mode` and no `unit_max_pages`.

- [ ] **Step 3: Implement routing**

In `maimai_campaign_search_plan.py`, import broad mode helpers and route `build_generic_search_units()` / `build_generic_search_plan()` when `is_broad_recall_strategy(strategy)` returns true. Preserve old behavior for all strategies without the mode.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_campaign_search_plan.py -q`

Expected: PASS.

### Task 4: Broad Mode Command Plan

**Files:**
- Modify: `scripts/maimai_campaign_orchestrator.py`
- Modify: `tests/test_maimai_campaign_orchestrator.py`

- [ ] **Step 1: Write failing test for command plan isolation**

Add a test that creates a broad strategy file and verifies broad mode includes page-quality/detail-priority/summary stages and excludes detailed rank/delivery/outreach package stages.

```python
def test_build_stage_command_plan_for_broad_recall_skips_recommendation_delivery(tmp_path: Path) -> None:
    strategy_path = tmp_path / "strategy.json"
    strategy_path.write_text(json.dumps({"strategy_mode": "broad_recall_adaptive_v1", "keyword_packages": [{"id": "p0", "keywords": ["大模型"]}], "company_pools": {"target": ["腾讯混元"]}}, ensure_ascii=False), encoding="utf-8")

    plan = build_stage_command_plan("data/campaigns/demo", str(strategy_path), policy=DEFAULT_RUN_POLICY)
    stages = [command["stage"] for command in plan]

    assert "evaluate_page_quality" in stages
    assert "detail_priority" in stages
    assert "broad_recall_summary" in stages
    assert "detailed_rank" not in stages
    assert "delivery_report" not in stages
    assert "outreach_package" not in stages
    assert "delivery_package" not in stages
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_campaign_orchestrator.py::test_build_stage_command_plan_for_broad_recall_skips_recommendation_delivery -q`

Expected: FAIL because the current command plan includes old delivery stages.

- [ ] **Step 3: Implement broad command plan branch**

Add `_is_broad_recall_strategy(strategy_path)` and a broad-specific branch in `build_stage_command_plan()` that returns stages:

- `compile_search_plan`
- `plan_search_waves`
- `search_live`
- `standardize_search_live`
- `evaluate_page_quality`
- `import_wave`
- `detail_priority`
- `detail_pack`
- `broad_recall_summary`
- `notify_blocked`

Keep old branch unchanged.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_campaign_orchestrator.py -q`

Expected: PASS.

### Task 5: Detail Priority and Summary CLI

**Files:**
- Modify: `scripts/maimai_broad_recall_adaptive.py`
- Test: `tests/test_maimai_broad_recall_adaptive.py`

- [ ] **Step 1: Write failing tests for CLI outputs**

Add tests for:

- `build_detail_priority_outputs()` writes `reports/detail-priority.json` and `review/initial-human-review-draft-search-wave-001.json`.
- `build_broad_recall_summary()` writes `reports/broad-recall-summary.json` and Markdown without recommendation/outreach language.

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py::test_build_detail_priority_outputs_writes_review_file tests/test_maimai_broad_recall_adaptive.py::test_build_broad_recall_summary_excludes_outreach_recommendations -q`

Expected: FAIL because functions are missing.

- [ ] **Step 3: Implement detail priority and summary**

Implement:

- `build_detail_priority_outputs(campaign_root, db_path, strategy, out_json, out_md, review_out)`
- `build_broad_recall_summary(campaign_root, out_json, out_md)`
- CLI subcommands `evaluate-page-quality`, `build-detail-priority`, and `summary`.

Map `detail_p0 -> A`, `detail_p1 -> B`, `detail_p2 -> C`, `skip -> 淘汰` only for compatibility with existing detail pack scripts.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_broad_recall_adaptive.py -q`

Expected: PASS.

### Task 6: Skill and Workflow Documentation Contracts

**Files:**
- Modify: `skills/maimai-talent-search-campaign/SKILL.md`
- Modify: `agents/workflows/maimai-unattended-campaign/AGENT.md`
- Modify: `tests/test_maimai_talent_search_campaign_skill.py`

- [ ] **Step 1: Write failing docs contract tests**

Add tests asserting the skill/workflow mention:

- `strategy_mode=broad_recall_adaptive_v1`
- no campaign total budget in broad mode
- `account_day_page_guardrail`
- detail priority labels
- summary-only report
- no recommendation/outreach sheet in broad mode

- [ ] **Step 2: Run RED**

Run: `python -m pytest tests/test_maimai_talent_search_campaign_skill.py::test_skill_documents_broad_recall_adaptive_experiment tests/test_maimai_talent_search_campaign_skill.py::test_workflow_documents_broad_recall_summary_only_mode -q`

Expected: FAIL because docs do not mention the new mode yet.

- [ ] **Step 3: Update docs**

Add a short experimental mode section to the skill and workflow. Preserve existing default behavior text.

- [ ] **Step 4: Run GREEN**

Run: `python -m pytest tests/test_maimai_talent_search_campaign_skill.py -q`

Expected: PASS.

### Task 7: Full Verification and Task Ledger

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_broad_recall_adaptive.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full suite**

Run: `python -m pytest tests scripts -q`

Expected: PASS, allowing only the known existing `scripts/test_boss.py` event-loop deprecation warning.

- [ ] **Step 3: Run diff hygiene**

Run: `git diff --check`

Expected: no output.

- [ ] **Step 4: Update task ledger review**

Update `tasks/todo.md` with a Review listing implemented files and verification commands.

- [ ] **Step 5: Commit implementation**

Run:

```powershell
git add scripts tests skills agents tasks docs/superpowers/plans/2026-05-24-maimai-broad-recall-adaptive-implementation-plan.md
git commit -m "实现脉脉宽召回自适应寻访实验模式"
```
