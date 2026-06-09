# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

无。

## Open Items

- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-09：LLM ranker hard budget 已接入当前 PR；默认新增 LLM 精排调用限制为 Top 60，每人 evidence block 默认限制 1200 chars，`score_pipeline run/resume` 新增 `--rank-limit` 和 `--candidate-evidence-max-chars`，并修正按粗筛得分顺序进入 ranker；聚焦测试 `24 passed`，相关测试 `78 passed`，全量测试 `1395 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：LLM usage coverage 已接入当前 PR；`call_llm_with_retry` 可透传 usage metadata，JD feedback/JD analyzer/LLM ranker/score pipeline 使用 `configs/llm-routing.json` 显式 route，并新增 `scripts.llm_usage report` 月度聚合；聚焦测试 `75 passed`，全量测试 `1392 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-09：成本治理 workflow 压缩与 shared policies 已完成；新增 `agents/policies/`，压缩 BOSS-Maimai/JD/Liepin/public-search workflow，并拆出 `agents/workflows/public-search/commands.md`；架构测试 `24 passed`，全量测试 `1384 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
