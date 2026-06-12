# Talent DB Incremental Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build P1 incremental `data/talent.db` synchronization for Feishu Drive cloud sync and cross-PC bundle sync without replacing the existing bundle/import safety model.

**Architecture:** Keep `TalentDB` as the local fact store and keep the existing bundle format as the only transfer format. Add reliable candidate-level waterlines, export candidate-closure incremental bundles, and make `talent_cloud_sync` default to incremental push after an explicit full bootstrap. Conflict handling continues to use the existing `talent_sync` import plan and `sync_conflicts` model.

**Tech Stack:** Python stdlib (`argparse`, `dataclasses`, `datetime`, `json`, `pathlib`, `sqlite3`, `tempfile`, `zipfile`), existing `TalentDB`, existing `scripts.talent_sync`, existing `scripts.talent_cloud_sync`, pytest, LocalFs cloud provider test double.

---

## File Structure

- Modify: `tasks/todo.md`
  - Add the Active Task for this implementation before code changes, then track progress and final review there.
- Modify: `scripts/talent_db.py`
  - Add candidate sync touch helpers.
  - Refresh `candidates.sync_updated_at` for all business writes that affect a candidate or candidate child row.
  - Extend `export_sync_rows()` and each `_export_*` helper to support full export and candidate-closure incremental export.
- Modify: `scripts/talent_sync_models.py`
  - Extend `BundleManifest` with optional incremental metadata fields while preserving existing full bundle fields.
- Modify: `scripts/talent_sync.py`
  - Extend `export_bundle()` to support `mode="incremental"`, `since`, and explicit candidate sync IDs.
  - Extend the CLI `export` command with `--mode`, `--since`, and `--candidate-sync-ids-file`.
  - Keep `verify-bundle`, `import`, dry-run, apply, and checksum behavior compatible with existing bundles.
- Modify: `scripts/talent_cloud_sync.py`
  - Extend cloud state defaults and migration.
  - Add full bootstrap vs incremental push mode.
  - Block push when remote has unapplied bundles.
  - Update pull/apply state and allow non-blocking field conflicts to be recorded by import.
- Modify: `docs/manual/talent-sync-guide.md`
  - Add cross-PC incremental export/import instructions and full bootstrap guidance.
- Modify: `docs/manual/talent-cloud-sync-guide.md`
  - Add explicit full bootstrap, daily incremental sync, push gate, and no-op behavior.
- Modify: `tests/test_talent_sync.py`
  - Add waterline, candidate-closure export, tombstone incremental export, CLI, and idempotent import tests.
- Modify: `tests/test_talent_cloud_sync.py`
  - Add explicit bootstrap mode, incremental push, remote pending gate, no-op push, and field-conflict apply tests.

## Task 0: Project Ledger Setup

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add Active Task entry**

Insert this Active Task near the top of `tasks/todo.md` under `## Active Task`. Preserve unrelated existing entries.

```markdown
### Talent DB 增量同步 P1

- [ ] 补齐候选人级 `sync_updated_at` 水位，确保候选人和关联数据写入都会刷新同步时间。
- [ ] 实现候选人闭包增量 bundle 导出，保留全量 bootstrap 行为。
- [ ] 扩展云同步 state、full bootstrap 和增量 push/pull 门禁。
- [ ] 更新跨 PC 文件同步和飞书 Drive 云同步文档。
- [ ] 运行聚焦测试、全量测试和 diff check，归档 Review。

边界：实现 P1 候选人闭包增量同步；不直接同步 `data/talent.db` 文件；不迁移云数据库；不做实时多人并发、行级最小 delta、云端清理或可视化冲突 UI。执行计划见 `docs/superpowers/plans/2026-06-12-talent-db-incremental-sync.md`。

验证方式：聚焦测试 `.venv/bin/python -m pytest tests/test_talent_sync.py tests/test_talent_cloud_sync.py -q`；完成后运行 `.venv/bin/python -m pytest tests -q` 和 `git diff --check`。
```

- [ ] **Step 2: Verify only ledger text changed**

Run:

```bash
rtk git diff -- tasks/todo.md
```

Expected: diff only adds the `Talent DB 增量同步 P1` Active Task text.

- [ ] **Step 3: Commit ledger setup**

Run:

```bash
rtk git add tasks/todo.md
rtk git commit -m "Track talent DB incremental sync task"
```

Expected: commit succeeds.

## Task 1: Candidate Sync Waterline

**Files:**
- Modify: `scripts/talent_db.py`
- Modify: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing tests for candidate sync timestamps**

Add `sqlite3` to the imports in `tests/test_talent_sync.py`:

```python
import sqlite3
```

Add these helpers near the existing test helpers:

```python
def _candidate_sync_updated_at(db_path: Path, candidate_id: int) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT sync_updated_at FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    return str(row[0])


def _reset_candidate_sync_updated_at(
    db: TalentDB,
    candidate_id: int,
    value: str = "2000-01-01 00:00:00",
) -> None:
    db._conn.execute(
        "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
        (value, candidate_id),
    )
    db._conn.commit()
```

Add this test:

```python
def test_candidate_update_refreshes_sync_updated_at(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        _reset_candidate_sync_updated_at(db, candidate_id)

        db.update_candidate(candidate_id, {"city": "Shanghai"})
    finally:
        db.close()

    assert _candidate_sync_updated_at(db_path, candidate_id) > "2000-01-01 00:00:00"
```

Add this test:

