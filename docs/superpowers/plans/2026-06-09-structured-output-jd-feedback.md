# Structured Output JD Feedback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 增加 provider-aware structured output adapter，并先接入 JD feedback parser，减少“JSON prompt + 正则抽取”的解析失败面。

**Architecture:** 在 `scripts.llm_client` 增加 `StructuredOutputSchema` 和 `complete_structured()` 协议；Anthropic 与 OpenAI-compatible client 各自把 schema 转成 provider request shape，并继续复用 usage ledger。JD feedback parser 优先调用 `complete_structured()`，缺失能力或失败时回退现有 `call_llm_with_retry()` + `extract_json_object()` 路径。

**Tech Stack:** Python 3.12、pytest、Anthropic Messages shape、OpenAI-compatible chat completions `response_format`。

---

### Task 1: Structured output adapter contract

**Files:**
- Modify: `scripts/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests**

Add tests that:
- `AnthropicMessagesClient.complete_structured()` passes `output_format={"type": "json_schema", "schema": ...}` to `messages.create()` and returns a dict.
- `OpenAICompatibleClient.complete_structured()` sends `response_format={"type": "json_schema", "json_schema": ...}` in `/chat/completions` payload and returns a dict.
- Existing `complete()` usage ledger behavior remains unchanged.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_llm_client.py::test_anthropic_client_complete_structured_sends_json_schema tests/test_llm_client.py::test_openai_compatible_client_complete_structured_sends_response_format -q`
Expected: FAIL because `StructuredOutputSchema` and `complete_structured()` do not exist.

- [ ] **Step 3: Implement minimal adapter**

Add `StructuredOutputSchema` dataclass and `complete_structured()` methods. Parse provider response text/content as JSON object. Record usage through existing `_record_usage_if_requested()`.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_llm_client.py -q`
Expected: PASS.

### Task 2: JD feedback structured schema

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `tests/test_jd_feedback_note_parser.py`

- [ ] **Step 1: Write failing tests**

Add tests that:
- single note parser calls `client.complete_structured()` when available and normalizes returned dict.
- batch parser calls `client.complete_structured()` with an items schema when available.
- fallback client without `complete_structured()` still uses existing prompt JSON path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py::test_parse_feedback_note_uses_structured_output_when_available tests/test_jd_feedback_note_parser.py::test_parse_feedback_notes_batch_uses_structured_output_when_available -q`
Expected: FAIL because parser does not call structured output.

- [ ] **Step 3: Implement JD feedback schemas**

Add schema builders for single and batch feedback. In `_parse_feedback_note_with_llm()` and `_parse_feedback_notes_batch_chunk()`, use `complete_structured()` when present; catch exceptions and fall back to existing `call_llm_with_retry()` path.

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_llm_client.py -q`
Expected: PASS.

### Task 3: Verification and task ledger

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run related tests**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_llm_client.py tests/test_llm_usage.py -q`
Expected: PASS.

- [ ] **Step 2: Run full verification**

Run:
- `git diff --check`
- `.venv/bin/python -m pytest tests -q`

- [ ] **Step 3: Document and stage carefully**

Archive this task in `tasks/archive/2026-06.md`, keep `tasks/todo.md` short, and stage only structured-output hunks, excluding unrelated second-brain research changes.
