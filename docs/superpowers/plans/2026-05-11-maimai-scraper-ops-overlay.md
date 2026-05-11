# maimai-scraper Ops Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化 `maimai-scraper` 批量详情体验：实时执行日志、详情批量重置、修复 3 条导入生成 30 个 jobs 的陈旧 job 混入问题，并在脉脉页面右侧增加三态悬浮球。

**Architecture:** 保持现有 MV3 扩展结构不变：`background.js` 继续作为状态与持久化中心，`detail_batch.js` 负责 job 状态机，`popup.*` 负责插件主页面，`content.js` 负责页面悬浮球 Shadow DOM。新增后台摘要接口供 popup 和悬浮球共享，避免重复计算状态。

**Tech Stack:** Chrome Extension Manifest V3、vanilla JavaScript、IndexedDB、`chrome.storage.local`、Python pytest 静态契约测试、Chrome pack smoke。

---

## File Structure

- Modify: `tests/test_maimai_scraper_extension.py`
  - 增加扩展契约测试，覆盖版本号、日志、reset、job 替换、防陈旧 jobs、悬浮球挂载和主页面打开入口。
- Modify: `extensions/maimai-scraper/manifest.json`
  - 版本升级到 `2.4`，描述保持功能真实。
- Modify: `extensions/maimai-scraper/idb.js`
  - 给 `DetailDB` 增加 `clearJobs()` 和 `clearDetails()`，支持批量详情 reset 和新任务替换。
- Modify: `extensions/maimai-scraper/detail_batch.js`
  - 增加 `reset()`，统一恢复默认状态、清空内存导入联系人、停止/暂停标志。
- Modify: `extensions/maimai-scraper/background.js`
  - 新增日志存储 helper、`resetDetailBatch`、`getScraperSummary`、`openMainPage`。
  - 修复 `startDetailBatch`：启动新批次前清空旧 `DetailDB.jobs/details` 和 storage 详情状态，保证导入 3 条只生成 3 个当前批次 jobs。
  - 导出 JSON 增加 `detailBatchLogs`。
- Modify: `extensions/maimai-scraper/popup.html`
  - 批量详情页增加“重置”按钮和实时日志区域。
- Modify: `extensions/maimai-scraper/popup.js`
  - 渲染日志列表、绑定 reset、使用 `getScraperSummary` 补齐联系人/详情/任务摘要。
- Modify: `extensions/maimai-scraper/popup.css`
  - 增加日志列表样式，保持 popup 紧凑。
- Modify: `extensions/maimai-scraper/content.js`
  - 新增 `mountFloatingScraperWidget()`，使用 Shadow DOM 注入右侧悬浮球。
  - 通过 `getScraperSummary` 三态展示：无任务、执行中、执行完毕。
- Modify: `tasks/todo.md`
  - 追加本次实施清单和最终 Review 位置。

---

## Task 1: Contract Tests

**Files:**
- Modify: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1.1: 写扩展契约失败测试**

在 `tests/test_maimai_scraper_extension.py` 末尾追加以下测试：

```python
def test_manifest_version_is_2_4_for_ops_overlay():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert manifest["version"] == "2.4"


def test_detail_db_supports_targeted_reset_methods():
    idb = read_extension_file("idb.js")

    assert "clearJobs" in idb
    assert "clearDetails" in idb


def test_detail_batch_exposes_reset_contract():
    detail_batch = read_extension_file("detail_batch.js")

    assert "reset: function" in detail_batch
    assert "importedContacts = []" in detail_batch
    assert "copy(DEFAULT_STATE)" in detail_batch


def test_background_replaces_stale_detail_jobs_before_new_run():
    background = read_extension_file("background.js")

    assert "resetDetailBatch" in background
    assert "appendDetailBatchLog" in background
    assert "detailBatchLogs" in background
    assert "DetailDB.clear()" in background
    assert "DetailBatch.reset()" in background
    assert "totalJobs: jobs.length" in background


def test_background_exposes_summary_and_open_main_page_messages():
    background = read_extension_file("background.js")

    assert "getScraperSummary" in background
    assert "openMainPage" in background
    assert "chrome.action.openPopup" in background
    assert "chrome.tabs.create" in background


def test_popup_detail_tab_has_reset_and_realtime_logs():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")

    assert "btn-reset-detail-batch" in popup_html
    assert "detail-log-list" in popup_html
    assert "resetDetailBatch" in popup_js
    assert "renderDetailBatchLogs" in popup_js
    assert "getScraperSummary" in popup_js


def test_content_mounts_floating_scraper_widget():
    content = read_extension_file("content.js")

    assert "mountFloatingScraperWidget" in content
    assert "maimai-scraper-floating-host" in content
    assert "getScraperSummary" in content
    assert "openMainPage" in content
    for label in ["联系人", "详情", "执行中", "导出 JSON"]:
        assert label in content
```

