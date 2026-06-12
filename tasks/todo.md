# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

暂无活跃任务。

## Open Items

- 多模态视频算法研究员 BOSS->脉脉后续：只对 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/structured/maimai-match-targets.jsonl` 的 19 个实名 target 启动匹配；13 个缺实名已触达人不进入自动匹配，除非人工补名。
- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-12：Talent DB 增量同步 P1 已完成并合入 `main`；支持候选人级 `sync_updated_at` 水位、候选人闭包增量 bundle、`talent_sync export --mode incremental`、飞书 Drive full bootstrap / incremental push-pull、远端 pending push 门禁和空增量 no-op；验证 `1463 passed, 1 warning`，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-12：GBrain 开源选型闭环已完成；本地安装 `gbrain 0.42.40.0` 并用隔离 PGLite/no-embedding/conservative 模式完成 smoke 与 redacted pilot，结论为 `keep_optional_adapter`；新增 adoption ADR、pilot report、runbook、安全 source-tree export，并把 JD delivery contract 固定为非阻塞 fallback 主路径；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-12：gbrain 第二大脑 P0 foundation 已接入；新增 second-brain event/case/query/gbrain/evaluation/CLI 模块，JD feedback 支持 `consultant_decision`，JD delivery workflow 记录 shadow calibration 和 post-run case generation 合同；focused tests、相关 JD tests、架构测试、全量测试和 diff check 均通过；完整记录已归档到 `tasks/archive/2026-06.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
- 2026-06：`tasks/archive/2026-06.md`
