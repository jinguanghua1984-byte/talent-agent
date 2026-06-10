# Agent Capabilities Contract

本项目的工作流只描述通用能力，不绑定具体 agent 运行时。

多运行时协作必须先遵守 `docs/dev/agent-collaboration-gates.md`。同一轮代码修改只指定一个主执行者；Claude Code、Codex 和确定性脚本共享 `tasks/`、campaign state/reports、`LLMUsageLedger` 等共享事实源，不能把任一工具的聊天上下文当作事实源。

## Shared Policies

下列 policy 是可复用合同索引；实际必须读取哪些 policy，以具体 workflow 的 Shared Policies/资源索引为准：

- `agents/policies/platform-automation-safety.md`
- `agents/policies/main-db-sync-gates.md`
- `agents/policies/feishu-publish-gates.md`
- `agents/policies/campaign-recovery.md`

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
4. 涉及第三方沟通、发送消息、上传文件、修改账号状态或其他外部副作用时，默认必须有 `human.confirm` 或 workflow 明确的任务级授权边界。
5. 飞书发布/IM 通知窄例外：如果 canonical workflow 明确引用 `agents/policies/feishu-publish-gates.md`，并声明发布目标、manifest dry-run、真实发布、回读和通知失败状态，则 dry-run 与回读通过后的发布/通知链路不再逐动作 `human.confirm`；执行失败必须按 workflow 写恢复证据。
6. 外部执行器窄例外：如果 canonical workflow 明确采用外部执行器，并且用户已给出 campaign/job 级真实执行授权，`shell.run` 可调用受 policy、intent、lock、stop 条件约束的执行器；此时不需要对每个对象再次 `human.confirm`。执行器必须只执行 workflow 指定的原子动作，不能替代 `computer.operate` 做浏览、筛选或上下文判断。
