| 日期 | 错误 | 根因 | 修复 |
| --- | --- | --- | --- |
| 2026-05-09 | `python scripts/score_pipeline.py --help` 报 `ModuleNotFoundError: No module named 'scripts.jd_analyzer'` | 以文件路径直跑脚本时，`sys.path[0]` 是 `scripts/`，项目根目录未进入导入路径，导致 `from scripts...` 绝对导入失败 | 在 `scripts/score_pipeline.py` 入口导入前，当 `__package__` 为空时把项目根目录加入 `sys.path` |
| 2026-05-10 | Codex Chrome Extension 两次 `browser.user.openTabs()` 连接超时 | Chrome、扩展安装状态和 native host 均正常，但 extension backend 握手无响应；无法继续使用内置 Chrome 插件做页面级调试 | 按 Chrome 插件流程打开同 Profile 新窗口后重试仍超时，后续应从 Codex 插件 UI 重装 Chrome 插件或修复 backend 通信链路 |
| 2026-05-11 | `maimai-scraper` 批量详情 42 条任务停在 30 且日志无说明 | safe 模式 `batchSize=30` 会批间休息 5-10 分钟，但旧日志只写 `batch_pause`，状态仍显示 running；429 也未纳入风控失败判断 | 持久化批间休息窗口并在 background/popup/悬浮球显示预计恢复时间；记录单个 job 失败接口状态；429 纳入风控/限流判断 |
| 2026-05-11 | `maimai-scraper` 自动翻页抓取总数不对 | 真实脉脉搜索请求的分页字段在 `search.paginationParam.page/size`，旧重放逻辑只改顶层 `body.page/pageNum/pageNo`；模板也没有展示请求头或按响应持续回写总数 | 新增分页元信息提取和嵌套分页写入；回传并展示请求头名；每页响应后更新 `totalFromApi/pagesize/totalPages` |
| 2026-05-11 | 批量详情状态进度更新但实时请求日志仍只显示导入日志 | `DetailBatch.run()` 发出的事件没有等待 `appendDetailBatchLog()` 完成，多个事件并发读写 `chrome.storage.local.detailBatchLogs` 时读-改-写互相覆盖 | 将 `emit()` 改为 async，并对所有批量详情事件 `await emit(...)`，串行化日志写入 |
