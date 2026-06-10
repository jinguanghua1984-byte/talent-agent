# Workflow Shared Policies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将长 workflow 中重复的自动化安全、主库写入、飞书发布和中断恢复合同抽成 shared policies，并压缩高频入口文档的默认加载成本。

**Architecture:** `agents/policies/` 保存跨 workflow 复用的安全与门禁合同；各 `agents/workflows/*/AGENT.md` 只保留触发入口、阶段状态机、workflow 特有产物和需要读取的 policy/reference。`tests/test_agent_architecture.py` 同时锁住 policy 文件内容、workflow 引用和现有关键安全 token，确保压缩不改变业务行为。

**Tech Stack:** Markdown canonical docs, Python `pathlib`, pytest contract tests.

---

## Scope

本计划只做运行时中立文档和合同测试重构，不修改业务脚本，不触发平台请求，不发布飞书，不写 Campaign DB 或 `data/talent.db`。

本轮优先处理：

- shared policies：平台自动化安全、主库同步门禁、飞书发布/通知门禁、campaign 恢复事实源。
- workflow 引用和压缩：`boss-maimai-cross-channel-delivery`、`jd-talent-delivery`、`liepin-unattended-campaign`、`maimai-unattended-campaign`。
- 最大长文档压缩：`public-search` 的执行细节拆到 `commands.md`，`AGENT.md` 保留入口和状态机。

本轮不处理：

- Python 代码行为变化。
- `LLMUsageLedger` 深化、provider batch API、模型路由配置变更。
- 真实 BOSS/脉脉/猎聘/飞书执行。
- 主库同步 apply 或任何 `data/talent.db` 写入。

## File Map

- Create: `agents/policies/README.md`
  Shared policy 目录索引，说明 canonical workflow 应如何引用 policy。
- Create: `agents/policies/platform-automation-safety.md`
  统一平台自动化边界：Computer Use、CDP、外部执行器窄例外、登录/验证码/风控停机。
- Create: `agents/policies/main-db-sync-gates.md`
  统一 Campaign DB 到 `data/talent.db` 的 dry-run/apply、bundle 校验、一次总授权和 `CONFIRM_SYNC_TEXT`。
- Create: `agents/policies/feishu-publish-gates.md`
  统一飞书 dry-run、发布、回读、IM 通知和 `blocked_notification_failed`。
- Create: `agents/policies/campaign-recovery.md`
  统一中断证据、`state/continuation-plan.json`、磁盘事实源和 `campaign_status summarize` / `next-action` 恢复入口。
- Create: `agents/workflows/public-search/commands.md`
  从 `public-search/AGENT.md` 拆出的执行搜索、token tracker、反馈、迭代和策略沉淀细节。
- Modify: `agents/capabilities.md`
  加入 shared policy 索引，保持运行时中立能力表不变。
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
  引用 shared policies，压缩重复安全/同步/飞书通知段落，保留 BOSS-Maimai 特有产物与 recent safety contracts。
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
  引用 main-db read-only 和 Feishu publish policies，压缩 S7/S8 重复门禁，保留 JD 交付特有目标和反馈 S9。
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`
  引用 platform/recovery/main-db policies，压缩重复停机和“不得写主库/不得交付”段落，保留猎聘阶段特有命令与确认文本。
- Modify: `agents/workflows/maimai-unattended-campaign/AGENT.md`
  增加 policy 引用，保留脉脉 CDP bootstrap、无人值守和主库人工边界。
- Modify: `agents/workflows/public-search/AGENT.md`
  改为轻量入口，指向 `commands.md` 和既有 references。
- Modify: `tests/test_agent_architecture.py`
  增加 policy/reference/line-budget 合同测试，并保留现有关键断言。
- Modify: `tasks/todo.md` and `tasks/archive/2026-06.md`
  实施完成后记录高层结果、验证证据和归档；计划阶段只记录 Active Task。

## Safety Contracts To Preserve

实施时这些字符串不能丢失，只能从 workflow 移到 policy 或在 workflow 中保留 workflow 特有引用：

- `Computer Use`
- `外部执行器`
- `不得使用 osascript`
- `坐标点击`
- `agents/workflows/maimai-unattended-campaign/AGENT.md`
- `auto_bootstrap_browser_after_plan_confirmation=true`
- `data/session/maimai-cdp-profile`
- `extensions/maimai-scraper`
- `--remote-debugging-port=9888`
- `http://127.0.0.1:9888`
- `state/continuation-plan.json`
- `campaign_status summarize`
- `next-action`
- `blocked_notification_failed`
- `data/talent.db`
- `talent_sync.py export`
- `verify-bundle`
- `talent_sync.py import`
- `CONFIRM_SYNC_TEXT`
- `确认同步人才库`
- `JD需求交付`
- `JD需求协同`
- `im +chat-search`
- `im +messages-send`
- `feishu/im-notification-results.json`
- `飞书发布和回读通过后`

