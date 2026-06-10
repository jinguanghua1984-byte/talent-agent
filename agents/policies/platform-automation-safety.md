# Platform Automation Safety Policy

## 适用范围

适用于 BOSS、脉脉、猎聘等需要真实平台页面、CDP、Computer Use 或受限执行器参与的 workflow。

## 通用禁止项

- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 不读取 Chrome cookie、localStorage、sessionStorage、profile、密码或 session store。
- 不构建脱离浏览器登录上下文的纯 HTTP 客户端。
- 不得使用 osascript、坐标点击、截图脚本点击或其它本机自动化替代 workflow 声明的 Computer Use、CDP 既有脚本或其它受控入口。

## Computer Use 边界

Computer Use 边界只适用于 workflow 声明由本地 App UI 或 desktop automation 执行的阶段，尤其 BOSS App 浏览、滚屏、进详情、返回列表、展开详情和筛选判断。此类阶段必须使用 Computer Use / `computer.operate`；如果运行时 Computer Use 缺失，必须停止并写入 `state/continuation-plan.json`，不得用 shell/UI 脚本继续浏览。

## 外部执行器窄例外

外部执行器只能在 workflow 已确认当前详情页、`state/current-contact-intent.json` 和 `executor-policy.json` 均通过后，处理当前详情页的一次 `立即沟通` 原子点击。执行器不得翻列表、找人、筛选、滚屏、读取详情上下文或替代 `computer.operate`。

## CDP 边界

CDP workflow 使用页面内受控请求、页面状态读取或 workflow 既有脚本，不因缺少 Computer Use 停机。CDP 仍必须复用浏览器登录上下文，不得绕过登录、验证码或安全页。脉脉默认 bootstrap 合同包含 `auto_bootstrap_browser_after_plan_confirmation=true`、`data/session/maimai-cdp-profile`、`extensions/maimai-scraper`、`--remote-debugging-port=9888` 和 `http://127.0.0.1:9888`；具体 workflow 可声明自己的 profile、端口和扩展。

## 停机条件

遇到登录失效、验证码、安全页、安全验证、访问异常、权限不足、HTTP 401/403/429/432、非 JSON、模板漂移、页面不匹配、付费弹窗或疑似真实发送风险时，必须停止当前阶段，写 `reports/interruption-*.json`，更新 `state/continuation-plan.json`，并追加事件账本。
