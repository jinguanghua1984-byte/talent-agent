# Campaign Status Next Action Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 强化 campaign 状态摘要和确定性 next-action，让长任务恢复时优先读取一页 JSON/Markdown，而不是重新加载长 workflow 和任务历史。

**Architecture:** 保持 `scripts.campaign_status` 和 `scripts.campaign_orchestrator` 只读；`campaign_status summarize` 负责 artifact completeness、阶段和计数归纳，`campaign_orchestrator next-action` 基于 summary 输出下一阶段、阻塞原因、缺失 artifact、安全命令和禁止命令。所有判断只来自 campaign 目录文件，不触发平台、DB apply、飞书发布或 IM 通知。

**Tech Stack:** Python 3.12、pytest、JSON/JSONL campaign artifacts、现有 `scripts.campaign_status` / `scripts.campaign_orchestrator` CLI。

---

### Task 1: Artifact completeness and stage detection

**Files:**
- Modify: `scripts/campaign_status.py`
- Modify: `tests/test_campaign_status.py`

- [ ] **Step 1: Write the failing test**

Add a test campaign with `raw/list-cards.jsonl`, no `structured/candidates.jsonl`, and assert `summarize_campaign()` returns:
- `artifact_status.raw_list_cards == "present"`
- `artifact_status.structured_candidates == "missing"`
- `missing_artifacts` contains `structured/candidates.jsonl`
- `derived_stage == "standardize-needed"`

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py::test_summarize_campaign_reports_missing_structured_candidates_and_stage -q`
Expected: FAIL because summary does not expose artifact completeness or derived stage.

- [ ] **Step 3: Write minimal implementation**

Add artifact path map, `_artifact_status()`, `_missing_artifacts()`, and `_derive_stage()` helpers. Include `artifact_status`, `missing_artifacts`, and `derived_stage` in summary.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py -q`
Expected: PASS.

### Task 2: DB sync and Feishu state detection

**Files:**
- Modify: `scripts/campaign_status.py`
- Modify: `tests/test_campaign_status.py`

- [ ] **Step 1: Write the failing test**

Add a campaign with `reports/campaign-db-sync-dry-run.json`, `reports/main-db-sync-dry-run.json`, `feishu/dry-run-results.json`, and no corresponding apply/publish files. Assert summary status includes these artifacts and `derived_stage == "main-db-apply-authorization"` when main DB dry-run is pending.

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py::test_summarize_campaign_reports_db_and_feishu_artifact_status -q`
Expected: FAIL because these artifact statuses are not exposed.

- [ ] **Step 3: Write minimal implementation**

Expand artifact map and `dry_run_apply_status` to cover campaign DB sync, main DB sync, Feishu dry-run, Feishu publish, Feishu readback, and IM notification.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py -q`
Expected: PASS.

### Task 3: Deterministic next-action rules

**Files:**
- Modify: `scripts/campaign_orchestrator.py`
- Modify: `tests/test_campaign_orchestrator_next_action.py`

- [ ] **Step 1: Write failing tests**

Add tests for:
- raw exists but structured missing -> `next_stage == "standardize"` and safe command points to `scripts.campaign_status summarize`
- campaign DB dry-run exists without apply -> `next_stage == "campaign-db-apply-authorization"` and `required_confirm_text == "确认写入 Campaign DB"`
- Feishu dry-run exists without publish -> `next_stage == "feishu-publish-preflight"` with safe `lark-cli doctor` / `lark-cli auth status`
- Feishu publish exists without IM -> `next_stage == "feishu-im-notification"`

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_campaign_orchestrator_next_action.py -q`
Expected: FAIL because next-action does not use artifact status or missing artifacts.

- [ ] **Step 3: Write minimal implementation**

Update `next_action()` to read `artifact_status`, `missing_artifacts`, and `dry_run_apply_status`; add deterministic rules before fallback. Include `missing_artifacts` in output summary.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py tests/test_campaign_orchestrator_next_action.py -q`
Expected: PASS.

### Task 4: Docs, task ledger, and verification

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run related tests**

Run: `.venv/bin/python -m pytest tests/test_campaign_status.py tests/test_campaign_orchestrator_next_action.py tests/test_agent_architecture.py -q`
Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:
- `git diff --check`
- `.venv/bin/python -m pytest tests -q`

- [ ] **Step 3: Document result**

Move the Active Task review into `tasks/archive/2026-06.md`, keep `tasks/todo.md` short, and stage only this task's hunks.
