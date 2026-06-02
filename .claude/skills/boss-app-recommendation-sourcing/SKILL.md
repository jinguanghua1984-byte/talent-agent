---
name: boss-app-recommendation-sourcing
description: "BOSS App 推荐列表寻访。用于通过 Computer Use 操作本机 BOSS App 采集推荐列表和详情，记录 would-contact；在 campaign 级授权后调用外部执行器点击立即沟通，并回采真实姓名。"
---

# Claude Code Adapter: boss-app-recommendation-sourcing

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/boss-app-recommendation-sourcing/SKILL.md`；canonical workflow 位于 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/boss-app-recommendation-sourcing/SKILL.md`，取得业务入口、默认参数、输出 contract、安全边界和 workflow 交接规则。
3. Read `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `computer.operate` -> Computer Use
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical skill 和 workflow 执行；当 workflow 指定外部执行器且 campaign 级授权成立时，`shell.run` 可直接调用执行器，不逐人询问。
6. 本文件不保存业务流程、规则或脚本。
