# Task 14 Documentation - bundle 同步文档

## 计划

- [x] 在 `tests/test_talent_library_workflow.py` 增加 bundle 同步文档契约测试
- [x] 运行聚焦单测确认红灯
- [x] 在 `agents/workflows/talent-library/references/data-contract.md` 增加“多端 bundle 同步”说明
- [x] 在 `README.md` 数据管理附近增加 status/export/verify/import 操作示例
- [x] 补齐 `scripts/talent_sync.py export --include-wechat-files` CLI 参数
- [x] 增加 CLI 附件导出测试并增强文档契约测试
- [x] 运行聚焦单测与文件级回归
- [x] 记录 Review 结果

## Review

- 红灯：`python -m pytest tests/test_talent_library_workflow.py::test_talent_library_documents_bundle_sync -q` 初次失败，原因是 `data-contract.md` 缺少 `bundle 同步`。
- 评审修复红灯：`python -m pytest tests/test_talent_sync.py::test_sync_cli_export_can_include_wechat_timeline_attachments -q` 初次失败，原因是 CLI 未识别 `--include-wechat-files`。
- 绿灯：`python -m pytest tests/test_talent_sync.py::test_sync_cli_export_can_include_wechat_timeline_attachments -q` 通过；`python -m pytest tests/test_talent_library_workflow.py -q` 通过；`python -m pytest tests/test_talent_sync.py -q` 通过，结果 `29 passed`。
- 差异检查：`git diff --check` 退出码为 0，仅提示 `README.md` 的 CRLF/LF 工作区换行告警。
- 文档覆盖：多端同步禁止覆盖 `data/talent.db`，记录 export、verify-bundle、dry-run import、apply import、同步身份、冲突记录和微信时间线附件恢复路径。

# Task 15 Full Verification

## Review

- 聚焦测试：`python -m pytest tests/test_talent_sync.py tests/test_talent_db.py tests/test_talent_library_cli.py tests/test_talent_library_workflow.py -q` -> `168 passed`。
- 语法检查：`python -m py_compile scripts/talent_sync.py scripts/talent_sync_models.py scripts/talent_db.py scripts/talent_models.py` -> PASS。
- 全量回归：`python -m pytest tests scripts -q` -> `493 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异检查：`git diff --check` -> PASS；仅提示 `README.md` 工作区 CRLF 将转 LF。
- 最终评审：发现 detail 合并、match score 冲突、微信时间线稳定键去重、附件导出根目录约束 4 个 Important，需要修复后重跑验证。

# Final Review Fixes

## 计划

- [x] 修复 `candidate_details` 合并：`summary` 冲突记录，`raw_data` 按顶层 namespace 合并并记录同 key 冲突。
- [x] 修复 `match_scores` 稳定键冲突：同 `(candidate_sync_id, jd_id, match_type)` 差异记录冲突而非静默丢弃。
- [x] 修复微信时间线导入稳定键去重，跨机器同一归档不重复插入。
- [x] 限制 `--include-wechat-files` 只打包数据库旁 `data/wechat-timelines/` 下的 markdown 归档。
- [x] 补对应回归测试、复审并重跑 Task 15 验证。

## Review

- 红灯：4 个新增回归测试首次运行全部失败，分别覆盖 detail raw_data/summary、match score 冲突、微信时间线稳定键、附件越界路径。
- 修复后新增测试：`python -m pytest tests/test_talent_sync.py::test_import_candidate_detail_merges_raw_data_and_records_conflicts tests/test_talent_sync.py::test_import_match_score_records_conflict_for_stable_key_difference tests/test_talent_sync.py::test_import_wechat_timeline_dedupes_by_archive_identity_across_nodes tests/test_talent_sync.py::test_export_wechat_attachments_skips_paths_outside_db_archive_dir -q` -> `4 passed`。
- 聚焦回归：`python -m pytest tests/test_talent_sync.py -q` -> `33 passed`；`python -m pytest tests/test_talent_db.py -q` -> `125 passed`。
- 语法检查：`python -m py_compile scripts/talent_db.py scripts/talent_sync.py` -> PASS。
- 差异检查：`git diff --check` -> PASS；仅提示既有 `README.md` 工作区 CRLF/LF 换行告警。

## 追加边界修复计划

- [x] 补默认 `data/talent.db` 形态的微信附件导出红灯测试。
- [x] 抽共享微信归档目录 helper，兼容主库 `data/talent.db` 与临时库 `source.db`。
- [x] 让导出 allowed_dir 和导入恢复 target_dir 复用同一 helper。
- [x] 运行新增测试、用户指定聚焦测试、完整 `tests/test_talent_sync.py`。

### 追加边界修复 Review

- 红灯：`python -m pytest tests/test_talent_sync.py::test_export_wechat_attachments_from_default_data_db_layout -q` 初次失败，确认 `data/talent.db` 会误跳过 `data/wechat-timelines/legal.md`。
- 绿灯：新增测试修复后通过，结果 `1 passed`。
- 聚焦验证：`python -m pytest tests/test_talent_sync.py::test_export_wechat_attachments_skips_paths_outside_db_archive_dir tests/test_talent_sync.py::test_export_can_include_wechat_timeline_attachments tests/test_talent_sync.py::test_import_wechat_attachment_is_idempotent_for_duplicate_bundle -q` -> `3 passed`。
- 完整同步测试：`python -m pytest tests/test_talent_sync.py -q` -> `34 passed`。
- 语法与差异检查：`python -m py_compile scripts/talent_sync.py` -> PASS；`git diff --check` -> PASS，仅提示既有 `README.md` CRLF/LF 告警。

## 微信时间线单侧 identifier 去重修复

- [x] 补 existing 有 `chat_identifier`、incoming 只有 `chat_name` 的红灯测试。
- [x] 补 existing 只有 `chat_name`、incoming 有 `chat_identifier` 的红灯测试。
- [x] 调整 `_matching_wechat_timeline()`：双方都有 identifier 时先按 identifier 匹配；否则回退到 `chat_name + start_time + end_time + markdown_path`。
- [x] 跑用户建议测试与 DB 回归。

### 微信时间线单侧 identifier 去重 Review

- 红灯：两条新增测试首次运行均失败，均插入了重复 timeline。
- 绿灯：两条新增测试修复后 `2 passed`。
- 聚焦验证：`python -m pytest tests/test_talent_sync.py::test_import_wechat_timeline_dedupes_by_archive_identity_across_nodes -q` -> `1 passed`。
- 完整同步测试：`python -m pytest tests/test_talent_sync.py -q` -> `36 passed`。
- DB 回归：`python -m pytest tests/test_talent_db.py -q` -> `125 passed`。
- 语法与差异检查：`python -m py_compile scripts/talent_db.py scripts/talent_sync.py` -> PASS；`git diff --check` -> PASS，仅提示既有 `README.md` CRLF/LF 告警。

# Final Verification

## Review

- 聚焦测试：`python -m pytest tests/test_talent_sync.py tests/test_talent_db.py tests/test_talent_library_cli.py tests/test_talent_library_workflow.py -q` -> `175 passed`。
- 语法检查：`python -m py_compile scripts/talent_sync.py scripts/talent_sync_models.py scripts/talent_db.py scripts/talent_models.py` -> PASS。
- 全量回归：`python -m pytest tests scripts -q` -> `500 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异检查：`git diff --check` -> PASS；仅提示 `README.md` 工作区 CRLF 将转 LF。
- 最终评审复审：Final Review Fixes 规格复审通过；质量复审提出的 timeline identifier 非对称问题已修复并复审通过。

# Talent DB Bundle Sync 实施计划（2026-05-13）

> 目标：未来多台机器同时写入本地人才库时，不再靠整库覆盖，而是通过可校验 bundle 做离线合并同步。
> 计划文档：`docs/superpowers/plans/2026-05-13-talent-db-bundle-sync.md`
> 当前状态：**已完成**

## 本轮执行清单

- [x] Task 1：同步元数据 schema、节点标识和历史行 `sync_id` 回填。
- [x] Task 2：本地写入路径同步化，确保候选人及关联表新增行都有 `sync_id`。
- [x] Task 3：候选人删除写入 tombstone。
- [x] Task 4：新增 bundle 模型和 canonical hash 工具。
- [x] Task 5：实现全量 bundle 导出和 JSONL/checksum 生成。
- [x] Task 6：实现 bundle 校验。
- [x] Task 7：实现空库导入、id 重映射和 apply 确认。
- [x] Task 8：实现重复 bundle 幂等跳过。
- [x] Task 9：实现来源键跨节点合并和 alias 记录。
- [x] Task 10：实现候选人字段冲突记录。
- [x] Task 11：实现 tombstone 导入删除。
- [x] Task 12：实现 `scripts/talent_sync.py` CLI。
- [x] Task 13：支持可选微信时间线附件打包。
- [x] Task 14：更新数据契约和 README。
- [x] Task 15：运行聚焦测试、语法检查、全量回归和 diff 检查。

---

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

# 脉脉 AI Infra 搜索计划自动化执行方案（2026-05-12）
> 当前状态：已完成
> 目标：盘点现有工具与实践经验，先验证核心可行性，再交付人工仅参与策略确认和最终审查的自动化方案。
> 方案文档：`docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`

## 任务清单

- [x] Task 1：盘点仓库内工具、扩展、workflow、测试和既有输出记录
- [x] Task 2：验证核心链路：采集数据导入、候选人检索/评分、详情目标生成、扩展契约检查
- [x] Task 3：形成可直接落地的自动化执行方案，明确人工参与点、模块边界、数据流和验证步骤
- [x] Task 4：写入正式设计文档并完成关键字、路径和格式校验

## Review

- 已盘点可复用工具：`extensions/maimai-scraper`、`scripts/talent_library.py import/detail`、`scripts/maimai_detail_import.py`、`scripts/talent_db.py`、`scripts/platform_match/search.py`、`scripts/platform_match/adapters/maimai.py` 以及相关测试。
- 核心测试：`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q`，结果 **37 passed**。
- 导入链路实跑：`talent_library import` 对 Downloads 下 11 个 `maimai-capture-2026-05-12*.json` dry-run，结果原始 2519、去重 1795、新建 0、合并 1795、待确认 0、失败 0。
- 详情目标链路实跑：`talent_library detail --top10-file data/output/talent-match-2026-05-10-alibaba-cloud-ai-agent-pm-top10.json`，结果联系人 10、缺失 0。
- 搜索请求可自动化证据：历史 capture 中 `/api/ent/v3/search/basic` 请求体包含 `search.query`、`positions`、`allcompanies`、`degrees`、`worktimes`、`age`、`query_relation` 和 `paginationParam`。
- 本地策略检索 POC：`data/talent.db` 当前 2733 人、脉脉来源 2733、目标公司宽口径命中 1610、硬排除标题命中 309、宽口径策略交集 1306；说明需要新增规则评分器，不应只靠搜索命中。
- 扩展语法检查：`node --check extensions/maimai-scraper/*.js` 等价逐文件检查通过。
- 方案已写入 `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`，覆盖人工门禁、数据流、评分规则、文件边界、实施任务和验收命令。
- 文档校验：`rg -n "37 passed|2519|1795|maimai_ai_infra_search_runner|auto_apply_after_clean_dry_run|query_relation|人工参与点|熔断" docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` 命中关键内容。
- `git diff --check -- docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md tasks/todo.md ...` 通过，无 whitespace 报错。

## 用户评审后的修订

