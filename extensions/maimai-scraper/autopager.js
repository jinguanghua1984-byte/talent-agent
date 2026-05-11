// autopager.js — 自动分页调度
// 不直接 fetch，通过 background → content → inject 消息链在 MAIN world 中执行请求

var AutoPager = (function () {
  var DEFAULT_MIN_INTERVAL = 3000;
  var DEFAULT_MAX_INTERVAL = 8000;
  var MAX_RETRIES = 3;

  function create(template, pageMeta, sendPageRequest) {
    var total = pageMeta.total || 0;
    var pagesize = pageMeta.pagesize || 30;
    var totalPages = Math.ceil(total / pagesize) || 1;

    return {
      template: template,
      totalPages: totalPages,
      currentPage: 0,
      totalFromApi: total,
      pagesize: pagesize,
      running: false,
      aborted: false,
      sendPageRequest: sendPageRequest,
      onResponse: null,
    };
  }

  function firstNumber(values, fallback) {
    for (var i = 0; i < values.length; i++) {
      var value = Number(values[i]);
      if (Number.isFinite(value) && value > 0) return value;
    }
    return fallback;
  }

  function updatePageMetaFromResponse(state, result) {
    var data = result && result.data && result.data.data ? result.data.data : {};
    var pageMeta = result && result.pageMeta ? result.pageMeta : {};
    var contacts = extractContacts(result && result.data);
    var pagesize = firstNumber([
      pageMeta.pagesize,
      data.pagesize,
      data.pageSize,
      data.limit,
      data.size,
      data.count,
      contacts.length,
    ], state.pagesize || 30);
    var total = firstNumber([
      pageMeta.total,
      data.total,
      data.total_match,
      data.totalCount,
      data.total_count,
    ], state.totalFromApi || contacts.length || 0);
    state.pagesize = pagesize;
    state.totalFromApi = total;
    state.totalPages = Math.ceil(total / pagesize) || state.totalPages || 1;
    return state;
  }

  function randomDelay(min, max) {
    var delay = min + Math.random() * (max - min);
    delay *= (1 + (Math.random() - 0.5) * 0.6);
    return new Promise(function (resolve) { setTimeout(resolve, delay); });
  }

  async function run(state, mode, maxPages, onResponse) {
    state.running = true;
    state.aborted = false;
    state.onResponse = onResponse || function () {};

    var targetPages = mode === "all"
      ? state.totalPages
      : Math.min(maxPages || 1, state.totalPages);

    state.currentPage = 1;

    while (state.currentPage < targetPages && !state.aborted) {
      await randomDelay(DEFAULT_MIN_INTERVAL, DEFAULT_MAX_INTERVAL);
      if (state.aborted) break;

      var nextPage = state.currentPage + 1;
      var retries = 0;
      var success = false;
      var result = null;

      while (retries < MAX_RETRIES && !success && !state.aborted) {
        try {
          result = await state.sendPageRequest(nextPage);
          if (result.httpStatus === 200 && result.data) {
            success = true;
          } else if (result.httpStatus === 403) {
            state.onResponse({
              type: "pager_paused",
              reason: "403 Forbidden — 可能触发验证码",
              page: nextPage,
            });
            await randomDelay(30000, 60000);
            retries++;
          } else {
            retries++;
            if (retries < MAX_RETRIES) {
              await randomDelay(5000 * retries, 15000 * retries);
            }
          }
        } catch (err) {
          retries++;
          if (retries < MAX_RETRIES) {
            await randomDelay(5000 * retries, 15000 * retries);
          }
        }
      }

      if (!success) {
        state.onResponse({
          type: "pager_error",
          reason: "重试 " + MAX_RETRIES + " 次后仍失败",
          page: nextPage,
        });
        break;
      }

      updatePageMetaFromResponse(state, result);
      targetPages = mode === "all"
        ? state.totalPages
        : Math.min(maxPages || 1, state.totalPages);

      var contacts = extractContacts(result.data);
      if (contacts.length > 0) {
        await PagerDB.append(contacts);
      }

      state.currentPage = nextPage;

      state.onResponse({
        type: "pager_progress",
        currentPage: state.currentPage,
        totalPages: targetPages,
        totalFromApi: state.totalFromApi,
        contactsInPage: contacts.length,
        totalContacts: await PagerDB.getCount(),
      });
    }

    state.running = false;

    state.onResponse({
      type: state.aborted ? "pager_cancelled" : "pager_complete",
      currentPage: state.currentPage,
      totalPages: targetPages,
      totalFromApi: state.totalFromApi,
      totalContacts: await PagerDB.getCount(),
    });
  }

  function extractContacts(data) {
    if (!data || !data.data) return [];
    return data.data.contacts || data.data.list || data.data.items || [];
  }

  function stop(state) {
    state.aborted = true;
    state.running = false;
  }

  return { create: create, run: run, stop: stop };
})();
