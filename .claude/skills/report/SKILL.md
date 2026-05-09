---
name: report
description: 生成推荐报告——将筛选后的候选人整理为面向客户的推荐文档，支持版本迭代
---

# Claude Code Adapter: report

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/report/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/report/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
