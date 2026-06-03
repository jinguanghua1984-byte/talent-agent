# 猎聘 CDP Live Gate P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为猎聘 CLI 增加独立 Chrome CDP profile 启动器和 live gate，使真实搜索可以在已登录猎聘页面上下文中执行白名单请求并写入 campaign raw。

**Architecture:** 复用脉脉“专用浏览器 profile + CDP Runtime.evaluate”的执行形态，但猎聘 P1 不依赖扩展模板。启动器只负责打开专用 Chrome 和写 session manifest；live gate 读取现有 campaign 合同、执行页面健康检查、调用 `get-search-condition-by-job` 和 `search-resumes`、写 raw/ledger/continuation。

**Tech Stack:** Python 3, pytest, Chrome DevTools Protocol WebSocket, JSON/JSONL campaign files, existing `scripts.liepin_*` helpers.

---

## File Structure

- Create `scripts/liepin_cdp_browser_bootstrap.py`: 猎聘专用 CDP Chrome 启动器，支持 macOS Chrome/Chromium/Edge 候选路径，默认 profile `data/session/liepin-cdp-profile`，端口 `9898`。
- Create `tests/test_liepin_cdp_browser_bootstrap.py`: 启动参数、manifest、dry-run、缺失浏览器错误测试。
- Create `scripts/liepin_search_live_gate.py`: CDP 目标页发现、页面健康检查、白名单请求表达式执行、campaign raw/ledger/continuation 写入。
- Create `tests/test_liepin_search_live_gate.py`: target finder、health blocker、CDP session、condition/search 成功写盘、阻断写恢复计划测试。
- Modify `scripts/liepin_campaign_orchestrator.py`: 增加 `launch-browser` 和 `run-live-search` 命令。
- Modify `tests/test_liepin_campaign_orchestrator.py`: CLI 新命令的 dry-run 和 delegated live gate 测试。
- Modify `agents/workflows/liepin-unattended-campaign/AGENT.md`: 把 P1 CDP 执行面写入 S1/S4，保留 P0 主库和详情边界。

## Task 1: CDP Browser Bootstrap

**Files:**
- Create: `tests/test_liepin_cdp_browser_bootstrap.py`
- Create: `scripts/liepin_cdp_browser_bootstrap.py`

- [ ] **Step 1: Write failing tests**
  - Assert browser args include `--remote-debugging-port=9898`, `--user-data-dir=data/session/liepin-cdp-profile`, `--no-first-run`, `--no-default-browser-check`, and the Liepin search URL.
  - Assert manifest schema is `liepin_cdp_browser_session_v1`, manual steps are `login_liepin`, `enter_resume_search`, `confirm_page_ready`, and `automation_boundary` is `launch_only`.
  - Assert macOS browser candidates include `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
  - Assert dry-run writes manifest without launching a browser.

- [ ] **Step 2: Run red test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_cdp_browser_bootstrap.py -q`.
  - Expected failure: module `scripts.liepin_cdp_browser_bootstrap` is missing.

- [ ] **Step 3: Implement bootstrap**
  - Implement `BrowserLaunchConfig`, `build_browser_args`, `build_session_manifest`, `default_browser_candidates`, `find_browser`, `write_manifest`, and `main`.
  - Do not inspect or copy browser cookies/profile files; only pass Chrome launch flags.

- [ ] **Step 4: Run green test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_cdp_browser_bootstrap.py -q`.
  - Expected: all bootstrap tests pass.

## Task 2: CDP Live Gate Core

**Files:**
- Create: `tests/test_liepin_search_live_gate.py`
- Create: `scripts/liepin_search_live_gate.py`

- [ ] **Step 1: Write failing tests for target and health**
  - Assert `find_liepin_target` selects a page whose URL contains `h.liepin.com/search/getConditionItem` and has `webSocketDebuggerUrl`.
  - Assert `is_blocking_health` returns `login`, `captcha`, `not_liepin_search`, or `None`.
  - Assert `health_expression` does not contain `document.cookie`, `localStorage`, or `sessionStorage`.

- [ ] **Step 2: Run red test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_search_live_gate.py -q`.
  - Expected failure: module is missing.

