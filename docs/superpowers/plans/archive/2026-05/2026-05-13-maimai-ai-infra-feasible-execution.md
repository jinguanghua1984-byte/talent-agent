# Maimai AI Infra Feasible Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Phase 0 已验证的技术边界内落地 AI Infra 人才采集、入库、评分、详情补全和最终审查流水线。

**Architecture:** 搜索与本地数据处理自动化，详情补全采用 human-in-the-loop popup 路径。系统不再追求“完全无人执行”，而是把风险动作固定在用户可见、可停止的 popup 触发点：本地生成任务包，用户在人才银行页 popup 加载/启动，导出后本地 dry-run/apply。

**Tech Stack:** Python 3, SQLite `data/talent.db`, Chrome/Edge MV3 extension `extensions/maimai-scraper`, localhost plan server, pytest, node syntax check。

---

## Current Feasible Boundary

### Keep

- `configs/maimai-ai-infra-search-strategy.json`
- `scripts/maimai_ai_infra_search_plan.py`
- `scripts/maimai_ai_infra_search_runner.py` dry-run-template-only and small-gate search runner logic
- `scripts/maimai_ai_infra_rank.py`
- `scripts/maimai_ai_infra_pipeline.py`
- `scripts/maimai_detail_targets.py`
- `scripts/maimai_detail_plan_server.py`
- `scripts/maimai_detail_import.py`
- `scripts/maimai_trace_diff.py`
- popup 批量详情路径

### Replace

- Replace `automation.html -> startDetailBatch` with `local detail plan server -> user opens popup -> load/start detail`.
- Replace “人工只参与策略确认和最终审查” with four human gates:
  1. 策略确认
  2. 搜索 apply 确认
  3. 详情 popup 启动
  4. 详情 apply 确认

### Prohibit

- No `automation.html` real detail fetch.
- No CDP/Runtime.evaluate real detail start.
- No automatic refresh/navigation/activation of talent bank page.
- No automatic recovery after login/captcha/security page.

## File Structure

Modify:

- `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` — mark reviewed and superseded for execution details.
- `data/output/maimai-ai-infra-feasibility-2026-05-12.md` — keep final Phase 0 conclusion.
- `tasks/todo.md` — track each execution gate and review result.

Create:

- `data/output/maimai-ai-infra-execution-YYYY-MM-DD.md` — final execution report for each run.
- `data/output/raw/maimai-ai-infra-search-run-YYYY-MM-DD.json` — raw search evidence.
- `data/output/raw/maimai-ai-infra-detail-targets-YYYY-MM-DD.json` — detail target task package.
- `data/output/raw/maimai-ai-infra-detail-capture-YYYY-MM-DD.json` — user-exported detail capture copy.

Do not modify:

- `data/talent.db` unless an apply command is explicitly authorized and preceded by clean dry-run.
- Downloaded source JSON files except copying them into `data/output/raw/`.

## Gate Definitions

| Gate | Scope | Pass Standard |
| --- | --- | --- |
| S1 | 3 search batches x 1 page | Already passed |
| S2 | 5 search batches x 1 page | JSON 200, no login/captcha/429, import dry-run clean |
| S3 | 5 search batches x 3 pages | useful A/B candidates, import dry-run clean |
| D1 | 3 detail targets via popup | Already passed |
| D2 | 10 detail targets via popup | failed_jobs=0, trace popup/visible |
| D3 | 30 detail targets via popup | failed_jobs=0, safe mode completes |

## Execution Status Update

