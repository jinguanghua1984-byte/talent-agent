// content.js — 内容脚本，桥接页面上下文和扩展后台
// 运行在隔离世界 (ISOLATED world)

(function () {
  "use strict";

  // 缓存模板状态（由 inject.js 通过 postMessage 更新）
  var templateCache = { hasTemplate: false, url: null, method: null };

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

})();
