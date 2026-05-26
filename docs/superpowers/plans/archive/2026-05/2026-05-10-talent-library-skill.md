# Talent Library Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `talent-library` aggregate skill as a runtime-neutral workflow for recruiter-facing talent database management.

**Architecture:** Add a canonical workflow under `agents/workflows/talent-library/`, a thin Claude adapter under `.claude/skills/talent-library/`, and small missing data-layer APIs in `TalentDB` for safe update/delete orchestration. Keep business scripts in `scripts/`; runtime-private skill files only adapt to canonical workflows.

**Tech Stack:** Python 3.11+, SQLite/FTS5 via `scripts/talent_db.py`, pytest, Markdown workflow specs, existing `agents/capabilities.md` runtime-neutral contract.

---

## File Structure

Create:

- `agents/workflows/talent-library/AGENT.md` — canonical runtime-neutral workflow and scene router.
- `agents/workflows/talent-library/references/scenarios.md` — detailed scene procedures for import/search/match/score/detail/update/delete.
- `agents/workflows/talent-library/references/data-contract.md` — SQLite-first data contract and output paths.
- `agents/workflows/talent-library/references/safety-rules.md` — hard-delete, batch write, source merge, and platform safety rules.
- `agents/workflows/talent-library/assets/candidate-table-template.md` — reusable candidate result table format.
- `agents/workflows/talent-library/assets/import-report-template.md` — import report structure.
- `agents/workflows/talent-library/assets/delete-confirmation-template.md` — delete dry-run/confirmation format.
- `.claude/skills/talent-library/SKILL.md` — Claude Code thin adapter.
- `tests/test_talent_library_workflow.py` — workflow structure and adapter tests.

Modify:

- `scripts/talent_models.py` — add `DeleteResult` dataclass.
- `scripts/talent_db.py` — add `update_candidate()` and `delete_candidate()` public APIs.
- `tests/test_talent_db.py` — add focused tests for update/delete APIs.
- `tests/test_agent_architecture.py` — include `talent-library` in canonical workflow coverage.
- `tasks/todo.md` — append implementation checklist and review notes.

Do not modify:

- Existing `platform-match`, `screen`, `public-search`, or `report` workflows except for architecture tests that include the new workflow.
- Existing platform adapter behavior.
- Existing `data-manager.py` JSON flows unless a later task explicitly requires compatibility changes.

---

### Task 1: Add Data Model for Hard Delete Results

**Files:**
- Modify: `scripts/talent_models.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Add failing import/test for `DeleteResult`**

Append this import in `tests/test_talent_db.py`:

```python
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
    DeleteResult,
    MatchScore,
    SortSpec,
    SourceProfile,
)
```

Append this test near the existing model/result tests:

```python
def test_delete_result_total_related_rows():
    result = DeleteResult(
        candidate_id=42,
        candidate_deleted=True,
        details_deleted=1,
        sources_deleted=2,
        score_events_deleted=3,
        match_scores_deleted=4,
        vectors_deleted=1,
    )

    assert result.related_rows_deleted == 11
    assert result.to_dict() == {
        "candidate_id": 42,
        "candidate_deleted": True,
        "details_deleted": 1,
        "sources_deleted": 2,
        "score_events_deleted": 3,
        "match_scores_deleted": 4,
        "vectors_deleted": 1,
        "related_rows_deleted": 11,
    }
```

- [ ] **Step 2: Run the focused failing test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_result_total_related_rows -q
```

Expected: FAIL with `ImportError` or `NameError` because `DeleteResult` does not exist.

- [ ] **Step 3: Implement `DeleteResult`**

Add this dataclass to `scripts/talent_models.py` after `IngestResult`:

