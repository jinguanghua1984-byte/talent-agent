# 通用 Agent 项目架构改造执行清单（2026-05-09）

> 来源计划：`docs/superpowers/plans/2026-05-09-general-agent-architecture.md`
> 当前状态：**已完成**

## 任务清单

- [x] Task 1：建立运行时中立的 agent 规范层 — commit `42419d3`
- [x] Task 2：将 `platform-match` 可执行代码迁出 `.claude` — commit `0c93bf8`
- [x] Task 3：统一资源、规则和路径解析 — commit `28f1829`
- [x] Task 4：增加通用 LLM provider 抽象 — commit `ef3fdb2`
- [x] Task 5：让评分 pipeline 支持 provider/model 参数 — commit `a1d27a5`
- [x] Task 6：薄化 `.claude/skills` 为兼容 adapter — commit `f59119b`
- [x] Task 7：迁移 `public-search` token tracker — commit `a9d3d8b`
- [x] Task 8：更新 README、环境变量和依赖说明 — commit `f4a0e5e`
- [x] Task 9：全量验证与架构扫描 — commit `8ee80b3`

## Review

- 全量测试：`python -m pytest tests scripts -q`，结果 **356 passed**
- 架构扫描：`rg -n "\.claude" scripts agents/workflows rules README.md`，结果仅 `README.md:30`（适配器描述，符合预期）
- Canonical workflow 私有工具扫描：`rg -n "Claude Code|WebSearch|mcp__" agents/workflows`，结果 **无输出**（已清理）
- CLI smoke：`python scripts/score_pipeline.py run --help`，结果包含 `--provider` 和 `--model`

---

# maimai-scraper 批量详情 30/42 停滞诊断与日志增强（2026-05-11）
> 当前状态：**已完成**
> 问题：用户反馈 42 条详情抓取任务停在 30，怀疑高频 API 触发反爬，但日志没有相关输出。

## 任务清单

- [x] Task 1：定位 30/42 停滞根因，确认是否为 safe 策略批间暂停或真实风控失败
- [x] Task 2：先补扩展契约测试，覆盖批间暂停文案、暂停窗口状态、429/风控日志
- [x] Task 3：增强调度器状态，持久化批间休息窗口和恢复时间
- [x] Task 4：增强 background/popup/悬浮球日志与展示，明确“批间休息”和失败原因
- [x] Task 5：运行聚焦测试、JS 语法检查和必要回归
- [x] Task 6：记录调试经验到 `memory/error-log.md`

## 调查记录

- `extensions/maimai-scraper/detail_batch.js` 的 safe 策略 `batchSize=30`，每 30 个已处理任务后会等待 5-10 分钟再继续。
- 当前 `detail_batch_paused` 事件的日志只显示 `批量详情已暂停: batch_pause`，没有展示休息时长、预计恢复时间或 30/42 进度。
- 批间休息期间 `state.status` 仍保持 `running`，悬浮球和状态轮询看起来像“执行中但进度不动”。
- `inject.js` / `detail_batch.js` 目前只把 401/403 或验证码文本视作认证/风控失败，429 限流响应未纳入熔断判断。

## Review

- 根因判断：42 条任务停在 30，高概率是 safe 模式 `batchSize=30` 触发的 5-10 分钟批间休息；旧 UI/日志没有展示休息时长与预计恢复时间。
- 导出核对：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-11 (2).json` 中 `contacts=42`，但 `detailJobs=0`、`metadata.total_jobs=0`、`detailBatchLogs=0`，不是可用于复盘这轮 30/42 运行态的完整 job 导出。
- 修复：`DetailBatch` 持久化 `batch_pause_started_at`、`batch_pause_until`、`batch_pause_delay_ms`、`batch_pause_completed`；background 日志显示“批间暂停：已完成 x/y，休息 n 分钟后继续”；popup/悬浮球显示“批间休息中”。
- 风控日志增强：429 响应纳入认证/风控失败判断；单个详情 job 失败会记录 `detail_batch_job_failed`，日志包含联系人、原因、接口状态和“疑似登录失效、风控或限流”提示。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **23 passed**。
- 验证：`node --check extensions/maimai-scraper/detail_batch.js/background.js/popup.js/content.js/inject.js` -> **PASS**。
- 验证：`python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_scraper_extension.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q` -> **56 passed**。
- 验证：`python -m pytest tests scripts -q` -> **400 passed, 1 warning**。
- 打包：Chrome `--pack-extension` 使用现有 pem 重新打包成功。

---

# maimai-scraper 自动翻页请求头与分页元信息修复（2026-05-11）
> 当前状态：**已完成**
> 问题：被动拦截搜索翻页时的请求头内容缺少可视化追踪；自动翻页抓取传递的分页信息不正确，导致抓取数据总数不对。

## 任务清单

- [x] Task 1：追踪被动拦截搜索请求模板、请求头、分页字段和自动翻页重放数据流
- [x] Task 2：补失败测试，覆盖请求头追踪、分页字段识别和总数统计
- [x] Task 3：修复 `inject.js` 中搜索模板保存和 pager fetch 的分页参数传递
- [x] Task 4：修复 `autopager/background/popup` 的总数统计和可观测日志
- [x] Task 5：运行扩展聚焦测试、JS 语法检查、相关回归和打包
- [x] Task 6：把根因和修复记录到 `memory/error-log.md`

## 调查记录

- 导出样本 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-11 (2).json` 中真实搜索请求为 `/api/ent/v3/search/basic?...`，请求头至少包含 `x-csrf-token`。
- 真实请求 body 的分页字段位于 `search.paginationParam.page/size`，同时存在 `search.page=0`、`search.size=30`、`search.total=1000`、`search.total_match=1000`。
- 响应总数字段位于 `responseData.data.total=1000`、`total_match=1000`，单页数量位于 `count=30`，联系人列表位于 `list`。
- 旧 `pagerFetch` 只改顶层 `body.page/pageNum/pageNo`，没有改 `search.paginationParam.page`，导致自动翻页可能重复请求第一页或错误页。

## Review

