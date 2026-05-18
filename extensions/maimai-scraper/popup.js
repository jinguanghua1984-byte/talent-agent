(function () {
  "use strict";

  // ---- DOM 引用 ----
  var reqCountEl = document.getElementById("req-count");
  var contactCountEl = document.getElementById("contact-count");
  var detailCountEl = document.getElementById("detail-count");
  var capturePreview = document.getElementById("capture-preview");
  var captureLogList = document.getElementById("capture-log-list");
  var statusBadge = document.getElementById("status-badge");

  // ---- Tab 切换 ----
  var tabs = document.querySelectorAll(".tab");
  var tabContents = document.querySelectorAll(".tab-content");

  tabs.forEach(function (tab) {
    tab.addEventListener("click", function () {
      tabs.forEach(function (t) { t.classList.remove("active"); });
      tabContents.forEach(function (tc) { tc.classList.remove("active"); });
      tab.classList.add("active");
      document.getElementById("tab-" + tab.dataset.tab).classList.add("active");
    });
  });

  // ---- 刷新统计数据 ----
  function isDetailBadgeActive() {
    return [
      "详情执行中",
      "详情暂停",
      "详情错误",
      "批间休息",
      "批量详情已重置",
    ].indexOf(statusBadge.textContent) !== -1;
  }

  function setCaptureBadge(text) {
    if (!isDetailBadgeActive()) {
      statusBadge.textContent = text;
    }
  }

  function requestKind(req) {
    var url = req && req.url ? String(req.url) : "";
    return (url.indexOf("/api/pc/u/") !== -1 ||
      url.indexOf("/api/pc/profile/") !== -1 ||
      url.indexOf("/api/profile/") !== -1 ||
      url.indexOf("/api/user/") !== -1)
      ? "详情"
      : "请求";
  }

  function renderCaptureOverview(data) {
    var requests = data.requests || data.captured || [];
    var contacts = data.contacts || [];
    var details = data.details || [];
    var totalContacts = data.totalContacts !== undefined ? data.totalContacts : contacts.length;
    var totalDetails = data.totalDetails !== undefined ? data.totalDetails : details.length;

    reqCountEl.textContent = data.totalRequests !== undefined ? data.totalRequests : requests.length;
    contactCountEl.textContent = totalContacts;
    detailCountEl.textContent = totalDetails;
    setCaptureBadge(totalDetails > 0
      ? totalDetails + " 详情"
      : totalContacts > 0
      ? totalContacts + " 人选"
      : "等待捕获");

    if (requests.length > 0) {
      var recent = requests.slice(-5).map(function (req) {
        var url = req && req.url ? String(req.url).split("?")[0] : "";
        return "[" + requestKind(req) + "] " + (req.method || "?") + " " + url + " → " + (req.status || "?");
      });
      capturePreview.textContent = recent.join("\n") +
        "\n\n--- 共 " + requests.length + " 条请求，" + totalContacts + " 条人选，" + totalDetails + " 条详情 ---";
    } else {
      capturePreview.textContent = "等待数据...\n\n1. 打开脉脉搜索页面\n2. 手动执行搜索或翻页\n3. 数据自动捕获";
    }
  }

  function refreshStats() {
    chrome.runtime.sendMessage({ type: "getScraperSummary" }, function (summary) {
      if (!chrome.runtime.lastError && summary && summary.ok) {
        renderCaptureOverview(summary);
        return;
      }
      chrome.storage.local.get({ captured: [], contacts: [], details: [] }, renderCaptureOverview);
    });
  }

  // ---- 被动拦截按钮 ----
  document.getElementById("btn-refresh").addEventListener("click", refreshStats);

  document.getElementById("btn-clear").addEventListener("click", function () {
    if (confirm("确认清除所有捕获数据？")) {
      chrome.runtime.sendMessage({ type: "clearAll" }, function () {
        refreshStats();
      });
    }
  });

  document.getElementById("btn-export-capture").addEventListener("click", function () {
    var filename = "maimai-passive-capture-" + new Date().toISOString().slice(0, 10) + ".json";

    chrome.runtime.sendMessage({ type: "exportCaptureJson", filename: filename }, function (r) {
      if (r && r.downloadId) {
        statusBadge.textContent = "被动数据已导出";
      } else {
        statusBadge.textContent = "导出失败";
      }
    });
  });

  // ---- 分页抓取控制 ----
  var pagerModeEl = document.getElementById("pager-mode");
  var pagerMaxPagesGroup = document.getElementById("pager-pages-group");
  var pagerMaxPagesEl = document.getElementById("pager-max-pages");
  var pagerInfoEl = document.getElementById("pager-info");
  var pagerTemplateInfoEl = document.getElementById("pager-template-info");
  var pagerMetaInfoEl = document.getElementById("pager-meta-info");
  var btnStartPager = document.getElementById("btn-start-pager");
  var btnStopPager = document.getElementById("btn-stop-pager");
  var btnExportPager = document.getElementById("btn-export-pager");
  var pagerProgressEl = document.getElementById("pager-progress");
  var pagerProgressFill = document.getElementById("pager-progress-fill");
  var pagerProgressText = document.getElementById("pager-progress-text");
  var pagerExecutionLogs = [];

  function escapeHtml(text) {
    return String(text).replace(/[<>&]/g, function (ch) {
      return {
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
      }[ch];
    });
  }

  function renderPagerLogs() {
    if (!captureLogList) return;
    if (pagerExecutionLogs.length === 0) {
      captureLogList.innerHTML = '<div class="capture-log-empty">开始逐页采集后显示实时请求进度</div>';
      return;
    }
    captureLogList.innerHTML = pagerExecutionLogs.slice(-60).reverse().map(function (entry) {
      return '<div class="capture-log-item">' + escapeHtml(entry) + '</div>';
    }).join("");
  }

  function appendPagerLog(message) {
    var ts = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    pagerExecutionLogs.push("[" + ts + "] " + message);
    renderPagerLogs();
  }

  pagerModeEl.addEventListener("change", function () {
    pagerMaxPagesGroup.style.display = pagerModeEl.value === "custom" ? "block" : "none";
  });

  function refreshPagerInfo() {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0] || tabs[0].url.indexOf("maimai.cn") === -1) {
        pagerTemplateInfoEl.textContent = "请在脉脉页面上使用";
        pagerTemplateInfoEl.className = "hint warn";
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, { type: "getTemplateStatus" }, function (resp) {
        if (chrome.runtime.lastError || !resp) {
          pagerTemplateInfoEl.textContent = "无法获取模板状态";
          pagerTemplateInfoEl.className = "hint warn";
          return;
        }
        if (resp.hasTemplate) {
          var total = resp.pageMeta ? resp.pageMeta.total : "?";
          var pagesize = resp.pageMeta ? resp.pageMeta.pagesize : "?";
          var totalPages = (resp.pageMeta && pagesize > 0) ? Math.ceil(total / pagesize) : "?";
          var headerList = resp.headerNames || (resp.template && resp.template.headerNames) || [];
          var headerText = headerList.length > 0 ? "；请求头: " + headerList.join(", ") : "；请求头: 未记录";
          pagerTemplateInfoEl.textContent = "模板: " + resp.method + " " + resp.url.split("?")[0];
          pagerTemplateInfoEl.className = "hint success";
          pagerMetaInfoEl.textContent = "共 " + total + " 条，每页 " + pagesize + " 条，约 " + totalPages + " 页" + headerText;
          pagerInfoEl.style.display = "flex";
        } else {
          pagerTemplateInfoEl.textContent = "未捕获模板 — 请先手动搜索一次";
          pagerTemplateInfoEl.className = "hint warn";
          pagerMetaInfoEl.textContent = "";
          pagerInfoEl.style.display = "flex";
        }
      });
    });
  }

  btnStartPager.addEventListener("click", function () {
    var mode = pagerModeEl.value;
    var maxPages = parseInt(pagerMaxPagesEl.value) || 3;
    btnStartPager.style.display = "none";
    btnStopPager.style.display = "inline-block";
    pagerProgressEl.style.display = "block";
    pagerProgressText.textContent = "启动中...";
    pagerProgressFill.style.width = "0%";
    pagerExecutionLogs = [];
    appendPagerLog("开始人选列表逐页采集，模式：" + (mode === "all" ? "全部页面" : "前 " + maxPages + " 页"));

    chrome.runtime.sendMessage({ type: "startPager", mode: mode, maxPages: maxPages }, function (resp) {
      if (!resp || !resp.ok) {
        pagerProgressText.textContent = "错误: " + (resp ? resp.error : "无响应");
        btnStartPager.style.display = "inline-block";
        btnStopPager.style.display = "none";
        appendPagerLog("启动失败：" + (resp ? resp.error : "无响应"));
      }
    });
  });

  btnStopPager.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "stopPager" }, function () {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressText.textContent = "正在停止...";
      appendPagerLog("已发送终止逐页采集请求");
    });
  });

  btnExportPager.addEventListener("click", function () {
    var filename = "maimai-pager-contacts-" + new Date().toISOString().slice(0, 10) + ".json";
    chrome.runtime.sendMessage({ type: "exportPagerJson", filename: filename }, function (r) {
      if (r && r.downloadId) {
        statusBadge.textContent = "列表数据已导出";
      } else if (r && r.empty) {
        statusBadge.textContent = "暂无列表数据";
        appendPagerLog("导出失败：人选列表数据池为空");
      } else {
        statusBadge.textContent = "导出失败";
      }
    });
  });

  chrome.runtime.onMessage.addListener(function (msg) {
    if (msg.type === "pager_progress") {
      var pct = Math.round((msg.currentPage / msg.totalPages) * 100);
      pagerProgressFill.style.width = pct + "%";
      pagerProgressText.textContent = "第 " + msg.currentPage + "/" + msg.totalPages + " 页 (" + msg.totalContacts + " 条)";
      appendPagerLog("第 " + msg.currentPage + "/" + msg.totalPages + " 页请求完成，新增 " + (msg.contactsInPage || 0) + " 条，累计 " + msg.totalContacts + " 条");
      refreshStats();
    }
    if (msg.type === "pager_complete") {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressFill.style.width = "100%";
      pagerProgressText.textContent = "完成！共 " + msg.totalContacts + " 条";
      statusBadge.textContent = msg.totalContacts + " 条已抓取";
      appendPagerLog("逐页采集完成，共保存 " + msg.totalContacts + " 条人选");
      refreshStats();
    }
    if (msg.type === "pager_cancelled") {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressText.textContent = "已停止 — " + msg.totalContacts + " 条已保存";
      appendPagerLog("逐页采集已停止，已保存 " + msg.totalContacts + " 条人选");
      refreshStats();
    }
    if (msg.type === "pager_error") {
      pagerProgressText.textContent = "错误 (第" + msg.page + "页): " + msg.reason;
      appendPagerLog("第 " + msg.page + " 页请求失败：" + msg.reason);
    }
    if (msg.type === "pager_paused") {
      pagerProgressText.textContent = "暂停 (第" + msg.page + "页): " + msg.reason;
      appendPagerLog("第 " + msg.page + " 页请求暂停：" + msg.reason);
    }
    if (msg.type && msg.type.indexOf("detail_batch_") === 0) {
      renderDetailBatchState(msg);
      refreshDetailBatchStatus();
    }
  });

  refreshPagerInfo();
  setInterval(refreshPagerInfo, 5000);

  // ---- 批量详情控制 ----
  var detailJobsCountEl = document.getElementById("detail-jobs-count");
  var detailDoneCountEl = document.getElementById("detail-done-count");
  var detailFailedCountEl = document.getElementById("detail-failed-count");
  var detailSkippedCountEl = document.getElementById("detail-skipped-count");
  var detailImportFileEl = document.getElementById("detail-import-file");
  var btnStartDetail = document.getElementById("btn-start-detail-batch");
  var btnStopDetail = document.getElementById("btn-stop-detail-batch");
  var btnExportDetail = document.getElementById("btn-export-detail-batch");
  var detailProgressFill = document.getElementById("detail-progress-fill");
  var detailProgressText = document.getElementById("detail-progress-text");
  var detailBatchLog = document.getElementById("detail-batch-log");
  var detailLogList = document.getElementById("detail-log-list");

  function detailCountsFromState(state) {
    return state && state.counts ? state.counts : {
      queued: 0,
      running: 0,
      done: 0,
      failed: 0,
      skipped: 0,
    };
  }

  function formatDetailDelayMs(ms) {
    var value = Math.max(0, Number(ms) || 0);
    var totalSeconds = Math.ceil(value / 1000);
    var minutes = Math.floor(totalSeconds / 60);
    var seconds = totalSeconds % 60;
    if (minutes > 0 && seconds > 0) return minutes + " 分 " + seconds + " 秒";
    if (minutes > 0) return minutes + " 分钟";
    return seconds + " 秒";
  }

  function remainingDetailPauseMs(state, input) {
    var until = state && state.batch_pause_until;
    if (until) {
      var parsed = Date.parse(until);
      if (!Number.isNaN(parsed)) {
        return Math.max(0, parsed - Date.now());
      }
    }
    return (input && input.delayMs) || (state && state.batch_pause_delay_ms) || 0;
  }

  function hasBatchPauseNotice(state, input) {
    return Boolean(
      (input && input.reason === "batch_pause") ||
      (state && state.batch_pause_until)
    );
  }

  function detailStatusLabel(status) {
    switch (status) {
      case "running":
        return "采集中";
      case "paused":
        return "已暂停";
      case "stopped":
        return "已终止";
      case "completed":
        return "已完成";
      case "failed":
        return "执行失败";
      case "idle":
      default:
        return "等待启动";
    }
  }

  function renderDetailBatchState(input) {
    var rawInput = input || {};
    var state = rawInput.state ? rawInput.state : rawInput;
    var counts = detailCountsFromState(state);
    // 兼容旧事件里的 input.total_jobs 形态，实际读取通过 rawInput 防止空输入报错。
    var inputTotalJobs = rawInput.total_jobs;
    var total = state.total_jobs || inputTotalJobs || rawInput.totalJobs || 0;
    var completed = (counts.done || 0) + (counts.failed || 0) + (counts.skipped || 0);
    var pct = total > 0 ? Math.round((completed / total) * 100) : 0;

    detailJobsCountEl.textContent = total;
    detailDoneCountEl.textContent = counts.done || 0;
    detailFailedCountEl.textContent = counts.failed || 0;
    detailSkippedCountEl.textContent = counts.skipped || 0;
    detailProgressFill.style.width = pct + "%";
    detailProgressText.textContent = "状态：" + detailStatusLabel(state.status || "idle") +
      "，已处理 " + completed + "/" + total;

    if (hasBatchPauseNotice(state, rawInput)) {
      var pauseCompleted = Math.max(state.batch_pause_completed || 0, completed);
      var pauseTotal = total > 0 ? "/" + total : "";
      detailProgressText.textContent = "状态：批间休息中，已处理 " + pauseCompleted + pauseTotal;
      detailBatchLog.textContent = "批间休息中：已完成 " + pauseCompleted + pauseTotal + "，约 " + formatDetailDelayMs(remainingDetailPauseMs(state, rawInput)) + " 后继续";
      statusBadge.textContent = "批间休息";
    } else if (state.circuit_breaker && state.circuit_breaker.tripped) {
      detailBatchLog.textContent = "熔断暂停：" + state.circuit_breaker.reason;
      statusBadge.textContent = "详情暂停";
    } else if (rawInput.reason) {
      detailBatchLog.textContent = "状态说明：" + rawInput.reason;
    } else if (rawInput.error) {
      detailBatchLog.textContent = "执行出错：" + rawInput.error;
      statusBadge.textContent = "详情错误";
    }
  }

  function escapeDetailLogText(text) {
    return String(text).replace(/[<>&]/g, function (ch) {
      return {
        "<": "&lt;",
        ">": "&gt;",
        "&": "&amp;",
      }[ch];
    });
  }

  function formatDetailLog(log) {
    if (typeof log === "string") return log;
    if (!log) return "";
    if (log.message) {
      var prefix = log.time || log.ts || log.at || "";
      return (prefix ? "[" + prefix + "] " : "") + log.message;
    }
    return JSON.stringify(log);
  }

  function renderDetailBatchLogs(logs) {
    var recentLogs = Array.isArray(logs) ? logs.slice(-50).reverse() : [];
    if (recentLogs.length === 0) {
      detailLogList.innerHTML = '<div class="detail-log-empty">暂无执行日志</div>';
      return;
    }
    detailLogList.innerHTML = recentLogs.map(function (log) {
      return '<div class="detail-log-item">' + escapeDetailLogText(formatDetailLog(log)) + '</div>';
    }).join("");
  }

  function refreshDetailBatchStatus() {
    chrome.runtime.sendMessage({ type: "getDetailBatchStatus" }, function (resp) {
      if (chrome.runtime.lastError || !resp || !resp.ok) {
        detailProgressText.textContent = "无法获取状态";
        return;
      }
      renderDetailBatchState(resp.state || {});
      renderDetailBatchLogs(resp.logs || []);
      if (resp.contacts !== undefined && !hasBatchPauseNotice(resp.state || {}, null)) {
        detailBatchLog.textContent = "人选来源：" + resp.contacts + " 条。默认低速顺序采集，导出后再做本地校验。";
      }
      chrome.runtime.sendMessage({ type: "getScraperSummary" }, function (summary) {
        if (summary && summary.detail) {
          var totalJobs = summary.detail.totalJobs || summary.detail.jobs || 0;
          var summaryState = summary.detail.state || {};
          var detailStatus = summary.detail.state && summary.detail.state.status;
          var isRunning = summary.detail.running;
          if (isRunning === undefined) {
            isRunning = detailStatus === "running";
          }
          if (totalJobs > 0) {
            statusBadge.textContent = summaryState.batch_pause_until
              ? "批间休息"
              : detailStatus === "paused"
              ? "详情暂停"
              : isRunning
              ? "详情执行中"
              : summary.totalDetails + " 详情";
          }
        }
      });
    });
  }

  function exportFullJsonForDetail() {
    var filename = "maimai-detail-capture-" + new Date().toISOString().slice(0, 10) + ".json";
    chrome.runtime.sendMessage({ type: "exportFullJson", filename: filename }, function (r) {
      statusBadge.textContent = r && r.downloadId ? "已导出" : "导出失败";
    });
  }

  function startDetailBatchFromPopup() {
    detailProgressText.textContent = "正在启动人选详情采集...";
    chrome.runtime.sendMessage({ type: "startDetailBatch" }, function (resp) {
      if (!resp || !resp.ok) {
        detailProgressText.textContent = "启动失败：" + (resp ? resp.error : "无响应");
        return;
      }
      detailBatchLog.textContent = "人选详情采集已启动，任务数：" + resp.totalJobs;
      refreshDetailBatchStatus();
    });
  }

  detailImportFileEl.addEventListener("change", function () {
    var file = detailImportFileEl.files && detailImportFileEl.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var parsed = JSON.parse(reader.result);
        chrome.runtime.sendMessage({ type: "importDetailContacts", contacts: parsed }, function (resp) {
          if (resp && resp.ok) {
            detailBatchLog.textContent = "已导入 " + resp.imported + " 条人选";
            detailProgressText.textContent = "已导入人选列表，等待开始采集";
            refreshDetailBatchStatus();
          } else {
            detailBatchLog.textContent = "导入失败：" + (resp ? resp.error : "无响应");
          }
        });
      } catch (err) {
        detailBatchLog.textContent = "JSON 解析失败：" + err.message;
      }
    };
    reader.readAsText(file, "utf-8");
  });

  btnStartDetail.addEventListener("click", function () {
    startDetailBatchFromPopup();
  });

  btnStopDetail.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "stopDetailBatch" }, function (resp) {
      if (resp && resp.state) renderDetailBatchState(resp.state);
      detailBatchLog.textContent = "已发送终止人选详情采集请求";
    });
  });

  btnExportDetail.addEventListener("click", exportFullJsonForDetail);

  // ---- 初始化 ----
  refreshStats();
  refreshDetailBatchStatus();

  // 自动刷新（列表采集和详情状态）
  setInterval(refreshStats, 2000);
  setInterval(refreshDetailBatchStatus, 5000);
})();
