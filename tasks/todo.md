# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

暂无。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。
- BOSS 当前职位今日沟通数达到付费解锁上限；等待额度重置或用户在 Codex 外处理后再续跑。

## Recent Done

- 2026-06-05：BOSS-Maimai cross-channel delivery 已合入主线：完成多渠道审计 schema/sync、BOSS target、Maimai identity scoring、Campaign DB import、主库 sync gate、JD handoff 和脉脉 URL 优先级；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-05：JD 推荐反馈自然语言解析已完成 review 收尾：review queue 行前置校验、非有限数字拒绝、标准 JSON 写出保护、全量测试通过；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-04：猎聘 adaptive 规划、single-wave live runner、adaptive raw 标准化、search import dry-run/apply、broad-recall summary、detail target 审计链已完成并验证；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
