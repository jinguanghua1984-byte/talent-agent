# platform-match 全量重设计 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 platform-match skill 从 TypeScript 表单填充架构重写为 Python Playwright API 拦截架构，支持三种执行模式（候选丰富、JD 驱动、对话式），并集成身份判定、JD 匹配、自学习机制。

**Architecture:** 混合分层架构——SKILL.md 作为编排层负责意图解析和决策，Python 脚本作为执行层负责浏览器操作和数据转换。通过 PlatformAdapter 协议支持多平台扩展，当前仅实现脉脉适配器。

**Tech Stack:** Python 3.11+, Playwright (async API), argparse (CLI), JSON Schema (validation)

**Spec:** `docs/superpowers/specs/2026-04-15-platform-match-redesign-design.md`

---

## File Map

### 新建文件

| 文件 | 职责 |
|------|------|
| `requirements.txt` | Python 依赖声明 |
| `.claude/skills/platform-match/scripts/__init__.py` | Python 包标识 |
| `.claude/skills/platform-match/scripts/session.py` | CDP 连接 + session 管理 |
| `.claude/skills/platform-match/scripts/search.py` | API 搜索 + 分页 + 结果解析 |
| `.claude/skills/platform-match/scripts/enrich.py` | 字段映射 + 逐字段冲突合并 + 写入 |
| `.claude/skills/platform-match/scripts/rate_limiter.py` | 令牌桶限流 + 熔断 |
| `.claude/skills/platform-match/scripts/adapters/__init__.py` | 适配器包标识 |
| `.claude/skills/platform-match/scripts/adapters/base.py` | PlatformAdapter 协议 + 类型定义 |
| `.claude/skills/platform-match/scripts/adapters/maimai.py` | 脉脉搜索适配器实现 |
| `.claude/skills/platform-match/rules/identity-rules.md` | 身份判定规则 |
| `.claude/skills/platform-match/rules/jd-match-rules.md` | 人岗匹配规则 |
| `.claude/skills/platform-match/rules/company-aliases.json` | 公司别名注册表 |
| `.claude/skills/platform-match/references/maimai/api-reference.md` | 脉脉搜索 API 规格文档 |
| `.claude/skills/platform-match/references/maimai/field-mapping.md` | API 字段 → candidate.schema 映射表 |
| `.claude/skills/platform-match/references/maimai/anti-detect.md` | 反检测策略 |
| `.claude/skills/platform-match/references/matching-strategy.md` | 多匹配判定策略 |
| `.claude/skills/platform-match/assets/candidate-list-template.md` | 候选人列表输出模板 |
| `.claude/skills/platform-match/assets/match-report-template.md` | 匹配报告模板 |
| `.claude/skills/platform-match/scripts/batch_progress.py` | 批次断点恢复管理 |
| `.claude/skills/platform-match/evals/evals.json` | 评估配置 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `schemas/candidate.schema.json` | 新增 active_state, project_experience; 扩展 sources[] |
| `scripts/data-manager.py` | 新增 batch 命令、dedup-merge 命令；修复 H2 bug |
| `.gitignore` | 新增 data/session/、data/batches/ 忽略规则 |
| `.claude/skills/platform-match/SKILL.md` | 全量重写（三种模式 + 自学习 + 错误处理） |
| `.claude/skills/public-search/SKILL.md` | 新增批次记录章节 |

### 删除文件

| 文件/目录 | 原因 |
|-----------|------|
| `.claude/skills/platform-match/modules/form-filler/` | 旧 TypeScript 表单填充，已作废 |
| `.claude/skills/platform-match/modules/loop-orchestrator/` | 旧 TypeScript 循环编排，已作废 |
| `.claude/skills/platform-match/modules/result-merger/` | 旧 TypeScript 结果合并，已作废 |
| `.claude/skills/platform-match/modules/logger.ts` | 旧 TypeScript 日志，已作废 |
| `.claude/skills/platform-match/references/form-controls-map.md` | DOM 控件映射，不再使用 |
| `.claude/skills/platform-match/references/maimai-fields.md` | 旧字段映射，被 field-mapping.md 替代 |
| `.claude/skills/platform-match/references/platform-config.md` | 旧配置，不再使用 |
| `.claude/skills/platform-match/references/anti-scraping.md` | 旧反爬文档，被 anti-detect.md 替代 |

---

## Phase 1: Foundation & Cleanup

### Task 1: Delete Obsolete Code

**Files:**
- Delete: `.claude/skills/platform-match/modules/` (entire directory)
- Delete: `.claude/skills/platform-match/references/form-controls-map.md`
- Delete: `.claude/skills/platform-match/references/maimai-fields.md`
- Delete: `.claude/skills/platform-match/references/platform-config.md`
- Delete: `.claude/skills/platform-match/references/anti-scraping.md`

- [ ] **Step 1: Verify files to delete exist**

Run: `ls -la .claude/skills/platform-match/modules/`
Expected: Lists form-filler/, loop-orchestrator/, result-merger/, logger.ts

Run: `ls .claude/skills/platform-match/references/`
Expected: Lists form-controls-map.md, maimai-fields.md, platform-config.md, anti-scraping.md

- [ ] **Step 2: Delete obsolete modules directory**

Run: `rm -rf .claude/skills/platform-match/modules/`

- [ ] **Step 3: Delete obsolete reference files**

Run: `rm .claude/skills/platform-match/references/form-controls-map.md .claude/skills/platform-match/references/maimai-fields.md .claude/skills/platform-match/references/platform-config.md .claude/skills/platform-match/references/anti-scraping.md`

- [ ] **Step 4: Verify cleanup**

Run: `ls .claude/skills/platform-match/`
Expected: Only SKILL.md, references/ (with browser-tools.md if it exists), and empty directories ready for new structure

- [ ] **Step 5: Commit**

```bash
git add -A .claude/skills/platform-match/
git commit -m "refactor: 删除已作废的 TypeScript 模块和旧参考文档"
```

---

### Task 2: Create Directory Structure & Dependencies

**Files:**
- Create: `requirements.txt`
- Create: `.claude/skills/platform-match/scripts/__init__.py`
- Create: `.claude/skills/platform-match/scripts/adapters/__init__.py`
- Create (dirs): `.claude/skills/platform-match/rules/`, `.claude/skills/platform-match/assets/`, `.claude/skills/platform-match/references/maimai/`, `.claude/skills/platform-match/evals/`

- [ ] **Step 1: Create requirements.txt**

```txt
playwright>=1.40.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`

- [ ] **Step 3: Create directory structure**

Run:
```bash
mkdir -p .claude/skills/platform-match/scripts/adapters
mkdir -p .claude/skills/platform-match/rules
mkdir -p .claude/skills/platform-match/assets
mkdir -p .claude/skills/platform-match/references/maimai
mkdir -p .claude/skills/platform-match/evals
mkdir -p data/session
mkdir -p data/batches
```

- [ ] **Step 4: Create __init__.py files**

`.claude/skills/platform-match/scripts/__init__.py` — empty file
`.claude/skills/platform-match/scripts/adapters/__init__.py` — empty file

- [ ] **Step 5: Update .gitignore**

Add to `.gitignore`:
```
# Session data (cookies, rate limit state, batch progress)
data/session/
data/batches/
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .claude/skills/platform-match/scripts/ .claude/skills/platform-match/rules/ .claude/skills/platform-match/assets/ .claude/skills/platform-match/references/maimai/ .claude/skills/platform-match/evals/ .gitignore
git commit -m "chore: 创建 platform-match 新目录结构和 Python 依赖"
```

---

## Phase 2: Schema & Data Manager Extensions

### Task 3: Update candidate.schema.json

**Files:**
- Modify: `schemas/candidate.schema.json`

- [ ] **Step 1: Add new fields to schema**

在 `schemas/candidate.schema.json` 的 `properties` 中新增以下字段：

```json
"active_state": {
  "type": "string",
  "description": "平台活跃状态（如 '今日活跃', '在线', '3天前活跃'）"
},
"project_experience": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["name", "period"],
    "properties": {
      "name": {
        "type": "string",
        "description": "项目名称"
      },
      "period": {
        "type": "string",
        "description": "时间段（如 '2023-06 - 2024-12'）"
      },
      "role": {
        "type": "string",
        "description": "担任角色"
      },
      "description": {
        "type": "string",
        "description": "项目描述"
      }
    }
  },
  "description": "项目经历数组"
}
```

- [ ] **Step 2: Expand sources[] schema**

替换现有的 `sources` 属性定义（保留 `required` 不变）为扩展版本：

```json
"sources": {
  "type": "array",
  "items": {
    "type": "object",
    "required": ["channel", "url", "found_at"],
    "properties": {
      "channel": {
        "type": "string",
        "description": "来源平台标识（maimai, boss, public-search）"
      },
      "url": {
        "type": "string",
        "description": "来源 URL"
      },
      "found_at": {
        "type": "string",
        "format": "date-time",
        "description": "发现时间（ISO 8601）"
      },
      "platform_id": {
        "type": "string",
        "description": "平台用户 ID（如脉脉 uid）"
      },
      "enrichment_level": {
        "type": "string",
        "enum": ["raw", "partial", "enriched"],
        "description": "本次来源的丰富程度"
      },
      "match_confidence": {
        "type": "integer",
        "minimum": 0,
        "maximum": 100,
        "description": "身份匹配置信度（0-100，仅候选丰富模式）"
      },
      "match_path": {
        "type": "string",
        "description": "匹配路径（A 或 B，仅候选丰富模式）"
      },
      "snapshot": {
        "type": "object",
        "properties": {
          "company_at_source": {
            "type": "string",
            "description": "发现时的公司"
          },
          "position_at_source": {
            "type": "string",
            "description": "发现时的职位"
          }
        },
        "description": "发现时的状态快照"
      }
    }
  },
  "description": "来源信息数组（只追加不覆盖）"
}
```

- [ ] **Step 3: Validate schema is valid JSON**

Run: `python -c "import json; json.load(open('schemas/candidate.schema.json', encoding='utf-8')); print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add schemas/candidate.schema.json
git commit -m "feat: 扩展 candidate schema — 新增 active_state, project_experience, sources[] 扩展字段"
```

---

### Task 4: Fix H2 Bug in data-manager.py

**Files:**
- Modify: `scripts/data-manager.py:329`

- [ ] **Step 1: Fix sources dedup key**

在 `scripts/data-manager.py` 的 `cmd_candidate_merge` 函数中，第 329 行：

将 `key = (src.get("type", ""), src.get("url", ""))` 改为 `key = (src.get("channel", ""), src.get("url", ""))`

- [ ] **Step 2: Run existing tests to verify**

Run: `python -m pytest scripts/test_data_manager.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/data-manager.py
git commit -m "fix: 修复 candidate merge 中 sources 去重键错误（type → channel）"
```

---

### Task 5: Add Batch Commands to data-manager.py

**Files:**
- Modify: `scripts/data-manager.py`

- [ ] **Step 0: Add `dedup-auto` command to build_parser() and main()**

在 candidate subparser 中添加:

```python
    cand_sub.add_parser("dedup-auto", help="自动检测重复候选人并输出合并建议")
```

在 candidate handler dict 中添加:

```python
"dedup-auto": cmd_candidate_dedup,  # 复用现有 dedup 逻辑
```

- [ ] **Step 1: Add batch data directory to get_data_dirs()**

在 `get_data_dirs()` 函数中添加 `"batches"` 条目：

```python
def get_data_dirs():
    root = get_project_root()
    return {
        "jds": os.path.join(root, "data", "jds"),
        "candidates": os.path.join(root, "data", "candidates"),
        "screens": os.path.join(root, "data", "screens"),
        "rules": os.path.join(root, "data", "rules"),
        "batches": os.path.join(root, "data", "batches"),
    }
```

- [ ] **Step 2: Write cmd_batch_list function**

```python
def cmd_batch_list(args):
    """列出所有搜索批次。"""
    results = []
    for fname in list_json_files(get_data_dirs()["batches"]):
        filepath = os.path.join(get_data_dirs()["batches"], fname)
        batch = read_json(filepath)
        results.append({
            "id": batch.get("id", ""),
            "created_at": batch.get("created_at", ""),
            "jd_id": batch.get("jd_id", ""),
            "total": batch.get("total", 0),
        })
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 3: Write cmd_batch_get function**

```python
def cmd_batch_get(args):
    """获取批次详情。"""
    batch_path = os.path.join(get_data_dirs()["batches"], f"{args.id}.json")
    if not os.path.exists(batch_path):
        print(f"错误: 批次不存在: {args.id}", file=sys.stderr)
        return 1
    data = read_json(batch_path)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 4: Write cmd_batch_candidates function**

