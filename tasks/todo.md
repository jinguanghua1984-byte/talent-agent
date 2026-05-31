# Current Task Ledger

> 这个文件只保存当前活跃任务、未完成项、最近完成摘要和归档索引。完整历史见 `tasks/archive/`。

## Active Task

### BOSS App 推荐列表寻访试跑 50 人（2026-05-31）

计划：
- [ ] 初始化独立 campaign 目录，策略为“列表中现有人选全部进入详情，无额外筛选要求”。
- [ ] 用 Computer Use 预检当前 BOSS App 是否在推荐列表页。
- [ ] 逐个处理前 50 人：采集列表卡片、进入详情、展开折叠内容、详情内滚动到底、保存结构化文本和截图哈希、返回列表。
- [ ] 全程 dry-run，不点击 `立即沟通`、不发送消息、不写主人才库。
- [ ] 生成本地 summary，并向用户汇报已处理人数、成功详情数、跳过/中断原因和恢复入口。

边界：
- 不处理网页端/CDP/BOSS API。
- 遇到登录失效、验证码、安全页、权限弹窗、UI 模板漂移、无法返回列表或疑似真实发送风险，立即停机并写 continuation plan。
- 本轮目标先处理 `50` 人，完成后停止并汇报。

### 将训练/推理框架宽召回数据同步到正式库（2026-05-31）

计划：
- [x] 从 Campaign DB `data/campaigns/ai-infra-framework-broad-recall-2026-05-29/talent.db` 导出 sync bundle。
- [x] 校验 bundle 完整性并对正式库 `data/talent.db` 做 dry-run import：新建 `29969`、合并 `5563`、冲突候选人 `0`。
- [x] 备份正式库后执行确认写入：新建 `29969`、合并 `5563`、冲突候选人 `376`。
- [x] 校验正式库完整性、导入记录、冲突队列和关键计数。
- [x] 更新任务记录；不发布飞书，不做未授权的冲突覆盖。

边界：
- 本轮用户已授权将本次寻访数据写入正式库。
- 只通过 `scripts/talent_sync.py` bundle/import 写入，不直接复制 SQLite。
- 若导入产生 `sync_conflicts`，先保留冲突并输出审计信息；不在未确认规则下覆盖正式库已有字段。

Review：
- 已导出并校验 bundle：`data/output/talent-sync-ai-infra-framework-broad-recall-2026-05-29-20260531-195122.zip`，bundle id `b6b8b506-9cec-4a14-98ca-3e651f96ba9a`。
- 已备份正式库：`data/backups/talent-20260531-195224-before-ai-infra-framework-broad-recall-sync.db`。
- 正式库写入完成：`candidates=56193`、`candidate_details=56193`、`source_profiles=56198`、`candidate_fts=56193`。
- 本次 bundle open conflicts `2957` 条，审计报告：`data/output/talent-sync-ai-infra-framework-broad-recall-2026-05-29-conflicts-20260531.md` / `.json`；未做未授权冲突覆盖。
- 验证：`PRAGMA integrity_check=ok`；`sync_imports` 已记录本次 bundle；`.venv/bin/python -m pytest tests/test_talent_sync.py -q` -> `39 passed`；`git diff --check` 通过。

### 脉脉训练/推理框架宽召回自适应寻访（2026-05-29）

- [x] 读取 `maimai-talent-search-campaign` skill 与 `maimai-unattended-campaign` canonical workflow。
- [x] 明确边界：只生成并验证宽召回 campaign 合同与搜索计划；真实脉脉执行必须等待搜索计划确认。
- [x] 生成 `data/campaigns/ai-infra-framework-broad-recall-2026-05-29/` 合同文件。
- [x] 离线编译 `search-plan.json`、`search-units.jsonl` 和 wave plan。
- [x] 运行状态检查与 focused tests，确认计划可恢复、可交接。

边界：
- 使用 `strategy_mode=broad_recall_adaptive_v1`。
- 按公司顺序摸排：同一公司全部关键词单元完成后再进入下一个公司。
- 不考虑业务总页数上限；`500` 仅作为单账号单日平台护栏。
- 本阶段不启动真实脉脉搜索、不抓详情、不写主库、不发布飞书交付包。

