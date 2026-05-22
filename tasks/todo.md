# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- [x] JD-driven 脉脉 campaign 通用化实施（2026-05-22）：执行 `docs/superpowers/plans/2026-05-22-maimai-jd-campaign-generalization.md`，修复 AI Infra 样板残留、公司/产品线映射、通用计划/评分/交付/反馈闭环。
  - [x] Task 1：修复 query-only 搜索模板过滤残留。
  - [x] Task 2-3：实现公司/产品线 registry 与通用 search-plan 编译。
  - [x] Task 4-6：实现通用 ranking、delivery report、feedback contract。
  - [x] Task 7-8：补混元 guardrail、聚焦/全量回归和 Review。

## Open Items

- 当前无主动执行中的开放任务；下一次任务开始时在这里写计划。

## Recent Done

- 2026-05-22：已开始核查通用化改造后 AI Infra schema 残留问题，并记录 lesson。
- 2026-05-22：已核对混元数据策略负责人 campaign 的 JD、requirements、strategy、search-units、wave plan、live plan 和执行 raw 证据，未修改 campaign 计划。
- 2026-05-22：已形成并执行 todo token 治理实施计划，详见 `docs/superpowers/plans/2026-05-22-todo-governance.md`。
- 2026-05-21：混元大模型数据策略负责人脉脉寻访继续执行已完成，完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-21：飞书 Wiki JD requirements export、混元寻访计划等已归档，完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`

## Review

- 本轮调查中，重点区分“搜索执行真实使用的计划”和“后续评分/交付复用的通用脚本 schema”，避免把 AI Infra 样板残留误判成单点文案错误。
- 本轮完成解释性核查和实施计划设计，未改 `data/campaigns/hunyuan-data-strategy-lead-2026-05-21/` 计划文件，也未运行全量 pytest。
- 关键发现：`search-units.jsonl`、`state/search-wave-*.json`、`state/live-search-wave-*.json` 是混元岗位实际搜索计划；根目录 `search-plan.json` 和最终报告标题/方向仍带有 AI Infra V2 痕迹，应作为后续调整的高优先级复核点。
- 进一步证据：严格 `allcompanies/positions` smoke 返回 0 人，query-only company anchor 返回 30 人，因此放弃严格结构化过滤有依据；但 wave002 resume 的真实请求出现 `allcompanies=BAT` 残留，说明 query-only 计划仍需显式清空高风险结构化过滤字段。
- 提案方向：将 `maimai_ai_infra_*` 搜索计划、评分、方向覆盖、交付报告脚本拆为 campaign-generic runtime + role-specific strategy；新增公司/产品线 alias registry 与交付评价 feedback contract，让下次 JD campaign 能动态生成公司映射、评分维度和下一轮搜索策略。
- 已将实施计划写入 `docs/superpowers/plans/2026-05-22-maimai-jd-campaign-generalization.md`，按 8 个工程任务拆分：先修 query-only 模板过滤残留，再补公司/产品线 registry、通用 search-plan 编译、通用 ranking、通用交付报告、feedback contract、混元 guardrail fixture/test 和最终回归。
- 本计划阶段不执行真实脉脉搜索、不修改历史 campaign raw、不写 `data/talent.db`；后续实现必须先跑聚焦测试，再跑相关回归与 `git diff --check`。
- `tasks/todo.md` 已缩减为当前工作台；完整历史迁移到 `tasks/archive/2026-05.md`。
- 迁移前：`2621` lines，`364242` bytes；迁移后：`18` lines，`1503` bytes。
- 归档检索验证通过：`rg -n "飞书推送|LLM 推理|GitHub HR|工作台提示" tasks/archive/2026-05.md` 命中历史记录。
- diff hygiene 通过：`git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md`。
- 本轮只改文档/任务账本，未运行全量 pytest；若后续改到脚本或 workflow，再运行 `python -m pytest tests scripts -q`。
- 已实现 JD-driven Maimai campaign 通用化第一阶段：query-only 默认清空 `allcompanies/positions` 和地域高风险模板残留；新增公司/产品线 registry；新增通用 search-plan、rank、delivery report、feedback contract；orchestrator 对 JD-style strategy 路由到 generic modules，对 legacy AI Infra strategy 保持兼容。
- 新增混元 guardrail fixture/test，锁定混元 strategy 生成链路不得出现 `AI Infra`、`训练框架`、`推理引擎` 样板残留，并确认 query-only `allcompanies=""`。
- Skill/workflow 已补 `company_product_mappings`、`delivery_feedback_contract` 和 S14 交付反馈阶段，要求用户评价落为机器可读 `feedback/*.json` 再生成下一轮 `strategy-adjustment*.json`。
- 验证：聚焦回归 `83 passed`；全量 `python -m pytest tests scripts -q` -> `763 passed, 1 warning`；新增/修改脚本 `py_compile` 通过；`git diff --check` 通过。
- 本轮未执行真实脉脉搜索，未修改历史 campaign raw，未写主库 `data/talent.db`。全量 warning 为既有 `scripts/test_boss.py` event loop deprecation，与本次改造无关。
