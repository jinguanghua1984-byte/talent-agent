# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-09：成本治理 workflow 压缩与 shared policies 已完成；新增 `agents/policies/`，压缩 BOSS-Maimai/JD/Liepin/public-search workflow，并拆出 `agents/workflows/public-search/commands.md`；架构测试 `24 passed`，全量测试 `1384 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：已将 `/Users/eric/Downloads/maimai-detail-capture-2026-06-08.json` 的 304 条脉脉详情写入主人才库；dry-run/apply 均为 matched 304、unmatched 0、failed_jobs 0、blockers 0，apply written 304；写库前备份 `data/backups/talent-20260609-012233-before-maimai-detail-capture-import.db`，报告位于 `data/output/maimai-detail-import-20260609-detail-capture-apply.md`；DB integrity/外键和 145 个聚焦测试通过，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：已将 `/Users/eric/Downloads/maimai-pager-contacts-2026-06-08.json` 的 304 条脉脉 pager contacts 导入主人才库；dry-run/apply 均为新建 126、合并 178、待确认 0、失败 0；写库前备份 `data/backups/talent-20260609-010411-before-maimai-pager-contacts-import.db`，报告位于 `data/output/talent-import-20260609-maimai-pager-contacts-apply.md`；DB integrity/外键和 138 个聚焦测试通过，完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
