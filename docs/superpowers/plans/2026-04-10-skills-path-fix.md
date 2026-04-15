# Skills 路径修复与 scripts 归属整理 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 skills 从项目根迁移到 `.claude/skills/` 后遗留的路径引用，并将 `token-tracker.py` 移入其归属 skill。

**Architecture:** 纯路径修复 + 文件移动，不涉及逻辑变更。分三批：SKILL.md 内联引用（运行时影响）、token-tracker 移动及引用更新、历史文档批量更新。

**Tech Stack:** 无（Markdown + 文件系统操作）

---

## 文件结构

```
变更前:
scripts/
├── data-manager.py          ← 不动（4 个 skill 共享）
└── token-tracker.py         ← 移走
.claude/skills/
├── platform-match/SKILL.md  ← 改路径引用
├── platform-match/references/platform-config.md  ← 改路径引用
├── screen/SKILL.md          ← 改路径引用
└── public-search/SKILL.md   ← 改 token-tracker 引用

变更后:
scripts/
└── data-manager.py          ← 不动
.claude/skills/
├── platform-match/SKILL.md
├── platform-match/references/platform-config.md
├── screen/SKILL.md
└── public-search/
    ├── SKILL.md
    └── scripts/
        └── token-tracker.py ← 从 scripts/ 移入
```

---

### Task 1: 修复 platform-match/SKILL.md 内联路径

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md` (3 处)

- [ ] **Step 1: 修复第 36 行**

将 `skills/platform-match/modules/maimai-scraper` 替换为 `.claude/skills/platform-match/modules/maimai-scraper`

- [ ] **Step 2: 修复第 144 行**

将 `skills/platform-match/modules/maimai-scraper/` 替换为 `.claude/skills/platform-match/modules/maimai-scraper/`

- [ ] **Step 3: 修复第 182 行**

将 `skills/platform-match/references/platform-config.md` 替换为 `.claude/skills/platform-match/references/platform-config.md`

- [ ] **Step 4: 验证**

Run: `grep -n 'skills/' .claude/skills/platform-match/SKILL.md | grep -v '.claude/skills/'`
Expected: 无输出（所有 `skills/` 引用都已更新为 `.claude/skills/`）

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/platform-match/SKILL.md
git commit -m "fix: 更新 platform-match SKILL.md 中的路径引用"
```

---

### Task 2: 修复 screen/SKILL.md 内联路径

**Files:**
- Modify: `.claude/skills/screen/SKILL.md` (2 处)

- [ ] **Step 1: 修复第 30 行**

将 `skills/screen/references/eval-criteria.md` 替换为 `.claude/skills/screen/references/eval-criteria.md`

- [ ] **Step 2: 修复第 49 行**

将 `skills/screen/references/eval-criteria.md` 替换为 `.claude/skills/screen/references/eval-criteria.md`

- [ ] **Step 3: 验证**

Run: `grep -n 'skills/' .claude/skills/screen/SKILL.md | grep -v '.claude/skills/'`
Expected: 无输出

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/screen/SKILL.md
git commit -m "fix: 更新 screen SKILL.md 中的路径引用"
```

---

### Task 3: 修复 platform-config.md 内联路径

**Files:**
- Modify: `.claude/skills/platform-match/references/platform-config.md` (1 处)

- [ ] **Step 1: 修复第 167 行**

将文件结构约定中的 `skills/platform-match/` 替换为 `.claude/skills/platform-match/`

- [ ] **Step 2: 验证**

Run: `grep -n 'skills/' .claude/skills/platform-match/references/platform-config.md | grep -v '.claude/skills/'`
Expected: 无输出

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/platform-match/references/platform-config.md
git commit -m "fix: 更新 platform-config.md 中的路径引用"
```

---

### Task 4: 移动 token-tracker.py 到 public-search/scripts/

**Files:**
- Move: `scripts/token-tracker.py` → `.claude/skills/public-search/scripts/token-tracker.py`
- Modify: `.claude/skills/public-search/SKILL.md` (4 处)