- [ ] **Step 1.2: 运行测试确认失败**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: FAIL，失败点包含版本号 `2.4`、`clearJobs`、`resetDetailBatch`、`getScraperSummary`、悬浮球相关字符串缺失。

---

## Task 2: Storage and State Reset Contract

**Files:**
- Modify: `extensions/maimai-scraper/idb.js`
- Modify: `extensions/maimai-scraper/detail_batch.js`

- [ ] **Step 2.1: 给 DetailDB 增加定向清理方法**

在 `extensions/maimai-scraper/idb.js` 的 `DetailDB return` 对象中加入：

```javascript
    clearJobs: function () {
      return client.clearStore(JOBS_STORE);
    },

    clearDetails: function () {
      return client.clearStore(DETAILS_STORE);
    },
```

保留已有 `clear()`：

```javascript
    clear: function () {
      return client.clearAll();
    },
```

- [ ] **Step 2.2: 给 DetailBatch 增加 reset**

在 `extensions/maimai-scraper/detail_batch.js` 的 return 对象中，放在 `getState` 前面加入：

```javascript
    reset: function () {
      stopRequested = true;
      pauseRequested = false;
      importedContacts = [];
      state = copy(DEFAULT_STATE);
      state.updated_at = now();
      return copy(state);
    },
```

- [ ] **Step 2.3: 运行语法检查**

Run:

```bash
node --check extensions/maimai-scraper/idb.js
node --check extensions/maimai-scraper/detail_batch.js
```

Expected: 两条命令均无输出并退出码为 0。

---

## Task 3: Background Logs, Summary, Reset, and Stale Job Fix

**Files:**
- Modify: `extensions/maimai-scraper/background.js`

- [ ] **Step 3.1: 新增日志 helper**

在 `saveDetailBatchState` 后加入：

```javascript
function appendDetailBatchLog(level, message, meta) {
  return new Promise(function (resolve) {
    chrome.storage.local.get({ detailBatchLogs: [] }, function (r) {
      var logs = r.detailBatchLogs || [];
      logs.push({
        ts: new Date().toISOString(),
        level: level || "info",
        message: String(message || ""),
        meta: meta || null,
      });
      if (logs.length > 120) {
        logs = logs.slice(logs.length - 120);
      }
      chrome.storage.local.set({ detailBatchLogs: logs }, function () {
        resolve(logs);
      });
    });
  });
}

function messageForDetailEvent(event) {
  var counts = event.counts || {};
  var total = event.total_jobs || 0;
  var done = counts.done || 0;
  var failed = counts.failed || 0;
  var skipped = counts.skipped || 0;
  if (event.type === "detail_batch_completed") {
    return "批量详情完成: " + done + "/" + total + " 成功，失败 " + failed + "，跳过 " + skipped;
  }
  if (event.type === "detail_batch_stopped") {
    return "批量详情已停止: 已处理 " + (done + failed + skipped) + "/" + total;
  }
  if (event.type === "detail_batch_paused") {
    return "批量详情暂停: " + (event.reason || "等待继续");
  }
  if (event.type === "detail_batch_error") {
    return "批量详情错误: " + (event.error || "未知错误");
  }
  if (event.job && event.job.id) {
    return "Job " + event.job.id + " -> " + event.job.status;
  }
  return "批量详情进度: " + (done + failed + skipped) + "/" + total;
}
```

- [ ] **Step 3.2: 让 detail 事件写入日志**

将 `emitDetailBatchEvent(event)` 改为：

