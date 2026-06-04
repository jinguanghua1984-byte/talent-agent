---
name: boss-maimai-cross-channel-delivery
description: "BOSS App 已筛优质人选补脉脉主页匹配、多渠道 Campaign DB 整合、主库同步和 JD/飞书交付。"
---

# Claude Code Adapter: boss-maimai-cross-channel-delivery

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`；canonical workflow 位于 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`，取得 BOSS primary、脉脉 supplement、身份匹配、Campaign DB clean、主库授权和自动交接规则。
3. Read `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `browser.operate` -> Browser/Computer Use
   - `computer.operate` -> Computer Use
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical skill 和 workflow 执行；主库 apply 前必须核对 `reports/main-db-sync-dry-run.json`、一次总授权和 `CONFIRM_SYNC_TEXT`。
6. 本文件不保存业务流程、规则或脚本，只负责运行时适配。
