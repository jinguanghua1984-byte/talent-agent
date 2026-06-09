# JD Feedback Batch Jobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 JD 推荐反馈解析增加 provider-neutral 离线批处理作业产物，并把 batch job id、custom id、prompt hash、输出 artifact 与 usage 写入成本账本。

**Architecture:** 保留现有规则优先和 in-process batch prompt；新增 `prepare-batch` 生成可提交给 provider batch API 的请求 JSONL/manifest，新增 `apply-batch` 读取 provider 输出并复用既有校验、review queue 和反馈汇总。`LLMUsageLedger` 增加可选 batch 元数据字段，真实 usage 在 apply 阶段按 provider 输出记录，避免把请求估算和真实费用混算。

**Tech Stack:** Python 3.12、pytest、JSONL artifact、现有 `scripts.llm_usage` / `scripts.jd_feedback_note_parser`。

---

### Task 1: 扩展 LLM usage batch 元数据

**Files:**
- Modify: `scripts/llm_usage.py`
- Modify: `tests/test_llm_usage.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_llm_usage.py` 增加测试：`usage_record_from_response(..., batch_job_id="job-1", batch_custom_id="chunk-000001", batch_output_artifact="data/output/run/feedback/batch-jobs/job-1/output.jsonl", output_artifact_hash="out-hash", batch_discount_applied=True)` 应返回包含这些字段的 `LLMUsageRecord`，且 `batch_discount_applied` 参与成本折扣。

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_llm_usage.py::test_usage_record_carries_provider_batch_metadata -q`
Expected: FAIL because `usage_record_from_response` has no batch metadata parameters.

- [ ] **Step 3: Write minimal implementation**

在 `LLMUsageRecord` dataclass 尾部增加可选字段：`batch_job_id`、`batch_custom_id`、`batch_output_artifact`、`output_artifact_hash`，并让 `usage_record_from_response` 接收和填充这些字段。

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_llm_usage.py -q`
Expected: PASS.

### Task 2: 生成 provider-neutral feedback batch job

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `tests/test_jd_feedback_note_parser.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_jd_feedback_note_parser.py` 增加 `test_prepare_feedback_batch_job_writes_manifest_requests_and_rule_results`：构造 outreach CSV，其中 1 条规则可解析、2 条 unresolved；调用 `prepare_feedback_batch_job(root, job_id="job-1")`；断言写出 `feedback/batch-jobs/job-1/batch-job-manifest.json`、`requests.jsonl`、`rule-results.json`，请求 custom id 为 `jd-feedback:job-1:chunk-000001`，prompt 中只包含 unresolved notes，manifest 记录 route/provider/model/stage、source CSV hash、prompt hash 和 expected output path。

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py::test_prepare_feedback_batch_job_writes_manifest_requests_and_rule_results -q`
Expected: FAIL because `prepare_feedback_batch_job` does not exist.

- [ ] **Step 3: Write minimal implementation**

新增 `prepare_feedback_batch_job()`，复用 CSV 校验、规则解析、`build_feedback_batch_prompt()` 和 route；按 `BATCH_PARSE_SIZE` 将 unresolved notes 分 chunk，写 manifest/request/rule-results，不调用 LLM、不写最终 `delivery-feedback.json`。

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py -q`
Expected: PASS.

### Task 3: 应用 batch output 并记录 usage

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `tests/test_jd_feedback_note_parser.py`

- [ ] **Step 1: Write the failing test**

在 `tests/test_jd_feedback_note_parser.py` 增加 `test_apply_feedback_batch_job_output_combines_rule_and_batch_results_and_records_usage`：先 prepare job，再写 provider output JSONL，包含 `custom_id`、`response.body.content[0].text`、`usage`、`id` 和 `stop_reason`；调用 `apply_feedback_batch_job(root, job_dir, output_jsonl, ledger=LLMUsageLedger(tmp_path / "ledger"))`；断言最终反馈输出包含 rule + batch accepted/review，ledger row 包含 `batch_job_id`、`batch_custom_id`、`batch_output_artifact`、`output_artifact_hash`、`batch_discount_applied=True` 和 provider usage tokens。

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py::test_apply_feedback_batch_job_output_combines_rule_and_batch_results_and_records_usage -q`
Expected: FAIL because `apply_feedback_batch_job` does not exist.

- [ ] **Step 3: Write minimal implementation**

新增 `apply_feedback_batch_job()`，读取 manifest/request/rule-results/output JSONL，按 chunk item index 规范化解析结果，复用最终输出写入逻辑；调用 `usage_record_from_response()` 生成 ledger row，并填充 batch metadata。

- [ ] **Step 4: Run focused tests**

Run: `.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_llm_usage.py -q`
Expected: PASS.

### Task 4: CLI 和验证

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `tests/test_jd_feedback_note_parser.py`
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Write CLI tests**

增加 `prepare-batch` 和 `apply-batch` CLI smoke tests，确认命令返回 0、输出 artifact 存在，且 validation error 不带 traceback。

- [ ] **Step 2: Implement CLI**

`python -m scripts.jd_feedback_note_parser prepare-batch --run-root <run_root> [--job-id <id>]` 生成 batch job；`apply-batch --run-root <run_root> --job-dir <dir> --output-jsonl <path> [--ledger-dir <dir>]` 应用结果并可写 usage ledger。

- [ ] **Step 3: Verify**

Run:
`.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_llm_usage.py tests/test_llm_client.py -q`
`.venv/bin/python -m pytest tests -q`

- [ ] **Step 4: Document results**

将 `tasks/todo.md` Active Task 写 Review，并把完整任务记录归档到 `tasks/archive/2026-06.md`；提交时只 staging 本任务相关文件。
