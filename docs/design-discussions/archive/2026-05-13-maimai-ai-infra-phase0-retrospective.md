# 脉脉 AI Infra Phase 0 调研复盘

日期：2026-05-13

## 最终判定

Phase 0 的目标不是证明“所有自动化都能跑”，而是找出在平台安全机制下真正可落地的边界。最终结论如下：

- 搜索小样本门禁通过：真实请求模板 + 已登录专用 Edge profile 可完成 3 个小批次 dry-run，未触发登录页、验证码、403、429 或非 JSON。
- 详情无人自动化入口不通过：`automation.html`/CDP 调用真实详情会改变 sender、active tab 和页面可见性，并已触发平台安全机制。
- 详情 human-in-the-loop 入口通过：`CLI 本地任务包服务 + 用户在人才银行页 popup 加载/启动 + safe 详情 + 导出 + 本地 dry-run` 的 3 目标小样本闭环已打通。
- 写库仍未自动放开：所有导入和详情补全必须先 dry-run；dry-run clean 且用户显式确认前不写库、不 apply。

当前可承诺的产品形态是“半自动招聘采集与评估流水线”，不是完全无人值守采集。

## 已验证证据

| 项目 | 结论 | 关键证据 |
| --- | --- | --- |
| 搜索字段 | 只允许自动 patch `query/search_query` 和分页 | `data/output/raw/maimai-ai-infra-field-calibration-ui-diff-2026-05-13.json` |
| 搜索执行 | 3 个小批次、每批 1 页通过 | `data/output/raw/maimai-ai-infra-search-gate-run-2026-05-13.json` |
| automation bridge smoke | 扩展消息与无人导出可用，但不能代表真实详情可用 | `data/output/raw/maimai-ai-infra-automation-bridge-smoke-real-cdp-2026-05-13.json` |
| 详情 token 导出 bug | 已修复并验证导出不再空过滤 jobs | `tests/test_maimai_scraper_extension.py` 相关契约 |
| automation 详情复跑 | 3 个 jobs 全失败并触发登录页 | `data/output/raw/maimai-ai-infra-detail-gate-authorized-run-2026-05-13.json` |
| 手动 popup 详情 | 30/30 成功 | `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (1).json` |
| automation probe 对照 | `automation.html` 会让人才银行页 hidden | `data/output/maimai-ai-infra-manual-vs-automation-probe-diff-2026-05-13.md` |
| popup 本地任务包详情 | 3/3 成功 | `C:\Users\Administrator\Downloads\maimai-capture-2026-05-13 (2).json` |

## 关键经验

1. **不要把 `Receiving end does not exist` 当根因。** 它发生在平台安全机制触发、人才银行页关闭或登出之后，只是下游症状。
2. **sender 和页面可见性是关键差异。** 手动成功路径的 sender 是 `popup.html`，人才银行页保持 active/visible；automation probe 的 sender 是 `automation.html`，人才银行页变为 inactive/hidden。
3. **窗口焦点不是充分条件。** 手动成功样本里 `windowFocused=false`、`document.hasFocus=false`，仍然 30/30 成功。
4. **`automation.html` 不能作为真实详情入口。** 它会抢占 active tab，并把业务页变成 hidden；这与成功路径相冲突。
5. **CDP 只能用于受控取证和离线编排。** 不应通过 CDP/Runtime.evaluate 去触发真实详情动作。
6. **扩展重载后业务页必须由用户刷新。** 否则 content script 接收端可能不存在，测试会被污染。
7. **原始 capture 必须归档。** 只保留写库结果无法复盘请求体、详情 payload、trace 和失败根因。
8. **dry-run 是入库门槛。** 搜索导入和详情补全都必须先 dry-run，clean 前不 apply。

## 技术边界

### 可以继续使用

