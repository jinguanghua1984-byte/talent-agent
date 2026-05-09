(function () {
  "use strict";

  // ---- DOM 引用 ----
  var reqCountEl = document.getElementById("req-count");
  var contactCountEl = document.getElementById("contact-count");
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
  function refreshStats() {
    chrome.storage.local.get({ captured: [], contacts: [] }, function (r) {
      reqCountEl.textContent = r.captured.length;
      contactCountEl.textContent = r.contacts.length;
      statusBadge.textContent = r.contacts.length > 0
        ? r.contacts.length + " 联系人"
        : "等待捕获";

      if (r.captured.length > 0) {
        var summary = r.captured.slice(-5).map(function (req) {
          return req.method + " " + req.url.split("?")[0] + " → " + (req.status || "?");
        });
        capturePreview.textContent = summary.join("\n") +
          "\n\n--- 共 " + r.captured.length + " 条请求 ---";
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

    // 优先从 IndexedDB 导出（分页数据），没有则从 chrome.storage 导出
    chrome.runtime.sendMessage({ type: "exportPagerJson", filename: filename }, function (r) {
      if (r && r.downloadId) {
        statusBadge.textContent = "已导出";
      } else {
        // IndexedDB 无数据，回退到 chrome.storage
        chrome.runtime.sendMessage({ type: "exportJson", filename: filename }, function (r2) {
          if (r2 && r2.downloadId) { statusBadge.textContent = "已导出"; }
        });
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
          pagerTemplateInfoEl.textContent = "模板: " + resp.method + " " + resp.url.split("?")[0];
          pagerTemplateInfoEl.className = "hint success";
          pagerMetaInfoEl.textContent = "共 " + total + " 条，每页 " + pagesize + " 条，约 " + totalPages + " 页";
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
  });

  refreshPagerInfo();
  setInterval(refreshPagerInfo, 5000);

  // ---- 初始化 ----
  refreshStats();
  refreshTemplateStatus();

  // 自动刷新（被动拦截模式下每 2 秒更新统计）
  setInterval(refreshStats, 2000);
  setInterval(refreshTemplateStatus, 5000);
})();
