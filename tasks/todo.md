# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-10：优化 BOSS 多模态/视频类寻访通用筛选策略已完成；在 BOSS sourcing 合同和 BOSS-Maimai 交接中新增明确视频/多模态信号优先于视觉/图像/图形边界词的规则，默认 `strategy.json` 增加 positive/negative/override 信号；新增合同测试覆盖余先生类“视频算法+语音/视频/图形求职目标”可进入 contact_hold、搜索/广告/推荐/NLP/语音/纯视觉仍排除、已触达 hold 边界候选可进入脉脉补充；验证 `19 passed`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-10：多模态视频算法研究员 BOSS-Maimai 真实触达寻访已完成本轮飞书交付；BOSS 列表扫描到底部，累计 `115` 张卡片、去重详情候选 `52` 人、raw 详情页 `58` 条、真实触达 `14` 人、实名脉脉 target `8` 人；脉脉 safe resume 搜索 `22` 批全部成功，身份判定 `0 auto_bound / 1 pending_confirmation / 7 no_match`，刘波需人工确认，未写 Campaign DB 和 `data/talent.db`；本地交付包质量门禁 passed，飞书报告 Wiki `TZdywhCTmipVshkFCfkcwoHqnpd`、跟进 Sheet Wiki `YEfMw7Zt3i9WQRkklMacrdTenyh` 已发布并回读 passed，已通知 `JD需求协同` message_id=`om_x100b6dbe3f262134b3cf7232c05ee73`；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：多模态视频算法研究员 BOSS-Maimai 寻访交付已完成修正版；将“未命中继续筛到命中或列表耗尽”写入 BOSS sourcing / BOSS-Maimai workflow 并新增合同测试；BOSS 继续筛到 30 张卡片后找到 1 位 dry-run 合格人选（刘先生 / 阿里云计算有限公司 / 图像算法，score 88），脉脉因 BOSS 脱敏姓名缺真实姓名阻断（selected 1、target 0、missing_real_name 1）；修正版报告已发布到飞书 Doc/Wiki `P4VOw8V6Ei4XmBkInvJcWRbPnjd`，并向 `JD需求协同` 发送 IM `om_x100b6db5390284a4b166e1a890ca2d8`；合同测试 `25 passed`，全量测试 `1412 passed, 1 warning`，campaign validate passed，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：Structured output JD feedback 已接入当前 PR；新增 `StructuredOutputSchema` 和 Anthropic/OpenAI-compatible `complete_structured()`，JD feedback single/batch parser 优先使用 structured output 并保留旧 JSON prompt fallback；相关测试 `50 passed`，全量测试 `1411 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：Campaign status next-action 强化已接入当前 PR；`campaign_status summarize` 新增 artifact completeness、missing artifacts、derived stage 和 DB/Feishu 状态，`campaign_orchestrator next-action` 增加 standardize、Campaign DB apply 授权、Feishu publish preflight、IM notification 规则；相关测试 `36 passed`，全量测试 `1406 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：JD feedback provider batch jobs 已接入当前 PR；新增 `prepare-batch` 生成 batch manifest/requests/rule-results，新增 `apply-batch` 应用 provider output 并把 batch job id/custom id/output artifact/usage 写入 `LLMUsageLedger`；聚焦测试 `45 passed`，全量测试 `1400 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：LLM ranker hard budget 已接入当前 PR；默认新增 LLM 精排调用限制为 Top 60，每人 evidence block 默认限制 1200 chars，`score_pipeline run/resume` 新增 `--rank-limit` 和 `--candidate-evidence-max-chars`，并修正按粗筛得分顺序进入 ranker；聚焦测试 `24 passed`，相关测试 `78 passed`，全量测试 `1395 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：LLM usage coverage 已接入当前 PR；`call_llm_with_retry` 可透传 usage metadata，JD feedback/JD analyzer/LLM ranker/score pipeline 使用 `configs/llm-routing.json` 显式 route，并新增 `scripts.llm_usage report` 月度聚合；聚焦测试 `75 passed`，全量测试 `1392 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
