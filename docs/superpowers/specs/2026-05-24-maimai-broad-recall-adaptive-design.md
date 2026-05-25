# 脉脉宽召回自适应寻访实验模式设计

## 背景

现有脉脉寻访流程已经具备从 JD 生成 campaign、执行列表搜索、导入 Campaign DB、列表粗筛、详情抓取、详情 apply、详评精排、交付报告和飞书交付包的完整能力。但实践中暴露出一个策略层问题：如果把完整 JD 精准画像直接用于脉脉搜索策略，搜索条件会过窄，导致搜索结果数量偏少，既浪费搜索限额，也可能错过可通过详情或后续人才库精排识别出来的潜在人选。

人工脉脉搜索通常不是固定抓每组条件的相同页数，而是先用公司、职位、宽关键词和硬性指标发起较宽搜索，然后逐页观察候选人质量。前几页质量高的组合会继续翻；连续几页明显偏离的组合会停止并切换搜索条件。现有实现的固定页数分配没有利用这个反馈信号。

本设计新增一个实验模式，用于验证“宽召回 + 自适应翻页 + 详情扩库 + 摘要报告”的寻访路径。它不替换现有流程，也不削弱已有原子能力。

## 目标

- 在不明显牺牲候选人相关性的前提下，最大化脉脉扩库收益。
- 用宽召回搜索条件覆盖更大的潜在人选池，避免把 JD must-have 全部压进搜索 query。
- 用规则页质评分模拟人工逐页观察，动态决定继续、观察或停止搜索组合。
- 取消 campaign 总页数预算，把 500 页理解为单账号单日平台护栏，而不是业务总预算。
- 将列表粗筛的语义从“最终推荐分档”调整为“详情抓取优先级”。
- 详情抓取后只写 Campaign DB 并生成寻访摘要报告，不在本流程内做人选推荐、外联表或飞书候选人交付包。
- 保持主库 `data/talent.db` 写入为人工边界，后续 JD 精准匹配交给已有 `jd-talent-delivery` workflow。

## 非目标

- 不绕过登录、验证码、安全页、429、403、432、平台日限或其他风控。
- 不自动切换账号。换账号由负责人在页面上手动完成，workflow 只负责识别阻断、停机和恢复。
- 不删除或降级现有详评精排、交付报告、外联队列和飞书交付包能力。
- 不把实验模式设为默认流程。真实任务验证通过前，现有 `maimai-unattended-campaign` 默认行为保持不变。
- 不在无人值守流程内自动写 `data/talent.db`。

## 方案选择

本次采用方案 B：新增实验 mode，共用底层原子能力。

对比：

- 方案 A：在现有 workflow 中加策略开关。改动最少，但容易把实验逻辑和旧的推荐交付路径混在一起，回滚和 A/B 对比不干净。
- 方案 B：新增 `strategy_mode=broad_recall_adaptive_v1`，复用现有搜索、导入、详情和通知原子能力，只替换策略编排和产出范围。隔离性和复用性平衡最好。
- 方案 C：新建完整独立 workflow 和脚本链。隔离最彻底，但会复制大量已有能力，后续维护成本高。

## 架构边界

新增实验模式：`strategy_mode=broad_recall_adaptive_v1`。

该模式属于同一套 campaign 体系，但走新的策略编排：

- 复用现有原子能力：搜索 live gate、raw 标准化、Campaign DB dry-run/apply、详情 pack、详情抓取、详情 apply、通知、恢复。
- 新增策略编排层：宽召回搜索计划、自适应翻页、页级质量评估、unit 状态机、寻访摘要报告。
- 保留旧精准交付链路：旧流程仍可继续生成详评、推荐报告、外联表和飞书交付包。
- 新模式不做人选推荐和外联，只服务“扩库、补详情、可恢复、摘要报告”。
- 主库 `data/talent.db` 仍是人工边界，新模式只写 Campaign DB。

设计原则：新 mode 改编排，不削弱已有原子能力；真实任务验证通过前不切默认。

## 搜索策略

新模式把 JD 抽取结果拆成两类配置：

- 扩库搜索条件：用于脉脉搜索，偏宽召回。
- 粗筛评分条件：用于列表结果判断是否值得抓详情，偏质量控制。

搜索条件接近人工做法：