- [ ] **Step 1: 创建目标目录**

Run: `mkdir -p .claude/skills/public-search/scripts`

- [ ] **Step 2: 移动文件**

Run: `mv scripts/token-tracker.py .claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 3: 清理空 scripts 目录（如果 data-manager.py 是唯一文件则保留）**

Run: `ls scripts/`
如果只剩 `data-manager.py` 和 `.gitkeep`，保留目录不动。

- [ ] **Step 4: 更新 public-search/SKILL.md 第 220 行**

将 `scripts/token-tracker.py` 替换为 `.claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 5: 更新 public-search/SKILL.md 第 225 行**

将代码块中的 `python scripts/token-tracker.py` 替换为 `python .claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 6: 更新 public-search/SKILL.md 第 555 行**

将 `scripts/token-tracker.py` 替换为 `.claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 7: 更新 public-search/SKILL.md 第 557 行**

将 `python scripts/token-tracker.py` 替换为 `python .claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 8: 更新 token-tracker.py 自身 docstring**

将文件第 9 行 `python scripts/token-tracker.py` 替换为 `python .claude/skills/public-search/scripts/token-tracker.py`

- [ ] **Step 9: 验证**

Run: `grep -rn 'scripts/token-tracker' .claude/skills/public-search/ --include='*.md' --include='*.py' | grep -v '.claude/skills/public-search/scripts/'`
Expected: 无输出

Run: `test -f .claude/skills/public-search/scripts/token-tracker.py && echo "OK" || echo "MISSING"`
Expected: OK

- [ ] **Step 10: Commit**

```bash
git add scripts/token-tracker.py .claude/skills/public-search/scripts/token-tracker.py .claude/skills/public-search/SKILL.md
git commit -m "refactor: 将 token-tracker.py 移入 public-search skill"
```

---

### Task 5: 更新 README.md 路径引用

**Files:**
- Modify: `README.md` (2 处)

- [ ] **Step 1: 修复 skills 目录引用**

将 README.md 第 26 行 `skills/` 相关描述更新为 `.claude/skills/`。具体改为：
- `skills/ — 4 个 CC Skill 定义` → `.claude/skills/ — 4 个 CC Skill 定义`

- [ ] **Step 2: 验证**

Run: `grep -n 'skills/' README.md | grep -v '.claude/skills/' | grep -v 'scripts/'`
Expected: 无输出（`scripts/data-manager.py` 引用保留不变）

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: 更新 README 中的 skills 目录路径"
```

---

### Task 6: 批量更新 docs/ 下历史文档路径（可选）

**Files:**
- Modify: `docs/superpowers/` 下约 6 个文件，共约 40 处旧 `skills/` 引用

这些是已执行完的计划/设计文档，修改仅为保持一致性，不影响运行。

- [ ] **Step 1: 查找所有需要更新的文件**

Run: `grep -rn 'skills/' docs/superpowers/ --include='*.md' | grep -v '.claude/skills/' | grep -v 'scripts/' | grep -v 'adapters/' | wc -l`
确认引用数量。

- [ ] **Step 2: 逐文件批量替换**

对每个匹配文件，将 `skills/public-search/`、`skills/platform-match/`、`skills/screen/`、`skills/report/` 分别替换为 `.claude/skills/public-search/`、`.claude/skills/platform-match/`、`.claude/skills/screen/`、`.claude/skills/report/`。

注意：保留 `adapters/claude-code/skills/` 和 `scripts/` 开头的引用不变。

- [ ] **Step 3: 全局验证**

Run: `grep -rn '\bskills/' docs/ --include='*.md' | grep -v '.claude/skills/' | grep -v 'scripts/' | grep -v 'adapters/'`
Expected: 无输出

- [ ] **Step 4: Commit**

```bash
git add docs/
git commit -m "docs: 批量更新历史文档中的 skills 路径引用"
```
