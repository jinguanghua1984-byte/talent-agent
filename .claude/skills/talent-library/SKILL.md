---
name: talent-library
description: "猎头顾问人才库管理。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、联系方式更新、微信聊天记录同步、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。触发词: 人才库、候选人库、导入人才、查询人才、匹配人才、人才评分、抓取详情、更新联系方式、同步微信聊天、删除人才、talent library、/talent-library"
---

# Claude Code Adapter: talent-library

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/talent-library/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/talent-library/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch 或可用搜索 MCP
   - `web.fetch` -> 可用网页读取 MCP
   - `browser.operate` -> MCP browser / Playwright
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
