# BOSS-Maimai Cross-Channel Delivery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a canonical BOSS -> Maimai cross-channel delivery flow that turns BOSS-selected candidates into Maimai-matched, multi-source Campaign DB records, syncs clean campaigns into `data/talent.db` under one explicit authorization, and hands off to JD delivery/Feishu.

**Architecture:** Keep BOSS sourcing, Maimai unattended search/detail, TalentDB sync, and JD delivery as separate capabilities. Add one cross-channel workflow that extracts BOSS targets, runs high-precision Maimai identity matching, imports BOSS-primary/Maimai-supplement records into Campaign DB, then gates bundle sync and delivery handoff. Extend `TalentDB` with source-profile-compatible identity and field-value audit tables so future platforms can plug into the same merge model.

**Tech Stack:** Python standard library, SQLite through `scripts/talent_db.py`, JSON/JSONL campaign artifacts, existing `scripts/talent_sync.py` bundle import/export, existing Maimai and JD delivery workflows, pytest.

---

## File Structure

- Create `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
  - Business entry contract for the new cross-channel flow.
  - States the one-time authorization boundary for main DB sync after Campaign DB gates pass.
  - Points to `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`.

- Create `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
  - Canonical runtime-neutral workflow for BOSS target extraction, Maimai matching, Campaign DB import, main DB sync, and JD delivery handoff.
  - Reuses `maimai-unattended-campaign` for live platform work and `jd-talent-delivery` for final delivery.

- Create `.claude/skills/boss-maimai-cross-channel-delivery/SKILL.md`
  - Claude adapter only. It must not contain business rules beyond mapping capabilities to the canonical skill/workflow.

- Modify `tests/test_agent_architecture.py`
  - Add the new workflow, skill, and adapter to architecture coverage.
  - Assert the high-precision matching and main DB authorization gates are present.

- Modify `scripts/talent_models.py`
  - Add `CandidateIdentityMatch` and `CandidateFieldValue` dataclasses.

- Modify `scripts/talent_db.py`
  - Add `candidate_identity_matches` and `candidate_field_values`.
  - Add public methods `record_identity_match`, `identity_matches`, `record_field_value`, `field_values`, and `merge_candidate_source`.
  - Include audit tables in sync export/import.

- Modify `scripts/talent_sync.py`
  - Include audit table names in `_SYNC_TABLES` so bundle manifests expose multi-channel audit counts.

- Create `tests/test_cross_channel_identity.py`
  - Unit tests for query order, scoring, fallback behavior, auto-bound thresholds, and pending confirmation.

- Create `scripts/cross_channel_identity.py`
  - Dataclasses and pure functions for BOSS target query planning, Maimai hit normalization, scoring, and identity decisions.

- Create `tests/test_boss_maimai_targets.py`
  - Unit tests for extracting BOSS contact/would-contact candidates into match targets.

- Create `scripts/boss_maimai_targets.py`
  - Reads BOSS campaign artifacts and writes `structured/maimai-match-targets.jsonl` plus a summary report.

- Create `tests/test_cross_channel_import.py`
  - Unit tests for BOSS-primary/Maimai-supplement import into Campaign DB and audit rows.

- Create `scripts/cross_channel_import.py`
  - Imports bound cross-channel candidates into Campaign DB; blocks pending/ambiguous identity matches.

- Modify `tests/test_jd_talent_delivery_match.py`
  - Add coverage for preferring Maimai profile URLs over other platform URLs.

- Modify `scripts/jd_talent_delivery_match.py`
  - Prefer openable Maimai profile URLs in `_source_url`.

- Create `tests/test_campaign_to_delivery.py`
  - Unit tests for Campaign DB gates, bundle dry-run/apply orchestration, and delivery handoff manifest.

- Create `scripts/campaign_to_delivery.py`
  - Validates Campaign DB, exports/verifies sync bundle, dry-runs main DB import, applies under authorization, and writes `state/jd-delivery-handoff.json`.

- Modify `docs/dev/script-inventory.md`
  - Register the new scripts and their side-effect boundaries.

- Modify `tasks/todo.md`
  - Track this implementation plan, progress, verification, and final review.

---

### Task 1: Add Cross-Channel Agent Contracts

**Files:**
- Create: `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- Create: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- Create: `.claude/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Write failing architecture tests**

Add the new entries to the existing maps in `tests/test_agent_architecture.py`:

```python
WORKFLOWS = [
    "public-search",
    "platform-match",
    "screen",
    "report",
    "talent-library",
    "wechat-chat-sync",
    "jd-talent-delivery",
    "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing",
    "boss-maimai-cross-channel-delivery",
    "liepin-unattended-campaign",
]

CANONICAL_SKILL_WORKFLOWS = {
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
    "boss-maimai-cross-channel-delivery": "boss-maimai-cross-channel-delivery",
    "liepin-talent-search-campaign": "liepin-unattended-campaign",
}

CLAUDE_ADAPTER_WORKFLOWS = {
    "public-search": "public-search",
    "platform-match": "platform-match",
    "screen": "screen",
    "report": "report",
    "talent-library": "talent-library",
    "wechat-chat-sync": "wechat-chat-sync",
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
    "boss-maimai-cross-channel-delivery": "boss-maimai-cross-channel-delivery",
    "liepin-talent-search-campaign": "liepin-unattended-campaign",
}
```

Append this test near the existing BOSS contract tests:

```python
def test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-maimai-cross-channel-delivery"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    for text in (skill, workflow):
        assert "BOSS 为 primary" in text
        assert "脉脉为 supplement" in text
        assert "`structured/maimai-match-targets.jsonl`" in text
        assert "`state/cross-channel-identity-ledger.jsonl`" in text
        assert "`reports/main-db-sync-dry-run.json`" in text
        assert "`data/talent.db`" in text
        assert "一次总授权" in text
        assert "Campaign DB clean" in text
        assert "jd-talent-delivery" in text

    identity_section = markdown_section(workflow, "S3 身份匹配判定")
    assert "`name_company_title`" in identity_section
    assert "`name_company_fallback`" in identity_section
    assert ">=95" in identity_section
    assert "不得自动绑定" in identity_section
    assert "`pending_confirmation`" in identity_section

    sync_section = markdown_section(workflow, "S9 主库 sync dry-run 与 apply")
    assert "`talent_sync.py export`" in sync_section
    assert "`verify-bundle`" in sync_section
    assert "`talent_sync.py import`" in sync_section
    assert "`CONFIRM_SYNC_TEXT`" in sync_section
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_canonical_workflow_files_exist tests/test_agent_architecture.py::test_runtime_neutral_skill_contracts_live_under_agents tests/test_agent_architecture.py::test_claude_skill_files_are_adapters_to_canonical_workflows tests/test_agent_architecture.py::test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates -q
```

Expected: failure mentioning missing `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md` or missing adapter/skill files.

- [ ] **Step 3: Create canonical skill**

Create `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`:

```markdown
---
name: boss-maimai-cross-channel-delivery
description: "BOSS App 已筛优质人选补脉脉主页匹配、多渠道 Campaign DB 整合、主库同步和 JD/飞书交付。"
---

# boss-maimai-cross-channel-delivery

## 目标

把 BOSS App 推荐寻访中已经筛出的 `contact` / `would_contact` 优质人选，整理成脉脉寻访清单，在脉脉搜索页匹配同一候选人，抓取脉脉主页信息，并以 BOSS 为 primary、脉脉为 supplement 写入 Campaign DB。Campaign DB clean 后，在用户一次总授权覆盖下自动同步到 `data/talent.db`，再交接 `jd-talent-delivery` 生成交付产物并推送飞书。

## 触发入口

- 用户要求“BOSS 优质人选补脉脉”“把 BOSS 筛出的人去脉脉匹配”“BOSS -> 脉脉 -> 主库 -> 飞书交付”时使用本 Skill。
- 如果只是从 JD 冷启动搜索脉脉，使用 `maimai-talent-search-campaign`。
- 如果只是执行 BOSS 推荐列表筛选，使用 `boss-app-recommendation-sourcing`。

## 输入

- `boss_campaign_root`：包含 BOSS campaign 产物的目录。
- `campaign_db_path`：默认 `data/campaigns/<campaign_id>/talent.db`。
- `main_db_path`：默认 `data/talent.db`。
- `allow_main_db_write_after_clean_campaign`：必须由用户明确授权；本流程只接受 campaign 级一次总授权。
- `delivery_jd_input`、`top_n`、`publish_feishu`、`notify_chat_id`：交给 `jd-talent-delivery` 使用。

## 输出产物

- `structured/maimai-match-targets.jsonl`
- `structured/cross-channel-bound-candidates.jsonl`
- `state/cross-channel-identity-ledger.jsonl`
- `state/main-db-sync-ledger.jsonl`
- `state/jd-delivery-handoff.json`
- `reports/maimai-match-summary.json`
- `reports/maimai-match-summary.md`
- `reports/cross-channel-import-dry-run.json`
- `reports/campaign-db-quality-gates.json`
- `reports/main-db-sync-dry-run.json`
- `reports/main-db-sync-result.json`

## Merge 边界

BOSS 为 primary，脉脉为 supplement。BOSS 已有的 `name`、`current_company`、`current_title`、`city`、`work_years`、`education` 不被脉脉覆盖。脉脉只补 `profile_url`、`platform_id`、BOSS 缺失字段、活跃状态和经历并集。同字段冲突必须写 `candidate_field_values`，身份匹配过程必须写 `candidate_identity_matches`。

## 脉脉匹配规则

查询顺序必须从高精准到宽召回：

1. `name_company_title`
2. `name_company_title_core`
3. `name_recent_company_title`
4. `name_school_title_core`
5. `name_company_fallback`

只有前 4 级 query 且 identity score `>=95` 才允许 `auto_bound`。`name_company_fallback`、结果过多、第一二名分差过小或 score `70-94` 必须进入 `pending_confirmation`，不得自动绑定。

## 主库写入授权

用户已确认：Campaign DB 干净后，可以基于一次总授权自动写入 `data/talent.db` 并继续生成飞书交付。写入前必须通过 Campaign DB gate、bundle verify、主库 import dry-run 和无 open conflict gate。失败时停止并写 `state/continuation-plan.json`。

## 自动交接

解析输入后读取并执行 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。本 Skill 不保存真实执行逻辑。
```

- [ ] **Step 4: Create canonical workflow**

Create `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`:

```markdown
---
name: boss-maimai-cross-channel-delivery
description: BOSS 优质人选补脉脉匹配、多渠道 Campaign DB 整合、主库同步和 JD/飞书交付 workflow。
---

# boss-maimai-cross-channel-delivery 工作流

## 触发入口

- 从 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md` 完成业务入口解析后自动交接。
- 用户要求继续 BOSS->脉脉跨渠道 campaign、恢复中断、执行主库同步或生成交付时，读取本 workflow 并从 `state/continuation-plan.json` 恢复。

