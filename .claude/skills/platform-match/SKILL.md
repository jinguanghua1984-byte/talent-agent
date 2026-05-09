---
name: platform-match
description: "招聘平台候选人搜索与信息丰富。在脉脉、Boss直聘等招聘平台上搜索候选人，丰富候选人库信息，或根据 JD/条件搜索目标人选。触发词: 匹配候选人、搜索脉脉、搜索Boss、平台找人、丰富候选人、platform match、/platform-match"
---

# Claude Code Adapter: platform-match

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/platform-match/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/platform-match/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch 或可用搜索 MCP
   - `web.fetch` -> 可用网页读取 MCP
   - `browser.operate` -> MCP browser / Playwright
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
