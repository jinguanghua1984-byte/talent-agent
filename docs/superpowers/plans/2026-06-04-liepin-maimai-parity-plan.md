# 猎聘寻访对标脉脉能力补齐 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让猎聘寻访从 P1 详情 smoke 进入可验收、可恢复的 campaign 化链路，第一期先补离线详情 raw dry-run/summary，为后续 Campaign DB import 做前置。

**Architecture:** 保持猎聘执行面为 CDP 页面内 fetch，但第一期新增 `scripts/liepin_detail_dry_run.py` 只读本地 `raw/detail-live/<pack_id>/job-*.json` 与 target pack。dry-run 输出字段完整性、隐私保护、缺 raw、partial/blocked job 和后续 apply blocker 统计，不连接浏览器，不写 Campaign DB，不写主库。

**Tech Stack:** Python stdlib, pytest, existing `scripts.liepin_campaign` campaign paths, existing `scripts.liepin_detail_live_gate` job schema.

---

## 对标结论

脉脉现有闭环包括：需求合同、宽召回 adaptive search units、wave planning、search live gate、search dry-run/apply 到 Campaign DB、详情优先级、详情 pack、详情 live、详情 dry-run/apply、summary/rank/delivery、飞书发布，以及人工边界下的主库同步。

猎聘当前已具备：`jobId` 初始化、独立 CDP Chrome、5 页搜索 smoke、搜索标准化、候选池诊断、`detail_p0` 目标包、10 人详情 smoke、被动详情 API 校准。

猎聘缺失能力按优先级排列：

1. 详情 raw 离线 dry-run/summary。
2. 搜索结果导入 Campaign DB。
3. 详情 apply 到 Campaign DB。
4. 猎聘 full detail pack planning 和恢复执行。
5. 猎聘宽召回 adaptive 搜索规划。
6. 基于 Campaign DB 的 summary/rank/delivery。
7. 人工确认下的主库 sync bundle 和冲突处理。

第一期只实现第 1 项。

## File Structure

- Create `scripts/liepin_detail_dry_run.py`: 离线读取 target pack 与 detail job raw，输出 `reports/detail-dry-run.json` 和 `reports/detail-dry-run.md`。
- Create `tests/test_liepin_detail_dry_run.py`: 覆盖 clean smoke、隐私保护、缺 raw、partial/blocked raw、报告脱敏和 CLI。
- Modify `scripts/liepin_campaign_orchestrator.py`: 增加 `detail-dry-run` 子命令。
- Modify `tests/test_liepin_campaign_orchestrator.py`: 覆盖 orchestrator 委托。
- Modify `agents/skills/liepin-talent-search-campaign/SKILL.md`: 写明详情 smoke 后可运行离线 dry-run，但仍不写数据库。
- Modify `agents/workflows/liepin-unattended-campaign/AGENT.md`: 在 P1 smoke 后增加 dry-run 阶段，Campaign DB apply 仍作为下一阶段设计。
- Modify `tests/test_agent_architecture.py`: 加入 detail dry-run 文档约束。
- Modify `tasks/todo.md`: 跟踪本轮计划、验证和 review。

## Task 1: Detail Raw Dry-Run Tests

- [x] 写 `tests/test_liepin_detail_dry_run.py`，构造 target pack 和 job raw。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_detail_dry_run.py -q`，预期 import 失败。
- [x] 实现 `scripts/liepin_detail_dry_run.py` 的最小 API：
  - `build_detail_dry_run(campaign_root, target_pack)`
  - `dry_run_detail_jobs(campaign_root, target_pack)`
  - CLI `python -m scripts.liepin_detail_dry_run --campaign-root ... --target-pack ...`
- [x] GREEN：同一测试文件通过。

## Task 2: Orchestrator And Contract Docs

- [x] 写 orchestrator 委托测试 `test_detail_dry_run_command_delegates_to_dry_run`。
- [x] RED：聚焦运行该测试，预期 `detail-dry-run` 命令不存在。
- [x] 在 `scripts/liepin_campaign_orchestrator.py` 增加 import、parser 和 dispatch。
- [x] 更新猎聘 skill/workflow 与架构测试，明确 `detail-dry-run` 不触发猎聘请求、不写 Campaign DB、不写主库。
- [x] GREEN：运行猎聘聚焦测试和架构测试。

## Task 3: Smoke Data Verification

- [x] 对已有 campaign 运行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-dry-run --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json
```