## 安全边界

- 不绕过 BOSS 或脉脉登录、验证码、权限、风控、安全页、429、432 或非 JSON 响应。
- 不读取 cookie、localStorage、sessionStorage、Chrome profile 或浏览器 session store。
- BOSS 为 primary，脉脉为 supplement；脉脉字段不得静默覆盖 BOSS 非空字段。
- Campaign DB clean 之前不得写 `data/talent.db`。
- 主库写入只能在 `allow_main_db_write_after_clean_campaign=true` 且一次总授权已记录时执行。
- 飞书交付复用 `jd-talent-delivery` 的 dry-run、发布、回读和 IM 通知门禁。

## 阶段

### S0 预检

读取 `boss_campaign_root`、`campaign_db_path`、`main_db_path`、JD 交付输入和授权参数。确认 BOSS campaign 有 `structured/candidates.jsonl` 和 `structured/contact-decisions.jsonl`。确认 `maimai-unattended-campaign` 和 `jd-talent-delivery` canonical workflow 可读。

### S1 BOSS 优质人选 target 生成

运行：

```bash
.venv/bin/python -m scripts.boss_maimai_targets export --campaign-root data/campaigns/<campaign_id>
```

输出 `structured/maimai-match-targets.jsonl`。缺真实姓名的人选写入 `reports/maimai-match-summary.json` 的 `missing_real_name`，不得进入自动匹配。

### S2 脉脉搜索执行

读取 `structured/maimai-match-targets.jsonl`。每个 target 按 query plan 顺序搜索脉脉，真实平台执行复用 `agents/workflows/maimai-unattended-campaign/AGENT.md` 的登录、验证码、429、432、安全页、raw 落盘和 continuation plan 规则。raw 搜索结果写 `raw/maimai-match-search/<target_id>/query-*.json`。

### S3 身份匹配判定

对 raw 搜索结果运行 identity scoring。query level 顺序为 `name_company_title`、`name_company_title_core`、`name_recent_company_title`、`name_school_title_core`、`name_company_fallback`。只有前 4 级 query 且 score `>=95` 可写 `auto_bound`。`name_company_fallback` 命中、结果过多、第一二名分差小或 score `70-94` 必须写 `pending_confirmation`，不得自动绑定。

判定结果写：

- `state/cross-channel-identity-ledger.jsonl`
- `structured/cross-channel-bound-candidates.jsonl`
- `reports/maimai-match-summary.json`
- `reports/maimai-match-summary.md`

### S4 人工确认门禁

如果存在 `pending_confirmation`、`missing_real_name` 或 `not_found` 且策略要求全员完成，停止并写 `state/continuation-plan.json`。人工确认后的绑定必须以 `confirmed_bound` 回写 ledger。

### S5 Campaign DB import dry-run

运行：

```bash
.venv/bin/python -m scripts.cross_channel_import import --campaign-root data/campaigns/<campaign_id> --db data/campaigns/<campaign_id>/talent.db --dry-run
```

dry-run 必须报告 BOSS source、Maimai source、identity audit、field audit、created、merged、blocked 和 errors。dry-run 有 blocker 时停止。

### S6 Campaign DB import apply

dry-run clean 后运行 apply。写入 Campaign DB 时先写 BOSS primary candidate，再对同一 candidate 写 maimai source 和 supplement。所有身份决策写 `candidate_identity_matches`，所有字段 merge 决策写 `candidate_field_values`。

### S7 脉脉详情补抓

对已有 maimai `platform_id` 的绑定候选人生成 detail target。详情执行和导入复用现有脉脉 detail 能力；`maimai_detail_import` 通过 `source_profiles(platform='maimai', platform_id=...)` 精确匹配 Campaign DB candidate。

### S8 Campaign DB quality gates

运行：

```bash
.venv/bin/python -m scripts.campaign_to_delivery validate-campaign --campaign-root data/campaigns/<campaign_id> --db data/campaigns/<campaign_id>/talent.db
```

必须满足 `PRAGMA integrity_check=ok`、无 pending identity、无 pending merge、无 open sync conflict、source/audit 数量符合 bound candidates。

### S9 主库 sync dry-run 与 apply

使用标准 sync bundle，不复制 SQLite：

```bash
.venv/bin/python -m scripts.talent_sync export --db data/campaigns/<campaign_id>/talent.db --out data/campaigns/<campaign_id>/sync/campaign-to-main.zip
.venv/bin/python -m scripts.talent_sync verify-bundle --bundle data/campaigns/<campaign_id>/sync/campaign-to-main.zip
.venv/bin/python -m scripts.talent_sync import --db data/talent.db --bundle data/campaigns/<campaign_id>/sync/campaign-to-main.zip
.venv/bin/python -m scripts.talent_sync import --db data/talent.db --bundle data/campaigns/<campaign_id>/sync/campaign-to-main.zip --apply --confirm CONFIRM_SYNC_TEXT
```

实际实现通过 `scripts.campaign_to_delivery sync-main` 调用 `talent_sync.export_bundle`、`verify_bundle` 和 `import_bundle`。只有 dry-run clean、`allow_main_db_write_after_clean_campaign=true` 和 `confirm=CONFIRM_SYNC_TEXT` 同时成立时才 apply。结果写 `reports/main-db-sync-dry-run.json`、`reports/main-db-sync-result.json` 和 `state/main-db-sync-ledger.jsonl`。

### S10 JD delivery / 飞书交付

主库验证通过后写 `state/jd-delivery-handoff.json`，再读取 `agents/skills/jd-talent-delivery/SKILL.md` 和 `agents/workflows/jd-talent-delivery/AGENT.md` 连续推进。交付 URL 必须优先使用脉脉 `profile_url`。

## 停机条件

- 脉脉登录失效、验证码、安全页、403、429、432、非 JSON、HTML、partial capture。
- BOSS target 缺真实姓名。
- identity match 进入 `pending_confirmation`。
- `name_company_fallback` 命中但未人工确认。
- Campaign DB dry-run 或 apply 有 blocker。
- sync bundle verify 失败。
- 主库 import dry-run 有 conflict、pending 或 errors。
- 主库 apply 后验证不一致。
- `jd-talent-delivery` quality gate blocked。
- 飞书 dry-run、真实发布、回读或 IM 通知失败。

## 验收

- 自动绑定只发生在高精准 query + score `>=95`。
- `name_company_fallback` 不会自动写绑定。
- Campaign DB 同时保存 BOSS source、Maimai source、identity audit 和 field audit。
- Campaign DB clean 后可以在一次总授权下自动 sync 主库。
- 主库写入后，JD delivery 外联表优先输出脉脉主页链接。
```

- [ ] **Step 5: Create Claude adapter**

Create `.claude/skills/boss-maimai-cross-channel-delivery/SKILL.md`:

```markdown
---
name: boss-maimai-cross-channel-delivery
description: "BOSS App 已筛优质人选补脉脉主页匹配、多渠道 Campaign DB 整合、主库同步和 JD/飞书交付。"
---

# Claude Code Adapter: boss-maimai-cross-channel-delivery

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`；canonical workflow 位于 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`。
3. Read `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `computer.operate` -> Computer Use
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical workflow 执行；主库写入只在一次总授权和 Campaign DB clean gate 成立后执行。
6. 本文件不保存业务流程、规则或脚本。
```

- [ ] **Step 6: Run architecture tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: all tests in `tests/test_agent_architecture.py` pass.

- [ ] **Step 7: Commit agent contract changes**

Run:

```bash
git add agents/skills/boss-maimai-cross-channel-delivery/SKILL.md agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md .claude/skills/boss-maimai-cross-channel-delivery/SKILL.md tests/test_agent_architecture.py
git commit -m "Add BOSS-Maimai cross-channel workflow contract"
```

Expected: commit succeeds and contains only the files listed in `git add`.

---

### Task 2: Extend TalentDB For Multi-Channel Audit

**Files:**
- Modify: `scripts/talent_models.py`
- Modify: `scripts/talent_db.py`
- Modify: `scripts/talent_sync.py`
- Modify: `tests/test_talent_db.py`
- Modify: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing TalentDB audit model tests**

Append to `tests/test_talent_db.py`:

```python
def test_cross_channel_audit_tables_and_methods(db_with_candidate: tuple[TalentDB, int]) -> None:
    db, candidate_id = db_with_candidate

    match_id = db.record_identity_match(
        {
            "candidate_id": candidate_id,
            "source_platform": "boss_app",
            "source_candidate_key": "boss-app:abc",
            "target_platform": "maimai",
            "target_platform_id": "mm-001",
            "target_profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            "query_text": "陶壮 华为 大模型",
            "query_level": "name_company_title",
            "confidence": 98,
            "score_breakdown": {"name": 30, "company": 25, "title": 25, "gap": 18},
            "match_status": "auto_bound",
            "decision_reason": "姓名、公司、职位均命中",
        }
    )
    field_id = db.record_field_value(
        {
            "candidate_id": candidate_id,
            "field_name": "current_company",
            "platform": "maimai",
            "field_value": "华为云计算技术有限公司",
            "confidence": 82,
            "merge_decision": "conflict_recorded",
            "decision_reason": "BOSS primary 已有华为技术有限公司",
        }
    )

    matches = db.identity_matches(candidate_id)
    fields = db.field_values(candidate_id)

    assert match_id > 0
    assert field_id > 0
    assert matches[0].candidate_id == candidate_id
    assert matches[0].target_platform == "maimai"
    assert matches[0].confidence == 98
    assert matches[0].score_breakdown["title"] == 25
    assert fields[0].field_name == "current_company"
    assert fields[0].merge_decision == "conflict_recorded"
    assert fields[0].field_value == "华为云计算技术有限公司"


def test_merge_candidate_source_keeps_existing_primary_fields(db: TalentDB) -> None:
    candidate_id = db.ingest(
        {
            "name": "陶壮",
            "current_company": "华为技术有限公司",
            "current_title": "大模型推理工程师",
            "city": "上海",
            "platform_id": "boss-001",
            "profile_url": "boss://candidate/boss-001",
        },
        platform="boss_app",
    )

    db.merge_candidate_source(
        candidate_id,
        {
            "name": "陶壮",
            "current_company": "华为云计算技术有限公司",
            "current_title": "AI Infra 研发",
            "hunting_status": "在看机会",
            "platform_id": "mm-001",
            "profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            "skill_tags": ["推理加速"],
        },
        platform="maimai",
    )

    candidate = db.get(candidate_id)
    sources = db.get_sources(candidate_id)

    assert candidate is not None
    assert candidate.current_company == "华为技术有限公司"
    assert candidate.current_title == "大模型推理工程师"
    assert candidate.hunting_status == "在看机会"
    assert sorted(source.platform for source in sources) == ["boss_app", "maimai"]
    assert any(source.platform_id == "mm-001" for source in sources)
```

