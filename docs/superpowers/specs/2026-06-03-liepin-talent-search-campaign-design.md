# 猎聘人才搜索 CLI P0 设计

> 日期：2026-06-03
> 状态：待用户审阅后进入实施计划
> 执行载体：已登录 Chrome 猎聘页内 fetch + 本地 CLI 编排

## 1. 背景

本轮接口调查确认 `https://h.liepin.com/search/getConditionItem` 是猎聘招聘端的前端 SPA 路由，不是 JSON API。真实搜索请求走 `https://api-h.liepin.com`。

已观测到的 P0 相关接口：

```text
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.get-search-condition-by-job
POST https://api-h.liepin.com/api/com.liepin.searchfront4r.h.search-resumes
```

`get-search-condition-by-job` 使用 `application/x-www-form-urlencoded`，请求体为 `jobId=<职位 ID>`，用于按职位生成默认搜索条件。`search-resumes` 也使用 `application/x-www-form-urlencoded`，核心字段为：

```text
searchParamsInputVo=<JSON 字符串>
logForm=<JSON 字符串>
```

这个安全模型与脉脉搜索类似：真实请求依赖已登录浏览器上下文和平台风控状态。P0 不做脱离浏览器的纯 HTTP 登录态搬运，而是让 CLI 负责计划、参数、落盘、恢复和标准化，真实请求在用户已登录的猎聘页面内通过受控 fetch 执行。

## 2. 目标

P0 目标是把一次猎聘单职位或单条件搜索做成可恢复、可审计的本地任务：

1. 从 `jobId` 和可选覆盖条件生成搜索参数。
2. 在已登录猎聘页面内调用 `get-search-condition-by-job` 获取职位默认条件。
3. 在同一页面上下文内调用 `search-resumes` 执行简历搜索。
4. 每页原始响应立即落盘到 campaign 目录。
5. 标准化 `cardResList` 中的候选人摘要字段，保留后续详情和恢复所需 ID。
6. 遇到登录、验证码、安全页、限流、非 JSON、接口结构漂移等阻断时立即停机并写恢复计划。
7. 输出本地 Markdown/JSON 摘要，不自动写入主人才库。

## 3. 非目标

P0 明确不做以下事情：

1. 不读取、导出、复制或保存 Chrome cookie、localStorage、浏览器 profile、密码或 session store。
2. 不构建脱离浏览器登录上下文的纯 HTTP 客户端。
3. 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
4. 不自动导航、刷新或点击猎聘业务页面；用户负责保持已登录页面可用。
5. 不抓取简历详情页。P0 只保留 `detailUrl` 和摘要字段，详情抓取作为 P1 单独设计。
6. 不自动写入 `data/talent.db`，不自动同步主库。
7. 不做无人值守大规模翻页。P0 默认用于小页数 smoke、字段校准和最小可恢复闭环。

## 4. 推荐方案

采用“浏览器内 fetch + CLI 编排”的方案。

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| 浏览器内 fetch + CLI 编排 | CLI 控制任务目录、参数、恢复和标准化；真实请求在已登录猎聘页面内执行 | 推荐，安全边界最接近现有脉脉模式 |
| Chrome 扩展被动监听 | 用户手动搜索，扩展记录请求和响应 | 适合接口校准，不适合 campaign 恢复和自动分页 |
| 纯 HTTP CLI | Python 直接请求 `api-h.liepin.com` | 不推荐，容易依赖敏感登录态搬运，也更容易触发风控 |

## 5. 架构边界

P0 设计一套与脉脉平行、但范围更小的猎聘 campaign 能力。

建议文件边界：

```text
agents/skills/liepin-talent-search-campaign/SKILL.md
agents/workflows/liepin-unattended-campaign/AGENT.md

scripts/liepin_api_contract.py
scripts/liepin_browser_runner.py
scripts/liepin_search_plan.py
scripts/liepin_search_live_gate.py
scripts/liepin_search_standardize.py
scripts/liepin_campaign_orchestrator.py
```

P0 实施时可以先落脚本和测试，再补 skill/workflow；最终业务入口仍应与脉脉一致，形成 canonical skill + workflow + scripts 三层边界。