- [x] 预期报告显示 10 个 target，9 个可入库详情，1 个 `privacy_protected`，`clean=true`，`no_database_write=true`。
- [x] 确认 `reports/detail-dry-run.md` 不包含 `showresumedetail`、`ck_id`、`sk_id`、`fk_id`。

## Task 4: Final Verification

- [x] 运行 `.venv/bin/python -m pytest tests/test_liepin_* tests/test_agent_architecture.py -q`。
- [x] 运行 `.venv/bin/python -m pytest tests -q`。
- [x] 运行敏感存储扫描。
- [x] 运行 `git diff --check`。
- [x] 更新 `tasks/todo.md` Review。

## Task 5: Search Result Campaign DB Import

- [x] 写 `tests/test_liepin_search_import.py`，覆盖 dry-run 不创建 DB、apply 写 campaign-local DB、重复平台 ID 去重、masked name 防误合并、报告脱敏和 CLI。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_search_import.py tests/test_liepin_campaign_orchestrator.py::test_import_search_commands_delegate_to_importer -q`，预期 import 失败。
- [x] 新增 `scripts/liepin_search_import.py`：
  - `dry_run_search_import(campaign_root)`：读取 `structured/candidate-summaries.jsonl`，在临时 DB 中模拟 `TalentDB.batch_ingest`，写 `reports/search-import-dry-run.json/.md`。
  - `apply_search_import(campaign_root, confirm)`：要求 `确认写入猎聘搜索结果`，只写 `data/campaigns/<campaign_id>/talent.db`，写 `reports/search-import-apply.json/.md`，追加 `state/import-ledger.jsonl`。
  - `search_summary_to_ingest_payload(row)`：将猎聘摘要映射为 TalentDB ingest payload，并移除 `ck_id/sk_id/fk_id/sss/pgRef` 等平台 token。
- [x] 在 `scripts/liepin_campaign_orchestrator.py` 增加 `import-search-dry-run` 和 `import-search-apply`。
- [x] 更新猎聘 skill/workflow 与架构测试，明确 search import dry-run/apply 不触发猎聘请求、不读取浏览器敏感存储、不写主库。

## Task 6: Search Import Runtime Verification

- [x] 对 `data/campaigns/liepin-smoke-2026-06-03-job-75703601` 运行 `import-search-dry-run`：`raw_count=150`、`unique_count=150`、`created=150`、`errors=0`。
- [x] 运行 `import-search-apply --confirm 确认写入猎聘搜索结果`：写入 campaign-local `talent.db`，`created=150`、`errors=0`。
- [x] 校验 Campaign DB：`PRAGMA integrity_check=ok`、`candidates=150`、`source_profiles(platform='liepin')=150`、`pending_merges=0`。
- [x] 校验主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 校验 search import reports 和 Campaign DB `profile_url/raw_profile` 不包含详情 URL token。
- [x] 验证：search import 聚焦测试 `5 passed`；猎聘聚焦 + 架构测试 `122 passed`；全量测试 `1187 passed, 1 warning`；`git diff --check` 通过。

## Task 7: Detail Apply Into Campaign DB

- [x] 写 `tests/test_liepin_detail_dry_run.py` 详情 apply 用例，覆盖确认文本、只写 campaign-local DB、隐私保护跳过、blocker 拒绝、缺 campaign DB 拒绝、ledger 记录和 raw_data 脱敏。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_detail_dry_run.py tests/test_liepin_campaign_orchestrator.py::test_detail_apply_command_delegates_to_detail_import -q`，预期 `CONFIRM_TEXT/apply_detail_jobs` 缺失。
- [x] 在 `scripts/liepin_detail_dry_run.py` 增加 `apply_detail_jobs(campaign_root, target_pack, confirm)`：
  - 要求 `确认写入猎聘详情`。
  - 复跑 `build_detail_dry_run`，非 clean 直接拒绝。
  - 只查找 campaign-local `source_profiles(platform='liepin', platform_id=...)`。
  - 将 `resumeDetailVo.workExperiences/eduExperiences/projectExperiences` 写入 `candidate_details`。
  - `raw_data.liepin_detail_capture` 不保存详情 URL、ck/sk/fk、rawPreview 或浏览器敏感存储。
  - 写 `reports/detail-apply.json/.md` 和 `state/import-ledger.jsonl`。
