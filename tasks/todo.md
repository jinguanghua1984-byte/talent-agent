# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### GBrain 开源选型闭环与真实适配验证

- [x] 确认当前 second-brain P0 与 GBrain 上游能力差距，形成 evidence-backed adoption decision。
- [x] 本机/隔离环境验证 GBrain 安装、doctor 和 search mode 门禁。
- [x] 用 Talent-Agent redacted case artifacts 做 pilot，对比 GBrain 与本地 fallback 的查询质量。
- [x] 根据 pilot 结果调整 adapter/query/workflow/docs，保持 JD delivery 非阻塞。
- [ ] 运行聚焦测试、全量测试和 diff check，归档 Review。

边界：先做开源选型闭环和本地 pilot，不把 GBrain 设为正式硬依赖；不导入 private case 到 public/shared source；不在仓库或聊天中保存 API key；不写 `data/talent.db`。执行计划见 `docs/superpowers/plans/2026-06-12-gbrain-open-source-adoption-closure.md`。

验证方式：`gbrain --version` / `gbrain doctor --json` / pilot import-query 证据；聚焦测试覆盖 `tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py`；完成后运行 `.venv/bin/python -m pytest tests -q` 和 `git diff --check`。

### 多模态视频算法研究员 Campaign DB 同步主库与增量包

- [x] 校验 campaign DB 已有 5 个确认绑定候选人，主库同步前状态可读。
- [x] 备份 `data/talent.db`，执行 `campaign_to_delivery sync-main` 写入主库。
- [x] 校验主库写入结果、sync result、handoff 和增量 bundle。
- [x] 生成其它 PC 导入说明，回填 Review 并归档。

边界：用户已授权将 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/talent.db` 中本轮 5 个 confirmed candidates 同步进主库 `data/talent.db`。仍不得直接复制/覆盖主库；必须使用 bundle sync 流程、确认文本 `确认同步人才库`、写前备份和写后验证。增量导入包只包含该 campaign DB 的同步数据，供其它 PC 通过 `scripts/talent_sync.py import` dry-run/backup/apply。

验证方式：`campaign_to_delivery validate-campaign`、主库 `PRAGMA integrity_check`、`campaign_to_delivery sync-main`、`talent_sync.py verify-bundle`、主库候选/来源/identity 计数和 5 人回读、聚焦测试和 `git diff --check`。

Review：2026-06-11 已将 campaign DB 的 5 个 confirmed candidates 通过 bundle sync 写入主库 `data/talent.db`，写前备份为 `data/backups/talent-db/talent-20260611-115925-before-boss-maimai-sync.db`。写入前主库 `PRAGMA integrity_check=ok`，候选数 `56328`；写入后 `PRAGMA integrity_check=ok`，候选数 `56332`。dry-run 为新建候选人 `4`、合并候选人 `1`、冲突候选人 `0`；apply 结果为新建 `4`、合并 `1`，5 条 identity match 和 40 条 field values 已入主库。张志达合并到主库既有人才 `candidate_id=38410`，7 个字段差异已记录到 `sync_conflicts`，不阻断导入。增量包生成并校验通过：`data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/exports/talent-sync-boss-maimai-incremental-20260611-115943.zip`，SHA256 `3ebb35acbc8f8836f5ba3fef05782e0b97029f49cc30e26b1f9e20abcbfcb96f`；其它 PC 导入说明为 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/exports/IMPORT-INSTRUCTIONS-20260611.md`。验证：bundle verify passed，`campaign_status` 为 `main_db_sync_and_incremental_bundle/completed`，聚焦测试 `63 passed`，全量测试 `1424 passed, 1 warning`，`git diff --check` clean。

### 微信“你今天做了啥”日报/人选跟进摘要草稿

- [x] 明确目标群与日期：`你今天做了啥`，`2026-06-10`。
- [x] 拉取并解析群消息，按“每日工作记录 / 人选跟进”分类。
- [x] 生成草稿 Markdown 文件，便于用户调整格式。
- [x] 校验消息计数、时间范围和产物路径。

边界：只读取微信本地历史消息并生成结构化草稿；不写 `data/talent.db`，不触发 BOSS/脉脉/飞书外联或同步，不把聊天内容导入主库。

验证方式：`wx history "48117422906@chatroom" --since 2026-06-10 --until 2026-06-10 -n 5000 --json` 拉取消息；用脚本核对消息数和时间范围；检查生成的 Markdown 文件存在且包含“每日工作记录”和“人选跟进”两类内容。

