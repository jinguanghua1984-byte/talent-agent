# 浏览器扩展工作台 V2.0 实施计划（2026-05-18）

> 目标：在已通过的 V2.0 设计基础上，写出可执行实施计划；本阶段不改扩展业务代码。

## 计划

- [x] 使用 `superpowers:writing-plans` 读取设计文档和现有扩展结构。
- [x] 写入实施计划到 `docs/superpowers/plans/2026-05-18-maimai-scraper-workbench-v2.md`。
- [x] 自检实施计划覆盖 spec、无占位项、路径和消息名一致。
- [x] 回填 Review，等待用户选择执行方式。

## Review

- 实施计划已写入 `docs/superpowers/plans/2026-05-18-maimai-scraper-workbench-v2.md`。
- 计划覆盖测试护栏、background 状态层、workbench UI、popup 启动器、side panel fallback 和最终验证。
- 自检结果：spec 覆盖、占位项扫描、消息名一致性、请求执行不变量均已检查。
- 实施完成：新增 `workbench.html/js/css` 常驻工作台；`background.js` 增加 workbench snapshot、pager logs、export 状态和 opener；`popup.html/css/js` 收缩为 launcher；`manifest.json` 启用 `sidePanel` 并指向 `workbench.html`。
- 请求边界：`content.js -> inject.js` 的 MAIN world 列表/详情请求链路保持不变；`popup.js` 与 `workbench.js` 不直接 `fetch` 脉脉业务接口。
- Review gate：Task 1-6 均完成实现、spec review 和 code quality review；已修复 review 中发现的旧 popup 合同残留、workbench runtime push listener、action 错误显示、storage live update、按钮重复启动、详情状态 live update 和 side panel 布局问题。
- 最终验证：扩展 JS 语法检查 `background/content/inject/autopager/detail_batch/popup/workbench` 全部 PASS；`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q` -> `50 passed`；`python -m pytest tests/test_talent_library_cli.py::test_import_entry_accepts_extension_capture_and_pager_export_shapes tests/test_maimai_trace_diff.py -q` -> `4 passed`；`python -m pytest tests scripts -q` -> `643 passed, 1 warning`；`git diff --check` -> PASS。
- 残留说明：全量回归 warning 为既有 `scripts/test_boss.py` event loop deprecation，与本次 maimai-scraper workbench 改造无关。

# 浏览器扩展 Popup/常驻工作台 V2.0 设计验证（2026-05-18）

> 目标：先验证现有列表查询和详情请求链路的技术契约，再设计一个不依赖短生命周期 popup 的 V2.0 工作台方案。当前阶段只做验证与设计，不实现。

## 计划

- [x] 读取扩展现状、历史 lessons 和安全边界。
- [x] 验证人选列表逐页查询链路：background -> content -> MAIN world `__MAIMAI_PAGER_FETCH__`。
- [x] 验证人选详情链路：background -> content -> MAIN world `__MAIMAI_DETAIL_FETCH__`。
- [x] 验证 V2.0 状态持久化和常驻 UI 不会改变上述请求发起位置。
- [x] 输出 V2.0 设计草案，等待确认后再写正式 spec。

## Review

- 现有列表链路：`popup.js startPager` -> `background.js startPager/getFullTemplate/pagerFetch` -> `content.js __MAIMAI_PAGER_FETCH__` -> `inject.js origFetch.call(window, tpl.url, ...)`；真实分页请求仍在页面 MAIN world。
- 现有详情链路：`popup.js startDetailBatch` -> `background.js sendDetailFetch` -> `content.js __MAIMAI_DETAIL_FETCH__` -> `inject.js fetchDetailEndpoint(...)`；详情接口仍由页面 MAIN world 发起。
- 本地契约检查：10 个关键 message/fetch marker 全部存在。
- 语法检查：`node --check` 覆盖 `background.js`、`content.js`、`inject.js`、`autopager.js`、`detail_batch.js`、`popup.js`，全部通过。
- 扩展契约测试：`python -m pytest tests/test_maimai_scraper_extension.py tests/test_maimai_trace_diff.py -q` -> `42 passed`。
- 本地浏览器版本：Chrome `148.0.7778.168`，Edge `148.0.3967.70`；满足 Chrome side panel API 的 Chrome 114+ / MV3+ 要求。
- 未执行真实脉脉搜索、详情请求、导航、刷新或 CDP 操作；本次验证只证明 V2.0 可在不移动真实请求执行点的前提下改造 UI 与状态层。
- 正式设计文档：`docs/superpowers/specs/2026-05-18-maimai-scraper-workbench-v2-design.md`。
- Spec 自检：占位词扫描无命中；请求执行不变量、side panel fallback、状态恢复、测试计划和验收标准已覆盖；`git diff --check` 通过。

# AI Infra 冷启动寻访 V2 计划重制（2026-05-14）

> 目标：基于初版人工搜索计划、Phase 0 技术边界、5/13 半自动闭环和 5/14 搜索 API 校准结果，重新制定一份不依赖既有人才库数据的 V2 实施计划。

## 执行清单

- [x] 复读 `docs/design-discussions/2026-05-12-maimai-ai-infra-talent-search-plan.md`，抽取原始业务目标、搜索原则、公司/职位/关键词结构。
- [x] 复读 `docs/superpowers/plans/2026-05-13-maimai-ai-infra-feasible-execution.md` 与 Phase 0 复盘，确认搜索、详情和写库的人机边界。
- [x] 复读 `docs/superpowers/plans/2026-05-14-maimai-search-api-calibration.md` 与搜索 API 说明书，确认可写筛选字段和禁用字段。
- [x] 新增 V2 冷启动实施计划文档，重点覆盖列表抓取、粗筛评分、初版报告、人工审核、详情任务包和最终寻访报告。
- [x] 校验 V2 文档无占位符、关键文件路径正确，并写入 Review。

## Review

- 新增文档：`docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md`。
- 计划定位：冷启动 campaign，不复用既有 `data/talent.db` 候选人；列表抓取为主，详情只补人工审核圈定范围。
- 搜索字段：只使用 2026-05-14 已确认字段；年龄范围使用 `min_age/max_age`，不写 `search.age` 或 `age_min/age_max`。
- 安全边界：搜索按门禁小步放大；详情补全继续使用 popup 本地任务包路径，不使用 `automation.html` 或 CDP 触发真实详情。
- 文档校验：占位词扫描无命中；关键章节扫描通过；`git diff --check` 通过。

## 规模和长时执行调整

- [x] 将搜索目标指标按 10 倍放大：原始列表 15,000-30,000、去重 8,000-18,000、列表 A+B 2,000-4,000、最终强推荐/推荐 200-500。
- [x] 将搜索执行拆成 campaign、wave、search unit、page task 四层，明确每层粒度和持久化文件。
- [x] 增加长时任务中断恢复机制：页级 raw 原子写入、`search-progress.json`、`search-events.jsonl`、`import-ledger.jsonl`、`--resume` 和 runtime 切片参数。
- [x] 调整详情审核和补全规模：总详情目标 600-1,200，拆成 5-10 个详情 wave，详情成功 500-1,000 后支撑 200-500 人最终推荐。
- [x] 补充详情 wave 恢复规则：capture 已归档不重抓、dry-run clean 后等待 apply、apply ledger 防重复写入。

## 下一步：V2 工程实施计划

- [x] 使用 `superpowers:writing-plans` 将 V2 设计转成工程实施计划。
- [x] 新增计划文档 `docs/superpowers/plans/2026-05-14-maimai-ai-infra-v2-cold-start-campaign.md`。
- [x] 计划拆分为 campaign helper、V2 strategy/search units、runner resume、wave import ledger、list/detailed scoring、human review、detail wave 和最终验证。
- [x] 自检计划文档无占位词、关键路径正确，并汇报执行选项。

## Subagent 执行进度

- [x] Task 1：Campaign helper 和数据安全边界，提交 `6a48ca6` + review fix `84bcdb9`，spec review 通过，code quality review 通过。
- [x] Task 2：原子 page raw、事件日志和 resume 状态重建，提交 `8ebe867` + review fix `72cf168` + re-review fix `e382c00`，spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_campaign.py -q` -> `16 passed`，`python -m py_compile scripts/maimai_ai_infra_campaign.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 3：V2 策略配置和 Search Unit 编译，提交 `a259f66` + spec fix `fbcd1b2` + quality fix `388bf82`，spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_strategy.py -q` -> `11 passed`，`python -m py_compile scripts/maimai_ai_infra_search_plan.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 4：Runner page task、resume 和 runtime 切片，提交 `a3d6ac1` + quality fix `24ea8b4` + re-review fix `585802a`，spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_runner.py -q` -> `22 passed`，`python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_runner.py -q` -> `38 passed`，`python -m py_compile scripts/maimai_ai_infra_search_runner.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 5：Wave contacts、import ledger 和 campaign pipeline，提交 `feac3ea` + spec fix `2057987` + quality fix `0475855`，spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_pipeline.py -q` -> `12 passed`，`python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_pipeline.py -q` -> `28 passed`，`python -m py_compile scripts/maimai_ai_infra_campaign.py scripts/maimai_ai_infra_pipeline.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 6：List/Detailed scoring modes and reports，提交 `ef38dc6` + `4a43848` + `086705a` + `1d33d97` + `c70bd98` + `870b435` + `ed72ec1` + `cd09253` + `224b992` + `1c1f663` + `de29229`；spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_pipeline.py -q` -> `39 passed`，`python -m py_compile scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 7：Human review input and detail wave targets，提交 `371c195` + quality fix `ff96e4c`；spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q` -> `11 passed`，`python -m pytest tests/test_maimai_ai_infra_pipeline.py -q` -> `14 passed`，`python -m py_compile scripts/maimai_ai_infra_review.py scripts/maimai_detail_targets.py` -> PASS，`git diff --check` -> PASS。
- [x] Task 8：Detail wave progress and duplicate apply guard，提交 `312ac34` + quality fix `98f3203` + re-review fix `76e9d4d`；spec review 通过，code quality review 通过；验证 `python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_detail_import.py -q` -> `28 passed`，`python -m py_compile scripts/maimai_ai_infra_pipeline.py scripts/maimai_detail_import.py` -> PASS，`git diff --check` -> PASS；复查方全量验证 `python -m pytest tests scripts -q` -> `591 passed, 1 warning`。
- [x] Task 9：Documentation, verification, and final review；已更新 V2 设计文档的 Implemented CLI Map，并完成聚焦、相关和全量回归。

## Task 9 Documentation, Verification, and Final Review

- [x] 确认当前断点：Task 1-8 已完成，剩余工作为 V2 设计文档 CLI 映射、聚焦验证、相关回归、全量回归和 Review 回填。
- [x] 在 `docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md` 增加“已实现 CLI 映射”，覆盖 `search_plan --out-units`、`search_runner --campaign-root --resume`、`pipeline run-campaign`、`detail_targets from-review`、`pipeline detail-wave dry-run/apply`。
- [x] 运行聚焦验证：`python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q` -> `97 passed`。
- [x] 运行相关回归：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_detail_import.py tests/test_maimai_detail_plan_server.py -q` -> `13 passed`；`python -m py_compile scripts/maimai_ai_infra_campaign.py scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_review.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_import.py` -> PASS；`git diff --check` -> PASS。
- [x] 运行全量回归：`python -m pytest tests scripts -q` -> `591 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- [x] 回填 Task 9 Review，标记最终验证状态。

### Task 9 Review

- 文档同步：`docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md` 已新增“已实现 CLI 映射”，覆盖搜索计划、runner dry-run/resume、campaign wave 导入、人工审核转详情任务包、详情 wave dry-run/apply。
- CLI 复核：只读复核确认文档映射与当前代码一致；`search_runner --campaign-root --resume` 实际需要配合 `--dry-run-template-only --units`，文档已写明。
- 聚焦验证：`python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_review.py tests/test_maimai_detail_targets.py -q` -> `97 passed`。
- 相关回归：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_detail_import.py tests/test_maimai_detail_plan_server.py -q` -> `13 passed`。
- 语法检查：`python -m py_compile scripts/maimai_ai_infra_campaign.py scripts/maimai_ai_infra_search_plan.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_review.py scripts/maimai_detail_targets.py scripts/maimai_detail_plan_server.py scripts/maimai_detail_import.py` -> PASS。
- 差异检查：`git diff --check` -> PASS。
- 全量回归：`python -m pytest tests scripts -q` -> `591 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。

## 筛选条件更新

- [x] 更新 V2 设计文档：毕业院校硬门槛改为 985/211/QS Top500/海外 Top500，专科和非重点不看。
- [x] 更新 V2 设计文档：年龄默认搜索 `24-40`，`24-35` 最佳，`35-40` 第二梯队，`40+` 淘汰。
- [x] 更新工程实施计划：V2 config 增加 `min_age=24/max_age=40`、`school_gate` 和 `age_bands`。
- [x] 更新工程实施计划：list/detailed scoring 任务增加院校硬筛、年龄分层、`40+` 淘汰测试要求。

# AI Infra V2 Campaign Dry-Run（2026-05-15）

> 目标：只执行离线 campaign dry-run，生成搜索计划、Search Units 和 page task 请求体 raw；不触发真实脉脉搜索，不写 DB。

## 计划

- [x] 复核工作树和入口参数，确认 `data/campaigns/` 已被 `.gitignore` 忽略。
- [x] 创建 campaign root：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/`。
- [x] 生成 `search-plan.json` 和 `search-units.jsonl`。
- [x] 执行 runner `--dry-run-template-only --campaign-root --units --resume`，限制首轮 dry-run 范围，验证请求体 patch、raw 落盘和 resume 行为。
- [x] 检查 dry-run 产物统计：`search-units.jsonl` 共 450 个 unit；`wave-001` 本轮 dry-run 已落盘 13 个 page raw，其中 1 页来自 CLI import 路径诊断，12 页来自修复后的正式 direct-script dry-run；样本请求体不含禁用字段 `age`，包含 `min_age=24/max_age=40`。
- [x] 运行必要聚焦测试和 `git diff --check`：`python -m pytest tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py -q` -> `58 passed`；`python -m py_compile scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py` -> PASS；`git diff --check` -> PASS。
- [x] 运行全量回归：`python -m pytest tests scripts -q` -> `592 passed, 1 warning`；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- [x] 写入 Review。

## Review

