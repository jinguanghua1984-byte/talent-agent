// inject.js — 运行在页面主上下文 (MAIN world)
// 拦截 fetch/XHR 请求和响应 + 提供主动搜索能力

if (!window.__maimaiScraperV2) {
  window.__maimaiScraperV2 = true;
  window.__maimaiData = { requests: [], contacts: [] };

  var TARGET_PATHS = [
    "/api/pc/search/",
    "/api/pc/u/",
    "/api/pc/profile/",
    "/api/pc/user/",
    "/api/profile/",
    "/api/user/",
    "/api/ent/",
    "/api/web/",
    "/ent/v41/",
    "/profile/detail",
  ];

  function shouldCapture(url) {
    try {
      var value = String(url || "");
      if (TARGET_PATHS.some(function (p) {
        return value.indexOf(p) !== -1;
      })) {
        return true;
      }
      return /\/api\/.*(profile|detail|user|resume|contact)/i.test(value);
    } catch (e) {
      return false;
    }
  }

  function headersToObj(h) {
    var o = {};
    if (h instanceof Headers) {
      h.forEach(function (v, k) { o[k] = v; });
    } else if (Array.isArray(h)) {
      h.forEach(function (pair) {
        if (pair && pair.length >= 2) o[pair[0]] = pair[1];
      });
    } else if (typeof h === "object" && h !== null) {
      Object.assign(o, h);
    }
    return o;
  }

  function safeParse(text) {
    try { return JSON.parse(text); } catch (e) { return null; }
  }

  function headerNames(headers) {
    return Object.keys(headers || {}).sort();
  }

  function firstNumber(values, fallback) {
    for (var i = 0; i < values.length; i++) {
      var value = Number(values[i]);
      if (Number.isFinite(value) && value > 0) return value;
    }
    return fallback;
  }

  function extractContactsFromData(data) {
    if (!data || !data.data) return [];
    return data.data.contacts || data.data.list || data.data.items || [];
  }

  function extractPageMeta(record) {
    var data = record && record.responseData && record.responseData.data ? record.responseData.data : {};
    var body = record && record.requestBody ? safeParse(record.requestBody) : null;
    var search = body && body.search ? body.search : {};
    var paginationParam = search.paginationParam || (body && body.paginationParam) || {};
    var contacts = extractContactsFromData(record.responseData);
    var total = firstNumber([
      data.total,
      data.total_match,
      data.totalCount,
      data.total_count,
      search.total,
      search.total_match,
    ], contacts.length || 0);
    var pagesize = firstNumber([
      data.pagesize,
      data.pageSize,
      data.limit,
      data.size,
      data.count,
      paginationParam.size,
      search.size,
      body && body.size,
      contacts.length,
    ], 30);
    var page = firstNumber([
      data.page,
      data.pageNum,
      data.pageNo,
      paginationParam.page,
      search.page ? search.page + 1 : null,
      body && body.page,
    ], 1);
    return {
      total: total,
      total_match: firstNumber([data.total_match, search.total_match], total),
      pagesize: pagesize,
      page: page,
      headerNames: headerNames(record.requestHeaders || {}),
    };
  }

  function setIfPresent(target, key, value) {
    if (target && Object.prototype.hasOwnProperty.call(target, key)) {
      target[key] = value;
    }
  }

  function applyPagerPage(body, page, pagesize) {
    body = body || {};
    var size = pagesize || 30;
    if (body.search && body.search.paginationParam) {
      body.search.paginationParam.page = page;
      body.search.paginationParam.size = size;
      setIfPresent(body.search, "page", Math.max(0, page - 1));
      setIfPresent(body.search, "size", size);
    } else if (body.paginationParam) {
      body.paginationParam.page = page;
      body.paginationParam.size = size;
    }

    setIfPresent(body, "page", page);
    setIfPresent(body, "pageNum", page);
    setIfPresent(body, "pageNo", page);
    setIfPresent(body, "pagesize", size);
    setIfPresent(body, "pageSize", size);
    setIfPresent(body, "limit", size);
    setIfPresent(body, "count", size);

    if (!body.search && !body.paginationParam && !Object.prototype.hasOwnProperty.call(body, "page")) {
      body.page = page;
      body.pageNum = page;
      body.pageNo = page;
    }
    return body;
  }

  function applySearchQuery(body, query) {
    body = body || {};
    if (body.search && typeof body.search === "object") {
      body.search.query = query;
      if (Object.prototype.hasOwnProperty.call(body.search, "search_query")) {
        body.search.search_query = query;
      }
    }
    body.query = query;
    body.keyword = query;
    body.keywords = query;
    body.q = query;
    return body;
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
    var contacts = extractContactsFromData(data);
    if (contacts.length === 0) return;

    var pageMeta = extractPageMeta(record);
    var requestHeaders = record.requestHeaders || {};

    window.__maimaiSearchTemplate = {
      url: record.url,
      method: record.method,
      headers: requestHeaders,
      requestHeaders: requestHeaders,
      headerNames: headerNames(requestHeaders),
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
      template: window.__maimaiSearchTemplate,
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
        applySearchQuery(body, params.body.query);
      }
      if (params.body.page !== undefined) {
        applyPagerPage(body, params.body.page, params.body.pagesize || tpl.pageMeta.pagesize);
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

    var body = applyPagerPage(
      JSON.parse(JSON.stringify(tpl.body || {})),
      page,
      tpl.pageMeta && tpl.pageMeta.pagesize
    );

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
      var pageMeta = extractPageMeta({
        responseData: result.data,
        requestBody: JSON.stringify(body),
        requestHeaders: headers,
      });
      window.postMessage({
        type: "__MAIMAI_PAGER_FETCH_RESULT__",
        requestId: requestId,
        status: "ok",
        httpStatus: result.status,
        data: result.data,
        raw: result.body,
        pageMeta: pageMeta,
        headerNames: pageMeta.headerNames,
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

  function detailEndpointUrls(job) {
    var id = encodeURIComponent(String(job && job.id ? job.id : ""));
    var token = job && job.trackable_token ? encodeURIComponent(String(job.trackable_token)) : "";
    return {
      basic: "/api/ent/talent/basic?channel=www&data_version=3.1&need_ai_info=0&resume_project_id=&show_tip=0&to_uid=" +
        id + "&trackable_token=" + token + "&version=1.0.0",
      projects: "/api/ent/candidate/associated/project/list?channel=www&data_version=4.1&fr=profile&to_uid=" +
        id + "&version=1.0.0",
      job_preference: "/api/ent/talent/job_preference?channel=www&page=0&size=20&to_uid=" +
        id + "&version=1.0.0",
      contact_btn: "/api/ent/v3/search/contact_btn?channel=www&to_uids=" +
        id + "&version=1.0.0",
    };
  }

  function looksLikeAuthOrCaptcha(text) {
    var value = String(text || "").toLowerCase();
    return value.indexOf("login") !== -1 ||
      value.indexOf("captcha") !== -1 ||
      value.indexOf("验证码") !== -1 ||
      value.indexOf("验证") !== -1 ||
      value.indexOf("权限") !== -1 ||
      value.indexOf("forbidden") !== -1;
  }

  function fetchDetailEndpoint(name, url) {
    return origFetch.call(window, url, {
      method: "GET",
      credentials: "include",
      headers: {
        "Accept": "application/json, text/plain, */*",
      },
    }).then(function (response) {
      return response.text().then(function (text) {
        var data = safeParse(text);
        return {
          name: name,
          ok: response.status >= 200 && response.status < 300 && Boolean(data),
          httpStatus: response.status,
          url: url,
          data: data,
          raw: text,
          error: data ? null : "非 JSON 响应",
          authFailure: response.status === 401 || response.status === 403 || response.status === 429 || (!data && looksLikeAuthOrCaptcha(text)),
        };
      });
    }).catch(function (err) {
      return {
        name: name,
        ok: false,
        httpStatus: 0,
        url: url,
        data: null,
        raw: "",
        error: err.message,
        authFailure: true,
      };
    });
  }

  function normalizeDetailData(endpointResult) {
    if (!endpointResult || !endpointResult.data) return null;
    return endpointResult.data.data || endpointResult.data;
  }

  // ---- 批量详情：在 MAIN world 中重放详情接口 ----
  window.addEventListener("message", function (e) {
    if (e.source !== window) return;
    if (!e.data || e.data.type !== "__MAIMAI_DETAIL_FETCH__") return;

    var requestId = e.data.requestId;
    var job = e.data.job || {};
    var jobId = job.id ? String(job.id) : "";
    var errors = [];
    var endpoints = {};

    if (!jobId) {
      window.postMessage({
        type: "__MAIMAI_DETAIL_FETCH_RESULT__",
        requestId: requestId,
        ok: false,
        jobId: jobId,
        endpoints: endpoints,
        detail: null,
        errors: ["missing_id"],
        error: "missing_id",
      }, "*");
      return;
    }

    if (!job.trackable_token) {
      endpoints.basic = {
        name: "basic",
        ok: false,
        httpStatus: 0,
        data: null,
        raw: "",
        error: "missing_trackable_token",
        authFailure: false,
      };
      window.postMessage({
        type: "__MAIMAI_DETAIL_FETCH_RESULT__",
        requestId: requestId,
        ok: false,
        jobId: jobId,
        endpoints: endpoints,
        detail: null,
        errors: ["missing_trackable_token"],
        error: "missing_trackable_token",
      }, "*");
      return;
    }

    var urls = detailEndpointUrls(job);
    fetchDetailEndpoint("basic", urls.basic)
      .then(function (basic) {
        endpoints.basic = basic;
        if (!basic.ok) {
          errors.push(basic.error || ("basic_http_" + basic.httpStatus));
          window.postMessage({
            type: "__MAIMAI_DETAIL_FETCH_RESULT__",
            requestId: requestId,
            ok: false,
            jobId: jobId,
            endpoints: endpoints,
            detail: null,
            errors: errors,
            error: errors[0],
          }, "*");
          return null;
        }

        return fetchDetailEndpoint("projects", urls.projects)
          .then(function (projects) {
            endpoints.projects = projects;
            if (!projects.ok) errors.push(projects.error || ("projects_http_" + projects.httpStatus));
            return fetchDetailEndpoint("job_preference", urls.job_preference);
          })
          .then(function (jobPreference) {
            if (!jobPreference) return null;
            endpoints.job_preference = jobPreference;
            if (!jobPreference.ok) errors.push(jobPreference.error || ("job_preference_http_" + jobPreference.httpStatus));
            return fetchDetailEndpoint("contact_btn", urls.contact_btn);
          })
          .then(function (contactBtn) {
            if (!contactBtn) return;
            endpoints.contact_btn = contactBtn;
            if (!contactBtn.ok) errors.push(contactBtn.error || ("contact_btn_http_" + contactBtn.httpStatus));

            var basicData = normalizeDetailData(endpoints.basic) || {};
            var detail = Object.assign({}, basicData);
            var projectsData = normalizeDetailData(endpoints.projects);
            var jobPreferenceData = normalizeDetailData(endpoints.job_preference);
            if (projectsData) {
              detail.user_project = projectsData.list || projectsData.items || projectsData.projects || projectsData;
            }
            if (jobPreferenceData) {
              detail.job_preferences = jobPreferenceData;
            }
            if (!detail.id) {
              detail.id = jobId;
            }

            window.postMessage({
              type: "__MAIMAI_DETAIL_FETCH_RESULT__",
              requestId: requestId,
              ok: true,
              jobId: jobId,
              endpoints: endpoints,
              detail: detail,
              errors: errors,
              error: errors.length ? errors[0] : null,
            }, "*");
          });
      });
  });

  console.log("[Maimai Scraper v2] 已安装 — 被动拦截 + 人选列表逐页采集 + 批量详情就绪");
}
