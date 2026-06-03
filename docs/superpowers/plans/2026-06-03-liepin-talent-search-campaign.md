# 猎聘人才搜索 CLI P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a P0 Liepin campaign CLI that can create safe contracts, generate form-encoded API requests, classify responses, standardize saved raw search pages, and prepare a controlled browser fetch runner without reading browser session stores or writing the main TalentDB.

**Architecture:** Follow the existing Maimai campaign shape, but keep Liepin P0 smaller. Pure Python modules handle API contracts, campaign paths, raw validation, standardization, reports, and CLI orchestration; a separate browser runner module only builds whitelist-checked in-page fetch expressions and does not run live requests in tests.

**Tech Stack:** Python 3, pytest, argparse, JSON/JSONL files, existing `scripts/` package conventions, canonical `agents/skills` and `agents/workflows` Markdown contracts.

---

## File Structure

- Create `scripts/liepin_api_contract.py`: endpoint constants, request body builders, response classification, and candidate summary extraction helpers.
- Create `scripts/liepin_campaign.py`: campaign path dataclass, manifest creation/validation, JSON/JSONL helpers, request ledger and continuation helpers.
- Create `scripts/liepin_search_standardize.py`: read raw search pages and write `structured/candidate-summaries.jsonl` plus summary reports.
- Create `scripts/liepin_browser_runner.py`: build safe JavaScript fetch expressions for the two whitelisted endpoints and expose dry-run CLI output.
- Create `scripts/liepin_campaign_orchestrator.py`: `init`, `status`, `plan-pages`, `standardize`, and `summarize` commands.
- Create `tests/test_liepin_api_contract.py`: request body and response classification tests.
- Create `tests/test_liepin_campaign.py`: campaign path, manifest, continuation, and ledger tests.
- Create `tests/test_liepin_search_standardize.py`: raw-to-summary tests.
- Create `tests/test_liepin_browser_runner.py`: whitelist and no-sensitive-storage expression tests.
- Create `tests/test_liepin_campaign_orchestrator.py`: CLI smoke tests.
- Modify `tests/test_agent_architecture.py`: include `liepin-unattended-campaign` workflow and `liepin-talent-search-campaign` skill.
- Create `agents/skills/liepin-talent-search-campaign/SKILL.md`: business entry contract.
- Create `agents/workflows/liepin-unattended-campaign/AGENT.md`: canonical workflow contract.
- Create `.claude/skills/liepin-talent-search-campaign/SKILL.md`: adapter to canonical skill/workflow.

## Task 1: API Contract

**Files:**
- Create: `tests/test_liepin_api_contract.py`
- Create: `scripts/liepin_api_contract.py`

- [ ] **Step 1: Write failing tests for form encoding and default request shape**

Add tests that import `build_condition_request_body`, `build_search_request_body`, `decode_form_body`, and endpoint constants. Verify `jobId=75703601`, `searchParamsInputVo`, and `logForm` are x-www-form-urlencoded and JSON fields round-trip.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_api_contract.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.liepin_api_contract'`.

- [ ] **Step 3: Implement minimal API contract helpers**

Implement endpoint constants, `DEFAULT_SEARCH_PARAMS`, `build_condition_request_body(job_id)`, `merge_condition_data(condition, overrides, job_id, cur_page)`, `build_search_request_body(params, log_form)`, and `decode_form_body(body)`.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_api_contract.py -q`
Expected: PASS for request body tests.

- [ ] **Step 5: Add failing tests for stop classification**

Add tests for `classify_api_result(status, content_type, raw_text, parsed)` covering `http_403`, `http_429`, `http_432`, `non_json_response`, `html_response`, `flag_not_1`, and a good `flag=1` response.

- [ ] **Step 6: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_api_contract.py -q`
Expected: FAIL because `classify_api_result` is missing.

- [ ] **Step 7: Implement classification**

Return dictionaries shaped as `{"ok": bool, "reason": str | None, "http_status": int | None}`. Treat JSON `flag != 1` as `flag_not_1`.

- [ ] **Step 8: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_api_contract.py -q`
Expected: PASS.

## Task 2: Campaign State

**Files:**
- Create: `tests/test_liepin_campaign.py`
- Create: `scripts/liepin_campaign.py`

- [ ] **Step 1: Write failing tests for campaign initialization**

Test that `ensure_campaign(tmp_path / "liepin-demo")` creates `campaign-manifest.json`, `state/`, `raw/condition/`, `raw/search/`, `structured/`, and `reports/`, with schema `liepin_talent_search_campaign_v1`.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign.py -q`
Expected: FAIL with missing module.

- [ ] **Step 3: Implement campaign paths and manifest**

Create `LiepinCampaignPaths`, `campaign_paths`, `atomic_write_json`, `append_jsonl`, and `ensure_campaign`. Reject existing manifests with mismatched campaign id or schema.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign.py -q`
Expected: PASS for initialization tests.

- [ ] **Step 5: Add failing tests for ledger and continuation**

Test `mark_page_completed`, `load_completed_pages`, and `write_continuation_plan`. Use Liepin zero-based `curPage`; raw path should be `raw/search/page-000.json`.

- [ ] **Step 6: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign.py -q`
Expected: FAIL because ledger functions are missing.

- [ ] **Step 7: Implement ledger and continuation helpers**

Implement request ledger JSONL writes, completed-page scanner, and continuation JSON writes. Validate page is a non-negative integer.

