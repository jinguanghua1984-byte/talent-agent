# 脉脉批量详情抓取 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or equivalent task-by-task execution. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `extensions/maimai-scraper` 中新增可暂停、可恢复、低速限流、可熔断的脉脉批量详情抓取能力，把几十到几百人的详情补全从手动逐个点击升级为扩展内顺序接口重放；本地入库继续走 `talent-library detail` 的 dry-run、确认、写入和逐人验证流程。

**Design Source:** `docs/design-discussions/2026-05-10-maimai-batch-detail-capture-design.md`

**Architecture:** 扩展负责在真实 Chrome 登录态、脉脉列表页上下文中批量重放详情接口并导出完整 JSON；本地 Python 脚本负责解析导出、精确匹配 `source_profiles.platform_id`、字段映射、dry-run 报告、确认写入和验证。第一阶段不使用 CDP，不打开外部 profile/detail 新页，不实现 DOM 自动点击兜底。

**Tech Stack:** Chrome Extension Manifest V3, plain JavaScript, IndexedDB, `chrome.storage.local`, Python 3.11+, SQLite `TalentDB`, pytest.

**Scope:** 实施 Phase 1-3 和必要的 Phase 5 入库工具化：接口重放最小闭环、多接口补全、断点恢复与熔断、完整导出、dry-run/apply CLI、workflow 文档。Phase 4 自动点击兜底只保留接口和文档占位，不在本计划首轮实现。

---

## 已知约束

1. 详情抓取必须发生在真实 Chrome 登录态中的脉脉页面上下文。
2. 禁止把 CDP / Playwright `page.evaluate(fetch)` 作为批量抓取方案基础。
3. 外部 `profile/detail` 新开页捕获不稳定，不作为主路径。
4. 列表页联系人 `id` 是详情接口 `to_uid`；`trackable_token` 通常可直接复用，但必须有失败兜底状态。
5. 核心详情接口是 `/api/ent/talent/basic`，不是旧 `/api/pc/u/`。
6. 完整导出必须包含 `contacts`、`details`、`detailJobs`、`requests`，不能只导出 `PagerDB.contacts`。
7. 涉及个人信息的导出 JSON、SQLite 数据库和报告不得提交到远端仓库。

---

## 当前系统事实

1. `extensions/maimai-scraper/manifest.json` 当前版本为 `2.2`，已覆盖 `*://maimai.cn/*` 和 `*://*.maimai.cn/*`。
2. `background.js` 已通过 `importScripts("idb.js", "autopager.js")` 加载分页存储和自动分页调度。
3. `idb.js` 当前只有 `PagerDB`，DB 为 `maimai_pager`，store 为 `contacts`。
4. `popup.html/js/css` 当前有被动拦截、主动搜索、DOM 抓取和分页抓取控制。
5. `inject.js` 已在 MAIN world 拦截 fetch/XHR，并支持主动搜索和分页请求重放。
6. `content.js` 已作为 isolated world 桥接 popup/background 与 MAIN world。
7. `exportFullJson` 已能合并 `PagerDB.contacts` 与 `chrome.storage.local` 中的 `captured/contacts/details`。
8. `agents/workflows/talent-library/references/scenarios.md` 已记录手动列表页弹窗捕获流程。

---

## File Structure

Create:

- `extensions/maimai-scraper/detail_batch.js` — 批量详情 job 状态机、限流、熔断和事件格式。
- `scripts/maimai_detail_import.py` — 解析扩展完整导出，执行 dry-run/apply，生成详情补全报告。
- `tests/test_maimai_scraper_extension.py` — 扩展文件静态契约测试。
- `tests/test_maimai_detail_import.py` — 本地详情导入 dry-run/apply 聚焦测试。

Modify:

- `extensions/maimai-scraper/manifest.json` — 版本升级到 `2.3`，描述补充批量详情。
- `extensions/maimai-scraper/idb.js` — 新增 `DetailDB`，保留 `PagerDB` 兼容 API。
- `extensions/maimai-scraper/background.js` — 加载 `detail_batch.js`，新增批量详情消息处理、导出增强、清理增强。
- `extensions/maimai-scraper/content.js` — 新增 `detailFetch` 命令桥接和结果超时处理。
- `extensions/maimai-scraper/inject.js` — 新增 MAIN world 详情接口重放。
- `extensions/maimai-scraper/popup.html` — 新增“批量详情”Tab 和控制面板。
- `extensions/maimai-scraper/popup.js` — 新增批量详情 UI 状态、控制按钮和进度订阅。
- `extensions/maimai-scraper/popup.css` — 新增批量详情面板样式。
- `agents/workflows/talent-library/references/scenarios.md` — 将批量详情流程写入 `detail` 场景。
- `tasks/todo.md` — 记录实施清单和验证结果。

Do not modify:

- `data/talent.db`
- `data/output/*`
- `extensions/maimai-scraper.crx`
- `extensions/maimai-scraper.pem`
- 现有历史设计文档，除非实施中发现方案事实需要修正。

---

## Data Contract

### Detail Job

```json
{
  "id": "166812124",
  "name": "范青",
  "company": "某公司",
  "position": "产品经理",
  "trackable_token": "...",
  "status": "queued|running|done|failed|skipped|paused",
  "attempts": 0,
  "started_at": null,
  "finished_at": null,
  "detail": {
    "basic": null,
    "projects": null,
    "job_preference": null,
    "contact_btn": null
  },
  "errors": []
}
```

### Export JSON

```json
{
  "exportTime": "2026-05-10T00:00:00.000Z",
  "metadata": {
    "export_type": "full",
    "detail_mode": "batch_replay",
    "pager_contacts": 100,
    "captured_requests": 200,
    "captured_details": 92,
    "total_jobs": 100,
    "queued": 0,
    "running": 0,
    "done": 92,
    "failed": 6,
    "skipped": 2,
    "circuit_breaker": {
      "tripped": false,
      "reason": null
    }
  },
  "contacts": [],
  "totalContacts": 100,
  "details": [],
  "totalDetails": 92,
  "detailJobs": [],
  "requests": []
}
```

### Detail Payload Shape

`details[]` 中每条记录统一为：

```json
{
  "id": "166812124",
  "url": "/api/ent/talent/basic?...",
  "ts": "2026-05-10T00:00:00.000Z",
  "mode": "batch_replay",
  "data": {},
  "job": {
    "id": "166812124",
    "status": "done"
  },
  "endpoints": {
    "basic": {},
    "projects": {},
    "job_preference": {},
    "contact_btn": {}
  }
}
```

本地入库优先读取 `detailJobs[].detail.basic`，其次读取 `details[].data`，再兜底读取被动捕获旧格式。

---

### Task 1: Add Extension Contract Tests

**Files:**
- Create: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1.1: 新增扩展结构契约测试**

测试内容：

1. `manifest.json` 能被 JSON 解析，版本为 `2.3`。
2. `background.js` 的 `importScripts` 包含 `detail_batch.js`。
3. `idb.js` 暴露 `DetailDB`，且包含 `getAllJobs`、`getAllDetails`、`clear`。
4. `background.js` 处理 `startDetailBatch`、`pauseDetailBatch`、`resumeDetailBatch`、`stopDetailBatch`、`getDetailBatchStatus`。
5. `content.js` 处理 `detailFetch`。
6. `inject.js` 处理 `__MAIMAI_DETAIL_FETCH__`，且包含 `/api/ent/talent/basic`、`/api/ent/candidate/associated/project/list`、`/api/ent/talent/job_preference`。
7. `popup.html` 包含 `data-tab="detail"` 和 `btn-start-detail-batch`。
8. `exportFullJson` 导出 `detailJobs`。

- [ ] **Step 1.2: 运行失败测试**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: FAIL，因为批量详情契约尚未实现。

- [ ] **Step 1.3: 静态语法基线**

