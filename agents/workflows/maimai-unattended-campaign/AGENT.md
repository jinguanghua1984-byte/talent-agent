---
name: maimai-unattended-campaign
description: 脉脉 unattended campaign 的 canonical workflow，约束搜索、详情、导入、报告和通知的阶段合同。
---

# maimai-unattended-campaign

## 安全边界

- 真实执行阶段不自动导航、刷新、点击已进入执行态的脉脉业务页面。
- 不绕过登录、验证码、权限、风控或搜索计划确认。
- 不在 clean dry-run 之外写 campaign DB；主人才库永远不在无人值守 workflow 内写入。
- 计划确认后允许按 `run-policy.json` 自动发布飞书消息、云文档和多维表格；摘要内容和表格标题必须使用中文。

## 无人值守推进规则

- 搜索计划生成完毕后只在计划确认点停一次；确认后自动启动 CDP 浏览器，加载 `data/session/maimai-cdp-profile` 和 `extensions/maimai-scraper`，不再提示负责人手动启动浏览器。
- 确认进入无人值守后，搜索 clean dry-run 自动 apply 到 Campaign DB，列表全批次抓取完成后自动进入粗筛，生成 A/B/C/淘汰漏斗。
- 详情默认只抓取 A+B；当 A+B+C 总数不超过 100 时抓取 A+B+C。详情健康检查通过、详情 dry-run clean 后自动 apply 到 Campaign DB。
- 详情抓取完成后自动进入详评和精排，自动生成交付包并推送飞书；摘要内容和表格标题必须使用中文。
- Campaign DB 之后由人工手动整合进主 DB；本 workflow 只记录同步包/报告和人工整合入口，不自动写主库。

## 宽召回自适应实验模式

当 `strategy.json` 显式包含 `strategy_mode=broad_recall_adaptive_v1` 时，进入并行实验编排；默认无人值守流程不变。该模式用于脉脉扩库，不用于本流程内做人选推荐交付。

实验模式执行规则：

- 不设置 campaign 总页数上限。
- `account_day_page_guardrail=500` 表示单账号单日平台护栏，不是业务总预算。
- 用户手动换账号或次日恢复后，workflow 从 `state/continuation-plan.json` 继续。
- 每个 search unit 先探测 2 页，按页质规则继续、观察或停止。
- 连续低质量页停止 unit，状态写为 `stopped_low_quality`。
- 列表粗筛只产生详情优先级：`detail_p0`、`detail_p1`、`detail_p2`、`skip`。
- 详情并发首版上限为 4；出现验证码、429、403、432、安全页或 partial capture 立即停机。
- 详情 apply 到 Campaign DB 后只生成寻访摘要报告，不进入详评精排，不生成外联队列，不发布候选人交付包。
- 主库 `data/talent.db` 仍为人工边界。

## 停机条件

