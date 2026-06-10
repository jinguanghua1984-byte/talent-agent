# LLM Ranker Hard Budget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 LLM 精排增加硬预算，限制进入 LLM 的候选人数和每个候选人的 evidence 长度，直接降低 ranker 输入 token。

**Architecture:** 在 `scripts/llm_ranker.py` 内集中实现预算：`rank_candidates()` 负责限制新增 LLM 调用候选人数，`build_rank_prompt()` / `_format_candidate()` 负责限制每人 evidence 字符数。`scripts/score_pipeline.py` 只暴露 CLI 和编排参数，不重复实现预算逻辑。缓存命中的候选人不消耗新的 LLM 预算，未命中的候选人按输入顺序截断；score pipeline 会按粗筛分数顺序传入候选人。

**Tech Stack:** Python stdlib, pytest, existing `scripts.llm_ranker`, `scripts.score_pipeline`.

---

### Task 1: Ranker Evidence Budget

**Files:**
- Modify: `scripts/llm_ranker.py`
- Test: `tests/test_llm_ranker.py`

- [ ] **Step 1: Write failing test for per-candidate evidence limit**

Add a test that builds a prompt from one candidate with a long `_desc_raw` and long work experience, calls:

```python
prompt = build_rank_prompt(SAMPLE_JD_TEXT, [long_candidate], evidence_max_chars=240)
```

Assert the prompt still contains the candidate ID and JD, but the candidate block is bounded and long repeated text is truncated.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_llm_ranker.py::TestBuildRankPrompt::test_applies_per_candidate_evidence_budget -q`

Expected: FAIL because `build_rank_prompt()` does not accept `evidence_max_chars`.

- [ ] **Step 3: Implement evidence budget**

Add `DEFAULT_CANDIDATE_EVIDENCE_MAX_CHARS = 1200`. Thread `evidence_max_chars` through `_format_candidate()` and `build_rank_prompt()`. Keep the candidate header visible, truncate body with `...` when over budget.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_llm_ranker.py::TestBuildRankPrompt::test_applies_per_candidate_evidence_budget -q`

Expected: PASS.

### Task 2: Rank Candidate Count Budget

**Files:**
- Modify: `scripts/llm_ranker.py`
- Test: `tests/test_llm_ranker.py`

- [ ] **Step 1: Write failing test for rank limit**

Patch `rank_single_batch`, pass five unscored candidates with `rank_limit=3`, and assert only the first three IDs are sent to LLM.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_llm_ranker.py::TestRankCandidates::test_limits_new_llm_candidates_before_batching -q`

Expected: FAIL because `rank_candidates()` does not accept `rank_limit`.

- [ ] **Step 3: Implement rank limit**

Add `DEFAULT_RANK_LIMIT = 60`. `rank_candidates()` should cap `unscored` to remaining budget before batching. If `rank_limit=None`, keep old unlimited behavior.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_llm_ranker.py::TestRankCandidates::test_limits_new_llm_candidates_before_batching -q`

Expected: PASS.

### Task 3: Score Pipeline Wiring

**Files:**
- Modify: `scripts/score_pipeline.py`
- Test: `tests/test_score_pipeline.py`

- [ ] **Step 1: Write failing test for pipeline knobs and coarse ordering**

Patch `screen_candidates()` to return scored IDs in an order different from the input list. Call `run_pipeline(..., rank_limit=2, candidate_evidence_max_chars=333)`. Assert `rank_candidates()` receives candidates in coarse score order and receives both budget parameters.

- [ ] **Step 2: Run red test**

Run: `.venv/bin/python -m pytest tests/test_score_pipeline.py::test_run_pipeline_passes_rank_budget_and_preserves_coarse_order -q`

Expected: FAIL because `run_pipeline()` does not accept the budget params.

- [ ] **Step 3: Implement pipeline wiring**

Add `rank_limit` and `candidate_evidence_max_chars` arguments to `run_pipeline()`. Add `--rank-limit` and `--candidate-evidence-max-chars` to `run` and `resume`. Build `coarse_candidates` by coarse score order, not original candidate order.

- [ ] **Step 4: Run green test**

Run: `.venv/bin/python -m pytest tests/test_score_pipeline.py::test_run_pipeline_passes_rank_budget_and_preserves_coarse_order -q`

Expected: PASS.

### Task 4: Verification And PR Update

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_llm_ranker.py tests/test_score_pipeline.py -q
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

Commit message: `Add hard budgets for LLM ranking`

Push: `git push origin codex/workflow-shared-policies`

---

## Self-Review

- Spec coverage: covers candidate evidence length, candidate count budget, score pipeline knobs, coarse score ordering, and verification.
- Boundary: does not call real LLM APIs; does not change ranking prompt semantics except truncating evidence; does not write database files.
- Ambiguity resolved: default hard budget is Top 60 for new LLM calls and 1200 chars per candidate evidence block; callers may override or pass `None` for unlimited rank count.
