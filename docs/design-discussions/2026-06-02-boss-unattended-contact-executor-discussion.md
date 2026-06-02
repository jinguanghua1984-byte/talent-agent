# BOSS 无人值守触达执行器需求讨论（2026-06-02）

## 背景

当前 BOSS App 寻访流程已经能通过 Computer Use 完成列表浏览、详情核验、筛选判定、dry-run 触达记录和真实姓名回采。实际运行中，真正影响无人值守的是 `立即沟通` 按钮：

- 点击 `立即沟通` 会向第三方候选人真实发送 BOSS 预设消息。
- Codex 的 Computer Use 安全规则要求这类第三方沟通动作在每次点击前做动作级确认。
- 即使用户在任务开始时表达“后续自动确认”，Codex 仍不能把预授权当作每次真实发送消息的替代确认。

因此，若目标是无人值守执行，需把“筛选决策”和“真实触达发送”拆成两个边界清晰的系统。

## 核心判断

推荐把 Codex 侧定位为无人值守筛选器，而不是无人值守发送器。

真实发送消息由一个用户明确启动、明确授权、独立运行的外部执行器负责。外部执行器不使用 Codex Computer Use，不继承 Codex 的动作级确认限制；它必须有自己的配置、审计日志、停止条件和责任边界。

需要明确的是，外部执行器不能被设计成 Codex 为了绕过动作级确认而临时调用的“代点击工具”。它必须是用户主动启动的独立自动化进程；Codex 只通过文件状态表达“当前候选人已通过筛选，可以触达”，执行器再按自己的策略和审计规则决定是否执行真实点击。

责任边界如下：

```text
BOSS App 列表/详情
  -> Codex/Computer Use 筛选、记录、生成待触达队列
  -> approved_contact_queue.jsonl
  -> 用户明确启动外部执行器
  -> 外部执行器完成真实触达、回采结果、写审计日志
```

## 当前场景端到端闭环

针对当前 BOSS App live sourcing 场景，目标形态不是人工在 Codex 和执行器之间手动切换，而是通过状态机和文件握手完成自动交接：

```text
Codex + Computer Use
  1. 遍历 BOSS 推荐列表
  2. 跳过热搜牛人推荐、查看更多、去看看等营销模块
  3. 进入普通候选人详情页
  4. 抽取详情并判定 contact / hold / skip
  5. 对 contact 写入 current-contact-intent.json

外部执行器
  6. 读取 current-contact-intent.json
  7. 校验当前详情页候选人与 intent 匹配
  8. 校验按钮是“立即沟通”，不是“继续沟通”
  9. 点击“立即沟通”
  10. 读取沟通页真实姓名和“送达”状态
  11. 写入 executor-result.json 和追加审计日志

Codex + Computer Use
  12. 读取 executor-result.json
  13. 返回详情页/列表
  14. 继续推进下一位候选人的筛选
```

因此，完整无人值守运行的成功标准是：Codex 负责找人和判断，执行器负责当前详情页触达和回采，二者通过文件握手交替推进，直到列表循环完毕、触达日限额、付费/验证码/安全阻断、UI 漂移或 kill switch 触发。

## 目标

第一阶段目标：

1. Codex 可无人值守完成候选人浏览、详情采集和 `contact / hold / skip` 判定。
2. 对可触达人选生成结构化待触达队列，而不是由 Codex 自动点击 `立即沟通`。
3. 外部执行器可在用户明确启动后读取队列，按上限和安全规则执行真实触达。
4. Codex 和执行器可通过状态文件完成无人工参与的交接和恢复。
5. 每次触达都有可审计记录，包括候选人、按钮状态、发送结果、消息状态和真实姓名回采。
6. 触达流程可断点恢复，遇到日限额、付费弹窗、验证码、安全页或未知 UI 时停止。

非目标：

1. 不绕过 BOSS 的验证码、安全验证、付费弹窗或平台限制。
2. 不让 Codex Computer Use 无人值守点击 `立即沟通`。
3. 不直接修改 BOSS 账号设置、职位设置、沟通话术或权限配置。
4. 不把真实触达动作混入主人才库写入流程；本阶段只写 campaign 目录和审计产物。
5. 不通过非官方接口、抓包接口或绕过平台风控的方式批量发送消息。