## Implementation Tasks

### Task 1: Add RED Architecture Tests

**Files:**
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Add shared policy constants and tests**

Append this code near the existing workflow contract tests:

```python
POLICY_CONTRACTS = {
    "platform-automation-safety": [
        "Computer Use",
        "外部执行器",
        "不得使用 osascript",
        "坐标点击",
        "CDP",
        "登录",
        "验证码",
        "安全页",
        "state/continuation-plan.json",
    ],
    "main-db-sync-gates": [
        "Campaign DB",
        "`data/talent.db`",
        "`talent_sync.py export`",
        "`verify-bundle`",
        "`talent_sync.py import`",
        "`CONFIRM_SYNC_TEXT`",
        "确认同步人才库",
        "一次总授权",
        "不得自动执行主库同步",
    ],
    "feishu-publish-gates": [
        "lark-cli",
        "dry-run",
        "回读",
        "`JD需求交付`",
        "`JD需求协同`",
        "`im +chat-search`",
        "`im +messages-send`",
        "`feishu/im-notification-results.json`",
        "blocked_notification_failed",
    ],
    "campaign-recovery": [
        "`reports/interruption-*.json`",
        "`state/continuation-plan.json`",
        "`state/events.jsonl`",
        "`state/request-ledger.jsonl`",
        "磁盘事实",
        "campaign_status summarize",
        "next-action",
        "不得盲信内存上下文",
    ],
}


def test_shared_policy_files_define_reusable_contracts():
    for name, required_tokens in POLICY_CONTRACTS.items():
        path = ROOT / "agents" / "policies" / f"{name}.md"
        assert path.exists(), f"missing shared policy: {path}"
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# ")
        for token in required_tokens:
            assert token in text, f"{path} missing policy token: {token}"
```

- [ ] **Step 2: Add workflow reference tests**

Append this code after `test_shared_policy_files_define_reusable_contracts`:

```python
WORKFLOW_POLICY_REFERENCES = {
    "boss-maimai-cross-channel-delivery": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "jd-talent-delivery": [
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "liepin-unattended-campaign": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
    "maimai-unattended-campaign": [
        "agents/policies/platform-automation-safety.md",
        "agents/policies/main-db-sync-gates.md",
        "agents/policies/feishu-publish-gates.md",
        "agents/policies/campaign-recovery.md",
    ],
}


def test_workflows_reference_shared_policies_for_reused_gates():
    for workflow_name, required_refs in WORKFLOW_POLICY_REFERENCES.items():
        workflow = (
            ROOT / "agents" / "workflows" / workflow_name / "AGENT.md"
        ).read_text(encoding="utf-8")
        for ref in required_refs:
            assert ref in workflow, f"{workflow_name} missing shared reference {ref}"
```

- [ ] **Step 3: Add line-budget tests**

Append this code after the reference tests:

```python
WORKFLOW_LINE_BUDGETS = {
    "boss-maimai-cross-channel-delivery": 190,
    "jd-talent-delivery": 215,
    "liepin-unattended-campaign": 265,
    "public-search": 260,
}


def test_compressed_workflows_stay_within_line_budgets():
    for workflow_name, max_lines in WORKFLOW_LINE_BUDGETS.items():
        path = ROOT / "agents" / "workflows" / workflow_name / "AGENT.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= max_lines, f"{workflow_name} has {len(lines)} lines"
```

- [ ] **Step 4: Add public-search command extraction test**