- [x] 在 orchestrator 增加 `detail-apply` 子命令。
- [x] 更新猎聘 skill/workflow 与架构测试，明确详情 apply 只服务于 campaign-local DB 闭环。

## Task 8: Detail Apply Runtime Verification

- [x] 对 `data/campaigns/liepin-smoke-2026-06-03-job-75703601` 运行 `detail-apply --confirm 确认写入猎聘详情`：`matched=9`、`written=9`、`unmatched=0`、`privacy_protected_count=1`。
- [x] 校验 Campaign DB：`PRAGMA integrity_check=ok`、`candidate_details=9`、`candidates.data_level='detailed'=9`、`liepin_detail_capture=9`。
- [x] 校验主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 校验 Campaign DB `candidate_details.raw_data` 和 detail apply reports 不包含详情 URL token 或 rawPreview。
- [x] 验证：P3 聚焦测试 `7 passed`；猎聘聚焦 + 架构测试 `125 passed`；全量测试 `1190 passed, 1 warning`；`git diff --check` 通过。

## Task 9: Campaign DB Local Summary

- [x] 写 `tests/test_liepin_campaign_summary.py`，覆盖只读 campaign DB、候选/详情计数、分布统计、报告脱敏、缺 DB 拒绝和 CLI。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_campaign_summary.py tests/test_liepin_campaign_orchestrator.py::test_campaign_summary_command_delegates_to_summary -q`，预期缺 `scripts.liepin_campaign_summary`。
- [x] 新增 `scripts/liepin_campaign_summary.py`：
  - `build_campaign_summary(campaign_root)` 使用 SQLite readonly 连接读取 campaign-local `talent.db`。
  - `write_campaign_summary(campaign_root)` 写 `reports/campaign-summary.json/.md`。
  - 摘要包含候选总数、来源档案数、详情数、详情覆盖率、data_level、城市/学历/年限/公司/职位 Top 和详情质量。
  - 报告明确不是推荐报告，不生成外联队列，不发布飞书，不写主库。
- [x] 在 orchestrator 增加 `campaign-summary` 子命令。
- [x] 更新猎聘 skill/workflow 与架构测试。

## Task 10: Campaign Summary Runtime Verification

- [x] 对 `data/campaigns/liepin-smoke-2026-06-03-job-75703601` 运行 `campaign-summary`：`candidate_count=150`、`source_profile_count=150`、`detail_count=9`、`detail_coverage_ratio=0.06`、`data_level_counts={core:141,detailed:9}`。
- [x] 校验主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 校验 summary reports 不包含详情 URL token、rawPreview 或 secret。
- [x] 验证：P4 聚焦测试 `5 passed`；猎聘聚焦 + 架构测试 `130 passed`；全量测试 `1195 passed, 1 warning`；`git diff --check` 通过。

## Task 11: Full Detail Pack Planning

- [x] 写 `tests/test_liepin_detail_targets.py` full pack planning 用例，覆盖多优先级、每包拆分、扣除 terminal jobs、分包 metadata、报告脱敏。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_detail_targets.py tests/test_liepin_campaign_orchestrator.py::test_plan_detail_packs_command_delegates_to_planner -q`，预期 `plan_detail_packs` 缺失。
- [x] 扩展 `scripts/liepin_detail_targets.py`：
  - `plan_detail_packs(campaign_root, priorities, pack_size, scope, exclude_completed)`。
  - 默认 priority 为 `detail_p0,detail_p1`，默认扣除 terminal detail jobs。
  - 输出 `raw/detail-targets/detail-targets-<scope>.json` 和 `raw/detail-targets/detail-<scope>-pack-*.json`。
  - 写 `reports/detail-pack-plan.json/.md`，reports 不包含详情 URL token。
