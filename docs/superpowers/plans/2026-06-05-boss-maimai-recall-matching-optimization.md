# BOSS-Maimai Recall Matching Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve BOSS-to-Maimai profile recall for already-screened BOSS candidates while keeping identity binding conservative and auditable.

**Architecture:** Keep BOSS as the primary source and Maimai as supplement. Extend pure matching utilities in `scripts/cross_channel_identity.py`, then have `scripts/boss_maimai_targets.py` export richer target evidence and query plans. Do not touch platform execution, Campaign DB import, main `data/talent.db`, or Feishu publishing in this implementation.

**Safety adjustment from implementation review:** school evidence inferred from free text is exported as `school_fallbacks`, not explicit `schools`; it may generate `name_school_fallback` only and must not generate auto-bindable `name_school_title_core`.

**Tech Stack:** Python 3.12, pytest, JSONL campaign artifacts, existing `scripts.*` modules.

---

## File Structure

- Modify `scripts/cross_channel_identity.py`
  - Add deterministic company alias helpers.
  - Extend `BossMaimaiTarget` and `QuerySpec` with optional evidence fields.
  - Extend query plan generation with non-auto-bind alias and school fallback levels.
  - Score alias company hits without relaxing auto-bind.

- Modify `scripts/boss_maimai_targets.py`
  - Export `company_aliases`.
  - Extract known school evidence from BOSS detail text as fallback-only `school_fallbacks`.
  - Preserve BOSS primary fields unchanged.

- Modify `tests/test_cross_channel_identity.py`
  - Add red tests for alias query plan, alias scoring, and school fallback conservatism.

- Modify `tests/test_boss_maimai_targets.py`
  - Add red tests for school extraction from BOSS text and exported alias query plans.

- Modify `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
  - Update canonical query levels and safety language.

- Modify `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
  - Mirror query-level and fallback safety contract.

- Modify `tests/test_agent_architecture.py`
  - Add or extend a contract test so future edits do not remove alias/school fallback safety.

- Modify `tasks/todo.md`
  - Mark implementation plan written and later track implementation progress.

Do not modify:

- `data/talent.db`
- `data/campaigns/*/talent.db`
- Feishu cloud artifacts
- CDP/browser scripts
- live campaign raw files

---

### Task 1: Company Alias Query Plan

**Files:**
- Modify: `tests/test_cross_channel_identity.py`
- Modify: `scripts/cross_channel_identity.py`

- [ ] **Step 1: Write failing company alias tests**

Append these tests near the existing query-plan tests in `tests/test_cross_channel_identity.py`:

```python
def test_build_company_aliases_normalizes_helmholtz_variants() -> None:
    aliases = build_company_aliases("亥姆霍兹信息安全中心(德国)")

    assert aliases == ("亥姆霍兹信息安全中心", "海姆霍兹信息安全中心")


def test_query_plan_includes_non_auto_bind_company_alias_for_helmholtz() -> None:
    target = BossMaimaiTarget(
        target_id="boss-app-f2215ccc5789dae01223268d",
        candidate_key="boss-app:f2215ccc5789dae01223268d",
        real_name="周超",
        current_company="亥姆霍兹信息安全中心",
        current_title="大模型算法",
        schools=("伦敦大学学院",),
    )

    plan = [item.to_dict() for item in build_query_plan(target)]

    assert {
        "level": "name_company_alias",
        "text": "周超 海姆霍兹信息安全中心",
        "allow_auto_bind": False,
        "evidence_type": "company_alias",
    } in plan
    assert {
        "level": "name_company_alias_title_core",
        "text": "周超 海姆霍兹信息安全中心 大模型算法",
        "allow_auto_bind": False,
        "evidence_type": "company_alias",
    } in plan
    assert {
        "level": "name_school_fallback",
        "text": "周超 伦敦大学学院",
        "allow_auto_bind": False,
        "evidence_type": "school",
    } in plan
```

Also update the import block:

```python
from scripts.cross_channel_identity import (
    BossMaimaiTarget,
    MaimaiSearchHit,
    build_company_aliases,
    build_query_plan,
    decide_match,
    score_hit,
)
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py::test_build_company_aliases_normalizes_helmholtz_variants tests/test_cross_channel_identity.py::test_query_plan_includes_non_auto_bind_company_alias_for_helmholtz -q
```

Expected: fail because `build_company_aliases` does not exist and query plan lacks alias levels.

- [ ] **Step 3: Implement minimal alias query support**

In `scripts/cross_channel_identity.py`, extend `QuerySpec`:

```python
@dataclass(frozen=True)
class QuerySpec:
    level: str
    text: str
    allow_auto_bind: bool
    evidence_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "level": self.level,
            "text": self.text,
            "allow_auto_bind": self.allow_auto_bind,
        }
        if self.evidence_type:
            data["evidence_type"] = self.evidence_type
        return data
```

Extend `BossMaimaiTarget`:

```python
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
    company_aliases: tuple[str, ...] = ()
    boss_payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "candidate_key": self.candidate_key,
            "real_name": self.real_name,
            "current_company": self.current_company,
            "current_title": self.current_title,
            "city": self.city,
            "education": self.education,
            "recent_companies": list(self.recent_companies),
            "schools": list(self.schools),
            "company_aliases": list(self.company_aliases),
            "boss_payload": dict(self.boss_payload),
        }
```

Update `_target_from_mapping()` with:

```python
company_aliases=_as_tuple(value.get("company_aliases")),
```

Add helper functions below `_dedupe`-style helpers, before `build_query_plan()`:

```python
COMPANY_SUFFIX_PATTERN = re.compile(r"[（(][^（）()]+[）)]$")
HELMHOLTZ_COMPANY_ALIASES = {
    "亥姆霍兹信息安全中心": ("海姆霍兹信息安全中心",),
    "海姆霍兹信息安全中心": ("亥姆霍兹信息安全中心",),
}


def _dedupe_texts(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _clean_text(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def _strip_company_suffix(company: str) -> str:
    return COMPANY_SUFFIX_PATTERN.sub("", _clean_text(company)).strip()


def build_company_aliases(company: str) -> tuple[str, ...]:
    text = _clean_text(company)
    base = _strip_company_suffix(text)
    values: list[str] = []
    if base and base != text:
        values.append(base)
    for alias in HELMHOLTZ_COMPANY_ALIASES.get(base, ()):
        values.append(alias)
    return _dedupe_texts(values)


def _target_company_aliases(item: BossMaimaiTarget) -> tuple[str, ...]:
    return _dedupe_texts([
        *item.company_aliases,
        *build_company_aliases(item.current_company),
    ])
```

Replace `build_query_plan()` with this version:

```python
def build_query_plan(target: BossMaimaiTarget | Mapping[str, Any]) -> list[QuerySpec]:
    item = _target_from_mapping(target)
    title_core = _title_core(item.current_title)
    recent_company = next((company for company in item.recent_companies if company), "")
    school = next((school for school in item.schools if school), "")
    company_aliases = _target_company_aliases(item)
    plan: list[QuerySpec] = []
    if title_core and item.current_company:
        plan.append(QuerySpec("name_company_title", _join_query(item.real_name, item.current_company, item.current_title), True))
        plan.append(QuerySpec("name_company_title_core", _join_query(item.real_name, item.current_company, title_core), True))
    for alias in company_aliases:
        plan.append(QuerySpec("name_company_alias", _join_query(item.real_name, alias), False, "company_alias"))
        if title_core:
            plan.append(QuerySpec("name_company_alias_title_core", _join_query(item.real_name, alias, title_core), False, "company_alias"))
    if title_core and recent_company:
        plan.append(QuerySpec("name_recent_company_title", _join_query(item.real_name, recent_company, title_core), True))
    if title_core and school:
        plan.append(QuerySpec("name_school_title_core", _join_query(item.real_name, school, title_core), True))
    if school:
        plan.append(QuerySpec("name_school_fallback", _join_query(item.real_name, school), False, "school"))
    plan.append(QuerySpec(FALLBACK_LEVEL, _join_query(item.real_name, item.current_company), False))
    return plan
```

- [ ] **Step 4: Run alias tests to verify green**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py::test_build_company_aliases_normalizes_helmholtz_variants tests/test_cross_channel_identity.py::test_query_plan_includes_non_auto_bind_company_alias_for_helmholtz -q
```

Expected: both tests pass.

- [ ] **Step 5: Run full cross-channel identity tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py -q
```

Expected: all tests in `tests/test_cross_channel_identity.py` pass. If existing exact-order tests fail, update their expected lists only when the new alias levels legitimately apply; non-Helmholtz targets should keep existing output shape.

---

### Task 2: BOSS School Evidence Extraction

**Files:**
- Modify: `tests/test_boss_maimai_targets.py`
- Modify: `scripts/boss_maimai_targets.py`

- [ ] **Step 1: Write failing school extraction test**

Append this test to `tests/test_boss_maimai_targets.py`:

```python
def test_export_extracts_school_from_boss_detail_text_and_adds_school_queries(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:zhoucha",
            "real_name": "周超",
            "real_name_status": "captured",
            "current_company": "亥姆霍兹信息安全中心",
            "current_title": "大模型算法",
            "recommendation": "contact",
            "detail_sections": {
                "basic_info": "博士；伦敦大学学院；电子电气工程",
                "summary": "参与 Sparse-ML 项目，研究 efficient and sparse training and LLM finetuning。",
                "work_experience": [
                    {
                        "company": "亥姆霍兹信息安全中心",
                        "title": "大模型算法",
                        "description": "伦敦大学学院电子电气工程博士，研究高效稀疏训练。",
                    }
                ],
            },
        },
    )

    export_targets(root)
    row = json.loads((root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8").strip())
    query_plan = row["query_plan"]

    assert row["schools"] == []
    assert row["school_fallbacks"] == ["伦敦大学学院"]
    assert row["company_aliases"] == ["海姆霍兹信息安全中心"]
    assert not any(item["level"] == "name_school_title_core" for item in query_plan)
    assert {
        "level": "name_school_fallback",
        "text": "周超 伦敦大学学院",
        "allow_auto_bind": False,
        "evidence_type": "school",
    } in query_plan
    assert any(item["text"] == "周超 海姆霍兹信息安全中心" for item in query_plan)
```

- [ ] **Step 2: Run test to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py::test_export_extracts_school_from_boss_detail_text_and_adds_school_queries -q
```

Expected: fail because `school_fallbacks` and `company_aliases` are not exported.

- [ ] **Step 3: Implement school extraction and alias export**

Update imports in `scripts/boss_maimai_targets.py`:

```python
from scripts.cross_channel_identity import BossMaimaiTarget, build_company_aliases, build_query_plan
```

Add helpers near `_as_strings()`:

```python
KNOWN_BOSS_SCHOOL_NAMES = ("伦敦大学学院",)


def _iter_text_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, dict):
        values: list[str] = []
        for item in value.values():
            values.extend(_iter_text_values(item))
        return values
    if isinstance(value, (list, tuple, set)):
        values: list[str] = []
        for item in value:
            values.extend(_iter_text_values(item))
        return values
    return []


def _extract_known_schools_from_texts(values: list[str]) -> list[str]:
    schools: list[str] = []
    for text in values:
        for school in KNOWN_BOSS_SCHOOL_NAMES:
            if school in text:
                schools.append(school)
    return schools
```

Keep `_schools()` limited to explicit structured school evidence and add fallback-only text extraction:

```python
def _schools(row: dict[str, Any]) -> list[str]:
    detail_sections = _detail_container(row, "detail_sections")
    detail = _detail_container(row, "detail")
    values = _as_strings(detail_sections.get("schools"))
    values += _as_strings(detail.get("schools"))
    values += _as_strings(detail_sections.get("education_experience"))
    values += _as_strings(detail.get("education_experience"))
    return _dedupe(values)


def _school_fallbacks(row: dict[str, Any]) -> list[str]:
    detail_sections = _detail_container(row, "detail_sections")
    detail = _detail_container(row, "detail")
    text_values = []
    text_values.extend(_iter_text_values(detail_sections))
    text_values.extend(_iter_text_values(detail))
    text_values.extend(_iter_text_values(row.get("education_detail")))
    return _dedupe(_extract_known_schools_from_texts(text_values))
```

Add helper:

```python
def _company_aliases(row: dict[str, Any]) -> list[str]:
    return list(build_company_aliases(str(row.get("current_company") or "").strip()))
```

Update `_target_from_candidate()`:

```python
def _target_from_candidate(row: dict[str, Any]) -> BossMaimaiTarget:
    return BossMaimaiTarget(
        target_id=safe_target_id(str(row.get("candidate_key") or "")),
        candidate_key=str(row.get("candidate_key") or ""),
        real_name=str(row.get("real_name") or "").strip(),
        current_company=str(row.get("current_company") or "").strip(),
        current_title=str(row.get("current_title") or "").strip(),
        city=str(row.get("city") or "").strip(),
        education=str(row.get("education") or "").strip(),
        recent_companies=tuple(_recent_companies(row)),
        schools=tuple(_schools(row)),
        school_fallbacks=tuple(_school_fallbacks(row)),
        company_aliases=tuple(_company_aliases(row)),
        boss_payload=_boss_payload(row),
    )
```

- [ ] **Step 4: Run school extraction test to verify green**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py::test_export_extracts_school_from_boss_detail_text_and_adds_school_queries -q
```

Expected: pass.

