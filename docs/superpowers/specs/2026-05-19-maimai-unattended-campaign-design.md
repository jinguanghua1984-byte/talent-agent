# 脉脉无人值守寻访 Campaign 设计

## 背景

本设计面向从寻访业务需求到最终交付报告的长任务闭环：

1. 输入人才寻访需求。
2. 通过几轮沟通确认后生成脉脉寻访实施计划。
3. 按计划执行人才列表搜索、列表数据采集、列表评分和粗筛。
4. 对优质人选抓取详情数据。
5. 基于详情做二次评分、精排和外联优先级排序。
6. 生成完整交付报告，必要时发布飞书摘要文档和候选人/外联 Sheet。

项目已经完整实践过 AI Infra V2 campaign，全量过程产物在 `data/campaigns/ai-infra-v2-2026-05-15-dry-run`。当前目录包含 450 个 search units、1350 个标准化搜索页 raw、596 个详情 job raw、12 个 contacts wave、完整 final report/outreach report/Feishu delivery package 源文件。现有 `scripts/maimai_ai_infra_*`、`scripts/maimai_detail_*`、`scripts/talent_sync.py` 已覆盖主要端到端能力，缺口主要是产品化入口和总编排。

## 核心边界

这里的“无人值守”定义为：负责人不需要在屏幕前监控任务；系统在平台状态正常时自动执行，在遇到需要人工处理的平台安全事件时自动停机、记录断点并通知负责人；负责人处理后系统从断点恢复。

本设计不承诺也不实现绕过验证码、登录、安全页、403、429、非 JSON 或平台风控。真实脉脉页面操作遵守既有安全边界：

- 不自动打开、导航、刷新脉脉业务页面。
- 不自动点击业务页面。
- 不用 `automation.html` 或 CDP `Runtime.evaluate` 启动真实详情抓取。
- 不让扩展 popup、side panel、service worker 直接请求脉脉业务接口。
- 只连接用户已经打开且稳定的人才银行页。
- 任何登录页、验证码、安全页、403、429、非 JSON、模板漂移、captcha/block 证据出现时立即停止当前真实平台阶段。

## 目标

- 产品化“根据寻访业务需求生成脉脉寻访实施计划”的场景，优先实现为 skill。
- 复用已有端到端能力，不重写搜索、评分、详情抓取、导入、报告生成主逻辑。
- 提供一个可恢复的长任务 workflow，串联 search plan、live gate、raw 标准化、campaign import、list rank、detail packs、detail live gate、detail import、detailed rank、delivery/outreach。
- 支持中断、断点恢复、分级重试和负责人通知。
- 让每个可写入动作有明确权限边界：campaign DB 可按预授权自动写入；主库 `data/talent.db` 同步必须单独显式确认。
- 让交付产物可审计：本地 report/CSV/JSON 完整留存，飞书只发布筛选后的报告和 Sheet，不上传 raw DB/capture。

## 非目标

- 不实现全自动绕过平台安全拦截。
- 不把历史 `data/talent.db` 作为冷启动 campaign 的隐性前提。
- 不在本设计中改造评分模型权重；评分逻辑继续由现有 strategy/config 和 rank 脚本承载。
- 不把 Feishu 分享权限变更、删除清理、主库同步纳入无人自动执行。
- 不把 agent 临场推理作为唯一执行记录；所有关键阶段必须落本地结构化状态和 report。

## 方案选择

### 推荐方案：Skill 入口 + Workflow 编排器

Skill 负责需求沟通、计划生成和启动前确认；workflow 编排器负责按固定状态机调用现有脚本。这个方案改动最小、最容易测试，也符合仓库当前“canonical workflow + runtime adapter”的架构。

### 备选方案：单体 Autopilot CLI

一个 `scripts/maimai_campaign_autopilot.py` 直接完成需求采集、计划生成和执行。优点是入口简单；缺点是业务沟通、状态恢复和真实平台执行耦合，后续维护和测试成本更高。

### 备选方案：Agent 全程驱动