- [ ] **Step 8: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign.py -q`
Expected: PASS.

## Task 3: Search Standardization

**Files:**
- Create: `tests/test_liepin_search_standardize.py`
- Create: `scripts/liepin_search_standardize.py`

- [ ] **Step 1: Write failing tests for candidate extraction**

Build a fixture with `flag=1`, `data.ckId/skId/fkId`, and one `cardResList` item containing `usercIdEncode`, `detailUrl`, and `simpleResumeForm`. Assert output summary fields include `platform=liepin`, `platform_id`, `display_name`, `profile_url`, and raw ref.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_search_standardize.py -q`
Expected: FAIL with missing module.

- [ ] **Step 3: Implement candidate summary extraction**

Read raw JSON, require `flag=1`, require `data.cardResList` list, normalize detail URL against `https://h.liepin.com`, and write one JSONL row per card.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_search_standardize.py -q`
Expected: PASS for candidate extraction.

- [ ] **Step 5: Add failing tests for template drift and CLI output**

Test that missing `cardResList` returns status `template_drift` and no summary rows, and CLI `--campaign-root --out` writes `reports/search-summary.json`.

- [ ] **Step 6: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_search_standardize.py -q`
Expected: FAIL for missing drift handling or CLI.

- [ ] **Step 7: Implement drift handling and CLI**

Return summary dict with `status`, `candidate_count`, `pages_scanned`, `skipped_pages`, and write Markdown + JSON reports.

- [ ] **Step 8: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_search_standardize.py -q`
Expected: PASS.

## Task 4: Browser Runner Safety

**Files:**
- Create: `tests/test_liepin_browser_runner.py`
- Create: `scripts/liepin_browser_runner.py`

- [ ] **Step 1: Write failing tests for endpoint whitelist and expression safety**

Test that only `get-search-condition-by-job` and `search-resumes` URLs are accepted. Test generated JavaScript includes `credentials: "include"` and does not include `document.cookie`, `localStorage`, or `sessionStorage`.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_browser_runner.py -q`
Expected: FAIL with missing module.

- [ ] **Step 3: Implement dry-run browser runner helpers**

Implement `validate_allowed_url(url)`, `build_in_page_fetch_expression(url, body)`, and CLI `dry-run-fetch --url --body-json`. Do not add live CDP execution yet.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_browser_runner.py -q`
Expected: PASS.

## Task 5: Orchestrator CLI

**Files:**
- Create: `tests/test_liepin_campaign_orchestrator.py`
- Create: `scripts/liepin_campaign_orchestrator.py`

- [ ] **Step 1: Write failing tests for init and plan-pages**

Test CLI `init --campaign-root <dir> --job-id 75703601` writes `requirements.json`, `strategy.json`, `run-policy.json`, and manifest. Test `plan-pages` writes `state/continuation-plan.json` with pages `[0]` by default and rejects max pages above policy limit.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`
Expected: FAIL with missing module.

- [ ] **Step 3: Implement init, status, and plan-pages**

Use campaign helpers and API contract defaults. Default page limit is 1, max is 5.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`
Expected: PASS for init and plan-pages.

- [ ] **Step 5: Add failing tests for standardize command**

Test CLI `standardize --campaign-root <dir>` delegates to standardizer and prints JSON with candidate count.

- [ ] **Step 6: Run red test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`
Expected: FAIL until standardize command exists.

- [ ] **Step 7: Implement standardize and summarize commands**

Call `standardize_campaign` and print JSON. `summarize` should read `reports/search-summary.json` without touching raw.

- [ ] **Step 8: Run green test**

Run: `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`
Expected: PASS.

## Task 6: Canonical Skill and Workflow

**Files:**
- Modify: `tests/test_agent_architecture.py`
- Create: `agents/skills/liepin-talent-search-campaign/SKILL.md`
- Create: `agents/workflows/liepin-unattended-campaign/AGENT.md`
- Create: `.claude/skills/liepin-talent-search-campaign/SKILL.md`

- [ ] **Step 1: Write failing architecture test updates**

Add `liepin-unattended-campaign` to `WORKFLOWS`, map `liepin-talent-search-campaign` to it in `CANONICAL_SKILL_WORKFLOWS`, and add Claude adapter mapping.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_agent_architecture.py -q`
Expected: FAIL with missing canonical files.

- [ ] **Step 3: Add canonical docs and adapter**

Create Markdown files with front matter, `## 目标`, `## 触发入口`, safety boundaries, stages, and references to `agents/workflows/liepin-unattended-campaign/AGENT.md`.

- [ ] **Step 4: Run green architecture test**

Run: `.venv/bin/python -m pytest tests/test_agent_architecture.py -q`
Expected: PASS.

## Task 7: Final Verification and Commit

**Files:**
- All files above.

- [ ] **Step 1: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_liepin_api_contract.py tests/test_liepin_campaign.py tests/test_liepin_search_standardize.py tests/test_liepin_browser_runner.py tests/test_liepin_campaign_orchestrator.py tests/test_agent_architecture.py -q`
Expected: PASS.

- [ ] **Step 2: Run security scan**

Run: `rg -n "cookies\\(|context\\.cookies|localStorage|sessionStorage|document\\.cookie" scripts/liepin_*.py tests/test_liepin_*.py agents/skills/liepin-talent-search-campaign agents/workflows/liepin-unattended-campaign`
Expected: no production hit; tests may contain forbidden strings only as assertions against generated expressions.

- [ ] **Step 3: Run full suite**

Run: `.venv/bin/python -m pytest tests -q`
Expected: PASS.

- [ ] **Step 4: Review git diff**

Run: `git diff --stat && git diff --check`
Expected: only Liepin implementation, docs, tests, plan, and task ledger changes; no whitespace errors.

- [ ] **Step 5: Commit relevant files only**

Stage the Liepin implementation files and plan/docs. Do not stage unrelated existing `tasks/todo.md` changes unless the staged patch is explicitly limited to this task.

Commit message: `Add Liepin talent search campaign P0`