- [ ] **Step 5: Run full target export tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_targets.py -q
```

Expected: all tests in `tests/test_boss_maimai_targets.py` pass. If existing tests assert exact target fields, update them to include `company_aliases` only where the expected candidate company produces aliases.

---

### Task 3: Conservative Alias And School Matching Decisions

**Files:**
- Modify: `tests/test_cross_channel_identity.py`
- Modify: `scripts/cross_channel_identity.py`

- [ ] **Step 1: Write failing conservative decision tests**

Append these tests to `tests/test_cross_channel_identity.py`:

```python
def test_alias_company_hit_scores_company_but_requires_confirmation() -> None:
    target = BossMaimaiTarget(
        target_id="boss-app-f2215ccc5789dae01223268d",
        candidate_key="boss-app:f2215ccc5789dae01223268d",
        real_name="周超",
        current_company="亥姆霍兹信息安全中心",
        current_title="大模型算法",
        company_aliases=("海姆霍兹信息安全中心",),
    )
    hit = MaimaiSearchHit(
        platform_id="239360802",
        name="周超",
        company="海姆霍兹信息安全中心",
        title="博士后",
        profile_url="https://maimai.cn/profile/detail?dstu=239360802",
    )

    decision = decide_match(target, [hit], "name_company_alias", "周超 海姆霍兹信息安全中心")

    assert decision.confidence >= 70
    assert decision.score_breakdown["company"] > 0
    assert decision.match_status == "pending_confirmation"
    assert decision.decision_reason == "score_requires_confirmation"


def test_school_fallback_hit_requires_confirmation() -> None:
    target = BossMaimaiTarget(
        target_id="boss-app-f2215ccc5789dae01223268d",
        candidate_key="boss-app:f2215ccc5789dae01223268d",
        real_name="周超",
        current_company="亥姆霍兹信息安全中心",
        current_title="大模型算法",
        schools=("伦敦大学学院",),
    )
    hit = MaimaiSearchHit(
        platform_id="239360802",
        name="周超",
        company="海姆霍兹信息安全中心",
        title="大模型算法",
        schools=("伦敦大学学院",),
    )

    decision = decide_match(target, [hit], "name_school_fallback", "周超 伦敦大学学院")

    assert decision.confidence >= 70
    assert decision.score_breakdown["school"] > 0
    assert decision.match_status == "pending_confirmation"
    assert decision.decision_reason == "score_requires_confirmation"
```

- [ ] **Step 2: Run tests to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py::test_alias_company_hit_scores_company_but_requires_confirmation tests/test_cross_channel_identity.py::test_school_fallback_hit_requires_confirmation -q
```

Expected: alias test fails because alias company score is 0. School fallback may already pass; if it passes, keep it as regression coverage.

- [ ] **Step 3: Implement alias scoring without auto-bind relaxation**

In `scripts/cross_channel_identity.py`, add helper:

```python
def _company_candidates(target: BossMaimaiTarget) -> tuple[str, ...]:
    values = [
        target.current_company,
        *_target_company_aliases(target),
    ]
    for recent in target.recent_companies:
        values.append(recent)
        values.extend(build_company_aliases(recent))
    return _dedupe_texts(values)
```

Replace `_company_score()` with:

```python
def _company_score(target: BossMaimaiTarget, hit: MaimaiSearchHit) -> int:
    hit_companies = (hit.company, *hit.work_companies)
    target_companies = _company_candidates(target)
    for company in hit_companies:
        if _norm(company) and _norm(company) == _norm(target.current_company):
            return COMPANY_WEIGHT
    for company in hit_companies:
        for target_company in target_companies:
            if _norm(company) and _norm(company) == _norm(target_company):
                return COMPANY_WEIGHT - 2
    for company in hit_companies:
        for target_company in target_companies:
            if _contains_match(company, target_company):
                return COMPANY_WEIGHT - 5
    return 0
```

Confirm that `HIGH_PRECISION_LEVELS` does not include `name_company_alias`, `name_company_alias_title_core`, or `name_school_fallback`.

- [ ] **Step 4: Run conservative decision tests to verify green**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py::test_alias_company_hit_scores_company_but_requires_confirmation tests/test_cross_channel_identity.py::test_school_fallback_hit_requires_confirmation -q
```

Expected: both tests pass.

- [ ] **Step 5: Run full identity tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py -q
```

Expected: all tests pass. Existing auto-bind tests must still pass only through original high-precision levels.

---

### Task 4: Canonical Contract Updates