遇到以下任一情况必须停止当前阶段，不得继续翻页、重试 apply 或推进下游：登录页、登录失效、验证码、安全页、403、429、432、非 JSON、HTML 响应、模板漂移、详情 partial capture。

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl`，并更新 `state/continuation-plan.json` 作为下一次恢复的唯一计划入口。

## 恢复事实来源

- 搜索恢复事实来源：`raw/search/unit-*/page-*.json`。
- 详情恢复事实来源：`raw/detail-live/<pack_id>/job-*.json`。
- apply 防重事实来源：`state/import-ledger.jsonl`。
- 通知失败状态：`blocked_notification_failed`。

## 通知合同

所有通知统一通过 `scripts/campaign_notify.py` 执行。通知失败不得改变 campaign 执行结果；必须记录事件并把通知状态写为 `blocked_notification_failed`。

## 阶段

### S0 需求合同

读取 Skill 产出的 `requirements.json`、`strategy.json`、`run-policy.json`、`search-implementation-plan.md` 和 `campaign-manifest.json`，确认 campaign root、输入范围、预算、停止阈值、自动推进策略和主库手动边界。

### S1 预检

检查目录、配置、登录态只读可用性、既有 raw/state/reports，以及是否存在未完成或冲突的历史运行。若搜索计划已确认且 `auto_bootstrap_browser_after_plan_confirmation=true`，自动启动 CDP 浏览器并加载扩展；只等待登录/验证码/人才银行页健康条件，不要求负责人手动启动浏览器。

### S2 搜索计划展开

把关键词包展开为 search units，给每个 unit 分配 wave、页数上限、预算扣减规则和停止阈值。

### S3 搜索健康检查

只做必要的只读健康检查；遇到登录失效、验证码、非 JSON 响应、模板漂移或预算不足时停止。

### S4 搜索执行

按 unit/page 采集搜索响应，写入 `raw/search/unit-*/page-*.json`。真实执行阶段不自动导航、刷新、点击已进入执行态的脉脉业务页面。

### S5 搜索恢复

从 `raw/search/unit-*/page-*.json` 重建已完成页、失败页、预算使用和 continuation plan；不得盲信内存状态。

### S6 搜索导入 dry-run

标准化搜索 raw，执行 dry-run，报告 created/merged/duplicate/pending/errors，不写入正式 ledger。

### S7 搜索导入 apply

在 dry-run 干净且 `allow_campaign_db_auto_apply_after_clean_dry_run=true` 时自动写入 Campaign DB，并追加 `state/import-ledger.jsonl` 防重记录；不再要求额外人工确认。

### S8 初筛与 A/B 分档

基于岗位画像、关键词命中、经历质量、公司/行业匹配度和排除规则生成 A/B/C/淘汰漏斗。列表全批次抓取完成后自动进入粗筛，粗筛完成后自动进入详情 pack 计划。

### S9 详情 pack 计划

默认只抓取 A+B；当 A+B+C 总数不超过 100 时抓取 A+B+C。按每组上限 100 人拆分 detail pack，写明 pack id、候选人 id、profile url 和恢复路径。

### S10 详情执行与恢复

详情执行写入 `raw/detail-live/<pack_id>/job-*.json`；恢复时只信这些 job raw 和 pack manifest。

### S11 详情 dry-run 与 apply

先 dry-run 校验 matched/unmatched/failed/capture blockers；dry-run clean 且 `allow_detail_campaign_db_auto_apply_after_clean_dry_run=true` 时自动 apply 到 Campaign DB，并使用 `state/import-ledger.jsonl` 防止重复写入。

### S12 报告与交付包

详情 apply 后自动进入详评和精排，生成本地 Markdown 报告、CSV、候选人 Sheet 数据和 outreach queue 数据。`allow_feishu_delivery_publish=true` 时自动生成交付包并推送飞书；摘要内容和表格标题必须使用中文。

### S13 通知与关闭

记录最终状态、剩余风险、恢复入口和下一步动作。通知发送失败时状态写为 `blocked_notification_failed`，不得把通知失败误报为 campaign 执行成功。Campaign DB 之后由人工手动整合进主 DB；不得自动执行主库同步或主库写入。

### S14 交付反馈与下一轮策略调整

交付包发布后，若用户提供评价，必须落为 `feedback/delivery-feedback-<date>.json`，再运行：

```powershell
python -m scripts.maimai_campaign_feedback --feedback data/campaigns/<campaign_id>/feedback/delivery-feedback-<date>.json --out data/campaigns/<campaign_id>/feedback/strategy-adjustment-<date>.json
```

反馈至少包含候选人级 `good/maybe/bad`、原因码、缺失画像、公司池调整和 query/unit 调整。下一轮搜索必须先读取 `strategy-adjustment-*.json`，不得只根据聊天文字临时改关键词。

## 验收

- 任一阶段失败都必须留下可恢复的事实来源和明确状态。
- apply 类阶段必须能从 `state/import-ledger.jsonl` 判断是否重复执行。
- 真实脉脉请求、浏览器动作和飞书发布由搜索计划确认后的无人值守授权覆盖；登录/验证码/安全页等平台阻断仍必须停止。
- 主库写入不包含在无人值守授权内，必须人工手动整合。