- 修复 `inject.js`：新增 `extractPageMeta()` 和 `applyPagerPage()`，保存模板时记录 `requestHeaders/headerNames`；自动翻页重放时同步更新 `search.paginationParam.page/size`、`search.page` 和已有顶层分页字段。
- 修复 `content.js`：`pagerFetch` 响应回传 `pageMeta/headerNames`。
- 修复 `autopager.js`：每页响应后用 `updatePageMetaFromResponse()` 回写 `totalFromApi/pagesize/totalPages`，避免总数只依赖初始模板。
- 修复 `background.js` / `popup.js`：启动 pager 响应和导出元数据包含 `headerNames`；popup 模板区显示“请求头: ...”。
- 验证：新增扩展契约测试先红后绿，`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **25 passed**。
- 验证：Node smoke 模拟真实脉脉请求体，自动翻页到第 2 页时 `search.paginationParam.page=2`、`search.page=1`、`pageMeta.total=1000`、请求头名包含 `x-csrf-token`。
- 验证：`node --check extensions/maimai-scraper/inject.js/autopager.js/content.js/background.js/popup.js` -> **PASS**。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q` -> **58 passed**。
- 验证：`python -m pytest tests scripts -q` -> **402 passed, 1 warning**。
- 打包：Chrome `--pack-extension` 使用现有 pem 重新打包成功。

---

# maimai-scraper 批量详情逐条执行日志增强（2026-05-11）
> 当前状态：**已完成**
> 问题：用户需要在批量详情执行日志中看到每一条详情请求是否执行成功。

## 任务清单

- [x] Task 1：确认当前详情 job 成功/失败事件和 popup 日志展示链路
- [x] Task 2：补契约测试，覆盖逐条成功日志、逐条失败日志和 popup 明细展示数量
- [x] Task 3：在 `detail_batch.js` 成功完成单个 job 时发出明确事件
- [x] Task 4：在 `background.js` 中生成包含联系人、进度、接口状态的成功/失败日志
- [x] Task 5：调整 popup 日志展示，确保能看到更多逐条执行明细
- [x] Task 6：运行聚焦测试、JS 语法检查、相关回归和打包

## 调查记录

- 旧链路中失败 job 已有 `detail_batch_job_failed` 事件，成功 job 只有 `detail_batch_progress`，日志文案是“批量详情进度 x/y”，无法看出每个联系人是否成功。
- popup 日志列表只展示 `logs.slice(-8)`，批量详情任务较多时很容易看不到逐条结果。

## Review

- 修复 `detail_batch.js`：单个 job 成功保存后发出 `detail_batch_job_succeeded`，携带联系人摘要、接口状态和可选 warning。
- 修复 `background.js`：新增“详情抓取成功: 姓名，进度 x/y；接口状态 basic=200...”日志；失败日志保持“详情抓取失败: ...”，同样带接口状态。
- 修复 `popup.js`：执行日志展示从最后 8 条扩展为最后 50 条，便于查看每一条详情的成功/失败结果。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **26 passed**。
- 验证：`node --check extensions/maimai-scraper/detail_batch.js/background.js/popup.js` -> **PASS**。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q` -> **59 passed**。
- 验证：`python -m pytest tests scripts -q` -> **403 passed, 1 warning**。
- 打包：Chrome `--pack-extension` 使用现有 pem 重新打包成功。

---

# maimai-scraper 批量详情日志不可见修复（2026-05-11）
> 当前状态：**已完成**
> 问题：用户反馈页面上没有显示批量详情执行日志。

## 任务清单

- [x] Task 1：检查 popup HTML/CSS/JS 的日志容器、渲染函数和状态刷新链路
- [x] Task 2：补契约测试，覆盖日志容器可见、日志刷新触发和实时事件追加
- [x] Task 3：修复 popup 日志不可见或不实时更新的问题
- [x] Task 4：必要时增强悬浮球/主页面入口对日志状态的提示
- [x] Task 5：运行聚焦测试、JS 语法检查、相关回归和打包

## 调查记录

- `popup.html` 已有 `detail-log-list` 容器，但没有“执行日志”标题，用户不容易识别日志区域。
- `popup.js` 收到 `detail_batch_*` 实时事件时只调用 `renderDetailBatchState(msg)`，没有立刻刷新 `detailBatchLogs`；日志列表要等 5 秒轮询才更新。
- `popup.css` 的日志列表高度只有 120px，逐条日志较多时可见区域太小。

## Review

- 修复 `popup.html`：在批量详情状态区下方新增“执行日志（最近 50 条）”标题。
- 修复 `popup.js`：收到任意 `detail_batch_*` 事件后立即调用 `refreshDetailBatchStatus()`，实时拉取并渲染持久化日志。
- 修复 `popup.css`：日志列表高度从 120px 增加到 220px。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **26 passed**。
- 验证：`node --check extensions/maimai-scraper/popup.js` -> **PASS**。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q` -> **59 passed**。
- 验证：`python -m pytest tests scripts -q` -> **403 passed, 1 warning**。
- 打包：Chrome `--pack-extension` 使用现有 pem 重新打包成功。

## Follow-up Review - 实时请求日志仍不显示

