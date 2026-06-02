---
name: boss-app-recommendation-sourcing
description: Use when the user wants to source candidates from the BOSS App recommendation list by operating the local BOSS App UI, screening cards and details, recording would-contact decisions, optionally running small confirmed live-contact tests, or backfilling real names from communication pages.
---

# boss-app-recommendation-sourcing

## 目标

把一次 BOSS App 推荐列表寻访整理成可执行、可恢复、可审计的任务合同。用户先打开本机 BOSS App 并进入目标职位的牛人推荐列表页；本 Skill 只负责需求抽取、合同生成、安全边界和 workflow 交接。

## 触发语义

用户表达以下意图时使用本 Skill：

- 从 BOSS App 推荐列表逐个看人选。
- 在 BOSS App 里按公司、职位、学历、年龄、技术栈等进一步筛选推荐人选。
- 用 Computer Use 操作 BOSS App 采集列表和详情。
- 对合适人选记录 `would_contact` 或做少量动作级确认的 `立即沟通` live-test。
- 从已沟通页面回采真实姓名。

不要使用 `platform-match` 网页搜索 workflow；本流程不操作 BOSS 网页端，不调用 BOSS API，不复用 CDP 搜索链路。

## 输入抽取

BOSS 推荐列表本身已经基于 JD 生成。用户通常只提供进一步筛选依据，例如：

- 目标公司或排除公司。
- 职位/职能/职级。
- 学历、年龄、城市、薪资。
- 技术栈、业务方向、行业背景。
- 必须项、加分项、排除项。

只对缺失或冲突的关键字段提问；能稳定抽取的字段直接写入 `requirements.json` 和 `strategy.json`。

## 默认运行策略

- `execution_surface="boss_app_computer_use"`
- `contact_mode="dry_run"`
- `allow_real_contact=false`
- `allow_live_contact_test=false`
- `live_contact_test_limit=0`
- `require_action_time_confirmation_for_real_contact=true`
- `capture_real_name_after_contact=true`
- 默认绝不点击 `立即沟通`；只有同时开启 `allow_real_contact=true` 和 `allow_live_contact_test=true`，且满足测试上限与动作级确认后，才允许少量 live-test 真实点击。
- 首版详情证据只保存结构化文本和截图哈希，不保存截图文件。
- 主人才库写入不在本 workflow 内执行。

## 输出产物

默认根目录：`data/campaigns/<campaign_id>/`。

必须生成：

- `requirements.json`
- `strategy.json`
- `run-policy.json`
- `campaign-manifest.json`
- `raw/list-cards.jsonl`
- `raw/detail-pages.jsonl`
- `raw/communication-pages.jsonl`
- `raw/screen-hashes.jsonl`
- `state/events.jsonl`
- `state/processed-cards.jsonl`
- `state/continuation-plan.json`
- `structured/candidates.jsonl`
- `structured/contact-decisions.jsonl`
- `reports/sourcing-summary.md`
- `reports/sourcing-summary.json`

可选外部触达执行器产物，只用于用户显式启动的外部执行器 handoff：

- `structured/approved-contact-queue.jsonl`
- `state/current-contact-intent.json`
- `state/executor.lock`
- `state/executor-result.json`
- `state/stop-executor.flag`
- `raw/executor-contact-attempts.jsonl`
- `reports/executor-summary.md`
- `reports/executor-summary.json`

Codex/Computer Use 不因这些文件存在而无人值守点击 `立即沟通`；这些文件只表达已审核触达意图、执行器审计和回写结果。

## 安全边界

- 默认不点击 `立即沟通`。
- 少量 live-test 真实点击必须同时满足 `allow_real_contact=true` 和 `allow_live_contact_test=true`，受 `live_contact_test_limit` 限制，并且每次点击前通过 `human.confirm` 动作级确认。
- BOSS App 点击 `立即沟通` 会自动发送预设消息，必须把这一副作用告知用户后再确认。
- 若采用外部触达执行器，Codex 只写 `structured/approved-contact-queue.jsonl` 和 `state/current-contact-intent.json`，不点击真实触达按钮；真实点击只能由用户显式启动独立 CLI，例如 `scripts.boss_contact_executor contact-current --execute`。
- 沟通页证据必须写入 `raw/communication-pages.jsonl`，真实姓名回填必须同步更新结构化候选人与沟通决策产物。
- 不处理验证码，不绕过安全页，不修改 BOSS App 设置、职位设置、沟通话术或账号权限。
- 真实姓名来自 live-test 后沟通页，或用户手动打开的已沟通页面；不能用真实姓名覆盖 `display_name`。

## 自动交接

合同文件生成后，读取并执行 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。真实 App 操作由 canonical workflow 通过 `computer.operate` 描述，运行时适配器映射到对应桌面 UI 操作能力。