Run:

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/popup.js
node --check extensions/maimai-scraper/idb.js
```

Expected: PASS，确认改动前没有语法问题；若本机无 Node，记录为未执行并用 Chrome pack 替代。

---

### Task 2: Add `DetailDB` Storage

**Files:**
- Modify: `extensions/maimai-scraper/idb.js`
- Modify: `extensions/maimai-scraper/background.js`

- [ ] **Step 2.1: 在 `idb.js` 中抽出小型 IndexedDB helper**

保留 `PagerDB` 对外方法不变：

- `append(contacts)`
- `getAll()`
- `getCount()`
- `clear()`

新增内部 helper，避免为 `DetailDB` 复制整段 open/transaction 代码。

- [ ] **Step 2.2: 新增 `DetailDB`**

DB：`maimai_detail`

Stores:

- `jobs`，`keyPath: "id"`
- `details`，`keyPath: "id"`

Public API:

- `putJob(job)`
- `putJobs(jobs)`
- `getJob(id)`
- `getAllJobs()`
- `putDetail(detail)`
- `getAllDetails()`
- `getCounts()`
- `clear()`

- [ ] **Step 2.3: 扩展清理路径**

在 `background.js` 的 `clearAll` 中同步清理：

- `PagerDB.clear()`
- `DetailDB.clear()`
- `chrome.storage.local` 的 `captured`、`contacts`、`details`、`detailBatchState`、`domScrapeResult`

- [ ] **Step 2.4: 扩展完整导出路径**

在 `exportFullJson` 中读取：

- `PagerDB.getAll()`
- `DetailDB.getAllJobs()`
- `DetailDB.getAllDetails()`
- `chrome.storage.local` 中的 `captured/contacts/details/detailBatchState`

合并去重规则：

1. `contacts` 按 `id` 优先去重。
2. `details` 按 `id` 优先去重，`DetailDB` 结果优先于旧 `storage.details`。
3. `detailJobs` 全量导出，不丢弃失败和跳过记录。

- [ ] **Step 2.5: 验证**

Run:

```bash
node --check extensions/maimai-scraper/idb.js
node --check extensions/maimai-scraper/background.js
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: `DetailDB` 与导出相关契约通过，批量消息和 UI 相关契约仍失败。

---

### Task 3: Add MAIN World Detail Replay

**Files:**
- Modify: `extensions/maimai-scraper/inject.js`
- Modify: `extensions/maimai-scraper/content.js`

- [ ] **Step 3.1: 在 `inject.js` 中新增详情 URL 构造 helper**

输入：

```js
{
  id: "166812124",
  trackable_token: "...",
  endpoints: ["basic", "projects", "job_preference", "contact_btn"]
}
```

输出：

- `basic`: `/api/ent/talent/basic?channel=www&data_version=3.1&need_ai_info=0&resume_project_id=&show_tip=0&to_uid=<uid>&trackable_token=<token>&version=1.0.0`
- `projects`: `/api/ent/candidate/associated/project/list?channel=www&data_version=4.1&fr=profile&to_uid=<uid>&version=1.0.0`
- `job_preference`: `/api/ent/talent/job_preference?channel=www&page=0&size=20&to_uid=<uid>&version=1.0.0`
- `contact_btn`: `/api/ent/v3/search/contact_btn?channel=www&to_uids=<uid>&version=1.0.0`

若缺少 `trackable_token`，`basic` 不发起请求，并返回 `missing_trackable_token` 错误。

- [ ] **Step 3.2: 新增 `__MAIMAI_DETAIL_FETCH__` 消息处理**

执行顺序：

1. 校验 `id`。
2. 顺序请求 `basic`。
3. `basic` 成功后再请求 `projects`、`job_preference`、`contact_btn`。
4. 每个 endpoint 都返回 `{ ok, httpStatus, data, raw, error }`。
5. 任一非关键配套接口失败时不阻断整个人选，只记录 endpoint error。
6. `basic` 401/403/非 JSON/验证码页面时标记整个人选失败。

- [ ] **Step 3.3: 请求必须复用页面登录态**

所有 fetch 使用：

```js
{
  method: "GET",
  credentials: "include",
  headers: {
    "Accept": "application/json, text/plain, */*"
  }
}
```

不要手工伪造 Cookie。

- [ ] **Step 3.4: 在 `content.js` 中新增 `detailFetch` 桥接**

消息链：

```text
background.js
  -> content.js { type: "detailFetch", job }
  -> inject.js window.postMessage("__MAIMAI_DETAIL_FETCH__")
  -> content.js "__MAIMAI_DETAIL_FETCH_RESULT__"
  -> background.js sendResponse(...)
```

超时建议 45 秒；超时结果必须包含 `error: "请求超时"`，不能静默。

- [ ] **Step 3.5: 验证**

Run:

```bash
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/content.js
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: MAIN world replay 和 content bridge 契约通过，background 批量调度与 UI 契约仍失败。

---

### Task 4: Add Batch Detail Orchestrator

**Files:**
- Create: `extensions/maimai-scraper/detail_batch.js`
- Modify: `extensions/maimai-scraper/background.js`
- Modify: `extensions/maimai-scraper/manifest.json`

- [ ] **Step 4.1: 在 `detail_batch.js` 中定义状态机**

状态：

- `idle`
- `running`
- `paused`
- `stopped`
- `completed`
- `failed`

Job 状态：

- `queued`
- `running`
- `done`
- `failed`
- `skipped`

默认策略：

- 单人间隔：5-12 秒随机。
- 每 30 人暂停：5-10 分钟随机。
- 每日上限：100 人。
- 单人最多重试：2 次。
- 连续 3 次认证/风控失败熔断。

为了首轮手工验证更快，UI 可以允许用户选择 `test` 模式，但导出 metadata 必须记录真实策略。

- [ ] **Step 4.2: 从 contacts 生成 jobs**

数据来源优先级：

1. `PagerDB.getAll()`
2. `chrome.storage.local.contacts`
3. popup 导入的联系人 JSON

规则：

- 缺少 `id`：`skipped`，错误 `missing_id`。
- 缺少 `trackable_token`：`skipped` 或 `failed`，错误 `missing_trackable_token`；首轮不自动点击兜底。
- 同一 `id` 去重，保留首条并记录重复数量到 metadata。

- [ ] **Step 4.3: background 新增消息处理**

新增消息：

- `startDetailBatch`
- `pauseDetailBatch`
- `resumeDetailBatch`
- `stopDetailBatch`
- `getDetailBatchStatus`
- `importDetailContacts`

`startDetailBatch` 必须拿到当前活动脉脉 tab，并通过 `chrome.tabs.sendMessage(tabId, { type: "detailFetch", job })` 逐个执行。

- [ ] **Step 4.4: 写入任务和详情结果**

每个人选执行前后都写 `DetailDB.putJob(job)`。

成功时写：

- `DetailDB.putDetail(detail)`
- 兼容性同步追加到 `chrome.storage.local.details`

失败时写：

- `DetailDB.putJob({...status: "failed", errors: [...]})`
- 不写 `details`

- [ ] **Step 4.5: 实现熔断**

以下情况累计为风控/认证失败：

- HTTP 401
- HTTP 403
- 非 JSON HTML 响应且包含登录/验证/验证码关键词
- fetch 返回网络错误且连续出现

连续 3 次后：

1. 停止后续请求。
2. 状态设为 `paused`。
3. `detailBatchState.circuit_breaker.tripped = true`。
4. popup 展示熔断原因。
5. 导出 JSON 保留熔断状态。

- [ ] **Step 4.6: 升级 manifest**

将 `manifest.json` 版本升级到 `2.3`，描述补充“批量详情”。

- [ ] **Step 4.7: 验证**

Run:

```bash
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/background.js
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: 除 UI 契约外，其余扩展契约通过。

---

### Task 5: Add Batch Detail Popup UI

**Files:**
- Modify: `extensions/maimai-scraper/popup.html`
- Modify: `extensions/maimai-scraper/popup.js`
- Modify: `extensions/maimai-scraper/popup.css`

- [ ] **Step 5.1: 新增“批量详情”Tab**

新增 tab：

```html
<button class="tab" data-tab="detail">批量详情</button>
```

控制项：

- 联系人来源状态。
- 预计 jobs 数。
- 已完成/失败/跳过/剩余。
- 策略选择：`safe`、`test`。
- 每日上限。
- 批次暂停间隔说明。
- 开始、暂停、继续、停止、刷新、导出 JSON。

- [ ] **Step 5.2: 新增联系人 JSON 导入**

支持用户选择扩展导出的 JSON 文件，读取其中：

- `contacts`
- 或 `detailJobs`
- 或纯数组

导入后发送 `importDetailContacts` 到 background；不直接写入数据库。

- [ ] **Step 5.3: 订阅 batch 进度事件**

background 发送：

- `detail_batch_progress`
- `detail_batch_paused`
- `detail_batch_completed`
- `detail_batch_error`
- `detail_batch_stopped`

