---
name: maimai-talent-search-campaign
description: "根据 JD 或寻访需求生成并执行脉脉人才搜索 campaign。用于根据需求搜索脉脉、制定脉脉寻访实施计划、恢复已有 campaign、启动搜索执行或处理无人值守寻访流程。"
---

# Claude Code Adapter: maimai-talent-search-campaign

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/maimai-talent-search-campaign/SKILL.md`；canonical workflow 位于 `agents/workflows/maimai-unattended-campaign/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/maimai-talent-search-campaign/SKILL.md`，取得需求抽取、搜索合同、默认值、确认点和 workflow 交接规则。
3. Read `agents/workflows/maimai-unattended-campaign/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch / MCP search
   - `web.fetch` -> MCP fetch / reader
   - `browser.operate` -> MCP browser / Playwright
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical skill 和 workflow 执行；本文件不保存业务流程、规则或脚本。