- [x] 在 orchestrator 增加 `plan-detail-packs` 子命令。
- [x] 更新猎聘 skill/workflow 与架构测试，明确该阶段只做 planning，后续 live detail 扩大执行必须另起确认点。

## Task 12: Full Detail Pack Planning Runtime Verification

- [x] 对 `data/campaigns/liepin-smoke-2026-06-03-job-75703601` 运行 `plan-detail-packs --priorities detail_p0,detail_p1 --pack-size 100 --scope p0-p1`。
- [x] 结果：`selected_count=115`、`excluded_completed_count=10`、`priority_counts={detail_p0:54,detail_p1:61}`、`pack_count=2`，分包为 100 和 15。
- [x] 校验 all-targets 和分包均标记 `no_live_request=true`、`no_database_write=true`。
- [x] 校验 `reports/detail-pack-plan.json/.md` 不包含详情 URL token、rawPreview 或 secret。
- [x] 验证：P5 聚焦测试 `14 passed`；猎聘聚焦 + 架构测试 `133 passed`；全量测试 `1198 passed, 1 warning`；`git diff --check` 通过。

## Task 13: Full Detail Live Execution Recovery Framework

- [x] 写 `tests/test_liepin_detail_live_gate.py` full pack live runner 用例，覆盖非 smoke pack、pack 专属 summary、`privacy_protected` 继续、terminal job 跳过、全部 terminal 时不连接 CDP。
- [x] RED：运行 `.venv/bin/python -m pytest tests/test_liepin_detail_live_gate.py tests/test_liepin_campaign_orchestrator.py::test_run_live_detail_pack_command_delegates_to_live_gate -q`，预期缺 `run_live_detail_pack`。
- [x] 泛化 `scripts/liepin_detail_live_gate.py`：
  - `run_live_detail_pack(...)` 支持单包上限 100。
  - 仍复用 `resume-view` 页面内 fetch、安全 header 清洗和详情 smoke 停机规则。
  - 已完成或 `privacy_protected` 的 terminal job 跳过并写 `detail_skipped_terminal`。
  - 全部 target 已经 terminal 时不连接 CDP，写 pack summary 并追加 `detail_pack_already_terminal`。
  - pack summary 写 `reports/detail-pack-<pack_id>-summary.json/.md`，不覆盖 `detail-smoke-summary`。
- [x] 在 `scripts/liepin_campaign_orchestrator.py` 增加 `run-live-detail-pack` 子命令。
- [x] 更新猎聘 skill/workflow 与架构测试，明确 full detail live 仍不写 Campaign DB、不写主库、不生成推荐或交付。

## Task 14: Full Detail Live Framework Verification

- [x] 运行 P6 聚焦测试：`29 passed`。
- [x] 运行猎聘聚焦 + 架构测试：`136 passed`。
- [x] 运行全量测试：`1201 passed, 1 warning`，warning 为既有 `tests/test_boss.py` event loop deprecation。
- [x] 运行敏感存储扫描和 `git diff --check`；敏感存储扫描只命中测试负断言和文档禁止条款，`git diff --check` 通过。
- [x] 更新 `tasks/todo.md` Review。

## Task 15: Full Detail Pack-001 Live Limit-5 Execution