```python
@dataclass(frozen=True)
class DeleteResult:
    candidate_id: int
    candidate_deleted: bool
    details_deleted: int = 0
    sources_deleted: int = 0
    score_events_deleted: int = 0
    match_scores_deleted: int = 0
    vectors_deleted: int = 0

    @property
    def related_rows_deleted(self) -> int:
        return (
            self.details_deleted
            + self.sources_deleted
            + self.score_events_deleted
            + self.match_scores_deleted
            + self.vectors_deleted
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_deleted": self.candidate_deleted,
            "details_deleted": self.details_deleted,
            "sources_deleted": self.sources_deleted,
            "score_events_deleted": self.score_events_deleted,
            "match_scores_deleted": self.match_scores_deleted,
            "vectors_deleted": self.vectors_deleted,
            "related_rows_deleted": self.related_rows_deleted,
        }
```

- [ ] **Step 4: Run the focused test again**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_result_total_related_rows -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

Run:

```bash
git add scripts/talent_models.py tests/test_talent_db.py
git commit -m "feat: add talent delete result model"
```

Expected: commit succeeds and includes only the model/test changes for this task.

---

### Task 2: Add `TalentDB.update_candidate()`

**Files:**
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing tests for partial update**

Append these tests to `tests/test_talent_db.py` near other CRUD tests:

```python
def test_update_candidate_updates_allowed_fields_without_losing_sources(db_with_candidate):
    db, candidate_id = db_with_candidate

    db.update_candidate(
        candidate_id,
        {
            "current_company": "OpenAI",
            "current_title": "Senior Product Manager",
            "skill_tags": ["AI", "Python", "Agents"],
        },
    )

    candidate = db.get(candidate_id)
    assert candidate is not None
    assert candidate.current_company == "OpenAI"
    assert candidate.current_title == "Senior Product Manager"
    assert candidate.skill_tags == ("AI", "Python", "Agents")

    sources = db.get_sources(candidate_id)
    assert len(sources) == 1
    assert sources[0].platform == "maimai"
    assert sources[0].platform_id == "maimai-1"


def test_update_candidate_rejects_unknown_fields(db_with_candidate):
    db, candidate_id = db_with_candidate

    with pytest.raises(ValueError, match="Unsupported candidate update field"):
        db.update_candidate(candidate_id, {"not_a_field": "value"})


def test_update_candidate_rejects_missing_candidate(db: TalentDB):
    with pytest.raises(ValueError, match="Candidate does not exist"):
        db.update_candidate(999, {"city": "Shanghai"})
```

- [ ] **Step 2: Run failing partial update tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_update_candidate_updates_allowed_fields_without_losing_sources tests/test_talent_db.py::test_update_candidate_rejects_unknown_fields tests/test_talent_db.py::test_update_candidate_rejects_missing_candidate -q
```

Expected: FAIL with `AttributeError: 'TalentDB' object has no attribute 'update_candidate'`.

- [ ] **Step 3: Import typing support if missing**

Confirm `scripts/talent_db.py` already imports `Any`. If not, update the import to include it:

```python
from typing import Any
```

- [ ] **Step 4: Add update field allowlist**

Add this module constant near `_SORT_FIELDS` in `scripts/talent_db.py`:

```python
_CANDIDATE_UPDATE_FIELDS = {
    "name",
    "gender",
    "age",
    "city",
    "work_years",
    "education",
    "current_company",
    "current_title",
    "expected_salary",
    "expected_city",
    "expected_title",
    "hunting_status",
    "skill_tags",
    "data_level",
}
```

- [ ] **Step 5: Implement `update_candidate()`**

Add this public method to `TalentDB` after `get_sources()`:

```python
    def update_candidate(self, candidate_id: int, patch: dict[str, Any]) -> Candidate:
        if not patch:
            existing = self.get(candidate_id)
            if existing is None:
                raise ValueError(f"Candidate does not exist: {candidate_id}")
            return existing

        unsupported = sorted(set(patch) - _CANDIDATE_UPDATE_FIELDS)
        if unsupported:
            raise ValueError(
                "Unsupported candidate update field(s): " + ", ".join(unsupported)
            )

        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        assignments: list[str] = []
        params: list[Any] = []
        for field, value in patch.items():
            assignments.append(f"{field} = ?")
            if field == "skill_tags":
                params.append(_json_dumps(value))
            else:
                params.append(value)

        assignments.append("updated_at = datetime('now')")
        params.append(candidate_id)

        with self._conn:
            self._conn.execute(
                f"""
                UPDATE candidates
                SET {", ".join(assignments)}
                WHERE id = ?
                """,
                tuple(params),
            )

        updated = self.get(candidate_id)
        if updated is None:
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        return updated
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_update_candidate_updates_allowed_fields_without_losing_sources tests/test_talent_db.py::test_update_candidate_rejects_unknown_fields tests/test_talent_db.py::test_update_candidate_rejects_missing_candidate -q
```

Expected: PASS.

- [ ] **Step 7: Run talent DB tests**

Run:

```bash
python -m pytest tests/test_talent_db.py -q
```

Expected: all `test_talent_db.py` tests pass.

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add scripts/talent_db.py tests/test_talent_db.py
git commit -m "feat: support candidate partial updates"
```

