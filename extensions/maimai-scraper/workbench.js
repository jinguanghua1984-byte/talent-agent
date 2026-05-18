(function () {
  "use strict";

  var state = null;
  var summary = null;
  var pagerLogs = [];
  var detailLogs = [];
  var snapshotRefreshTimer = null;
  var DEFAULT_DETAIL_LOG = "默认低速顺序采集；遇到验证、权限或限流异常会暂停。";

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

  function setStatusMessage(message) {
    var target = $("status-line");
    if (!target) return;
    target.textContent = message || "";
    target.hidden = !message;
  }

  function setPagerTemplateError(message) {
    var target = $("pager-template-info");
    if (!target) return;
    target.textContent = message || "";
    target.hidden = !message;
  }

  function isTemplateCaptureError(message) {
    message = message || "";
    return message.indexOf("未捕获搜索模板") !== -1
      || message.indexOf("模板") !== -1
      || message.indexOf("捕获") !== -1;
  }

  function showActionResult(resp, fallbackMessage) {
    var hasDownloadId = resp && typeof resp.downloadId !== "undefined";
    if (!resp || !(resp.ok || hasDownloadId || resp.empty === true)) {
      var message = resp && resp.error ? resp.error : fallbackMessage;
      setStatusMessage(message);
      if (isTemplateCaptureError(message)) {
        setPagerTemplateError(message);
      }
      return false;
    }
    setStatusMessage("");
    return true;
  }

  function setButtonBusy(button, busy) {
    if (!button) return;
    if (busy) {
      button.dataset.defaultText = button.dataset.defaultText || button.textContent;
      button.textContent = "处理中...";
      button.disabled = true;
      return;
    }
    if (button.dataset.defaultText) {
      button.textContent = button.dataset.defaultText;
    }
    button.disabled = false;
    updateControlStates();
  }

  function scheduleSnapshotRefresh() {
    if (snapshotRefreshTimer) return;
    snapshotRefreshTimer = setTimeout(function () {
      snapshotRefreshTimer = null;
      loadSnapshot();
    }, 150);
  }

  function updatePagerPagesVisibility() {
    $("pager-pages-group").hidden = $("pager-mode").value !== "custom";
  }

  function isPagerActiveStatus(status) {
    return ["running", "paused", "stopping"].indexOf(status || "") !== -1;
  }

  function isDetailActiveStatus(detailState) {
    detailState = detailState || {};
    var status = detailState.status || "";
    return ["running", "paused", "stopping"].indexOf(status) !== -1 || Boolean(detailState.batch_pause_until);
  }

  function updateControlStates() {
    var pager = state && state.pager ? state.pager : {};
    var pagerActive = isPagerActiveStatus(pager.status);
    var pagerStopping = pager.status === "stopping";
    $("btn-start-pager").disabled = pagerActive;
    $("btn-stop-pager").disabled = !pagerActive || pagerStopping;
    $("pager-mode").disabled = pagerActive;
    $("pager-max-pages").disabled = pagerActive;

    var detail = state && state.detail ? state.detail : {};
    var detailState = detail.state || {};
    var detailActive = isDetailActiveStatus(detailState);
    var detailStopping = detailState.status === "stopping";
    $("btn-start-detail-batch").disabled = detailActive;
    $("btn-stop-detail-batch").disabled = !detailActive || detailStopping;
    $("detail-import-file").disabled = detailActive;
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
    if (pager.last_error && isTemplateCaptureError(pager.last_error)) {
      setPagerTemplateError(pager.last_error);
    } else if (!pager.last_error) {
      setPagerTemplateError("");
    }
    $("pager-mode").value = pager.mode || "all";
    $("pager-max-pages").value = pager.max_pages || 3;
    updatePagerPagesVisibility();
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
    } else if (detail.last_error || detailState.error) {
      $("detail-batch-log").textContent = "详情采集异常：" + (detail.last_error || detailState.error);
    } else {
      $("detail-batch-log").textContent = DEFAULT_DETAIL_LOG;
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
    updateControlStates();
  }

  function loadSnapshot() {
    return sendMessage({ type: "getWorkbenchSnapshot" }).then(function (resp) {
      if (!resp || !resp.ok) {
        setStatusMessage(resp && resp.error ? resp.error : "无法读取工作台状态");
        return;
      }
      setStatusMessage("");
      state = resp.workbenchState || {};
      summary = resp.summary || {};
      pagerLogs = resp.pagerLogs || [];
      detailLogs = resp.detailLogs || [];
      setActiveView(state.active_view || "capture");
      renderAll();
    });
  }

  function exportWith(message, filenamePrefix) {
    var filename = filenamePrefix + "-" + new Date().toISOString().slice(0, 10) + ".json";
    var payload = Object.assign({}, message, { filename: filename });
    return sendMessage(payload).then(function (resp) {
      if (!showActionResult(resp, "导出失败")) return null;
      if (resp.empty) setStatusMessage("没有可导出的数据");
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
      updatePagerPagesVisibility();
    });
    $("btn-start-pager").addEventListener("click", function () {
      var button = $("btn-start-pager");
      setButtonBusy(button, true);
      sendMessage({
        type: "startPager",
        mode: $("pager-mode").value,
        maxPages: parseInt($("pager-max-pages").value, 10) || 3,
      }).then(function (resp) {
        if (showActionResult(resp, "启动列表采集失败")) {
          setPagerTemplateError("");
          return loadSnapshot();
        }
        return null;
      }).then(function () {
        setButtonBusy(button, false);
      });
    });
    $("btn-stop-pager").addEventListener("click", function () {
      sendMessage({ type: "stopPager" }).then(function (resp) {
        if (showActionResult(resp, "停止列表采集失败")) return loadSnapshot();
        return null;
      });
    });
    $("btn-export-pager").addEventListener("click", function () {
      exportWith({ type: "exportPagerJson" }, "maimai-pager-contacts");
    });
    $("detail-import-file").addEventListener("change", function () {
      var file = $("detail-import-file").files && $("detail-import-file").files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function () {
        try {
          sendMessage({ type: "importDetailContacts", contacts: JSON.parse(reader.result) }).then(function (resp) {
            if (showActionResult(resp, "导入人选列表失败")) return loadSnapshot();
            return null;
          });
        } catch (err) {
          var message = "JSON 解析失败：" + err.message;
          $("detail-batch-log").textContent = message;
          setStatusMessage(message);
        }
      };
      reader.readAsText(file, "utf-8");
    });
    $("btn-start-detail-batch").addEventListener("click", function () {
      var button = $("btn-start-detail-batch");
      setButtonBusy(button, true);
      sendMessage({ type: "startDetailBatch" }).then(function (resp) {
        if (showActionResult(resp, "启动详情采集失败")) return loadSnapshot();
        return null;
      }).then(function () {
        setButtonBusy(button, false);
      });
    });
    $("btn-stop-detail-batch").addEventListener("click", function () {
      sendMessage({ type: "stopDetailBatch" }).then(function (resp) {
        if (showActionResult(resp, "停止详情采集失败")) return loadSnapshot();
        return null;
      });
    });
    $("btn-export-detail-batch").addEventListener("click", function () {
      exportWith({ type: "exportFullJson" }, "maimai-detail-capture");
    });
    $("btn-refresh").addEventListener("click", loadSnapshot);
    $("btn-export-capture").addEventListener("click", function () {
      exportWith({ type: "exportCaptureJson" }, "maimai-passive-capture");
    });
    $("btn-export-full").addEventListener("click", function () {
      exportWith({ type: "exportFullJson" }, "maimai-capture");
    });
    $("btn-clear-all").addEventListener("click", function () {
      if (!confirm("确认清除所有捕获数据？")) return;
      sendMessage({ type: "clearAll" }).then(function (resp) {
        if (showActionResult(resp, "清除数据失败")) {
          setPagerTemplateError("");
          return loadSnapshot();
        }
        return null;
      });
    });
    chrome.storage.onChanged.addListener(function (changes, areaName) {
      if (areaName !== "local") return;
      if (changes.workbenchState) state = changes.workbenchState.newValue || state;
      if (changes.pagerLogs) pagerLogs = changes.pagerLogs.newValue || [];
      if (changes.detailBatchLogs) detailLogs = changes.detailBatchLogs.newValue || [];
      if (
        changes.captured ||
        changes.contacts ||
        changes.details ||
        changes.detailBatchState ||
        changes.detailImportedContacts ||
        changes.detailBatchRunToken ||
        changes.detailBatchLogs
      ) {
        scheduleSnapshotRefresh();
      }
      renderAll();
    });
  }

  bindEvents();
  loadSnapshot();
})();