由 agent 动态读 plan、跑命令、处理异常。优点是灵活；缺点是可重复性差，难以保证长任务恢复和审计一致性。不作为产品化主路径。

最终采用推荐方案。

## 总体架构

新增两个产品化入口，底层复用现有脚本：

1. `skills/maimai-talent-search-campaign/SKILL.md`
   - 面向用户的业务入口。
   - 通过几轮问题确认需求。
   - 生成 `requirements.json`、`strategy.json`、`run-policy.json` 和人类可读实施计划。
   - 不直接执行真实平台请求。

2. `agents/workflows/maimai-unattended-campaign/AGENT.md`
   - Canonical workflow。
   - 定义阶段、状态文件、命令、恢复规则和安全停机规则。
   - Runtime adapter 必须先读取该 workflow 再执行。

3. `scripts/maimai_campaign_orchestrator.py`
   - 薄编排器。
   - 只负责调用现有 CLI、聚合状态、写 events、执行恢复策略。
   - 不复制搜索、评分、详情导入、报告生成逻辑。

4. `scripts/maimai_search_live_standardize.py`
   - 小型胶水 CLI。
   - 把 `maimai_ai_infra_search_live_gate.py --out <run.json>` 输出标准化到 `raw/search/unit-*/page-*.json`。
   - 复用 `scripts/maimai_ai_infra_campaign.py` 中的 `page_raw_path()`、`mark_page_completed()` 语义。

5. `scripts/feishu_delivery_package.py`
   - 将已有 one-off Feishu helper 正式化。
   - 输入 final report/outreach CSV/quality audit，输出摘要云文档、候选人 Sheet、outreach queue Sheet。
   - 每次运行前检查 `lark-cli doctor`、auth/token、scope。

## 业务入口设计

Skill 通过最多五轮沟通收敛需求，每轮只问当前缺失的关键决策：

1. 岗位和业务目标：目标岗位、业务方向、资深度、交付候选人数量。
2. 硬筛条件：地域、年龄/年限、学历学校、公司类型、排除条件。
3. 搜索策略：优先公司池、岗位词、关键词包、是否冷启动、每日请求预算。
4. 详情预算：详情抓取人数目标、单 pack 大小、停止阈值。
5. 交付格式：本地报告、CSV、飞书文档/Sheet、外联队列字段。

Skill 输出：

```text
data/campaigns/<campaign_id>/
  requirements.json
  strategy.json
  run-policy.json
  search-implementation-plan.md
  campaign-manifest.json
```

`requirements.json` 保存用户原始业务表达和确认后的结构化需求。`strategy.json` 是搜索和评分配置。`run-policy.json` 保存预授权、重试、通知和停止规则。

## 数据目录

每个 campaign 独立运行：

```text
data/campaigns/<campaign_id>/
  campaign-manifest.json
  requirements.json
  strategy.json
  run-policy.json
  search-plan.json
  search-units.jsonl
  talent.db
  raw/
    search-live-runs/
    search/unit-000001/page-001.json
    contacts/contacts-wave-001.json
    detail-targets/
    detail-live/<pack_id>/job-000001-<platform_id>.json
  review/
  state/
    events.jsonl
    stage-state.json
    search-progress.json
    detail-progress.json
    import-ledger.jsonl
    continuation-plan.json
  reports/
```

真实候选人、raw capture、campaign DB 均保留在 `data/campaigns/`，保持 gitignored。

## 执行状态机

### S0 需求确认

Skill 生成 requirements、strategy 和 run-policy。负责人确认后才能进入 S1。

### S1 计划编译

调用：

```bash
python scripts/maimai_ai_infra_search_plan.py --config <campaign_root>/strategy.json --out <campaign_root>/search-plan.json --out-units <campaign_root>/search-units.jsonl
```

输出 search plan 和不可变 search units。计划生成后写 `state/events.jsonl`。

### S2 搜索预检

运行 dry-run-template-only，确认请求模板和 units 可被解析：

```bash
python scripts/maimai_ai_infra_search_runner.py --dry-run-template-only --campaign-root <campaign_root> --units <campaign_root>/search-units.jsonl --resume --max-runtime-minutes 180
```