- 生成 campaign root：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/`；该目录被 `.gitignore` 忽略，未进入待提交文件。
- 生成计划产物：`search-plan.json` 和 `search-units.jsonl`；Search Units 共 450 个，`wave-001` 覆盖 40 个 unit。
- dry-run 产物：`raw/search/` 已落盘 13 个 page raw；`reports/search-runner-dry-run-wave-001-summary.json` 记录正式 dry-run 写入 12 页，`tasks_pending=119`，`units_seen=40`。
- 字段检查：样本请求体 `status=dry-run-template-only`，`query_relation=1`，`min_age=24`，`max_age=40`，不含禁用字段 `age`。
- 中途修复：直接运行 `python scripts/maimai_ai_infra_search_runner.py ...` 初次报 `ModuleNotFoundError: scripts.maimai_ai_infra_campaign`；已按 TDD 补子进程红测并给 runner 增加直接脚本入口路径保护，同类 `pipeline` 和 `detail_targets` 已有保护，无需改动。
- 错误沉淀：已按项目规则追加 `memory/error-log.md` 一行，记录 direct-script import path 问题。
- 验证：runner 直接入口红测修复后通过；受影响模块回归 `58 passed`；全量回归 `592 passed, 1 warning`；`git diff --check` PASS。

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

# 脉脉搜索 API 说明书前置校准（2026-05-14）

> 目标：承接 `docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` 的搜索字段语义缺口。先由用户在人才银行页手动切换条件并搜索，扩展只被动捕获请求；本地生成搜索 API 说明书和请求头生成规则，经用户确认后再改 runner。
> 计划文档：`docs/superpowers/plans/2026-05-14-maimai-search-api-calibration.md`

- [x] Task 1：复核昨天进度：S3 搜索已执行并 apply，D4 全部 A 档详情已通过 popup 路径 dry-run/apply；当前断点是搜索字段和请求头规格未沉淀。
- [x] Task 2：复核安全边界：不自动导航、不刷新、不打开 automation 页面、不通过 CDP 触发真实详情；搜索校准必须走用户手动操作 + 扩展被动捕获。
- [x] Task 3：写前置校准计划，明确输出 `maimai-search-api-spec-YYYY-MM-DD.json/md`。
- [x] Task 4：TDD 新增离线搜索 API 规格生成器 `scripts/maimai_search_api_spec.py`。
- [x] Task 5：运行聚焦测试、py_compile 和 `git diff --check`。
- [x] Task 6：等待用户手动执行多组搜索并提供导出 JSON 后，生成正式说明书。

## 当前进度定位

- 已完成：`docs/superpowers/plans/2026-05-13-maimai-ai-infra-feasible-execution.md` 中 Task 1-9、S3 搜索、D4 剩余 205 人详情 apply。
- 已验证：搜索 runner/live gate 只能安全主动 patch `query/search_query` 与分页；`allcompanies/degrees/query_relation/positions/worktimes/age` 尚未通过多条件 diff 确认。
- 今天前置动作：先补离线说明书生成工具，不碰浏览器、不写 DB、不跑真实搜索。

## Review

- 红测：`python -m pytest tests/test_maimai_search_api_spec.py -q` 初次失败，原因是 `scripts.maimai_search_api_spec` 尚不存在。
- 追加红测：发现 `newSearchRecords` 与 `latestSearchRecords` 中同一搜索请求会重复计数，补 `test_build_search_api_spec_dedupes_same_record_across_capture_sections`，初次失败为 `samples.count=2`。
- 修复：新增 `scripts/maimai_search_api_spec.py`，从扩展导出 capture 中筛选 `POST /api/ent/v3/search/basic`，生成 endpoint、headers、body policy、字段观测、样本摘要和 Markdown 说明书；按 `id/ts/url/body` 稳定 key 去重。
- 草案输出：使用昨天 UI/request diff 生成 `data/output/maimai-search-api-spec-2026-05-14.json` 与 `data/output/maimai-search-api-spec-2026-05-14.md`；当前只有 1 个去重样本，说明书明确标注仅自动生成 `query/search_query` 与分页，其他字段只保留模板值。
- 人工校准输入：用户提供 `C:\Users\Administrator\Downloads\maimai-capture-2026-05-14 (1).json`，已归档为 `data/output/raw/maimai-search-api-calibration-2026-05-14.json`。
- 正式说明书输出：重新生成 `data/output/maimai-search-api-spec-2026-05-14.json` 与 `data/output/maimai-search-api-spec-2026-05-14.md`；本次提取到 24 条去重搜索样本，共同请求头为 `x-csrf-token`。
- 待确认字段：`allcompanies`、`degrees`、`query_relation`、`positions`、`worktimes`、`age`、`schools`、`major`；字段确认前不更新 runner。
- 本轮验收：`python -m pytest tests/test_maimai_search_api_spec.py -q` -> **3 passed**；`python -m py_compile scripts/maimai_search_api_spec.py` -> **PASS**；`git diff --check` -> **PASS**。
- 用户确认：`search.query_relation` 中 `0=AND`、`1=OR`，已写入规格 `field_catalog.semantics`，不再列入待确认字段。
- 说明书增强：新增 `field_catalog` 和 Markdown「字段优先级」章节，保留全量 `field_observations`，并把字段分为关键字段、优先确认筛选字段、次级筛选字段、模板保留字段和其他已观测字段。
- 增量验收：`python -m pytest tests/test_maimai_search_api_spec.py -q` -> **5 passed**；`python -m py_compile scripts/maimai_search_api_spec.py` -> **PASS**。
- 优先筛选字段确认：`allcompanies` 为公司/公司集合筛选，正任职/曾任职默认全选不区分，逗号为 OR；`positions` 为候选人职位关键词，逗号为 OR；`worktimes` 忽略快捷档位，优先使用 `worktimes_min/worktimes_max` 表示具体工作年数；`schools` 为学校名 OR；`major` 为专业名 OR。
- 待后续确认：`degrees` 暂待用户专门上传样本；`age` 暂未确认。
- 字段语义写入验证：`python -m pytest tests/test_maimai_search_api_spec.py -q` -> **5 passed**；`python -m py_compile scripts/maimai_search_api_spec.py` -> **PASS**；`git diff --check` -> **PASS**。
- 聚焦验证：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py -q` -> **17 passed**。
- 语法检查：`python -m py_compile scripts/maimai_search_api_spec.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py` -> **PASS**。
- 全量回归：`python -m pytest tests scripts -q` -> **503 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异空白检查：`git diff --check` -> **PASS**。
- Task 3 续做红测：`test_patch_search_body_applies_explicit_confirmed_filters_only` 与 `test_patch_search_body_rejects_unconfirmed_filter_fields` 初次失败，确认 runner 尚未支持显式确认字段写入，也未拒绝未确认 `age`。
- Task 3 修复：`scripts/maimai_ai_infra_search_runner.py` 新增确认字段白名单与 `search_filters` 归一化；只允许 `allcompanies/degrees/degrees_min/degrees_max/only_bachelor_degree/min_only_bachelor_degree/max_only_bachelor_degree/positions/worktimes/worktimes_min/worktimes_max/schools/major/query_relation`，未知或未确认字段报错。
- live gate 同步：`scripts/maimai_ai_infra_search_live_gate.py` 复用同一白名单，页面内 fetch 只把显式确认字段写入模板已有字段；不新增导航、刷新、DB 写入或真实搜索触发。
- 计划元数据同步：`scripts/maimai_ai_infra_search_plan.py` 在 `search_body_patch` 中标出 `confirmed_filter_fields`，`age` 继续保留在 `local_filter_only`。
- Task 3 聚焦验证：`python -m pytest tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py -q` -> **17 passed**。
- 校准相关回归：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_strategy.py -q` -> **27 passed**。
- 语法检查：`python -m py_compile scripts/maimai_search_api_spec.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_plan.py` -> **PASS**。
- 全量回归：`python -m pytest tests scripts -q` -> **509 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 差异空白检查：`git diff --check` -> **PASS**。
- 用户校正：年龄范围参数确认为 `min_age/max_age`，例如 `min_age=16`、`max_age=40` 表示 16-40 岁；不实现 `age_min/age_max` 别名，`age` 本身仍不可写。
- 年龄范围 TDD：新增规格语义、runner patch、live gate expression 和 search plan 元数据红测；初次均失败，确认缺少 `min_age/max_age` 链路。
- 年龄范围修复：`scripts/maimai_search_api_spec.py` 写入 `search.min_age/search.max_age` 语义；runner/live gate 白名单允许 `min_age/max_age`；`search_body_patch.confirmed_filter_fields` 同步新增两字段。
- 重新生成说明书：`data/output/maimai-search-api-spec-2026-05-14.json` 与 `data/output/maimai-search-api-spec-2026-05-14.md` 已包含 `min_age/max_age` 和 16-40 岁示例。
- 年龄范围聚焦验证：`python -m pytest tests/test_maimai_search_api_spec.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_strategy.py -q` -> **27 passed**。
- 年龄范围语法检查：`python -m py_compile scripts/maimai_search_api_spec.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_plan.py` -> **PASS**。
- 年龄范围全量回归：`python -m pytest tests scripts -q` -> **509 passed, 1 warning**；warning 为既有 `scripts/test_boss.py` event loop deprecation。
- 年龄范围差异空白检查：`git diff --check` -> **PASS**。

# AI Infra 最终报告与 DB 盘点（2026-05-14）

> 目标：在不触发真实脉脉搜索、不写 DB 的前提下，复查 2026-05-12 自动搜索方案的实际落点，生成当前 DB 覆盖盘点和最终状态报告，帮助决定是否进入 S4 calibrated search 或先做人工审查。

## 执行清单

- [x] 复查 5/12 方案、5/13 执行记录和 5/14 字段校准结果。
- [x] 只读查询 `data/talent.db`，统计脉脉候选、详情覆盖、A/B/C 分层和 Top B 缺详情数量。
- [x] 生成 `data/output/maimai-ai-infra-db-audit-2026-05-14.json/md`。
- [x] 生成 `data/output/maimai-ai-infra-final-status-2026-05-14.md`。
- [x] 运行聚焦验证和 `git diff --check`。
- [x] 写入 Review，明确下一步建议。

## Review

- 5/12 方案状态：原“完全无人执行详情补全”目标已被 5/13 复审降级；搜索 dry-run/本地导入/评分/shortlist 保留，详情补全实际采用 `本地任务包服务 + 用户在人才银行页 popup 手动启动 + 导出 + dry-run/apply`。
- 搜索与写入进度：S2 精确查询通过但结果为空；S2b 搜索 apply 新建 130、合并 9；S3 搜索 apply 新建 256、合并 158。
- 详情进度：D2 10、D3 30、D4 首段 100、D4 剩余 205 均已 dry-run clean 后 apply，合计 345 人次详情写入；未手写 SQL。
- 字段校准进度：5/14 已确认 `query_relation`、`allcompanies`、`degrees`、`positions`、`worktimes_min/max`、`schools`、`major`、`min_age/max_age`；runner/live gate 已支持显式 `search_filters` 白名单。
- 当前 DB 盘点：脉脉候选人 3119，source_profiles 3119，有详情候选人 3119，`data_level` 为 `detailed=3118/core=1`。
- 当前重新评分：A=341、B=624、C=916、淘汰=1238；A 档详情覆盖 341/341，B 档 Top 50 缺详情 0。
- 生成产物：`data/output/maimai-ai-infra-db-audit-2026-05-14.json`、`data/output/maimai-ai-infra-db-audit-2026-05-14.md`、`data/output/maimai-ai-infra-shortlist-current-2026-05-14.json`、`data/output/maimai-ai-infra-shortlist-current-2026-05-14.md`、`data/output/maimai-ai-infra-final-status-2026-05-14.md`。
- 聚焦验证：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_maimai_ai_infra_pipeline.py -q` -> **9 passed**。
- 语法检查：`python -m py_compile scripts/maimai_ai_infra_rank.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_search_plan.py` -> **PASS**。
- 差异空白检查：`git diff --check` -> **PASS**。
- 下一步建议：先人工审查 `maimai-ai-infra-db-audit-2026-05-14.md` 的 A 档 Top 50 和 B 档 Top 50；若 A 档质量足够，进入人工外联/深审名单整理；若质量不足，再设计 S4 calibrated search，真实搜索仍需单独授权。

# AI Infra V2 S4a 小样本列表搜索（2026-05-15）

> 目标：在用户明确授权“确认执行 AI Infra V2 列表搜索”后，只执行 S4a 小样本真实列表搜索。范围限定为 3 个 batch、每个 batch 1 页；不写 DB、不抓详情、不 apply。

## 执行计划

- [x] 确认授权与边界：只跑 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-s4a-plan.json` 中的 3 个 batch。
- [x] 执行 live gate：通过已登录 CDP 页面模板请求 `/api/ent/v3/search/basic`，延迟 8 秒，超时 30 秒。
- [x] 检查输出 JSON：核对 `status`、`stopReason`、每页 HTTP 状态、解析错误、列表长度、页面健康状态和 contacts 数量。
- [x] 写入 Review：记录 raw 证据路径、是否熔断、是否需要人工处理；本轮不导入 DB。

## Review

- 执行命令：`python scripts/maimai_ai_infra_search_live_gate.py --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-s4a-plan.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-s4a-run-2026-05-15.json --cdp-url http://127.0.0.1:9888 --delay-seconds 8 --timeout-seconds 30`。
- 输出证据：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-s4a-run-2026-05-15.json`，该目录受 `.gitignore` 管理，不提交运行数据。
- 结果：`status=completed`，`stopReason=null`，3 个 batch 全部完成，共保留 90 条列表 contacts。
- 分页核验：`unit-000001/000002/000003` 均为 1 页；每页 `httpStatus=200`、`parseError=null`、`contentType=application/json`、`listLength=30`。
- 页面健康：执行前后均为 `title=人才银行`、`readyState=complete`、`visibilityState=visible`、`hasLoginPrompt=false`、`hasCaptcha=false`。
- 请求体核验：每页请求均不含禁用字段 `age`；包含 `min_age=24`、`max_age=40`、`worktimes_min=2`、`worktimes_max=10`、`degrees=1,2,3`。
- 边界确认：本轮只做列表搜索；未抓详情、未写 `data/talent.db`、未执行 apply。若继续导入列表结果，需要单独授权 `确认导入 AI Infra V2 列表结果`。

# AI Infra V2 S4a 列表结果导入门禁（2026-05-15）

> 目标：把 S4a 小样本真实列表搜索结果接入 campaign 标准流水线，只跑列表导入 dry-run；不写主库、不写 campaign 库、不抓详情、不 apply。

## 执行计划

- [x] 将 `raw/search-live-s4a-run-2026-05-15.json` 中的 3 个真实 page 标准化落到 `raw/search/unit-*/page-001.json`，保留 `responseSummary`、`request` 和 contacts。
- [x] 运行 `run-campaign --wave wave-001` dry-run，从页级 raw 重建 `contacts-wave-001.json` 并生成导入报告。
- [x] 检查 dry-run 报告：原始/去重 contacts、新建/合并/待确认/失败数量，以及是否产生真实 DB 写入。
- [x] 写入 Review；若 dry-run clean，再等待单独授权后才允许列表结果 apply。

## Review

- 标准化页级 raw：`unit-000001/page-001.json`、`unit-000002/page-001.json`、`unit-000003/page-001.json` 已从 S4a live run 落盘，合计 90 条原始 contacts。
- dry-run 命令：`python scripts/maimai_ai_infra_pipeline.py run-campaign --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --config configs/maimai-ai-infra-v2-cold-start-strategy.json --wave wave-001 --db data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`。
- contacts payload：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/contacts/contacts-wave-001.json`，跨 batch 去重后 `total_contacts=73`。
- dry-run 报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/import-list-wave-001-dry-run.md/json`。
- dry-run 结果：`raw_contacts=73`，`unique_contacts=73`，`duplicates_skipped=0`，`pre_errors=0`；导入模拟为 `created=73`、`merged=0`、`pending=0`、`errors=0`。
- 写入边界：本轮未加 `--apply`，未创建 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`，未写主库，未生成 import ledger。

# AI Infra V2 S4b continuation 准备（2026-05-15）

> 目标：在不执行真实搜索的前提下，准备 S4b wave-001 continuation 计划。执行 S4b 前仍需用户明确授权。

## 执行计划

- [x] 读取 `search-units.jsonl`，确认 wave-001 共 40 个 unit。
- [x] 生成 continuation plan：跳过 S4a 已完成的 `unit-000001..unit-000003` 第 1 页，从剩余 page task 继续。
- [x] 写入 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-s4b-continuation-plan.json`。

## Review

- S4b plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-s4b-continuation-plan.json`。
- 范围：40 个 batch；`unit-000001..unit-000003` 从 `start_page=2` 到 `max_pages=3`，其余 `unit-000004..unit-000040` 从第 1 页到第 3 页。
- 规模：`expected_page_tasks=117`，理论最多 `expected_max_contacts=3510`。
- 边界：尚未执行真实搜索；执行前需要明确授权。建议授权语为 `确认执行 AI Infra V2 S4b 列表搜索`。

# AI Infra V2 S4b 列表搜索执行（2026-05-15）

> 目标：在用户明确授权 `确认执行 AI Infra V2 S4b 列表搜索` 后，执行 wave-001 continuation 列表搜索；只抓列表，不抓详情、不写 DB、不 apply。

## 执行计划

- [x] 记录授权和范围：使用 `search-live-s4b-continuation-plan.json`，40 个 batch、117 个 page task。
- [x] 执行 S4b live gate，输出 `raw/search-live-s4b-run-2026-05-15.json`。
- [x] 检查 live raw：`status/stopReason`、每页 HTTP 状态、解析错误、页面健康、请求体字段。
- [x] 若 completed，将 S4b 聚合 raw 标准化落到 `raw/search/unit-*/page-*.json`。
- [x] 运行 `run-campaign --wave wave-001` dry-run，重建 wave contacts 并生成导入报告。
- [x] 运行聚焦测试和 `git diff --check`，记录 Review。

## Review

- live gate 命令：`python scripts/maimai_ai_infra_search_live_gate.py --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-s4b-continuation-plan.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-s4b-run-2026-05-15.json --cdp-url http://127.0.0.1:9888 --delay-seconds 8 --timeout-seconds 30`。
- live raw 证据：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-s4b-run-2026-05-15.json`；结果为 `status=completed`、`stopReason=null`，40 个 batch、117 个 page task 全部完成，S4b 原始列表 contacts 为 2121。
- 分页核验：117 页全部 `httpStatus=200`、`parseError=null`；执行后页面健康为 `title=人才银行`、`readyState=complete`、`hasLoginPrompt=false`、`hasCaptcha=false`，`visibilityState=hidden` 但未影响请求完成。
- 请求体核验：每页请求均不含禁用字段 `age`；包含 `min_age=24`、`max_age=40`、`worktimes_min=2`、`worktimes_max=10`、`degrees=1,2,3`。
- 页级 raw：S4b 已标准化落盘到 `raw/search/unit-*/page-*.json`，当前 wave-001 页级 raw 合计 120 页、2211 条 page contacts，其中包含 S4a 3 页 90 条和 S4b 117 页 2121 条。
- dry-run 命令：`python scripts/maimai_ai_infra_pipeline.py run-campaign --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --config configs/maimai-ai-infra-v2-cold-start-strategy.json --wave wave-001 --db data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`。
- contacts payload：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/contacts/contacts-wave-001.json`，pipeline 标准化去重后 `total_contacts=818`。
- dry-run 报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/import-list-wave-001-dry-run.md/json`；结果为 `raw_contacts=818`、`unique_contacts=818`、`duplicates_skipped=0`、`pre_errors=0`、`created=818`、`merged=0`、`pending=0`、`errors=0`。
- 写入边界：本轮未加 `--apply`，未创建 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`，未写 `data/talent.db`，未生成 import ledger，未抓详情。
- 验证：`python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_search_live_gate.py -q` -> `51 passed`；`git diff --check` -> PASS。

# AI Infra V2 S4b 列表结果 apply 到 campaign DB（2026-05-15）

> 目标：在用户明确授权“把这 818 条列表 dry-run 结果真实写入 campaign DB”后，只把 wave-001 列表结果 apply 到 campaign 专用库；不写主库、不抓详情、不执行详情 apply。

## 执行计划