- 用户截图显示新版日志区域已经出现，但只显示“已导入 90 条详情联系人”；状态为 `running — 13/90`，说明 job 状态和计数在更新，但 job 事件日志没有稳定写入。
- 根因：`detail_batch.js` 的 `emit(onEvent, event)` 没有等待 `background.appendDetailBatchLog()` 完成；多个 progress/success/failed 事件并发读写 `chrome.storage.local.detailBatchLogs`，读-改-写互相覆盖，导致只剩导入/启动类日志。
- 修复：`emit()` 改为 async，并把所有 `emit(onEvent, ...)` 调整为 `await emit(onEvent, ...)`，让日志写入串行化。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **26 passed**。
- 验证：`node --check extensions/maimai-scraper/detail_batch.js` -> **PASS**。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q` -> **59 passed**。
- 验证：`python -m pytest tests scripts -q` -> **403 passed, 1 warning**。
- 打包：Chrome `--pack-extension` 使用现有 pem 重新打包成功。

# maimai-scraper Chrome 扩展加载失败修复（2026-05-10）

> 当前状态：**已完成**
> 报错：`Invalid value for key 'declarative_net_request.rule_resources': The provided path 'rules.json' is invalid. 无法加载清单。`

## 任务清单

- [x] Task 1：检查 `extensions/maimai-scraper` 的 manifest 与资源文件
- [x] Task 2：定位 `declarative_net_request.rule_resources` 引用失败的根因
- [x] Task 3：实施最小修复，避免影响扩展其他功能
- [x] Task 4：验证 JSON/manifest 规则与项目测试

## Review

- 根因：`manifest.json` 声明了 `declarative_net_request.rule_resources`，但扩展目录缺少被引用的 `rules.json`，Chrome 因悬空规则资源拒绝加载清单。
- 修复：移除未使用的 `declarativeNetRequest` 权限和 `declarative_net_request` 配置，避免继续声明不存在的规则集。
- 静态验证：PowerShell `ConvertFrom-Json` 解析 manifest 成功，且无 `declarative_net_request` / `declarativeNetRequest` 残留。
- 扩展验证：`chrome.exe --pack-extension="D:\workspace\talent-agent\extensions\maimai-scraper"` 退出码 0。
- 全量测试：`python -m pytest tests scripts -q`，结果 **356 passed, 1 warning**。

---

# talent-library Skill 实施清单（2026-05-10）

> 当前状态：**已完成**
> 设计文档：`docs/superpowers/specs/2026-05-10-talent-library-skill-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-10-talent-library-skill.md`

## 任务清单

- [x] Task 1：增加 `DeleteResult` 数据模型
- [x] Task 2：增加 `TalentDB.update_candidate()`
- [x] Task 3：增加 `TalentDB.delete_candidate()`
- [x] Task 4：新增 `agents/workflows/talent-library` canonical workflow
- [x] Task 5：新增 `.claude/skills/talent-library` 适配器和架构测试
- [x] Task 6：全量验证

## Review

- 基线测试：`python -m pytest tests/test_talent_db.py -q`，结果 **115 passed**。
- 数据层聚焦测试：`python -m pytest tests/test_talent_models.py::test_delete_result_total_related_rows tests/test_talent_db.py::test_update_candidate_updates_allowed_fields_without_losing_sources tests/test_talent_db.py::test_update_candidate_rejects_unknown_fields tests/test_talent_db.py::test_update_candidate_rejects_missing_candidate tests/test_talent_db.py::test_delete_candidate_removes_candidate_and_related_rows tests/test_talent_db.py::test_delete_candidate_rejects_missing_candidate tests/test_talent_db.py::test_delete_candidate_removes_vector_when_available -q`，结果 **7 passed**。
- Workflow/adapter 测试：`python -m pytest tests/test_agent_architecture.py tests/test_talent_library_workflow.py -q`，结果 **9 passed**。
- 全量测试：`python -m pytest tests scripts -q`，结果 **367 passed, 1 warning**。
- 架构扫描：``rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows``，结果 **无输出**。

---

# talent-library import 导入脉脉抓取结果（2026-05-10）

> 当前状态：**已完成**
> 输入文件：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-08 (6).json`
> 主数据源：`data/talent.db`

## 任务清单

- [x] Task 1：读取 `talent-library` import workflow、数据契约和安全规则
- [x] Task 2：检查输入 JSON 存在性和结构
- [x] Task 3：执行 dry-run，统计预计新增/合并/待确认/失败
- [x] Task 4：用户确认后正式写入 SQLite 人才库
- [x] Task 5：生成导入报告并验证数据库结果

## Review

- dry-run：输入 `923` 条联系人，映射 `923` 条候选人，缺失姓名 `0` 条；当前 `data/talent.db` 不存在，临时库预计 `created=923, merged=0, pending=0, errors=0`。
- 正式导入：用户确认后新建 `data/talent.db`，结果 `before=0, created=923, merged=0, pending=0, errors=0, after=923`。
- 数据库验证：`TalentDB.count()` 为 `923`，`CandidateFilter(platforms=["maimai"])` 为 `923`；抽样候选人包含 maimai 来源、结构化字段和 detail 数据。
- 测试验证：`python -m pytest tests/test_talent_db.py tests/test_talent_models.py -q`，结果 **131 passed**。
- 导入报告：`data/output/talent-import-2026-05-10-maimai-capture.md`。

---

# talent-library match 阿里云 AI Agent PM JD（2026-05-10）

> 当前状态：**已完成**
> JD：`data/jds/jd-20260410-alibaba-cloud-ai-agent-pm.json`
> 候选人库：`data/talent.db`

## 任务清单

- [x] Task 1：读取 JD、`talent-library match` 场景和 `screen` 评分框架
- [x] Task 2：对 923 位候选人执行本地五维匹配评分
- [x] Task 3：生成 Top10 详细报告
- [x] Task 4：验证报告内容和记录结果

## Review

- 候选池：从 `data/talent.db` 读取并评估 `923` 位候选人。
- 评分方法：按 `screen` 五维框架本地规则评分，未调用外部 LLM，未写回 `match_scores`。
- Top3：范青 `88`、黄赟 `85`、吴佳硕 `82`。
- 输出报告：`data/output/talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.md`。
- 结构化明细：`data/output/talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.json`。
- 报告验证：Markdown 使用 `utf-8-sig` 写出，中文标题和固定文案已复查正常。

---

# 脉脉 Top10 详情抓取实现确认（2026-05-10）
> 当前状态：**调查中**
> 目标：确认仓库中是否已有非 CDP 的人选详情批量抓取方法，避免重复尝试不可行路径。

## 任务清单

- [x] Task 1：搜索仓库中 `maimai`、`detail`、`scraper`、`profile` 相关实现
- [x] Task 2：核对 `scripts/platform_match` 中详情抓取是否依赖 CDP / Playwright fetch
- [x] Task 3：核对 `extensions/maimai-scraper` 是否支持被动捕获详情接口和 JSON 导出
- [x] Task 4：给出可复用路径和下一步执行方案

## Review

- 现有 Python 详情入口为 `scripts/platform_match/adapters/maimai.py::MaimaiAdapter.get_detail()`，实现依赖 `page.evaluate(fetch)` 请求 `https://maimai.cn/api/pc/u/{platform_id}`，属于 CDP/Playwright 路径，不作为本次抓取方案。
- `extensions/maimai-scraper/inject.js` 已被动拦截 `/api/pc/u/`，可在用户手动打开详情页时捕获详情接口响应。
- 现有 `maimai-capture-2026-05-08 (6).json` 是分页联系人导出，仅包含 `contacts`，无 `requests` 和 `/api/pc/u/` 详情响应。
- git 历史未发现可直接复用的非 CDP Python 批量详情抓取 CLI；旧 `maimai-scraper` 方案主要是设计/TypeScript 表单与导出模块，未保留可执行 Python 详情批量抓取脚本。

---

# 脉脉 Top10 详情补全（2026-05-10）
> 当前状态：**执行中**
> 路径：真实 Chrome 登录态在脉脉列表页内点击候选人详情弹窗，`maimai-scraper` 被动捕获详情相关接口，导出 JSON 后由本地脚本解析入库。

## 任务清单

