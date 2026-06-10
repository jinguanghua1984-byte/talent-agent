---
name: boss-maimai-cross-channel-delivery
description: BOSS 优质人选补脉脉匹配、多渠道 Campaign DB 整合、主库同步和 BOSS campaign 交付 workflow。
---

# boss-maimai-cross-channel-delivery

## 触发入口

从 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md` 完成需求抽取、输入确认和合同生成后交接执行；适用于 BOSS 已筛优质人选补脉脉主页、多渠道 campaign 合并、主库同步和 BOSS campaign 飞书交付。

## Shared Policies

复用 `agents/policies/platform-automation-safety.md`、`agents/policies/main-db-sync-gates.md`、`agents/policies/feishu-publish-gates.md`、`agents/policies/campaign-recovery.md`；本文件只保留 BOSS-Maimai 特有阶段、产物、命令和门禁差异。

## 安全边界

- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段不被脉脉覆盖，未确认身份不得合并为同一 candidate，`pending_confirmation` 不得自动进入主库。
- 主库 `data/talent.db` 只在 Campaign DB clean、`reports/main-db-sync-dry-run.json` 无阻塞、备份/导出校验通过且用户一次总授权后写入；登录、验证码、安全页、付费墙或平台风控按 shared policy 停机。

## 脉脉匹配 CDP 与无人值守合同

脉脉搜索、详情、阻断和恢复必须复用 `agents/workflows/maimai-unattended-campaign/AGENT.md`；本 workflow 只增加 BOSS target、身份判定和多渠道 merge 门禁。BOSS 优质人选 target 和匹配范围确认后只停一次，确认后固定：`auto_bootstrap_browser_after_plan_confirmation=true`、`allow_campaign_db_auto_apply_after_clean_dry_run=true`、`allow_detail_campaign_db_auto_apply_after_clean_dry_run=true`；主库写入不包含在无人值守授权内，仍由 S9 的一次总授权和 `CONFIRM_SYNC_TEXT` 控制。

确认后先探测健康的 `http://127.0.0.1:9888` CDP 会话；不健康且 `auto_bootstrap_browser_after_plan_confirmation=true` 时自动启动 CDP 浏览器，确认后不得提示负责人手动启动浏览器。启动使用 `data/session/maimai-cdp-profile`、加载 `extensions/maimai-scraper`，参数包含 `--remote-debugging-port=9888`，写 `data/session/maimai-cdp-browser-session.json`：

```bash
.venv/bin/python -m scripts.maimai_cdp_browser_bootstrap --profile data/session/maimai-cdp-profile --extension extensions/maimai-scraper --remote-debugging-port 9888 --manifest-out data/session/maimai-cdp-browser-session.json
```

bootstrap 只负责 launch；只等待登录/验证码/人才银行页健康条件，不自动绕过登录、验证码或安全页。进入真实执行态后不得自动导航、刷新、点击已进入执行态的脉脉业务页面，不得手动操作 Chrome DOM，不得直接打开个人主页 URL 代替既有搜索/详情脚本。

恢复事实来源固定为 `raw/maimai-match-search/<target_id>/query-*.json`、`raw/detail-live/<pack_id>/job-*.json`、`state/import-ledger.jsonl`、`state/continuation-plan.json`；通知失败状态为 `blocked_notification_failed`。Campaign DB search/import 或 detail dry-run clean 后，不得要求 Campaign DB clean dry-run 后再次人工确认；只有 `pending_confirmation`、字段冲突、schema 错误、平台阻断或主库 S9 授权门禁才允许停机。

## 阶段

### S0 预检

确认 BOSS campaign root、岗位上下文、输出目录、`structured/candidates.jsonl`、`structured/contact-decisions.jsonl`、`state/events.jsonl`、用户补全范围和 continuation plan；产物清单必须包含 `structured/maimai-match-targets.jsonl`、`state/cross-channel-identity-ledger.jsonl`、`reports/main-db-sync-dry-run.json` 和后续 `data/talent.db` sync 目标。预检只确认路径，不写主库。