Expected: commit succeeds.

---

### Task 3: Add `TalentDB.delete_candidate()`

**Files:**
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing hard-delete tests**

Append these tests to `tests/test_talent_db.py`:

```python
def test_delete_candidate_removes_candidate_and_related_rows(db_with_candidate):
    db, candidate_id = db_with_candidate
    db.enrich(
        candidate_id,
        {
            "work_experience": [{"company": "ByteDance", "title": "PM"}],
            "raw_data": {"source": "detail"},
            "summary": "Experienced product manager",
        },
    )
    db.update_overall_score(
        candidate_id,
        88.0,
        trigger="manual_evaluation",
        detail={"reason": "测试"},
    )
    db.save_match_score(
        candidate_id,
        jd_id="jd-delete-test",
        match_type="final",
        score=91.0,
        dimensions={"岗位匹配度": 90},
        reason="匹配",
    )

    result = db.delete_candidate(candidate_id)

    assert result.candidate_id == candidate_id
    assert result.candidate_deleted is True
    assert result.details_deleted == 1
    assert result.sources_deleted == 1
    assert result.score_events_deleted == 1
    assert result.match_scores_deleted == 1
    assert db.get(candidate_id) is None
    assert db.get_detail(candidate_id) is None
    assert db.get_sources(candidate_id) == []
    assert db.get_match_scores("jd-delete-test") == []


def test_delete_candidate_rejects_missing_candidate(db: TalentDB):
    with pytest.raises(ValueError, match="Candidate does not exist"):
        db.delete_candidate(999)
```

- [ ] **Step 2: Run failing hard-delete tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_candidate_removes_candidate_and_related_rows tests/test_talent_db.py::test_delete_candidate_rejects_missing_candidate -q
```

Expected: FAIL with `AttributeError: 'TalentDB' object has no attribute 'delete_candidate'`.

- [ ] **Step 3: Import `DeleteResult`**

Update the `scripts/talent_db.py` import from `scripts.talent_models` to include `DeleteResult`:

```python
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
    DeleteResult,
    IngestResult,
    MatchScore,
    PageResult,
    PendingMerge,
    SearchHit,
    SortSpec,
    SourceProfile,
    VectorHit,
)
```

- [ ] **Step 4: Implement helper for row counts**

Add this private module function near other helpers in `scripts/talent_db.py`:

```python
def _count_rows(conn: sqlite3.Connection, table: str, column: str, value: Any) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
        (value,),
    ).fetchone()
    return int(row[0])