- [x] Task 1：生成 Top10 详情页打开清单
- [ ] Task 2：用户在 Chrome 中用 `maimai-scraper` 清空旧数据并在列表页逐个点击 10 个详情弹窗
- [x] Task 3：用户导出详情捕获 JSON 并提供本地路径
- [x] Task 4：解析导出 JSON，dry-run 展示可补全字段和风险
- [x] Task 5：用户确认后写入 `data/talent.db`
- [x] Task 6：生成详情补全报告
- [x] Task 7：把成功实践更新到 `talent-library detail` 执行方法

## 执行记录

- 2026-05-10：用户反馈详情页未捕获，截图显示请求数为 0。定位为扩展只匹配 `maimai.cn`，未覆盖 `www.maimai.cn` 子域，且 UI 未单独展示详情响应。
- 2026-05-10：已将 `extensions/maimai-scraper` 升级到 2.2，补充 `*://*.maimai.cn/*`，扩大详情相关 API 匹配，并在导出 JSON 中新增 `details` / `totalDetails`。
- 2026-05-10：用户实测列表页内手动点击弹出的详情可以捕获，外部链接打开的新详情页无法捕获。执行路径改为列表页内点击详情弹窗，不再要求逐个打开外部 profile URL。
- 2026-05-10：用户导出的 `maimai-capture-2026-05-10.json` 仍是联系人列表，验证为 `contacts=30, details=0, requests=0`。定位为导出按钮优先走 IndexedDB 分页导出，未包含 `chrome.storage.local` 中的详情捕获；已新增 `exportFullJson` 并让清除同步清 `PagerDB`。
- 2026-05-10：新导出文件验证通过：`details=10, requests=178, contacts=70`。dry-run 成功匹配本地 Top10 的 10/10 人；工作经历将由 2 条扩展到 2-8 条，吴佳硕新增 2 条项目经历，小蝴蝶帕鲁新增 3 条项目经历。
- 2026-05-10：用户确认后已写入 `data/talent.db`。10/10 候选人验证通过：`data_level=detailed`，`raw_data.maimai_detail_capture` 存在；最终报告 `data/output/talent-detail-2026-05-10-maimai-top10.md`，结构化结果 `data/output/talent-detail-2026-05-10-maimai-top10-result.json`。
- 2026-05-10：已将成功实践写入 `agents/workflows/talent-library/references/scenarios.md` 的 `detail` 场景，明确脉脉详情补全采用列表页弹窗捕获、完整导出、dry-run、确认写入和逐人验证流程。

---

# 脉脉批量详情抓取实施计划（2026-05-11）
> 当前状态：**计划已完成，待实施确认**
> 设计文档：`docs/design-discussions/2026-05-10-maimai-batch-detail-capture-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-10-maimai-batch-detail-capture.md`

## 任务清单

- [x] Task 1：新增扩展静态契约测试
- [x] Task 2：新增 `DetailDB` 详情任务存储
- [x] Task 3：新增 MAIN world 详情接口重放
- [x] Task 4：新增批量详情调度器、限流和熔断
- [x] Task 5：新增 popup “批量详情”界面
- [x] Task 6：新增本地详情导入 dry-run/apply CLI
- [x] Task 7：更新 `talent-library detail` 执行文档
- [x] Task 8：执行 Chrome 扩展打包和真实页面小批量验证
- [x] Task 9：全量测试、行为回归和 Review 记录

## Review

- 计划来源：已读取 `docs/design-discussions/2026-05-10-maimai-batch-detail-capture-design.md`。
- 现状核对：已核对 `extensions/maimai-scraper` 当前 `manifest/background/content/inject/popup/idb/autopager` 结构，确认当前只有手动详情捕获和分页联系人抓取，没有批量详情 job 状态机。
- 范围决策：首轮实施 Phase 1-3 和必要的本地入库工具化；Phase 4 自动点击兜底延后单独设计。
- 本次未进入代码实现，未运行项目测试；下一步需要用户确认后按实施计划逐项执行。

## Task 1 Review - Extension Contract Tests

- [x] Step 1.1: 新增 `tests/test_maimai_scraper_extension.py`，使用 `pathlib/json` 做扩展静态契约测试。
- [x] Step 1.2: 运行 `python -m pytest tests/test_maimai_scraper_extension.py -q`，结果为 **8 failed**，失败点覆盖 manifest 版本、detail_batch 加载、DetailDB、批量详情消息、detailFetch、MAIN world 详情重放、popup detail tab、detailJobs 导出。

## Task 2 Review - DetailDB 存储和导出增强

- [x] Step 2.1: 在 `idb.js` 抽出 IndexedDB helper，保持 `PagerDB` 外部 API 不变。
- [x] Step 2.2: 新增 `DetailDB`，包含 jobs/details stores 和公开 API。
- [x] Step 2.3: 增强 `clearAll`，同步清理 PagerDB、DetailDB 和相关 storage 字段。
- [x] Step 2.4: 增强 `exportFullJson`，合并导出 contacts/details/detailJobs 和 detail metadata。
- [x] Step 2.5: 运行 `node --check` 和 `pytest` 验证。

验证结果：
- `node --check extensions/maimai-scraper/idb.js`：PASS。
- `node --check extensions/maimai-scraper/background.js`：PASS。
- `python -m pytest tests/test_maimai_scraper_extension.py -q`：6 failed, 2 passed；`DetailDB` 和 `exportFullJson/detailJobs` 相关断言已通过，剩余失败属于 manifest/detail_batch 消息、content/inject 桥接和 popup UI 后续任务。

## Task 3-5 Review - 扩展批量详情闭环

- [x] Task 3：`content.js` 新增 `detailFetch` 桥接，`inject.js` 新增 `__MAIMAI_DETAIL_FETCH__`，顺序请求 `/api/ent/talent/basic`、项目、求职意向和联系按钮接口。
- [x] Task 4：新增 `detail_batch.js` 状态机，支持 jobs 生成、低速限流、暂停、继续、停止、失败记录、每日上限和连续认证/风控失败熔断；`background.js` 新增 `startDetailBatch`、`pauseDetailBatch`、`resumeDetailBatch`、`stopDetailBatch`、`getDetailBatchStatus`、`importDetailContacts`。
- [x] Task 5：`popup.html/js/css` 新增“批量详情”Tab，包含联系人导入、safe/test 策略、每日上限、开始/暂停/继续/停止/刷新/导出和进度展示。

验证结果：
- `node --check extensions/maimai-scraper/background.js`：PASS。
- `node --check extensions/maimai-scraper/detail_batch.js`：PASS。
- `node --check extensions/maimai-scraper/content.js`：PASS。
- `node --check extensions/maimai-scraper/inject.js`：PASS。
- `node --check extensions/maimai-scraper/idb.js`：PASS。
- `node --check extensions/maimai-scraper/popup.js`：PASS。
- `python -m pytest tests/test_maimai_scraper_extension.py -q`：**8 passed**。

