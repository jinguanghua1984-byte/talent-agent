# Claude Code + Codex 协作门禁

本门禁用于同时使用 Claude Code、Codex 和确定性脚本时的任务分工、写入隔离、共享事实源和合并前记录。目标是减少重复读取、重复推理和并行覆盖。

## 默认分工

| 工具 | 适合任务 | 不建议承担 |
| --- | --- | --- |
| Claude Code | 长上下文项目理解、workflow/skills/任务状态审查、跨目录规划、安全门禁、最终合并前审查 | 大量局部样板代码生成、与其他 agent 并行改同一目录 |
| Codex | 局部脚本实现、单文件/少文件代码补全、测试失败修复、小范围重构草案 | 需要读取大量项目约束、涉及 dry-run/apply 授权、飞书发布、主库写入门禁的任务 |
| 确定性脚本 | 状态摘要、schema 校验、diff 检查、成本 dry-run、next-action 判断 | 需要自然语言判断、候选人推荐理由、复杂权衡的任务 |

## 启动前主执行者门禁

同一轮代码修改只指定一个工具负责最终落地。另一个工具最多提供只读审查、局部 patch 草案或测试失败修复建议。

启动前必须写清：

- 主执行者：Claude Code、Codex 或确定性脚本。
- 任务目标：本轮要完成的行为边界。
- 写入范围：允许修改的目录和文件。
- 禁止事项：不得触发的平台动作、DB 写入、发布动作或授权外操作。
- 验证命令：聚焦测试、全量测试和必要的 dry-run。

如果任务涉及主库同步、Campaign DB apply、飞书发布或外部平台沟通，主执行者只能执行项目 workflow 明确允许的脚本命令，并保留人工授权证据。

## 写入隔离

大任务默认使用独立 branch / worktree。不得让两个 agent 同时改同一目录、同一 migration、同一 workflow 文档或同一 DB 写入脚本。

允许并行的情况：

- 一个工具只读审查，另一个工具写代码。
- 一个工具改脚本，另一个工具只跑测试并回报失败证据。
- 两个工具处理完全不相交的目录，并在任务台写明边界。

不允许并行的情况：

- 两个 agent 同时改 `scripts/` 中同一业务入口。
- 两个 agent 同时改同一 canonical workflow 或 adapter。
- 一个工具在另一个工具未收尾时执行主库、Campaign DB 或飞书相关写操作。

## 共享事实源

多工具协作时，不能把任一工具的聊天上下文当作事实源。共同事实源必须是 repo 内可审计 artifact：

- `tasks/todo.md`：当前 Active Task、边界、检查项和短 Review。
- `tasks/archive/`：已完成任务的完整记录。
- campaign `state` / `ledger` / `reports`：平台寻访进度、恢复点和质量门禁。
- `data/talent.db` 以及 dry-run/apply 报告：人才库变更事实。
- `LLMUsageLedger`：跨 provider 的成本、usage、prompt hash 和估算来源。
- `campaign_status summarize` 和 `next-action`：长任务恢复与下一步判断入口。

跨工具交接时必须生成短交接包，至少包含：

- 目标
- 已改文件
- 剩余风险
- 验证命令
- 禁止事项
- 下一步合法命令

## 外部副作用门禁

涉及主库同步、Campaign DB apply、飞书发布、外部平台沟通、发送消息、上传文件、修改账号状态等动作时，只认项目脚本和人工授权，不认任一 agent 的上下文判断。

执行前必须满足：

- workflow 或 skill 明确允许该动作。
- dry-run、质量门禁或 readback 要求已经通过。
- `tasks/todo.md` 或对应 campaign state 中记录授权边界。
- 命令参数包含项目定义的确认文本或 policy 文件。

执行后必须落盘：

- 命令输出摘要。
- 写入的本地或云端 artifact。
- 回读验证证据。
- 失败时的 blocked reason 和 continuation plan。

## 合并前记录

合并、提交或交接前必须记录：

- 哪个工具改了哪些文件。
- 基于哪个任务摘要执行。
- 验证命令是什么，输出结果是什么。
- 是否有未解决风险。
- 是否存在未归档的 Active Task。

Codex 产出的 patch 进入主线前，应由 Claude Code 或确定性脚本统一跑格式、测试、diff review 和项目门禁。Claude Code 产出的跨目录改动进入主线前，也必须用同样证据记录。
