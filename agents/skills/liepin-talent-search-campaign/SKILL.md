---
name: liepin-talent-search-campaign
description: Use when the user wants to create or run a Liepin recruiting-side talent search campaign through an already logged-in browser page, including jobId-based resume search, raw capture, standardization, and recoverable CLI orchestration.
---

# liepin-talent-search-campaign

## 目标

把一次猎聘招聘端人才搜索整理成可执行、可恢复、可审计的 P0 campaign 合同。该 Skill 负责业务输入抽取、`jobId` 和搜索条件整理、运行边界确认、合同文件生成，并交接到 `agents/workflows/liepin-unattended-campaign/AGENT.md`。

## 触发语义

用户表达以下意图时使用本 Skill：

- 根据猎聘职位 `jobId` 搜简历。
- 构建猎聘 CLI、猎聘寻访 campaign、猎聘简历搜索任务。
- 使用已登录猎聘页面执行 `search-resumes`。
- 对猎聘搜索 raw 做标准化、摘要和恢复计划。
- 继续或恢复已有猎聘 campaign。

如果用户只是调研接口，先记录接口结论；如果用户明确进入实施或执行 campaign，则读取 canonical workflow。

## 输入抽取

优先从用户输入中抽取：

- `campaign_id`
- `jobId`
- 目标职位或岗位名称
- 搜索城市、学历、年限、关键词、排序和简历类型覆盖项
- 页数上限
- 是否只做 dry-run、是否允许真实浏览器内 fetch

只对缺失或冲突的关键字段提问。P0 最小可执行输入是 `jobId`，或一组明确的通用搜索条件。

## 默认运行策略

- `execution_surface="cdp_in_page_fetch"`
- 默认 `max_pages=1`
- 单次人工确认后最多 `max_pages=5`
- `allow_detail_fetch=false`
- `allow_campaign_db_write=false`
- `allow_main_db_write=false`
- `main_db_sync_mode="manual_only"`
- 不读取 Chrome cookie、localStorage、profile、密码或 session store。
- 不做脱离浏览器登录上下文的纯 HTTP 客户端。
- 不自动导航、刷新或点击猎聘业务页面。

## 输出产物

默认根目录：`data/campaigns/<campaign_id>/`。

必须生成或维护：

- `requirements.json`
- `strategy.json`
- `run-policy.json`
- `campaign-manifest.json`
- `raw/condition/job-<job_id>.json`
- `raw/search/page-000.json`
- `state/events.jsonl`
- `state/request-ledger.jsonl`
- `state/continuation-plan.json`
- `structured/candidate-summaries.jsonl`
- `reports/search-summary.json`
- `reports/search-summary.md`
- `reports/search-import-dry-run.json`
- `reports/search-import-dry-run.md`
- `reports/search-import-apply.json`
- `reports/search-import-apply.md`
- `reports/campaign-summary.json`
- `reports/campaign-summary.md`
- `reports/candidate-pool-diagnostic.json`
- `reports/candidate-pool-diagnostic.md`
- `reports/interruption-*.json`

## 安全边界

- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 遇到登录失效、验证码、安全页、403、429、432、非 JSON、HTML 响应、`flag != 1` 或模板漂移，必须立即停止并写恢复计划。
- 停机不等于失败；只要 raw 和 continuation 完整，可以在用户处理平台状态后恢复。
- P0 不抓简历详情，不还原脱敏姓名，不写主人才库。候选池诊断只基于列表摘要生成详情优先级预览，不等同于推荐报告。

## 详情 smoke 边界

