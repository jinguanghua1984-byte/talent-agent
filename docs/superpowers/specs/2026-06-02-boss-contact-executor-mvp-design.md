# BOSS 当前详情页触达执行器 MVP 设计

> 日期：2026-06-02
> 状态：已完成设计；2026-06-02 已按 campaign 级授权执行器路径修订
> 基于：`docs/design-discussions/2026-06-02-boss-unattended-contact-executor-discussion.md`

## 1. 背景

现有 BOSS App 推荐列表寻访 workflow 已经能用 Computer Use 完成列表浏览、详情采集、筛选判定、dry-run 触达记录和真实姓名回采。真实无人值守的关键风险在 `立即沟通`：点击该按钮会向第三方候选人发送 BOSS 当前预设消息。因此真实点击必须走受 policy、intent、lock 和停止条件约束的外部执行器，而不是由 Computer Use 直接点击。

本设计将真实触达动作移出 Codex Computer Use。Codex 负责筛选、写入待触达 intent，并在用户给出 campaign 级真实触达授权后通过 `shell.run` 调用执行器；执行器负责当前详情页的真实点击、沟通页回采和审计日志。不具备 campaign 级授权时，只能展示命令等待用户手动执行。

## 2. 已确认决策

- MVP 范围采用“当前详情页触达执行器 + 文件握手”，不做完整队列消费器。
- 执行器纳入本仓库实现，遵守 `AGENTS.md`：业务脚本放在 `scripts/`，不放运行时目录。
- GUI 操作底座优先采用 macOS Accessibility / 本机 UI 自动化。
- 真实执行需要 campaign 级授权：用户明确说明“合适立即沟通、不用二次确认、联系 N 人后结束”等范围后，`executor-policy.json` 允许真实触达，并且 CLI 必须传入 `--execute`。
- 第一版生产入口是 `contact-current` 原子命令：只处理当前已打开详情页，不自己遍历列表、不自己判断谁合适。
- 第一版保留 dry-run / mock UI 测试能力，用于验证文件协议、状态机和审计日志。

## 3. 目标

1. Codex 在筛选到 `contact` 人选并停留在候选人详情页后，能写入结构化 `current-contact-intent.json`。
2. 执行器能读取 intent，校验当前 BOSS App 详情页与 intent 匹配。
3. 执行器只在按钮精确为 `立即沟通` 时点击；`继续沟通`、`立即联系牛人`、付费弹窗、验证码、安全页、登录页或未知 UI 均不得点击。
4. 执行器点击成功后能回采沟通页真实姓名、消息状态和可见发送证据。
5. 执行器写入 `executor-result.json` 和追加审计日志，供 Codex 或脚本回写现有 BOSS sourcing 产物。
6. 任意异常都要写入结构化停止原因，保留断点，不伪造成功触达。

## 4. 非目标

1. 不让 Codex Computer Use 无人值守点击 `立即沟通`。
2. 不把执行器设计成通用代点击工具；它只能在 campaign 级授权、当前详情页 intent 和 policy 均通过时处理当前候选人。
3. 不消费完整 `approved-contact-queue.jsonl` 并自动定位候选人。
4. 不实现常驻 `watch-intent` daemon；该能力留到验证当前页触达闭环后再设计。
5. 不绕过 BOSS 验证码、安全验证、登录、付费弹窗、搜索畅聊卡或平台日限额。
6. 不修改 BOSS 账号设置、职位设置、沟通话术或权限。
7. 不写主人才库 `data/talent.db`。

## 5. 架构

```text
BOSS App 当前详情页
  ^
  | macOS Accessibility / 本机 UI 自动化
  |
scripts/boss_contact_executor.py contact-current
  ^
  | 读取 intent / policy / lock
  | 写 result / audit
  |
data/campaigns/<campaign_id>/
  ^
  | Computer Use 筛选、详情采集、写 intent
  |
Codex + boss-app-recommendation-sourcing workflow
```

职责边界：

