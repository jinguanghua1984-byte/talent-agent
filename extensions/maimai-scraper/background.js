importScripts("idb.js", "autopager.js", "detail_batch.js");

// background.js — Service Worker

var pendingSearchCallbacks = {};
var __activePager = null;
var __pagerTabId = null;
var __pagerStarting = false;
var __activeDetailBatch = null;
var __detailBatchTabId = null;
var __detailBatchRunToken = 0;
var __detailBatchRunning = false;
var __detailBatchStarting = false;
var __detailBatchRecovery = null;
var __diagnosticTraceWrite = Promise.resolve();
var __workbenchStateWrite = Promise.resolve();

function tagDetailBatchRecord(record, runToken) {
  return Object.assign({}, record || {}, { run_token: runToken });
}

function detailBatchRecordMatchesToken(record, runToken) {
  if (!runToken) return true;
  return !record || record.run_token === undefined || record.run_token === runToken;
}

function detailBatchJobMatchesToken(record, runToken) {
  if (!runToken) return true;
  return Boolean(record && record.run_token === runToken);
}

function filterDetailBatchRecords(records, runToken) {
  return (records || []).filter(function (record) {
    return detailBatchRecordMatchesToken(record, runToken);
  });
}

function filterDetailBatchJobs(records, runToken) {
  return (records || []).filter(function (record) {
    return detailBatchJobMatchesToken(record, runToken);
  });
}

function detailBatchStateForToken(state, runToken) {
  if (!state) return null;
  if (!runToken || state.run_token === undefined || state.run_token === runToken) {
    return state;
  }
  return null;
}

function isDetailRecord(record) {
  var url = record && record.url ? String(record.url) : "";
  if (
    url.indexOf("/api/pc/u/") !== -1 ||
    url.indexOf("/api/pc/profile/") !== -1 ||
    url.indexOf("/api/pc/user/") !== -1 ||
    url.indexOf("/api/profile/") !== -1 ||
    url.indexOf("/api/user/") !== -1
  ) {
    return true;
  }
  var data = record && record.responseData;
  var payload = data && data.data ? data.data : data;
  if (!payload || typeof payload !== "object") return false;
  var contacts = payload.contacts || payload.list || payload.items || [];
  if (contacts.length > 0) return false;
  return Boolean(payload.exp || payload.edu || payload.user_project || payload.profile || payload.name);
}

function detailKey(record) {
  var data = record && record.responseData;
  var payload = data && data.data ? data.data : data || {};
  return String(
    payload.id ||
    payload.uid ||
    payload.user_id ||
    payload.dstu ||
    (record && record.url) ||
    (record && record.id) ||
    Date.now()
  );
}

function dedupeByPreferredId(items) {
  var byKey = new Map();
  (items || []).forEach(function (item, index) {
    if (!item) return;
    var key = item.id || item.detail_url || item.url || JSON.stringify(item).slice(0, 120) || index;
    byKey.set(String(key), item);
  });
  return Array.from(byKey.values());
}

function detailStatusCounts(jobs, detailBatchState) {
  var counts = {
    queued: 0,
    running: 0,
    done: 0,
    failed: 0,
    skipped: 0,
  };
  (jobs || []).forEach(function (job) {
    var status = job && job.status ? String(job.status) : "";
    if (Object.prototype.hasOwnProperty.call(counts, status)) {
      counts[status]++;
    }
  });

  if (detailBatchState && detailBatchState.counts) {
    Object.keys(counts).forEach(function (key) {
      if (typeof detailBatchState.counts[key] === "number") {
        counts[key] = detailBatchState.counts[key];
      }
    });
  }
  return counts;
}

function detailCircuitBreaker(detailBatchState) {
  if (!detailBatchState) {
    return { tripped: false, reason: null };
  }
  return detailBatchState.circuit_breaker ||
    detailBatchState.circuitBreaker ||
    { tripped: false, reason: null };
}

function buildFullExportData() {
  return Promise.all([
    PagerDB.getAll().catch(function () { return []; }),
    DetailDB.getAllJobs().catch(function () { return []; }),
    DetailDB.getAllDetails().catch(function () { return []; }),
    new Promise(function (resolve) {
      chrome.storage.local.get({
        captured: [],
        contacts: [],
        details: [],
        detailBatchState: null,
        detailBatchLogs: [],
        detailBatchRunToken: __detailBatchRunToken,
        diagnosticTraces: [],
      }, function (r) {
        resolve(r);
      });
    }),
  ]).then(function (parts) {
    var pagerContacts = parts[0] || [];
    var detailJobs = parts[1] || [];
    var detailDbDetails = parts[2] || [];
    var stored = parts[3] || { captured: [], contacts: [], details: [], detailBatchState: null };
    var currentRunToken = stored.detailBatchRunToken || __detailBatchRunToken;
    detailJobs = filterDetailBatchJobs(detailJobs, currentRunToken);
    detailDbDetails = filterDetailBatchRecords(detailDbDetails, currentRunToken);
    var storageDetails = filterDetailBatchRecords(stored.details || [], currentRunToken);
    var detailLogs = filterDetailBatchRecords(stored.detailBatchLogs || [], currentRunToken);
    var detailBatchState = detailBatchStateForToken(stored.detailBatchState, currentRunToken);
    var statusCounts = detailStatusCounts(detailJobs, detailBatchState);
    var contacts = dedupeByPreferredId((stored.contacts || []).concat(pagerContacts || []));
    var details = dedupeByPreferredId(storageDetails.concat(detailDbDetails || []));
    return {
      exportTime: new Date().toISOString(),
      metadata: {
        export_type: "full",
        detail_mode: (detailBatchState && detailBatchState.mode) || "batch_replay",
        pager_contacts: pagerContacts.length,
        captured_requests: (stored.captured || []).length,
        captured_details: (stored.details || []).length,
        total_jobs: detailJobs.length,
        queued: statusCounts.queued,
        running: statusCounts.running,
        done: statusCounts.done,
        failed: statusCounts.failed,
        skipped: statusCounts.skipped,
        circuit_breaker: detailCircuitBreaker(detailBatchState),
      },
      contacts: contacts,
      totalContacts: contacts.length,
      details: details,
      totalDetails: details.length,
      detailJobs: detailJobs,
      detailBatchLogs: detailLogs,
      diagnosticTraces: stored.diagnosticTraces || [],
      requests: stored.captured || [],
    };
  });
}

function downloadJsonData(data, filename, saveAs, sendResponse) {
  var jsonStr = JSON.stringify(data, null, 2);
  var url = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
  chrome.downloads.download({
    url: url,
    filename: filename || "maimai-export.json",
    saveAs: saveAs !== false,
  }, function (downloadId) {
    sendResponse({ ok: true, downloadId: downloadId });
  });
}

