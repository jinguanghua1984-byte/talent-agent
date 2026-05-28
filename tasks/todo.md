# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-28：已完成九坤大模型产品 7 个 JD 拆解、本地人才库 Top30 推荐、飞书 Wiki 发布和 `JD需求协同` 群通知；质量门禁全部 passed，验证 `.venv/bin/python -m pytest tests -q` 为 `952 passed, 1 warning`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：已将 `codex/script-cleanup-hygiene` 合并到 `main` 并推送 GitHub；关键提交为 `eb4b4e6`（JD `profile_url` 修复）和 `5066466`（merge commit）。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：已按同一规则批量修复 11 个飞书外联表 `profile_url`。11 个 Wiki URL 均解析为 Sheet；共 330 条外联行，均按平台 ID 从 `data/talent.db` 找到完整 URL 并只更新 `profile_url` 列；回读验证 `profile_failures=0`、`non_profile_changes=0`。完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