当前结果：
- 已生成 264 个公司×关键词 unit，初始探测 528 页，拆成 11 个 wave。
- 已验证前 8 个 unit 均为 `华为盘古`，第 9 个进入 `月之暗面`，符合逐公司摸排。
- 已收到确认并启动真实搜索；CDP 健康检查通过，`search-wave-001` 在 `unit-000023/page-9` 触发 `captcha_api` 后已按 continuation plan 恢复并完成标准化。
- `search-wave-002` 执行 15 个 batch 后在 `unit-000040/page-5` 触发 `captcha_api` 停机；人工验证后已恢复并完成 wave 002 continuation，新增标准化 `66` 页。
- `search-wave-003` 后续因 `http_432` 停机；用户切换账号后已从 `unit-000064/page-9` 恢复并完成 wave 003 continuation，新增标准化 `97` 页。
- `search-wave-004` 第二次 continuation 已从 `unit-000091/page-5` 恢复并完成，新增标准化 `99` 页。
- `search-wave-005` 已从 `unit-000116/page-1` 恢复并完成，新增标准化 `50` 页。
- `search-wave-006` 已从 `unit-000145/page-7` 恢复并完成，新增标准化 `42` 页。
- `search-wave-007` 已从 `unit-000163/page-3` 恢复并完成，新增标准化 `116` 页。
- `search-wave-008` 已从 `unit-000188/page-3` 恢复并完成，新增标准化 `100` 页。
- `search-wave-009` 已启动，执行 12 个 batch 后在 `unit-000212/page-1` 触发 `captcha_api` 停机；已标准化本轮成功页 `49` 页。
- 人工验证后续跑 `search-wave-009`，平台立即在 `unit-000212/page-1` 再次返回 `captcha_api`；本次未新增标准化页，已写入中断报告 `reports/interruption-search-wave-009-captcha-api-20260530T020811.json`。
- `search-wave-009` 已从 `unit-000212/page-1` 恢复并完成，新增标准化 `79` 页；随后启动 `search-wave-010`。
- `search-wave-010` 执行 8 个 batch 后在 `unit-000233/page-10` 触发 `captcha_api` 停机；已标准化本轮成功页 `70` 页。
- `search-wave-010` 已从 `unit-000233/page-10` 恢复并完成，新增标准化 `147` 页；随后启动最后一批 `search-wave-011`。
- `search-wave-011` 在第一个 unit `unit-000251/page-3` 触发 `captcha_api` 停机；已标准化本轮成功页 `2` 页。
- `search-wave-011` 已从 `unit-000251/page-3` 恢复，执行 3 个 batch 后在 `unit-000253/page-12` 触发 `http_432` 停机；已标准化本轮成功页 `49` 页。
- `search-wave-011` 已从 `unit-000253/page-12` 恢复，新增标准化 `148` 页后在 `unit-000264/page-2` 触发 `captcha_api` 停机；中断报告为 `reports/interruption-search-wave-011-captcha-api-20260531T093004.json`。
- 用户恢复后已重新确认 CDP `9888` 和人才银行页健康；续跑在 `unit-000264/page-2` 立即再次触发 `captcha_api`，本次新增标准化 `0` 页，中断报告为 `reports/interruption-search-wave-011-captcha-api-retry-20260531T093905.json`。
- 用户再次验证后已从 `unit-000264/page-2` 续跑完成，新增标准化 `13` 页；`unit-000264` 在第 13、14 页连续低质后按规则停止。
- 搜索列表阶段已全部覆盖完成：264 个 unit 中 `exhausted=16`、`stopped_low_quality=248`，canonical raw `2138` 页，`seen_candidates=35538`。
- 已写入搜索完成报告 `reports/search-live-complete-20260531T101245.json`；未导入 Campaign DB，未抓详情，未写主库，未发布飞书。
- 当前状态：`state/continuation-plan.json` 已更新为 `search_live completed`，无待恢复阻断。
- 验证：focused tests `44 passed`；完整测试 `.venv/bin/python -m pytest tests -q` -> `957 passed, 1 warning`；`maimai_campaign_orchestrator status/resume` 可读完成状态；`git diff --check` 通过。
- 用户已授权进入后续无人值守：搜索 raw clean dry-run 后自动 apply 到 Campaign DB，粗筛后除 `skip/淘汰` 外全部抓详情，详情 live gate 以 4 并发执行；无错误则自动推进。
- 本轮详情范围覆盖 `detail_p0/detail_p1/detail_p2`，不抓取 `skip/淘汰`；主库同步和飞书发布仍不在本轮自动边界内。
- 当前执行检查项：
  - [x] 更新 run-policy 的详情目标范围。
  - [x] 逐 wave 导入搜索 raw 到 Campaign DB：11 个 wave dry-run/apply 均 clean，Campaign DB `candidates=35532`。
  - [x] 生成详情优先级和详情 pack：非淘汰目标 `14650` 人，拆分 `147` 个 pack，missing `0`。
  - [x] 4 并发执行详情抓取：首次在 `detail-ab-pack-014` index `25` 遇到 `TypeError: Failed to fetch` 后由用户验证并恢复；最终完成 `147/147` 个 pack，详情 job raw `14650/14650`。
  - [x] 详情 dry-run/apply 后生成宽召回摘要并验证：Campaign DB 写入详情 `14606` 条；`39` 个 `missing_work_experience` blocker 未伪造详情，已生成 clean 子集 apply 并保留原始证据；摘要报告已生成。