BOSS campaign 只能在上游 sourcing 已完成正常终止条件后进入本 workflow：列表循环到底部（含列表耗尽证据），或默认真实触达模式下 `立即沟通当日限额达到上限`。BOSS sourcing 默认 `contact_mode="external_executor"`、`allow_real_contact=true`，默认可以点击 `立即沟通` 且无需另行明确授权；未明确沟通次数上限时不设置本地人数上限，只有平台明确提示次数用尽才算触达上限。当前屏或当前批次无 `contact` 不是可交付终态；合格人选后继续扫描，不得把单个命中作为上游完成条件；如果上游没有列表循环到底部证据，且也没有默认真实触达模式下的平台明确提示次数用尽证据，必须回到 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md` 继续扫描。

上游 BOSS sourcing 的通用信号优先级必须沿用到本 workflow：用户明确的目标公司和搜索/广告/推荐/NLP/纯语音等排除项仍是硬门；但若候选已因 JD 关键正向信号进入 `contact` 或 strong `hold`，视觉、图像、图形、XR、3D、CV、音视频工程、编解码、SDK、流媒体等边界词只能作为风险进入脉脉补全、身份确认和交付说明，不得在 S1 target 生成或 S10 交付阶段再次作为单独排除理由。

对多模态视频算法 JD，上游 BOSS 候选若标签、求职目标或详情明确包含“视频算法”“视频目标”或“语音/视频/图形”，必须作为视频算法相关候选进入脉脉补全与交付判断；不得仅因同屏出现视觉、图像处理、图形、XR 等边界词直接跳过，边界风险应进入交付说明。

### S1 BOSS 优质人选 target 生成

从 BOSS 已筛候选人中选出 contact、strong hold 或用户指定人选，使用 `scripts/boss_maimai_targets.py export` 生成 `structured/maimai-match-targets.jsonl`；每个 target 保留 BOSS 主键、姓名、公司、职位、城市、年限、学历、证据路径和 query variants。BOSS 为 primary，脉脉为 supplement；BOSS 非空 `name/current_company/current_title/city/work_years/education` 后续不得被覆盖。

### S2 脉脉搜索执行

按 target query variants 执行脉脉主页检索；先应用 CDP 与无人值守合同，优先复用 `http://127.0.0.1:9888`，不健康时自动启动 CDP Chrome。真实检索复用既有脉脉 CDP/search 脚本和 `/api/ent/v3/search/basic` 模板，保存搜索词、命中、公开主页证据、失败原因和平台限制到 `raw/maimai-match-search/<target_id>/query-*.json`；可复用既有 campaign 结果时先读盘，缺失再补搜。搜索只产出 evidence，不绑定身份，不写 `data/talent.db`。

### S3 身份匹配判定

按固定层级顺序判定身份：`name_company_title`、`name_company_title_core`、`name_company_alias`、`name_company_alias_title_core`、`name_recent_company_title`、`name_school_title_core`、`name_school_fallback`、`name_company_fallback`。`name_company_alias`、`name_company_alias_title_core`、`name_school_fallback`、`name_company_fallback` 只召回，不得自动绑定；学校层仅在 BOSS 明确采集 `schools` 字段时生成，纯 `education` 不作为 auto-bind 证据。

可自动绑定的高精度层级都必须有非空职位或有效职位核心词；缺职位时不得生成可自动绑定的高精度 query。只有高精度层级命中且综合分数 `>=95`，才允许写入 `auto_bound`。`name_company_fallback` 不得自动绑定；fallback 命中、候选过多、第二名分差过小、综合分 70-94、字段证据冲突或关键证据缺失时，状态写为 `pending_confirmation`。无结果或低分不匹配时写 `no_match`；明确排除时写 `rejected`。

所有判定必须写入 `candidate_identity_matches`，并追加 `state/cross-channel-identity-ledger.jsonl`，记录证据、分数、层级、状态、时间和人工确认需求。

### S4 人工确认门禁

汇总 `pending_confirmation`、候选过多、close second 和字段冲突清单，生成待确认视图；人工确认只能把具体 BOSS candidate 与具体脉脉 profile 绑定、拒绝或标记缺资料，不得批量默认跳过。未完成确认的人选可留在 Campaign DB，但不得进入主库 apply；确认结果继续写入 `candidate_identity_matches` 与 `state/cross-channel-identity-ledger.jsonl`。

### S5 Campaign DB import dry-run

对 BOSS primary 与脉脉 supplement 做 Campaign DB import dry-run；脉脉只补 `profile_url`、`platform_id`、缺失字段、状态和经历 union，字段冲突写 `candidate_field_values`，不覆盖 BOSS 主值。使用 `scripts.cross_channel_import import --dry-run` 输出 `reports/cross-channel-import-dry-run.json`；未处理 `pending_confirmation`、关键冲突或 schema 错误阻塞 apply。

