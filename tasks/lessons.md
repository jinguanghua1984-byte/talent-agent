# Lessons

- 2026-05-11：用户询问“方案文档是否设计完整”时，评审对象是文档的需求覆盖、架构闭环、风险与验收标准，不等同于检查代码是否已经实现；只有用户明确问“是否落地/是否实现/代码状态”时才切到实现核对。
- 2026-05-10：生成包含中文的报告时，不要把中文固定文案直接写进 PowerShell here-string 再交给 Python；该链路可能把非 ASCII 文案写成 `?`。应使用 UTF-8 文件模板、`apply_patch`，或在脚本中用 Unicode 转义构造文案，并用 `utf-8-sig` 写出面向 Windows 查看器的 Markdown。
- 2026-05-10：即使最终用 Python `utf-8-sig` 写文件，只要 Python 源码本身来自 PowerShell here-string 的中文字面量，仍可能提前乱码；面向用户的中文 Markdown 固定文案必须改用 `apply_patch` 模板或 Python Unicode 转义，并在写后读取首行校验。
- 2026-05-10：Chrome 扩展的 match pattern `*://maimai.cn/*` 不覆盖 `www.maimai.cn` 等子域。脉脉详情页捕获异常为 0 时，先检查 `host_permissions` 和 `content_scripts.matches` 是否包含 `*://*.maimai.cn/*`，再让用户重载扩展和刷新页面。
- 2026-05-10：Chrome 扩展重载后，旧页面中的 content script 会残留并抛 `Extension context invalidated`。修改扩展时要提示用户重载扩展后刷新业务页面；content script 中所有 `chrome.runtime.sendMessage` 也要包一层 try/catch 和 `chrome.runtime.id` 检查。
- 2026-05-10：`maimai-scraper` 的导出按钮如果优先走 IndexedDB 分页导出，会把被动拦截的详情请求漏掉；详情补全必须使用完整导出，同时包含 `contacts`、`details`、`requests`。清除数据也必须同步清 `PagerDB`，否则旧联系人列表会抢占导出结果。