## Task 6 Review - 本地详情导入 CLI

- [x] 新增 `scripts/maimai_detail_import.py`，支持 `dry-run` 和 `apply`。
- [x] dry-run 校验导出 JSON 顶层 `details` 或 `detailJobs`，按 `source_profiles.platform='maimai'` 与 `platform_id` 精确匹配，不修改数据库。
- [x] apply 必须带 `--confirm "确认写入脉脉详情"`，只写入精确匹配人选，写入后逐人验证 `data_level='detailed'` 和 `raw_data.maimai_detail_capture`。
- [x] 新增 `tests/test_maimai_detail_import.py` 覆盖 dry-run、apply 和确认语句。

验证结果：
- `python -m pytest tests/test_maimai_detail_import.py -q`：**3 passed**。
- `python -m py_compile scripts/maimai_detail_import.py`：PASS。
- `python -m pytest scripts/test_maimai.py tests/test_talent_db.py::test_get_detail_after_enrich -q`：**28 passed**。
- `python scripts/maimai_detail_import.py --help`：PASS。

## Task 7 Review - Workflow 文档

- [x] 已在 `agents/workflows/talent-library/references/scenarios.md` 的 `detail` 场景新增“脉脉详情补全：批量详情接口重放”流程。
- [x] 原“列表页弹窗捕获”调整为小批量或失败记录兜底路径。

## Task 8-9 Review - 打包、回归和最终验证

- Chrome pack：`chrome.exe` 不在 PATH；改用 `C:\Program Files\Google\Chrome\Application\chrome.exe` 并复用既有 `extensions/maimai-scraper.pem` 执行打包，结果 **PASS**。
- 扩展语法检查：`node --check extensions/maimai-scraper/idb.js detail_batch.js background.js content.js inject.js popup.js`，结果 **PASS**。
- 扩展契约测试：`python -m pytest tests/test_maimai_scraper_extension.py -q`，结果 **8 passed**。
- 本地详情导入测试：`python -m pytest tests/test_maimai_detail_import.py -q`，结果 **3 passed**。
- 映射/入库聚焦回归：`python -m pytest scripts/test_maimai.py tests/test_talent_db.py::test_get_detail_after_enrich -q`，结果 **28 passed**。
- 全量测试：`python -m pytest tests scripts -q`，结果 **379 passed, 1 warning**。
- 架构扫描：`rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows`，结果 **无输出**。
- 代码审查：轻量最终审查发现 2 个问题（显式导入联系人优先级、popup HTML 结构），已修复并复审 **APPROVED**。
- 真实页面验证：用户反馈 **测试通过**。

---

# 推荐列表驱动脉脉批量详情抓取（2026-05-11）
> 当前状态：**执行中**
> 实施计划：`docs/superpowers/plans/2026-05-11-maimai-recommendation-detail-targets.md`

## 任务清单

- [x] Task 1：新增推荐列表转详情目标 JSON 的测试
- [x] Task 2：实现 `scripts/maimai_detail_targets.py`
- [x] Task 3：扩展导入逻辑兼容 `top10/candidates/matches/results`
- [x] Task 4：更新 `talent-library detail` 推荐列表业务流文档
- [x] Task 5：聚焦测试、扩展语法检查和全量验证

## Review

- 计划来源：用户反馈真实业务流是先 `talent-library search/match` 得到推荐列表，再导入 `maimai-scraper` 批量抓详情，而不是直接对全量列表 JSON 抓详情。
- 设计决策：保持既有批量详情实现一致，新增本地转换工具输出顶层 `contacts`，同时让扩展导入路径直接识别常见推荐列表 JSON 结构。

## Task 1-4 Review

- 新增 `tests/test_maimai_detail_targets.py`，覆盖 match `top10` JSON、显式 candidate_id 列表、推荐项自带 `profile_url` 三种输入。
- 新增 `scripts/maimai_detail_targets.py`，支持：
  - `from-file --input <recommendation.json> --db data/talent.db --out <targets.json>`
  - `from-ids --ids 1,2,3 --db data/talent.db --out <targets.json>`
- 扩展 `importDetailContacts` 已兼容 `contacts`、`detailJobs`、`top10`、`candidates`、`matches`、`results`、`items` 和原始数组。
- `popup.js` 文件导入改为把完整 JSON 交给 background 归一化，避免前端提前丢失 `top10/results`。
- `talent-library detail` 文档已新增“推荐列表驱动的批量详情”流程。

验证记录：
- `python -m pytest tests/test_maimai_detail_targets.py -q`：**3 passed**。
- `python -m py_compile scripts/maimai_detail_targets.py`：PASS。
- `node --check extensions/maimai-scraper/background.js; node --check extensions/maimai-scraper/popup.js`：PASS。
- `python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_scraper_extension.py -q`：**12 passed**。
- 真实 Top10 match JSON smoke：`data/output/talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.json` 转换结果 `total_input=10, total_contacts=10, missing=0`。

## Task 5 Review

- 聚焦回归：`python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_scraper_extension.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q`，结果 **42 passed**。
- 扩展语法检查：`node --check extensions/maimai-scraper/idb.js detail_batch.js background.js content.js inject.js popup.js`，结果 **PASS**。
- Chrome pack：复用既有 `extensions/maimai-scraper.pem` 打包，结果 **PASS**。
- 全量测试：`python -m pytest tests scripts -q`，结果 **383 passed, 1 warning**。
- 架构扫描：`rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows`，结果 **无输出**。

## talent-library detail 入口集成（2026-05-11）

- [x] 新增 `scripts/talent_library.py detail` 统一业务入口，支持 `--ids`、`--top10-file`、`--recommendation-file`、`--out`、`--db`。
- [x] 新增 `tests/test_talent_library_cli.py`，覆盖通过 ids 和 top10 file 生成 `maimai-detail-targets.json`。
- [x] 更新 `agents/workflows/talent-library/AGENT.md`，声明 `detail` 场景扩展参数。
- [x] 更新 `agents/workflows/talent-library/references/scenarios.md`，将用户入口改为 `talent-library detail --ids/--top10-file`，底层脚本仅作为运行时映射。

