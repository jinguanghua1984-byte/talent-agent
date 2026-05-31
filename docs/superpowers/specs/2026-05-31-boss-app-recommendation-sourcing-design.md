# BOSS App 推荐列表寻访工作流设计

> 日期：2026-05-31
> 状态：已按用户反馈更新，待实施计划
> 执行载体：Computer Use 操作本机 BOSS App

## 1. 背景与目标

本工作流面向 BOSS 直聘 App 的推荐人选列表。用户先在本机打开 BOSS App，并进入目标职位下的牛人推荐列表页；agent 不执行网页搜索，不调用 BOSS 网页端 API，不复用 `platform-match` 的 CDP/浏览器执行链路。

目标是把一次 App 推荐列表寻访做成可恢复、可审计的任务：

1. 按用户提供的寻访提示词生成结构化合同。
2. 从当前推荐列表开始逐个读取候选人卡片。
3. 根据列表信息做初筛，只有高概率合适的人选才进入详情页。
4. 在详情页滚动、展开折叠内容，采集完整可见信息。
5. 根据详情信息做最终判定。
6. 对合适人选记录 `would_contact`，默认不真实点击 `立即沟通`。
7. 第一版支持少量 live-test：在用户明确开启、未超过测试上限且动作前再次确认后，可点击 `立即沟通` 验证真实流程。
8. 真实沟通或人工打开已沟通页面后，在沟通页采集真实姓名，并回填候选人数据。
9. 列表滚动到底部或遇到平台/安全阻断时停止并通知用户。

## 2. 非目标

第一版不做以下事情：

1. 不操作 BOSS 网页端，不使用 CDP、Playwright、浏览器扩展或 `page.evaluate(fetch)`。
2. 不从代码主动请求 BOSS API。
3. 不自动执行真实 `立即沟通`，因为 BOSS App 进入沟通页会自动发送预设消息。第一版只允许少量 live-test，并且必须动作前确认。
4. 不承诺绕过验证码、登录、安全页、系统权限弹窗或平台限制。
5. 不自动写入主人才库 `data/talent.db`。任务结果先保存在独立任务目录，后续导入另走 dry-run/apply。

## 3. 推荐方案

采用“canonical workflow + Computer Use 执行 + 本地结构化脚本”的方案。

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| 扩展 `platform-match` | 复用现有 Boss adapter 和搜索命令 | 不推荐。当前需求是 App 推荐列表逐卡片处理，不是网页搜索 |
| 新建浏览器插件 | 可捕获网页请求和导出数据 | 不适用。用户目标是本机 BOSS App |
| 新建 BOSS App workflow | workflow 约束 Computer Use 操作，脚本负责合同、状态、结构化、报告 | 推荐 |

执行职责分层：

| 层 | 职责 |
| --- | --- |
| `agents/skills/boss-app-recommendation-sourcing/SKILL.md` | 业务入口，抽取寻访目标、生成任务合同、交接 workflow |
| `agents/workflows/boss-app-recommendation-sourcing/AGENT.md` | canonical workflow，定义 Computer Use 操作、停机条件、恢复规则 |
| `scripts/boss_app_*` | 合同初始化、状态校验、结构化数据验证、报告生成、导入前 dry-run |
| Computer Use | 读取 App UI、点击卡片、滚动详情、展开内容、返回列表、定位沟通按钮 |

## 4. 任务目录与合同

每次任务创建独立目录：

```text
data/campaigns/<campaign_id>/
  requirements.json
  strategy.json
  run-policy.json
  campaign-manifest.json
  raw/
    list-cards.jsonl
    detail-pages.jsonl
    communication-pages.jsonl
    screen-hashes.jsonl
  state/
    events.jsonl
    processed-cards.jsonl
    continuation-plan.json
  structured/
    candidates.jsonl
    contact-decisions.jsonl
  reports/
    sourcing-summary.md
    sourcing-summary.json
    interruption-*.json
```

`requirements.json` 保存用户提示词、进一步筛选条件、must-have、nice-to-have、排除项、地点、资历、行业和特殊限制。由于 BOSS 推荐列表本身已经基于 JD 生成，用户多数情况下只补充公司、职位、学历、年龄、技术栈等进一步判断依据，而不是重新提供完整 JD。

`strategy.json` 保存列表初筛规则、详情精筛规则、评分阈值、进入详情阈值、`would_contact` 阈值和证据字段。

`run-policy.json` 至少包含：

```json
{
  "execution_surface": "boss_app_computer_use",
  "contact_mode": "dry_run",
  "allow_real_contact": false,
  "allow_live_contact_test": false,
  "live_contact_test_limit": 0,
  "require_action_time_confirmation_for_real_contact": true,
  "capture_real_name_after_contact": true,
  "stop_on_login_or_security_page": true,
  "stop_on_captcha": true,
  "stop_on_ui_template_drift": true,
  "list_end_stall_scrolls": 3
}
```

## 5. 候选人数据模型