> 2026-05-13 执行复核：本计划的 Task 1-9 已按门禁原则完成并验证。原 S2 精确查询平台门禁通过但业务结果为 0，因此未对 S2 空结果做 apply；随后按执行记录追加 S2b 宽查询并完成搜索 dry-run/apply、shortlist、D2 详情 dry-run/apply。D3 30 人详情放大门禁也已通过 popup local plan 路径完成 dry-run/apply。Gate 表中的 S3（5 批 x 3 页）已在用户授权后执行并写入：完整 raw 为 `data/output/raw/maimai-ai-infra-search-run-s3-2026-05-13.json`，contacts payload 为 `data/output/raw/maimai-ai-infra-search-run-s3-2026-05-13.contacts.json`，导入 dry-run 为 `data/output/talent-import-ai-infra-s3-dry-run-2026-05-13.md`，apply 报告为 `data/output/talent-import-ai-infra-s3-apply-2026-05-13.md`。S3 apply 通过现有 `talent_library.py import` DB 工具完成；下一步可基于 S3 shortlist 选择新一轮详情目标。

## Task 1: Archive Phase 0 Final Result

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`
- Modify: `tasks/todo.md`

- [x] **Step 1: Add supersession note to old plan**

Add at the top of `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`:

```markdown
> 2026-05-13 复审结论：本计划的“完全无人执行详情补全”目标不再成立。搜索 dry-run 和本地评分仍保留；真实详情补全改为 `CLI 本地任务包服务 + 用户在人才银行页 popup 加载/启动 + 导出 + dry-run`。落地执行以 `docs/superpowers/plans/2026-05-13-maimai-ai-infra-feasible-execution.md` 为准。
```

- [x] **Step 2: Verify the note exists**

Run:

```bash
rg -n "2026-05-13 复审结论|feasible-execution" docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md
```

Expected: both phrases appear.

## Task 2: Prepare Search Batch Gate S2

**Files:**
- Read: `configs/maimai-ai-infra-search-strategy.json`
- Read: `scripts/maimai_ai_infra_search_plan.py`
- Output: `data/output/maimai-ai-infra-search-plan-s2-YYYY-MM-DD.json`

- [x] **Step 1: Generate current search plan**

Run:

```bash
python scripts/maimai_ai_infra_search_plan.py --config configs/maimai-ai-infra-search-strategy.json --out data/output/maimai-ai-infra-search-plan-s2-2026-05-13.json
```

Expected:

- file exists
- batches are ordered by priority
- each batch has `query`, `page_size`, `max_pages`

- [x] **Step 2: Select first 5 S2 batches**

Create:

```text
data/output/raw/maimai-ai-infra-search-plan-s2-selected-2026-05-13.json
```

The file must contain:

```json
{
  "gate": "S2",
  "max_batches": 5,
  "max_pages_per_batch": 1,
  "writeDb": false,
  "apply": false,
  "detailFetch": false,
  "batches": []
}
```

Fill `batches` with the first 5 batches from the generated plan.

- [x] **Step 3: Run template dry-run**

Run:

```bash
python scripts/maimai_ai_infra_search_runner.py --plan data/output/maimai-ai-infra-search-plan-s2-2026-05-13.json --template data/output/raw/maimai-ai-infra-search-template-2026-05-12.json --out data/output/raw/maimai-ai-infra-search-run-s2-template-2026-05-13.json --dry-run-template-only
```

Expected:

- no network access
- patched body only changes `query/search_query` and pagination

## Task 3: Execute Search Gate S2

**Files:**
- Output: `data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.json`
- Output: `data/output/talent-import-ai-infra-s2-dry-run-2026-05-13.md`

- [x] **Step 1: Ask user to prepare browser**

User actions:

1. Open the dedicated Edge profile.
2. Open and keep talent bank page stable.
3. Do not open `automation.html`.
4. Confirm no login page or captcha.

- [x] **Step 2: Run S2 live search only after explicit authorization**

Run the existing search gate runner or equivalent script with these constraints:

```text
gate=S2
max_batches=5
max_pages_per_batch=1
writeDb=false
apply=false
detailFetch=false
patch_fields=query/search_query,pagination
stop_on=login,captcha,403,429,non_json
```

Output:

```text
data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.json
```

Expected:

- each response HTTP 200 JSON, or batch is cleanly marked stopped
- no DB writes

- [x] **Step 3: Convert contacts payload**

Run:

```bash
python - <<'PY'
from pathlib import Path
from scripts.maimai_ai_infra_pipeline import extract_contacts_payload
extract_contacts_payload(
    Path("data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.json"),
    Path("data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.contacts.json"),
)
PY
```

- [x] **Step 4: Import dry-run**

Run:

```bash
python scripts/talent_library.py import --input data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.contacts.json --db data/talent.db --out data/output/talent-import-ai-infra-s2-dry-run-2026-05-13.md
```

Pass standard:

- `errors=0`
- `pending=0`

If dry-run is not clean, stop and write an exception report.

## Task 4: Search Apply Gate

**Files:**
- Read: `data/output/talent-import-ai-infra-s2-dry-run-2026-05-13.md`
- Output: `data/output/talent-import-ai-infra-s2-apply-2026-05-13.md`

- [x] **Step 1: Ask for explicit apply authorization**

Only proceed if the user says:

```text
确认导入 AI Infra 搜索结果
```

- [x] **Step 2: Apply import**

Run:

```bash
python scripts/talent_library.py import --input data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.contacts.json --db data/talent.db --out data/output/talent-import-ai-infra-s2-apply-2026-05-13.md --apply --confirm "确认导入人才"
```

Expected:

- no errors
- result counts recorded in execution report

## Task 5: Rank and Produce Shortlist

**Files:**
- Output: `data/output/maimai-ai-infra-shortlist-s2-2026-05-13.json`
- Output: `data/output/maimai-ai-infra-shortlist-s2-2026-05-13.md`

- [x] **Step 1: Run ranking**

Run:

```bash
python scripts/maimai_ai_infra_rank.py --db data/talent.db --config configs/maimai-ai-infra-search-strategy.json --out-json data/output/maimai-ai-infra-shortlist-s2-2026-05-13.json --out-md data/output/maimai-ai-infra-shortlist-s2-2026-05-13.md
```

Expected:

- JSON contains `grades.A`, `grades.B`, `grades.C`, `grades.淘汰`
- Markdown contains A/B sections with evidence

- [x] **Step 2: Select detail targets**

For D2, select:

- all A candidates from new/updated search pool
- enough B candidates to reach 10 total targets

Run:

```bash
python scripts/maimai_detail_targets.py from-file --input data/output/maimai-ai-infra-shortlist-s2-2026-05-13.json --db data/talent.db --out data/output/raw/maimai-ai-infra-detail-targets-d2-2026-05-13.json
```

Expected:

- `totalContacts <= 10`
- `missing=0` preferred; missing items go into report

## Task 6: Detail Gate D2 via Popup Local Plan

**Files:**
- Input: `data/output/raw/maimai-ai-infra-detail-targets-d2-2026-05-13.json`
- Output: user downloaded capture path
- Output: `data/output/maimai-ai-infra-detail-d2-dry-run-2026-05-13.md`

- [x] **Step 1: Start local detail plan server**

Run:

```bash
python scripts/maimai_detail_plan_server.py --plan data/output/raw/maimai-ai-infra-detail-targets-d2-2026-05-13.json --port 8765
```

Expected:

```text
http://127.0.0.1:8765/detail-plan.json
```

- [x] **Step 2: Ask user to execute popup path**

User actions:

1. Reload the extension.
2. Refresh or reopen talent bank page manually.
3. Keep talent bank page active.
4. Open extension popup.
5. Go to 批量详情.
6. Click `加载任务包`.
7. Confirm imported count.
8. Click `开始详情`.
9. Wait for completion.
10. Click `导出 JSON`.
11. Send downloaded file path.

- [x] **Step 3: Copy raw capture**

Run:

```bash
python - <<'PY'
from pathlib import Path
import shutil
src = Path(r"<USER_DOWNLOADED_CAPTURE>")
dst = Path("data/output/raw/maimai-ai-infra-detail-capture-d2-2026-05-13.json")
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(src, dst)
print(dst)
PY
```

Replace `<USER_DOWNLOADED_CAPTURE>` with the path provided by the user.

- [x] **Step 4: Dry-run detail import**

Run:

```bash
python scripts/maimai_detail_import.py dry-run --capture-file data/output/raw/maimai-ai-infra-detail-capture-d2-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-d2-dry-run-2026-05-13.md
```

Pass standard:

- `failed_jobs=0`
- unmatched is explainable
- no login/captcha/security evidence in trace

## Task 7: Detail Apply Gate

**Files:**
- Read: `data/output/maimai-ai-infra-detail-d2-dry-run-2026-05-13.md`
- Output: `data/output/maimai-ai-infra-detail-d2-apply-2026-05-13.md`
- Output: `data/output/maimai-ai-infra-detail-d2-apply-2026-05-13.json`

- [x] **Step 1: Ask for explicit detail apply authorization**

Only proceed if the user says:

```text
确认写入 AI Infra 脉脉详情
```

- [x] **Step 2: Apply details**

Run:

```bash
python scripts/maimai_detail_import.py apply --capture-file data/output/raw/maimai-ai-infra-detail-capture-d2-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-d2-apply-2026-05-13.md --json-out data/output/maimai-ai-infra-detail-d2-apply-2026-05-13.json --confirm "确认写入脉脉详情"
```

Expected:

- `written > 0`
- no failed jobs are written

## Task 8: Final Execution Report

**Files:**
- Create: `data/output/maimai-ai-infra-execution-2026-05-13.md`

- [x] **Step 1: Build report**

Report must include:

- strategy version
- S2 batch count and stop reasons
- search import dry-run/apply result
- shortlist A/B/C counts
- D2 target count
- detail dry-run/apply result
- raw file list
- unresolved risks
- next gate recommendation

- [x] **Step 2: Verify report references all required files**

Run:

```bash
rg -n "search-run-s2|shortlist-s2|detail-targets-d2|detail-capture-d2|dry-run" data/output/maimai-ai-infra-execution-2026-05-13.md
```

Expected: all required filenames appear.

## Task 9: Verification

**Files:**
- No production data writes unless apply gates were authorized.

- [x] **Step 1: Run focused tests**

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py tests/test_maimai_trace_diff.py -q
```