popup 实时刷新进度条和状态文案。

- [ ] **Step 5.4: 文案必须避免误导**

UI 明确显示：

- “在脉脉列表页使用”
- “低速顺序执行”
- “触发验证/权限异常会暂停”
- “导出后需本地 dry-run 再入库”

不要承诺自动绕过风控。

- [ ] **Step 5.5: 验证**

Run:

```bash
node --check extensions/maimai-scraper/popup.js
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: 扩展静态契约测试全部通过。

---

### Task 6: Add Local Detail Import CLI

**Files:**
- Create: `scripts/maimai_detail_import.py`
- Create: `tests/test_maimai_detail_import.py`
- Modify: `agents/workflows/talent-library/references/scenarios.md`

- [ ] **Step 6.1: 新增失败测试 fixture**

测试数据包含：

1. 一个本地候选人，`source_profiles.platform="maimai"`，`platform_id="166812124"`。
2. 一个导出 JSON，包含 `detailJobs[].detail.basic`。
3. 一个未匹配详情。
4. 一个失败 job。

期望 dry-run 输出：

- `matched=1`
- `unmatched=1`
- `failed_jobs=1`
- 不修改数据库。

- [ ] **Step 6.2: 实现 dry-run**

CLI:

```bash
python scripts/maimai_detail_import.py dry-run --capture-file <json> --db data/talent.db --out data/output/<report>.md
```

行为：

1. 校验顶层包含 `details` 或 `detailJobs`。
2. 提取每条详情的 `platform_id`。
3. 用 `source_profiles(platform='maimai', platform_id=<id>)` 精确匹配。
4. 调用 `MaimaiAdapter.map_to_schema()`。
5. 统计旧值/新值数量：
   - 工作经历
   - 教育经历
   - 项目经历
6. 生成 Markdown dry-run 报告。
7. 生成结构化 JSON dry-run 结果。
8. 不写库。

- [ ] **Step 6.3: 实现 apply**

CLI:

```bash
python scripts/maimai_detail_import.py apply --capture-file <json> --db data/talent.db --confirm "确认写入脉脉详情"
```

写入规则：

1. 只写入 dry-run 可精确匹配的人。
2. 跳过未匹配和失败 job。
3. 调用 `TalentDB.enrich(candidate_id, detail_data)`。
4. `detail_data.raw_data.maimai_detail_capture` 必须保留：
   - `capture_file`
   - `platform_id`
   - `record_url`
   - `record_id`
   - `mode`
   - `endpoints`
   - 原始 payload
5. 写入后逐人验证：
   - `data_level == "detailed"`
   - `get_detail(candidate_id)` 不为空
   - `raw_data.maimai_detail_capture` 存在

- [ ] **Step 6.4: 报告输出**

生成：

- `data/output/talent-detail-{YYYY-MM-DD}-maimai-batch-dry-run.md`
- `data/output/talent-detail-{YYYY-MM-DD}-maimai-batch-result.md`
- `data/output/talent-detail-{YYYY-MM-DD}-maimai-batch-result.json`

报告不得包含超大原始响应正文，只展示摘要和路径。

- [ ] **Step 6.5: 验证**

Run:

```bash
python -m pytest tests/test_maimai_detail_import.py -q
python -m pytest scripts/test_maimai.py tests/test_talent_db.py::test_get_detail_after_enrich -q
```

Expected: PASS。

---

### Task 7: Update Workflow Documentation

**Files:**
- Modify: `agents/workflows/talent-library/references/scenarios.md`
- Modify: `tasks/todo.md`

- [ ] **Step 7.1: 更新 `talent-library detail` 脉脉流程**

新增“批量详情：接口重放”小节：

1. 先用分页抓取或导入 JSON 准备联系人。
2. 切到“批量详情”Tab。
3. 使用 safe 模式启动。
4. 熔断/失败时先导出 JSON，不继续盲目重试。
5. 导出完整 JSON。
6. 本地执行 `maimai_detail_import.py dry-run`。
7. 用户确认后执行 apply。
8. 验证报告。

保留原有“列表页弹窗捕获”作为小批量或失败记录兜底。

- [ ] **Step 7.2: 更新 `tasks/todo.md`**

把本计划每个 Task 加入执行清单，实施时逐项勾选并追加 Review。

- [ ] **Step 7.3: 架构扫描**

Run:

```bash
rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows
```

Expected: 无输出。

---

### Task 8: Extension Packaging and Manual Chrome Verification

**Files:**
- No source changes unless verification finds a bug.

- [ ] **Step 8.1: Chrome extension pack smoke**

Run:

```powershell
chrome.exe --pack-extension="D:\workspace\talent-agent\extensions\maimai-scraper"
```

Expected: exit code 0。

- [ ] **Step 8.2: Reload extension**

在真实 Chrome 中：

1. 打开 `chrome://extensions`。
2. 开启开发者模式。
3. 重新加载 unpacked `extensions/maimai-scraper`。
4. 刷新脉脉列表页。