```python
def test_candidate_child_writes_refresh_parent_sync_updated_at(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        source_profile_id = db.get_sources(candidate_id)[0].id

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.record_identity_match(
            {
                "candidate_id": candidate_id,
                "source_platform": "boss",
                "source_candidate_key": "boss-1",
                "target_platform": "maimai",
                "target_platform_id": "maimai-1",
                "target_profile_url": "https://maimai.cn/profile/detail?dstu=maimai-1",
                "query_text": "Alice Acme",
                "query_level": "person",
                "confidence": 0.95,
                "score_breakdown": {"name": 0.98},
                "match_status": "confirmed",
                "decision_reason": "same person",
            }
        )
        after_identity = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_identity > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.record_field_value(
            {
                "candidate_id": candidate_id,
                "field_name": "current_title",
                "platform": "maimai",
                "source_profile_id": source_profile_id,
                "field_value": {"value": "AI Engineer"},
                "confidence": 0.9,
                "merge_decision": "keep_primary",
            }
        )
        after_field = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_field > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice Followup",
                "markdown_path": "wechat/alice.md",
                "message_count": 3,
            },
        )
        after_wechat = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_wechat > "2000-01-01 00:00:00"

        _reset_candidate_sync_updated_at(db, candidate_id)
        db.save_match_score(
            candidate_id,
            "jd-1",
            "final",
            88,
            {"skill": 90},
            "strong match",
        )
        after_match = _candidate_sync_updated_at(db_path, candidate_id)
        assert after_match > "2000-01-01 00:00:00"
    finally:
        db.close()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_candidate_update_refreshes_sync_updated_at tests/test_talent_sync.py::test_candidate_child_writes_refresh_parent_sync_updated_at -q
```

Expected: tests fail because current code only updates `updated_at` on several paths and does not consistently refresh `sync_updated_at`.

- [ ] **Step 3: Add touch helper in `TalentDB`**

In `scripts/talent_db.py`, add this method after `_ensure_candidate_sync_id()`:

```python
    def _touch_candidate_sync(self, candidate_id: int) -> None:
        self._conn.execute(
            """
            UPDATE candidates
            SET updated_at = datetime('now'),
                sync_updated_at = datetime('now')
            WHERE id = ?
            """,
            (candidate_id,),
        )
```

- [ ] **Step 4: Use touch helper for direct candidate updates**

In `update_candidate()`, replace the appended assignment:

```python
        assignments.append("updated_at = datetime('now')")
```

with:

```python
        assignments.append("updated_at = datetime('now')")
        assignments.append("sync_updated_at = datetime('now')")
```

In `_merge_candidate()`, change both candidate timestamp updates to include `sync_updated_at = datetime('now')`.

For the branch with `set_clause`, the SQL must become:

```python
                f"""
                UPDATE candidates
                SET {set_clause},
                    updated_at = datetime('now'),
                    sync_updated_at = datetime('now')
                WHERE id = ?
                """
```

For the no-field-update branch, the SQL must become:

```python
                """
                UPDATE candidates
                SET updated_at = datetime('now'),
                    sync_updated_at = datetime('now')
                WHERE id = ?
                """
```

- [ ] **Step 5: Use touch helper for child writes**

In `record_identity_match()`, after the `INSERT INTO candidate_identity_matches` statement and before leaving the transaction, add:

```python
            if candidate_id is not None:
                self._touch_candidate_sync(int(candidate_id))
```

In `record_field_value()`, after the `INSERT INTO candidate_field_values` statement and before leaving the transaction, add:

```python
            self._touch_candidate_sync(candidate_id)
```

In `add_wechat_timeline()`, replace the existing `UPDATE candidates SET updated_at = datetime('now') WHERE id = ?` statement with:

```python
            self._touch_candidate_sync(candidate_id)
```

In `save_match_score()`, after the `INSERT INTO match_scores` statement and before leaving the transaction, add:

```python
            self._touch_candidate_sync(candidate_id)
```

In `update_overall_score()` or the method that inserts into `score_events`, change the candidate update SQL from:

```python
                UPDATE candidates
                SET overall_score = ?,
                    score_version = score_version + 1,
                    updated_at = datetime('now')
                WHERE id = ?
```

to:

```python
                UPDATE candidates
                SET overall_score = ?,
                    score_version = score_version + 1,
                    updated_at = datetime('now'),
                    sync_updated_at = datetime('now')
                WHERE id = ?
```

In `enrich()`, replace candidate timestamp updates after detail merge with:

```python
                """
                UPDATE candidates
                SET data_level = 'detailed',
                    updated_at = datetime('now'),
                    sync_updated_at = datetime('now')
                WHERE id = ?
                """
```

- [ ] **Step 6: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_candidate_update_refreshes_sync_updated_at tests/test_talent_sync.py::test_candidate_child_writes_refresh_parent_sync_updated_at -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit waterline changes**

Run:

```bash
rtk git add scripts/talent_db.py tests/test_talent_sync.py
rtk git commit -m "Add candidate sync waterline touches"
```

Expected: commit succeeds.

## Task 2: Candidate-Closure Incremental Export

**Files:**
- Modify: `scripts/talent_db.py`
- Modify: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing tests for incremental candidate closure export**

Add this helper near the existing bundle helpers in `tests/test_talent_sync.py`:

```python
def _read_bundle_jsonl(bundle_path: Path, relative_path: str) -> list[dict]:
    with zipfile.ZipFile(bundle_path) as bundle:
        payload = bundle.read(relative_path).decode("utf-8")
    if not payload.strip():
        return []
    return [json.loads(line) for line in payload.splitlines()]
```

Add this test:

```python
def test_export_incremental_bundle_contains_changed_candidate_closure(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "incremental.zip"
    db = TalentDB(db_path)
    try:
        old_candidate_id = db.ingest(
            {
                "name": "Old Alice",
                "current_company": "Old Co",
                "platform_id": "maimai-old",
                "work_experience": [{"company": "Old Co"}],
            },
            platform="maimai",
        )
        changed_candidate_id = db.ingest(
            {
                "name": "Changed Bob",
                "current_company": "New Co",
                "platform_id": "maimai-new",
                "work_experience": [{"company": "New Co"}],
            },
            platform="maimai",
        )
        db.save_match_score(
            changed_candidate_id,
            "jd-1",
            "final",
            91,
            {"skill": 92},
            "strong",
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", old_candidate_id),
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2030-01-01 00:00:00", changed_candidate_id),
        )
        db._conn.commit()
    finally:
        db.close()

    summary = export_bundle(
        db_path,
        bundle_path,
        mode="incremental",
        since="2029-01-01T00:00:00Z",
    )

    assert summary["mode"] == "incremental"
    assert summary["tables"]["candidates"] == 1
    candidates = _read_bundle_jsonl(bundle_path, "data/candidates.jsonl")
    details = _read_bundle_jsonl(bundle_path, "data/candidate_details.jsonl")
    sources = _read_bundle_jsonl(bundle_path, "data/source_profiles.jsonl")
    scores = _read_bundle_jsonl(bundle_path, "data/match_scores.jsonl")
    assert [row["name"] for row in candidates] == ["Changed Bob"]
    assert len(details) == 1
    assert len(sources) == 1
    assert len(scores) == 1
    assert scores[0]["candidate_sync_id"] == candidates[0]["sync_id"]
```

