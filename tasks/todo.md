# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### 猎聘 Campaign DB 主库同步 handoff dry-run（2026-06-04）

计划：
- [x] 完成上一阶段 adaptive live recovery/idempotence 聚焦实现和合同更新。
- [x] 对照 `talent_sync.py export/verify-bundle/import dry-run`，补猎聘 campaign-local DB 到主库同步 handoff RED 测试。
- [x] 实现只读主库 dry-run/report 命令，不执行 import apply。
- [x] 更新猎聘 skill/workflow，明确主库写入仍需单独确认。
- [x] 验证 JD delivery 可承接主库中的猎聘来源 URL，并在猎聘 workflow 中明确后续推荐/飞书交付交给 `jd-talent-delivery`。
- [x] 运行聚焦、猎聘聚焦、全量测试、敏感边界扫描和最终 diff 检查。

边界：
- 只读取 campaign-local `talent.db` 并写 `exports/` 与 `reports/` handoff 产物。
- 可对指定主库路径执行 dry-run plan；不得创建、修改或 apply 到 `data/talent.db`。
- 不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储。

阶段结果：
- adaptive live recovery/idempotence 已完成：`tests/test_liepin_adaptive_search_live_gate.py` -> `5 passed`；猎聘聚焦 + 架构测试 -> `162 passed`；`git diff --check` 通过。
- 新增 `main-db-sync-handoff`：导出 campaign-local sync bundle、verify bundle、生成主库 dry-run plan 和 `reports/main-db-sync-handoff.json/.md`；明确 `no_main_db_write=true`。
- JD delivery 兼容性已补测试：猎聘脱敏 `profile_url` 可进入推荐 JSON 与 outreach CSV，质量门禁通过；猎聘 workflow 不直接生成推荐/飞书交付，而是在主库同步后交给 `jd-talent-delivery`。
- 最终验证：JD delivery + 猎聘聚焦集合 `184 passed`；全量测试 `1232 passed, 1 warning`，warning 为既有 BOSS event loop deprecation；敏感边界扫描仅命中测试负断言和禁止条款；`git diff --check` 通过。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。
- BOSS 当前职位今日沟通数达到付费解锁上限；等待额度重置或用户在 Codex 外处理后再续跑。

## Recent Done

- 2026-06-04：猎聘 adaptive 规划、single-wave live runner、adaptive raw 标准化、search import dry-run/apply、broad-recall summary、detail target 审计链已完成并验证；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-04：猎聘 full detail pack planning/live/dry-run/apply 到 Campaign DB 与 Campaign Summary 阶段已完成；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-04：BOSS + 脉脉跨渠道交付设计与实施计划已写入文档，等待独立执行选择；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
