# GBrain Open Source Adoption Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the open-source selection loop for Talent-Agent second-brain by validating real GBrain behavior, deciding what to reuse, and replacing placeholder integration with evidence-backed adoption boundaries.

**Architecture:** Keep `talent-agent` repo artifacts as the fact source. Treat GBrain as a rebuildable index and synthesis layer only after a local pilot proves installability, import shape, query quality, citations, gap analysis, and safety boundaries. All production workflow changes remain non-blocking until an explicit adoption gate passes.

**Tech Stack:** Python standard library, pytest, current `scripts.second_brain*` modules, GBrain CLI/MCP as an optional external tool, Markdown research/ADR artifacts, local-only pilot directories under ignored runtime paths.

---

## Current Decision State

Current implementation status:

- `scripts/second_brain_gbrain.py` is a thin optional wrapper around a presumed `gbrain import` command.
- `scripts/second_brain_query.py` primarily uses local case fallback.
- JD delivery remains repo-first and non-blocking, which is correct.
- The open-source selection objective is not closed because we have not run real GBrain, mapped its current CLI/data model, or tested its synthesis/search behavior against Talent-Agent case artifacts.

Recommended adoption stance for this plan:

- **Default:** GBrain is the primary candidate for the derived memory/index layer.
- **Do not make it a hard dependency** until the pilot passes.
- **Do not import private case data into any public/shared source** until access policy is explicit.
- **Do not persist user API keys in repo or chat.**

## Source Facts To Verify During Execution

Use current upstream documentation, not old assumptions:

- GBrain README: `https://github.com/garrytan/gbrain`
- Agent install guide: `https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md`
- Personal brain tutorial: `https://github.com/garrytan/gbrain/blob/master/docs/tutorials/personal-brain.md`
- Company brain tutorial: `https://github.com/garrytan/gbrain/blob/master/docs/tutorials/company-brain.md`
- Skillpack reference: `https://github.com/garrytan/gbrain/blob/master/docs/GBRAIN_SKILLPACK.md`

Key upstream claims to validate locally:

- Local PGLite brain can be initialized with `gbrain init --pglite` or current equivalent.
- GBrain supports raw retrieval via `gbrain search`.
- GBrain supports synthesized answers with citations/gap analysis via `gbrain think`.
- GBrain can serve MCP locally with `gbrain serve`.
- GBrain import/sync expects Markdown directories, not Talent-Agent's current zip bundle shape.

## Files

Create:

- `docs/research/2026-06-12-gbrain-adoption-fit.md`  
  Evidence-backed selection/ADR note with upstream version, install result, capability matrix, risks, and go/no-go decision.
- `docs/research/2026-06-12-gbrain-pilot-report.md`  
  Pilot results: imported corpus, query outputs, citation quality, gap analysis quality, fallback comparison, cost notes.
- `docs/dev/gbrain-second-brain-runbook.md`  
  Operator runbook for local GBrain setup, import, sync, query, rebuild, and troubleshooting.

Modify if the pilot passes:

- `scripts/second_brain_gbrain.py`  
  Replace zip-only wrapper with current GBrain command model: source tree export, import/sync/embed/query/think wrappers, structured unavailable events.
- `scripts/second_brain_query.py`  
  Consume structured GBrain search/think output when available; retain local fallback.
- `scripts/second_brain.py`  
  Add CLI commands for `gbrain-status`, `gbrain-export-source`, `gbrain-query`, and safer `gbrain-rebuild` if supported by verified upstream behavior.
- `agents/skills/jd-talent-delivery/SKILL.md`  
  Document the verified optional GBrain path and the non-blocking fallback.
- `agents/workflows/jd-talent-delivery/AGENT.md`  
  Add the post-run and pre-run operator commands only after local pilot passes.
- `tasks/todo.md` and `tasks/archive/2026-06.md`  
  Track active execution and archive evidence.

Test:

- `tests/test_second_brain_gbrain.py`
- `tests/test_second_brain_query.py`
- `tests/test_second_brain_cli.py`
- Add `tests/fixtures/fake_gbrain.py` or an inline temporary fake CLI helper inside tests.

Runtime-only, not committed unless sanitized:

- `artifacts/gbrain-pilot/`
- `.tmp/gbrain-pilot/`
- Local GBrain home/database directories.