- [x] 预检 `raw/detail-targets/detail-p0-p1-pack-001.json`：schema 为 `liepin_detail_pack_plan_v1`，共 100 个 target，前 5 个 target 无 terminal raw。
- [x] 预检 `state/request-template.json` 存在，主库 `data/talent.db` 时间戳为 `Jun  1 20:32:52 2026`。
- [x] 发现并修复 full pack schema 兼容问题：`run_live_detail_pack` 接受 `liepin_detail_pack_plan_v1`，smoke runner 默认仍只接受 smoke schema。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 5 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit5-20260604
```

- [x] 结果：`status=completed`、`completed=5`、`failed=0`、`blocked=false`、`skipped_terminal=0`。
- [x] 新增 raw：`raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-004.json`，5 条均为 `status=done`、响应 `flag=1`。
- [x] ledger 追加 5 条 `detail_completed`；summary 写 `reports/detail-pack-detail-p0-p1-pack-001-summary.json/.md`。

## Task 16: Full Detail Pack-001 Limit-5 Verification

- [x] pack summary 脱敏扫描无 `showresumedetail`、`ck_id/sk_id/fk_id`、`rawPreview` 或 secret 命中。
- [x] Campaign DB 未写入：`PRAGMA integrity_check=ok`，`candidate_details=9`，`candidates.data_level='detailed'=9`。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 验证：schema 兼容聚焦测试 `2 passed`；P7/P6 聚焦测试 `29 passed`；猎聘聚焦 + 架构测试 `136 passed`；全量测试 `1201 passed, 1 warning`；敏感存储扫描只命中测试负断言和文档禁止条款；`git diff --check` 通过。

## Task 17: Full Detail Pack-001 Continue To Limit-25

- [x] 预检 `detail-p0-p1-pack-001` 前 25 个 target：`done=5`、`missing=20`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 25 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit25-20260604
```

- [x] 结果：`status=completed`、`completed=20`、`skipped_terminal=5`、`failed=0`、`blocked=false`。
- [x] `raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-024.json` 共 25 条均为 `status=done`，响应 `flag=1`。
- [x] ledger 本轮追加 5 条 `detail_skipped_terminal` 和 20 条 `detail_completed`；pack summary 更新为 `targets=25`、`completed=20`、`skipped_terminal=5`。
- [x] summary 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 18: Full Detail Pack-001 Continue To Limit-50

- [x] 预检 `detail-p0-p1-pack-001` 前 50 个 target：`done=25`、`missing=25`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 50 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit50-20260604
```

- [x] 结果：`status=blocked`、`completed=17`、`skipped_terminal=25`、`failed=1`、`stopReason=business_block`。
- [x] 停机点：`job_index=42`、`platform_id=6e626cf7e088O607f6124149f`；已写 `state/detail-live-detail-p0-p1-pack-001-continuation-after-business_block.json` 和 interruption 报告。
- [x] 当前 `raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-041.json` 共 42 条均为 `status=done`；`job-042.json` 到 `job-049.json` 仍缺失。
- [x] ledger 本轮追加 25 条 `detail_skipped_terminal`、17 条 `detail_completed` 和 1 条 `detail_blocked`。
- [x] summary/interruption 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`；`git diff --check` 通过。

## Task 19: Fix Detail Business Block False Positive And Resume Limit-50

- [x] 根因：P9 `business_block` 是分类器误报；`httpStatus=200`、`flag=1`，关键词 `受限` 出现在候选项目经历正文“场地受限”，不是平台限制提示。
- [x] TDD：新增回归断言，顶层 `msg=受限` 仍阻断，`resumeDetailVo.projectExperiences[].rpdDuty` 中出现“场地受限”不阻断。
- [x] 修复 `classify_detail_result`：业务阻断关键词只扫描 `rawPreview` 和顶层平台提示字段 `msg/message/error/errorMsg/errorMessage/tips/tip/title`，不扫描完整简历正文。
- [x] 恢复执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 50 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit50-resume-20260604
```

- [x] 结果：`status=completed`、`completed=8`、`skipped_terminal=42`、`failed=0`。
- [x] 当前 `raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-049.json` 共 50 条均为 `status=done`，响应 `flag=1`。
- [x] summary 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 验证：误报回归测试 `1 passed`；详情 live gate 测试 `28 passed`；猎聘聚焦 + 架构测试 `136 passed`；全量测试 `1201 passed, 1 warning`；敏感存储扫描只命中测试负断言和文档禁止条款；`git diff --check` 通过。

## Task 20: Full Detail Pack-001 Continue To Limit-75

- [x] 预检 `detail-p0-p1-pack-001` 前 75 个 target：`done=50`、`missing=25`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 75 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit75-20260604
```

- [x] 结果：`status=completed`、`completed=25`、`skipped_terminal=50`、`failed=0`。
- [x] 当前 `raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-074.json` 共 75 条均为 `status=done`，响应 `flag=1`。
- [x] ledger 本轮追加 50 条 `detail_skipped_terminal` 和 25 条 `detail_completed`；pack summary 更新为 `targets=75`、`completed=25`、`skipped_terminal=50`。
- [x] summary 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 21: Full Detail Pack-001 Complete To Limit-100

