---
name: boss-maimai-cross-channel-delivery
description: "BOSS App 已筛优质人选补脉脉主页匹配、多渠道 Campaign DB 整合、主库同步和 BOSS campaign 交付；不默认交接 `jd-talent-delivery`。"
---

# boss-maimai-cross-channel-delivery

## 目标

把 BOSS App 已筛出的优质人选作为主线，补充脉脉主页和详情证据，形成可审计、可回滚、可同步的多渠道 Campaign DB，并在授权后同步到 `data/talent.db`。同步后生成本次 BOSS campaign 任务摘要、交付报告和后续跟进表，不默认交接 `jd-talent-delivery`。

本合同的渠道优先级固定为：BOSS 为 primary，脉脉为 supplement。BOSS 的非空 `name/current_company/current_title/city/work_years/education` 不被脉脉覆盖；脉脉只补 `profile_url`、`platform_id`、BOSS 缺失字段、在线/求职状态和经历 union。字段冲突不直接覆盖，写入 `candidate_field_values`，由后续质量门禁或人工确认处理。

## 触发入口

用户表达以下意图时使用本 Skill：

- BOSS App 已经筛出一批优质候选人，需要补脉脉主页或脉脉详情。
- 需要把 BOSS 与脉脉证据合并到同一个 campaign。
- 需要在 Campaign DB clean 后，把多渠道结果同步到主人才库。
- 需要生成本次 BOSS campaign 交付包并推送新飞书交付。

合同生成后自动交接到 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。

## 输入

最小输入：

- BOSS campaign root，包含已筛候选人和 contact/hold 决策。
- JD 或岗位上下文，用于维持候选人筛选口径。
- 本次脉脉补全范围，例如全部 BOSS 优质人选、仅缺 `profile_url` 的人选或人工指定名单。

BOSS campaign 必须来自完整的 BOSS App sourcing 阶段：当前屏或当前批次没有合格人选不能作为最终无候选结论；合格人选后继续扫描，不得把单个命中作为上游正常终止条件。BOSS sourcing 默认真实触达模式为 `contact_mode="external_executor"`、`allow_real_contact=true`，默认可以点击 `立即沟通` 且无需另行明确授权。上游只有在列表循环到底部（含按 `list_end_stall_scrolls`/列表底部证据确认列表耗尽），或默认真实触达模式下 `立即沟通当日限额达到上限` 时，才算完成 BOSS sourcing；未明确沟通次数上限时不设置本地人数上限，只有平台明确提示次数用尽才算触达上限；dry-run 模式必须继续到列表循环到底部。

上游筛选策略必须保留通用信号优先级：用户明确的目标公司和搜索/广告/推荐/NLP/纯语音等排除项仍是硬门；但若 BOSS 候选已因 JD 关键正向信号进入 `contact` 或 strong `hold`，视觉、图像、图形、XR、3D、CV、音视频工程、编解码、SDK、流媒体等边界词只能作为风险进入脉脉补全和交付说明，不得在跨渠道交接阶段再次作为单独排除理由。

对多模态视频算法 JD，上游 BOSS 候选若标签、求职目标或详情明确包含“视频算法”“视频目标”或“语音/视频/图形”，必须作为视频算法相关候选进入脉脉补全与交付判断；不得仅因同屏出现视觉、图像处理、图形、XR 等边界词直接跳过，边界风险应进入交付说明。

可选输入：

- 既有脉脉 campaign root。
- 公司别名、学校别名、title 归一化规则。
- 用户对主库写入、飞书交付范围和交付顺序的限制。

## 输出产物

默认根目录仍使用 `data/campaigns/<campaign_id>/`。本 workflow 必须至少维护以下产物：

- `structured/maimai-match-targets.jsonl`：从 BOSS 优质人选生成的脉脉补全目标。
- `structured/candidates.jsonl`：多渠道合并后的 Campaign DB 候选人视图。
- `structured/contact-decisions.jsonl`：BOSS 联系意图、脉脉补全状态和后续交付建议。
- `state/cross-channel-identity-ledger.jsonl`：身份匹配判定、证据、分数、自动绑定或待确认状态。
- `reports/cross-channel-import-dry-run.json`：Campaign DB 合并 dry-run。
- `reports/cross-channel-import-result.json`：Campaign DB 合并 apply 结果。
- `reports/campaign-db-quality-gates.json`：Campaign DB clean 结果。
- `reports/main-db-sync-dry-run.json`：写入 `data/talent.db` 前的主库 dry-run。
- `reports/main-db-sync-result.json`：用户一次总授权后的主库 apply 结果。
- `reports/boss-maimai-delivery-report.json`：本次 BOSS campaign 交付报告结构化结果。
- `reports/boss-maimai-delivery-report.md`：面向交付复盘的本次 BOSS campaign 交付报告。
- `reports/boss-maimai-follow-up-queue.csv`：所有已沟通 BOSS 人选的后续跟进队列。
- `reports/boss-maimai-follow-up-queue.md`：面向人工执行的后续跟进摘要。
- `reports/boss-maimai-delivery-quality-gates.json`：本次 BOSS campaign 交付质量门禁。
- `feishu/boss-maimai-delivery-manifest.json`：新飞书交付 manifest；旧 Top30 飞书包保持不动。
- `feishu/im-notification-message.txt`：飞书发布回读通过后发送到 `JD需求协同` 的 IM 通知正文。
- `feishu/im-notification-results.json`：`im +messages-send` 发送结果和消息回读证据。
- `state/boss-maimai-delivery-handoff.json`：S10 BOSS campaign delivery 的输入摘要。

