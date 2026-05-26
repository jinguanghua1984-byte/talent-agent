# Script Cleanup And Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `scripts/` 从混合的生产入口、库模块、测试文件和一次性任务脚本，整理为边界清晰、可验证、可持续维护的脚本层。

**Architecture:** 采用分阶段清理：先迁移明显放错位置的测试和已有替代的 legacy 入口，再处理 `data-manager.py` 这类兼容入口，最后用文档清单和自动化测试防止新的单次任务脚本回流到 `scripts/`。所有删除动作都先用引用扫描和测试证明安全；`hunyuan_abc_*` 这类历史一次性脚本需要用户明确批准后才删除。

**Tech Stack:** Python 3.12、pytest、pathlib、正则静态扫描、Git、Markdown 文档。

---

## Current Evidence

- `scripts/` 当前顶层文件数为 65，其中包含生产 CLI、库模块、PowerShell 监督脚本和 5 个 `scripts/test_*.py` 测试文件。
- `scripts/test_boss.py`、`scripts/test_data_manager.py`、`scripts/test_enrich.py`、`scripts/test_maimai.py`、`scripts/test_rate_limiter.py` 放在运行时代码目录内；当前 `AGENTS.md` 因此要求执行 `python -m pytest tests scripts -q`。
- `scripts/score_candidates.py` 文件头明确标记为 `[LEGACY]`，并说明已被 `score_pipeline.py` 替代，新项目应使用 `python -m scripts.score_pipeline run ...`。
- `scripts/hunyuan_abc_detail_tasks.py:21-23` 写死了 `data/output/hunyuan-8jd-main-db-match-2026-05-22/...`、`data/campaigns/hunyuan-8jd-abc-detail-2026-05-22` 和 `data/talent.db`，属于单次 Hunyuan ABC 详情补抓任务脚本。
- `scripts/hunyuan_abc_parallel_supervisor.ps1:125-134` 只负责启动 `scripts.hunyuan_abc_detail_tasks run`，也属于同一批单次任务辅助脚本。
- `scripts/data-manager.py` 是早期 JSON 数据管理 CLI，文件名带连字符，无法作为 `scripts.data_manager` 正常 import；但 README 和多个 canonical workflow 仍引用 `python scripts/data-manager.py`。
- `maimai_ai_infra_*` 不能在第一阶段删除：`scripts/maimai_campaign_orchestrator.py:373-382` 会按 legacy AI Infra strategy 路由到 `scripts.maimai_ai_infra_search_plan`、`scripts.maimai_ai_infra_rank` 和 `scripts.maimai_ai_infra_delivery_report`；`tests/test_maimai_campaign_orchestrator.py` 也覆盖了该兼容路径。

## Safety Rules

- 本计划只整理脚本层，不写入 `data/talent.db`，不移动 `data/output/`、`data/campaigns/` 或飞书同步文件。
- 删除 tracked 脚本前必须先执行引用扫描、聚焦测试和 `git diff --check`。
- `hunyuan_abc_detail_tasks.py` 和 `hunyuan_abc_parallel_supervisor.ps1` 需要用户明确确认后才能删除；没有确认时实施停在审批门，不继续执行删除。
- `.venv/bin/python` 是本仓库验证默认 Python；计划中的 pytest 和 py_compile 命令均使用 `.venv/bin/python`。
- 历史归档 `tasks/archive/` 和历史设计计划可以保留旧脚本名称；清理时只更新 README、AGENTS、agents/workflows、docs/manual、docs/dev、tests 等当前有效入口。

## File Structure

- Move: `scripts/test_boss.py` -> `tests/test_boss.py`
- Move: `scripts/test_data_manager.py` -> `tests/test_data_manager.py`
- Move: `scripts/test_enrich.py` -> `tests/test_enrich.py`
- Move: `scripts/test_maimai.py` -> `tests/test_maimai.py`
- Move: `scripts/test_rate_limiter.py` -> `tests/test_rate_limiter.py`
- Modify: `AGENTS.md` - 将验证命令改为 `.venv/bin/python -m pytest tests -q`。
- Delete after verification: `scripts/score_candidates.py`
- Delete only after user approval: `scripts/hunyuan_abc_detail_tasks.py`
- Delete only after user approval: `scripts/hunyuan_abc_parallel_supervisor.ps1`
- Move: `scripts/data-manager.py` -> `scripts/data_manager.py`
- Create: `scripts/data-manager.py` - 兼容 shim，只转发到 `scripts.data_manager.main()`。
- Modify: `README.md` - 将当前有效示例改为 `python -m scripts.data_manager ...`。
- Modify: `agents/workflows/platform-match/AGENT.md`、`agents/workflows/public-search/AGENT.md`、`agents/workflows/report/AGENT.md`、`agents/workflows/screen/AGENT.md` - 将当前工作流中的 `python scripts/data-manager.py ...` 改为 `python -m scripts.data_manager ...`。
- Create: `docs/dev/script-inventory.md` - 记录脚本分类、legacy 兼容层、已移除入口和新增脚本准入规则。
- Create or extend: `tests/test_script_hygiene.py` - 增加脚本目录护栏测试。
- Modify: `tasks/todo.md` and `tasks/archive/2026-05.md` - 只记录实施过程、验证证据和审批结果。