- 用户指出三个未充分验证点：Python CDP runner 可能触发反爬/登出、扩展导入/开始/导出依赖人工点击、`search_body_patch` 字段语义不明确。
- 已补充 `tasks/lessons.md`：端到端无人执行不能用本地数据链路验证替代。
- 调查结论：项目既有脉脉详情设计明确写过“CDP 抓取不可行，不作为方案基础”；Boss 渠道也有 `page.evaluate(fetch)` 触发强制登出的记录，因此 Python CDP 直接 fetch 不能作为默认主路径。
- 扩展结论：`background.js` 已有 `clearAll/importDetailContacts/startDetailBatch/getDetailBatchStatus/exportFullJson` 等内部消息，逻辑可复用；但当前没有本地 Python 到扩展后台的稳定自动化桥，且 `exportFullJson` 使用 `saveAs: true`，不满足无人保存文件。
- 字段结论：11 个历史搜索请求只验证了 `query/search_query`、分页、部分 `degrees/allcompanies/query_relation` 值存在；`positions/worktimes/age` 无有效样本，不能直接写入自动请求。
- 方案修订：已在 `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` 新增 Phase 0 可行性门禁，把 Python CDP 直接 fetch 降级为 POC，默认改为扩展/页面上下文模板重放或 UI 驱动 + 被动捕获；未验证字段只做本地过滤。

# 脉脉 AI Infra 人才搜索计划文档整理（2026-05-12）
> 当前状态：已完成
> 目标文档：`docs/design-discussions/2026-05-12-maimai-ai-infra-talent-search-plan.md`

## 任务清单

- [x] Task 1：将脉脉手动搜索策略整理为结构化 Markdown 文档
- [x] Task 2：覆盖公司优先级、关键词包、职位名称、搜索模板、筛选规则和执行节奏
- [x] Task 3：校验文档已写入目标目录，且核心关键词可检索

## Review

- 已新增 `docs/design-discussions/2026-05-12-maimai-ai-infra-talent-search-plan.md`，覆盖搜索原则、字段填写规则、候选人分层、公司优先级、职位名称、关键词包、搜索模板、执行节奏、停止规则和记录字段。
- 验证命令：`Get-Item docs\design-discussions\2026-05-12-maimai-ai-infra-talent-search-plan.md`，结果文件存在，大小 11910 字节。
- 验证命令：`rg -n "AI Infra|DeepSeek|Token|vLLM|SGLang|Moonshot" docs\design-discussions\2026-05-12-maimai-ai-infra-talent-search-plan.md`，结果核心关键词均可检索。
- 验证命令：`git diff --check -- docs\design-discussions\2026-05-12-maimai-ai-infra-talent-search-plan.md tasks\todo.md`，结果通过，无 whitespace 报错。

# 合并 worktree talent-contact-wechat-timeline 到 main（2026-05-12）
> 当前状态：已完成
> 目标：将 `talent-contact-wechat-timeline` worktree 对应分支合并到 `main`，并保留当前 `main` 上已有未提交改动。

## 任务清单

- [x] Task 1：确认目标 worktree 与分支状态，核对分支干净且可合并。
- [x] Task 2：保护当前 `main` 未提交改动，避免合并覆盖用户工作。
- [x] Task 3：执行 `talent-contact-wechat-timeline` 到 `main` 的合并并处理冲突。
- [x] Task 4：恢复合并前未提交改动，确认没有丢失。
- [x] Task 5：运行项目验证命令并记录结果。

## Review

- 目标 worktree `D:/workspace/talent-agent/.worktrees/talent-contact-wechat-timeline` 干净，对应分支 `talent-contact-wechat-timeline`。
- 合并方式：先 `git stash push --include-untracked -m "pre-merge-talent-contact-wechat-timeline-2026-05-12"` 保护当前 `main` 未提交改动，再 `git merge --ff-only talent-contact-wechat-timeline`；结果 fast-forward 到 `045d464`。
- stash 恢复时 `tasks/todo.md` 发生追加段落冲突；已保留目标分支的联系方式/微信实现记录，以及合并前本地 AI Infra 文档记录和本次合并记录。
- 验证命令：`python -m pytest tests scripts -q` -> **419 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- 最终状态：`main` 当前领先 `origin/main` 8 个 commit；合并前的未提交改动已恢复为未暂存状态。

---

# 清理 worktree talent-contact-wechat-timeline（2026-05-12）
> 当前状态：已完成
> 目标：删除已合并的 `talent-contact-wechat-timeline` worktree 和本地分支。

## 任务清单

- [x] Task 1：确认目标 worktree 干净，且 `talent-contact-wechat-timeline` 与 `main` 指向同一提交。
- [x] Task 2：删除 `.worktrees/talent-contact-wechat-timeline` worktree。
- [x] Task 3：删除已合并的本地分支 `talent-contact-wechat-timeline`。
- [x] Task 4：验证 worktree list、branch list 和当前工作区状态。

## Review

- 删除命令：`git worktree remove "D:/workspace/talent-agent/.worktrees/talent-contact-wechat-timeline"` -> 通过。
- 删除分支：`git branch -d talent-contact-wechat-timeline` -> 删除本地分支 `045d464`。
- 验证：`git worktree list --porcelain` 已不包含 `talent-contact-wechat-timeline`；`git branch --list talent-contact-wechat-timeline` 无输出；`Test-Path D:\workspace\talent-agent\.worktrees\talent-contact-wechat-timeline` -> `False`。
- 当前状态：`main` 仍领先 `origin/main` 8 个 commit；已有未提交改动保持为未暂存状态。
- Whitespace：`git diff --check` -> PASS。

---

# 脉脉 AI Infra 自动化搜索实施（2026-05-12）
> 当前状态：已实现并合并到 `main`。
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
- 合并：`maimai-ai-infra-automated-search` 已 fast-forward 合并到 `main`，commit `21dcc20`。
- 残余风险：独立 review 子代理未在 5 分钟内返回结果，已关闭；本次没有取得额外审查 findings。真实脉脉页面执行仍受 Phase 0 门禁约束，当前交付是离线 dry-run/template、本地评分和报告闭环。

## 2026-05-12 复核补强

- [x] 补齐 Phase 0 请求模板证据：从 `data/output/raw/maimai-ai-infra-field-calibration-2026-05-12.json` 提取 `sample_request.body`，生成 `data/output/raw/maimai-ai-infra-search-template-2026-05-12.json`，并用 `--template` 重新跑 runner/pipeline。
- [x] 增强 `run_pipeline()`：支持 `template_path` / CLI `--template`，避免流水线只使用默认空模板。
- [x] 增强测试覆盖：新增 `run_pipeline()` 主链路测试，断言真实模板形状中的 `sid/sessionid/highlight_exp/data_version` 被保留；补充 runner 对 `search` 内会话字段的保留断言；补充二梯队技术岗、泛岗位强技术证据评分 fixture。
- [x] 更新过程记录：`data/output/maimai-ai-infra-feasibility-2026-05-12.md` 已记录真实模板 dry-run 证据和保守结论。

### Review

- RED：`python -m pytest tests/test_maimai_ai_infra_pipeline.py::test_run_pipeline_uses_real_request_template_and_writes_outputs tests/test_maimai_ai_infra_strategy.py::test_ai_infra_score_grades_common_candidate_shapes tests/test_maimai_ai_infra_runner.py::test_patch_search_body_preserves_session_fields_and_patches_verified_fields -q` -> 1 failed, 2 passed，失败原因为 `run_pipeline()` 尚不支持 `template_path`。
- GREEN：同一命令复跑 -> **3 passed**。
- 聚焦验证：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **11 passed**。
- 计划 Phase 0 聚焦：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_scraper_extension.py -q` -> **37 passed**。
- 既有链路回归：`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q` -> **40 passed**。
- JS 语法：`node --check extensions/maimai-scraper/idb.js/detail_batch.js/background.js/content.js/inject.js/popup.js` -> **PASS**。
- Python 编译：`python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py` -> **PASS**。
- 全量测试：`python -m pytest tests scripts -q` -> **430 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- Whitespace：`git diff --check` -> **PASS**。

---

# maimai-scraper 无人导出与 Automation Bridge（2026-05-12）
> 当前状态：已完成实现与验证
> 目标：解锁 Phase 0 的扩展自动化桥与无人导出门禁，让本地 runner 后续可以在扩展上下文内调用批量详情链路，不依赖 popup DOM 或人工保存文件。

## 任务清单

- [x] Task 1：补扩展契约测试，覆盖 `getFullExportData`、`exportFullJson saveAs:false` 和 `automation.html/js`。
- [x] Task 2：重构 `background.js` 完整导出数据组装，新增不下载的 JSON 返回通道。
- [x] Task 3：新增 `automation.html` / `automation.js`，封装 `clearAll/importDetailContacts/startDetailBatch/getDetailBatchStatus/getFullExportData`。
- [x] Task 4：运行扩展聚焦测试、JS 语法检查、AI Infra 回归、全量测试和 whitespace 检查。

## 约束

- 不改变真实脉脉请求执行策略；真实搜索仍必须等 Phase 0 小样本验证。
- automation bridge 只暴露扩展内部消息编排，不绕过验证码、权限、风控或平台限制。
- 导出默认 UI 行为保持人工下载；无人导出必须通过显式 `saveAs:false` 或 `getFullExportData`。

## Review

- RED：`python -m pytest tests/test_maimai_scraper_extension.py::test_full_export_supports_unattended_data_return tests/test_maimai_scraper_extension.py::test_automation_page_exposes_detail_bridge_without_popup_dom -q` -> **2 failed**，原因是缺少 `buildFullExportData/getFullExportData` 和 `automation.html`。
- GREEN：同一命令复跑 -> **2 passed**。
- 扩展契约：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **28 passed**。
- JS 语法：`node --check extensions/maimai-scraper/idb.js detail_batch.js background.js content.js inject.js popup.js automation.js` -> **PASS**。
- AI Infra 聚焦：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **11 passed**。
- 既有导入/详情回归：`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_scraper_extension.py -q` -> **42 passed**。
- 全量测试：`python -m pytest tests scripts -q` -> **432 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- Whitespace：`git diff --check` -> **PASS**。
- 残余风险：本轮只解锁扩展上下文内的无人导出和消息桥；尚未用真实 Chrome CDP 打开 `chrome-extension://<id>/automation.html` 做端到端调用，也尚未跑真实脉脉小样本搜索。

## 2026-05-12 Bridge Smoke 复核

- [x] 补 `manifest.json` 的 `web_accessible_resources`，允许 CDP 直接打开 `automation.html` / `automation.js`。
- [x] 用隔离浏览器验证 extension automation bridge：Chrome 147 未接受当前 `--load-extension` 参数挂载仓库扩展；Edge 隔离 profile 成功加载仓库扩展并完成 smoke。
- [x] 记录 smoke 输出到 `data/output/raw/maimai-ai-infra-automation-bridge-smoke-2026-05-12.json`。
- [x] 更新 `data/output/maimai-ai-infra-feasibility-2026-05-12.md`，将扩展自动化桥与无人导出门禁从未验证提升为隔离扩展上下文内通过。

### Review

- RED：`python -m pytest tests/test_maimai_scraper_extension.py::test_automation_page_exposes_detail_bridge_without_popup_dom -q` -> **1 failed**，原因是 `manifest.json` 未暴露 automation 资源。
- GREEN：同一命令复跑 -> **1 passed**。
- Edge CDP smoke：`clearAll`、`importDetailContacts`、`getDetailBatchStatus`、`getFullExportData`、`exportFullJson(saveAs:false)` 均通过；无活跃脉脉标签页时 `startDetailBatch` 返回受控错误 `请在脉脉列表页使用批量详情`。
- 扩展契约：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **28 passed**。
- AI Infra 聚焦：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **11 passed**。
- Manifest JSON：解析通过。
- 全量测试：`python -m pytest tests scripts -q` -> **432 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` 的 `asyncio.get_event_loop()` deprecation。
- Whitespace：`git diff --check` -> **PASS**。
- 仍未通过：真实已登录 Chrome 的标准 CDP 端点；当前 9222 返回 404，无法验证真实登录态会话健康和真实详情启动。
---

# 脉脉 AI Infra Phase 0 专用 CDP Profile 复核（2026-05-13）

> 目标：在用户已登录的专用 Edge CDP profile 中，只做登录态健康检查与扩展 automation bridge smoke，不触发真实搜索、不绕过验证码、不执行批量抓取。

## 任务清单

- [x] Task 1：确认 `127.0.0.1:9888` CDP 页面列表、脉脉登录态与异常文本。
- [x] Task 2：打开 `chrome-extension://mdhjdjdmkghiecabeolipnhlcdecgnpj/automation.html`，复跑 automation bridge smoke。
- [x] Task 3：若存在已登录脉脉页面，只验证 `startDetailBatch` 前置链路的受控返回，不导入真实批量目标、不跑真实搜索。
- [x] Task 4：更新 `data/output/maimai-ai-infra-feasibility-2026-05-12.md`，记录真机复核结论。
- [x] Task 5：运行聚焦回归与 `git diff --check`。