function activeMaimaiTab() {
  return new Promise(function (resolve, reject) {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0]) {
        reject(new Error("无活跃标签页"));
        return;
      }
      if (!tabs[0].url || tabs[0].url.indexOf("maimai.cn") === -1) {
        reject(new Error("请在脉脉列表页使用批量详情"));
        return;
      }
      resolve(tabs[0]);
    });
  });
}

function sendDetailFetch(tabId, job) {
  return new Promise(function (resolve) {
    chrome.tabs.sendMessage(tabId, { type: "detailFetch", job: job }, function (resp) {
      if (chrome.runtime.lastError) {
        resolve({
          ok: false,
          error: chrome.runtime.lastError.message,
          errors: [chrome.runtime.lastError.message],
        });
        return;
      }
      resolve(resp || { ok: false, error: "无响应", errors: ["无响应"] });
    });
  });
}

function summarizeDiagnosticTab(tab) {
  if (!tab) return null;
  return {
    id: tab.id,
    windowId: tab.windowId,
    active: Boolean(tab.active),
    highlighted: Boolean(tab.highlighted),
    url: tab.url || "",
    title: tab.title || "",
    status: tab.status || "",
    discarded: Boolean(tab.discarded),
  };
}

function senderTypeForDiagnostic(sender) {
  var url = sender && sender.url ? String(sender.url) : "";
  if (url.indexOf("automation.html") !== -1) return "automation";
  if (url.indexOf("popup.html") !== -1) return "popup";
  if (url.indexOf("maimai.cn") !== -1) return "maimai_content";
  if (url.indexOf("chrome-extension://") === 0) return "extension";
  if (sender && sender.tab) return "content";
  return "unknown";
}

function queryDiagnosticActiveTab() {
  return new Promise(function (resolve) {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      var err = chrome.runtime.lastError;
      resolve({
        error: err ? err.message : null,
        tab: summarizeDiagnosticTab(tabs && tabs[0]),
      });
    });
  });
}

function queryDiagnosticMaimaiTabs() {
  return new Promise(function (resolve) {
    chrome.tabs.query({ url: ["*://maimai.cn/*", "*://*.maimai.cn/*"] }, function (tabs) {
      var err = chrome.runtime.lastError;
      resolve({
        error: err ? err.message : null,
        tabs: (tabs || []).map(summarizeDiagnosticTab),
      });
    });
  });
}

function getDiagnosticCurrentWindow() {
  return new Promise(function (resolve) {
    chrome.windows.getCurrent({}, function (windowInfo) {
      var err = chrome.runtime.lastError;
      resolve({
        error: err ? err.message : null,
        window: windowInfo ? {
          id: windowInfo.id,
          focused: Boolean(windowInfo.focused),
          state: windowInfo.state || "",
          type: windowInfo.type || "",
        } : null,
      });
    });
  });
}

function getDiagnosticTabById(tabId) {
  if (typeof tabId !== "number" || Number.isNaN(tabId)) {
    return Promise.resolve({ error: null, tab: null });
  }
  return new Promise(function (resolve) {
    chrome.tabs.get(tabId, function (tab) {
      var err = chrome.runtime.lastError;
      resolve({
        error: err ? err.message : null,
        tab: summarizeDiagnosticTab(tab),
      });
    });
  });
}

function chooseDiagnosticTargetTab(msg, activeTab, maimaiTabs, explicitTab) {
  if (explicitTab) return explicitTab;
  if (activeTab && activeTab.url && activeTab.url.indexOf("maimai.cn") !== -1) {
    return activeTab;
  }
  if (maimaiTabs && maimaiTabs.length === 1) {
    return maimaiTabs[0];
  }
  return null;
}

function traceDiagnosticPageState(tab) {
  if (!tab || typeof tab.id !== "number") {
    return Promise.resolve({ ok: false, skipped: "no_target_tab" });
  }
  if (!tab.url || tab.url.indexOf("maimai.cn") === -1) {
    return Promise.resolve({ ok: false, skipped: "target_not_maimai", target: summarizeDiagnosticTab(tab) });
  }
  return new Promise(function (resolve) {
    chrome.tabs.sendMessage(tab.id, { type: "tracePageState" }, function (resp) {
      if (chrome.runtime.lastError) {
        resolve({
          ok: false,
          error: chrome.runtime.lastError.message,
          target: summarizeDiagnosticTab(tab),
        });
        return;
      }
      resolve(Object.assign({ target: summarizeDiagnosticTab(tab) }, resp || { ok: false, error: "无响应" }));
    });
  });
}

function buildDiagnosticTrace(action, msg, sender) {
  var started = Date.now();
  var startedAt = new Date(started).toISOString();
  var explicitTargetTabId = msg && msg.targetTabId !== undefined ? Number(msg.targetTabId) : null;

  return Promise.all([
    queryDiagnosticActiveTab(),
    queryDiagnosticMaimaiTabs(),
    getDiagnosticCurrentWindow(),
    getDiagnosticTabById(explicitTargetTabId),
  ]).then(function (parts) {
    var activeResult = parts[0] || {};
    var maimaiResult = parts[1] || {};
    var windowResult = parts[2] || {};
    var explicitResult = parts[3] || {};
    var activeTab = activeResult.tab || null;
    var maimaiTabs = maimaiResult.tabs || [];
    var targetTab = chooseDiagnosticTargetTab(msg, activeTab, maimaiTabs, explicitResult.tab || null);

    return traceDiagnosticPageState(targetTab).then(function (pageState) {
      var ended = Date.now();
      var currentWindow = windowResult.window || null;
      return {
        id: "trace_" + ended + "_" + Math.random().toString(36).slice(2, 8),
        action: action,
        actionLabel: (msg && msg.label) || action,
        source: senderTypeForDiagnostic(sender),
        senderType: senderTypeForDiagnostic(sender),
        sender: {
          id: sender && sender.id ? sender.id : "",
          url: sender && sender.url ? sender.url : "",
          frameId: sender && typeof sender.frameId === "number" ? sender.frameId : null,
          tab: summarizeDiagnosticTab(sender && sender.tab),
        },
        activeTab: activeTab,
        activeTabError: activeResult.error || null,
        maimaiTabs: maimaiTabs,
        maimaiTabsError: maimaiResult.error || null,
        targetTab: targetTab,
        explicitTargetTabId: explicitTargetTabId,
        explicitTargetTabError: explicitResult.error || null,
        currentWindow: currentWindow,
        windowFocused: Boolean(currentWindow && currentWindow.focused),
        windowError: windowResult.error || null,
        pageState: pageState,
        timing: {
          startedAt: startedAt,
          endedAt: new Date(ended).toISOString(),
          durationMs: ended - started,
        },
      };
    });
  });
}