预检不触发真实脉脉请求。

### S3 列表搜索 Live Gate

按 wave 执行真实搜索，调用现有 live gate：

```bash
python -m scripts.maimai_ai_infra_search_live_gate --plan <wave_plan.json> --out <campaign_root>/raw/search-live-runs/<run_id>.json --cdp-url http://127.0.0.1:9888 --delay-seconds <n> --timeout-seconds <n>
```

成功后标准化：

```bash
python -m scripts.maimai_search_live_standardize --campaign-root <campaign_root> --run <run.json> --units <campaign_root>/search-units.jsonl
```

标准化页级 raw 是搜索恢复的事实来源。

### S4 Wave 导入 Campaign DB

每个 wave 先 dry-run：

```bash
python -m scripts.maimai_ai_infra_pipeline run-campaign --campaign-root <campaign_root> --config <campaign_root>/strategy.json --wave <wave_id> --db <campaign_root>/talent.db
```

若 `pre_errors=0`、`pending=0`、`errors=0`，并且 `run-policy.json` 允许 campaign DB 自动 apply，则执行：

```bash
python -m scripts.maimai_ai_infra_pipeline run-campaign --campaign-root <campaign_root> --config <campaign_root>/strategy.json --wave <wave_id> --db <campaign_root>/talent.db --apply
```

每次 apply 写 `state/import-ledger.jsonl`，禁止重复 apply。

### S5 列表评分和粗筛

调用：

```bash
python -m scripts.maimai_ai_infra_rank --db <campaign_root>/talent.db --config <campaign_root>/strategy.json --mode list --out-json <campaign_root>/reports/list-rank.json --out-md <campaign_root>/reports/list-rank.md
```

按 strategy 的阈值自动生成详情目标集合。默认规则是 A/B 或达到分数阈值的人进入详情候选池，实际阈值由 `strategy.json` 固化。

### S6 详情任务包

调用：

```bash
python -m scripts.maimai_ai_infra_detail_plan build-ab-packs --campaign-root <campaign_root> --pack-count <n>
```

默认 pack 大小控制在 80-150 人，复用既有 4 包 x 149 人的成功经验。

### S7 详情 Health Check 和 Probe

每包先 health check：

```bash
python -m scripts.maimai_ai_infra_detail_live_gate --plan <pack.json> --out <healthcheck.json> --cdp-url http://127.0.0.1:9888 --timeout-seconds 45 --health-check-only
```

成功信号必须同时满足 `status=health_ok`、`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。

新 campaign 或策略变化较大时先跑 `--max-jobs 1` probe。probe clean 后再跑整包。

### S8 详情抓取

调用：

```bash
python -m scripts.maimai_ai_infra_detail_live_gate --plan <pack.json> --out <capture.json> --cdp-url http://127.0.0.1:9888 --delay-seconds <n> --timeout-seconds 45
```

成功 job raw 写到 `raw/detail-live/<pack_id>/job-*.json`。重跑同一 pack 时复用 `next_resume_index()`，跳过已完成 job。

### S9 详情导入

整包完成且 `partial=false` 后先 dry-run：

```bash
python -m scripts.maimai_ai_infra_pipeline detail-wave dry-run --campaign-root <campaign_root> --wave <pack_id> --capture-file <capture.json> --db <campaign_root>/talent.db
```

若 `matched=target_count`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`，并且 run-policy 允许 campaign DB 自动 apply，则执行：

```bash
python -m scripts.maimai_ai_infra_pipeline detail-wave apply --campaign-root <campaign_root> --wave <pack_id> --capture-file <capture.json> --db <campaign_root>/talent.db --confirm "确认写入脉脉详情"
```

任何 partial capture 不允许 apply。

### S10 详情评分和精排

调用：

```bash
python -m scripts.maimai_ai_infra_rank --db <campaign_root>/talent.db --config <campaign_root>/strategy.json --mode detailed --candidate-ids-file <targets.json> --out-json <campaign_root>/reports/final-detail-rank.json --out-md <campaign_root>/reports/final-detail-rank.md
```