- 公司维度：目标公司按组合拆分，大公司通常单公司一个 unit，小公司可合并成小组。
- 职位维度：使用多职位或多关键字，不把职位名收窄到单一精确 title。
- 关键词维度：先使用宽关键词；如果前几页偏离明显，再进入长尾关键词组合。
- 硬指标：学历、院校、年龄、工作年限作为过滤或强评分信号。
- 薪资：作为可选匹配度提升信号，不作为首版必填条件。
- 城市：默认不作为搜索项，除非 JD 明确强地域限制。
- 不把完整 JD must-have 全部塞进搜索 query。

## 自适应翻页

每个 search unit 的执行逻辑：

1. 先探测 2 页。
2. 每页标准化后立即做页级质量评分。
3. 高质量页继续翻。
4. 中等质量页最多进入 1 页观察。
5. 低质量页累计。
6. 连续 2 页低质量，停止该 unit。
7. 单 unit 默认最多 15 页，防止单组合无限消耗执行窗口。
8. 没有 campaign 总预算；平台或账号日限触发停机恢复。

低质量停止不是失败，状态记录为 `stopped_low_quality`。高质量 unit 可继续执行到 `unit_max_pages` 或直到质量衰减。

### 在线反馈回路补充

`broad_recall_adaptive_v1` 的真实执行不能只在搜索完成后生成页质报告。live gate 必须在每个成功页面返回后立即调用页质评分，并把评分结果写入本轮 run 产物和持久状态。

执行规则：

1. 每个 unit 从 `start_page` 开始执行，默认初始计划仍从 page 1 开始。
2. 前 `probe_pages` 页必须执行，除非遇到登录、验证码、429、403、432、非 JSON 或安全页等平台阻断。
3. `search-units.jsonl` 中的 `max_pages` 只表示初始 probe 页数；live gate 在 adaptive 模式下必须用 `unit_max_pages` 作为运行时上限，不能要求 page 3-N 预先出现在 wave plan 里。
4. 每页成功返回后，基于该页候选人、跨 run `seen-candidates` 和当前策略调用 `score_page_quality`。
5. `good` 或 `observe` 状态继续尝试下一页；`low` 会累计 `consecutive_low_quality_pages`。
6. 当连续低质量页达到 `max_consecutive_low_quality_pages`，当前 unit 状态写为 `stopped_low_quality`，本 unit 剩余页不再请求，live gate 直接切换到下一个 unit。
7. 当 `next_page > unit_max_pages`，当前 unit 写为 `exhausted`，不再继续。
8. 每页评分后立即刷新 `reports/page-quality*.jsonl`、`state/adaptive-unit-state*.json` 和 `state/seen-candidates*.jsonl`，避免平台阻断后丢失已完成页的决策依据。
9. 默认固定计划模式不传 adaptive 参数，行为保持不变。

执行产物：

- live run 的每个 page 追加 `adaptiveQuality`，每个 batch 追加 `adaptiveStopReason`。
- `reports/page-quality.jsonl` 或 wave 专属 page-quality JSONL 保存页级评分。
- `state/adaptive-unit-state.json` 或 wave 专属 state JSON 保存每个 unit 的最新状态。
- `state/seen-candidates.jsonl` 保存跨 unit 去重集合。

验收标准：

- 高质量 unit 在 `probe_pages=2` 且 `unit_max_pages>=3` 时会实际请求 page 3。
- 连续两页低质量 unit 不会请求 page 3，并会切换到下一组条件。
- broad mode orchestrator 生成的 live gate 命令必须带上 strategy、adaptive state、seen candidates 和 page-quality 输出路径。
- 平台阻断仍按既有硬停机规则处理，不因 adaptive 逻辑吞掉中断证据。

首版页质判断使用规则评分，不使用 LLM。默认阈值只是实验初值，真实任务后允许调参：

- `page_good_ratio >= 30%`：继续翻页。
- `page_good_ratio >= 10% and < 30%`：观察。
- `page_good_ratio < 10%`：低质量页。
- 连续 2 个低质量页停止。

页级评分看“可进入详情候选人”的比例，而不是只看总人数。

## 页质规则评分

候选人级正向信号：

- 目标公司、同集团、产品线或公司别名命中。
- 职位名、职位别名或宽职位词命中。
- 宽关键词命中。
- 学历、院校、年龄、工作年限符合硬性指标。
- profile 可抓详情。
- 候选人未在当前 campaign 中重复出现。

