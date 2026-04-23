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

## 搜索流程

### 1. 定位搜索 iframe

搜索页在 iframe 中加载，路径包含 `/web/frame/search/`。

```python
for frame in page.frames:
    if "/web/frame/search/" in frame.url and "about:" not in frame.url:
        search_frame = frame
```

超时: 15 次轮询，每次 0.5s（共 7.5s）。

### 2. 填入关键词

定位 `.input-text` 输入框 → click → 清空 → type(query, delay=50)。

### 3. 触发搜索

优先点击 `.icon-search` 图标，找不到时回退到 Enter 键。

### 4. 拦截响应

在 **page 级别**（不是 frame 级别）注册 response listener：
- 过滤 URL 包含 `geeks.json` 且不含 `t.zhipin.com`
- 校验 `page` 和 `keywords` 参数匹配
- 超时: 20 次轮询，每次 0.5s（共 10s）

### 5. 解析结果

响应 body 结构: `{ zpData: { geeks: [{ geekCard: {...} }], totalCount, hasMore } }`

取 `geeks[].geekCard` 作为搜索结果项。

## 分页

与脉脉相同，通过 page 参数控制分页。
每次翻页重新触发搜索并拦截对应 page 的响应。

## 与脉脉的对比

| 维度 | 脉脉 | Boss 直聘 |
|------|------|----------|
| 搜索方式 | 主动 API 调用 (page.evaluate(fetch)) | 被动拦截 (page.on('response')) |
| 页面操作 | 创建新页面 → goto → fetch | 复用已有页面 → iframe 内输入 |
| 反爬风险 | 低（自有 API） | 高（不能 new_page / fetch） |
| 前提条件 | Chrome 打开任意页面 | Chrome 打开 zhipin.com 且已登录 |
| 结果位置 | API 响应直接返回 | geekCard 嵌套在 geeks 数组中 |
| 筛选参数 | 在 fetch URL 中拼接 | 在搜索页 UI 中设置（当前未实现） |

## 已知限制

1. **session.py verify 风险**: `session.py verify --mode cdp` 会 `new_page()` + `goto()`，
   可能触发 Boss 反检测。Boss 的前置检查应优先检查 Chrome 是否已有 zhipin.com 页面，
   而非主动访问。
2. **筛选参数未暴露**: search.py CLI 未暴露 city/education/work_years 参数，
   Boss 的 build_search_params() 虽然支持这些字段但当前未被使用。
3. **分页翻页**: 当前每次翻页需要重新填入关键词并点击搜索，效率较低。