- [x] 记录 apply 授权和边界：目标库仅为 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`。
- [x] 执行 `run-campaign --wave wave-001 --apply`，输入仍为 S4a+S4b 标准化页级 raw 生成的 818 条唯一联系人。
- [x] 检查 apply 报告、campaign DB 计数、import ledger，并确认 `data/talent.db` 未修改。
- [x] 运行聚焦测试和 `git diff --check`。
- [x] 写入 Review，明确下一步若要详情抓取或主库写入仍需单独授权。

## Review

- apply 命令：`python scripts/maimai_ai_infra_pipeline.py run-campaign --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --config configs/maimai-ai-infra-v2-cold-start-strategy.json --wave wave-001 --db data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db --apply`。
- apply 报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/import-list-wave-001-apply.md/json`；结果为 `raw_contacts=818`、`unique_contacts=818`、`duplicates_skipped=0`、`pre_errors=0`、`created=818`、`merged=0`、`pending=0`、`errors=0`。
- campaign DB：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db` 已创建；核验计数为 `candidates=818`、`source_profiles=818`、`candidate_details=818`、`pending_merges=0`、`sync_conflicts=0`、`maimai_profiles=818`。
- apply ledger：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/state/import-ledger.jsonl` 已写入 `started` 和 `completed` 两条，`import_ledger_has_apply(..., "wave-001")=True`。
- 主库边界：`data/talent.db` 未修改，核验时间戳仍为 `2026-05-14 13:54:21`；本轮未抓详情、未执行详情 apply。
- 验证：`python -m pytest tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py -q` -> `39 passed`；`git diff --check` -> PASS。

# AI Infra V2 wave-001 列表初筛报告（2026-05-15）

> 目标：基于已 apply 到 campaign DB 的 818 条列表联系人，生成 V2 list-mode 初筛名单和初版报告；不触发真实脉脉请求、不抓详情、不写主库。

## 执行计划

- [x] 对 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db` 运行 V2 list-mode 评分，输出 shortlist JSON/MD。
- [x] 基于 shortlist 和 wave-001 产物生成 `initial-list-report.md/json`，覆盖 raw/page/wave、A/B/C/淘汰 funnel 和 A/B Top 名单。
- [x] 若 A/B 名单存在，生成人工审核队列草稿；仅作为 `detail_now/hold/reject` 输入素材，不生成详情任务包。
- [x] 核验报告统计、主库未修改、聚焦测试和 `git diff --check`。
- [x] 写入 Review，明确下一步为人工审核或继续搜索，不自动进入详情抓取。

## Review

- 中途发现初筛异常：首次评分结果为 `A=0/B=0/C=0/淘汰=818`，原因是列表 raw 中已有 `school/edu/schools`，但导入后只保存在 `source_profiles.raw_profile`，list-mode 评分未读取，导致院校硬门槛全部命中 `school_not_priority`。
- 修复：`scripts/talent_library.py` 在导入脉脉列表联系人时同步保存 `candidate_details.raw_data.maimai_list`；`scripts/maimai_ai_infra_rank.py` 的 list-mode 只读取该命名空间里的列表学校证据，不读取完整详情文本、不放松院校硬门槛。
- 回归测试：新增 `tests/test_talent_library_cli.py::test_import_entry_apply_preserves_maimai_list_raw_for_scoring`、`tests/test_maimai_ai_infra_strategy.py::test_score_candidate_list_mode_uses_maimai_list_raw_school_tags`、`tests/test_maimai_ai_infra_strategy.py::test_rank_candidates_list_mode_uses_maimai_list_raw_school_tags`。
- campaign DB 补全：用修复后的导入映射对同一 `contacts-wave-001.json` 幂等补齐 raw data，结果 `created=0`、`merged=818`、`pending=0`、`errors=0`；DB 核验 `raw_maimai_list=818`。
- shortlist：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/initial-list-shortlist-wave-001.json/md`；结果 `total_candidates=818`，`A=120`、`B=144`、`C=261`、`淘汰=293`。
- 初版报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/initial-list-report-wave-001.md/json`；funnel 为 `raw_count=2211`、`page_count=120`、`wave_count=1`。
- 人工审核草稿：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/review/initial-human-review-draft-wave-001.json`；包含 A+B 共 264 人，默认 `decision=hold`，仅供人工改为 `detail_now/hold/reject`，未生成详情任务包。
- 边界：`data/talent.db` 未修改，核验时间戳仍为 `2026-05-14 13:54:21`；本轮未触发脉脉请求、未抓详情、未执行详情 apply。
- 错误沉淀：已在 `memory/error-log.md` 记录 list-mode 院校证据丢失问题。
- 验证：`python -m pytest tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py -q` -> `75 passed`；`python -m py_compile scripts/maimai_ai_infra_rank.py scripts/talent_library.py scripts/maimai_ai_infra_pipeline.py` -> PASS；`git diff --check` -> PASS。

# AI Infra V2 后续 wave 执行规则（2026-05-15）

> 用户确认：后续每个搜索批次都执行到 pipeline 的人工评审草稿为止；真正的人工评审决策和详情抓取等所有搜索任务完成后统一处理。

## 固定边界

- [x] 每个 wave 的自动步骤：列表 live search -> 页级 raw 标准化 -> run-campaign dry-run -> run-campaign apply 到 campaign DB -> list-mode 初筛报告 -> 人工审核草稿。
- [x] 每个 wave 的停止点：只生成 `review/initial-human-review-draft-<wave>.json`，默认 `decision=hold`。
- [x] 禁止中途做人工评审决策、生成详情任务包、启动详情 plan server、抓详情或详情 apply。
- [x] 主库 `data/talent.db` 继续保持只读边界；自动写入只允许发生在 campaign DB。
- [x] 纠正规则：若某个 wave 因 429/403/验证码/登录/非 JSON/模板异常等条件中断，只记录中断点、中断原因、已完成页级 raw、continuation plan 和页面健康状态；不基于 partial 数据继续 dry-run/apply/评分/生成评审草稿。等该 wave 补齐并 clean 后再进入后续 pipeline。

# AI Infra V2 wave-002 列表搜索到人工评审草稿（2026-05-15）

> 目标：继续后续搜索任务，执行 wave-002 的 40 个 search unit；完成列表搜索、campaign DB apply、初筛报告和人工审核草稿，仍不进入详情。

## 执行计划

- [x] 生成 wave-002 live gate plan，范围为 `unit-000041..unit-000080`、每 unit 3 页。
- [x] 执行 wave-002 live gate；若登录、验证码、403、429、非 JSON 或模板异常则立即熔断，不重试。
- [x] 检查 live raw：`status/stopReason`、每页 HTTP 状态、解析错误、页面健康和请求体字段。
- [x] 标准化 wave-002 页级 raw，运行 `run-campaign --wave wave-002` dry-run；若 clean，再 apply 到 campaign DB。
- [x] 生成 wave-002 list-mode shortlist、initial-list-report 和人工审核草稿，默认 `decision=hold`。
- [x] 运行聚焦测试和 `git diff --check`，写入 Review。

## Review

- plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-002-plan.json`；范围为 40 个 batch、120 个 page task，理论最多 3600 条原始 contacts。
- live gate 命令：`python scripts/maimai_ai_infra_search_live_gate.py --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-002-plan.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-002-run-2026-05-15.json --cdp-url http://127.0.0.1:9888 --delay-seconds 8 --timeout-seconds 30`。
- 熔断结果：`status=stopped`、`stopReason=http_429`；按规则未重试。raw 证据为 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-002-run-2026-05-15.json`。
- 已完成范围：9 个 batch 有结果，26 次 page 请求中 25 页成功、1 页 `httpStatus=429`；已成功页落盘为 `unit-000041..unit-000048/page-001..003` 和 `unit-000049/page-001`，合计 25 页、302 条 page contacts。
- 页面健康：熔断后仍为 `title=人才银行`、`readyState=complete`、`hasLoginPrompt=false`、`hasCaptcha=false`，`visibilityState=hidden`；未见登录或验证码。
- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-002-continuation-after-429-plan.json`；从 `unit-000049/page-002` 继续，剩余 32 个 batch、95 个 page task，理论最多 2850 条原始 contacts。
- 已废弃的 partial pipeline：本轮曾基于 429 前的部分数据生成 `contacts-wave-002.json`、`import-list-wave-002-*`、`initial-list-*-wave-002-partial.*` 和 `initial-human-review-draft-wave-002-partial.json`；用户已纠正后续规则，之后类似中断只记录断点和过程数据，不再基于 partial 继续 pipeline。
- 主库边界：`data/talent.db` 未修改，核验时间戳仍为 `2026-05-14 13:54:21`；本轮未抓详情、未生成详情任务包、未执行详情 apply。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `87 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。

# AI Infra V2 wave-002 continuation after 429（2026-05-15）

> 目标：在用户要求“继续执行 wave-002”后，从 `search-live-wave-002-continuation-after-429-plan.json` 继续列表搜索；仍执行到人工审核草稿为止，不进入详情。

## 执行计划

- [x] 使用 continuation plan 从 `unit-000049/page-002` 继续，剩余 32 个 batch、95 个 page task。
- [x] 执行 live gate；遇 429/403/验证码/登录/非 JSON/模板异常立即熔断，不自动重试。
- [x] 标准化成功页，更新 wave-002 contacts；注意 wave-002 partial 已 apply，后续写库需按增量处理，不能直接重复整波 apply。
- [x] 更新 wave-002 shortlist、initial-list-report 和人工审核草稿。
- [x] 运行聚焦测试和 `git diff --check`，写入 Review。

## Review

- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-002-continuation-after-429-plan.json`；从 `unit-000049/page-002` 继续，32 个 batch、95 个 page task。
- live gate 命令：`python scripts/maimai_ai_infra_search_live_gate.py --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-002-continuation-after-429-plan.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-002-continuation-run-2026-05-15.json --cdp-url http://127.0.0.1:9888 --delay-seconds 8 --timeout-seconds 30`。
- live gate 结果：`status=completed`、`stopReason=null`；32 个 batch、95 页全部完成，continuation 原始 contacts 为 1623。
- 分页核验：95 页全部 `httpStatus=200`、`parseError=null`；无登录、无验证码；请求体不含 `age`，包含 `min_age=24`、`max_age=40`、`worktimes_min=2`、`worktimes_max=10`、`degrees=1,2,3`。
- 页级 raw：continuation 成功页已标准化落盘；wave-002 现为完整 120 页、1925 条 page contacts。
- full dry-run：重新生成 `contacts-wave-002.json`，全量去重后 `total_contacts=537`；`import-list-wave-002-dry-run.json` 为 `raw_contacts=537`、`unique_contacts=537`、`created=295`、`merged=242`、`pending=0`、`errors=0`。
- continuation apply：由于 wave-002 partial 已有 completed apply ledger，本轮没有重复调用 `run-campaign --apply`，而是使用底层导入器做幂等全量补写，并单独记录 `action=apply_continuation`；结果 `created=295`、`merged=242`、`pending=0`、`errors=0`。
- apply 报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/import-list-wave-002-continuation-apply.md/json`；ledger 已写入 `state/import-ledger.jsonl` 的 `apply_continuation started/completed`。
- campaign DB：当前 `candidates=1213`、`source_profiles=1213`、`candidate_details=1213`、`pending_merges=0`、`sync_conflicts=0`。
- wave-002 shortlist：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/initial-list-shortlist-wave-002.json/md`；结果 `total_candidates=537`，`A=63`、`B=93`、`C=169`、`淘汰=212`。
- wave-002 初版报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/initial-list-report-wave-002.md/json`；funnel 为 `raw_count=1925`、`page_count=120`、`wave_count=1`、`partial=false`。
- wave-002 人工审核草稿：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/review/initial-human-review-draft-wave-002.json`；包含 A+B 共 156 人，默认 `decision=hold`。partial 草稿仍保留作历史证据，但后续应使用全量草稿。
- 主库边界：`data/talent.db` 未修改，核验时间戳仍为 `2026-05-14 13:54:21`；本轮未抓详情、未生成详情任务包、未执行详情 apply。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `87 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。
# AI Infra V2 wave-003 至 wave-012 批量列表搜索执行（2026-05-15）
> 目标：按用户授权依次执行 `wave-003` 至 `wave-012` 的真实列表搜索；每个完整 wave 执行到 campaign DB apply、list-mode 初筛报告和人工评审草稿为止。若任一 wave 触发登录、验证码、403、429、非 JSON、parse error 或模板异常，只记录断点、原因和过程数据，并暂停后续任务。

## 执行计划

- [x] 预检 campaign root、`search-units.jsonl`、campaign DB 和主库只读边界。
- [x] 逐个 wave 生成 live gate plan，范围为对应 `search-units.jsonl` 的 unit。
- [x] 对 `wave-003` 执行 live gate；遇 `http_429` 熔断后只标准化成功页级 raw。
- [ ] 对每个完整 wave 执行 `run-campaign` dry-run；clean 后 apply 到 campaign DB。
- [ ] 对每个完整 wave 生成 list-mode shortlist、initial-list-report 和人工评审草稿，默认 `decision=hold`。
- [x] 若发生熔断，生成 continuation plan，记录断点和页面健康状态，不跑 partial pipeline。
- [ ] 每个完整 wave 后运行聚焦验证和 `git diff --check`。

## Review

- `wave-003` live gate 已执行，输出 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-003-run-2026-05-15.json`。
- 熔断结果：`status=stopped`、`stopReason=http_429`；中断点为 `unit-000098/page-003`，最后成功页为 `unit-000098/page-002`。
- 已按规则只保留过程数据：标准化成功页级 raw 53 页、1182 条 page contacts。
- continuation plan 已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-003-continuation-after-429-plan.json`，剩余 23 个 batch、67 个 page task。
- 中断报告已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-003-2026-05-15.json`。
- 已确认未基于 partial 数据继续 pipeline：未生成 `contacts-wave-003.json`、`import-list-wave-003-*`、`initial-list-shortlist-wave-003.*`、`initial-list-report-wave-003.*` 或 `initial-human-review-draft-wave-003.json`。
- campaign DB 未新增写入，仍为 `candidates=1213`、`source_profiles=1213`、`candidate_details=1213`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。

## 恢复后执行 Review