```javascript
function emitDetailBatchEvent(event) {
  appendDetailBatchLog(event.type === "detail_batch_error" ? "error" : "info", messageForDetailEvent(event), {
    type: event.type,
    status: event.status || null,
    current_index: event.current_index || 0,
    counts: event.counts || null,
  }).then(function () {
    try {
      chrome.runtime.sendMessage(event).catch(function () {});
    } catch (err) {}
  });
}
```

- [ ] **Step 3.3: 扩展 storage 读取函数**

将 `storageContactsAndState()` 的 defaults 改为：

```javascript
    chrome.storage.local.get({
      captured: [],
      contacts: [],
      details: [],
      detailImportedContacts: [],
      detailBatchState: null,
      detailBatchLogs: [],
    }, function (r) {
      resolve(r);
    });
```

- [ ] **Step 3.4: 新增 scraper 摘要构造函数**

在 `normalizeImportContacts` 后加入：

```javascript
function buildScraperSummary() {
  return Promise.all([
    PagerDB.getCount().catch(function () { return 0; }),
    DetailDB.getAllJobs().catch(function () { return []; }),
    DetailDB.getCounts().catch(function () { return { jobs: 0, details: 0 }; }),
    storageContactsAndState(),
  ]).then(function (parts) {
    var pagerCount = parts[0] || 0;
    var detailJobs = parts[1] || [];
    var detailCounts = parts[2] || { jobs: 0, details: 0 };
    var stored = parts[3] || {};
    var detailState = stored.detailBatchState || DetailBatch.getState();
    var detailStatusCountsValue = detailStatusCounts(detailJobs, detailState);
    var pagerRunning = Boolean(__activePager && __activePager.running);
    var detailRunning = detailState && (detailState.status === "running" || detailState.status === "paused");
    var lastCompleted = detailState && detailState.status === "completed";
    var contactsCount = Math.max(
      pagerCount,
      (stored.detailImportedContacts || []).length,
      (stored.contacts || []).length
    );
    var detailsCount = Math.max(detailCounts.details || 0, (stored.details || []).length);

    return {
      ok: true,
      contacts: contactsCount,
      requests: (stored.captured || []).length,
      details: detailsCount,
      detailImportedContacts: (stored.detailImportedContacts || []).length,
      pager: __activePager ? {
        running: Boolean(__activePager.running),
        currentPage: __activePager.currentPage || 0,
        totalPages: __activePager.totalPages || 0,
        totalContacts: __activePager.totalContacts || contactsCount,
      } : { running: false, currentPage: 0, totalPages: 0, totalContacts: contactsCount },
      detail: {
        running: Boolean(detailRunning),
        completed: Boolean(lastCompleted),
        state: detailState,
        counts: detailStatusCountsValue,
        totalJobs: detailState.total_jobs || detailJobs.length,
      },
      logs: (stored.detailBatchLogs || []).slice(-20),
    };
  });
}
```

- [ ] **Step 3.5: resetDetailBatch 消息**

在 `// ---- Batch Detail 消息处理 ----` 下方、`importDetailContacts` 之前加入：

```javascript
  if (msg.type === "resetDetailBatch") {
    var resetState = DetailBatch.reset();
    Promise.all([
      DetailDB.clear().catch(function () {}),
      new Promise(function (resolve) {
        chrome.storage.local.set({
          detailImportedContacts: [],
          detailBatchState: resetState,
          detailBatchLogs: [],
          details: [],
        }, function () {
          resolve();
        });
      }),
    ]).then(function () {
      appendDetailBatchLog("info", "批量详情已重置", null).then(function () {
        sendResponse({ ok: true, state: resetState });
      });
    });
    return true;
  }
```

- [ ] **Step 3.6: 导入联系人时清理旧 jobs 和日志**

将 `importDetailContacts` 成功路径改为：

```javascript
    var importedCount = DetailBatch.importContacts(contactsToImport);
    Promise.all([
      DetailDB.clear().catch(function () {}),
      new Promise(function (resolve) {
        chrome.storage.local.set({
          contacts: contactsToImport,
          detailImportedContacts: contactsToImport,
          detailBatchState: DetailBatch.reset(),
          detailBatchLogs: [],
          details: [],
        }, function () {
          resolve();
        });
      }),
    ]).then(function () {
      appendDetailBatchLog("info", "已导入 " + importedCount + " 条详情联系人", {
        imported: importedCount,
      }).then(function () {
        sendResponse({ ok: true, imported: importedCount });
      });
    });
    return true;
```

