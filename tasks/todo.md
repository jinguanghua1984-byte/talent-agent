# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### 人才库推荐反馈自然语言解析调研与设计（2026-06-04）

计划：
- [x] 盘点现有 JD delivery feedback 设计、代码、schema、测试和业务指南。
- [x] 确认当前反馈能力缺口：业务需要手填结构化字段和原因码，自然语言解析入口尚未落地。
- [x] 给出自然语言反馈解析的可选方案、推荐架构和安全边界。
- [x] 写入正式 spec，并按 review 修正数据 contract、review queue 和 run-root 入口。
- [x] 写入实施计划。
- [ ] 用户选择执行方式后，再进入代码改造。

边界：
- 本阶段先调研和设计，不改业务代码，不改 `data/talent.db`，不触发平台采集或飞书云端写入。
- 结构化反馈字段继续作为内部 contract；业务侧目标是只填写自然语言不适配说明。
- AI 解析结果必须可审计、可回退、可人工覆盖；不得自动直接修改评分卡或主库。

阶段结果：
- 已确认现有 Phase 1：`scripts/jd_delivery_feedback.py` 可编译结构化反馈，`reports/outreach-queue.csv` 已含 8 个空反馈列，S9 反馈回收默认只生成本地校准建议。
- 已确认缺口：`docs/manual/jd-delivery-feedback-guide.md` 要求业务理解 `feedback_label`、`feedback_stage`、`reason_codes` 等字段，填写复杂度偏高。
- 正式 spec：`docs/superpowers/specs/2026-06-04-jd-delivery-natural-language-feedback-design.md`。
- 实施计划：`docs/superpowers/plans/2026-06-04-jd-delivery-feedback-note-parser.md`。
- 设计决策：外联表只保留 `feedback_note`；LLM 直接解析；prompt 必须输出 `parse_confidence`；低置信度/降级条目进入 `parse-review-queue.json` 且默认不进入校准闭环；批量解析以 `--run-root` 为主入口；移除生命周期布尔列和 `actionable_at_30`。
- 验证：计划自审通过；`git diff --check` 通过。

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