| 层 | 职责 | 明确不做 |
| --- | --- | --- |
| Codex 筛选层 | 浏览列表、采集详情、判定 `contact/hold/skip`、写 approved queue 和 current intent；在 campaign 级授权后调用执行器 | 不用 Computer Use 点击真实触达按钮 |
| 执行器层 | 校验当前详情页、点击 `立即沟通`、回采实名和消息状态、写审计日志 | 不遍历列表、不判断候选人是否合适 |
| 回写层 | 将执行器结果转成现有 `contact-decisions`、`communication-pages` 和 candidates 快照 | 不写主库、不修正筛选理由 |

## 6. 新增文件

```text
data/campaigns/<campaign_id>/
  executor-policy.json
  structured/
    approved-contact-queue.jsonl
  state/
    current-contact-intent.json
    executor.lock
    executor-result.json
    stop-executor.flag
  raw/
    executor-contact-attempts.jsonl
  reports/
    executor-summary.json
    executor-summary.md
    interruption-executor-*.json
```

`approved-contact-queue.jsonl` 是长期追加队列，用于审计“哪些候选人曾被筛选层批准触达”。MVP 执行器不主动消费它，但会校验当前 intent 对应候选人已经出现在该队列或当前 candidates 快照中。

`current-contact-intent.json` 是实时握手文件，只代表当前 BOSS App 已打开详情页的候选人。执行器只处理这个文件。

## 7. 执行器 policy

路径：`data/campaigns/<campaign_id>/executor-policy.json`。

最小结构：

```json
{
  "schema": "boss_contact_executor_policy_v1",
  "campaign_id": "boss-app-targeted-live-20260601",
  "allow_real_contact": true,
  "operator_acknowledgement": "I understand this sends real messages to third-party candidates.",
  "max_contacts_per_run": 1,
  "max_contacts_per_day": 50,
  "message_template_id": "boss-current-preset",
  "require_execute_flag": true,
  "skip_continue_chat": true,
  "stop_on_paid_prompt": true,
  "stop_on_captcha": true,
  "stop_on_login_or_security_page": true,
  "stop_on_unknown_ui": true,
  "capture_real_name_after_contact": true,
  "kill_switch_path": "data/campaigns/boss-app-targeted-live-20260601/state/stop-executor.flag"
}
```

规则：

1. `--execute` 缺失时，执行器只能 dry-run，不点击。
2. `--execute` 存在时，必须满足 `allow_real_contact=true`。
3. `operator_acknowledgement` 必须精确等于固定确认语。
4. `max_contacts_per_run` 在 MVP 中固定为 `1`；如果配置为其他值，真实执行拒绝启动。
5. `message_template_id` 只记录 BOSS 当前预设消息的审计标签；MVP 不修改 BOSS 话术。

## 8. Intent 协议

路径：`state/current-contact-intent.json`。

```json
{
  "schema": "boss_current_contact_intent_v1",
  "intent_id": "20260602T003000-boss-app-4e80b5a850ad",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:4e80b5a850adfb7321ac8fd1",
  "display_name": "陶先生",
  "current_company": "上海华为技术有限公司",
  "current_title": "博士后研究员-大模型方向",
  "expected_button": "立即沟通",
  "current_page": "candidate_detail",
  "approval_status": "approved_for_auto_contact",
  "score": 90,
  "reasons": [
    "华为目标公司",
    "大模型推理框架和 MoE 推理加速方向匹配"
  ],
  "risks": [
    "在职-暂不考虑"
  ],
  "message_template_id": "boss-current-preset",
  "created_by": "codex_screening_loop",
  "created_at": "2026-06-02T00:29:50+08:00",
  "expires_at": "2026-06-02T00:39:50+08:00"
}
```

执行器硬校验：

1. `schema` 必须是 `boss_current_contact_intent_v1`。
2. `approval_status` 必须是 `approved_for_auto_contact`。
3. `expected_button` 必须是 `立即沟通`。
4. `current_page` 必须是 `candidate_detail`。
5. 当前时间不得晚于 `expires_at`。
6. `candidate_key`、`display_name`、`current_company`、`current_title` 必须非空。

`expires_at` 默认由 Codex 设置为 `created_at + 10 分钟`。过期 intent 不执行，防止页面已经变化但旧 intent 仍残留。

## 9. 当前页面匹配规则

执行器点击前必须通过 UI 校验：