- 用户确认恢复后，已从 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-003-continuation-after-429-plan.json` 继续执行。
- `wave-003` continuation completed：23 个 batch、67 个剩余 page task 全部完成；`wave-003` 最终为 120 页、2089 条 page contacts、675 个去重 contacts。
- `wave-003` dry-run clean：`pre_errors=0`、`pending=0`、`errors=0`；apply 写入 campaign DB，结果 `created=536`、`merged=139`、`pending=0`、`errors=0`。
- `wave-003` 已生成 `reports/initial-list-shortlist-wave-003.json/md`、`reports/initial-list-report-wave-003.json/md` 和 `review/initial-human-review-draft-wave-003.json`；初筛分布为 `A=55`、`B=120`、`C=235`、`淘汰=265`，评审草稿 175 人，全部默认 `decision=hold`。
- `wave-003` 后聚焦验证通过：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `87 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。
- 随后启动 `wave-004`，live gate 输出 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-004-run-2026-05-15.json`，在 `unit-000148/page-002` 触发 `http_429` 熔断；最后成功页为 `unit-000148/page-001`。
- 已按规则只保留 `wave-004` 过程数据：标准化成功页级 raw 82 页、1441 条 page contacts。
- `wave-004` continuation plan 已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-004-continuation-after-429-plan.json`，剩余 13 个 batch、38 个 page task。
- `wave-004` 中断报告已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-004-2026-05-15.json`。
- 已确认未基于 `wave-004` partial 数据继续 pipeline：未生成 `contacts-wave-004.json`、`import-list-wave-004-*`、`initial-list-shortlist-wave-004.*`、`initial-list-report-wave-004.*` 或 `initial-human-review-draft-wave-004.json`。
- 当前 campaign DB 为 `candidates=1749`、`source_profiles=1749`、`candidate_details=1749`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。

## 恢复节奏调整

- 用户确认继续执行，并要求 `wave-004` 完整结束后随机休息 10-15 分钟；后续每个完整 wave 之间也随机休息 10-15 分钟，用于观察是否减少 429 熔断。
- 执行边界不变：熔断时只记录断点、原因、已获得数据和 continuation plan，不基于 partial 数据跑后续 pipeline，也不自动进入下一 wave。

## 第二次恢复后执行 Review

- 已从 `wave-004` continuation plan 继续执行：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-004-continuation-after-429-plan.json`。
- `wave-004` continuation completed：13 个 batch、38 个剩余 page task 全部完成；`wave-004` 最终为 120 页、1477 条 page contacts、511 个去重 contacts。
- `wave-004` dry-run clean：`pre_errors=0`、`pending=0`、`errors=0`；apply 写入 campaign DB，结果 `created=291`、`merged=220`、`pending=0`、`errors=0`。
- `wave-004` 已生成 `reports/initial-list-shortlist-wave-004.json/md`、`reports/initial-list-report-wave-004.json/md` 和 `review/initial-human-review-draft-wave-004.json`；初筛分布为 `A=66`、`B=82`、`C=168`、`淘汰=195`，评审草稿 148 人，全部默认 `decision=hold`。
- `wave-004` 后聚焦验证通过：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `87 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。
- `wave-004` 完整结束后已随机休息 871 秒，约 14.5 分钟；休息记录为 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/rest-after-wave-004-2026-05-15.json`。
- 随后启动 `wave-005`，live gate 输出 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-005-run-2026-05-15.json`；运行中先出现大量 `http_432`，最终 `stopReason=http_429` 熔断。
- `wave-005` 第一个异常页为 `unit-000164/page-003`，`httpStatus=432`；最后成功页为 `unit-000164/page-002`；最终 429 出现在 `unit-000198/page-001`。
- 已按规则只保留 `wave-005` 过程数据：标准化成功页级 raw 11 页、0 条 page contacts。
- `wave-005` continuation plan 已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-005-continuation-after-429-plan.json`，剩余 37 个 batch、109 个 page task。
- `wave-005` 中断报告已生成：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-005-2026-05-15.json`。
- 已确认未基于 `wave-005` partial 数据继续 pipeline：未生成 `contacts-wave-005.json`、`import-list-wave-005-*`、`initial-list-shortlist-wave-005.*`、`initial-list-report-wave-005.*` 或 `initial-human-review-draft-wave-005.json`。
- 当前 campaign DB 为 `candidates=2040`、`source_profiles=2040`、`candidate_details=2040`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。
- 用户观察：今天已达每日请求限额，当前估计约 500 次请求；本日不再继续执行真实搜索，避免基于限流状态反复触发风控。
- 后续恢复规则：从 `wave-005` continuation plan 继续前，先拆成更小切片，建议每片约 50 个 page task；切片或 wave 间继续随机休息，再观察是否降低 429/432 熔断。

# AI Infra V2 wave-005 换账号后恢复执行（2026-05-15）

> 目标：用户已换账号并手动搜索过一次，恢复 `wave-005` continuation；先校验新模板，再按约 50 个 page task 小切片执行。若触发 429/403/验证码/登录/非 JSON/模板异常，立即停止，只记录断点和过程数据。

## 执行计划

- [x] 只读检查新账号 CDP 页面健康和 `window.__maimaiSearchTemplate`。
- [x] 修复并验证新模板缺 `min_age/max_age`、含旧 `age` 时的请求体 patch，确保真实请求不发送 `search.age`，并显式写入 `min_age/max_age`。
- [x] 将 `wave-005` continuation plan 拆分为约 50 个 page task 的小切片。
- [ ] 顺序执行切片；切片间随机休息，任一切片熔断则停止，不跑 partial pipeline。
- [ ] 仅当 `wave-005` 全部 120 页补齐后，运行 run-campaign dry-run；clean 后 apply 到 campaign DB。
- [ ] 生成 `wave-005` list-mode shortlist、initial-list-report 和人工评审草稿，默认 `decision=hold`。
- [ ] 运行聚焦测试、语法检查和 `git diff --check`，写入 Review。

## Review

- 新账号模板只读检查：页面仍为 `title=人才银行`、`readyState=complete`，无登录、无验证码；`window.__maimaiSearchTemplate` 存在且指向 `/api/ent/v3/search/basic`。
- 模板漂移：新账号模板 `searchShape` 包含旧 `age` 字段且缺少 `min_age/max_age`；已修复 runner/live gate，显式写入确认过的 `min_age/max_age`，并在年龄范围存在时删除 `search.age`。
- 修复验证：`python -m pytest tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_search_live_gate.py -q` -> `36 passed`；`python -m py_compile scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_search_live_gate.py` -> PASS；只构造请求体探针确认 `hasAge=false`、`min_age=24`、`max_age=40`。
- 切片计划：`wave-005` continuation 已拆为 3 片，页数分别为 50、50、9；summary 为 `reports/wave-005-continuation-slices-2026-05-15.json`。
- slice-001：`raw/search-live-wave-005-slice-001-run-2026-05-15.json` completed，18 个 batch、50 页、8 条 contacts；每页 `httpStatus=200`、`parseError=null`、无登录/验证码、请求体不含 `age` 且包含 `min_age=24/max_age=40`。已标准化 50 页，wave-005 到达 61/120 页。
- slice-002：休息 686 秒后启动；`raw/search-live-wave-005-slice-002-run-2026-05-15.json` stopped，`stopReason=http_429`。第一异常页 `unit-000186/page-002`，最后成功页 `unit-000186/page-001`。
- 中断处理：已标准化 429 前 15 个成功页、36 条 contacts；当前 wave-005 为 76/120 页完整，剩余 44 页。
- 新 continuation plan：`search-live-wave-005-continuation-after-slice-002-429-plan.json`，从 `unit-000186/page-002` 开始，到 `unit-000200/page-003`，共 15 个 batch、44 个 page task。
- 中断报告：`reports/interruption-wave-005-slice-002-2026-05-15.json`；按规则未执行 slice-003，未生成 `contacts-wave-005.json`，未运行 dry-run/apply/评分或人工评审草稿。
- campaign DB 未新增写入，仍为 `candidates=2040`、`source_profiles=2040`、`candidate_details=2040`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `111 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS；无 `maimai_ai_infra_search_live_gate.py` 进程残留。
- 用户说明 `http_429` 熔断实际为 API 验证码，人工通过后继续执行 `search-live-wave-005-continuation-after-slice-002-429-plan.json`。
- after-captcha run：`raw/search-live-wave-005-after-captcha-run-2026-05-15.json` completed，15 个 batch、44 页、84 条 contacts；每页 `httpStatus=200`、`parseError=null`、无登录/验证码、请求体不含 `age` 且包含 `min_age=24/max_age=40`。已标准化 44 页，wave-005 达到 120/120 页。
- wave-005 dry-run clean：`contacts-wave-005.json` 为 48 个去重 contacts，`pre_errors=0`、`pending=0`、`errors=0`；apply 写入 campaign DB，结果 `created=43`、`merged=5`、`pending=0`、`errors=0`。
- wave-005 已生成 `reports/initial-list-shortlist-wave-005.json/md`、`reports/initial-list-report-wave-005.json/md` 和 `review/initial-human-review-draft-wave-005.json`；初筛分布为 `A=6`、`B=4`、`C=8`、`淘汰=30`，评审草稿 10 人，全部默认 `decision=hold`。
- wave-005 对账：四次执行来源共 120 页、128 条 page contacts，去重后 48 个联系人全部在 `contacts-wave-005.json` 和 campaign DB 中；campaign DB 当前 `candidates=2083`、`source_profiles=2083`、`candidate_details=2083`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 未修改。
- 纠正记录：live gate 已补强 API 熔断识别，HTTP 432 立即停止，HTTP 429 且 `block_info.block_type`/`captcha_type` 含 captcha 时记为 `captcha_api`；验证 `python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py -q` -> `37 passed`。

# AI Infra V2 wave-006 列表搜索到人工评审草稿（2026-05-15）

> 目标：继续执行 wave-006。范围为 `unit-000201..unit-000240`，共 40 个 unit、120 个 page task；按约 50 页切片执行。若触发 403/429/432/API 验证码/登录/页面验证码/非 JSON/模板异常，立即暂停，只记录断点、原因、已获得数据和 continuation plan，不基于 partial 数据跑后续 pipeline。

## 执行计划

- [x] 预检：确认 wave-006 尚未采集，wave-005 已完成，campaign DB 无 pending/conflict，且无 live gate 进程残留。
- [x] 补强 live gate API 熔断识别：432 和 API captcha 不再继续刷页。
- [x] 生成 wave-006 full plan 与约 50 页小切片 plan。
- [x] 只读检查页面健康和 `window.__maimaiSearchTemplate`；通过后按顺序执行切片。
- [x] 每个 completed 切片核验页级状态和请求体，标准化写入 `raw/search/unit-*/page-*.json`；切片间随机休息 10-15 分钟。
- [x] 仅当 wave-006 全部 120 页补齐后，运行 run-campaign dry-run；clean 后 apply 到 campaign DB。
- [x] 生成 wave-006 list-mode shortlist、initial-list-report 和人工评审草稿，默认 `decision=hold`。
- [x] 运行聚焦测试、语法检查和 `git diff --check`，写入 Review。

## Review

- slice-001：`raw/search-live-wave-006-slice-001-run-2026-05-15.json` completed，17 个 batch、50 页、74 条 contacts；已标准化 50 页。
- slice-002：`raw/search-live-wave-006-slice-002-run-2026-05-15.json` completed，18 个 batch、50 页、72 条 contacts；每页 `httpStatus=200`、`parseError=null`、无登录/验证码/API block，请求体不含 `age` 且包含 `min_age=24/max_age=40`、`worktimes_min=2/worktimes_max=10`；已标准化 50 页。
- slice-003 前已随机休息 669 秒，约 11.15 分钟；记录为 `reports/rest-before-wave-006-slice-003-2026-05-15.json`。
- slice-003：`raw/search-live-wave-006-slice-003-run-2026-05-15.json` stopped，`stopReason=captcha_api`；异常页为 `unit-000236/page-001`，`httpStatus=429`，`block_info.block_type=captcha_yd`，`captcha_type=text_click`。
- 中断处理：只标准化 429 前 5 个成功页、13 条 contacts；当前 `wave-006` 为 105/120 页、159 条 page contacts。
- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-006-continuation-after-slice-003-captcha-plan.json`，从 `unit-000236/page-001` 开始，剩余 5 个 batch、15 个 page task。
- 中断报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-006-slice-003-2026-05-15.json`。
- 已确认未基于 `wave-006` partial 数据继续 pipeline：未生成 `contacts-wave-006.json`、`import-list-wave-006-*`、`initial-list-shortlist-wave-006.*`、`initial-list-report-wave-006.*` 或 `initial-human-review-draft-wave-006.json`。
- campaign DB 未新增写入，仍为 `candidates=2083`、`source_profiles=2083`、`candidate_details=2083`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 验证：无 `maimai_ai_infra_search_live_gate.py` 进程残留；`git diff --check` -> PASS。按熔断规则未运行 full-wave dry-run/apply/评分/人工评审草稿。

## 恢复后执行 Review

- 用户确认继续后，已从 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-006-continuation-after-slice-003-captcha-plan.json` 恢复执行。
- after-captcha run：`raw/search-live-wave-006-after-captcha-run-2026-05-15.json` completed，5 个 batch、15 页、35 条 contacts；每页 `httpStatus=200`、`parseError=null`、无登录/验证码/API block，请求体不含 `age` 且包含 `min_age=24/max_age=40`、`worktimes_min=2/worktimes_max=10`。
- 已标准化剩余 15 页，`wave-006` 最终为 120/120 页、194 条 page contacts。
- `wave-006` dry-run clean：`raw/contacts/contacts-wave-006.json` 为 77 个去重 contacts，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-006` apply 写入 campaign DB：`created=70`、`merged=7`、`pending=0`、`errors=0`。
- `wave-006` 已生成 `reports/initial-list-shortlist-wave-006.json/md`、`reports/initial-list-report-wave-006.json/md` 和 `review/initial-human-review-draft-wave-006.json`；初筛分布为 `A=5`、`B=8`、`C=7`、`淘汰=57`，评审草稿 13 人，全部默认 `decision=hold`。
- campaign DB 当前 `candidates=2153`、`source_profiles=2153`、`candidate_details=2153`、`pending_merges=0`、`sync_conflicts=0`；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS；无 `maimai_ai_infra_search_live_gate.py` 进程残留。

# AI Infra V2 wave-007 列表搜索预检阻塞（2026-05-16）

> 目标：从 `wave-007` 开始继续列表搜索 pipeline，只生成用户审查报告，不进入详情。预检失败时只记录断点、原因和恢复计划，不启动真实搜索。

## Review

- 预检确认 `wave-007` 有 40 个 unit、120 个 page task，当前 0/120 页，未生成 `contacts-wave-007.json`、shortlist、initial-list-report 或人工评审草稿。
- 预检阻塞：`http://127.0.0.1:9888/json/list` 连接被拒绝，`stopReason=cdp_unavailable`；未找到可读的现有人才银行 CDP session，因此未启动 live gate、未发真实搜索请求。
- full plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-007-plan.json`。
- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-007-continuation-after-cdp-unavailable-plan.json`，从 `unit-000241/page-001` 开始，剩余 120 个 page task。
- 中断报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-007-2026-05-16.json`。
- 已确认未基于 partial 数据继续 pipeline：未运行 dry-run/apply/评分/人工评审草稿；主库 `data/talent.db` 未修改，预检记录时间戳仍为 `2026-05-14T13:54:21.4543850+08:00`。

# AI Infra V2 wave-008 标准列表搜索到人工评审草稿（2026-05-16）

> 目标：在已有 compressed probe 之后，执行标准 `wave-008` 全量列表搜索，用于后续对比压缩策略是否有效。本轮仍只到人工评审草稿，不生成详情任务包、不抓详情。

## Review

- 预检：`wave-008` 标准页级 raw 为 0/120；CDP `127.0.0.1:9888` 人才银行页健康，`hasLoginPrompt=false`、`hasCaptcha=false`、模板为 `/api/ent/v3/search/basic`，且包含 `min_age/max_age`。
- 标准计划：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-008-plan.json`，40 个 batch、120 个 page task，范围 `unit-000281..unit-000320`。
- live gate：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-008-run-2026-05-16.json` completed，40 个 batch、120 页、top-level contacts=8，无 `stopReason`。
- 页级 raw：已标准化 120/120 页到 `raw/search/unit-*/page-*.json`，页级 contacts 合计 8，异常页 0。
- `wave-008` dry-run clean：`raw/contacts/contacts-wave-008.json` 去重后 2 人，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-008` apply 写入 campaign DB：`created=1`、`merged=1`、`pending=0`、`errors=0`；主库 `data/talent.db` 未修改。
- 评分和报告：`reports/initial-list-shortlist-wave-008.json/md`、`reports/initial-list-report-wave-008.json/md` 已生成；初筛分布为 `A=0`、`B=0`、`C=1`、`淘汰=1`。
- 人工评审草稿：`review/initial-human-review-draft-wave-008.json` 已生成；A/B 共 0 人，默认 `decision=hold`，按规则未生成详情任务包。
- 压缩对比摘要：`reports/wave-008-compressed-vs-standard-comparison-2026-05-16.json/md`。compressed probe 为 36 成功页、1 个唯一联系人；标准 wave 为 120 成功页、2 个唯一联系人；unique/success-page 分别约 `0.0278` vs `0.0167`。
- campaign DB 当前 `candidates=2163`、`source_profiles=2163`、`candidate_details=2163`、`pending_merges=0`、`sync_conflicts=0`；无 `maimai_ai_infra_search_live_gate.py --plan` 进程残留。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。

# AI Infra V2 wave-009 换账号后标准列表搜索到人工评审草稿（2026-05-16）

> 目标：用户切换脉脉账号后，重新检查环境；确认无登录/验证码/模板阻塞后继续执行标准 `wave-009`。本轮仍只到人工评审草稿，不生成详情任务包、不抓详情。

## Review

- 新账号环境预检：CDP `127.0.0.1:9888` 人才银行页健康，`hasLoginPrompt=false`、`hasCaptcha=false`、模板为 `/api/ent/v3/search/basic`；模板里仍有旧 `age` 字段且缺少 `min_age/max_age`，但 live gate 会在应用已确认年龄范围时删除 `age` 并补入 `min_age/max_age`。
- 初始状态：`wave-009` 标准页级 raw 为 0/120，未生成 `contacts-wave-009.json`、shortlist、initial-list-report 或人工评审草稿；无 live gate 进程残留；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14T13:54:21.4543850+08:00`。
- 标准计划：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-009-plan.json`，40 个 batch、120 个 page task，范围 `unit-000321..unit-000360`。
- live gate：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/search-live-wave-009-run-2026-05-16.json` completed，40 个 batch、120 页、top-level contacts=0，无 `stopReason`。
- 页级 raw：已标准化 120/120 页到 `raw/search/unit-*/page-*.json`，页级 contacts 合计 0，异常页 0。
- `wave-009` dry-run clean：`raw/contacts/contacts-wave-009.json` 去重后 0 人，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-009` apply 为 campaign DB no-op：`created=0`、`merged=0`、`pending=0`、`errors=0`；主库 `data/talent.db` 未修改。
- 评分和报告：`reports/initial-list-shortlist-wave-009.json/md`、`reports/initial-list-report-wave-009.json/md` 已生成；初筛分布为 `A=0`、`B=0`、`C=0`、`淘汰=0`。
- 人工评审草稿：`review/initial-human-review-draft-wave-009.json` 已生成；A/B 共 0 人，默认 `decision=hold`，按规则未生成详情任务包。
- campaign DB 当前 `candidates=2163`、`source_profiles=2163`、`candidate_details=2163`、`pending_merges=0`、`sync_conflicts=0`；无 `maimai_ai_infra_search_live_gate.py --plan` 进程残留。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS。

# AI Infra V2 wave-007 状态对账与续跑（2026-05-16）

> 目标：对账 `wave-007` 的预检阻塞记录与实际产物；若 live run 已完成且未进入下游，则补标准化 page raw、run-campaign、初筛报告和人工评审草稿，不进入详情。

## 执行计划

- [x] 对账 `tasks/todo.md`、中断报告与 `raw/search-live-wave-007-run-2026-05-16.json`，确认最新实际断点。
- [x] 将 `wave-007` live run 成功页标准化回填到 `raw/search/unit-*/page-*.json`。
- [x] 对 `wave-007` 运行 `run-campaign` dry-run；clean 后 apply 到 campaign DB。
- [x] 生成 `wave-007` 的 shortlist、initial-list-report 和人工评审草稿，默认 `decision=hold`。
- [x] 验证 campaign DB、主库边界、关键产物和 `git diff --check`，写入 Review。

## Review

