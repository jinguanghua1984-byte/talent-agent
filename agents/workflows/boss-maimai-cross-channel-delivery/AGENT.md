---
name: boss-maimai-cross-channel-delivery
description: BOSS 优质人选补脉脉匹配、多渠道 Campaign DB 整合、主库同步和 BOSS campaign 交付 workflow。
---

# boss-maimai-cross-channel-delivery

## 触发入口

- 从 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md` 完成需求抽取、输入确认和合同生成后交接执行。
- 用户要求把 BOSS 已筛优质人选补脉脉主页、合并多渠道 campaign、同步 `data/talent.db` 或生成本次 BOSS campaign 交付包并推送新飞书交付时，读取本 workflow。

## 安全边界

- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段不被脉脉覆盖。
- 主库 `data/talent.db` 不在 Campaign DB clean 前写入。
- 主库 apply 前必须有 `reports/main-db-sync-dry-run.json`、备份、导出校验和用户一次总授权。
- 未确认身份不得合并为同一 candidate；`pending_confirmation` 不得自动进入主库。
- 不处理登录、验证码、安全页、付费墙或平台风控；出现这些情况时停止并写恢复状态。

## 脉脉匹配 CDP 与无人值守合同

脉脉搜索、详情、阻断和恢复必须复用 `agents/workflows/maimai-unattended-campaign/AGENT.md` 的安全边界；本 workflow 只增加 BOSS target、身份判定和多渠道 merge 门禁，不另造新的脉脉浏览器模型。

BOSS 优质人选 target 和匹配范围确认后，只在该确认点停一次。确认后无人值守策略固定为：

- `auto_bootstrap_browser_after_plan_confirmation=true`
- `allow_campaign_db_auto_apply_after_clean_dry_run=true`
- `allow_detail_campaign_db_auto_apply_after_clean_dry_run=true`
- 主库写入不包含在无人值守授权内，仍由 S9 的一次总授权和 `CONFIRM_SYNC_TEXT` 控制。

确认后先探测健康的 `http://127.0.0.1:9888` CDP 会话。若端口未监听或会话不健康，且 `auto_bootstrap_browser_after_plan_confirmation=true`，自动启动 CDP 浏览器，不再提示负责人手动启动浏览器。启动必须使用 `data/session/maimai-cdp-profile`、加载 `extensions/maimai-scraper`，启动参数必须包含 `--remote-debugging-port=9888`，并写入 `data/session/maimai-cdp-browser-session.json`。推荐入口：

```bash
.venv/bin/python -m scripts.maimai_cdp_browser_bootstrap --profile data/session/maimai-cdp-profile --extension extensions/maimai-scraper --remote-debugging-port 9888 --manifest-out data/session/maimai-cdp-browser-session.json
```

bootstrap 只负责 launch；只等待登录/验证码/人才银行页健康条件，不自动绕过登录、验证码或安全页。进入真实执行态后不得自动导航、刷新、点击已进入执行态的脉脉业务页面，不得手动操作 Chrome DOM，不得直接打开个人主页 URL 代替既有搜索/详情脚本。

恢复事实来源固定为：

- 搜索恢复事实来源：`raw/maimai-match-search/<target_id>/query-*.json`
- 详情恢复事实来源：`raw/detail-live/<pack_id>/job-*.json`
- apply 防重事实来源：`state/import-ledger.jsonl`
- 中断恢复入口：`state/continuation-plan.json`
- 通知失败状态：`blocked_notification_failed`

Campaign DB search/import 或 detail dry-run clean 后，不得要求 Campaign DB clean dry-run 后再次人工确认；只有 `pending_confirmation`、字段冲突、schema 错误、平台阻断或主库 S9 授权门禁才允许停机。

## 阶段

### S0 预检

确认 BOSS campaign root、岗位上下文、输出目录和当前状态文件存在。检查 `structured/candidates.jsonl`、`structured/contact-decisions.jsonl`、`state/events.jsonl` 和用户指定的补全范围。若已有中断恢复状态，先核对 continuation plan，不重复处理已完成候选人。

产物清单必须包含 `structured/maimai-match-targets.jsonl`、`state/cross-channel-identity-ledger.jsonl`、`reports/main-db-sync-dry-run.json` 和后续 `data/talent.db` sync 目标。预检阶段只确认路径，不写主库。

### S1 BOSS 优质人选 target 生成

从 BOSS 已筛候选人中选出 contact、strong hold 或用户指定的人选，使用 `scripts/boss_maimai_targets.py export` 生成 `structured/maimai-match-targets.jsonl`。每个 target 保留 BOSS 主键、姓名、当前公司、当前职位、城市、工作年限、学历、BOSS 证据路径和匹配所需的 query variants。