1. 当前前台 App 是 BOSS App 或可识别为 BOSS App 窗口。
2. 当前页面是候选人详情页，不是列表页、沟通页、搜索结果页或营销模块页。
3. 页面可见展示名必须包含 `display_name`。
4. 页面可见文本必须包含 `current_company` 或 `current_title` 中至少一个；如果公司和职位都无法匹配，停止为 `page_mismatch`。
5. 页面不得出现 `热搜牛人推荐`、`查看更多牛人`、`去看看` 等营销入口作为当前主页面。
6. 页面不得出现搜索付费相关文本，例如 `搜索畅聊卡`、`剩余次数不足`、`立即开聊`。

匹配失败时不点击，写入 `executor-result.json`：

```json
{
  "result": "stopped",
  "stopped_reason": "page_mismatch",
  "next_action_for_codex": "write_interruption_and_stop"
}
```

## 10. 按钮规则

执行器只允许点击精确文案 `立即沟通`。

| 识别结果 | 行为 | result |
| --- | --- | --- |
| `立即沟通` | 允许点击 | `sent` 或后续阻断结果 |
| `继续沟通` | 不点击，记录已沟通过 | `skipped_continue_chat` |
| `立即联系牛人` | 不点击，按付费/搜索详情风险停止 | `stopped_paid_or_search_contact` |
| 找不到按钮 | 不点击，停止 | `button_not_found` |
| 多个疑似按钮 | 不点击，停止 | `ambiguous_contact_button` |

`继续沟通` 不算错误，但必须写审计日志，Codex 后续可返回列表继续。

## 11. 执行状态机

```text
load_policy
  -> acquire_lock
  -> load_intent
  -> validate_intent
  -> preflight_ui
  -> validate_page_match
  -> validate_button
  -> click_contact
  -> wait_communication_page
  -> capture_real_name_and_message_status
  -> write_result
  -> release_lock
```

任一阶段失败都进入：

```text
write_result(stopped/skipped)
  -> append_audit_event
  -> mark_lock_released_or_stopped
  -> exit_nonzero_for_stopped
```

`stop-executor.flag` 在 `load_policy`、`preflight_ui`、`click_contact` 前各检查一次。点击已经发出后不再中断回采流程，避免留下未记录的真实发送。

## 12. Result 协议

路径：`state/executor-result.json`。

成功：

```json
{
  "schema": "boss_executor_result_v1",
  "intent_id": "20260602T003000-boss-app-4e80b5a850ad",
  "campaign_id": "boss-app-targeted-live-20260601",
  "candidate_key": "boss-app:4e80b5a850adfb7321ac8fd1",
  "result": "sent",
  "button_before_click": "立即沟通",
  "message_template_id": "boss-current-preset",
  "message_status": "送达",
  "real_name": "陶壮",
  "communication_page_text": "沟通页顶部：陶壮；AI Infra训练与推理研发...",
  "next_action_for_codex": "record_contact_return_to_list_and_continue",
  "stopped_reason": null,
  "started_at": "2026-06-02T00:30:00+08:00",
  "finished_at": "2026-06-02T00:30:08+08:00"
}
```

跳过已沟通：

```json
{
  "schema": "boss_executor_result_v1",
  "result": "skipped_continue_chat",
  "button_before_click": "继续沟通",
  "real_name": null,
  "message_status": null,
  "next_action_for_codex": "record_skip_return_to_list_and_continue",
  "stopped_reason": null
}
```

阻断：

```json
{
  "schema": "boss_executor_result_v1",
  "result": "stopped",
  "button_before_click": "立即联系牛人",
  "real_name": null,
  "message_status": null,
  "next_action_for_codex": "write_interruption_and_stop",
  "stopped_reason": "paid_search_chat_card"
}
```

`result=sent` 的最低条件：

1. 点击前按钮是 `立即沟通`。
2. 点击后进入沟通页或可确认的会话页面。
3. 回采到非空 `real_name`。
4. 回采到 `送达`、`已读`、`已触达` 中任一消息状态。

如果点击后进入沟通页但无法回采实名或消息状态，结果为 `sent_unverified`，必须停止，等待人工复核。