```

Use only hard-coded table and column names from caller code; never pass user input to `table` or `column`.

- [ ] **Step 5: Implement `delete_candidate()`**

Add this public method to `TalentDB` after `update_candidate()`:

```python
    def delete_candidate(self, candidate_id: int) -> DeleteResult:
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        details_deleted = _count_rows(
            self._conn, "candidate_details", "candidate_id", candidate_id
        )
        sources_deleted = _count_rows(
            self._conn, "source_profiles", "candidate_id", candidate_id
        )
        score_events_deleted = _count_rows(
            self._conn, "score_events", "candidate_id", candidate_id
        )
        match_scores_deleted = _count_rows(
            self._conn, "match_scores", "candidate_id", candidate_id
        )
        vectors_deleted = 0
        if self._vec_available:
            vectors_deleted = _count_rows(
                self._conn, "candidate_vectors", "candidate_id", candidate_id
            )

        with self._conn:
            self._conn.execute(
                "DELETE FROM candidates WHERE id = ?",
                (candidate_id,),
            )

        return DeleteResult(
            candidate_id=candidate_id,
            candidate_deleted=True,
            details_deleted=details_deleted,
            sources_deleted=sources_deleted,
            score_events_deleted=score_events_deleted,
            match_scores_deleted=match_scores_deleted,
            vectors_deleted=vectors_deleted,
        )
```

- [ ] **Step 6: Run focused hard-delete tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_candidate_removes_candidate_and_related_rows tests/test_talent_db.py::test_delete_candidate_rejects_missing_candidate -q
```

Expected: PASS.

- [ ] **Step 7: Run all talent DB tests**

Run:

```bash
python -m pytest tests/test_talent_db.py -q
```

Expected: all `test_talent_db.py` tests pass.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add scripts/talent_db.py scripts/talent_models.py tests/test_talent_db.py
git commit -m "feat: support hard deleting talent records"
```

Expected: commit succeeds.

---

### Task 4: Add Talent Library Canonical Workflow

**Files:**
- Create: `agents/workflows/talent-library/AGENT.md`
- Create: `agents/workflows/talent-library/references/scenarios.md`
- Create: `agents/workflows/talent-library/references/data-contract.md`
- Create: `agents/workflows/talent-library/references/safety-rules.md`
- Create: `agents/workflows/talent-library/assets/candidate-table-template.md`
- Create: `agents/workflows/talent-library/assets/import-report-template.md`
- Create: `agents/workflows/talent-library/assets/delete-confirmation-template.md`

- [ ] **Step 1: Create workflow directories**

Run:

```bash
mkdir agents\workflows\talent-library
mkdir agents\workflows\talent-library\references
mkdir agents\workflows\talent-library\assets
```

Expected: directories exist.

- [ ] **Step 2: Create `AGENT.md`**

Create `agents/workflows/talent-library/AGENT.md` with this content:

```markdown
---
name: talent-library
description: "猎头顾问人才库管理。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。触发词: 人才库、候选人库、导入人才、查询人才、匹配人才、人才评分、抓取详情、更新人才、删除人才、talent library、/talent-library"
---

# talent-library 工作流

## 触发入口

```text
/talent-library                         → 对话式场景路由
/talent-library import <path>           → 人才导入
/talent-library search <query>          → 人才查询
/talent-library match --jd <id|file>    → JD 匹配
/talent-library score <filter>          → 综合评分或 JD 匹配评分
/talent-library detail <candidate-id>   → 详情抓取或信息丰富
/talent-library update <candidate-id>   → 人才信息更新
/talent-library delete <candidate-id>   → 硬删除前确认
```

## 前置检查

1. 读取 `agents/capabilities.md`，确认当前运行时工具映射。
2. 检查 Python 环境：`python --version`，需要 3.11+。
3. 检查主库路径：`data/talent.db`。不存在时允许 `TalentDB` 初始化。
4. 写操作前确认当前工作目录是项目根目录。
5. 平台抓取、详情补全、JD 匹配评分分别转入现有 workflow 或脚本：
   - 平台能力：`agents/workflows/platform-match/AGENT.md`
   - 筛选评估：`agents/workflows/screen/AGENT.md`
   - 评分 pipeline：`scripts/score_pipeline.py`