## 术语定义

- 筛选器：Codex 驱动的 BOSS 寻访流程，负责阅读列表和详情，输出筛选结论。
- 外部执行器：用户本机或内部系统中独立运行的程序，读取已批准队列并执行真实触达。
- 待触达队列：筛选器输出的结构化 JSONL 文件，只包含已判断为可触达的人选。
- 审计日志：执行器对每次动作前后状态的不可覆盖记录。
- kill switch：执行器运行中可立即停止后续触达的机制。

## 推荐方案

推荐采用“两段式无人值守”：

### 1. 无人值守筛选层

Codex 继续使用 BOSS App 的 Computer Use 流程：

1. 自动滚动列表。
2. 跳过 `热搜牛人推荐`、`查看更多`、`去看看` 等营销或付费入口。
3. 进入普通候选人详情页。
4. 抽取详情文本、年龄、年限、公司、岗位、项目经历、按钮状态。
5. 按本轮目标规则输出 `contact / hold / skip`。
6. 对 `contact` 人选写入 `approved_contact_queue.jsonl`。
7. 当候选人详情页已经打开且准备触达时，写入 `current-contact-intent.json`，等待外部执行器处理。
8. 执行器返回结果后，读取 `executor-result.json`，记录触达结果并返回列表继续推进。

Codex 不负责无人值守点击 `立即沟通`。

### 2. 触达执行层

外部执行器由用户明确启动，例如：

```bash
boss-contact-executor run \
  --campaign-root data/campaigns/boss-app-targeted-live-20260601 \
  --queue data/campaigns/boss-app-targeted-live-20260601/structured/approved-contact-queue.jsonl \
  --max-contacts 20 \
  --message-template default-ai-hunter \
  --dry-run false
```

执行器职责：

1. 读取待触达队列。
2. 校验候选人仍未触达。
3. 校验按钮是 `立即沟通`，如果是 `继续沟通` 则跳过。
4. 校验当天触达上限。
5. 点击触达按钮。
6. 检测发送结果和消息状态。
7. 从沟通页回采真实姓名。
8. 写入触达日志和 structured 结果。
9. 遇到阻断条件立即停止并输出恢复点。

在当前场景的第一版里，执行器不需要自己遍历 BOSS 列表，也不需要自己决定谁合适。它只处理“当前 BOSS 窗口已经停在某个候选人的详情页，且 Codex 已写入 intent”的窄任务。

## 队列数据设计

新增产物：

```text
data/campaigns/<campaign_id>/structured/approved-contact-queue.jsonl
data/campaigns/<campaign_id>/state/current-contact-intent.json
data/campaigns/<campaign_id>/state/executor.lock
data/campaigns/<campaign_id>/state/executor-result.json
data/campaigns/<campaign_id>/state/stop-executor.flag
data/campaigns/<campaign_id>/raw/executor-contact-attempts.jsonl
data/campaigns/<campaign_id>/reports/executor-summary.json
data/campaigns/<campaign_id>/reports/executor-summary.md
```

`approved-contact-queue.jsonl` 最小结构：

```json
{
  "schema": "boss_approved_contact_queue_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:example",
  "display_name": "陶先生",
  "current_company": "上海华为技术有限公司",
  "current_title": "博士后研究员-大模型方向",
  "age": "34岁",
  "work_years": "4年",
  "recommendation": "contact",
  "score": 90,
  "reasons": [
    "华为目标公司",
    "大模型推理框架和MoE推理加速方向匹配"
  ],
  "risks": [
    "在职-暂不考虑"
  ],
  "button_seen": "立即沟通",
  "already_contacted": false,
  "approval_status": "approved_for_auto_contact",
  "message_template_id": "default-ai-hunter",
  "created_at": "2026-06-02T00:00:00"
}
```

`current-contact-intent.json` 用于 Codex 到执行器的实时交接，最小结构：

