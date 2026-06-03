---
name: liepin-unattended-campaign
description: 猎聘招聘端人才搜索的 canonical workflow，约束 CDP 页面内 fetch、raw 落盘、标准化、停机恢复和主库边界。
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
- 响应缺少 P0 必需字段，例如 `data.cardResList` 或 `data.resList`。
- 无法确认当前页面是可用的猎聘招聘端页面。

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl` 或 `state/request-ledger.jsonl`，并更新 `state/continuation-plan.json`。

## 阶段

### S0 需求合同

读取 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`，确认 `jobId`、搜索覆盖项、页数上限、浏览器执行面和主库人工边界。

### S1 页面预检

优先使用独立 CDP Chrome profile，而不是 Codex Chrome extension。确认计划后执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator launch-browser --profile data/session/liepin-cdp-profile --remote-debugging-port 9898
```

用户在该专用浏览器中完成登录并进入猎聘找简历页后，预检只读取页面 URL、标题和可见文本。页面不满足条件时停止，并要求用户手动打开可用页面。

### S2 条件生成

当有 `jobId` 时，通过页面内受控 fetch 调用：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.get-search-condition-by-job
```

成功响应保存到 `raw/condition/job-<job_id>.json`。失败按停机条件处理。

### S3 搜索计划展开

把 `strategy.json.page_plan` 展开为 `curPage` 计划。P0 默认 1 页，人工确认后最多 5 页。计划写入 `state/continuation-plan.json`。

### S4 搜索执行

逐页通过 CDP `Runtime.evaluate` 在已登录页面上下文内执行受控 fetch：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes
```

执行命令：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-search --campaign-root data/campaigns/<campaign_id> --cdp-url http://127.0.0.1:9898 --max-pages 1
```

每页成功后立即写 `raw/search/page-<curPage>.json`，并追加 `state/request-ledger.jsonl`。真实执行阶段不自动刷新、导航或点击业务页面。CDP live gate 不读取浏览器敏感存储；登录态只由页面上下文自然携带。

### S5 恢复

恢复时只信磁盘事实：扫描 `raw/search/page-*.json`、`state/request-ledger.jsonl` 和 `state/continuation-plan.json`。已成功页不得重复请求；从下一页继续。

### S6 标准化

运行 `scripts.liepin_search_standardize`，从 `cardResList` 或 `resList` 输出 `structured/candidate-summaries.jsonl`、`reports/search-summary.json` 和 `reports/search-summary.md`。字段结构漂移时记录 `template_drift`，不生成不完整结论。

### S7 候选池诊断

运行 `scripts.liepin_campaign_orchestrator diagnose-pool`，只读取 `structured/candidate-summaries.jsonl`，生成 `reports/candidate-pool-diagnostic.json` 和 `reports/candidate-pool-diagnostic.md`。该阶段只做分布统计和 `detail_p0/detail_p1/detail_p2/skip` 详情优先级预览，不触发新的猎聘请求，不抓详情，不写数据库，不生成最终推荐报告。

### S7a P1 详情 smoke 目标包

候选池诊断完成后，详情 smoke 必须单独确认；不得把候选池诊断自动升级为详情请求。默认只选择 `detail_p0` 前 10 人，单次上限 20。

确认后先生成 target pack：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-smoke --campaign-root data/campaigns/<campaign_id> --priority detail_p0 --limit 10
```

该命令只读取 `structured/candidate-summaries.jsonl` 和候选池诊断优先级，写 `raw/detail-targets/liepin-detail-p0-smoke-001.json`、`reports/detail-smoke-targets.json` 和 `reports/detail-smoke-targets.md`。生成 target pack 不触发猎聘请求。

### S7b P1 详情 smoke live gate

再次确认 CDP 页面可用后，才允许执行详情 smoke：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-smoke --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json --cdp-url http://127.0.0.1:9898 --limit 10 --delay-seconds 3 --timeout-seconds 30 --run-id detail-smoke-001
```

详情 smoke 逐人写 `raw/detail-live/<pack_id>/job-*.json`，并追加 `state/detail-request-ledger.jsonl`。遇到登录页、验证码、安全页、401、403、429、432、非 JSON、业务阻断或 partial capture 时立即停止，写 interruption 和 continuation。

详情 smoke 只写 `reports/detail-smoke-summary.json` 和 `reports/detail-smoke-summary.md` 作为执行摘要，不生成推荐结论，不写 Campaign DB，不写主库，不写 outreach queue。

### S8 关闭

P0 到搜索摘要和候选池诊断即止；P1 详情 smoke 只在单独确认后小批执行。后续 full detail、`detail_p1`、Campaign DB import、主库同步、推荐和交付必须另起设计和实施计划，并经过 dry-run、备份、apply 和完整性验证。

## 验收

- 任一阶段失败都必须留下可恢复的事实来源和明确状态。
- raw 搜索页必须以 `curPage` 零基页码保存。
- 标准化输出必须保留 `resIdEncode`、`usercIdEncode`、`detailUrl` 和 `ckId/skId/fkId`。
- 主人才库不在本 workflow 内写入。