注意：这段代码先调用 `DetailBatch.importContacts()`，再调用 `DetailBatch.reset()` 会清空内存导入联系人。实现时应采用下面的顺序，避免清空刚导入的数据：

```javascript
    var resetState = DetailBatch.reset();
    var importedCount = DetailBatch.importContacts(contactsToImport);
    Promise.all([
      DetailDB.clear().catch(function () {}),
      new Promise(function (resolve) {
        chrome.storage.local.set({
          contacts: contactsToImport,
          detailImportedContacts: contactsToImport,
          detailBatchState: resetState,
          detailBatchLogs: [],
          details: [],
        }, function () {
          resolve();
        });
      }),
    ]).then(function () {
      appendDetailBatchLog("info", "已导入 " + importedCount + " 条详情联系人", {
        imported: importedCount,
      }).then(function () {
        sendResponse({ ok: true, imported: importedCount });
      });
    });
    return true;
```

- [ ] **Step 3.7: 启动新批次前替换旧 jobs**

在 `startDetailBatch` 中，将 `return DetailDB.putJobs(jobs).then(function () {` 改为：

```javascript
      return DetailDB.clear().then(function () {
        return DetailDB.putJobs(jobs);
      }).then(function () {
        return appendDetailBatchLog("info", "批量详情启动: " + jobs.length + " 个 jobs", {
          jobs: jobs.length,
          duplicateContacts: built.duplicates,
        });
      }).then(function () {
```

这一步修复“导入 3 条联系人却导出/统计出现 30 个 jobs”：旧 IndexedDB jobs 不再混入当前批次。

- [ ] **Step 3.8: getDetailBatchStatus 返回日志**

将 `getDetailBatchStatus` 的 `sendResponse` 改为：

```javascript
      sendResponse({
        ok: true,
        state: stored.detailBatchState || DetailBatch.getState(),
        counts: counts,
        contacts: ((stored.detailImportedContacts || []).length || (stored.contacts || []).length),
        logs: stored.detailBatchLogs || [],
      });
```

- [ ] **Step 3.9: 新增 summary 和主页面入口消息**

在 `getDetailBatchStatus` 后加入：

```javascript
  if (msg.type === "getScraperSummary") {
    buildScraperSummary().then(sendResponse).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "openMainPage") {
    try {
      if (chrome.action && chrome.action.openPopup) {
        chrome.action.openPopup().then(function () {
          sendResponse({ ok: true, mode: "popup" });
        }).catch(function () {
          chrome.tabs.create({ url: chrome.runtime.getURL("popup.html") }, function (tab) {
            sendResponse({ ok: true, mode: "tab", tabId: tab && tab.id });
          });
        });
      } else {
        chrome.tabs.create({ url: chrome.runtime.getURL("popup.html") }, function (tab) {
          sendResponse({ ok: true, mode: "tab", tabId: tab && tab.id });
        });
      }
    } catch (err) {
      sendResponse({ ok: false, error: err.message });
    }
    return true;
  }
```

- [ ] **Step 3.10: 导出 JSON 包含日志**

在 `exportFullJson` storage defaults 增加 `detailBatchLogs: []`，并在导出 `data` 中加入：

```javascript
        detailBatchLogs: stored.detailBatchLogs || [],
```

- [ ] **Step 3.11: clearAll 清理日志**

在 `clearAll` 的 `chrome.storage.local.set` 中加入：

```javascript
          detailBatchLogs: [],
```

- [ ] **Step 3.12: 运行语法检查**

Run:

```bash
node --check extensions/maimai-scraper/background.js
```

Expected: 无输出并退出码为 0。

---

## Task 4: Popup Detail Logs and Reset

**Files:**
- Modify: `extensions/maimai-scraper/popup.html`
- Modify: `extensions/maimai-scraper/popup.js`
- Modify: `extensions/maimai-scraper/popup.css`

- [ ] **Step 4.1: popup HTML 增加 reset 和日志列表**

在批量详情第二个 `.btn-row` 中加入：

```html
      <button id="btn-reset-detail-batch">重置</button>
```

在 `detail-batch-log` 后加入：