- [ ] **Step 2: Write failing sync bundle audit test**

Append to `tests/test_talent_sync.py`:

```python
def test_sync_bundle_round_trips_cross_channel_audit_tables(tmp_path: Path) -> None:
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "cross-channel.zip"

    source = TalentDB(source_db)
    try:
        candidate_id = source.ingest(
            {
                "name": "陶壮",
                "current_company": "华为技术有限公司",
                "current_title": "大模型推理工程师",
                "platform_id": "boss-001",
            },
            platform="boss_app",
        )
        source.merge_candidate_source(
            candidate_id,
            {
                "name": "陶壮",
                "platform_id": "mm-001",
                "profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            },
            platform="maimai",
        )
        source.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:abc",
                "target_platform": "maimai",
                "target_platform_id": "mm-001",
                "target_profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
                "query_text": "陶壮 华为 大模型",
                "query_level": "name_company_title",
                "confidence": 98,
                "score_breakdown": {"total": 98},
                "match_status": "auto_bound",
                "decision_reason": "高精度匹配",
            }
        )
        source.record_field_value(
            {
                "candidate_id": candidate_id,
                "field_name": "profile_url",
                "platform": "maimai",
                "field_value": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
                "confidence": 95,
                "merge_decision": "supplement_added",
                "decision_reason": "补充脉脉主页",
            }
        )
    finally:
        source.close()

    export_summary = export_bundle(source_db, bundle_path, mode="full")
    assert export_summary["tables"]["candidate_identity_matches"] == 1
    assert export_summary["tables"]["candidate_field_values"] == 1

    plan = import_bundle(bundle_path, target_db, apply=False)
    assert plan["incoming"]["candidate_identity_matches"] == 1
    assert plan["incoming"]["candidate_field_values"] == 1

    result = import_bundle(bundle_path, target_db, apply=True, confirm=CONFIRM_SYNC_TEXT)
    assert result["created"]["candidate_identity_matches"] == 1
    assert result["created"]["candidate_field_values"] == 1

    target = TalentDB(target_db)
    try:
        candidates = target.search()
        assert len(candidates) == 1
        matches = target.identity_matches(candidates[0].id)
        fields = target.field_values(candidates[0].id)
    finally:
        target.close()

    assert matches[0].target_platform_id == "mm-001"
    assert fields[0].merge_decision == "supplement_added"
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_db.py::test_cross_channel_audit_tables_and_methods tests/test_talent_db.py::test_merge_candidate_source_keeps_existing_primary_fields tests/test_talent_sync.py::test_sync_bundle_round_trips_cross_channel_audit_tables -q
```

Expected: failures for missing `record_identity_match`, `CandidateIdentityMatch`, or missing sync table counts.

- [ ] **Step 4: Add audit dataclasses**

Append to `scripts/talent_models.py`:

```python
@dataclass(frozen=True)
class CandidateIdentityMatch:
    id: int
    candidate_id: int | None
    source_platform: str
    source_candidate_key: str
    target_platform: str
    target_platform_id: str | None = None
    target_profile_url: str | None = None
    query_text: str = ""
    query_level: str = ""
    confidence: float = 0.0
    score_breakdown: dict[str, Any] = field(default_factory=dict)
    match_status: str = ""
    decision_reason: str | None = None
    confirmed_by: str | None = None
    confirmed_at: str | None = None
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class CandidateFieldValue:
    id: int
    candidate_id: int
    field_name: str
    platform: str
    source_profile_id: int | None = None
    field_value: Any = None
    confidence: float = 0.0
    merge_decision: str = ""
    decision_reason: str | None = None
    created_at: str = ""
```

Update the import list in `tests/test_talent_db.py` if needed:

```python
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFieldValue,
    CandidateFilter,
    CandidateIdentityMatch,
    MatchScore,
    SortSpec,
    SourceProfile,
    WechatTimeline,
)
```

- [ ] **Step 5: Add TalentDB schema and methods**

Modify `scripts/talent_db.py`:

1. Import the new models:

```python
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFieldValue,
    CandidateFilter,
    CandidateIdentityMatch,
    IngestResult,
    MatchScore,
    ScoreEvent,
    SortSpec,
    SourceProfile,
    WechatTimeline,
)
```

2. Add table names to `_SYNC_IMPORT_TABLES` after `source_profiles`:

```python
_SYNC_IMPORT_TABLES = (
    "candidates",
    "candidate_details",
    "source_profiles",
    "candidate_identity_matches",
    "candidate_field_values",
    "candidate_wechat_timelines",
    "score_events",
    "match_scores",
    "tombstones",
)
```

3. Add schema in `_init_schema` after `source_profiles`:

```python
self._conn.executescript(
    """
    CREATE TABLE IF NOT EXISTS candidate_identity_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER,
        source_platform TEXT NOT NULL,
        source_candidate_key TEXT NOT NULL,
        target_platform TEXT NOT NULL,
        target_platform_id TEXT,
        target_profile_url TEXT,
        query_text TEXT NOT NULL,
        query_level TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0,
        score_breakdown TEXT NOT NULL DEFAULT '{}',
        match_status TEXT NOT NULL,
        decision_reason TEXT,
        confirmed_by TEXT,
        confirmed_at TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        updated_at TEXT DEFAULT (datetime('now')),
        sync_id TEXT,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id)
    );

    CREATE TABLE IF NOT EXISTS candidate_field_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        candidate_id INTEGER NOT NULL,
        field_name TEXT NOT NULL,
        platform TEXT NOT NULL,
        source_profile_id INTEGER,
        field_value TEXT NOT NULL,
        confidence REAL NOT NULL DEFAULT 0,
        merge_decision TEXT NOT NULL,
        decision_reason TEXT,
        created_at TEXT DEFAULT (datetime('now')),
        sync_id TEXT,
        FOREIGN KEY(candidate_id) REFERENCES candidates(id),
        FOREIGN KEY(source_profile_id) REFERENCES source_profiles(id)
    );
    CREATE INDEX IF NOT EXISTS idx_identity_matches_candidate ON candidate_identity_matches(candidate_id);
    CREATE INDEX IF NOT EXISTS idx_identity_matches_source ON candidate_identity_matches(source_platform, source_candidate_key);
    CREATE INDEX IF NOT EXISTS idx_identity_matches_target ON candidate_identity_matches(target_platform, target_platform_id);
    CREATE INDEX IF NOT EXISTS idx_field_values_candidate ON candidate_field_values(candidate_id);
    CREATE INDEX IF NOT EXISTS idx_field_values_field ON candidate_field_values(field_name, platform);
    """
)
```

4. Add sync id column support in `_migrate_schema`:

```python
self._ensure_columns("candidate_identity_matches", {"sync_id": "TEXT"})
self._ensure_columns("candidate_field_values", {"sync_id": "TEXT"})
```

5. Add sync id backfill entries:

```python
for table, id_column, prefix in (
    ("source_profiles", "id", "source_profile"),
    ("candidate_identity_matches", "id", "identity_match"),
    ("candidate_field_values", "id", "field_value"),
    ("candidate_wechat_timelines", "id", "wechat_timeline"),
    ("score_events", "id", "score_event"),
    ("match_scores", "id", "match_score"),
):
    ...
```

6. Add public methods after `get_sources`:

```python
    def merge_candidate_source(
        self, candidate_id: int, data: dict[str, Any], platform: str
    ) -> None:
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        with self._conn:
            self._merge_candidate(candidate_id, data, platform)

    def record_identity_match(self, data: dict[str, Any]) -> int:
        required = (
            "source_platform",
            "source_candidate_key",
            "target_platform",
            "query_text",
            "query_level",
            "match_status",
        )
        for field in required:
            if not str(data.get(field) or "").strip():
                raise ValueError(f"{field} is required")
        candidate_id = data.get("candidate_id")
        if candidate_id is not None and not self._candidate_exists(int(candidate_id)):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO candidate_identity_matches (
                    candidate_id, source_platform, source_candidate_key,
                    target_platform, target_platform_id, target_profile_url,
                    query_text, query_level, confidence, score_breakdown,
                    match_status, decision_reason, confirmed_by, confirmed_at,
                    sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    str(data["source_platform"]),
                    str(data["source_candidate_key"]),
                    str(data["target_platform"]),
                    data.get("target_platform_id"),
                    data.get("target_profile_url"),
                    str(data["query_text"]),
                    str(data["query_level"]),
                    float(data.get("confidence") or 0),
                    _json_dumps(data.get("score_breakdown") or {}),
                    str(data["match_status"]),
                    data.get("decision_reason"),
                    data.get("confirmed_by"),
                    data.get("confirmed_at"),
                    self._new_sync_id("identity_match"),
                ),
            )
            return int(cursor.lastrowid)

    def identity_matches(self, candidate_id: int | None = None) -> list[CandidateIdentityMatch]:
        if candidate_id is None:
            rows = self._conn.execute(
                "SELECT * FROM candidate_identity_matches ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM candidate_identity_matches
                WHERE candidate_id = ?
                ORDER BY id
                """,
                (candidate_id,),
            ).fetchall()
        return [
            CandidateIdentityMatch(
                id=row["id"],
                candidate_id=row["candidate_id"],
                source_platform=row["source_platform"],
                source_candidate_key=row["source_candidate_key"],
                target_platform=row["target_platform"],
                target_platform_id=row["target_platform_id"],
                target_profile_url=row["target_profile_url"],
                query_text=row["query_text"],
                query_level=row["query_level"],
                confidence=float(row["confidence"] or 0),
                score_breakdown=_json_loads(row["score_breakdown"], {}, "candidate_identity_matches.score_breakdown"),
                match_status=row["match_status"],
                decision_reason=row["decision_reason"],
                confirmed_by=row["confirmed_by"],
                confirmed_at=row["confirmed_at"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    def record_field_value(self, data: dict[str, Any]) -> int:
        required = ("candidate_id", "field_name", "platform", "merge_decision")
        for field in required:
            if data.get(field) in (None, ""):
                raise ValueError(f"{field} is required")
        candidate_id = int(data["candidate_id"])
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO candidate_field_values (
                    candidate_id, field_name, platform, source_profile_id,
                    field_value, confidence, merge_decision, decision_reason,
                    sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    str(data["field_name"]),
                    str(data["platform"]),
                    data.get("source_profile_id"),
                    _json_dumps(data.get("field_value")),
                    float(data.get("confidence") or 0),
                    str(data["merge_decision"]),
                    data.get("decision_reason"),
                    self._new_sync_id("field_value"),
                ),
            )
            return int(cursor.lastrowid)

    def field_values(self, candidate_id: int | None = None) -> list[CandidateFieldValue]:
        if candidate_id is None:
            rows = self._conn.execute(
                "SELECT * FROM candidate_field_values ORDER BY id"
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT * FROM candidate_field_values
                WHERE candidate_id = ?
                ORDER BY id
                """,
                (candidate_id,),
            ).fetchall()
        return [
            CandidateFieldValue(
                id=row["id"],
                candidate_id=row["candidate_id"],
                field_name=row["field_name"],
                platform=row["platform"],
                source_profile_id=row["source_profile_id"],
                field_value=_json_loads(row["field_value"], None, "candidate_field_values.field_value"),
                confidence=float(row["confidence"] or 0),
                merge_decision=row["merge_decision"],
                decision_reason=row["decision_reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
```

