# Maimai Scraper Workbench V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent Side Panel workbench for `extensions/maimai-scraper` while preserving the existing page MAIN world list and detail request paths.

**Architecture:** Add a `workbench.html/js/css` UI that restores state from `background.js` snapshots and storage changes. Keep real Maimai list and detail requests in `inject.js` through the existing `content.js` bridge. Reduce popup to a lightweight launcher and summary surface.

**Tech Stack:** Chrome Manifest V3, Side Panel API, plain JavaScript, `chrome.storage.local`, IndexedDB via existing `idb.js`, pytest static contract tests, `node --check`.

---

## File Structure

- Modify: `extensions/maimai-scraper/manifest.json`
  - Add `"sidePanel"` permission and `side_panel.default_path`.
- Create: `extensions/maimai-scraper/workbench.html`
  - Persistent workbench document used by Side Panel and tab fallback.
- Create: `extensions/maimai-scraper/workbench.css`
  - Workbench layout, tabs, stats, logs, buttons, and responsive side-panel widths.
- Create: `extensions/maimai-scraper/workbench.js`
  - UI rendering, snapshot restore, storage subscriptions, file import, start/stop/export controls.
- Modify: `extensions/maimai-scraper/background.js`
  - Add `workbenchState`, `pagerLogs`, snapshot API, Side Panel opener, pager event persistence, export-state persistence.
- Modify: `extensions/maimai-scraper/popup.html`
  - Replace full control surface with launcher summary.
- Modify: `extensions/maimai-scraper/popup.css`
  - Simplify popup styling for launcher and quick export.
- Modify: `extensions/maimai-scraper/popup.js`
  - Replace long-running UI logic with summary refresh, workbench open, and quick export.
- Modify: `extensions/maimai-scraper/content.js`
  - Keep the floating widget, but make `openMainPage` open the workbench through background.
- Modify: `tests/test_maimai_scraper_extension.py`
  - Add workbench, Side Panel, state recovery, and request-boundary contract tests.

Do not modify `inject.js`, `autopager.js`, `detail_batch.js`, or `idb.js` unless a test proves that a small compatibility change is required. The request execution invariant depends on keeping the current MAIN world bridge intact.

---

### Task 1: Add Workbench V2 Contract Tests

**Files:**
- Modify: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Add failing tests for manifest, files, background state, popup launcher, and request boundaries**

Append these tests after `test_detail_batch_logs_each_job_success_and_failure`:

```python
def test_manifest_declares_side_panel_workbench():
    manifest = json.loads(read_extension_file("manifest.json"))

    assert "sidePanel" in manifest["permissions"]
    assert manifest["side_panel"]["default_path"] == "workbench.html"
    assert manifest["action"]["default_popup"] == "popup.html"


def test_workbench_files_define_restoreable_ui_contract():
    workbench_html = read_extension_file("workbench.html")
    workbench_js = read_extension_file("workbench.js")
    workbench_css = read_extension_file("workbench.css")

    assert 'id="workbench-root"' in workbench_html
    assert "workbench.css" in workbench_html
    assert "workbench.js" in workbench_html
    for marker in [
        "btn-start-pager",
        "btn-stop-pager",
        "btn-export-pager",
        "detail-import-file",
        "btn-start-detail-batch",
        "btn-stop-detail-batch",
        "btn-export-detail-batch",
        "btn-export-capture",
        "btn-clear-all",
        "pager-log-list",
        "detail-log-list",
    ]:
        assert marker in workbench_html
    for marker in [
        'type: "getWorkbenchSnapshot"',
        'type: "setWorkbenchView"',
        'type: "startPager"',
        'type: "stopPager"',
        'type: "exportPagerJson"',
        'type: "importDetailContacts"',
        'type: "startDetailBatch"',
        'type: "stopDetailBatch"',
        'type: "exportFullJson"',
        "chrome.storage.onChanged.addListener",
        "renderPagerLogs",
        "renderDetailLogs",
    ]:
        assert marker in workbench_js
    assert ".workbench-shell" in workbench_css
    assert ".log-list" in workbench_css


def test_background_exposes_workbench_state_snapshot_and_logs():
    background = read_extension_file("background.js")

    for marker in [
        "DEFAULT_WORKBENCH_STATE",
        "workbenchState",
        "pagerLogs",
        "getWorkbenchSnapshot",
        "setWorkbenchView",
        "appendPagerLog",
        "clearPagerLogs",
        "recordExportResult",
        "updateWorkbenchPagerStateFromEvent",
        "buildWorkbenchSnapshot",
        "openWorkbench",
        "chrome.sidePanel.open",
        "workbench.html",
    ]:
        assert marker in background

    pager_block = background.split("AutoPager.run", 1)[1].split("safeRespond", 1)[0]
    assert "updateWorkbenchPagerStateFromEvent(event" in pager_block
    assert "chrome.runtime.sendMessage(event)" in pager_block


def test_popup_is_launcher_not_long_running_console():
    popup_html = read_extension_file("popup.html")
    popup_js = read_extension_file("popup.js")

    assert "btn-open-workbench" in popup_html
    assert "打开工作台" in popup_html
    assert "popup-summary" in popup_html
    assert 'type: "openWorkbench"' in popup_js
    assert 'type: "getScraperSummary"' in popup_js
    assert 'type: "exportFullJson"' in popup_js
    assert "pagerExecutionLogs" not in popup_js
    assert "setInterval(refreshPagerInfo" not in popup_js
    assert "capture-log-list" not in popup_html
    assert "detail-log-list" not in popup_html


def test_workbench_and_popup_do_not_directly_fetch_maimai_business_urls():
    for name in ["workbench.js", "popup.js"]:
        text = read_extension_file(name)
        assert "fetch(" not in text
        assert "/api/ent/" not in text
        assert "/api/pc/" not in text

    background = read_extension_file("background.js")
    assert "fetch(" not in background
    assert "__MAIMAI_PAGER_FETCH__" in read_extension_file("content.js")
    assert "origFetch.call(window, tpl.url" in read_extension_file("inject.js")
    assert "__MAIMAI_DETAIL_FETCH__" in read_extension_file("content.js")
    assert "fetchDetailEndpoint(\"basic\", urls.basic)" in read_extension_file("inject.js")


def test_open_main_page_delegates_to_workbench():
    background = read_extension_file("background.js")
    content = read_extension_file("content.js")

    open_main_block = background.split('if (msg.type === "openMainPage")', 1)[1].split('if (msg.type === "clearAll")', 1)[0]
    assert "openWorkbenchPage" in open_main_block
    assert "popup.html" not in open_main_block
    assert 'safeSendMessage({ type: "openMainPage" })' in content
```

