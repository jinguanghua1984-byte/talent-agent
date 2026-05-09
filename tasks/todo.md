# 本地人才库 SQLite 重构执行清单（2026-05-08）

> 来源计划：`docs/superpowers/plans/2026-05-08-local-talent-database.md`
> 执行模式：`superpowers:subagent-driven-development`

## 执行前校验

- [x] 已创建独立分支：`codex/local-talent-database-impl`
- [x] 已确认计划存在实现阻塞点（schema、FTS、ID 约束等），执行时按“可运行优先”收敛实现

## 任务清单

- [x] Task 1：安装并登记 `sqlite-vec` 依赖
- [x] Task 2：实现 `scripts/talent_models.py` + `tests/test_talent_models.py`
- [x] Task 3：实现 `scripts/talent_db.py` 基础 schema + get/enrich/sources
- [x] Task 4：实现 ingest / 去重 / batch_ingest / resolve_merge
- [x] Task 5：实现 search / count（过滤、排序、分页）
- [x] Task 6：实现 FTS5 全文搜索
- [x] Task 7：实现 sqlite-vec 向量存储与搜索（含可用性降级）
- [x] Task 8：实现评分 API（overall_score / match_scores / top_candidates）
- [x] Task 9：实现 JSON 到 SQLite 迁移脚本与测试
- [x] Task 10：补齐集成测试与真实迁移验证
  - [x] 在 `tests/test_talent_db.py` 新增 `test_full_talent_db_workflow`
  - [x] 覆盖 batch_ingest 多候选人、精确重复合并、年龄/技能/source/detail 合并
  - [x] 覆盖 overall score、coarse/llm_rank/final match score、FTS、search/filter/sort
  - [x] 覆盖 sqlite-vec 可用时的 embedding 保存与 vector_search；不可用则跳过该段
  - [x] 覆盖 get_top_candidates 只按 final 分数排序
  - [x] 使用真实 `data/candidates` 跑临时库迁移验证
- [x] Task 11：运行全量回归测试并修复发现的问题

## 审查记录

- [x] 子代理规格审查（逐任务）
- [x] 子代理代码质量审查（逐任务）
- [x] 最终整体审查

## Review

- 核心测试通过：`python -m pytest tests/test_talent_models.py tests/test_talent_db.py tests/test_talent_migrate.py -q`，结果 `140 passed`。
- 全量回归通过：`python -m pytest tests/ -v`，结果 `201 passed`。
- 真实迁移验证通过：对 `data/candidates` 生成临时库 `data/talent.verify.db`，结果 `created=78, merged=3, pending=0, errors=0`；验证后已删除临时库文件。
- 真实迁移中发现 `expected_city` 存在列表形态，已在迁移层归一化为 JSON 文本并补测试。
- 未修改真实生产库 `data/talent.db`。