## 13. 审计日志

路径：`raw/executor-contact-attempts.jsonl`。

每次执行至少追加两个事件：

```json
{
  "schema": "boss_contact_attempt_event_v1",
  "event_type": "attempt_started",
  "attempt_id": "20260602T003000-boss-app-4e80b5a850ad",
  "intent_id": "20260602T003000-boss-app-4e80b5a850ad",
  "candidate_key": "boss-app:4e80b5a850adfb7321ac8fd1",
  "started_at": "2026-06-02T00:30:00+08:00"
}
```

```json
{
  "schema": "boss_contact_attempt_event_v1",
  "event_type": "attempt_finished",
  "attempt_id": "20260602T003000-boss-app-4e80b5a850ad",
  "candidate_key": "boss-app:4e80b5a850adfb7321ac8fd1",
  "button_before_click": "立即沟通",
  "action": "click_contact",
  "result": "sent",
  "message_status": "送达",
  "real_name": "陶壮",
  "stopped_reason": null,
  "finished_at": "2026-06-02T00:30:08+08:00"
}
```

如已发出点击但进程崩溃，下次启动时发现 lock 或未完成 attempt，必须先进入 recovery preflight，不允许直接再次点击同一 candidate。

## 14. 锁与恢复

`state/executor.lock` 使用原子创建。内容：

```json
{
  "schema": "boss_executor_lock_v1",
  "lock_id": "20260602T003000-boss-app-4e80b5a850ad",
  "intent_id": "20260602T003000-boss-app-4e80b5a850ad",
  "candidate_key": "boss-app:4e80b5a850adfb7321ac8fd1",
  "status": "running",
  "created_at": "2026-06-02T00:30:00+08:00",
  "pid": 12345
}
```

结束时不删除锁文件，而是更新为：

```json
{
  "status": "finished",
  "finished_at": "2026-06-02T00:30:08+08:00",
  "result": "sent"
}
```

如果发现 `status=running` 且进程不存在，执行器不自动清理真实执行锁；它写 `stale_lock_requires_review` 并退出。只有 dry-run/mock 模式可在测试中自动清理。

## 15. 与现有 BOSS sourcing 的集成

现有 `scripts/boss_app_sourcing.py` 保持主记录语义：

- `structured/candidates.jsonl` 保存候选人快照。
- `structured/contact-decisions.jsonl` 保存 would-contact / contacted 决策。
- `raw/communication-pages.jsonl` 保存沟通页回采文本。
- `reports/sourcing-summary.*` 统计触达和实名回填。

新增或扩展 helper：

| helper | 职责 |
| --- | --- |
| `record_approved_contact_queue_item` | 对 `detail_decision=contact` 且按钮为 `立即沟通` 的候选人追加 approved queue |
| `write_current_contact_intent` | 在当前详情页写实时 intent |
| `consume_executor_result` | 读取 executor-result，回写 contact decision、communication page 和 candidates 快照 |
| `summarize_executor_results` | 生成 executor summary |
| `validate_executor_artifacts` | 校验 intent/result/audit/lock 的一致性 |

`consume_executor_result` 的行为：

- `sent`：追加 `contact-decisions.jsonl`，`mode=external_executor`，`contacted=true`；追加 `raw/communication-pages.jsonl`；回填 `real_name_source=communication_page_after_external_executor`。
- `skipped_continue_chat`：追加 contact decision，标记 `already_contacted=true`、`contacted=false`、`skip_reason=continue_chat`。
- `sent_unverified` 或 `stopped`：更新 `state/continuation-plan.json`，写 `reports/interruption-executor-*.json`，不继续自动推进。

## 16. CLI 设计

生产命令：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id> \
  --execute
```

dry-run 命令：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id>
```

mock UI 测试命令：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id> \
  --mock-ui-fixture tests/fixtures/boss_contact_executor/detail-ready.json
```

辅助命令：

```bash
.venv/bin/python -m scripts.boss_contact_executor validate \
  --campaign-root data/campaigns/<campaign_id>

.venv/bin/python -m scripts.boss_contact_executor summarize \
  --campaign-root data/campaigns/<campaign_id>