- 状态对账：`reports/interruption-wave-007-2026-05-16.json` 与 `tasks/todo.md` 记录停在 `cdp_unavailable`，但更晚的 `raw/search-live-wave-007-run-2026-05-16.json` 实际为 `status=completed`；该 run 创建时间为 `2026-05-16 10:11:21`，晚于中断报告的 `2026-05-16 09:44:50`，说明预检阻塞记录已过期。
- live run 实际结果：`wave-007` 共 40 个 batch、120 页全部完成，页级 `httpStatus` 均为 200；原始页联系人共 26 条，去重后 10 个联系人。
- 标准化回填：已用现有 campaign helper 将 `raw/search-live-wave-007-run-2026-05-16.json` 成功页全部回填为 `raw/search/unit-*/page-*.json`；`wave-007` 当前为 120/120 页标准化完成。
- dry-run clean：`raw/contacts/contacts-wave-007.json` 为 10 个去重 contacts；`reports/import-list-wave-007-dry-run.md/json` 结果为 `pre_errors=0`、`pending=0`、`errors=0`、`created=9`、`merged=1`。
- apply 结果：`reports/import-list-wave-007-apply.md/json` 结果为 `created=9`、`merged=1`、`pending=0`、`errors=0`；`state/import-ledger.jsonl` 已写入 `started` 和 `completed` 两条 `wave-007` apply 记录。
- campaign DB：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db` 从 `candidates=2153` 增至 `2162`；`source_profiles=2162`、`candidate_details=2162`、`pending_merges=0`、`sync_conflicts=0`。
- shortlist：`reports/initial-list-shortlist-wave-007.json/md` 已生成；结果 `total_candidates=10`，`A=1`、`B=3`、`C=2`、`淘汰=4`。
- 初版报告：`reports/initial-list-report-wave-007.json/md` 已生成；funnel 为 `raw_count=26`、`page_count=120`、`wave_count=1`、`partial=false`，coverage 为 `direction_count=10`、`company_count=9`。
- 人工评审草稿：`review/initial-human-review-draft-wave-007.json` 已生成；包含 A+B 共 4 人，全部默认 `decision=hold`，优先级为 `A->P0`、`B->P1`。
- 主库边界：`data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`；本轮未进入详情抓取或详情 apply。

# AI Infra V2 wave-006 之后联系人下降原因分析（2026-05-16）

> 目标：解释为什么从 `wave-006` 开始抓到的联系人明显减少，区分“query 面变窄 / 命中本来少”和“执行链路异常 / 数据丢失”两类原因，并给出证据。

## 执行计划

- [x] 汇总 `wave-001..wave-007` 的 page contacts、去重 contacts、shortlist 和 page-level total/zero-page 分布。
- [x] 对比 `wave-005..wave-007` 的 live run、plan 和 raw page，确认减少是否来自 query 命中量下降而非标准化/导入丢数。
- [x] 抽样核对 `wave-006`、`wave-007` 的 query/company/position 组合与返回 totals，判断是否是波次策略本身更窄。
- [x] 输出结论、证据和后续建议，写入 Review。

## Review

- 严格说联系人断崖不是从 `wave-006` 才开始，而是 `2026-05-15` 的 `wave-005` 就已经进入低命中区：`wave-004 -> wave-005 -> wave-006 -> wave-007` 的去重联系人分别是 `511 -> 48 -> 77 -> 10`；raw contacts 分别是 `1477 -> 128 -> 194 -> 26`。
- 这不是执行链路丢数。`wave-005/006/007` 最终都补齐了 `120/120` 页；`run-campaign` dry-run/apply 都是 clean；去重倍率稳定，`raw/unique` 分别为 `2.67 / 2.52 / 2.60`，没有出现“重复异常增多把结果吃掉”的迹象。
- page-level total 直接证明是上游命中池变小，而不是本地标准化或导入丢数：`wave-004` 平均每页 `total=328.01`、中位数 `6`；`wave-005` 掉到 `3.19`、中位数 `0`；`wave-006` 为 `4.85`、中位数 `4`；`wave-007` 进一步掉到 `0.65`、中位数 `0`，最大单页 total 也只有 `4`。
- 公司池切换是主因。`wave-002..wave-004` 还包含 `阿里巴巴/快手/百度/月之暗面` 这类高密度公司；`wave-005..wave-007` 切到 `DeepSeek/MiniMax/智谱/阶跃星辰/生数科技/爱诗科技`。其中 `wave-007` 的 `生数科技/爱诗科技` 最稀疏：两家公司各 60 页里，正 total 页只有 `18/12`，平均每页 total 只有 `0.8/0.5`。
- `keyword_pack` 不是主要瓶颈，`company + position` 硬筛才是。`wave-005` 有 `19/20` 对、`wave-006` 有 `20/20` 对、`wave-007` 有 `20/20` 对同一 `company + position` 下的 `inference/training` 三页 totals 完全一致，说明换词包几乎没有扩展结果集；真正限制结果的是 `allcompanies + positions` 这两个筛选。
- `wave-006` 本身并不比 `wave-005` 更差，反而略有恢复：`unique_contacts 77 > 48`，`avg_total_per_page 4.85 > 3.19`。所以如果要找“为什么从 `wave-006` 开始明显少”，更准确的结论是：`wave-006` 只是延续了 `wave-005` 进入 tier2 长尾公司池后的低命中状态；`wave-007` 因公司池更小再次下降。
- `wave-007` 另有一个 bookkeeping 问题：`tasks/todo.md` 和中断报告一度停在 `cdp_unavailable`，但实际后来已有 completed live run；不过这个问题只影响状态判断，不影响最终联系人数量。对账后补跑 page raw / import / shortlist，结果仍然是低命中。
- 后续建议：对 `生数科技/爱诗科技` 这类更小公司，不要继续均匀铺 10 个 technical position * 2 个词包。优先保留已验证有量的 `机器学习平台 / 推理引擎 / 高性能计算`，并考虑放松 `positions` 或改用更宽的 precision title 批次，否则大部分 batch 会继续是全 0 页。
- 验证：本次统计统一基于 canonical `raw/search/unit-*/page-*.json` 与 wave report/shortlist 产物重算，避免把中断重试页重复计数；`git diff --check` -> PASS。

# AI Infra V2 wave-008 compressed probe（2026-05-16）

> 目标：基于 `wave-005..007` 的低命中分析，先执行一版压缩后的 `wave-008` 探针计划，只看 live result 数据；不写 DB、不进入详情、不替代 canonical `wave-008`，除非结果证明值得扩展。

## 执行计划

- [x] 生成 `search-live-wave-008-compressed-plan.json`，从原始 `wave-008` 的 40 个 unit 压缩到约 12 个 batch。
- [x] 预检 CDP 和人才银行页面健康；若不可用，只记录阻塞，不发真实搜索。
- [x] 执行 compressed live gate；遇 429/432/403/API 验证码/登录/非 JSON/模板异常立即停止。
- [x] 汇总 page total、contacts、去重联系人、命中 position/keyword_pack 分布。
- [x] 根据结果判断是否继续扩展或转为正式 `wave-008` 导入，写入 Review。

## Review

- 压缩计划：`search-live-wave-008-compressed-plan.json` 共 `12` 个 batch、`36` 个 page task，覆盖 `硅基流动/推理引擎` 与 `字节跳动/机器学习工程师|深度学习工程师|平台开发工程师` 的高信号词包。
- 首次 live gate：`raw/search-live-wave-008-compressed-run-2026-05-16.json` 在 `unit-000303/page-001` 触发 `captcha_api` 停机；此前已完成 `unit-000283..302` 共 `9` 个 batch、`27` 个成功页，页级 `httpStatus=200`。
- 用户手动过码后，已生成 continuation plan：`search-live-wave-008-compressed-continuation-after-captcha-plan.json`，只补 `unit-000303/309/310` 剩余 `3` 个 batch、`9` 个 page task。
- continuation run：`raw/search-live-wave-008-compressed-continuation-run-2026-05-16.json` 为 `status=completed`；剩余 `9` 页全部成功，未再次触发 403/429/432/API 验证码/登录/非 JSON/模板异常。
- 合并结果汇总见 `reports/search-live-wave-008-compressed-summary-2026-05-16.json/md`：总尝试页 `37`（其中 `429` 阻塞页 `1`），成功页 `36`，`httpStatus=200` 共 `36` 页；`positive_total_pages=6`、`zero_total_pages=30`、`page_total_sum=6`、`avg_total_per_success_page=0.1667`、`median_total=0`、`max_total=1`。
- 联系人结果：页级 raw contacts 只有 `2` 条，去重后只剩 `1` 人；两条 raw 都来自 `硅基流动 + 推理引擎` 的 `inference/training` 两个 batch，同一联系人重复命中。`字节跳动` 的 `10` 个 batch、`30` 个成功页全部 `total=0`。
- 结论：这版 compressed probe 不值得扩展，也不转正式 `wave-008` 导入；保持“不写 DB、不进入详情、不替代 canonical wave-008”。如果后续还要探 `wave-008`，更合理的是先做 `page-001 only` 探针，只有当某个 batch 的 `page1 total > 30` 时再补第 2-3 页，否则固定 3 页会继续浪费请求额度。

# AI Infra V2 wave-010 标准列表搜索到人工评审草稿（2026-05-16）

> 目标：继续执行标准 `wave-010`。本轮仍只到人工评审草稿，不生成详情任务包、不抓详情；遇 403/429/432/API 验证码/登录/页面验证码/非 JSON/模板异常立即熔断并记录 continuation。

## 执行计划

- [x] 预检：确认无 live gate 进程残留、主库 `data/talent.db` 不变、`wave-010` 仍未采集，且 CDP 人才银行页健康。
- [x] 生成 `search-live-wave-010-plan.json`，覆盖 `unit-000361..unit-000400` 共 40 个 batch、120 个 page task。
- [x] 执行 `wave-010` live gate；若熔断，只标准化成功页并写 continuation/interruption 后停止。
- [x] 完成后标准化 120 页到 `raw/search/unit-*/page-*.json`。
- [x] 运行 `run-campaign --wave wave-010` dry-run；clean 后 apply 到 campaign DB。
- [x] 生成 `initial-list-shortlist-wave-010.*`、`initial-list-report-wave-010.*` 和 `review/initial-human-review-draft-wave-010.json`。
- [x] 运行聚焦测试、语法检查和 `git diff --check`，确认无 live gate 进程残留且主库未修改。

## Review

- 预检：`wave-010` 为 `unit-000361..unit-000400` 共 40 个 batch、120 个 page task；执行前标准化页为 `0/120`，未生成 contacts/import/shortlist/report/review；无 live gate 进程残留。CDP 人才银行页健康，`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，模板为 `POST /api/ent/v3/search/basic` 且包含 `min_age/max_age`。
- 标准计划：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-010-plan.json`，覆盖 `unit-000361..unit-000400`。
- live gate：`raw/search-live-wave-010-run-2026-05-16.json` stopped，`stopReason=captcha_api`；失败页为 `unit-000368/page-003`，HTTP `429`，`block_info.block_type=captcha_yd`，`captcha_type=text_click`。
- 中断前成功页：已标准化 `23/120` 页，包含 `unit-000361..unit-000367` 全部 21 页，以及 `unit-000368/page-001..002`；失败页 `unit-000368/page-003` 未写入 page raw。
- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-010-continuation-after-captcha-api-plan.json`，从 `unit-000368/page-003` 继续，剩余 `33` 个 batch、`97` 个 page task。
- 中断报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-010-2026-05-16.json`，包含 `beforeHealth/templateStatus/afterHealth`、失败页响应摘要、raw preview、`block_info` 和 downstream-not-run 证据。
- 已确认未基于 partial 数据继续 pipeline：未生成 `contacts-wave-010.json`、`import-list-wave-010-*`、`initial-list-shortlist-wave-010.*`、`initial-list-report-wave-010.*` 或 `initial-human-review-draft-wave-010.json`。
- 轻量验证：continuation plan 可读且 `resume_from=unit-000368/page-003`、剩余页数 `97`；中断报告 `stopReason=captcha_api`；无 live gate 进程残留；`git diff --check` -> PASS；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 用户处理验证码后继续执行：`raw/search-live-wave-010-continuation-after-captcha-api-run-2026-05-16.json` completed，33 个 batch、97 页、top-level contacts=306，无 `stopReason`。
- 页级 raw：已标准化 continuation 全部 97 页；`wave-010` 最终补齐 `120/120` 页，页级 contacts 合计 `306`。
- `wave-010` dry-run clean：`raw/contacts/contacts-wave-010.json` 去重后 `102` 人，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-010` apply 写入 campaign DB：`created=96`、`merged=6`、`pending=0`、`errors=0`；campaign DB 当前 `candidates=2259`、`source_profiles=2259`、`candidate_details=2259`、`pending_merges=0`、`sync_conflicts=0`。
- 评分和报告：`reports/initial-list-shortlist-wave-010.json/md`、`reports/initial-list-report-wave-010.json/md` 已生成；初筛分布为 `A=4`、`B=5`、`C=9`、`淘汰=84`。
- 人工评审草稿：`review/initial-human-review-draft-wave-010.json` 已生成；A+B 共 `9` 人，全部默认 `decision=hold`，优先级为 `A->P0`、`B->P1`；未生成详情任务包。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS；无 `maimai_ai_infra_search_live_gate.py --plan` 进程残留；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。

- 用户要求继续前复核：`wave-010` 产物完整性再次通过，`120/120` 页、`contacts_total=102`、review items `9`、无 detail-wave-010 产物；聚焦测试再次 `112 passed`，语法检查、`git diff --check`、主库边界和 live gate 进程检查均通过。

# AI Infra V2 wave-011 标准列表搜索到人工评审草稿（2026-05-16）

> 目标：在 `wave-010` 验证通过后继续执行标准 `wave-011`。本轮仍只到人工评审草稿，不生成详情任务包、不抓详情；遇 403/429/432/API 验证码/登录/页面验证码/非 JSON/模板异常立即熔断并记录 continuation。

## 执行计划

- [x] 预检：确认无 live gate 进程残留、主库 `data/talent.db` 不变、`wave-011` 尚未采集，且 CDP 人才银行页健康。
- [x] 生成 `search-live-wave-011-plan.json`，覆盖 `unit-000401..unit-000440` 共 40 个 batch、120 个 page task。
- [x] 执行 `wave-011` live gate；若熔断，只标准化成功页并写 continuation/interruption 后停止。
- [x] 完成后标准化 120 页到 `raw/search/unit-*/page-*.json`。
- [x] 运行 `run-campaign --wave wave-011` dry-run；clean 后 apply 到 campaign DB。
- [x] 生成 `initial-list-shortlist-wave-011.*`、`initial-list-report-wave-011.*` 和 `review/initial-human-review-draft-wave-011.json`。
- [x] 运行聚焦测试、语法检查和 `git diff --check`，确认无 live gate 进程残留且主库未修改。

## Review

