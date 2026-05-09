---
name: screen
description: 候选人筛选评估——将候选人池与JD匹配，打分排序，支持规则进化
---

# Claude Code Adapter: screen

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/screen/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/screen/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
