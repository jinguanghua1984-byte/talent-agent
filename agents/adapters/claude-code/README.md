# Claude Code Adapter

Claude Code 通过 `.claude/skills/*/SKILL.md` 进入工作流。每个 Skill 文件只负责：

1. 保留 Claude Code 需要的 frontmatter。
2. 读取对应的 `agents/workflows/<name>/AGENT.md`。
3. 按 `agents/capabilities.md` 将通用能力映射到 Claude Code 工具。

Claude Code 私有配置保留在 `.claude/settings.local.json`，不进入通用规范层。