- 预检：`wave-011` 为 `unit-000401..unit-000440` 共 40 个 batch、120 个 page task；执行前标准化页为 `0/120`，未生成 contacts/import/shortlist/report/review；无 live gate 进程残留。CDP 人才银行页健康，`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，模板为 `POST /api/ent/v3/search/basic` 且包含 `min_age/max_age`。
- 标准计划：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-011-plan.json`，覆盖 `unit-000401..unit-000440`。
- live gate：`raw/search-live-wave-011-run-2026-05-16.json` stopped，`stopReason=exception`；失败点为 `unit-000403/page-003`，`batch_error=Connection timed out`。页面健康仍为 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- 中断前成功页：已标准化 `8/120` 页，包含 `unit-000401..unit-000402` 全部 6 页，以及 `unit-000403/page-001..002`；失败页 `unit-000403/page-003` 未写入 page raw。
- continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-011-continuation-after-connection-timeout-plan.json`，从 `unit-000403/page-003` 继续，剩余 `38` 个 batch、`112` 个 page task。
- 中断报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-011-2026-05-16.json`，包含 `beforeHealth/templateStatus/afterHealth`、失败点、最后成功页和 downstream-not-run 证据。
- 已确认未基于 partial 数据继续 pipeline：未生成 `contacts-wave-011.json`、`import-list-wave-011-*`、`initial-list-shortlist-wave-011.*`、`initial-list-report-wave-011.*` 或 `initial-human-review-draft-wave-011.json`。
- 轻量验证：continuation plan 可读且 `resume_from=unit-000403/page-003`、剩余页数 `112`；中断报告 `stopReason=exception`、`stopError=Connection timed out`；无 live gate 进程残留；`git diff --check` -> PASS；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 用户确认网页侧无验证码后，先跑单页 probe：`raw/search-live-wave-011-probe-after-connection-timeout-run-2026-05-16.json` completed，`unit-000403/page-003` 请求成功，HTTP 200，无验证码，已标准化该页；`wave-011` 进度到 `9/120`。
- probe 成功后继续执行剩余计划：`raw/search-live-wave-011-continuation-after-probe-success-run-2026-05-16.json` stopped，`stopReason=captcha_api`；失败页为 `unit-000417/page-002`，HTTP `429`，`block_info.block_type=captcha_yd`，`captcha_type=text_click`。
- 第二次中断前成功页：已标准化新增 `40` 页、`549` 条 page contacts；`wave-011` 当前标准化进度为 `49/120`。
- 新 continuation plan：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-011-continuation-after-captcha-api-2-plan.json`，从 `unit-000417/page-002` 继续，剩余 `24` 个 batch、`71` 个 page task。
- 新中断报告：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/interruption-wave-011-after-probe-success-2026-05-16.json`，包含失败页 `httpStatus/responseSummary/responseRawPreview/block_info/captcha_type` 和 downstream-not-run 证据。
- 轻量验证：当前 `wave-011` 为 `49/120` 页；continuation plan 可读且 `resume_from=unit-000417/page-002`、剩余页数 `71`；未生成 contacts/import/shortlist/report/review；无 live gate 进程残留；`git diff --check` -> PASS；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。
- 用户继续后执行 `search-live-wave-011-continuation-after-captcha-api-2-plan.json`：在 `unit-000423/page-002` 再次触发 `captcha_api`，HTTP `429`，`block_info.block_type=captcha_yd`，`captcha_type=text_click`。
- 第三次中断处理：标准化 429 前新增 `18` 页、`270` 条 page contacts；`wave-011` 进度到 `67/120`；写入 `search-live-wave-011-continuation-after-captcha-api-3-plan.json`，从 `unit-000423/page-002` 继续，剩余 `53` 页；中断报告为 `reports/interruption-wave-011-after-captcha-api-2-2026-05-16.json`。
- 用户继续后先跑单页 probe：`raw/search-live-wave-011-probe-after-captcha-api-3-run-2026-05-16.json` completed，`unit-000423/page-002` 请求成功，HTTP 200，无验证码，已标准化该页；`wave-011` 进度到 `68/120`。
- probe 成功后继续执行剩余 `52` 页：`raw/search-live-wave-011-continuation-after-captcha-api-3-probe-success-run-2026-05-16.json` completed，18 个 batch、52 页、top-level contacts=217，无 `stopReason`。
- 页级 raw：已标准化最后 52 页；`wave-011` 最终补齐 `120/120` 页，页级 contacts 合计 `1036`。
- `wave-011` dry-run clean：`raw/contacts/contacts-wave-011.json` 去重后 `332` 人，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-011` apply 写入 campaign DB：`created=265`、`merged=67`、`pending=0`、`errors=0`；campaign DB 当前 `candidates=2524`、`source_profiles=2524`、`candidate_details=2524`、`pending_merges=0`、`sync_conflicts=0`。
- 评分和报告：`reports/initial-list-shortlist-wave-011.json/md`、`reports/initial-list-report-wave-011.json/md` 已生成；初筛分布为 `A=4`、`B=17`、`C=42`、`淘汰=269`。
- 人工评审草稿：`review/initial-human-review-draft-wave-011.json` 已生成；A+B 共 `21` 人，全部默认 `decision=hold`，优先级为 `A->P0`、`B->P1`；未生成详情任务包。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS；无 `maimai_ai_infra_search_live_gate.py --plan` 进程残留；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。

# AI Infra V2 wave-012 标准列表搜索到人工评审草稿（2026-05-16）

> 目标：继续执行标准 `wave-012`。本轮仍只到人工评审草稿，不生成详情任务包、不抓详情；遇 403/429/432/API 验证码/登录/页面验证码/非 JSON/模板异常立即熔断并记录 continuation。

## 执行计划

- [x] 预检：确认无 live gate 进程残留、主库 `data/talent.db` 不变、`wave-012` 尚未采集，且 CDP 人才银行页健康。
- [x] 生成 `search-live-wave-012-plan.json`，覆盖 `unit-000441..unit-000450` 共 10 个 batch、30 个 page task。
- [x] 执行 `wave-012` live gate；若熔断，只标准化成功页并写 continuation/interruption 后停止。
- [x] 完成后标准化 30 页到 `raw/search/unit-*/page-*.json`。
- [x] 运行 `run-campaign --wave wave-012` dry-run；clean 后 apply 到 campaign DB。
- [x] 生成 `initial-list-shortlist-wave-012.*`、`initial-list-report-wave-012.*` 和 `review/initial-human-review-draft-wave-012.json`。
- [x] 运行聚焦测试、语法检查和 `git diff --check`，确认无 live gate 进程残留且主库未修改。

## Review

- 预检：`wave-012` 为 `unit-000441..unit-000450` 共 10 个 batch、30 个 page task；执行前标准化页为 `0/30`，未生成 contacts/import/shortlist/report/review；无 live gate 进程残留。CDP 人才银行页健康，`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，模板为 `POST /api/ent/v3/search/basic` 且包含 `min_age/max_age`。
- 标准计划：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/search-live-wave-012-plan.json`，覆盖 `unit-000441..unit-000450`。
- live gate：`raw/search-live-wave-012-run-2026-05-16.json` completed，10 个 batch、30 页、top-level contacts=455，无 `stopReason`。
- 页级 raw：已标准化 `30/30` 页到 `raw/search/unit-*/page-*.json`，页级 contacts 合计 `455`，异常页 `0`。
- `wave-012` dry-run clean：`raw/contacts/contacts-wave-012.json` 去重后 `178` 人，`pre_errors=0`、`pending=0`、`errors=0`。
- `wave-012` apply 写入 campaign DB：`created=124`、`merged=54`、`pending=0`、`errors=0`；campaign DB 当前 `candidates=2648`、`source_profiles=2648`、`candidate_details=2648`、`pending_merges=0`、`sync_conflicts=0`。
- 评分和报告：`reports/initial-list-shortlist-wave-012.json/md`、`reports/initial-list-report-wave-012.json/md` 已生成；初筛分布为 `A=2`、`B=9`、`C=21`、`淘汰=146`。
- 人工评审草稿：`review/initial-human-review-draft-wave-012.json` 已生成；A+B 共 `11` 人，全部默认 `decision=hold`，优先级为 `A->P0`、`B->P1`；未生成详情任务包。
- 验证：`python -m pytest tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_runner.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_strategy.py tests/test_talent_library_cli.py -q` -> `112 passed`；`python -m py_compile scripts/maimai_ai_infra_search_live_gate.py scripts/maimai_ai_infra_search_runner.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py scripts/talent_library.py` -> PASS；`git diff --check` -> PASS；无 `maimai_ai_infra_search_live_gate.py --plan` 进程残留；主库 `data/talent.db` 未修改，时间戳仍为 `2026-05-14 13:54:21`。

# AI Infra V2 A/B 详情直连抓取计划设计（2026-05-16）

> 目标：设计 A/B 档联系人详情抓取计划，切成四个任务包，并尝试以搜索 live gate 类似方式在已打开人才银行页直接调用详情接口，省掉本地发布任务包和人工 popup 导入步骤。

## 执行计划

- [x] 只读审计 12 个 wave 的人工评审草稿，确认 A/B 原始行、去重目标数、缺 `platform_id`/`trackable_token` 情况。
- [x] 设计四包切分口径和每包目标规模。
- [x] 设计 direct detail live gate 的输入、输出、熔断、continuation 和 import/apply 边界。
- [x] 落盘实施计划到 `docs/superpowers/plans/2026-05-16-maimai-ai-infra-direct-detail-live-gate.md`。
- [ ] 等待用户确认是否开始实现工具链；本阶段不发真实详情请求、不写 campaign DB、不改主库。

## Review

- 只读审计结果：A/B 原始评审行 `811`，按 `candidate_id` 去重后 `596`；其中 A 档 `235`、B 档 `361`；重复 A/B 行 `215`。
- campaign DB 解析结果：`missing_source=0`、`missing_platform=0`、`missing_token=0`。
- 四包设计：`detail-ab-pack-001..004` 各 `149` 人；A/B 分布分别为 `59/90`、`59/90`、`59/90`、`58/91`。
- 计划边界：后续实现前仍不得触发真实详情 API；执行时先做 page health check，再做单人 probe，整包完成后才允许 `detail-wave dry-run/apply` 到 campaign DB。

# AI Infra V2 A/B 详情直连抓取工具链实现（2026-05-16）

> 目标：在当前 `feat/maimai-ai-infra-v2-campaign` 分支实现详情直连抓取工具链；作为 campaign 子任务，不新开分支。真实详情数据最终只允许写入 campaign DB，不写 `data/talent.db`。

## 执行计划

- [x] 实现 A/B 详情目标四包生成器和测试。
- [x] 实现 direct detail live gate 和测试。
- [x] 补 detailed ranking 的 candidate scope CLI 和测试。
- [x] 实现最终详情报告生成器和测试。
- [x] 生成真实四包计划并跑离线验证；真实详情 probe 前暂停确认。

## Review

- 当前边界：本阶段先实现工具链和离线测试，不触发真实详情 API，不写 campaign DB，不写主库。
- Task 1 完成：新增只读 A/B 详情目标四包生成器；DB 读取使用 SQLite `mode=ro` 且路径 URI 安全转义；缺 DB、缺 review、缺 `platform_id`、缺 `trackable_token` 均 blocked 且不写 runnable pack。
- Task 1 验证：`python -m pytest tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_detail_targets.py -q` -> `16 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_plan.py` -> PASS；`git diff --check -- scripts/maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_plan.py` -> PASS。
- Task 2 完成：新增 direct detail live gate；支持健康检查、顺序页面上下文 GET 详情接口、成功 job 原子落盘、capture 重建、known fuse 中断报告和 continuation plan。`completed_limited/stopped` capture 会标记 partial，并被 detail dry-run/apply 阻断，避免把单人 probe 当整包 apply。
- Task 3 完成：`maimai_ai_infra_rank` 支持 `--mode list|detailed` 与 `--candidate-ids-file`；candidate ids 文件兼容 `{"candidate_ids":[]}` 和 detail target manifest `{"contacts":[...]}`；scoped detailed ranking 不混入 C/淘汰或其他 wave 候选人。
- Task 4 完成：新增最终详情报告生成器，读取 A/B targets、detail-wave apply result 和 detailed rank JSON，输出 coverage、pack apply 状态、A/B/C/淘汰分布、Top candidates 和主库未写说明。
- Task 5 完成：已离线生成真实四包计划到 campaign root；`status=ready input_rows=811 unique_targets=596 missing=0 packs=149,149,149,149`，manifest 显示总目标 `596`，`detail-ab-pack-001..004` 各 `149` 人。
- 综合验证：`python -m pytest tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_ai_infra_detail_report.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_strategy.py -q` -> `95 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_plan.py scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_ai_infra_detail_report.py scripts/maimai_detail_targets.py scripts/maimai_detail_import.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py` -> PASS；相关 `git diff --check` -> PASS。
- 安全边界复核：本轮没有运行 health check 或真实详情请求；无 detail/search live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。
- 真实 probe：用户确认后执行 `detail-ab-pack-001 --max-jobs 1`，返回 `status=completed_limited`、`completed_jobs=1`、`stopReason=null`；生成 capture `raw/detail-live-detail-ab-pack-001-probe-2026-05-16.json` 和 job raw `raw/detail-live/detail-ab-pack-001/job-000001-235988813.json`。
- probe 核验：job `status=done`、errors `0`，辅助接口 `projects/job_preference/contact_btn` 均 HTTP 200 且无 parse error；无 interruption report；无 live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。
- probe 后保护性校验：partial capture 的 `detail-wave dry-run` 被识别为 `dry_run_dirty`，`capture_blockers=[partial_detail_capture]`，没有 `detail_apply` ledger；只读查询确认 candidate 573 仍未写入 `maimai_detail_capture`。
- Pack 001 full run：用户继续后执行 `detail-ab-pack-001` 全量抓取，复用已完成第 1 个 job，从剩余目标继续；最终 `status=completed`、`completed_jobs=149/149`、`failed_jobs=0`、`stopReason=null`，无 interruption report。
- Pack 001 dry-run：`python -m scripts.maimai_ai_infra_pipeline detail-wave dry-run --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --wave detail-ab-pack-001 --capture-file data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-run-2026-05-17.json` -> `dry_run_clean`；matched `149`、unmatched `0`、failed_jobs `0`、apply_blockers `0`、capture_blockers `0`。
- Pack 001 当前尚未 apply；无 `detail_apply` ledger，无 detail/search live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。
- Pack 001 apply：用户确认后执行 `detail-wave apply` 到 campaign DB，结果 `apply_completed`；`matched=149`、`written=149`、`verified_candidate_ids=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=0`、`capture_blockers=0`。
- Pack 001 apply 核验：`state/import-ledger.jsonl` 已写入 `detail_apply started/completed` 两条记录；campaign DB 只读查询 `maimai_detail_capture` 行数为 `149`，candidate `573` 已有 detail capture；无 detail/search live gate Python 进程残留。
- 主库边界：apply 后 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；写入只发生在 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`。

# AI Infra V2 A/B 详情 Pack 002 执行（2026-05-17）

> 目标：在 Pack 001 已完成并 apply 后，继续执行 `detail-ab-pack-002`。保持同一安全边界：只连接已打开的人才银行页，不自动导航/刷新/点击业务页面；详情数据只写 campaign DB，不写 `data/talent.db`。

## 执行计划

- [x] 预检：确认 Pack 002 尚未抓取、无 detail/search live gate 进程残留，并记录 `data/talent.db` 与 campaign DB 时间戳。
- [x] 运行 Pack 002 page health check，要求 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- [x] 执行 `detail-ab-pack-002` 全量详情抓取；如遇熔断，只保留已成功 job raw、capture、continuation plan 和 interruption report。
- [x] 若全量抓取完成，运行 Pack 002 `detail-wave dry-run`，只在 `dry_run_clean` 后继续。
- [x] 若 dry-run clean，apply 到 campaign DB，并核验 ledger、detail capture 行数和主库未修改。
- [x] 运行必要验证，确认无 live gate 进程残留，回填 Review。

## Review

- 预检：`detail-ab-pack-002.json` 目标数为 `149`；执行前无 Pack 002 job raw/capture/report 残留，无 detail/search live gate 进程残留。主库 `data/talent.db` 时间戳为 `2026-05-14 13:54:21`，campaign DB 时间戳为 `2026-05-17 00:33:26`。
- 页面健康：`detail-ab-pack-002` health check 返回 `status=health_ok`、`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，未发详情接口请求。
- Pack 002 full run：执行 `raw/detail-live-detail-ab-pack-002-run-2026-05-17.json`，结果 `status=completed`、`completed_jobs=149/149`、`stopReason=null`；job raw 目录 `raw/detail-live/detail-ab-pack-002/` 下 `job-*.json` 共 `149` 个；无 Pack 002 interruption report。
- Pack 002 dry-run：`reports/detail-wave-detail-ab-pack-002-dry-run.json/md` 已生成；`matched=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Pack 002 apply：`reports/detail-wave-detail-ab-pack-002-apply.json/md` 已生成；`matched=149`、`written=149`、`verified_candidate_ids=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Ledger 与 DB 核验：`state/import-ledger.jsonl` 已写入 `detail_apply started/completed` 两条 Pack 002 记录；campaign DB `maimai_detail_capture` 行数从 `149` 增至 `298`，`candidate_details=2648`。
- 主库边界：apply 后 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；写入只发生在 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`，该库时间戳更新为 `2026-05-17 01:19:50`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_detail_import.py tests/test_maimai_ai_infra_pipeline.py -q` -> `49 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_detail_import.py scripts/maimai_ai_infra_pipeline.py` -> PASS；`git diff --check` -> PASS；无 detail/search live gate Python 进程残留。

# AI Infra V2 A/B 外联执行包与 P0/P1 抽检（2026-05-17）

> 目标：基于已生成的 `final-outreach-priority-ab-packs-001-004.json`，生成可直接外联使用的轻量 CSV/Markdown，并对 P0/P1 前 30 做字段完整性、硬风险、证据和方向标签抽检。保持边界：只读 reports JSON；不触发 live gate；不读写主库。

## 执行计划

- [x] 新增外联执行包导出测试，覆盖 CSV 字段、Markdown 队列、P0/P1 抽检样本和字段完整性问题。
- [x] 新增导出脚本，支持从 outreach priority JSON 生成 execution CSV/MD 与 audit JSON/MD。
- [x] 用真实 A/B 交付结果生成外联执行包和 P0/P1 抽检报告。
- [x] 核验导出行数、P0/P1 抽检数量、关键字段缺失、硬风险和主库/live gate 边界。
- [x] 运行聚焦测试、语法检查、`git diff --check`，回填 Review。

## Review

- 新增 `scripts/maimai_ai_infra_outreach_export.py`：从 `final-outreach-priority` 只读生成外联执行 CSV/MD，并生成 P0/P1 TopN 抽检 JSON/MD；默认抽检 P0/P1 各 30 人。
- 新增 `tests/test_maimai_ai_infra_outreach_export.py`：先红灯验证模块缺失，再覆盖 CSV 字段、队列顺序、抽检样本、缺 profile URL 和缺关键证据问题。
- 真实外联执行包已生成：
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/outreach-execution-queue-ab-packs-001-004.csv`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/outreach-execution-queue-ab-packs-001-004.md`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/outreach-quality-audit-p0-p1-top30-ab-packs-001-004.json`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/outreach-quality-audit-p0-p1-top30-ab-packs-001-004.md`
- 导出核验：CSV `595` 行；优先级分布 `P0=150`、`P1=300`、`P2=145`；字段包含 `priority/rank/candidate_id/name/platform_id/company/title/city/work_years/score/grade/recommendation_label/directions/key_evidence/risk_summary/suggested_outreach_angle/profile_url`。
- 抽检核验：P0 前 `30`、P1 前 `30`；`issue_counts={}`；无重复 `candidate_id`；抽检项均为 `ready`。
- 安全边界：无 detail/search live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；本步骤只读 reports JSON。
- 验证：`python -m pytest tests/test_maimai_ai_infra_outreach_export.py tests/test_maimai_ai_infra_delivery_report.py -q` -> `2 passed`；`python -m py_compile scripts/maimai_ai_infra_outreach_export.py scripts/maimai_ai_infra_delivery_report.py` -> PASS；`git diff --check` -> PASS；`python -m pytest tests scripts -q` -> `632 passed, 1 warning`（既有 `scripts/test_boss.py` event loop deprecation）。

# AI Infra V2 工程收尾与文档状态同步（2026-05-17）

> 目标：在交付报告和外联执行包完成后，同步 V2 设计文档里的已实现 CLI 映射、Task 7/8 状态和本轮停止扩池结论，准备进入提交/合并收尾。保持边界：只改文档和任务记录，不触发 live gate，不读写主库。

## 执行计划

- [x] 审当前 diff、产物追踪状态和 V2 文档待勾选项。
- [x] 更新 V2 设计文档：补 direct detail、final delivery、outreach export CLI 映射；勾选 Task 7；新增本轮 A/B 交付状态 Task 8。
- [x] 运行文档/语法/差异检查，确认主库和 live gate 边界。
- [x] 汇总可提交范围与下一步合并建议。

## Review

- 已更新 `docs/design-discussions/2026-05-14-maimai-ai-infra-talent-search-plan-v2.md`：补充 A/B 详情四包、direct detail live gate、scoped detailed rank、最终详情覆盖报告、交付版最终寻访报告、外联执行包导出等 CLI 映射。
- Task 7 已同步为完成：`--mode detailed`、`final-search-report`、强推荐/推荐/观察/不推荐、下一轮建议、详情推翻降级测试、外联优先级和外联执行包均已勾选。
- 新增 Task 8 本轮 A/B 交付状态：详情目标 `596`，四包全部 apply；交付推荐 `强推荐=358`、`推荐=160`、`观察=77`、`不推荐=1`；外联 `P0=150`、`P1=300`、`P2=145`；最终强推荐+推荐 `518`，结论为停止扩池、转入外联消化。
- 验证：`python -m pytest tests/test_maimai_ai_infra_outreach_export.py tests/test_maimai_ai_infra_delivery_report.py tests/test_maimai_ai_infra_detail_report.py tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_live_gate.py -q` -> `29 passed`；`python -m py_compile scripts/maimai_ai_infra_outreach_export.py scripts/maimai_ai_infra_delivery_report.py scripts/maimai_ai_infra_detail_report.py scripts/maimai_ai_infra_detail_plan.py scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_ai_infra_rank.py` -> PASS；`git diff --check` -> PASS。
- 边界：无 detail/search live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`。
- 可提交范围建议：将当前 branch 上 AI Infra V2 工具链、测试、计划文档和任务记录作为一个 feature commit；`data/campaigns/` 已在 `.gitignore`，真实候选人报告产物不会进入 git。

