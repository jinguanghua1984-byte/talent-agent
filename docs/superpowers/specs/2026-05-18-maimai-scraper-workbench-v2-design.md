# 脉脉采集扩展工作台 V2.0 设计

日期：2026-05-18

状态：待用户评审

## 背景

当前 `extensions/maimai-scraper` 采用 Chrome Manifest V3 扩展架构，主要入口是 `action.default_popup = popup.html`。浏览器的 action popup 是短生命周期页面：用户点击业务网页、切换 tab 或切换窗口后，popup 会被销毁；再次打开时，只有已经持久化到 `chrome.storage.local` 或 IndexedDB 的数据能恢复，popup 内存里的选项、日志和局部 UI 状态会丢失。

这正好影响当前使用体验：列表分页日志 `pagerExecutionLogs`、当前 tab、部分进度文案、按钮显隐状态等仍在 `popup.js` 内存中。详情任务比列表任务好一些，因为已有 `detailBatchState`、`detailBatchLogs`、`DetailDB` 和 run token，但整体 UI 仍依赖 popup 周期性拉取。

V2.0 的目标是把 popup 从主工作区降级为入口，把长期可见的控制、进度、日志和导出能力迁移到常驻工作台，同时不改变真实脉脉请求的发起位置。

## 设计前技术验证

本设计先验证现有列表查询与详情请求链路，确认 V2.0 可以只改 UI 和状态层，而不移动真实业务请求。

已验证的人选列表逐页查询链路：

```text
popup.js startPager
  -> background.js startPager / getFullTemplate / pagerFetch
  -> content.js postMessage("__MAIMAI_PAGER_FETCH__")
  -> inject.js 在页面 MAIN world 调用 origFetch.call(window, tpl.url, ...)
```

已验证的人选详情链路：

```text
popup.js startDetailBatch
  -> background.js sendDetailFetch(tab.id, job)
  -> content.js postMessage("__MAIMAI_DETAIL_FETCH__")
  -> inject.js 在页面 MAIN world 调用 fetchDetailEndpoint(...)
```

验证结果：

- 本地 10 个关键 message/fetch marker 契约检查全部通过。
- `node --check` 覆盖 `background.js`、`content.js`、`inject.js`、`autopager.js`、`detail_batch.js`、`popup.js`，全部通过。
- `python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q` 通过，结果 `42 passed`。
- 本机 Chrome 版本为 `148.0.7778.168`，Edge 版本为 `148.0.3967.70`。
- Chrome 官方 Side Panel API 文档说明该 API 用于在浏览器侧边栏承载扩展内容，需要 `"sidePanel"` permission，适用于 Chrome 114+ / MV3+，并支持 `side_panel.default_path`。

本次验证未执行真实脉脉搜索、详情请求、导航、刷新或 CDP 操作。它证明的是：只要 V2.0 保持上述桥接链路不变，就可以在不改变真实请求执行点的前提下改造 UI 和状态层。

## 目标

1. 用常驻工作台替代 popup 承载主流程，用户操作网页或切换窗口后仍能看到采集状态。
2. 重新打开工作台后恢复视图、进度、日志、表单选项和导出状态。
3. 列表分页和详情请求仍由脉脉页面 MAIN world 发起，保持当前可用的登录态和 cookie 上下文。
4. 保留当前“手动搜索 / 被动捕获 / 页面内请求重放 / 导出 JSON”的业务形态。
5. 为后续多渠道或通用 action plugin 预留状态与事件接口，但本次不重构为多渠道插件。

## 非目标

1. 不引入 CDP、Playwright、DevTools 或远程调试。
2. 不自动导航、不刷新脉脉页面、不自动打开业务 URL。
3. 不让 service worker、side panel 或 popup 直接请求脉脉业务接口。
4. 不恢复 `automation.html` 作为正常用户路径。
5. 不改变详情接口列表、分页参数 patch 策略、导出 envelope 或入库流程。
6. 不在 V2.0 中实现 Boss 渠道或多渠道插件迁移。

## 方案选择

推荐方案：Side Panel 主工作台 + 独立扩展 Tab fallback + popup 启动器。

Side Panel 适合承载长期可见的任务状态、日志、导入、导出和停止操作。它是扩展页面，能访问 Chrome API，又不会像 action popup 一样因为用户点击网页而立即销毁。本机 Chrome/Edge 版本满足 API 要求。

