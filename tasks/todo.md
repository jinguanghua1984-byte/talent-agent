# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- `pm-ai-vertical-broad-recall-2026-05-28` 剩余 2 个详情 blocker 已随 campaign 作为 `core` 级候选人入主库，但未写入伪造详情：汪俊（`platform_id=35260004`）和徐傲蕾（`platform_id=82917951`），原因均为 `missing_work_experience`；后续如要提升到 detailed，需要单独补齐或剔除。
- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-28：已完成九坤大模型产品 7 个 JD 的 v2 年轻高潜推荐重跑；7 个 `*-run-002` 输出包质量门禁全部 `passed`，均已发布飞书 `JD需求交付` 并向 `JD需求协同` 通知；验证 `.venv/bin/python -m pytest tests -q` -> `955 passed, 1 warning`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-28：已处理 `pm-ai-vertical-broad-recall-2026-05-28` 主库同步产生的 `292` 条 open `sync_conflicts`；处理后 `open_conflicts=0`，分布为 `resolved_keep_local=263`、`resolved_standardized_remote=6`、`resolved_use_remote=23`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-28：已将 `pm-ai-vertical-broad-recall-2026-05-28` Campaign DB 通过 `scripts.talent_sync` 安全导入主库；dry-run `6211` 新建、`789` 合并、`0` 冲突，apply 后主库候选人 `26224`，Campaign 来源 key `7003/7003` 和详情 capture `4285/4285` 均覆盖。完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