Review：2026-06-11 已完成 `2026-06-10` 群消息摘要草稿；`wx history` 校验消息数 `17`，首条 `2026-06-10 10:35:36`，末条 `2026-06-10 18:49:39`。草稿写入 `wechat/48117422906@chatroom-你今天做了啥/2026-06-10.md`，并补充 `history.json` / `history-digests.jsonl` 支持后续增量。核心结构包括每日工作记录、人选跟进表、待办汇总和后续 skill 字段建议；未写 `data/talent.db`，未触发外联或飞书同步。验证：Markdown 核心章节存在，历史 JSON/JSONL 可解析，`git diff --check -- tasks/todo.md` clean。

### 多模态视频算法研究员 BOSS->脉脉匹配续跑

- [x] 用户授权继续脉脉匹配。
- [x] 读取 canonical BOSS-Maimai / Maimai unattended workflow，确认脚本入口和停机边界。
- [x] 核对 19 个实名 target、旧匹配产物和 continuation 状态，决定复用/补搜范围。
- [x] 通过仓库脚本检查 CDP/Talent Bank 健康状态；只在合同允许范围内自动 bootstrap，不手动操作 Chrome DOM。
- [x] 对缺失或需刷新 target 执行脉脉搜索匹配，落盘 raw 与身份判定。
- [x] 生成/刷新匹配 summary、台账和后续 Campaign DB/主库边界说明。
- [x] 运行聚焦验证并回填 Review。

边界：只消费 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/structured/maimai-match-targets.jsonl` 中 19 个实名 target；13 个缺实名已触达人不进入自动匹配。真实脉脉 Talent Bank 工作必须复用现有 CDP/search/detail 脚本与 `agents/workflows/maimai-unattended-campaign/AGENT.md`；不手动操作 Chrome DOM，不直接打开个人主页替代脚本；遇到登录、验证码、安全页、HTTP 403/429/432、CloudWAF/非 JSON、模板漂移或平台限制立即停机并记录 continuation。未获单独授权前不写 `data/talent.db`。

验证方式：`campaign_status summarize` / `campaign_orchestrator next-action` 检查阶段；匹配脚本产物检查 `raw/maimai-match-search/`、`state/cross-channel-identity-ledger.jsonl`、`reports/maimai-match-summary.*`；聚焦测试优先覆盖 `tests/test_cross_channel_identity.py`、`tests/test_campaign_status.py`、`tests/test_campaign_orchestrator_next_action.py`，最后 `git diff --check`。

Review：2026-06-11 续跑已完成 11 个缺失实名 target 的脉脉 live search，累计 33 批、54 contacts，未触发登录/验证码/风控/模板漂移；身份 ledger 覆盖 19/19，当前 `1 confirmed_bound / 4 pending_confirmation / 14 no_match`。新增 `reports/maimai-match-pending-review.{json,md}` 作为人工确认交接，并把 `state/continuation-plan.json` 更新为 `blocked_pending_confirmation`。修正 `campaign_status` / `campaign_orchestrator next-action`：当脉脉最终判定已覆盖 target 且存在 pending 时，不再误报 `requires_maimai_cdp`，改停 `cross-channel-identity-review`。验证：`tests/test_cross_channel_identity.py tests/test_campaign_status.py tests/test_campaign_orchestrator_next_action.py tests/test_maimai_ai_infra_search_live_gate.py -q` -> 50 passed；`.venv/bin/python -m pytest tests -q` -> 1424 passed, 1 warning；`git diff --check` clean。下一步停在 S4 人工确认门禁：4 个 pending 未经确认不得自动绑定、不得进入主库 apply；本轮未写 Campaign DB 和 `data/talent.db`。

### 多模态视频算法研究员 BOSS->脉脉确认后飞书追加

- [x] 用户确认 4 个 `pending_confirmation` 均为同一人。
- [x] 更新 identity ledger / all decisions / bound candidates / identity summary。
- [x] 执行 Campaign DB import dry-run、apply 和 quality gates；不写主库。
- [x] 重建 BOSS-Maimai 交付报告和 follow-up queue。
- [x] 在既有飞书报告 Doc 和跟进 Sheet 后追加更新，不生成新文档。
- [x] 回读飞书更新结果，运行聚焦验证并回填 Review。

边界：本轮用户确认只覆盖黄玉岩、刘骁、张志达、张一山 4 个脉脉身份绑定；允许更新本 campaign 内部记录、Campaign DB、本地交付物和既有飞书交付物。不得写 `data/talent.db`，不得新建飞书交付 Doc/Sheet；飞书只追加到旧报告 Wiki `TZdywhCTmipVshkFCfkcwoHqnpd` 和旧跟进表 Wiki `YEfMw7Zt3i9WQRkklMacrdTenyh`。

验证方式：`cross_channel_import import --dry-run/apply`、`campaign_to_delivery validate-campaign`、`boss_maimai_campaign_delivery build`、飞书追加后 readback、`campaign_status summarize` / `campaign_orchestrator next-action`、聚焦测试和 `git diff --check`。

Review：2026-06-11 已按用户确认将黄玉岩、刘骁、张志达、张一山 4 个待确认脉脉命中更新为 `confirmed_bound`，identity 分布为 `5 confirmed_bound / 14 no_match / 0 pending`。已完成 Campaign DB import dry-run/apply 与 quality gates，重建交付报告和跟进表；未写 `data/talent.db`。飞书交付按要求追加到既有报告 Wiki `TZdywhCTmipVshkFCfkcwoHqnpd` 和既有跟进 Sheet `YEfMw7Zt3i9WQRkklMacrdTenyh`，未新建文档；Sheet 回读 `32` 条数据、`5` 个 confirmed、`0` pending，关键行：刘波 row 9、刘骁 row 15、黄玉岩 row 24、张志达 row 25、张一山 row 28。回读证据写入 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/feishu/boss-maimai-existing-append-readback-20260611.json`；已通知 `JD需求协同`，message_id=`om_x100b6d968f46a508b1121aecceacffd`。`campaign_status` 显示 `existing_feishu_delivery_append/completed`。验证：聚焦测试 `67 passed`，全量测试 `1424 passed, 1 warning`，`git diff --check` clean。