Add this test:

```python
def test_export_incremental_bundle_includes_recent_tombstones(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "incremental-delete.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Deleted Alice",
                "current_company": "Acme",
                "platform_id": "maimai-delete",
            },
            platform="maimai",
        )
        db.delete_candidate(candidate_id)
    finally:
        db.close()

    summary = export_bundle(
        db_path,
        bundle_path,
        mode="incremental",
        since="2000-01-01T00:00:00Z",
    )

    assert summary["tables"]["candidates"] == 0
    assert summary["tables"]["tombstones"] == 1
    tombstones = _read_bundle_jsonl(bundle_path, "data/tombstones.jsonl")
    assert tombstones[0]["entity_type"] == "candidate"
    assert tombstones[0]["reason"] == "local_delete"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_export_incremental_bundle_contains_changed_candidate_closure tests/test_talent_sync.py::test_export_incremental_bundle_includes_recent_tombstones -q
```

Expected: FAIL with `Unsupported export mode: incremental`.

- [ ] **Step 3: Add timestamp and sync-id filter helpers**

In `scripts/talent_db.py`, add these helpers near the export helpers:

```python
def _normalize_sync_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return str(value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed.replace(microsecond=0).isoformat(sep=" ")


def _sync_id_where_clause(
    column: str,
    sync_ids: set[str] | None,
    prefix: str = "WHERE",
) -> tuple[str, tuple[Any, ...]]:
    if sync_ids is None:
        return "", ()
    if not sync_ids:
        return f"{prefix} 1 = 0", ()
    placeholders = ", ".join("?" for _ in sync_ids)
    return f"{prefix} {column} IN ({placeholders})", tuple(sorted(sync_ids))
```

If `datetime` or `UTC` is not imported at the top of `scripts/talent_db.py`, import them:

```python
from datetime import UTC, datetime
```

- [ ] **Step 4: Add changed candidate lookup**

Add this method on `TalentDB` near `export_sync_rows()`:

```python
    def _candidate_sync_ids_changed_since(self, since: str | None) -> set[str] | None:
        normalized_since = _normalize_sync_timestamp(since)
        if normalized_since is None:
            return None
        rows = self._conn.execute(
            """
            SELECT sync_id
            FROM candidates
            WHERE sync_updated_at >= ?
              AND sync_id IS NOT NULL
              AND sync_id != ''
            ORDER BY sync_id
            """,
            (normalized_since,),
        ).fetchall()
        return {str(row["sync_id"]) for row in rows}
```

- [ ] **Step 5: Extend `export_sync_rows()` signature**

Replace the existing method:

```python
    def export_sync_rows(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "candidates": self._export_candidates(),
            "candidate_details": self._export_candidate_details(),
            "source_profiles": self._export_source_profiles(),
            "candidate_identity_matches": self._export_identity_matches(),
            "candidate_field_values": self._export_field_values(),
            "candidate_wechat_timelines": self._export_wechat_timelines(),
            "score_events": self._export_score_events(),
            "match_scores": self._export_match_scores(),
            "tombstones": self._export_tombstones(),
        }
```

with:

```python
    def export_sync_rows(
        self,
        candidate_sync_ids: set[str] | list[str] | tuple[str, ...] | None = None,
        since: str | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        selected_sync_ids: set[str] | None
        if candidate_sync_ids is not None:
            selected_sync_ids = {str(sync_id) for sync_id in candidate_sync_ids if sync_id}
        else:
            selected_sync_ids = self._candidate_sync_ids_changed_since(since)

        return {
            "candidates": self._export_candidates(selected_sync_ids),
            "candidate_details": self._export_candidate_details(selected_sync_ids),
            "source_profiles": self._export_source_profiles(selected_sync_ids),
            "candidate_identity_matches": self._export_identity_matches(selected_sync_ids),
            "candidate_field_values": self._export_field_values(selected_sync_ids),
            "candidate_wechat_timelines": self._export_wechat_timelines(selected_sync_ids),
            "score_events": self._export_score_events(selected_sync_ids),
            "match_scores": self._export_match_scores(selected_sync_ids),
            "tombstones": self._export_tombstones(selected_sync_ids, since=since),
        }
```

- [ ] **Step 6: Add filters to export helpers**

Update each export helper signature:

```python
    def _export_candidates(
        self,
        candidate_sync_ids: set[str] | None = None,
    ) -> list[dict[str, Any]]:
```

Use this WHERE clause inside `_export_candidates()`:

```python
        where_clause, params = _sync_id_where_clause("sync_id", candidate_sync_ids)
```

Append `{where_clause}` before `ORDER BY sync_id`, and pass `params` to `execute()`.

For each child export that joins `candidates`, use:

```python
        where_clause, params = _sync_id_where_clause(
            "candidates.sync_id",
            candidate_sync_ids,
        )
```

Append `{where_clause}` before the existing `ORDER BY`.

For `_export_identity_matches()`, keep the `LEFT JOIN` but filter by candidate sync ID only when `candidate_sync_ids` is not `None`:

```python
        where_clause, params = _sync_id_where_clause(
            "candidates.sync_id",
            candidate_sync_ids,
        )
```

Rows with `candidate_id IS NULL` are excluded from incremental candidate-closure export and still included in full export.

Update `_export_tombstones()` to accept filters:

```python
    def _export_tombstones(
        self,
        candidate_sync_ids: set[str] | None = None,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if candidate_sync_ids is not None:
            if candidate_sync_ids:
                placeholders = ", ".join("?" for _ in candidate_sync_ids)
                clauses.append(
                    "NOT (entity_type = 'candidate') OR entity_sync_id IN "
                    f"({placeholders})"
                )
                params.extend(sorted(candidate_sync_ids))
            else:
                clauses.append("entity_type = 'candidate'")
        normalized_since = _normalize_sync_timestamp(since)
        if normalized_since is not None:
            clauses.append("deleted_at >= ?")
            params.append(normalized_since)
        where_clause = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"""
            SELECT entity_type, entity_sync_id, deleted_at, source_node_id, reason
            FROM sync_tombstones
            {where_clause}
            ORDER BY entity_type, entity_sync_id
            """,
            tuple(params),
        ).fetchall()
        return [_export_row(row) for row in rows]
```

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_export_incremental_bundle_contains_changed_candidate_closure tests/test_talent_sync.py::test_export_incremental_bundle_includes_recent_tombstones -q
```

Expected: `2 passed`.

- [ ] **Step 8: Commit incremental export core**

Run:

```bash
rtk git add scripts/talent_db.py tests/test_talent_sync.py
rtk git commit -m "Add candidate-closure incremental export"
```

Expected: commit succeeds.

## Task 3: Bundle Manifest and CLI

**Files:**
- Modify: `scripts/talent_sync_models.py`
- Modify: `scripts/talent_sync.py`
- Modify: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing tests for manifest metadata and CLI arguments**

Add this test to `tests/test_talent_sync.py`:

```python
def test_incremental_bundle_manifest_records_cursor_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "incremental.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2030-01-01 00:00:00", candidate_id),
        )
        db._conn.commit()
    finally:
        db.close()

    export_bundle(
        db_path,
        bundle_path,
        mode="incremental",
        since="2029-01-01T00:00:00Z",
    )

    with zipfile.ZipFile(bundle_path) as bundle:
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
    assert manifest["export_mode"] == "incremental"
    assert manifest["base_cursor"] == "2029-01-01 00:00:00"
    assert manifest["cursor_started_at"].endswith("+00:00")
    assert manifest["candidate_count"] == 1
```

Add this test:

```python
def test_export_cli_accepts_incremental_since_argument(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "cli-incremental.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2030-01-01 00:00:00", candidate_id),
        )
        db._conn.commit()
    finally:
        db.close()

    result = sync_main(
        [
            "export",
            "--db",
            str(db_path),
            "--out",
            str(bundle_path),
            "--mode",
            "incremental",
            "--since",
            "2029-01-01T00:00:00Z",
        ]
    )

    assert result == 0
    assert bundle_path.exists()
    assert verify_bundle(bundle_path)["ok"] is True
```

Add this test:

```python
def test_export_incremental_requires_since_or_candidate_file(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "invalid-incremental.zip"
    db = TalentDB(db_path)
    db.close()

    with pytest.raises(ValueError, match="incremental export requires"):
        export_bundle(db_path, bundle_path, mode="incremental")
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_incremental_bundle_manifest_records_cursor_metadata tests/test_talent_sync.py::test_export_cli_accepts_incremental_since_argument tests/test_talent_sync.py::test_export_incremental_requires_since_or_candidate_file -q
```

Expected: failures for missing CLI arguments and missing manifest fields.

- [ ] **Step 3: Extend `BundleManifest`**

In `scripts/talent_sync_models.py`, replace the `BundleManifest` dataclass with this shape:

```python
@dataclass
class BundleManifest:
    bundle_schema_version: int
    export_mode: str
    source_node_id: str
    export_id: str
    created_at: str
    tables: dict[str, int]
    attachments: dict[str, bool]
    base_cursor: str | None = None
    cursor_started_at: str | None = None
    candidate_count: int | None = None
```

- [ ] **Step 4: Extend `export_bundle()` signature and validation**

In `scripts/talent_sync.py`, update the signature:

```python
def export_bundle(
    db_path: str | Path,
    bundle_path: str | Path,
    mode: str = "full",
    include_wechat_files: bool = False,
    since: str | None = None,
    candidate_sync_ids: set[str] | list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
```

Replace the current mode check with:

```python
    if mode not in {"full", "incremental"}:
        raise ValueError(f"Unsupported export mode: {mode}")
    if mode == "incremental" and since is None and candidate_sync_ids is None:
        raise ValueError(
            "incremental export requires --since or --candidate-sync-ids-file"
        )
```

Set `cursor_started_at` before opening the DB:

```python
    cursor_started_at = datetime.now(UTC).replace(microsecond=0).isoformat()
```

Call export rows like this:

```python
        table_rows = db.export_sync_rows(
            candidate_sync_ids=candidate_sync_ids,
            since=since if mode == "incremental" else None,
        )
```

Build the manifest like this:

```python
    base_cursor = None
    if mode == "incremental" and since is not None:
        base_cursor = _normalize_sync_timestamp(since)
    manifest = BundleManifest(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
        export_mode=mode,
        source_node_id=source_node_id,
        export_id=str(uuid.uuid4()),
        created_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
        tables=table_counts,
        attachments={"wechat_timelines": False},
        base_cursor=base_cursor,
        cursor_started_at=cursor_started_at if mode == "incremental" else None,
        candidate_count=table_counts.get("candidates", 0),
    )
```

Import `_normalize_sync_timestamp` from `scripts.talent_db`:

```python
from scripts.talent_db import TalentDB, _normalize_sync_timestamp
```

- [ ] **Step 5: Add candidate sync ID file reader**

In `scripts/talent_sync.py`, add:

```python
def _read_candidate_sync_ids_file(path: str | Path | None) -> set[str] | None:
    if path is None:
        return None
    sync_ids: set[str] = set()
    with Path(path).open("r", encoding="utf-8-sig") as file:
        for line in file:
            text = line.strip()
            if not text:
                continue
            if text.startswith("{"):
                row = json.loads(text)
                sync_id = row.get("sync_id") or row.get("candidate_sync_id")
                if sync_id:
                    sync_ids.add(str(sync_id))
                continue
            sync_ids.add(text)
    return sync_ids
```

- [ ] **Step 6: Extend CLI export command**

In `cmd_export()`, pass mode and filters:

```python
    candidate_sync_ids = _read_candidate_sync_ids_file(args.candidate_sync_ids_file)
    summary = export_bundle(
        args.db,
        args.out,
        mode=args.mode,
        include_wechat_files=args.include_wechat_files,
        since=args.since,
        candidate_sync_ids=candidate_sync_ids,
    )
```

In `build_parser()`, change the export parser help to `"导出同步 bundle"` and add:

```python
    export.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default="full",
        help="导出模式：full 全量，incremental 增量",
    )
    export.add_argument("--since", default=None, help="增量导出的起始时间")
    export.add_argument(
        "--candidate-sync-ids-file",
        default=None,
        help="每行一个 candidate sync_id，或 JSONL 中包含 sync_id/candidate_sync_id",
    )
```

Remove the duplicate hard-coded `mode="full"` from `cmd_export()`.

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py::test_incremental_bundle_manifest_records_cursor_metadata tests/test_talent_sync.py::test_export_cli_accepts_incremental_since_argument tests/test_talent_sync.py::test_export_incremental_requires_since_or_candidate_file -q
```

Expected: `3 passed`.

- [ ] **Step 8: Run full talent sync tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py -q
```

Expected: all tests in `tests/test_talent_sync.py` pass.

- [ ] **Step 9: Commit bundle CLI changes**

Run:

```bash
rtk git add scripts/talent_sync.py scripts/talent_sync_models.py tests/test_talent_sync.py
rtk git commit -m "Add incremental talent sync bundle CLI"
```

Expected: commit succeeds.

## Task 4: Cloud State, Bootstrap Mode, and Incremental Push

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Update test helper for explicit push mode**

In `tests/test_talent_cloud_sync.py`, update `_config()` to accept an export mode:

```python
def _config(
    tmp_path: Path,
    db_path: Path,
    key: str | None = None,
    export_mode: str = "full",
) -> CloudSyncConfig:
    return CloudSyncConfig(
        provider="localfs",
        db_path=db_path,
        state_path=tmp_path / "cloud-state.json",
        work_dir=tmp_path / "work",
        localfs_root=tmp_path / "remote",
        encryption_key=key or keygen(),
        auto_apply=True,
        include_wechat_files=False,
        export_mode=export_mode,
    )
```

This keeps existing cloud tests on explicit full bootstrap behavior.

- [ ] **Step 2: Write failing tests for incremental cloud push**

Add this test:

```python
def test_incremental_push_requires_prior_cursor_or_since(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    _seed_candidate(db_path, "Alice")
    config = _config(tmp_path, db_path, export_mode="incremental")
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)

    with pytest.raises(CloudSyncError, match="incremental push requires"):
        push(config, provider=provider)
```

Add this test:

```python
def test_incremental_push_uploads_only_changes_after_cursor(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    key = keygen()
    old_id = _seed_candidate(db_path, "Old Alice", platform_id="maimai-old")
    changed_id = _seed_candidate(db_path, "Changed Bob", platform_id="maimai-new")
    db = TalentDB(db_path)
    try:
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", old_id),
        )
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2030-01-01 00:00:00", changed_id),
        )
        db._conn.commit()
    finally:
        db.close()
    config = _config(tmp_path, db_path, key=key, export_mode="incremental")
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)
    state = load_state(config.state_path)
    state["last_successful_push_started_at"] = "2029-01-01T00:00:00Z"
    state["schema"] = "talent_cloud_state_v2"
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.state_path.write_text(json.dumps(state), encoding="utf-8")

    result = push(config, provider=provider)

    assert result["uploaded"] is True
    assert result["tables"]["candidates"] == 1
    index_files = provider.list_files("bundle-index")
    index_data = json.loads(Path(index_files[0]["token"]).read_text(encoding="utf-8"))
    assert index_data["export_mode"] == "incremental"
    assert index_data["tables"]["candidates"] == 1