- [x] **Step 2: Run syntax checks**

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/popup.js
python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_detail_plan_server.py scripts/maimai_trace_diff.py
git diff --check
```

- [x] **Step 3: Run full regression**

```bash
python -m pytest tests scripts -q
```

Expected: pass, aside from already-known warnings.

## Operational Rule

After every run, archive raw inputs and outputs in `data/output/raw/`. If a browser/platform signal appears, stop immediately and write the failure into the execution report; do not retry in the same run.

## Self-Review

- Spec coverage: updates the old automated plan, records Phase 0 lessons, preserves feasible search/rank/pipeline work, replaces unsafe detail automation with popup local plan.
- Placeholder scan: no unresolved placeholder wording.
- Type consistency: file names use S2/D2 gate names consistently; apply confirmation strings match existing CLI contracts.

## D4 Remaining 205 Execution Update

- 2026-05-13：D4 首段 100 人详情已通过现有 `scripts/maimai_detail_import.py apply` 写入；剩余 continuation 包为 `data/output/raw/maimai-ai-infra-detail-targets-d4-s3-all-a-remaining-205-2026-05-13.json`。
- 已按用户要求将详情每日上限默认值临时调整为 `10000`，由用户人工把握节奏；popup 输入框最大值也同步为 `10000`。
- 剩余包复核：`totalContacts=205`、`contacts=205`、`missing=0`、首位联系人为徐睿（`229042988`）。
- 已启动只读 detail plan server：`http://127.0.0.1:8765/detail-plan.json`，`/health` 返回 `ok=true,totalContacts=205`。
- 服务日志：`data/output/raw/maimai-detail-plan-server-d4-s3-all-a-remaining-205-8765.out.log` 与 `data/output/raw/maimai-detail-plan-server-d4-s3-all-a-remaining-205-8765.err.log`。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q` -> **39 passed**；`python -m pytest tests scripts -q` -> **457 passed, 1 warning**；`node --check extensions/maimai-scraper/detail_batch.js extensions/maimai-scraper/popup.js extensions/maimai-scraper/automation.js` -> **PASS**；`git diff --check` -> **PASS**。
- 本轮不写 DB。用户导出剩余详情 JSON 后，仍需先执行 dry-run；只有用户明确回复 `确认写入 AI Infra 脉脉详情` 后才允许调用现有 DB 工具写入。

## D4 Batch Pause Recovery Update

- 2026-05-13：D4 剩余 205 人执行到 `30/205` 后，批间休息倒计时到 0 秒未继续。
- 根因：MV3 background service worker 可能在 5-10 分钟长 `setTimeout` 中被浏览器挂起；`batch_pause_until` 已持久化，但内存中的 `DetailBatch.run()` 等待链丢失。
- 修复：`getDetailBatchStatus/getScraperSummary` 会调用 `recoverExpiredBatchPauseIfNeeded()`；若 `batch_pause_until` 已过期且仍有剩余 jobs，则从 `DetailDB.getAllJobs()` 与持久化 state 恢复同一 run token 续跑。
- 约束：恢复路径不清空 jobs/details，不重新导入任务包；优先使用持久化的 `detailBatchTabId`，缺失或失效时只回退到当前已激活的人才银行 tab，不自动导航或刷新。
- 验证：新增红测 `test_background_recovers_expired_batch_pause_from_persisted_jobs`；聚焦测试 **40 passed**，全量回归 **458 passed, 1 warning**，JS 语法检查与 `git diff --check` 通过。

## D4 Batch Pause Progress Display Update

- 2026-05-13：现场出现日志已到 `120/205`，但批间暂停状态回退显示 `60/205`。
- 根因：`batch_pause_completed` 使用当前 `DetailBatch.run()` 调用内的 `processed` 计数；service worker 恢复续跑后该计数不是全量累计完成数。
- 修复：批间暂停写入 `state.counts.done/failed/skipped` 的累计完成数；background/popup/悬浮球显示时取 `batch_pause_completed` 与真实 counts 的较大值，兼容已持久化的旧错误状态。
- 验证：新增红测 `test_batch_pause_progress_uses_cumulative_completed_count_after_resume`；聚焦测试 **41 passed**，全量回归 **459 passed, 1 warning**，JS 语法检查与 `git diff --check` 通过。

## D4 Remaining 205 Dry-Run Update

- 2026-05-13：用户提供 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13.json`；复核发现该文件与早先 D4 首段 `100/305` capture 哈希相同。
- 实际采用 Downloads 最新文件 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (1).json`，归档为 `data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-remaining-205-2026-05-13.json`。
- capture 统计：`contacts=205`、`detailJobs=205`、`details=205`、job 状态 `done=205`、最后日志 `批量详情已完成`。
- dry-run：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-dry-run-2026-05-13.md` -> 匹配 205、未匹配 0、失败 jobs 0、写入人数 0。
- 本轮未写 DB；本地 detail plan server 已停止。下一步只有在用户明确回复 `确认写入 AI Infra 脉脉详情` 后，才允许调用现有 `scripts/maimai_detail_import.py apply`。

## D4 Remaining 205 Apply Update

- 2026-05-13：用户明确授权 `确认写入 AI Infra 脉脉详情，使用已有db工具`。
- 使用现有工具：`scripts/maimai_detail_import.py apply`；未手写 SQL 或自定义写库逻辑。
- apply 报告：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.md`；apply JSON：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.json`。
- apply 结果：匹配 205、未匹配 0、失败 jobs 0、写入人数 205、`verified_candidate_ids=205`。
- 写后只读 dry-run：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-post-apply-dry-run-2026-05-13.md` -> 匹配 205、未匹配 0、失败 jobs 0。
- 验证：详情导入聚焦测试 **9 passed**，相关脚本 py_compile 通过，`git diff --check` 通过。