## 资源索引

| 场景 | 文件 |
| --- | --- |
| 详细场景流程 | `agents/workflows/talent-library/references/scenarios.md` |
| 数据契约 | `agents/workflows/talent-library/references/data-contract.md` |
| 安全规则 | `agents/workflows/talent-library/references/safety-rules.md` |
| 查询表格模板 | `agents/workflows/talent-library/assets/candidate-table-template.md` |
| 导入报告模板 | `agents/workflows/talent-library/assets/import-report-template.md` |
| 删除确认模板 | `agents/workflows/talent-library/assets/delete-confirmation-template.md` |
| 平台搜索/详情 | `agents/workflows/platform-match/AGENT.md` |
| JD 筛选评估 | `agents/workflows/screen/AGENT.md` |
| 本地人才库设计 | `docs/superpowers/specs/2026-05-08-local-talent-database-design.md` |
| Skill 设计 | `docs/superpowers/specs/2026-05-10-talent-library-skill-design.md` |

## 场景路由

1. 判断用户意图属于 `import`、`search`、`match`、`score`、`detail`、`update`、`delete` 中哪一类。
2. 意图明确时直接执行对应场景。
3. 意图模糊时只问一个最小澄清问题。
4. 批量写操作先 dry-run 展示影响范围。
5. 删除、批量更新、评分覆盖必须通过 `human.confirm` 获得明确确认。

## 主数据源

第一版以 SQLite `data/talent.db` 为主库。旧 `data/candidates/*.json` 只作为迁移和兼容入口。

禁止在 workflow 中用临时 SQL 字符串绕过 `scripts/talent_db.py` 的公开 API。缺少能力时先补 Python API 和测试。

## 场景执行

读取 `agents/workflows/talent-library/references/scenarios.md`，按对应场景执行。

## 安全执行

读取 `agents/workflows/talent-library/references/safety-rules.md`。高风险写操作必须先展示影响范围，再等待用户确认。
```

- [ ] **Step 3: Create `scenarios.md`**

Create `agents/workflows/talent-library/references/scenarios.md` with this content:

```markdown
# talent-library 场景流程

## import：人才导入

输入支持插件导出 JSON、平台搜索结果 JSON、旧 `data/candidates/*.json` 和单个候选人 JSON。

流程：
1. 识别输入路径、JSON 类型和平台来源。
2. 平台数据先映射为人才库字段。
3. 调用 `TalentDB.batch_ingest(candidates, platform)`。
4. 展示 created、merged、pending、errors。
5. 有 pending merges 时展示人工确认队列。
6. 用户要求报告时写入 `data/output/talent-import-{YYYY-MM-DD}-{slug}.md`。

## search：人才查询

流程：
1. 将自然语言转换为 `CandidateFilter` 和 `SortSpec`。
2. 结构化过滤调用 `TalentDB.search()`。
3. 关键词检索调用 `TalentDB.fulltext_search()`。
4. 默认每页展示 20 条。
5. 用户要求导出时写入 `data/output/talent-search-{YYYY-MM-DD}-{slug}.md`。

## match：人才匹配

流程：
1. 读取 JD ID、JD 文件、JD 文本或自然语言画像。
2. 从 SQLite 人才库构建候选池。
3. 候选池过大时先按结构化条件和 `overall_score` 粗筛。
4. 需要完整评分时调用 `scripts/score_pipeline.py` 或按 `agents/workflows/screen/AGENT.md` 执行。
5. 用 `TalentDB.save_match_score()` 写回评分。
6. 输出 Top N、匹配理由、关键差距、风险点。

## score：人才评分

