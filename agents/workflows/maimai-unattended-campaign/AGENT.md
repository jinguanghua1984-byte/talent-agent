---
name: maimai-unattended-campaign
description: 脉脉 unattended campaign 的 canonical workflow，约束搜索、详情、导入、报告和通知的阶段合同。
---

# maimai-unattended-campaign

## 安全边界

- 真实执行阶段不自动导航、刷新、点击已进入执行态的脉脉业务页面。
- 不绕过登录、验证码、权限、风控或用户确认。
- 不在未确认 dry-run 结果前写 campaign DB 或主人才库。
- 不发布飞书消息、云文档或多维表格，除非当前任务明确授权。

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

读取 Skill 产出的 `requirements.json`、`strategy.json`、`run-policy.json`、`search-implementation-plan.md` 和 `campaign-manifest.json`，确认 campaign root、输入范围、预算、停止阈值和人工确认点。

### S1 预检

检查目录、配置、登录态只读可用性、既有 raw/state/reports，以及是否存在未完成或冲突的历史运行。

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

在 dry-run 干净且得到明确确认后写入 campaign DB，并追加 `state/import-ledger.jsonl` 防重记录。

### S8 初筛与 A/B 分档

基于岗位画像、关键词命中、经历质量、公司/行业匹配度和排除规则生成 A/B/C/D 档。

### S9 详情 pack 计划

只对 A/B 档人选抓详情，按每组上限 100 人拆分 detail pack，写明 pack id、候选人 id、profile url 和恢复路径。

### S10 详情执行与恢复

详情执行写入 `raw/detail-live/<pack_id>/job-*.json`；恢复时只信这些 job raw 和 pack manifest。

### S11 详情 dry-run 与 apply

先 dry-run 校验 matched/unmatched/failed/capture blockers；得到明确确认后 apply，并使用 `state/import-ledger.jsonl` 防止重复写入。

### S12 报告与交付包

生成本地 Markdown 报告、CSV、候选人 Sheet 数据和 outreach queue 数据；涉及飞书云文档或多维表格发布时必须另行确认。

### S13 通知与关闭

记录最终状态、剩余风险、恢复入口和下一步动作。通知发送失败时状态写为 `blocked_notification_failed`，不得把通知失败误报为 campaign 执行成功。

## 验收

- 任一阶段失败都必须留下可恢复的事实来源和明确状态。
- apply 类阶段必须能从 `state/import-ledger.jsonl` 判断是否重复执行。
- 真实脉脉请求、浏览器动作、飞书发布和主库写入都必须有单独授权。