独立扩展 Tab 作为 fallback。若浏览器策略、用户设置或某些场景下 side panel 无法打开，`background.js` 使用 `chrome.tabs.create({ url: chrome.runtime.getURL("workbench.html") })` 打开相同工作台页面。这个 fallback 也可用于大屏查看日志。

继续强化 popup 不作为主方案。popup 的生命周期由浏览器控制，无法从根上解决隐藏问题，只能降低状态丢失概率。

## 总体架构

目标结构：

```text
extensions/maimai-scraper/
  manifest.json
  popup.html
  popup.css
  popup.js
  workbench.html
  workbench.css
  workbench.js
  background.js
  content.js
  inject.js
  idb.js
  autopager.js
  detail_batch.js
  automation.html
  automation.js
```

`workbench.html/js/css` 是 V2.0 主 UI。它同时作为 side panel 页面和独立 tab fallback 页面，避免维护两套 UI。

`popup.html/js/css` 缩减为启动器，只显示摘要和入口：

- 打开常驻工作台。
- 显示联系人、详情、任务状态摘要。
- 提供必要的快速导出入口。
- 不承载长任务日志和复杂状态。

`background.js` 继续负责：

- 任务调度。
- 数据汇总。
- 导出。
- 详情 run token。
- 状态持久化。
- 向 UI 广播事件。

`content.js` 继续负责：

- 页面浮窗。
- background 与页面 MAIN world 的消息桥。
- `pagerFetch`、`detailFetch`、`tracePageState` 等页面内桥接。

`inject.js` 继续负责：

- 被动拦截 fetch/XHR。
- 保存搜索模板。
- 在页面 MAIN world 发起分页请求。
- 在页面 MAIN world 发起详情接口请求。

## 请求执行不变量

V2.0 必须满足以下不变量：

1. 人选列表分页请求只能通过 `content.js -> __MAIMAI_PAGER_FETCH__ -> inject.js -> origFetch.call(window, tpl.url, ...)` 发起。
2. 人选详情请求只能通过 `content.js -> __MAIMAI_DETAIL_FETCH__ -> inject.js -> fetchDetailEndpoint(...)` 发起。
3. `workbench.js`、`popup.js`、`background.js` 不得直接 `fetch()` 脉脉业务 URL。
4. `startPager` 和 `startDetailBatch` 仍绑定到已打开的脉脉 tab；如果没有合格 tab，只提示用户手动切到页面，不自动打开或刷新。
5. 任何 UI 重构不得修改 `inject.js` 的请求 URL、headers、credentials 或分页 body patch 策略，除非另开单独搜索 API 校准任务。

这些不变量要写入测试，作为防止 V2.0 破坏请求链路的硬门。

## 状态模型

新增统一工作台状态 `workbenchState`，由 `background.js` 持久化到 `chrome.storage.local`。

```json
{
  "schema_version": 1,
  "active_view": "capture",
  "active_maimai_tab_id": null,
  "last_opened_at": "2026-05-18T00:00:00.000Z",
  "capture": {
    "total_requests": 0,
    "total_contacts": 0,
    "total_details": 0,
    "last_capture_at": null
  },
  "pager": {
    "status": "idle",
    "mode": "all",
    "max_pages": 3,
    "current_page": 0,
    "total_pages": 0,
    "total_from_api": 0,
    "total_contacts": 0,
    "started_at": null,
    "updated_at": null,
    "finished_at": null,
    "last_error": null
  },
  "detail": {
    "state": null,
    "jobs": 0,
    "done": 0,
    "failed": 0,
    "skipped": 0,
    "imported_contacts": 0,
    "last_error": null
  },
  "export": {
    "last_export_type": null,
    "last_export_at": null,
    "last_download_id": null
  }
}
```

日志分开保存：

- `pagerLogs`: 最近 120 条列表分页事件。
- `detailBatchLogs`: 保留现有字段，最近 120 条详情事件。
- `diagnosticTraces`: 保留现有字段。

数据分层：

- `PagerDB` 继续保存分页联系人。
- `DetailDB` 继续保存详情 jobs 和 details。
- `chrome.storage.local` 保存可恢复状态和最近日志。
- `chrome.storage.session` 只可用于非关键 UI 暂态，不得保存恢复必需状态。

## 工作台 UI

工作台包含三个主视图：

1. `capture`：列表采集。
2. `detail`：批量详情。
3. `export`：导出和诊断。

列表采集视图：