- [ ] **Step 6: Add sync export/import for audit rows**

Modify `TalentDB.export_sync_rows` to include:

```python
            "candidate_identity_matches": self._export_identity_matches(),
            "candidate_field_values": self._export_field_values(),
```

Add export helpers:

```python
    def _export_identity_matches(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_identity_matches.sync_id,
                candidates.sync_id AS candidate_sync_id,
                candidate_identity_matches.source_platform,
                candidate_identity_matches.source_candidate_key,
                candidate_identity_matches.target_platform,
                candidate_identity_matches.target_platform_id,
                candidate_identity_matches.target_profile_url,
                candidate_identity_matches.query_text,
                candidate_identity_matches.query_level,
                candidate_identity_matches.confidence,
                candidate_identity_matches.score_breakdown,
                candidate_identity_matches.match_status,
                candidate_identity_matches.decision_reason,
                candidate_identity_matches.confirmed_by,
                candidate_identity_matches.confirmed_at,
                candidate_identity_matches.created_at,
                candidate_identity_matches.updated_at
            FROM candidate_identity_matches
            LEFT JOIN candidates ON candidates.id = candidate_identity_matches.candidate_id
            ORDER BY candidate_identity_matches.sync_id
            """
        ).fetchall()
        return [_export_row(row, json_fields={"score_breakdown": {}}) for row in rows]

    def _export_field_values(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_field_values.sync_id,
                candidates.sync_id AS candidate_sync_id,
                source_profiles.sync_id AS source_profile_sync_id,
                candidate_field_values.field_name,
                candidate_field_values.platform,
                candidate_field_values.field_value,
                candidate_field_values.confidence,
                candidate_field_values.merge_decision,
                candidate_field_values.decision_reason,
                candidate_field_values.created_at
            FROM candidate_field_values
            JOIN candidates ON candidates.id = candidate_field_values.candidate_id
            LEFT JOIN source_profiles ON source_profiles.id = candidate_field_values.source_profile_id
            ORDER BY candidate_field_values.sync_id
            """
        ).fetchall()
        return [_export_row(row, json_fields={"field_value": None}) for row in rows]
```

In `apply_sync_import`, import audit rows after `_import_sync_source_profiles`:

```python
            self._import_sync_identity_matches(
                table_rows.get("candidate_identity_matches", []),
                candidate_id_map,
                summary,
            )
            self._import_sync_field_values(
                table_rows.get("candidate_field_values", []),
                candidate_id_map,
                summary,
            )
```

Add import helpers:

```python
    def _import_sync_identity_matches(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            sync_id = row.get("sync_id")
            existed = self._sync_row_exists("candidate_identity_matches", sync_id)
            if existed:
                summary["skipped"]["candidate_identity_matches"] += 1
                continue
            candidate_sync_id = str(row.get("candidate_sync_id") or "")
            candidate_id = candidate_id_map.get(candidate_sync_id)
            self._conn.execute(
                """
                INSERT INTO candidate_identity_matches (
                    candidate_id, source_platform, source_candidate_key,
                    target_platform, target_platform_id, target_profile_url,
                    query_text, query_level, confidence, score_breakdown,
                    match_status, decision_reason, confirmed_by, confirmed_at,
                    created_at, updated_at, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row.get("source_platform"),
                    row.get("source_candidate_key"),
                    row.get("target_platform"),
                    row.get("target_platform_id"),
                    row.get("target_profile_url"),
                    row.get("query_text"),
                    row.get("query_level"),
                    row.get("confidence"),
                    _json_dumps(row.get("score_breakdown") or {}),
                    row.get("match_status"),
                    row.get("decision_reason"),
                    row.get("confirmed_by"),
                    row.get("confirmed_at"),
                    row.get("created_at"),
                    row.get("updated_at"),
                    sync_id,
                ),
            )
            summary["created"]["candidate_identity_matches"] += 1

    def _import_sync_field_values(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            sync_id = row.get("sync_id")
            existed = self._sync_row_exists("candidate_field_values", sync_id)
            if existed:
                summary["skipped"]["candidate_field_values"] += 1
                continue
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["candidate_field_values"] += 1
                continue
            self._conn.execute(
                """
                INSERT INTO candidate_field_values (
                    candidate_id, field_name, platform, source_profile_id,
                    field_value, confidence, merge_decision, decision_reason,
                    created_at, sync_id
                )
                VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row.get("field_name"),
                    row.get("platform"),
                    _json_dumps(row.get("field_value")),
                    row.get("confidence"),
                    row.get("merge_decision"),
                    row.get("decision_reason"),
                    row.get("created_at"),
                    sync_id,
                ),
            )
            summary["created"]["candidate_field_values"] += 1
```

Modify `scripts/talent_sync.py` `_SYNC_TABLES`:

```python
_SYNC_TABLES = (
    "candidates",
    "candidate_details",
    "source_profiles",
    "candidate_identity_matches",
    "candidate_field_values",
    "candidate_wechat_timelines",
    "score_events",
    "match_scores",
    "tombstones",
)
```

- [ ] **Step 7: Run audit tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_db.py::test_cross_channel_audit_tables_and_methods tests/test_talent_db.py::test_merge_candidate_source_keeps_existing_primary_fields tests/test_talent_sync.py::test_sync_bundle_round_trips_cross_channel_audit_tables -q
```

Expected: all three tests pass.

- [ ] **Step 8: Run broader DB/sync tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_db.py tests/test_talent_sync.py -q
```

Expected: all tests in both files pass.

- [ ] **Step 9: Commit TalentDB audit changes**

Run:

```bash
git add scripts/talent_models.py scripts/talent_db.py scripts/talent_sync.py tests/test_talent_db.py tests/test_talent_sync.py
git commit -m "Extend TalentDB cross-channel audit schema"
```

Expected: commit succeeds and contains only the files listed in `git add`.

---

### Task 3: Implement BOSS To Maimai Target Extraction

**Files:**
- Create: `scripts/boss_maimai_targets.py`
- Create: `tests/test_boss_maimai_targets.py`

- [ ] **Step 1: Write failing target extraction tests**

Create `tests/test_boss_maimai_targets.py`:

```python
import json
from pathlib import Path

import pytest

from scripts import boss_maimai_targets


def _append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def test_export_targets_selects_contact_and_would_contact_with_real_name(tmp_path: Path) -> None:
    root = tmp_path / "boss-campaign"
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:1",
            "display_name": "陶先生",
            "real_name": "陶壮",
            "real_name_source": "communication_page_after_external_executor",
            "current_company": "华为技术有限公司",
            "current_title": "大模型推理工程师",
            "city": "上海",
            "education": "硕士",
            "work_years": "8年",
            "recommendation": "contact",
            "score": 92,
            "detail": {
                "recent_companies": ["华为云"],
                "schools": ["上海交通大学"],
            },
        },
    )
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:2",
            "display_name": "李女士",
            "real_name": "李敏",
            "current_company": "字节跳动",
            "current_title": "推荐算法专家",
            "recommendation": "would_contact",
            "score": 88,
        },
    )
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:3",
            "display_name": "王先生",
            "real_name": "王强",
            "current_company": "普通公司",
            "current_title": "测试经理",
            "recommendation": "skip",
            "score": 20,
        },
    )

    result = boss_maimai_targets.export_targets(root)
    rows = boss_maimai_targets.load_jsonl(root / "structured/maimai-match-targets.jsonl")

    assert result["target_count"] == 2
    assert result["missing_real_name_count"] == 0
    assert [row["real_name"] for row in rows] == ["陶壮", "李敏"]
    assert rows[0]["schema"] == "boss_maimai_match_target_v1"
    assert rows[0]["target_id"] == "boss-app-1"
    assert rows[0]["query_plan"][0]["level"] == "name_company_title"
    assert rows[0]["query_plan"][-1]["level"] == "name_company_fallback"
    assert rows[0]["recent_companies"] == ["华为云"]
    assert rows[0]["schools"] == ["上海交通大学"]


def test_export_targets_blocks_missing_real_name(tmp_path: Path) -> None:
    root = tmp_path / "boss-campaign"
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:no-name",
            "display_name": "赵先生",
            "current_company": "腾讯",
            "current_title": "后台研发",
            "recommendation": "contact",
            "score": 91,
        },
    )

    result = boss_maimai_targets.export_targets(root)
    rows = boss_maimai_targets.load_jsonl(root / "structured/maimai-match-targets.jsonl")
    report = json.loads((root / "reports/maimai-match-summary.json").read_text(encoding="utf-8"))

    assert rows == []
    assert result["target_count"] == 0
    assert result["missing_real_name_count"] == 1
    assert report["missing_real_name"][0]["candidate_key"] == "boss-app:no-name"


def test_export_targets_rejects_missing_campaign_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="structured/candidates.jsonl"):
        boss_maimai_targets.export_targets(tmp_path / "missing")
```

