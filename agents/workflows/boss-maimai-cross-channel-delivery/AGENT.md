---
name: boss-maimai-cross-channel-delivery
description: BOSS 优质人选补脉脉匹配、多渠道 Campaign DB 整合、主库同步和 JD/飞书交付 workflow。
---

# boss-maimai-cross-channel-delivery

## 触发入口

- 从 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md` 完成需求抽取、输入确认和合同生成后交接执行。
- 用户要求把 BOSS 已筛优质人选补脉脉主页、合并多渠道 campaign、同步 `data/talent.db` 或继续 `jd-talent-delivery` 飞书交付时，读取本 workflow。

## 安全边界

- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段不被脉脉覆盖。
- 主库 `data/talent.db` 不在 Campaign DB clean 前写入。
- 主库 apply 前必须有 `reports/main-db-sync-dry-run.json`、备份、导出校验和用户一次总授权。
- 未确认身份不得合并为同一 candidate；`pending_confirmation` 不得自动进入主库。
- 不处理登录、验证码、安全页、付费墙或平台风控；出现这些情况时停止并写恢复状态。

## 阶段

### S0 预检

确认 BOSS campaign root、岗位上下文、输出目录和当前状态文件存在。检查 `structured/candidates.jsonl`、`structured/contact-decisions.jsonl`、`state/events.jsonl` 和用户指定的补全范围。若已有中断恢复状态，先核对 continuation plan，不重复处理已完成候选人。

产物清单必须包含 `structured/maimai-match-targets.jsonl`、`state/cross-channel-identity-ledger.jsonl`、`reports/main-db-sync-dry-run.json` 和后续 `data/talent.db` sync 目标。预检阶段只确认路径，不写主库。

### S1 BOSS 优质人选 target 生成

从 BOSS 已筛候选人中选出 contact、strong hold 或用户指定的人选，生成 `structured/maimai-match-targets.jsonl`。每个 target 保留 BOSS 主键、姓名、当前公司、当前职位、城市、工作年限、学历、BOSS 证据路径和匹配所需的 query variants。

生成规则保持 BOSS 为 primary，脉脉为 supplement；BOSS 非空 `name/current_company/current_title/city/work_years/education` 在后续 merge 中不得被覆盖。

### S2 脉脉搜索执行

按 target 的 query variants 执行脉脉主页检索，保存搜索词、命中列表、公开主页证据、失败原因和平台限制。能稳定复用既有脉脉 campaign 时，先读取既有结果；缺失时再补搜。

搜索阶段只产生候选 evidence，不直接绑定身份，不写 `data/talent.db`。

### S3 身份匹配判定

按固定层级顺序判定身份：

1. `name_company_title`
2. `name_company_title_core`
3. `name_recent_company_title`
4. `name_school_title_core`
5. `name_company_fallback`

只有前四个层级命中且综合分数 `>=95`，才允许写入 `auto_bound`。`name_company_fallback` 不得自动绑定；fallback 命中、候选过多、第二名分差过小、综合分 70-94、字段证据冲突或关键证据缺失时，状态写为 `pending_confirmation`。明确不匹配时写 rejected。

所有判定必须写入 `candidate_identity_matches`，并追加 `state/cross-channel-identity-ledger.jsonl`，记录证据、分数、层级、状态、时间和人工确认需求。

### S4 人工确认门禁

汇总 `pending_confirmation`、候选过多、close second 和字段冲突清单，生成待确认视图。人工确认只能把具体 BOSS candidate 与具体脉脉 profile 绑定、拒绝或标记缺资料；不得用批量默认值跳过身份门禁。

未完成确认的人选可以留在 Campaign DB，但不得进入主库 apply。确认结果继续写入 `candidate_identity_matches` 与 `state/cross-channel-identity-ledger.jsonl`。

### S5 Campaign DB import dry-run

对 BOSS primary 与脉脉 supplement 做 Campaign DB merge dry-run。脉脉可补 `profile_url`、`platform_id`、缺失字段、状态和经历 union；字段冲突写 `candidate_field_values`，不覆盖 BOSS 主值。

dry-run 输出 `reports/cross-channel-merge-dry-run.json`，列出新增候选人、补字段、经历 union、冲突字段、身份待确认项和阻塞项。只要存在未处理的 `pending_confirmation`、关键冲突或 schema 错误，不能进入 apply。

### S6 Campaign DB import apply

当 S5 dry-run 无阻塞项后，把合并结果写入 campaign 本地 DB 与结构化产物。写入后更新 `structured/candidates.jsonl`、`structured/contact-decisions.jsonl`、`candidate_field_values`、`candidate_identity_matches` 和 `state/events.jsonl`。

本阶段仍不写 `data/talent.db`。如果 apply 后发现计数、主键或身份 ledger 不一致，停止并生成恢复说明。

### S7 脉脉详情补抓

对已绑定且缺少关键补充证据的人选补抓脉脉详情。补抓只补 supplement 字段、状态和经历 union；不得覆盖 BOSS primary 非空核心字段。

遇到登录、验证码、安全页、429、403、付费墙或平台限制时停止，保留已完成详情和待恢复 target。

### S8 Campaign DB quality gates

运行 campaign 质量门禁并生成 `reports/campaign-quality-gates.json`。通过条件：

- 身份 ledger 与 `candidate_identity_matches` 计数一致。
- 无阻塞 `pending_confirmation` 进入主库候选集合。
- BOSS primary 核心字段未被覆盖。
- `candidate_field_values` 完整记录冲突候选值。
- `structured/maimai-match-targets.jsonl`、`state/cross-channel-identity-ledger.jsonl` 和合并报告均可追溯。

只有报告明确 Campaign DB clean，才允许进入 S9。

### S9 主库 sync dry-run 与 apply

主库路径固定为 `data/talent.db`。先执行主库同步 dry-run，并把结果写入 `reports/main-db-sync-dry-run.json`。dry-run 必须覆盖新增、更新、冲突、跳过、身份绑定、字段来源和交付影响。

进入 apply 前必须完成：

- `talent_sync.py export`
- `verify-bundle`
- `talent_sync.py import` dry-run
- 用户对本次 `reports/main-db-sync-dry-run.json` 给出一次总授权，并提供 `CONFIRM_SYNC_TEXT`

只有 Campaign DB clean、dry-run 无阻塞冲突、备份和 bundle 校验通过、且一次总授权有效时，才能执行 `talent_sync.py import` apply 写入 `data/talent.db`。apply 结果写入 `reports/main-db-sync-apply.json`。授权只覆盖本 campaign 和本 dry-run，不得复用于变更后的数据。

### S10 JD delivery / 飞书交付

主库同步完成后，写 `reports/delivery-handoff.json`，列出本次可交付候选人、BOSS/脉脉证据、字段来源、主库写入结果和仍需人工处理的人选。然后交接给 `agents/workflows/jd-talent-delivery/AGENT.md` 与 `jd-talent-delivery`，继续 JD 推荐报告和飞书交付。

## 停机条件

- BOSS 与脉脉身份无法判定，且用户未确认。
- `pending_confirmation`、关键字段冲突或 schema 错误会影响主库写入。
- Campaign DB quality gates 未达到 Campaign DB clean。
- `reports/main-db-sync-dry-run.json` 显示阻塞冲突、备份失败或 bundle 校验失败。
- 缺少一次总授权或 `CONFIRM_SYNC_TEXT`。
- 遇到登录、验证码、安全页、平台限制、付费墙或疑似风控。

停机时更新 `state/events.jsonl`、恢复状态和对应报告，说明已完成阶段、剩余 target、阻塞原因和下一步所需用户动作。

## 验收

- `structured/maimai-match-targets.jsonl` 覆盖本次 BOSS 优质人选补全范围。
- BOSS 为 primary，脉脉为 supplement；BOSS 非空核心字段未被覆盖。
- 身份匹配记录写入 `candidate_identity_matches` 和 `state/cross-channel-identity-ledger.jsonl`。
- fallback、候选过多、close second、70-94 分和冲突项进入 `pending_confirmation`，不得自动绑定。
- Campaign DB clean 后才生成并使用 `reports/main-db-sync-dry-run.json`。
- 写入 `data/talent.db` 前完成 `talent_sync.py export`、`verify-bundle`、`talent_sync.py import` dry-run、一次总授权和 `CONFIRM_SYNC_TEXT`。
- S10 成功交接 `jd-talent-delivery`，飞书交付只使用已同步或明确标注来源的人选。