规则：
1. 提到 JD、岗位、匹配时，默认做 JD 匹配评分。
2. 提到综合评分、人才质量、候选人质量分时，做 `overall_score`。
3. 模糊时先询问评分类型。
4. 综合评分写入 `TalentDB.update_overall_score()`。
5. JD 匹配评分写入 `TalentDB.save_match_score()`。

## detail：详情抓取

流程：
1. 查询候选人的 `source_profiles`。
2. 有平台 ID 或 profile URL 时优先走平台详情能力。
3. 没有平台线索时转入 `platform-match` 搜索并确认身份。
4. 字段映射后调用 `TalentDB.enrich()`。
5. 置信度不足时禁止自动写入详情。

## update：人才更新

流程：
1. 查询并展示当前记录摘要。
2. 解析更新意图。
3. 校验字段。
4. dry-run 展示将变更的字段。
5. 用户确认后调用 `TalentDB.update_candidate()`、`TalentDB.enrich()`、`TalentDB.resolve_merge()` 或评分 API。
6. 展示变更摘要。

## delete：人才删除

流程：
1. 定位候选人。
2. 多条命中时展示列表并要求用户选择。
3. 展示 `candidates`、`candidate_details`、`source_profiles`、`score_events`、`match_scores`、`candidate_vectors` 影响范围。
4. 要求用户明确确认，例如 `确认删除候选人 123`。
5. 调用 `TalentDB.delete_candidate(candidate_id)`。
6. 输出删除摘要。
7. 旧 JSON 同步删除必须单独确认。
```

- [ ] **Step 4: Create `data-contract.md`**

Create `agents/workflows/talent-library/references/data-contract.md` with this content:

```markdown
# talent-library 数据契约

## 主库

主数据源是 `data/talent.db`。

核心 API：
- `TalentDB.ingest(data, platform)`
- `TalentDB.batch_ingest(candidates, platform)`
- `TalentDB.search(filters, sort, page, page_size)`
- `TalentDB.fulltext_search(query, limit)`
- `TalentDB.get(candidate_id)`
- `TalentDB.get_detail(candidate_id)`
- `TalentDB.get_sources(candidate_id)`
- `TalentDB.update_candidate(candidate_id, patch)`
- `TalentDB.enrich(candidate_id, detail_data)`
- `TalentDB.update_overall_score(candidate_id, score, trigger, detail)`
- `TalentDB.save_match_score(candidate_id, jd_id, match_type, score, dimensions, reason)`
- `TalentDB.delete_candidate(candidate_id)`

## 旧 JSON

`data/candidates/*.json` 只作为迁移和兼容入口。新写入默认进入 SQLite。SQLite 删除不自动删除旧 JSON。

## 输出

输出目录是 `data/output/`。

命名：
- `talent-import-{YYYY-MM-DD}-{slug}.md`
- `talent-search-{YYYY-MM-DD}-{slug}.md`
- `talent-match-{YYYY-MM-DD}-{slug}.md`
- `talent-score-{YYYY-MM-DD}-{slug}.md`
- `talent-detail-{YYYY-MM-DD}-{slug}.md`
- `talent-update-{YYYY-MM-DD}-{slug}.md`
- `talent-delete-{YYYY-MM-DD}-{slug}.md`
```

- [ ] **Step 5: Create `safety-rules.md`**

Create `agents/workflows/talent-library/references/safety-rules.md` with this content:

```markdown
# talent-library 安全规则

1. 删除必须二次确认。
2. 批量更新和批量删除必须先 dry-run。
3. 来源数据只追加，不静默覆盖。
4. 评分覆盖必须写入事件或匹配记录。
5. 平台抓取遵守 `platform-match` 限流、session 和熔断规则。
6. 身份匹配置信度不足时，不自动合并或写入详情。
7. 写库失败时必须输出失败原因和已完成/未完成范围。
8. 不在 workflow 中拼接临时 SQL 绕过 `TalentDB`。
```

- [ ] **Step 6: Create asset templates**

Create `agents/workflows/talent-library/assets/candidate-table-template.md`:

```markdown
| ID | 姓名 | 公司 | 职位 | 城市 | 年限 | 学历 | 数据级别 | 综合分 | 来源 |
| --- | --- | --- | --- | --- | ---: | --- | --- | ---: | --- |
| <id> | <name> | <company> | <title> | <city> | <work_years> | <education> | <data_level> | <overall_score> | <platforms> |
```

Create `agents/workflows/talent-library/assets/import-report-template.md`:

```markdown
# 人才导入报告