## Review

- CDP 登录态健康：`127.0.0.1:9888` 可用，脉脉人才银行页与社区页均已登录且 `document.readyState=complete`，未见登录/验证码提示。
- automation bridge 真机 smoke：通过，输出 `data/output/raw/maimai-ai-infra-automation-bridge-smoke-real-cdp-2026-05-13.json`；空队列 `startDetailBatch` 返回 `ok=true,totalJobs=0`，未触发真实详情请求；测试联系人已清理。
- 过程记录：已更新 `data/output/maimai-ai-infra-feasibility-2026-05-12.md`。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> 28 passed；`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> 11 passed；`git diff --check` -> PASS。

## 下次恢复待办

- [ ] 先确认专用 Edge CDP profile 仍在 `127.0.0.1:9888`，且脉脉人才银行页仍为已登录状态；只读检查，不搜索。
- [ ] 做 UI/request diff 字段校准：由人工在页面触发一次小搜索，扩展只被动读取捕获到的 `/api/ent/v3/search/basic` 请求，校准 `query_relation`、`allcompanies`、`degrees` 的真实含义。
- [ ] 将字段校准结果写入 `data/output/maimai-ai-infra-feasibility-2026-05-12.md` 和 raw calibration JSON；未校准字段继续只做本地过滤，不写入自动请求。
- [ ] 字段校准通过后，再向用户确认是否执行搜索门禁；未确认前不跑自动搜索。
- [ ] 搜索门禁范围固定为 3 个小批次、每批 1 页、dry-run only，不写库、不 apply、不跑详情抓取。
- [ ] 熔断条件：登录失效、验证码、403、429、非 JSON、请求体结构不兼容或页面异常，出现任一项立即停止并写报告。

---

# 脉脉 AI Infra Phase 0 字段校准（2026-05-13）

> 目标：只做 UI/request diff 被动校准。由人工在脉脉人才银行页触发一次小搜索，扩展被动捕获 `/api/ent/v3/search/basic` 请求；本轮不自动发搜索、不写库、不 apply、不跑详情抓取。

## 任务清单

- [x] Task 1：只读确认 `127.0.0.1:9888` CDP 与脉脉登录态。
- [x] Task 2：记录扩展捕获基线时间与现有搜索请求数量，不清空用户数据。
- [x] Task 3：等待人工在人才银行页触发一次小搜索并回复“已搜索”。
- [x] Task 4：读取新增 `/api/ent/v3/search/basic` 请求，提取 `query_relation`、`allcompanies`、`degrees`、分页字段和查询词。
- [x] Task 5：写入 raw calibration JSON 与过程记录。
- [x] Task 6：运行 `git diff --check`，必要时提交任务记录。

## Review

- 基线：`data/output/raw/maimai-ai-infra-field-calibration-baseline-2026-05-13.json`，`capturedCount=29`，`searchRecordCount=0`。
- 人工搜索后：`data/output/raw/maimai-ai-infra-field-calibration-ui-diff-2026-05-13.json`，新增 1 条 `/api/ent/v3/search/basic`，响应 JSON 正常，`count=30,total=173,total_match=173`。
- 字段证据：`query/search_query` 为 `"算法" "agent"`；分页为 `paginationParam.page=1,size=30` 与 `page=0,size=30`；`allcompanies="一线互联网公司"`、`degrees="2,3"`、`query_relation=0` 仍只保留模板值，不主动改写。
- 约束：未自动发搜索，未写库，未 apply，未跑详情抓取；搜索执行门禁仍需用户二次确认。
- 验证：`ConvertFrom-Json` 读取校准 JSON 成功，`newSearchRecordCount=1`；过程记录可检索到 `UI/request diff 字段校准`、`newSearchRecordCount=1`、`query/search_query` 与 `不主动改写`；`git diff --check` -> PASS。

---

# 脉脉 AI Infra Phase 0 搜索执行门禁（2026-05-13）

> 目标：在用户授权后，用已登录专用 Edge CDP profile 和真实 UI 捕获模板，执行 3 个小批次、每批 1 页的搜索执行门禁。只 dry-run 取证，不写库、不 apply、不跑详情抓取；遇到登录失效、验证码、403、429、非 JSON、请求结构变化立即熔断。

## 任务清单

- [x] Task 1：修正扩展主动搜索 nested `search.query/search_query` patch，并补契约测试。
- [x] Task 2：只读确认专用 Edge CDP 登录态和页面模板可用。
- [x] Task 3：执行 3 个小批次、每批 1 页搜索，记录每批响应与会话健康。
- [x] Task 4：写入 raw run JSON 与 Phase 0 过程记录。
- [x] Task 5：运行聚焦测试、JS 语法检查、`git diff --check` 并提交记录。

## Review

- 修复点：扩展主动搜索原先只改写顶层 `body.query/keyword/keywords/q`，真实脉脉搜索关键词位于 nested `body.search.query/search_query`；已新增 `applySearchQuery()` 同步改写 nested 与兼容顶层字段。
- RED/GREEN：新增 `test_active_search_patches_nested_search_query_fields`，先验证旧实现缺口，再修复为通过；聚焦复跑 `test_active_search_patches_nested_search_query_fields` 与 `test_search_template_tracks_headers_and_nested_pagination` -> **2 passed**。
- 搜索门禁输出：`data/output/raw/maimai-ai-infra-search-gate-run-2026-05-13.json`。
- 搜索门禁范围：3 个小批次、每批 1 页、dry-run only；未写库、未 apply、未执行详情抓取。
- 批次结果：`"AI Infra" "LLM"` -> HTTP 200 JSON，`total=1,count=1,listLength=1`；`"vLLM" "SGLang"` -> HTTP 200 JSON，`total=2,count=2,listLength=2`；`"GPU" "CUDA"` -> HTTP 200 JSON，`total=19,count=19,listLength=19`。
- 会话健康：前后页面均为 `人才银行`，`readyState=complete`，`hasLoginPrompt=false`，`hasCaptcha=false`，`hasTalentBank=true`，cookie 可见长度 783。
- 结论：搜索执行方式门禁可标记为 `phase0-pass-for-search-gate`；但真实详情抓取仍未执行，详情链路只有空队列 preflight 通过，因此 Phase 0 端到端仍不能宣称完全通过。
- 最终验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **29 passed**；`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **11 passed**；`node --check extensions/maimai-scraper/inject.js` -> **PASS**；`git diff --check` -> **PASS**。

---

# 脉脉 AI Infra Phase 0 详情小样本门禁（2026-05-13）

> 目标：只用 1-3 个明确目标，在已登录专用 Edge CDP profile 中验证真实详情链路：`importDetailContacts -> startDetailBatch(safe) -> getFullExportData -> maimai_detail_import dry-run`。本轮仍不写库、不 apply、不扩大搜索；遇到登录失效、验证码、403、429、非 JSON、详情队列异常或导出结构不兼容立即熔断。

## 任务清单

- [ ] Task 1：只读确认 `127.0.0.1:9888` CDP、人才银行页登录态、扩展 automation bridge 与队列为空。
- [ ] Task 2：从本地已入库/搜索门禁结果中挑选 1-3 个明确目标，生成 `data/output/raw/maimai-ai-infra-detail-gate-targets-2026-05-13.json`，不写库。
- [ ] Task 3：通过 `automation.html` 导入小样本目标，safe 模式启动详情批次，轮询状态并记录熔断信号。
- [ ] Task 4：导出完整 raw JSON 到 `data/output/raw/maimai-ai-infra-detail-gate-run-2026-05-13.json`，随后清理扩展队列。
- [ ] Task 5：对导出结果运行 `scripts/maimai_detail_import.py dry-run`，更新过程记录与任务 Review。
- [ ] Task 6：运行聚焦测试、JS 语法检查、`git diff --check`，必要时提交 tracked 记录。

## 当前预检记录

- 已写入计划并开始只读预检，未启动真实详情批次。
- 预检输出：`data/output/raw/maimai-ai-infra-detail-gate-preflight-2026-05-13.json`。
- 扩展状态：automation bridge 可用，详情队列 `status=idle,total_jobs=0`；扩展中残留 `totalContacts=52,capturedRequests=37`。
- 证据保护：已完整备份扩展当前导出到 `data/output/raw/maimai-ai-infra-detail-gate-existing-export-before-run-2026-05-13.json`。
- 目标选择：已从备份导出中选择 3 个具备 `id + trackable_token` 的目标，写入 `data/output/raw/maimai-ai-infra-detail-gate-targets-2026-05-13.json`。
- 熔断：打开人才银行页后等待 7 秒，页面跳转为 `https://maimai.cn/`，标题 `脉脉-成就职业梦想`，`hasLoginPrompt=true`，输出 `data/output/raw/maimai-ai-infra-detail-gate-talent-page-health-2026-05-13.json`；按规则停止，未导入目标、未启动详情、未写库、未 apply。
- 用户回复“已登录”后复核：`data/output/raw/maimai-ai-infra-detail-gate-login-recheck-2026-05-13.json` 显示当前 `127.0.0.1:9888` 只有 automation 页和 `https://maimai.cn/platform/login?...` 登录页；`hasLoginPrompt=true`、`hasCaptcha=true`，仍未通过登录态门禁。继续停止，未导入目标、未启动详情、未写库、未 apply。
- 用户重新登录并手动导航后复核：现有页面列表中可见 `https://maimai.cn/ent/v41/recruit/talents?tab=1`，标题 `人才银行`，无登录/验证码提示；但扩展 `chrome.tabs.query({active:true,currentWindow:true})` 返回活动 tab 为 `https://maimai.cn/` 首页。因 `startDetailBatch` 依赖活动 tab，继续停止，未导入目标、未启动详情、未写库、未 apply。
- 用户手动激活人才银行页后：活动 tab 确认为 `https://maimai.cn/ent/v41/recruit/talents?pid=&tab=1`，导入 3 个目标成功，`startDetailBatch({mode:"safe",dailyLimit:3})` 返回 `ok=true,totalJobs=3`。状态轮询显示 `completed`、`done=3`、`failed=0`，但导出 `data/output/raw/maimai-ai-infra-detail-gate-run-2026-05-13.json` 中 `detailJobs=[]`、`details=[]`，只有 `metadata.captured_details=3`；`maimai_detail_import.py dry-run` 结果 `matched=0,unmatched=0,failed_jobs=0`。根因为扩展未把 start 后的新 `detailBatchRunToken` 持久化，导出时用旧 token 过滤掉本轮 jobs/details；已补本地测试和修复，但当前浏览器扩展尚未重载，本轮详情门禁不通过，未写库、未 apply。

---

# 脉脉 AI Infra Phase 0 详情小样本门禁重跑（2026-05-13）

> 目标：在修复 `detailBatchRunToken` 持久化问题并重载扩展后，重新验证 1-3 个明确目标的真实详情链路：`importDetailContacts -> startDetailBatch(safe) -> getFullExportData -> maimai_detail_import dry-run`。本轮仍只做门禁取证，不写库、不 apply、不扩大搜索。

## 执行约束

