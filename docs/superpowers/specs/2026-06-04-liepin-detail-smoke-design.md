# 猎聘详情抓取 P1 小批 smoke 设计

> 日期：2026-06-04
> 状态：已确认方案 A，待用户审阅后进入实施计划
> 执行载体：已登录猎聘招聘端页面内受控 fetch + 本地 CLI 编排

## 1. 背景

猎聘 P0/P1 搜索链路已经完成到 5 页 live smoke、标准化和候选池离线诊断。当前 campaign：

```text
data/campaigns/liepin-smoke-2026-06-03-job-75703601
```

已生成 150 条候选摘要，候选池诊断结果为：

```text
detail_p0=64
detail_p1=61
detail_p2=13
skip=12
```

现有摘要字段已经保留后续详情所需的最小身份信息：

```text
profile_url
platform_id        # resIdEncode
user_id_encode     # usercIdEncode
raw_ref
```

搜索 workflow 明确规定 P0 到搜索摘要和候选池诊断即止。详情抓取、Campaign DB 写入和主库同步必须另起设计和实施计划。本设计只覆盖详情抓取 P1 的第一步：小批 smoke 校准详情接口和恢复机制。

## 2. 目标

P1 小批 smoke 的目标是用最小真实请求量确认猎聘详情抓取是否可以稳定进入可恢复流程：

1. 从 `candidate-pool-diagnostic.json` 选择 `detail_p0` 前 10-20 人生成 detail target pack。
2. 只使用已标准化摘要和 raw 引用里的候选身份字段，不读取浏览器敏感存储。
3. 在已登录猎聘页面上下文内访问详情接口或详情页所需的白名单请求。
4. 每个候选详情 raw 独立落盘到 `raw/detail-live/<pack_id>/job-*.json`。
5. 遇到平台阻断、非 JSON、结构漂移或 partial capture 立即停机。
6. 写入 interruption report 和 continuation plan，使后续可从磁盘事实恢复。
7. 仅输出 smoke 级详情捕获摘要，不写数据库，不生成推荐报告。

## 3. 非目标

本阶段明确不做以下事情：

1. 不抓取 `detail_p0` 全量或 `detail_p1` 候选。
2. 不写 Campaign DB。
3. 不写主库 `data/talent.db`。
4. 不生成最终推荐报告、外联队列、飞书交付包或主库同步包。
5. 不还原脱敏姓名，不尝试绕过平台对简历详情的展示权限。
6. 不读取、导出、复制或保存 Chrome cookie、localStorage、sessionStorage、profile、密码或 session store。
7. 不构建脱离浏览器上下文的纯 HTTP 客户端。
8. 不绕过登录、验证码、安全页、权限、付费限制、详情日限或平台风控。

## 4. 推荐方案

采用“detail target pack + 页面内受控 fetch + per-candidate raw job”的小批 smoke 方案。

| 方案 | 说明 | 结论 |
| --- | --- | --- |
| 小批 smoke | 只取 `detail_p0` 前 10-20 人，校准接口、落盘和恢复 | 推荐，真实请求量小，风险面可控 |
| 全量 `detail_p0` 分包 | 直接把 64 个 P0 候选拆包执行 | 暂不推荐，接口未校准前容易放大阻断和脏数据 |
| 纯离线 target pack | 只生成 pack，不触发浏览器请求 | 可作为实施第一步，但不能验证详情接口 |

实施计划应先完成离线 target pack 和单元测试，再实现 live gate。第一次真实执行默认 `--limit 10`，用户明确要求时才放宽到 20。

## 5. 架构边界

建议新增或扩展以下模块：

```text
scripts/liepin_detail_targets.py
scripts/liepin_detail_live_gate.py
scripts/liepin_campaign_orchestrator.py
agents/workflows/liepin-unattended-campaign/AGENT.md
agents/skills/liepin-talent-search-campaign/SKILL.md
```

职责分层：

| 模块 | 职责 |
| --- | --- |
| `liepin_detail_targets.py` | 读取候选池诊断和摘要 JSONL，生成小批 detail target pack |
| `liepin_detail_live_gate.py` | 连接 CDP、健康检查、执行白名单详情请求、写 raw job、处理中断 |
| `liepin_campaign_orchestrator.py` | 暴露 `plan-detail-smoke` 和 `run-live-detail-smoke` 命令 |
| canonical workflow | 增加 S8 之后的 P1 详情 smoke 阶段和停机边界 |
| canonical skill | 标明详情 smoke 需要单独确认，不自动进入主库或推荐交付 |

