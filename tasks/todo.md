# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

- [ ] JD Talent Delivery skill 实施（2026-05-23）：按 `docs/superpowers/plans/2026-05-23-jd-talent-delivery-skill.md` 执行，新增本地 JD 人才库推荐与飞书 Wiki 交付 workflow；主库只读，飞书发布默认真实执行但先 dry-run 预检。
  - [x] Task 1：Skill contract 与测试。
  - [x] Task 2：Canonical workflow 与架构测试。
  - [ ] Task 3：岗位画像 builder。
  - [ ] Task 4：Scorecard builder。
  - [ ] Task 5：人才库匹配、推荐报告和外联表。
  - [ ] Task 6：飞书发布 manifest。
  - [ ] Task 7：飞书 preflight 与真实发布 executor。
  - [ ] Task 8：端到端 workspace CLI 接线。
  - [ ] Task 9：聚焦、架构相关和全量验证。

- [x] 混元 8JD 详情后主库级重新精排（2026-05-23）：基于已写入 2648 条详情后的 `data/talent.db`，重跑 8 个 JD 的 `maimai_campaign_rank --mode detailed`，并与 2026-05-22 旧精排结果对比。
  - [x] 运行 8 个 campaign strategy 的主库 detailed rank，输出到新的 `data/output/` 目录。
  - [x] 汇总每个 JD 的 A/B/C/淘汰数量和 Top10。
  - [x] 对比详情写入前后的 A/B/C 数量变化和 Top 候选人变化。
  - [x] 校验输出 JSON/Markdown 可读，并更新任务台账 Review。

- [x] 混元 8JD ABC 详情结果写入主库（2026-05-23）：用户要求“下一步写入主库”，基于 27 个 clean dry-run capture 顺序 apply 到 `data/talent.db`。
  - [x] 写入前备份 `data/talent.db`，并验证备份可读与 `PRAGMA integrity_check=ok`。
  - [x] 记录写入前主库基线：候选人/来源/详情表计数、已有 `maimai_detail_capture` 数量。
  - [x] 按 `detail-abc-pack-001` 到 `detail-abc-pack-027` 顺序 apply，使用既有 clean dry-run 作为前置校验。
  - [x] 写入后验证 `PRAGMA integrity_check`、写入人数、`maimai_detail_capture` 增量和 apply 报告。
  - [x] 更新任务台账 Review，保留备份路径、apply 汇总和后续重新精排入口。

- [x] 混元 8JD ABC 三档详情抓取任务与无人值守执行（2026-05-22）：基于主库 detailed rank 的 A/B/C 三档生成去重详情目标池，按 pack 执行脉脉详情 live gate；主库详情写入仍保持人工边界。
  - [x] 确认 `maimai-unattended-campaign` 详情阶段边界、现有 detail live gate/import 接口和主库 ABC rank JSON 字段。
  - [x] 生成 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/` 下的目标 manifest、pack JSON、run-policy 和执行摘要。
  - [x] 对 `http://127.0.0.1:9888` 做只读健康检查，确认已有脉脉人才银行页可用且无登录/验证码/安全页阻断。
  - [x] 按 pack 顺序无人值守执行详情抓取；遇到登录、验证码、403/429/432、非 JSON、HTML、模板漂移或 partial capture 时停机并保留 continuation。
    - 执行记录：已从单进程切为显式分片并发 runner；2/3/4 并发均已观察 3 分钟以上，无 stderr、无验证码/429/非 JSON 阻断，并发上限固定为 4。
    - 已启动 `scripts/hunyuan_abc_parallel_supervisor.ps1` 自动补位，最多 4 个活动分片；全部 `detail-abc-pack-001` 到 `detail-abc-pack-027` 已完成。
  - [x] 对完成的 capture 做主库 dry-run 校验；不自动 apply `data/talent.db`，完成后给出明确人工写入入口。
  - [x] 更新任务台账 Review，记录目标数量、pack 数、已完成数量、阻断原因和后续恢复命令。