## Execution Gates

Gate A: Current repo state

- Current `main` is ahead of `origin/main` by one local commit: `796f5ad Harden second brain case generation`.
- Before implementation, decide whether to push this commit or keep working locally.
- Recommended: push current clean commit before starting the adoption branch, so the pilot work has a stable base.

Gate B: Install permission

- If `gbrain` is missing, stop and ask before installing Bun or GBrain globally.
- Preferred pilot path is local/isolated: use a temporary `HOME` for `gbrain init` and do not modify user shell profiles unless explicitly approved.

Gate C: Search mode and model cost

- Upstream installer requires explicit search-mode confirmation.
- Default recommendation for first pilot: `conservative` or `balanced`, not `tokenmax`, until query value is proven.
- Do not ask the user for API keys unless the no-key / keyword-only smoke test is insufficient.

Gate D: Private data

- First pilot uses synthetic or public/redacted second-brain case pages only.
- Private case pages require a separate allowlist and access policy.

Gate E: Adoption decision

- Only after pilot evidence exists, choose one:
  - `adopt_primary_index`: GBrain becomes the preferred optional index/synthesis path.
  - `keep_optional_adapter`: current repo-first fallback remains primary; GBrain stays manual.
  - `reject_for_now`: remove or freeze GBrain adapter work and document why.

---

### Task 1: Record Active Task And Push/Park Current Commit Decision

**Files:**

- Modify: `tasks/todo.md`
- Optional command only: `git push`

- [ ] **Step 1: Add Active Task**

Insert this task near the top of `tasks/todo.md` under `## Active Task`:

```markdown
### GBrain 开源选型闭环与真实适配验证

- [ ] 确认当前 second-brain P0 与 GBrain 上游能力差距，形成 evidence-backed adoption decision。
- [ ] 本机/隔离环境验证 GBrain 安装、doctor、import/search/think 或记录明确阻断。
- [ ] 用 Talent-Agent redacted case artifacts 做 pilot，对比 GBrain 与本地 fallback 的查询质量。
- [ ] 根据 pilot 结果调整 adapter/query/workflow/docs，保持 JD delivery 非阻塞。
- [ ] 运行聚焦测试、全量测试和 diff check，归档 Review。

边界：先做开源选型闭环和本地 pilot，不把 GBrain 设为正式硬依赖；不导入 private case 到 public/shared source；不在仓库或聊天中保存 API key；不写 `data/talent.db`。

验证方式：`gbrain --version` / `gbrain doctor --json` / pilot import-query 证据；聚焦测试覆盖 `tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py`；完成后运行 `.venv/bin/python -m pytest tests -q` 和 `git diff --check`。
```

- [ ] **Step 2: Check current branch state**

Run:

```bash
rtk git status --short --branch
rtk git log -1 --oneline
```

Expected before implementation:

```text
* main...origin/main [ahead 1]
clean — nothing to commit
796f5ad Harden second brain case generation
```

- [ ] **Step 3: Ask user whether to push current commit**

Use this exact decision prompt:

```text
当前 main 本地领先 origin/main 一个已验证提交 796f5ad。建议先推送，保证 GBrain 选型闭环从稳定基线开始。是否现在推送这个提交？
```

- [ ] **Step 4: If user approves push**

Run:

```bash
rtk git push
rtk git status --short --branch
```

Expected:

```text
main...origin/main
clean — nothing to commit
```

- [ ] **Step 5: Commit task-ledger-only change if it is the only change**

Run:

```bash
rtk git diff --check
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py -q
rtk git add tasks/todo.md
rtk git diff --cached --check
rtk git commit -m "Plan gbrain adoption closure"
```

Expected:

```text
tests pass
commit created
```

### Task 2: Upstream Reality Check And ADR

**Files:**

- Create: `docs/research/2026-06-12-gbrain-adoption-fit.md`

- [ ] **Step 1: Capture upstream docs and version signals**

Run:

```bash
rtk mkdir -p artifacts/gbrain-pilot/upstream
rtk proxy zsh -lc 'curl -fsSL https://raw.githubusercontent.com/garrytan/gbrain/master/README.md > artifacts/gbrain-pilot/upstream/README.md'
rtk proxy zsh -lc 'curl -fsSL https://raw.githubusercontent.com/garrytan/gbrain/master/INSTALL_FOR_AGENTS.md > artifacts/gbrain-pilot/upstream/INSTALL_FOR_AGENTS.md'
rtk proxy zsh -lc 'curl -fsSL https://raw.githubusercontent.com/garrytan/gbrain/master/docs/GBRAIN_SKILLPACK.md > artifacts/gbrain-pilot/upstream/GBRAIN_SKILLPACK.md'
rtk rg -n "gbrain init|gbrain import|gbrain search|gbrain think|gbrain serve|search mode|PGLite|MCP|OAuth|schema" artifacts/gbrain-pilot/upstream
```

Expected:

```text
rg prints current upstream command references
```

- [ ] **Step 2: Write adoption fit document**

Create `docs/research/2026-06-12-gbrain-adoption-fit.md` with this structure:

```markdown
# GBrain Adoption Fit For Talent-Agent Second Brain

## Decision

Status: proposed
Recommendation: run local pilot before changing production workflow

## Why We Are Evaluating GBrain

- Avoid rebuilding long-term memory, hybrid retrieval, synthesis, citations, gap analysis, graph traversal, and MCP surfaces.
- Keep Talent-Agent repo artifacts as fact source.
- Use GBrain only as a derived, rebuildable index until proven.

## Current Talent-Agent Implementation

- Repo artifacts: event ledger, redacted public case pages, private case pages, source refs.
- GBrain adapter status: thin optional wrapper, not verified against current upstream CLI.
- Query status: local fallback is primary.

## Upstream Capabilities To Reuse

| Capability | Upstream evidence | Talent-Agent use | Adoption status |
| --- | --- | --- | --- |
| Local PGLite brain | README / install guide | local pilot | unverified |
| Markdown import/sync | README / install guide | import public case pages | unverified |
| `gbrain search` | README | raw calibration retrieval | unverified |
| `gbrain think` | README | cited synthesis + gap analysis | unverified |
| Knowledge graph | README / skillpack | candidate/company/JD relationships | later |
| MCP server | README / tutorials | Codex/agent memory tool | later |
| Search mode cost controls | install guide | prevent surprise spend | must gate |

## Risks

- CLI shape may differ from our current zip adapter.
- GBrain may require Bun and external embedding providers for full value.
- Private case data needs access policy before import.
- Self-hosted operational burden may outweigh P0 value.

## Pilot Acceptance Criteria

- Install or explicit blocker documented.
- A redacted Talent-Agent source tree imports without private data leakage.
- At least three JD calibration queries return useful citations or gap notes.
- Fallback remains available when GBrain is missing.
- Recommended adoption status is one of: `adopt_primary_index`, `keep_optional_adapter`, `reject_for_now`.
```

- [ ] **Step 3: Verify document has no placeholders**

Run:

```bash
rtk rg -n "TBD|TODO|FIXME|PLACEHOLDER" docs/research/2026-06-12-gbrain-adoption-fit.md || true
rtk git diff --check -- docs/research/2026-06-12-gbrain-adoption-fit.md
```

Expected:

```text
no placeholder matches
diff check clean
```

- [ ] **Step 4: Commit ADR**

Run:

```bash
rtk git add docs/research/2026-06-12-gbrain-adoption-fit.md
rtk git diff --cached --check
rtk git commit -m "Evaluate gbrain adoption fit"
```

Expected:

```text
commit created
```

### Task 3: Local GBrain Smoke Test In Isolated Home

**Files:**

- Modify: `docs/research/2026-06-12-gbrain-adoption-fit.md`
- Create runtime evidence under: `artifacts/gbrain-pilot/smoke/`

- [ ] **Step 1: Check whether GBrain is already installed**

Run:

```bash
rtk proxy zsh -lc 'command -v gbrain || true'
rtk proxy zsh -lc 'gbrain --version || true'
```

Expected:

```text
Either a version prints, or command is missing
```

- [ ] **Step 2: If GBrain is missing, stop for install approval**

Ask the user:

```text
本机未找到 gbrain。上游推荐通过 Bun 安装：`bun install -g github:garrytan/gbrain`。是否允许我安装 Bun/GBrain，还是先只完成文档级选型并暂停？
```

- [ ] **Step 3: If user approves install**

