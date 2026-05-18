(function () {
  "use strict";

  function $(id) {
    return document.getElementById(id);
  }

  var statusLine = $("status-line");
  var statusBadge = $("status-badge");
  var reqCountEl = $("req-count");
  var contactCountEl = $("contact-count");
  var detailCountEl = $("detail-count");
  var btnOpenWorkbench = $("btn-open-workbench");
  var btnExportFull = $("btn-export-full");
  var btnRefresh = $("btn-refresh");

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

  function numberOrLength(value, fallbackArray) {
    if (typeof value === "number") return value;
    if (Array.isArray(fallbackArray)) return fallbackArray.length;
    return 0;
  }

  function setBadge(text, mode) {
    statusBadge.textContent = text || "--";
    statusBadge.classList.toggle("error", mode === "error");
    statusBadge.classList.toggle("pending", mode === "pending");
  }

  function setStatus(message, badge, mode) {
    statusLine.textContent = message;
    if (badge) setBadge(badge, mode);
  }

  function showError(message) {
    setStatus(message || "操作失败", "错误", "error");
  }

  function summaryBadge(totals) {
    if (totals.details > 0) return totals.details + " 详情";
    if (totals.contacts > 0) return totals.contacts + " 人选";
    return "等待捕获";
  }

  function renderSummary(summary) {
    var totals = {
      requests: numberOrLength(summary.totalRequests, summary.requests),
      contacts: numberOrLength(summary.totalContacts, summary.contacts),
      details: numberOrLength(summary.totalDetails, summary.details),
    };

    reqCountEl.textContent = totals.requests;
    contactCountEl.textContent = totals.contacts;
    detailCountEl.textContent = totals.details;
    setStatus(
      "请求 " + totals.requests + " · 人选 " + totals.contacts + " · 详情 " + totals.details,
      summaryBadge(totals)
    );
  }

  function withBusy(button, label, task) {
    var originalText = button.textContent;
    button.disabled = true;
    button.textContent = label;
    return task().finally(function () {
      button.disabled = false;
      button.textContent = originalText;
    });
  }

  function refreshSummary() {
    setStatus("正在读取状态...", "读取中", "pending");
    return sendMessage({ type: "getScraperSummary" }).then(function (resp) {
      if (!resp || !resp.ok) {
        showError(resp && resp.error ? resp.error : "无法读取状态");
        return;
      }
      renderSummary(resp);
    });
  }

  function openWorkbench() {
    return withBusy(btnOpenWorkbench, "打开中...", function () {
      setStatus("正在打开工作台...", "打开中", "pending");
      return new Promise(function (resolve) {
        if (!(chrome.windows && chrome.windows.getCurrent)) {
          resolve({ ok: false, error: "side_panel_window_unavailable" });
          return;
        }
        chrome.windows.getCurrent(function (windowInfo) {
          if (chrome.runtime.lastError) {
            resolve({ ok: false, error: chrome.runtime.lastError.message });
            return;
          }
          resolve(sendMessage({ type: "openWorkbench", windowId: windowInfo && windowInfo.id }));
        });
      }).then(function (resp) {
        if (!resp || !resp.ok) {
          showError(resp && resp.error ? resp.error : "无法打开工作台");
          return;
        }
        setStatus("工作台已打开", "工作台");
      });
    });
  }

  function exportFullJson() {
    return withBusy(btnExportFull, "导出中...", function () {
      var filename = "maimai-capture-" + new Date().toISOString().slice(0, 10) + ".json";
      setStatus("正在导出完整 JSON...", "导出中", "pending");
      return sendMessage({ type: "exportFullJson", filename: filename }).then(function (resp) {
        if (!resp || !(resp.ok || typeof resp.downloadId !== "undefined")) {
          showError(resp && resp.error ? resp.error : "导出失败");
          return;
        }
        setStatus("完整 JSON 已导出", "已导出");
        refreshSummary();
      });
    });
  }

  btnOpenWorkbench.addEventListener("click", openWorkbench);
  btnExportFull.addEventListener("click", exportFullJson);
  btnRefresh.addEventListener("click", function () {
    withBusy(btnRefresh, "刷新中...", refreshSummary);
  });

  refreshSummary();
})();