## Open Items

- 多模态视频算法研究员 BOSS->脉脉后续：只对 `data/campaigns/multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09/structured/maimai-match-targets.jsonl` 的 19 个实名 target 启动匹配；13 个缺实名已触达人不进入自动匹配，除非人工补名。
- 猎聘 parity 后续缺口：Campaign DB 到主库同步 handoff 仍只能做 dry-run/report，不得写 `data/talent.db`，真实 apply 需单独确认。
- 猎聘 parity 后续缺口：JD delivery/ranking 与飞书交付是否纳入猎聘寻访默认链路，需要先按 broad-recall summary 与主库同步边界设计。
- 大疆 BG OTD 脉脉寻访仍有历史平台验证码阻断；继续该旧 campaign 前需用户在平台侧处理验证码/安全验证。

## Recent Done

- 2026-06-12：已按只读对照手工吸收 `.worktrees/codex/gbrain-second-brain-p0` 的局部细节；补齐 canonical JD 产物路径、case 脱敏、outreach 行级 source refs、JSONL 缺尾换行保护、`access token` marker 变体和 consultant decision 空白归一化；未 merge/cherry-pick 整个 worktree，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-12：gbrain 第二大脑 P0 foundation 已接入；新增 second-brain event/case/query/gbrain/evaluation/CLI 模块，JD feedback 支持 `consultant_decision`，JD delivery workflow 记录 shadow calibration 和 post-run case generation 合同；focused tests、相关 JD tests、架构测试、全量测试和 diff check 均通过；完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-12：已完成当前全部更新提交并推送；推送前本地 `main` 领先 `origin/main` 两个提交：`5f729f1 Design gbrain second brain P0`、`8083654 Plan gbrain second brain P0`，已推送到远端并确认 `HEAD` 与 `origin/main` 一致，完整记录已归档到 `tasks/archive/2026-06.md`。
- 2026-06-10：多模态视频算法研究员 BOSS 寻访已按用户要求停止并完成脉脉匹配交接准备；campaign `multimodal-video-algorithm-boss-maimai-real-contact-2026-06-09` 刷新到 `386` 张列表卡、`137` 条详情、`32` 次真实触达、`19` 个实名；`validate-executor` passed（36 条 approved queue、127 条 executor attempts、无 issues）；已导出 `structured/maimai-match-targets.jsonl`（19 个实名 target，13 个缺实名不进自动匹配）并新增 `reports/maimai-handoff-prep.md`，完整记录已归档到 `tasks/archive/2026-06.md`。
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