- [ ] **Step 2: Run the new tests and confirm red**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_manifest_declares_side_panel_workbench tests/test_maimai_scraper_extension.py::test_workbench_files_define_restoreable_ui_contract tests/test_maimai_scraper_extension.py::test_background_exposes_workbench_state_snapshot_and_logs tests/test_maimai_scraper_extension.py::test_popup_is_launcher_not_long_running_console tests/test_maimai_scraper_extension.py::test_workbench_and_popup_do_not_directly_fetch_maimai_business_urls tests/test_maimai_scraper_extension.py::test_open_main_page_delegates_to_workbench -q
```

Expected: FAIL because workbench files, Side Panel manifest fields, and background workbench messages do not exist yet.

- [ ] **Step 3: Commit the failing contract tests**

Run:

```bash
git add tests/test_maimai_scraper_extension.py
git commit -m "test: cover maimai workbench v2 contracts"
```

Expected: commit succeeds with only test changes.

---

### Task 2: Add Background Workbench State and Snapshot API

**Files:**
- Modify: `extensions/maimai-scraper/background.js`
- Test: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Add workbench state helpers**

In `background.js`, insert this block after `clearDiagnosticTraceStorage()` and before `saveDetailBatchState()`:

```javascript
var DEFAULT_WORKBENCH_STATE = {
  schema_version: 1,
  active_view: "capture",
  active_maimai_tab_id: null,
  last_opened_at: null,
  capture: {
    total_requests: 0,
    total_contacts: 0,
    total_details: 0,
    last_capture_at: null,
  },
  pager: {
    status: "idle",
    mode: "all",
    max_pages: 3,
    current_page: 0,
    total_pages: 0,
    total_from_api: 0,
    total_contacts: 0,
    started_at: null,
    updated_at: null,
    finished_at: null,
    last_error: null,
  },
  detail: {
    state: null,
    jobs: 0,
    done: 0,
    failed: 0,
    skipped: 0,
    imported_contacts: 0,
    last_error: null,
  },
  export: {
    last_export_type: null,
    last_export_at: null,
    last_download_id: null,
  },
};

function copyJson(value) {
  return JSON.parse(JSON.stringify(value));
}

function mergePlainObject(base, patch) {
  var result = Object.assign({}, base || {});
  Object.keys(patch || {}).forEach(function (key) {
    var value = patch[key];
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      result[key] &&
      typeof result[key] === "object" &&
      !Array.isArray(result[key])
    ) {
      result[key] = mergePlainObject(result[key], value);
    } else {
      result[key] = value;
    }
  });
  return result;
}

function normalizeWorkbenchState(state) {
  return mergePlainObject(copyJson(DEFAULT_WORKBENCH_STATE), state || {});
}

function loadWorkbenchStorage() {
  return new Promise(function (resolve) {
    chrome.storage.local.get({
      workbenchState: copyJson(DEFAULT_WORKBENCH_STATE),
      pagerLogs: [],
      detailBatchLogs: [],
    }, function (r) {
      resolve({
        workbenchState: normalizeWorkbenchState(r.workbenchState),
        pagerLogs: r.pagerLogs || [],
        detailBatchLogs: r.detailBatchLogs || [],
      });
    });
  });
}

function saveWorkbenchStatePatch(patch) {
  return loadWorkbenchStorage().then(function (stored) {
    var state = normalizeWorkbenchState(mergePlainObject(stored.workbenchState, patch || {}));
    return new Promise(function (resolve) {
      chrome.storage.local.set({ workbenchState: state }, function () {
        resolve(state);
      });
    });
  });
}

function appendPagerLog(level, message, meta) {
  return new Promise(function (resolve) {
    chrome.storage.local.get({ pagerLogs: [] }, function (r) {
      var logs = r.pagerLogs || [];
      logs.push({
        ts: new Date().toISOString(),
        level: level || "info",
        message: message || "",
        meta: meta || null,
      });
      chrome.storage.local.set({ pagerLogs: logs.slice(-120) }, function () {
        resolve(logs.slice(-120));
      });
    });
  });
}

function clearPagerLogs() {
  return new Promise(function (resolve) {
    chrome.storage.local.set({ pagerLogs: [] }, function () {
      resolve([]);
    });
  });
}

function pagerLogMessageForEvent(event) {
  if (!event || !event.type) return "列表采集状态更新";
  if (event.type === "pager_progress") {
    return "第 " + event.currentPage + "/" + event.totalPages + " 页完成，新增 " + (event.contactsInPage || 0) + " 条，累计 " + (event.totalContacts || 0) + " 条";
  }
  if (event.type === "pager_complete") {
    return "列表采集完成，共保存 " + (event.totalContacts || 0) + " 条人选";
  }
  if (event.type === "pager_cancelled") {
    return "列表采集已停止，已保存 " + (event.totalContacts || 0) + " 条人选";
  }
  if (event.type === "pager_error") {
    return "第 " + event.page + " 页请求失败：" + (event.reason || "未知错误");
  }
  if (event.type === "pager_paused") {
    return "第 " + event.page + " 页请求暂停：" + (event.reason || "未知原因");
  }
  return "列表采集状态更新";
}

function updateWorkbenchPagerStateFromEvent(event, mode, maxPages) {
  event = event || {};
  var nowIso = new Date().toISOString();
  var status = "running";
  var finishedAt = null;
  var lastError = null;
  if (event.type === "pager_complete") {
    status = "completed";
    finishedAt = nowIso;
  } else if (event.type === "pager_cancelled") {
    status = "stopped";
    finishedAt = nowIso;
  } else if (event.type === "pager_error") {
    status = "failed";
    lastError = event.reason || "pager_error";
  } else if (event.type === "pager_paused") {
    status = "paused";
    lastError = event.reason || "pager_paused";
  }
  return saveWorkbenchStatePatch({
    pager: {
      status: status,
      mode: mode || undefined,
      max_pages: maxPages || undefined,
      current_page: event.currentPage || event.page || 0,
      total_pages: event.totalPages || 0,
      total_from_api: event.totalFromApi || 0,
      total_contacts: event.totalContacts || 0,
      updated_at: nowIso,
      finished_at: finishedAt,
      last_error: lastError,
    },
  }).then(function () {
    return appendPagerLog(status === "failed" ? "error" : "info", pagerLogMessageForEvent(event), event);
  });
}

