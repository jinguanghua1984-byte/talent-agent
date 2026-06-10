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
- 对合适人选记录 `would_contact`，并默认通过外部执行器调用当前详情页精确文案 `立即沟通` 做真实触达。
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

筛选多模态、视频、AIGC、图形/音视频等边界词密集岗位时，必须区分硬排除、正向信号和边界风险。目标公司候选若标签、求职目标、列表摘要或详情明确包含 JD 关键正向信号，应先进入详情/触达判断，不得用边界词直接列表跳过。

通用优先级：

- 硬排除：当前公司不在用户确认目标范围，或命中用户明确排除的搜索、广告、推荐、NLP、纯语音等主线时，继续作为硬门。
- 正向信号：与 JD 主任务直接相关的方向词优先于边界风险词；多模态视频类 JD 中，“视频算法”“视频生成/编辑/理解”“视频数据链路”“视频目标”“语音/视频/图形”“AIGC”“多模态”“VLM”“Diffusion”“世界模型”“VLA”等都属于正向信号。
- 边界风险：视觉、图像处理、图形、XR、3D、CV、音视频工程、编解码、SDK、流媒体等不得作为单独 skip 理由；当正向信号存在时，只能写入候选风险、降低优先级或置为 `hold`。
- 信息稀疏：目标公司候选若职位/标签显示算法、深度学习、大模型、AIGC、多模态或研究员，但列表证据不足，优先进入详情核实，不在列表层直接跳过。

筛选多模态视频算法类 JD 时，目标公司候选若标签、求职目标或详情明确包含“视频算法”“视频目标”或“语音/视频/图形”，必须先按视频算法相关信号进入详情/触达判断；不得仅因同屏出现视觉、图像处理、图形、XR 等边界词直接跳过，相关边界风险应写入候选风险和交付说明。

## 默认运行策略

- `execution_surface="boss_app_computer_use"`
- `contact_mode="external_executor"`
- `allow_real_contact=true`
- `allow_live_contact_test=false`
- `live_contact_test_limit=0`
- `external_executor_contact_limit=null`
- `external_executor_stop_policy="platform_limit_or_list_end"`
- `require_action_time_confirmation_for_real_contact=true`
- `capture_real_name_after_contact=true`
- 浏览、滚屏、进详情、返回列表、展开详情等 App 页面操作全部使用 Computer Use / `computer.operate`。
- 只有当前详情页已确认触达、`state/current-contact-intent.json` 与 `executor-policy.json` 均满足时，才使用外部执行器点击精确文案 `立即沟通`。
- 不得使用 osascript、坐标点击、截图脚本点击或其它本机自动化替代 Computer Use 做列表浏览、详情采集、滚屏、返回或筛选判断。
- 默认可以点击 `立即沟通`，但只能由外部执行器在当前详情页执行，Computer Use 不直接点击；该默认真实触达模式无需另行明确授权。
- 如果执行任务的命令明确给出沟通次数上限，写入 `external_executor_contact_limit` / `executor-policy.max_contacts_per_day`；未明确沟通次数上限时不设置本地人数上限，直到平台明确提示次数用尽或列表循环到底部。
- 外部执行器每次仍只处理当前详情页的一名候选人，必须由 `state/current-contact-intent.json` 和 `executor-policy.json` 同时授权，且 CLI 带 `--execute`。
- live-test 仍属于旧的动作级确认路径：只有同时开启 `allow_real_contact=true` 和 `allow_live_contact_test=true`，且满足测试上限与动作级确认后，才允许少量 `computer.operate` 真实点击。
- 当前屏或当前批次没有 `contact` 人选时必须继续扫描下一屏；发现合格人选后继续扫描，先记录 `would_contact`、S6a 执行器 handoff 或授权范围内真实触达结果，不得把单个命中作为正常终止条件。
- 正常终止只允许两种情况：列表循环到底部（含连续 `list_end_stall_scrolls` 次滚动无新卡片并确认列表耗尽），或默认真实触达模式下 `立即沟通当日限额达到上限`。未明确沟通次数上限时，不得用本地计数提前停止，只有平台明确提示次数用尽才算触达上限。
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

外部触达执行器产物，用于 campaign 级授权后的真实触达和审计：

- `structured/approved-contact-queue.jsonl`
- `state/current-contact-intent.json`
- `executor-policy.json`
- `state/executor.lock`
- `state/executor-result.json`
- `state/stop-executor.flag`
- `raw/executor-contact-attempts.jsonl`
- `reports/executor-summary.md`
- `reports/executor-summary.json`

Codex/Computer Use 不因这些文件存在而直接点击 `立即沟通`；真实点击只允许通过 `scripts.boss_contact_executor contact-current --execute` 完成。执行器是最小点击器：只校验当前详情页、按钮和 intent，点击精确文案 `立即沟通`，回采沟通页并写审计；列表浏览、详情采集、候选筛选、翻页和报告仍由 Computer Use/workflow 完成。

## 安全边界

- 默认真实触达模式允许点击 `立即沟通`，无需另行明确授权，但只能由外部执行器执行当前详情页的一次精确点击。
- 若执行命令明确要求 dry-run 或 `allow_real_contact=false`，Codex 只能写 queue/intent 并展示命令，不得自行启动带 `--execute` 的执行器。
- 少量 live-test 真实点击必须同时满足 `allow_real_contact=true` 和 `allow_live_contact_test=true`，受 `live_contact_test_limit` 限制，并且每次点击前通过 `human.confirm` 动作级确认。
- BOSS App 点击 `立即沟通` 会自动发送预设消息，必须把这一副作用告知用户后再确认。
- Codex 可按 workflow 调用外部执行器执行当前详情页触达，不再逐人询问。每次调用前必须已写入 `structured/approved-contact-queue.jsonl`、`state/current-contact-intent.json` 和 `executor-policy.json`；执行器 policy 必须 `allow_real_contact=true`、包含固定 acknowledgement、`max_contacts_per_run=1`；未明确沟通次数上限时 `max_contacts_per_day=null`，且命令必须带 `--execute`。
- 执行器不得替代 Computer Use 做列表遍历、详情阅读、筛选判断或翻页；它只做当前详情页 `立即沟通` 点击、沟通页回采和审计。
- 沟通页证据必须写入 `raw/communication-pages.jsonl`，真实姓名回填必须同步更新结构化候选人与沟通决策产物。
- 不处理验证码，不绕过安全页，不修改 BOSS App 设置、职位设置、沟通话术或账号权限。
- 真实姓名来自 live-test 后沟通页，或用户手动打开的已沟通页面；不能用真实姓名覆盖 `display_name`。
- 如果当前运行时没有 Computer Use / `computer.operate` 能力，必须停止并写恢复状态；不得改用 osascript 或坐标点击继续浏览。

## 自动交接

合同文件生成后，读取并执行 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。真实 App 操作由 canonical workflow 通过 `computer.operate` 描述，运行时适配器映射到对应桌面 UI 操作能力。
