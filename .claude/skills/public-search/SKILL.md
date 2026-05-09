---
name: public-search
description: 公域搜索候选人——根据JD或搜索策略，在公开渠道搜索候选人信息，支持策略归因、多轮迭代和经验沉淀
---

# Claude Code Adapter: public-search

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/public-search/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/public-search/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch 或可用搜索 MCP
   - `web.fetch` -> 可用网页读取 MCP
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
