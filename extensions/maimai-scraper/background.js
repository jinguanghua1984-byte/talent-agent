importScripts("idb.js", "autopager.js", "detail_batch.js");

// background.js — Service Worker

var pendingSearchCallbacks = {};
var __activePager = null;
var __pagerTabId = null;
var __activeDetailBatch = null;
var __detailBatchTabId = null;
var __detailBatchRunToken = 0;

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
  if (typeof event.batch_pause_completed === "number" && event.batch_pause_completed > 0) {
    return event.batch_pause_completed;
  }
  var counts = event && event.counts ? event.counts : {};
  return (counts.done || 0) + (counts.failed || 0) + (counts.skipped || 0);
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
    }, function (r) {
      resolve(r);
    });
  });
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
  if (msg.type === "getScraperSummary") {
    buildScraperSummary().then(function (summary) {
      sendResponse(Object.assign({ ok: true }, summary));
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "openMainPage") {
    function openPopupFallback() {
      chrome.tabs.create({ url: chrome.runtime.getURL("popup.html") }, function (tab) {
        sendResponse({ ok: true, tabId: tab && tab.id });
      });
    }

    if (chrome.action && chrome.action.openPopup) {
      try {
        var popupResult = chrome.action.openPopup();
        if (popupResult && popupResult.then) {
          popupResult.then(function () {
            sendResponse({ ok: true, opened: "popup" });
          }).catch(function () {
            openPopupFallback();
          });
        } else {
          sendResponse({ ok: true, opened: "popup" });
        }
      } catch (err) {
        openPopupFallback();
      }
    } else {
      openPopupFallback();
    }
    return true;
  }

  if (msg.type === "clearAll") {
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
          domScrapeResult: null,
        }, function () {
          sendResponse({ ok: true });
        });
      });
    return true;
  }

  // 导出完整 JSON 文件：合并 IndexedDB 分页联系人和 chrome.storage 捕获详情。
  if (msg.type === "exportFullJson") {
    buildFullExportData().then(function (data) {
      if (msg.saveAs === false) {
        sendResponse({ ok: true, data: data });
        return;
      }
      downloadJsonData(data, msg.filename || "maimai-export.json", msg.saveAs, sendResponse);
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  if (msg.type === "getFullExportData") {
    buildFullExportData().then(function (data) {
      sendResponse({ ok: true, data: data });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }

  // 导出为 JSON 文件
  if (msg.type === "exportJson") {
    chrome.storage.local.get({ captured: [], contacts: [], details: [] }, function (r) {
      var data = {
        exportTime: new Date().toISOString(),
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
        sendResponse({ downloadId: downloadId });
      });
    });
    return true;
  }

  // ---- Batch Detail 消息处理 ----

  if (msg.type === "importDetailContacts") {
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
    __detailBatchRunToken++;
    var runToken = __detailBatchRunToken;
    Promise.all([
      activeMaimaiTab(),
      detailBatchContacts(),
    ]).then(function (parts) {
      if (runToken !== __detailBatchRunToken) {
        sendResponse({ ok: false, error: "批量详情启动已被新任务取代" });
        return;
      }
      var tab = parts[0];
      var contacts = parts[1] || [];
      var built = DetailBatch.createJobs(contacts);
      var jobs = built.jobs;
      __detailBatchTabId = tab.id;

      return DetailDB.clear().then(function () {
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
        __activeDetailBatch = DetailBatch.run(jobs, {
          mode: msg.mode || "safe",
          dailyLimit: msg.dailyLimit,
          duplicateContacts: built.duplicates,
        }, {
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
            emitDetailBatchEvent(Object.assign({ type: "detail_batch_error", error: err.message }, failedState), runToken);
          });
        });
        sendResponse({ ok: true, totalJobs: jobs.length, duplicateContacts: built.duplicates });
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
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
    Promise.all([
      DetailDB.getAllJobs().catch(function () { return []; }),
      DetailDB.getAllDetails().catch(function () { return []; }),
      storageContactsAndState(),
    ]).then(function (parts) {
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

    function safeRespond(data) {
      if (!responded) { responded = true; sendResponse(data); }
    }

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0]) { safeRespond({ ok: false, error: "无活跃标签页" }); return; }
      tabId = tabs[0].id;

      chrome.tabs.sendMessage(tabId, { type: "getFullTemplate" }, function (tplResp) {
        if (chrome.runtime.lastError || !tplResp || !tplResp.template) {
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

          AutoPager.run(pagerState, msg.mode, msg.maxPages, function (event) {
            chrome.runtime.sendMessage(event).catch(function () {});
          });

          safeRespond({
            ok: true,
            totalPages: pagerState.totalPages,
            pageMeta: pageMeta,
            headerNames: template.headerNames || [],
          });
        }).catch(function (err) {
          safeRespond({ ok: false, error: "初始化失败: " + err.message });
        });
      });
    });
    return true;
  }

  if (msg.type === "stopPager") {
    if (__activePager) {
      AutoPager.stop(__activePager);
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
          sendResponse({ downloadId: downloadId });
        });
      });
    }).catch(function (err) {
      sendResponse({ empty: true });
    });
    return true;
  }
});