- [ ] **Step 2: Run target tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py -q
```

Expected: import failure because `scripts/boss_maimai_targets.py` does not exist.

- [ ] **Step 3: Implement target extraction**

Create `scripts/boss_maimai_targets.py`:

```python
"""从 BOSS App campaign 生成脉脉匹配 target 清单。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.cross_channel_identity import build_query_plan

TARGET_SCHEMA = "boss_maimai_match_target_v1"
SELECTED_RECOMMENDATIONS = {"contact", "would_contact"}


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        raise FileNotFoundError(file)
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{file} line {line_number}: must be an object")
        rows.append(value)
    return rows


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "-", value).strip("-")
    return slug or "target"


def _list_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _detail_values(candidate: dict[str, Any], key: str) -> list[str]:
    detail = candidate.get("detail") if isinstance(candidate.get("detail"), dict) else {}
    return _list_value(detail.get(key))


def _target_from_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    target = {
        "schema": TARGET_SCHEMA,
        "target_id": _slug(str(candidate["candidate_key"])),
        "candidate_key": candidate["candidate_key"],
        "display_name": candidate.get("display_name") or "",
        "real_name": candidate.get("real_name") or "",
        "real_name_source": candidate.get("real_name_source") or "",
        "current_company": candidate.get("current_company") or "",
        "current_title": candidate.get("current_title") or "",
        "city": candidate.get("city") or "",
        "education": candidate.get("education") or "",
        "work_years": candidate.get("work_years") or "",
        "score": candidate.get("score"),
        "recommendation": candidate.get("recommendation"),
        "recent_companies": _detail_values(candidate, "recent_companies"),
        "schools": _detail_values(candidate, "schools"),
        "boss_payload": candidate,
    }
    target["query_plan"] = [query.to_dict() for query in build_query_plan(target)]
    return target


def export_targets(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates_path = root / "structured/candidates.jsonl"
    candidates = load_jsonl(candidates_path)
    selected = [
        item
        for item in candidates
        if str(item.get("recommendation") or "") in SELECTED_RECOMMENDATIONS
    ]

    targets: list[dict[str, Any]] = []
    missing_real_name: list[dict[str, Any]] = []
    for candidate in selected:
        if not str(candidate.get("real_name") or "").strip():
            missing_real_name.append(
                {
                    "candidate_key": candidate.get("candidate_key"),
                    "display_name": candidate.get("display_name") or "",
                    "current_company": candidate.get("current_company") or "",
                    "current_title": candidate.get("current_title") or "",
                    "reason": "missing_real_name",
                }
            )
            continue
        targets.append(_target_from_candidate(candidate))

    _write_jsonl(root / "structured/maimai-match-targets.jsonl", targets)
    summary = {
        "schema": "boss_maimai_match_targets_summary_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "selected_count": len(selected),
        "target_count": len(targets),
        "missing_real_name_count": len(missing_real_name),
        "missing_real_name": missing_real_name,
        "target_path": "structured/maimai-match-targets.jsonl",
    }
    _write_json(root / "reports/maimai-match-summary.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导出 BOSS -> 脉脉匹配 target")
    subparsers = parser.add_subparsers(dest="command", required=True)
    export = subparsers.add_parser("export")
    export.add_argument("--campaign-root", required=True)
    export.set_defaults(func=lambda args: export_targets(args.campaign_root))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run target extraction tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py -q
```

Expected: tests fail only if `scripts.cross_channel_identity.build_query_plan` is not implemented yet. If Task 4 has not run, commit Task 3 after Task 4 Step 4. If Task 4 is already implemented, all tests pass.

- [ ] **Step 5: Commit target extraction**

Run after Task 4 provides `cross_channel_identity.py`:

```bash
git add scripts/boss_maimai_targets.py tests/test_boss_maimai_targets.py
git commit -m "Export BOSS candidates for Maimai matching"
```

Expected: commit succeeds and contains only the target extraction script and test.

---

### Task 4: Implement Cross-Channel Identity Scoring

**Files:**
- Create: `scripts/cross_channel_identity.py`
- Create: `tests/test_cross_channel_identity.py`

- [ ] **Step 1: Write failing identity tests**

Create `tests/test_cross_channel_identity.py`:

```python
from scripts.cross_channel_identity import (
    BossMaimaiTarget,
    MaimaiSearchHit,
    build_query_plan,
    decide_match,
    score_hit,
)


def _target() -> BossMaimaiTarget:
    return BossMaimaiTarget(
        target_id="boss-app-1",
        candidate_key="boss-app:1",
        real_name="陶壮",
        current_company="华为技术有限公司",
        current_title="大模型推理工程师",
        city="上海",
        education="硕士",
        recent_companies=("华为云",),
        schools=("上海交通大学",),
    )


def test_build_query_plan_orders_high_precision_before_fallback() -> None:
    queries = build_query_plan(_target())

    assert [query.level for query in queries] == [
        "name_company_title",
        "name_company_title_core",
        "name_recent_company_title",
        "name_school_title_core",
        "name_company_fallback",
    ]
    assert queries[0].text == "陶壮 华为技术有限公司 大模型推理工程师"
    assert queries[-1].text == "陶壮 华为技术有限公司"
    assert queries[-1].allow_auto_bind is False


def test_high_precision_score_can_auto_bind() -> None:
    target = _target()
    hit = MaimaiSearchHit(
        platform_id="mm-001",
        name="陶壮",
        company="华为技术有限公司",
        title="大模型推理工程师",
        city="上海",
        education="硕士",
        profile_url="https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
    )

    decision = decide_match(target, [hit], query_level="name_company_title", query_text="陶壮 华为技术有限公司 大模型推理工程师")

    assert decision.match_status == "auto_bound"
    assert decision.confidence >= 95
    assert decision.target_platform_id == "mm-001"
    assert decision.score_breakdown["query_level"] == "name_company_title"


def test_name_company_fallback_never_auto_binds() -> None:
    target = _target()
    hit = MaimaiSearchHit(
        platform_id="mm-001",
        name="陶壮",
        company="华为技术有限公司",
        title="AI Infra",
        city="上海",
        profile_url="https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
    )

    decision = decide_match(target, [hit], query_level="name_company_fallback", query_text="陶壮 华为技术有限公司")

    assert decision.match_status == "pending_confirmation"
    assert decision.confidence >= 70
    assert "fallback" in decision.decision_reason


def test_many_results_or_close_second_place_goes_pending() -> None:
    target = _target()
    hits = [
        MaimaiSearchHit(platform_id="mm-001", name="陶壮", company="华为技术有限公司", title="大模型推理工程师", city="上海"),
        MaimaiSearchHit(platform_id="mm-002", name="陶壮", company="华为云", title="大模型工程师", city="上海"),
        MaimaiSearchHit(platform_id="mm-003", name="陶壮", company="荣耀", title="算法工程师", city="上海"),
        MaimaiSearchHit(platform_id="mm-004", name="陶壮", company="华为", title="后端工程师", city="深圳"),
    ]

    decision = decide_match(target, hits, query_level="name_company_title", query_text="陶壮 华为技术有限公司 大模型推理工程师")

    assert decision.match_status == "pending_confirmation"
    assert decision.score_breakdown["result_count"] == 4
    assert decision.score_breakdown["second_gap"] < 8


def test_low_score_is_not_found() -> None:
    target = _target()
    hit = MaimaiSearchHit(platform_id="mm-404", name="陶伟", company="腾讯", title="测试经理", city="北京")

    decision = decide_match(target, [hit], query_level="name_company_title", query_text="陶壮 华为技术有限公司 大模型推理工程师")

    assert decision.match_status == "not_found"
    assert decision.confidence < 70


def test_score_hit_exposes_dimension_breakdown() -> None:
    target = _target()
    hit = MaimaiSearchHit(platform_id="mm-001", name="陶壮", company="华为云", title="大模型推理", city="上海", education="硕士")

    score = score_hit(target, hit, query_level="name_recent_company_title", result_count=1, second_score=None)

    assert score.total >= 90
    assert score.breakdown["name"] == 30
    assert score.breakdown["company"] >= 20
    assert score.breakdown["title"] >= 20
    assert score.breakdown["city"] == 8
```

- [ ] **Step 2: Run identity tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py -q
```

Expected: import failure because `scripts/cross_channel_identity.py` does not exist.

- [ ] **Step 3: Implement identity scoring**

Create `scripts/cross_channel_identity.py`:

```python
"""BOSS target 与脉脉搜索结果的身份匹配评分。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any


HIGH_PRECISION_LEVELS = {
    "name_company_title",
    "name_company_title_core",
    "name_recent_company_title",
    "name_school_title_core",
}


@dataclass(frozen=True)
class QuerySpec:
    level: str
    text: str
    allow_auto_bind: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "text": self.text,
            "allow_auto_bind": self.allow_auto_bind,
        }


@dataclass(frozen=True)
class BossMaimaiTarget:
    target_id: str
    candidate_key: str
    real_name: str
    current_company: str = ""
    current_title: str = ""
    city: str = ""
    education: str = ""
    recent_companies: tuple[str, ...] = ()
    schools: tuple[str, ...] = ()
    boss_payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MaimaiSearchHit:
    platform_id: str
    name: str
    company: str = ""
    title: str = ""
    city: str = ""
    education: str = ""
    schools: tuple[str, ...] = ()
    work_companies: tuple[str, ...] = ()
    profile_url: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IdentityScore:
    total: int
    breakdown: dict[str, Any]


@dataclass(frozen=True)
class IdentityDecision:
    source_platform: str
    source_candidate_key: str
    target_platform: str
    target_platform_id: str | None
    target_profile_url: str
    query_text: str
    query_level: str
    confidence: int
    score_breakdown: dict[str, Any]
    match_status: str
    decision_reason: str
    hit: MaimaiSearchHit | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_platform": self.source_platform,
            "source_candidate_key": self.source_candidate_key,
            "target_platform": self.target_platform,
            "target_platform_id": self.target_platform_id,
            "target_profile_url": self.target_profile_url,
            "query_text": self.query_text,
            "query_level": self.query_level,
            "confidence": self.confidence,
            "score_breakdown": self.score_breakdown,
            "match_status": self.match_status,
            "decision_reason": self.decision_reason,
            "hit": self.hit.raw if self.hit else None,
        }


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _contains(haystack: str, needle: str) -> bool:
    haystack = _text(haystack)
    needle = _text(needle)
    if not haystack or not needle:
        return False
    if needle.isascii():
        return needle.casefold() in haystack.casefold()
    return needle in haystack or haystack in needle


def _title_core(title: str) -> str:
    words = [part for part in re.split(r"[-/·|\s]+", _text(title)) if part]
    for word in words:
        if any(key in word for key in ("大模型", "算法", "推荐", "推理", "AI", "Infra", "后端", "平台")):
            return word
    return words[0] if words else ""


def _target_from_mapping(value: dict[str, Any]) -> BossMaimaiTarget:
    return BossMaimaiTarget(
        target_id=str(value.get("target_id") or ""),
        candidate_key=str(value.get("candidate_key") or ""),
        real_name=str(value.get("real_name") or ""),
        current_company=str(value.get("current_company") or ""),
        current_title=str(value.get("current_title") or ""),
        city=str(value.get("city") or ""),
        education=str(value.get("education") or ""),
        recent_companies=tuple(str(item) for item in value.get("recent_companies") or [] if str(item)),
        schools=tuple(str(item) for item in value.get("schools") or [] if str(item)),
        boss_payload=dict(value.get("boss_payload") or {}),
    )


def build_query_plan(target: BossMaimaiTarget | dict[str, Any]) -> list[QuerySpec]:
    if isinstance(target, dict):
        target = _target_from_mapping(target)
    name = _text(target.real_name)
    company = _text(target.current_company)
    title = _text(target.current_title)
    title_core = _title_core(title)
    recent_company = _text(target.recent_companies[0] if target.recent_companies else "")
    school = _text(target.schools[0] if target.schools else target.education)
    queries = [
        QuerySpec("name_company_title", _text(f"{name} {company} {title}"), True),
        QuerySpec("name_company_title_core", _text(f"{name} {company} {title_core}"), True),
        QuerySpec("name_recent_company_title", _text(f"{name} {recent_company or company} {title_core or title}"), True),
        QuerySpec("name_school_title_core", _text(f"{name} {school} {title_core or title}"), True),
        QuerySpec("name_company_fallback", _text(f"{name} {company}"), False),
    ]
    seen: set[tuple[str, str]] = set()
    result: list[QuerySpec] = []
    for query in queries:
        key = (query.level, query.text)
        if query.text and key not in seen:
            result.append(query)
            seen.add(key)
    return result