```python
def cmd_batch_candidates(args):
    """从批次中筛选候选人。"""
    batch_path = os.path.join(get_data_dirs()["batches"], f"{args.id}.json")
    if not os.path.exists(batch_path):
        print(f"错误: 批次不存在: {args.id}", file=sys.stderr)
        return 1

    batch = read_json(batch_path)
    candidates = batch.get("candidates", [])

    # 按 score 过滤
    filter_expr = args.filter
    if filter_expr:
        try:
            # 支持简单表达式: "score>80"
            if ">" in filter_expr:
                field, value = filter_expr.split(">", 1)
                field = field.strip()
                value = float(value.strip())
                candidates = [c for c in candidates if c.get(field, 0) > value]
            elif ">=" in filter_expr:
                field, value = filter_expr.split(">=", 1)
                field = field.strip()
                value = float(value.strip())
                candidates = [c for c in candidates if c.get(field, 0) >= value]
            elif "<" in filter_expr:
                field, value = filter_expr.split("<", 1)
                field = field.strip()
                value = float(value.strip())
                candidates = [c for c in candidates if c.get(field, 0) < value]
        except (ValueError, IndexError):
            print(f"警告: 无法解析过滤表达式 '{filter_expr}'", file=sys.stderr)

    result = [{"id": c.get("id", ""), "name": c.get("name", ""), "score": c.get("score", 0)} for c in candidates]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 5: Register batch commands in build_parser()**

在 `build_parser()` 函数中，screen 命令注册之后添加：

```python
    # --- Batch ---
    batch_parser = subparsers.add_parser("batch", help="搜索批次管理")
    batch_sub = batch_parser.add_subparsers(dest="action")

    batch_sub.add_parser("list", help="列出所有搜索批次")

    batch_get = batch_sub.add_parser("get", help="获取批次详情")
    batch_get.add_argument("id", help="批次 ID")

    batch_cands = batch_sub.add_parser("candidates", help="从批次中筛选候选人")
    batch_cands.add_argument("id", help="批次 ID")
    batch_cands.add_argument("--filter", default=None, help="过滤表达式（如 score>80）")
```

- [ ] **Step 6: Register batch handler in main()**

在 `main()` 函数的 if-elif 链中添加：

```python
    elif args.command == "batch":
        handler = {
            "list": cmd_batch_list,
            "get": cmd_batch_get,
            "candidates": cmd_batch_candidates,
        }.get(args.action)
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest scripts/test_data_manager.py -v`
Expected: All existing tests pass

- [ ] **Step 8: Commit**

```bash
git add scripts/data-manager.py
git commit -m "feat: data-manager 新增 batch list/get/candidates 命令"
```

---

### Task 6: Add dedup-merge Command to data-manager.py

**Files:**
- Modify: `scripts/data-manager.py`

- [ ] **Step 1: Write cmd_candidate_dedup_merge function**

```python
def cmd_candidate_dedup_merge(args):
    """合并两个候选人为同一自然人。

    1. primary-id 存活，secondary-id 重命名为 .merged.json
    2. sources[] 合并去重
    3. 字段冲突按逐字段策略处理
    4. enrichment_level 取两者中更高的
    """
    primary_id = args.primary_id
    secondary_id = args.secondary_id

    primary_path = os.path.join(get_data_dirs()["candidates"], f"{primary_id}.json")
    secondary_path = os.path.join(get_data_dirs()["candidates"], f"{secondary_id}.json")

    if not os.path.exists(primary_path):
        print(f"错误: 主候选人不存在: {primary_id}", file=sys.stderr)
        return 1
    if not os.path.exists(secondary_path):
        print(f"错误: 次候选人不存在: {secondary_id}", file=sys.stderr)
        return 1

    primary = read_json(primary_path)
    secondary = read_json(secondary_path)

    # 合并 sources（去重，按 channel+url）
    all_sources = primary.get("sources", []) + secondary.get("sources", [])
    seen = set()
    unique_sources = []
    for src in all_sources:
        key = (src.get("channel", ""), src.get("url", ""))
        if key not in seen:
            seen.add(key)
            unique_sources.append(src)

    # enrichment_level 取最高
    level_order = {"raw": 0, "partial": 1, "enriched": 2}
    primary_level = level_order.get(primary.get("enrichment_level", "raw"), 0)
    secondary_level = level_order.get(secondary.get("enrichment_level", "raw"), 0)
    best_level = max(primary_level, secondary_level)
    level_map = {0: "raw", 1: "partial", 2: "enriched"}

    # 合并：secondary 的非空字段补充到 primary
    merged = dict(primary)
    for key, value in secondary.items():
        if key in ("id", "created_at"):
            continue
        if key == "sources":
            continue  # 已单独处理
        if value and not merged.get(key):
            merged[key] = value

    merged["sources"] = unique_sources
    merged["enrichment_level"] = level_map[best_level]
    merged["updated_at"] = today_iso()

    # 写入 primary
    atomic_write_json(primary_path, merged)

    # 重命名 secondary 为 .merged.json
    merged_path = secondary_path.replace(".json", ".merged.json")
    os.replace(secondary_path, merged_path)

    print(json.dumps({
        "primary_id": primary_id,
        "secondary_id": secondary_id,
        "merged_sources_count": len(unique_sources),
        "enrichment_level": merged["enrichment_level"],
    }, ensure_ascii=False, indent=2))
    return 0
```

- [ ] **Step 2: Register dedup-merge in build_parser()**

在 candidate subparser 中添加：

```python
    cand_dedup_merge = cand_sub.add_parser("dedup-merge", help="合并两个候选人为同一自然人")
    cand_dedup_merge.add_argument("primary_id", help="主候选人 ID（保留）")
    cand_dedup_merge.add_argument("secondary_id", help="次候选人 ID（合并后标记为 .merged）")
```

- [ ] **Step 3: Register handler in main()**

在 candidate handler dict 中添加：

```python
"dedup-merge": cmd_candidate_dedup_merge,
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest scripts/test_data_manager.py -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/data-manager.py
git commit -m "feat: data-manager 新增 candidate dedup-merge 命令"
```

---

### Task 6.5: Create evals.json

**Files:**
- Create: `.claude/skills/platform-match/evals/evals.json`

- [ ] **Step 1: Create initial evals config**

```json
{
  "version": "1.0",
  "evals": []
}
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/platform-match/evals/evals.json
git commit -m "chore: 初始化 evals 配置文件"
```

---

### Task 6.6: Implement batch_progress.py

**Files:**
- Create: `.claude/skills/platform-match/scripts/batch_progress.py`

- [ ] **Step 1: Write batch_progress.py**

```python
#!/usr/bin/env python3
"""batch_progress.py — 批次断点恢复管理

管理模式 1 批次执行的进度，支持中断恢复。

用法:
    python batch_progress.py create --batch-id <id> --candidates <json-array>
    python batch_progress.py update --batch-id <id> --candidate-id <cand-id> --status completed
    python batch_progress.py get --batch-id <id>
    python batch_progress.py list
    python batch_progress.py resume <batch-id>
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone


SESSION_DIR = os.path.join(os.getcwd(), "data", "session")


def _progress_path(batch_id: str) -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    return os.path.join(SESSION_DIR, f"batch-progress-{batch_id}.json")


def _list_progress_files() -> list[str]:
    if not os.path.exists(SESSION_DIR):
        return []
    return [
        f for f in os.listdir(SESSION_DIR)
        if f.startswith("batch-progress-") and f.endswith(".json")
    ]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def cmd_create(args):
    """创建进度文件。"""
    candidates = json.loads(args.candidates)
    progress = {
        "batch_id": args.batch_id,
        "started_at": _now_iso(),
        "candidates": [
            {"id": c["id"], "status": "pending", "result": None}
            for c in candidates
        ],
        "summary": {"completed": 0, "failed": 0, "pending": len(candidates)},
    }
    path = _progress_path(args.batch_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    print(json.dumps(progress, ensure_ascii=False, indent=2))
    return 0


def cmd_update(args):
    """更新候选人状态。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(f"错误: 进度文件不存在: {args.batch_id}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    updated = False
    for cand in progress["candidates"]:
        if cand["id"] == args.candidate_id:
            cand["status"] = args.status
            cand["result"] = args.result
            updated = True
            break

    if not updated:
        print(f"错误: 候选人 {args.candidate_id} 不在进度文件中", file=sys.stderr)
        return 1

    # 更新摘要
    completed = sum(1 for c in progress["candidates"] if c["status"] == "completed")
    failed = sum(1 for c in progress["candidates"] if c["status"] == "failed")
    pending = sum(1 for c in progress["candidates"] if c["status"] in ("pending", "in_progress"))
    progress["summary"] = {"completed": completed, "failed": failed, "pending": pending}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)

    print(json.dumps(progress, ensure_ascii=False, indent=2))
    return 0


def cmd_get(args):
    """获取进度。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(f"错误: 进度文件不存在: {args.batch_id}", file=sys.stderr)
        return 1

    with open(path, "r", encoding="utf-8") as f:
        print(json.dumps(json.load(f), ensure_ascii=False, indent=2))
    return 0


def cmd_list(args):
    """列出所有进度文件。"""
    results = []
    for fname in _list_progress_files():
        path = os.path.join(SESSION_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            progress = json.load(f)
        results.append({
            "batch_id": progress.get("batch_id", ""),
            "started_at": progress.get("started_at", ""),
            "summary": progress.get("summary", {}),
        })
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


def cmd_resume(args):
    """获取断点恢复信息。"""
    path = _progress_path(args.batch_id)
    if not os.path.exists(path):
        print(json.dumps({"resumable": False}))
        return 0

    with open(path, "r", encoding="utf-8") as f:
        progress = json.load(f)

    # 找到需要恢复的候选人
    remaining = [
        c for c in progress["candidates"]
        if c["status"] in ("pending", "in_progress")
    ]

    if not remaining:
        print(json.dumps({"resumable": False, "message": "批次已完成"}))
        return 0

    print(json.dumps({
        "resumable": True,
        "batch_id": args.batch_id,
        "completed": progress["summary"]["completed"],
        "total": len(progress["candidates"]),
        "remaining": [{"id": c["id"], "status": c["status"]} for c in remaining],
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="批次进度管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    create_p = subparsers.add_parser("create", help="创建进度文件")
    create_p.add_argument("--batch-id", required=True)
    create_p.add_argument("--candidates", required=True, help="候选人 JSON 数组")

    update_p = subparsers.add_parser("update", help="更新候选人状态")
    update_p.add_argument("--batch-id", required=True)
    update_p.add_argument("--candidate-id", required=True)
    update_p.add_argument("--status", required=True, choices=["pending", "in_progress", "completed", "failed", "not_found"])
    update_p.add_argument("--result", default=None)

    get_p = subparsers.add_parser("get", help="获取进度")
    get_p.add_argument("--batch-id", required=True)

    subparsers.add_parser("list", help="列出所有进度")

    resume_p = subparsers.add_parser("resume", help="获取断点恢复信息")
    resume_p.add_argument("batch_id", help="批次 ID")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "create": cmd_create,
        "update": cmd_update,
        "get": cmd_get,
        "list": cmd_list,
        "resume": cmd_resume,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test create and get**

Run:
```bash
python .claude/skills/platform-match/scripts/batch_progress.py create --batch-id test-1 --candidates '[{"id":"c1"},{"id":"c2"},{"id":"c3"}]'
python .claude/skills/platform-match/scripts/batch_progress.py get --batch-id test-1
```
Expected: JSON with 3 candidates all "pending"

Run:
```bash
python .claude/skills/platform-match/scripts/batch_progress.py update --batch-id test-1 --candidate-id c1 --status completed
python .claude/skills/platform-match/scripts/batch_progress.py resume test-1
```
Expected: `{"resumable": true, "remaining": [{"id": "c2", "status": "pending"}, {"id": "c3", "status": "pending"}]}`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/platform-match/scripts/batch_progress.py
git commit -m "feat: 实现 batch_progress.py — 批次断点恢复管理"
```

---

## Phase 3: Infrastructure

### Task 7: Implement session.py

**Files:**
- Create: `.claude/skills/platform-match/scripts/session.py`

- [ ] **Step 1: Write session.py**

```python
#!/usr/bin/env python3
"""session.py — CDP 连接 + session 管理

管理浏览器 session 的连接、验证和 cookies 备份恢复。

