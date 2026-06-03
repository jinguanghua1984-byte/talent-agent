---
name: liepin-talent-search-campaign
description: Use when the user wants to create or run a Liepin recruiting-side talent search campaign through an already logged-in browser page, including jobId-based resume search, raw capture, standardization, and recoverable CLI orchestration.
---

# liepin-talent-search-campaign

## 目标

把一次猎聘招聘端人才搜索整理成可执行、可恢复、可审计的 P0 campaign 合同。该 Skill 负责业务输入抽取、`jobId` 和搜索条件整理、运行边界确认、合同文件生成，并交接到 `agents/workflows/liepin-unattended-campaign/AGENT.md`。

## 触发语义

用户表达以下意图时使用本 Skill：

- 根据猎聘职位 `jobId` 搜简历。
- 构建猎聘 CLI、猎聘寻访 campaign、猎聘简历搜索任务。
- 使用已登录猎聘页面执行 `search-resumes`。
- 对猎聘搜索 raw 做标准化、摘要和恢复计划。
- 继续或恢复已有猎聘 campaign。

如果用户只是调研接口，先记录接口结论；如果用户明确进入实施或执行 campaign，则读取 canonical workflow。

## 输入抽取

优先从用户输入中抽取：

- `campaign_id`
- `jobId`
- 目标职位或岗位名称
- 搜索城市、学历、年限、关键词、排序和简历类型覆盖项
- 页数上限
- 是否只做 dry-run、是否允许真实浏览器内 fetch

只对缺失或冲突的关键字段提问。P0 最小可执行输入是 `jobId`，或一组明确的通用搜索条件。

## 默认运行策略

- `execution_surface="cdp_in_page_fetch"`
- 默认 `max_pages=1`
- 单次人工确认后最多 `max_pages=5`
- `allow_detail_fetch=false`
- `allow_campaign_db_write=false`
- `allow_main_db_write=false`
- `main_db_sync_mode="manual_only"`
- 不读取 Chrome cookie、localStorage、profile、密码或 session store。
- 不做脱离浏览器登录上下文的纯 HTTP 客户端。
- 不自动导航、刷新或点击猎聘业务页面。

## 输出产物

默认根目录：`data/campaigns/<campaign_id>/`。

必须生成或维护：

- `requirements.json`
- `strategy.json`
- `run-policy.json`
- `campaign-manifest.json`
- `raw/condition/job-<job_id>.json`
- `raw/search/page-000.json`
- `state/events.jsonl`
- `state/request-ledger.jsonl`
- `state/continuation-plan.json`
- `structured/candidate-summaries.jsonl`
- `reports/search-summary.json`
- `reports/search-summary.md`
- `reports/candidate-pool-diagnostic.json`
- `reports/candidate-pool-diagnostic.md`
- `reports/interruption-*.json`

## 安全边界

- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 遇到登录失效、验证码、安全页、403、429、432、非 JSON、HTML 响应、`flag != 1` 或模板漂移，必须立即停止并写恢复计划。
- 停机不等于失败；只要 raw 和 continuation 完整，可以在用户处理平台状态后恢复。
- P0 不抓简历详情，不还原脱敏姓名，不写主人才库。候选池诊断只基于列表摘要生成详情优先级预览，不等同于推荐报告。

## 自动交接

合同文件生成后，读取并执行 `agents/workflows/liepin-unattended-campaign/AGENT.md`。真实浏览器内请求必须由 workflow 按阶段和运行策略控制。
