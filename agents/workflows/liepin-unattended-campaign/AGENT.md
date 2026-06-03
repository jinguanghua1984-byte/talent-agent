---
name: liepin-unattended-campaign
description: 猎聘招聘端人才搜索 P0 的 canonical workflow，约束页面内 fetch、raw 落盘、标准化、停机恢复和主库边界。
---

# liepin-unattended-campaign

## 触发入口

- 从 `agents/skills/liepin-talent-search-campaign/SKILL.md` 生成需求合同后交接执行。
- 用户要求继续执行已有猎聘 campaign、恢复中断、标准化 raw、生成摘要或准备单页 smoke test。
- 只接受落盘合同作为执行事实来源：`requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。

## 安全边界

- 不读取 Chrome cookie、localStorage、profile、密码或 session store。
- 不构建脱离浏览器登录上下文的纯 HTTP 客户端。
- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 不自动导航、刷新或点击已进入执行态的猎聘业务页面。
- 不抓简历详情，不还原脱敏姓名，不写主人才库。
- `allow_detail_fetch=false`、`allow_campaign_db_write=false`、`allow_main_db_write=false` 是 P0 固定边界。

## 停机条件

遇到以下任一情况必须停止当前阶段，不得继续翻页、重试或推进下游：

- 登录页或登录失效。
- 验证码、安全验证或访问异常。
- HTTP 403、429、432。
- 非 JSON、HTML 响应。
- JSON `flag` 不等于 `1`。
- 响应缺少 P0 必需字段，例如 `data.cardResList`。
- 无法确认当前页面是可用的猎聘招聘端页面。

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl` 或 `state/request-ledger.jsonl`，并更新 `state/continuation-plan.json`。

## 阶段

### S0 需求合同

读取 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`，确认 `jobId`、搜索覆盖项、页数上限、浏览器执行面和主库人工边界。

### S1 页面预检

确认用户已在浏览器中打开并登录猎聘招聘端页面。预检只读取页面 URL、标题和可见文本。页面不满足条件时停止，并要求用户手动打开可用页面。

### S2 条件生成

当有 `jobId` 时，通过页面内受控 fetch 调用：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.get-search-condition-by-job
```

成功响应保存到 `raw/condition/job-<job_id>.json`。失败按停机条件处理。

### S3 搜索计划展开

把 `strategy.json.page_plan` 展开为 `curPage` 计划。P0 默认 1 页，人工确认后最多 5 页。计划写入 `state/continuation-plan.json`。

### S4 搜索执行

逐页通过页面内受控 fetch 调用：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes
```

每页成功后立即写 `raw/search/page-<curPage>.json`，并追加 `state/request-ledger.jsonl`。真实执行阶段不自动刷新、导航或点击业务页面。

### S5 恢复

恢复时只信磁盘事实：扫描 `raw/search/page-*.json`、`state/request-ledger.jsonl` 和 `state/continuation-plan.json`。已成功页不得重复请求；从下一页继续。

### S6 标准化

运行 `scripts.liepin_search_standardize`，从 `cardResList` 输出 `structured/candidate-summaries.jsonl`、`reports/search-summary.json` 和 `reports/search-summary.md`。字段结构漂移时记录 `template_drift`，不生成不完整结论。

### S7 关闭

P0 到摘要即止。后续详情抓取、Campaign DB 写入或主库同步必须另起设计和实施计划，并经过 dry-run、备份、apply 和完整性验证。

## 验收

- 任一阶段失败都必须留下可恢复的事实来源和明确状态。
- raw 搜索页必须以 `curPage` 零基页码保存。
- 标准化输出必须保留 `resIdEncode`、`usercIdEncode`、`detailUrl` 和 `ckId/skId/fkId`。
- 主人才库不在本 workflow 内写入。
