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

---

# talent-library Skill 实施清单（2026-05-10）

> 当前状态：**已完成**
> 设计文档：`docs/superpowers/specs/2026-05-10-talent-library-skill-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-10-talent-library-skill.md`

## 任务清单

- [x] Task 1：增加 `DeleteResult` 数据模型
- [x] Task 2：增加 `TalentDB.update_candidate()`
- [x] Task 3：增加 `TalentDB.delete_candidate()`
- [x] Task 4：新增 `agents/workflows/talent-library` canonical workflow
- [x] Task 5：新增 `.claude/skills/talent-library` 适配器和架构测试
- [x] Task 6：全量验证

## Review

- 基线测试：`python -m pytest tests/test_talent_db.py -q`，结果 **115 passed**。
- 数据层聚焦测试：`python -m pytest tests/test_talent_models.py::test_delete_result_total_related_rows tests/test_talent_db.py::test_update_candidate_updates_allowed_fields_without_losing_sources tests/test_talent_db.py::test_update_candidate_rejects_unknown_fields tests/test_talent_db.py::test_update_candidate_rejects_missing_candidate tests/test_talent_db.py::test_delete_candidate_removes_candidate_and_related_rows tests/test_talent_db.py::test_delete_candidate_rejects_missing_candidate tests/test_talent_db.py::test_delete_candidate_removes_vector_when_available -q`，结果 **7 passed**。
- Workflow/adapter 测试：`python -m pytest tests/test_agent_architecture.py tests/test_talent_library_workflow.py -q`，结果 **9 passed**。
- 全量测试：`python -m pytest tests scripts -q`，结果 **367 passed, 1 warning**。
- 架构扫描：``rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows``，结果 **无输出**。