BOSS App 的列表页和详情页通常只展示加密名，例如 `张先生`。点击 `立即沟通` 后进入沟通页，可能显示更完整真实姓名，例如 `张 XX`。因此候选人结构必须把展示名和真实名分开。

```json
{
  "candidate_key": "boss-app-run-local-key",
  "platform": "boss_app",
  "display_name": "张先生",
  "real_name": null,
  "real_name_status": "not_available_dry_run",
  "real_name_source": null,
  "name_confidence": "masked",
  "current_company": "",
  "current_title": "",
  "city": "",
  "work_years": null,
  "education": "",
  "expected_salary": "",
  "active_state": "",
  "list_snapshot": {},
  "detail_sections": {},
  "screen_evidence": [
    {
      "page": "detail",
      "screenshot_hash": "sha256:...",
      "screen_region": null,
      "captured_at": "2026-05-31T00:00:00+08:00"
    }
  ],
  "screening": {
    "list_decision": "",
    "detail_decision": "",
    "score": 0,
    "reasons": [],
    "risks": []
  },
  "contact": {
    "would_contact": false,
    "contact_mode": "dry_run",
    "contacted": false,
    "live_contact_test": false,
    "contact_button_seen": false,
    "communication_page_seen": false,
    "preset_message_auto_sent": false
  }
}
```

真实姓名补全规则：

1. 默认 `dry_run` 不点击 `立即沟通`，所以 `real_name_status=not_available_dry_run`。
2. 第一版可执行少量 live-test。必须同时满足 `allow_live_contact_test=true`、未超过 `live_contact_test_limit`、候选人已通过详情精筛，并且点击前获得动作级确认。
3. live-test 点击 `立即沟通` 后，BOSS App 可能自动发送预设消息。进入沟通页后读取真实姓名，写入 `real_name`，并把 `real_name_source` 设为 `communication_page_after_live_contact_test`。
4. 如果用户已经手动沟通过，并手动打开对应沟通页让 agent 读取，则可写入 `real_name_source=manual_opened_communication_page`，不产生新的发送动作。
5. 不能用真实姓名覆盖展示名；两者同时保留，方便追溯页面来源。

## 6. 工作流阶段

### S0 需求合同

从用户输入中抽取进一步筛选策略，落盘为 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。BOSS 推荐列表已由具体 JD 驱动，本 workflow 不重新设计搜索策略；只对公司、职位、学历、年龄、技术栈、排除项等筛选依据中的缺失或冲突字段提问。

### S1 App 预检

要求用户已打开 BOSS App 并进入目标职位的推荐列表页。Computer Use 只读取当前屏幕状态，不切换账号、不处理验证码、不绕过权限弹窗。

通过条件：

- 当前前台是 BOSS App。
- 页面是候选人推荐列表或可由用户确认的候选人列表。
- 能识别至少一个候选人卡片区域。
- `contact_mode=dry_run` 且 `allow_real_contact=false`。

### S2 列表卡片采集

对当前可见卡片逐个采集：

- 展示名。
- 当前或最近职位、公司、经验、学历、城市、薪资、活跃状态等可见字段。
- 卡片序号、屏幕区域、截图哈希和采集时间。

卡片去重使用本地运行键，不依赖 BOSS 平台 ID：

- 展示名。
- 公司/职位/城市/学历/薪资等可见字段。
- 卡片截图哈希。
- 列表滚动批次和位置。

### S3 列表初筛

根据 `strategy.json` 评分。低概率人选记录为 `skip_list_stage`，不进入详情。高概率人选点击卡片进入详情页。

### S4 详情采集

进入详情页后执行：

1. 读取首屏详情。
2. 查找并点击 `展开全部`、`查看更多`、相似文案或可折叠区域。
3. 在详情页内部滚动，直到连续滚动未出现新内容或到达底部。
4. 保存每屏结构化文本、截图哈希、详情段落结构和滚动事件。
5. 返回列表页，并确认回到原列表上下文。

详情采集必须覆盖可见的基本信息、求职意向、工作经历、教育经历、项目经历、技能标签、自我描述、作品/附件入口和其他评价信息。若某段不可见，则记录 `missing_reason`，不要伪造。

### S5 详情精筛

基于详情信息重新评分，输出：

- `recommendation`: `contact` / `hold` / `skip`
- `score`
- `positive_evidence`
- `negative_evidence`
- `missing_evidence`
- `decision_reason`

### S6 沟通 dry-run

当 `recommendation=contact` 时，第一版只做 dry-run：

1. 定位 `立即沟通` 按钮。
2. 记录按钮存在、位置和截图哈希。
3. 写入 `would_contact=true`。
4. 不点击按钮，不进入沟通页，不发送消息。
5. `real_name` 保持空，`real_name_status=not_available_dry_run`。

### S6b 少量 live-test 沟通

第一版包含 live-test 能力，但默认关闭。开启后仍必须遵守动作级确认。

进入 live-test 前必须满足：