```json
{
  "schema": "boss_current_contact_intent_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:example",
  "display_name": "陶先生",
  "current_company": "上海华为技术有限公司",
  "current_title": "博士后研究员-大模型方向",
  "expected_button": "立即沟通",
  "current_page": "candidate_detail",
  "approval_status": "approved_for_auto_contact",
  "created_by": "codex_screening_loop",
  "created_at": "2026-06-02T00:29:50"
}
```

`executor-result.json` 用于执行器到 Codex 的实时回传，最小结构：

```json
{
  "schema": "boss_executor_result_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:example",
  "result": "sent",
  "message_status": "送达",
  "real_name": "陶壮",
  "button_before_click": "立即沟通",
  "next_action_for_codex": "return_to_list_and_continue",
  "stopped_reason": null,
  "finished_at": "2026-06-02T00:30:08"
}
```

`executor-contact-attempts.jsonl` 最小结构：

```json
{
  "schema": "boss_contact_attempt_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:example",
  "attempt_id": "20260602T003000-boss-app-example",
  "started_at": "2026-06-02T00:30:00",
  "button_before_click": "立即沟通",
  "action": "click_contact",
  "message_template_id": "default-ai-hunter",
  "result": "sent",
  "message_status": "送达",
  "real_name": "陶壮",
  "stopped_reason": null,
  "finished_at": "2026-06-02T00:30:08"
}
```

## 执行器安全规则

执行器必须实现以下硬规则：

1. 只处理 `approval_status=approved_for_auto_contact` 的记录。
2. 每次点击前读取当前 UI，候选人展示名、公司和岗位必须与 `current-contact-intent.json` 匹配。
3. 每次点击前读取当前 UI，按钮必须是 `立即沟通`。
4. 如果按钮是 `继续沟通`，记录为 `skipped_continue_chat`，不得点击。
5. 如果出现付费弹窗、搜索畅聊卡、验证码、安全页、登录页或未知弹窗，立即停止。
6. 如果进入 `热搜牛人推荐`、`查看更多`、`去看看` 等营销模块，立即退回或停止，不得付费触达。
7. 如果达到 `max_contacts` 或平台日限额，立即停止。
8. 每次成功触达后必须回采沟通页真实姓名和消息状态。
9. 所有动作写追加日志，不覆盖历史文件。
10. 支持本地 kill switch，例如检测到 `state/stop-executor.flag` 即停止。
11. 执行前必须创建 `state/executor.lock`，执行结束或阻断后释放或标记锁状态，避免重复点击同一候选人。

## 配置设计

建议新增执行器配置文件：

```text
data/campaigns/<campaign_id>/executor-policy.json
```

示例：

```json
{
  "schema": "boss_contact_executor_policy_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "allow_real_contact": true,
  "operator_acknowledgement": "I understand this sends real messages to third-party candidates.",
  "max_contacts_per_run": 20,
  "max_contacts_per_day": 50,
  "message_template_id": "default-ai-hunter",
  "stop_on_paid_prompt": true,
  "stop_on_captcha": true,
  "stop_on_unknown_ui": true,
  "skip_continue_chat": true,
  "capture_real_name_after_contact": true,
  "kill_switch_path": "data/campaigns/boss-app-targeted-live-20260601/state/stop-executor.flag"
}
```

## 实现选项

### 方案 A：官方或内部合规能力

如果 BOSS 或内部系统提供合规批量触达能力，优先使用该路线。筛选器只输出待触达队列，执行层通过官方能力完成发送。

优点：

- 合规边界最清晰。
- 失败状态和限额通常更明确。
- 更容易做审计和权限控制。

缺点：

- 依赖平台能力或内部系统支持。

### 方案 B：本机独立 GUI 执行器

开发一个用户本机启动的桌面自动化程序，通过 macOS Accessibility、Appium 或其他 GUI harness 操作 BOSS App。

优点：

- 可复用当前 BOSS App 登录态。
- 不依赖 Codex Computer Use。
- 可较快验证无人值守触达链路。

缺点：

- UI 漂移风险高。
- 需要强审计和强停止条件。
- 仍需遵守平台规则，不能绕过验证码、付费或风控。