**Files:**
- Modify: `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Write failing architecture contract test**

Add this test to `tests/test_agent_architecture.py` near existing workflow/skill contract tests:

```python
def test_boss_maimai_cross_channel_contract_mentions_alias_and_school_fallback_safety():
    skill = Path("agents/skills/boss-maimai-cross-channel-delivery/SKILL.md").read_text(encoding="utf-8")
    workflow = Path("agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md").read_text(encoding="utf-8")
    combined = skill + "\n" + workflow

    assert "name_company_alias" in combined
    assert "name_school_fallback" in combined
    assert "不得自动绑定" in combined
    assert "BOSS 为 primary" in combined
```

If `Path` is not imported at the top of the file, add:

```python
from pathlib import Path
```

- [ ] **Step 2: Run test to verify red**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_maimai_cross_channel_contract_mentions_alias_and_school_fallback_safety -q
```

Expected: fail because the canonical contracts do not mention the new query levels yet.

- [ ] **Step 3: Update skill contract**

In `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`, replace the query-level list in `## 脉脉匹配规则` with:

```markdown
1. `name_company_title`
2. `name_company_title_core`
3. `name_company_alias`，公司 alias 召回层，不得自动绑定
4. `name_company_alias_title_core`，公司 alias + title core 召回层，不得自动绑定
5. `name_recent_company_title`
6. `name_school_title_core`，仅在 BOSS 明确采集到 `schools` 字段时生成；纯 `education` 学历不得作为该层 auto-bind 证据
7. `name_school_fallback`，姓名 + 学校召回层，不得自动绑定
8. `name_company_fallback`
```

Add this sentence after the list:

```markdown
公司 alias 和学校 fallback 只用于提高召回，不得直接 `auto_bound`；命中后必须进入 `pending_confirmation` 或后续详情强证据确认，BOSS 为 primary 的非空核心字段仍不得被脉脉覆盖。
```

- [ ] **Step 4: Update workflow contract**

In `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`, replace the query-level list in `### S3 身份匹配判定` with the same eight-level list and add the same safety sentence.

- [ ] **Step 5: Run architecture contract test to verify green**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_maimai_cross_channel_contract_mentions_alias_and_school_fallback_safety -q
```

Expected: pass.

---

### Task 5: End-to-End Local Verification

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Update task ledger implementation status**

In `tasks/todo.md`, add or update an Active Task line:

```markdown
- [ ] S3c BOSS-Maimai 召回匹配优化实现：按 `docs/superpowers/plans/2026-06-05-boss-maimai-recall-matching-optimization.md` 执行 TDD，实现公司 alias、学校 fallback 和保守身份判定；不写 DB、不跑平台、不推飞书。
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cross_channel_identity.py tests/test_boss_maimai_targets.py tests/test_agent_architecture.py -q
```

Expected: all focused tests pass.

- [ ] **Step 3: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full suite passes.

- [ ] **Step 4: Check whitespace and changed files**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors. Changed files should be limited to:

```text
scripts/cross_channel_identity.py
scripts/boss_maimai_targets.py
tests/test_cross_channel_identity.py
tests/test_boss_maimai_targets.py
agents/skills/boss-maimai-cross-channel-delivery/SKILL.md
agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md
tests/test_agent_architecture.py
tasks/todo.md
```

Existing unrelated dirty files may remain dirty and must not be reverted.

- [ ] **Step 5: Record completion evidence**

Update `tasks/todo.md` S3c line to checked and include:

```markdown
- [x] S3c BOSS-Maimai 召回匹配优化实现：已完成公司 alias、学校 fallback 和保守身份判定；局部测试与全量测试通过，未写 DB、未跑平台、未推飞书。
```

Do not archive the full task record until the broader BOSS-Maimai delivery task is complete.

---

## Self-Review

- Spec coverage:
  - Company alias generation: Task 1 and Task 3.
  - School evidence extraction: Task 2.
  - Query plan expansion: Task 1 and Task 2.
  - Conservative binding: Task 3 and Task 4.
  - Canonical contract updates: Task 4.
  - Verification: Task 5.

- Placeholder scan:
  - This plan contains no placeholder implementation steps.
  - Every code change step includes concrete snippets.

- Type consistency:
  - `QuerySpec.evidence_type` is optional and omitted from existing non-evidence query dictionaries.
  - `BossMaimaiTarget.company_aliases` is a tuple and exported as a list through `to_dict()`.
  - `build_company_aliases()` returns `tuple[str, ...]`.

---

## Execution Handoff

Plan complete. Two execution options:

1. Subagent-Driven (recommended): dispatch a fresh subagent per task, review between tasks, fast iteration.
2. Inline Execution: execute tasks in this session with checkpoints for review.