Append this code after the line-budget tests:

```python
def test_public_search_commands_reference_preserves_execution_contract():
    workflow = (
        ROOT / "agents" / "workflows" / "public-search" / "AGENT.md"
    ).read_text(encoding="utf-8")
    commands = (
        ROOT / "agents" / "workflows" / "public-search" / "commands.md"
    ).read_text(encoding="utf-8")

    assert "agents/workflows/public-search/commands.md" in workflow
    for token in [
        "Token Tracker",
        "scripts/public_search/token_tracker.py",
        "data/token-tracker/tokens.jsonl",
        "搜索反馈",
        "迭代循环",
        "策略沉淀",
        "放弃记录",
    ]:
        assert token in commands
```

- [ ] **Step 5: Run RED tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_agent_architecture.py::test_shared_policy_files_define_reusable_contracts \
  tests/test_agent_architecture.py::test_workflows_reference_shared_policies_for_reused_gates \
  tests/test_agent_architecture.py::test_compressed_workflows_stay_within_line_budgets \
  tests/test_agent_architecture.py::test_public_search_commands_reference_preserves_execution_contract \
  -q
```

Expected: FAIL because `agents/policies/*.md` and `agents/workflows/public-search/commands.md` do not exist yet, and current workflow line counts exceed the new budgets.

### Task 2: Create Shared Policy Documents

**Files:**
- Create: `agents/policies/README.md`
- Create: `agents/policies/platform-automation-safety.md`
- Create: `agents/policies/main-db-sync-gates.md`
- Create: `agents/policies/feishu-publish-gates.md`
- Create: `agents/policies/campaign-recovery.md`

- [ ] **Step 1: Create policy directory index**

Create `agents/policies/README.md`:

```markdown
# Shared Agent Policies

这些 policy 是运行时中立的 cross-workflow 安全合同。`agents/workflows/*/AGENT.md` 应在资源索引中引用需要的 policy，并只保留本 workflow 特有阶段、命令和产物。

| Policy | 用途 |
| --- | --- |
| `agents/policies/platform-automation-safety.md` | 平台自动化、Computer Use、CDP、外部执行器和平台阻断停机边界 |
| `agents/policies/main-db-sync-gates.md` | Campaign DB 到主库 `data/talent.db` 的 dry-run/apply 门禁 |
| `agents/policies/feishu-publish-gates.md` | 飞书 dry-run、发布、回读和 IM 完成通知门禁 |
| `agents/policies/campaign-recovery.md` | 中断证据、continuation plan、磁盘事实源和下一步判断 |
```

- [ ] **Step 2: Create platform automation safety policy**

Create `agents/policies/platform-automation-safety.md` with these sections:

```markdown
# Platform Automation Safety Policy

## 适用范围

适用于 BOSS、脉脉、猎聘等需要真实平台页面、CDP、Computer Use 或受限执行器参与的 workflow。

## 通用禁止项

- 不绕过登录、验证码、安全页、权限、付费限制、搜索日限或平台风控。
- 不读取 Chrome cookie、localStorage、sessionStorage、profile、密码或 session store。
- 不构建脱离浏览器登录上下文的纯 HTTP 客户端。
- 不用 `osascript`、坐标点击、截图脚本点击或其它本机自动化替代 Computer Use 做列表浏览、详情采集、滚屏、返回、筛选判断或页面上下文判断。

## Computer Use 边界

浏览、滚屏、进详情、返回列表、展开详情和筛选判断全部使用 Computer Use / `computer.operate`。如果运行时 Computer Use 缺失，必须停止并写入 `state/continuation-plan.json`，不得用 shell/UI 脚本继续浏览。

## 外部执行器窄例外

外部执行器只能在 workflow 已确认当前详情页、`state/current-contact-intent.json` 和 `executor-policy.json` 均通过后，处理当前详情页的一次 `立即沟通` 原子点击。执行器不得翻列表、找人、筛选、滚屏、读取详情上下文或替代 `computer.operate`。

## CDP 边界

CDP 只能复用浏览器登录上下文内的页面内受控请求或页面状态读取。脉脉默认 bootstrap 合同包含 `auto_bootstrap_browser_after_plan_confirmation=true`、`data/session/maimai-cdp-profile`、`extensions/maimai-scraper`、`--remote-debugging-port=9888` 和 `http://127.0.0.1:9888`；具体 workflow 可声明自己的 profile、端口和扩展。

