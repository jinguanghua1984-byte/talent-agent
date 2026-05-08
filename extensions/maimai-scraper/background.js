importScripts("idb.js", "autopager.js");

// background.js — Service Worker

var pendingSearchCallbacks = {};

chrome.runtime.onMessage.addListener(function (msg, _sender, sendResponse) {
  // 存储捕获的请求数据
  if (msg.type === "capture") {
    chrome.storage.local.get({ captured: [], contacts: [] }, function (r) {
      var requests = r.captured || [];
      requests.push(msg.record);

      // 自动提取 contacts
      var contacts = r.contacts || [];
      var data = msg.record.responseData;
      if (data && data.data) {
        var newContacts = data.data.contacts || data.data.list || data.data.items || [];
        if (newContacts.length > 0) {
          // 按 id 去重
          var existingIds = new Set(contacts.map(function (c) { return c.id; }));
          newContacts.forEach(function (c) {
            if (c.id && !existingIds.has(c.id)) {
              contacts.push(c);
            }
          });
        }
      }

      chrome.storage.local.set({
        captured: requests,
        contacts: contacts,
      });
    });
    sendResponse({ ok: true });
    return true;
  }

  // 搜索结果回调
  if (msg.type === "searchResult") {
    if (pendingSearchCallbacks[msg.requestId]) {
      pendingSearchCallbacks[msg.requestId](msg);
      delete pendingSearchCallbacks[msg.requestId];
    }
    sendResponse({ ok: true });
    return true;
  }

  // DOM 抓取结果回调
  if (msg.type === "domScrapeResult") {
    chrome.storage.local.set({ domScrapeResult: msg });
    sendResponse({ ok: true });
    return true;
  }

  // 获取存储数据
  if (msg.type === "getStoredData") {
    chrome.storage.local.get({ captured: [], contacts: [] }, function (r) {
      sendResponse(r);
    });
    return true;
  }

  // 清除数据
  if (msg.type === "clearAll") {
    chrome.storage.local.set({ captured: [], contacts: [], domScrapeResult: null }, function () {
      sendResponse({ ok: true });
    });
    return true;
  }

  // 导出为 JSON 文件
  if (msg.type === "exportJson") {
    chrome.storage.local.get({ captured: [], contacts: [] }, function (r) {
      var data = {
        exportTime: new Date().toISOString(),
        contacts: r.contacts || [],
        totalContacts: (r.contacts || []).length,
        requests: r.captured || [],
      };
      var jsonStr = JSON.stringify(data, null, 2);
      var url = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
      chrome.downloads.download({
        url: url,
        filename: msg.filename || "maimai-export.json",
        saveAs: true,
      }, function (downloadId) {
        sendResponse({ downloadId: downloadId });
      });
    });
    return true;
  }

  // ---- AutoPager 消息处理 ----

  if (msg.type === "startPager") {
    var tabId = null;
    var responded = false;

    function safeRespond(data) {
      if (!responded) { responded = true; sendResponse(data); }
    }

    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
      if (!tabs[0]) { safeRespond({ ok: false, error: "无活跃标签页" }); return; }
      tabId = tabs[0].id;

      chrome.tabs.sendMessage(tabId, { type: "getFullTemplate" }, function (tplResp) {
        if (chrome.runtime.lastError || !tplResp || !tplResp.template) {
          safeRespond({ ok: false, error: "未捕获搜索模板 — 请先手动搜索一次" });
          return;
        }

        var template = tplResp.template;
        var pageMeta = template.pageMeta || { total: 0, pagesize: 30 };

        PagerDB.clear().then(function () {
          return new Promise(function (resolve) {
            chrome.storage.local.get({ contacts: [] }, function (r) {
              resolve(r.contacts || []);
            });
          });
        }).then(function (existingContacts) {
          return PagerDB.append(existingContacts);
        }).then(function () {
          function sendPageRequest(page) {
            return new Promise(function (resolve, reject) {
              chrome.tabs.sendMessage(tabId, { type: "pagerFetch", page: page }, function (resp) {
                if (chrome.runtime.lastError) {
                  reject(new Error(chrome.runtime.lastError.message));
                  return;
                }
                resolve(resp || { httpStatus: 0, error: "无响应" });
              });
            });
          }

          var pagerState = AutoPager.create(template, pageMeta, sendPageRequest);

          window.__activePager = pagerState;
          window.__pagerTabId = tabId;

          AutoPager.run(pagerState, msg.mode, msg.maxPages, function (event) {
            chrome.runtime.sendMessage(event).catch(function () {});
          });

          safeRespond({ ok: true, totalPages: pagerState.totalPages });
        }).catch(function (err) {
          safeRespond({ ok: false, error: "初始化失败: " + err.message });
        });
      });
    });
    return true;
  }

  if (msg.type === "stopPager") {
    if (window.__activePager) {
      AutoPager.stop(window.__activePager);
      sendResponse({ ok: true });
    } else {
      sendResponse({ ok: false, error: "无正在运行的抓取" });
    }
    return false;
  }

  if (msg.type === "getPagerStatus") {
    var pager = window.__activePager;
    sendResponse(pager ? {
      running: pager.running,
      currentPage: pager.currentPage,
      totalPages: pager.totalPages,
      totalFromApi: pager.totalFromApi,
    } : { running: false });
    return false;
  }

  if (msg.type === "exportPagerJson") {
    PagerDB.getAll().then(function (contacts) {
      return PagerDB.getCount().then(function (count) {
        var pager = window.__activePager || {};
        var data = {
          exportTime: new Date().toISOString(),
          metadata: {
            total_pages: pager.totalPages || 0,
            captured_pages: pager.currentPage || 0,
            total_count: pager.totalFromApi || 0,
            search_params: {
              url: pager.template ? pager.template.url : "",
              method: pager.template ? pager.template.method : "",
            },
          },
          contacts: contacts,
          totalContacts: count,
        };
        var jsonStr = JSON.stringify(data, null, 2);
        var url = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);
        chrome.downloads.download({
          url: url,
          filename: msg.filename || "maimai-pager-export.json",
          saveAs: true,
        }, function (downloadId) {
          sendResponse({ downloadId: downloadId });
        });
      });
    }).catch(function (err) {
      sendResponse({ ok: false, error: err.message });
    });
    return true;
  }
});