当前阻断：
- 无当前人工阻断；详情抓取 supervisor 已结束。
- 已保留历史中断证据：`reports/interruption-detail-detail-ab-pack-014-2026-05-31.json`，原因是 `detail-ab-pack-014` index `25` 的 `TypeError: Failed to fetch`。

Review：
- 本轮无人值守后续阶段已完成：搜索 raw 导入 Campaign DB、详情优先级与 pack、4 并发详情 live、详情 dry-run/apply、宽召回摘要报告。
- 核心产物：`reports/broad-recall-summary.md`、`reports/broad-recall-summary.json`、`reports/detail-wave-clean-subset-blockers-2026-05-31.json`。
- 验证：`status/resume` 均指向 `broad_recall_summary completed`；Campaign DB `PRAGMA integrity_check=ok`；无遗留 search/detail live 进程；`git diff --check` 通过；`.venv/bin/python -m pytest tests -q` -> `995 passed, 1 warning`。
- 边界：未写主库 `data/talent.db`，未发布飞书。

## Open Items

- `pm-ai-vertical-broad-recall-2026-05-28` 剩余 2 个详情 blocker 已随 campaign 作为 `core` 级候选人入主库，但未写入伪造详情：汪俊（`platform_id=35260004`）和徐傲蕾（`platform_id=82917951`），原因均为 `missing_work_experience`；后续如要提升到 detailed，需要单独补齐或剔除。
- 主库 `data/talent.db` 的 campaign DB 同步、ABC 详情写入和详情后全量 detailed rank 均已完成；下一步可基于 `data/output/hunyuan-8jd-main-db-match-after-detail-2026-05-23/` 做 JD 级人工复核与触达队列。
- 03/04 两个 JD 正文仍为“待补充”，本轮只按标题、职级和人才画像制定低置信度扩库策略；后续精排前需要补齐正式 JD 或用交付反馈校准。
- 详情后主库级 detailed rank 已按 `--limit 13332` 全量口径产出；03/04 因 JD 正文缺失仍只可作为低置信候选池，不应用于强推荐结论。

## Recent Done

- 2026-05-31：已处理 `ai-infra-framework-broad-recall-2026-05-29` 主库同步冲突 `2957` 条；备份后事务写入并逐条做 local-value drift 校验，最终 `resolved_keep_local=2539`、`resolved_use_remote=381`、`resolved_standardized_remote=37`，本 bundle open conflicts 为 `0`。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-31：已完成 BOSS App 推荐列表寻访 workflow 首版：新增 canonical skill/workflow、Computer Use 能力合同、`scripts/boss_app_sourcing.py` 合同/状态/候选人/联系安全/实名回填/报告 helper 和 36 个聚焦测试；全量验证 `.venv/bin/python -m pytest tests -q` -> `995 passed, 1 warning`，`git diff --check` 通过。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-30：已按 UI 浏览 BOSS 当前列表中薪资上限超过 50K 的人选卡片，查看 7 个详情并返回列表；未主动请求接口、未发起沟通、未收藏、未写库。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-29：已完成平台化人才服务中台产品方案设计，文档位于 `docs/superpowers/specs/2026-05-29-platform-talent-service-design.md`；方案确认采用“服务中台 + 飞书协作”，覆盖业务架构、技术架构、数据同步、双账本、权限审计、飞书交付和 P1-P3 阶段路线。完整记录见 `tasks/archive/2026-05.md`。
- 2026-05-28：已完成九坤大模型产品 7 个 JD 的 v2 年轻高潜推荐重跑；7 个 `*-run-002` 输出包质量门禁全部 `passed`，均已发布飞书 `JD需求交付` 并向 `JD需求协同` 通知；验证 `.venv/bin/python -m pytest tests -q` -> `955 passed, 1 warning`。完整记录见 `tasks/archive/2026-05.md`。

## Archive Index

- 2026-05：`tasks/archive/2026-05.md`