- [x] 预检 `detail-p0-p1-pack-001` 全 100 个 target：`done=75`、`missing=25`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --cdp-url http://127.0.0.1:9898 --limit 100 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-001-limit100-20260604
```

- [x] 结果：`status=completed`、`completed=25`、`skipped_terminal=75`、`failed=0`。
- [x] 当前 `raw/detail-live/detail-p0-p1-pack-001/job-000.json` 到 `job-099.json` 共 100 条均为 `status=done`，响应 `flag=1`。
- [x] ledger 本轮追加 75 条 `detail_skipped_terminal` 和 25 条 `detail_completed`；pack summary 更新为 `targets=100`、`completed=25`、`skipped_terminal=75`。
- [x] summary 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 22: Full Detail Pack-001 Offline Dry-Run

- [x] 首次运行发现 `detail-dry-run` 仍只接受 smoke target schema；按 TDD 增加 full pack schema 回归测试并修复为同时接受 `liepin_detail_pack_plan_v1`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-dry-run --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json
```

- [x] 结果：`target_count=100`、`job_count=100`、`matched=100`、`ready_for_campaign_db_count=100`、`privacy_protected_count=0`、`missing_raw_count=0`、`unexpected_raw_count=0`、`failed_job_count=0`、`capture_blocker_count=0`、`apply_blocker_count=0`、`clean=true`。
- [x] `reports/detail-dry-run.json/.md` 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=9`、`detailed=9`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 验证：detail dry-run 聚焦测试 `8 passed`；猎聘聚焦 + 架构测试 `137 passed`；全量测试 `1202 passed, 1 warning`；敏感存储扫描只命中测试负断言和文档禁止条款；`git diff --check` 通过。

## Task 23: Full Detail Pack-001 Apply Into Campaign DB

- [x] apply 前预检：pack-001 dry-run `clean=true`、`ready_for_campaign_db_count=100`；Campaign DB 为 `candidates=150`、`source_profiles(liepin)=150`、`candidate_details=9`、`detailed=9`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-apply --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-001.json --confirm 确认写入猎聘详情
```

- [x] 结果：`matched=100`、`written=100`、`unmatched=0`、`privacy_protected_count=0`、`no_main_db_write=true`。
- [x] Campaign DB apply 后：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=109`，`candidates.data_level='detailed'=109`，`liepin_detail_capture=109`。
- [x] Campaign DB `candidate_details.raw_data` 和 `reports/detail-apply.json/.md` 精确脱敏扫描无命中。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] 验证：detail apply 聚焦测试 `8 passed`；猎聘聚焦 + 架构测试 `137 passed`；全量测试 `1202 passed, 1 warning`；敏感存储扫描只命中测试负断言和文档禁止条款；`git diff --check` 通过。

## Task 24: Campaign Summary After Pack-001 Apply

- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator campaign-summary --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601
```

- [x] 结果：`candidate_count=150`、`source_profile_count=150`、`detail_count=109`、`detail_coverage_ratio=0.7266666666666667`、`data_level_counts={detailed:109,core:41}`。
- [x] 详情质量：`with_work_experience=109`、`with_education_experience=109`、`with_project_experience=16`。
- [x] Campaign DB 校验：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=109`，`candidates.data_level='detailed'=109`。
- [x] `reports/campaign-summary.json/.md` 和 Campaign DB `candidate_details.raw_data` 脱敏扫描无详情 URL token、`rawPreview`、secret 或浏览器敏感存储命中。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 25: Full Detail Pack-002 Live Limit-15 Execution

- [x] 预检 `detail-p0-p1-pack-002`：schema 为 `liepin_detail_pack_plan_v1`，共 15 个 target；job index 为 `100-114`，当前 `missing=15`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-pack --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-002.json --cdp-url http://127.0.0.1:9898 --limit 15 --delay-seconds 3 --timeout-seconds 30 --run-id detail-pack-p0-p1-002-limit15-20260604
```

