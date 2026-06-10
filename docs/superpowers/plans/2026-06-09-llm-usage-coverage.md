# LLM Usage Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在当前 workflow/shared-policies PR 中，把已有 `LLMUsageLedger` 和 `configs/llm-routing.json` 接到真实高频 LLM 调用路径，并新增月度 usage 聚合报表。

**Architecture:** 保持业务行为不变，把 usage 覆盖做成调用元数据透传：`pipeline_utils.call_llm_with_retry()` 接收 `workflow/stage/ledger/artifact` 参数，真实 `scripts.llm_client` 继续负责从 API response 生成 ledger record。各业务入口只解析 route 并传入 stage，不直接拼 ledger JSON。`scripts.llm_usage report` 读取月度 JSONL 并按 workflow/stage/provider/model 聚合。

**Tech Stack:** Python stdlib, pytest, existing `scripts.llm_client`, `scripts.llm_usage`, `configs/llm-routing.json`.

---

### Task 1: LLM Call Metadata Pass-Through

**Files:**
- Modify: `scripts/pipeline_utils.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing test for metadata pass-through**

Add a test using a fake client with `complete(messages, model, max_tokens, **kwargs)` and assert `call_llm_with_retry()` forwards:

```python
workflow="jd-feedback"
stage="parse-low-confidence-batch"
ledger=object()
artifact_root="data/output/run"
input_artifact_hash="hash"
```

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_llm_client.py::test_call_llm_with_retry_forwards_usage_metadata_to_complete_client -q`

Expected: FAIL because `call_llm_with_retry()` does not accept usage metadata yet.

- [ ] **Step 3: Implement pass-through**

Extend `call_llm_with_retry()` keyword-only args and pass them to `client.complete()` when the generic client path is used. Leave direct `client.messages.create()` behavior unchanged.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_llm_client.py::test_call_llm_with_retry_forwards_usage_metadata_to_complete_client -q`

Expected: PASS.

### Task 2: Business LLM Route Coverage

**Files:**
- Modify: `configs/llm-routing.json`
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `scripts/jd_analyzer.py`
- Modify: `scripts/llm_ranker.py`
- Modify: `scripts/score_pipeline.py`
- Test: `tests/test_jd_feedback_note_parser.py`
- Test: `tests/test_jd_analyzer.py`
- Test: `tests/test_llm_ranker.py`
- Test: `tests/test_score_pipeline.py`

- [ ] **Step 1: Write failing tests for route metadata**

Add focused tests that assert:

```python
parse_feedback_note(...).client.calls[0]["kwargs"]["workflow"] == "jd-feedback"
parse_feedback_note(...).client.calls[0]["kwargs"]["stage"] == "parse-single-note"
parse_feedback_notes_batch(...).client.calls[0]["kwargs"]["stage"] == "parse-low-confidence-batch"
analyze_jd(...).call_llm_with_retry(..., workflow="jd-talent-delivery", stage="role-profile")
rank_single_batch(...).call_llm_with_retry(..., stage="detailed-rank")
calibration_round(...).call_llm_with_retry(..., stage="calibration-rank")
run_pipeline(...) uses route model when model is None
```

- [ ] **Step 2: Run red tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_jd_feedback_note_parser.py::test_parse_feedback_note_passes_single_route_metadata \
  tests/test_jd_feedback_note_parser.py::test_parse_feedback_notes_batch_passes_batch_route_metadata \
  tests/test_jd_analyzer.py::TestAnalyzeJd::test_analyze_passes_route_metadata \
  tests/test_llm_ranker.py::TestRankSingleBatch::test_ranks_batch_passes_route_metadata \
  tests/test_llm_ranker.py::TestCalibrationRound::test_calibration_passes_route_metadata \
  tests/test_score_pipeline.py::test_run_pipeline_uses_route_model_when_model_is_not_explicit \
  -q
```

Expected: FAIL because business call sites still use hard-coded `max_tokens` without route metadata.

- [ ] **Step 3: Implement route wiring**

Use `resolve_llm_route()` at each LLM call site. Preserve explicit `model` overrides. Add `jd-feedback.parse-single-note`, set `jd-feedback.parse-low-confidence-batch.max_tokens` to `2048`, and add `jd-talent-delivery.calibration-rank`.

- [ ] **Step 4: Run green tests**

Run the same focused command.

Expected: PASS.

### Task 3: Usage Report Command

**Files:**
- Modify: `scripts/llm_usage.py`
- Test: `tests/test_llm_usage.py`

- [ ] **Step 1: Write failing report test**

Create two monthly JSONL rows and assert:

```python
summary["month"] == "2026-06"
summary["totals"]["calls"] == 2
summary["totals"]["estimated_cost_usd"] == 0.3
summary["groups"][0]["workflow"] == "jd-feedback"
```

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_llm_usage.py::test_summarize_usage_groups_monthly_records_by_route -q`

Expected: FAIL because `summarize_usage()` does not exist.

- [ ] **Step 3: Implement `summarize_usage()` and `report` CLI**

Read `llm-usage-YYYY-MM.jsonl`, group by `workflow/stage/provider/model`, aggregate calls, tokens, cache tokens, source counts, and estimated cost. Add `report --month YYYY-MM --ledger-dir <dir>`.

- [ ] **Step 4: Run green test and CLI smoke**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_usage.py::test_summarize_usage_groups_monthly_records_by_route -q
.venv/bin/python -m scripts.llm_usage report --month 2026-06 --ledger-dir /tmp/nonexistent-ledger
```

Expected: test PASS; CLI outputs a zero-call JSON summary for missing ledger.

### Task 4: Verification And PR Update

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_llm_client.py \
  tests/test_llm_usage.py \
  tests/test_jd_feedback_note_parser.py \
  tests/test_jd_analyzer.py \
  tests/test_llm_ranker.py \
  tests/test_score_pipeline.py \
  -q
```

- [ ] **Step 2: Run full suite**

Run: `.venv/bin/python -m pytest tests -q`

- [ ] **Step 3: Run diff checks**

Run:

```bash
git diff --check
git diff --cached --check
```

- [ ] **Step 4: Commit and push current PR branch**

Commit message: `Instrument LLM usage across ranking workflows`

Push: `git push origin codex/workflow-shared-policies`

---

## Self-Review

- Spec coverage: covers feedback parsing, JD analysis, ranker/calibration, score pipeline route defaults, and monthly report.
- Boundary: does not call real LLM APIs in tests; does not write `data/talent.db`; does not include unrelated research docs.
- Verification: focused tests, full test suite, whitespace checks, and remote hash confirmation.