- 详情 smoke 必须在候选池诊断完成后单独确认；不能由搜索、标准化或候选池诊断自动触发。
- 默认只生成 `detail_p0` 前 10 人目标包，单次上限 20。
- target pack 生成只读取本地 `structured/candidate-summaries.jsonl`，不触发猎聘请求。
- live 详情 smoke 使用页面内 fetch 调用 `POST /api/com.liepin.rresume.userh.pc.resume-view`，请求体为 `paramForm`，并复用 `state/request-template.json` 中清洗后的安全 header。
- live 详情 smoke 遇到登录、验证码、安全页、401、403、429、432、非 JSON、详情页 HTML、业务阻断或 partial capture 必须立即停止并写 interruption/continuation。
- 详情接口返回 `code=11000` 且语义为候选人隐私保护时，记录为候选级 `privacy_protected` 终态并继续后续候选。
- 如果详情页返回 HTML，下一步是 `calibrate-detail-api` 被动校准：用户手动打开详情页，CLI 只监听 CDP Network 事件形态，不触发猎聘请求，不保存 Cookie、header 值、query 值、请求 body 值或响应字段值。
- 详情 smoke 不写 Campaign DB，不写主库，不写 `data/talent.db`。
- 详情 smoke 不生成推荐报告，不生成推荐结论，不生成外联队列（outreach queue），不生成飞书交付包（Feishu package）。
- 详情 smoke 完成后可以运行离线 `detail-dry-run` 验收；该阶段只读取 `raw/detail-live/<pack_id>/job-*.json` 和 target pack，不触发猎聘请求，不连接 CDP，不写 Campaign DB，不写主库。
- `detail-dry-run` 允许把 `code=11000` 统计为候选级 `privacy_protected` 终态；只在缺 raw、platform mismatch、partial detail、非 JSON、HTML 详情壳、失败 job 或 apply blocker 时标记为不 clean。
- `detail-apply` 必须在 `detail-dry-run` clean 后运行，要求确认文本 `确认写入猎聘详情`，只把可用详情写入 campaign-local `talent.db`；隐私保护候选只计数不写详情。
- `detail-apply` 不写主库 `data/talent.db`，不触发猎聘请求，不生成推荐报告、外联队列或飞书交付包。
- full detail pack planning 使用 `plan-detail-packs`，只读取 `structured/candidate-summaries.jsonl` 和既有 terminal detail jobs，生成 `raw/detail-targets/detail-targets-<scope>.json` 与分包 pack；该阶段不连接 CDP，不触发猎聘请求，不写数据库。
- full detail live execution 必须在 `plan-detail-packs` 后另起确认点，通过 `run-live-detail-pack` 执行单个已规划 pack；默认上限 100，仍使用页面内 fetch 调用 `POST /api/com.liepin.rresume.userh.pc.resume-view`。
- `run-live-detail-pack` 复用详情 smoke 的停机规则，逐人写 `raw/detail-live/<pack_id>/job-*.json`，追加 `state/detail-request-ledger.jsonl`，并写 `reports/detail-pack-<pack_id>-summary.json/.md`。
- 恢复执行只信磁盘事实：已完成或 `privacy_protected` 的 terminal job 必须跳过并记录 `detail_skipped_terminal`；全部 target 已经是 terminal job 时不得连接 CDP，只写摘要并追加 `detail_pack_already_terminal`。
- `run-live-detail-pack` 遇登录、验证码、安全页、401、403、429、432、非 JSON、详情页 HTML、业务阻断、platform mismatch 或 partial capture 必须立即停止并写 interruption/continuation。
- full detail live 仍不写 Campaign DB，不写主库 `data/talent.db`，不生成推荐报告、外联队列或飞书交付包；详情入库仍必须后续运行 `detail-dry-run` 和确认文本 `detail-apply`。

## 搜索结果 Campaign DB 边界

- 搜索结果导入 Campaign DB 必须先运行 `import-search-dry-run`，该阶段只读取 `structured/candidate-summaries.jsonl`，不触发猎聘请求，不连接 CDP，不写 `talent.db`。
- `import-search-apply` 必须要求确认文本 `确认写入猎聘搜索结果`，只写 campaign-local `data/campaigns/<campaign_id>/talent.db`，并追加 `state/import-ledger.jsonl`。
- 搜索导入报告不得包含 `showresumedetail`、`ck_id/sk_id/fk_id`、`rawPreview` 或平台 token 值。
- 搜索导入仍禁止写主库 `data/talent.db`；主库同步必须另起人工确认流程。

## Campaign DB 摘要边界

- `campaign-summary` 只读 campaign-local `talent.db`，输出 `reports/campaign-summary.json` 和 `reports/campaign-summary.md`。
- 摘要只包含候选总数、详情覆盖、城市/学历/年限/公司/职位分布和详情质量统计。
- `campaign-summary` 不是推荐报告，不生成外联队列，不发布飞书，不写 Campaign DB，不写主库。

## 自动交接

合同文件生成后，读取并执行 `agents/workflows/liepin-unattended-campaign/AGENT.md`。真实浏览器内请求必须由 workflow 按阶段和运行策略控制。