Run:

```bash
rtk proxy zsh -lc 'command -v bun || curl -fsSL https://bun.sh/install | bash'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; bun install -g github:garrytan/gbrain'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; gbrain --version'
```

Expected:

```text
gbrain prints a version number
```

- [ ] **Step 4: Initialize an isolated smoke brain**

Run:

```bash
rtk mkdir -p artifacts/gbrain-pilot/smoke
rtk proxy zsh -lc 'set -e; export PATH="$HOME/.bun/bin:$PATH"; tmp_home="$(pwd)/artifacts/gbrain-pilot/smoke/home"; mkdir -p "$tmp_home"; HOME="$tmp_home" gbrain init --pglite | tee artifacts/gbrain-pilot/smoke/init.log'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain doctor --json > artifacts/gbrain-pilot/smoke/doctor.json'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain stats > artifacts/gbrain-pilot/smoke/stats.txt || true'
```

Expected:

```text
doctor.json exists
init.log exists
```

- [ ] **Step 5: Search mode gate**

Inspect `artifacts/gbrain-pilot/smoke/init.log`. If upstream printed a search-mode/cost prompt, ask the user before changing config:

```text
GBrain 初始化提示需要选择 search mode。建议 pilot 先用 balanced，避免 tokenmax 成本膨胀。是否确认使用 balanced？
```

If approved:

```bash
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain config set search.mode balanced'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain search modes > artifacts/gbrain-pilot/smoke/search-modes.txt'
```

- [ ] **Step 6: Update adoption fit document**

Append:

```markdown
## Local Smoke Result

- `gbrain --version`: <actual version or blocker>
- `gbrain init --pglite`: <passed/failed>
- `gbrain doctor --json`: <passed/failed and key finding>
- Search mode selected: <mode or not configured>
- Install notes: <Bun/global install/no install>
```

Replace `<...>` with actual evidence before committing.

- [ ] **Step 7: Commit smoke result**

Run:

```bash
rtk rg -n "<actual|<passed|<mode|<Bun" docs/research/2026-06-12-gbrain-adoption-fit.md && exit 1 || true
rtk git diff --check -- docs/research/2026-06-12-gbrain-adoption-fit.md
rtk git add docs/research/2026-06-12-gbrain-adoption-fit.md
rtk git diff --cached --check
rtk git commit -m "Record gbrain smoke test"
```

Expected:

```text
commit created
```

### Task 4: Redacted Talent-Agent Source Tree Pilot

**Files:**

- Modify: `scripts/second_brain_gbrain.py`
- Test: `tests/test_second_brain_gbrain.py`
- Create runtime pilot tree under: `artifacts/gbrain-pilot/brain/`

- [ ] **Step 1: Write failing test for source-tree export**

Add this test to `tests/test_second_brain_gbrain.py`:

```python
def test_export_source_tree_includes_public_cases_and_events_without_private_cases(
    tmp_path: Path,
) -> None:
    (tmp_path / "docs" / "second-brain" / "cases").mkdir(parents=True)
    (tmp_path / "data" / "second-brain").mkdir(parents=True)
    (tmp_path / "data" / "second-brain" / "private-cases").mkdir(parents=True)
    (tmp_path / "docs" / "second-brain" / "cases" / "public.md").write_text(
        "# Public Case\n\nEvidence only.\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "second-brain" / "private-cases" / "private.md").write_text(
        "# Private Case\n\n张三\n",
        encoding="utf-8",
    )
    (tmp_path / "data" / "second-brain" / "events.jsonl").write_text(
        '{"event_type":"batch_feedback_summarized","visibility":"public"}\n',
        encoding="utf-8",
    )

    from scripts.second_brain_gbrain import export_source_tree

    out_dir = export_source_tree(repo_root=tmp_path, out_dir=tmp_path / "brain")

    assert (out_dir / "cases" / "public.md").exists()
    assert (out_dir / "events" / "events.jsonl").exists()
    assert not (out_dir / "private-cases").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py::test_export_source_tree_includes_public_cases_and_events_without_private_cases -q
```

Expected:

```text
FAIL because export_source_tree is missing
```

- [ ] **Step 3: Implement minimal source-tree export**

Add to `scripts/second_brain_gbrain.py`:

```python
def export_source_tree(*, repo_root: str | Path, out_dir: str | Path) -> Path:
    repo = Path(repo_root)
    target = Path(out_dir)
    cases_out = target / "cases"
    events_out = target / "events"
    cases_out.mkdir(parents=True, exist_ok=True)
    events_out.mkdir(parents=True, exist_ok=True)

    public_case_dir = repo / "docs" / "second-brain" / "cases"
    if public_case_dir.exists():
        for path in sorted(public_case_dir.glob("*.md")):
            if path.is_file():
                (cases_out / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

    events_path = repo / "data" / "second-brain" / "events.jsonl"
    if events_path.exists():
        (events_out / "events.jsonl").write_text(events_path.read_text(encoding="utf-8"), encoding="utf-8")

    return target
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py -q
```

Expected:

```text
tests pass
```

- [ ] **Step 5: Generate pilot source tree**

Run:

```bash
rtk .venv/bin/python - <<'PY'
from pathlib import Path
from scripts.second_brain_gbrain import export_source_tree
out = export_source_tree(repo_root=Path("."), out_dir=Path("artifacts/gbrain-pilot/brain"))
print(out)
PY
rtk find artifacts/gbrain-pilot/brain -maxdepth 3 -type f | sort
```

Expected:

```text
Only public case/events files are listed; no private-cases directory
```

- [ ] **Step 6: Commit source-tree export**

Run:

```bash
rtk git diff --check
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py -q
rtk git add scripts/second_brain_gbrain.py tests/test_second_brain_gbrain.py
rtk git diff --cached --check
rtk git commit -m "Export gbrain source tree"
```

Expected:

```text
commit created
```

### Task 5: Real Import/Search/Think Pilot

**Files:**

- Create: `docs/research/2026-06-12-gbrain-pilot-report.md`
- Runtime evidence: `artifacts/gbrain-pilot/query/`

- [ ] **Step 1: Import pilot tree into isolated GBrain**

Run:

```bash
rtk mkdir -p artifacts/gbrain-pilot/query
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain import "$(pwd)/artifacts/gbrain-pilot/brain" --no-embed | tee artifacts/gbrain-pilot/query/import.log'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain search "多模态视频算法 顾问反馈 不认可 原因" > artifacts/gbrain-pilot/query/search-multimodal.txt'
rtk proxy zsh -lc 'export PATH="$HOME/.bun/bin:$PATH"; HOME="$(pwd)/artifacts/gbrain-pilot/smoke/home" gbrain think "针对新的多模态视频算法 JD，历史顾问反馈提示我应该如何调整推荐理由？请列出引用和不知道的缺口。" > artifacts/gbrain-pilot/query/think-multimodal.txt || true'
```

Expected:

```text
import.log exists
search-multimodal.txt exists
think-multimodal.txt exists or explicit missing-key/model blocker exists
```

- [ ] **Step 2: Write pilot report**

Create `docs/research/2026-06-12-gbrain-pilot-report.md`:

```markdown
# GBrain Pilot Report For Talent-Agent Second Brain

## Pilot Setup

- GBrain version:
- Install mode:
- Search mode:
- Source tree:
- Private data included: no

## Import Result

- Command:
- Result:
- Errors:

## Query 1: Raw Search

- Query:
- Useful hits:
- Citation/source quality:
- Missing data:

## Query 2: Think / Synthesis

- Query:
- Answer usefulness:
- Citation quality:
- Gap analysis quality:
- Failure/blocker:

## Comparison Against Local Fallback

- Local fallback strengths:
- GBrain strengths:
- GBrain weaknesses:

## Recommendation

Decision: keep_optional_adapter

Rationale:

Next changes:
```

Fill every bullet with actual evidence before committing.

- [ ] **Step 3: Verify no empty evidence fields**

Run:

```bash
rtk rg -n "^- [A-Za-z ]+:$|^Decision: $" docs/research/2026-06-12-gbrain-pilot-report.md && exit 1 || true
rtk git diff --check -- docs/research/2026-06-12-gbrain-pilot-report.md
```

Expected:

```text
no empty evidence fields
```

- [ ] **Step 4: Ask adoption gate question**

Ask the user:

```text
Pilot 结果已经记录。我的建议是 `<actual decision>`。你是否同意按这个 adoption level 修改 adapter/query/workflow，还是先停在文档结论？
```

- [ ] **Step 5: Commit pilot report**

Run:

```bash
rtk git add docs/research/2026-06-12-gbrain-pilot-report.md
rtk git diff --cached --check
rtk git commit -m "Record gbrain pilot report"
```

Expected:

```text
commit created
```

### Task 6: Adapter And Query Integration After Adoption Gate

**Files:**

- Modify: `scripts/second_brain_gbrain.py`
- Modify: `scripts/second_brain_query.py`
- Modify: `scripts/second_brain.py`
- Test: `tests/test_second_brain_gbrain.py`
- Test: `tests/test_second_brain_query.py`
- Test: `tests/test_second_brain_cli.py`

- [ ] **Step 1: Write fake CLI test for current GBrain commands**

Add a helper test that creates an executable fake `gbrain` in `tmp_path` and asserts command shape:

```python
def test_query_gbrain_uses_search_and_think_commands(tmp_path: Path) -> None:
    fake = tmp_path / "gbrain"
    log = tmp_path / "calls.log"
    fake.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        f"pathlib.Path({str(log)!r}).write_text(' '.join(sys.argv[1:]) + '\\n', encoding='utf-8')\n"
        "if sys.argv[1] == 'search':\n"
        "    print('CASE: docs/second-brain/cases/example.md')\n"
        "elif sys.argv[1] == 'think':\n"
        "    print('Answer with citation docs/second-brain/cases/example.md')\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)

    from scripts.second_brain_gbrain import query_gbrain

    result = query_gbrain(
        repo_root=tmp_path,
        query="多模态 JD 校准",
        gbrain_bin=str(fake),
    )

    assert result["status"] == "queried"
    assert "docs/second-brain/cases/example.md" in result["think"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py::test_query_gbrain_uses_search_and_think_commands -q
```

Expected:

```text
FAIL because query_gbrain is missing
```

- [ ] **Step 3: Implement minimal `query_gbrain` wrapper**

Add to `scripts/second_brain_gbrain.py`:

```python
def query_gbrain(
    *,
    repo_root: str | Path,
    query: str,
    gbrain_bin: str = "gbrain",
) -> dict[str, Any]:
    repo = Path(repo_root)
    resolved = shutil.which(gbrain_bin) if "/" not in gbrain_bin else gbrain_bin
    if not resolved or not Path(resolved).exists():
        return {"status": "gbrain_unavailable", "reason": "gbrain binary not found"}
    search = subprocess.run(
        [resolved, "search", query],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    think = subprocess.run(
        [resolved, "think", query],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if search.returncode != 0 and think.returncode != 0:
        return {
            "status": "gbrain_unavailable",
            "reason": think.stderr.strip() or search.stderr.strip() or "gbrain query failed",
        }
    return {
        "status": "queried",
        "search": search.stdout,
        "think": think.stdout,
    }
```

- [ ] **Step 4: Thread GBrain result into historical calibration**

Add tests in `tests/test_second_brain_query.py` asserting that a GBrain result with citation/gap text appears in `historical-calibration.json` and Markdown.

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_query.py -q
```

Expected:

```text
tests pass
```

- [ ] **Step 5: Add CLI command**

Add `gbrain-query` to `scripts/second_brain.py` with args:

```text
--repo-root
--query
--out
--gbrain-bin
```

The command writes JSON containing:

```json
{
  "status": "queried",
  "search": "...",
  "think": "..."
}
```

Tests in `tests/test_second_brain_cli.py` must run with a fake CLI path, not real GBrain.

- [ ] **Step 6: Run focused tests**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py -q
```

Expected:

```text
tests pass
```

- [ ] **Step 7: Commit adapter integration**

Run:

```bash
rtk git diff --check
rtk git add scripts/second_brain_gbrain.py scripts/second_brain_query.py scripts/second_brain.py tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py
rtk git diff --cached --check
rtk git commit -m "Integrate verified gbrain query path"
```

Expected:

```text
commit created
```

### Task 7: Runbook And Workflow Contract

**Files:**

- Create: `docs/dev/gbrain-second-brain-runbook.md`
- Modify: `agents/skills/jd-talent-delivery/SKILL.md`
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Test: `tests/test_agent_architecture.py`

