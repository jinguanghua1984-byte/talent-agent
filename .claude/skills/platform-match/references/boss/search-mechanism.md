# Boss 直聘搜索机制

## 概述

Boss 直聘采用**被动网络拦截**方式获取搜索结果，与脉脉的主动 API 调用完全不同。

核心差异：不在代码中发起 fetch 请求，而是模拟用户在搜索框输入关键词，
通过 `page.on('response')` 拦截浏览器发出的 geeks.json 响应。

## 前提条件

1. Chrome 已通过 `--remote-debugging-port=9222` 启动
2. **已有一个 Boss 直聘页面打开且处于登录状态**（zhipin.com）
3. 页面需处于人才搜索页（/web/frame/search/ iframe 可用）

**不能 `context.new_page()`** — 会触发 browser-check.min.js 导致强制登出。
**不能 `page.evaluate(fetch)`** — 会触发反爬检测导致强制登出（code: 7）。
**不能 `page.goto('/web/geek/{id}')`** — 导航到候选人详情页同样触发 browser-check.min.js 导致强制登出。

## 正确的页面 URL

Boss 端人才搜索页是 `/web/chat/search`（非 `/web/recruit/geek-search`，该路径返回 404）。
搜索 iframe 路径为 `/web/frame/search/`，嵌套在 `/web/chat/search` 页面内。

## 搜索流程

### 0. 清空职位筛选

搜索栏有两个前置筛选条件：**职位筛选**和**城市筛选**。
职位筛选默认有值（如"AI Infra训练和推理研发"），不清空会导致搜索结果为空。

```python
job_filter = await search_frame.query_selector(".search-current-job")
if job_filter:
    current_text = (await job_filter.inner_text()).strip()
    if current_text and current_text != "不限职位":
        await job_filter.click()       # 打开下拉
        await asyncio.sleep(0.5)
        items = await search_frame.query_selector_all('li[ka="search_select_job"]')
        if items:
            await items[0].click()    # 点击"不限职位"
            await asyncio.sleep(0.5)
```

### 1. 定位搜索 iframe

搜索页在 iframe 中加载，路径包含 `/web/frame/search/`。

```python
for frame in page.frames:
    if "/web/frame/search/" in frame.url and "about:" not in frame.url:
        search_frame = frame
```

超时: 15 次轮询，每次 0.5s（共 7.5s）。

### 2. 填入关键词

**注意：关键词输入框是 `.search-input`，不是 `.input-text`。**

`.input-text` 是另一个筛选条件的输入框（位于关键词框右侧），选错会导致搜索关键词与 API 请求不匹配。

清空方式必须是 `Control+a` → `Backspace`，不能用 `fill("")`（Vue 组件不响应 fill）。

```python
keyword_input = await search_frame.query_selector(".search-input")
await keyword_input.click()
await asyncio.sleep(0.3)
await keyword_input.press("Control+a")
await asyncio.sleep(0.1)
await keyword_input.press("Backspace")
await asyncio.sleep(0.3)
await keyword_input.type(query, delay=100)
```

### 3. 触发搜索

优先点击 `.icon-search` 图标，找不到时回退到 Enter 键。

### 4. 拦截响应

在 **page 级别**（不是 frame 级别）注册 response listener：
- 过滤 URL 包含 `geeks.json` 且不含 `t.zhipin.com`
- 校验 `page` 和 `keywords` 参数匹配
- 超时: 20 次轮询，每次 0.5s（共 10s）
- **response.json() 是异步方法**，在同步 on_response 回调中不能 await，
  需要在回调外保存 response 对象，后续再 await

### 5. 解析结果

响应 body 结构: `{ zpData: { geeks: [{ geekCard: {...} }], totalCount, hasMore } }`

取 `geeks[].geekCard` 作为搜索结果项。

## 分页（滚动翻页）

Boss 直聘搜索结果使用**无限滚动加载**，没有分页按钮。

翻页方式：滚动到搜索 iframe 底部，触发加载下一页，拦截新的 geeks.json 响应。

```python
await search_frame.evaluate('window.scrollTo(0, document.body.scrollHeight)')
await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
await asyncio.sleep(2)
```

检测结束条件：
1. `hasMore === False` — API 返回无更多数据
2. 连续 3 次滚动后无新数据 — 滚动到底部

每次翻页 geeks.json 的 `page` 参数自动递增，响应中 `hasMore` 为 `False` 时表示已到最后一页。

## 与脉脉的对比

| 维度 | 脉脉 | Boss 直聘 |
|------|------|----------|
| 搜索方式 | 主动 API 调用 (page.evaluate(fetch)) | 被动拦截 (page.on('response')) |
| 页面操作 | 创建新页面 → goto → fetch | 复用已有页面 → iframe 内输入 |
| 反爬风险 | 低（自有 API） | 高（不能 new_page / fetch / goto 详情页） |
| 前提条件 | Chrome 打开任意页面 | Chrome 打开 zhipin.com 且已登录 |
| 结果位置 | API 响应直接返回 | geekCard 嵌套在 geeks 数组中 |
| 筛选参数 | 在 fetch URL 中拼接 | 用户在搜索页 UI 手动设置 |
| 分页方式 | page 参数 | 滚动加载（无限滚动） |
| 正确页面 | 任意 | /web/chat/search（非 /web/recruit/geek-search） |
| 关键词选择器 | N/A | `.search-input`（非 `.input-text`） |

## 已知限制

1. **session.py verify 风险**: `session.py verify --mode cdp` 会 `new_page()` + `goto()`，
   可能触发 Boss 反检测。Boss 的前置检查应优先检查 Chrome 是否已有 zhipin.com 页面，
   而非主动访问。
2. **筛选参数**: Boss 搜索页的筛选条件（城市、学历、经验、薪资等）只能由用户在 UI 手动设置，
   代码中无法安全地操作这些筛选器（已知城市筛选和职位筛选的 DOM 交互有风险）。
   推荐流程：用户手动设置筛选条件 → 代码只负责输入关键词和翻页。
3. **get_detail 不可用**: 导航到 `/web/geek/{id}` 会触发 browser-check.min.js → 强制登出。
   侧边面板（`.geek-detail`）仅显示摘要信息（姓名、年龄、学历、一段经历、一段教育），
   不含完整简历。搜索 API 的 geekCard 已包含大部分可用字段（工作经历列表、教育、技能标签等），
   可满足 `enrichment_level: "partial"` 的入库需求。
4. **职位筛选默认有值**: 每次搜索前必须清空职位筛选（选"不限职位"），
   否则搜索结果会被限制在当前选中的职位范围内，可能导致 0 结果。