```html
    <div class="detail-log-list" id="detail-log-list"></div>
```

- [ ] **Step 4.2: popup JS 增加 DOM 引用**

在批量详情 DOM 引用区加入：

```javascript
  var btnResetDetail = document.getElementById("btn-reset-detail-batch");
  var detailLogList = document.getElementById("detail-log-list");
```

- [ ] **Step 4.3: popup JS 增加日志渲染**

在 `detailCountsFromState` 后加入：

```javascript
  function renderDetailBatchLogs(logs) {
    var list = (logs || []).slice(-8).reverse();
    if (!detailLogList) return;
    if (list.length === 0) {
      detailLogList.textContent = "暂无执行日志";
      return;
    }
    detailLogList.innerHTML = list.map(function (log) {
      var time = log.ts ? new Date(log.ts).toLocaleTimeString() : "--:--:--";
      var level = log.level || "info";
      return '<div class="detail-log-row ' + level + '">' +
        '<span class="detail-log-time">' + time + '</span>' +
        '<span class="detail-log-message">' + String(log.message || "").replace(/[<>&]/g, function (ch) {
          return ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" })[ch];
        }) + '</span>' +
      '</div>';
    }).join("");
  }
```

- [ ] **Step 4.4: popup JS 在刷新状态时渲染日志**

在 `refreshDetailBatchStatus` 成功回调中，`renderDetailBatchState(resp.state || {});` 后加入：

```javascript
      renderDetailBatchLogs(resp.logs || []);
```

- [ ] **Step 4.5: popup JS 绑定 reset**

在 `btnStopDetail` listener 后加入：

```javascript
  btnResetDetail.addEventListener("click", function () {
    if (!confirm("确认重置批量详情统计和导入信息？")) return;
    chrome.runtime.sendMessage({ type: "resetDetailBatch" }, function (resp) {
      if (!resp || !resp.ok) {
        detailBatchLog.textContent = "重置失败: " + (resp ? resp.error : "无响应");
        return;
      }
      detailImportFileEl.value = "";
      renderDetailBatchState(resp.state || {});
      renderDetailBatchLogs([]);
      detailBatchLog.textContent = "批量详情已重置";
      refreshDetailBatchStatus();
    });
  });
```

- [ ] **Step 4.6: popup JS 启动后读取 summary**

在 `refreshDetailBatchStatus()` 中，保留现有 `getDetailBatchStatus`，并新增一个轻量摘要调用：

```javascript
    chrome.runtime.sendMessage({ type: "getScraperSummary" }, function (summary) {
      if (summary && summary.ok && summary.detail && summary.detail.totalJobs > 0) {
        statusBadge.textContent = summary.detail.running
          ? "详情执行中"
          : summary.details + " 详情";
      }
    });
```

- [ ] **Step 4.7: popup CSS 增加日志列表样式**

在 `popup.css` 末尾加入：

```css
.detail-log-list {
  max-height: 120px;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  background: #fff;
  margin-top: 6px;
}
.detail-log-row {
  display: grid;
  grid-template-columns: 64px 1fr;
  gap: 6px;
  padding: 5px 6px;
  border-bottom: 1px solid #f1f3f4;
  font-size: 11px;
  line-height: 1.35;
}
.detail-log-row:last-child { border-bottom: 0; }
.detail-log-row.error { color: #b3261e; }
.detail-log-time { color: #6b7280; font-variant-numeric: tabular-nums; }
.detail-log-message { color: inherit; word-break: break-word; }
```

- [ ] **Step 4.8: popup 语法检查**

Run:

```bash
node --check extensions/maimai-scraper/popup.js
```

Expected: 无输出并退出码为 0。

---

## Task 5: Floating Widget in Content Script

**Files:**
- Modify: `extensions/maimai-scraper/content.js`

- [ ] **Step 5.1: 增加悬浮球挂载函数**

在 `safeSendMessage` 后加入：