- 显示请求数、人选数、详情数。
- 显示搜索模板状态、总数、页大小、请求头名。
- 保留“全部页面 / 前 N 页”选择。
- 提供开始、停止、导出人选列表 JSON。
- 展示 `pagerLogs`，重新打开后仍可见。

批量详情视图：

- 支持导入 JSON。
- 显示任务、完成、失败、跳过。
- 支持开始、终止、导出完整 JSON。
- 展示批间休息、熔断、限流、验证码/登录风险提示。
- 展示 `detailBatchLogs`，重新打开后仍可见。

导出和诊断视图：

- 导出被动拦截 JSON。
- 导出人选列表 JSON。
- 导出完整详情 JSON。
- 查看最近诊断 trace 摘要。
- 提供清空数据入口，保留现有确认弹窗。

工作台不使用营销式首页。打开后第一屏直接展示当前任务状态和主要操作。

## Popup 启动器

popup 只保留轻量摘要：

- 标题和状态 badge。
- 联系人 / 详情 / 当前任务状态。
- `打开工作台`。
- `导出完整 JSON`。
- `刷新摘要`。

点击扩展图标时优先打开 side panel。若失败，打开独立扩展 tab。

popup 不再维护：

- pager 日志数组。
- 长任务进度条状态。
- 复杂 tab 切换状态。
- 详情执行日志。

## Background 消息契约

保留现有消息：

- `getScraperSummary`
- `startPager`
- `stopPager`
- `getPagerStatus`
- `exportPagerJson`
- `importDetailContacts`
- `startDetailBatch`
- `stopDetailBatch`
- `getDetailBatchStatus`
- `exportCaptureJson`
- `exportFullJson`
- `getFullExportData`
- `clearAll`

新增消息：

- `openWorkbench`
- `getWorkbenchSnapshot`
- `setWorkbenchView`
- `appendPagerLog`
- `clearPagerLogs`
- `recordExportResult`

`openMainPage` 兼容保留，但内部应优先委托 `openWorkbench`。页面浮窗点击后打开工作台，而不是强依赖 action popup。

`getWorkbenchSnapshot` 返回：

```json
{
  "ok": true,
  "workbenchState": {},
  "summary": {},
  "pagerLogs": [],
  "detailLogs": []
}
```

UI 启动后先调用 `getWorkbenchSnapshot` 完成首屏恢复，再订阅 `chrome.storage.onChanged` 和 runtime message 做增量刷新。

## 事件与日志

列表分页事件从只发给当前 popup，改为先写持久化日志，再广播给所有 UI。

事件来源：

- `AutoPager.run()` 发出 `pager_progress`、`pager_complete`、`pager_cancelled`、`pager_error`、`pager_paused`。
- `background.js` 将事件转换为 `pagerLogs` 文案并更新 `workbenchState.pager`。
- `workbench.js` 和页面浮窗只渲染状态，不自行推导 canonical state。

详情日志继续使用 `appendDetailBatchLog()`，但工作台统一从 snapshot 和 storage change 恢复，不依赖 popup 打开期间收到的 runtime message。

## 错误处理和恢复

工作台重新打开：

1. 读取 `getWorkbenchSnapshot`。
2. 渲染 `workbenchState.active_view`。
3. 渲染 `pagerLogs` 和 `detailBatchLogs`。
4. 调用 `getScraperSummary` 校准计数。
5. 如果检测到过期批间休息，复用现有 `recoverExpiredBatchPauseIfNeeded()`。

Side Panel 打开失败：

1. `background.js` 捕获 `chrome.runtime.lastError` 或 promise rejection。
2. fallback 到 `chrome.tabs.create({ url: chrome.runtime.getURL("workbench.html") })`。
3. 记录一条 UI 日志：`side_panel_unavailable_fallback_tab`。

没有可用脉脉 tab：

- `startPager` 返回 `请在脉脉页面上使用`。
- `startDetailBatch` 返回 `请在脉脉列表页使用批量详情`。
- UI 显示提示，不自动导航、不刷新。

业务请求失败：

- 继续沿用现有 403/429/401/非 JSON/验证码/权限风险处理。
- 详情连续认证或风控失败仍触发熔断。
- 列表分页失败仍记录页码、重试次数和错误原因。

## Manifest 变更

V2.0 需要：

```json
{
  "permissions": ["storage", "scripting", "downloads", "sidePanel"],
  "side_panel": {
    "default_path": "workbench.html"
  },
  "action": {
    "default_popup": "popup.html",
    "default_title": "脉脉人选数据采集"
  }
}
```