# AI Infra V2 campaign DB 整合主库与分支清理（2026-05-17）

> 目标：把 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db` 通过同步 bundle dry-run/apply 整合进主库 `data/talent.db`，然后删除已合并的 `feat/maimai-ai-infra-v2-campaign` 本地分支。保持边界：不覆盖主库文件；先 dry-run、备份、apply；不触发任何 live gate。

## 执行计划

- [x] 从 campaign DB 导出 talent sync bundle，并校验 checksum。
- [x] 对 `data/talent.db` 做 import dry-run，核对新增、合并、冲突、跳过、删除范围。
- [x] 在无候选人冲突或可接受冲突前提下，备份主库并 apply 同步。
- [x] 验证主库候选人/来源/详情/AI Infra detail capture 覆盖变化，确认无 live gate 进程。
- [x] 删除已合并 feature 分支，检查 `main` 与 `origin/main` 状态。

## Review

- 使用标准 `talent_sync` 路径整合，不覆盖 SQLite 文件：`export` campaign DB -> `verify-bundle` -> `import` dry-run -> 备份主库 -> `import --apply --confirm "确认同步人才库"`。
- Bundle：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/campaign-to-main-sync-full-2026-05-17.zip`；checksum 校验通过。
- Dry-run：候选人预计新增 `2334`、合并 `314`、候选人冲突 `0`、跳过 `0`、删除 `0`；dry-run JSON 已写入 `reports/campaign-to-main-sync-dry-run-2026-05-17.json`。
- 备份：主库 apply 前备份到 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/talent-main-before-campaign-sync-2026-05-17.db`。
- Apply：CLI 返回新增候选人 `2334`、合并候选人 `314`、报告候选人冲突 `63`、跳过 `0`；同步导入记录 `sync_imports=1`。
- 主库同步后计数：`candidates=5453`、`source_profiles=5453`、`candidate_details=5453`、`pending_merges=0`、`sync_conflicts=143`。
- 详情覆盖：`candidate_details.raw_data` 中 `maimai_detail_capture` 从 `388` 增至 `904`；其中 `516` 条 raw_data 引用了本轮 `ai-infra-v2-2026-05-15-dry-run` campaign 路径。
- `sync_conflicts` 分布：`candidate=63`、`candidate_detail=80`；Top 字段为 `candidate_detail.raw_data.maimai_detail_capture=80`、`hunting_status=14`、`expected_city=11`、`education=11`、`gender=10`。这些是 sync 机制记录的非覆盖冲突，不是导入失败。
- 已删除本地分支 `feat/maimai-ai-infra-v2-campaign`；当前 `main...origin/main` 同步，但本任务记录尚需提交/推送。

# AI Infra V2 A/B 交付版最终寻访报告（2026-05-17）

> 目标：在四个 A/B 详情包全部完成并生成 detailed rank 后，补齐交付版 `final-search-report` 和外联优先级队列。保持边界：只读 campaign DB、detail targets、rank/report 产物；不写 `data/talent.db`；不触发 live gate。

## 执行计划

- [x] 补充 delivery report 聚合测试，覆盖 funnel、推荐标签映射、P0/P1/P2 队列、方向/公司覆盖和误判缺口。
- [x] 新增交付版报告脚本，生成 `final-search-report-ab-packs-001-004.json/md` 与 `final-outreach-priority-ab-packs-001-004.json/md`。
- [x] 使用真实 campaign 数据生成交付产物，并核验候选人数、队列互斥、rank/target 一致性。
- [x] 复核主库边界和 live gate 进程状态。
- [x] 运行聚焦测试、语法检查和 `git diff --check`。

## Review

- 新增 `scripts/maimai_ai_infra_delivery_report.py`：只读 campaign DB（SQLite `mode=ro`）和现有 rank/target/apply 报告，生成交付版最终寻访报告与外联优先级队列。
- 新增 `tests/test_maimai_ai_infra_delivery_report.py`：先红灯验证新模块缺失，再覆盖 funnel、强推荐/推荐/观察/不推荐映射、P0/P1/P2 队列、方向/公司覆盖、详情推翻样本和输出落盘。
- 真实产物已生成：
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-search-report-ab-packs-001-004.json`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-search-report-ab-packs-001-004.md`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-outreach-priority-ab-packs-001-004.json`
  - `data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-outreach-priority-ab-packs-001-004.md`
- 交付口径：详情目标 `596`、详情完成 `596`、缺失 `0`；强推荐 `358`、推荐 `160`、观察 `77`、不推荐 `1`；外联队列 `P0=150`、`P1=300`、`P2=145`。
- 一致性核验：`candidate_cards=596`；rank IDs、target IDs、card IDs 完全一致；P0/P1/P2 队列总数 `595` 且互斥，不与 excluded 重叠；excluded `1` 人来自 `excluded_education`。
- 覆盖摘要：方向覆盖 Top 为训练框架 `288`、推理引擎 `280`、框架平台 `246`、算子/异构 `130`、智算平台 `72`；公司 Top 覆盖包含字节跳动 `229`、百度 `98`、快手 `64`、阿里巴巴 `44`。
- 安全边界：无 detail/search live gate Python 进程残留；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；报告阶段未读取或写入主库。
- 验证：`python -m pytest tests/test_maimai_ai_infra_delivery_report.py tests/test_maimai_ai_infra_detail_report.py tests/test_maimai_ai_infra_strategy.py -q` -> `31 passed`；`python -m py_compile scripts/maimai_ai_infra_delivery_report.py scripts/maimai_ai_infra_detail_report.py scripts/maimai_ai_infra_rank.py` -> PASS；`git diff --check` -> PASS；`python -m pytest tests scripts -q` -> `631 passed, 1 warning`（既有 `scripts/test_boss.py` event loop deprecation）。

# AI Infra V2 A/B 最终详情排名与报告（2026-05-17）

> 目标：在四个 A/B 详情包全部 apply 后，基于 campaign DB 生成 scoped detailed ranking 和最终详情报告。保持边界：只读 campaign DB 和 detail target/report 产物，不写 `data/talent.db`。

## 执行计划

- [x] 预检：确认 A/B target manifest 为 `596` 人，四个 pack apply 均 `matched=149`、`written=149`、无 blockers。
- [x] 生成 scoped detailed ranking：只覆盖 `detail-targets-ab-all.json` 中的 A/B 目标，不混入 C/淘汰或其他候选人。
- [x] 核验 rank JSON：候选人数 `596`，所有条目 `score_mode=detailed`，candidate id 集合等于 A/B manifest。
- [x] 生成 final detail report JSON/MD。
- [x] 核验 report coverage：target `596`、completed detail `596`、missing `0`、四个 pack apply status 齐全。
- [x] 运行聚焦测试、语法检查和 `git diff --check`，确认主库未修改，回填 Review。

## Review

- 输入预检：`raw/detail-targets/detail-targets-ab-all.json` 包含 `596` 个 A/B 目标；四个 apply 报告均为 `matched=149`、`written=149`、`verified_candidate_ids=149`、`unmatched=0`、`failed_jobs=0`、无 `apply_blockers/capture_blockers`。
- scoped detailed ranking：已生成 `reports/final-detail-rank-ab-packs-001-004.json/md`；rank JSON `ranked=596`，candidate id 集合与 A/B manifest 完全一致，`outside_count=0`、`missing_count=0`，所有条目 `score_mode=detailed`。
- final detail report：已生成 `reports/final-detail-report-ab-packs-001-004.json/md`；CLI 返回 `status=ready targets=596 completed=596 missing=0 recommended=595`。
- report coverage：`target_count=596`、`completed_detail_count=596`、`missing_detail_count=0`；四个 pack 状态均为 `apply_status=applied`、`completed_detail_count=149`；最终分布为 `A=447`、`B=148`、`C=0`、`淘汰=1`，最终推荐 `595`。
- DB 核验：主库 `data/talent.db` 仍为 `candidates=3119`、`source_profiles=3119`、`candidate_details=3119`、`pending_merges=0`、`sync_conflicts=0`，时间戳仍为 `2026-05-14 13:54:21`；campaign DB 为 `candidates=2648`、`source_profiles=2648`、`candidate_details=2648`、`maimai_detail_capture=596`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_detail_report.py tests/test_maimai_ai_infra_strategy.py -q` -> `30 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_report.py scripts/maimai_ai_infra_rank.py` -> PASS；`git diff --check` -> PASS；无 detail/search live gate Python 进程残留。

# AI Infra V2 A/B 详情 Pack 003 执行（2026-05-17）

> 目标：在用户确认继续后，执行 `detail-ab-pack-003`。保持安全边界：只连接已打开的人才银行页，不自动导航/刷新/点击业务页面；详情数据只写 campaign DB，不写 `data/talent.db`。

## 执行计划

- [x] 预检：确认 Pack 003 尚未抓取、无 detail/search live gate 进程残留，并记录 `data/talent.db` 与 campaign DB 时间戳。
- [x] 运行 Pack 003 page health check，要求 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- [x] 执行 `detail-ab-pack-003` 全量详情抓取；如遇熔断，只保留已成功 job raw、capture、continuation plan 和 interruption report。
- [x] 若全量抓取完成，运行 Pack 003 `detail-wave dry-run`，只在 `dry_run_clean` 后继续。
- [x] 若 dry-run clean，apply 到 campaign DB，并核验 ledger、detail capture 行数和主库未修改。
- [x] 运行必要验证，确认无 live gate 进程残留，回填 Review。

## Review

- 预检：`detail-ab-pack-003.json` 目标数为 `149`；执行前无 Pack 003 job raw/capture/report 残留，无 detail/search live gate 进程残留。主库 `data/talent.db` 时间戳为 `2026-05-14 13:54:21`，campaign DB 时间戳为 `2026-05-17 01:19:50`；campaign DB `maimai_detail_capture` 行数为 `298`。
- 页面健康：`detail-ab-pack-003` health check 返回 `status=health_ok`、`hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，未发详情接口请求。
- Pack 003 full run 中断：执行 `raw/detail-live-detail-ab-pack-003-run-2026-05-17.json`，在第 10 个目标停机，结果 `status=stopped`、`completed_jobs=9/149`、`stopReason=exception`；job raw 目录 `raw/detail-live/detail-ab-pack-003/` 下 `job-*.json` 共 `9` 个。
- 中断原因：`reports/interruption-detail-detail-ab-pack-003-2026-05-17.json` 显示 `stopError=Connection timed out`，失败点 `failedIndex=9`、`failedCandidateId=973`、`failedPlatformId=231560414`；失败前后页面健康均为 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- continuation：已生成 `raw/detail-targets/detail-live-detail-ab-pack-003-continuation-after-exception-plan.json`，`resume_from.index=9`，剩余 `140` 人；已成功的 `9` 个 job raw 保留为恢复点。
- 下游边界：Pack 003 为 partial capture，未运行 `detail-wave dry-run`、未 apply、未生成 final report；campaign DB `maimai_detail_capture` 仍为 `298`，没有新增 Pack 003 写入。
- 安全核验：无 detail/search live gate Python 进程残留；`git diff --check` -> PASS；主库 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`，campaign DB 时间戳仍为 `2026-05-17 01:19:50`。
- 用户确认：该中断判断为网络不稳定导致的 timeout，不是业务风控熔断；允许从 continuation 重试超时点。
- Pack 003 continuation：复用原 pack plan 和同一 capture out，从已有 `9` 个 job raw 后继续；最终 `status=completed`、`completed_jobs=149/149`、`stopReason=null`。
- Pack 003 dry-run：`reports/detail-wave-detail-ab-pack-003-dry-run.json/md` 已生成；`matched=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Pack 003 apply：`reports/detail-wave-detail-ab-pack-003-apply.json/md` 已生成；`matched=149`、`written=149`、`verified_candidate_ids=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Ledger 与 DB 核验：`state/import-ledger.jsonl` 已写入 `detail_apply started/completed` 两条 Pack 003 记录；campaign DB `maimai_detail_capture` 行数从 `298` 增至 `447`，`candidate_details=2648`。
- 主库边界：apply 后 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；写入只发生在 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`，该库时间戳更新为 `2026-05-17 02:01:51`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_detail_import.py tests/test_maimai_ai_infra_pipeline.py -q` -> `49 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_detail_import.py scripts/maimai_ai_infra_pipeline.py` -> PASS；`git diff --check` -> PASS；无 detail/search live gate Python 进程残留。

# AI Infra V2 A/B 详情 Pack 004 执行（2026-05-17）

> 目标：执行最后一个 A/B 详情任务包 `detail-ab-pack-004`。保持安全边界：只连接已打开的人才银行页，不自动导航/刷新/点击业务页面；详情数据只写 campaign DB，不写 `data/talent.db`。用户已确认纯网络 timeout 可从恢复点重试。

## 执行计划

- [x] 预检：确认 Pack 004 尚未抓取、无 detail/search live gate 进程残留，并记录 `data/talent.db` 与 campaign DB 时间戳。
- [x] 运行 Pack 004 page health check，要求 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- [x] 执行 `detail-ab-pack-004` 全量详情抓取；如遇熔断，只保留已成功 job raw、capture、continuation plan 和 interruption report；如仅为 timeout，按用户授权从恢复点重试。
- [x] 若全量抓取完成，运行 Pack 004 `detail-wave dry-run`，只在 `dry_run_clean` 后继续。
- [x] 若 dry-run clean，apply 到 campaign DB，并核验 ledger、detail capture 行数和主库未修改。
- [x] 运行必要验证，确认无 live gate 进程残留，回填 Review。

## Review

- Pack 004 第一次中断：执行到 `completed_jobs=46/149` 后停机，`stopReason=exception`；失败点 `failedIndex=46`、`failedCandidateId=147`、`failedPlatformId=235441789`，错误为页面 `fetch` 抛 `TypeError: Failed to fetch`。失败前后页面健康均为 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`，无 HTTP 风控状态码；已生成 continuation，从 index `46` 继续。
- Pack 004 continuation：从 index `46` 继续后成功完成；最终 capture `raw/detail-live-detail-ab-pack-004-run-2026-05-17.json` 为 `status=completed`、`completed_jobs=149/149`、`stopReason=null`、`partial=false`，job raw 共 `149` 个。
- Pack 004 dry-run：`reports/detail-wave-detail-ab-pack-004-dry-run.json/md` 已生成；`matched=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Pack 004 apply：`reports/detail-wave-detail-ab-pack-004-apply.json/md` 已生成；`matched=149`、`written=149`、`verified_candidate_ids=149`、`unmatched=0`、`failed_jobs=0`、`apply_blockers=[]`、`capture_blockers=[]`。
- Ledger 与 DB 核验：`state/import-ledger.jsonl` 已写入 `detail_apply started/completed` 两条 Pack 004 记录；campaign DB `maimai_detail_capture` 行数从 `447` 增至 `596`，覆盖四包 A/B 目标总数，`candidate_details=2648`。
- 主库边界：apply 后 `data/talent.db` 时间戳仍为 `2026-05-14 13:54:21`；写入只发生在 `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`，该库时间戳更新为 `2026-05-17 02:42:13`。
- 验证：`python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_detail_import.py tests/test_maimai_ai_infra_pipeline.py -q` -> `49 passed`；`python -m py_compile scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_detail_import.py scripts/maimai_ai_infra_pipeline.py` -> PASS；`git diff --check` -> PASS；无 detail/search live gate Python 进程残留。

# 人才库同步包导出（2026-05-17）

> 目标：按 `talent-library` 多端 bundle 同步契约，从 `data/talent.db` 导出可传输的 zip 同步包，并校验 bundle 完整性。

## 执行计划

- [x] 读取 `talent-library` workflow、数据契约和同步手册，确认导出入口与默认参数。
- [x] 确认主库 `data/talent.db` 存在。
- [x] 执行 `python scripts/talent_sync.py export --db data/talent.db --out data/output/talent-sync-full.zip`。
- [x] 执行 `python scripts/talent_sync.py verify-bundle --bundle data/output/talent-sync-full.zip`。
- [x] 回填导出文件路径、文件大小和校验结果。

## Review

- 导出前状态：`python scripts/talent_sync.py status --db data/talent.db` -> `node_id=f10862a8-f87f-498e-83c6-fd168448da08`、候选人 `5453`、导入记录 `1`。
- 导出结果：`python scripts/talent_sync.py export --db data/talent.db --out data/output/talent-sync-full.zip` -> `导出完成`，模式 `full`，候选人 `5453`。
- 文件位置：`data/output/talent-sync-full.zip`；初版大小 `14077261` 字节，后续导入验证发现 JSONL Unicode 行分隔符问题，已修复并重新导出。
- 当前正式包：大小 `14077270` 字节，更新时间 `2026-05-17 12:56:10`；旧包已留存到 `data/backups/talent-sync-full-before-jsonl-fix-20260517-125022.zip`。
- 完整性校验：`python scripts/talent_sync.py verify-bundle --bundle data/output/talent-sync-full.zip` -> `bundle 校验通过`。

# 人才库同步包导入验证与备份（2026-05-17）

> 目标：验证 `data/output/talent-sync-full.zip` 可以正常导入，同时先备份主库；主库只做 dry-run，真实 apply 只在备份副本上执行。

## 执行计划

- [x] 确认同步包存在，并确认 `scripts/talent_sync.py import` 的 dry-run/apply 参数。
- [x] 备份当前主库 `data/talent.db` 到 `data/backups/`。
- [x] 复制一份导入测试库，避免在主库上做真实写入。
- [x] 执行 `verify-bundle` 校验同步包完整性。
- [x] 对主库执行 dry-run import，确认导入预览可生成。
- [x] 对测试库执行 apply import，确认真实导入流程可完成。
- [x] 核对主库未执行 apply，并回填结果。

## Review

- 初次验证：旧包 `verify-bundle` 通过，但主库 dry-run 报 `JSONDecodeError: Unterminated string`，定位到 `data/candidate_details.jsonl` 第 1525 条含合法 `U+2028` 行分隔符，被 `_read_jsonl().splitlines()` 误拆。
- 修复：`scripts/talent_sync.py` 的 JSONL 读取改为只按 `\n` 分隔；导出端将 `U+2028/U+2029` 写成 JSON 转义序列；新增回归测试 `test_import_bundle_handles_unicode_line_separator_inside_json_string`。
- 新包：重新执行 `python scripts/talent_sync.py export --db data/talent.db --out data/output/talent-sync-full.zip` -> `导出完成`，候选人 `5453`，当前文件大小 `14077270` 字节。
- 备份：最终主库备份为 `data/backups/talent-db-backup-final-20260517-125819.db`；导入测试库为 `data/backups/talent-db-import-test-final-20260517-125819.db`。
- 新包完整性：`python scripts/talent_sync.py verify-bundle --bundle data/output/talent-sync-full.zip` -> `bundle 校验通过`；逐文件 JSONL 解析通过，且 `literal_unicode_separators=[]`。
- 主库 dry-run：`python scripts/talent_sync.py import --db data/talent.db --bundle data/output/talent-sync-full.zip` -> `新建候选人=0，合并候选人=5453，冲突候选人=0，跳过候选人=0`。
- 测试库 apply：`python scripts/talent_sync.py import --db data/backups/talent-db-import-test-final-20260517-125819.db --bundle data/output/talent-sync-full.zip --apply --confirm "确认同步人才库"` -> `新建候选人=0，合并候选人=5453，冲突候选人=0，跳过候选人=0`。
- 主库核对：`python scripts/talent_sync.py status --db data/talent.db` -> 候选人 `5453`、导入记录 `1`；测试库导入记录为 `2`，说明真实 apply 发生在测试库而非主库。
- 验证：`python -m pytest tests/test_talent_sync.py -q` -> `37 passed`；`python -m py_compile scripts/talent_sync.py` -> PASS；`git diff --check` -> PASS。

# 飞书 CLI 安装（2026-05-18）

> 目标：按飞书/开放平台官方入口安装本机 CLI，并验证命令可用；不代用户完成需要账号授权的登录步骤。

## 执行计划

- [x] 确认官方安装入口和本机 Node/npm 环境。
- [x] 执行官方安装命令安装飞书 CLI。
- [x] 验证 CLI 命令、版本和 PATH 可用性。
- [x] 回填 Review，记录后续登录/配置步骤。

## Review

- 本机环境：Node `v24.13.0`，npm registry 为 `https://registry.npmjs.org/`，全局 npm prefix 为 `C:\Users\Administrator\AppData\Roaming\npm`。
- 官方包确认：npm `@larksuite/cli@latest` 当前为 `1.0.32`，bin 为 `lark-cli`。
- 安装命令：`npm install -g @larksuite/cli@latest` -> `added 7 packages in 2m`。
- PATH 验证：`Get-Command lark-cli` -> `C:\Users\Administrator\AppData\Roaming\npm\lark-cli.ps1`。
- 版本验证：`lark-cli --version` -> `lark-cli version 1.0.32`；`lark-cli --help` 正常列出 `api/auth/config/docs/im/base/sheets/wiki` 等命令。
- Agent skills：按 `lark-cli --help` 的官方提示执行 `npx -y skills add larksuite/cli -g -y`，安装器识别 `codex` 环境并安装 `25` 个 `lark-*` skills 到 `C:\Users\Administrator\.agents\skills`。
- 健康检查：`lark-cli doctor` 中 `cli_version` 和 `cli_update` 通过；`config_file` 失败为预期状态，原因是尚未配置飞书应用和授权。后续需要用户提供 app 信息或完成 `lark-cli config init --new` / `lark-cli auth login` 授权流程。
- 后续授权：`lark-cli auth login` 初次失败提示未配置；已按 CLI 提示执行 `lark-cli config init --new --lang zh`，用户完成网页配置后返回 `OK: 应用配置成功`，App ID 为 `cli_aa80ddcb80789ccd`。
- 登录方式：`lark-cli auth login --recommend --no-wait --json` 生成 device flow 后，使用 `lark-cli auth login --device-code ...` 等待用户授权；最终返回 `OK: 授权成功`，用户为 `金光华`。
- 授权验证：`lark-cli auth status` -> `tokenStatus=valid`，`expiresAt=2026-05-18T10:49:15+08:00`，`refreshExpiresAt=2026-05-25T08:49:15+08:00`；`lark-cli profile list` 显示 active profile 为 `cli_aa80ddcb80789ccd`。
- 最终健康检查：`lark-cli doctor` -> `ok=true`；`cli_version`、`cli_update`、`config_file`、`app_resolved`、`token_exists`、`token_local`、`token_verified`、`endpoint_open`、`endpoint_mcp` 全部通过。