验证记录：
- `python -m pytest tests/test_talent_library_cli.py -q`：**3 passed**。
- `python -m py_compile scripts/talent_library.py`：PASS。
- `python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_talent_library_workflow.py tests/test_agent_architecture.py -q`：**15 passed**。
- `python scripts/talent_library.py detail --top10-file data\output\talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.json --db data\talent.db --out %TEMP%\maimai-detail-targets-entry-smoke.json`：联系人 **10**，缺失 **0**。
- `python scripts/talent_library.py detail --ids 440,747 --db data\talent.db --out %TEMP%\maimai-detail-targets-ids-smoke.json`：联系人 **2**，缺失 **0**。
- `python -m pytest tests scripts -q`：**386 passed, 1 warning**。
- 架构扫描：`rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows`，结果 **无输出**。

---

# maimai-scraper 批量详情与悬浮球优化（2026-05-11）
> 当前状态：**计划已完成，待实施确认**
> 实施计划：`docs/superpowers/plans/2026-05-11-maimai-scraper-ops-overlay.md`

## 任务清单

- [x] Task 1：新增扩展契约测试，覆盖日志、reset、job 替换和悬浮球
- [x] Task 2：扩展 `DetailDB` 和 `DetailBatch` reset 契约
- [x] Task 3：增强 `background.js` 日志、summary、reset，并修复陈旧 jobs 混入
- [x] Task 4：增强 popup 批量详情页实时日志和重置操作
- [x] Task 5：在 `content.js` 注入页面右侧三态悬浮球
- [x] Task 6：版本升级、语法检查、聚焦测试、全量测试和 Chrome pack
- [ ] Task 7：真实脉脉页面手工验收

## Review

- 扩展契约测试：`python -m pytest tests/test_maimai_scraper_extension.py -q`，结果 **20 passed**。
- JS 语法检查：`node --check extensions/maimai-scraper/idb.js detail_batch.js background.js content.js inject.js popup.js`，结果 **PASS**。
- 关联回归：`python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_talent_library_cli.py tests/test_maimai_scraper_extension.py -q`，结果 **29 passed**。
- maimai 聚焦回归：`python -m pytest tests/test_maimai_detail_targets.py tests/test_maimai_scraper_extension.py tests/test_maimai_detail_import.py scripts/test_maimai.py -q`，结果 **53 passed**。
- 全量测试：`python -m pytest tests scripts -q`，结果 **397 passed, 1 warning**。
- Chrome pack：`& "C:\Program Files\Google\Chrome\Application\chrome.exe" --pack-extension="D:\workspace\talent-agent\extensions\maimai-scraper" --pack-extension-key="D:\workspace\talent-agent\extensions\maimai-scraper.pem"`，结果 **PASS**。
- 最终代码复审：已修复 reset 旧异步写回、reset 后 contacts 残留、悬浮球实时轮询、popup `total_jobs` 实时事件兼容、导出 token 过滤缺口；最终复审 **无 Critical / Important / Minor**。
- 最终复验：`python -m pytest tests/test_maimai_scraper_extension.py -q` **20 passed**；`python -m pytest tests scripts -q` **397 passed, 1 warning**；`git diff --check` 无 whitespace error（仅提示 `scripts/test_maimai.py` CRLF 将被 Git 转 LF）。
- 真实脉脉页面手工验收待执行：重载扩展后验证悬浮球三态、3 联系人导入只生成 3 个 jobs、实时日志、导出 JSON 和 reset。

# Boss 渠道浏览器插件扩展设计（2026-05-12）
> 当前状态：设计文档已完成，待用户评审
> 设计文档：`docs/superpowers/specs/2026-05-12-boss-channel-browser-extension-design.md`

## 任务清单

- [x] Task 1：梳理现有脉脉插件、导入链路、Boss adapter、Boss 机制文档和数据模型
- [x] Task 2：确认 Boss 第一版产品边界为“列表闭环 + 详情被动捕获实验区”
- [x] Task 3：比较扩展现有插件、新建 Boss 插件、只做 Python/CDP 三种方案
- [x] Task 4：形成推荐设计：现有插件渠道化，Boss 只做被动监听和低风险页面辅助
- [x] Task 5：写入正式设计文档并完成自检
- [x] Task 6：用户评审设计文档
- [x] Task 7：用户确认后进入实施计划编写
- [x] Task 8：写入实施计划并完成自检

## Review

- 关键决策：第一版不承诺 Boss 批量详情主动抓取；Boss 列表数据入库为 `partial`，详情只做被动捕获实验区。
- 插件策略：新建 `extensions/talent-channel-scraper`，从现有 `maimai-scraper` 迁移公共能力，过渡期保留旧插件目录以降低回归风险。
- 数据策略：统一 capture envelope，`source_profiles.platform` 区分渠道，`platform_id` 只在同平台内精确匹配，跨渠道保持保守合并。
- 机制差异：脉脉可主动重放接口；Boss 禁止主动 `fetch`、禁止自动详情页导航、禁止新开页面探测登录态。
- 计划记录：用户已确认设计，实施计划已写入 `docs/superpowers/plans/2026-05-12-boss-channel-browser-extension.md`；自检无占位符，`git diff --check` 通过。

---

# talent-library import 导入 Downloads 脉脉捕获数据（2026-05-12）

> 当前状态：已完成真实导入；import 路由写库收束到 `TalentDB.batch_ingest()`。

## 任务清单

