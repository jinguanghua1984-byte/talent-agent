# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### BOSS-Maimai cross-channel delivery（2026-06-05）

计划：
- [x] 实施 canonical skill/workflow/adapter 和架构测试。
- [x] 扩展 TalentDB 多渠道审计 schema、sync export/import 和测试。
- [x] 实施 BOSS target 生成、脉脉 identity scoring 和 Campaign DB import。
- [x] 实施主库 sync gate、JD delivery handoff 和脉脉 URL 优先级。
- [x] 运行聚焦测试、全量测试和 `git diff --check`，写 Review 并归档。

边界：
- 只实现离线数据整合、Campaign DB 写入、主库 sync gate 和交付 handoff；不操作 BOSS/脉脉平台。
- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段不被脉脉覆盖。
- Campaign DB 存在 blocked/errors、pending identity、pending merge、open sync conflict 或 dry-run 冲突时，不写 `data/talent.db`。
- 主库写入必须同时满足 Campaign DB clean、dry-run clean、一次总授权 flag 和 `CONFIRM_SYNC_TEXT`。

验证：
- `/Users/eric/workspace/talent-agent/.venv/bin/python -m pytest tests/test_agent_architecture.py tests/test_boss_maimai_targets.py tests/test_cross_channel_identity.py tests/test_cross_channel_import.py tests/test_campaign_to_delivery.py tests/test_jd_talent_delivery_match.py tests/test_talent_db.py tests/test_talent_sync.py -q`。
- `/Users/eric/workspace/talent-agent/.venv/bin/python -m pytest tests -q`。
- `git diff --check`。

Review：
- 2026-06-05：已完成 BOSS-Maimai cross-channel delivery 实现收口。聚焦测试 `249 passed`；全量测试 `1219 passed, 1 warning`，warning 为既有 `tests/test_boss.py::TestBossGetDetailUnavailable::test_get_detail_returns_none` event loop deprecation；`git diff --check` 通过。

## Open Items

- 子线程额度限制导致 Task 5 最后一轮复审、Task 6-8 由主线程本地执行；最终验证必须覆盖同等命令。
- 真实 campaign 执行时，如出现 `pending_confirmation`、`no_match`、平台限制或 dry-run 冲突，必须按 workflow 停机并等待人工处理。

## Recent Done

- 2026-06-05：Task 7 已完成 `scripts/campaign_to_delivery.py` 与 `tests/test_campaign_to_delivery.py`，实现 Campaign DB quality gates、主库 bundle dry-run/apply、一次总授权 gate 和 `state/jd-delivery-handoff.json`。验证：`tests/test_campaign_to_delivery.py` 7 passed；`tests/test_campaign_to_delivery.py tests/test_talent_sync.py` 50 passed；`tests/test_cross_channel_import.py tests/test_campaign_to_delivery.py tests/test_jd_talent_delivery_match.py` 43 passed。
- 2026-06-05：Task 6 已完成 JD delivery 脉脉 URL 优先级，BOSS source 在前时仍输出可打开的脉脉主页链接并保留 `trackable_token`。验证：`tests/test_jd_talent_delivery_match.py` 18 passed；`git diff --check` 通过。
- 2026-06-05：Task 5 已完成并加固 Campaign DB import：BOSS primary + Maimai supplement 写入、clean gate、事务原子性、identity/field audit、CLI 结构化错误和 raw_profile 合并。完整记录见 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