# 飞书 CLI 能力介绍云文档（2026-05-18）

> 目标：创建一篇飞书云文档，介绍飞书 CLI 的主要能力，并结合当前工作流给出优先使用建议。

## 执行计划

- [x] 确认 `docs +create` 的 v2 文档创建参数和格式要求。
- [x] 编写 XML 文档源稿，覆盖 CLI 能力、身份/权限边界、推荐场景和上手路径。
- [x] 使用 `lark-cli docs +create --api-version v2` 创建云文档。
- [x] 读取新文档并运行健康检查，回填文档 URL 和验证结果。

## Review

- 源稿文件：`tasks/feishu-cli-capabilities-doc.xml`。
- 格式检查：用 XML root wrapper 解析源稿 -> `XML_OK`；`lark-cli docs +create --api-version v2 --parent-position my_library --content '@tasks/feishu-cli-capabilities-doc.xml' --dry-run` 成功生成请求预览。
- 创建命令：`lark-cli docs +create --api-version v2 --parent-position my_library --content '@tasks/feishu-cli-capabilities-doc.xml'`。
- 创建结果：`ok=true`，`identity=user`，`document_id=SY3JdOuQootb1LxJwT6cld9Ln3f`，`revision_id=3`，`warnings=[]`。
- 文档 URL：`https://sq8org1v4k6.feishu.cn/docx/SY3JdOuQootb1LxJwT6cld9Ln3f`。
- 读取验证：`lark-cli docs +fetch --api-version v2 --doc 'https://sq8org1v4k6.feishu.cn/docx/SY3JdOuQootb1LxJwT6cld9Ln3f' --detail with-ids` -> `ok=true`，标题、表格、grid、checkbox、pre 代码块均可读回。
- 健康检查：`lark-cli doctor` -> `ok=true`，CLI、config、token、open endpoint、MCP endpoint 全部通过。

# AI Infra campaign 飞书交付包（2026-05-18）

> 目标：为 AI Infra campaign 生成飞书交付包，包括摘要云文档、候选人 Sheet 和 outreach queue Sheet；使用现有 reports artifacts，不重新跑真实采集，不写本地 DB。

## 执行计划

- [x] 核验 final delivery/outreach artifacts、行数、标签分布和质量审计状态。
- [x] 生成候选人 Sheet 源数据和 outreach queue Sheet 源数据，避免上传原始 DB/zip 或未筛选 raw。
- [x] 创建候选人 Sheet，并写入表头和全部行。
- [x] 创建 outreach queue Sheet，并写入表头和全部行。
- [x] 创建摘要云文档，链接两张 Sheet，写明交付范围、关键指标、使用建议和风险边界。
- [x] 读取验证云文档和两张 Sheet，运行 `lark-cli doctor`，回填 Review。

## Review

- 使用现有 reports artifacts：`final-search-report-ab-packs-001-004.json`、`final-detail-report-ab-packs-001-004.json`、`outreach-execution-queue-ab-packs-001-004.csv`、`outreach-quality-audit-p0-p1-top30-ab-packs-001-004.json`；未重新跑真实采集，未读取或上传 SQLite DB/zip/raw。
- 摘要云文档：`https://sq8org1v4k6.feishu.cn/docx/Ja4zdyvXaoky4XxORDccQrK8n7g`；`docs +fetch --api-version v2 --detail with-ids` -> `ok=true`，可读回标题、漏斗、方向覆盖、详情包状态和两张 Sheet 链接。
- 候选人 Sheet：`https://sq8org1v4k6.feishu.cn/sheets/N08Qs52LJhCR6dtlm3rcmIW6nng`；`sheet_id=2f04c5`，`row_count=597` 含表头，候选人数据 `596` 行，`column_count=24`，表头冻结 `frozen_row_count=1`。
- 候选人分布：`强推荐=358`、`推荐=160`、`观察=77`、`不推荐=1`；优先级视图 `P0=150`、`P1=300`、`P2=145`，另有 `1` 个不推荐候选人无外联优先级。
- Outreach queue Sheet：`https://sq8org1v4k6.feishu.cn/sheets/PsnSs9CFqhPw7xtvqqPcdA1AnOh`；`sheet_id=8a18ce`，`row_count=596` 含表头，外联队列 `595` 行，`column_count=22`，表头冻结 `frozen_row_count=1`。
- Outreach 队列分布：`P0=150`、`P1=300`、`P2=145`；新增执行列 `owner/status/last_touch_at/next_followup_at/notes`，默认 `status=待联系`。
- 质量审计：P0/P1 各抽样 `30` 人，`issue_counts={}`，`duplicate_candidate_ids=[]`；摘要文档已写明候选人/外联数据属于敏感信息，分享前需确认飞书权限范围。
- 本地结果记录：`data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/feishu-delivery-package-2026-05-18.json`；源 CSV/XML 写在同一 reports 目录，属于 `data/campaigns/` 忽略范围。
- 验证：候选人 Sheet `sheets +read --sheet-id 2f04c5 --range A1:X5` -> `ok=true`；outreach Sheet `sheets +read --sheet-id 8a18ce --range A1:V5` -> `ok=true`；`lark-cli doctor` -> `ok=true`；`git diff --check` -> PASS。
- 中途修复：Python 子进程不能解析 `lark-cli` shim，已改为直接调用 Node CLI 入口；`sheets +append` 多行写入不能用 `<sheetId>!A1` 单格 range，已改为 `--range <sheet_id>`；两项已记录到 `memory/error-log.md`。
- 残留说明：调试早期因解析/append 参数失败，飞书云空间里可能存在少数只含表头的候选人草稿 Sheet；它们未写入交付包、不在摘要文档中引用。如需清理，需要额外走搜索授权和删除确认流程。

# 脉脉扩展 popup 页面优化（2026-05-18）

> 目标：按最新产品要求精简扩展 popup，只保留“人选列表采集”和“批量详情”两条主路径；被动拦截和逐页采集导出必须拆成独立入口，详情采集界面隐藏低频/内部控制项。

## 执行计划

- [x] 梳理现有 `popup.html/js/css`、后台导出消息和扩展契约测试，确认主动搜索、DOM 抓取、本地任务包等入口的依赖。
- [x] 优化“人选列表采集”标签：移除主动搜索/DOM 抓取 tab，改名、拆分被动拦截与逐页采集导出，修复刷新按钮统计源，增加逐页请求执行日志。
- [x] 优化“批量详情”标签：隐藏安全策略、每日上限、本地任务包加载和执行区域；调整导入/开始/终止/进度/统计文案为中文业务表达。
- [x] 更新 `tests/test_maimai_scraper_extension.py` 静态契约，覆盖新 UI 与拆分导出入口。
- [x] 运行扩展 JS 语法检查、聚焦测试和必要回归，回填 Review。

## Review

- popup 标题、manifest name/default title 已改为“脉脉人选数据采集”；manifest 描述同步去掉主动搜索、DOM 抓取的产品表述。
- “人选列表采集”仅保留被动拦截与逐页采集入口；被动导出走 `exportCaptureJson`/`chrome.storage.local` 池，逐页导出走 `exportPagerJson`/`PagerDB` 池。
- 刷新按钮改为读取 `getScraperSummary`，可覆盖 PagerDB 中的逐页采集联系人；失败时回退 `chrome.storage.local`。
- 逐页采集新增请求执行日志区，实时记录启动、每页完成、暂停、失败、停止和完成事件。
- “批量详情”隐藏策略、每日上限、本地任务包加载、暂停、继续、刷新、重置；导入/开始/终止和进度文本已改为中文业务文案。
- 验证：扩展 JS `node --check` 全部通过；`python -m pytest tests/test_maimai_scraper_extension.py -q` -> `39 passed`；`python -m pytest tests scripts -q` -> `634 passed, 1 warning`；`git diff --check` -> PASS。
- 残留：全量回归 warning 为既有 `scripts/test_boss.py` event loop deprecation；工作树中 `memory/error-log.md`、`tasks/feishu-cli-capabilities-doc.xml` 是本次开始前已有脏状态，未纳入本次修改。

# 扩展列表导出导入兼容检查（2026-05-18）

> 目标：确认“导出被动拦截 JSON”和“导出人选列表 JSON”的人选数据格式是否一致，以及是否都可以直接走 `talent-library import` 导入人才库。

## Review

- 代码结论：两个导出文件的顶层 envelope 不完全一致；被动拦截导出包含 `metadata.export_type=capture`、`contacts`、`details`、`requests`，逐页列表导出包含分页 `metadata`、`contacts`。但 `contacts[]` 都保留脉脉原始联系人对象，字段来源一致。
- 导入入口：`scripts/talent_library.py import` 的 `_items_from_payload()` 优先读取顶层 `contacts`，会忽略 `metadata/details/requests`；后续统一走 `MaimaiAdapter.map_to_schema()` 和 `TalentDB.batch_ingest()`。
- 可导入前提：每条联系人至少要有 `name`；有 `id` 时会写入 `source_profiles.platform_id`，否则只能按姓名/公司/职位等弱键去重，不建议作为正式导入数据。
- 已补回归：`tests/test_talent_library_cli.py::test_import_entry_accepts_extension_capture_and_pager_export_shapes`，分别用被动拦截和逐页列表两种导出形状做 `talent-library import` dry-run，结果均 `raw_contacts=1`、`unique_contacts=1`、`created=1`、`pre_errors=0`，且 dry-run 不写库。
- 验证：`python -m pytest tests/test_talent_library_cli.py::test_import_entry_accepts_extension_capture_and_pager_export_shapes -q` -> `1 passed`；`python -m pytest tests/test_talent_library_cli.py -q` -> `10 passed`；`python -m pytest tests/test_maimai_scraper_extension.py tests/test_talent_library_cli.py -q` -> `49 passed`；`python -m pytest tests scripts -q` -> `635 passed, 1 warning`；`git diff --check` -> PASS。
