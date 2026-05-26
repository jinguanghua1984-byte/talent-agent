# Todo Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `tasks/todo.md` 从长期历史日志改造成“当前工作台”，把已完成任务归档到低频读取文件，降低上下文 token 消耗、减少合并冲突，并保留可追溯证据。

**Architecture:** `tasks/todo.md` 只保留当前活跃任务、未完成项、最近完成摘要和归档索引；历史完整 Review 迁移到 `tasks/archive/YYYY-MM.md`。仓库级规则写入 `AGENTS.md`，让后续 agent 默认只读活跃区，需要历史时用 `rg` 定向检索归档。

**Tech Stack:** Markdown、PowerShell、`rg`、Git、现有 pytest 验证命令。

---

## File Structure

- Modify: `tasks/todo.md`
  - 只保留当前活跃区、未完成项、最近完成摘要和 Archive Index。
- Create: `tasks/archive/README.md`
  - 说明归档目录用途、写入格式、检索方式。
- Create: `tasks/archive/2026-05.md`
  - 承接当前 `tasks/todo.md` 中已经完成的 2026-05 历史任务完整记录。
- Modify: `AGENTS.md`
  - 在 Task Management 中加入 todo token 治理规则，防止后续继续无限追加。
- Optional later: `scripts/check_task_ledger.py`
  - 仅当手工治理反复失效时再加，不在本轮默认实现。

## Success Criteria

- `tasks/todo.md` 从约 `363KB / 927 lines` 降到目标 `150-300 lines`。
- `tasks/todo.md` 顶部包含明确的 `Active Task`、`Open Items`、`Recent Done`、`Archive Index`。
- 已完成历史没有丢失，能在 `tasks/archive/2026-05.md` 通过标题和关键词检索到。
- `AGENTS.md` 明确要求 todo 只做当前工作台，完成任务后归档。
- `git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md` 通过。
- 如本轮只改文档和任务账本，不需要运行全量 `python -m pytest tests scripts -q`；若同时改脚本或 workflow，再运行全量测试。

---

### Task 1: Baseline And Safety Check

**Files:**
- Read: `tasks/todo.md`
- Read: `AGENTS.md`
- Read: git worktree state

- [x] **Step 1: Confirm current branch and dirty files**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## main...origin/main [ahead N]
```

There may be existing modified or untracked files. Do not revert or stage unrelated changes.

- [x] **Step 2: Measure current todo size**

Run:

```powershell
(Get-Content tasks/todo.md -Encoding UTF8 | Measure-Object -Line -Word -Character) | Format-List
Get-Item tasks/todo.md | Select-Object FullName,Length,LastWriteTime | Format-List
```

Expected:

```text
Lines      : around 927
Length     : around 363171
```

Record the exact before metrics in the final Review.

- [x] **Step 3: List top-level task headings**

Run:

```powershell
rg -n "^# " tasks/todo.md
```

Expected: a list of historical task headings. Use it to decide which completed blocks move to `tasks/archive/2026-05.md`.

---

### Task 2: Add Archive Governance Files

**Files:**
- Create: `tasks/archive/README.md`
- Create: `tasks/archive/2026-05.md`

- [x] **Step 1: Create archive directory**

Run:

```powershell
New-Item -ItemType Directory -Force tasks/archive
```

Expected:

```text
Directory: D:\workspace\talent-agent\tasks
```

- [x] **Step 2: Add archive README**

Create `tasks/archive/README.md` with this content:

```markdown
# Task Archive

这里保存已经完成的任务记录。`tasks/todo.md` 只作为当前工作台，不长期保存完整历史。

## 归档规则

- 完成任务后，把完整计划和 Review 移到 `tasks/archive/YYYY-MM.md`。
- `tasks/todo.md` 只保留最近 1-3 个完成摘要，以及归档索引。
- 归档内容保持 append-only；合并冲突时保留双方记录。
- 查历史优先用 `rg "<关键词>" tasks/archive tasks/lessons.md memory/error-log.md`。

## 写入格式

每个归档块保留原任务标题、目标、计划、Review、关键产物路径、验证命令和结果。
```

- [x] **Step 3: Create monthly archive header**

Create `tasks/archive/2026-05.md` with this content:

```markdown
# 2026-05 Task Archive

> 从 `tasks/todo.md` 迁出的已完成任务记录。迁移只改变存放位置，不改变事实内容。

```

---

### Task 3: Trim `tasks/todo.md` Into Active Ledger

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-05.md`

- [x] **Step 1: Identify active or unfinished blocks**

Run:

```powershell
rg -n "\[ \]|阻塞|待|下一步|未完成|pending|TODO" tasks/todo.md
```