候选人级负向信号：

- 职位明显偏离。
- 关键词只有弱相关。
- 硬性条件明显不符。
- 候选人重复。
- 当前页候选人数量过低。

页级汇总信号：

- `good_candidate_count`
- `candidate_count`
- `new_candidate_count`
- `duplicate_ratio`
- `detail_eligible_count`
- `page_good_ratio`
- `quality_band = good / observe / low`
- `decision = continue / observe / stop_unit / blocked`

## 预算与平台护栏

新模式不设置 campaign 总页数上限。寻访项目可以跨天、跨账号、分多次执行，只要状态完整持久化。

保留三类执行护栏：

- `account_day_page_guardrail=500`：单账号单日平台护栏，不是业务预算。触发后停机并写 continuation plan。
- `run_slice_max_pages`：可选字段，限制本次执行窗口最多跑多少页，便于人为控制运行时长。
- `unit_max_pages=15`：单搜索组合上限，避免一个组合吃光执行窗口。

换账号由负责人手动完成。workflow 不需要识别账号身份，也不尝试切换账号。平台日限、429、验证码或安全页只表现为阻断信号：

- 能识别具体证据时，记录具体原因，例如 `http_429`、`captcha_api`、`daily_limit`。
- 证据不够具体时，记录为 `account_day_guardrail_or_platform_limit`。
- 写 `state/continuation-plan.json`，用户手动处理后从该入口继续。

## 状态持久化

取消 campaign 总预算后，持久化是核心能力。新模式必须把执行过程当成一等数据。

建议新增或扩展以下文件：

```text
data/campaigns/<campaign_id>/
  search-units.jsonl
  raw/search/unit-*/page-*.json
  reports/page-quality.jsonl
  reports/broad-recall-summary.json
  reports/broad-recall-summary.md
  state/adaptive-unit-state.json
  state/seen-candidates.jsonl
  state/execution-runs.jsonl
  state/continuation-plan.json
  state/import-ledger.jsonl
```

字段语义：

- `search-units.jsonl`：所有搜索组合，包含公司组、职位词、关键词、硬指标、初始页数和最大页数。
- `state/adaptive-unit-state.json`：每个 unit 的状态，取值包括 `pending / active / observing / stopped_low_quality / exhausted / blocked / completed`。
- `state/seen-candidates.jsonl`：跨 unit、跨 run 的已见候选人集合，用于计算重复率和避免重复浪费。
- `raw/search/unit-*/page-*.json`：每页原始响应，抓到一页立即落盘。
- `reports/page-quality.jsonl`：每页质量评分、好/中/差判断、继续或停止原因。
- `state/execution-runs.jsonl`：每次执行窗口记录，包含开始时间、结束时间、页数和停止原因。
- `state/continuation-plan.json`：唯一恢复入口，记录下一步从哪个 unit、哪一页继续。
- `state/import-ledger.jsonl`：沿用现有导入防重机制，确保 Campaign DB apply 可重复安全执行。

## 恢复逻辑

恢复时只信磁盘事实，不信内存状态：

1. 扫描 `raw/search`、`reports/page-quality.jsonl`、`state/adaptive-unit-state.json` 和 `state/import-ledger.jsonl`。
2. 重建已抓页、已导入页、已见候选人和 unit 状态。
3. 如果上一轮因平台日限、验证码、429 或安全页停止，用户手动处理后从 `continuation-plan.json` 继续。
4. 已因低质量停止的 unit 不自动重跑，除非用户显式要求。
5. 换账号只产生新的 execution run，不重建 campaign。

恢复必须避免：

- 重复抓同一页。
- 重复写 Campaign DB。
- 重新打开已低质量停止的 unit。
- 丢失阻断原因和下一步入口。

## 列表粗筛与详情优先级

新模式中，列表粗筛不是最终推荐，而是详情抓取优先级。

建议语义：

- `detail_p0`：高度值得补详情，优先抓。
- `detail_p1`：可能匹配，抓详情后入库。
- `detail_p2`：弱相关但有扩库价值，视详情容量抓。
- `skip`：明显不相关，不抓详情。

为了复用已有原子能力，内部可以映射到 A/B/C/淘汰，但新模式报告里不得把这些档位表达为“强推荐/推荐/观察”。

详情策略：