## 输入
- 来源：<source>
- 平台：<platform>
- 文件：<path>

## 结果
- 新建：<created>
- 合并：<merged>
- 待确认合并：<pending>
- 失败：<errors>

## 失败明细
<error_details>
```

Create `agents/workflows/talent-library/assets/delete-confirmation-template.md`:

```markdown
# 删除确认

## 候选人
- ID：<candidate_id>
- 姓名：<name>
- 公司：<company>
- 职位：<title>

## 将删除的关联数据
- 详情记录：<details_count>
- 来源记录：<sources_count>
- 综合评分事件：<score_events_count>
- JD 匹配评分：<match_scores_count>
- 向量记录：<vectors_count>

请用户明确确认：确认删除候选人 <candidate_id>
```

- [ ] **Step 7: Commit Task 4**

Run:

```bash
git add agents/workflows/talent-library
git commit -m "feat: add talent library workflow"
```

Expected: commit succeeds.

---

### Task 5: Add Claude Adapter and Architecture Tests

**Files:**
- Create: `.claude/skills/talent-library/SKILL.md`
- Modify: `tests/test_agent_architecture.py`
- Create: `tests/test_talent_library_workflow.py`

- [ ] **Step 1: Create Claude adapter**

Create `.claude/skills/talent-library/SKILL.md`:

```markdown
---
name: talent-library
description: "猎头顾问人才库管理。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。触发词: 人才库、候选人库、导入人才、查询人才、匹配人才、人才评分、抓取详情、更新人才、删除人才、talent library、/talent-library"
---

# Claude Code Adapter: talent-library

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/talent-library/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/talent-library/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch 或可用搜索 MCP
   - `web.fetch` -> 可用网页读取 MCP
   - `browser.operate` -> MCP browser / Playwright
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
```

- [ ] **Step 2: Update canonical workflow list**

In `tests/test_agent_architecture.py`, change:

```python
WORKFLOWS = ["public-search", "platform-match", "screen", "report"]
```

to:

```python
WORKFLOWS = ["public-search", "platform-match", "screen", "report", "talent-library"]
```

- [ ] **Step 3: Add talent-library workflow tests**

Create `tests/test_talent_library_workflow.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "agents" / "workflows" / "talent-library"


def test_talent_library_workflow_resources_exist():
    expected = [
        WORKFLOW / "AGENT.md",
        WORKFLOW / "references" / "scenarios.md",
        WORKFLOW / "references" / "data-contract.md",
        WORKFLOW / "references" / "safety-rules.md",
        WORKFLOW / "assets" / "candidate-table-template.md",
        WORKFLOW / "assets" / "import-report-template.md",
        WORKFLOW / "assets" / "delete-confirmation-template.md",
    ]

    for path in expected:
        assert path.exists(), f"missing talent-library resource: {path}"


def test_talent_library_workflow_declares_all_scenes():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    scenarios = (WORKFLOW / "references" / "scenarios.md").read_text(encoding="utf-8")

    for scene in ["import", "search", "match", "score", "detail", "update", "delete"]:
        assert scene in text
        assert f"## {scene}" in scenarios


def test_talent_library_workflow_is_sqlite_first():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    data_contract = (WORKFLOW / "references" / "data-contract.md").read_text(
        encoding="utf-8"
    )

    assert "data/talent.db" in text
    assert "data/talent.db" in data_contract
    assert "旧 `data/candidates/*.json` 只作为迁移和兼容入口" in data_contract