function updateWorkbenchFromSummary(summary) {
  summary = summary || {};
  var detail = summary.detail || {};
  var counts = detail.counts || {};
  return saveWorkbenchStatePatch({
    capture: {
      total_requests: summary.totalRequests || 0,
      total_contacts: summary.totalContacts || 0,
      total_details: summary.totalDetails || 0,
      last_capture_at: new Date().toISOString(),
    },
    detail: {
      state: detail.state || null,
      jobs: detail.totalJobs || detail.jobs || 0,
      done: counts.done || 0,
      failed: counts.failed || 0,
      skipped: counts.skipped || 0,
      imported_contacts: detail.contacts || 0,
      last_error: detail.state && detail.state.error ? detail.state.error : null,
    },
  });
}

function buildWorkbenchSnapshot() {
  return Promise.all([
    buildScraperSummary(),
    loadWorkbenchStorage(),
  ]).then(function (parts) {
    var summary = parts[0] || {};
    var stored = parts[1] || {};
    return updateWorkbenchFromSummary(summary).then(function (state) {
      return {
        ok: true,
        workbenchState: state || stored.workbenchState,
        summary: summary,
        pagerLogs: stored.pagerLogs || [],
        detailLogs: stored.detailBatchLogs || [],
      };
    });
  });
}

function recordExportResult(exportType, downloadId) {
  return saveWorkbenchStatePatch({
    export: {
      last_export_type: exportType || null,
      last_export_at: new Date().toISOString(),
      last_download_id: downloadId || null,
    },
  });
}