- [x] Task 1：核对 `talent-library` import workflow、数据契约和安全规则。
- [x] Task 2：核对 `scripts/talent_library.py` 是否已有 `import` 路由，以及现有 `detail` 路由边界。
- [x] Task 3：核对 `TalentDB.batch_ingest()` 的输入契约、去重/合并行为和错误统计。
- [x] Task 4：核对脉脉扩展 `contacts` JSON 到 batch ingest 输入的字段映射。
- [x] Task 5：形成自洽执行方案：import 路由负责解析、去重、字段规范化、dry-run/report；写库只通过 `TalentDB.batch_ingest()`。
- [x] Task 6：补 `talent-library import` CLI、dry-run/apply 报告和回归测试。
- [x] Task 7：对 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-12*.json` 执行 dry-run 与 apply。
- [x] Task 8：写后验证重复数据不会再次新增，并运行全量测试。

## Review

- workflow 契约：`agents/workflows/talent-library/AGENT.md` 将 `import` 路由到 `TalentDB.batch_ingest()`；`references/scenarios.md` 要求批量写入前 dry-run，用户确认后再调用 batch ingest；`safety-rules.md` 要求批量写入先展示新增、修改、跳过、失败和待确认数量。
- 当前代码缺口：`scripts/talent_library.py` 只有 `detail` 子命令，没有 `import` 子命令；不能把导入委托给 `talent_migrate.py` 作为正式入口。
- `TalentDB.batch_ingest()` 契约：输入必须是已规范化候选人 dict；用 `platform + platform_id` 优先去重，再按姓名、公司、职位、城市、学历精确合并；返回 created/merged/pending/errors。
- 脉脉映射注意点：`MaimaiAdapter.map_to_schema()` 会返回 `_source`、`status` 和列表型 `expected_city`，import 路由必须提升 `platform_id/profile_url`、转换 `status -> hunting_status`、把列表型文本字段转成可入库文本，并保留原始 contact 到 `raw_profile`。
- 临时库试跑：未写真实 `data/talent.db`；11 个 Downloads 文件共 2519 条联系人，按脉脉 ID 去重后 1795 条；规范化后调用 `TalentDB.batch_ingest()` 得到 `created=1781, merged=14, pending=0, errors=0`。
- 实现变更：`scripts/talent_library.py import` 支持 `--input/--input-dir/--pattern/--platform/--db/--out/--apply/--confirm`；默认 dry-run 使用临时 SQLite 副本，不写真实库；apply 必须带 `--confirm "确认导入人才"`。
- 测试覆盖：`tests/test_talent_library_cli.py` 新增 dry-run 去重不写库、apply 字段规范化与来源写入测试。
- 真实导入：dry-run 报告 `data/output/talent-import-2026-05-12-downloads-maimai-dry-run.md`；apply 报告 `data/output/talent-import-2026-05-12-downloads-maimai-apply.md`。
- 写库结果：原始联系人 2519，跨文件重复 724，去重后 1795；写入 `created=1781, merged=14, pending=0, errors=0`；`data/talent.db` 候选人总数从 952 增至 2733。
- 写后验证：脉脉 `platform_id` 重复数为 0；同一批数据写后 dry-run 为 `created=0, merged=1795, pending=0, errors=0`，符合今日重复只导入一次。
- 验证命令：`python -m pytest tests/test_talent_library_cli.py -q` -> 5 passed；`python -m pytest tests/test_talent_library_cli.py tests/test_talent_db.py::test_batch_ingest_mixed_created_merged_errors tests/test_talent_db.py::test_same_platform_id_merges_even_when_identity_fields_change -q` -> 7 passed；`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_talent_migrate.py tests/test_talent_library_workflow.py -q` -> 28 passed；`python -m pytest tests scripts -q` -> 405 passed, 1 warning。

---

# 人才库联系方式与微信聊天记录设计（2026-05-12）

> 当前状态：实施计划已完成，待选择执行方式；尚未进入实现。

## 任务清单

- [x] Task 1：探索项目上下文，核对现有人才库模型、导入、更新、workflow 和测试契约。
- [x] Task 2：判断是否需要视觉辅助；本次为数据模型/workflow 设计，默认不需要。
- [x] Task 3：逐一澄清联系方式与微信聊天记录的产品边界、数据来源和同步方式。
- [x] Task 4：提出 2-3 个设计方案，比较表结构、导入路径、隐私风险和后续扩展性。
- [x] Task 5：呈现推荐设计，覆盖架构、组件、数据流、错误处理和测试策略，并等待用户确认。
- [x] Task 6：用户确认后写入 `docs/superpowers/specs/2026-05-12-talent-contact-and-wechat-timeline-design.md`。
- [x] Task 7：设计文档自检，排除占位符、矛盾、范围漂移和歧义。
- [x] Task 8：等待用户评审设计文档。
- [x] Task 9：用户批准后再进入实施计划编写。

## Review

- 已确认联系方式第一版每类只保留一个当前值：邮箱、手机号、微信号、预留微信 id。
- 已确认微信聊天记录同步为手动触发 skill，通过已安装的 `wechat-cli export` 导出 markdown，支持指定联系人、时间范围和数量上限。
- 推荐方案为轻量结构化字段 + 独立微信聊天归档 skill：联系方式写候选人结构化字段，聊天正文写 `data/wechat-timelines/*.md`，SQLite 只保存归档索引。
- 设计文档已写入 `docs/superpowers/specs/2026-05-12-talent-contact-and-wechat-timeline-design.md`；自检无占位符、矛盾、范围漂移和歧义。
- 用户已审核设计并确认进入实施计划编写。
- 实施计划已写入 `docs/superpowers/plans/2026-05-12-talent-contact-and-wechat-timeline.md`，等待选择 Subagent-Driven 或 Inline Execution。

---

# 人才库联系方式 Task 1 实施（2026-05-12）
> 当前状态：实现与聚焦回归已完成，等待提交
> 计划文件：`docs/superpowers/plans/2026-05-12-talent-contact-and-wechat-timeline.md`

## 任务清单

- [x] Task 1.1：补 Candidate 联系方式序列化失败测试，并确认 RED
- [x] Task 1.2：实现 Candidate 的 `email`、`phone`、`wechat`、`wechat_id` 字段，并确认 GREEN
- [x] Task 1.3：补 TalentDB 联系方式建库/更新失败测试，并确认 RED
- [x] Task 1.4：实现 SQLite schema、迁移、插入、更新和合并填空逻辑，并确认 GREEN
- [x] Task 1.5：补 batch ingest 联系方式填空不覆盖测试
- [x] Task 1.6：更新 `schemas/candidate.schema.json`
- [x] Task 1.7：运行聚焦回归并提交 `feat: add candidate contact fields`

## Review

- RED：`python -m pytest tests/test_talent_models.py::TestCandidate::test_contact_fields_round_trip -q` -> 1 failed，原因是 `Candidate.__init__()` 不接受 `email`。
- GREEN：`python -m pytest tests/test_talent_models.py::TestCandidate::test_contact_fields_round_trip -q` -> 1 passed。
- RED：`python -m pytest tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields -q` -> 2 failed，原因是联系方式未入库且 update allowlist 拒绝新字段。
- GREEN：`python -m pytest tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields -q` -> 2 passed。
- Fill-only：`python -m pytest tests/test_talent_db.py::test_batch_ingest_contact_fields_fill_empty_without_overwriting -q` -> 1 passed。
- 聚焦回归：`python -m pytest tests/test_talent_models.py tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields tests/test_talent_db.py::test_batch_ingest_contact_fields_fill_empty_without_overwriting -q` -> 20 passed。
- Schema 校验：`python -c "import json, pathlib; json.loads(pathlib.Path('schemas/candidate.schema.json').read_text(encoding='utf-8')); print('schema json ok')"` -> schema json ok。
- Commit：待提交。

---

# 人才库联系方式与微信聊天记录实施（2026-05-12）

> 当前状态：已完成实现与验证。
> 设计文档：`docs/superpowers/specs/2026-05-12-talent-contact-and-wechat-timeline-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-12-talent-contact-and-wechat-timeline.md`

## 任务清单

- [x] Task 1：扩展候选人联系方式模型、SQLite schema、导入合并和更新契约。
- [x] Task 2：新增微信聊天 markdown 归档索引表和 TalentDB API。
- [x] Task 3：新增 `scripts/talent_library.py wechat-sync`，封装 `wechat-cli export`。
- [x] Task 4：新增 `wechat-chat-sync` canonical workflow 和薄适配 skill。
- [x] Task 5：更新 `talent-library` workflow 的联系方式和微信同步契约。
- [x] Task 6：运行聚焦回归、全量测试和静态检查。

## Review

- Task 1 commit：`b6b66b7 feat: add candidate contact fields`；覆盖 `Candidate.email/phone/wechat/wechat_id`、SQLite 迁移、更新 allowlist、导入 fill-only 合并和 JSON schema。
- Task 2 commit：`d018450 Add WeChat timeline index API`；新增 `WechatTimeline`、`candidate_wechat_timelines`、`TalentDB.add_wechat_timeline()`、`TalentDB.get_wechat_timelines()` 和删除级联计数。
- Task 3 commit：`3ddf97e feat: add wechat chat sync cli`；新增 `talent-library wechat-sync`，支持候选人定位、可选联系方式更新、`wechat-cli export`、markdown front matter、消息计数和索引写入。
- Task 4 commit：`c13c2e7 docs: add wechat chat sync workflow`；新增 runtime-neutral `wechat-chat-sync` workflow、CLI 契约、归档格式、模板和 `.claude` adapter。
- Task 5 commit：`8cd4e0b docs: integrate contacts and wechat sync workflow`；`talent-library` 文档声明联系方式字段、时间线索引 API、`wechat-sync` 场景和隐私安全规则。
- 聚焦回归：`python -m pytest tests/test_talent_models.py tests/test_talent_db.py tests/test_talent_library_cli.py tests/test_talent_library_workflow.py tests/test_wechat_chat_sync_workflow.py tests/test_agent_architecture.py -q` -> **159 passed**。
- 全量测试：`python -m pytest tests scripts -q` -> **419 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- 静态检查：`python -m py_compile scripts/talent_models.py scripts/talent_db.py scripts/talent_library.py` -> PASS。
- CLI smoke：`python scripts/talent_library.py wechat-sync --help` -> PASS，输出包含 `--candidate-id`、`--chat-name`、`--start-time`、`--end-time`、`--out-dir`。
- Whitespace：`git diff --check` -> PASS。
- 已知限制：已用 monkeypatch 覆盖 `wechat-cli` 成功和失败路径；尚未在真实微信环境中执行手工导出验收，实际可用性仍取决于本机 `wechat-cli export`、微信数据库可访问性和用户提供的时间范围。

---

# 脉脉 AI Infra 自动化搜索实施（2026-05-12）
> 当前状态：实现与验证已完成，等待选择集成方式。
> 计划文件：`docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`
> 工作区：`.worktrees/maimai-ai-infra-automated-search`

## 任务清单

- [x] Task 0：建立隔离 worktree，保护当前 `main` 上已有未提交改动。
- [x] Task 1：新增策略配置与策略加载/校验测试。
- [x] Task 2：新增搜索批次编译器与 CLI 输出。
- [x] Task 3：新增搜索 runner 的请求体 patch、dry-run-template-only 和 POC 边界。
- [x] Task 4：新增 run result -> import payload 与 dry-run/apply 流水线。
- [x] Task 5：新增 AI Infra 本地评分与 shortlist 输出。
- [x] Task 6：接入 Top 候选详情目标生成与扩展自动化桥可行性记录。
- [x] Task 7：生成最终审查报告。
- [x] Task 8：运行计划要求的聚焦回归、静态检查、`git diff --check` 和必要全量测试。

## 执行约束

- 第一版不得把 Python CDP 直接 `fetch` 作为默认主路径；未验证字段只做模板校验或本地过滤。
- 真实网页自动化只能在 Phase 0 通过后开启；本次默认先交付 dry-run/template、本地评分和报告闭环。
- 批量写库必须先 dry-run；只有策略显式授权并且 dry-run clean 时才允许 apply。

## Review

- 新增 `configs/maimai-ai-infra-search-strategy.json`，包含人工门禁、批次限额、公司梯队、别名、职位批次、关键词包、排除词和学校分组。
- 新增 `scripts/maimai_ai_infra_search_plan.py`，可生成稳定批次 id、80/20 优先级搜索计划，且每个 batch 只含一个职位名称。
- 新增 `scripts/maimai_ai_infra_search_runner.py`，默认只支持 `--dry-run-template-only`，只 patch 已验证字段：`query/search_query`、分页和 page size；真实 live search 在 Phase 0 通过前会直接拒绝。
- 新增 `scripts/maimai_ai_infra_rank.py`，基于公司、职位、技术证据、学历和年限做 A/B/C/淘汰分层，不依赖 LLM。
- 新增 `scripts/maimai_ai_infra_pipeline.py`，串联 plan、runner dry-run、contacts payload、import dry-run、shortlist、详情目标和最终审查报告；只有 `strategy_confirmed=true` 且 `auto_apply_after_clean_dry_run=true` 且 dry-run clean 时才 apply。
- 新增测试：`tests/test_maimai_ai_infra_strategy.py`、`tests/test_maimai_ai_infra_runner.py`、`tests/test_maimai_ai_infra_pipeline.py`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **10 passed**。
- 验证：`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q` -> **40 passed**。
- 验证：`node --check extensions/maimai-scraper/idb.js/detail_batch.js/background.js/content.js/inject.js/popup.js` -> **PASS**。
- 验证：`python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py` -> **PASS**。
- 验证：`python -m pytest tests scripts -q` -> **429 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- 验证：`git diff --check` -> **PASS**。
- Smoke：用主 checkout 的真实 `data/talent.db` 只读跑 `maimai_ai_infra_rank.py`，评估 2733 人，输出 A=281、B=556、C=817、淘汰=1079。
- 残余风险：独立 review 子代理未在 5 分钟内返回结果，已关闭；本次没有取得额外审查 findings。真实脉脉页面执行仍受 Phase 0 门禁约束，当前交付是离线 dry-run/template、本地评分和报告闭环。