def _company_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    companies = [target.current_company, *target.recent_companies]
    hit_text = " ".join([hit.company, *hit.work_companies])
    if any(_contains(hit_text, company) for company in companies if company):
        return 25
    if any(_contains(hit_text, company[:2]) for company in companies if len(company) >= 2):
        return 18
    return 0


def _title_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    target_title = target.current_title
    target_core = _title_core(target_title)
    if _contains(hit.title, target_title):
        return 25
    if target_core and _contains(hit.title, target_core):
        return 22
    return 0


def score_hit(
    target: BossMaimaiTarget,
    hit: MaimaiSearchHit,
    query_level: str,
    result_count: int,
    second_score: int | None,
) -> IdentityScore:
    breakdown = {
        "name": 30 if _text(target.real_name) == _text(hit.name) else 0,
        "company": _company_score(target, hit),
        "title": _title_score(target, hit),
        "city": 8 if target.city and _contains(hit.city, target.city) else 0,
        "education": 5 if target.education and _contains(hit.education, target.education) else 0,
        "school": 5 if any(_contains(" ".join(hit.schools), school) for school in target.schools) else 0,
        "query_level": query_level,
        "result_count": result_count,
    }
    total = int(sum(value for value in breakdown.values() if isinstance(value, int)))
    if result_count >= 4:
        total -= 5
        breakdown["result_count_penalty"] = -5
    if second_score is not None:
        breakdown["second_gap"] = total - second_score
    else:
        breakdown["second_gap"] = None
    return IdentityScore(max(0, min(100, total)), breakdown)


def decide_match(
    target: BossMaimaiTarget,
    hits: list[MaimaiSearchHit],
    query_level: str,
    query_text: str,
) -> IdentityDecision:
    if not hits:
        return IdentityDecision(
            source_platform="boss_app",
            source_candidate_key=target.candidate_key,
            target_platform="maimai",
            target_platform_id=None,
            target_profile_url="",
            query_text=query_text,
            query_level=query_level,
            confidence=0,
            score_breakdown={"query_level": query_level, "result_count": 0},
            match_status="not_found",
            decision_reason="脉脉搜索无结果",
            hit=None,
        )
    first_pass = [
        (hit, score_hit(target, hit, query_level, len(hits), None))
        for hit in hits
    ]
    ordered = sorted(first_pass, key=lambda item: item[1].total, reverse=True)
    best_hit, best_score = ordered[0]
    second_total = ordered[1][1].total if len(ordered) > 1 else None
    best_score = score_hit(target, best_hit, query_level, len(hits), second_total)
    gap = best_score.breakdown.get("second_gap")

    if best_score.total < 70:
        status = "not_found"
        reason = "最高分低于 70"
    elif query_level == "name_company_fallback":
        status = "pending_confirmation"
        reason = "fallback query 命中需要人工确认"
    elif len(hits) >= 4 or (isinstance(gap, int) and gap < 8):
        status = "pending_confirmation"
        reason = "结果过多或第一二名分差过小"
    elif query_level in HIGH_PRECISION_LEVELS and best_score.total >= 95:
        status = "auto_bound"
        reason = "高精准 query 且 identity score >=95"
    else:
        status = "pending_confirmation"
        reason = "identity score 需要人工确认"

    return IdentityDecision(
        source_platform="boss_app",
        source_candidate_key=target.candidate_key,
        target_platform="maimai",
        target_platform_id=best_hit.platform_id,
        target_profile_url=best_hit.profile_url,
        query_text=query_text,
        query_level=query_level,
        confidence=best_score.total,
        score_breakdown=best_score.breakdown,
        match_status=status,
        decision_reason=reason,
        hit=best_hit,
    )


def load_search_hits(path: str) -> list[MaimaiSearchHit]:
    data = json.loads(path)
    if not isinstance(data, list):
        raise ValueError("search hits must be a list")
    return [
        MaimaiSearchHit(
            platform_id=str(item.get("platform_id") or item.get("id") or ""),
            name=str(item.get("name") or ""),
            company=str(item.get("company") or item.get("current_company") or ""),
            title=str(item.get("title") or item.get("current_title") or ""),
            city=str(item.get("city") or ""),
            education=str(item.get("education") or ""),
            schools=tuple(str(school) for school in item.get("schools") or []),
            work_companies=tuple(str(company) for company in item.get("work_companies") or []),
            profile_url=str(item.get("profile_url") or item.get("url") or ""),
            raw=dict(item),
        )
        for item in data
        if isinstance(item, dict)
    ]
```

- [ ] **Step 4: Run identity tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py -q
```

Expected: all identity tests pass.

- [ ] **Step 5: Run target extraction tests again**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py tests/test_cross_channel_identity.py -q
```

Expected: both test files pass.

- [ ] **Step 6: Commit identity scoring**

Run:

```bash
git add scripts/cross_channel_identity.py tests/test_cross_channel_identity.py scripts/boss_maimai_targets.py tests/test_boss_maimai_targets.py
git commit -m "Score BOSS to Maimai identity matches"
```

Expected: commit succeeds. If Task 3 was already committed separately, stage only `scripts/cross_channel_identity.py` and `tests/test_cross_channel_identity.py`.

---

### Task 5: Import Bound Cross-Channel Candidates Into Campaign DB

**Files:**
- Create: `scripts/cross_channel_import.py`
- Create: `tests/test_cross_channel_import.py`

- [ ] **Step 1: Write failing import tests**

Create `tests/test_cross_channel_import.py`:

```python
import json
from pathlib import Path

import pytest

from scripts import cross_channel_import
from scripts.talent_db import TalentDB


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _bound_row(status: str = "auto_bound") -> dict:
    return {
        "schema": "boss_maimai_bound_candidate_v1",
        "target": {
            "target_id": "boss-app-1",
            "candidate_key": "boss-app:1",
            "real_name": "陶壮",
            "current_company": "华为技术有限公司",
            "current_title": "大模型推理工程师",
            "city": "上海",
            "education": "硕士",
            "work_years": "8年",
            "boss_payload": {
                "candidate_key": "boss-app:1",
                "real_name": "陶壮",
                "current_company": "华为技术有限公司",
                "current_title": "大模型推理工程师",
                "city": "上海",
                "education": "硕士",
                "work_years": 8,
                "skill_tags": ["推理加速"],
                "profile_url": "boss://candidate/boss-001",
            },
        },
        "decision": {
            "source_platform": "boss_app",
            "source_candidate_key": "boss-app:1",
            "target_platform": "maimai",
            "target_platform_id": "mm-001",
            "target_profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            "query_text": "陶壮 华为技术有限公司 大模型推理工程师",
            "query_level": "name_company_title",
            "confidence": 98,
            "score_breakdown": {"total": 98},
            "match_status": status,
            "decision_reason": "高精度匹配",
        },
        "maimai_hit": {
            "platform_id": "mm-001",
            "name": "陶壮",
            "company": "华为云计算技术有限公司",
            "title": "AI Infra 研发",
            "city": "上海",
            "profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            "hunting_status": "在看机会",
            "skill_tags": ["AI Infra"],
        },
    }


def test_import_bound_candidates_keeps_boss_primary_and_adds_maimai_source(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / "structured/cross-channel-bound-candidates.jsonl", [_bound_row()])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["created"] == 1
    assert result["blocked"] == []
    db = TalentDB(db_path)
    try:
        candidates = db.search()
        candidate = candidates[0]
        sources = db.get_sources(candidate.id)
        matches = db.identity_matches(candidate.id)
        fields = db.field_values(candidate.id)
    finally:
        db.close()

    assert candidate.name == "陶壮"
    assert candidate.current_company == "华为技术有限公司"
    assert candidate.current_title == "大模型推理工程师"
    assert candidate.hunting_status == "在看机会"
    assert sorted(source.platform for source in sources) == ["boss_app", "maimai"]
    assert any(source.platform_id == "mm-001" for source in sources)
    assert matches[0].match_status == "auto_bound"
    assert any(field.field_name == "current_company" and field.merge_decision == "primary_kept" for field in fields)
    assert any(field.field_name == "profile_url" and field.merge_decision == "supplement_added" for field in fields)


def test_import_bound_candidates_dry_run_does_not_create_db_rows(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / "structured/cross-channel-bound-candidates.jsonl", [_bound_row()])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=True)

    assert result["would_import"] == 1
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_import_bound_candidates_blocks_pending_confirmation(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / "structured/cross-channel-bound-candidates.jsonl", [_bound_row(status="pending_confirmation")])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["created"] == 0
    assert result["blocked"][0]["reason"] == "identity_not_confirmed"


def test_import_bound_candidates_rejects_missing_bound_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="cross-channel-bound-candidates.jsonl"):
        cross_channel_import.import_bound_candidates(tmp_path / "campaign", tmp_path / "campaign/talent.db")
```

- [ ] **Step 2: Run import tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_import.py -q
```

Expected: import failure because `scripts/cross_channel_import.py` does not exist.

- [ ] **Step 3: Implement cross-channel import**

Create `scripts/cross_channel_import.py`:

```python
"""把 BOSS primary + 脉脉 supplement 绑定结果写入 Campaign DB。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB

BOUND_FILE = "structured/cross-channel-bound-candidates.jsonl"
CONFIRMED_STATUSES = {"auto_bound", "confirmed_bound"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _boss_payload(row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target") if isinstance(row.get("target"), dict) else {}
    payload = dict(target.get("boss_payload") or {})
    payload.setdefault("name", target.get("real_name"))
    payload.setdefault("current_company", target.get("current_company"))
    payload.setdefault("current_title", target.get("current_title"))
    payload.setdefault("city", target.get("city"))
    payload.setdefault("education", target.get("education"))
    payload["platform_id"] = payload.get("platform_id") or target.get("candidate_key")
    payload["raw_profile"] = {
        "boss_app_detail_capture": payload,
        "cross_channel_target": target,
    }
    return payload


def _maimai_payload(row: dict[str, Any]) -> dict[str, Any]:
    hit = row.get("maimai_hit") if isinstance(row.get("maimai_hit"), dict) else {}
    decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
    return {
        "name": hit.get("name") or row.get("target", {}).get("real_name"),
        "current_company": hit.get("company"),
        "current_title": hit.get("title"),
        "city": hit.get("city"),
        "hunting_status": hit.get("hunting_status"),
        "skill_tags": hit.get("skill_tags") or [],
        "platform_id": decision.get("target_platform_id") or hit.get("platform_id"),
        "profile_url": decision.get("target_profile_url") or hit.get("profile_url"),
        "raw_profile": {
            "maimai_search_hit": hit,
            "cross_channel_identity_match": decision,
        },
    }


def _field_audit_rows(candidate_id: int, boss: dict[str, Any], maimai: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for field in ("name", "current_company", "current_title", "city", "education", "work_years", "hunting_status", "profile_url"):
        boss_value = boss.get(field)
        maimai_value = maimai.get(field)
        if maimai_value in (None, "", []):
            decision = "ignored_empty"
            value = maimai_value
        elif boss_value in (None, "", []):
            decision = "filled_empty" if field != "profile_url" else "supplement_added"
            value = maimai_value
        elif boss_value == maimai_value:
            decision = "primary_kept"
            value = maimai_value
        elif field == "profile_url":
            decision = "supplement_added"
            value = maimai_value
        else:
            decision = "primary_kept"
            value = maimai_value
        rows.append(
            {
                "candidate_id": candidate_id,
                "field_name": field,
                "platform": "maimai",
                "field_value": value,
                "confidence": 90 if decision != "ignored_empty" else 0,
                "merge_decision": decision,
                "decision_reason": "BOSS primary，脉脉补缺或记录来源",
            }
        )
    return rows


def _record_audits(db: TalentDB, candidate_id: int, row: dict[str, Any], boss: dict[str, Any], maimai: dict[str, Any]) -> None:
    decision = dict(row.get("decision") or {})
    decision["candidate_id"] = candidate_id
    db.record_identity_match(decision)
    for audit in _field_audit_rows(candidate_id, boss, maimai):
        db.record_field_value(audit)


def import_bound_candidates(campaign_root: str | Path, db_path: str | Path, dry_run: bool = False) -> dict[str, Any]:
    root = Path(campaign_root)
    rows = _load_jsonl(root / BOUND_FILE)
    result = {
        "schema": "cross_channel_import_result_v1",
        "dry_run": dry_run,
        "input_count": len(rows),
        "would_import": 0,
        "created": 0,
        "blocked": [],
        "errors": [],
    }

    confirmed_rows: list[dict[str, Any]] = []
    for row in rows:
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        if decision.get("match_status") not in CONFIRMED_STATUSES:
            result["blocked"].append(
                {
                    "candidate_key": row.get("target", {}).get("candidate_key"),
                    "reason": "identity_not_confirmed",
                    "match_status": decision.get("match_status"),
                }
            )
            continue
        confirmed_rows.append(row)
    result["would_import"] = len(confirmed_rows)
    if dry_run:
        _write_json(root / "reports/cross-channel-import-dry-run.json", result)
        TalentDB(db_path).close()
        return result
    if result["blocked"]:
        _write_json(root / "reports/cross-channel-import-result.json", result)
        return result

    db = TalentDB(db_path)
    try:
        for row in confirmed_rows:
            boss = _boss_payload(row)
            maimai = _maimai_payload(row)
            candidate_id = db.ingest(boss, platform="boss_app")
            db.merge_candidate_source(candidate_id, maimai, platform="maimai")
            _record_audits(db, candidate_id, row, boss, maimai)
            result["created"] += 1
    finally:
        db.close()

    _write_json(root / "reports/cross-channel-import-result.json", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入 BOSS+脉脉绑定候选人到 Campaign DB")
    subparsers = parser.add_subparsers(dest="command", required=True)
    importer = subparsers.add_parser("import")
    importer.add_argument("--campaign-root", required=True)
    importer.add_argument("--db", required=True)
    importer.add_argument("--dry-run", action="store_true")
    importer.set_defaults(func=lambda args: import_bound_candidates(args.campaign_root, args.db, dry_run=args.dry_run))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("blocked") or result.get("errors") else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run import tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_import.py -q
```

Expected: all import tests pass.

- [ ] **Step 5: Commit import changes**

Run:

```bash
git add scripts/cross_channel_import.py tests/test_cross_channel_import.py
git commit -m "Import BOSS-primary Maimai-supplement candidates"
```

Expected: commit succeeds and contains only the import script and test.

---

### Task 6: Prefer Maimai URLs In JD Delivery

**Files:**
- Modify: `scripts/jd_talent_delivery_match.py`
- Modify: `tests/test_jd_talent_delivery_match.py`

- [ ] **Step 1: Write failing Maimai URL priority test**

Append to `tests/test_jd_talent_delivery_match.py` near existing source URL tests:

```python
def test_source_url_prefers_openable_maimai_profile_url() -> None:
    candidate = Candidate(
        id=1,
        name="陶壮",
        current_company="华为技术有限公司",
        current_title="大模型推理工程师",
    )
    bundle = CandidateBundle(
        candidate=candidate,
        detail=None,
        sources=[
            SourceProfile(
                id=1,
                candidate_id=1,
                platform="boss_app",
                platform_id="boss-001",
                profile_url="boss://candidate/boss-001",
            ),
            SourceProfile(
                id=2,
                candidate_id=1,
                platform="maimai",
                platform_id="mm-001",
                profile_url="https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok&show_tip=1&utm_source=test",
            ),
        ],
    )

    assert _source_url(bundle) == "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
```

If `Candidate`, `SourceProfile`, `CandidateBundle`, or `_source_url` are not imported in the test file, add:

```python
from scripts.jd_talent_delivery_match import CandidateBundle, _source_url
from scripts.talent_models import Candidate, SourceProfile
```

- [ ] **Step 2: Run URL priority test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_match.py::test_source_url_prefers_openable_maimai_profile_url -q
```

Expected: failure because `_source_url` returns the BOSS URL.

- [ ] **Step 3: Implement URL priority**

Modify `scripts/jd_talent_delivery_match.py`:

```python
def _source_priority(source: Any) -> tuple[int, int]:
    platform = str(getattr(source, "platform", "") or "")
    url = str(getattr(source, "profile_url", "") or "")
    if platform == "maimai" and url:
        return (0, 0)
    if url:
        return (1, 0)
    return (2, 0)


def _source_url(bundle: CandidateBundle) -> str:
    for source in sorted(bundle.sources, key=_source_priority):
        url = getattr(source, "profile_url", "") or ""
        if not url:
            continue
        if getattr(source, "platform", "") == "maimai":
            return build_openable_maimai_profile_url(str(url))
        return str(url)
    return ""
```

Keep `is_openable_maimai_profile_url` in quality-gate code unchanged.

- [ ] **Step 4: Run JD delivery match tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_match.py -q
```

Expected: all tests in `tests/test_jd_talent_delivery_match.py` pass.

- [ ] **Step 5: Commit URL priority change**

Run:

```bash
git add scripts/jd_talent_delivery_match.py tests/test_jd_talent_delivery_match.py
git commit -m "Prefer Maimai profile URLs in delivery"
```

Expected: commit succeeds and contains only the delivery match script and test.

---

### Task 7: Implement Campaign DB To Main DB Sync And Delivery Handoff

**Files:**
- Create: `scripts/campaign_to_delivery.py`
- Create: `tests/test_campaign_to_delivery.py`

- [ ] **Step 1: Write failing campaign gate and sync tests**

Create `tests/test_campaign_to_delivery.py`:

```python
import json
from pathlib import Path

import pytest

from scripts import campaign_to_delivery
from scripts.talent_db import TalentDB
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT


def _clean_campaign_db(path: Path) -> int:
    db = TalentDB(path)
    try:
        candidate_id = db.ingest(
            {
                "name": "陶壮",
                "current_company": "华为技术有限公司",
                "current_title": "大模型推理工程师",
                "platform_id": "boss-001",
            },
            platform="boss_app",
        )
        db.merge_candidate_source(
            candidate_id,
            {
                "name": "陶壮",
                "platform_id": "mm-001",
                "profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
            },
            platform="maimai",
        )
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:1",
                "target_platform": "maimai",
                "target_platform_id": "mm-001",
                "target_profile_url": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
                "query_text": "陶壮 华为技术有限公司 大模型推理工程师",
                "query_level": "name_company_title",
                "confidence": 98,
                "score_breakdown": {"total": 98},
                "match_status": "auto_bound",
                "decision_reason": "高精度匹配",
            }
        )
        db.record_field_value(
            {
                "candidate_id": candidate_id,
                "field_name": "profile_url",
                "platform": "maimai",
                "field_value": "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok",
                "confidence": 95,
                "merge_decision": "supplement_added",
                "decision_reason": "补充脉脉主页",
            }
        )
        return candidate_id
    finally:
        db.close()


def test_validate_campaign_ready_passes_clean_campaign(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    _clean_campaign_db(root / "talent.db")

    result = campaign_to_delivery.validate_campaign_ready(root, root / "talent.db")

    assert result["status"] == "passed"
    assert result["integrity_check"] == "ok"
    assert result["pending_identity_count"] == 0
    assert result["candidate_count"] == 1


def test_validate_campaign_ready_blocks_pending_identity(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    db_path = root / "talent.db"
    _clean_campaign_db(db_path)
    db = TalentDB(db_path)
    try:
        candidate_id = db.search()[0].id
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss_app",
                "source_candidate_key": "boss-app:2",
                "target_platform": "maimai",
                "target_platform_id": "mm-002",
                "query_text": "陶壮 华为",
                "query_level": "name_company_fallback",
                "confidence": 88,
                "score_breakdown": {"total": 88},
                "match_status": "pending_confirmation",
                "decision_reason": "fallback",
            }
        )
    finally:
        db.close()

    result = campaign_to_delivery.validate_campaign_ready(root, db_path)

    assert result["status"] == "blocked"
    assert "pending_identity" in result["blockers"]


def test_sync_main_requires_authorization(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)

    with pytest.raises(ValueError, match="allow_main_db_write_after_clean_campaign"):
        campaign_to_delivery.sync_main_db(
            root,
            campaign_db,
            main_db,
            allow_main_db_write_after_clean_campaign=False,
            confirm=CONFIRM_SYNC_TEXT,
        )


def test_sync_main_exports_bundle_applies_and_writes_handoff(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    root.mkdir()
    campaign_db = root / "talent.db"
    main_db = tmp_path / "main.db"
    _clean_campaign_db(campaign_db)

    result = campaign_to_delivery.sync_main_db(
        root,
        campaign_db,
        main_db,
        allow_main_db_write_after_clean_campaign=True,
        confirm=CONFIRM_SYNC_TEXT,
        delivery_context={"jd_input": "AI Infra JD", "top_n": 30, "publish_feishu": True},
    )

    assert result["status"] == "applied"
    assert result["dry_run"]["incoming"]["candidates"] == 1
    assert (root / "reports/main-db-sync-dry-run.json").exists()
    assert (root / "reports/main-db-sync-result.json").exists()
    handoff = json.loads((root / "state/jd-delivery-handoff.json").read_text(encoding="utf-8"))
    assert handoff["main_db_path"] == str(main_db)
    assert handoff["delivery_context"]["top_n"] == 30

    db = TalentDB(main_db)
    try:
        assert db.count() == 1
        assert db.get_sources(db.search()[0].id)[1].platform == "maimai"
    finally:
        db.close()
```

