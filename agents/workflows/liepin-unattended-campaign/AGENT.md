---
name: liepin-unattended-campaign
description: 猎聘招聘端人才搜索的 canonical workflow，约束 CDP 页面内 fetch、raw 落盘、标准化、停机恢复和主库边界。
---

# liepin-unattended-campaign

## 触发入口

- 从 `agents/skills/liepin-talent-search-campaign/SKILL.md` 生成需求合同后交接执行。
- 用户要求继续执行已有猎聘 campaign、恢复中断、标准化 raw、生成摘要或准备单页 smoke test。
- 只接受落盘合同作为执行事实来源：`requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。

## 安全边界

- 不读取 Chrome cookie、localStorage、profile、密码或 session store。
- 不构建脱离浏览器登录上下文的纯 HTTP 客户端。
- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 不自动导航、刷新或点击已进入执行态的猎聘业务页面。
- 不抓简历详情，不还原脱敏姓名，不写主人才库。
- `allow_detail_fetch=false`、`allow_campaign_db_write=false`、`allow_main_db_write=false` 是 P0 固定边界。

## 停机条件

遇到以下任一情况必须停止当前阶段，不得继续翻页、重试或推进下游：

- 登录页或登录失效。
- 验证码、安全验证或访问异常。
- HTTP 403、429、432。
- 非 JSON、HTML 响应。
- JSON `flag` 不等于 `1`。
- 响应缺少 P0 必需字段，例如 `data.cardResList` 或 `data.resList`。
- 无法确认当前页面是可用的猎聘招聘端页面。

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl` 或 `state/request-ledger.jsonl`，并更新 `state/continuation-plan.json`。

## 阶段

### S0 需求合同

读取 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`，确认 `jobId`、搜索覆盖项、页数上限、浏览器执行面和主库人工边界。

### S1 页面预检

优先使用独立 CDP Chrome profile，而不是 Codex Chrome extension。确认计划后执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator launch-browser --profile data/session/liepin-cdp-profile --remote-debugging-port 9898
```

用户在该专用浏览器中完成登录并进入猎聘找简历页后，预检只读取页面 URL、标题和可见文本。页面不满足条件时停止，并要求用户手动打开可用页面。

### S2 条件生成

当有 `jobId` 时，通过页面内受控 fetch 调用：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.get-search-condition-by-job
```

成功响应保存到 `raw/condition/job-<job_id>.json`。失败按停机条件处理。

### S3 搜索计划展开

把 `strategy.json.page_plan` 展开为 `curPage` 计划。P0 默认 1 页，人工确认后最多 5 页。计划写入 `state/continuation-plan.json`。

### S3a 宽召回 adaptive 搜索规划

当 `strategy.json` 明确设置 `strategy_mode=liepin_broad_recall_adaptive_v1` 时，先运行离线规划：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-adaptive-search --campaign-root data/campaigns/<campaign_id>
```

该阶段只读取 `strategy.json`，生成 `search-units.jsonl`、`raw/search-live-runs/wave-plan.json`、wave sidecar 和 `reports/broad-recall-plan.*`。它不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储，不写数据库。

S3a 完成后停止在确认点。后续要执行 live 搜索时，必须由用户单独确认，并继续沿用 S4 的登录、验证码、安全页、HTTP 403/429/432、非 JSON、`flag != 1` 和模板漂移停机规则。

### S3b 宽召回 adaptive single-wave live 执行

