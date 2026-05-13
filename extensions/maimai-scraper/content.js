// content.js — 内容脚本，桥接页面上下文和扩展后台
// 运行在隔离世界 (ISOLATED world)

(function () {
  "use strict";

  // 缓存模板状态（由 inject.js 通过 postMessage 更新）
  var templateCache = { hasTemplate: false, url: null, method: null };
  var floatingScraperRefresh = null;

  function safeSendMessage(message, callback) {
    try {
      if (!chrome || !chrome.runtime || !chrome.runtime.id) {
        return;
      }
      chrome.runtime.sendMessage(message, function (response) {
        var lastError = chrome.runtime.lastError;
        if (lastError && lastError.message !== "Extension context invalidated.") {
          console.warn("[Maimai Scraper] sendMessage failed:", lastError.message);
        }
        if (callback) callback(response);
      });
    } catch (err) {
      if (!err || err.message !== "Extension context invalidated.") {
        console.warn("[Maimai Scraper] extension context unavailable:", err && err.message);
      }
    }
  }

  function shouldRefreshFloatingScraperWidget(type) {
    return type === "pager_progress"
      || type === "pager_complete"
      || (typeof type === "string" && type.indexOf("detail_batch_") === 0);
  }

  function formatLocalDate(date) {
    function pad(value) {
      return String(value).padStart(2, "0");
    }
    return date.getFullYear() + "-" + pad(date.getMonth() + 1) + "-" + pad(date.getDate());
  }

  function mountFloatingScraperWidget() {
    var hostId = "maimai-scraper-floating-host";
    if (document.getElementById(hostId)) return;
    if (!document.documentElement || !document.body) return;

    var host = document.createElement("div");
    host.id = hostId;
    var shadow = host.attachShadow({ mode: "open" });

    var style = document.createElement("style");
    style.textContent = [
      ":host{position:fixed;right:0;top:42%;z-index:2147483647;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#172033;}",
      ".widget{width:176px;box-sizing:border-box;background:#fff;border:1px solid rgba(23,32,51,.14);border-right:0;border-radius:8px 0 0 8px;box-shadow:0 10px 28px rgba(15,23,42,.18);padding:10px 10px 9px;cursor:pointer;user-select:none;}",
      ".title{font-size:13px;font-weight:700;line-height:18px;white-space:normal;}",
      ".meta{margin-top:3px;font-size:12px;line-height:16px;color:#5f6b7a;}",
      ".progress{display:none;height:4px;margin-top:8px;background:#edf1f7;border-radius:999px;overflow:hidden;}",
      ".bar{height:100%;width:0;background:#2f7cf6;border-radius:999px;transition:width .18s ease;}",
      ".stats{display:none;margin-top:7px;font-size:11px;line-height:15px;color:#405064;}",
      ".actions{display:none;margin-top:8px;}",
      "button{width:100%;height:28px;border:1px solid #2f7cf6;border-radius:6px;background:#2f7cf6;color:#fff;font-size:12px;font-weight:600;cursor:pointer;}",
      "button:hover{background:#1f6be3;}"
    ].join("");

    var widget = document.createElement("div");
    widget.className = "widget";
    widget.setAttribute("role", "button");
    widget.setAttribute("tabindex", "0");

    var titleEl = document.createElement("div");
    titleEl.className = "title";
    var metaEl = document.createElement("div");
    metaEl.className = "meta";
    var progressEl = document.createElement("div");
    progressEl.className = "progress";
    var barEl = document.createElement("div");
    barEl.className = "bar";
    var statsEl = document.createElement("div");
    statsEl.className = "stats";
    var actionsEl = document.createElement("div");
    actionsEl.className = "actions";
    var exportButton = document.createElement("button");
    exportButton.type = "button";
    exportButton.textContent = "导出 JSON";

    progressEl.appendChild(barEl);
    actionsEl.appendChild(exportButton);
    widget.appendChild(titleEl);
    widget.appendChild(metaEl);
    widget.appendChild(progressEl);
    widget.appendChild(statsEl);
    widget.appendChild(actionsEl);
    shadow.appendChild(style);
    shadow.appendChild(widget);
    document.documentElement.appendChild(host);

    function setProgress(done, total) {
      var pct = total > 0 ? Math.max(0, Math.min(100, Math.round((done / total) * 100))) : 0;
      progressEl.style.display = total > 0 ? "block" : "none";
      barEl.style.width = pct + "%";
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

    function remainingBatchPauseMs(state) {
      if (state && state.batch_pause_until) {
        var parsed = Date.parse(state.batch_pause_until);
        if (!Number.isNaN(parsed)) return Math.max(0, parsed - Date.now());
      }
      return state && state.batch_pause_delay_ms ? state.batch_pause_delay_ms : 0;
    }

    function render(summary) {
      summary = summary || {};
      var totalContacts = summary.totalContacts || 0;
      var totalDetails = summary.totalDetails || 0;
      var pager = summary.pager || {};
      var detail = summary.detail || {};
      var state = detail.state || {};
      var counts = detail.counts || state.counts || {};
      var status = state.status || "";
      var totalJobs = detail.totalJobs || detail.jobs || state.total_jobs || 0;
      var done = counts.done || 0;
      var failed = counts.failed || 0;
      var skipped = counts.skipped || 0;
      var completedJobs = done + failed + skipped;
      var detailRunning = detail.running || status === "running" || status === "paused";
      var detailCompleted = detail.completed || status === "completed";

      statsEl.style.display = "none";
      actionsEl.style.display = "none";
      setProgress(0, 0);

      if (detailCompleted) {
        titleEl.textContent = "任务执行完毕";
        metaEl.textContent = "详情 " + totalDetails + " · 任务 " + completedJobs + "/" + totalJobs;
        statsEl.textContent = "成功 " + done + " · 失败 " + failed;
        statsEl.style.display = "block";
        actionsEl.style.display = "block";
        setProgress(completedJobs, totalJobs);
        return;
      }

      if (detailRunning) {
        if (state.batch_pause_until) {
          titleEl.textContent = "批间休息中";
          metaEl.textContent = "已完成 " + Math.max(state.batch_pause_completed || 0, completedJobs) + "/" + totalJobs;
          statsEl.textContent = "约 " + formatDetailDelayMs(remainingBatchPauseMs(state)) + " 后继续";
        } else {
          titleEl.textContent = status === "paused" ? "详情抓取已暂停" : "详情抓取执行中";
          metaEl.textContent = "进度 " + completedJobs + "/" + totalJobs;
          statsEl.textContent = "成功 " + done + " · 失败 " + failed;
        }
        statsEl.style.display = "block";
        setProgress(completedJobs, totalJobs);
        return;
      }

      if (pager.running) {
        titleEl.textContent = "联系人抓取执行中";
        metaEl.textContent = "页进度 " + (pager.currentPage || 0) + "/" + (pager.totalPages || 0);
        statsEl.textContent = "联系人 " + totalContacts + (pager.totalFromApi ? " / " + pager.totalFromApi : "");
        statsEl.style.display = "block";
        setProgress(pager.currentPage || 0, pager.totalPages || 0);
        return;
      }

      titleEl.textContent = "Maimai Scraper";
      metaEl.textContent = "联系人 " + totalContacts + " · 详情 " + totalDetails;
    }

    function refresh() {
      safeSendMessage({ type: "getScraperSummary" }, render);
    }

    widget.addEventListener("click", function () {
      safeSendMessage({ type: "openMainPage" });
    });

    widget.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        safeSendMessage({ type: "openMainPage" });
      }
    });

    function exportFullJson() {
      var filename = "maimai-capture-" + formatLocalDate(new Date()) + ".json";
      safeSendMessage({ type: "exportFullJson", filename: filename }, refresh);
    }

    exportButton.addEventListener("click", function (event) {
      event.stopPropagation();
      exportFullJson();
    });

    exportButton.addEventListener("keydown", function (event) {
      if (event.key !== "Enter" && event.key !== " ") return;
      event.preventDefault();
      event.stopPropagation();
      exportFullJson();
    });

    floatingScraperRefresh = refresh;
    refresh();
    setInterval(refresh, 2000);
  }

  function refreshFloatingScraperWidget() {
    if (floatingScraperRefresh) {
      floatingScraperRefresh();
    }
  }

  // 转发页面数据到 background
  window.addEventListener("message", function (e) {
    if (e.source !== window) return;

    // 缓存模板更新通知
    if (e.data && e.data.type === "__MAIMAI_TEMPLATE_UPDATED__") {
      templateCache = {
        hasTemplate: e.data.hasTemplate,
        url: e.data.url,
        method: e.data.method,
        pageMeta: e.data.pageMeta || null,
        contactCount: e.data.contactCount || 0,
        template: e.data.template || null,
      };
    }

    if (e.data && e.data.type === "__MAIMAI_DATA__") {
      safeSendMessage({
        type: "capture",
        record: e.data.record,
      });
    }

    if (e.data && e.data.type === "__MAIMAI_SEARCH_RESULT__") {
      safeSendMessage({
        type: "searchResult",
        requestId: e.data.requestId,
        status: e.data.status,
        data: e.data.data,
        raw: e.data.raw,
        error: e.data.error,
      });
    }

    if (e.data && e.data.type === "__MAIMAI_DOM_SCRAPE_RESULT__") {
      safeSendMessage({
        type: "domScrapeResult",
        requestId: e.data.requestId,
        count: e.data.count,
        results: e.data.results,
      });
    }
  });

  // 转发 popup/background 命令到页面
  chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
    if (msg && shouldRefreshFloatingScraperWidget(msg.type)) {
      refreshFloatingScraperWidget();
    }

    if (msg.type === "search") {
      var requestId = "search_" + Date.now();
      window.postMessage({
        type: "__MAIMAI_SEARCH_CMD__",
        requestId: requestId,
        params: msg.params,
      }, "*");
      sendResponse({ requestId: requestId });
      return true;
    }

    if (msg.type === "domScrape") {
      var requestId = "dom_" + Date.now();
      window.postMessage({
        type: "__MAIMAI_DOM_SCRAPE_CMD__",
        requestId: requestId,
      }, "*");
      sendResponse({ requestId: requestId });
      return true;
    }

    if (msg.type === "getCaptured") {
      safeSendMessage({ type: "getStoredData" }, function (r) {
        sendResponse(r);
      });
      return true;
    }

    if (msg.type === "getPageData") {
      // 直接从页面上下文读取 __maimaiData
      var script = document.createElement("script");
      script.textContent = `
        (function() {
          var data = window.__maimaiData || { requests: [], contacts: [] };
          window.postMessage({
            type: "__MAIMAI_PAGE_DATA__",
            data: {
              requests: data.requests,
              contacts: data.contacts,
              requestCount: data.requests.length,
              contactCount: data.contacts.length,
            }
          }, "*");
        })();
      `;
      document.documentElement.appendChild(script);
      script.remove();
      sendResponse({ ok: true });
      return true;
    }

    if (msg.type === "getTemplateStatus") {
      sendResponse(templateCache);
      return false;
    }

    if (msg.type === "getFullTemplate") {
      sendResponse({ template: templateCache.template || null });
      return false;
    }

    if (msg.type === "pagerFetch") {
      var requestId = "pager_" + Date.now();
      var pagerResponded = false;
      var pagerTimeoutId = null;

      function respondPager(payload) {
        if (pagerResponded) return;
        pagerResponded = true;
        window.removeEventListener("message", fetchHandler);
        if (pagerTimeoutId !== null) {
          clearTimeout(pagerTimeoutId);
          pagerTimeoutId = null;
        }
        sendResponse(payload);
      }

      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH__",
        requestId: requestId,
        page: msg.page,
      }, "*");

      var fetchHandler = function (e) {
        if (e.source !== window || !e.data || e.data.type !== "__MAIMAI_PAGER_FETCH_RESULT__") return;
        if (e.data.requestId !== requestId) return;
        respondPager({
          httpStatus: e.data.httpStatus,
          data: e.data.data,
          raw: e.data.raw,
          error: e.data.error,
          pageMeta: e.data.pageMeta || null,
          headerNames: e.data.headerNames || [],
        });
      };
      window.addEventListener("message", fetchHandler);

      pagerTimeoutId = setTimeout(function () {
        respondPager({ httpStatus: 0, error: "请求超时" });
      }, 15000);
      return true;
    }

    if (msg.type === "tracePageState") {
      sendResponse({
        ok: true,
        href: location.href,
        title: document.title,
        visibilityState: document.visibilityState,
        hasFocus: document.hasFocus(),
      });
      return false;
    }

    if (msg.type === "detailFetch") {
      var detailRequestId = "detail_" + Date.now() + "_" + Math.random().toString(36).slice(2, 8);
      var detailResponded = false;

      function respondDetail(payload) {
        if (detailResponded) return;
        detailResponded = true;
        sendResponse(payload);
      }

      window.postMessage({
        type: "__MAIMAI_DETAIL_FETCH__",
        requestId: detailRequestId,
        job: msg.job,
      }, "*");

      var detailHandler = function (e) {
        if (e.source !== window || !e.data || e.data.type !== "__MAIMAI_DETAIL_FETCH_RESULT__") return;
        if (e.data.requestId !== detailRequestId) return;
        window.removeEventListener("message", detailHandler);
        respondDetail({
          ok: e.data.ok,
          jobId: e.data.jobId,
          endpoints: e.data.endpoints || {},
          detail: e.data.detail || null,
          errors: e.data.errors || [],
          error: e.data.error || null,
        });
      };
      window.addEventListener("message", detailHandler);

      setTimeout(function () {
        window.removeEventListener("message", detailHandler);
        respondDetail({ ok: false, error: "请求超时", errors: ["请求超时"] });
      }, 45000);
      return true;
    }
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountFloatingScraperWidget, { once: true });
  } else {
    mountFloatingScraperWidget();
  }
})();
