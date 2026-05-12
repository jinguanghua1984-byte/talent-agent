---
name: wechat-chat-sync
description: "微信聊天记录手动同步。用于顾问指定候选人、微信联系人或群名、时间范围，通过 wechat-cli 导出 markdown 聊天记录，并把归档索引写回本地人才库。触发词：同步微信聊天、微信聊天记录、wechat sync、聊天时间线。"
---

# Claude Code Adapter: wechat-chat-sync

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/wechat-chat-sync/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/wechat-chat-sync/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文档不保存业务流程。