只对详情目标集合精排，避免混入非本轮候选人。

### S11 交付报告

调用：

```bash
python -m scripts.maimai_ai_infra_delivery_report --campaign-root <campaign_root> --targets <targets.json> --rank-json <rank.json> --out-report-json <final_report.json> --out-report-md <final_report.md> --out-outreach-json <outreach.json> --out-outreach-md <outreach.md>
python -m scripts.maimai_ai_infra_outreach_export --outreach-json <outreach.json> --out-csv <execution.csv> --out-md <execution.md> --out-audit-json <audit.json> --out-audit-md <audit.md>
```

报告必须包含 funnel、最终标签分布、P0/P1/P2、方向覆盖、公司覆盖、风险标记、详情推翻列表判断的误判分析、下一轮缺口建议。

### S12 飞书交付包

若 run-policy 允许发布飞书交付包，调用正式化后的 Feishu helper：

```bash
python -m scripts.feishu_delivery_package --campaign-root <campaign_root> --final-report <final_report.json> --outreach-csv <execution.csv> --audit-json <audit.json> --manifest-out <feishu_manifest.json>
```

该阶段只上传摘要文档、候选人 Sheet、outreach queue Sheet，不上传 SQLite DB、sync zip、raw capture、raw live run。

## 重试策略

自动重试只允许处理非平台安全类瞬时错误：

- 本地文件锁或临时 I/O 错误。
- CDP 连接短暂不可用，但下一次 health check clean。
- `Connection timed out` 且页面 health clean。
- Feishu CLI 网络瞬断或 token 可刷新。

默认最多 3 次指数退避。以下错误不自动重试：

- 登录页。
- 验证码或安全验证。
- 403、429、432。
- 非 JSON、HTML 响应。
- 模板字段漂移。
- 详情 capture `partial=true`。
- dry-run 出现 blockers、unmatched、failed jobs。

不自动重试的错误进入 `blocked` 状态，生成 continuation plan 并通知负责人。

## 恢复策略

搜索恢复以 `raw/search/unit-*/page-*.json` 为事实来源。`state/search-progress.json` 只作为缓存，恢复时必须扫描 canonical raw pages 重建进度。

详情恢复以 `raw/detail-live/<pack_id>/job-*.json` 为事实来源。重跑同一 pack 时从第一个缺失 job 继续。

Wave apply 和 detail apply 以 `state/import-ledger.jsonl` 为防重事实来源。ledger 已记录 completed 的 wave/pack 不允许再次 apply，只允许重新生成报告。

恢复命令统一由 `state/continuation-plan.json` 提供，包含：

```json
{
  "campaign_id": "example",
  "blocked_stage": "detail_live",
  "reason": "captcha_api",
  "safe_to_resume_after": "负责人完成验证码并确认人才银行页 health clean",
  "resume_command": "python -m scripts.maimai_campaign_orchestrator resume --campaign-root data/campaigns/example",
  "checkpoint_source": "raw/detail-live/detail-ab-pack-003/job-*.json"
}
```

## 通知设计

新增通知抽象 `scripts/campaign_notify.py`，第一版支持本地文件和控制台，后续可接入飞书 IM。

每次停机通知包含：

- campaign id。
- 当前 stage。
- 已完成数量和总量。
- 停机原因。
- 证据文件。
- 负责人需要执行的动作。
- 恢复命令。

通知本身失败不能吞掉停机原因；必须写入 `reports/interruption-*.json` 和 `state/events.jsonl`。

## 权限和预授权

`run-policy.json` 明确每类动作的授权：

```json
{
  "allow_live_search": true,
  "allow_campaign_db_auto_apply_after_clean_dry_run": true,
  "allow_detail_live_after_health_ok": true,
  "allow_detail_campaign_db_auto_apply_after_clean_dry_run": true,
  "allow_main_db_write": false,
  "allow_feishu_delivery_publish": false,
  "stop_on_platform_security_signal": true,
  "max_auto_retries": 3
}
```