function recordDiagnosticTrace(trace) {
  __diagnosticTraceWrite = __diagnosticTraceWrite.catch(function () {}).then(function () {
    return new Promise(function (resolve) {
      chrome.storage.local.get({ diagnosticTraces: [] }, function (r) {
        var diagnosticTraces = r.diagnosticTraces || [];
        diagnosticTraces.push(trace);
        chrome.storage.local.set({ diagnosticTraces: diagnosticTraces.slice(-200) }, function () {
          resolve(trace);
        });
      });
    });
  });
  return __diagnosticTraceWrite;
}

function recordActionDiagnosticTrace(action, msg, sender) {
  try {
    buildDiagnosticTrace(action, msg || {}, sender || {}).then(function (trace) {
      return recordDiagnosticTrace(trace);
    }).catch(function () {});
  } catch (err) {}
}

function clearDiagnosticTraceStorage() {
  __diagnosticTraceWrite = __diagnosticTraceWrite.catch(function () {}).then(function () {
    return new Promise(function (resolve) {
      chrome.storage.local.set({ diagnosticTraces: [] }, function () {
        resolve([]);
      });
    });
  });
  return __diagnosticTraceWrite;
}

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
    if (value === undefined) return;
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
  __workbenchStateWrite = __workbenchStateWrite.catch(function () {}).then(function () {
    return loadWorkbenchStorage().then(function (stored) {
      var state = normalizeWorkbenchState(mergePlainObject(stored.workbenchState, patch || {}));
      return new Promise(function (resolve) {
        chrome.storage.local.set({ workbenchState: state }, function () {
          resolve(state);
        });
      });
    });
  });
  return __workbenchStateWrite;
}