- [x] 混元 8JD campaign DB -> 主人才库真实同步（2026-05-22）：用户已明确授权 `确认同步混元8JD campaign DB 到主库 data/talent.db`，按已校验 bundle 顺序 apply，先备份再写主库。
  - [x] 创建 `data/talent.db` 的 SQLite 一致备份并验证备份可读。
  - [x] 重新校验 8 个同步 bundle。
  - [x] 按 01 -> 08 顺序 apply 到 `data/talent.db`，记录每个 bundle created/merged/conflicts/skipped。
  - [x] 同步完成后检查 `PRAGMA integrity_check`、候选人/详情/来源计数、`sync_imports`、`sync_conflicts`。
  - [x] 产出真实同步报告，更新后续逐 JD 高精度匹配入口。

- [x] 混元 8JD 主库级逐 JD 详细匹配（2026-05-22）：基于扩充后的 `data/talent.db`，用 8 个 campaign 的 `strategy.json` 分别跑 `maimai_campaign_rank --mode detailed`。
  - [x] 生成 8 个 JD 的主库 detailed rank JSON/Markdown。
  - [x] 汇总每个 JD 的 A/B/C/淘汰数量与 Top 候选人入口。
  - [x] 更新任务台账和验证结果。

- [x] 混元 8JD campaign DB -> 主人才库同步 dry-run 预检（2026-05-22）：已完成 bundle 导出、校验和真实主库 dry-run；真实 `data/talent.db` apply 等待明确授权。
  - [x] 导出并校验 8 个 campaign-local DB 的同步 bundle。
  - [x] 对真实主库 `data/talent.db` 执行逐 bundle dry-run，记录 created/merged/conflicts/skipped。
  - [x] 产出同步预检报告和下一步确认口令。
  - [x] 测试库累计 apply 模拟因耗时过长中止并清理临时 DB；真实写入前改为即时备份 + 顺序 apply + 完整性验证。

- [x] 混元 AI DATA 8JD batch campaign 搜索执行与 Campaign DB 扩库（2026-05-22）：基于 `docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md`，已按 8 个 JD campaign root 完成首轮 campaign-local 人才池扩充；主库同步与逐 JD 精排等待单独授权。
  - [x] 生成 batch manifest、`jd-index.json`、8 个 campaign 的 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json` 和 `search-implementation-plan.md`。
  - [x] 编译 8 个 campaign 的 `search-plan.json`、`search-units.jsonl` 和 `state/search-wave-plan.json`。
  - [x] 校验 query-only filters、manifest schema、03/04 低置信度缺失字段、样板词扫描和聚焦测试。
  - [x] 用户已确认 batch 搜索计划，8 个 campaign `run-policy.json` 已标记 `search_plan_confirmed=true`。
  - [x] 已启动 CDP 浏览器和 `extensions/maimai-scraper`，CDP `http://127.0.0.1:9888/json/version` 可用。
  - [x] 修复 `run-campaign` 对 generic JD `strategy.json` 的兼容问题，避免误走 legacy AI Infra schema 校验。
  - [x] 01 岗位 3 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 01 Campaign DB `candidates=2662`，list rank 为 `A=0/B=0/C=137/淘汰=2525`。
  - [x] 05 岗位 2 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 05 Campaign DB `candidates=1889`，list rank 为 `A=0/B=3/C=154/淘汰=1732`。
  - [x] 08 岗位 2 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 08 Campaign DB `candidates=833`，list rank 为 `A=0/B=3/C=61/淘汰=769`。
  - [x] 06 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 06 Campaign DB `candidates=907`，list rank 为 `A=0/B=0/C=62/淘汰=845`。
  - [x] 07 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 07 Campaign DB `candidates=937`，list rank 为 `A=0/B=1/C=74/淘汰=862`。
  - [x] 02 岗位 1 个 search wave 已完成标准化、dry-run clean 和 Campaign DB apply；当前 02 Campaign DB `candidates=1079`，list rank 为 `A=0/B=38/C=99/淘汰=942`。
  - [x] 03 岗位 `search-wave-001` 验证码恢复后已补齐剩余 28 页，完成标准化、dry-run clean 和 Campaign DB apply；当前 03 Campaign DB `candidates=734`，list rank 为 `A=0/B=0/C=71/淘汰=429`。
  - [x] 04 岗位 `search-wave-001` 在 `http_432` 与 `missing_search_template` 两次阻塞后已恢复并补齐剩余 9 页，完成标准化、dry-run clean 和 Campaign DB apply；当前 04 Campaign DB `candidates=516`，list rank 为 `A=0/B=0/C=27/淘汰=473`。