生成规则保持 BOSS 为 primary，脉脉为 supplement；BOSS 非空 `name/current_company/current_title/city/work_years/education` 在后续 merge 中不得被覆盖。

### S2 脉脉搜索执行

按 target 的 query variants 执行脉脉主页检索。搜索执行前必须应用“脉脉匹配 CDP 与无人值守合同”：优先复用 `http://127.0.0.1:9888`，不健康时按 `auto_bootstrap_browser_after_plan_confirmation=true` 自动启动 CDP Chrome，并加载 `data/session/maimai-cdp-profile` 与 `extensions/maimai-scraper`。

真实检索必须通过既有脉脉 CDP/search 脚本复用 `/api/ent/v3/search/basic` 模板执行，保存搜索词、命中列表、公开主页证据、失败原因和平台限制到 `raw/maimai-match-search/<target_id>/query-*.json`。能稳定复用既有脉脉 campaign 时，先读取既有结果；缺失时再补搜。恢复时只信磁盘 raw、`state/continuation-plan.json` 和脚本状态，不盲信内存上下文。

搜索阶段只产生候选 evidence，不直接绑定身份，不写 `data/talent.db`。

### S3 身份匹配判定

按固定层级顺序判定身份：

1. `name_company_title`
2. `name_company_title_core`
3. `name_company_alias`，公司 alias 召回层，不得自动绑定
4. `name_company_alias_title_core`，公司 alias + title core 召回层，不得自动绑定
5. `name_recent_company_title`
6. `name_school_title_core`，仅在 BOSS 明确采集到 `schools` 字段时生成；纯 `education` 学历不得作为该层 auto-bind 证据
7. `name_school_fallback`，姓名 + 学校召回层，不得自动绑定
8. `name_company_fallback`

公司 alias 和学校 fallback 只用于提高召回，不得直接 `auto_bound`；命中后必须进入 `pending_confirmation` 或后续详情强证据确认，BOSS 为 primary 的非空核心字段仍不得被脉脉覆盖。

可自动绑定的高精度层级都必须有非空职位或有效职位核心词；缺职位时不得生成可自动绑定的高精度 query。只有高精度层级命中且综合分数 `>=95`，才允许写入 `auto_bound`。`name_company_fallback` 不得自动绑定；fallback 命中、候选过多、第二名分差过小、综合分 70-94、字段证据冲突或关键证据缺失时，状态写为 `pending_confirmation`。无结果或低分不匹配时写 `no_match`；明确排除时写 `rejected`。

所有判定必须写入 `candidate_identity_matches`，并追加 `state/cross-channel-identity-ledger.jsonl`，记录证据、分数、层级、状态、时间和人工确认需求。

### S4 人工确认门禁

汇总 `pending_confirmation`、候选过多、close second 和字段冲突清单，生成待确认视图。人工确认只能把具体 BOSS candidate 与具体脉脉 profile 绑定、拒绝或标记缺资料；不得用批量默认值跳过身份门禁。

未完成确认的人选可以留在 Campaign DB，但不得进入主库 apply。确认结果继续写入 `candidate_identity_matches` 与 `state/cross-channel-identity-ledger.jsonl`。

### S5 Campaign DB import dry-run

对 BOSS primary 与脉脉 supplement 做 Campaign DB import dry-run。脉脉可补 `profile_url`、`platform_id`、缺失字段、状态和经历 union；字段冲突写 `candidate_field_values`，不覆盖 BOSS 主值。

dry-run 使用 `scripts.cross_channel_import import --dry-run`，输出 `reports/cross-channel-import-dry-run.json`，列出将导入人选、blocked、errors 和阻塞项。只要存在未处理的 `pending_confirmation`、关键冲突或 schema 错误，不能进入 apply。

### S6 Campaign DB import apply

当 S5 dry-run 无阻塞项后，使用 `scripts.cross_channel_import import` 把合并结果写入 campaign 本地 DB。写入后至少生成 `reports/cross-channel-import-result.json`，并维护 `candidate_field_values`、`candidate_identity_matches`；如需面向人工浏览的结构化视图，再更新 `structured/candidates.jsonl`、`structured/contact-decisions.jsonl` 和 `state/events.jsonl`。

本阶段仍不写 `data/talent.db`。如果 apply 后发现计数、主键或身份 ledger 不一致，停止并生成恢复说明。

### S7 脉脉详情补抓