```

Add this test:

```python
def test_incremental_push_noops_when_no_rows_changed(tmp_path: Path) -> None:
    db_path = tmp_path / "source.db"
    candidate_id = _seed_candidate(db_path, "Alice")
    db = TalentDB(db_path)
    try:
        db._conn.execute(
            "UPDATE candidates SET sync_updated_at = ? WHERE id = ?",
            ("2000-01-01 00:00:00", candidate_id),
        )
        db._conn.commit()
    finally:
        db.close()
    config = _config(tmp_path, db_path, export_mode="incremental")
    provider = LocalFsProvider(config.localfs_root)
    init_remote(provider)
    state = load_state(config.state_path)
    state["schema"] = "talent_cloud_state_v2"
    state["last_successful_push_started_at"] = "2029-01-01T00:00:00Z"
    config.state_path.parent.mkdir(parents=True, exist_ok=True)
    config.state_path.write_text(json.dumps(state), encoding="utf-8")

    result = push(config, provider=provider)

    assert result == {"uploaded": False, "reason": "no_changes", "bundle_id": None}
    assert provider.list_files("bundle-index") == []
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_incremental_push_requires_prior_cursor_or_since tests/test_talent_cloud_sync.py::test_incremental_push_uploads_only_changes_after_cursor tests/test_talent_cloud_sync.py::test_incremental_push_noops_when_no_rows_changed -q
```

Expected: failures because `CloudSyncConfig` has no `export_mode` and push still exports full bundles.

- [ ] **Step 4: Extend cloud config and state migration**

In `scripts/talent_cloud_sync.py`, set schemas:

```python
STATE_SCHEMA = "talent_cloud_state_v2"
LEGACY_STATE_SCHEMA = "talent_cloud_state_v1"
```

Add fields to `CloudSyncConfig`:

```python
    export_mode: str = "incremental"
    since: str | None = None
```

In `from_env()`, set:

```python
            export_mode=os.environ.get("TALENT_SYNC_EXPORT_MODE", "incremental"),
            since=os.environ.get("TALENT_SYNC_SINCE") or None,
```

Update `load_state()` so it accepts legacy state and returns v2 defaults:

```python
def _empty_state() -> dict[str, Any]:
    return {
        "schema": STATE_SCHEMA,
        "provider": "",
        "remote": {},
        "seen_bundle_ids": [],
        "applied_bundle_ids": [],
        "applied_bundles": [],
        "blocked_remote_bundles": [],
        "last_sync_at": None,
        "last_push_bundle_id": None,
        "last_pushed_db_fingerprint": None,
        "last_successful_push_started_at": None,
    }
```

Use `_empty_state()` in `load_state()`. When reading existing state:

```python
    if data.get("schema") not in {STATE_SCHEMA, LEGACY_STATE_SCHEMA}:
        raise CloudSyncError(f"unsupported cloud state schema: {data.get('schema')}")
    defaults = _empty_state()
    defaults.update(data)
    defaults["schema"] = STATE_SCHEMA
    defaults.setdefault("seen_bundle_ids", [])
    defaults.setdefault("applied_bundle_ids", [])
    defaults.setdefault("applied_bundles", [])
    defaults.setdefault("blocked_remote_bundles", [])
    defaults.setdefault("last_successful_push_started_at", None)
    return defaults