职责分层：

| 层 | 职责 |
| --- | --- |
| `liepin-talent-search-campaign` skill | 从业务输入抽取职位、搜索条件、页数上限和安全边界，生成 campaign 合同 |
| `liepin-unattended-campaign` workflow | 定义浏览器页预检、真实请求、停机、恢复、标准化和人工主库边界 |
| `liepin_*` scripts | 参数生成、请求执行封装、raw 校验、标准化、报告和状态恢复 |
| Chrome 猎聘页面 | 承载已登录上下文，只执行白名单接口 fetch |

## 6. Campaign 目录与合同

每次任务创建独立目录：

```text
data/campaigns/<campaign_id>/
  requirements.json
  strategy.json
  run-policy.json
  campaign-manifest.json
  raw/
    condition/
      job-<job_id>.json
    search/
      page-000.json
      page-001.json
  state/
    events.jsonl
    continuation-plan.json
    request-ledger.jsonl
  structured/
    candidate-summaries.jsonl
  reports/
    search-summary.json
    search-summary.md
    interruption-*.json
```

`requirements.json` 至少包含：

```json
{
  "campaign_id": "liepin-<topic>-<date>",
  "source_input": "",
  "job_id": 75703601,
  "target_role": "",
  "candidate_profile": {},
  "missing_fields": [],
  "confirmed_defaults": {}
}
```

`strategy.json` 至少包含：

```json
{
  "search_scene": "job",
  "condition_source": "get-search-condition-by-job",
  "overrides": {
    "keyword": "",
    "wantDqs": "",
    "eduLevels": [],
    "workYearsLow": null,
    "workYearsHigh": null,
    "sortType": "0",
    "resumetype": "0"
  },
  "page_plan": {
    "start_cur_page": 0,
    "max_pages": 1
  }
}
```

`run-policy.json` 至少包含：

```json
{
  "execution_surface": "chrome_in_page_fetch",
  "allowed_hosts": ["api-h.liepin.com"],
  "allowed_endpoints": [
    "/api/com.liepin.searchfront4r.h.get-search-condition-by-job",
    "/api/com.liepin.searchfront4r.h.search-resumes"
  ],
  "request_content_type": "application/x-www-form-urlencoded",
  "default_page_limit": 1,
  "max_page_limit": 5,
  "request_interval_seconds": 3,
  "stop_on_login_or_security_page": true,
  "stop_on_captcha": true,
  "stop_on_http_403": true,
  "stop_on_http_429": true,
  "stop_on_http_432": true,
  "stop_on_non_json": true,
  "stop_on_flag_not_1": true,
  "allow_detail_fetch": false,
  "allow_campaign_db_write": false,
  "allow_main_db_write": false,
  "main_db_sync_mode": "manual_only"
}
```

## 7. API 请求合同

### 7.1 按职位获取搜索条件

请求：

```text
POST /api/com.liepin.searchfront4r.h.get-search-condition-by-job
Content-Type: application/x-www-form-urlencoded

jobId=75703601
```

成功响应示例字段：

```json
{
  "flag": 1,
  "data": {
    "eduLevel": "040",
    "eduLevels": ["040", "030", "010"],
    "workYearsLow": 3,
    "workYearsHigh": 99,
    "eduLevelTz": true,
    "nowDqs": "010",
    "wantDqsOut": [{"dqName": "北京", "dqCode": "010"}],
    "searchType": "1",
    "sortType": "0"
  }
}
```

P0 将响应完整保存到 `raw/condition/job-<job_id>.json`。参数生成时只使用白名单字段，并允许 `strategy.json` 覆盖。

### 7.2 搜索简历

请求：

```text
POST /api/com.liepin.searchfront4r.h.search-resumes
Content-Type: application/x-www-form-urlencoded

searchParamsInputVo=<JSON 字符串>&logForm=<JSON 字符串>
```

`searchParamsInputVo` P0 白名单字段：