Expected: a short list of truly open items. Keep these in `tasks/todo.md`; completed historical blocks move to archive.

- [x] **Step 2: Move completed historical blocks**

Move completed task blocks from `tasks/todo.md` into `tasks/archive/2026-05.md` under the monthly header. Preserve each block's original title, goal, plan, Review, links, and verification evidence.

Do not summarize the archived block during the move. Summaries belong in `tasks/todo.md`, not in the archive.

- [x] **Step 3: Rewrite `tasks/todo.md` header**

Make `tasks/todo.md` start with this structure:

```markdown
# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- 当前无主动执行中的任务；下一次任务开始时在这里写计划。

## Open Items

- [x] 执行 `docs/superpowers/plans/2026-05-22-todo-governance.md`，完成 todo 治理落地。

## Recent Done

- 2026-05-22：已形成 todo token 治理实施计划，详见 `docs/superpowers/plans/2026-05-22-todo-governance.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
```

If there are genuine unfinished items discovered in Step 1, add them under `Open Items` with source pointers.

- [x] **Step 4: Measure new todo size**

Run:

```powershell
(Get-Content tasks/todo.md -Encoding UTF8 | Measure-Object -Line -Word -Character) | Format-List
Get-Item tasks/todo.md | Select-Object FullName,Length,LastWriteTime | Format-List
```

Expected:

```text
Lines      : between 150 and 300, or lower if there are few open items
Length     : much lower than 363171
```

---

### Task 4: Update Agent Instructions

**Files:**
- Modify: `AGENTS.md`

- [x] **Step 1: Add todo governance under Task Management**

Update the Task Management section with this rule:

```markdown
3.  **Token Governance**: `tasks/todo.md` 是当前工作台，不是长期历史库。默认只保留 Active Task、Open Items、最近 1-3 个 Recent Done 和 Archive Index；完成任务后将完整记录迁移到 `tasks/archive/YYYY-MM.md`。
4.  **Historical Lookup**: 需要历史上下文时，先用 `rg` 在 `tasks/archive/`、`tasks/lessons.md`、`memory/error-log.md` 中按关键词检索，不要默认整段读取历史归档。
```

Renumber the following Task Management items so the list stays sequential.

- [x] **Step 2: Keep existing project rules intact**

Verify these rules still exist in `AGENTS.md` after editing:

```powershell
rg -n "Plan First|Verify Plan|Track Progress|Document Results|中文沟通|python -m pytest tests scripts -q" AGENTS.md
```

Expected: each pattern is found.

---

### Task 5: Verification And Review

**Files:**
- Read: `tasks/todo.md`
- Read: `tasks/archive/2026-05.md`
- Read: `AGENTS.md`

- [x] **Step 1: Check Markdown diff hygiene**

Run:

```powershell
git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md
```

Expected:

```text
```

No output means pass.

- [x] **Step 2: Verify archive searchability**

Run:

```powershell
rg -n "飞书推送|LLM 推理|GitHub HR|工作台提示" tasks/archive/2026-05.md
```

Expected: historical task headings or Review lines are found in the archive.

- [x] **Step 3: Verify todo stays small and useful**

Run:

```powershell
Get-Content tasks/todo.md -Encoding UTF8 -TotalCount 80
```

Expected: the first 80 lines show current ledger sections, not a long completed-task history.

- [x] **Step 4: Write final Review in `tasks/todo.md`**

Add a concise Review under the active governance item:

```markdown
## Review

- `tasks/todo.md` 已缩减为当前工作台；完整历史迁移到 `tasks/archive/2026-05.md`。
- 迁移前：`<exact before lines>` lines，`<exact before bytes>` bytes；迁移后：`<exact after lines>` lines，`<exact after bytes>` bytes。
- 归档检索验证通过：`rg -n "飞书推送|LLM 推理|GitHub HR|工作台提示" tasks/archive/2026-05.md` 命中历史记录。
- diff hygiene 通过：`git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md`。
- 本轮只改文档/任务账本，未运行全量 pytest；若后续改到脚本或 workflow，再运行 `python -m pytest tests scripts -q`。
```

Replace angle-bracket values with exact measured numbers before marking complete.

---

## Rollback Plan

- If archive migration goes wrong, restore only the touched task files from Git or from the pre-migration diff. Do not reset unrelated dirty files.
- If `tasks/todo.md` loses an open item, recover it from `tasks/archive/2026-05.md` or `git diff`.
- If `AGENTS.md` numbering becomes confusing, keep the new token governance rules but reformat the list only; do not remove existing workflow rules.