```javascript
  function mountFloatingScraperWidget() {
    if (document.getElementById("maimai-scraper-floating-host")) return;
    var host = document.createElement("div");
    host.id = "maimai-scraper-floating-host";
    var root = host.attachShadow({ mode: "open" });
    root.innerHTML = [
      "<style>",
      ":host{all:initial}",
      ".ball{position:fixed;right:18px;top:42%;z-index:2147483647;width:138px;min-height:62px;border-radius:8px;background:#ffffff;color:#202124;box-shadow:0 8px 24px rgba(0,0,0,.18);border:1px solid #dadce0;font-family:-apple-system,'Segoe UI',sans-serif;font-size:12px;cursor:pointer;overflow:hidden}",
      ".bar{height:4px;background:#1a73e8;width:0%}",
      ".body{padding:8px 10px}",
      ".title{font-weight:600;font-size:12px;margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}",
      ".meta{color:#5f6368;line-height:1.45}",
      ".actions{display:flex;gap:4px;margin-top:6px}",
      "button{border:1px solid #dadce0;background:#fff;border-radius:4px;font-size:11px;padding:3px 6px;cursor:pointer}",
      "button.primary{background:#1a73e8;border-color:#1a73e8;color:#fff}",
      ".running .bar{background:#188038}",
      ".done .bar{background:#1a73e8;width:100%}",
      ".idle .bar{background:#dadce0;width:100%}",
      "</style>",
      "<div class='ball idle' id='ball'>",
      "  <div class='bar' id='bar'></div>",
      "  <div class='body'>",
      "    <div class='title' id='title'>Maimai Scraper</div>",
      "    <div class='meta' id='meta'>联系人 0 · 详情 0</div>",
      "    <div class='actions' id='actions'></div>",
      "  </div>",
      "</div>",
    ].join("");
    (document.body || document.documentElement).appendChild(host);

    var ball = root.getElementById("ball");
    var bar = root.getElementById("bar");
    var title = root.getElementById("title");
    var meta = root.getElementById("meta");
    var actions = root.getElementById("actions");

    function pct(done, total) {
      return total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0;
    }

    function render(summary) {
      if (!summary || !summary.ok) return;
      var detail = summary.detail || {};
      var detailState = detail.state || {};
      var counts = detail.counts || {};
      var pager = summary.pager || {};
      var done = (counts.done || 0) + (counts.failed || 0) + (counts.skipped || 0);
      var total = detail.totalJobs || detailState.total_jobs || 0;
      var progress = pct(done, total);
      actions.innerHTML = "";

      if (pager.running) {
        ball.className = "ball running";
        bar.style.width = pct(pager.currentPage || 0, pager.totalPages || 0) + "%";
        title.textContent = "联系人抓取执行中";
        meta.textContent = "第 " + (pager.currentPage || 0) + "/" + (pager.totalPages || 0) + " 页 · " + (pager.totalContacts || summary.contacts || 0) + " 人";
        return;
      }

      if (detail.running) {
        ball.className = "ball running";
        bar.style.width = progress + "%";
        title.textContent = detailState.status === "paused" ? "详情抓取已暂停" : "详情抓取执行中";
        meta.textContent = done + "/" + total + " · 成功 " + (counts.done || 0) + " · 失败 " + (counts.failed || 0);
        return;
      }

      if (detail.completed) {
        ball.className = "ball done";
        bar.style.width = "100%";
        title.textContent = "任务执行完毕";
        meta.textContent = "详情 " + summary.details + " · 成功 " + (counts.done || 0) + " · 失败 " + (counts.failed || 0);
        actions.innerHTML = "<button class='primary' id='export'>导出 JSON</button>";
        root.getElementById("export").addEventListener("click", function (event) {
          event.stopPropagation();
          safeSendMessage({
            type: "exportFullJson",
            filename: "maimai-capture-" + new Date().toISOString().slice(0, 10) + ".json",
          });
        });
        return;
      }

      ball.className = "ball idle";
      bar.style.width = "100%";
      title.textContent = "Maimai Scraper";
      meta.textContent = "联系人 " + summary.contacts + " · 详情 " + summary.details;
    }

    function refresh() {
      safeSendMessage({ type: "getScraperSummary" }, render);
    }

    ball.addEventListener("click", function () {
      safeSendMessage({ type: "openMainPage" });
    });

    refresh();
    setInterval(refresh, 2000);
    chrome.runtime.onMessage.addListener(function (msg) {
      if (msg.type === "pager_progress" || msg.type === "pager_complete" || (msg.type && msg.type.indexOf("detail_batch_") === 0)) {
        refresh();
      }
    });
  }
```