## 停机条件

遇到登录失效、验证码、安全页、安全验证、访问异常、权限不足、HTTP 401/403/429/432、非 JSON、模板漂移、页面不匹配、付费弹窗或疑似真实发送风险时，必须停止当前阶段，写 `reports/interruption-*.json`，更新 `state/continuation-plan.json`，并追加事件账本。
```

- [ ] **Step 3: Create main DB sync gates policy**

Create `agents/policies/main-db-sync-gates.md` with these sections:

```markdown
# Main DB Sync Gates Policy

## 适用范围

适用于 Campaign DB、同步 bundle 或本地候选结果准备写入主库 `data/talent.db` 的 workflow。

## 基本边界

- `data/talent.db` 是主人才库，未通过本 policy 前不得创建、覆盖或写入。
- Campaign DB apply 不等于主库 apply；Campaign DB clean 后仍必须单独执行主库 dry-run。
- 无人值守授权不覆盖主库写入。

## 必需步骤

1. 先执行 `talent_sync.py export` 导出源 bundle。
2. 执行 `verify-bundle` 校验 bundle。
3. 对目标 `data/talent.db` 执行 `talent_sync.py import` dry-run，生成 dry-run/apply 计划。
4. dry-run 必须覆盖新增、更新、冲突、跳过、身份绑定、字段来源和交付影响。
5. 只有 Campaign DB clean、dry-run 无阻塞冲突、bundle 校验通过、用户对本次 dry-run 给出一次总授权，并提供 `CONFIRM_SYNC_TEXT` / `确认同步人才库`，才能执行 `talent_sync.py import --apply`。

## 授权约束

一次总授权只覆盖本 campaign、本 bundle 和本 dry-run。源数据、bundle、目标 DB 或 dry-run 结果变化后，必须重新 dry-run 并重新授权。不得自动执行主库同步，不得复用旧授权。
```

- [ ] **Step 4: Create Feishu publish gates policy**

Create `agents/policies/feishu-publish-gates.md` with these sections:

```markdown
# Feishu Publish Gates Policy

## 适用范围

适用于需要通过 `lark-cli` 发布 Docs、Sheets、Drive、Wiki 或发送飞书 IM 通知的 workflow。

## 发布前门禁

- 发布前必须执行对应 manifest dry-run，确认只引用本次任务的报告、表格、quality gates 和输出目录。
- 发布前必须校验 `lark-cli doctor`、`lark-cli auth status` 和所需 Docs/Sheets/Wiki/IM scope。
- 包含中文 JSON payload 的命令必须使用 UTF-8 argv runner，不得把 JSON、中文或 URL 拼成 PowerShell 字符串。

## 发布和回读

飞书发布后必须回读 Wiki 节点、Doc outline、Sheet 表头和前几行。回读是验证，不是乱码修复兜底；如果回读不一致，视为发布失败，必须修正发布器或 manifest。

## IM 完成通知

飞书发布和回读通过后，必须发送 IM 完成通知。默认知识库和群包括 `JD需求交付` 与 `JD需求协同`；默认命令形态为 `im +chat-search` 和 `im +messages-send`。通知正文、发送结果和回读证据必须写入 `feishu/im-notification-results.json` 或 workflow 指定的等价产物。

## 通知失败

通知失败不得改变业务执行结果，但不得把任务误报为完整关闭。通知失败状态必须写为 `blocked_notification_failed`，并记录可恢复的通知重试入口。
```

- [ ] **Step 5: Create campaign recovery policy**

Create `agents/policies/campaign-recovery.md` with these sections:

```markdown
# Campaign Recovery Policy

## 事实源

恢复时只信磁盘事实，不盲信内存上下文。优先读取 campaign-local raw、`state/continuation-plan.json`、`state/events.jsonl`、`state/request-ledger.jsonl`、import ledger、reports 和 dry-run/apply 结果。

## 中断证据