- [ ] **Step 1: Write runbook**

Create `docs/dev/gbrain-second-brain-runbook.md`:

```markdown
# GBrain Second Brain Runbook

## Boundary

- Talent-Agent repo artifacts are the fact source.
- GBrain is a derived index/synthesis layer.
- JD delivery must not fail because GBrain is unavailable.
- Private case import requires explicit access-policy approval.

## Local Pilot Setup

1. Verify CLI: `gbrain --version`
2. Verify health: `gbrain doctor --json`
3. Export source tree: `.venv/bin/python -m scripts.second_brain gbrain-export-source --repo-root . --out artifacts/gbrain-pilot/brain`
4. Import source tree: `gbrain import artifacts/gbrain-pilot/brain --no-embed`
5. Query: `gbrain search "<query>"`
6. Synthesize: `gbrain think "<query>"`

## Search Mode

Use `balanced` for pilot unless the user explicitly chooses another mode.

## Troubleshooting

- Missing binary: adapter returns `gbrain_unavailable`.
- Missing API keys: keyword search may work; synthesis may fail.
- Bad citation quality: keep local fallback primary.
- Private data concern: stop and inspect source tree before import.
```

- [ ] **Step 2: Update JD skill/workflow contract**

Add a short contract:

```markdown
GBrain is optional. Before each JD run, operators may generate historical calibration through verified GBrain query commands. If GBrain is unavailable or pilot adoption is not approved, use local fallback. Do not block JD delivery.
```

- [ ] **Step 3: Run architecture test**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected:

```text
tests pass
```

- [ ] **Step 4: Commit docs**

Run:

```bash
rtk git diff --check
rtk git add docs/dev/gbrain-second-brain-runbook.md agents/skills/jd-talent-delivery/SKILL.md agents/workflows/jd-talent-delivery/AGENT.md
rtk git diff --cached --check
rtk git commit -m "Document verified gbrain second brain workflow"
```

Expected:

```text
commit created
```

### Task 8: Final Verification, Archive, And User Handoff

**Files:**

- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run focused tests**

Run:

```bash
rtk .venv/bin/python -m pytest tests/test_second_brain_gbrain.py tests/test_second_brain_query.py tests/test_second_brain_cli.py tests/test_agent_architecture.py -q
```

Expected:

```text
tests pass
```

- [ ] **Step 2: Run full verification**

Run:

```bash
rtk git diff --check
rtk .venv/bin/python -m pytest tests -q
```

Expected:

```text
diff check clean
all tests pass, allowing existing warning if unchanged
```

- [ ] **Step 3: Archive task record**

Append to `tasks/archive/2026-06.md`:

```markdown
# GBrain 开源选型闭环与真实适配验证（2026-06-12）

## 结论

- Adoption decision:
- Reason:

## Evidence

- GBrain version:
- Smoke result:
- Pilot import:
- Search/think result:
- Tests:

## Follow-up

- 
```

Fill each field with actual evidence.

- [ ] **Step 4: Update Recent Done**

Add a one-line summary to `tasks/todo.md` under `## Recent Done`, and remove the Active Task block if complete.

- [ ] **Step 5: Commit archive**

Run:

```bash
rtk git diff --check
rtk git add tasks/todo.md tasks/archive/2026-06.md
rtk git diff --cached --check
rtk git commit -m "Record gbrain adoption closure"
```

Expected:

```text
commit created
```

- [ ] **Step 6: Present final handoff**

Report:

```text
结论：<adoption decision>
关键证据：<3 bullets>
修改范围：<files>
验证：<test counts>
下一步：<push / defer / follow-up>
```

## Self-Review

- Spec coverage: covers open-source selection, install verification, source-shape mapping, pilot query quality, integration decision, implementation, docs, tests, and archive.
- Placeholder scan: remaining angle-bracket examples appear only in instructions that require replacement during execution; execution steps explicitly require failing if placeholders remain before commit.
- Type consistency: planned functions are `export_source_tree` and `query_gbrain`; current module is `scripts.second_brain_gbrain`; current query builder remains `build_historical_calibration`.
- Safety: keeps GBrain optional, preserves repo-first source of truth, uses isolated pilot home, blocks private data import without approval, and gates API key/search-mode decisions.
