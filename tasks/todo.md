# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- 2026-05-27：合并并推送当前分支到 GitHub。
  - [x] 确认当前分支、远端和相对 `origin/main` 的差异范围。
  - [x] 跑全量测试和 diff hygiene，确认待合并内容可提交。
  - [ ] 提交本地 JD `profile_url` 修复相关改动。
  - [ ] 合并到 `main` 并推送 GitHub。
  - [ ] 推送后确认本地 `main` 与 `origin/main` 一致。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-27：已按同一规则批量修复 11 个飞书外联表 `profile_url`。11 个 Wiki URL 均解析为 Sheet；共 330 条外联行，均按平台 ID 从 `data/talent.db` 找到完整 URL 并只更新 `profile_url` 列；回读验证 `profile_failures=0`、`non_profile_changes=0`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：JD 交付 `profile_url` 可打开性修复完成。代码层保留脉脉详情页 `dstu + trackable_token` 并继续清洗非必要参数；质量门禁仅放行 `profile_url` 字段中的合法详情页 token。已只更新指定飞书 Sheet 的 23 个 `profile_url` 单元格，其他字段变化为 0；14 条当前人才库无 `platform_id` 命中的行保持原值。验证：聚焦测试 `71 passed`，全量 `.venv/bin/python -m pytest tests -q` -> `942 passed, 1 warning`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：脚本清理和 hygiene 第一轮实施已完成。测试文件已迁移到 `tests/`，`AGENTS.md` 验证命令改为 `.venv/bin/python -m pytest tests -q`；`score_candidates.py` 与已获确认的 Hunyuan ABC 一次性脚本已移出运行时目录；`data-manager.py` 改为 shim，新入口为 `python -m scripts.data_manager`；`maimai_ai_infra_*` 保留为 legacy compatibility layer 并有路由回归覆盖。验证：`.venv/bin/python -m pytest tests -q` -> `939 passed, 1 warning`，py_compile、引用扫描和 diff hygiene 通过。完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
