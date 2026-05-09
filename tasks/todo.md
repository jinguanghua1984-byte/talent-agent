# 通用 Agent 项目架构改造执行清单（2026-05-09）

> 来源计划：`docs/superpowers/plans/2026-05-09-general-agent-architecture.md`
> 当前状态：**已完成**

## 任务清单

- [x] Task 1：建立运行时中立的 agent 规范层 — commit `42419d3`
- [x] Task 2：将 `platform-match` 可执行代码迁出 `.claude` — commit `0c93bf8`
- [x] Task 3：统一资源、规则和路径解析 — commit `28f1829`
- [x] Task 4：增加通用 LLM provider 抽象 — commit `ef3fdb2`
- [x] Task 5：让评分 pipeline 支持 provider/model 参数 — commit `a1d27a5`
- [x] Task 6：薄化 `.claude/skills` 为兼容 adapter — commit `f59119b`
- [x] Task 7：迁移 `public-search` token tracker — commit `a9d3d8b`
- [x] Task 8：更新 README、环境变量和依赖说明 — commit `f4a0e5e`
- [x] Task 9：全量验证与架构扫描 — commit `8ee80b3`

## Review

- 全量测试：`python -m pytest tests scripts -q`，结果 **356 passed**
- 架构扫描：`rg -n "\.claude" scripts agents/workflows rules README.md`，结果仅 `README.md:30`（适配器描述，符合预期）
- Canonical workflow 私有工具扫描：`rg -n "Claude Code|WebSearch|mcp__" agents/workflows`，结果 **无输出**（已清理）
- CLI smoke：`python scripts/score_pipeline.py run --help`，结果包含 `--provider` 和 `--model`
