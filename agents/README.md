# Talent Agent Runtime-Neutral Architecture

`agents/` 是 Talent Agent 的规范层，定义所有 agent 都能执行的工作流、工具能力契约和运行时适配方式。

## 目录

- `capabilities.md`：通用能力名称与各运行时工具映射。
- `workflows/`：运行时中立的业务工作流。
- `adapters/`：面向具体 agent 运行时的适配说明。

## 分层约定

1. 业务流程写在 `agents/workflows/<name>/AGENT.md`。
2. 可执行逻辑写在 `scripts/`。
3. 配置和规则写在 `rules/`、`schemas/`、`data/search-strategies/`。
4. 运行时目录只做入口适配，例如 `.claude/skills/*/SKILL.md`。