- [ ] **Step 3: Implement target, health, and CDP session**
  - Implement `/json/list` reader, target selection, `CdpSession.evaluate`, and health expression.
  - Health expression may read URL, title, visible text, ready state, and visibility state only.

- [ ] **Step 4: Run green test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_search_live_gate.py -q`.
  - Expected: target/health/session tests pass.

## Task 3: Campaign Live Search Execution

**Files:**
- Modify: `tests/test_liepin_search_live_gate.py`
- Modify: `scripts/liepin_search_live_gate.py`

- [ ] **Step 1: Write failing execution tests**
  - With fake CDP session, assert `run_live_search` calls condition first, then one search page, and writes:
    - `raw/condition/job-75703601.json`
    - `raw/search/page-000.json`
    - `state/request-ledger.jsonl`
    - `reports/live-search-run-*.json`
  - Assert saved search raw uses existing `mark_page_completed` shape.
  - Assert HTTP `429` or JSON `flag != 1` stops, writes `reports/interruption-*.json`, and updates `state/continuation-plan.json`.

- [ ] **Step 2: Run red test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_search_live_gate.py -q`.
  - Expected failure: `run_live_search` behavior is missing.

- [ ] **Step 3: Implement live execution**
  - Load campaign contracts via `ensure_campaign`.
  - Build condition body with `build_condition_request_body`.
  - Merge condition data with strategy overrides via `merge_condition_data`.
  - Build search body with `build_search_request_body`.
  - Execute expressions built by `build_in_page_fetch_expression`.
  - Classify every API result using `classify_api_result`.
  - On success, save raw and ledger; on block, save interruption and continuation.

- [ ] **Step 4: Run green test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_search_live_gate.py -q`.
  - Expected: all live gate tests pass.

## Task 4: Orchestrator and Workflow Integration

**Files:**
- Modify: `tests/test_liepin_campaign_orchestrator.py`
- Modify: `scripts/liepin_campaign_orchestrator.py`
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`

- [ ] **Step 1: Write failing CLI tests**
  - Assert `launch-browser --dry-run` delegates to bootstrap and writes a manifest path.
  - Assert `run-live-search --campaign-root <dir> --cdp-url http://127.0.0.1:9898 --max-pages 1` delegates to live gate and prints JSON.

- [ ] **Step 2: Run red test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`.
  - Expected failure: commands are missing.

- [ ] **Step 3: Implement CLI commands and docs**
  - Add orchestrator subcommands without changing existing `init/status/plan-pages/standardize/summarize` behavior.
  - Document CDP P1 in workflow S1 and S4.

- [ ] **Step 4: Run green test**
  - Run `.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q`.
  - Expected: orchestrator tests pass.

## Task 5: Verification and Commit

**Files:**
- All files changed above.

- [ ] **Step 1: Run focused tests**
  - Run `.venv/bin/python -m pytest tests/test_liepin_* tests/test_agent_architecture.py -q`.
  - Expected: all focused tests pass.

- [ ] **Step 2: Run full tests**
  - Run `.venv/bin/python -m pytest tests -q`.
  - Expected: all repo tests pass.

- [ ] **Step 3: Run security scan**
  - Run `rg -n "cookies\\(|context\\.cookies|localStorage|sessionStorage|document\\.cookie" scripts/liepin_*.py tests/test_liepin_*.py agents/skills/liepin-talent-search-campaign agents/workflows/liepin-unattended-campaign`.
  - Expected: no production Liepin scripts read browser sensitive storage; test assertions may contain forbidden strings only as negative checks.

- [ ] **Step 4: Commit scoped files**
  - Stage only P1 plan/code/test/workflow files. Do not stage unrelated `tasks/todo.md` history unless explicitly reviewed.