- [x] 结果：`status=completed`、`completed=15`、`skipped_terminal=0`、`failed=0`。
- [x] 当前 `raw/detail-live/detail-p0-p1-pack-002/job-100.json` 到 `job-114.json` 共 15 条均为 `status=done`，HTTP `200`，响应 `flag=1`。
- [x] ledger 本轮追加 15 条 `detail_completed`；pack summary 写入 `reports/detail-pack-detail-p0-p1-pack-002-summary.json/.md`。
- [x] summary 脱敏扫描无命中；Campaign DB 仍为 `candidate_details=109`、`detailed=109`；主库 `data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 26: Full Detail Pack-002 Offline Dry-Run

- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-dry-run --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-002.json
```

- [x] 结果：`target_count=15`、`job_count=15`、`matched=15`、`ready_for_campaign_db_count=15`、`privacy_protected_count=0`、`missing_raw_count=0`、`unexpected_raw_count=0`、`failed_job_count=0`、`capture_blocker_count=0`、`apply_blocker_count=0`、`clean=true`。
- [x] `reports/detail-dry-run.json/.md` 已刷新为 pack-002 dry-run 结果，脱敏扫描无详情 URL token、`rawPreview`、secret 或浏览器敏感存储命中。
- [x] Campaign DB 未写入：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=109`，`candidates.data_level='detailed'=109`。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 27: Full Detail Pack-002 Apply Into Campaign DB

- [x] apply 前预检：pack-002 dry-run `clean=true`、`ready_for_campaign_db_count=15`；Campaign DB 为 `candidate_details=109`、`detailed=109`。
- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator detail-apply --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 --target-pack raw/detail-targets/detail-p0-p1-pack-002.json --confirm 确认写入猎聘详情
```

- [x] 结果：`matched=15`、`written=15`、`unmatched=0`、`privacy_protected_count=0`、`no_main_db_write=true`。
- [x] Campaign DB apply 后：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=124`，`candidates.data_level='detailed'=124`，`liepin_detail_capture=124`。
- [x] Campaign DB `candidate_details.raw_data` 和 `reports/detail-apply.json/.md` 精确脱敏扫描无详情 URL token 或 `rawPreview` 命中。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 28: Final Campaign Summary After Pack-002 Apply

- [x] 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator campaign-summary --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601
```

- [x] 结果：`candidate_count=150`、`source_profile_count=150`、`detail_count=124`、`detail_coverage_ratio=0.8266666666666667`、`data_level_counts={detailed:124,core:26}`。
- [x] 详情质量：`with_work_experience=124`、`with_education_experience=124`、`with_project_experience=18`。
- [x] Campaign DB 校验：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=124`，`candidates.data_level='detailed'=124`，`liepin_detail_capture=124`。
- [x] `reports/campaign-summary.json/.md` 和 Campaign DB `candidate_details.raw_data` 脱敏扫描无详情 URL token、`rawPreview`、secret 或浏览器敏感存储命中。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。

## Task 29: Phase Closure Verification

- [x] 猎聘聚焦 + 架构测试：

```bash
.venv/bin/python -m pytest tests/test_liepin_* tests/test_agent_architecture.py -q
```

结果：`137 passed`。

- [x] 全量测试：

```bash
.venv/bin/python -m pytest tests -q
```

结果：`1202 passed, 1 warning`；warning 为既有 `tests/test_boss.py` event loop deprecation。

- [x] 敏感存储扫描仅命中测试负断言和文档禁止条款，未发现 production 猎聘代码读取 `document.cookie`、`localStorage`、`sessionStorage`、Chrome profile 或 session store。
- [x] Campaign DB 边界：`PRAGMA integrity_check=ok`，`candidates=150`，`source_profiles(liepin)=150`，`candidate_details=124`，`candidates.data_level='detailed'=124`，`liepin_detail_capture=124`；`candidate_details.raw_data` 详情 URL token 与 `rawPreview` 精确扫描全为 0。
- [x] 主库未写入：`data/talent.db` 时间戳仍为 `Jun  1 20:32:52 2026`。
- [x] `git diff --check` 通过。