function resetWorkbenchStateAndPagerLogs() {
  __workbenchStateWrite = __workbenchStateWrite.catch(function () {}).then(function () {
    return new Promise(function (resolve) {
      chrome.storage.local.set({
        workbenchState: copyJson(DEFAULT_WORKBENCH_STATE),
        pagerLogs: [],
      }, function () {
        resolve(copyJson(DEFAULT_WORKBENCH_STATE));
      });
    });
  });
  return __workbenchStateWrite;
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

function hasWorkbenchDocument() {
  var manifest = chrome.runtime.getManifest ? chrome.runtime.getManifest() : {};
  var resources = manifest.web_accessible_resources || [];
  if (manifest.side_panel && manifest.side_panel.default_path === "workbench.html") return true;
  return resources.some(function (group) {
    return (group.resources || []).indexOf("workbench.html") !== -1;
  });
}

function sidePanelOpenOptions(msg, sender) {
  msg = msg || {};
  if (typeof msg.windowId === "number" && msg.windowId >= 0) {
    return { windowId: msg.windowId };
  }
  if (sender && sender.tab && typeof sender.tab.windowId === "number") {
    return { windowId: sender.tab.windowId };
  }
  if (sender && sender.tab && typeof sender.tab.id === "number") {
    return { tabId: sender.tab.id };
  }
  return null;
}

function openWorkbenchPage(msg, sender, sendResponse) {
  if (!hasWorkbenchDocument()) {
    sendResponse({ ok: false, error: "workbench_not_available" });
    return;
  }

  function recordOpened() {
    saveWorkbenchStatePatch({ last_opened_at: new Date().toISOString() }).catch(function () {});
  }

  if (!(chrome.sidePanel && chrome.sidePanel.open)) {
    sendResponse({ ok: false, error: "side_panel_api_unavailable" });
    return;
  }

  var openOptions = sidePanelOpenOptions(msg, sender);
  if (!openOptions) {
    sendResponse({ ok: false, error: "side_panel_window_unavailable" });
    return;
  }

  try {
    var opened = chrome.sidePanel.open(openOptions);
    if (opened && opened.then) {
      opened.then(function () {
        recordOpened();
        sendResponse({ ok: true, opened: "sidePanel" });
      }).catch(function (err) {
        sendResponse({ ok: false, error: err && err.message ? err.message : "side_panel_open_failed" });
      });
    } else {
      recordOpened();
      sendResponse({ ok: true, opened: "sidePanel" });
    }
  } catch (err) {
    sendResponse({ ok: false, error: err && err.message ? err.message : "side_panel_open_failed" });
  }
}

function saveDetailBatchState(state, runToken) {
  return new Promise(function (resolve) {
    var taggedState = runToken ? tagDetailBatchRecord(state, runToken) : state;
    chrome.storage.local.set({
      detailBatchState: taggedState,
      detailBatchRunToken: runToken || __detailBatchRunToken,
    }, function () {
      resolve();
    });
  });
}

function saveDetailBatchTabId(tabId) {
  __detailBatchTabId = tabId;
  return new Promise(function (resolve) {
    chrome.storage.local.set({ detailBatchTabId: tabId || null }, function () {
      resolve();
    });
  });
}

function appendStorageDetail(detail, runToken) {
  return new Promise(function (resolve) {
    chrome.storage.local.get({ details: [] }, function (r) {
      var details = r.details || [];
      var exists = new Set(details.map(function (d) { return String(d.id); }));
      var taggedDetail = runToken ? tagDetailBatchRecord(detail, runToken) : detail;
      if (taggedDetail && taggedDetail.id && !exists.has(String(taggedDetail.id))) {
        details.push(taggedDetail);
      }
      chrome.storage.local.set({ details: details }, function () {
        resolve();
      });
    });
  });
}

function appendDetailBatchLog(level, message, meta, runToken) {
  return new Promise(function (resolve) {
    chrome.storage.local.get({ detailBatchLogs: [] }, function (r) {
      var logs = r.detailBatchLogs || [];
      logs.push({
        ts: new Date().toISOString(),
        level: level || "info",
        message: message || "",
        meta: meta || null,
        run_token: runToken,
      });
      chrome.storage.local.set({ detailBatchLogs: logs.slice(-120) }, function () {
        resolve();
      });
    });
  });
}

function formatDelayMs(ms) {
  var value = Math.max(0, Number(ms) || 0);
  var totalSeconds = Math.ceil(value / 1000);
  var minutes = Math.floor(totalSeconds / 60);
  var seconds = totalSeconds % 60;
  if (minutes > 0 && seconds > 0) return minutes + " 分 " + seconds + " 秒";
  if (minutes > 0) return minutes + " 分钟";
  return seconds + " 秒";
}

function completedCountForDetailEvent(event) {
  var counts = event && event.counts ? event.counts : {};
  var counted = (counts.done || 0) + (counts.failed || 0) + (counts.skipped || 0);
  var batchCompleted = event && typeof event.batch_pause_completed === "number" ? event.batch_pause_completed : 0;
  return Math.max(batchCompleted, counted);
}

function endpointStatusText(endpoints) {
  endpoints = endpoints || {};
  var parts = Object.keys(endpoints).map(function (key) {
    var item = endpoints[key] || {};
    return key + "=" + (item.httpStatus || 0);
  });
  return parts.length ? "；接口状态 " + parts.join(", ") : "";
}

function messageForDetailEvent(event) {
  var type = event && event.type ? String(event.type) : "";
  if (type === "detail_batch_completed") {
    return "批量详情已完成";
  }
  if (type === "detail_batch_stopped") {
    return "批量详情已停止";
  }
  if (type === "detail_batch_paused") {
    if (event && event.reason === "batch_pause") {
      var completed = completedCountForDetailEvent(event);
      var total = typeof event.total_jobs === "number" ? event.total_jobs : 0;
      var delay = event.delayMs || event.batch_pause_delay_ms || 0;
      var progress = total > 0 ? completed + "/" + total : completed;
      return "批间暂停: 已完成 " + progress + "，休息 " + formatDelayMs(delay) + " 后继续";
    }
    if (event && event.reason === "daily_limit_reached") {
      return "批量详情已暂停: 已达到每日上限，明天或调整上限后继续";
    }
    return event && event.reason ? "批量详情已暂停: " + event.reason : "批量详情已暂停";
  }
  if (type === "detail_batch_job_failed") {
    var job = (event && event.job) || {};
    var label = job.name || job.id || "未知联系人";
    var reason = (event && event.reason) || "detail_fetch_failed";
    var riskText = event && event.riskFailure ? "；疑似登录失效、风控或限流" : "";
    return "详情抓取失败: " + label + "，原因 " + reason + endpointStatusText(event && event.endpoints) + riskText;
  }
  if (type === "detail_batch_job_succeeded") {
    var successJob = (event && event.job) || {};
    var successLabel = successJob.name || successJob.id || "未知联系人";
    var completedNow = completedCountForDetailEvent(event);
    var totalNow = typeof event.total_jobs === "number" ? event.total_jobs : 0;
    var progressNow = totalNow > 0 ? "，进度 " + completedNow + "/" + totalNow : "";
    var warnings = event && Array.isArray(event.warnings) ? event.warnings.filter(Boolean) : [];
    var warningText = warnings.length > 0 ? "；部分接口异常 " + warnings.join(", ") : "";
    return "详情抓取成功: " + successLabel + progressNow + endpointStatusText(event && event.endpoints) + warningText;
  }
  if (type === "detail_batch_error") {
    return event && event.error ? "批量详情出错: " + event.error : "批量详情出错";
  }
  if (type === "detail_batch_progress") {
    var counts = event && event.counts ? event.counts : {};
    var done = typeof counts.done === "number" ? counts.done : 0;
    var total = typeof event.total_jobs === "number" ? event.total_jobs : 0;
    if (total > 0) {
      return "批量详情进度: " + done + "/" + total;
    }
    return "批量详情进行中";
  }
  return "批量详情状态更新";
}

function emitDetailBatchEvent(event, runToken) {
  var level = event && event.type === "detail_batch_error" ? "error" : "info";
  if (event && event.type === "detail_batch_job_failed") level = "warn";
  return appendDetailBatchLog(level, messageForDetailEvent(event), event, runToken).then(function () {
    try {
      var sent = chrome.runtime.sendMessage(event);
      if (sent && sent.catch) sent.catch(function () {});
    } catch (err) {}
  });
}

function storageContactsAndState() {
  return new Promise(function (resolve) {
    chrome.storage.local.get({
      captured: [],
      contacts: [],
      details: [],
      detailImportedContacts: [],
      detailBatchState: null,
      detailBatchLogs: [],
      detailBatchRunToken: __detailBatchRunToken,
      detailBatchTabId: __detailBatchTabId,
    }, function (r) {
      resolve(r);
    });
  });
}

function tabForDetailBatchRecovery(stored) {
  return new Promise(function (resolve, reject) {
    var tabId = (stored && stored.detailBatchTabId) || __detailBatchTabId;
    if (!tabId) {
      activeMaimaiTab().then(resolve, reject);
      return;
    }
    chrome.tabs.get(tabId, function (tab) {
      if (chrome.runtime.lastError || !tab || !tab.url || tab.url.indexOf("maimai.cn") === -1) {
        activeMaimaiTab().then(resolve, reject);
        return;
      }
      resolve(tab);
    });
  });
}

function detailBatchOptionsFromState(state) {
  state = state || {};
  var policy = state.policy || {};
  return {
    mode: state.mode || policy.mode || "safe",
    dailyLimit: policy.dailyLimit || 10000,
    duplicateContacts: state.duplicate_contacts || 0,
  };
}

function isActiveDetailBatchState(state) {
  var status = state && state.status ? String(state.status) : "";
  return status === "running" || status === "paused" || status === "stopping";
}

function normalizeJobsForDetailResume(jobs) {
  return (jobs || []).map(function (job) {
    if (job && job.status === "running") {
      return Object.assign({}, job, { status: "queued" });
    }
    return job;
  });
}

function hasRemainingDetailJobs(jobs) {
  return (jobs || []).some(function (job) {
    var status = job && job.status ? String(job.status) : "queued";
    return status !== "done" && status !== "failed" && status !== "skipped";
  });
}

function runDetailBatchJobs(tab, jobs, options, runToken) {
  __detailBatchRunning = true;
  saveDetailBatchTabId(tab.id);
  __activeDetailBatch = DetailBatch.run(jobs, options || {}, {
    sendDetailFetch: function (job) {
      return sendDetailFetch(tab.id, job);
    },
    saveJob: function (job) {
      if (runToken !== __detailBatchRunToken) return Promise.resolve();
      return DetailDB.putJob(tagDetailBatchRecord(job, runToken));
    },
    saveDetail: function (detail) {
      if (runToken !== __detailBatchRunToken) return Promise.resolve();
      var taggedDetail = tagDetailBatchRecord(detail, runToken);
      return DetailDB.putDetail(taggedDetail).then(function () {
        if (runToken !== __detailBatchRunToken) return Promise.resolve();
        return appendStorageDetail(taggedDetail, runToken);
      });
    },
    saveState: function (state) {
      if (runToken !== __detailBatchRunToken) return Promise.resolve();
      return saveDetailBatchState(state, runToken);
    },
    onEvent: function (event) {
      if (runToken !== __detailBatchRunToken) return;
      return emitDetailBatchEvent(event, runToken);
    },
  }).catch(function (err) {
    if (runToken !== __detailBatchRunToken) return;
    var failedState = Object.assign({}, DetailBatch.getState(), {
      status: "failed",
      error: err.message,
      updated_at: new Date().toISOString(),
    });
    return saveDetailBatchState(failedState, runToken).then(function () {
      if (runToken !== __detailBatchRunToken) return;
      return emitDetailBatchEvent(Object.assign({ type: "detail_batch_error", error: err.message }, failedState), runToken);
    });
  }).finally(function () {
    if (runToken === __detailBatchRunToken) {
      __detailBatchRunning = false;
    }
  });
  return __activeDetailBatch;
}

function recoverExpiredBatchPauseIfNeeded() {
  if (__detailBatchRunning) {
    return Promise.resolve({ ok: true, resumed: false, reason: "detail_batch_running" });
  }
  if (__detailBatchRecovery) return __detailBatchRecovery;

  __detailBatchRecovery = Promise.all([
    DetailDB.getAllJobs().catch(function () { return []; }),
    storageContactsAndState(),
  ]).then(function (parts) {
    var storedJobs = parts[0] || [];
    var stored = parts[1] || {};
    var currentRunToken = stored.detailBatchRunToken || __detailBatchRunToken;
    var state = detailBatchStateForToken(stored.detailBatchState, currentRunToken);
    if (!state || !state.batch_pause_until) {
      return { ok: true, resumed: false, reason: "no_batch_pause" };
    }
    var pauseUntil = Date.parse(state.batch_pause_until);
    if (Number.isNaN(pauseUntil) || pauseUntil > Date.now()) {
      return { ok: true, resumed: false, reason: "batch_pause_waiting" };
    }

    var jobs = normalizeJobsForDetailResume(filterDetailBatchJobs(storedJobs, currentRunToken));
    if (!hasRemainingDetailJobs(jobs)) {
      return { ok: true, resumed: false, reason: "no_remaining_jobs" };
    }

    __detailBatchRunToken = currentRunToken || __detailBatchRunToken;
    return tabForDetailBatchRecovery(stored).then(function (tab) {
      return appendDetailBatchLog("info", "批间休息到点，自动继续", {
        completed: state.batch_pause_completed || 0,
        totalJobs: state.total_jobs || jobs.length,
        tabId: tab.id,
      }, currentRunToken).then(function () {
        runDetailBatchJobs(tab, jobs, detailBatchOptionsFromState(state), currentRunToken);
        return { ok: true, resumed: true };
      });
    }).catch(function (err) {
      return appendDetailBatchLog("warn", "批间休息已结束，但无法自动继续: " + err.message, {
        error: err.message,
      }, currentRunToken).then(function () {
        return { ok: false, resumed: false, error: err.message };
      });
    });
  }).finally(function () {
    __detailBatchRecovery = null;
  });

  return __detailBatchRecovery;
}

function buildScraperSummary() {
  return Promise.all([
    PagerDB.getAll().catch(function () { return []; }),
    DetailDB.getAllJobs().catch(function () { return []; }),
    DetailDB.getAllDetails().catch(function () { return []; }),
    DetailDB.getCounts().catch(function () { return { jobs: 0, details: 0 }; }),
    storageContactsAndState(),
  ]).then(function (parts) {
    var pagerContacts = parts[0] || [];
    var detailJobs = parts[1] || [];
    var detailDbDetails = parts[2] || [];
    var detailCounts = parts[3] || { jobs: 0, details: 0 };
    var stored = parts[4] || {};
    var currentRunToken = stored.detailBatchRunToken || __detailBatchRunToken;
    detailJobs = filterDetailBatchJobs(detailJobs, currentRunToken);
    detailDbDetails = filterDetailBatchRecords(detailDbDetails, currentRunToken);
    detailCounts = { jobs: detailJobs.length, details: detailDbDetails.length };
    var storageDetails = filterDetailBatchRecords(stored.details || [], currentRunToken);
    var detailLogs = filterDetailBatchRecords(stored.detailBatchLogs || [], currentRunToken);
    var detailBatchState = detailBatchStateForToken(stored.detailBatchState, currentRunToken) || DetailBatch.getState();
    var contacts = dedupeByPreferredId((stored.contacts || []).concat(pagerContacts));
    var details = dedupeByPreferredId(storageDetails.concat(detailDbDetails));
    var pager = __activePager || {};

    return {
      contacts: contacts,
      totalContacts: contacts.length,
      requests: stored.captured || [],
      totalRequests: (stored.captured || []).length,
      details: details,
      totalDetails: details.length,
      pager: {
        running: Boolean(pager.running),
        currentPage: pager.currentPage || 0,
        totalPages: pager.totalPages || 0,
        totalFromApi: pager.totalFromApi || 0,
      },
      detail: {
        state: detailBatchState,
        running: Boolean(detailBatchState && (detailBatchState.status === "running" || detailBatchState.status === "paused")),
        completed: Boolean(detailBatchState && detailBatchState.status === "completed"),
        totalJobs: detailBatchState.total_jobs || detailJobs.length,
        counts: detailStatusCounts(detailJobs, detailBatchState),
        storageCounts: detailCounts,
        jobs: detailJobs.length,
        contacts: ((stored.detailImportedContacts || []).length || contacts.length),
      },
      logs: detailLogs.slice(-20),
    };
  });
}

function detailBatchContacts() {
  return Promise.all([
    PagerDB.getAll().catch(function () { return []; }),
    storageContactsAndState(),
  ]).then(function (parts) {
    var pagerContacts = parts[0] || [];
    var stored = parts[1] || { contacts: [] };
    var imported = DetailBatch.getImportedContacts();
    if (imported.length > 0) return imported;
    if ((stored.detailImportedContacts || []).length > 0) return stored.detailImportedContacts || [];
    if (pagerContacts.length > 0) return pagerContacts;
    if ((stored.contacts || []).length > 0) return stored.contacts || [];
    return [];
  });
}

function parseMaimaiProfileUrl(url) {
  var result = {};
  if (!url) return result;
  try {
    var parsed = new URL(url);
    var dstu = parsed.searchParams.get("dstu") || parsed.searchParams.get("to_uid");
    var token = parsed.searchParams.get("trackable_token");
    if (dstu) result.id = dstu;
    if (token) result.trackable_token = token;
  } catch (err) {}
  return result;
}

function importItemsFromPayload(payload) {
  if (Array.isArray(payload)) return payload;
  if (!payload || typeof payload !== "object") return [];
  var keys = ["contacts", "detailJobs", "top10", "candidates", "matches", "results", "items"];
  for (var i = 0; i < keys.length; i++) {
    var value = payload[keys[i]];
    if (Array.isArray(value)) return value;
  }
  return [];
}

function normalizeImportContact(item) {
  if (!item || typeof item !== "object") return null;
  if (item.source_contact) {
    item = item.source_contact;
  }
  var profileUrl = item.profile_url || item.detail_url || item.url || "";
  var parsedUrl = parseMaimaiProfileUrl(profileUrl);
  var id = item.platform_id || item.maimai_id || item.uid || item.id || item.dstu || parsedUrl.id || "";
  return {
    id: id ? String(id) : "",
    trackable_token: String(item.trackable_token || item.trackableToken || parsedUrl.trackable_token || ""),
    name: String(item.name || ""),
    company: String(item.company || item.current_company || ""),
    position: String(item.position || item.title || item.current_title || ""),
    candidate_id: item.candidate_id || null,
    detail_url: String(profileUrl || (id ? "https://maimai.cn/u/" + id : "")),
    source_contact: item,
  };
}

function normalizeImportContacts(payload) {
  var items = importItemsFromPayload(payload);
  var seen = new Set();
  var contacts = [];
  items.forEach(function (item) {
    var contact = normalizeImportContact(item);
    if (!contact) return;
    var key = contact.id || ("missing_" + contacts.length);
    if (contact.id && seen.has(key)) return;
    if (contact.id) seen.add(key);
    contacts.push(contact);
  });
  return contacts;
}

chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  // 存储捕获的请求数据
  if (msg.type === "capture") {
    chrome.storage.local.get({ captured: [], contacts: [], details: [] }, function (r) {
      var requests = r.captured || [];
      requests.push(msg.record);

      // 自动提取 contacts
      var contacts = r.contacts || [];
      var details = r.details || [];
      var data = msg.record.responseData;
      if (data && data.data) {
        var newContacts = data.data.contacts || data.data.list || data.data.items || [];
        if (newContacts.length > 0) {
          // 按 id 去重
          var existingIds = new Set(contacts.map(function (c) { return c.id; }));
          newContacts.forEach(function (c) {
            if (c.id && !existingIds.has(c.id)) {
              contacts.push(c);
            }
          });
        }
      }
      if (isDetailRecord(msg.record)) {
        var key = detailKey(msg.record);
        var existingDetailIds = new Set(details.map(function (d) { return d.id; }));
        if (!existingDetailIds.has(key)) {
          details.push({
            id: key,
            url: msg.record.url,
            ts: msg.record.ts,
            data: data && data.data ? data.data : data,
            recordId: msg.record.id,
          });
        }
      }

      chrome.storage.local.set({
        captured: requests,
        contacts: contacts,
        details: details,
      });
    });
    sendResponse({ ok: true });
    return true;
  }

  // 搜索结果回调
  if (msg.type === "searchResult") {
    if (pendingSearchCallbacks[msg.requestId]) {
      pendingSearchCallbacks[msg.requestId](msg);
      delete pendingSearchCallbacks[msg.requestId];
    }
    sendResponse({ ok: true });
    return true;
  }

  // DOM 抓取结果回调
  if (msg.type === "domScrapeResult") {
    chrome.storage.local.set({ domScrapeResult: msg });
    sendResponse({ ok: true });
    return true;
  }

  // 获取存储数据
  if (msg.type === "getStoredData") {
    chrome.storage.local.get({ captured: [], contacts: [], details: [] }, function (r) {
      sendResponse(r);
    });
    return true;
  }

  // 清除数据
  if (msg.type === "openWorkbench") {
    openWorkbenchPage(msg, _sender, sendResponse);
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

  if (msg.type === "getScraperSummary") {
    recoverExpiredBatchPauseIfNeeded().then(function () {
      return buildScraperSummary();
    }).then(function (summary) {
      sendResponse(Object.assign({ ok: true }, summary));
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "openMainPage") {
    openWorkbenchPage(msg, _sender, sendResponse);
    return true;
  }

  if (msg.type === "clearAll") {
    recordActionDiagnosticTrace("clearAll", msg, _sender);
    __detailBatchRunToken++;
    DetailBatch.reset();
    Promise.resolve()
      .then(function () {
        return Promise.all([
          PagerDB.clear().catch(function () {}),
          DetailDB.clear().catch(function () {}),
        ]);
      })
      .then(function () {
        chrome.storage.local.set({
          captured: [],
          contacts: [],
          detailImportedContacts: [],
          details: [],
          detailBatchState: null,
          detailBatchLogs: [],
          detailBatchRunToken: __detailBatchRunToken,
          detailBatchTabId: null,
          domScrapeResult: null,
        }, function () {
          resetWorkbenchStateAndPagerLogs().then(function () {
            sendResponse({ ok: true });
          });
        });
      });
    return true;
  }

  // 导出完整 JSON 文件：合并 IndexedDB 分页联系人和 chrome.storage 捕获详情。
  if (msg.type === "exportFullJson") {
    recordActionDiagnosticTrace("exportFullJson", msg, _sender);
    buildFullExportData().then(function (data) {
      if (msg.saveAs === false) {
        recordExportResult("full", null).then(function () {
          sendResponse({ ok: true, data: data });
        });
        return;
      }
      downloadJsonData(data, msg.filename || "maimai-export.json", msg.saveAs, function (result) {
        if (result && result.downloadId) {
          recordExportResult("full", result.downloadId).then(function () {
            sendResponse(result);
          });
          return;
        }
        sendResponse(result);
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "getFullExportData") {
    recordActionDiagnosticTrace("getFullExportData", msg, _sender);
    buildFullExportData().then(function (data) {
      sendResponse({ ok: true, data: data });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "preflightTrace") {
    buildDiagnosticTrace("preflightTrace", msg, _sender).then(function (trace) {
      return recordDiagnosticTrace(trace);
    }).then(function (trace) {
      sendResponse({ ok: true, trace: trace });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "probeOnly") {
    buildDiagnosticTrace("probeOnly", msg, _sender).then(function (trace) {
      return recordDiagnosticTrace(trace);
    }).then(function (trace) {
      sendResponse({ ok: true, trace: trace });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "getDiagnosticTraces") {
    chrome.storage.local.get({ diagnosticTraces: [] }, function (r) {
      sendResponse({ ok: true, traces: r.diagnosticTraces || [] });
    });
    return true;
  }

  if (msg.type === "clearDiagnosticTraces") {
    clearDiagnosticTraceStorage().then(function () {
      sendResponse({ ok: true });
    });
    return true;
  }

  // 导出被动拦截 JSON 文件：只读取 chrome.storage.local 中的请求、联系人和详情池。
  if (msg.type === "exportCaptureJson" || msg.type === "exportJson") {
    chrome.storage.local.get({ captured: [], contacts: [], details: [] }, function (r) {
      var data = {
        exportTime: new Date().toISOString(),
        metadata: {
          export_type: "capture",
          source_pool: "passive_interception",
        },
        contacts: r.contacts || [],
        totalContacts: (r.contacts || []).length,
        details: r.details || [],
        totalDetails: (r.details || []).length,
        requests: r.captured || [],
      };
      var jsonStr = JSON.stringify(data, null, 2);
      var url = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
      chrome.downloads.download({
        url: url,
        filename: msg.filename || "maimai-export.json",
        saveAs: true,
      }, function (downloadId) {
        recordExportResult("capture", downloadId).then(function () {
          sendResponse({ downloadId: downloadId });
        });
      });
    });
    return true;
  }

  // ---- Batch Detail 消息处理 ----

  if (msg.type === "importDetailContacts") {
    recordActionDiagnosticTrace("importDetailContacts", msg, _sender);
    var payload = msg.contacts || msg.payload || [];
    var contactsToImport = normalizeImportContacts(payload);
    if (contactsToImport.length === 0) {
      sendResponse({ ok: false, error: "联系人 JSON 格式不支持" });
      return false;
    }
    __detailBatchRunToken++;
    var importResetState = DetailBatch.reset();
    var importedCount = DetailBatch.importContacts(contactsToImport);
    DetailDB.clear().then(function () {
      chrome.storage.local.set({
        contacts: contactsToImport,
        detailImportedContacts: contactsToImport,
        detailBatchState: importResetState,
        detailBatchLogs: [],
        details: [],
        detailBatchRunToken: __detailBatchRunToken,
        detailBatchTabId: null,
      }, function () {
        appendDetailBatchLog("info", "已导入 " + importedCount + " 条详情联系人", {
          imported: importedCount,
        }, __detailBatchRunToken).then(function () {
          sendResponse({ ok: true, imported: importedCount });
        });
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "resetDetailBatch") {
    __detailBatchRunToken++;
    var resetState = DetailBatch.reset();
    DetailDB.clear().then(function () {
      chrome.storage.local.set({
        contacts: [],
        detailImportedContacts: [],
        detailBatchState: null,
        detailBatchLogs: [],
        details: [],
        detailBatchRunToken: __detailBatchRunToken,
        detailBatchTabId: null,
      }, function () {
        appendDetailBatchLog("info", "批量详情已重置", null, __detailBatchRunToken).then(function () {
          sendResponse({ ok: true, state: resetState });
        });
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "startDetailBatch") {
    recordActionDiagnosticTrace("startDetailBatch", msg, _sender);
    if (__detailBatchRunning || __detailBatchStarting) {
      sendResponse({ ok: false, error: "批量详情正在运行，请先终止当前任务" });
      return true;
    }
    __detailBatchStarting = true;
    var runToken = __detailBatchRunToken;
    Promise.all([
      activeMaimaiTab(),
      detailBatchContacts(),
      storageContactsAndState(),
    ]).then(function (parts) {
      if (runToken !== __detailBatchRunToken) {
        sendResponse({ ok: false, error: "批量详情启动已被新任务取代" });
        return;
      }
      var stored = parts[2] || {};
      var currentRunToken = stored.detailBatchRunToken || runToken;
      var storedState = detailBatchStateForToken(stored.detailBatchState, currentRunToken);
      if (isActiveDetailBatchState(storedState)) {
        sendResponse({ ok: false, error: "批量详情正在运行，请先终止当前任务" });
        return;
      }
      __detailBatchRunToken++;
      runToken = __detailBatchRunToken;
      var tab = parts[0];
      var contacts = parts[1] || [];
      var built = DetailBatch.createJobs(contacts);
      var jobs = built.jobs;

      return saveDetailBatchTabId(tab.id).then(function () {
        return DetailDB.clear();
      }).then(function () {
        if (runToken !== __detailBatchRunToken) return null;
        return DetailDB.putJobs(jobs.map(function (job) {
          return tagDetailBatchRecord(job, runToken);
        }));
      }).then(function () {
        if (runToken !== __detailBatchRunToken) return null;
        return appendDetailBatchLog("info", "批量详情启动: " + jobs.length + " 个 jobs", {
          jobs: jobs.length,
          duplicateContacts: built.duplicates,
        }, runToken);
      }).then(function () {
        if (runToken !== __detailBatchRunToken) {
          sendResponse({ ok: false, error: "批量详情启动已被新任务取代" });
          return;
        }
        runDetailBatchJobs(tab, jobs, {
          mode: msg.mode || "safe",
          dailyLimit: msg.dailyLimit,
          duplicateContacts: built.duplicates,
        }, runToken);
        sendResponse({ ok: true, totalJobs: jobs.length, duplicateContacts: built.duplicates });
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    }).finally(function () {
      __detailBatchStarting = false;
    });
    return true;
  }

  if (msg.type === "pauseDetailBatch") {
    var pausedState = DetailBatch.pause();
    saveDetailBatchState(pausedState, __detailBatchRunToken).then(function () {
      emitDetailBatchEvent(Object.assign({ type: "detail_batch_paused", reason: "user_pause" }, pausedState), __detailBatchRunToken);
      sendResponse({ ok: true, state: pausedState });
    });
    return true;
  }

  if (msg.type === "resumeDetailBatch") {
    var resumedState = DetailBatch.resume();
    saveDetailBatchState(resumedState, __detailBatchRunToken).then(function () {
      emitDetailBatchEvent(Object.assign({ type: "detail_batch_progress", reason: "user_resume" }, resumedState), __detailBatchRunToken);
      sendResponse({ ok: true, state: resumedState });
    });
    return true;
  }

  if (msg.type === "stopDetailBatch") {
    var stoppedState = DetailBatch.stop();
    saveDetailBatchState(stoppedState, __detailBatchRunToken).then(function () {
      emitDetailBatchEvent(Object.assign({ type: "detail_batch_stopped" }, stoppedState), __detailBatchRunToken);
      sendResponse({ ok: true, state: stoppedState });
    });
    return true;
  }

  if (msg.type === "getDetailBatchStatus") {
    recordActionDiagnosticTrace("getDetailBatchStatus", msg, _sender);
    recoverExpiredBatchPauseIfNeeded().then(function () {
      return Promise.all([
      DetailDB.getAllJobs().catch(function () { return []; }),
      DetailDB.getAllDetails().catch(function () { return []; }),
      storageContactsAndState(),
      ]);
    }).then(function (parts) {
      var jobs = parts[0] || [];
      var details = parts[1] || [];
      var stored = parts[2];
      var currentRunToken = stored.detailBatchRunToken || __detailBatchRunToken;
      jobs = filterDetailBatchJobs(jobs, currentRunToken);
      details = filterDetailBatchRecords(details, currentRunToken);
      var counts = { jobs: jobs.length, details: details.length };
      var logs = filterDetailBatchRecords(stored.detailBatchLogs || [], currentRunToken);
      var state = detailBatchStateForToken(stored.detailBatchState, currentRunToken) || DetailBatch.getState();
      sendResponse({
        ok: true,
        state: state,
        counts: counts,
        contacts: ((stored.detailImportedContacts || []).length || (stored.contacts || []).length),
        logs: logs,
      });
    });
    return true;
  }

  // ---- AutoPager 消息处理 ----

  if (msg.type === "startPager") {
    var tabId = null;
    var responded = false;
    var existingContactCount = 0;

    function safeRespond(data) {
      if (!responded) { responded = true; sendResponse(data); }
    }

    if (__pagerStarting || (__activePager && __activePager.running)) {
      safeRespond({ ok: false, error: "人选列表采集正在运行，请先停止当前任务" });
      return true;
    }
    __pagerStarting = true;

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0]) { __pagerStarting = false; safeRespond({ ok: false, error: "无活跃标签页" }); return; }
      tabId = tabs[0].id;

      chrome.tabs.sendMessage(tabId, { type: "getFullTemplate" }, function (tplResp) {
        if (chrome.runtime.lastError || !tplResp || !tplResp.template) {
          __pagerStarting = false;
          safeRespond({ ok: false, error: "未捕获搜索模板 — 请先手动搜索一次" });
          return;
        }

        var template = tplResp.template;
        var pageMeta = template.pageMeta || { total: 0, pagesize: 30 };

        PagerDB.clear().then(function () {
          return new Promise(function (resolve) {
            chrome.storage.local.get({ contacts: [] }, function (r) {
              resolve(r.contacts || []);
            });
          });
        }).then(function (existingContacts) {
          existingContactCount = existingContacts.length;
          return PagerDB.append(existingContacts);
        }).then(function () {
          function sendPageRequest(page) {
            return new Promise(function (resolve, reject) {
              chrome.tabs.sendMessage(tabId, { type: "pagerFetch", page: page }, function (resp) {
                if (chrome.runtime.lastError) {
                  reject(new Error(chrome.runtime.lastError.message));
                  return;
                }
                resolve(resp || { httpStatus: 0, error: "无响应" });
              });
            });
          }

          var pagerState = AutoPager.create(template, pageMeta, sendPageRequest);

          __activePager = pagerState;
          __pagerTabId = tabId;

          saveWorkbenchStatePatch({
            active_maimai_tab_id: tabId,
            pager: {
              status: "running",
              mode: msg.mode || "all",
              max_pages: msg.maxPages || 3,
              current_page: 1,
              total_pages: pagerState.totalPages || 0,
              total_from_api: pagerState.totalFromApi || 0,
              total_contacts: existingContactCount,
              started_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
              finished_at: null,
              last_error: null,
            },
          });
          clearPagerLogs().then(function () {
            return appendPagerLog("info", "开始人选列表逐页采集，模式：" + ((msg.mode || "all") === "all" ? "全部页面" : "前 " + (msg.maxPages || 3) + " 页"), {
              mode: msg.mode || "all",
              maxPages: msg.maxPages || 3,
            });
          });

          AutoPager.run(pagerState, msg.mode, msg.maxPages, function (event) {
            updateWorkbenchPagerStateFromEvent(event, msg.mode || "all", msg.maxPages || 3).then(function () {
              chrome.runtime.sendMessage(event).catch(function () {});
            });
          });

          safeRespond({
            ok: true,
            totalPages: pagerState.totalPages,
            pageMeta: pageMeta,
            headerNames: template.headerNames || [],
          });
        }).catch(function (err) {
          safeRespond({ ok: false, error: "初始化失败: " + err.message });
        }).finally(function () {
          __pagerStarting = false;
        });
      });
    });
    return true;
  }

  if (msg.type === "stopPager") {
    if (__activePager) {
      AutoPager.stop(__activePager);
      saveWorkbenchStatePatch({
        pager: {
          status: "stopping",
          updated_at: new Date().toISOString(),
        },
      });
      appendPagerLog("info", "已发送终止逐页采集请求", null);
      sendResponse({ ok: true });
    } else {
      sendResponse({ ok: false, error: "无正在运行的抓取" });
    }
    return false;
  }

  if (msg.type === "getPagerStatus") {
    var pager = __activePager;
    sendResponse(pager ? {
      running: pager.running,
      currentPage: pager.currentPage,
      totalPages: pager.totalPages,
      totalFromApi: pager.totalFromApi,
    } : { running: false });
    return false;
  }

  if (msg.type === "exportPagerJson") {
    PagerDB.getCount().then(function (count) {
      if (count === 0) {
        sendResponse({ empty: true });
        return;
      }
      return PagerDB.getAll().then(function (contacts) {
        var pager = __activePager || {};
        var data = {
          exportTime: new Date().toISOString(),
          metadata: {
            total_pages: pager.totalPages || 0,
            captured_pages: pager.currentPage || 0,
            total_count: pager.totalFromApi || 0,
            search_params: {
              url: pager.template ? pager.template.url : "",
              method: pager.template ? pager.template.method : "",
              headerNames: pager.template ? (pager.template.headerNames || []) : [],
            },
          },
          contacts: contacts,
          totalContacts: count,
        };
        var jsonStr = JSON.stringify(data, null, 2);
        var url = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
        chrome.downloads.download({
          url: url,
          filename: msg.filename || "maimai-pager-export.json",
          saveAs: true,
        }, function (downloadId) {
          recordExportResult("pager", downloadId).then(function () {
            sendResponse({ downloadId: downloadId });
          });
        });
      });
    }).catch(function (err) {
      sendResponse({ empty: true });
    });
    return true;
  }
});