```json
{
  "nowDqs": "",
  "wantDqs": "010",
  "workYearsLow": 3,
  "workYearsHigh": 99,
  "eduLevels": ["040", "030", "010"],
  "eduLevelTz": true,
  "industrys": "",
  "nowJobTitles": "",
  "wantIndustry": "",
  "wantJobTitles": "",
  "languageSkills": [],
  "resumetype": "0",
  "sortType": "0",
  "searchType": "1",
  "curPage": 0,
  "pageSize": "",
  "keyword": "",
  "anyKeyword": "0",
  "jobName": "",
  "jobPeriod": "0",
  "compName": "",
  "compPeriod": "0",
  "school": "",
  "major": "",
  "schoolKindList": [],
  "activeStatus": "",
  "jobStability": "",
  "jobId": 75703601
}
```

`logForm` P0 字段：

```json
{
  "ckId": "",
  "skId": "",
  "fkId": "",
  "searchScene": "job"
}
```

响应成功后，P0 保存响应里的 `ckId`、`skId`、`fkId`，并将它们写入下一页 continuation。`curPage` 按已观测请求从 `0` 开始；是否必须携带上一页返回的 `skId/fkId`，在 P0 smoke test 中校准。

## 8. 字段映射

P0 标准化输出 `structured/candidate-summaries.jsonl`，不直接写 TalentDB。每行保留猎聘摘要和可追溯 raw 引用。

建议结构：

```json
{
  "platform": "liepin",
  "platform_id": "626d6effe7E64786e28109f",
  "user_id_encode": "a8cdf300df99eef3294faa3b009a587d",
  "display_name": "于**",
  "name_confidence": "masked",
  "current_company": "富藏甲(北京)科技发展有限公司",
  "current_title": "运营经理",
  "city": "北京",
  "education": "本科",
  "work_years": 18,
  "expected_city": "北京",
  "expected_title": "运营经理/主管",
  "active_status": {"code": "5", "name": ""},
  "profile_url": "https://h.liepin.com/resume/showresumedetail/...",
  "resume_source": "h_search",
  "resume_type": 0,
  "raw_ref": {
    "search_page": "raw/search/page-000.json",
    "card_index": 0,
    "ckId": "",
    "skId": "",
    "fkId": ""
  }
}
```

字段来源：

| 标准字段 | 猎聘字段 |
| --- | --- |
| `platform_id` | `simpleResumeForm.resIdEncode` |
| `user_id_encode` | `cardResList[].usercIdEncode` |
| `display_name` | `simpleResumeForm.resName` |
| `current_company` | `simpleResumeForm.resCompany` |
| `current_title` | `simpleResumeForm.resTitle` 或 `highLightJobTitle` |
| `city` | `simpleResumeForm.resDqName` |
| `education` | `simpleResumeForm.resEdulevelName` |
| `work_years` | `simpleResumeForm.resWorkyearAge` |
| `expected_city` | `simpleResumeForm.wantDq` 或 `cardResList[].wantDq` |
| `expected_title` | `simpleResumeForm.wantJobTitle` 或 `cardResList[].wantJobTitle` |
| `profile_url` | `https://h.liepin.com` + `detailUrl` |

姓名通常是脱敏展示名，P0 不尝试还原真实姓名。

## 9. 工作流阶段

### S0 需求合同

读取用户输入，生成 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。P0 只要求 `jobId` 或一组明确的搜索条件；缺少 `jobId` 时，必须明确该任务是通用条件搜索，不调用职位前置接口。

### S1 浏览器页预检

确认用户已在 Chrome 打开并登录猎聘招聘端页面。预检只读取页面 URL、标题和可见文本，不读取浏览器敏感存储。页面不满足条件时停止，并要求用户手动打开猎聘招聘端搜索页。

### S2 条件生成

当有 `jobId` 时，在页面内 fetch `get-search-condition-by-job`。成功后把返回数据与 `strategy.json` overrides 合并为 `searchParamsInputVo`。失败时按停机规则写 interruption。

### S3 搜索计划展开

把 `start_cur_page` 和 `max_pages` 展开成页计划。P0 默认最多 1 页，人工显式确认后最多 5 页。页计划写入 `state/continuation-plan.json`。

