# Agent Capabilities Contract

本项目的工作流只描述通用能力，不绑定具体 agent 运行时。

| 通用能力 | 语义 | Claude Code 映射 | Codex 映射 |
| --- | --- | --- | --- |
| `file.read` | 读取项目内文本文件 | Read | shell / filesystem |
| `file.write` | 创建或更新项目内文本文件 | Write / Edit | apply_patch |
| `shell.run` | 执行本地命令 | Bash | shell_command |
| `web.search` | 搜索公开网页 | WebSearch / MCP search | web search / browser skill |
| `web.fetch` | 抓取网页正文 | MCP fetch / reader | web open / browser skill |
| `browser.operate` | 操作本地浏览器或调试端口 | MCP browser / Playwright | browser plugin / Playwright |
| `computer.operate` | 操作本地 App UI，例如读取屏幕、点击、滚动、输入、返回 | Computer Use / desktop automation | Computer Use |
| `human.confirm` | 需要用户确认后继续 | 直接询问用户 | 直接询问用户 |

工作流规则：

1. `agents/workflows/*/AGENT.md` 只使用上表中的通用能力名称。
2. 运行时私有工具名称只能出现在 `agents/adapters/*` 或对应运行时目录中。
3. 可执行 Python 代码必须放在项目根目录 `scripts/` 包内，不能放在运行时私有目录中。
4. 涉及第三方沟通、发送消息、上传文件、修改账号状态或其他外部副作用时，`computer.operate` 必须先经过 `human.confirm` 动作级确认。
5. 窄例外：如果 canonical workflow 明确采用外部执行器，并且用户已给出 campaign/job 级真实执行授权，`shell.run` 可调用受 policy、intent、lock、stop 条件约束的执行器；此时不需要对每个对象再次 `human.confirm`。执行器必须只执行 workflow 指定的原子动作，不能替代 `computer.operate` 做浏览、筛选或上下文判断。