- [ ] **Step 8.3: 小批量 test 模式验证**

在脉脉列表页：

1. 清除旧数据。
2. 准备 3-5 个 contacts。
3. 批量详情使用 `test` 模式。
4. 观察进度：done/failed/skipped 必须变化。
5. 导出 JSON。
6. 检查 JSON 顶层包含 `detailJobs` 和 `details`。

- [ ] **Step 8.4: safe 模式验证**

在 10-30 人批次上验证：

1. 请求间隔在 safe 范围内。
2. 失败记录不会导致静默丢失。
3. 暂停/继续有效。
4. 停止后导出保留已完成和失败状态。

- [ ] **Step 8.5: 本地 dry-run 验证**

Run:

```bash
python scripts/maimai_detail_import.py dry-run --capture-file <export.json> --db data/talent.db
```

Expected:

- 只精确匹配本地存在的 `platform_id`。
- 未匹配记录进入报告。
- 数据库未修改。

- [ ] **Step 8.6: 用户确认后 apply**

只有用户明确确认后运行：

```bash
python scripts/maimai_detail_import.py apply --capture-file <export.json> --db data/talent.db --confirm "确认写入脉脉详情"
```

Expected:

- 匹配人选写入详情。
- 每人验证通过。
- 输出最终报告。

---

### Task 9: Full Verification and Review

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 9.1: 全量测试**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: PASS。

- [ ] **Step 9.2: 扩展语法检查**

Run:

```bash
node --check extensions/maimai-scraper/idb.js
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/popup.js
```

Expected: PASS，或记录 Node 不可用。

- [ ] **Step 9.3: 行为差异复核**

确认以下旧能力仍可用：

1. 被动拦截请求和详情。
2. 主动搜索。
3. DOM 抓取。
4. 分页抓取。
5. 清除数据同时清空 PagerDB 和 DetailDB。
6. 完整导出包含旧字段和新字段。

- [ ] **Step 9.4: Review 写入 `tasks/todo.md`**

记录：

- 测试结果。
- Chrome pack 结果。
- 小批量验证结果。
- safe 模式验证结果。
- dry-run/apply 结果。
- 已知残余风险。

---

## Deferred: Phase 4 自动点击兜底

首轮不实现自动点击兜底。后续单独计划应覆盖：

1. DOM 定位候选人卡片。
2. 滚动和点击详情入口。
3. 等待被动捕获 `/api/ent/talent/basic`。
4. 自动关闭弹窗。
5. 仅对 `missing_trackable_token` 或接口重放失败的人启用。
6. 更保守限流：每人 8-20 秒，每 10 人暂停 3-5 分钟。
7. 任意验证码、权限异常或页面结构变化立即暂停。

---

## Acceptance Criteria

1. 扩展可从现有 contacts 生成 detail jobs。
2. 扩展能在 MAIN world 中顺序重放 `/api/ent/talent/basic` 和配套接口。
3. 扩展支持暂停、继续、停止、失败记录和熔断。
4. 完整导出包含 `contacts`、`details`、`detailJobs`、`requests`。
5. 本地 dry-run 不改库，并能展示匹配/未匹配/失败统计。
6. apply 必须显式确认，且只写入精确匹配的人选。
7. 写入后逐人验证 `data_level='detailed'` 与 `raw_data.maimai_detail_capture`。
8. `python -m pytest tests scripts -q` 通过。
9. Chrome extension pack smoke 通过。
10. `talent-library detail` 文档记录批量详情路径和手动弹窗兜底路径。