- 不主动 `goto` 或刷新脉脉企业端 URL；只有用户已经手动打开并激活稳定的人才银行页时，才读取现有状态。
- 重跑前必须确认浏览器中已加载的是当前修复后的扩展；若无法确认，停止并要求用户手动重载扩展与刷新人才银行页。
- 样本范围固定为既有 1-3 个目标，`safe` 模式，`dailyLimit=3`。
- 熔断条件：登录失效、验证码、403、429、非 JSON、活动 tab 非人才银行页、详情队列异常、导出结构变化、`detailJobs/details` 为空。
- `maimai_detail_import.py dry-run` clean 前不写库、不 apply。

## 任务清单

- [x] Task 1：本地确认 `detailBatchRunToken` 修复和契约测试存在。
- [x] Task 2：只读确认 `127.0.0.1:9888` CDP、现有人才银行页、活动 tab 与扩展 automation bridge 状态；不自动导航。
- [x] Task 3：确认扩展已重载到当前代码；若未重载，停止并让用户手动重载扩展、刷新人才银行页。
- [x] Task 4：复用 `data/output/raw/maimai-ai-infra-detail-gate-targets-2026-05-13.json`，导入 1-3 个目标并启动 safe 详情批次。
- [x] Task 5：轮询状态并导出 raw JSON；若 `detailJobs/details` 可用则运行详情 dry-run，否则记录失败统计。
- [x] Task 6：更新 `data/output/maimai-ai-infra-feasibility-2026-05-12.md`、详情 dry-run 报告与本 Review。
- [x] Task 7：运行扩展聚焦测试、JS 语法检查和 `git diff --check`。

## 当前记录

- 已确认上次失败根因是浏览器扩展未重载，导致旧导出逻辑仍按旧 `detailBatchRunToken` 过滤本轮 jobs/details。
- 本轮从只读预检开始，不触发真实详情请求，直到确认扩展版本和活动 tab 均满足前置条件。
- 本地修复确认：`python -m pytest tests/test_maimai_scraper_extension.py::test_background_persists_current_detail_batch_token_with_state tests/test_maimai_scraper_extension.py::test_background_guards_stale_detail_batch_callbacks tests/test_maimai_scraper_extension.py::test_background_captures_detail_batch_token_before_start_prework -q` -> **3 passed**；`node --check extensions/maimai-scraper/background.js` -> **PASS**。
- 只读预检：`127.0.0.1:9888` 可用，现有页面包含 `https://maimai.cn/ent/v41/recruit/talents?tab=1`（标题 `人才银行`）与 `edge://extensions/`；扩展 service worker 为 `chrome-extension://mdhjdjdmkghiecabeolipnhlcdecgnpj/background.js`，manifest version `2.4`，运行时 `saveDetailBatchState()` 已包含 `detailBatchRunToken: runToken || __detailBatchRunToken`。
- 受控失败：第一次重跑打开 `automation.html` 后，活动 tab 切到扩展页，`startDetailBatch` 返回 `ok=false,error="请在脉脉列表页使用批量详情"`；未触发真实详情请求，导出 `data/output/raw/maimai-ai-infra-detail-gate-run-2026-05-13-retry.json` 中 `detailJobs=0,details=0,captured_details=0`，结束后已 `clearAll`。
- 修正执行方式（已被用户纠正）：不能简单改成“打开 automation bridge 后重新激活人才银行 tab”。用户指出人才银行页是被我的某个操作触发平台安全机制后自动关闭；因此打开 automation 页、切换 tab、调用扩展后台都要视为高风险操作，不能再自动继续。
- 二次重跑前置检查：当前 CDP 页面列表只剩 `chrome-extension://mdhjdjdmkghiecabeolipnhlcdecgnpj/automation.html` 与 `edge://extensions/`，已不存在现有 `maimai.cn/ent/v41/recruit/talents` 人才银行页；按规则停止，未启动 `startDetailBatch`，未触发真实详情请求。
- 当前结论：详情门禁复跑暂停。下一步不是要求用户马上重开页面，而是先由用户决定是否继续承担平台安全风险；未获明确授权前，我不再触碰脉脉页面、automation 页或扩展后台。
- 用户明确授权后继续详情小样本复跑。前置检查显示现有人才银行页与 automation 页均存在，`chrome.tabs.query({active:true,currentWindow:true})` 返回人才银行页。
- 授权复跑结果：`clearAll -> importDetailContacts(3) -> startDetailBatch({mode:"safe",dailyLimit:3})` 执行；`start_resp.ok=true,totalJobs=3`，输出控制文件 `data/output/raw/maimai-ai-infra-detail-gate-authorized-control-2026-05-13.json`。
- 失败证据：最终状态 `completed` 但 `done=0,failed=3`，三个 job 均报 `Could not establish connection. Receiving end does not exist.`；导出 `data/output/raw/maimai-ai-infra-detail-gate-authorized-run-2026-05-13.json` 中 `detailJobs=3,details=0,captured_details=0,total_jobs=3`。
- dry-run：`python scripts/maimai_detail_import.py dry-run --capture-file data/output/raw/maimai-ai-infra-detail-gate-authorized-run-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-gate-authorized-dry-run-2026-05-13.md` -> `matched=0,unmatched=0,failed_jobs=3`。
- 授权复跑后页面复核：人才银行页跳转为 `https://maimai.cn/platform/login?to=...`，说明本轮再次触发平台安全机制；已停止所有脉脉页面和扩展操作。
- 当前结论：`detailBatchRunToken` 导出修复生效（导出不再空过滤 job），但真实详情小样本门禁仍 **不通过**；失败原因从旧 token 过滤问题转为扩展 content script 接收端缺失，并伴随平台安全机制触发。不能进入写库、apply 或更大规模自动化。

## Review

- 授权复跑控制证据：`data/output/raw/maimai-ai-infra-detail-gate-authorized-control-2026-05-13.json`。
- 授权复跑导出：`data/output/raw/maimai-ai-infra-detail-gate-authorized-run-2026-05-13.json`，`detailJobs=3,details=0,failed_jobs=3`。
- dry-run：`python scripts/maimai_detail_import.py dry-run --capture-file data/output/raw/maimai-ai-infra-detail-gate-authorized-run-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-gate-authorized-dry-run-2026-05-13.md` -> `matched=0,unmatched=0,failed_jobs=3`。
- 报告更新：`data/output/maimai-ai-infra-feasibility-2026-05-12.md` 已追加授权复跑结论：token 修复生效，但真实详情小样本门禁不通过。
- 验证：`python -m pytest tests/test_maimai_scraper_extension.py -q` -> **30 passed**。
- 验证：`node --check extensions/maimai-scraper/background.js` -> **PASS**。
- 验证：`git diff --check` -> **PASS**。
- 最终安全结论：停止所有脉脉页面、automation 页与扩展后台操作；后续详情补全应改为人工触发/被动捕获路径，或重新设计低风控门禁方案。

---

# 脉脉详情手动路径 vs 自动化路径差异比对方案（2026-05-13）

> 目标：解释为什么“浏览器扩展 popup 手动导入 JSON 并点击批量详情”可成功，而“通过 automation/CLI 调用扩展同一链路”会失败并触发平台安全机制。当前只做方案设计，不触碰脉脉页面，不调用扩展后台。

## 当前证据与纠正

- 手动路径用户反馈可成功，不触发平台安全机制。
- 自动化授权复跑中，`startDetailBatch` 可创建 3 个 jobs，说明 background、导入与 token 导出链路可用。
- 自动化复跑后人才银行页跳转到登录页，说明自动化流程触发了平台安全机制。
- 用户纠正：`Could not establish connection. Receiving end does not exist.` 不应作为首要根因；它发生在安全机制触发、人才银行页已关闭/登出后，自然会找不到 content script 接收端。
- 当前重点：比较自动执行和手动执行详情批量抓取的差异，找出触发安全机制的具体行为，并评估是否可规避。

## 核心假设

- H1：自动化路径的 CDP 附着、Runtime.evaluate、读取页面列表或检查 active tab 本身可能触发平台安全策略。
- H2：automation 页或 CLI 调用改变了窗口/标签焦点、当前 active tab 或页面可见性；手动 popup 路径则保持用户真实前台操作上下文。
- H3：automation sender 来源是 `automation.html` 或外部 CDP 驱动，手动 sender 来源是 `popup.html`；扩展后台消息的 sender、时间间隔和触发栈不同。
- H4：自动化路径的调用节奏过于机械，例如导入后立即 start、1 秒轮询、快速导出/清理；手动路径有自然停顿。
- H5：自动化路径调用了额外的非手动动作，例如打开 automation 页、读取 CDP `/json/list`、反复 `getDetailBatchStatus`、`getFullExportData`、`clearAll`，这些组合可能构成异常行为。
- H6：`Receiving end does not exist` 只是安全机制触发后的下游观测，不作为首要根因；content script ping 只用于确认“页面是否已被关闭/登出”。

## 对比方案

- [ ] Task 1：只做代码级静态差异表，列出手动 popup 和 automation 页调用的共同点与差异点，不连接浏览器。
- [ ] Task 2：为扩展增加诊断 trace，不改变真实抓取逻辑；记录 `sender.url`、sender 类型、active tab、window focus、target tab、页面 visibility、导入来源、start 前后时间间隔、轮询频率和清理/导出动作。
- [ ] Task 3：新增 `preflightTrace` / `probeOnly` 模式，只记录自动化动作对窗口/标签/页面状态的影响，不发真实详情请求；content script ping 仅作为后置状态项，不作为根因先验。
- [ ] Task 4：由用户执行一次手动成功路径，导出诊断 trace 与 capture JSON；我只读取本地导出文件。
- [ ] Task 5：在用户明确授权后执行 automation 的 `probeOnly` 对照，不发真实详情请求；若与手动 trace 差异明显，停止，不进入真实详情。
- [ ] Task 6：写一个本地 diff 脚本比较两份 trace，输出差异矩阵和根因判定。
- [ ] Task 7：只有当 `probeOnly` 与手动路径在 active tab、content script、visibility、sender 节奏等关键项完全一致时，才讨论是否做 1 个目标的真实详情 A/B；默认不继续真实自动化。

## 预期判定矩阵

- 若 automation `preflightTrace` 尚未发真实详情请求就导致 URL/标题/登录态变化：根因优先判定为 CDP 附着、automation 页或状态读取动作触发安全机制。
- 若手动与自动化的 active tab/focus/visibility/sender 不同：优先判定为调用上下文差异。
- 若上下文一致但 automation 的时间间隔、轮询频率、导出/清理动作不同：优先判定为调用节奏差异。
- 若自动化只要打开 automation 页就改变 active tab 或页面可见性：需要改为不打开新页、不依赖 active tab 的显式 `targetTabId` 或由 popup 内部发起的设计。
- 若所有前置信号一致但真实详情仍触发登录页：优先判定为平台对程序化扩展后台调用或 CDP 附着敏感；不再继续自动化。
- 若 automation 只要打开 automation 页就改变 active tab：需要改为不依赖 active tab 的显式 `targetTabId` 设计，且仍需通过 `probeOnly` 验证。

## 安全边界

- 不再用 CDP 自动导航、刷新或激活人才银行页。
- 不在未授权情况下打开 automation 页或调用扩展后台。
- 首轮对比只允许被动读取人工导出的 trace；automation 首轮只允许 `probeOnly`，不发真实详情请求。
- 任一环节出现登录页、验证码、429/403、content script 缺失或页面异常，立即停止并写报告。

## 执行计划