- 默认抓 `detail_p0 + detail_p1`。
- 平台稳定且详情执行窗口允许时，可扩大到 `detail_p2`。
- 详情 pack 大小保留每包 100 人。
- 并发首版上限按已验证的 4。
- 发生验证码、429、403、432、安全页或 partial capture 时立即停机并写恢复计划。

详情 apply 后写 Campaign DB，并校验：

- candidate/source/detail 计数。
- pending/conflict。
- `PRAGMA integrity_check`。
- import ledger。
- failed/unmatched/capture blockers。

## 产出范围

新模式不做：

- detailed rank。
- 最终候选人推荐报告。
- 外联 sheet。
- 飞书候选人交付包。
- 主库自动同步。

新模式只生成寻访摘要报告，包含：

- 本次寻访目标和宽召回策略。
- search units 执行情况。
- 每个 unit 的页级质量走势和停止原因。
- raw 页数、候选人数、去重人数、新增/合并数。
- 详情计划、详情完成数、失败/阻断数。
- Campaign DB apply 校验结果。
- 可恢复入口。
- 主库手动同步建议。

## 与现有流程的关系

现有精准推荐链路继续保留：

- `maimai-unattended-campaign` 旧默认行为不变。
- detailed rank、delivery report、outreach package 和 Feishu delivery package 代码保留。
- `jd-talent-delivery` 继续从 `data/talent.db` 做精准匹配、TopN 推荐和飞书交付。

新模式只负责扩库和补详情。进入主库后的精准匹配由已有 workflow 完成。

## 配置草案

`strategy.json` 增加：

```json
{
  "strategy_mode": "broad_recall_adaptive_v1",
  "search_intent": "talent_pool_expansion",
  "adaptive_search": {
    "probe_pages": 2,
    "unit_max_pages": 15,
    "good_ratio_continue": 0.3,
    "good_ratio_observe": 0.1,
    "max_consecutive_low_quality_pages": 2,
    "stop_on_high_duplicate_ratio": true
  },
  "detail_priority_labels": ["detail_p0", "detail_p1", "detail_p2", "skip"]
}
```

`run-policy.json` 增加或调整：

```json
{
  "campaign_page_budget": null,
  "account_day_page_guardrail": 500,
  "run_slice_max_pages": null,
  "detail_concurrency": 4,
  "auto_rank_after_detail_apply": false,
  "auto_publish_feishu_delivery_after_detail_rank": false,
  "allow_feishu_delivery_publish": false,
  "main_db_sync_mode": "manual_only",
  "allow_main_db_write": false
}
```

## 验证策略

实现前后必须保证旧流程不退化：

- 旧 `maimai-unattended-campaign` 文档合同测试仍通过。
- 旧 `maimai_campaign_orchestrator` stage command 计划仍能生成 detailed rank 和 delivery package。
- 新模式测试确认 `strategy_mode=broad_recall_adaptive_v1` 时跳过 detailed rank、outreach package 和 Feishu delivery package。
- 新模式测试确认搜索 unit 支持宽召回字段、自适应页数和 unit 状态。
- 新模式测试确认 page quality 可从标准化 raw 生成，且低质量连续阈值能停止 unit。
- 新模式测试确认 continuation plan 可从平台阻断和日限场景生成。
- 新模式测试确认详情优先级不使用“强推荐/推荐/观察”作为业务输出。
- 新模式测试确认摘要报告包含策略、执行、详情、Campaign DB 校验和恢复入口。

真实任务验收指标：

- 有效候选人去重数。
- 新增 Campaign DB 人数。
- 详情完成数。
- 无效页比例。
- 因低质量提前停止节省的页数。
- 高质量 unit 扩展带来的新增人选。
- 平台阻断次数和恢复可靠性。
- 后续同步主库后，`jd-talent-delivery` 是否能从人才库里找到更好人选。

## 切默认规则

在以下条件满足前，新模式只能作为实验入口：

- 至少完成 1-2 个真实寻访任务。
- 中断恢复成功。
- Campaign DB dry-run/apply 无重复写入问题。
- 详情并发 4 未触发明显平台风险。
- 摘要报告能解释为什么停、为什么继续、产出了多少数据。
- 用户确认新模式业务效果优于旧固定页数模式。

满足以上条件后，再单独讨论是否把 `broad_recall_adaptive_v1` 切为默认策略。