- [ ] **Step 2: Run campaign-to-delivery tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_campaign_to_delivery.py -q
```

Expected: import failure because `scripts/campaign_to_delivery.py` does not exist.

- [ ] **Step 3: Implement campaign gates and sync**

Create `scripts/campaign_to_delivery.py`:

```python
"""Campaign DB clean 后同步主库并生成 JD delivery handoff。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.talent_db import TalentDB
from scripts.talent_sync import export_bundle, import_bundle, verify_bundle
from scripts.talent_sync_models import CONFIRM_SYNC_TEXT


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def validate_campaign_ready(campaign_root: str | Path, db_path: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    db = TalentDB(db_path)
    try:
        integrity = db._conn.execute("PRAGMA integrity_check").fetchone()[0]
        pending_identity = db._conn.execute(
            """
            SELECT COUNT(*)
            FROM candidate_identity_matches
            WHERE match_status = 'pending_confirmation'
            """
        ).fetchone()[0]
        pending_merges = db._conn.execute(
            "SELECT COUNT(*) FROM pending_merges WHERE status = 'pending'"
        ).fetchone()[0]
        open_conflicts = db._conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE status = 'open'"
        ).fetchone()[0]
        candidate_count = db.count()
        source_count = db._conn.execute("SELECT COUNT(*) FROM source_profiles").fetchone()[0]
        identity_count = db._conn.execute("SELECT COUNT(*) FROM candidate_identity_matches").fetchone()[0]
        field_count = db._conn.execute("SELECT COUNT(*) FROM candidate_field_values").fetchone()[0]
    finally:
        db.close()

    blockers: list[str] = []
    if integrity != "ok":
        blockers.append("integrity_check")
    if pending_identity:
        blockers.append("pending_identity")
    if pending_merges:
        blockers.append("pending_merges")
    if open_conflicts:
        blockers.append("open_sync_conflicts")
    result = {
        "schema": "campaign_db_quality_gates_v1",
        "checked_at": datetime.now().isoformat(timespec="seconds"),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "integrity_check": integrity,
        "pending_identity_count": pending_identity,
        "pending_merge_count": pending_merges,
        "open_sync_conflict_count": open_conflicts,
        "candidate_count": candidate_count,
        "source_profile_count": source_count,
        "identity_match_count": identity_count,
        "field_value_count": field_count,
    }
    _write_json(root / "reports/campaign-db-quality-gates.json", result)
    return result


def _write_handoff(root: Path, main_db_path: Path, delivery_context: dict[str, Any]) -> dict[str, Any]:
    handoff = {
        "schema": "jd_delivery_handoff_v1",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "main_db_path": str(main_db_path),
        "delivery_skill": "jd-talent-delivery",
        "delivery_workflow": "agents/workflows/jd-talent-delivery/AGENT.md",
        "delivery_context": delivery_context,
        "url_priority": ["maimai", "other_platforms"],
    }
    _write_json(root / "state/jd-delivery-handoff.json", handoff)
    return handoff


def sync_main_db(
    campaign_root: str | Path,
    campaign_db_path: str | Path,
    main_db_path: str | Path,
    *,
    allow_main_db_write_after_clean_campaign: bool,
    confirm: str,
    delivery_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not allow_main_db_write_after_clean_campaign:
        raise ValueError("allow_main_db_write_after_clean_campaign is required")
    if confirm != CONFIRM_SYNC_TEXT:
        raise ValueError(f"confirm must be {CONFIRM_SYNC_TEXT}")

    root = Path(campaign_root)
    campaign_db = Path(campaign_db_path)
    main_db = Path(main_db_path)
    gates = validate_campaign_ready(root, campaign_db)
    if gates["status"] != "passed":
        result = {"schema": "main_db_sync_result_v1", "status": "blocked", "gates": gates}
        _write_json(root / "reports/main-db-sync-result.json", result)
        return result

    bundle_path = root / "sync/campaign-to-main.zip"
    export_summary = export_bundle(campaign_db, bundle_path, mode="full")
    verification = verify_bundle(bundle_path)
    if not verification["ok"]:
        result = {
            "schema": "main_db_sync_result_v1",
            "status": "blocked",
            "reason": "bundle_verify_failed",
            "verification": verification,
        }
        _write_json(root / "reports/main-db-sync-result.json", result)
        return result

    dry_run = import_bundle(bundle_path, main_db, apply=False)
    _write_json(root / "reports/main-db-sync-dry-run.json", dry_run)
    if dry_run["conflicts"].get("candidates", 0) or dry_run["pending"].get("candidates", 0) or dry_run.get("errors"):
        result = {
            "schema": "main_db_sync_result_v1",
            "status": "blocked",
            "reason": "main_db_dry_run_not_clean",
            "dry_run": dry_run,
        }
        _write_json(root / "reports/main-db-sync-result.json", result)
        return result

    apply_result = import_bundle(bundle_path, main_db, apply=True, confirm=confirm)
    handoff = _write_handoff(root, main_db, delivery_context or {})
    result = {
        "schema": "main_db_sync_result_v1",
        "status": "applied",
        "bundle_path": str(bundle_path),
        "export_summary": export_summary,
        "verification": verification,
        "dry_run": dry_run,
        "apply_result": apply_result,
        "handoff": handoff,
    }
    _write_json(root / "reports/main-db-sync-result.json", result)
    _append_jsonl(root / "state/main-db-sync-ledger.jsonl", result)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Campaign DB 到主库同步与交付 handoff")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate-campaign")
    validate.add_argument("--campaign-root", required=True)
    validate.add_argument("--db", required=True)
    validate.set_defaults(func=lambda args: validate_campaign_ready(args.campaign_root, args.db))

    sync = subparsers.add_parser("sync-main")
    sync.add_argument("--campaign-root", required=True)
    sync.add_argument("--campaign-db", required=True)
    sync.add_argument("--main-db", default="data/talent.db")
    sync.add_argument("--allow-main-db-write-after-clean-campaign", action="store_true")
    sync.add_argument("--confirm", default="")
    sync.set_defaults(
        func=lambda args: sync_main_db(
            args.campaign_root,
            args.campaign_db,
            args.main_db,
            allow_main_db_write_after_clean_campaign=args.allow_main_db_write_after_clean_campaign,
            confirm=args.confirm,
        )
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = args.func(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run campaign-to-delivery tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_campaign_to_delivery.py -q
```

Expected: all campaign-to-delivery tests pass.

- [ ] **Step 5: Commit sync and handoff**

Run:

```bash
git add scripts/campaign_to_delivery.py tests/test_campaign_to_delivery.py
git commit -m "Sync clean campaigns to main DB for delivery"
```

Expected: commit succeeds and contains only the sync/handoff script and test.

---

### Task 8: Wire Documentation, Inventory, And Final Workflow Evidence

**Files:**
- Modify: `docs/dev/script-inventory.md`
- Modify: `tasks/todo.md`
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- Modify: `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`

- [ ] **Step 1: Update script inventory**

Add rows to `docs/dev/script-inventory.md` using the file's existing table format. The entries must state side effects:

```markdown
| `scripts/boss_maimai_targets.py` | 从 BOSS campaign 生成脉脉匹配 target | 写 `structured/maimai-match-targets.jsonl` 和 `reports/maimai-match-summary.*`；不连接平台、不写 DB |
| `scripts/cross_channel_identity.py` | BOSS target 与脉脉搜索结果身份评分 | 纯函数模块；不读写文件、不连接平台、不写 DB |
| `scripts/cross_channel_import.py` | 将 BOSS primary + Maimai supplement 写入 Campaign DB | 只写指定 Campaign DB；不写 `data/talent.db` |
| `scripts/campaign_to_delivery.py` | Campaign DB clean 后导出 bundle、dry-run/apply 主库并写交付 handoff | 只有授权和 gate 成立时写 `data/talent.db`；不直接发布飞书 |
```

- [ ] **Step 2: Update task ledger active task**

In `tasks/todo.md`, update the active task plan to include implementation progress:

```markdown
- [ ] 实施 canonical skill/workflow/adapter 和架构测试。
- [ ] 扩展 TalentDB 多渠道审计 schema、sync export/import 和测试。
- [ ] 实施 BOSS target 生成、脉脉 identity scoring 和 Campaign DB import。
- [ ] 实施主库 sync gate、JD delivery handoff 和脉脉 URL 优先级。
- [ ] 运行聚焦测试、全量测试和 `git diff --check`，写 Review 并归档。
```

- [ ] **Step 3: Run focused cross-channel suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py tests/test_boss_maimai_targets.py tests/test_cross_channel_identity.py tests/test_cross_channel_import.py tests/test_campaign_to_delivery.py tests/test_jd_talent_delivery_match.py tests/test_talent_db.py tests/test_talent_sync.py -q
```

Expected: all focused tests pass.

- [ ] **Step 4: Run full verification**

Run:

```bash
.venv/bin/python -m pytest tests -q
git diff --check
```

Expected: full test suite passes; `git diff --check` prints no output and exits `0`.

- [ ] **Step 5: Inspect worktree scope**

Run:

```bash
git status --short
git diff --stat
```

Expected: cross-channel changes are limited to files in this plan plus existing unrelated dirty files that predated this task. Do not stage unrelated dirty files.

- [ ] **Step 6: Commit final docs/inventory updates**

Run:

```bash
git add docs/dev/script-inventory.md tasks/todo.md agents/skills/boss-maimai-cross-channel-delivery/SKILL.md agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md
git commit -m "Document BOSS-Maimai delivery workflow"
```

Expected: commit succeeds if those files have changes. If `tasks/todo.md` contains unrelated pre-existing user changes, do not stage it; instead commit only the workflow/inventory docs and mention the task ledger remained uncommitted.

---

## Final Verification Checklist

- [ ] `tests/test_agent_architecture.py` passes and the canonical skill/workflow/adapter are runtime-neutral.
- [ ] `tests/test_cross_channel_identity.py` proves high-precision query ordering and `name_company_fallback` manual confirmation.
- [ ] `tests/test_cross_channel_import.py` proves BOSS primary fields are kept and Maimai source/profile URL are added.
- [ ] `tests/test_talent_db.py` and `tests/test_talent_sync.py` prove audit tables persist and sync bundle round-trips them.
- [ ] `tests/test_jd_talent_delivery_match.py` proves Maimai profile URLs are preferred in delivery.
- [ ] `tests/test_campaign_to_delivery.py` proves Campaign DB gates and one-authorization main DB apply behavior.
- [ ] `.venv/bin/python -m pytest tests -q` passes.
- [ ] `git diff --check` passes.
- [ ] No raw platform payload, SQLite DB, sync zip, cookie, localStorage, sessionStorage, or token-bearing non-profile fields are added to Feishu delivery contracts.