- [x] Task 1：补扩展契约测试，要求 background 支持 `preflightTrace`、`probeOnly`、`getDiagnosticTraces`、`clearDiagnosticTraces`，并记录 `sender.url`、active tab、window focus、页面可见性和 action label。
- [x] Task 2：补 automation 契约测试，要求 `window.maimaiScraperAutomation` 暴露 `preflightTrace()`、`probeOnly()`、`getDiagnosticTraces()`、`clearDiagnosticTraces()`。
- [x] Task 3：补 content 契约测试，要求 content script 支持非侵入式 `tracePageState`，只返回 `location.href`、`document.title`、`document.visibilityState`、`document.hasFocus()`，不发真实详情请求。
- [x] Task 4：新增本地 `scripts/maimai_trace_diff.py` 与测试，用两份 trace JSON 输出 sender、active tab、visibility、timing、extra actions 的差异矩阵。
- [x] Task 5：实现扩展诊断 trace 和 automation API，保持真实 `startDetailBatch` 链路不变。
- [x] Task 6：运行聚焦测试、JS/Python 语法检查、`git diff --check`。

## Review

- 已实现扩展诊断 trace：`preflightTrace`、`probeOnly`、`getDiagnosticTraces`、`clearDiagnosticTraces`；`probeOnly` 不调用 `sendDetailFetch` 或 `DetailBatch.run`。
- 已实现 content 被动页态探针：`tracePageState` 只返回 `location.href`、`document.title`、`document.visibilityState`、`document.hasFocus()`，不向页面 `postMessage`，不触发真实详情请求。
- 已让关键批量动作写入诊断 trace：`clearAll`、`importDetailContacts`、`startDetailBatch`、`getDetailBatchStatus`、`getFullExportData`、`exportFullJson`；完整导出包含 `diagnosticTraces`，便于手动路径导出后离线比对。
- 已新增 `scripts/maimai_trace_diff.py`，支持读取 `traces` / `diagnosticTraces` / 嵌套 `data` 形态，输出 sender、active tab、visibility/focus、动作序列和调用间隔差异矩阵。
- RED 验证：新增扩展诊断契约测试与 trace diff 测试均先失败，缺口分别为诊断接口/动作 trace/diff 脚本不存在。
- 聚焦验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q` -> **37 passed**。
- 语法检查：`node --check extensions/maimai-scraper/background.js`、`content.js`、`automation.js` -> **PASS**；`python -m py_compile scripts/maimai_trace_diff.py` -> **PASS**。
- 全量验证：`python -m pytest tests scripts -q` -> **441 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异检查：`git diff --check` -> **PASS**。

## 手动成功路径 trace 读取（2026-05-13）

- 用户完成手动详情抓取并导出：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (1).json`。
- 本地只读检查结果：`contacts=30`、`detailJobs=30`、`details=30`、`captured_details=30`、`failed=0`、`diagnosticTraces=166`。
- 详情结果：30 个 jobs 全部 `done`，4 个详情接口均返回 200；`maimai_detail_import.py dry-run` 输出 `data/output/maimai-ai-infra-manual-detail-dry-run-2026-05-13.md`，结果 `matched=17,unmatched=13,failed_jobs=0`，未写库、未 apply。
- 手动 trace 基线：所有 trace 的 `senderType=popup`，`sender.url=chrome-extension://mdhjdjdmkghiecabeolipnhlcdecgnpj/popup.html`。
- 手动 trace 页面状态：所有 trace 的 active tab / target tab / page href 均为 `https://maimai.cn/ent/v41/recruit/talents?tab=1`，标题 `人才银行`，`visibilityState=visible`。
- 手动 trace 焦点状态：`windowFocused=false` 且 `document.hasFocus=false`，但详情仍成功；因此窗口焦点/页面焦点不是充分触发条件，后续更应优先比较 sender、active tab、visibility、动作序列和真实详情请求来源。
- 手动动作序列：`clearAll -> exportFullJson -> importDetailContacts -> startDetailBatch`；`importDetailContacts -> startDetailBatch` 间隔约 3507ms。
- 手动详情节奏：30 个 job 的单次详情耗时约 `695-1040ms`，job start 间隔约 `5954-13144ms`，平均约 `9464ms`，符合 safe 模式的自然节奏。
- 上次自动化失败导出尚未包含 `diagnosticTraces`，不能与本次手动 trace 做同粒度 diff；下一步需要一个不发真实详情请求的 automation `probeOnly` trace 对照，且必须由用户再次明确授权。

## Automation probeOnly 对照执行（2026-05-13）

- [x] Task 1：只读检查 `127.0.0.1:9888/json/list`，确认是否已有 `automation.html` 和人才银行页；不导航、不刷新、不激活 tab。
- [x] Task 2：通过 automation 页执行 `clearDiagnosticTraces -> preflightTrace -> probeOnly -> getDiagnosticTraces`；不调用 `importDetailContacts`、`startDetailBatch`、`detailFetch`、`getFullExportData`。
- [x] Task 3：保存 automation trace 到 `data/output/raw/maimai-ai-infra-automation-probe-trace-2026-05-13.json`。
- [x] Task 4：用 `scripts/maimai_trace_diff.py` 比较手动导出与 automation probe trace，输出到 `data/output/maimai-ai-infra-manual-vs-automation-probe-diff-2026-05-13.md`。
- [x] Task 5：记录对照结果；若出现登录页、验证码、content script 缺失或 pageState 异常，立即停止且不进入真实详情。

## Automation probeOnly 对照 Review（2026-05-13）

- 执行前 CDP 页面：存在 `https://maimai.cn/ent/v41/recruit/talents?tab=1` 人才银行页和扩展 service worker；不存在 `automation.html`。
- 为获得真实 automation sender，本轮临时打开扩展 `automation.html`；未导航、刷新或激活人才银行页，未调用导入/启动详情/真实详情请求。
- probe 输出：`data/output/raw/maimai-ai-infra-automation-probe-trace-2026-05-13.json`，`diagnosticTraces=2`，动作仅 `preflightTrace` 和 `probeOnly`。
- 执行后人才银行页仍存在，标题 `人才银行`，未观察到登录页/验证码；临时 automation 页已关闭，页面列表中 `remainingAutomationPages=0`。
- diff 输出：`data/output/maimai-ai-infra-manual-vs-automation-probe-diff-2026-05-13.md`。
- 核心差异 1：手动成功路径 `senderType=popup` / `sender.url=.../popup.html`；automation probe `senderType=automation` / `sender.url=.../automation.html`。
- 核心差异 2：手动成功路径中人才银行页是 active/visible；automation probe 中 active tab 变为 automation 页，人才银行页 `active=false`、`visibilityState=hidden`。
- 核心差异 3：手动成功路径 `windowFocused=false`、`document.hasFocus=false` 仍成功；automation probe `windowFocused=true` 但人才银行页 hidden，说明关键不是“窗口聚焦”，而是“目标页是否仍作为前台可见业务页”。
- 当前根因判断：自动化路径在进入真实详情前已经改变调用上下文，最可疑触发因素是 `automation.html`/CDP 作为 sender 且把人才银行页置为 hidden；这与用户手动 popup 成功路径存在强差异。
- 规避方向：不要用会抢占 active tab 的 `automation.html` 作为生产详情入口；优先改成 popup/用户手动触发路径，或设计不打开新页且显式 `targetTabId`、同时保持人才银行页 active/visible 的低风险控制面。真实详情自动化在该差异消除前不应继续。

## Popup 本地任务包自动化重设计（2026-05-13）

> 目标：不再用 `automation.html`/CDP 作为真实详情入口；改为本地 CLI 提供任务包，用户在人才银行页打开扩展 popup 点击加载/启动，让真实详情触发仍来自已验证成功的 `popup.html` sender。

- [x] Task 1：写入实施计划 `docs/superpowers/plans/2026-05-13-maimai-popup-local-plan-automation.md`。
- [x] Task 2：补 popup 本地任务包契约测试，要求 manifest 允许 localhost、popup 暴露本地任务包 URL、加载、加载并启动按钮，JS 使用 `fetch(localPlanUrl)` 并复用 `importDetailContacts/startDetailBatch`。
- [x] Task 3：实现 popup 本地任务包入口：`detail-local-plan-url`、`btn-load-local-detail-plan`、`btn-load-start-local-detail-plan`、`detail-local-plan-status`。
- [x] Task 4：新增 `scripts/maimai_detail_plan_server.py`，只读服务 `/detail-plan.json` 与 `/health`，默认 `127.0.0.1:8765`。
- [x] Task 5：补 `tests/test_maimai_detail_plan_server.py`，覆盖 contacts 形态、顶层 list 形态和缺失 contacts 报错。
- [x] Task 6：运行验证并准备进入用户协作执行。

## Popup 本地任务包自动化 Review（2026-05-13）

- 新增 popup 任务包入口，但真实详情仍由用户在 popup 点击触发；没有新增 CDP/automation.html 真实详情路径。
- `manifest.json` 新增 `http://127.0.0.1/*`、`http://localhost/*` host permissions，仅用于 popup 读取本地任务包。
- `scripts/maimai_detail_plan_server.py` 只读取指定 JSON 文件并服务给 popup，不触碰浏览器。
- 聚焦验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q` -> **38 passed**。
- 语法检查：`node --check extensions/maimai-scraper/popup.js`、`python -m py_compile scripts/maimai_detail_plan_server.py`、`git diff --check` -> **PASS**。
- 全量验证：`python -m pytest tests scripts -q` -> **445 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。

## Popup 本地任务包执行结果（2026-05-13）

- 用户按新方案执行 popup 本地任务包路径后导出：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (2).json`。
- 导出检查：`contacts=3`、`detailJobs=3`、`details=3`、`captured_details=3`、`done=3`、`failed=0`、`skipped=0`、`circuit_breaker.tripped=false`。
- 三个详情 job 均成功，四个详情接口均返回 200：`basic=200`、`projects=200`、`job_preference=200`、`contact_btn=200`。
- job 节奏：单 job 耗时 `669-843ms`；job start 间隔约 `5928ms`、`8815ms`，符合 safe 模式低速执行。
- dry-run：`python scripts/maimai_detail_import.py dry-run --capture-file "C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (2).json" --db data/talent.db --out data/output/maimai-ai-infra-popup-local-plan-dry-run-2026-05-13.md` -> `matched=2,unmatched=1,failed_jobs=0`；未写库、未 apply。
- trace 清洗：导出中残留了上一次 automation probe 的 2 条旧 trace；已生成仅包含本轮 popup sender 的 trace：`data/output/raw/maimai-ai-infra-popup-local-plan-trace-2026-05-13.json`。
- trace diff：`data/output/maimai-ai-infra-manual-vs-popup-local-plan-diff-2026-05-13.md`；与手动成功基线相比，sender/active tab/page visibility/page focus/window focus 均一致，仅动作序列因本轮目标数和前置状态轮询不同而不同。
- 结论：`CLI 本地任务包服务 + 用户在人才银行页 popup 加载/启动 + 扩展 safe 详情 + 导出 + 本地 dry-run` 小样本闭环已打通。该结论覆盖 3 个目标的 human-in-the-loop 自动化，不代表可以恢复 `automation.html`/CDP 真实详情入口。

## AI Infra Phase 0 收口与可行落地计划（2026-05-13）

> 目标：结束前期可行性调研，把调研结论和经验记录完整；复审 `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md`，制定当前技术可行条件下的执行计划。

- [x] Task 1：读取旧自动搜索计划、Phase 0 可行性报告、详情差异对照、popup 本地任务包方案和现有 AI Infra 脚本。
- [x] Task 2：更新 `data/output/maimai-ai-infra-feasibility-2026-05-12.md` 顶部最终判定：搜索小样本通过，`automation.html`/CDP 真实详情入口不通过，popup 本地任务包详情闭环通过。
- [x] Task 3：新增调研复盘 `docs/design-discussions/2026-05-13-maimai-ai-infra-phase0-retrospective.md`，记录关键证据、技术边界、禁用路径、放大策略和对旧计划的影响。
- [x] Task 4：在旧计划 `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` 顶部加入 2026-05-13 复审结论，标注“完全无人详情补全”目标不再成立。
- [x] Task 5：新增当前可行落地计划 `docs/superpowers/plans/2026-05-13-maimai-ai-infra-feasible-execution.md`。
- [x] Task 6：运行文档一致性检查和 `git diff --check`，补充本 Review。