`plan-adaptive-search` 完成并经单独确认后，允许只执行一个已规划 wave sidecar：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-adaptive-search --campaign-root data/campaigns/<campaign_id> --wave-plan raw/search-live-runs/search-wave-001-plan.json --cdp-url http://127.0.0.1:9898 --delay-seconds 3 --timeout-seconds 30 --run-id adaptive-search-wave-001
```

`run-live-adaptive-search` 只读取 wave sidecar 中的 unit、页码和 `search_params_overrides`，不得重新生成搜索条件，不得自动扩大到其他 wave。执行中逐页写 `raw/search-adaptive/<wave_id>/<unit_id>/page-*.json`，追加 `state/request-ledger.jsonl`，并写 `reports/page-quality-<wave_id>.jsonl` 与 `state/adaptive-unit-state-<wave_id>.json`。

恢复时只信磁盘事实：扫描 `raw/search-adaptive/<wave_id>/<unit_id>/page-*.json`、`reports/page-quality-<wave_id>.jsonl` 和 `state/adaptive-unit-state-<wave_id>.json`。已成功 raw 页面不得重复请求；已有 page-quality 行不得重复追加；从下一缺失页继续。当 unit 或整个 wave 已经全终止时，只更新恢复状态和 run summary，不得连接 CDP。

该阶段通过已登录页面上下文调用猎聘搜索接口；不得读取 cookie、localStorage、sessionStorage、Chrome profile 或 session store。遇登录、验证码、安全页、HTTP 403/429/432、非 JSON、`flag != 1`、模板漂移或无法确认猎聘找简历页时立即停止并写 interruption/continuation。

该阶段只写 raw search、页质报告和恢复状态，不写 Campaign DB，不写主库 `data/talent.db`，不生成推荐报告、外联队列或飞书交付包。搜索结果入库必须后续另跑 `import-search-dry-run` 和确认文本 `import-search-apply`。

### S3c 宽召回 adaptive 搜索标准化

adaptive live 完成后，先把指定 wave 的 raw search 标准化为候选摘要：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator standardize-adaptive-search --campaign-root data/campaigns/<campaign_id> --wave-id search-wave-001
```

`standardize-adaptive-search` 只读取 `raw/search-adaptive/<wave_id>/<unit_id>/page-*.json`，写 `structured/candidate-summaries.jsonl`、`reports/search-summary.json` 和 `reports/search-summary.md`。该阶段不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储，不写数据库。标准化完成后，才允许回到 `import-search-dry-run` 和确认文本 `import-search-apply`。

### S3d 宽召回 adaptive 摘要

adaptive 搜索标准化、导入 dry-run/apply 和 Campaign Summary 完成后，可以生成只读宽召回摘要：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator broad-recall-summary --campaign-root data/campaigns/<campaign_id>
```

`broad-recall-summary` 只读取 `reports/page-quality-*.jsonl`、`reports/search-summary.json`、`reports/search-import-*.json` 和 `reports/campaign-summary.json`，写 `reports/broad-recall-summary.json` 与 `reports/broad-recall-summary.md`。它不连接 CDP，不触发猎聘请求，不写数据库，不生成推荐报告、外联队列或飞书交付包。

### S3e 主库同步 handoff dry-run

Campaign DB 摘要或 broad-recall summary 完成后，可以生成主库同步前置材料：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator main-db-sync-handoff --campaign-root data/campaigns/<campaign_id> --main-db data/talent.db
```

`main-db-sync-handoff` 只读取 campaign-local `talent.db`，导出 `exports/talent-sync-*.zip`，校验 bundle，并对目标主库执行 dry-run import plan，写 `reports/main-db-sync-handoff.json` 与 `reports/main-db-sync-handoff.md`。该阶段不得自动执行主库同步，不得执行 `talent_sync.py import --apply`，不得创建或修改 `data/talent.db`。

真实主库写入必须另起确认流程：先 dry-run clean，再备份主库，再用同步确认文本 apply，最后执行完整性验证和冲突处理。

猎聘寻访 workflow 到此只提供后续交付前置能力，不直接生成候选人推荐报告、外联队列或飞书交付包。主库同步完成后，后续精准匹配、推荐报告、外联表和飞书发布必须交给 `jd-talent-delivery`。

### S4 搜索执行