1. `allow_live_contact_test=true`。
2. `live_contact_test_limit` 大于 0，且本轮已真实沟通数量未超过上限。
3. 候选人 `recommendation=contact`。
4. 已记录 `display_name`、详情精筛证据和 `would_contact=true`。
5. 点击前向用户说明：BOSS App 点击 `立即沟通` 会自动发送预设消息，确认对象、展示名和判定理由。
6. 用户在动作前明确确认。

点击后采集：

- 沟通页真实姓名。
- 页面标题或会话抬头。
- 是否观测到预设消息已自动发送。
- 返回详情页或列表页的路径。

真实沟通结果写入 `structured/contact-decisions.jsonl`，并回填 `structured/candidates.jsonl` 中的 `real_name`、`real_name_status`、`real_name_source` 和 `contact.contacted`。

### S7 列表滚动与结束

返回列表后继续处理未处理可见卡片。当前屏卡片处理完后向下滚动加载下一批。

停止条件：

- 明确看到列表底部或无更多推荐。
- 连续 `list_end_stall_scrolls` 次滚动没有新卡片。
- 登录失效、验证码、安全页、权限弹窗、系统遮挡。
- UI 模板漂移导致无法稳定识别卡片、详情页或返回路径。
- 任何疑似会真实发送沟通消息的动作即将发生，但未获得动作级确认。

### S8 报告与关闭

生成本地报告：

- 列表扫描数量。
- 进入详情数量。
- `would_contact` 数量。
- live-test 真实沟通数量和剩余测试额度。
- 跳过原因分布。
- 真实姓名补全状态分布。
- 中断点和恢复入口。
- 需要用户人工复核的人选清单。

## 7. 安全边界

Computer Use 直接操作本机 App，必须按真实 UI 风险处理。

默认允许：

- 读取屏幕。
- 滚动列表和详情。
- 点击候选人卡片进入详情。
- 点击展开折叠内容。
- 点击返回。
- 定位但不点击 `立即沟通`。

默认或未获得动作级确认时禁止：

- 点击会发送消息、投递、关注、收藏、拨号、加微信、申请联系方式或修改账号状态的按钮。
- 处理验证码或绕过安全页。
- 修改 BOSS App 设置、职位设置、沟通话术或账号权限。
- 删除、屏蔽或拉黑人选。

动作级确认：

- 点击 `立即沟通` 必须单独确认，因为会自动发送预设消息。
- 输入或发送任何消息必须单独确认。
- 任何上传文件、分享联系方式、拨号、加微信等动作必须单独确认。

## 8. 恢复策略

恢复事实来源是本地任务目录，而不是内存状态。

恢复时读取：

- `state/processed-cards.jsonl`：已处理卡片本地键。
- `structured/candidates.jsonl`：已结构化候选人。
- `state/continuation-plan.json`：最后屏幕、最后动作、停止原因和下一步建议。
- `raw/screen-hashes.jsonl`：关键页面哈希证据。

恢复规则：

1. 已完成详情采集的人选不重复进入详情，除非用户显式要求重采。
2. 已记录 `would_contact` 的人选不重复尝试沟通 dry-run。
3. 如果 App 当前不在原列表页，提示用户手动回到目标推荐列表后继续。
4. 如果无法确认列表上下文，停止并生成人工恢复说明。

## 9. 测试与验收

自动化测试集中在非 UI 业务逻辑：

- 合同初始化字段完整性。
- `display_name` / `real_name` 生命周期。
- `contact_mode=dry_run` 下禁止真实联系动作。
- 卡片去重键稳定性。
- 详情段落结构化和缺失原因记录。
- `would_contact` 决策输出。
- continuation plan 可恢复。

人工验收使用 BOSS App 小样本：

1. 用户打开 BOSS App 推荐列表。
2. dry-run 处理 3-5 张可见卡片。
3. 至少 1 人进入详情页，滚动并展开全部内容。
4. dry-run 对合适人选只记录 `would_contact`，不真实点击 `立即沟通`。
5. 报告中能看到展示名、详情信息、判断理由、按钮定位证据和 `real_name_status=not_available_dry_run`。
6. live-test 在用户动作级确认后少量点击 `立即沟通`，进入沟通页后读取真实姓名并回填 `real_name`。
7. 用户手动打开一个已沟通过的沟通页后，agent 能读取真实姓名并回填 `real_name`，但不发送新消息。

完成代码改造后的仓库验证命令：

```bash
.venv/bin/python -m pytest tests -q
```

## 10. 已确认问题

用户已确认：

1. 首版候选人详情采集只保存结构化文本和截图哈希。
2. BOSS 推荐列表本身基于 JD，用户大多数情况下只提供进一步筛选依据，例如公司、职位、学历、年龄、技术栈。
3. 人工已沟通页面回采真实姓名纳入第一版。
4. 第一版允许少量真实执行 `立即沟通` 做 live-test，但每次点击前必须动作级确认。