对已绑定且缺少关键补充证据的人选补抓脉脉详情。详情执行继续复用 `agents/workflows/maimai-unattended-campaign/AGENT.md` 的 live detail 边界：通过既有详情脚本连接 `http://127.0.0.1:9888`，详情 raw 写入 `raw/detail-live/<pack_id>/job-*.json`，恢复时只信这些 job raw 和 pack manifest。

补抓只补 supplement 字段、状态和经历 union；不得覆盖 BOSS primary 非空核心字段。详情 dry-run clean 且 `allow_detail_campaign_db_auto_apply_after_clean_dry_run=true` 时自动 apply 到 Campaign DB，并使用 `state/import-ledger.jsonl` 防重；不得要求 Campaign DB clean dry-run 后再次人工确认。

遇到登录、验证码、安全页、429、403、付费墙或平台限制时停止，保留已完成详情和待恢复 target。

### S8 Campaign DB quality gates

运行 `scripts.campaign_to_delivery validate-campaign` 并生成 `reports/campaign-db-quality-gates.json`。通过条件：

- 身份 ledger 与 `candidate_identity_matches` 计数一致。
- 无阻塞 `pending_confirmation` 进入主库候选集合。
- BOSS primary 核心字段未被覆盖。
- `candidate_field_values` 完整记录冲突候选值。
- `structured/maimai-match-targets.jsonl`、`state/cross-channel-identity-ledger.jsonl` 和合并报告均可追溯。

只有报告明确 Campaign DB clean，才允许进入 S9。

### S9 主库 sync dry-run 与 apply

主库路径固定为 `data/talent.db`。先执行主库同步 dry-run，并把结果写入 `reports/main-db-sync-dry-run.json`。dry-run 必须覆盖新增、更新、冲突、跳过、身份绑定、字段来源和交付影响。

进入 apply 前必须完成：

- `scripts.campaign_to_delivery sync-main` 生成 campaign-to-main bundle，内部调用 `talent_sync.py export` 等价的 `export_bundle`
- `verify-bundle`
- `talent_sync.py import` dry-run
- 用户对本次 `reports/main-db-sync-dry-run.json` 给出一次总授权，并提供 `CONFIRM_SYNC_TEXT`

只有 Campaign DB clean、dry-run 无阻塞冲突、bundle 校验通过、且一次总授权有效时，才能执行 `talent_sync.py import` apply 写入 `data/talent.db`。apply 结果写入 `reports/main-db-sync-result.json`。授权只覆盖本 campaign 和本 dry-run，不得复用于变更后的数据。

### S10 BOSS campaign delivery / 飞书交付

主库同步完成后，写 `state/boss-maimai-delivery-handoff.json`，列出本次可交付候选人、BOSS/脉脉证据、字段来源、主库写入结果、已沟通 BOSS 人选和仍需人工处理的人选。然后执行本次 BOSS campaign delivery，不复用或覆盖旧 Top30 飞书包；旧 Top30 飞书包保持不动。

使用以下命令生成本次 BOSS campaign delivery 产物：

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery build --campaign-root <campaign_root> --main-db data/talent.db
```

产物包括：

- `reports/boss-maimai-delivery-report.json`
- `reports/boss-maimai-delivery-report.md`
- `reports/boss-maimai-follow-up-queue.csv`
- `reports/boss-maimai-follow-up-queue.md`
- `reports/boss-maimai-delivery-quality-gates.json`
- `feishu/boss-maimai-delivery-manifest.json`
- `feishu/im-notification-message.txt`
- `feishu/im-notification-results.json`

新飞书 manifest 先独立 dry-run，确认只引用本次 BOSS campaign 交付报告、follow-up queue 和 quality gates 后再生成：

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery manifest --campaign-root <campaign_root> --dry-run
```

质量门禁必须在 `reports/boss-maimai-delivery-quality-gates.json` 中明确记录：

- `follow_up_row_count == real_contact_count`
- 所有已沟通 BOSS 人选进入 follow-up。
- 脉脉命中只影响 `preferred_channel`，不得改变 BOSS primary 核心字段。
- 新飞书 manifest 只引用本次 BOSS campaign 交付报告、follow-up queue 和 quality gates。
- 旧 Top30 飞书包保持不动。

飞书发布和回读通过后，必须同步发送 IM 完成通知：

```bash
lark-cli im +chat-search --as user --query JD需求协同 --disable-search-by-user --search-types private,public_joined,external --page-size 10 --format json
lark-cli im +messages-send --as user --chat-id <JD需求协同_chat_id> --idempotency-key <short_boss_maimai_key> --text <feishu/im-notification-message.txt>
```

通知目标固定为 `JD需求协同`；发送动作固定使用 `im +messages-send`，不得只完成 Wiki/Doc/Sheet 发布而跳过群通知。

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