逐页通过 CDP `Runtime.evaluate` 在已登录页面上下文内执行受控 fetch：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes
```

执行命令：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-search --campaign-root data/campaigns/<campaign_id> --cdp-url http://127.0.0.1:9898 --max-pages 1
```

每页成功后立即写 `raw/search/page-<curPage>.json`，并追加 `state/request-ledger.jsonl`。真实执行阶段不自动刷新、导航或点击业务页面。CDP live gate 不读取浏览器敏感存储；登录态只由页面上下文自然携带。

### S5 恢复

恢复时只信磁盘事实：扫描 `raw/search/page-*.json`、`state/request-ledger.jsonl` 和 `state/continuation-plan.json`。已成功页不得重复请求；从下一页继续。

### S6 标准化

运行 `scripts.liepin_search_standardize`，从 `cardResList` 或 `resList` 输出 `structured/candidate-summaries.jsonl`、`reports/search-summary.json` 和 `reports/search-summary.md`。字段结构漂移时记录 `template_drift`，不生成不完整结论。

### S7 候选池诊断

运行 `scripts.liepin_campaign_orchestrator diagnose-pool`，只读取 `structured/candidate-summaries.jsonl`，生成 `reports/candidate-pool-diagnostic.json` 和 `reports/candidate-pool-diagnostic.md`。该阶段只做分布统计和 `detail_p0/detail_p1/detail_p2/skip` 详情优先级预览，不触发新的猎聘请求，不抓详情，不写数据库，不生成最终推荐报告。

### S7d 搜索结果 Campaign DB dry-run/apply

搜索标准化完成后，允许先做 search import dry-run：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator import-search-dry-run --campaign-root data/campaigns/<campaign_id>
```

该阶段只读取 `structured/candidate-summaries.jsonl`，在临时 DB 中模拟写入，生成 `reports/search-import-dry-run.json` 与 `reports/search-import-dry-run.md`。不得连接 CDP，不得触发猎聘请求，不得读取浏览器敏感存储，不得创建或修改 campaign-local `talent.db`。

dry-run clean 后，允许在明确确认文本下写入 campaign-local DB：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator import-search-apply --campaign-root data/campaigns/<campaign_id> --confirm 确认写入猎聘搜索结果
```

`import-search-apply` 只写 `data/campaigns/<campaign_id>/talent.db`，并追加 `state/import-ledger.jsonl`；不得写主库 `data/talent.db`。搜索导入报告不得包含 `showresumedetail`、`ck_id/sk_id/fk_id`、`rawPreview` 或平台 token 值。

### S7a P1 详情 smoke 目标包

候选池诊断完成后，详情 smoke 必须单独确认；不得把候选池诊断自动升级为详情请求。默认只选择 `detail_p0` 前 10 人，单次上限 20。

确认后先生成 target pack：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-smoke --campaign-root data/campaigns/<campaign_id> --priority detail_p0 --limit 10
```

该命令只读取 `structured/candidate-summaries.jsonl` 和候选池诊断优先级，写 `raw/detail-targets/liepin-detail-p0-smoke-001.json`、`reports/detail-smoke-targets.json` 和 `reports/detail-smoke-targets.md`。生成 target pack 不触发猎聘请求。

### S7b P1 详情 smoke live gate

再次确认 CDP 页面可用后，才允许执行详情 smoke：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-smoke --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json --cdp-url http://127.0.0.1:9898 --limit 10 --delay-seconds 3 --timeout-seconds 30 --run-id detail-smoke-001
```

详情 smoke 逐人通过页面内 fetch 调用详情 JSON 接口：

```text
POST https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view
```

请求体使用 `paramForm`，并复用 `state/request-template.json` 中清洗后的安全 header；不得读取 Cookie 或浏览器存储。逐人写 `raw/detail-live/<pack_id>/job-*.json`，并追加 `state/detail-request-ledger.jsonl`。遇到登录页、验证码、安全页、401、403、429、432、非 JSON、详情页 HTML、业务阻断或 partial capture 时立即停止，写 interruption 和 continuation。

