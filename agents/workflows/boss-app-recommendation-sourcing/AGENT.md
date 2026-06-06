---
name: boss-app-recommendation-sourcing
description: BOSS App 推荐列表寻访 canonical workflow，约束合同、本地 App UI 操作、安全确认、真实姓名回填、恢复和报告。
---

# boss-app-recommendation-sourcing

## 触发入口

- 从 `agents/skills/boss-app-recommendation-sourcing/SKILL.md` 完成需求抽取和合同生成后交接执行。
- 用户要求继续、恢复、中断后接着扫 BOSS App 推荐列表、回采已沟通真实姓名或执行少量 live-test 时，读取本 workflow 并按当前状态继续。

## 能力边界

- 使用 `file.read`、`file.write`、`shell.run`、`computer.operate` 和 `human.confirm`。
- 不使用 BOSS 网页端、CDP、浏览器扩展或 BOSS API。
- Python 脚本只负责合同、状态、结构化和报告；App UI 操作由 `computer.operate` 执行。
- 浏览、滚屏、进详情、返回列表、展开详情等 App 页面操作全部使用 Computer Use / `computer.operate`。
- 只有当前详情页已确认触达、`state/current-contact-intent.json` 与 `executor-policy.json` 均满足时，才使用外部执行器点击精确文案 `立即沟通`。
- 不得使用 osascript、坐标点击、截图脚本点击或其它本机自动化替代 Computer Use 做列表浏览、详情采集、滚屏、返回或筛选判断。
- 如果运行时 Computer Use 缺失或不可调用，停止推进并写 `state/continuation-plan.json`；不得用 shell/UI 脚本继续浏览。

## 安全边界

- 默认 `contact_mode=dry_run`，只定位 `立即沟通`，记录 `would_contact`，不点击。
- 默认 `allow_real_contact=false`，因此默认绝不点击 `立即沟通`。
- live-test 真实点击必须同时满足 `allow_real_contact=true` 和 `allow_live_contact_test=true`、未超过 `live_contact_test_limit`、候选人 `recommendation=contact`，并在点击前用 `human.confirm` 说明候选人、判定理由和自动发送预设消息的副作用。
- campaign 级真实触达授权是独立于 live-test 的执行器路径。用户明确给出“合适立即沟通、不用二次确认、联系 N 人后结束”等授权时，本 workflow 可通过 `shell.run` 调用外部执行器；不再对每位候选人调用 `human.confirm`。
- 外部执行器只能点击当前详情页精确文案 `立即沟通`。列表滚动、详情采集、候选筛选、回到列表和报告由 `computer.operate` 与 sourcing helper 完成；不得让执行器遍历列表或判断候选人是否合适。
- 登录失效、验证码、安全页、权限弹窗、系统遮挡、UI 模板漂移或疑似真实发送风险时必须停止，写入 `reports/interruption-<stage>-<reason>-<timestamp>.json`，更新 `state/continuation-plan.json`，并追加到 `state/events.jsonl`。
- 不处理验证码，不修改账号设置，不修改沟通话术，不删除/屏蔽/拉黑人选。

## 阶段

### S0 合同检查

读取 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。确认 `execution_surface=boss_app_computer_use`，默认 `contact_mode=dry_run`。

### S1 App 预检

使用 `computer.operate` 读取当前前台 App 和页面。通过条件：

- 当前为 BOSS App。
- 用户已进入目标职位的推荐列表页。
- 可识别至少一个候选人卡片。

失败时写 `state/continuation-plan.json` 并请求用户手动回到推荐列表。

如果当前运行时不提供 Computer Use / `computer.operate`，本阶段必须写入 `state/continuation-plan.json`，状态为 `blocked_missing_computer_use`，并停止执行；不得用 osascript、坐标点击或其它 shell UI 自动化替代 S2-S5/S7。

### S2 列表卡片采集

对当前可见卡片逐个读取展示名、公司、职位、学历、年龄、经验、薪资、城市、活跃状态和屏幕区域。把结构化结果追加到 `raw/list-cards.jsonl`，把截图哈希追加到 `raw/screen-hashes.jsonl`。

### S3 列表初筛

按 `strategy.json` 判断是否进入详情。低概率人选写入 `structured/candidates.jsonl`，状态为 `skip_list_stage`。高概率人选进入 S4。

### S4 详情采集

使用 `computer.operate` 点击卡片进入详情页。读取首屏文本，点击 `展开全部`、`查看更多` 或相近折叠入口，在详情页内部滚动到底。只保存结构化文本和截图哈希。完成后返回列表页。

### S5 详情精筛

基于详情结构化文本输出 `contact`、`hold` 或 `skip`，并写入证据、分数、缺失项和风险。

### S6 沟通 dry-run

对 `recommendation=contact` 的候选人定位 `立即沟通` 按钮，记录 `would_contact=true`、按钮位置和截图哈希，不点击按钮。

### S6a 外部执行器 handoff