```

- [ ] **Step 5: Add export cursor helper**

Add this helper:

```python
def _incremental_since(config: CloudSyncConfig, state: dict[str, Any]) -> str:
    if config.since:
        return config.since
    cursor = state.get("last_successful_push_started_at")
    if not cursor:
        raise CloudSyncError(
            "incremental push requires prior bootstrap/full pull or --since"
        )
    return str(cursor)
```

- [ ] **Step 6: Update `push()` to use full or incremental mode**

In `push()`, after loading state and before creating the temporary directory, compute:

```python
    export_mode = config.export_mode
    if export_mode not in {"full", "incremental"}:
        raise CloudSyncError(f"unsupported export mode: {export_mode}")
    push_started_at = _now_utc()
    since = None
    if export_mode == "incremental":
        since = _incremental_since(config, state)
```

Keep the fingerprint shortcut only for full mode:

```python
    current_fingerprint = _db_fingerprint(config.db_path)
    if (
        export_mode == "full"
        and state.get("last_pushed_db_fingerprint") == current_fingerprint
    ):
        return {
            "uploaded": False,
            "reason": "unchanged",
            "bundle_id": state.get("last_push_bundle_id"),
        }
```

Call `export_bundle()` with:

```python
        summary = export_bundle(
            config.db_path,
            plain_bundle,
            mode=export_mode,
            include_wechat_files=config.include_wechat_files,
            since=since,
        )
```

After verification, before encryption, return no-op for empty incremental bundles:

```python
        if export_mode == "incremental" and all(
            count == 0 for count in summary["tables"].values()
        ):
            state["schema"] = STATE_SCHEMA
            state["provider"] = config.provider
            state["last_sync_at"] = _now_utc()
            save_state(config.state_path, state)
            return {"uploaded": False, "reason": "no_changes", "bundle_id": None}
```

Add index metadata:

```python
            "export_mode": export_mode,
            "base_cursor": manifest.get("base_cursor"),
            "cursor_started_at": manifest.get("cursor_started_at"),
```

After upload succeeds, update state:

```python
    state["schema"] = STATE_SCHEMA
    state["provider"] = config.provider
    state["last_push_bundle_id"] = bundle_id
    state["last_pushed_db_fingerprint"] = current_fingerprint
    state["last_sync_at"] = _now_utc()
    state["last_successful_push_started_at"] = push_started_at
```

- [ ] **Step 7: Add CLI mode flags**

In `_add_common_flags()`, add:

```python
    parser.add_argument(
        "--mode",
        choices=("full", "incremental"),
        default=None,
        help="push/export 模式；默认使用 TALENT_SYNC_EXPORT_MODE 或 incremental",
    )
    parser.add_argument("--since", default=None, help="增量 push 的起始时间")
```

In `_config_from_args()`, set:

```python
    config = CloudSyncConfig.from_env(db_path=args.db)
    if getattr(args, "mode", None):
        config = dataclasses.replace(config, export_mode=args.mode)
    if getattr(args, "since", None):
        config = dataclasses.replace(config, since=args.since)
    return config
```

If `dataclasses` is not imported as a module, add:

```python
import dataclasses
```

- [ ] **Step 8: Run incremental cloud push tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_incremental_push_requires_prior_cursor_or_since tests/test_talent_cloud_sync.py::test_incremental_push_uploads_only_changes_after_cursor tests/test_talent_cloud_sync.py::test_incremental_push_noops_when_no_rows_changed -q
```

Expected: `3 passed`.

- [ ] **Step 9: Commit cloud incremental push**

Run:

```bash
rtk git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
rtk git commit -m "Add incremental cloud sync push mode"
```

Expected: commit succeeds.

## Task 5: Remote Pending Gate and Pull State

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing test for pending remote push gate**

Add this test:

```python
def test_push_blocks_when_remote_bundle_has_not_been_pulled(tmp_path: Path) -> None:
    key = keygen()
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    _seed_candidate(left_db, "Alice", platform_id="maimai-left")
    _seed_candidate(right_db, "Bob", platform_id="maimai-right")
    left_config = _config(tmp_path / "left", left_db, key=key, export_mode="full")
    right_config = _config(tmp_path / "right", right_db, key=key, export_mode="full")
    right_config = dataclasses.replace(
        right_config,
        localfs_root=left_config.localfs_root,
    )
    provider = LocalFsProvider(left_config.localfs_root)
    init_remote(provider)
    push(left_config, provider=provider)

    with pytest.raises(CloudSyncError, match="pull remote bundles before push"):
        push(right_config, provider=provider)
```

- [ ] **Step 2: Write failing test for pull state applied bundle records**

Add this test:

```python
def test_pull_records_applied_bundle_metadata_and_export_cursor(tmp_path: Path) -> None:
    key = keygen()
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    _seed_candidate(source_db, "Alice")
    source_config = _config(tmp_path / "source", source_db, key=key, export_mode="full")
    target_config = _config(tmp_path / "target", target_db, key=key, export_mode="full")
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push_result = push(source_config, provider=provider)

    pull_result = pull(target_config, provider=provider)

    state = load_state(target_config.state_path)
    assert pull_result["applied"] == 1
    assert push_result["bundle_id"] in state["applied_bundle_ids"]
    assert state["applied_bundles"][0]["bundle_id"] == push_result["bundle_id"]
    assert state["last_successful_push_started_at"] is not None
```

- [ ] **Step 3: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_push_blocks_when_remote_bundle_has_not_been_pulled tests/test_talent_cloud_sync.py::test_pull_records_applied_bundle_metadata_and_export_cursor -q
```

Expected: pending gate test fails because push currently allows direct upload; state metadata test fails because `applied_bundles` and export cursor are not recorded.

- [ ] **Step 4: Add remote pending helper**

In `scripts/talent_cloud_sync.py`, add:

```python
def _unapplied_remote_indexes(
    indexes: list[dict[str, Any]],
    state: dict[str, Any],
    db_path: Path,
    local_node_id: str,
) -> list[dict[str, Any]]:
    pending: list[dict[str, Any]] = []
    for index in indexes:
        bundle_id = str(index["bundle_id"])
        if bundle_id in state["applied_bundle_ids"]:
            continue
        if _local_import_recorded(db_path, bundle_id):
            continue
        if local_node_id and index.get("source_node_id") == local_node_id:
            continue
        pending.append(index)
    return pending