例外：详情接口返回 `code=11000` 且语义为候选人隐私保护时，这是候选级终态 `privacy_protected`，应写入对应 `job-*.json` 并继续后续候选；不得将其视为整包风控或整包失败。

如果停止原因为 `detail_html`，说明 `showresumedetail` 返回详情页外壳而不是真实 JSON 详情接口；不得重试 `run-live-detail-smoke`。下一步只能先进入被动详情 API 校准，由用户在页面中手动打开详情页，CLI 只监听 CDP Network 事件：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator calibrate-detail-api --campaign-root data/campaigns/<campaign_id> --cdp-url http://127.0.0.1:9898 --listen-seconds 30 --run-id detail-api-calibration-001
```

`calibrate-detail-api` 不导航、不点击、不发起猎聘请求；只记录允许 host 的 JSON XHR/Fetch 接口形态，包括 host、path、query key、payload key 和响应字段名。不得保存 Cookie、header 值、query 值、请求 body 值或响应字段值。

详情 smoke 只写 `reports/detail-smoke-summary.json` 和 `reports/detail-smoke-summary.md` 作为执行摘要，不生成推荐报告，不生成推荐结论，不写 Campaign DB，不写主库，不写 `data/talent.db`，不写外联队列（outreach queue），不生成飞书交付包（Feishu package）。

### S7c P1 详情 raw 离线 dry-run

详情 smoke 完成后，允许运行离线 dry-run 验收：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-dry-run --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json
```

该阶段只读取 target pack 和 `raw/detail-live/<pack_id>/job-*.json`，写 `reports/detail-dry-run.json` 与 `reports/detail-dry-run.md`。它不连接 CDP，不触发猎聘请求，不读取浏览器敏感存储，不写 Campaign DB，不写主库 `data/talent.db`。

dry-run 必须统计：

- `ready_for_campaign_db_count`：字段结构完整且无 apply blocker 的详情数。
- `privacy_protected_count`：`code=11000` 的候选级隐私保护终态。
- `missing_raw_count`、`failed_job_count`、`capture_blocker_count` 和 `apply_blocker_count`。
- `clean`：缺 raw、unexpected raw、失败 job、capture blocker、apply blocker 均为 0 时为 true；隐私保护不视为整包阻断。

`detail-dry-run` 仍不是 Campaign DB apply；搜索结果导入、详情 apply、主库同步、推荐和交付必须另起设计和实施计划，并经过 dry-run、备份、apply 和完整性验证。

### S7e P1 详情 apply 到 Campaign DB

`detail-dry-run` clean 且搜索结果已经写入 campaign-local `talent.db` 后，允许在确认文本下写入详情：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-apply --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json --confirm 确认写入猎聘详情
```

`detail-apply` 只写 `data/campaigns/<campaign_id>/talent.db` 的 `candidate_details`，并追加 `state/import-ledger.jsonl`；不得写主库 `data/talent.db`。隐私保护候选计入 `privacy_protected_count`，不写详情，不视为整包失败。遇到缺 raw、unexpected raw、失败 job、capture blocker、apply blocker 或 campaign DB 缺失时必须拒绝写入。

详情 apply 后仍不得生成推荐报告、推荐结论、外联队列或飞书交付包；这些必须另起设计。

### S7f Campaign DB 本地摘要

搜索结果和小批详情写入 campaign-local `talent.db` 后，允许生成只读本地摘要：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator campaign-summary --campaign-root data/campaigns/<campaign_id>
```

`campaign-summary` 只读 `data/campaigns/<campaign_id>/talent.db`，写 `reports/campaign-summary.json` 和 `reports/campaign-summary.md`。报告只包含候选总数、详情覆盖、城市/学历/年限/公司/职位分布和详情质量统计。它不是推荐报告，不生成推荐结论、外联队列或飞书交付包，不写 Campaign DB，不写主库 `data/talent.db`。

