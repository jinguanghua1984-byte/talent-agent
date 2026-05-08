// content.js — 内容脚本，桥接页面上下文和扩展后台
// 运行在隔离世界 (ISOLATED world)

(function () {
  "use strict";

  // 缓存模板状态（由 inject.js 通过 postMessage 更新）
  var templateCache = { hasTemplate: false, url: null, method: null };

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
      };
    }

    if (e.data && e.data.type === "__MAIMAI_DATA__") {
      chrome.runtime.sendMessage({
        type: "capture",
        record: e.data.record,
      });
    }

    if (e.data && e.data.type === "__MAIMAI_SEARCH_RESULT__") {
      chrome.runtime.sendMessage({
        type: "searchResult",
        requestId: e.data.requestId,
        status: e.data.status,
        data: e.data.data,
        raw: e.data.raw,
        error: e.data.error,
      });
    }

    if (e.data && e.data.type === "__MAIMAI_DOM_SCRAPE_RESULT__") {
      chrome.runtime.sendMessage({
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
      chrome.runtime.sendMessage({ type: "getStoredData" }, function (r) {
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
      var script = document.createElement("script");
      script.textContent = "(function(){" +
        "var t = window.__maimaiSearchTemplate;" +
        "window.postMessage({" +
        "  type: '__MAIMAI_FULL_TEMPLATE__'," +
        "  template: t" +
        "}, '*');" +
        "})();";
      document.documentElement.appendChild(script);
      script.remove();

      var handler = function (e) {
        if (e.source !== window || !e.data || e.data.type !== "__MAIMAI_FULL_TEMPLATE__") return;
        window.removeEventListener("message", handler);
        sendResponse({ template: e.data.template });
      };
      window.addEventListener("message", handler);

      setTimeout(function () {
        window.removeEventListener("message", handler);
        sendResponse({ template: null });
      }, 3000);
      return true;
    }

    if (msg.type === "pagerFetch") {
      var requestId = "pager_" + Date.now();
      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH__",
        requestId: requestId,
        page: msg.page,
      }, "*");

      var fetchHandler = function (e) {
        if (e.source !== window || !e.data || e.data.type !== "__MAIMAI_PAGER_FETCH_RESULT__") return;
        if (e.data.requestId !== requestId) return;
        window.removeEventListener("message", fetchHandler);
        sendResponse({
          httpStatus: e.data.httpStatus,
          data: e.data.data,
          raw: e.data.raw,
          error: e.data.error,
        });
      };
      window.addEventListener("message", fetchHandler);

      setTimeout(function () {
        window.removeEventListener("message", fetchHandler);
        sendResponse({ httpStatus: 0, error: "请求超时" });
      }, 15000);
      return true;
    }
  });
})();