```

CLI 退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | sent、skipped_continue_chat 或 dry-run 成功 |
| `2` | policy / intent / schema 校验失败 |
| `3` | UI 不匹配、按钮异常、付费/验证码/安全阻断 |
| `4` | lock 或恢复状态需要人工处理 |

## 17. macOS UI 适配边界

执行器内部抽象 `BossContactUI`：

```text
read_current_page() -> BossPageSnapshot
find_contact_button(snapshot) -> ContactButtonState
click_contact(button) -> ClickResult
wait_for_communication_page() -> BossPageSnapshot
extract_communication_result(snapshot) -> CommunicationResult
```

实现：

- `MacAccessibilityBossUI`：真实 macOS UI 自动化。
- `FixtureBossUI`：测试 fixture，不接触真实 UI。

`BossPageSnapshot` 只保存文本、可访问元素摘要、按钮文案、窗口标题和可选截图哈希；默认不保存截图文件。

## 18. 错误处理

硬停止条件：

- `stop-executor.flag` 存在。
- intent 过期。
- 当前页和 intent 不匹配。
- 按钮不是 `立即沟通`。
- 出现 `搜索畅聊卡`、`立即开聊`、`剩余次数不足`、付费提示。
- 出现验证码、安全验证、登录页。
- 点击后无法确认沟通页。
- 点击后无法回采实名或消息状态。
- stale lock 未人工处理。

所有硬停止都必须：

1. 写 `executor-result.json`。
2. 追加 `raw/executor-contact-attempts.jsonl`。
3. 写或更新 `state/continuation-plan.json`。
4. 写 `reports/interruption-executor-<reason>-<timestamp>.json`。

## 19. 测试策略

新增测试文件：

- `tests/test_boss_contact_executor.py`
- 必要时扩展 `tests/test_boss_app_sourcing.py`
- 必要时扩展 `tests/test_agent_architecture.py`

重点测试：

1. policy 缺 `--execute` 时不点击。
2. `allow_real_contact=false` 时即使传 `--execute` 也拒绝。
3. acknowledgement 不匹配时拒绝。
4. intent schema、approval、expected button、expires_at 校验。
5. 页面匹配要求 display name + company/title。
6. `继续沟通` 跳过且不点击。
7. `立即联系牛人` 和 `搜索畅聊卡` 停止。
8. sent 成功结果写入 result 和 audit。
9. sent_unverified 停止并保留断点。
10. stale lock 不自动清理。
11. `consume_executor_result` 正确回写现有 candidates、contact-decisions、communication-pages。
12. validate/summarize 能识别 result、audit 和 contact decision 是否一致。

验证命令：

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py tests/test_boss_app_sourcing.py -q
.venv/bin/python -m pytest tests -q
git diff --check
```

## 20. 验收标准

MVP 通过以下标准才算完成：

1. dry-run/mock 模式能完整验证 intent -> result -> audit -> consume result 的文件链路。
2. 真实 `--execute` 模式在 policy 和 intent 不满足时拒绝点击。
3. 真实 `--execute` 模式只会点击 `立即沟通`。
4. `继续沟通`、`立即联系牛人`、付费弹窗、验证码、安全页、登录页均不点击。
5. 成功触达后能回采真实姓名和 `送达/已读/已触达` 状态。
6. 成功触达后现有 BOSS sourcing summary 能统计 external executor 触达和实名回填。
7. 任意阻断都能留下 `executor-result.json`、audit JSONL、interruption report 和 continuation plan。
8. 用户无需在 Codex 中对每个候选人的 `立即沟通` 做动作级确认；真实点击由用户显式启动的外部执行器完成。

## 21. 后续阶段

P2：`watch-intent` 常驻执行器。用户启动一次后，执行器轮询新 intent，在 `max_contacts_per_run` 内连续处理当前详情页触达。该阶段需要额外解决重复消费、陈旧 intent、长时间锁、进程健康和 kill switch 响应。

P3：完整队列消费执行器。执行器读取 `approved-contact-queue.jsonl`，自己定位候选人并连续触达。该阶段需要单独设计候选人定位、列表恢复、重复卡片、营销模块绕过和平台风控节流，不应混入 MVP。