function openWorkbenchPage(sendResponse) {
  function openTabFallback(reason) {
    appendPagerLog("info", "side_panel_unavailable_fallback_tab", { reason: reason || null }).then(function () {
      chrome.tabs.create({ url: chrome.runtime.getURL("workbench.html") }, function (tab) {
        sendResponse({ ok: true, opened: "tab", tabId: tab && tab.id });
      });
    });
  }

  saveWorkbenchStatePatch({ last_opened_at: new Date().toISOString() }).then(function () {
    if (chrome.sidePanel && chrome.sidePanel.open) {
      try {
        var opened = chrome.sidePanel.open({});
        if (opened && opened.then) {
          opened.then(function () {
            sendResponse({ ok: true, opened: "sidePanel" });
          }).catch(function (err) {
            openTabFallback(err && err.message);
          });
        } else {
          sendResponse({ ok: true, opened: "sidePanel" });
        }
      } catch (err) {
        openTabFallback(err.message);
      }
    } else {
      openTabFallback("sidePanel API unavailable");
    }
  });
}
```

- [ ] **Step 2: Add background message handlers**

In `background.js`, inside `chrome.runtime.onMessage.addListener`, add this block before the existing `if (msg.type === "getScraperSummary")` branch:

```javascript
  if (msg.type === "openWorkbench") {
    openWorkbenchPage(sendResponse);
    return true;
  }

  if (msg.type === "getWorkbenchSnapshot") {
    recoverExpiredBatchPauseIfNeeded().then(function () {
      return buildWorkbenchSnapshot();
    }).then(function (snapshot) {
      sendResponse(snapshot);
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "setWorkbenchView") {
    saveWorkbenchStatePatch({ active_view: msg.view || "capture" }).then(function (state) {
      sendResponse({ ok: true, workbenchState: state });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "clearPagerLogs") {
    clearPagerLogs().then(function () {
      sendResponse({ ok: true });
    });
    return true;
  }

  if (msg.type === "recordExportResult") {
    recordExportResult(msg.exportType, msg.downloadId).then(function (state) {
      sendResponse({ ok: true, workbenchState: state });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }
```

- [ ] **Step 3: Update clearAll to reset workbench state and pager logs**

In the `clearAll` storage reset object, add these keys:

```javascript
          workbenchState: copyJson(DEFAULT_WORKBENCH_STATE),
          pagerLogs: [],
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_background_exposes_workbench_state_snapshot_and_logs -q
```

Expected: FAIL only if following tasks have not yet wired pager event persistence. Background helper markers should now exist.

- [ ] **Step 5: Commit background state helpers**

Run:

```bash
git add extensions/maimai-scraper/background.js
git commit -m "feat: add maimai workbench state snapshot"
```

Expected: commit succeeds with `background.js` changes.

---

### Task 3: Persist Pager Events and Open Workbench

**Files:**
- Modify: `extensions/maimai-scraper/background.js`
- Test: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Delegate openMainPage to workbench**

Replace the full `if (msg.type === "openMainPage")` branch with:

```javascript
  if (msg.type === "openMainPage") {
    openWorkbenchPage(sendResponse);
    return true;
  }
```

- [ ] **Step 2: Initialize workbench pager state when pager starts**

Inside the `startPager` branch, after `__pagerTabId = tabId;`, add:

```javascript
          saveWorkbenchStatePatch({
            active_maimai_tab_id: tabId,
            pager: {
              status: "running",
              mode: msg.mode || "all",
              max_pages: msg.maxPages || 3,
              current_page: 1,
              total_pages: pagerState.totalPages || 0,
              total_from_api: pagerState.totalFromApi || 0,
              total_contacts: existingContacts.length || 0,
              started_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              finished_at: null,
              last_error: null,
            },
          });
          clearPagerLogs();
          appendPagerLog("info", "开始人选列表逐页采集，模式：" + ((msg.mode || "all") === "all" ? "全部页面" : "前 " + (msg.maxPages || 3) + " 页"), {
            mode: msg.mode || "all",
            maxPages: msg.maxPages || 3,
          });
```

- [ ] **Step 3: Persist pager events before broadcasting**

Replace the existing `AutoPager.run` callback:

```javascript
          AutoPager.run(pagerState, msg.mode, msg.maxPages, function (event) {
            chrome.runtime.sendMessage(event).catch(function () {});
          });
```

with:

```javascript
          AutoPager.run(pagerState, msg.mode, msg.maxPages, function (event) {
            updateWorkbenchPagerStateFromEvent(event, msg.mode || "all", msg.maxPages || 3).then(function () {
              chrome.runtime.sendMessage(event).catch(function () {});
            });
          });
```

- [ ] **Step 4: Persist stop request**

In the `stopPager` branch, after `AutoPager.stop(__activePager);`, add:

```javascript
      saveWorkbenchStatePatch({
        pager: {
          status: "stopping",
          updated_at: new Date().toISOString(),
        },
      });
      appendPagerLog("info", "已发送终止逐页采集请求", null);
```

- [ ] **Step 5: Persist export results**

In `exportFullJson`, wrap the download response so successful downloads call `recordExportResult`:

```javascript
      downloadJsonData(data, msg.filename || "maimai-export.json", msg.saveAs, function (result) {
        if (result && result.downloadId) {
          recordExportResult("full", result.downloadId).then(function () {
            sendResponse(result);
          });
          return;
        }
        sendResponse(result);
      });
```

In `exportCaptureJson`, change the `chrome.downloads.download` callback to:

```javascript
      }, function (downloadId) {
        recordExportResult("capture", downloadId).then(function () {
          sendResponse({ downloadId: downloadId });
        });
      });
```

In `exportPagerJson`, change the `chrome.downloads.download` callback to:

```javascript
        }, function (downloadId) {
          recordExportResult("pager", downloadId).then(function () {
            sendResponse({ downloadId: downloadId });
          });
        });
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_background_exposes_workbench_state_snapshot_and_logs tests/test_maimai_scraper_extension.py::test_open_main_page_delegates_to_workbench -q
```

Expected: PASS.

- [ ] **Step 7: Commit pager persistence and workbench opener**

Run:

```bash
git add extensions/maimai-scraper/background.js
git commit -m "feat: persist maimai pager workbench events"
```

Expected: commit succeeds with background event and opener changes.

---

### Task 4: Add Workbench UI Files

**Files:**
- Create: `extensions/maimai-scraper/workbench.html`
- Create: `extensions/maimai-scraper/workbench.css`
- Create: `extensions/maimai-scraper/workbench.js`
- Test: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Create workbench HTML**

Create `extensions/maimai-scraper/workbench.html` with:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="workbench.css">
</head>
<body>
  <main class="workbench-shell" id="workbench-root">
    <header class="topbar">
      <div>
        <h1>脉脉人选数据采集</h1>
        <p id="status-line">正在读取状态...</p>
      </div>
      <span class="badge" id="status-badge">--</span>
    </header>

    <section class="stats" id="popup-summary">
      <span>请求 <b id="req-count">0</b></span>
      <span>人选 <b id="contact-count">0</b></span>
      <span>详情 <b id="detail-count">0</b></span>
    </section>

    <nav class="tabs" aria-label="工作台视图">
      <button class="tab active" data-view="capture">列表采集</button>
      <button class="tab" data-view="detail">批量详情</button>
      <button class="tab" data-view="export">导出诊断</button>
    </nav>

    <section class="view active" id="view-capture">
      <div class="panel">
        <div class="form-row">
          <label>
            <span>人选列表逐页采集</span>
            <select id="pager-mode">
              <option value="all">全部页面</option>
              <option value="custom">前 N 页</option>
            </select>
          </label>
          <label id="pager-pages-group">
            <span>页数</span>
            <input type="number" id="pager-max-pages" value="3" min="1" max="100">
          </label>
        </div>
        <div class="template-box">
          <div id="pager-template-info">模板状态：等待捕获</div>
          <div id="pager-meta-info"></div>
        </div>
        <div class="btn-row">
          <button id="btn-start-pager" class="primary">开始抓取</button>
          <button id="btn-stop-pager">停止</button>
          <button id="btn-export-pager">导出人选列表 JSON</button>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" id="pager-progress-fill"></div>
        </div>
        <div class="progress-text" id="pager-progress-text">等待开始</div>
      </div>
      <section class="log-panel">
        <h2>列表执行日志</h2>
        <div class="log-list" id="pager-log-list"></div>
      </section>
    </section>

    <section class="view" id="view-detail">
      <div class="panel">
        <section class="stats detail-stats">
          <span>任务 <b id="detail-jobs-count">0</b></span>
          <span>完成 <b id="detail-done-count">0</b></span>
          <span>失败 <b id="detail-failed-count">0</b></span>
          <span>跳过 <b id="detail-skipped-count">0</b></span>
        </section>
        <label class="file-field">
          <span>导入人选列表 JSON</span>
          <input type="file" id="detail-import-file" accept="application/json,.json">
        </label>
        <div class="btn-row">
          <button id="btn-start-detail-batch" class="primary">开始人选详情采集</button>
          <button id="btn-stop-detail-batch">终止</button>
          <button id="btn-export-detail-batch">导出完整 JSON</button>
        </div>
        <div class="progress-bar">
          <div class="progress-fill detail-progress-fill" id="detail-progress-fill"></div>
        </div>
        <div class="progress-text" id="detail-progress-text">等待导入人选列表</div>
        <pre class="detail-log" id="detail-batch-log">默认低速顺序采集；遇到验证、权限或限流异常会暂停。</pre>
      </div>
      <section class="log-panel">
        <h2>详情执行日志</h2>
        <div class="log-list" id="detail-log-list"></div>
      </section>
    </section>

    <section class="view" id="view-export">
      <div class="panel">
        <div class="btn-row">
          <button id="btn-refresh">刷新摘要</button>
          <button id="btn-export-capture">导出被动拦截 JSON</button>
          <button id="btn-export-full">导出完整 JSON</button>
          <button id="btn-clear-all">清除全部数据</button>
        </div>
        <pre class="capture-preview" id="capture-preview">等待数据...</pre>
      </div>
    </section>
  </main>
  <script src="workbench.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create workbench CSS**

Create `extensions/maimai-scraper/workbench.css` with:

```css
* { box-sizing: border-box; }
body { margin: 0; min-width: 360px; font-family: -apple-system, "Segoe UI", sans-serif; font-size: 13px; color: #172033; background: #f6f8fb; }
.workbench-shell { max-width: 720px; margin: 0 auto; padding: 12px; }
.topbar { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; margin-bottom: 10px; }
.topbar h1 { margin: 0; font-size: 17px; line-height: 24px; letter-spacing: 0; }
.topbar p { margin: 2px 0 0; color: #5f6b7a; font-size: 12px; line-height: 18px; }
.badge { flex: 0 0 auto; padding: 3px 8px; border-radius: 999px; background: #e8f5e9; color: #2e7d32; font-size: 11px; }
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 8px 0; }
.stats span { padding: 8px; background: #fff; border: 1px solid #e3e7ee; border-radius: 6px; color: #5f6b7a; }
.stats b { display: block; margin-top: 2px; color: #1a73e8; font-size: 16px; }
.tabs { display: flex; gap: 4px; margin: 10px 0; }
.tab { flex: 1; min-height: 32px; border: 1px solid #d5dbe5; border-radius: 6px; background: #fff; cursor: pointer; font-size: 12px; }
.tab.active { background: #1a73e8; border-color: #1a73e8; color: #fff; }
.view { display: none; }
.view.active { display: block; }
.panel, .log-panel { background: #fff; border: 1px solid #e3e7ee; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
.form-row { display: grid; grid-template-columns: 1fr 110px; gap: 8px; }
label span { display: block; margin-bottom: 4px; color: #5f6b7a; font-size: 11px; }
select, input[type="number"], input[type="file"] { width: 100%; min-height: 30px; border: 1px solid #d5dbe5; border-radius: 5px; padding: 4px 7px; font-size: 12px; }
.template-box { margin: 8px 0; color: #405064; font-size: 12px; line-height: 18px; }
.btn-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
button { min-height: 30px; border: 1px solid #d5dbe5; border-radius: 5px; padding: 6px 10px; background: #fff; cursor: pointer; font-size: 12px; white-space: nowrap; }
button.primary { background: #1a73e8; border-color: #1a73e8; color: #fff; }
button:hover { background: #f0f4ff; }
button.primary:hover { background: #1557b0; }
.progress-bar { height: 7px; background: #edf1f7; border-radius: 999px; overflow: hidden; margin-top: 8px; }
.progress-fill { width: 0; height: 100%; background: #1a73e8; transition: width .18s ease; }
.detail-progress-fill { background: #2e7d32; }
.progress-text { margin-top: 6px; text-align: center; color: #5f6b7a; font-size: 12px; }
.log-panel h2 { margin: 0 0 6px; font-size: 13px; letter-spacing: 0; }
.log-list { max-height: 260px; overflow: auto; border: 1px solid #e3e7ee; border-radius: 6px; background: #fbfcfe; }
.log-item, .log-empty { padding: 6px 7px; border-bottom: 1px solid #edf1f7; color: #405064; font-size: 11px; line-height: 1.4; word-break: break-word; }
.log-item:last-child { border-bottom: 0; }
.log-empty { color: #8b96a5; }
.detail-log, .capture-preview { width: 100%; max-height: 180px; overflow: auto; margin: 8px 0 0; padding: 8px; border-radius: 6px; background: #1e1e1e; color: #d4d4d4; font-size: 11px; line-height: 1.45; white-space: pre-wrap; word-break: break-word; }
@media (max-width: 430px) {
  .workbench-shell { padding: 10px; }
  .form-row { grid-template-columns: 1fr; }
  .stats { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
```

- [ ] **Step 3: Create workbench JavaScript**

Create `extensions/maimai-scraper/workbench.js` with:

```javascript
(function () {
  "use strict";

  var state = null;
  var summary = null;
  var pagerLogs = [];
  var detailLogs = [];

  function $(id) {
    return document.getElementById(id);
  }

  function sendMessage(message) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(message, function (resp) {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve(resp || { ok: false, error: "无响应" });
      });
    });
  }

  function escapeHtml(text) {
    return String(text).replace(/[<>&]/g, function (ch) {
      return { "<": "&lt;", ">": "&gt;", "&": "&amp;" }[ch];
    });
  }

  function formatLog(log) {
    if (typeof log === "string") return log;
    if (!log) return "";
    var ts = log.ts || log.time || "";
    var message = log.message || JSON.stringify(log);
    return (ts ? "[" + ts + "] " : "") + message;
  }

  function setBadge(text) {
    $("status-badge").textContent = text || "--";
  }

  function setActiveView(view) {
    var activeView = view || "capture";
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.classList.toggle("active", tab.dataset.view === activeView);
    });
    document.querySelectorAll(".view").forEach(function (section) {
      section.classList.toggle("active", section.id === "view-" + activeView);
    });
    sendMessage({ type: "setWorkbenchView", view: activeView });
  }

  function renderStats() {
    var totalRequests = summary && summary.totalRequests ? summary.totalRequests : 0;
    var totalContacts = summary && summary.totalContacts ? summary.totalContacts : 0;
    var totalDetails = summary && summary.totalDetails ? summary.totalDetails : 0;
    $("req-count").textContent = totalRequests;
    $("contact-count").textContent = totalContacts;
    $("detail-count").textContent = totalDetails;
    setBadge(totalDetails > 0 ? totalDetails + " 详情" : totalContacts > 0 ? totalContacts + " 人选" : "等待捕获");
    $("status-line").textContent = "请求 " + totalRequests + " · 人选 " + totalContacts + " · 详情 " + totalDetails;
  }

  function renderCapturePreview() {
    var requests = summary && summary.requests ? summary.requests : [];
    if (requests.length === 0) {
      $("capture-preview").textContent = "等待数据...\n\n1. 打开脉脉搜索页面\n2. 手动执行搜索或翻页\n3. 数据自动捕获";
      return;
    }
    $("capture-preview").textContent = requests.slice(-8).map(function (req) {
      var url = req && req.url ? String(req.url).split("?")[0] : "";
      return "[" + (req.method || "?") + "] " + url + " -> " + (req.status || "?");
    }).join("\n");
  }

  function renderPager() {
    var pager = state && state.pager ? state.pager : {};
    var total = pager.total_pages || 0;
    var current = pager.current_page || 0;
    var pct = total > 0 ? Math.max(0, Math.min(100, Math.round((current / total) * 100))) : 0;
    $("pager-progress-fill").style.width = pct + "%";
    $("pager-progress-text").textContent = pager.status === "idle"
      ? "等待开始"
      : "状态：" + pager.status + "，页进度 " + current + "/" + total + "，人选 " + (pager.total_contacts || 0);
    $("pager-mode").value = pager.mode || "all";
    $("pager-max-pages").value = pager.max_pages || 3;
  }

  function renderDetail() {
    var detail = state && state.detail ? state.detail : {};
    var total = detail.jobs || 0;
    var done = detail.done || 0;
    var failed = detail.failed || 0;
    var skipped = detail.skipped || 0;
    var completed = done + failed + skipped;
    var pct = total > 0 ? Math.max(0, Math.min(100, Math.round((completed / total) * 100))) : 0;
    $("detail-jobs-count").textContent = total;
    $("detail-done-count").textContent = done;
    $("detail-failed-count").textContent = failed;
    $("detail-skipped-count").textContent = skipped;
    $("detail-progress-fill").style.width = pct + "%";
    $("detail-progress-text").textContent = total > 0 ? "已处理 " + completed + "/" + total : "等待导入人选列表";
    var detailState = detail.state || {};
    if (detailState.batch_pause_until) {
      $("detail-batch-log").textContent = "批间休息中：已完成 " + Math.max(detailState.batch_pause_completed || 0, completed) + "/" + total;
    } else if (detailState.circuit_breaker && detailState.circuit_breaker.tripped) {
      $("detail-batch-log").textContent = "熔断暂停：" + detailState.circuit_breaker.reason;
    }
  }

  function renderPagerLogs() {
    var target = $("pager-log-list");
    if (!pagerLogs.length) {
      target.innerHTML = '<div class="log-empty">暂无列表执行日志</div>';
      return;
    }
    target.innerHTML = pagerLogs.slice(-80).reverse().map(function (log) {
      return '<div class="log-item">' + escapeHtml(formatLog(log)) + '</div>';
    }).join("");
  }

  function renderDetailLogs() {
    var target = $("detail-log-list");
    if (!detailLogs.length) {
      target.innerHTML = '<div class="log-empty">暂无详情执行日志</div>';
      return;
    }
    target.innerHTML = detailLogs.slice(-80).reverse().map(function (log) {
      return '<div class="log-item">' + escapeHtml(formatLog(log)) + '</div>';
    }).join("");
  }

  function renderAll() {
    renderStats();
    renderCapturePreview();
    renderPager();
    renderDetail();
    renderPagerLogs();
    renderDetailLogs();
  }

  function loadSnapshot() {
    return sendMessage({ type: "getWorkbenchSnapshot" }).then(function (resp) {
      if (!resp || !resp.ok) {
        $("status-line").textContent = resp && resp.error ? resp.error : "无法读取工作台状态";
        return;
      }
      state = resp.workbenchState || {};
      summary = resp.summary || {};
      pagerLogs = resp.pagerLogs || [];
      detailLogs = resp.detailLogs || [];
      setActiveView(state.active_view || "capture");
      renderAll();
    });
  }

  function exportWith(type, filenamePrefix) {
    var filename = filenamePrefix + "-" + new Date().toISOString().slice(0, 10) + ".json";
    return sendMessage({ type: type, filename: filename }).then(function (resp) {
      setBadge(resp && resp.downloadId ? "已导出" : "导出失败");
      return loadSnapshot();
    });
  }

  function bindEvents() {
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        setActiveView(tab.dataset.view);
      });
    });
    $("pager-mode").addEventListener("change", function () {
      if (!state) state = {};
      if (!state.pager) state.pager = {};
      state.pager.mode = $("pager-mode").value;
    });
    $("btn-start-pager").addEventListener("click", function () {
      sendMessage({
        type: "startPager",
        mode: $("pager-mode").value,
        maxPages: parseInt($("pager-max-pages").value, 10) || 3,
      }).then(loadSnapshot);
    });
    $("btn-stop-pager").addEventListener("click", function () {
      sendMessage({ type: "stopPager" }).then(loadSnapshot);
    });
    $("btn-export-pager").addEventListener("click", function () {
      exportWith("exportPagerJson", "maimai-pager-contacts");
    });
    $("detail-import-file").addEventListener("change", function () {
      var file = $("detail-import-file").files && $("detail-import-file").files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          sendMessage({ type: "importDetailContacts", contacts: JSON.parse(reader.result) }).then(loadSnapshot);
        } catch (err) {
          $("detail-batch-log").textContent = "JSON 解析失败：" + err.message;
        }
      };
      reader.readAsText(file, "utf-8");
    });
    $("btn-start-detail-batch").addEventListener("click", function () {
      sendMessage({ type: "startDetailBatch" }).then(loadSnapshot);
    });
    $("btn-stop-detail-batch").addEventListener("click", function () {
      sendMessage({ type: "stopDetailBatch" }).then(loadSnapshot);
    });
    $("btn-export-detail-batch").addEventListener("click", function () {
      exportWith("exportFullJson", "maimai-detail-capture");
    });
    $("btn-refresh").addEventListener("click", loadSnapshot);
    $("btn-export-capture").addEventListener("click", function () {
      exportWith("exportCaptureJson", "maimai-passive-capture");
    });
    $("btn-export-full").addEventListener("click", function () {
      exportWith("exportFullJson", "maimai-capture");
    });
    $("btn-clear-all").addEventListener("click", function () {
      if (!confirm("确认清除所有捕获数据？")) return;
      sendMessage({ type: "clearAll" }).then(loadSnapshot);
    });
    chrome.storage.onChanged.addListener(function (changes, areaName) {
      if (areaName !== "local") return;
      if (changes.workbenchState) state = changes.workbenchState.newValue || state;
      if (changes.pagerLogs) pagerLogs = changes.pagerLogs.newValue || [];
      if (changes.detailBatchLogs) detailLogs = changes.detailBatchLogs.newValue || [];
      renderAll();
    });
    chrome.runtime.onMessage.addListener(function (msg) {
      if (msg && (msg.type === "pager_progress" || msg.type === "pager_complete" || msg.type === "pager_error" || msg.type === "pager_cancelled" || msg.type === "pager_paused" || String(msg.type || "").indexOf("detail_batch_") === 0)) {
        loadSnapshot();
      }
    });
  }

  bindEvents();
  loadSnapshot();
})();
```

- [ ] **Step 4: Run syntax check**

Run:

```bash
node --check extensions/maimai-scraper/workbench.js
```

Expected: no output and exit code 0.

- [ ] **Step 5: Run focused workbench test**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_workbench_files_define_restoreable_ui_contract -q
```

Expected: PASS.

- [ ] **Step 6: Commit workbench files**

Run:

```bash
git add extensions/maimai-scraper/workbench.html extensions/maimai-scraper/workbench.css extensions/maimai-scraper/workbench.js
git commit -m "feat: add maimai scraper workbench ui"
```

Expected: commit succeeds with three new workbench files.

---

### Task 5: Convert Popup to Launcher

**Files:**
- Modify: `extensions/maimai-scraper/popup.html`
- Modify: `extensions/maimai-scraper/popup.css`
- Modify: `extensions/maimai-scraper/popup.js`
- Test: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Replace popup HTML with launcher UI**

Replace `extensions/maimai-scraper/popup.html` with:

```html
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="popup.css">
</head>
<body>
  <div class="launcher">
    <header class="header">
      <div>
        <h3>脉脉人选数据采集</h3>
        <p id="status-line">正在读取状态...</p>
      </div>
      <span class="badge" id="status-badge">--</span>
    </header>
    <div class="stats" id="popup-summary">
      <span>请求 <b id="req-count">0</b></span>
      <span>人选 <b id="contact-count">0</b></span>
      <span>详情 <b id="detail-count">0</b></span>
    </div>
    <div class="btn-row">
      <button id="btn-open-workbench" class="primary">打开工作台</button>
      <button id="btn-export-full">导出完整 JSON</button>
      <button id="btn-refresh">刷新</button>
    </div>
  </div>
  <script src="popup.js"></script>
</body>
</html>
```

- [ ] **Step 2: Replace popup CSS**

Replace `extensions/maimai-scraper/popup.css` with:

```css
body { width: 340px; box-sizing: border-box; font-family: -apple-system, "Segoe UI", sans-serif; font-size: 13px; padding: 0; margin: 0; color: #172033; background: #f6f8fb; }
.launcher { padding: 12px; }
.header { display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
.header h3 { margin: 0; font-size: 15px; line-height: 22px; letter-spacing: 0; }
.header p { margin: 2px 0 0; color: #5f6b7a; font-size: 12px; line-height: 17px; }
.badge { flex: 0 0 auto; background: #e8f5e9; color: #2e7d32; padding: 3px 8px; border-radius: 999px; font-size: 11px; }
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; margin: 8px 0; }
.stats span { padding: 7px; border: 1px solid #e3e7ee; border-radius: 6px; background: #fff; color: #5f6b7a; font-size: 12px; }
.stats b { display: block; margin-top: 2px; color: #1a73e8; font-size: 15px; }
.btn-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
button { min-height: 30px; border: 1px solid #d5dbe5; border-radius: 5px; background: #fff; padding: 6px 10px; cursor: pointer; font-size: 12px; white-space: nowrap; }
button.primary { background: #1a73e8; border-color: #1a73e8; color: #fff; }
button:hover { background: #f0f4ff; }
button.primary:hover { background: #1557b0; }
```

- [ ] **Step 3: Replace popup JavaScript**

Replace `extensions/maimai-scraper/popup.js` with:

```javascript
(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  function sendMessage(message) {
    return new Promise(function (resolve) {
      chrome.runtime.sendMessage(message, function (resp) {
        if (chrome.runtime.lastError) {
          resolve({ ok: false, error: chrome.runtime.lastError.message });
          return;
        }
        resolve(resp || { ok: false, error: "无响应" });
      });
    });
  }

  function setBadge(text) {
    $("status-badge").textContent = text || "--";
  }

  function renderSummary(summary) {
    summary = summary || {};
    var totalRequests = summary.totalRequests || 0;
    var totalContacts = summary.totalContacts || 0;
    var totalDetails = summary.totalDetails || 0;
    $("req-count").textContent = totalRequests;
    $("contact-count").textContent = totalContacts;
    $("detail-count").textContent = totalDetails;
    $("status-line").textContent = "请求 " + totalRequests + " · 人选 " + totalContacts + " · 详情 " + totalDetails;
    if (summary.detail && summary.detail.state && summary.detail.state.batch_pause_until) {
      setBadge("批间休息");
    } else if (summary.detail && summary.detail.running) {
      setBadge("详情执行中");
    } else if (summary.pager && summary.pager.running) {
      setBadge("列表执行中");
    } else if (totalDetails > 0) {
      setBadge(totalDetails + " 详情");
    } else if (totalContacts > 0) {
      setBadge(totalContacts + " 人选");
    } else {
      setBadge("等待捕获");
    }
  }

  function refreshSummary() {
    sendMessage({ type: "getScraperSummary" }).then(function (resp) {
      if (!resp || !resp.ok) {
        $("status-line").textContent = resp && resp.error ? resp.error : "无法读取状态";
        setBadge("错误");
        return;
      }
      renderSummary(resp);
    });
  }

  $("btn-open-workbench").addEventListener("click", function () {
    sendMessage({ type: "openWorkbench" }).then(function (resp) {
      if (!resp || !resp.ok) {
        $("status-line").textContent = resp && resp.error ? resp.error : "无法打开工作台";
        setBadge("错误");
      }
    });
  });

  $("btn-export-full").addEventListener("click", function () {
    var filename = "maimai-capture-" + new Date().toISOString().slice(0, 10) + ".json";
    sendMessage({ type: "exportFullJson", filename: filename }).then(function (resp) {
      setBadge(resp && resp.downloadId ? "已导出" : "导出失败");
      refreshSummary();
    });
  });

  $("btn-refresh").addEventListener("click", refreshSummary);
  refreshSummary();
})();
```

- [ ] **Step 4: Run popup syntax and launcher tests**

Run:

```bash
node --check extensions/maimai-scraper/popup.js
python -m pytest tests/test_maimai_scraper_extension.py::test_popup_is_launcher_not_long_running_console -q
```

Expected: both pass.

- [ ] **Step 5: Update tests that still expect old popup controls**

The old popup tests `test_popup_contains_detail_tab_and_start_button`, `test_popup_detail_tab_hides_extra_controls_and_keeps_realtime_logs`, `test_popup_capture_tab_has_split_exports_and_pager_logs`, `test_popup_and_floating_widget_show_batch_pause_as_resting`, `test_search_template_tracks_headers_and_nested_pagination`, and `test_detail_batch_logs_each_job_success_and_failure` still reference full popup controls. Replace popup expectations in those tests so they point at `workbench.html` and `workbench.js` for the long-running UI, while keeping popup expectations limited to launcher behavior.

Use this pattern for migrated assertions:

```python
workbench_html = read_extension_file("workbench.html")
workbench_js = read_extension_file("workbench.js")

assert "btn-start-detail-batch" in workbench_html
assert "detail-log-list" in workbench_html
assert "renderDetailLogs" in workbench_js
assert "btn-start-pager" in workbench_html
assert "pager-log-list" in workbench_html
assert "renderPagerLogs" in workbench_js
```

- [ ] **Step 6: Run affected popup/workbench tests**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_popup_contains_detail_tab_and_start_button tests/test_maimai_scraper_extension.py::test_popup_detail_tab_hides_extra_controls_and_keeps_realtime_logs tests/test_maimai_scraper_extension.py::test_popup_capture_tab_has_split_exports_and_pager_logs tests/test_maimai_scraper_extension.py::test_popup_and_floating_widget_show_batch_pause_as_resting tests/test_maimai_scraper_extension.py::test_search_template_tracks_headers_and_nested_pagination tests/test_maimai_scraper_extension.py::test_detail_batch_logs_each_job_success_and_failure tests/test_maimai_scraper_extension.py::test_popup_is_launcher_not_long_running_console -q
```

Expected: PASS.

- [ ] **Step 7: Commit popup launcher conversion**

Run:

```bash
git add extensions/maimai-scraper/popup.html extensions/maimai-scraper/popup.css extensions/maimai-scraper/popup.js tests/test_maimai_scraper_extension.py
git commit -m "feat: convert maimai popup to workbench launcher"
```

Expected: commit succeeds with popup and test changes.

---

### Task 6: Add Side Panel Manifest and Fallback Integration

**Files:**
- Modify: `extensions/maimai-scraper/manifest.json`
- Modify: `extensions/maimai-scraper/content.js`
- Test: `tests/test_maimai_scraper_extension.py`

- [ ] **Step 1: Update manifest**

Change `extensions/maimai-scraper/manifest.json` so permissions and side panel fields read:

```json
  "permissions": ["storage", "scripting", "downloads", "sidePanel"],
```

Add this object after the `action` object:

```json
  "side_panel": {
    "default_path": "workbench.html"
  },
```

Keep `action.default_popup` as `popup.html`.

- [ ] **Step 2: Keep floating widget opener unchanged at the content boundary**

Confirm `content.js` still calls:

```javascript
safeSendMessage({ type: "openMainPage" });
```

No `content.js` change is needed if this line still exists; background now delegates `openMainPage` to `openWorkbenchPage`.

- [ ] **Step 3: Run manifest and opener tests**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_manifest_declares_side_panel_workbench tests/test_maimai_scraper_extension.py::test_open_main_page_delegates_to_workbench -q
```

Expected: PASS.

- [ ] **Step 4: Run manifest JSON parse check**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py::test_manifest_is_json_and_version_is_2_4 -q
```

Expected: PASS.

- [ ] **Step 5: Commit Side Panel manifest**

Run:

```bash
git add extensions/maimai-scraper/manifest.json extensions/maimai-scraper/content.js
git commit -m "feat: enable maimai scraper side panel"
```

Expected: commit succeeds. If `content.js` did not change, git commits only `manifest.json`.

---

### Task 7: Full Verification and Documentation Review

**Files:**
- Modify: `tasks/todo.md`
- Test: extension files and pytest suite

- [ ] **Step 1: Run all extension syntax checks**

Run:

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/autopager.js
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/popup.js
node --check extensions/maimai-scraper/workbench.js
```

Expected: every command exits 0 with no syntax error output.

- [ ] **Step 2: Run focused extension tests**

Run:

```bash
python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q
```

Expected: all tests pass. The previous baseline was `42 passed`; the new count should be higher because Task 1 added tests.

- [ ] **Step 3: Run broader relevant import tests**

Run:

```bash
python -m pytest tests/test_talent_library_cli.py::test_import_entry_accepts_extension_capture_and_pager_export_shapes tests/test_maimai_trace_diff.py -q
```

Expected: PASS. This confirms exported capture and pager shapes still match downstream import and trace analysis expectations.

- [ ] **Step 4: Run diff whitespace check**

Run:

```bash
git diff --check
```

Expected: exit code 0.

- [ ] **Step 5: Update tasks review**

In `tasks/todo.md`, update the `浏览器扩展工作台 V2.0 实施计划（2026-05-18）` Review with:

```markdown
- 实施计划已写入 `docs/superpowers/plans/2026-05-18-maimai-scraper-workbench-v2.md`。
- 计划覆盖测试护栏、background 状态层、workbench UI、popup 启动器、side panel fallback 和最终验证。
- 自检结果：spec 覆盖、空白项扫描、消息名一致性、请求执行不变量均已检查。
```

When implementation finishes during execution, append the actual syntax, pytest, and manual verification results under the same Review section.

- [ ] **Step 6: Commit plan review update**

Run:

```bash
git add tasks/todo.md
git commit -m "docs: record maimai workbench implementation plan"
```

Expected: commit succeeds with task review updates.

---

## Self-Review Checklist

- Spec coverage:
  - Side Panel and fallback: Task 2, Task 3, Task 6.
  - Workbench persistent UI: Task 4.
  - Popup launcher: Task 5.
  - `workbenchState` and `pagerLogs`: Task 2, Task 3.
  - Request execution invariant: Task 1, Task 7.
  - Existing list/detail chain preservation: Task 1, Task 7.
  - Verification commands: Task 7.
- Placeholder scan:
  - The plan uses concrete file paths, message names, test functions, command lines, expected results, and commit messages.
- Type and naming consistency:
  - State key is `workbenchState`.
  - Log key is `pagerLogs`.
  - Snapshot message is `getWorkbenchSnapshot`.
  - Opener message is `openWorkbench`.
  - View message is `setWorkbenchView`.
  - Fallback target is `workbench.html`.