停机后必须保留已成功 raw 和中断证据，写入 `reports/interruption-*.json`，追加 `state/events.jsonl` 或 `state/request-ledger.jsonl`，并更新 `state/continuation-plan.json`。已成功页、已成功 target 或 terminal job 不得重复请求。

## 恢复入口

长任务恢复优先运行 `campaign_status summarize` 获取一页摘要，再运行 `next-action` 获取合法下一步、阻塞原因、需要的确认文本、安全命令和禁止事项。

## 停机后行为

如果恢复摘要缺少必要 raw、manifest、continuation plan 或 dry-run 证据，必须停止并生成修复说明。不得用模型推断替代缺失的磁盘事实，不得在不确定阶段继续发起平台请求或写入数据库。
```

- [ ] **Step 6: Run policy test subset**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_shared_policy_files_define_reusable_contracts -q
```

Expected: PASS.

### Task 3: Wire Policies Into Capabilities And Workflow Resource Indexes

**Files:**
- Modify: `agents/capabilities.md`
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`
- Modify: `agents/workflows/maimai-unattended-campaign/AGENT.md`

- [ ] **Step 1: Add shared policy index to capabilities**

Add a short section to `agents/capabilities.md`:

```markdown
## Shared Policies

运行时适配器执行 workflow 前，必须读取 workflow 资源索引中列出的 shared policy：

- `agents/policies/platform-automation-safety.md`
- `agents/policies/main-db-sync-gates.md`
- `agents/policies/feishu-publish-gates.md`
- `agents/policies/campaign-recovery.md`
```

- [ ] **Step 2: Add resource-index references**

For each workflow, add these rows to its resource/reference table or equivalent section:

```markdown
| `agents/policies/platform-automation-safety.md` | 平台自动化、Computer Use、CDP、外部执行器和平台阻断停机边界 |
| `agents/policies/main-db-sync-gates.md` | Campaign DB 到主库 `data/talent.db` 的 dry-run/apply 门禁 |
| `agents/policies/feishu-publish-gates.md` | 飞书发布、回读和 IM 完成通知门禁 |
| `agents/policies/campaign-recovery.md` | 中断证据、continuation plan、磁盘事实源和下一步判断 |
```

Only include policies that apply to that workflow:

- BOSS-Maimai: all four.
- JD delivery: main DB, Feishu, recovery.
- Liepin: platform, main DB, recovery.
- Maimai: all four.

- [ ] **Step 3: Run reference tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_workflows_reference_shared_policies_for_reused_gates -q
```

Expected: PASS after all resource-index references exist.

### Task 4: Compress BOSS-Maimai Workflow Without Losing Recent Safety Contracts

**Files:**
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- Test: `tests/test_agent_architecture.py`

- [ ] **Step 1: Replace repeated policy prose with policy references**

In `boss-maimai-cross-channel-delivery/AGENT.md`, keep BOSS-Maimai-specific stages S0-S10 and remove generic explanations that are now covered by:

- `agents/policies/platform-automation-safety.md`
- `agents/policies/main-db-sync-gates.md`
- `agents/policies/feishu-publish-gates.md`
- `agents/policies/campaign-recovery.md`

Keep these workflow-specific tokens in the workflow file itself:

```text
agents/workflows/maimai-unattended-campaign/AGENT.md
auto_bootstrap_browser_after_plan_confirmation=true
data/session/maimai-cdp-profile
extensions/maimai-scraper
--remote-debugging-port=9888
http://127.0.0.1:9888
raw/maimai-match-search/<target_id>/query-*.json
state/import-ledger.jsonl
structured/maimai-match-targets.jsonl
state/cross-channel-identity-ledger.jsonl
reports/main-db-sync-dry-run.json
CONFIRM_SYNC_TEXT
S10 BOSS campaign delivery / 飞书交付
feishu/boss-maimai-delivery-manifest.json
feishu/im-notification-message.txt
feishu/im-notification-results.json
JD需求协同
旧 Top30 飞书包保持不动
```

- [ ] **Step 2: Preserve contract tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_agent_architecture.py::test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates \
  tests/test_agent_architecture.py::test_boss_maimai_cross_channel_s10_is_campaign_delivery_not_jd_default \
  tests/test_agent_architecture.py::test_boss_maimai_cross_channel_reuses_maimai_cdp_unattended_contract \
  -q
