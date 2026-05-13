(function () {
  "use strict";

  // ---- DOM 引用 ----
  var reqCountEl = document.getElementById("req-count");
  var contactCountEl = document.getElementById("contact-count");
  var detailCountEl = document.getElementById("detail-count");
  var capturePreview = document.getElementById("capture-preview");
  var searchResult = document.getElementById("search-result");
  var domResult = document.getElementById("dom-result");
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

  // ---- 更新模板状态 ----
  function refreshTemplateStatus() {
    var el = document.getElementById("search-template-status");
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0] || tabs[0].url.indexOf("maimai.cn") === -1) {
        el.textContent = "请在脉脉页面上使用";
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, { type: "getTemplateStatus" }, function (resp) {
        if (chrome.runtime.lastError || !resp) {
          el.textContent = "模板状态: 无法获取（刷新页面重试）";
          return;
        }
        if (resp.hasTemplate) {
          el.textContent = "模板状态: 已捕获 (" + resp.method + " " + resp.url + ")";
          el.className = "hint success";
        } else {
          el.textContent = "模板状态: 未捕获 — 请先手动搜索一次";
          el.className = "hint warn";
        }
      });
    });
  }

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

  function refreshStats() {
    chrome.storage.local.get({ captured: [], contacts: [], details: [] }, function (r) {
      reqCountEl.textContent = r.captured.length;
      contactCountEl.textContent = r.contacts.length;
      detailCountEl.textContent = r.details.length;
      setCaptureBadge(r.details.length > 0
        ? r.details.length + " 详情"
        : r.contacts.length > 0
        ? r.contacts.length + " 联系人"
        : "等待捕获");

      if (r.captured.length > 0) {
        var summary = r.captured.slice(-5).map(function (req) {
          var kind = (req.url.indexOf("/api/pc/u/") !== -1 ||
            req.url.indexOf("/api/pc/profile/") !== -1 ||
            req.url.indexOf("/api/profile/") !== -1 ||
            req.url.indexOf("/api/user/") !== -1)
            ? "详情"
            : "请求";
          return "[" + kind + "] " + req.method + " " + req.url.split("?")[0] + " → " + (req.status || "?");
        });
        capturePreview.textContent = summary.join("\n") +
          "\n\n--- 共 " + r.captured.length + " 条请求，" + r.details.length + " 条详情 ---";
      } else {
        capturePreview.textContent = "等待数据...\n\n1. 打开脉脉搜索页面\n2. 执行搜索\n3. 数据自动捕获";
      }
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

  document.getElementById("btn-export").addEventListener("click", function () {
    var filename = "maimai-capture-" + new Date().toISOString().slice(0, 10) + ".json";

    // 完整导出：同时包含分页联系人、被动拦截请求和详情响应。
    chrome.runtime.sendMessage({ type: "exportFullJson", filename: filename }, function (r) {
      if (r && r.downloadId) {
        statusBadge.textContent = "已导出";
      } else {
        statusBadge.textContent = "导出失败";
      }
    });
  });

  // ---- 主动搜索 ----
  document.getElementById("btn-search").addEventListener("click", function () {
    var query = document.getElementById("search-query").value.trim();
    if (!query) {
      searchResult.innerHTML = '<span class="error">请输入搜索关键词</span>';
      return;
    }

    var params = {
      body: {
        query: query,
        page: parseInt(document.getElementById("search-page").value) || 1,
        pagesize: parseInt(document.getElementById("search-pagesize").value) || 30,
      },
    };

    searchResult.innerHTML = "搜索中...";
    statusBadge.textContent = "搜索中...";

    // 发送搜索命令到 content script → inject.js
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0] || tabs[0].url.indexOf("maimai.cn") === -1) {
        searchResult.innerHTML = '<span class="error">请在脉脉页面上使用此扩展</span>';
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, { type: "search", params: params }, function (resp) {
        if (chrome.runtime.lastError) {
          searchResult.innerHTML = '<span class="error">发送失败: ' +
            chrome.runtime.lastError.message + '</span>';
          return;
        }
      });
    });

    // 等待搜索结果
    var listener = function (msg) {
      if (msg.type === "searchResult") {
        chrome.runtime.onMessage.removeListener(listener);
        if (msg.status === "ok") {
          var data = msg.data;
          if (data && data.data) {
            var contacts = data.data.contacts || data.data.list || data.data.items || [];
            var total = data.data.total || contacts.length;
            searchResult.innerHTML =
              '<span class="success">成功: ' + contacts.length + '/' + total + ' 条结果</span>' +
              '<pre>' + JSON.stringify(data, null, 2).slice(0, 2000) + '</pre>';
            statusBadge.textContent = contacts.length + " 条结果";
          } else {
            searchResult.innerHTML =
              '<span class="warn">响应无数据，原始响应:</span>' +
              '<pre>' + (msg.raw || JSON.stringify(data)).slice(0, 2000) + '</pre>';
          }
        } else {
          searchResult.innerHTML = '<span class="error">错误: ' + (msg.error || "未知") + '</span>';
        }
      }
    };
    chrome.runtime.onMessage.addListener(listener);

    // 超时处理
    setTimeout(function () {
      chrome.runtime.onMessage.removeListener(listener);
      if (searchResult.innerHTML === "搜索中...") {
        searchResult.innerHTML = '<span class="error">搜索超时 (10s)</span>';
        statusBadge.textContent = "超时";
      }
    }, 10000);
  });

  // ---- DOM 抓取 ----
  document.getElementById("btn-dom-scrape").addEventListener("click", function () {
    domResult.innerHTML = "抓取中...";

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0] || tabs[0].url.indexOf("maimai.cn") === -1) {
        domResult.innerHTML = '<span class="error">请在脉脉页面上使用此扩展</span>';
        return;
      }
      chrome.tabs.sendMessage(tabs[0].id, { type: "domScrape" }, function (resp) {
        if (chrome.runtime.lastError) {
          domResult.innerHTML = '<span class="error">失败: ' +
            chrome.runtime.lastError.message + '</span>';
        }
      });
    });

    var domListener = function (msg) {
      if (msg.type === "domScrapeResult") {
        chrome.runtime.onMessage.removeListener(domListener);
        if (msg.count > 0) {
          domResult.innerHTML =
            '<span class="success">找到 ' + msg.count + ' 个人才卡片</span>' +
            '<pre>' + JSON.stringify(msg.results.slice(0, 5), null, 2) + '</pre>';
        } else {
          domResult.innerHTML =
            '<span class="warn">未找到人才卡片，可能选择器需要调整</span>';
        }
      }
    };
    chrome.runtime.onMessage.addListener(domListener);

    setTimeout(function () {
      chrome.runtime.onMessage.removeListener(domListener);
      if (domResult.innerHTML === "抓取中...") {
        domResult.innerHTML = '<span class="error">抓取超时 (10s)</span>';
      }
    }, 10000);
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
  var pagerProgressEl = document.getElementById("pager-progress");
  var pagerProgressFill = document.getElementById("pager-progress-fill");
  var pagerProgressText = document.getElementById("pager-progress-text");

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

    chrome.runtime.sendMessage({ type: "startPager", mode: mode, maxPages: maxPages }, function (resp) {
      if (!resp || !resp.ok) {
        pagerProgressText.textContent = "错误: " + (resp ? resp.error : "无响应");
        btnStartPager.style.display = "inline-block";
        btnStopPager.style.display = "none";
      }
    });
  });

  btnStopPager.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "stopPager" }, function () {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressText.textContent = "正在停止...";
    });
  });

  chrome.runtime.onMessage.addListener(function (msg) {
    if (msg.type === "pager_progress") {
      var pct = Math.round((msg.currentPage / msg.totalPages) * 100);
      pagerProgressFill.style.width = pct + "%";
      pagerProgressText.textContent = "第 " + msg.currentPage + "/" + msg.totalPages + " 页 (" + msg.totalContacts + " 条)";
    }
    if (msg.type === "pager_complete") {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressFill.style.width = "100%";
      pagerProgressText.textContent = "完成！共 " + msg.totalContacts + " 条";
      statusBadge.textContent = msg.totalContacts + " 条已抓取";
    }
    if (msg.type === "pager_cancelled") {
      btnStopPager.style.display = "none";
      btnStartPager.style.display = "inline-block";
      pagerProgressText.textContent = "已停止 — " + msg.totalContacts + " 条已保存";
    }
    if (msg.type === "pager_error") {
      pagerProgressText.textContent = "错误 (第" + msg.page + "页): " + msg.reason;
    }
    if (msg.type === "pager_paused") {
      pagerProgressText.textContent = "暂停 (第" + msg.page + "页): " + msg.reason;
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
  var detailModeEl = document.getElementById("detail-mode");
  var detailDailyLimitEl = document.getElementById("detail-daily-limit");
  var detailLocalPlanUrlEl = document.getElementById("detail-local-plan-url");
  var btnLoadLocalDetailPlan = document.getElementById("btn-load-local-detail-plan");
  var btnLoadStartLocalDetailPlan = document.getElementById("btn-load-start-local-detail-plan");
  var detailLocalPlanStatusEl = document.getElementById("detail-local-plan-status");
  var detailImportFileEl = document.getElementById("detail-import-file");
  var btnStartDetail = document.getElementById("btn-start-detail-batch");
  var btnPauseDetail = document.getElementById("btn-pause-detail-batch");
  var btnResumeDetail = document.getElementById("btn-resume-detail-batch");
  var btnStopDetail = document.getElementById("btn-stop-detail-batch");
  var btnRefreshDetail = document.getElementById("btn-refresh-detail-batch");
  var btnExportDetail = document.getElementById("btn-export-detail-batch");
  var btnResetDetail = document.getElementById("btn-reset-detail-batch");
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
    detailProgressText.textContent = (state.status || "idle") + " — " + completed + "/" + total;

    if (hasBatchPauseNotice(state, rawInput)) {
      var pauseCompleted = Math.max(state.batch_pause_completed || 0, completed);
      var pauseTotal = total > 0 ? "/" + total : "";
      detailProgressText.textContent = "批间休息中 — " + pauseCompleted + pauseTotal;
      detailBatchLog.textContent = "批间休息中: 已完成 " + pauseCompleted + pauseTotal + "，约 " + formatDetailDelayMs(remainingDetailPauseMs(state, rawInput)) + " 后继续";
      statusBadge.textContent = "批间休息";
    } else if (state.circuit_breaker && state.circuit_breaker.tripped) {
      detailBatchLog.textContent = "熔断暂停: " + state.circuit_breaker.reason;
      statusBadge.textContent = "详情暂停";
    } else if (rawInput.reason) {
      detailBatchLog.textContent = rawInput.reason;
    } else if (rawInput.error) {
      detailBatchLog.textContent = "错误: " + rawInput.error;
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
        detailBatchLog.textContent = "联系人来源: " + resp.contacts + " 条。safe 模式低速顺序执行，导出后需本地 dry-run。";
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
    var filename = "maimai-capture-" + new Date().toISOString().slice(0, 10) + ".json";
    chrome.runtime.sendMessage({ type: "exportFullJson", filename: filename }, function (r) {
      statusBadge.textContent = r && r.downloadId ? "已导出" : "导出失败";
    });
  }

  function startDetailBatchFromPopup() {
    detailProgressText.textContent = "启动批量详情...";
    chrome.runtime.sendMessage({ type: "startDetailBatch",
      mode: detailModeEl.value,
      dailyLimit: parseInt(detailDailyLimitEl.value) || 10000,
    }, function (resp) {
      if (!resp || !resp.ok) {
        detailProgressText.textContent = "错误: " + (resp ? resp.error : "无响应");
        return;
      }
      detailBatchLog.textContent = "批量详情已启动，Jobs: " + resp.totalJobs;
      refreshDetailBatchStatus();
    });
  }

  function importLocalDetailPlan(planPayload, shouldStart) {
    chrome.runtime.sendMessage({ type: "importDetailContacts", contacts: planPayload }, function (resp) {
      if (!resp || !resp.ok) {
        detailLocalPlanStatusEl.textContent = "任务包导入失败: " + (resp ? resp.error : "无响应");
        return;
      }
      detailLocalPlanStatusEl.textContent = "已从本地任务包导入 " + resp.imported + " 条联系人";
      detailBatchLog.textContent = "已导入 " + resp.imported + " 条联系人";
      refreshDetailBatchStatus();
      if (shouldStart) {
        startDetailBatchFromPopup();
      }
    });
  }

  function loadLocalDetailPlan(shouldStart) {
    var localPlanUrl = detailLocalPlanUrlEl.value.trim() || "http://127.0.0.1:8765/detail-plan.json";
    detailLocalPlanStatusEl.textContent = "读取本地任务包...";
    fetch(localPlanUrl, { cache: "no-store" })
      .then(function (resp) {
        if (!resp.ok) throw new Error("HTTP " + resp.status);
        return resp.json();
      })
      .then(function (planPayload) {
        importLocalDetailPlan(planPayload, shouldStart);
      })
      .catch(function (err) {
        detailLocalPlanStatusEl.textContent = "任务包读取失败: " + err.message;
      });
  }

  btnLoadLocalDetailPlan.addEventListener("click", function () {
    loadLocalDetailPlan(false);
  });

  btnLoadStartLocalDetailPlan.addEventListener("click", function () {
    loadLocalDetailPlan(true);
  });

  detailImportFileEl.addEventListener("change", function () {
    var file = detailImportFileEl.files && detailImportFileEl.files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function () {
      try {
        var parsed = JSON.parse(reader.result);
        chrome.runtime.sendMessage({ type: "importDetailContacts", contacts: parsed }, function (resp) {
          if (resp && resp.ok) {
            detailBatchLog.textContent = "已导入 " + resp.imported + " 条联系人";
            refreshDetailBatchStatus();
          } else {
            detailBatchLog.textContent = "导入失败: " + (resp ? resp.error : "无响应");
          }
        });
      } catch (err) {
        detailBatchLog.textContent = "JSON 解析失败: " + err.message;
      }
    };
    reader.readAsText(file, "utf-8");
  });

  btnStartDetail.addEventListener("click", function () {
    startDetailBatchFromPopup();
  });

  btnPauseDetail.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "pauseDetailBatch" }, function (resp) {
      if (resp && resp.state) renderDetailBatchState(resp.state);
    });
  });

  btnResumeDetail.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "resumeDetailBatch" }, function (resp) {
      if (resp && resp.state) renderDetailBatchState(resp.state);
    });
  });

  btnStopDetail.addEventListener("click", function () {
    chrome.runtime.sendMessage({ type: "stopDetailBatch" }, function (resp) {
      if (resp && resp.state) renderDetailBatchState(resp.state);
    });
  });

  btnRefreshDetail.addEventListener("click", refreshDetailBatchStatus);
  btnExportDetail.addEventListener("click", exportFullJsonForDetail);
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
      statusBadge.textContent = "批量详情已重置";
      refreshDetailBatchStatus();
    });
  });

  // ---- 初始化 ----
  refreshStats();
  refreshTemplateStatus();
  refreshDetailBatchStatus();

  // 自动刷新（被动拦截模式下每 2 秒更新统计）
  setInterval(refreshStats, 2000);
  setInterval(refreshTemplateStatus, 5000);
  setInterval(refreshDetailBatchStatus, 5000);
})();