```

- [ ] **Step 5: Block push when remote has pending bundles**

In `push()`, after `provider.ensure_layout()` and after loading state, add:

```python
    config.work_dir.mkdir(parents=True, exist_ok=True)
    local_node_id = _node_id(config.db_path) if config.db_path.exists() else ""
    remote_indexes = _download_indexes(provider, config.work_dir)
    pending_remote = _unapplied_remote_indexes(
        remote_indexes,
        state,
        config.db_path,
        local_node_id,
    )
    if pending_remote:
        raise CloudSyncError("pull remote bundles before push")
```

Do not remove the existing open conflict guard.

- [ ] **Step 6: Record applied bundle metadata during pull**

In `pull()`, set:

```python
    pull_started_at = _now_utc()
```

When `config.auto_apply` succeeds, replace:

```python
                state["applied_bundle_ids"].append(bundle_id)
```

with:

```python
                if bundle_id not in state["applied_bundle_ids"]:
                    state["applied_bundle_ids"].append(bundle_id)
                state["applied_bundles"].append(
                    {
                        "bundle_id": bundle_id,
                        "source_node_id": str(index.get("source_node_id") or ""),
                        "created_at": str(index.get("created_at") or ""),
                        "applied_at": _now_utc(),
                    }
                )
```

Before `save_state()`, initialize export cursor for devices that have just pulled their first baseline:

```python
    if applied and not state.get("last_successful_push_started_at"):
        state["last_successful_push_started_at"] = pull_started_at
```

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_push_blocks_when_remote_bundle_has_not_been_pulled tests/test_talent_cloud_sync.py::test_pull_records_applied_bundle_metadata_and_export_cursor -q
```

Expected: `2 passed`.

- [ ] **Step 8: Commit pending gate and pull state**

Run:

```bash
rtk git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
rtk git commit -m "Gate cloud push on unapplied remote bundles"
```

Expected: commit succeeds.

## Task 6: Cloud Pull Conflict Semantics