### S6 Campaign DB import apply

S5 dry-run 无阻塞后，用 `scripts.cross_channel_import import` 写 campaign 本地 DB，生成 `reports/cross-channel-import-result.json`，维护 `candidate_field_values`、`candidate_identity_matches`，必要时更新 `structured/candidates.jsonl`、`structured/contact-decisions.jsonl`、`state/events.jsonl`。本阶段仍不写 `data/talent.db`；计数、主键或身份 ledger 不一致则停止。

### S7 脉脉详情补抓

对已绑定且缺少关键补充证据的人选补抓脉脉详情。详情执行继续复用 `agents/workflows/maimai-unattended-campaign/AGENT.md` 的 live detail 边界：通过既有详情脚本连接 `http://127.0.0.1:9888`，详情 raw 写入 `raw/detail-live/<pack_id>/job-*.json`，恢复时只信这些 job raw 和 pack manifest。

补抓只补 supplement 字段、状态和经历 union；不得覆盖 BOSS primary 非空核心字段。详情 dry-run clean 且 `allow_detail_campaign_db_auto_apply_after_clean_dry_run=true` 时自动 apply 到 Campaign DB，并使用 `state/import-ledger.jsonl` 防重；不得要求 Campaign DB clean dry-run 后再次人工确认。

遇到登录、验证码、安全页、429、403、付费墙或平台限制时停止，保留已完成详情和待恢复 target。

### S8 Campaign DB quality gates

运行 `scripts.campaign_to_delivery validate-campaign` 并生成 `reports/campaign-db-quality-gates.json`；通过条件为身份 ledger 与 `candidate_identity_matches` 计数一致、无阻塞 `pending_confirmation` 进入主库候选集合、BOSS primary 核心字段未被覆盖、`candidate_field_values` 完整记录冲突候选值、`structured/maimai-match-targets.jsonl` 与 `state/cross-channel-identity-ledger.jsonl` 可追溯。只有报告明确 Campaign DB clean，才允许进入 S9。

### S9 主库 sync dry-run 与 apply

主库路径固定为 `data/talent.db`。先执行主库同步 dry-run，结果写入 `reports/main-db-sync-dry-run.json`，覆盖新增、更新、冲突、跳过、身份绑定、字段来源和交付影响。进入 apply 前必须完成：`scripts.campaign_to_delivery sync-main` 生成 campaign-to-main bundle，内部调用 `talent_sync.py export` 等价的 `export_bundle`；`verify-bundle`；`talent_sync.py import` dry-run；用户对本次 `reports/main-db-sync-dry-run.json` 给出一次总授权，并提供 `CONFIRM_SYNC_TEXT`。

只有 Campaign DB clean、dry-run 无阻塞冲突、bundle 校验通过、且一次总授权有效时，才能执行 `talent_sync.py import` apply 写入 `data/talent.db`。apply 结果写入 `reports/main-db-sync-result.json`。授权只覆盖本 campaign 和本 dry-run，不得复用于变更后的数据。

### S10 BOSS campaign delivery / 飞书交付

主库同步完成后，写 `state/boss-maimai-delivery-handoff.json`，列出本次可交付候选人、BOSS/脉脉证据、字段来源、主库写入结果、已沟通 BOSS 人选和仍需人工处理的人选。然后执行本次 BOSS campaign delivery，不复用或覆盖旧 Top30 飞书包；旧 Top30 飞书包保持不动。

使用 `.venv/bin/python -m scripts.boss_maimai_campaign_delivery build --campaign-root <campaign_root> --main-db data/talent.db` 生成本次 BOSS campaign delivery 产物：`reports/boss-maimai-delivery-report.json`、`reports/boss-maimai-delivery-report.md`、`reports/boss-maimai-follow-up-queue.csv`、`reports/boss-maimai-follow-up-queue.md`、`reports/boss-maimai-delivery-quality-gates.json`、`feishu/boss-maimai-delivery-manifest.json`、`feishu/im-notification-message.txt`、`feishu/im-notification-results.json`。

新飞书 manifest 先独立 dry-run，命令为 `.venv/bin/python -m scripts.boss_maimai_campaign_delivery manifest --campaign-root <campaign_root> --dry-run`，确认只引用本次 BOSS campaign 交付报告、follow-up queue 和 quality gates 后再生成。

