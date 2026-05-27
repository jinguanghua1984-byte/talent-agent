# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- 2026-05-27：合并并推送当前分支到 GitHub。
  - [x] 确认当前分支、远端和相对 `origin/main` 的差异范围。
  - [x] 跑全量测试和 diff hygiene，确认待合并内容可提交。
  - [x] 提交本地 JD `profile_url` 修复相关改动。
  - [x] 合并到 `main` 并处理任务台账冲突。
  - [ ] 合并后验证、推送 GitHub，并确认本地 `main` 与 `origin/main` 一致。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-27：已提交 JD 交付 `profile_url` 可打开性修复并合并当前分支到 `main`；合并中仅 `tasks/todo.md` 冲突，已按当前工作台规则保留精简任务台账。
- 2026-05-27：已按同一规则批量修复 11 个飞书外联表 `profile_url`。11 个 Wiki URL 均解析为 Sheet；共 330 条外联行，均按平台 ID 从 `data/talent.db` 找到完整 URL 并只更新 `profile_url` 列；回读验证 `profile_failures=0`、`non_profile_changes=0`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-27：人才库云同步 detail merge 修复已在远端 `main` 记录并推送；本次合并保留相关代码、测试和任务台账更新。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
