# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- 当前无进行中的任务。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-27：脚本清理和 hygiene 第一轮实施已完成。测试文件已迁移到 `tests/`，`AGENTS.md` 验证命令改为 `.venv/bin/python -m pytest tests -q`；`score_candidates.py` 与已获确认的 Hunyuan ABC 一次性脚本已移出运行时目录；`data-manager.py` 改为 shim，新入口为 `python -m scripts.data_manager`；`maimai_ai_infra_*` 保留为 legacy compatibility layer 并有路由回归覆盖。验证：`.venv/bin/python -m pytest tests -q` -> `939 passed, 1 warning`，py_compile、引用扫描和 diff hygiene 通过。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：已归档 2026-05-24 前的 superpowers 文档，顶层只保留 2026-05-24 及之后文档；聚焦测试 `12 passed`，全量 `.venv/bin/python -m pytest tests scripts -q` -> `931 passed, 1 warning`。
- 2026-05-27：Agent skill 分层和 Claude Code adapter 补齐完成，canonical skill contract 已迁移到 `agents/skills/`，Claude adapter 已同步；聚焦测试 `24 passed`，全量 `.venv/bin/python -m pytest tests scripts -q` -> `907 passed, 1 warning`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