## Task 1: Establish Script Inventory

**Files:**
- Create: `docs/dev/script-inventory.md`
- Create: `tests/test_script_hygiene.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Write the failing inventory test**

Add this initial test to `tests/test_script_hygiene.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "dev" / "script-inventory.md"


def test_script_inventory_exists_and_names_cleanup_boundaries() -> None:
    text = INVENTORY.read_text(encoding="utf-8")
    required_markers = [
        "## Runtime CLI",
        "## Library Modules",
        "## Legacy Compatibility",
        "## Removed Or Approval-Gated Scripts",
        "score_candidates.py",
        "hunyuan_abc_detail_tasks.py",
        "hunyuan_abc_parallel_supervisor.ps1",
        "maimai_ai_infra_search_plan.py",
        "data-manager.py",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    assert missing == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_script_inventory_exists_and_names_cleanup_boundaries -q
```

Expected: fail with `FileNotFoundError` for `docs/dev/script-inventory.md`.

- [ ] **Step 3: Create the inventory document**

Create `docs/dev/script-inventory.md` with these sections:

```markdown
# Script Inventory

本清单记录 `scripts/` 的当前职责边界，用于脚本清理、代码审查和新增入口准入。

## Runtime CLI

- `scripts/talent_library.py`：人才库导入、查询和报告入口。
- `scripts/talent_sync.py`：人才库 bundle 导入导出入口。
- `scripts/talent_cloud_sync.py`：人才库云同步入口。
- `scripts/jd_talent_delivery.py`：JD 推荐交付 workflow 入口。
- `scripts/maimai_campaign_orchestrator.py`：脉脉 campaign 阶段编排入口。
- `scripts/score_pipeline.py`：JD 驱动评分 pipeline 入口。

## Library Modules

- `scripts/talent_db.py`、`scripts/talent_models.py`、`scripts/talent_sync_models.py`：人才库核心模型和持久化。
- `scripts/talent_cloud_sync_common.py`、`scripts/talent_cloud_sync_providers.py`：云同步 provider 和通用能力。
- `scripts/maimai_campaign_*.py`：通用脉脉 campaign 计划、评分、报告和反馈模块。
- `scripts/jd_talent_delivery_*.py`：JD 推荐画像、评分卡、匹配和飞书发布模块。

## Legacy Compatibility

- `scripts/data-manager.py`：当前为旧 JSON 数据管理 CLI；Task 5 后保留为兼容 shim，新调用使用 `python -m scripts.data_manager ...`。
- `scripts/maimai_ai_infra_search_plan.py`、`scripts/maimai_ai_infra_rank.py`、`scripts/maimai_ai_infra_delivery_report.py`：legacy AI Infra strategy 兼容层，仍由 `scripts/maimai_campaign_orchestrator.py` 在旧策略下路由使用。

## Removed Or Approval-Gated Scripts

- `scripts/score_candidates.py`：已被 `scripts/score_pipeline.py` 替代，计划从运行时目录删除。
- `scripts/hunyuan_abc_detail_tasks.py`：Hunyuan 8JD ABC 详情补抓一次性任务脚本，删除需要用户明确确认。
- `scripts/hunyuan_abc_parallel_supervisor.ps1`：Hunyuan ABC 详情补抓监督脚本，删除需要用户明确确认。

## Admission Rules

- 新增生产入口必须有稳定 CLI help、聚焦测试和文档入口。
- 新增库模块必须被生产入口或测试引用。
- 测试文件必须放在 `tests/`，不得新增 `scripts/test_*.py`。
- 带固定日期、固定 campaign root 或固定 data/output 路径的一次性任务脚本不得进入 `scripts/`。
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_script_inventory_exists_and_names_cleanup_boundaries -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit the inventory baseline**

Run:

```bash
git add docs/dev/script-inventory.md tests/test_script_hygiene.py tasks/todo.md
git commit -m "docs: add script inventory cleanup baseline"
```

Expected: commit succeeds.

## Task 2: Move Tests Out Of Runtime Scripts

**Files:**
- Move: `scripts/test_boss.py` -> `tests/test_boss.py`
- Move: `scripts/test_data_manager.py` -> `tests/test_data_manager.py`
- Move: `scripts/test_enrich.py` -> `tests/test_enrich.py`
- Move: `scripts/test_maimai.py` -> `tests/test_maimai.py`
- Move: `scripts/test_rate_limiter.py` -> `tests/test_rate_limiter.py`
- Modify: `tests/test_script_hygiene.py`
- Modify: `AGENTS.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add the failing runtime-test guard**

Append to `tests/test_script_hygiene.py`:

```python
def test_runtime_scripts_do_not_contain_pytest_modules() -> None:
    offenders = sorted(path.name for path in (ROOT / "scripts").glob("test_*.py"))
    assert offenders == []
```

- [ ] **Step 2: Run the guard to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_runtime_scripts_do_not_contain_pytest_modules -q
```

Expected: fail with offenders equal to `['test_boss.py', 'test_data_manager.py', 'test_enrich.py', 'test_maimai.py', 'test_rate_limiter.py']`.

- [ ] **Step 3: Move the test files with Git**

Run:

```bash
git mv scripts/test_boss.py tests/test_boss.py
git mv scripts/test_data_manager.py tests/test_data_manager.py
git mv scripts/test_enrich.py tests/test_enrich.py
git mv scripts/test_maimai.py tests/test_maimai.py
git mv scripts/test_rate_limiter.py tests/test_rate_limiter.py
```

Expected: `git status --short` shows five renames.

- [ ] **Step 4: Update the verification command**

Modify `AGENTS.md` verification block from:

```bash
python -m pytest tests scripts -q
```

to:

```bash
.venv/bin/python -m pytest tests -q
```

- [ ] **Step 5: Run focused moved-test verification**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_boss.py \
  tests/test_data_manager.py \
  tests/test_enrich.py \
  tests/test_maimai.py \
  tests/test_rate_limiter.py \
  tests/test_script_hygiene.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit the test relocation**

Run:

```bash
git add AGENTS.md tests/test_boss.py tests/test_data_manager.py tests/test_enrich.py tests/test_maimai.py tests/test_rate_limiter.py tests/test_script_hygiene.py
git add -u scripts
git commit -m "test: move script tests into tests directory"
```

Expected: commit succeeds.

## Task 3: Remove Legacy Score Candidates Entry

**Files:**
- Delete: `scripts/score_candidates.py`
- Modify: `docs/dev/script-inventory.md`
- Modify: `tests/test_script_hygiene.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add the failing legacy-entry guard**

Append to `tests/test_script_hygiene.py`:

```python
def test_legacy_score_candidates_is_not_a_runtime_script() -> None:
    assert not (ROOT / "scripts" / "score_candidates.py").exists()
```

- [ ] **Step 2: Run the guard to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_legacy_score_candidates_is_not_a_runtime_script -q
```

Expected: fail because `scripts/score_candidates.py` still exists.

- [ ] **Step 3: Confirm no active reference requires the file**

Run:

```bash
rg -n "score_candidates.py|scripts.score_candidates" \
  README.md AGENTS.md agents scripts tests docs/manual docs/dev \
  --glob '!scripts/score_candidates.py'
```

Expected: no output. If output appears in active docs or tests, update those references to `python -m scripts.score_pipeline ...` before deletion.

- [ ] **Step 4: Delete the file**

Run:

```bash
git rm scripts/score_candidates.py
```

Expected: `rm 'scripts/score_candidates.py'`.

- [ ] **Step 5: Update the inventory**

Change the `score_candidates.py` bullet in `docs/dev/script-inventory.md` to:

```markdown
- `scripts/score_candidates.py`：已移出运行时目录；历史评分入口由 `scripts/score_pipeline.py` 取代。
```

- [ ] **Step 6: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py -q
.venv/bin/python -m pytest tests/test_score_pipeline.py -q
```

Expected: script hygiene tests pass; score pipeline tests pass. If `tests/test_score_pipeline.py` does not exist, run `rg -n "score_pipeline" tests` and execute the listed score pipeline tests.

- [ ] **Step 7: Commit the deletion**

Run:

```bash
git add docs/dev/script-inventory.md tests/test_script_hygiene.py tasks/todo.md
git add -u scripts
git commit -m "refactor: remove legacy score candidates script"
```

Expected: commit succeeds.

## Task 4: Approval Gate For Hunyuan ABC One-Off Scripts

**Files:**
- Delete after approval: `scripts/hunyuan_abc_detail_tasks.py`
- Delete after approval: `scripts/hunyuan_abc_parallel_supervisor.ps1`
- Modify: `docs/dev/script-inventory.md`
- Modify: `tests/test_script_hygiene.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add the dated one-off guard**

Append to `tests/test_script_hygiene.py`:

```python
import re


def test_runtime_scripts_do_not_hardcode_dated_campaign_paths() -> None:
    offenders = []
    for path in sorted((ROOT / "scripts").iterdir()):
        if path.suffix not in {".py", ".ps1"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        has_dated_campaign_path = (
            ("data/campaigns/" in text or "data\\campaigns\\" in text)
            and re.search(r"20\d\d-\d\d-\d\d", text)
        )
        if has_dated_campaign_path:
            offenders.append(path.name)
    assert offenders == []
```

- [ ] **Step 2: Run the guard to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_runtime_scripts_do_not_hardcode_dated_campaign_paths -q
```

Expected: fail with `hunyuan_abc_detail_tasks.py` and `hunyuan_abc_parallel_supervisor.ps1`.

- [ ] **Step 3: Re-check active references before asking for approval**

Run:

```bash
rg -n "hunyuan_abc_detail_tasks|hunyuan_abc_parallel_supervisor" \
  README.md AGENTS.md agents scripts tests docs/manual docs/dev \
  --glob '!scripts/hunyuan_abc_detail_tasks.py' \
  --glob '!scripts/hunyuan_abc_parallel_supervisor.ps1'
```

Expected: no active runtime or workflow references. Historical mentions under `tasks/archive/` can remain outside this command.

- [ ] **Step 4: Stop for explicit deletion approval**

Ask the user for this exact decision:

```text
确认后我会删除 scripts/hunyuan_abc_detail_tasks.py 和 scripts/hunyuan_abc_parallel_supervisor.ps1。是否确认删除这两个 Hunyuan ABC 一次性任务脚本？
```

Expected: proceed only if the user explicitly confirms deletion. If the user does not confirm, stop this implementation and record that the cleanup is blocked by deletion approval.

- [ ] **Step 5: Delete the approved one-off scripts**

Run only after approval:

```bash
git rm scripts/hunyuan_abc_detail_tasks.py scripts/hunyuan_abc_parallel_supervisor.ps1
```

Expected: both files removed from the index.

- [ ] **Step 6: Update the inventory**

Change the Hunyuan bullets in `docs/dev/script-inventory.md` to:

```markdown
- `scripts/hunyuan_abc_detail_tasks.py`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。
- `scripts/hunyuan_abc_parallel_supervisor.ps1`：已移出运行时目录；历史执行记录保留在 `tasks/archive/2026-05.md`。
```

- [ ] **Step 7: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py -q
rg -n "hunyuan_abc_detail_tasks|hunyuan_abc_parallel_supervisor" \
  README.md AGENTS.md agents scripts tests docs/manual docs/dev
```

Expected: pytest passes; `rg` produces no active runtime references.

- [ ] **Step 8: Commit the approval-gated deletion**

Run:

```bash
git add docs/dev/script-inventory.md tests/test_script_hygiene.py tasks/todo.md
git add -u scripts
git commit -m "refactor: remove approved hunyuan abc one-off scripts"
```

Expected: commit succeeds.

## Task 5: Convert Data Manager To Importable Module With Compatibility Shim

**Files:**
- Move: `scripts/data-manager.py` -> `scripts/data_manager.py`
- Create: `scripts/data-manager.py`
- Modify: `tests/test_data_manager.py`
- Modify: `README.md`
- Modify: `agents/workflows/platform-match/AGENT.md`
- Modify: `agents/workflows/public-search/AGENT.md`
- Modify: `agents/workflows/report/AGENT.md`
- Modify: `agents/workflows/screen/AGENT.md`
- Modify: `docs/dev/script-inventory.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add module-entry and legacy-shim tests**

Modify the top of `tests/test_data_manager.py` so CLI execution uses module mode by default while still testing the old file path:

```python
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEGACY_SCRIPT_PATH = os.path.join(PROJECT_ROOT, "scripts", "data-manager.py")
PYTHON = sys.executable


def run_cli(*args, cwd=None, use_legacy=False):
    """运行 data manager CLI 并返回 (returncode, stdout, stderr)。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    command = [PYTHON, LEGACY_SCRIPT_PATH] if use_legacy else [PYTHON, "-m", "scripts.data_manager"]
    result = subprocess.run(
        command + list(args),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=cwd or PROJECT_ROOT,
        env=env,
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()
```

Add this test near the existing CLI tests:

```python
class TestEntrypoints(BaseTestCase):
    """入口兼容性测试。"""

    def test_module_entrypoint_prints_help(self):
        rc, out, err = run_cli(cwd=self.tmpdir)
        self.assertEqual(rc, 1)
        self.assertIn("usage:", out)
        self.assertEqual(err, "")

    def test_legacy_hyphen_script_still_delegates(self):
        rc, out, err = run_cli(cwd=self.tmpdir, use_legacy=True)
        self.assertEqual(rc, 1)
        self.assertIn("usage:", out)
        self.assertEqual(err, "")
```

- [ ] **Step 2: Run the module-entry test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_data_manager.py::TestEntrypoints -q
```

Expected: fail with `No module named scripts.data_manager`.

- [ ] **Step 3: Move implementation to importable module**

Run:

```bash
git mv scripts/data-manager.py scripts/data_manager.py
```

Expected: `scripts/data_manager.py` contains the existing implementation and `main()` function.

- [ ] **Step 4: Create compatibility shim**

Create `scripts/data-manager.py`:

```python
#!/usr/bin/env python3
"""兼容旧命令的 data manager shim。

新代码请使用: python -m scripts.data_manager ...
"""

from scripts.data_manager import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Update active docs and workflows**

Replace current active references:

```bash
python scripts/data-manager.py
```

with:

```bash
python -m scripts.data_manager
```

in:

```text
README.md
agents/workflows/platform-match/AGENT.md
agents/workflows/public-search/AGENT.md
agents/workflows/report/AGENT.md
agents/workflows/screen/AGENT.md
```

- [ ] **Step 6: Update the inventory**

Set the data manager bullets to:

```markdown
- `scripts/data_manager.py`：JSON 数据管理 CLI 的 importable module。
- `scripts/data-manager.py`：旧命令兼容 shim；只转发到 `scripts.data_manager.main()`。
```

- [ ] **Step 7: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_data_manager.py tests/test_script_hygiene.py -q
.venv/bin/python -m py_compile scripts/data_manager.py scripts/data-manager.py
rg -n "python scripts/data-manager.py" README.md agents/workflows docs/manual docs/dev
```

Expected: pytest passes; py_compile passes; `rg` produces no active references. Historical plans and archives can still mention the old command.

- [ ] **Step 8: Commit the data manager compatibility change**

Run:

```bash
git add README.md agents/workflows docs/dev/script-inventory.md tests/test_data_manager.py tests/test_script_hygiene.py tasks/todo.md
git add scripts/data_manager.py scripts/data-manager.py
git add -u scripts
git commit -m "refactor: add importable data manager entrypoint"
```

Expected: commit succeeds.

## Task 6: Preserve And Label Legacy AI Infra Compatibility

**Files:**
- Modify: `docs/dev/script-inventory.md`
- Modify: `tests/test_script_hygiene.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add compatibility documentation guard**

Append to `tests/test_script_hygiene.py`:

```python
def test_ai_infra_legacy_modules_are_documented_as_compatibility_layer() -> None:
    text = INVENTORY.read_text(encoding="utf-8")
    required = [
        "Legacy Compatibility",
        "maimai_ai_infra_search_plan.py",
        "maimai_ai_infra_rank.py",
        "maimai_ai_infra_delivery_report.py",
        "legacy AI Infra strategy",
    ]
    missing = [item for item in required if item not in text]
    assert missing == []
```

- [ ] **Step 2: Run the documentation guard**

Run:

```bash
.venv/bin/python -m pytest tests/test_script_hygiene.py::test_ai_infra_legacy_modules_are_documented_as_compatibility_layer -q
```

Expected: pass after `docs/dev/script-inventory.md` includes the compatibility text from Task 1.

- [ ] **Step 3: Run routing regression tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_maimai_campaign_orchestrator.py \
  tests/test_maimai_ai_infra_strategy.py \
  tests/test_maimai_ai_infra_delivery_report.py \
  -q
```

Expected: tests pass, including both legacy AI Infra routing and generic campaign routing.

- [ ] **Step 4: Record the no-delete decision**

Add this note to `docs/dev/script-inventory.md` under `Legacy Compatibility`:

```markdown
清理原则：`maimai_ai_infra_*` 当前不是一次性脚本；它们是旧策略兼容层。只有在 `maimai_campaign_*` 完成等价迁移、orchestrator 不再路由到旧模块、并且对应回归测试移除旧路径后，才能另起计划删除。
```

- [ ] **Step 5: Commit the compatibility guard**

Run:

```bash
git add docs/dev/script-inventory.md tests/test_script_hygiene.py tasks/todo.md
git commit -m "test: document ai infra legacy compatibility"
```

Expected: commit succeeds.

## Task 7: Final Verification And Completion Record

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-05.md`

- [ ] **Step 1: Run repository verification**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: all tests pass. The previous known warning from old `scripts/test_boss.py` should disappear after moving tests, or appear under `tests/test_boss.py` if the underlying event loop warning remains.

- [ ] **Step 2: Run compile checks for changed script entrypoints**

Run:

```bash
.venv/bin/python -m py_compile scripts/data_manager.py scripts/data-manager.py
```

Expected: command exits with code 0.

- [ ] **Step 3: Run active-reference scans**

Run:

```bash
rg -n "python scripts/data-manager.py" README.md agents/workflows docs/manual docs/dev
rg -n "score_candidates.py|scripts.score_candidates" README.md AGENTS.md agents scripts tests docs/manual docs/dev
rg -n "hunyuan_abc_detail_tasks|hunyuan_abc_parallel_supervisor" README.md AGENTS.md agents scripts tests docs/manual docs/dev
```

Expected: no output for all three commands after the approved cleanup. If Hunyuan deletion was not approved, the third scan is expected to show the approval-gated files and the implementation should already be stopped at Task 4.

- [ ] **Step 4: Run diff hygiene**

Run:

```bash
git diff --check
git diff --cached --check
```

Expected: both commands exit with code 0.

- [ ] **Step 5: Update task records**

In `tasks/todo.md`, write a short Review with:

```markdown
Review：已完成脚本清理第一轮。测试文件已迁移到 `tests/`，`AGENTS.md` 验证命令改为 `.venv/bin/python -m pytest tests -q`；`score_candidates.py` 已从运行时目录删除；Hunyuan ABC 一次性脚本按用户确认结果处理；`data-manager.py` 已改为 shim，新入口为 `python -m scripts.data_manager`；`maimai_ai_infra_*` 保留为 legacy compatibility layer 并有路由回归覆盖；新增 `docs/dev/script-inventory.md` 和 `tests/test_script_hygiene.py` 防止回流。验证：记录 pytest、py_compile、rg 和 diff hygiene 结果。
```

Append the detailed task record to `tasks/archive/2026-05.md`.

- [ ] **Step 6: Commit completion records**

Run:

```bash
git add tasks/todo.md tasks/archive/2026-05.md
git commit -m "chore: record script cleanup completion"
```

Expected: commit succeeds.

## Stop Conditions

- If `rg` shows any active workflow or test still depends on a deletion candidate, stop and update the plan with the exact reference instead of deleting.
- If the user does not approve deletion of `hunyuan_abc_detail_tasks.py` and `hunyuan_abc_parallel_supervisor.ps1`, stop after Task 4 Step 4 and record the blocked state.
- If `.venv/bin/python -m pytest tests -q` fails for behavior unrelated to the cleanup, do not hide it with broad refactors; isolate the failing test and record whether it is pre-existing or caused by the cleanup.
- If any command would touch `data/talent.db`, `data/campaigns/` runtime data, Feishu Drive, or cloud sync state, stop because those paths are outside this script-hygiene plan.

## Self-Review

- Spec coverage: plan covers test relocation, `score_candidates.py` retirement, approval-gated Hunyuan cleanup, `data-manager.py` compatibility modernization, `maimai_ai_infra_*` preservation, script inventory, guardrail tests, task ledger, archive record and final verification.
- Placeholder scan target: the plan intentionally avoids unresolved placeholders and uses exact paths, commands, expected outputs and approval wording.
- Type and name consistency: all referenced tests use `ROOT` and `INVENTORY` defined in Task 1; `scripts.data_manager.main()` exists after Task 5 because the original `scripts/data-manager.py` already defines `main()`.
