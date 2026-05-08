// inject.js — 运行在页面主上下文 (MAIN world)
// 拦截 fetch/XHR 请求和响应 + 提供主动搜索能力

if (!window.__maimaiScraperV2) {
  window.__maimaiScraperV2 = true;
  window.__maimaiData = { requests: [], contacts: [] };

  var TARGET_PATHS = [
    "/api/pc/search/",
    "/api/pc/u/",
    "/api/ent/",
    "/api/web/",
    "/ent/v41/",
  ];

  function shouldCapture(url) {
    try {
      return TARGET_PATHS.some(function (p) {
        return url.indexOf(p) !== -1;
      });
    } catch (e) {
      return false;
    }
  }

  function headersToObj(h) {
    var o = {};
    if (h instanceof Headers) {
      h.forEach(function (v, k) { o[k] = v; });
    } else if (typeof h === "object" && h !== null) {
      Object.assign(o, h);
    }
    return o;
  }

  function safeParse(text) {
    try { return JSON.parse(text); } catch (e) { return null; }
  }

  // ---- 拦截 fetch（捕获请求 + 响应）----
  var origFetch = window.fetch;
  window.fetch = function () {
    var args = arguments;
    var url = typeof args[0] === "string"
      ? args[0]
      : (args[0] && args[0].url ? args[0].url : "");
    var opts = args[1] || {};

    if (!shouldCapture(url)) {
      return origFetch.apply(this, args);
    }

    var record = {
      id: Date.now() + "_" + Math.random().toString(36).slice(2, 8),
      ts: new Date().toISOString(),
      url: url,
      method: opts.method || "GET",
      requestHeaders: headersToObj(opts.headers),
      requestBody: opts.body || null,
    };

    return origFetch.apply(this, args).then(function (response) {
      var clone = response.clone();
      clone.text().then(function (body) {
        record.status = response.status;
        record.responseHeaders = headersToObj(response.headers);
        record.responseBody = body;
        record.responseData = safeParse(body);

        window.__maimaiData.requests.push(record);

        // 自动提取 contacts
        var data = record.responseData;
        if (data && data.data) {
          var contacts = data.data.contacts || data.data.list || data.data.items || [];
          if (contacts.length > 0) {
            window.__maimaiData.contacts = window.__maimaiData.contacts.concat(contacts);
          }
        }

        // 保存搜索请求模板（用于主动搜索）
        saveSearchTemplate(record);

        // 通知 content script
        window.postMessage({ type: "__MAIMAI_DATA__", record: record }, "*");
      }).catch(function () {});
      return response;
    });
  };
  window.fetch.toString = function () { return origFetch.toString(); };

  // ---- 拦截 XMLHttpRequest（捕获请求 + 响应）----
  var origOpen = XMLHttpRequest.prototype.open;
  var origSend = XMLHttpRequest.prototype.send;
  var origSetHeader = XMLHttpRequest.prototype.setRequestHeader;

  XMLHttpRequest.prototype.open = function (method, url) {
    this.__mmMeta = { method: method, url: url, headers: {} };
    return origOpen.apply(this, arguments);
  };

  XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
    if (this.__mmMeta) { this.__mmMeta.headers[name] = value; }
    return origSetHeader.apply(this, arguments);
  };

  XMLHttpRequest.prototype.send = function (body) {
    var meta = this.__mmMeta;
    if (meta && shouldCapture(meta.url)) {
      var record = {
        id: Date.now() + "_" + Math.random().toString(36).slice(2, 8),
        ts: new Date().toISOString(),
        url: meta.url,
        method: meta.method,
        requestHeaders: meta.headers,
        requestBody: body || null,
      };

      this.addEventListener("load", function () {
        record.status = this.status;
        record.responseBody = this.responseText;
        record.responseData = safeParse(this.responseText);

        window.__maimaiData.requests.push(record);

        var data = record.responseData;
        if (data && data.data) {
          var contacts = data.data.contacts || data.data.list || data.data.items || [];
          if (contacts.length > 0) {
            window.__maimaiData.contacts = window.__maimaiData.contacts.concat(contacts);
          }
        }

        // 保存搜索请求模板（用于主动搜索）
        saveSearchTemplate(record);

        window.postMessage({ type: "__MAIMAI_DATA__", record: record }, "*");
      });
    }
    return origSend.apply(this, arguments);
  };

  // ---- 保存最近一次搜索请求模板（从被动拦截中提取）----
  window.__maimaiSearchTemplate = null;

  function saveSearchTemplate(record) {
    var data = record.responseData;
    if (!data || !data.data) return;
    var contacts = data.data.contacts || data.data.list || data.data.items || [];
    if (contacts.length === 0) return;

    var pageMeta = {
      total: data.data.total || data.data.totalCount || data.data.count || 0,
      pagesize: data.data.pagesize || data.data.pageSize || data.data.limit || data.data.size || 30,
      page: data.data.page || data.data.pageNum || data.data.pageNo || 1,
    };

    window.__maimaiSearchTemplate = {
      url: record.url,
      method: record.method,
      headers: record.requestHeaders || {},
      body: record.requestBody ? safeParse(record.requestBody) : null,
      pageMeta: pageMeta,
      contactCount: contacts.length,
    };

    window.postMessage({
      type: "__MAIMAI_TEMPLATE_UPDATED__",
      hasTemplate: true,
      url: record.url,
      method: record.method,
      pageMeta: pageMeta,
      contactCount: contacts.length,
    }, "*");
  }

  // ---- 主动搜索：基于拦截到的请求模板重发 ----
  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data || e.data.type !== "__MAIMAI_SEARCH_CMD__") return;

    var params = e.data.params || {};
    var requestId = e.data.requestId;
    var tpl = window.__maimaiSearchTemplate;

    if (!tpl) {
      window.postMessage({
        type: "__MAIMAI_SEARCH_RESULT__",
        requestId: requestId,
        status: "error",
        error: "无请求模板 — 请先在页面上手动搜索一次，让扩展捕获真实请求格式",
      }, "*");
      return;
    }

    // 克隆模板 body，替换关键词和分页
    var body = JSON.parse(JSON.stringify(tpl.body || {}));
    if (params.body) {
      if (params.body.query !== undefined) {
        // 尝试多种可能的字段名
        body.query = params.body.query;
        body.keyword = params.body.query;
        body.keywords = params.body.query;
        body.q = params.body.query;
      }
      if (params.body.page !== undefined) {
        body.page = params.body.page;
        body.pageNum = params.body.page;
        body.pageNo = params.body.page;
      }
      if (params.body.pagesize !== undefined) {
        body.pagesize = params.body.pagesize;
        body.pageSize = params.body.pagesize;
        body.limit = params.body.pagesize;
        body.count = params.body.pagesize;
      }
    }

    var headers = JSON.parse(JSON.stringify(tpl.headers));
    // 确保 Content-Type 正确
    if (!headers["Content-Type"] && !headers["content-type"]) {
      headers["Content-Type"] = "application/json";
    }

    var searchOpts = {
      method: tpl.method || "POST",
      headers: headers,
      body: JSON.stringify(body),
      credentials: "include",
    };

    origFetch.call(window, tpl.url, searchOpts)
      .then(function (r) { return r.text(); })
      .then(function (text) {
        var data = safeParse(text);
        window.postMessage({
          type: "__MAIMAI_SEARCH_RESULT__",
          requestId: requestId,
          status: "ok",
          data: data,
          raw: text,
        }, "*");
      })
      .catch(function (err) {
        window.postMessage({
          type: "__MAIMAI_SEARCH_RESULT__",
          requestId: requestId,
          status: "error",
          error: err.message,
        }, "*");
      });
  });

  // ---- DOM 抓取：从页面 DOM 提取人才列表 ----
  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data || e.data.type !== "__MAIMAI_DOM_SCRAPE_CMD__") return;

    var requestId = e.data.requestId;
    var results = [];

    // 尝试多种选择器定位人才卡片
    var cards = document.querySelectorAll(
      '.talent-card, .contact-card, .search-result-item, ' +
      '[class*="talent"], [class*="contact"], [class*="result-card"]'
    );

    cards.forEach(function (card) {
      var item = {};
      item.name = (card.querySelector('[class*="name"], .name, h3, h4') || {}).textContent || "";
      item.company = (card.querySelector('[class*="company"], .company') || {}).textContent || "";
      item.position = (card.querySelector('[class*="position"], [class*="title"], .title') || {}).textContent || "";
      item.text = card.textContent.trim();
      item.html = card.innerHTML;
      results.push(item);
    });

    window.postMessage({
      type: "__MAIMAI_DOM_SCRAPE_RESULT__",
      requestId: requestId,
      count: results.length,
      results: results,
    }, "*");
  });

  // ---- AutoPager: 从 MAIN world 发起分页请求 ----
  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data || e.data.type !== "__MAIMAI_PAGER_FETCH__") return;

    var requestId = e.data.requestId;
    var page = e.data.page;
    var tpl = window.__maimaiSearchTemplate;

    if (!tpl) {
      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH_RESULT__",
        requestId: requestId,
        status: "error",
        error: "无请求模板",
      }, "*");
      return;
    }

    var body = JSON.parse(JSON.stringify(tpl.body || {}));
    body.page = page;
    body.pageNum = page;
    body.pageNo = page;

    var headers = JSON.parse(JSON.stringify(tpl.headers || {}));
    if (!headers["Content-Type"] && !headers["content-type"]) {
      headers["Content-Type"] = "application/json";
    }

    origFetch.call(window, tpl.url, {
      method: tpl.method || "POST",
      headers: headers,
      body: JSON.stringify(body),
      credentials: "include",
    })
    .then(function (r) {
      return r.text().then(function (text) {
        return { status: r.status, body: text, data: safeParse(text) };
      });
    })
    .then(function (result) {
      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH_RESULT__",
        requestId: requestId,
        status: "ok",
        httpStatus: result.status,
        data: result.data,
        raw: result.body,
      }, "*");
    })
    .catch(function (err) {
      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH_RESULT__",
        requestId: requestId,
        status: "error",
        error: err.message,
      }, "*");
    });
  });

  console.log("[Maimai Scraper v2] 已安装 — 被动拦截 + 主动搜索 + DOM 抓取就绪");
}