### S7g Full detail pack planning

需要扩大详情抓取前，必须先只做目标包规划：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-packs --campaign-root data/campaigns/<campaign_id> --priorities detail_p0,detail_p1 --pack-size 100 --scope p0-p1
```

`plan-detail-packs` 只读取 `structured/candidate-summaries.jsonl`、候选池诊断规则和既有 `raw/detail-live` terminal jobs。它会扣除已完成或隐私保护的 terminal jobs，写 `raw/detail-targets/detail-targets-<scope>.json`、`raw/detail-targets/detail-<scope>-pack-*.json`、`reports/detail-pack-plan.json` 和 `reports/detail-pack-plan.md`。

该阶段只做 planning，不连接 CDP，不触发猎聘请求，不写 Campaign DB，不写主库 `data/talent.db`，不生成推荐报告、外联队列或飞书交付包。后续 live detail 扩大执行必须另起确认点。

### S7h Full detail live execution recovery

`plan-detail-packs` 完成并经过单独确认后，允许按单个 pack 执行 full detail live runner：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 100 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-001
```

`run-live-detail-pack` 只执行已规划 target pack，不重新选择候选，不自动扩大到其他 pack。执行面仍是已登录猎聘页面内 fetch：

```text
POST https://api-h.liepin.com/api/com.liepin.rresume.userh.pc.resume-view
```

请求体使用 `paramForm`，并复用 `state/request-template.json` 中清洗后的安全 header；不得读取 Cookie、localStorage、sessionStorage、Chrome profile 或 session store。

恢复执行只信磁盘事实：扫描 `raw/detail-live/<pack_id>/job-*.json`。已完成或 `privacy_protected` 的 terminal job 必须跳过并向 `state/detail-request-ledger.jsonl` 追加 `detail_skipped_terminal`；全部 target 已经是 terminal job 时不得连接 CDP，只写 `reports/detail-pack-<pack_id>-summary.json/.md` 并追加 `detail_pack_already_terminal`。

执行中逐人写 `raw/detail-live/<pack_id>/job-*.json`，追加 `state/detail-request-ledger.jsonl`，并在完成或停止时写 `reports/detail-pack-<pack_id>-summary.json` 与 `reports/detail-pack-<pack_id>-summary.md`。`code=11000` 仍是候选级 `privacy_protected` 终态，应继续后续候选。

遇到登录页、验证码、安全页、401、403、429、432、非 JSON、详情页 HTML、业务阻断、platform mismatch 或 partial capture 时必须立即停止，写 `reports/interruption-detail-<pack_id>-*.json` 和 `state/detail-live-<pack_id>-continuation-after-<reason>.json`。停止后不得盲目重试；必须由用户处理平台状态或重新校准后恢复。

该阶段只写 raw detail 和恢复账本，不写 Campaign DB，不写主库 `data/talent.db`，不生成推荐报告、推荐结论、外联队列或飞书交付包。详情入库必须回到离线 `detail-dry-run` 和确认文本 `detail-apply` 流程。

### S8 关闭

P0 到搜索摘要和候选池诊断即止；P1 详情 smoke 只在单独确认后小批执行，详情 raw dry-run 和详情 apply 只服务于 campaign-local DB 闭环。Full detail pack planning 只生成目标包；Full detail live execution recovery 只写 raw detail 和恢复账本。主库同步、推荐和交付必须另起设计和实施计划，并经过 dry-run、备份、apply 和完整性验证。

## 验收

- 任一阶段失败都必须留下可恢复的事实来源和明确状态。
- raw 搜索页必须以 `curPage` 零基页码保存。
- 标准化输出必须保留 `resIdEncode`、`usercIdEncode`、`detailUrl` 和 `ckId/skId/fkId`。
- 主人才库不在本 workflow 内写入。
