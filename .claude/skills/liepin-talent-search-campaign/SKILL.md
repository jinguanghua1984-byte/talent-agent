---
name: liepin-talent-search-campaign
description: "猎聘招聘端人才搜索 P0。用于通过已登录猎聘页面执行受控页面内 fetch、保存 raw、标准化摘要和写恢复计划。"
---

# Claude Code Adapter: liepin-talent-search-campaign

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/liepin-talent-search-campaign/SKILL.md`；canonical workflow 位于 `agents/workflows/liepin-unattended-campaign/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/liepin-talent-search-campaign/SKILL.md`，取得业务入口、默认参数、输出 contract、安全边界和 workflow 交接规则。
3. Read `agents/workflows/liepin-unattended-campaign/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `browser.operate` -> Browser/Chrome 页面操作
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical skill 和 workflow 执行；不得读取浏览器敏感存储，不得绕过平台验证，不得写主人才库。
6. 本文件不保存业务流程、规则或脚本。