- `configs/maimai-ai-infra-search-strategy.json`
- `scripts/maimai_ai_infra_search_plan.py`
- `scripts/maimai_ai_infra_search_runner.py` 的 dry-run-template-only 能力
- `scripts/maimai_ai_infra_rank.py`
- `scripts/maimai_ai_infra_pipeline.py` 的离线编排能力
- `scripts/maimai_detail_plan_server.py`
- `scripts/maimai_detail_import.py`
- `extensions/maimai-scraper` 的 popup 批量详情入口
- `scripts/maimai_trace_diff.py`

### 必须限制使用

- `automation.html`：只允许 probe/诊断，不允许真实详情。
- CDP：只允许只读健康检查、搜索小样本门禁、离线报告取证；不允许触发真实详情。
- 搜索字段 patch：只允许 `query/search_query` 和分页；`allcompanies/degrees/query_relation/positions/worktimes/age` 暂不主动改写。

### 禁止作为落地主路径

- CDP 直接调用扩展后台启动详情。
- CDP 打开 `automation.html` 后启动真实详情。
- 自动刷新、自动导航或自动激活人才银行页来“修复”状态。
- 遇到登录页/验证码后自动重试或自动恢复。

## 新落地架构

```text
策略配置
  -> 搜索计划生成
  -> 搜索小批次受控执行或人工导出
  -> 搜索结果导入 dry-run
  -> 用户确认后 apply
  -> 本地规则评分与 shortlist
  -> 详情目标任务包
  -> 本地 detail plan server
  -> 用户在人才银行页 popup 加载并启动 safe 详情
  -> 用户导出 capture
  -> 详情 dry-run
  -> 用户确认后 apply
  -> 最终审查报告
```

## 放大策略

详情补全不得从 3 条直接扩大到上百条。推荐门槛：

| 阶段 | 目标数 | 通过条件 |
| --- | --- | --- |
| Gate D1 | 3 | `failed_jobs=0`，trace 保持 `popup.html` 和 `visible` |
| Gate D2 | 10 | `failed_jobs=0` 或失败均为可解释数据问题，无登录/验证码 |
| Gate D3 | 30 | safe 模式完整跑完，导出后 dry-run clean |
| Gate D4 | 30+ | 每批 30，批间暂停生效；人工确认后再继续下一批 |

搜索同样小步扩大：

| 阶段 | 批次数 | 页数 | 通过条件 |
| --- | --- | --- | --- |
| Gate S1 | 3 | 1 | 已通过 |
| Gate S2 | 5 | 1 | 无登录/验证码/429，联系人可 dry-run |
| Gate S3 | 5 | 3 | 新增联系人和 A/B 候选有效 |
| Gate S4 | 10 | 3 | 每批归档 raw，失败批次可解释 |

## 需要保留的文件

- `data/output/maimai-ai-infra-feasibility-2026-05-12.md`
- `data/output/raw/maimai-ai-infra-search-gate-run-2026-05-13.json`
- `data/output/raw/maimai-ai-infra-automation-probe-trace-2026-05-13.json`
- `data/output/maimai-ai-infra-manual-vs-automation-probe-diff-2026-05-13.md`
- `data/output/raw/maimai-ai-infra-popup-local-plan-trace-2026-05-13.json`
- `data/output/maimai-ai-infra-manual-vs-popup-local-plan-diff-2026-05-13.md`
- `data/output/maimai-ai-infra-popup-local-plan-dry-run-2026-05-13.md`

## 对旧计划的影响

`docs/superpowers/plans/2026-05-12-maimai-ai-infra-automated-search.md` 中以下内容需要修订：

- “人工只参与策略确认和最终结果审查”不可作为近期目标。
- “扩展自动化桥执行详情补全”不可作为默认路径。
- `automation.html` 只能保留诊断能力，不进入生产详情链路。
- 详情补全 Task 6 应改为 popup 本地任务包方案。
- 推荐落地顺序应加入搜索/详情分级门禁，不允许直接扩大。