## Open Items

- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-22：已修复 `scripts/maimai_ai_infra_pipeline.py` 的 generic JD strategy 导入兼容，并新增 `tests/test_maimai_ai_infra_pipeline.py` 回归；聚焦测试 `58 passed`。
- 2026-05-22：01 岗位首轮 150 页已完成 Campaign DB apply，campaign-local DB 当前 `candidates=2662`，`pending_merges=0`，`sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 2026-05-22：05 岗位首轮 100 页已完成 Campaign DB apply，campaign-local DB 当前 `candidates=1889`，`pending_merges=0`，`sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 2026-05-22：08/06/07/02 岗位首轮已完成 Campaign DB apply，当前 campaign-local DB 分别为 `833/907/937/1079` 人，均无 pending/conflict 且 integrity `ok`。
- 2026-05-22：03 岗位 `search-wave-001` 已从 `captcha_api` continuation 恢复并完成 Campaign DB apply，当前 campaign-local DB 为 `734` 人，无 pending/conflict 且 integrity `ok`。
- 2026-05-22：04 岗位 `search-wave-001` 已从 `http_432`/`missing_search_template` continuation 恢复并完成 Campaign DB apply，当前 campaign-local DB 为 `516` 人，无 pending/conflict 且 integrity `ok`。
- 2026-05-22：混元 8JD 主库同步 dry-run 预检完成，8 个 bundle 均校验通过；逐 bundle 对真实主库 dry-run 合计 `exported=9557/created=9392/merged=165/conflicts=0/skipped=0`，真实主库未 apply，`sync_imports` 未新增。
- 2026-05-22：混元 8JD 已真实同步到主库；备份为 `data/backups/talent-main-before-hunyuan-8jd-sync-20260522-211400.db`，apply 合计 `created=7835/merged=1722/conflicts=14/skipped=0`，主库 `candidates=13332/sync_imports=10/integrity=ok`。
- 2026-05-22：混元 8JD 主库级 detailed rank 已生成，汇总见 `data/output/hunyuan-8jd-main-db-match-2026-05-22/main-db-detailed-rank-summary.md`。
- 2026-05-22：已开始核查通用化改造后 AI Infra schema 残留问题，并记录 lesson。
- 2026-05-22：已核对混元数据策略负责人 campaign 的 JD、requirements、strategy、search-units、wave plan、live plan 和执行 raw 证据，未修改 campaign 计划。
- 2026-05-22：已形成并执行 todo token 治理实施计划，详见 `docs/superpowers/plans/2026-05-22-todo-governance.md`。
- 2026-05-21：混元大模型数据策略负责人脉脉寻访继续执行已完成，完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-21：飞书 Wiki JD requirements export、混元寻访计划等已归档，完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`

## Review

- 2026-05-23 JD Talent Delivery Task 2：新增 runtime-neutral canonical workflow `agents/workflows/jd-talent-delivery/AGENT.md`，覆盖资源索引、S0-S7、scorecard 一致性、安全边界和飞书停机条件；新增 `tests/test_jd_talent_delivery_workflow.py` 并将 `jd-talent-delivery` 加入架构 `WORKFLOWS`。由于架构测试要求每个 workflow 都有运行时 adapter，新增最小 `.claude/skills/jd-talent-delivery/SKILL.md` 指向 canonical workflow。验证：先跑 `python -m pytest tests/test_jd_talent_delivery_workflow.py -q` 红灯，因缺少 workflow 文件 `FileNotFoundError` 失败；创建 workflow 后同命令 `4 passed`；新增架构列表后组合测试因缺少 adapter 失败；补 adapter 后 `python -m pytest tests/test_jd_talent_delivery_workflow.py tests/test_agent_architecture.py -q` -> `9 passed`。`git diff --check` 通过；workflow 私有运行时禁词扫描无命中。
- 2026-05-23 详情后主库级重新精排：已用 `python -m scripts.maimai_campaign_rank --mode detailed --limit 13332` 对 8 个混元 JD 全量重跑，输出目录为 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/`。汇总见 `main-db-detailed-rank-after-detail-summary.md/json`，前后对比见 `main-db-detailed-rank-pre-post-comparison.md/json`。与详情写入前同口径相比，8JD 合计 `A 16->19 (+3)`、`B 450->493 (+43)`、`C 9686->10036 (+350)`、`A+B 466->512 (+46)`、`A+B+C 10152->10548 (+396)`、`淘汰 96504->96108 (-396)`。验证：3 个汇总 JSON 均可解析，8 个 rank JSON 均为 `total_candidates=13332`，8 个 Markdown 输出存在，主库 `PRAGMA integrity_check=ok/candidates=13332/candidate_details=13332/source_profiles=13332/maimai_detail_capture_rows=3625`。
- 2026-05-23 ABC 详情写入主库：写入前备份为 `data/backups/talent-main-before-hunyuan-abc-detail-apply-20260523-003549.db`，备份 `integrity=ok/candidates=13332/source_profiles=13332/candidate_details=13332/maimai_detail_capture=977`。已修正专用 detail campaign manifest 缺少 `schema=maimai_ai_infra_v2_campaign` 导致 pipeline apply 前置校验失败的问题；失败发生在写库前，随后从 `detail-abc-pack-001` 重新顺序 apply。27 个 pack 全部写入主库，汇总 `matched=2648/written=2648/unmatched=0/failed_jobs=0/capture_blockers=0/apply_blockers=0`。写入后主库 `integrity=ok/candidates=13332/source_profiles=13332/candidate_details=13332/maimai_detail_capture=3625/hunyuan_abc_capture_rows=2648/detailed_candidates=13319`。摘要见 `data/output/hunyuan-8jd-abc-detail-main-apply-2026-05-23/main-detail-apply-summary.md/json`，逐包 JSONL 为 `apply-summary.jsonl`。
- 2026-05-22 ABC 详情抓取启动：新增 `scripts/hunyuan_abc_detail_tasks.py`，从 `data/output/hunyuan-8jd-main-db-match-2026-05-22/main-db-detailed-rank-summary.json` 读取 8JD A/B/C 三档，生成 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/`。ABC 输入行 `10152`，去重候选人 `3173`，已有 `maimai_detail_capture` 跳过 `525`，缺失 `0`，可执行目标 `2648`，拆为 `27` 个 pack（前 26 个 100 人，最后 48 人）。CDP 健康检查通过：`hasLoginPrompt=false/hasCaptcha=false/hasTalentBank=true`。后台无人值守 runner 已启动，PID `19304`，主库 apply 策略为 `manual_only`。
- 2026-05-22 ABC 详情并发试跑：`scripts/hunyuan_abc_detail_tasks.py` 已支持 `--pack-ids` 与 `--runner-id`，避免多进程抢同一 pack；原顺序 PID `19304` 在 `pack002=32/100` 时停止，随后分片试跑 2 -> 3 -> 4 并发。4 并发截至 `22:54:04` 进度 `709/2648`，`pack001` 到 `pack005` 已完成，`pack006=82/100`、`pack007=62/100`、`pack008=43/100`、`pack009=22/100`；各分片 stderr 均为 `0`，未见平台阻断。验证：`python -m py_compile scripts/hunyuan_abc_detail_tasks.py` 通过；`python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_detail_import.py -q` -> `24 passed`。
- 2026-05-22 ABC 详情并发补位：新增 `scripts/hunyuan_abc_parallel_supervisor.ps1`，自动识别完成/活动 pack 并保持最多 4 个分片。已修正 supervisor 不应把自身 process json 算作 worker 的监控口径。当前 supervisor PID `27972`，状态文件 `data/campaigns/hunyuan-8jd-abc-detail-2026-05-22/state/parallel-supervisor-state.json` 显示 `completed_packs=8/27`、`done_jobs=931/2648`、`percent=35.16`，活动分片为 `pack009/010/011/012`，stderr 均为 `0`。
- 2026-05-23 ABC 详情抓取完成：`parallel-supervisor-state.json` 显示 `status=completed`、`completed_packs=27/27`、`done_jobs=2648/2648`、`percent=100`，完成时间 `2026-05-23T00:29:08`。27 个 dry-run 报告全部存在，汇总 `matched=2648/unmatched=0/failed_jobs=0/capture_blockers=0/apply_blockers=0`，没有 dirty 包；所有 stderr 日志为空。未自动 apply `data/talent.db`。
- 2026-05-22 主库真实同步：报告为 `data/output/hunyuan-8jd-main-sync-apply-2026-05-22/main-sync-apply-summary-20260522-211400.md/json`；同步前备份为 `data/backups/talent-main-before-hunyuan-8jd-sync-20260522-211400.db`，备份 `candidates=5497/source_profiles=5497/candidate_details=5497/sync_imports=2/integrity=ok`。8 个 bundle 顺序 apply 后主库 `candidates=13332/source_profiles=13332/candidate_details=13332/pending_merges=0/sync_conflicts=1814/sync_imports=10`，`PRAGMA integrity_check=ok`。候选人级 apply 合计 `created=7835/merged=1722/conflicts=14/skipped=0`。
- 2026-05-22 主库级逐 JD detailed rank：输出目录为 `data/output/hunyuan-8jd-main-db-match-2026-05-22/`，8 个 JD 均生成 `*-main-db-detailed-rank.md/json` 和 `main-db-detailed-rank-summary.md/json`。A/B/C 数：01=`1/19/1182`，02=`2/146/1679`，03=`0/0/931`，04=`0/1/997`，05=`7/236/1615`，06=`0/1/1141`，07=`0/5/974`，08=`6/42/1167`。03/04 因 JD 正文缺失仍为低置信。
- 2026-05-22 主库同步预检：输出目录为 `data/output/hunyuan-8jd-main-sync-precheck-2026-05-22/`，包含 8 个 campaign bundle 与 `main-sync-dry-run-summary.md/json`。8 个 bundle 均 `verify_ok=true`；逐 bundle dry-run 合计 `exported=9557/created=9392/merged=165/conflicts=0/skipped=0`。`data/talent.db` 未 apply；SQLite 读/备份预检使文件 mtime 变为 `2026-05-22T20:37:21`，但业务计数仍为 `candidates=5497/source_profiles=5497/candidate_details=5497/sync_imports=2`，最新 `sync_imports.imported_at=2026-05-20 04:12:30`，`PRAGMA integrity_check=ok`。
- 测试库累计 apply 模拟曾启动但因耗时过长中止，临时 `main-sync-simulation-*.db*` 已清理；该模拟不作为证据。真实写入前应即时备份主库，再顺序 apply 8 个 bundle 并做 `PRAGMA integrity_check`、候选人数、sync_conflicts 验证。
- 2026-05-22 继续执行补充四：04 人工刷新搜索模板后已补齐 `search-wave-001` 剩余 9 页；标准化后 30/30 页齐备，dry-run/apply `raw=516/unique=516/created=516/pending=0/errors=0`；04 Campaign DB `candidates=516/source_profiles=516/candidate_details=516/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=27/淘汰=473`。
- 混元 8JD 首轮 campaign-local 扩库完成：01/02/03/04/05/06/07/08 Campaign DB 当前分别为 `2662/1079/734/516/1889/907/937/833` 人；均已完成 list rank，且主库 `data/talent.db` 未写。
- 验证：聚焦回归 `python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py -q` -> `58 passed`；全量 `python -m pytest tests scripts -q` -> `765 passed, 1 warning`，warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 2026-05-22 继续执行补充三：03 验证码恢复后已补齐 `search-wave-001` 剩余 28 页；标准化后 30/30 页齐备，dry-run/apply `raw=734/unique=734/created=734/pending=0/errors=0`；03 Campaign DB `candidates=734/source_profiles=734/candidate_details=734/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=71/淘汰=429`。
- 04 岗位 `search-wave-001` 在 `unit-000005 page 2` 触发 `http_432`，按 workflow 停机；已标准化成功 21/30 页作为 checkpoint，但未对 04 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-http-432-plan.json`，剩余 9 页等待人工处理风控/安全提示后恢复。
- 04 恢复尝试在预检阶段返回 `missing_search_template`：页面健康检查显示仍在人才银行页、无登录弹窗/验证码，但 `templateStatus.hasSearchTemplate=false`，因此没有进入任何 batch，也没有新增 raw page。已写 `reports/interruption-search-wave-001-missing-template-2026-05-22.json`，下一步需在人才银行页手动执行一次搜索刷新模板后再恢复。
- 2026-05-22 继续执行补充二：08 验证码恢复后已补齐 `search-wave-001` 剩余 7 页，并完成 `search-wave-002` 10 页；08 Campaign DB 最终 `candidates=833/source_profiles=833/candidate_details=833/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=3/C=61/淘汰=769`。
- 06 岗位首轮 45 页完成：`search-wave-001` dry-run/apply `raw=907/created=907/pending=0/errors=0`；06 Campaign DB `candidates=907/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=0/C=62/淘汰=845`。
- 07 岗位首轮 45 页完成：`search-wave-001` dry-run/apply `raw=937/created=937/pending=0/errors=0`；07 Campaign DB `candidates=937/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=1/C=74/淘汰=862`。
- 02 岗位首轮 40 页完成：`search-wave-001` dry-run/apply `raw=1079/created=1079/pending=0/errors=0`；02 Campaign DB `candidates=1079/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=38/C=99/淘汰=942`。
- 03 岗位 `search-wave-001` 在 `unit-000001 page 3` 触发 `captcha_api`，按 workflow 停机；已标准化成功 2/30 页作为 checkpoint，但未对 03 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-captcha-plan.json`，剩余 28 页等待人工处理验证码后恢复。
- 2026-05-22 继续执行补充：01 岗位验证码恢复后已补齐 `search-wave-003` 剩余 6 页，第三波 dry-run `raw=991/unique=991/created=678/merged=313/pending=0/errors=0` 并 apply clean；01 Campaign DB 最终 `candidates=2662/source_profiles=2662/candidate_details=2662/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`。
- 05 岗位首轮 100 页完成：`search-wave-001` dry-run/apply `raw=907/created=907/pending=0/errors=0`；`search-wave-002` dry-run/apply `raw=986/created=982/merged=4/pending=0/errors=0`；05 Campaign DB 最终 `candidates=1889/source_profiles=1889/candidate_details=1889/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`，list rank 为 `A=0/B=3/C=154/淘汰=1732`。
- 08 岗位 `search-wave-001` 在 `unit-000009 page 4` 触发 `captcha_api`，按 workflow 停机；已标准化成功 43/50 页作为 checkpoint，但未对 08 执行 dry-run/apply。已写 `reports/interruption-search-wave-001-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-001-resume-after-captcha-plan.json`，剩余 7 页等待人工处理验证码后恢复。
- 2026-05-22 继续执行结果：`scripts/maimai_ai_infra_pipeline.py` 已支持 generic JD `strategy.json`，`run-campaign` 不再因缺少 legacy AI Infra keys 阻塞；新增回归 `test_run_campaign_wave_generates_plan_files_for_generic_jd_strategy`，聚焦测试 `python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py -q` -> `58 passed`。
- 01 岗位 `search-wave-001`：live run `status=completed/stopReason=null/batches=10/contacts=1355`；标准化 50 页；dry-run `raw=984/unique=984/created=984/merged=0/pending=0/errors=0`；Campaign DB apply clean。
- 01 岗位 `search-wave-002`：live run `status=completed/stopReason=null/batches=10/contacts=1367`；标准化 50 页；dry-run `raw=1282/unique=1282/created=1000/merged=282/pending=0/errors=0`；Campaign DB apply clean。
- 01 Campaign DB 当前状态：`candidates=1984/source_profiles=1984/candidate_details=1984/pending_merges=0/sync_conflicts=0`，`PRAGMA integrity_check=ok`；主库 `data/talent.db` 未写。
- 01 岗位当前 list rank：`reports/list-rank.md/json` 已生成，列表证据下 `A=0/B=0/C=61/淘汰=923`，说明仍需完成剩余搜索与后续详情抓取后再做高精度结论。
- 01 岗位 `search-wave-003`：live run 在 `unit-000029 page 5` 触发 `captcha_api`，按 workflow 停机；已标准化成功的 44/50 页作为 checkpoint，但未对第三波执行 dry-run/apply。已写 `reports/interruption-search-wave-003-2026-05-22.json`、`state/continuation-plan.json` 和 `state/search-wave-003-resume-after-captcha-plan.json`，剩余 6 页等待人工处理验证码后恢复。
- 2026-05-22：已执行混元 8JD batch campaign 合同生成与离线搜索计划编译；产物根目录为 `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/`，8 个 JD 独立 campaign root 均已生成。
- 8 个 campaign 首轮总计划页数为 500：01=150、02=40、03=30、04=30、05=100、06=45、07=45、08=60；对应 wave 数为 3/1/1/1/2/1/1/2。
- 关键产物：batch `campaign-manifest.json`、`jd-index.json`、`reports/batch-search-plan-summary.md/json`；每个 JD 的 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json`、`search-implementation-plan.md`、`search-plan.json`、`search-units.jsonl`、`state/search-wave-plan.json`。
- 校验：8 个 campaign workflow status 可读；全部 search units 满足 `allcompanies=""`、`positions=""`、`query_relation=0`；03/04 `missing_fields` 已包含 `岗位职责正文`、`任职要求正文`、`技术栈细节`；样板词扫描无命中；生成器 `py_compile` 通过；聚焦测试 `python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_search_filter_clearing.py -q` -> `35 passed`。
- 兼容修正：新 campaign 的 `campaign-manifest.json.schema` 写为 pipeline 兼容的 `maimai_ai_infra_v2_campaign`，同时用 `contract_schema=maimai_jd_campaign_v2` 标识 JD 合同类型，避免后续标准化/Campaign DB pipeline 因 schema 不兼容阻塞。
- 本轮未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`；下一步必须等待用户确认 batch 搜索计划。
- 用户确认 batch 搜索计划后，已更新 8 个 campaign 的 `run-policy.json` 和 `state/stage-state.json`，并启动 CDP 浏览器；session manifest 写入 `data/campaigns/hunyuan-ai-data-8jd-batch-2026-05-22/state/browser-bootstrap.json`。
- CDP 预检：启动前 `http://127.0.0.1:9888/json/version` 不可用；启动后返回 Chrome CDP version 信息，说明端口可用。当前状态为 `browser_bootstrap_launched_waiting_manual_handoff`。
- 当前仍未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`；下一步需要人工在该浏览器内登录脉脉、进入人才银行页并手动执行一次搜索模板。
- 2026-05-22：已阅读 `docs/business-requirements/` 下 8 个文件名含 `hunyuan` 的 JD，并生成综合扩库型脉脉寻访计划：`docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md`。
- 本计划采用“1 个 batch 计划 + 8 个 JD campaign root”的结构，先用共享公司池/关键词簇扩充 Campaign DB 与本地人才库，再用每个 JD 的 `strategy.json` 对 `data/talent.db` 做独立精排。
- 已明确首轮 500 页预算分配、6 类人才画像簇、query-only 搜索边界、排除规则、详情抓取规则、Campaign DB 到主库的人工同步边界和逐 JD 本地精排命令形态。
- 03/04 两个 JD 正文为“待补充”，计划中已标为低置信度；后续不能用它们给强结论，精排前需补正式 JD 或通过交付反馈校准。
- 校验：计划文档样板词扫描无命中；`git diff --check -- docs/superpowers/plans/2026-05-22-hunyuan-8jd-maimai-sourcing-plan.md tasks/todo.md` 通过。
- 本轮未执行真实脉脉搜索，未写 Campaign DB，未写主库 `data/talent.db`。
- 本轮调查中，重点区分“搜索执行真实使用的计划”和“后续评分/交付复用的通用脚本 schema”，避免把 AI Infra 样板残留误判成单点文案错误。
- 本轮完成解释性核查和实施计划设计，未改 `data/campaigns/hunyuan-data-strategy-lead-2026-05-21/` 计划文件，也未运行全量 pytest。
- 关键发现：`search-units.jsonl`、`state/search-wave-*.json`、`state/live-search-wave-*.json` 是混元岗位实际搜索计划；根目录 `search-plan.json` 和最终报告标题/方向仍带有 AI Infra V2 痕迹，应作为后续调整的高优先级复核点。
- 进一步证据：严格 `allcompanies/positions` smoke 返回 0 人，query-only company anchor 返回 30 人，因此放弃严格结构化过滤有依据；但 wave002 resume 的真实请求出现 `allcompanies=BAT` 残留，说明 query-only 计划仍需显式清空高风险结构化过滤字段。
- 提案方向：将 `maimai_ai_infra_*` 搜索计划、评分、方向覆盖、交付报告脚本拆为 campaign-generic runtime + role-specific strategy；新增公司/产品线 alias registry 与交付评价 feedback contract，让下次 JD campaign 能动态生成公司映射、评分维度和下一轮搜索策略。
- 已将实施计划写入 `docs/superpowers/plans/2026-05-22-maimai-jd-campaign-generalization.md`，按 8 个工程任务拆分：先修 query-only 模板过滤残留，再补公司/产品线 registry、通用 search-plan 编译、通用 ranking、通用交付报告、feedback contract、混元 guardrail fixture/test 和最终回归。
- 本计划阶段不执行真实脉脉搜索、不修改历史 campaign raw、不写 `data/talent.db`；后续实现必须先跑聚焦测试，再跑相关回归与 `git diff --check`。
- `tasks/todo.md` 已缩减为当前工作台；完整历史迁移到 `tasks/archive/2026-05.md`。
- 迁移前：`2621` lines，`364242` bytes；迁移后：`18` lines，`1503` bytes。
- 归档检索验证通过：`rg -n "飞书推送|LLM 推理|GitHub HR|工作台提示" tasks/archive/2026-05.md` 命中历史记录。
- diff hygiene 通过：`git diff --check -- tasks/todo.md tasks/archive/README.md tasks/archive/2026-05.md AGENTS.md`。
- 本轮只改文档/任务账本，未运行全量 pytest；若后续改到脚本或 workflow，再运行 `python -m pytest tests scripts -q`。
- 已实现 JD-driven Maimai campaign 通用化第一阶段：query-only 默认清空 `allcompanies/positions` 和地域高风险模板残留；新增公司/产品线 registry；新增通用 search-plan、rank、delivery report、feedback contract；orchestrator 对 JD-style strategy 路由到 generic modules，对 legacy AI Infra strategy 保持兼容。
- 新增混元 guardrail fixture/test，锁定混元 strategy 生成链路不得出现 `AI Infra`、`训练框架`、`推理引擎` 样板残留，并确认 query-only `allcompanies=""`。
- Skill/workflow 已补 `company_product_mappings`、`delivery_feedback_contract` 和 S14 交付反馈阶段，要求用户评价落为机器可读 `feedback/*.json` 再生成下一轮 `strategy-adjustment*.json`。
- 验证：聚焦回归 `83 passed`；全量 `python -m pytest tests scripts -q` -> `763 passed, 1 warning`；新增/修改脚本 `py_compile` 通过；`git diff --check` 通过。
- 本轮未执行真实脉脉搜索，未修改历史 campaign raw，未写主库 `data/talent.db`。全量 warning 为既有 `scripts/test_boss.py` event loop deprecation，与本次改造无关。
- 已基于 `docs/business-requirements/01-hunyuan-llm-data-strategy-lead.md` 生成 v2 campaign：`data/campaigns/hunyuan-llm-data-strategy-lead-v2-2026-05-22/`。产物包含 `requirements.json`、`strategy.json`、`run-policy.json`、`campaign-manifest.json`、`search-implementation-plan.md`、`search-plan.json`、`search-units.jsonl`、`state/search-wave-plan.json`、`reports/search-plan-summary.md`。
- v2 搜索计划规模：90 个 search units，342 页，拆为 7 个 wave，页数为 `50/50/50/48/48/48/48`；全部 unit 均为 query-only，`allcompanies=""`、`positions=""`，无 `AI Infra/训练框架/推理引擎` 样板残留。
- 本轮 workflow status 通过，聚焦测试 `python -m pytest tests/test_maimai_campaign_search_plan.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_search_filter_clearing.py -q` -> `35 passed`。尚未执行真实脉脉搜索，等待搜索计划确认。
- 接手后复核：`maimai_campaign_orchestrator status` 仍停在 `draft_pending_search_plan_confirmation`；再次校验 search units 和聚焦测试，确认 `35 passed`，真实脉脉搜索仍未执行。