当候选人已判定为 `contact`，且 BOSS 当前详情页按钮为 `立即沟通` 时，写入外部执行器 handoff 产物：`structured/approved-contact-queue.jsonl` 和 `state/current-contact-intent.json`。这些文件表达已审核触达意图；真实点击只能由执行器完成，不能由 `computer.operate` 直接点击。

如果本 campaign 没有真实触达授权，只能展示下面的命令并等待用户手动执行：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id> \
  --execute
```

如果用户已给出 campaign 级真实触达授权，workflow 必须直接通过 `shell.run` 调用同一命令，不再逐人二次确认：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id> \
  --execute
```

`--execute` 只能在上述 campaign 级授权成立且 policy/intent 均通过时使用。

调用前必须满足：

- 用户授权范围仍在本职位、本筛选规则、本 campaign 触达上限内。
- `executor-policy.json` 存在，`allow_real_contact=true`，`operator_acknowledgement` 为固定确认语，`max_contacts_per_run=1`，`stop_on_paid_prompt=true`，`stop_on_captcha=true`，`stop_on_login_or_security_page=true`，`stop_on_unknown_ui=true`。
- `state/current-contact-intent.json` 未过期，`approval_status=approved_for_auto_contact`，`expected_button=立即沟通`，`current_page=candidate_detail`。
- 当前 BOSS App 详情页由 Computer Use 定位，不交给执行器翻列表或找人。

执行器使用 macOS Accessibility / 本机 UI 自动化校验当前详情页、按钮状态和 intent。执行器运行期间可维护 `state/executor.lock`、`state/stop-executor.flag`、`raw/executor-contact-attempts.jsonl`、`reports/executor-summary.md` 和 `reports/executor-summary.json`。

执行器返回后，Codex 读取 `state/executor-result.json`，通过 sourcing helper 回写 `structured/contact-decisions.jsonl`、`raw/communication-pages.jsonl`、`structured/candidates.jsonl`。

如果 result 是 `sent`，workflow 消费结果、记录送达和实名，然后用 `computer.operate` 返回列表并继续处理下一位候选人。

如果 result 是 `skipped_continue_chat`，workflow 记录已沟通过，不计入本轮新增触达，然后返回列表继续。

如果 result 是 `stopped` 或 `sent_unverified`，workflow 必须写 `reports/interruption-executor-*.json` 和 `state/continuation-plan.json`，停止自动推进。付费弹窗、验证码、安全验证、登录失效、未知 UI、页面不匹配都属于停止条件，不购买、不绕过。

### S6b live-test 真实沟通

仅在 run-policy 同时开启 `allow_real_contact=true` 和 `allow_live_contact_test=true`，且未超过 `live_contact_test_limit` 时执行。点击前必须用 `human.confirm` 做动作级确认并说明：

- 展示名。
- 详情判定理由。
- live-test 剩余额度。
- 点击 `立即沟通` 会自动发送预设消息。

确认后用 `computer.operate` 点击 `立即沟通`，进入沟通页后读取真实姓名、会话抬头、可见沟通状态和是否观察到预设消息已发送，并追加到 `raw/communication-pages.jsonl`。把 `real_name` 和 `real_name_source=communication_page_after_live_contact_test` 回填到 `structured/candidates.jsonl`，并写入 `structured/contact-decisions.jsonl`。

### S6c 人工已沟通页面回采

用户手动打开已沟通页面后，使用 `computer.operate` 读取真实姓名、会话抬头和可见沟通状态，并追加到 `raw/communication-pages.jsonl`。把 `real_name_source=manual_opened_communication_page` 回填到 `structured/candidates.jsonl`，并写入 `structured/contact-decisions.jsonl`。本阶段不发送新消息。

### S7 列表滚动与结束

当前屏处理完成后滚动列表。连续 `list_end_stall_scrolls` 次滚动无新卡片，或识别到列表底部时停止。

### S8 报告与关闭

运行：

```bash
.venv/bin/python -m scripts.boss_app_sourcing summarize --campaign-root data/campaigns/<campaign_id>
```

报告必须包含列表扫描数、详情数、`would_contact` 数、live-test 数、真实姓名补全状态、跳过原因和恢复入口。

## 恢复入口

恢复时只信本地文件：

- `state/processed-cards.jsonl`
- `structured/candidates.jsonl`
- `structured/contact-decisions.jsonl`
- `state/continuation-plan.json`

如果当前 App 不在原推荐列表页，请用户手动回到列表页后继续。

## 验收

- dry-run 不点击 `立即沟通`。
- campaign 级真实触达授权存在时，workflow 可调用外部执行器 `contact-current --execute`，不逐人 `human.confirm`。
- 执行器只处理当前详情页的一次 `立即沟通` 点击，不负责列表遍历、详情采集、候选筛选或翻页。
- live-test 每次真实点击都有动作级确认记录。
- 详情只保存结构化文本和截图哈希。
- `display_name` 与 `real_name` 同时保留。
- 中断后可从 continuation plan 恢复。