`action.default_popup` 保留用于兼容用户当前习惯。后续如果确认 side panel 体验稳定，可再评估是否让 action 点击直接打开 side panel；V2.0 不强制取消 popup。

## 测试计划

新增测试：

1. `manifest` 包含 `"sidePanel"` permission 和 `side_panel.default_path = "workbench.html"`。
2. `workbench.html` 加载 `workbench.js` 和 `workbench.css`。
3. `popup.js` 包含 `openWorkbench`，不再包含长任务日志数组。
4. `workbench.js` 调用 `getWorkbenchSnapshot` 并订阅 `chrome.storage.onChanged`。
5. `background.js` 提供 `openWorkbench`、`getWorkbenchSnapshot`、`appendPagerLog`。
6. `pager_progress`、`pager_complete`、`pager_error` 会写入 `pagerLogs`。
7. 重新打开 UI 能从 `pagerLogs`、`detailBatchLogs`、`workbenchState` 恢复。
8. `workbench.js` 和 `popup.js` 不直接 fetch 脉脉业务 URL。
9. `background.js` 不新增任何直接 fetch 脉脉业务 URL。
10. 列表请求链路仍包含 `__MAIMAI_PAGER_FETCH__` 和 `origFetch.call(window, tpl.url, ...)`。
11. 详情请求链路仍包含 `__MAIMAI_DETAIL_FETCH__` 和 `fetchDetailEndpoint(...)`。
12. `openWorkbench` side panel 失败时 fallback 到 `chrome.tabs.create(workbench.html)`。

保留现有测试：

- `tests/test_maimai_scraper_extension.py`
- `tests/test_maimai_trace_diff.py`

验证命令：

```bash
node --check extensions/maimai-scraper/background.js
node --check extensions/maimai-scraper/content.js
node --check extensions/maimai-scraper/inject.js
node --check extensions/maimai-scraper/autopager.js
node --check extensions/maimai-scraper/detail_batch.js
node --check extensions/maimai-scraper/popup.js
node --check extensions/maimai-scraper/workbench.js
python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q
git diff --check
```

实现后人工验收只做用户授权的真实页面操作：

1. 用户手动打开脉脉页面并手动搜索一次。
2. 工作台显示已捕获模板和首屏人选。
3. 用户点击列表分页开始，确认新增页请求成功、日志持续更新。
4. 用户导入小样本详情 JSON，在脉脉列表页点击开始详情，确认详情请求成功、日志持续更新。
5. 用户点击网页或切换窗口后，工作台仍保持可见或可恢复。
6. 重新打开扩展后，列表和详情状态不丢。

## 验收标准

V2.0 完成时必须满足：

1. 点击扩展后可打开常驻工作台；side panel 不可用时自动打开独立扩展 tab。
2. popup 关闭、点击网页、切换窗口后，列表分页日志和详情日志不丢。
3. 重新打开工作台能恢复 active view、pager 进度、detail 进度、最近日志和导出状态。
4. 列表分页请求仍在页面 MAIN world 发起。
5. 详情请求仍在页面 MAIN world 发起。
6. 不新增 CDP、自动导航、自动刷新或 service worker 直接业务请求。
7. 所有新增和既有扩展测试通过。
8. `tasks/todo.md` Review 写明验证命令和结果。

## 风险和约束

Side Panel 是 Chrome/Edge 能力，其他 Chromium 变体可能禁用或表现不同，因此必须保留独立 tab fallback。

MV3 service worker 仍可能被挂起。V2.0 不依赖 service worker 内存保存 UI 状态；所有恢复必需状态必须写入 `chrome.storage.local` 或 IndexedDB。

真实脉脉请求是否成功仍取决于页面登录态、模板是否捕获、平台限流和验证码状态。V2.0 只能保证不改变当前已验证的请求发起链路，不能绕过平台风控。

## 实施边界

正式实施计划应按以下顺序拆分：

1. 增加测试保护请求执行不变量。
2. 增加 `workbenchState`、`pagerLogs` 和 snapshot 消息。
3. 新增 `workbench.html/js/css`，先复用现有 popup 功能。
4. 缩减 popup 为启动器。
5. 增加 side panel manifest 和 fallback 打开逻辑。
6. 完成恢复、日志、导出和人工验收。

每一步都应保持现有列表分页和详情链路测试为绿灯。