**Files:**
- Modify: `scripts/talent_cloud_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Write failing test for non-blocking field conflicts**

Add this test:

```python
def test_pull_applies_field_conflicts_and_records_sync_conflict(tmp_path: Path) -> None:
    key = keygen()
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    source_candidate_id = _seed_candidate(
        source_db,
        "Alice",
        platform_id="maimai-same",
    )
    target_candidate_id = _seed_candidate(
        target_db,
        "Alice",
        platform_id="maimai-same",
    )
    source = TalentDB(source_db)
    try:
        source.update_candidate(source_candidate_id, {"city": "Shanghai"})
    finally:
        source.close()
    target = TalentDB(target_db)
    try:
        target.update_candidate(target_candidate_id, {"city": "Beijing"})
    finally:
        target.close()
    source_config = _config(tmp_path / "source", source_db, key=key, export_mode="full")
    target_config = _config(tmp_path / "target", target_db, key=key, export_mode="full")
    target_config = dataclasses.replace(
        target_config,
        localfs_root=source_config.localfs_root,
    )
    provider = LocalFsProvider(source_config.localfs_root)
    init_remote(provider)
    push(source_config, provider=provider)

    result = pull(target_config, provider=provider)

    assert result["applied"] == 1
    assert result["blocked"] == []
    conn = sqlite3.connect(str(target_db))
    try:
        open_conflict_count = conn.execute(
            "SELECT COUNT(*) FROM sync_conflicts WHERE status = 'open'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert open_conflict_count >= 1
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_pull_applies_field_conflicts_and_records_sync_conflict -q
```

Expected: FAIL because `_has_conflicts()` blocks all conflict counts before apply.

- [ ] **Step 3: Replace cloud conflict predicate**

In `scripts/talent_cloud_sync.py`, replace `_has_conflicts()` with:

```python
def _has_blocking_conflicts(plan: dict[str, Any]) -> bool:
    return int(plan.get("conflicts", {}).get("candidates", 0) or 0) > 0
```

Replace both calls in `pull()`:

```python
            if _has_blocking_conflicts(plan):
                blocked.append({"bundle_id": bundle_id, "reason": "conflicts", "plan": plan})
                continue
```

and:

```python
            if _has_blocking_conflicts(preview):
                blocked.append({"bundle_id": bundle_id, "reason": "conflicts", "plan": preview})
                continue
```

Do not block on `candidate_field_values`, `candidate_details`, `source_profiles`, `score_events`, `match_scores`, or `candidate_wechat_timelines` conflict counts.

- [ ] **Step 4: Run existing candidate conflict test**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_pull_stops_on_conflict_without_auto_apply -q
```

Expected: PASS. The existing test uses a candidate identity conflict and must remain blocked.

- [ ] **Step 5: Run field conflict test**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_cloud_sync.py::test_pull_applies_field_conflicts_and_records_sync_conflict -q
```

Expected: PASS.

- [ ] **Step 6: Commit cloud pull conflict semantics**

Run:

```bash
rtk git add scripts/talent_cloud_sync.py tests/test_talent_cloud_sync.py
rtk git commit -m "Allow cloud pull field conflict recording"
```

Expected: commit succeeds.

## Task 7: Documentation and Compatibility Pass

**Files:**
- Modify: `docs/manual/talent-sync-guide.md`
- Modify: `docs/manual/talent-cloud-sync-guide.md`
- Modify: `tests/test_talent_sync.py`
- Modify: `tests/test_talent_cloud_sync.py`

- [ ] **Step 1: Add cross-PC incremental guide text**

In `docs/manual/talent-sync-guide.md`, add this section after the cloud sync section:

```markdown
### 增量同步包

日常跨电脑同步优先使用增量包。增量包不是数据库文件，而是系统生成的安全 zip 包。

发送端导出增量包：

```bash
.venv/bin/python -m scripts.talent_sync export \
  --db data/talent.db \
  --mode incremental \
  --since 2026-06-12T00:00:00Z \
  --out data/sync/talent-sync-incremental-20260612.zip
```

接收端先校验：

```bash
.venv/bin/python -m scripts.talent_sync verify-bundle \
  --bundle data/sync/talent-sync-incremental-20260612.zip
```

接收端先 dry-run：

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-20260612.zip
```

确认后写入：

```bash
.venv/bin/python -m scripts.talent_sync import \
  --db data/talent.db \
  --bundle data/sync/talent-sync-incremental-20260612.zip \
  --apply \
  --confirm "确认同步人才库"
```

新电脑第一次使用仍然先导入全量包。全量包完成后，后续再使用增量包。
```

- [ ] **Step 2: Add cloud incremental guide text**

In `docs/manual/talent-cloud-sync-guide.md`, add this daily flow text after the first setup section:

```markdown
### 第一次同步和日常同步

第一次把一台电脑的数据放到飞书 Drive 时，使用 full bootstrap：

```bash
.venv/bin/python -m scripts.talent_cloud_sync push --provider feishu --mode full
```

其它电脑第一次使用时，先拉取这个全量 bootstrap：

```bash
.venv/bin/python -m scripts.talent_cloud_sync pull --provider feishu
```

日常同步使用增量：

```bash
.venv/bin/python -m scripts.talent_cloud_sync sync --provider feishu
```

`sync` 会先拉取远端未应用的 bundle，再上传本机增量。如果远端已有本机没拉取的 bundle，系统会拒绝 push，要求先 pull。

如果本机没有任何变化，增量 push 会返回 no-op，不上传空包。
```

- [ ] **Step 3: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py tests/test_talent_cloud_sync.py -q
```

Expected: both test files pass.

- [ ] **Step 4: Fix compatibility failures from existing tests**

If existing tests fail because helper defaults changed, keep production default incremental and make test setup explicit. Use these exact replacements in `tests/test_talent_cloud_sync.py` when a test intends initial bootstrap:

```python
source_config = _config(tmp_path / "source", source_db, key=key, export_mode="full")
```

and:

```python
left_config = _config(tmp_path / "left", left_db, key=key, export_mode="full")
```

For a target that only pulls, keep `export_mode="full"` or omit it because target mode is not used by `pull()`.

- [ ] **Step 5: Commit docs and compatibility updates**

Run:

```bash
rtk git add docs/manual/talent-sync-guide.md docs/manual/talent-cloud-sync-guide.md tests/test_talent_sync.py tests/test_talent_cloud_sync.py
rtk git commit -m "Document talent DB incremental sync flows"
```

Expected: commit succeeds.

## Task 8: Final Verification and Task Review

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_talent_sync.py tests/test_talent_cloud_sync.py -q
```

Expected: focused tests pass.

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full suite passes.

- [ ] **Step 3: Run diff whitespace check**

Run:

```bash
rtk git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Update task ledger review**

In `tasks/todo.md`, mark all `Talent DB 增量同步 P1` checklist items complete and add a Review block. Use the exact command summaries from Step 1 and Step 2 in the final sentence. The final sentence must use this shape: `验证：聚焦测试 <exact focused pytest summary>；全量测试 <exact full pytest summary>；git diff --check clean。`

```markdown
Review：2026-06-12 已完成 Talent DB 增量同步 P1。实现候选人级 `sync_updated_at` 水位，覆盖候选人字段、详情、来源、identity、field value、微信时间线、score event、match score 等写入路径；`talent_sync export` 支持 full / incremental、`--since` 和候选人 sync_id 文件；飞书 Drive 云同步支持 full bootstrap、增量 push、远端未应用 bundle push 门禁、pull applied bundle state 和空增量 no-op；跨 PC 文件同步复用同一 bundle 格式。验证：聚焦测试使用 Step 1 的 pytest 摘要；全量测试使用 Step 2 的 pytest 摘要；git diff --check clean。
```

Before committing, replace `聚焦测试使用 Step 1 的 pytest 摘要` and `全量测试使用 Step 2 的 pytest 摘要` with the actual summary text, such as `147 passed` or `1424 passed, 1 warning`.

- [ ] **Step 5: Archive detailed task record**

Append a concise completed entry to `tasks/archive/2026-06.md` using the same Review evidence from Step 4. Keep `tasks/todo.md` as the current workbench and do not paste long implementation diffs into it.

- [ ] **Step 6: Commit final ledger**

Run:

```bash
rtk git add tasks/todo.md tasks/archive/2026-06.md
rtk git commit -m "Record talent DB incremental sync completion"
```

Expected: commit succeeds.

- [ ] **Step 7: Report final status**

Report:

```text
Talent DB 增量同步 P1 已完成。
聚焦测试：copy the exact Step 1 pytest summary
全量测试：copy the exact Step 2 pytest summary
diff check：clean
关键提交：list the short commit hashes created in this plan
```

## Self-Review

Spec coverage:

- 多人多设备、低频同步：covered by push pending gate and pull-first sync flow in Tasks 4 and 5.
- 新设备 full bootstrap：covered by explicit cloud `--mode full` and manual full bundle docs in Tasks 4 and 7.
- 自动水位、手动 `--since`、任务级候选人集合：covered by Tasks 2, 3, and 4.
- 云上同步和跨 PC 文件同步：covered by Tasks 4, 5, 6, and 7.
- 候选人闭包增量：covered by Task 2 tests and export filtering.
- `sync_updated_at` reliable waterline: covered by Task 1.
- Push strict gate: covered by Task 5.
- Pull conflict behavior option C: covered by Task 6.
- Local state waterline: covered by Tasks 4 and 5.
- Cloud bundle retention: no cleanup code is introduced; existing immutable index/bundle layout remains.

Completeness scan:

- The plan contains no TBD markers and no angle-bracket stand-in values.
- The final Review and report steps instruct the implementer to copy exact verification summaries from the commands they just ran.

Type consistency:

- `export_bundle()` accepts `mode`, `since`, and `candidate_sync_ids`.
- `TalentDB.export_sync_rows()` accepts `candidate_sync_ids` and `since`.
- Cloud config uses `export_mode` and `since`.
- Cloud state uses `talent_cloud_state_v2`, keeps legacy `applied_bundle_ids`, and adds `applied_bundles` plus `last_successful_push_started_at`.