```

Expected: PASS.

- [ ] **Step 3: Check line budget**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_compressed_workflows_stay_within_line_budgets -q
```

Expected: this test may still fail for other workflows until later tasks, but the failure output for `boss-maimai-cross-channel-delivery` must be gone.

### Task 5: Compress JD Delivery Workflow Feishu And Recovery Gates

**Files:**
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Test: `tests/test_agent_architecture.py`

- [ ] **Step 1: Keep JD-specific orchestration**

Keep these sections in `jd-talent-delivery/AGENT.md`:

- Trigger and defaults: `top_n=30`, `publish_feishu=true`, `wiki_space_id=7642607697183001542`.
- S0-S6 local JD/profile/scorecard/matching/report stages.
- S7 and S8 as short stage commands and workflow-specific outputs.
- S9 feedback parsing boundary and `feedback_note`-only contract.

- [ ] **Step 2: Move repeated Feishu text to policy reference**

Replace repeated Feishu dry-run,回读,IM 说明 with concise references to `agents/policies/feishu-publish-gates.md`, while keeping these workflow-specific tokens:

```text
JD需求交付
JD需求协同
lark-cli
im +chat-search
im +messages-send
feishu/im-notification-results.json
飞书完成通知
data/talent.db 只读
feedback_note
```

- [ ] **Step 3: Run JD workflow tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_jd_talent_delivery_workflow.py \
  tests/test_jd_talent_delivery_skill.py \
  tests/test_agent_architecture.py::test_shared_policy_files_define_reusable_contracts \
  tests/test_agent_architecture.py::test_workflows_reference_shared_policies_for_reused_gates \
  -q
```

Expected: PASS.

### Task 6: Compress Liepin And Maimai Platform/Recovery Gates

**Files:**
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`
- Modify: `agents/workflows/maimai-unattended-campaign/AGENT.md`
- Test: `tests/test_agent_architecture.py`

- [ ] **Step 1: Compress Liepin duplicated stop/recovery/main-db prose**

In `liepin-unattended-campaign/AGENT.md`, keep the phase-specific commands and confirmation texts. Move generic platform and recovery rules to policy references.

Keep these Liepin-specific tokens:

```text
launch-browser --profile data/session/liepin-cdp-profile --remote-debugging-port 9898
plan-adaptive-search
run-live-adaptive-search
standardize-adaptive-search
broad-recall-summary
main-db-sync-handoff
import-search-dry-run
import-search-apply
确认写入猎聘搜索结果
detail-dry-run
detail-apply
确认写入猎聘详情
plan-detail-packs
run-live-detail-pack
detail_pack_already_terminal
calibrate-detail-api
raw/detail-live/<pack_id>/job-*.json
state/detail-request-ledger.jsonl
```

- [ ] **Step 2: Add Maimai policy references without weakening bootstrap contract**

In `maimai-unattended-campaign/AGENT.md`, add resource references to the four policies. Do not remove these Maimai-specific tokens:

```text
auto_bootstrap_browser_after_plan_confirmation=true
data/session/maimai-cdp-profile
extensions/maimai-scraper
--remote-debugging-port=9888
http://127.0.0.1:9888
blocked_notification_failed
data/talent.db
```

- [ ] **Step 3: Run Liepin/Maimai architecture tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_agent_architecture.py::test_liepin_contracts_define_broad_recall_adaptive_planning_boundary \
  tests/test_agent_architecture.py::test_liepin_contracts_define_detail_smoke_boundary \
  tests/test_agent_architecture.py::test_boss_maimai_cross_channel_reuses_maimai_cdp_unattended_contract \
  tests/test_agent_architecture.py::test_workflows_reference_shared_policies_for_reused_gates \
  -q
```

Expected: PASS.

### Task 7: Extract Public Search Execution Details To Commands Document

**Files:**
- Create: `agents/workflows/public-search/commands.md`
- Modify: `agents/workflows/public-search/AGENT.md`
- Test: `tests/test_agent_architecture.py`

- [ ] **Step 1: Create public-search commands document**

Move the detailed sections from `public-search/AGENT.md` into `agents/workflows/public-search/commands.md`:

```markdown
# public-search Commands And Execution Contracts