不新增运行时业务脚本目录；所有 Python 业务逻辑仍放在 `scripts/`。

## 6. Detail Target Pack

目标包保存到：

```text
data/campaigns/<campaign_id>/raw/detail-targets/liepin-detail-p0-smoke-001.json
```

建议结构：

```json
{
  "metadata": {
    "export_type": "liepin_detail_smoke_targets",
    "campaign_id": "liepin-smoke-2026-06-03-job-75703601",
    "pack_id": "liepin-detail-p0-smoke-001",
    "source_priority": "detail_p0",
    "limit": 10,
    "created_at": "2026-06-04T00:00:00+08:00",
    "no_database_write": true
  },
  "contacts": [
    {
      "index": 0,
      "platform": "liepin",
      "platform_id": "res-id-encode",
      "user_id_encode": "userc-id-encode",
      "profile_url": "https://h.liepin.com/resume/showresumedetail/...",
      "display_name": "候选人摘要名",
      "current_company": "当前公司",
      "current_title": "当前职位",
      "priority": "detail_p0",
      "raw_ref": {
        "search_page": 0,
        "card_index": 0
      }
    }
  ]
}
```

选择规则：

1. 只读取 `structured/candidate-summaries.jsonl` 和 `reports/candidate-pool-diagnostic.json`。
2. 只选择 `priority=detail_p0`。
3. 默认限制 10 人，上限 20 人。
4. 按候选池诊断已有顺序稳定排序。
5. `platform_id`、`user_id_encode`、`profile_url` 缺失时跳过，并在 pack report 记录原因。
6. target pack 可以包含 `profile_url`，但报告样本和公开摘要必须继续脱敏，不展示 `showresumedetail` 或 `ck/sk/fk` token。

## 7. 详情接口校准

详情 smoke 的 live gate 不预设完整接口合同。第一次实现应支持两层校准：

1. 从 `profile_url` 或 raw search card 中解析猎聘详情页路径和 query。
2. 在页面上下文内执行最小白名单请求，捕获响应形态。

白名单只允许猎聘招聘端相关 host：

```text
h.liepin.com
api-h.liepin.com
```

如果详情页本身返回 HTML，而真实详情数据由后续 API 加载，P1 smoke 只记录可确认的响应形态和必要 API，不做 DOM 抓取和点击。若接口需要新的非敏感 header，应复用现有 `state/request-template.json` 清洗机制，只允许 allowlist header，并继续拒绝认证类 header。

保存 raw 时应记录：

```json
{
  "status": "done",
  "platform_id": "res-id-encode",
  "user_id_encode": "userc-id-encode",
  "profile_url_ref": true,
  "requests": [
    {
      "name": "detail",
      "url": "https://api-h.liepin.com/...",
      "httpStatus": 200,
      "contentType": "application/json",
      "data": {}
    }
  ],
  "captured_at": "2026-06-04T00:00:00+08:00"
}
```

`profile_url_ref=true` 表示 raw 内存在详情 URL 引用；公开报告不得展开该 URL。

## 8. 执行流程

### S1 生成目标包

命令形态：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-smoke \
  --campaign-root data/campaigns/<campaign_id> \
  --priority detail_p0 \
  --limit 10
```

输出：

```text
raw/detail-targets/liepin-detail-p0-smoke-001.json
reports/detail-smoke-targets.json
reports/detail-smoke-targets.md
```

### S2 页面健康检查

沿用现有 CDP health check，只读取 URL、标题和可见文本。必须确认：

1. 页面属于猎聘招聘端。
2. 未出现登录页、验证码、安全验证或访问异常。
3. 当前 CDP target 可执行 `Runtime.evaluate`。

健康检查失败时不执行详情请求。

### S3 详情 smoke 执行

命令形态：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-smoke \
  --campaign-root data/campaigns/<campaign_id> \
  --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json \
  --cdp-url http://127.0.0.1:9898 \
  --limit 10 \
  --delay-seconds 3 \
  --timeout-seconds 20
```

每个候选成功后立即写：

```text
raw/detail-live/liepin-detail-p0-smoke-001/job-000.json
raw/detail-live/liepin-detail-p0-smoke-001/job-001.json
```

并追加：

```text
state/detail-request-ledger.jsonl
```

### S4 标准化摘要

本阶段只输出 smoke capture summary：