用法:
    python session.py status
    python session.py save [--output <path>]
    python session.py verify --platform maimai
    python session.py endpoints
    python session.py restore --platform maimai [--session-file <path>]
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("错误: 需要安装 playwright。运行: pip install playwright", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

DEFAULT_CDP_URL = "http://localhost:9222"
SESSION_DIR = os.path.join(os.getcwd(), "data", "session")
MAX_COOKIE_BACKUPS = 3

PLATFORM_VERIFY_URLS = {
    "maimai": "https://maimai.cn/",
}


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _ensure_session_dir() -> str:
    os.makedirs(SESSION_DIR, exist_ok=True)
    return SESSION_DIR


def _cookie_backup_path(platform: str) -> str:
    return os.path.join(_ensure_session_dir(), f"{platform}-cookies.json")


def _list_cookie_backups(platform: str) -> list[str]:
    session_dir = _ensure_session_dir()
    backups = sorted(
        Path(session_dir).glob(f"{platform}-cookies-*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return [str(p) for p in backups]


def _rotate_cookie_backups(platform: str) -> None:
    backups = _list_cookie_backups(platform)
    while len(backups) >= MAX_COOKIE_BACKUPS:
        oldest = backups.pop(0)
        os.remove(oldest)


def _save_cookie_backup(cookies: list[dict], platform: str) -> str:
    _rotate_cookie_backups(platform)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(
        _ensure_session_dir(), f"{platform}-cookies-{timestamp}.json"
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    return path


def _output_json(data: dict | list) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# 命令实现
# ---------------------------------------------------------------------------

async def _status() -> int:
    """检查 CDP 连接状态。"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
            contexts = browser.contexts
            result = {
                "status": "ok",
                "cdp_url": DEFAULT_CDP_URL,
                "context_count": len(contexts),
            }
            if contexts:
                pages = contexts[0].pages
                result["page_count"] = len(pages)
                if pages:
                    result["current_url"] = pages[0].url
            await browser.close()
            _output_json(result)
            return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "CDP_UNREACHABLE",
            "message": f"无法连接到 Chrome CDP: {e}",
            "retryable": True,
            "hint": "请确保 Chrome 已启动: chrome --remote-debugging-port=9222",
        })
        return 1


async def _save(output: str | None) -> int:
    """导出当前浏览器 cookies。"""
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
            context = browser.contexts[0]
            cookies = await context.cookies()
            await browser.close()

        output_path = output or _cookie_backup_path("default")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        _output_json({
            "status": "ok",
            "cookie_count": len(cookies),
            "output_path": output_path,
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "SAVE_FAILED",
            "message": str(e),
            "retryable": False,
        })
        return 1


async def _verify(platform: str, mode: str = "cdp") -> int:
    """验证平台登录态。"""
    verify_url = PLATFORM_VERIFY_URLS.get(platform)
    if not verify_url:
        _output_json({
            "status": "error",
            "code": "UNKNOWN_PLATFORM",
            "message": f"不支持的平台: {platform}",
            "retryable": False,
        })
        return 1

    try:
        async with async_playwright() as p:
            if mode == "standalone":
                # 降级模式：从 cookies 恢复
                cookies_path = _cookie_backup_path(platform)
                if not os.path.exists(cookies_path):
                    _output_json({
                        "status": "error",
                        "code": "NO_COOKIES",
                        "message": "未找到 cookies 备份，请先用默认模式执行一次",
                        "retryable": False,
                    })
                    return 1

                with open(cookies_path, "r", encoding="utf-8") as f:
                    cookies = json.load(f)

                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                await context.add_cookies(cookies)
            else:
                # 默认模式：连接已有 Chrome
                browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
                context = browser.contexts[0]

            page = await context.new_page()
            await page.goto(verify_url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)

            # 检查是否被重定向到登录页
            current_url = page.url
            logged_in = "login" not in current_url.lower()

            # 检查 cookies 是否存在关键 token
            browser_cookies = await context.cookies()
            has_auth_cookie = any(
                "token" in c["name"].lower() or "session" in c["name"].lower()
                for c in browser_cookies
            )

            await browser.close()

            is_valid = logged_in or has_auth_cookie
            _output_json({
                "status": "ok" if is_valid else "error",
                "platform": platform,
                "mode": mode,
                "logged_in": logged_in,
                "has_auth_cookie": has_auth_cookie,
                "current_url": current_url,
            })
            return 0 if is_valid else 1
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "VERIFY_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


async def _endpoints() -> int:
    """列出 CDP 端点信息。"""
    try:
        import urllib.request
        resp = urllib.request.urlopen(f"{DEFAULT_CDP_URL}/json/version", timeout=5)
        data = json.loads(resp.read())
        _output_json({
            "status": "ok",
            "browser": data.get("Browser", ""),
            "user_agent": data.get("User-Agent", ""),
            "websocket_url": data.get("webSocketDebuggerUrl", ""),
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "ENDPOINTS_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


async def _restore(platform: str, session_file: str | None) -> int:
    """从 cookies 备份恢复 session。"""
    cookies_path = session_file or _cookie_backup_path(platform)

    if not os.path.exists(cookies_path):
        _output_json({
            "status": "error",
            "code": "NO_COOKIES",
            "message": f"Cookies 文件不存在: {cookies_path}",
            "retryable": False,
        })
        return 1

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()

            with open(cookies_path, "r", encoding="utf-8") as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)

            # 验证 cookies 是否有效
            verify_url = PLATFORM_VERIFY_URLS.get(platform, "")
            if verify_url:
                page = await context.new_page()
                await page.goto(verify_url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(2000)
                is_valid = "login" not in page.url.lower()
                await browser.close()

                if not is_valid:
                    _output_json({
                        "status": "error",
                        "code": "COOKIES_EXPIRED",
                        "message": "Cookies 已过期，请先用默认模式重新登录",
                        "retryable": False,
                    })
                    return 1

        _output_json({
            "status": "ok",
            "platform": platform,
            "cookies_path": cookies_path,
            "cookie_count": len(cookies),
        })
        return 0
    except Exception as e:
        _output_json({
            "status": "error",
            "code": "RESTORE_FAILED",
            "message": str(e),
            "retryable": True,
        })
        return 1


# ---------------------------------------------------------------------------
# CLI 入口
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Session 管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("status", help="检查 CDP 连接状态")

    save_p = subparsers.add_parser("save", help="导出 cookies")
    save_p.add_argument("--output", default=None, help="输出路径")

    verify_p = subparsers.add_parser("verify", help="验证平台登录态")
    verify_p.add_argument("--platform", required=True, help="平台名称")
    verify_p.add_argument("--mode", choices=["cdp", "standalone"], default="cdp")

    subparsers.add_parser("endpoints", help="列出 CDP 端点")

    restore_p = subparsers.add_parser("restore", help="从 cookies 恢复 session")
    restore_p.add_argument("--platform", required=True, help="平台名称")
    restore_p.add_argument("--session-file", default=None, help="指定 cookies 文件")

    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status": lambda: _status(),
        "save": lambda: _save(args.output),
        "verify": lambda: _verify(args.platform, args.mode),
        "endpoints": lambda: _endpoints(),
        "restore": lambda: _restore(args.platform, args.session_file),
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return await handler()


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test status command (requires Chrome running with CDP)**

Run: `python .claude/skills/platform-match/scripts/session.py status`
Expected: JSON output with status "ok" or "error" + hint

Run: `python .claude/skills/platform-match/scripts/session.py endpoints`
Expected: JSON output with browser version info

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/platform-match/scripts/session.py
git commit -m "feat: 实现 session.py — CDP 连接、cookies 备份恢复、登录态验证"
```

---

### Task 8: Implement rate_limiter.py

**Files:**
- Create: `.claude/skills/platform-match/scripts/rate_limiter.py`

- [ ] **Step 1: Write rate_limiter.py**

```python
#!/usr/bin/env python3
"""rate_limiter.py — 令牌桶限流 + 熔断机制

三层频率控制:
1. 硬性底线（不可配置）
2. 弹性控制（可配置）
3. 异常熔断（自动触发）

用法:
    python rate_limiter.py status --platform maimai
    python rate_limiter.py tick --platform maimai
    python rate_limiter.py reset
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

SESSION_DIR = os.path.join(os.getcwd(), "data", "session")
STATE_FILE = os.path.join(SESSION_DIR, "rate-limit-state.json")


@dataclass(frozen=True)
class HardLimits:
    """硬性底线（不可配置）。"""
    search_interval_min: float = 3.0   # 秒
    search_interval_max: float = 8.0
    page_interval_min: float = 2.0
    page_interval_max: float = 5.0
    continuous_op_minutes: int = 30
    continuous_pause_min: float = 60.0
    continuous_pause_max: float = 120.0


@dataclass(frozen=True)
class HeadlessLimits:
    """降级模式限流参数（更保守）。"""
    search_interval_min: float = 8.0
    search_interval_max: float = 15.0
    batch_max: int = 15
    daily_max: int = 80


@dataclass(frozen=True)
class ElasticConfig:
    """弹性控制（可配置）。"""
    batch_max: int = 30
    batch_pause_min: float = 300.0   # 5 分钟
    batch_pause_max: float = 600.0   # 10 分钟
    daily_max: int = 200


DEFAULT_LIMITS = {
    "maimai": ElasticConfig(),
}


@dataclass
class CircuitState:
    """熔断状态。"""
    is_open: bool = False
    trigger_reason: str = ""
    triggered_at: float = 0.0
    consecutive_failures: int = 0


@dataclass
class PlatformState:
    """单平台状态。"""
    last_search_at: float = 0.0
    last_page_at: float = 0.0
    continuous_op_count: int = 0
    continuous_op_start: float = 0.0
    batch_count: int = 0
    daily_count: int = 0
    daily_date: str = ""
    circuit: CircuitState = field(default_factory=CircuitState)


# ---------------------------------------------------------------------------
# 文件锁（跨平台）
# ---------------------------------------------------------------------------

def _acquire_lock(filepath: str) -> bool:
    """尝试获取文件锁。"""
    global _lock_file
    try:
        if sys.platform == "win32":
            import msvcrt
            _lock_file = open(filepath + ".lock", "w")
            msvcrt.locking(_lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        else:
            import fcntl
            _lock_file = open(filepath + ".lock", "w")
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
    except (IOError, OSError):
        return False


def _release_lock() -> None:
    """释放文件锁。"""
    global _lock_file
    try:
        if _lock_file is None:
            return
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(_lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(_lock_file.fileno(), fcntl.LOCK_UN)
        _lock_file.close()
        _lock_file = None
    except Exception:
        pass


_lock_file = None  # 模块级锁文件引用


# ---------------------------------------------------------------------------
# 状态持久化
# ---------------------------------------------------------------------------

def _ensure_session_dir() -> None:
    os.makedirs(SESSION_DIR, exist_ok=True)


def _load_state() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(state: dict) -> None:
    _ensure_session_dir()
    tmp_path = STATE_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, STATE_FILE)


def _get_platform_state(platform: str, headless: bool = False) -> PlatformState:
    state = _load_state()
    key = f"{platform}_headless" if headless else platform
    raw = state.get(key, {})
    return PlatformState(
        last_search_at=raw.get("last_search_at", 0.0),
        last_page_at=raw.get("last_page_at", 0.0),
        continuous_op_count=raw.get("continuous_op_count", 0),
        continuous_op_start=raw.get("continuous_op_start", 0.0),
        batch_count=raw.get("batch_count", 0),
        daily_count=raw.get("daily_count", 0),
        daily_date=raw.get("daily_date", ""),
        circuit=CircuitState(
            is_open=raw.get("circuit", {}).get("is_open", False),
            trigger_reason=raw.get("circuit", {}).get("trigger_reason", ""),
            triggered_at=raw.get("circuit", {}).get("triggered_at", 0.0),
            consecutive_failures=raw.get("circuit", {}).get("consecutive_failures", 0),
        ),
    )


def _save_platform_state(platform: str, ps: PlatformState, headless: bool = False) -> None:
    state = _load_state()
    key = f"{platform}_headless" if headless else platform
    state[key] = {
        "last_search_at": ps.last_search_at,
        "last_page_at": ps.last_page_at,
        "continuous_op_count": ps.continuous_op_count,
        "continuous_op_start": ps.continuous_op_start,
        "batch_count": ps.batch_count,
        "daily_count": ps.daily_count,
        "daily_date": ps.daily_date,
        "circuit": {
            "is_open": ps.circuit.is_open,
            "trigger_reason": ps.circuit.trigger_reason,
            "triggered_at": ps.circuit.triggered_at,
            "consecutive_failures": ps.circuit.consecutive_failures,
        },
    }
    _save_state(state)


# ---------------------------------------------------------------------------
# 限流逻辑
# ---------------------------------------------------------------------------

import random


def check_search(platform: str, headless: bool = False) -> dict:
    """检查是否可以执行搜索，返回等待时间。"""
    ps = _get_platform_state(platform, headless)
    hard = HardLimits()
    elastic = DEFAULT_LIMITS.get(platform, ElasticConfig())

    if headless:
        hl = HeadlessLimits()

    # 检查熔断
    if ps.circuit.is_open:
        elapsed = time.time() - ps.circuit.triggered_at
        cooldown = 1800  # 30 分钟
        if elapsed < cooldown:
            return {
                "allowed": False,
                "reason": "circuit_break",
                "wait_seconds": int(cooldown - elapsed),
                "trigger_reason": ps.circuit.trigger_reason,
            }
        else:
            # 自动恢复
            ps = PlatformState(
                last_search_at=ps.last_search_at,
                last_page_at=ps.last_page_at,
                continuous_op_count=0,
                continuous_op_start=time.time(),
                batch_count=ps.batch_count,
                daily_count=ps.daily_count,
                daily_date=ps.daily_date,
            )

    now = time.time()

    # 检查搜索间隔
    min_interval = hl.search_interval_min if headless else hard.search_interval_min
    max_interval = hl.search_interval_max if headless else hard.search_interval_max
    if ps.last_search_at > 0:
        elapsed_since_search = now - ps.last_search_at
        if elapsed_since_search < min_interval:
            return {
                "allowed": False,
                "reason": "rate_limit",
                "wait_seconds": int(min_interval - elapsed_since_search),
            }

    # 检查连续操作上限
    if ps.continuous_op_count >= 10:
        elapsed_continuous = now - ps.continuous_op_start
        if elapsed_continuous > hard.continuous_op_minutes * 60:
            pause = random.uniform(hard.continuous_pause_min, hard.continuous_pause_max)
            return {
                "allowed": False,
                "reason": "continuous_pause",
                "wait_seconds": int(pause),
            }

    # 检查批次上限
    batch_max = hl.batch_max if headless else elastic.batch_max
    if ps.batch_count >= batch_max:
        pause = random.uniform(elastic.batch_pause_min, elastic.batch_pause_max)
        return {
            "allowed": False,
            "reason": "batch_limit",
            "wait_seconds": int(pause),
        }

    # 检查每日上限
    daily_max = hl.daily_max if headless else elastic.daily_max
    today = time.strftime("%Y-%m-%d")
    if ps.daily_date == today and ps.daily_count >= daily_max:
        return {
            "allowed": False,
            "reason": "daily_limit",
            "wait_seconds": 86400,
        }

    # 计算随机延迟
    if ps.last_search_at > 0:
        delay = random.uniform(min_interval, max_interval)
    else:
        delay = 0

    return {"allowed": True, "delay_seconds": delay}


def record_search(platform: str, headless: bool = False) -> None:
    """记录一次搜索操作。"""
    if not _acquire_lock(STATE_FILE):
        return
    try:
        ps = _get_platform_state(platform, headless)
        now = time.time()
        today = time.strftime("%Y-%m-%d")

        ps = PlatformState(
            last_search_at=now,
            last_page_at=ps.last_page_at,
            continuous_op_count=ps.continuous_op_count + 1,
            continuous_op_start=ps.continuous_op_start if ps.continuous_op_start > 0 else now,
            batch_count=ps.batch_count + 1,
            daily_count=ps.daily_count + 1 if ps.daily_date == today else 1,
            daily_date=today,
            circuit=CircuitState(
                is_open=False,
                trigger_reason="",
                triggered_at=0.0,
                consecutive_failures=0,
            ),
        )
        _save_platform_state(platform, ps, headless)
    finally:
        _release_lock()


def record_page(platform: str, headless: bool = False) -> None:
    """记录一次翻页操作。"""
    if not _acquire_lock(STATE_FILE):
        return
    try:
        ps = _get_platform_state(platform, headless)
        ps = PlatformState(
            last_search_at=ps.last_search_at,
            last_page_at=time.time(),
            continuous_op_count=ps.continuous_op_count + 1,
            continuous_op_start=ps.continuous_op_start,
            batch_count=ps.batch_count,
            daily_count=ps.daily_count,
            daily_date=ps.daily_date,
            circuit=ps.circuit,
        )
        _save_platform_state(platform, ps, headless)
    finally:
        _release_lock()


def trigger_circuit_break(platform: str, reason: str, headless: bool = False) -> None:
    """触发熔断。"""
    if not _acquire_lock(STATE_FILE):
        return
    try:
        ps = _get_platform_state(platform, headless)
        ps = PlatformState(
            last_search_at=ps.last_search_at,
            last_page_at=ps.last_page_at,
            continuous_op_count=ps.continuous_op_count,
            continuous_op_start=ps.continuous_op_start,
            batch_count=ps.batch_count,
            daily_count=ps.daily_count,
            daily_date=ps.daily_date,
            circuit=CircuitState(
                is_open=True,
                trigger_reason=reason,
                triggered_at=time.time(),
                consecutive_failures=ps.circuit.consecutive_failures + 1,
            ),
        )
        _save_platform_state(platform, ps, headless)
    finally:
        _release_lock()


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------

def cmd_status(args):
    ps = _get_platform_state(args.platform, args.headless)
    result = {
        "platform": args.platform,
        "headless": args.headless,
        "last_search_at": ps.last_search_at,
        "batch_count": ps.batch_count,
        "daily_count": ps.daily_count,
        "daily_date": ps.daily_date,
        "circuit_open": ps.circuit.is_open,
    }
    if ps.circuit.is_open:
        result["circuit_reason"] = ps.circuit.trigger_reason
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_tick(args):
    check = check_search(args.platform, args.headless)
    print(json.dumps(check, ensure_ascii=False, indent=2))
    return 0


def cmd_reset(args):
    if not _acquire_lock(STATE_FILE):
        print("错误: 无法获取文件锁", file=sys.stderr)
        return 1
    try:
        _save_state({})
        print(json.dumps({"status": "ok", "message": "已重置所有限流状态"}, ensure_ascii=False, indent=2))
        return 0
    finally:
        _release_lock()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="限流管理 CLI")
    subparsers = parser.add_subparsers(dest="command")

    status_p = subparsers.add_parser("status", help="查看限流状态")
    status_p.add_argument("--platform", required=True, help="平台名称")
    status_p.add_argument("--headless", action="store_true")

    tick_p = subparsers.add_parser("tick", help="检查是否可以执行操作")
    tick_p.add_argument("--platform", required=True, help="平台名称")
    tick_p.add_argument("--headless", action="store_true")

    subparsers.add_parser("reset", help="重置所有限流状态")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "status": cmd_status,
        "tick": cmd_tick,
        "reset": cmd_reset,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Test rate limiter**

Run: `python .claude/skills/platform-match/scripts/rate_limiter.py status --platform maimai`
Expected: JSON with initial state (all zeros)

Run: `python .claude/skills/platform-match/scripts/rate_limiter.py tick --platform maimai`
Expected: `{"allowed": true, "delay_seconds": 0}`

Run: `python .claude/skills/platform-match/scripts/rate_limiter.py reset`
Expected: `{"status": "ok", "message": "已重置所有限流状态"}`

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/platform-match/scripts/rate_limiter.py
git commit -m "feat: 实现 rate_limiter.py — 令牌桶限流、三层控制、异常熔断"
```

---

## Phase 4: Adapter & Search

### Task 9: Implement base.py (PlatformAdapter Protocol)

**Files:**
- Create: `.claude/skills/platform-match/scripts/adapters/base.py`

- [ ] **Step 1: Write base.py**

```python
"""base.py — PlatformAdapter 协议与类型定义

所有平台适配器必须实现 PlatformAdapter 协议。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Any


@dataclass(frozen=True)
class SearchParams:
    """搜索参数。"""
    query: str
    city: str | None = None
    page: int = 1
    page_size: int = 30


@dataclass
class SearchError:
    """搜索错误。"""
    code: str
    message: str
    retryable: bool = False
    trigger_reason: str | None = None


@dataclass
class SearchResult:
    """搜索结果。"""
    items: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    page: int = 1
    has_more: bool = False
    error: SearchError | None = None


@dataclass
class CandidateData:
    """从 API 获取的候选人原始数据。"""
    raw: dict[str, Any]
    platform_id: str
    detail_url: str


class PlatformAdapter(Protocol):
    """平台适配器协议。

    新增平台只需创建适配器文件并实现此协议。
    """

    platform_name: str

    def build_search_params(
        self,
        candidate: dict | None = None,
        jd: dict | None = None,
        user_input: dict | None = None,
    ) -> list[SearchParams]:
        """构建搜索参数列表。

        Args:
            candidate: 已有候选人信息（模式 1）
            jd: JD 信息（模式 2）
            user_input: 用户自然语言输入（模式 3）

        Returns:
            搜索参数列表（可能有多组搜索策略）
        """
        ...

    def map_to_schema(self, api_data: dict) -> dict:
        """将 API 原始数据映射为 candidate.schema 格式。

        Args:
            api_data: API 返回的候选人数据

        Returns:
            符合 candidate.schema 的字段字典
        """
        ...

    async def search(
        self,
        page: Any,  # playwright Page
        params: SearchParams,
    ) -> SearchResult:
        """执行搜索。

        Args:
            page: Playwright Page 对象（已连接到浏览器）
            params: 搜索参数

        Returns:
            搜索结果
        """
        ...

    async def get_detail(
        self,
        page: Any,  # playwright Page
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。

        Args:
            page: Playwright Page 对象
            platform_id: 平台用户 ID

        Returns:
            候选人详情数据，不存在则返回 None
        """
        ...
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/platform-match/scripts/adapters/base.py
git commit -m "feat: 定义 PlatformAdapter 协议与核心类型"
```

---

### Task 10: Implement maimai.py (MaimaiAdapter)

**Files:**
- Create: `.claude/skills/platform-match/scripts/adapters/maimai.py`

- [ ] **Step 1: Write maimai.py**

```python
"""maimai.py — 脉脉平台适配器

通过 Playwright 拦截脉脉搜索 API 请求获取候选人数据。
不使用表单填充，而是直接构造 API 请求。
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import (
    CandidateData,
    PlatformAdapter,
    SearchError,
    SearchResult,
    SearchParams,
)


# ---------------------------------------------------------------------------
# 脉脉搜索 API 配置
# ---------------------------------------------------------------------------

SEARCH_API_URL = "https://maimai.cn/api/pc/search/contacts"
DETAIL_API_URL = "https://maimai.cn/api/pc/u/"

# API 字段 → candidate.schema 映射
# 详见 references/maimai/field-mapping.md
HUNTING_STATUS_MAP = {
    5: "在职-看机会",
    0: "在职-不看",
    1: "在职-不看",
    2: "在职-不看",
    3: "在职-不看",
    4: "在职-不看",
}

EDUCATION_MAP = {
    1: "本科",
    2: "硕士",
    3: "博士",
    4: "大专",
}


def _parse_work_years(raw: str) -> int:
    """从 '4年7个月' 提取年数取整。"""
    if not raw:
        return 0
    match = re.search(r"(\d+)年", raw)
    return int(match.group(1)) if match else 0


def _normalize_period(raw: str) -> str:
    """将 '2021-09-01至今' 转换为 '2021-09 - 至今'。"""
    if not raw:
        return raw
    parts = raw.split("至今")
    if len(parts) == 2:
        start = parts[0].rsplit("-", 1)[0] if "-" in parts[0] else parts[0]
        return f"{start} - 至今"
    # 处理正常范围
    parts = raw.split("至")
    if len(parts) == 2:
        start = parts[0].rsplit("-", 1)[0] if "-" in parts[0] else parts[0]
        end = parts[1].rsplit("-", 1)[0] if "-" in parts[1] else parts[1]
        return f"{start} - {end}"
    return raw


class MaimaiAdapter:
    """脉脉平台适配器。"""

    platform_name: str = "maimai"

    def build_search_params(
        self,
        candidate: dict | None = None,
        jd: dict | None = None,
        user_input: dict | None = None,
    ) -> list[SearchParams]:
        """构建搜索参数。

        模式 1（候选丰富）: 双路径搜索
          路径 A: "{name} {current_company}"
          路径 B: "{name} {current_title}"

        模式 2（JD 驱动）: 从 JD 提取关键词
          由 SKILL.md 编排层负责提取，此处接收预构建的参数

        模式 3（对话式）: 用户直接提供
        """
        params: list[SearchParams] = []

        if candidate:
            name = candidate.get("name", "")
            company = candidate.get("current_company", "")
            title = candidate.get("current_title", "")

            # 路径 A: name + company
            if name and company:
                params.append(SearchParams(query=f"{name} {company}"))

            # 路径 B: name + title
            if name and title:
                params.append(SearchParams(query=f"{name} {title}"))

            # 最简搜索: 仅 name
            if name and not params:
                params.append(SearchParams(query=name))

        elif jd:
            # JD 驱动模式：由 SKILL.md 预构建搜索参数
            # 这里接收 user_input 中的预构建参数
            pass

        if user_input and "query" in user_input:
            params.append(SearchParams(
                query=user_input["query"],
                city=user_input.get("city"),
            ))

        return params

    def map_to_schema(self, api_data: dict) -> dict:
        """将脉脉 API 数据映射为 candidate.schema 格式。"""
        result: dict[str, Any] = {}

        # 基本信息
        result["name"] = api_data.get("name", "")
        result["gender"] = {
            1: "男", 2: "女"
        }.get(api_data.get("gender_str"), "未提及")
        result["age"] = api_data.get("age")
        result["city"] = api_data.get("city", "")
        result["current_company"] = api_data.get("company", "")
        result["current_title"] = api_data.get("position", "")

        # 学历
        sdegree = api_data.get("sdegree")
        if sdegree:
            result["education"] = EDUCATION_MAP.get(sdegree, "本科")

        # 工作年限
        worktime = api_data.get("worktime", "")
        result["work_years"] = _parse_work_years(worktime)

        # 求职状态
        hunting = api_data.get("hunting_status")
        if hunting is not None:
            result["status"] = HUNTING_STATUS_MAP.get(hunting, "在职-不看")

        # 活跃状态
        active = api_data.get("active_state")
        if active:
            result["active_state"] = active

        # 工作经历
        experiences = api_data.get("exp", [])
        if experiences:
            result["work_experience"] = [
                {
                    "period": _normalize_period(exp.get("v", "")),
                    "company": exp.get("company", ""),
                    "title": exp.get("position", ""),
                    "description": exp.get("description", ""),
                }
                for exp in experiences
                if exp.get("company") or exp.get("position")
            ]

        # 教育经历
        educations = api_data.get("edu", [])
        if educations:
            result["education_experience"] = [
                {
                    "period": _normalize_period(edu.get("v", "")),
                    "school": edu.get("school", ""),
                    "major": edu.get("major", ""),
                    "description": edu.get("sdegree", ""),
                }
                for edu in educations
                if edu.get("school") or edu.get("major")
            ]

        # 技能标签（合并去重）
        tags = set()
        for tag in api_data.get("exp_tags", []) or []:
            if tag:
                tags.add(tag)
        for tag in api_data.get("tag_list", []) or []:
            if tag:
                tags.add(tag)
        if tags:
            result["skill_tags"] = sorted(tags)

        # 期望信息
        prefs = api_data.get("job_preferences", {})
        if prefs:
            regions = prefs.get("regions", [])
            if regions:
                result["expected_city"] = regions
            positions = prefs.get("positions", [])
            if positions:
                result["expected_title"] = positions[0]
            salary = prefs.get("salary", "")
            if salary:
                result["expected_salary"] = salary

        # 项目经历
        projects = api_data.get("user_project", [])
        if projects:
            result["project_experience"] = [
                {
                    "name": p.get("name", ""),
                    "period": _normalize_period(p.get("period", "")),
                    "role": p.get("role", ""),
                    "description": p.get("description", ""),
                }
                for p in projects
                if p.get("name")
            ]

        # Source 信息
        uid = api_data.get("id", "")
        detail_url = api_data.get("detail_url", "")
        if uid or detail_url:
            result["_source"] = {
                "channel": "maimai",
                "url": detail_url or f"https://maimai.cn/u/{uid}",
                "platform_id": str(uid) if uid else None,
                "enrichment_level": "enriched",
            }

        return result

    async def search(
        self,
        page: Any,
        params: SearchParams,
    ) -> SearchResult:
        """通过 API 拦截执行搜索。

        使用 route 拦截搜索 API 请求，构造并发送自定义请求。
        """
        try:
            # 构造 API 请求参数
            request_data = {
                "query": params.query,
                "page": params.page,
                "pagesize": params.page_size,
            }

            # 使用 page.evaluate 发送 API 请求（利用浏览器已有的登录态）
            response = await page.evaluate(
                """async ({url, data}) => {
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify(data),
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                {"url": SEARCH_API_URL, "data": request_data},
            )

            if response["status"] != 200:
                return SearchResult(
                    error=SearchError(
                        code="API_ERROR",
                        message=f"API 返回状态码 {response['status']}",
                        retryable=response["status"] in (429, 502, 503),
                    )
                )

            body = json.loads(response["body"])
            data = body.get("data", {})

            items = data.get("contacts", []) or data.get("list", []) or []
            total = data.get("total", len(items))
            has_more = params.page * params.page_size < total

            return SearchResult(
                items=items,
                total=total,
                page=params.page,
                has_more=has_more,
            )
        except json.JSONDecodeError as e:
            return SearchResult(
                error=SearchError(
                    code="PARSE_ERROR",
                    message=f"API 响应解析失败: {e}",
                    retryable=True,
                )
            )
        except Exception as e:
            return SearchResult(
                error=SearchError(
                    code="SEARCH_FAILED",
                    message=str(e),
                    retryable=True,
                )
            )

    async def get_detail(
        self,
        page: Any,
        platform_id: str,
    ) -> CandidateData | None:
        """获取候选人详情。"""
        try:
            response = await page.evaluate(
                """async ({url}) => {
                    const resp = await fetch(url, {
                        credentials: 'include',
                    });
                    return {
                        status: resp.status,
                        body: await resp.text(),
                    };
                }""",
                {"url": f"{DETAIL_API_URL}{platform_id}"},
            )

            if response["status"] != 200:
                return None

            body = json.loads(response["body"])
            data = body.get("data", body)

            if not data:
                return None

            return CandidateData(
                raw=data,
                platform_id=platform_id,
                detail_url=f"https://maimai.cn/u/{platform_id}",
            )
        except Exception:
            return None
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/platform-match/scripts/adapters/maimai.py
git commit -m "feat: 实现 MaimaiAdapter — API 拦截搜索、字段映射、详情获取"
```

---

### Task 11: Implement search.py

**Files:**
- Create: `.claude/skills/platform-match/scripts/search.py`

- [ ] **Step 1: Write search.py**

```python
#!/usr/bin/env python3
"""search.py — API 搜索 + 分页 + 结果解析

封装搜索流程：连接浏览器 → 执行搜索 → 分页获取 → 返回结果。

用法:
    python search.py search --platform maimai --query "张三 阿里巴巴" [--pages 3]
    python search.py search --platform maimai --params-file <path>
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Any

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("错误: 需要安装 playwright。运行: pip install playwright", file=sys.stderr)
    sys.exit(1)

# 添加父目录到 path 以支持导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.base import SearchParams, SearchResult  # noqa: E402
from adapters.maimai import MaimaiAdapter  # noqa: E402
from rate_limiter import check_search, record_search, record_page, trigger_circuit_break  # noqa: E402


DEFAULT_CDP_URL = "http://localhost:9222"
DEFAULT_PAGES = 3
DEFAULT_PAGE_SIZE = 30

ADAPTERS = {
    "maimai": MaimaiAdapter(),
}


async def _do_search(
    platform: str,
    query: str,
    pages: int = DEFAULT_PAGES,
    headless: bool = False,
) -> dict:
    """执行搜索并返回所有页结果。"""
    adapter = ADAPTERS.get(platform)
    if not adapter:
        return {
            "status": "error",
            "code": "UNKNOWN_PLATFORM",
            "message": f"不支持的平台: {platform}",
            "retryable": False,
        }

    # 限流检查
    check = check_search(platform, headless)
    if not check["allowed"]:
        return {
            "status": "error",
            "code": "RATE_LIMITED",
            "message": f"触发限流: {check['reason']}",
            "retryable": True,
            "wait_seconds": check.get("wait_seconds", 0),
        }

    # 随机延迟
    delay = check.get("delay_seconds", 0)
    if delay > 0:
        await asyncio.sleep(delay)

    try:
        async with async_playwright() as p:
            if headless:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                # TODO: 从 cookies 恢复（调用 session.py restore）
            else:
                browser = await p.chromium.connect_over_cdp(DEFAULT_CDP_URL)
                context = browser.contexts[0]

            page = await context.new_page()
            params = SearchParams(query=query, page_size=DEFAULT_PAGE_SIZE)

            all_items = []
            total = 0

            for page_num in range(1, pages + 1):
                params = SearchParams(
                    query=query,
                    page=page_num,
                    page_size=DEFAULT_PAGE_SIZE,
                )

                result = await adapter.search(page, params)

                if result.error:
                    if result.error.code in ("CAPTCHA", "FORBIDDEN"):
                        trigger_circuit_break(
                            platform,
                            result.error.code,
                            headless,
                        )
                        return {
                            "status": "error",
                            "code": "CIRCUIT_BREAK",
                            "message": f"触发熔断: {result.error.message}",
                            "retryable": False,
                            "trigger_reason": result.error.code,
                        }

                    # P1 错误：重试一次
                    await asyncio.sleep(2)
                    result = await adapter.search(page, params)
                    if result.error:
                        return {
                            "status": "error",
                            "code": result.error.code,
                            "message": result.error.message,
                            "retryable": result.error.retryable,
                        }

                all_items.extend(result.items)
                total = result.total

                # 翻页限流
                if result.has_more and page_num < pages:
                    page_check = check_search(platform, headless)
                    page_delay = page_check.get("delay_seconds", 2)
                    await asyncio.sleep(max(page_delay, 2))
                    record_page(platform, headless)

            record_search(platform, headless)

            await browser.close()

            return {
                "status": "ok",
                "data": {
                    "items": all_items,
                    "total": total,
                    "pages_fetched": pages,
                    "query": query,
                    "platform": platform,
                },
            }

    except Exception as e:
        trigger_circuit_break(platform, str(e), headless)
        return {
            "status": "error",
            "code": "SEARCH_EXCEPTION",
            "message": str(e),
            "retryable": True,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

async def _cmd_search(args):
    result = await _do_search(
        platform=args.platform,
        query=args.query,
        pages=args.pages,
        headless=args.headless,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ok" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="搜索 CLI")
    subparsers = parser.add_subparsers(dest="command")

    search_p = subparsers.add_parser("search", help="执行搜索")
    search_p.add_argument("--platform", required=True, help="平台名称")
    search_p.add_argument("--query", required=True, help="搜索关键词")
    search_p.add_argument("--pages", type=int, default=DEFAULT_PAGES, help="搜索页数")
    search_p.add_argument("--headless", action="store_true")

    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {"search": lambda: _cmd_search(args)}
    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return await handler()


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/platform-match/scripts/search.py
git commit -m "feat: 实现 search.py — API 搜索、分页、限流集成、熔断处理"
```

---

### Task 12: Implement enrich.py

**Files:**
- Create: `.claude/skills/platform-match/scripts/enrich.py`

- [ ] **Step 1: Write enrich.py**

```python
#!/usr/bin/env python3
"""enrich.py — 字段映射 + 逐字段冲突合并 + 写入

负责将 API 搜索结果映射为 candidate.schema 格式，
处理多源数据冲突，并通过 data-manager.py 写入候选人库。

用法:
    python enrich.py map --platform maimai --api-data <json-string>
    python enrich.py merge --candidate-id <id> --new-data <json-file>
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# 逐字段冲突策略
# ---------------------------------------------------------------------------

# 最新来源优先
LATEST_FIRST_FIELDS = {
    "current_company", "current_title", "expected_salary",
    "expected_city", "status", "active_state",
}

# 首次来源优先（已有则不覆盖）
FIRST_SOURCE_FIELDS = {
    "education_experience",
}

# 合并去重
MERGE_DEDUP_FIELDS = {
    "skill_tags", "work_experience",
}

# 多数投票
MAJORITY_VOTE_FIELDS = {
    "age", "gender",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def merge_fields(existing: dict, new_data: dict) -> dict:
    """按逐字段冲突策略合并新数据到已有候选人。

    Args:
        existing: 已有候选人数据
        new_data: 新获取的数据（已映射为 schema 格式）

    Returns:
        合并后的候选人数据
    """
    result = dict(existing)

    for key, value in new_data.items():
        if key.startswith("_"):
            continue  # 跳过内部字段（如 _source）

        if value is None or value == "" or value == []:
            continue  # 跳过空值

        if key in LATEST_FIRST_FIELDS:
            result[key] = value

        elif key in FIRST_SOURCE_FIELDS:
            if not result.get(key):
                result[key] = value

        elif key in MERGE_DEDUP_FIELDS:
            existing_val = result.get(key, [])
            if isinstance(existing_val, list) and isinstance(value, list):
                # 合并去重
                if key == "skill_tags":
                    merged = list(set(existing_val) | set(value))
                    result[key] = sorted(merged)
                elif key == "work_experience":
                    # 按公司+时间段去重
                    existing_keys = {
                        (e.get("company", ""), e.get("period", ""))
                        for e in existing_val
                    }
                    merged = list(existing_val)
                    for item in value:
                        item_key = (item.get("company", ""), item.get("period", ""))
                        if item_key not in existing_keys:
                            merged.append(item)
                            existing_keys.add(item_key)
                    result[key] = merged

        elif key in MAJORITY_VOTE_FIELDS:
            # 简化实现：新值直接覆盖（多数投票需要多源数据）
            if not result.get(key):
                result[key] = value

        else:
            # 默认：已有为空则写入
            if not result.get(key):
                result[key] = value

    result["updated_at"] = _now_iso()
    return result


def append_source(existing: dict, source: dict) -> dict:
    """追加 source 到 sources 数组（去重）。

    Args:
        existing: 已有候选人数据
        source: 要追加的 source 对象

    Returns:
        更新后的候选人数据
    """
    result = dict(existing)
    sources = list(result.get("sources", []))

    # 按 channel + platform_id 去重
    new_key = (source.get("channel", ""), source.get("platform_id", ""))
    existing_keys = {
        (s.get("channel", ""), s.get("platform_id", ""))
        for s in sources
    }

    if new_key not in existing_keys or not new_key[1]:
        sources.append(source)

    result["sources"] = sources
    return result


def enrich_enrichment_level(existing: dict) -> dict:
    """提升 enrichment_level（只升不降）。"""
    result = dict(existing)
    level_order = {"raw": 0, "partial": 1, "enriched": 2}
    current = level_order.get(result.get("enrichment_level", "raw"), 0)

    # 从 sources 推断最高级别
    for src in result.get("sources", []):
        src_level = level_order.get(src.get("enrichment_level", "raw"), 0)
        current = max(current, src_level)

    level_map = {0: "raw", 1: "partial", 2: "enriched"}
    result["enrichment_level"] = level_map[current]
    return result


# ---------------------------------------------------------------------------
# data-manager.py 交互
# ---------------------------------------------------------------------------

def _get_data_manager_path() -> str:
    """获取 data-manager.py 路径。"""
    # 从 scripts/ 目录的上一级查找
    return os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "data-manager.py",
    )


def _run_data_manager(*args: str) -> dict:
    """调用 data-manager.py 并返回 JSON 输出。"""
    dm_path = _get_data_manager_path()
    if not os.path.exists(dm_path):
        return {"error": f"data-manager.py 不存在: {dm_path}"}

    result = subprocess.run(
        [sys.executable, dm_path, *args],
        capture_output=True,
        text=True,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )

    if result.returncode != 0:
        return {"error": result.stderr.strip()}

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw_output": result.stdout}


# ---------------------------------------------------------------------------
# CLI 命令
# ---------------------------------------------------------------------------

def cmd_map(args):
    """将 API 数据映射为 schema 格式。"""
    from adapters.maimai import MaimaiAdapter

    adapter = MaimaiAdapter()

    try:
        api_data = json.loads(args.api_data)
    except json.JSONDecodeError as e:
        print(json.dumps({
            "status": "error",
            "code": "INVALID_JSON",
            "message": f"JSON 解析失败: {e}",
        }, ensure_ascii=False, indent=2))
        return 1

    mapped = adapter.map_to_schema(api_data)
    print(json.dumps({
        "status": "ok",
        "data": mapped,
    }, ensure_ascii=False, indent=2))
    return 0


def cmd_merge(args):
    """合并新数据到已有候选人。"""
    candidate_id = args.candidate_id

    # 读取已有候选人
    existing = _run_data_manager("candidate", "get", candidate_id)
    if "error" in existing:
        print(json.dumps({
            "status": "error",
            "code": "CANDIDATE_NOT_FOUND",
            "message": existing["error"],
        }, ensure_ascii=False, indent=2))
        return 1

    # 读取新数据
    with open(args.new_data, "r", encoding="utf-8") as f:
        new_data = json.load(f)

    # 提取 source 信息
    source = new_data.pop("_source", None)

    # 合并字段
    merged = merge_fields(existing, new_data)

    # 追加 source
    if source:
        merged = append_source(merged, source)

    # 提升 enrichment_level
    merged = enrich_enrichment_level(merged)

    # 写入临时文件
    tmp_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"_tmp_update_{candidate_id}.json",
    )
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    # 调用 data-manager update
    result = _run_data_manager("candidate", "update", candidate_id, tmp_file)

    # 清理临时文件
    try:
        os.remove(tmp_file)
    except OSError:
        pass

    if "error" in result:
        print(json.dumps({
            "status": "error",
            "code": "UPDATE_FAILED",
            "message": result["error"],
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "status": "ok",
        "candidate_id": candidate_id,
        "fields_updated": list(set(new_data.keys()) - {"_source"}),
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="数据丰富 CLI")
    subparsers = parser.add_subparsers(dest="command")

    map_p = subparsers.add_parser("map", help="将 API 数据映射为 schema 格式")
    map_p.add_argument("--platform", required=True, help="平台名称")
    map_p.add_argument("--api-data", required=True, help="API 原始数据 (JSON 字符串)")

    merge_p = subparsers.add_parser("merge", help="合并新数据到已有候选人")
    merge_p.add_argument("--candidate-id", required=True, help="候选人 ID")
    merge_p.add_argument("--new-data", required=True, help="新数据 JSON 文件路径")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "map": cmd_map,
        "merge": cmd_merge,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/platform-match/scripts/enrich.py
git commit -m "feat: 实现 enrich.py — 逐字段冲突合并、source 追加、enrichment_level 提升"
```

---

## Phase 5: Reference Materials

### Task 13: Create Reference Documents

**Files:**
- Create: `.claude/skills/platform-match/references/maimai/api-reference.md`
- Create: `.claude/skills/platform-match/references/maimai/field-mapping.md`
- Create: `.claude/skills/platform-match/references/maimai/anti-detect.md`
- Create: `.claude/skills/platform-match/references/matching-strategy.md`

- [ ] **Step 1: Create api-reference.md**

```markdown
# 脉脉搜索 API 参考

## 搜索 API

- **URL**: `https://maimai.cn/api/pc/search/contacts`
- **Method**: POST
- **Content-Type**: application/json
- **认证**: cookies（需先登录）

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |
| page | int | 否 | 页码，默认 1 |
| pagesize | int | 否 | 每页条数，默认 30 |

### 响应结构

```json
{
  "code": 0,
  "data": {
    "contacts": [...],
    "total": 100,
    "has_more": true
  }
}
```

### contacts[] 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 脉脉 uid |
| name | string | 姓名 |
| gender_str | int | 性别（1=男, 2=女） |
| age | int | 年龄 |
| city | string | 城市 |
| company | string | 当前公司 |
| position | string | 当前职位 |
| sdegree | int | 最高学历（1=本科, 2=硕士, 3=博士, 4=大专） |
| worktime | string | 工作年限（如 "4年7个月"） |
| hunting_status | int | 求职状态（5=看机会, 0/1-4=不看） |
| active_state | string | 活跃状态 |
| exp[] | array | 工作经历 |
| edu[] | array | 教育经历 |
| exp_tags[] | array | 经验标签 |
| tag_list[] | array | 技能标签 |
| job_preferences | object | 求职意向 |
| detail_url | string | 个人主页 URL |
| user_project[] | array | 项目经历 |

> 注：以上字段基于现有数据推测，需在登录后实测确认完整枚举值。实施时需校准。

## 反爬信号

| 信号 | 处理 |
|------|------|
| 返回验证码页面 | 触发熔断 |
| HTTP 403 | 触发熔断 |
| 连续 3 次空结果 | 触发熔断 |
| 响应 > 10s | 触发熔断 |
```

- [ ] **Step 2: Create field-mapping.md**

```markdown
# 脉脉 API 字段 → candidate.schema 映射表

## 基本信息映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| name | name | 直接映射 |
| gender_str | gender | 1→"男", 2→"女", 其他→"未提及" |
| age | age | 直接映射 |
| city | city | 直接映射 |
| company | current_company | 直接映射 |
| position | current_title | 直接映射 |
| sdegree | education | 1→"本科", 2→"硕士", 3→"博士", 4→"大专" |
| worktime | work_years | "4年7个月" → 提取数字取整 |
| hunting_status | status | 见下方完整映射表 |
| active_state | active_state | 直接映射 |

## 经历映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| exp[].company | work_experience[].company | 直接映射 |
| exp[].position | work_experience[].title | 直接映射 |
| exp[].v | work_experience[].period | "2021-09-01至今" → "2021-09 - 至今" |
| exp[].description | work_experience[].description | 直接映射 |
| edu[].school | education_experience[].school | 直接映射 |
| edu[].major | education_experience[].major | 直接映射 |
| edu[].v | education_experience[].period | 同上格式转换 |
| edu[].sdegree | education_experience[].description | 附加学历信息 |
| user_project[] | project_experience | 直接映射（name, period, role, description） |

## 意向映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| job_preferences.regions[] | expected_city | 数组直接映射 |
| job_preferences.positions[] | expected_title | 取第一个 |
| job_preferences.salary | expected_salary | 直接映射 |

## 标签映射

| 脉脉 API 字段 | candidate.schema 字段 | 转换逻辑 |
|---|---|---|
| exp_tags[] + tag_list[] | skill_tags | 合并去重 |

## 来源映射

| 脉脉 API 字段 | sources[] 字段 | 转换逻辑 |
|---|---|---|
| id | platform_id | 直接映射 |
| detail_url | url | 直接映射，无则构造 `https://maimai.cn/u/{id}` |
| — | channel | 固定 "maimai" |
| — | found_at | 搜索时间（ISO 8601） |
| — | enrichment_level | 固定 "enriched" |

## hunting_status 完整映射

| 脉脉值 | candidate status | 说明 |
|---|---|---|
| 5 | "在职-看机会" | 主动求职 |
| 0, 1, 2, 3, 4 | "在职-不看" | 未主动求职 |
| 待确认 | "离职-求职中" | 已离职 |
| 无此字段 | 不更新 | API 未返回时不覆盖 |

> 注：完整枚举值需在登录后实测确认。
```

- [ ] **Step 3: Create anti-detect.md**

```markdown
# 反检测策略

## 默认模式（CDP 连接）

使用真实 Chrome 浏览器，零检测风险：
- 用户手动启动 Chrome（已登录）
- 通过 CDP 协议连接
- 所有请求来自真实浏览器环境
- 无需任何反检测措施

## 降级模式（Headless + Stealth）

使用 Playwright stealth 模式：
- `playwright.chromium.launch(headless=True)` + stealth 插件
- 从 cookies 备份恢复登录态
- 更保守的速率控制（8-15s 间隔）
- 更低的操作上限（单批 15，每日 80）

### 检测风险

| 风险等级 | 场景 | 缓解措施 |
|---------|------|---------|
| 低 | 正常搜索浏览 | stealth 插件 + 随机延迟 |
| 中 | 大量翻页 | 增加间隔 + 降低并发 |
| 高 | 频繁搜索同一关键词 | 轮换关键词顺序 |

### 降级模式注意事项

1. **cookies 过期**：备份 cookies 有时效性，过期后需重新用默认模式登录
2. **IP 风控**：同一 IP 大量请求可能触发风控
3. **操作频率**：降级模式使用更保守的默认参数
```

- [ ] **Step 4: Create matching-strategy.md**

```markdown
# 多匹配判定策略

## 身份判定（候选丰富模式）

### 双路径搜索

```
路径 A: query = "{name} {current_company}"
  → 精确度高，但如果人已跳槽可能搜不到

路径 B: query = "{name} {current_title}"
  → 覆盖面广，但同名干扰多

执行顺序: 先 A → 有结果用 A → 无结果走 B → 都无 → 标记"未找到"
```

### 判定流程

#### 步骤 1: 精确过滤
- company 完全匹配（含别名，见 `rules/company-aliases.json`）
- AND position 相似度 > 70%
- 剩余 ≤ 1 → 自动选取（仅限置信度 ≥ 95%）

#### 步骤 2: 模糊匹配
- company 匹配 + education 重叠 OR work_experience 时间重叠
- 剩余 ≤ 1 → 向用户建议，待确认

#### 步骤 3: 多维度评分

| 维度 | 分值 | 说明 |
|------|------|------|
| company 匹配度 | 0-30 | 完全匹配=30, 别名匹配=25, 部分匹配=15 |
| position 匹配度 | 0-25 | 完全匹配=25, 相似>70%=20, 部分匹配=10 |
| education 匹配度 | 0-20 | 学校完全匹配=20, 学历匹配=10 |
| city 匹配度 | 0-10 | 完全匹配=10, 同省=5 |
| skill_tags 重叠度 | 0-15 | 按重叠比例计算 |

+ rules/identity-rules.md 中匹配到的规则加分

判定：
- 差距 > 20 → 自动选取（≥ 95%）
- 否则 → 向用户建议最优人选，待确认

#### 步骤 4: 置信度 < 70%
- 展示 Top 3 供用户选择，不给出建议

### 原则
只有"几乎确定是同一个人"（≥ 95%）才自动选，其余一律人控。

## JD 匹配（JD 驱动模式）

### 评分维度

| 维度 | 分值 | 说明 |
|------|------|------|
| 职位匹配度 | 0-30 | 当前职位与 JD 目标岗位的匹配 |
| 技能重叠度 | 0-25 | 技能标签与 JD 要求的重叠 |
| 行业经验 | 0-20 | 行业背景与 JD 的相关性 |
| 学历背景 | 0-15 | 学历与 JD 要求的匹配 |
| 意向匹配 | 0-10 | 求职意向与 JD 的匹配 |

+ rules/jd-match-rules.md 中匹配到的规则加分
+ 用户自定义维度（动态添加/调整权重）

### 候选人唯一性

```
匹配优先级:
1. platform_id 精确匹配 → 100% 确认同一人
2. name + education + company 时间重叠 → 90%+ 置信度
3. name + company（同时间段） → 70% 置信度
4. 仅 name 相似 → 50% 置信度，标记待确认
```
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/platform-match/references/
git commit -m "docs: 创建脉脉 API 参考、字段映射、反检测策略、匹配策略文档"
```

---

### Task 14: Create Rules & Templates

**Files:**
- Create: `.claude/skills/platform-match/rules/identity-rules.md`
- Create: `.claude/skills/platform-match/rules/jd-match-rules.md`
- Create: `.claude/skills/platform-match/rules/company-aliases.json`
- Create: `.claude/skills/platform-match/assets/candidate-list-template.md`
- Create: `.claude/skills/platform-match/assets/match-report-template.md`

- [ ] **Step 1: Create identity-rules.md**

```markdown
# 身份判定规则

## 自动判定规则（系统生成，由用户确认后生效）

> 当前暂无自动判定规则。系统会在用户选择目标人选时，采集判定理由并提炼为可复用规则。

## 人工兜底规则

- 无法自动判定时，展示 Top 3 给用户选择
- 用户选择"都不是"时，标记候选人为"平台未收录"

## 置信度阈值

| 阈值 | 行为 |
|------|------|
| ≥ 95% | 自动选取（报告中标注"请复核"） |
| 70-94% | 向用户建议最优人选，待确认 |
| < 70% | 展示 Top 3，用户选择 |
```

- [ ] **Step 2: Create jd-match-rules.md**

```markdown
# 人岗匹配规则

## 评分维度

| 维度 | 分值 | 说明 |
|------|------|------|
| 职位匹配度 | 0-30 | 当前职位与 JD 目标岗位的匹配 |
| 技能重叠度 | 0-25 | 技能标签与 JD 要求的重叠 |
| 行业经验 | 0-20 | 行业背景与 JD 的相关性 |
| 学历背景 | 0-15 | 学历与 JD 要求的匹配 |
| 意向匹配 | 0-10 | 求职意向与 JD 的匹配 |

## 自定义规则

> 当前暂无自定义匹配规则。系统会在用户批量选择候选人时，采集选择理由并提炼为可复用规则。

## 注意事项

- 此处的评分与 screen skill 的详细人岗评估（Tier S/A/B）是不同层级的评分
- 此评分为粗筛依据，screen 会在完整候选人信息基础上做更深入的评估
```

- [ ] **Step 3: Create company-aliases.json**

```json
{
  "阿里巴巴": ["阿里巴巴集团", "阿里", "Alibaba"],
  "字节跳动": ["字节", "ByteDance", "字节跳动有限公司"],
  "腾讯": ["腾讯科技", "Tencent", "腾讯控股"],
  "百度": ["百度集团", "Baidu", "百度在线"],
  "美团": ["美团点评", "Meituan"],
  "京东": ["京东集团", "JD.com", "京东科技"],
  "拼多多": ["PDD", "拼多多集团"],
  "网易": ["网易公司", "NetEase"],
  "小米": ["小米集团", "Xiaomi"],
  "华为": ["华为技术", "Huawei"],
  "滴滴": ["滴滴出行", "DiDi"],
  "快手": ["快手科技", "Kuaishou"]
}
```

- [ ] **Step 4: Create candidate-list-template.md**

```markdown
# 候选人搜索列表

**搜索时间**: {{search_time}}
**搜索平台**: {{platform}}
**搜索条件**: {{query}}
**结果数量**: {{total}} 人

| # | 姓名 | 公司 | 职位 | 学历 | 工作年限 | 活跃状态 | 求职状态 |
|---|------|------|------|------|---------|---------|---------|
{{#each candidates}}
| {{index}} | {{name}} | {{company}} | {{title}} | {{education}} | {{work_years}}年 | {{active_state}} | {{status}} |
{{/each}}

## 操作

- 输入编号查看详情
- 输入 "选择 1,3,5" 批量入库
- 输入 "调整条件" 重新搜索
- 输入 "结束" 退出搜索
```

- [ ] **Step 5: Create match-report-template.md**

```markdown
# 平台匹配报告

**执行时间**: {{report_time}}
**执行模式**: {{mode}}
**平台**: {{platform}}

## 摘要

| 指标 | 数值 |
|------|------|
| 待处理 | {{total_candidates}} 人 |
| 已丰富 | {{enriched_count}} 人 |
| 未找到 | {{not_found_count}} 人 |
| 待确认 | {{pending_count}} 人 |

## 详细结果

### 已丰富

{{#each enriched}}
#### {{name}} — {{company}}
- **置信度**: {{confidence}}%
- **匹配路径**: {{match_path}}
- **更新字段**: {{updated_fields}}
- **来源**: [脉脉]({{source_url}})

{{/each}}

### 未找到

{{#each not_found}}
- {{name}} — {{company}}（平台未收录）

{{/each}}

### 待确认

{{#each pending}}
- {{name}} — {{company}}（{{reason}}）

{{/each}}
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/platform-match/rules/ .claude/skills/platform-match/assets/
git commit -m "docs: 创建身份判定规则、人岗匹配规则、公司别名、输出模板"
```

---

## Phase 6: SKILL.md Full Rewrite

### Task 15: Rewrite SKILL.md

**Files:**
- Modify: `.claude/skills/platform-match/SKILL.md`（全量重写）

> **重要说明**: SKILL.md 是 Claude 读取并遵循的编排指令，不是可执行代码。
> 内容采用结构化步骤描述，指导 Claude 如何调用 Python 脚本、处理数据、与用户交互。

- [ ] **Step 1: Write SKILL.md frontmatter**

```yaml
---
name: platform-match
description: >
  招聘平台候选人搜索与信息丰富。在脉脉等招聘平台上搜索候选人，
  丰富候选人库信息，或根据 JD/条件搜索目标人选。
triggers:
  - "匹配候选人"
  - "搜索脉脉"
  - "平台找人"
  - "丰富候选人"
  - "platform match"
  - "/platform-match"
---
```

- [ ] **Step 2: Write SKILL.md body — 参数路由与模式选择**

```markdown
# platform-match Skill

## 参数解析与模式路由

```
/platform-match                              → 对话式（模式 3）
/platform-match --candidates <filter>        → 候选丰富（模式 1）
/platform-match --candidates batch:<batch-id> → 候选丰富（模式 1，从批次读取）
/platform-match --jd <id|file>               → JD 驱动（模式 2）
/platform-match --headless                   → 降级模式（附加在任意模式上）
```

降级模式标志: `--headless` 参数。影响: 更保守的速率控制、更低的操作上限。

## 前置检查（所有模式共用）

1. 检查 Python 环境: `python --version` (需 3.11+)
2. 检查 Playwright: `python -c "from playwright.async_api import async_playwright"`
3. 检查 session 状态:
   - 默认模式: `python scripts/session.py status`
   - 降级模式: `python scripts/session.py verify --platform maimai --mode standalone`
4. 如果 session 不可用:
   - 默认模式 → 提示用户: "请先启动 Chrome: `chrome --remote-debugging-port=9222`"
   - 降级模式 → 提示用户: "未找到 cookies 备份，请先用默认模式执行一次"

## 资源索引

| 场景 | 文件 |
|------|------|
| 脉脉 API 规格 | `references/maimai/api-reference.md` |
| 字段映射 | `references/maimai/field-mapping.md` |
| 反检测策略 | `references/maimai/anti-detect.md` |
| 匹配策略 | `references/matching-strategy.md` |
| 身份判定规则 | `rules/identity-rules.md` |
| 人岗匹配规则 | `rules/jd-match-rules.md` |
| 公司别名 | `rules/company-aliases.json` |
| 候选人列表模板 | `assets/candidate-list-template.md` |
| 匹配报告模板 | `assets/match-report-template.md` |
```

- [ ] **Step 3: Write SKILL.md body — 模式 1（候选丰富）**

```markdown
## 模式 1: 候选丰富（人找人）

### 步骤 1: 选择待丰富候选人

输入 A: `--candidates batch:<batch-id>`
  1. 读取批次: `python scripts/data-manager.py batch get <batch-id>`
  2. 获取候选人列表: `python scripts/data-manager.py batch candidates <batch-id> --filter "score>0"`
  3. 展示批次摘要表格（name, company, title, score）
  4. 用户确认或筛选

输入 B: `--candidates "company=阿里巴巴"` 或 `--candidates "enrichment=raw"`
  1. 列出候选人: `python scripts/data-manager.py candidate list`
  2. 按条件过滤（Claude 在内存中过滤）
  3. 展示筛选结果
  4. 用户确认

无参数 → 交互式选择
  1. 列出所有候选人
  2. 展示摘要表格
  3. 用户自然语言筛选: "只处理前10个" / "跳过李四"
  4. 确认最终列表

过滤条件: `enrichment_level in ["raw", "partial"]`

### 步骤 2: 逐个搜索匹配

FOR EACH candidate:
  2.1 生成搜索参数
    - 路径 A: query = "{name} {current_company}"
    - 路径 B: query = "{name} {current_title}"（路径 A 无结果时降级）

  2.2 检查 platform_id 是否已关联
    - 在 candidates sources[] 中查找 channel="maimai" 的记录
    - 已关联（同记录）→ 跳过搜索，提示"已有脉脉数据"
    - 已关联（其他记录）→ 提示可能重复，建议去重
    - 未关联 → 执行搜索

  2.3 调用搜索
    ```
    python scripts/search.py search --platform maimai --query "<query>" --pages 1
    ```
    - 解析 JSON 输出
    - 0 结果 → 标记"平台未收录"
    - 1 结果 → 进入判定
    - 多结果 → 进入判定

  2.4 身份判定（参考 `references/matching-strategy.md`）

    **Claude 在内存中执行评分**（不调用脚本）:

    a) 加载公司别名: 读取 `rules/company-aliases.json`
    b) 对每个搜索结果打分（5 维度，总分 100）
    c) 加载身份判定规则: 读取 `rules/identity-rules.md`
    d) 应用匹配到的规则加分

    判定结果:
    - ≥ 95% → 自动选取（报告中标注"请复核"）
    - 70-94% → 向用户建议最优人选，展示评分明细，待确认
    - < 70% → 展示 Top 3 供用户选择

  2.5 用户确认后的自学习
    - 询问: "你选择这个人选的主要依据是什么？"（用户可跳过）
    - 如果用户提供了理由 → Claude 抽象为规则 → 展示规则 → 用户确认/修改/拒绝
    - 确认 → 追加到 `rules/identity-rules.md`（标注来源日期）

  2.6 丰富写入
    ```
    # 映射 API 数据
    python scripts/enrich.py map --platform maimai --api-data '<json>'
    # 写入候选人
    python scripts/enrich.py merge --candidate-id <id> --new-data <tmp-file>
    ```
    - 临时文件包含映射后的数据 + _source 信息
    - enrich.py 处理逐字段合并和 source 追加

  2.7 速率检查
    ```
    python scripts/rate_limiter.py tick --platform maimai [--headless]
    ```
    - 如果 allowed=false → 等待 wait_seconds → 继续

### 步骤 3: 生成报告

使用 `assets/match-report-template.md` 模板生成报告。
输出到 `data/output/platform-match-report.md`。
```

- [ ] **Step 4: Write SKILL.md body — 模式 2（JD 驱动）**

```markdown
## 模式 2: JD 驱动（条件找人）

### 步骤 1: 读取 JD 与搜索策略

输入 A: `--jd <jd-id>`
  ```
  python scripts/data-manager.py jd get <jd-id>
  ```

输入 B: `--jd <file-path>`
  读取本地文件

输入 C: 用户直接提供 JD 文本

然后:
1. Claude 解析 JD 自动提取搜索条件（关键词、行业、职位等）
2. 获取用户搜索策略（增强层）:
   - 用户随 JD 提供 → 例: "优先大厂经验，P7 以上"
   - 用户未提供 → 系统主动询问
   - 用户可回答"没有"
3. 综合生成搜索计划（基础组 2-3 + 增强组 1-2），用户确认

### 步骤 2: 执行搜索

FOR EACH 搜索组:
  ```
  python scripts/search.py search --platform maimai --query "<query>" --pages 3
  ```
  - 默认前 3 页 = 90 条
  - 跨组去重（按 platform_id，Claude 在内存中处理）

### 步骤 3: 结果排序与筛选

1. 加载 `rules/jd-match-rules.md`
2. 对每个结果评分（5 维度，总分 100）:
   - 职位匹配度(30) + 技能重叠度(25) + 行业经验(20) + 学历背景(15) + 意向匹配(10)
3. 标注命中规则
4. 展示 Top N（默认 20），标注得分明细

### 步骤 4: 用户选择入库

1. 用户批量勾选要添加的候选人
2. 统一询问选择理由:
   - "你选择了以下 8 位候选人，主要考量是什么？"
   - 整体描述 → 提炼通用规则
   - 个别说明 → 提炼附加规则
   - 跳过 → 不触发规则提炼
3. 自学习: 展示规则 → 确认 → 写入 `rules/jd-match-rules.md`

### 步骤 5: 写入候选人库

FOR EACH 用户选中:
  1. 检查是否已存在（name + company 去重）
  2. 不存在 → 创建临时 JSON → `python scripts/data-manager.py candidate create <tmp-file>`
  3. 已存在 → 合并数据 → `python scripts/enrich.py merge --candidate-id <id> --new-data <tmp-file>`

### 步骤 6: 生成报告

使用 `assets/candidate-list-template.md` 模板。
输出到 `data/output/platform-match-search-list.md`。
```

- [ ] **Step 5: Write SKILL.md body — 模式 3（对话式）**

```markdown
## 模式 3: 对话式

### 步骤 1: 理解搜索需求

1. 用户自然语言 → Claude 解析为搜索参数
2. 展示解析结果，用户确认
3. 如有歧义 → 主动询问

### 步骤 2: 执行搜索

```
python scripts/search.py search --platform maimai --query "<query>" --pages 3
```

### 步骤 3: 展示与交互

1. 展示摘要表格（name, company, title, education, active_state）
2. 用户可选择:
   - 调整条件重新搜索
   - 选择加入候选人库（同模式 2 步骤 5）
   - 查看某人详情
   - 结束搜索

### 步骤 4: 按需写入

同模式 2 步骤 5。
```

- [ ] **Step 6: Write SKILL.md body — 错误处理与契约**

```markdown
## 错误处理

所有 Python 脚本通过 stdout JSON 返回结果和错误:

```json
{"status": "ok", "data": {...}}
{"status": "error", "code": "SESSION_EXPIRED", "message": "...", "retryable": false}
{"status": "error", "code": "CIRCUIT_BREAK", "message": "...", "retryable": false, "trigger_reason": "..."}
```

### 错误分级

| 级别 | 处理方式 | Claude 行为 |
|------|---------|------------|
| P0（阻塞） | 暂停，提示解决步骤 | 明确告知用户，等待用户操作后继续 |
| P1（重试） | 自动重试 1 次 | 静默处理，报告中汇总 |
| P2（跳过） | 标记状态，继续 | 报告中标注"已跳过" |
| P3（记录） | 仅记录 | 无感知 |

### 熔断恢复

触发熔断后:
1. 停止所有搜索操作
2. 通知用户: "触发熔断: {reason}，建议等待 30 分钟"
3. 用户手动确认继续 → 重置限流 → 继续
4. 或等待 30 分钟后自动提示

## Skill 间衔接契约

| 契约 | 说明 |
|------|------|
| 不修改 id | 候选人 ID 一旦生成就不变 |
| 不删除候选人 | 丰富失败的标记状态，不删除 |
| enrichment_level 只升不降 | raw → partial → enriched |
| sources 只追加不覆盖 | 新增 source 追加到数组 |
| 输出报告格式固定 | markdown，screen/report 可解析 |

## 断点恢复

模式 1 批次中断后:
1. 保存进度:
   ```
   python scripts/batch_progress.py create --batch-id <batch-id> --candidates '<json>'
   ```
2. 每处理一个候选人后更新状态:
   ```
   python scripts/batch_progress.py update --batch-id <id> --candidate-id <cand-id> --status completed --result enriched
   ```
3. 发生中断（P0 错误 / Chrome 关闭 / 用户取消）时:
   - 将当前候选人标记为 `in_progress`
   - 展示: "已处理 X/Y，剩余 Z 个"
4. 用户重新执行时检测断点:
   ```
   python scripts/batch_progress.py resume <batch-id>
   ```
5. 提示: "发现未完成的批次（X/Y 已完成），是否从断点继续？"
   - 用户确认 → 跳过已完成的，从 in_progress/pending 继续
   - 用户拒绝 → 从头开始
```

- [ ] **Step 7: Commit**

```bash
git add .claude/skills/platform-match/SKILL.md
git commit -m "feat: 全量重写 SKILL.md — 三种执行模式、自学习机制、错误处理"
```

---

## Phase 7: public-search Integration

### Task 16: Modify public-search SKILL.md

**Files:**
- Modify: `.claude/skills/public-search/SKILL.md`

- [ ] **Step 1: Add batch recording section to public-search SKILL.md**

在 public-search SKILL.md 的「候选人写入」章节后新增以下章节:

```markdown
## 批次记录

每轮搜索结束时，自动创建批次文件。

### 批次文件格式

存储路径: `data/batches/public-search-<date>-<seq>.json`

```json
{
  "id": "public-search-20260415-1",
  "created_at": "2026-04-15T08:30:00",
  "jd_id": "jd-20260415-alibaba-aigc-pm",
  "strategy_file": "data/search-strategies/instances/2026-04-15-aigc-pm.md",
  "round": 1,
  "query_summary": "AI产品经理 AIGC 互联网",
  "candidates": [
    {
      "id": "cand-1",
      "name": "张三",
      "company": "阿里巴巴",
      "title": "产品经理",
      "score": 92,
      "match_highlights": ["AIGC产品经验", "百万DAU"]
    }
  ],
  "total": 2,
  "metadata": {
    "channels_used": ["LinkedIn", "Google"],
    "keywords_used": ["AI产品经理", "AIGC"],
    "token_cost": 30600
  }
}
```

### 候选人初筛评分（pre_screen_score）

搜索确认时，Claude 对每个候选人打初步匹配度（0-100）:

| 维度 | 分值 | 说明 |
|------|------|------|
| 职位匹配度 | 0-30 | 当前职位与 JD 目标岗位的匹配 |
| 技能重叠度 | 0-25 | 技能标签与 JD 要求的重叠 |
| 行业经验 | 0-20 | 行业背景与 JD 的相关性 |
| 公司背景 | 0-15 | 公司类型/规模与 JD 的匹配 |
| 综合印象 | 0-10 | 基于公开信息的整体判断 |

> 注: 此分数为 public-search 阶段的粗筛依据，与 screen skill 的详细人岗评估是不同层级。

### 写入流程

1. 确定批次 ID: `public-search-YYYYMMDD-<seq>`（seq 从 1 递增）
2. 为每个候选人打 pre_screen_score
3. 写入批次文件到 `data/batches/`
4. 可通过 data-manager 批次命令查询:
   - `python scripts/data-manager.py batch list`
   - `python scripts/data-manager.py batch get <batch-id>`
   - `python scripts/data-manager.py batch candidates <batch-id> --filter "score>80"`
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/public-search/SKILL.md
git commit -m "feat: public-search 新增批次记录机制与 pre_screen_score 评分"
```

---

## Phase 8: Testing

### Task 17: Unit Tests for rate_limiter

**Files:**
- Create: `scripts/test_rate_limiter.py`

- [ ] **Step 1: Write test file**

```python
"""rate_limiter.py 单元测试"""

import json
import os
import sys
import tempfile
import unittest

# 添加脚本路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "platform-match"))


class TestRateLimiter(unittest.TestCase):
    """限流器测试。"""

    def setUp(self):
        """每个测试使用临时目录。"""
        self.tmpdir = tempfile.mkdtemp()
        # 临时修改 SESSION_DIR
        import rate_limiter
        self._original_session_dir = rate_limiter.SESSION_DIR
        rate_limiter.SESSION_DIR = self.tmpdir

    def tearDown(self):
        import rate_limiter
        rate_limiter.SESSION_DIR = self._original_session_dir

    def test_check_search_allowed_when_empty(self):
        """空状态时应允许搜索。"""
        from rate_limiter import check_search
        result = check_search("maimai")
        self.assertTrue(result["allowed"])
        self.assertEqual(result["delay_seconds"], 0)

    def test_check_search_rate_limit(self):
        """连续搜索后应触发限流。"""
        from rate_limiter import check_search, record_search
        record_search("maimai")
        result = check_search("maimai")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "rate_limit")

    def test_record_search_increments_count(self):
        """记录搜索应递增计数器。"""
        from rate_limiter import record_search, _get_platform_state
        record_search("maimai")
        state = _get_platform_state("maimai")
        self.assertEqual(state.batch_count, 1)
        self.assertEqual(state.daily_count, 1)

    def test_circuit_break_triggers(self):
        """熔断触发后应阻止搜索。"""
        from rate_limiter import trigger_circuit_break, check_search
        trigger_circuit_break("maimai", "CAPTCHA")
        result = check_search("maimai")
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "circuit_break")

    def test_reset_clears_state(self):
        """重置应清除所有限流状态。"""
        from rate_limiter import record_search, check_search, _load_state
        record_search("maimai")
        # 重置
        _load_state.__module__  # 确保模块加载
        state_file = os.path.join(self.tmpdir, "rate-limit-state.json")
        with open(state_file, "w") as f:
            json.dump({}, f)
        result = check_search("maimai")
        self.assertTrue(result["allowed"])

    def test_headless_stricter_limits(self):
        """降级模式应使用更严格的限流。"""
        from rate_limiter import check_search, record_search
        record_search("maimai", headless=True)
        result = check_search("maimai", headless=True)
        self.assertFalse(result["allowed"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

Run: `cd D:/workspace/talent-agent && python -m pytest scripts/test_rate_limiter.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/test_rate_limiter.py
git commit -m "test: 添加 rate_limiter 单元测试"
```

---

### Task 18: Unit Tests for enrich

**Files:**
- Create: `scripts/test_enrich.py`

- [ ] **Step 1: Write test file**

```python
"""enrich.py 字段合并单元测试"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".claude", "skills", "platform-match"))


class TestFieldMerge(unittest.TestCase):
    """逐字段冲突合并测试。"""

    def test_latest_first_overwrites(self):
        """最新来源优先字段应被覆盖。"""
        from enrich import merge_fields
        existing = {"name": "张三", "current_company": "A公司"}
        new_data = {"current_company": "B公司"}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["current_company"], "B公司")

    def test_first_source_preserves(self):
        """首次来源优先字段，已有则不覆盖。"""
        from enrich import merge_fields
        existing = {"name": "张三", "education_experience": [{"school": "北大"}]}
        new_data = {"education_experience": [{"school": "清华"}]}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["education_experience"][0]["school"], "北大")

    def test_first_source_writes_when_empty(self):
        """首次来源优先字段，为空时写入。"""
        from enrich import merge_fields
        existing = {"name": "张三"}
        new_data = {"education_experience": [{"school": "清华"}]}
        result = merge_fields(existing, new_data)
        self.assertEqual(len(result["education_experience"]), 1)

    def test_skill_tags_merge_dedup(self):
        """技能标签应合并去重。"""
        from enrich import merge_fields
        existing = {"name": "张三", "skill_tags": ["Python", "Java"]}
        new_data = {"skill_tags": ["Java", "Go"]}
        result = merge_fields(existing, new_data)
        self.assertEqual(sorted(result["skill_tags"]), ["Go", "Java", "Python"])

    def test_skip_empty_values(self):
        """空值不应覆盖已有数据。"""
        from enrich import merge_fields
        existing = {"name": "张三", "age": 30}
        new_data = {"age": None, "city": ""}
        result = merge_fields(existing, new_data)
        self.assertEqual(result["age"], 30)
        self.assertNotIn("city", result)

    def test_skip_internal_fields(self):
        """_ 开头的内部字段应被跳过。"""
        from enrich import merge_fields
        existing = {"name": "张三"}
        new_data = {"_source": {"channel": "maimai"}, "city": "北京"}
        result = merge_fields(existing, new_data)
        self.assertNotIn("_source", result)
        self.assertEqual(result["city"], "北京")


class TestAppendSource(unittest.TestCase):
    """Source 追加测试。"""

    def test_append_new_source(self):
        """追加新 source。"""
        from enrich import append_source
        existing = {"name": "张三", "sources": []}
        source = {"channel": "maimai", "url": "https://maimai.cn/u/123", "platform_id": "123"}
        result = append_source(existing, source)
        self.assertEqual(len(result["sources"]), 1)

    def test_dedup_same_platform_id(self):
        """相同 channel + platform_id 不应重复追加。"""
        from enrich import append_source
        source = {"channel": "maimai", "url": "https://maimai.cn/u/123", "platform_id": "123"}
        existing = {"name": "张三", "sources": [source]}
        result = append_source(existing, source)
        self.assertEqual(len(result["sources"]), 1)


class TestEnrichmentLevel(unittest.TestCase):
    """enrichment_level 提升测试。"""

    def test_level_only_goes_up(self):
        """enrichment_level 只升不降。"""
        from enrich import enrich_enrichment_level
        existing = {"enrichment_level": "partial", "sources": [
            {"enrichment_level": "raw"}
        ]}
        result = enrich_enrichment_level(existing)
        self.assertEqual(result["enrichment_level"], "partial")

    def test_level_promotes_from_sources(self):
        """从 sources 推断更高的 enrichment_level。"""
        from enrich import enrich_enrichment_level
        existing = {"enrichment_level": "raw", "sources": [
            {"enrichment_level": "enriched"}
        ]}
        result = enrich_enrichment_level(existing)
        self.assertEqual(result["enrichment_level"], "enriched")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests**

Run: `cd D:/workspace/talent-agent && python -m pytest scripts/test_enrich.py -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add scripts/test_enrich.py
git commit -m "test: 添加 enrich 字段合并单元测试"
```

---

## 执行检查清单

完成所有任务后，验证以下内容:

- [ ] 旧 TypeScript 模块已删除
- [ ] 新 Python 脚本均可独立运行（`python scripts/session.py status` 等）
- [ ] candidate.schema.json 包含新字段（active_state, project_experience, sources[] 扩展）
- [ ] data-manager.py 新命令可用（`batch list`, `candidate dedup-merge`, `candidate dedup-auto`）
- [ ] H2 bug 已修复（sources 去重键 type → channel）
- [ ] batch_progress.py 可创建、更新、恢复进度
- [ ] SKILL.md 包含三种模式的完整编排指令
- [ ] SKILL.md 断点恢复流程引用 batch_progress.py
- [ ] evals.json 已初始化
- [ ] 所有单元测试通过
- [ ] .gitignore 包含 data/session/ 和 data/batches/
- [ ] public-search SKILL.md 包含批次记录章节