## 执行搜索

保留原 `## 执行搜索`、`### 执行逻辑`、`### Token 消耗追踪`、`### 信息提取`、`### 候选人写入`、`### 批次记录` 的完整业务合同。

## 搜索反馈

保留原 `## 搜索反馈`、三层反馈、成本分析、Token Tracker 降级规则。

## 迭代循环

保留原 `## 迭代循环`、用户选择、每轮迭代操作和 Git commit 记录规则。

## 策略沉淀

保留原 `## 搜索结果：放弃`、`## 策略沉淀`、Instance 到 Template 到 Universal 规则的提升流程、用户可控原则和数据排除规则。

## 岗位感知

保留原 `## 岗位感知` 和 `### Token Tracker 部署`。
```

The implementation should move the actual existing prose, not replace it with the summary above.

- [ ] **Step 2: Keep AGENT.md as routing/state-machine entry**

Update `public-search/AGENT.md` so it keeps:

- front matter and `# 公域搜索`
- `## 触发入口`
- `## 引导模式`
- `## 工具依赖`
- `## 参考文档`
- `## 协作策略生成`
- a short `## 执行与恢复` section that points to `agents/workflows/public-search/commands.md`

Add this explicit reference:

```markdown
执行搜索、Token Tracker、反馈、迭代循环、放弃记录、策略沉淀和岗位感知的详细合同位于 `agents/workflows/public-search/commands.md`。运行时进入执行阶段前必须读取该文件。
```

- [ ] **Step 3: Run public-search tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_agent_architecture.py::test_public_search_commands_reference_preserves_execution_contract \
  tests/test_agent_architecture.py::test_compressed_workflows_stay_within_line_budgets \
  -q
```

Expected: PASS for `public-search`; if other line budgets still fail, finish the remaining compression before final verification.

### Task 8: Full Verification

**Files:**
- Read-only verification across repo.

- [ ] **Step 1: Check line counts**

Run:

```bash
wc -l \
  agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md \
  agents/workflows/jd-talent-delivery/AGENT.md \
  agents/workflows/liepin-unattended-campaign/AGENT.md \
  agents/workflows/public-search/AGENT.md \
  agents/workflows/public-search/commands.md \
  agents/policies/*.md
```

Expected:

- `boss-maimai-cross-channel-delivery/AGENT.md` <= 190 lines.
- `jd-talent-delivery/AGENT.md` <= 215 lines.
- `liepin-unattended-campaign/AGENT.md` <= 265 lines.
- `public-search/AGENT.md` <= 260 lines.
- New policy docs and `commands.md` hold the extracted detail.

- [ ] **Step 2: Run architecture tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full tests**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: PASS.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

### Task 9: Update Task Ledger And Archive

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Write implementation review**

After verification passes, update `tasks/todo.md` with a short Review:

```markdown
## Review

- 新增 `agents/policies/` shared policy 合同，覆盖平台自动化、主库同步、飞书发布和 campaign 恢复。
- 已压缩 BOSS-Maimai、JD delivery、Liepin 和 public-search workflow；安全门禁由架构测试锁定。
- 验证：`tests/test_agent_architecture.py`、全量 `tests` 和 `git diff --check` 均通过。
```

- [ ] **Step 2: Archive full record**

Append a compact full record to `tasks/archive/2026-06.md` with:

- 目标和边界。
- 新增/修改文件。
- 最终 line counts。
- RED and GREEN verification commands.
- Remaining risks.

- [ ] **Step 3: Compact todo**

Return `tasks/todo.md` to compact form: Active Task becomes `无。`; Recent Done keeps one concise summary for this task; Archive Index remains unchanged.

## Final Review Checklist

Before reporting implementation complete:

- [ ] No Python behavior changed.
- [ ] No platform request, Feishu publish, Campaign DB apply, or `data/talent.db` write was performed.
- [ ] Existing critical contract tests still pass.
- [ ] New policy tests prove reusable gates are present.
- [ ] Workflow line budgets pass.
- [ ] `git diff --check` passes.
- [ ] Full `.venv/bin/python -m pytest tests -q` passes.
