# AGENTS.md

本仓库采用运行时中立的 agent 架构。

## 工作流入口

通用工作流位于 `agents/workflows/<name>/AGENT.md`。运行时适配器必须读取 canonical workflow 后再执行。

## 可执行代码

Python 代码位于 `scripts/`。运行时目录不得保存业务脚本，只能保存入口适配文件。

## 验证

完成改造后运行：

```bash
python -m pytest tests scripts -q
```

## 任务管理

1.  **Plan First**: 非平凡任务先把计划写入 `tasks/todo.md` 的 Active Task。
2.  **Verify Plan**: 实施前确认计划、边界、待修改文件和验证方式。
3.  **Token Governance**: `tasks/todo.md` 是当前工作台，不是长期历史库。默认只保留 Active Task、Open Items、最近 1-3 个 Recent Done 和 Archive Index；完成任务后将完整记录迁移到 `tasks/archive/YYYY-MM.md`。
4.  **Historical Lookup**: 需要历史上下文时，先用 `rg` 在 `tasks/archive/`、`tasks/lessons.md`、`memory/error-log.md` 中按关键词检索，不要默认整段读取历史归档。
5.  **Track Progress**: 执行中持续更新 Active Task 的检查项，不要把无关历史段落纳入本次 diff。
6.  **Explain Changes**: 每个阶段只写高层结果、关键产物和验证证据。
7.  **Document Results**: 完成后在 `tasks/todo.md` 写简短 Review，并把完整任务记录归档。
8.  **Capture Lessons**: 用户纠正或出现非显而易见错误后，按项目规则更新 `tasks/lessons.md` 或 `memory/error-log.md`。

## 沟通

默认使用中文交流；代码注释和文档也使用中文。