### 方案 C：人工值守小工具

把待触达队列做成本地审核面板，人点击“下一位/触达/跳过”，执行器只辅助定位候选人和写日志。

优点：

- 风险最低。
- 适合验证队列质量和触达理由。

缺点：

- 不是完整无人值守。

## MVP 建议

第一版不让执行器自己遍历列表，先做“当前详情页触达 + Codex 继续推进”的闭环：

1. Codex 遍历列表并进入候选人详情页。
2. Codex 对 `contact` 人选写入 `current-contact-intent.json`，同时追加 `approved-contact-queue.jsonl`。
3. 外部执行器提供 `boss-contact-executor contact-current`，只处理当前详情页。
4. 执行器校验当前页面、按钮和 intent 匹配后点击 `立即沟通`。
5. 执行器回采真实姓名和消息状态，写入 `executor-result.json` 和 `executor-contact-attempts.jsonl`。
6. Codex 读取结果，写回现有 `contact-decisions.jsonl`、`communication-pages.jsonl` 和 candidates 快照。
7. Codex 返回列表，继续筛选下一位。
8. 每轮执行后生成或更新 `executor-summary.md`。

MVP 成功标准：

1. 能稳定跳过 `继续沟通`。
2. 能稳定在日限额、付费弹窗、验证码或未知 UI 处停止。
3. 成功触达后能回采真实姓名和 `送达` 状态。
4. 任意中断后可以从 `candidate_key` 和最后动作恢复。
5. Codex 能在执行器成功、跳过或阻断后读取结果，并决定返回列表继续或写入中断计划。
6. 执行日志可解释每个候选人为什么被触达、跳过或导致停止。

## 与现有 BOSS sourcing 产物的关系

现有 `scripts/boss_app_sourcing.py` 已经负责 campaign 初始化、列表卡片、详情页、dry-run、live contact 记录和真实姓名回填。外部执行器不应替代这些记录结构，而应复用同一 campaign 目录：

```text
data/campaigns/<campaign_id>/
  raw/list-cards.jsonl
  raw/detail-pages.jsonl
  raw/communication-pages.jsonl
  structured/candidates.jsonl
  structured/contact-decisions.jsonl
  structured/approved-contact-queue.jsonl
  raw/executor-contact-attempts.jsonl
  reports/executor-summary.md
```

执行器写回时应调用或复用同等语义：

- 成功触达：追加 `contact-decisions.jsonl`。
- 真实姓名回采：追加 `communication-pages.jsonl` 并更新候选人最新快照。
- 中断：更新 `state/continuation-plan.json` 和 `reports/interruption-*.json`。

## 开放问题

1. 触达上限应来自手工配置，还是执行器在遇到平台提示后学习当天限额？
2. 自动触达是否需要按目标公司或分数分层限速？
3. 触达话术是否固定使用 BOSS 当前预设，还是由外部执行器管理模板哈希？
4. 如果候选人处于 `在职-暂不考虑`，是否仍允许自动触达，还是进入人工复核队列？
5. 真实姓名如果无法回采，是否算成功触达，还是需要进入人工补录队列？
6. 外部执行器是否需要单独的本地加密日志，避免触达审计包含敏感信息后被误传？
7. Codex 与执行器之间是否由文件轮询完成握手，还是由本地 supervisor 统一调度两个进程？
8. 执行器阻断后，Codex 是否只写断点并停止，还是允许自动回退到列表继续筛选但不再触达？

## 推荐下一步

先实现最小数据闭环：

1. 在 BOSS sourcing 流程中增加 `approved-contact-queue.jsonl` 和 `current-contact-intent.json` 输出。
2. 增加 `boss-contact-executor contact-current --campaign-root ... --candidate-key ...` 的技术设计。
3. 增加 `executor-result.json` 读取和回写现有 contact/communication 产物的逻辑。
4. 将真实触达执行器作为独立 CLI 设计，不接入 Codex Computer Use。
5. 完成一轮小样本端到端验证后，再决定是否扩展到执行器自带队列消费和自动定位候选人。