def test_talent_library_safety_mentions_hard_delete_confirmation():
    safety = (WORKFLOW / "references" / "safety-rules.md").read_text(encoding="utf-8")
    delete_template = (
        WORKFLOW / "assets" / "delete-confirmation-template.md"
    ).read_text(encoding="utf-8")

    assert "删除必须二次确认" in safety
    assert "确认删除候选人 <candidate_id>" in delete_template
```

- [ ] **Step 4: Run workflow tests**

Run:

```bash
python -m pytest tests/test_agent_architecture.py tests/test_talent_library_workflow.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git add .claude/skills/talent-library tests/test_agent_architecture.py tests/test_talent_library_workflow.py
git commit -m "test: cover talent library workflow adapter"
```

Expected: commit succeeds.

---

### Task 6: Update Task Tracking and Run Full Verification

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Append implementation checklist to `tasks/todo.md`**

Append this checklist after the current sections:

```markdown

---

# talent-library Skill 实施清单（2026-05-10）

> 当前状态：**已完成**
> 设计文档：`docs/superpowers/specs/2026-05-10-talent-library-skill-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-10-talent-library-skill.md`

## 任务清单

- [x] Task 1：增加 `DeleteResult` 数据模型
- [x] Task 2：增加 `TalentDB.update_candidate()`
- [x] Task 3：增加 `TalentDB.delete_candidate()`
- [x] Task 4：新增 `agents/workflows/talent-library` canonical workflow
- [x] Task 5：新增 `.claude/skills/talent-library` 适配器和架构测试
- [x] Task 6：全量验证

## Review
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: all tests pass. Existing deprecation warnings are acceptable only if no failures occur.

- [ ] **Step 3: Run architecture grep**

Run:

```bash
rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows
```

Expected: no output from canonical workflows.

- [ ] **Step 4: Update Review in `tasks/todo.md`**

Append the actual verification outputs under the `## Review` heading. Use this exact shape and replace only the pass count with the number printed by pytest:

```markdown
- 全量测试：`python -m pytest tests scripts -q`，结果 **356 passed**
- 架构扫描：`rg -n "Claude Code|WebSearch|mcp__|`Read`|`Write`|`Bash`|\\.claude/skills" agents/workflows`，结果 **无输出**
```

Use the actual pass count from the test run.

- [ ] **Step 5: Final status check**

Run:

```bash
git status --short
```

Expected: only intended tracked files are modified or staged.

- [ ] **Step 6: Commit Task 6**

Run:

```bash
git add tasks/todo.md
git commit -m "docs: record talent library implementation"
```

Expected: commit succeeds.

---

## Self-Review

### Spec Coverage

- Single aggregate skill `talent-library`: Task 4 and Task 5.
- Seven internal scenes: Task 4 `AGENT.md` and `scenarios.md`.
- SQLite-first data source: Task 4 `data-contract.md`; Task 2 and Task 3 APIs.
- Hard delete after confirmation: Task 3 API; Task 4 safety/template docs.
- Runtime-neutral architecture: Task 4 canonical workflow; Task 5 architecture tests.
- Skill-creator standard structure: Task 5 adapter and Task 4 references/assets.
- Existing implementation reuse: Task 4 workflow references `platform-match`, `screen`, `score_pipeline.py`, and `TalentDB`.

### Placeholder Scan

No deferred implementation markers are used. Every task has concrete files, code snippets, commands, and expected outcomes.

### Type Consistency

- `DeleteResult` is defined in `scripts/talent_models.py` and imported by `scripts/talent_db.py`.
- `TalentDB.update_candidate(candidate_id, patch)` returns `Candidate`.
- `TalentDB.delete_candidate(candidate_id)` returns `DeleteResult`.
- Workflow references match the exact planned paths.