## Merge 边界

- BOSS 为 primary，脉脉为 supplement。
- BOSS 非空 `name/current_company/current_title/city/work_years/education` 不被脉脉覆盖。
- 脉脉可补齐 `profile_url`、`platform_id`、BOSS 缺失字段、在线/求职状态、认证状态、公开主页证据和工作/教育经历 union。
- 同一字段两侧均非空且不一致时，保留 BOSS 主值，脉脉候选值写入 `candidate_field_values`，标注来源、证据路径、置信度和待处理状态。
- 身份匹配过程必须写入 `candidate_identity_matches`，并同步追加到 `state/cross-channel-identity-ledger.jsonl`。
- 合并前先 dry-run；只有 Campaign DB clean 才能进入主库同步 dry-run。

## 脉脉匹配规则

先从 BOSS 优质人选生成 `structured/maimai-match-targets.jsonl`。搜索与判定按以下层级顺序执行：

1. `name_company_title`
2. `name_company_title_core`
3. `name_company_alias`，公司 alias 召回层，不得自动绑定
4. `name_company_alias_title_core`，公司 alias + title core 召回层，不得自动绑定
5. `name_recent_company_title`
6. `name_school_title_core`，仅在 BOSS 明确采集到 `schools` 字段时生成；纯 `education` 学历不得作为该层 auto-bind 证据
7. `name_school_fallback`，姓名 + 学校召回层，不得自动绑定
8. `name_company_fallback`

公司 alias 和学校 fallback 只用于提高召回，不得直接 `auto_bound`；命中后必须进入 `pending_confirmation` 或后续详情强证据确认，BOSS 为 primary 的非空核心字段仍不得被脉脉覆盖。

可自动绑定的高精度层级都必须有非空职位或有效职位核心词；缺职位时不得生成可自动绑定的高精度 query。只有高精度层级命中且综合分数 `>=95`，才允许写入 `auto_bound`。`name_company_fallback` 命中、候选过多、第二名分差过小、综合分 `70-94`、冲突或缺字段时，必须进入 `pending_confirmation`，不得自动绑定。无结果或低于 70 写入 `no_match`；出现明确排除证据时写入 `rejected`，并保留原因。

## 主库写入授权

主库路径固定为 `data/talent.db`。本 Skill 不允许在 Campaign DB clean 之前写主库。

进入主库前必须先生成 `reports/main-db-sync-dry-run.json`，并完成导出 bundle、bundle 校验和 dry-run 校验。只有当 Campaign DB clean、dry-run 无阻塞冲突、用户给出一次总授权后，workflow 才能把本 campaign 合并写入 `data/talent.db`，并进入本次 BOSS campaign 飞书交付。

一次总授权只覆盖本 campaign、本次 dry-run 报告和本次交付目标；不得复用到其他 campaign 或之后变更过的数据集。

## 自动交接

执行入口为 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。workflow 完成 S9 主库 sync dry-run 与 apply 后，把交付摘要写入 `state/boss-maimai-delivery-handoff.json`，并进入 S10 BOSS campaign delivery，生成 `reports/boss-maimai-delivery-report.json`、`reports/boss-maimai-delivery-report.md`、`reports/boss-maimai-follow-up-queue.csv`、`reports/boss-maimai-follow-up-queue.md`、`reports/boss-maimai-delivery-quality-gates.json`、`feishu/boss-maimai-delivery-manifest.json`、`feishu/im-notification-message.txt` 和 `feishu/im-notification-results.json`。

S10 必须保证所有已沟通 BOSS 人选进入 follow-up，脉脉命中只影响 `preferred_channel`；旧 Top30 飞书包保持不动。飞书发布和回读通过后，必须用 `im +chat-search --as user` 搜索 `JD需求协同`，再用 `im +messages-send --as user` 同步发送完成通知，并把通知正文和发送/回读结果落盘。需要面向具体 JD 的推荐包时，应作为后续独立任务另行启动，不属于本 Skill 的默认自动交接。
