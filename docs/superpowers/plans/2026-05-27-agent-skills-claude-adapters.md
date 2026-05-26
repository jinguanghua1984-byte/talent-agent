# Agent Skills And Claude Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把根目录 `skills/` 中的两个业务入口合同迁移到 `agents/skills/`，并补齐 Claude Code adapter，使 skill、workflow 和 runtime adapter 分层清晰。

**Architecture:** `agents/skills/<name>/SKILL.md` 保存运行时中立的业务语义入口、默认参数和 workflow 交接合同；`agents/workflows/<name>/AGENT.md` 保存 canonical workflow；`.claude/skills/<name>/SKILL.md` 只做 Claude Code 私有入口适配，先读取能力映射和 canonical skill，再读取 workflow。

**Tech Stack:** Markdown skill/workflow 文档、Python pytest 文档契约测试、Git 文件移动。

---

### Task 1: 目录和适配器契约测试

**Files:**
- Modify: `tests/test_agent_architecture.py`
- Modify: `tests/test_jd_talent_delivery_skill.py`
- Modify: `tests/test_maimai_talent_search_campaign_skill.py`

- [ ] **Step 1: 写失败测试**

把 skill 测试路径从 `skills/...` 改到 `agents/skills/...`；在架构测试中要求：
- `agents/skills/jd-talent-delivery/SKILL.md` 存在并交接 `agents/workflows/jd-talent-delivery/AGENT.md`。
- `agents/skills/maimai-talent-search-campaign/SKILL.md` 存在并交接 `agents/workflows/maimai-unattended-campaign/AGENT.md`。
- 根目录 `skills/` 不再保存 canonical skill。
- `.claude/skills/maimai-talent-search-campaign/SKILL.md` 存在。
- `jd-talent-delivery` Claude adapter 读取 canonical skill contract。

- [ ] **Step 2: 运行红灯验证**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py tests/test_jd_talent_delivery_skill.py tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: FAIL，失败点应指向缺少 `agents/skills/...` 或缺少 `.claude/skills/maimai-talent-search-campaign/SKILL.md`。

### Task 2: 迁移运行时中立 skill contract

**Files:**
- Move: `skills/jd-talent-delivery/SKILL.md` -> `agents/skills/jd-talent-delivery/SKILL.md`
- Move: `skills/maimai-talent-search-campaign/SKILL.md` -> `agents/skills/maimai-talent-search-campaign/SKILL.md`
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`

- [ ] **Step 1: 移动文件**

Run:

```bash
mkdir -p agents/skills
git mv skills agents/skills
```

- [ ] **Step 2: 同步 workflow 引用**

把 `agents/workflows/jd-talent-delivery/AGENT.md` 中的 `skills/jd-talent-delivery/SKILL.md` 改为 `agents/skills/jd-talent-delivery/SKILL.md`。

- [ ] **Step 3: 运行聚焦测试**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_talent_delivery_skill.py tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: PASS。

### Task 3: 补齐 Claude Code adapter

**Files:**
- Modify: `.claude/skills/jd-talent-delivery/SKILL.md`
- Create: `.claude/skills/maimai-talent-search-campaign/SKILL.md`
- Modify: `agents/adapters/claude-code/README.md`

- [ ] **Step 1: 强化已有 adapter**

`jd-talent-delivery` adapter 必须先读取 `agents/capabilities.md`，再读取 `agents/skills/jd-talent-delivery/SKILL.md`，最后读取 `agents/workflows/jd-talent-delivery/AGENT.md`。

- [ ] **Step 2: 新增 maimai adapter**

新增 `.claude/skills/maimai-talent-search-campaign/SKILL.md`，frontmatter 使用同名 `name` 和业务触发 `description`；正文声明这是运行时私有入口，并要求读取 `agents/capabilities.md`、canonical skill contract 和 `agents/workflows/maimai-unattended-campaign/AGENT.md`。

- [ ] **Step 3: 运行架构测试**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: PASS。

### Task 4: 文档同步

**Files:**
- Modify: `README.md`
- Modify: `agents/README.md`

- [ ] **Step 1: 更新目录说明**

`README.md` 和 `agents/README.md` 必须明确：
- `agents/skills/` 是运行时中立业务入口合同。
- `agents/workflows/` 是 canonical workflow。
- `.claude/skills/` 是 Claude Code 兼容适配器。

- [ ] **Step 2: 运行文档/架构聚焦测试**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py tests/test_jd_talent_delivery_skill.py tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: PASS。

### Task 5: 最终验证和任务记录

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-05.md`

- [ ] **Step 1: 运行仓库要求验证**

Run:

```bash
.venv/bin/python -m pytest tests scripts -q
```

Expected: PASS，允许既有 warning，但不能有失败。

- [ ] **Step 2: 运行 diff hygiene**

Run:

```bash
git diff --check
```

Expected: 无输出，exit 0。

- [ ] **Step 3: 写 Review 并归档**

在 `tasks/todo.md` 写简短 Review，把完整记录归档到 `tasks/archive/2026-05.md`。Review 必须包含修改范围、测试命令、未触碰的边界和已知 warning。