## AI Infra Phase 0 收口 Review

- 旧计划保留搜索 dry-run、本地导入 dry-run、本地评分和 shortlist 主干；废弃 `automation.html`/CDP 真实详情入口作为默认路径。
- 新计划将人机协作点固定为：策略确认、搜索 apply 确认、详情 popup 启动、详情 apply 确认。
- 新计划将扩大路径拆为搜索 Gate S2/S3 和详情 Gate D2/D3，避免从 3 条详情直接扩大到大批量。
- 新计划的可执行主线：策略配置 -> 搜索 S2 -> 搜索 dry-run/apply gate -> rank -> 详情目标 -> detail plan server -> 用户 popup 启动 -> 详情 dry-run/apply gate -> 最终执行报告。
- 文档一致性检查通过：旧计划已标注 superseded，新落地计划引用 `2026-05-13-maimai-ai-infra-feasible-execution.md`，未发现需要处理的占位项。
- `git diff --check` 已通过；本收口阶段未执行浏览器、CDP 或真实平台动作。
- 全量本地回归通过：`python -m pytest tests scripts -q` -> 445 passed, 1 个既有 `scripts/test_boss.py` 事件循环弃用 warning。
- 语法检查通过：`node --check` 覆盖扩展主要 JS；`python -m py_compile` 覆盖新增详情计划服务和 trace diff 脚本。

# AI Infra Gate S2/D2 执行（2026-05-13）

> 目标：在当前可行技术边界下执行搜索 Gate S2（5 批 x 1 页，无写库）和详情 Gate D2（10 人 popup 本地任务包），全程保留 raw 证据，写库必须等待显式 apply 授权。

- [x] Task 1：生成 S2 搜索计划 `data/output/maimai-ai-infra-search-plan-s2-2026-05-13.json`。
- [x] Task 2：生成 S2 选中 5 批文件 `data/output/raw/maimai-ai-infra-search-plan-s2-selected-2026-05-13.json`。
- [x] Task 3：运行 S2 模板 dry-run，确认只 patch `query/search_query` 和分页字段。
- [x] Task 4：定位或补齐受控 live search 执行方式；禁止详情、禁止写库、遇登录/验证码/429/非 JSON 立即停止。
- [x] Task 5：用户确认专用 Edge profile 人才银行页健康后，执行 S2 live search，输出 raw run JSON。
- [x] Task 6：把 S2 搜索结果转换为 contacts payload，并运行搜索导入 dry-run。
- [x] Task 7：dry-run clean 后请求搜索 apply 授权；未授权不写 `data/talent.db`。（本轮 contacts=0，apply 为无写入 no-op，未请求授权）
- [x] Task 8：生成 AI Infra shortlist，并选出 D2 10 人详情目标任务包。
- [x] Task 9：启动本地 detail plan server，引导用户用 popup 执行 D2，取得下载 JSON 后运行详情 dry-run。
- [x] Task 10：生成执行报告、更新 Review，并运行必要验证。

## AI Infra Gate S2/D2 Review

- S2 计划生成通过：全量计划 80 批，每批默认 3 页；S2 selected plan 已收紧为前 5 批、每批 1 页，且 `writeDb=false`、`apply=false`、`detailFetch=false`。
- S2 模板 dry-run 通过：`data/output/raw/maimai-ai-infra-search-run-s2-template-2026-05-13.json` 为 `dry-run-template-only`，共 5 批 5 页。
- 模板 patch 校验通过：`query/search_query` 已替换为批次关键词；`allcompanies/degrees/positions/worktimes/age` 保持模板值不变；分页为 page=1、size=30。
- 新增受控 live runner：`scripts/maimai_ai_infra_search_live_gate.py`。它只连接已有人才银行页 CDP target，读取页面内 `window.__maimaiSearchTemplate`，只替换 query 和分页；不打开 `automation.html`、不触发详情、不写库，遇登录/验证码/403/429/非 JSON 立即停止并写 raw run。
- live runner TDD 验证：先新增 `tests/test_maimai_ai_infra_search_live_gate.py` 并观察到 `ModuleNotFoundError` 红灯；实现后 `python -m pytest tests/test_maimai_ai_infra_search_live_gate.py -q` -> 4 passed。
- 会话恢复后修复 Edge CDP WebSocket Origin：`CdpSession` 使用 `websocket.create_connection(..., suppress_origin=True)`，避免 Edge 拒绝默认 `Origin: http://127.0.0.1:9888`；补 `test_cdp_session_suppresses_origin_header` 锁定行为。
- 根据只读复核补强 live runner 信任边界：新增 `validate_search_template_status()`，要求模板为 `POST /api/ent/v3/search/basic`，且 body 含 query/search_query 与分页字段；不兼容时在发页面内 `fetch` 前写 `stopReason=incompatible_request_shape` 并停止。
- 补强 raw run 证据：每批保留 `responseData`（完整解析 JSON）和 `responseRawPreview`（前 2000 字符），异常分支会写入 batch `error`；最终健康检查异常时写 `afterHealthError`，不丢已采集证据。
- 恢复后验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **16 passed**；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py` -> **PASS**；`git diff --check` -> **PASS**。
- 用户明确确认后执行 S2 live search：`data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.json`，结果 `status=completed`、`batches=5`、`contacts=0`；5 个 batch 均为 HTTP 200 JSON，`code=0/result=ok`，无登录、验证码、403、429 或非 JSON 熔断。
- S2 响应业务结果：5 个精确查询均返回 `total=0,total_match=0,count=0,listLength=0`；页面执行前后仍为 `https://maimai.cn/ent/v41/recruit/talents?tab=1`，`hasLoginPrompt=false`、`hasCaptcha=false`。
- contacts payload：`data/output/raw/maimai-ai-infra-search-run-s2-2026-05-13.contacts.json`，`total_contacts=0`。
- 搜索导入 dry-run：`data/output/talent-import-ai-infra-s2-dry-run-2026-05-13.md` -> 原始 0、去重后 0、新建 0、合并 0、待确认 0、失败 0；未写 `data/talent.db`，未 apply。
- 当前暂停点：S2 平台门禁通过但业务结果为空；继续 rank/D2 会基于旧库而不是 S2 新结果，不符合“从新/更新搜索池选 D2 目标”的计划。下一步应重规划 S2b/S3 查询宽度，降低引号精确匹配强度或选取更宽的公司/关键词批次后再请求新的 live search 授权。

## S2b 宽查询探针

> 目标：针对 S2 五个精确查询全部返回 0 的情况，先用 5 个更宽关键词验证平台搜索是否能返回可用候选。仍只做搜索，不写库、不 apply、不触发详情。

- [x] Task 1：生成 S2b selected plan：`data/output/raw/maimai-ai-infra-search-plan-s2b-selected-2026-05-13.json`。
- [x] Task 2：运行 S2b 模板 dry-run：`data/output/raw/maimai-ai-infra-search-run-s2b-template-2026-05-13.json`。
- [x] Task 3：用户确认专用 Edge profile 人才银行页健康后，执行 S2b live search。
- [x] Task 4：若 S2b 返回联系人，转换 contacts payload 并运行导入 dry-run；clean 前不写库、不 apply。

## S2b Review

- S2b 查询：`AI Infra`、`ML Infra`、`大模型`、`分布式训练`、`推理`。
- S2b selected plan 约束：`max_batches=5`、`max_pages_per_batch=1`、`writeDb=false`、`apply=false`、`detailFetch=false`。
- S2b 模板 dry-run 通过：5 个 batch 均为 `dry-run-template-only`，每批 1 页；`query/search_query` 被替换为宽关键词，分页为 `page=1,size=30`。
- 模板保留项：`allcompanies=一线互联网公司`，`degrees/positions/worktimes/age` 等模板字段未由 S2b 改写。
- 验证：`git diff --check` -> **PASS**。
- 用户明确确认后执行 S2b live search：`data/output/raw/maimai-ai-infra-search-run-s2b-2026-05-13.json`，结果 `status=completed`、`batches=5`、`contacts=150`；5 个 batch 均为 HTTP 200 JSON，无登录、验证码、403、429 或非 JSON 熔断。
- S2b 每批返回：`AI Infra` 30/440，`ML Infra` 30/228，`大模型` 30/1000（total_match=3087），`分布式训练` 30/1000，`推理` 30/751；页面执行前后仍为人才银行页，`hasLoginPrompt=false`、`hasCaptcha=false`。
- contacts payload：`data/output/raw/maimai-ai-infra-search-run-s2b-2026-05-13.contacts.json`，`total_contacts=150`。
- 搜索导入 dry-run：`data/output/talent-import-ai-infra-s2b-dry-run-2026-05-13.md` -> 原始 150、去重后 139、新建 130、合并 9、待确认 0、失败 0；未写 `data/talent.db`，未 apply。
- 备注：S2b raw run 的 `run_id` 字段沿用 live runner 默认 `maimai-ai-infra-search-s2-2026-05-13`，但文件名和 selected plan gate 均为 S2b；本轮不改写 raw 证据。
- 当前门禁：S2b 搜索 dry-run clean，可进入搜索 apply 授权门禁；只有用户明确回复 `确认导入 AI Infra 搜索结果` 后才允许写入 `data/talent.db`。
- 用户明确回复 `确认导入 AI Infra 搜索结果` 后执行 apply：`data/output/talent-import-ai-infra-s2b-apply-2026-05-13.md` -> 原始 150、去重后 139、新建 130、合并 9、待确认 0、失败 0。
- 生成 S2b shortlist：`data/output/maimai-ai-infra-shortlist-s2b-2026-05-13.json` 与 `data/output/maimai-ai-infra-shortlist-s2b-2026-05-13.md`；分层统计 A=315、B=572、C=840、淘汰=1136。
- 生成 D2 详情目标包：`data/output/raw/maimai-ai-infra-detail-targets-d2-s2b-2026-05-13.json`，取 A 档前 10 人，`total_contacts=10,missing=0`。
- 已启动本地 detail plan server：`http://127.0.0.1:8765/detail-plan.json`，`/health` 返回 `ok=true,totalContacts=10`；日志在 `data/output/raw/maimai-detail-plan-server-d2-s2b-8765.out.log` 与 `.err.log`。
- 用户完成 D2 popup 路径并提供下载文件：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (3).json`；已归档为 `data/output/raw/maimai-ai-infra-detail-capture-d2-s2b-2026-05-13.json`。
- D2 capture 检查：`contacts=10,detailJobs=10,details=10,captured_details=10,total_jobs=10,done=10,failed=0,skipped=0,diagnosticTraces=96`；导出中残留早先 automation probe trace 2 条，本轮 D2 实际 trace 主要为 popup sender，popup visible trace 90 条。
- D2 详情 dry-run：`data/output/maimai-ai-infra-detail-d2-s2b-dry-run-2026-05-13.md` -> 匹配 10、未匹配 0、失败 jobs 0、写入人数 0。
- 本地 detail plan server 已停止，`127.0.0.1:8765` 不再监听。
- 当前门禁：D2 dry-run clean，可进入详情 apply 授权门禁；只有用户明确回复 `确认写入 AI Infra 脉脉详情` 后才允许写入详情。
- 用户明确回复 `确认写入 AI Infra 脉脉详情` 后执行详情 apply：`data/output/maimai-ai-infra-detail-d2-s2b-apply-2026-05-13.md` 与 `data/output/maimai-ai-infra-detail-d2-s2b-apply-2026-05-13.json` -> 匹配 10、未匹配 0、失败 jobs 0、写入人数 10。
- 写后抽样/全量目标验证：10 个 candidate_id 均存在 `candidate_details` 记录，详情 JSON 计数与 apply 报告一致：刘松伟 work=4/edu=2/project=0，jr 4/3/0，廖常越 4/2/0，王大锤 4/0/0，林睿江 3/2/0，陈垣桥 8/5/0，Mr Red 2/2/0，廖嘉伟 5/2/0，大梦想家 6/3/0，阳晨 2/1/0。
- 最终执行报告：`data/output/maimai-ai-infra-execution-2026-05-13.md` 已更新 S2/S2b、search apply、shortlist、D2 target、D2 capture、detail dry-run/apply 和残余风险。
- 最终聚焦验证：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py tests/test_maimai_trace_diff.py tests/test_maimai_detail_import.py tests/test_maimai_detail_targets.py -q` -> **67 passed**。
- 最终语法检查：`node --check extensions/maimai-scraper/background.js/content.js/inject.js/popup.js` -> **PASS**；`python -m py_compile scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_targets.py scripts/maimai_detail_import.py scripts/maimai_trace_diff.py` -> **PASS**；`git diff --check` -> **PASS**。
- 最终全量回归：`python -m pytest tests scripts -q` -> **454 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 本轮执行结论：S2 精确查询平台门禁通过但结果为空；S2b 宽查询成功，搜索 apply 写入 130 新建/9 合并；D2 popup 详情 10/10 成功，详情 apply 写入 10 人；未发生登录/验证码/403/429 熔断。