```text
reports/detail-smoke-summary.json
reports/detail-smoke-summary.md
```

摘要只统计：

```text
targets
completed
failed
blocked
template_drift
captured_field_groups
next_step
```

不生成候选推荐结论，不进入 DB import。

## 9. 停机与恢复

遇到以下任一情况立即停止当前 pack，不继续下一人，不重试：

1. 登录页或登录失效。
2. 验证码、安全验证或访问异常。
3. HTTP 401、403、429、432。
4. 非 JSON 响应且无法确认是预期 HTML 详情页。
5. JSON `flag`、`code` 或业务状态显示失败、无权限、余额不足、访问受限。
6. 响应结构与已校准详情字段不匹配。
7. 单个候选只捕获到 partial detail。
8. CDP/WebSocket 断开或页面 target 不可用。

停机产物：

```text
reports/interruption-detail-<pack_id>-<date>.json
raw/detail-live/<pack_id>/job-*.json
state/detail-live-<pack_id>-continuation-after-<reason>.json
```

恢复规则：

1. 只信磁盘事实：target pack、`raw/detail-live/<pack_id>/job-*.json`、detail ledger 和 continuation plan。
2. 已有 `status=done` 的 job 不重复请求。
3. 从 `resume_from.platform_id` 或下一 job index 继续。
4. 如果停机原因是登录、验证码、安全验证或平台限制，必须等待用户处理后再恢复。

## 10. 安全与数据处理

详情 smoke 延续猎聘搜索线的安全边界：

1. CDP 只用于页面内 `Runtime.evaluate`，不读取浏览器敏感存储。
2. 请求 header 只来自清洗后的 allowlist 模板。
3. 显式拒绝 `Cookie`、`Authorization`、`Proxy-Authorization`。
4. 不保存浏览器 profile、session、storage 或认证材料。
5. raw 产物保存在 ignored campaign 目录，报告样本默认脱敏。
6. 不把详情 URL、`showresumedetail`、`ck/sk/fk` token 放入公开 Markdown 样本。
7. 不绕过平台风控；阻断即停机。

## 11. 测试策略

实施阶段按 TDD 增加以下测试：

```text
tests/test_liepin_detail_targets.py
tests/test_liepin_detail_live_gate.py
tests/test_liepin_campaign_orchestrator.py
tests/test_agent_architecture.py
```

覆盖点：

1. target pack 只选择 `detail_p0`，默认限制 10，上限 20。
2. 缺失 `profile_url/platform_id/user_id_encode` 的候选被跳过并记录原因。
3. live gate 表达式只访问白名单 host。
4. header 清洗拒绝认证类 header。
5. HTTP 401/403/429/432、非 JSON、验证码、安全页、partial capture 都生成 interruption 和 continuation。
6. per-candidate raw job 可用于恢复，已完成 job 不重复请求。
7. summary 报告不展示详情 URL、`showresumedetail` 或 `ck/sk/fk` token。

验证命令：

```bash
.venv/bin/python -m pytest tests/test_liepin_* tests/test_agent_architecture.py -q
.venv/bin/python -m pytest tests -q
rg -n "cookies\(|context\.cookies|document\.cookie|localStorage|sessionStorage" scripts/liepin_*.py tests/test_liepin_*.py agents/skills/liepin-talent-search-campaign agents/workflows/liepin-unattended-campaign
git diff --check
```

## 12. 验收标准

设计进入实施后，P1 小批 smoke 只有在以下条件全部满足时才算完成：

1. 离线 target pack 生成稳定，可重复。
2. 第一次 live smoke 请求数不超过 10 个候选。
3. 所有成功详情都有独立 raw job 文件。
4. 任一阻断都有 interruption report 和 continuation plan。
5. detail summary 只描述捕获状态和字段组，不给候选推荐结论。
6. 聚焦测试、全量测试、安全扫描和 `git diff --check` 通过。
7. 没有 Campaign DB 写入，没有主库写入。

## 13. 后续阶段

本设计完成后进入实施计划。实施计划应分成四个可验证步骤：

1. 离线 target pack。
2. live gate dry-run 表达式和阻断处理。
3. 小批真实 smoke。
4. smoke summary 和 workflow/skill 文档更新。

若 smoke 成功，后续仍需另起设计决定是否进入：

1. `detail_p0` 全量分包。
2. `detail_p1` 扩展。
3. Campaign DB detail import。
4. 主库同步和候选推荐交付。