- [ ] **Step 5.2: DOM ready 后挂载**

在 `content.js` 末尾、IIFE 结束前加入：

```javascript
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountFloatingScraperWidget, { once: true });
  } else {
    mountFloatingScraperWidget();
  }
```

- [ ] **Step 5.3: content 语法检查**

Run:

```bash
node --check extensions/maimai-scraper/content.js
```

Expected: 无输出并退出码为 0。

---

## Task 6: Manifest Version and Regression Verification

**Files:**
- Modify: `extensions/maimai-scraper/manifest.json`

- [ ] **Step 6.1: 升级 manifest 版本**

将：

```json
  "version": "2.3",
```

改为：

```json
  "version": "2.4",
```

- [ ] **Step 6.2: 跑扩展聚焦测试**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py -q
```

Expected: PASS，所有 maimai scraper 静态契约测试通过。

- [ ] **Step 6.3: 跑 JS 语法检查**

Run:

```bash
node --check extensions/maimai-scraper/idb.js
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/popup.js
```

Expected: 全部无输出并退出码为 0。

- [ ] **Step 6.4: 跑关联回归**

Run:

```bash
python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_talent_library_cli.py tests/test_maimai_scraper_extension.py -q
```

Expected: PASS。

- [ ] **Step 6.5: 跑全量测试**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: PASS。当前基线为 `386 passed, 1 warning`，新增测试后通过数会增加。

- [ ] **Step 6.6: Chrome pack smoke**

Run:

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --pack-extension="D:\workspace\talent-agent\extensions\maimai-scraper" --pack-extension-key="D:\workspace\talent-agent\extensions\maimai-scraper.pem"
```

Expected: 退出码 0，生成/更新 `extensions/maimai-scraper.crx`。

---

## Task 7: Manual Acceptance on Maimai Page

**Files:**
- No source change unless verification finds a defect.
- Modify after completion: `tasks/todo.md`

- [ ] **Step 7.1: 扩展重载验证**

在 Chrome 扩展页重载 `extensions/maimai-scraper`，刷新已登录的脉脉页面。

Expected:
- 页面右侧出现悬浮球。
- 无任务时显示 `联系人 N · 详情 M`。
- 点击悬浮球非导出按钮区域会打开插件主页面；若 Chrome 不允许直接打开 action popup，则打开扩展的 `popup.html` 标签页。

- [ ] **Step 7.2: 3 联系人导入验证**

在 popup 的“批量详情”页导入一个只含 3 条联系人的 JSON。

Expected:
- 日志显示 `已导入 3 条详情联系人`。
- Jobs 仍为 0，直到点击开始。
- 旧 jobs、旧详情统计被清空。

- [ ] **Step 7.3: 3 jobs 启动验证**

点击“开始详情”。

Expected:
- 启动响应和 UI 均显示 Jobs 为 3。
- 导出 JSON 的 `metadata.total_jobs` 为 3。
- 导出 JSON 的 `detailJobs.length` 为 3。
- 不再出现导入 3 条但导出 30 个 jobs 的情况。

- [ ] **Step 7.4: 实时日志验证**

观察 popup 和悬浮球状态。

Expected:
- popup 日志随着 `running/done/failed/paused/completed` 更新。
- 悬浮球在详情执行中显示 `详情抓取执行中`、进度、成功/失败数。
- 完成后悬浮球显示摘要并出现 `导出 JSON` 操作。

- [ ] **Step 7.5: reset 验证**

点击批量详情页“重置”。

Expected:
- Jobs、完成、失败、跳过归零。
- 导入文件控件清空。
- 详情导入联系人和旧详情 jobs 清空。
- 悬浮球回到无任务态。

---

## Self-Review

**Spec coverage:** 计划覆盖 4 个用户需求：执行日志、批量详情 reset、3 条导入生成 30 jobs 修复、右侧三态悬浮球与导出/主页面入口。

**Placeholder scan:** 未发现占位词、延后实现描述或未定义文件路径。

**Type consistency:** 统一使用 `detailBatchLogs`、`resetDetailBatch`、`getScraperSummary`、`openMainPage`、`DetailBatch.reset()`、`DetailDB.clearJobs()`、`DetailDB.clearDetails()`。