### S4 搜索执行

逐页在页面内 fetch `search-resumes`。每次请求前检查 page plan 和 request ledger；每次成功返回后立即写 `raw/search/page-<curPage>.json`，再追加 `state/request-ledger.jsonl`。

### S5 停机与恢复

任一阻断条件出现时立即停止，不继续翻页，不自动重试。写：

```text
reports/interruption-<run_id>-<reason>.json
state/events.jsonl
state/continuation-plan.json
```

恢复时只信磁盘事实：扫描 raw、ledger 和 continuation，跳过已成功页，从下一页继续。

### S6 标准化与摘要

从 raw 中读取 `cardResList`，输出 `structured/candidate-summaries.jsonl`、`reports/search-summary.json` 和 `reports/search-summary.md`。如果字段结构不匹配，记录 `template_drift`，不生成不完整结论。

### S7 人工主库边界

P0 到摘要即止。后续如需导入主库，必须另起设计和实施计划，走 dry-run、备份、apply、完整性校验和人工确认。

## 10. 停机分类

P0 停机分类：

| 原因 | 判定 |
| --- | --- |
| `login_required` | 页面或响应显示登录失效 |
| `captcha_or_security` | 页面或响应含验证码、安全验证、访问异常等证据 |
| `http_403` | HTTP 403 |
| `http_429` | HTTP 429 |
| `http_432` | HTTP 432 或类似平台次数上限 |
| `non_json_response` | 响应不是 JSON |
| `html_response` | API 返回 HTML |
| `flag_not_1` | JSON `flag` 不等于 `1` |
| `template_drift` | 响应缺少 P0 必需字段 |
| `browser_unavailable` | 无法连接或声明的猎聘页不可用 |

停机不等于失败。只要 raw 和 continuation 完整，就可以在用户处理平台状态后恢复。

## 11. 测试与验证

P0 实施时优先写离线测试，不依赖真实猎聘账号：

1. 参数生成测试：`jobId` 默认条件 + overrides 能生成预期 `searchParamsInputVo`。
2. 表单编码测试：请求体必须是 `application/x-www-form-urlencoded`，且 JSON 字段可逆解析。
3. 响应标准化测试：用已观测 `cardResList` fixture 输出候选人摘要。
4. 停机分类测试：覆盖 `flag=0`、HTML、非 JSON、403、429、432、字段缺失。
5. 恢复测试：已有 page 0 raw 时，从 page 1 continuation 继续。
6. 安全扫描测试：实现中不得出现读取浏览器敏感存储的调用。

真实 smoke test 只在用户授权后执行：

```text
1 个 jobId
1 页 search-resumes
raw 落盘
candidate-summaries.jsonl 生成
不抓详情
不写主库
```

## 12. 风险与待校准点

1. `curPage` 已观测为从 `0` 开始，仍需用 P0 smoke test 校准翻页语义。
2. `pageSize` 已观测为空字符串但返回约 30 条，P0 先保留页面默认；是否显式设为 `30` 需另行校准。
3. `ckId/skId/fkId` 的传递规则需要实测。P0 必须保存每页响应返回值，并在 continuation 中记录下一页应使用的值。
4. 猎聘简历姓名和详情权限可能强依赖账号权益。P0 不承诺拿到未展示字段。
5. 账号搜索额度和风控阈值未知。P0 默认 1 页，人工确认后最多 5 页。
6. 详情抓取、详情标准化和 TalentDB 导入都属于 P1 以后范围。

## 13. 后续实施顺序

用户审阅本设计后，下一步进入实施计划。建议实施顺序：

1. 新增离线 API 合同与 fixture 测试。
2. 实现 `liepin_api_contract.py` 的参数生成和响应校验。
3. 实现 `liepin_search_standardize.py` 的 raw 到摘要转换。
4. 实现 `liepin_browser_runner.py` 的白名单页面内 fetch 执行器。
5. 实现 `liepin_campaign_orchestrator.py` 的 init/status/run/resume/summarize。
6. 补充 skill/workflow canonical 文档和架构测试。
7. 在用户授权下执行单页 smoke test。