## D3 详情放大门禁准备（2026-05-13）

> 目标：在 D2 10 人 popup 详情成功后，继续用相同 human-in-the-loop 路径准备 D3 30 人详情任务包。仍不使用 `automation.html` 或 CDP 触发详情；真实详情必须由用户在人才银行页手动打开 popup 加载/启动。

- [x] Task 1：从 `data/output/maimai-ai-infra-shortlist-s2b-2026-05-13.json` 选择 A 档后续 30 人，排除已完成 D2 的 10 人。
- [x] Task 2：生成 `data/output/raw/maimai-ai-infra-detail-targets-d3-s2b-2026-05-13.json`，要求 `total_contacts=30,missing=0`。
- [x] Task 3：启动只读 detail plan server，服务 D3 目标包，验证 `/health` 和 `/detail-plan.json`。
- [x] Task 4：等待用户手动 popup 执行 D3 并提供导出 JSON；取得后再做详情 dry-run。

## D3 Review

- D3 目标包：`data/output/raw/maimai-ai-infra-detail-targets-d3-s2b-2026-05-13.json`，`total_contacts=30,missing=0`。
- 本地只读 detail plan server 已验证：`/health` 返回 `ok=true,totalContacts=30`，`/detail-plan.json` 首个联系人为姜卓；完成 capture 后已停止，`127.0.0.1:8765` 不再监听。
- 用户完成 D3 popup 路径并提供下载文件：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (4).json`；已归档为 `data/output/raw/maimai-ai-infra-detail-capture-d3-s2b-2026-05-13.json`。
- D3 capture 检查：`contacts=30,detailJobs=30,details=30,total_jobs=30,done=30,failed=0,skipped=0,diagnosticTraces=200,circuit_breaker.tripped=false`；30 个 job 状态均为 `done`。
- D3 详情 dry-run：`data/output/maimai-ai-infra-detail-d3-s2b-dry-run-2026-05-13.md` -> 匹配 30、未匹配 0、失败 jobs 0、写入人数 0。
- 当前门禁：D3 dry-run clean，可进入详情 apply 授权门禁；只有用户明确回复 `确认写入 AI Infra 脉脉详情` 后才允许写入详情。
- 用户明确回复 `确认写入 AI Infra 脉脉详情` 并要求使用现有 db 写入工具后，执行 `scripts/maimai_detail_import.py apply`，未手写 SQL 或自定义写库逻辑。
- D3 详情 apply：`data/output/maimai-ai-infra-detail-d3-s2b-apply-2026-05-13.md` 与 `data/output/maimai-ai-infra-detail-d3-s2b-apply-2026-05-13.json` -> 匹配 30、未匹配 0、失败 jobs 0、写入人数 30，工具返回 30 个 `verified_candidate_ids`。
- D3 聚焦验证：`python -m pytest tests/test_maimai_detail_import.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_plan_server.py -q` -> **9 passed**；`python -m py_compile scripts/maimai_detail_import.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py` -> **PASS**。
- D3 收口验证：`git diff --check` -> **PASS**；`python -m pytest tests scripts -q` -> **454 passed, 1 warning**，warning 为既有 `scripts/test_boss.py` event loop deprecation。

# AI Infra Gate S3 准备（2026-05-13）

> 目标：承接 S2b 宽查询成功结果，准备 S3 搜索放大门禁（5 批 x 3 页）。准备阶段只生成本地计划和模板 dry-run，不访问脉脉、不写库、不触发详情；live search 必须等待用户单独明确授权。

- [x] Task 1：基于 `data/output/raw/maimai-ai-infra-search-plan-s2b-selected-2026-05-13.json` 生成 `data/output/raw/maimai-ai-infra-search-plan-s3-selected-2026-05-13.json`，要求 5 批、每批 `max_pages=3`。
- [x] Task 2：运行 S3 模板 dry-run，输出 `data/output/raw/maimai-ai-infra-search-run-s3-template-2026-05-13.json`，确认只 patch `query/search_query` 与分页字段。
- [x] Task 3：等待用户明确回复 `确认执行 S3 live search` 后，才允许执行真实 S3 搜索；执行前再次确认浏览器人才银行页健康，不写库、不触发详情。
- [x] Task 4：修复 live runner 未执行多页的问题，补 TDD 覆盖 `max_pages` 和 continuation `start_page`。
- [x] Task 5：归档首轮 page1 partial raw，生成 pages 2-3 continuation plan，执行 continuation 并合并为完整 S3 raw。
- [x] Task 6：转换完整 S3 contacts payload，运行搜索导入 dry-run；clean 前不写库、不 apply。

## S3 准备 Review

- S3 selected plan：`data/output/raw/maimai-ai-infra-search-plan-s3-selected-2026-05-13.json`，`gate=S3`、`max_batches=5`、`max_pages_per_batch=3`，查询为 `AI Infra|ML Infra|大模型|分布式训练|推理`。
- S3 template dry-run：`data/output/raw/maimai-ai-infra-search-run-s3-template-2026-05-13.json`，状态为 `dry-run-template-only`，5 个 batch 均生成 3 个 patched pages。
- 样本校验：第 1 批第 1/2/3 页分别写入 `paginationParam.page=1/2/3`、`search.page=0/1/2`，`query/search_query=AI Infra`，并保留 `allcompanies=一线互联网公司`。
- 用户明确回复 `确认执行 S3 live search` 后执行 S3 live search。首轮暴露 live runner 只执行每批第 1 页的问题，已归档为 `data/output/raw/maimai-ai-infra-search-run-s3-page1-partial-2026-05-13.json`。
- 修复 `scripts/maimai_ai_infra_search_live_gate.py`：支持按 `max_pages` 多页循环，并支持 `start_page` continuation；新增测试覆盖该行为。
- continuation plan：`data/output/raw/maimai-ai-infra-search-plan-s3-continuation-pages2-3-2026-05-13.json`，只抓第 2-3 页，避免重复请求第 1 页。
- continuation raw：`data/output/raw/maimai-ai-infra-search-run-s3-continuation-pages2-3-2026-05-13.json` -> 5 批、300 contacts、无熔断。
- 完整 S3 raw：`data/output/raw/maimai-ai-infra-search-run-s3-2026-05-13.json` -> 5 批 x 3 页、450 原始 contacts、每批 90 contacts、`status=completed,stopReason=null`。
- 完整 S3 contacts payload：`data/output/raw/maimai-ai-infra-search-run-s3-2026-05-13.contacts.json` -> `total_contacts=450`。
- S3 导入 dry-run：`data/output/talent-import-ai-infra-s3-dry-run-2026-05-13.md` -> 原始 450、去重后 414、新建 256、合并 158、待确认 0、失败 0；未写 `data/talent.db`，未 apply。
- S3 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py -q` -> **18 passed**；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py` -> **PASS**；`git diff --check` -> **PASS**；`python -m pytest tests scripts -q` -> **456 passed, 1 warning**。
- 用户明确回复 `确认导入 AI Infra S3 搜索结果` 并要求调用已有 db 工具后，使用 `scripts/talent_library.py import --apply --confirm "确认导入人才"` 执行 S3 apply；未手写 SQL 或自定义写库逻辑。
- S3 apply 报告：`data/output/talent-import-ai-infra-s3-apply-2026-05-13.md` -> 原始 450、去重后 414、新建 256、合并 158、待确认 0、失败 0。
- S3 写后只读复跑：`data/output/talent-import-ai-infra-s3-post-apply-dry-run-2026-05-13.md` -> 原始 450、去重后 414、新建 0、合并 414、待确认 0、失败 0。
- S3 shortlist：`data/output/maimai-ai-infra-shortlist-s3-2026-05-13.json` 与 `data/output/maimai-ai-infra-shortlist-s3-2026-05-13.md`；分层统计 A=346、B=619、C=916、淘汰=1238。
- S3 apply 收口验证：`python -m pytest tests/test_talent_library_cli.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py -q` -> **27 passed**；`python -m py_compile scripts/talent_library.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py` -> **PASS**；`git diff --check` -> **PASS**；`python -m pytest tests scripts -q` -> **456 passed, 1 warning**。
- 当前门禁：S3 搜索结果已写入；下一步可基于 S3 shortlist 选择新一轮详情目标，仍需 popup 启动和详情 apply 单独授权。

# AI Infra Gate D4 详情准备（2026-05-13）

> 目标：基于 S3 shortlist 选择全部尚未完成 `maimai_detail_capture` 的 A 档候选人。仍不使用 `automation.html` 或 CDP 触发详情；真实详情必须由用户在人才银行页 popup 加载本地任务包并手动启动。

- [x] Task 1：从 `data/output/maimai-ai-infra-shortlist-s3-2026-05-13.json` 选择全部 A 档且尚无 `raw_data.maimai_detail_capture` 的候选人，并保留选择审计文件。
- [x] Task 2：调用现有 `scripts/maimai_detail_targets.py from-ids` 生成 `data/output/raw/maimai-ai-infra-detail-targets-d4-s3-all-a-2026-05-13.json`，要求 `total_contacts=305,missing=0`。
- [x] Task 3：启动只读 detail plan server，服务 D4 all-A 目标包，验证 `/health` 和 `/detail-plan.json`。
- [x] Task 4：等待用户手动 popup 执行 D4 并提供导出 JSON；取得后再做详情 dry-run。
- [x] Task 5：D4 首段因 daily limit 只完成 100/305，归档 partial capture 并运行详情 dry-run。
- [x] Task 6：生成剩余 205 人 continuation 任务包；暂不启动服务，避免 daily limit 后误继续。

## D4 准备 Review

- 用户纠正：30 人数量级已由 D3 验证，不应再次生成 30 人任务包；旧的 `data/output/raw/maimai-ai-infra-detail-targets-d4-s3-2026-05-13.json` 不继续使用。
- 选择审计：`data/output/raw/maimai-ai-infra-detail-target-candidates-d4-s3-all-a-2026-05-13.json`，S3 A 档共 346 人，其中已有 `maimai_detail_capture` 的候选人已排除，最终选择 305 人。
- D4 all-A 任务包：`data/output/raw/maimai-ai-infra-detail-targets-d4-s3-all-a-2026-05-13.json`，`total_contacts=305,missing=0`，首个联系人为周依源。
- 本地只读 detail plan server 已启动：`http://127.0.0.1:8765/detail-plan.json`，`/health` 返回 `ok=true,totalContacts=305`。
- 服务日志：`data/output/raw/maimai-detail-plan-server-d4-s3-all-a-8765.out.log` 与 `data/output/raw/maimai-detail-plan-server-d4-s3-all-a-8765.err.log`。
- 用户提供 D4 导出：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13.json`；已归档为 `data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-2026-05-13.json`。
- D4 capture 检查：`contacts=305,detailJobs=305,details=100,total_jobs=305,done=100,queued=205,failed=0,skipped=0,diagnosticTraces=200`；`circuit_breaker.reason=daily_limit_reached`，未出现失败 job。
- D4 详情 dry-run：`data/output/maimai-ai-infra-detail-d4-s3-all-a-dry-run-2026-05-13.md` -> 匹配 100、未匹配 0、失败 jobs 0、写入人数 0。
- 本地 detail plan server 已停止，`127.0.0.1:8765` 不再监听。
- 剩余 continuation 任务包：`data/output/raw/maimai-ai-infra-detail-targets-d4-s3-all-a-remaining-205-2026-05-13.json`，`total_contacts=205,missing=0`，首个剩余联系人为徐睿。
- 剩余选择审计：`data/output/raw/maimai-ai-infra-detail-target-candidates-d4-s3-all-a-remaining-205-2026-05-13.json`。
- 用户明确回复 `确认写入 AI Infra 脉脉详情` 并要求使用 db 已有工具后，执行 `scripts/maimai_detail_import.py apply`，未手写 SQL 或自定义写库逻辑。
- D4 首段 apply：`data/output/maimai-ai-infra-detail-d4-s3-all-a-apply-2026-05-13.md` 与 `data/output/maimai-ai-infra-detail-d4-s3-all-a-apply-2026-05-13.json` -> 匹配 100、未匹配 0、失败 jobs 0、写入人数 100，工具返回 100 个 `verified_candidate_ids`。
- D4 写后只读复跑：`data/output/maimai-ai-infra-detail-d4-s3-all-a-post-apply-dry-run-2026-05-13.md` -> 匹配 100、未匹配 0、失败 jobs 0。
- 当前门禁：D4 首段 100 人已写入；剩余 205 人应等 daily limit 恢复后再用 continuation 包继续 popup，详情 apply 仍需单独授权。

# AI Infra Gate D4 剩余 205 人详情任务包（2026-05-13）

> 目标：将 popup 详情每日上限默认值临时放宽到 10000，由用户人工把握节奏；复用已生成的剩余 205 人 continuation 包并启动只读 detail plan server。本轮不写 DB。

- [x] Task 1：复核剩余任务包 `data/output/raw/maimai-ai-infra-detail-targets-d4-s3-all-a-remaining-205-2026-05-13.json`，要求 `totalContacts=205`、`contacts=205`、`missing=0`、首位联系人为徐睿。
- [x] Task 2：将扩展详情每日限额默认值统一调整为 10000，并补充静态契约测试。
- [x] Task 3：运行聚焦测试、JS 语法检查和 `git diff --check`。
- [x] Task 4：启动 `detail plan server` 服务剩余 205 人任务包，并验证 `/health` 与 `/detail-plan.json`。
- [x] Task 5：记录执行结果并通知用户手动 reload 扩展、通过 popup 执行详情。

## D4 剩余 205 人 Review

- 限额调整：`SAFE_POLICY.dailyLimit`、popup 默认值、popup fallback、automation fallback 均改为 `10000`；popup 输入框 `max=10000`，避免 UI 阻止用户输入。
- 聚焦验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q` -> **39 passed**。
- 全量回归：`python -m pytest tests scripts -q` -> **457 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- JS 语法检查：`node --check extensions/maimai-scraper/detail_batch.js extensions/maimai-scraper/popup.js extensions/maimai-scraper/automation.js` -> **PASS**。
- 差异空白检查：`git diff --check` -> **PASS**。
- 本地 detail plan server 已启动：`http://127.0.0.1:8765/detail-plan.json`，进程 ID `34764`。
- `/health` 验证：`ok=true,totalContacts=205`。
- `/detail-plan.json` 验证：`totalContacts=205`、`contacts=205`、首位联系人为徐睿（`229042988`）。
- 服务日志：`data/output/raw/maimai-detail-plan-server-d4-s3-all-a-remaining-205-8765.out.log` 与 `data/output/raw/maimai-detail-plan-server-d4-s3-all-a-remaining-205-8765.err.log`。
- 本轮未写入 `data/talent.db`；后续详情 apply 仍需用户明确授权，并且只使用 `scripts/maimai_detail_import.py`。