主库同步仍走现有安全路径：`talent_sync.py export`、`verify-bundle`、主库 dry-run、主库备份、显式确认 apply。

## 已有能力复用映射

| 阶段 | 复用能力 |
|---|---|
| JD/需求辅助解析 | `scripts/jd_analyzer.py`、`scripts/score_pipeline.py` |
| 搜索 API 规格 | `scripts/maimai_search_api_spec.py` |
| 搜索计划 | `scripts/maimai_ai_infra_search_plan.py` |
| 搜索 live gate | `scripts/maimai_ai_infra_search_live_gate.py` |
| Campaign 路径和页级 raw | `scripts/maimai_ai_infra_campaign.py` |
| Wave 导入 | `scripts/maimai_ai_infra_pipeline.py run-campaign` |
| 列表/详情评分 | `scripts/maimai_ai_infra_rank.py` |
| 详情任务包 | `scripts/maimai_ai_infra_detail_plan.py`、`scripts/maimai_detail_targets.py` |
| 详情 live gate | `scripts/maimai_ai_infra_detail_live_gate.py` |
| 详情导入 | `scripts/maimai_ai_infra_pipeline.py detail-wave`、`scripts/maimai_detail_import.py` |
| 详情覆盖报告 | `scripts/maimai_ai_infra_detail_report.py` |
| 最终交付报告 | `scripts/maimai_ai_infra_delivery_report.py` |
| 外联包 | `scripts/maimai_ai_infra_outreach_export.py` |
| 主库同步 | `scripts/talent_sync.py` |

## 测试计划

新增测试集中在编排胶水，不重复测试已覆盖的业务逻辑：

1. Skill 输出 schema 测试：需求确认结果能生成 requirements、strategy、run-policy。
2. Orchestrator 状态机测试：每个 stage 能进入下一阶段，失败时进入 blocked。
3. Search live standardize 测试：从 live-run fixture 写出 canonical `raw/search/unit-*/page-*.json`。
4. Resume 测试：扫描 raw pages 重建搜索进度，覆盖 `state/search-progress.json` 滞后的情况。
5. Detail resume 测试：已有 job raw 时从第一个缺失 job 继续。
6. Ledger 防重测试：已 apply 的 wave/pack 不重复写入。
7. Safety stop 测试：验证码、403、429、非 JSON、partial capture 不触发 apply。
8. Delivery parity 测试：用 `data/campaigns/ai-infra-v2-2026-05-15-dry-run` 的 fixture 或脱敏 fixture 验证最终 funnel 行数和标签分布。
9. Feishu helper dry-run 测试：生成 docs/sheets payload，不真实发布。

验收命令：

```bash
python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_detail_live_gate.py -q
python -m pytest tests/test_maimai_ai_infra_delivery_report.py tests/test_maimai_ai_infra_outreach_export.py tests/test_talent_sync.py -q
python -m pytest tests scripts -q
```

## 验收标准

- 能从自然语言需求生成结构化 campaign spec 和搜索实施计划。
- 能复用现有 AI Infra V2 campaign 产物做 replay，不触发真实脉脉请求。
- 能按 wave 执行搜索、标准化 raw、导入 campaign DB、评分和生成详情包。
- 能在 detail pack 中断后从 job raw 恢复。
- 平台安全信号出现时不自动重试真实请求，不 apply partial 数据。
- Clean dry-run 后仅写 campaign DB，不写主库。
- 生成 final report、outreach queue、quality audit。
- Feishu 发布阶段只上传筛选后的交付产物。
- `tasks/todo.md` 记录执行计划和 Review。

## 设计自检

- 范围聚焦在产品化入口和长任务编排，没有重写已有搜索、详情、评分和报告逻辑。
- 安全边界与 Phase 0、feasible execution、workbench V2 文档一致。
- 状态恢复以 raw artifacts 和 ledger 为准，避免依赖可能滞后的 progress cache。
- 所有真实平台动作都有 stop condition，所有写库动作都有 dry-run 和授权边界。
- Feishu 交付明确排除 raw DB/capture 上传。
