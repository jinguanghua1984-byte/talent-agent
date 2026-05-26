# Claude Code Adapter

Claude Code 通过 `.claude/skills/*/SKILL.md` 进入工作流。每个 Skill 文件只负责：

1. 保留 Claude Code 需要的 frontmatter。
2. 如果存在对应的 `agents/skills/<name>/SKILL.md`，先读取 canonical skill contract。
3. 读取对应的 `agents/workflows/<name>/AGENT.md`；如果 skill 名称和 workflow 名称不同，按 adapter 中声明的 workflow 路径读取。
4. 按 `agents/capabilities.md` 将通用能力映射到 Claude Code 工具。

Claude Code 私有配置保留在 `.claude/settings.local.json`，不进入通用规范层。