发布目标为 `JD需求交付` 下本次 BOSS campaign 新交付包：报告 Doc 使用 `drive +import --type docx` 导入为包含 `BOSS寻访交付报告` 的 Doc，跟进表使用 `sheets +create` 创建包含 `BOSS跟进表` 的 Sheet，并用 `sheets +append` 写入 `reports/boss-maimai-follow-up-queue.csv`。manifest 必须记录 `readback_expectations`；发布后回读 Wiki/Doc/Sheet，确认目标挂载、Doc 标题、Sheet 标题、Sheet 行数和旧 Top30 包 `not_modified`。无法挂到目标知识库或无法回读时，S10 停止。

质量门禁必须在 `reports/boss-maimai-delivery-quality-gates.json` 中明确记录：`follow_up_row_count == real_contact_count`、所有已沟通 BOSS 人选进入 follow-up、脉脉命中只影响 `preferred_channel`、新飞书 manifest 只引用本次产物、旧 Top30 飞书包保持不动。

飞书发布和回读通过后，必须同步发送 IM 完成通知：`lark-cli im +chat-search --as user --query JD需求协同 --disable-search-by-user --search-types private,public_joined,external --page-size 10 --format json`；`lark-cli im +messages-send --as user --chat-id <JD需求协同_chat_id> --idempotency-key <short_boss_maimai_key> --text <feishu/im-notification-message.txt>`。通知目标固定为 `JD需求协同`；发送动作固定使用 `im +messages-send`，不得只完成 Wiki/Doc/Sheet 发布而跳过群通知。

通知正文写入 `feishu/im-notification-message.txt`，发送结果和 `im +messages-mget` 回读证据写入 `feishu/im-notification-results.json`。通知内容必须包含任务执行结果、报告链接、跟进表链接、follow-up 行数、脉脉命中数和旧 Top30 包保持不动。

## 停机条件

- BOSS 与脉脉身份无法判定，且用户未确认。
- `pending_confirmation`、关键字段冲突或 schema 错误会影响主库写入。
- Campaign DB quality gates 未达到 Campaign DB clean。
- `reports/main-db-sync-dry-run.json` 显示阻塞冲突、备份失败或 bundle 校验失败。
- 缺少一次总授权或 `CONFIRM_SYNC_TEXT`。
- CDP bootstrap 失败、`http://127.0.0.1:9888` 无健康人才银行页、搜索或详情模板漂移。
- 遇到登录、验证码、安全页、403、429、432、非 JSON、HTML 响应、详情 partial capture、平台限制、付费墙或疑似风控。
- 飞书发布后的 IM 通知失败时写 `blocked_notification_failed`，不得把通知失败误报为 campaign 完整关闭。

停机时更新 `state/events.jsonl`、恢复状态和对应报告，说明已完成阶段、剩余 target、阻塞原因和下一步所需用户动作。

## 验收

- `structured/maimai-match-targets.jsonl` 覆盖本次 BOSS 优质人选补全范围。
- 脉脉匹配阶段明确复用 `agents/workflows/maimai-unattended-campaign/AGENT.md`，确认后不得提示负责人手动启动浏览器。
- CDP Chrome 启动或复用记录可追溯：`http://127.0.0.1:9888`、`data/session/maimai-cdp-profile`、`extensions/maimai-scraper` 和 `--remote-debugging-port=9888`。
- 搜索 raw 写入 `raw/maimai-match-search/<target_id>/query-*.json`；详情 raw 写入 `raw/detail-live/<pack_id>/job-*.json`；重复 apply 可由 `state/import-ledger.jsonl` 判定。
- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段未被覆盖。
- 身份匹配记录写入 `candidate_identity_matches` 和 `state/cross-channel-identity-ledger.jsonl`。
- fallback、候选过多、close second、70-94 分和冲突项进入 `pending_confirmation`，不得自动绑定。
- Campaign DB clean 后才生成并使用 `reports/main-db-sync-dry-run.json`。
- 写入 `data/talent.db` 前完成 `talent_sync.py export`、`verify-bundle`、`talent_sync.py import` dry-run、一次总授权和 `CONFIRM_SYNC_TEXT`。
- S10 成功生成 campaign delivery report、follow-up、gates、manifest 和 IM 通知结果，飞书交付只使用已同步或明确标注来源的人选。