# maimai-scraper 批间休息到期不续跑修复（2026-05-13）

> 现象：D4 剩余 205 人详情执行到 30/205 后进入批间休息；日志显示休息 8 分钟，之后 popup 倒计时显示约 0 秒但没有继续。

- [x] Task 1：定位根因：MV3 background service worker 可能在 5-10 分钟长 `setTimeout` 期间被浏览器挂起，导致内存中的 `DetailBatch.run()` 等待链丢失。
- [x] Task 2：补失败契约测试 `test_background_recovers_expired_batch_pause_from_persisted_jobs`，要求 background 能从持久化 jobs/state 恢复过期批间休息。
- [x] Task 3：实现 `recoverExpiredBatchPauseIfNeeded()` 和 `runDetailBatchJobs()`，在 `getDetailBatchStatus/getScraperSummary` 中检测过期 `batch_pause_until` 并用同一 run token 续跑，不清空已完成 jobs/details。
- [x] Task 4：持久化 `detailBatchTabId`，优先用原 tab 续跑；若缺失或失效，则只回退到当前已激活的人才银行 tab，不自动导航/刷新。
- [x] Task 5：运行聚焦测试与语法检查。

## 批间休息修复 Review

- 红测：`python -m pytest tests/test_maimai_scraper_extension.py::test_background_recovers_expired_batch_pause_from_persisted_jobs -q` 先失败，确认旧代码缺少恢复路径。
- 修复：新增从 `DetailDB.getAllJobs()` 与 `detailBatchState` 恢复过期批间休息的路径；`running` 状态 job 会转回 `queued` 后续跑。
- 聚焦验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q` -> **40 passed**。
- 全量回归：`python -m pytest tests scripts -q` -> **458 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- JS 语法检查：`node --check extensions/maimai-scraper/background.js/detail_batch.js/popup.js/content.js` -> **PASS**。
- 差异空白检查：`git diff --check` -> **PASS**。
- 操作提示：修复需要用户重载扩展后，在人才银行页重新打开 popup；若原 30/205 状态仍在 IndexedDB/storage 中，状态刷新会触发“批间休息到点，自动继续”。

# maimai-scraper 批间休息进度回退显示修复（2026-05-13）

> 现象：执行日志刚显示 `详情抓取成功 ... 进度 120/205`，下一条批间暂停却显示 `已完成 60/205`。

- [x] Task 1：定位根因：恢复续跑后，`batch_pause_completed` 使用的是当前 `DetailBatch.run()` 调用内的 `processed` 计数，而不是 `state.counts` 中的累计完成数。
- [x] Task 2：补红测 `test_batch_pause_progress_uses_cumulative_completed_count_after_resume`。
- [x] Task 3：修复 `detail_batch.js`，批间暂停写入累计完成数。
- [x] Task 4：修复 `background.js`、`popup.js`、`content.js`，显示时取 `batch_pause_completed` 和真实 counts 的较大值，兼容已持久化的旧错误状态。
- [x] Task 5：运行聚焦测试、JS 语法检查、全量回归和 `git diff --check`。

## 批间休息进度回退 Review

- 红测：`python -m pytest tests/test_maimai_scraper_extension.py::test_batch_pause_progress_uses_cumulative_completed_count_after_resume -q` 先失败，修复后通过。
- 聚焦验证：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_detail_plan_server.py -q` -> **41 passed**。
- 全量回归：`python -m pytest tests scripts -q` -> **459 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- JS 语法检查：`node --check extensions/maimai-scraper/background.js extensions/maimai-scraper/detail_batch.js extensions/maimai-scraper/popup.js extensions/maimai-scraper/content.js` -> **PASS**。
- 差异空白检查：`git diff --check` -> **PASS**。
- 当前判断：截图中的 `60/205` 是批间暂停显示字段回退，不代表已抓取的 120 条详情丢失；导出 JSON 后应以 `detailJobs/details` 实际数量为准。

# AI Infra D4 剩余 205 人详情 Dry-Run（2026-05-13）

> 目标：归档用户导出的剩余 205 人详情 capture，并用现有 `scripts/maimai_detail_import.py dry-run` 检查；本轮不写 DB。

- [x] Task 1：检查用户提供路径 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13.json`。
- [x] Task 2：发现该路径与早先 D4 首段 `100/305` capture 哈希相同，不是本轮新导出；改用 Downloads 最新文件 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (1).json`。
- [x] Task 3：归档到 `data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-remaining-205-2026-05-13.json`。
- [x] Task 4：检查 capture 结构：`contacts=205`、`detailJobs=205`、`details=205`、job 状态 `done=205`、最后日志 `批量详情已完成`。
- [x] Task 5：调用现有详情导入工具 dry-run：`python scripts/maimai_detail_import.py dry-run --capture-file data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-remaining-205-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-dry-run-2026-05-13.md`。
- [x] Task 6：停止本地 detail plan server，避免误加载旧任务包。

## D4 剩余 205 Dry-Run Review

- 用户提供的无后缀下载文件是旧 capture：`contacts=305`、`detailJobs=305`、`details=100`，与 `data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-2026-05-13.json` SHA256 相同。
- 实际采用最新下载文件：`C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (1).json`，`ExportTime=2026-05-13T11:43:45.068Z`。
- 归档 capture：`data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-remaining-205-2026-05-13.json`。
- capture 统计：`contacts=205`、`totalContacts=205`、`detailJobs=205`、`details=205`、`metadata.total_jobs=205`、`metadata.captured_details=205`、job 状态 `done=205`。
- dry-run 报告：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-dry-run-2026-05-13.md`。
- dry-run 结果：匹配 205、未匹配 0、失败 jobs 0、写入人数 0。
- 本轮未写入 `data/talent.db`；只有用户明确回复 `确认写入 AI Infra 脉脉详情` 后，才允许调用 `scripts/maimai_detail_import.py apply`。
- 本地 detail plan server 已停止，`127.0.0.1:8765` 不再监听。

# AI Infra D4 剩余 205 人详情 Apply（2026-05-13）

> 目标：在用户明确授权“确认写入 AI Infra 脉脉详情，使用已有db工具”后，用现有 `scripts/maimai_detail_import.py apply` 写入剩余 205 人详情。

- [x] Task 1：复核 dry-run clean：匹配 205、未匹配 0、失败 jobs 0。
- [x] Task 2：调用现有 DB 工具 apply，不手写 SQL：`python scripts/maimai_detail_import.py apply --capture-file data/output/raw/maimai-ai-infra-detail-capture-d4-s3-all-a-remaining-205-2026-05-13.json --db data/talent.db --out data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.md --json-out data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.json --confirm "确认写入脉脉详情"`。
- [x] Task 3：运行写后只读 dry-run。
- [x] Task 4：运行详情导入相关聚焦测试与 Python 语法检查。
- [x] Task 5：更新执行记录。

## D4 剩余 205 Apply Review

- apply 报告：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.md`。
- apply JSON：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-apply-2026-05-13.json`。
- apply 结果：匹配 205、未匹配 0、失败 jobs 0、写入人数 205、`verified_candidate_ids=205`。
- 写后只读 dry-run：`data/output/maimai-ai-infra-detail-d4-s3-all-a-remaining-205-post-apply-dry-run-2026-05-13.md` -> 匹配 205、未匹配 0、失败 jobs 0。
- 聚焦测试：`python -m pytest tests/test_maimai_detail_import.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_plan_server.py -q` -> **9 passed**。
- Python 语法检查：`python -m py_compile scripts/maimai_detail_import.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py` -> **PASS**。
- 差异空白检查：`git diff --check` -> **PASS**。
- 本轮写入严格使用现有 `scripts/maimai_detail_import.py apply` DB 工具，未手写 SQL 或自定义写库逻辑。
