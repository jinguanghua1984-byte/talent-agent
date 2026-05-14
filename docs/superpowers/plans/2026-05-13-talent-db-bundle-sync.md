# Talent DB Bundle Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为本地 SQLite 人才库增加可离线传递的 bundle 级同步工具，使多台机器可以同时写入后通过导出/导入 bundle 合并数据。

**Architecture:** SQLite 的自增 `id` 继续只作为本机主键；跨机器同步新增稳定 `sync_id`、节点标识、实体别名、冲突表和删除墓碑。MVP 使用可校验的全量 zip bundle 做幂等导入；后续基于同一元数据增加增量操作日志 bundle。

**Tech Stack:** Python stdlib (`sqlite3`, `json`, `zipfile`, `hashlib`, `uuid`, `argparse`, `tempfile`)、现有 `TalentDB` API、pytest。

---

## Current Constraints

- 主库是本地 SQLite：`data/talent.db`。
- `.gitignore` 已忽略 `data/*.db`、`data/*.db-wal`、`data/*.db-shm`，数据库不会进入 Git。
- 现有候选人、详情、来源、微信时间线、评分等表主要依赖本地自增 `candidate_id`。
- `TalentDB` 会启用 WAL；单次迁移可以复制快照，但多端同时写不能靠整库覆盖。
- 现有导入工具 `scripts/talent_library.py import` 只覆盖脉脉 capture 导入，不是全量数据库同步。

## Target Semantics

1. **本地 id 不跨机器传播为身份。** Bundle 中所有引用必须使用 `sync_id` 或稳定来源键。
2. **幂等。** 同一个 bundle 导入多次不重复创建候选人、来源、详情、评分、时间线。
3. **不静默覆盖冲突。** 不同机器并发修改同一字段且值不同，写入 `sync_conflicts`，保留本地值。
4. **可传播删除。** 删除不只物理删行，还写 tombstone，后续 bundle 能让另一台机器知道删除发生过。
5. **可审计。** 每次 export/import 生成 manifest 和报告；apply 必须有确认语。
6. **索引本地重建。** 不同步 `candidate_fts`、`candidate_vectors`；导入后本地按现有初始化逻辑重建或保持可重建状态。

## Bundle Format

Bundle 是 zip 文件：

```text
talent-sync-bundle-v1.zip
  manifest.json
  checksums.sha256
  data/candidates.jsonl
  data/candidate_details.jsonl
  data/source_profiles.jsonl
  data/candidate_wechat_timelines.jsonl
  data/score_events.jsonl
  data/match_scores.jsonl
  data/tombstones.jsonl
  attachments/wechat-timelines/<relative-path>.md   # 可选
```

`manifest.json` 示例：

```json
{
  "bundle_schema_version": 1,
  "export_mode": "full",
  "source_node_id": "b2a7d2fe-8b9d-4d4d-8c2a-1ad6a4a61e35",
  "export_id": "20260513T220000Z-b2a7d2fe",
  "created_at": "2026-05-13T22:00:00Z",
  "db_schema": "talent-agent-sqlite",
  "tables": {
    "candidates": 1200,
    "candidate_details": 305,
    "source_profiles": 1217,
    "candidate_wechat_timelines": 0,
    "score_events": 24,
    "match_scores": 1200,
    "tombstones": 0
  },
  "attachments": {
    "wechat_timelines": false
  }
}
```

## Conflict Policy

Field merge policy for `candidates`:

| Field type | Policy |
| --- | --- |
| identity fields (`name`) | do not overwrite; conflict if different after normalization |
| fill-only fields (`gender`, `age`, `city`, `education`, company/title/contact fields) | fill empty local value; if both non-empty and different, create conflict |
| `skill_tags` | union, preserve existing order first |
| `data_level` | keep highest rank (`lead` < `core` < `detailed`) |
| `overall_score`, `score_version` | local score stays; imported `score_events` and `match_scores` are retained; optional conflict if both modified score after shared base |
| `updated_at`, `created_at` | local DB timestamps stay local; bundle timestamps stored only in sync metadata |

For details:

| Detail field | Policy |
| --- | --- |
| experience lists | merge by JSON canonical hash |
| `summary` | fill empty; conflict if both non-empty and different |
| `raw_data` | deep merge by top-level source namespace; conflict on same key with different canonical JSON |

For append-like records:

| Entity | Policy |
| --- | --- |
| `source_profiles` | unique by `(platform, platform_id)` when platform_id exists; otherwise by `(candidate_sync_id, platform, profile_url)` |
| `candidate_wechat_timelines` | unique by `(candidate_sync_id, chat_identifier/chat_name, start_time, end_time, markdown_path)` |
| `score_events` | append idempotently by `sync_id` |
| `match_scores` | unique by `(candidate_sync_id, jd_id, match_type)`; conflict if score/reason differ and neither side is exact duplicate |
| `pending_merges`, `merge_log` | v1 不同步，保持本机人工处理；v2 再评估 |

---

## Files

- Create: `scripts/talent_sync_models.py`  
  Bundle dataclasses, canonical JSON/hash helpers, constants.
- Create: `scripts/talent_sync.py`  
  CLI: `init`, `status`, `export`, `import`, `verify-bundle`。
- Modify: `scripts/talent_db.py`  
  Add sync metadata schema, bootstrap APIs, entity listing APIs, import/apply APIs, tombstones, conflict recording.
- Modify: `scripts/talent_models.py`  
  Add lightweight sync result dataclasses if they belong with public models.
- Create: `tests/test_talent_sync.py`  
  End-to-end bundle export/import tests.
- Modify: `tests/test_talent_db.py`  
  Schema migration and delete tombstone tests.
- Modify: `agents/workflows/talent-library/references/data-contract.md`  
  Document bundle sync as the supported multi-machine path.
- Modify: `README.md`  
  Add short operational commands.

---

### Task 1: Add Sync Metadata Schema

**Files:**
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing schema migration test**

Append to `tests/test_talent_db.py`:

```python
def test_sync_schema_initializes_node_and_entity_columns(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {"name": "Alice", "platform_id": "maimai-1"},
            platform="maimai",
        )
        row = db._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        node = db._conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'node_id'"
        ).fetchone()
        tables = {
            item[0]
            for item in db._conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    finally:
        db.close()

    assert row is not None
    assert row["sync_id"]
    assert node is not None
    assert node["value"]
    assert {
        "sync_meta",
        "sync_entity_aliases",
        "sync_conflicts",
        "sync_tombstones",
        "sync_imports",
    }.issubset(tables)
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_sync_schema_initializes_node_and_entity_columns -q
```

Expected: FAIL because `sync_meta` / `sync_id` do not exist.

- [ ] **Step 3: Implement schema additions**

In `TalentDB._init_schema()`, add:

```sql
CREATE TABLE IF NOT EXISTS sync_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_entity_aliases (
    entity_type TEXT NOT NULL,
    remote_sync_id TEXT NOT NULL,
    local_sync_id TEXT NOT NULL,
    source_node_id TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY(entity_type, remote_sync_id, source_node_id)
);

CREATE TABLE IF NOT EXISTS sync_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_sync_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    local_value TEXT,
    remote_value TEXT,
    source_node_id TEXT,
    bundle_id TEXT,
    status TEXT DEFAULT 'open',
    created_at TEXT DEFAULT (datetime('now')),
    resolved_at TEXT
);

CREATE TABLE IF NOT EXISTS sync_tombstones (
    entity_type TEXT NOT NULL,
    entity_sync_id TEXT NOT NULL,
    deleted_at TEXT DEFAULT (datetime('now')),
    source_node_id TEXT NOT NULL,
    reason TEXT,
    PRIMARY KEY(entity_type, entity_sync_id)
);

CREATE TABLE IF NOT EXISTS sync_imports (
    bundle_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL,
    imported_at TEXT DEFAULT (datetime('now')),
    mode TEXT NOT NULL,
    summary TEXT
);
```

Add migration helper:

```python
def _ensure_sync_schema(self) -> None:
    self._ensure_columns("candidates", {
        "sync_id": "TEXT",
        "sync_origin_node_id": "TEXT",
        "sync_updated_at": "TEXT",
    })
    self._ensure_columns("candidate_details", {"sync_id": "TEXT"})
    self._ensure_columns("source_profiles", {"sync_id": "TEXT"})
    self._ensure_columns("candidate_wechat_timelines", {"sync_id": "TEXT"})
    self._ensure_columns("score_events", {"sync_id": "TEXT"})
    self._ensure_columns("match_scores", {"sync_id": "TEXT"})
    self._ensure_node_id()
    self._backfill_sync_ids()
```

Add `_ensure_columns()`, `_ensure_node_id()`, `_backfill_sync_ids()` using `uuid.uuid4()`.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_sync_schema_initializes_node_and_entity_columns -q
```

Expected: PASS.

---

### Task 2: Make Local Writes Sync-Aware

**Files:**
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
def test_new_candidate_and_related_rows_receive_sync_ids(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Alice",
            "platform_id": "maimai-1",
            "work_experience": [{"company": "Acme"}],
        },
        platform="maimai",
    )
    db.update_overall_score(candidate_id, 88, "manual", {"note": "seed"})
    db.save_match_score(candidate_id, "jd-1", "final", 88, {"skill": 90}, "good")

    candidate = db._conn.execute(
        "SELECT sync_id FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()
    detail = db._conn.execute(
        "SELECT sync_id FROM candidate_details WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    source = db._conn.execute(
        "SELECT sync_id FROM source_profiles WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    score_event = db._conn.execute(
        "SELECT sync_id FROM score_events WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()
    match_score = db._conn.execute(
        "SELECT sync_id FROM match_scores WHERE candidate_id = ?",
        (candidate_id,),
    ).fetchone()

    assert candidate["sync_id"]
    assert detail["sync_id"]
    assert source["sync_id"]
    assert score_event["sync_id"]
    assert match_score["sync_id"]
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_new_candidate_and_related_rows_receive_sync_ids -q
```

Expected: FAIL for missing sync ids on at least one related table.

- [ ] **Step 3: Assign sync ids during writes**

Update insert/upsert paths:

- `_insert_candidate()`: insert `sync_id`, `sync_origin_node_id`, `sync_updated_at`.
- `_add_source_profile()`: insert/update `sync_id`.
- `_enrich_no_commit()`: insert/update `candidate_details.sync_id`.
- `update_overall_score()`: insert `score_events.sync_id`.
- `save_match_score()`: insert/update `match_scores.sync_id`.
- `add_wechat_timeline()`: insert `candidate_wechat_timelines.sync_id`.

Use helper:

```python
def _new_sync_id(entity_type: str) -> str:
    return f"{entity_type}:{uuid.uuid4()}"
```

- [ ] **Step 4: Run green tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_new_candidate_and_related_rows_receive_sync_ids -q
python -m pytest tests/test_talent_db.py -q
```

Expected: PASS.

---

### Task 3: Tombstone Deletes

**Files:**
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing tombstone test**

Append:

```python
def test_delete_candidate_records_sync_tombstone(db: TalentDB):
    candidate_id = db.ingest(
        {"name": "Alice", "platform_id": "maimai-1"},
        platform="maimai",
    )
    sync_id = db._conn.execute(
        "SELECT sync_id FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()["sync_id"]

    db.delete_candidate(candidate_id)

    row = db._conn.execute(
        """
        SELECT entity_type, entity_sync_id
        FROM sync_tombstones
        WHERE entity_type = 'candidate' AND entity_sync_id = ?
        """,
        (sync_id,),
    ).fetchone()
    assert row is not None
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_candidate_records_sync_tombstone -q
```

Expected: FAIL because delete does not write tombstone.

- [ ] **Step 3: Implement tombstone write**

In `delete_candidate()` read candidate `sync_id` before delete. Inside the same transaction insert:

```sql
INSERT INTO sync_tombstones(entity_type, entity_sync_id, source_node_id, reason)
VALUES ('candidate', ?, ?, 'local_delete')
ON CONFLICT(entity_type, entity_sync_id) DO UPDATE SET
    deleted_at = excluded.deleted_at,
    source_node_id = excluded.source_node_id,
    reason = excluded.reason
```

- [ ] **Step 4: Run green tests**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_candidate_records_sync_tombstone -q
python -m pytest tests/test_talent_db.py -q
```

Expected: PASS.

---

### Task 4: Bundle Models and Canonical Hashes

**Files:**
- Create: `scripts/talent_sync_models.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing model tests**

Create `tests/test_talent_sync.py`:

```python
import json
import zipfile
from pathlib import Path

from scripts.talent_sync_models import canonical_json, record_hash


def test_canonical_json_is_order_stable():
    left = {"b": 2, "a": [{"y": 1, "x": 2}]}
    right = {"a": [{"x": 2, "y": 1}], "b": 2}

    assert canonical_json(left) == canonical_json(right)
    assert record_hash(left) == record_hash(right)
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_canonical_json_is_order_stable -q
```

Expected: FAIL because module does not exist.

- [ ] **Step 3: Implement helpers**

Create:

```python
"""人才库 bundle 同步模型和哈希工具。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

BUNDLE_SCHEMA_VERSION = 1
CONFIRM_SYNC_TEXT = "确认同步人才库"


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def record_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class BundleManifest:
    bundle_schema_version: int
    export_mode: str
    source_node_id: str
    export_id: str
    created_at: str
    db_schema: str = "talent-agent-sqlite"
    tables: dict[str, int] = field(default_factory=dict)
    attachments: dict[str, bool] = field(default_factory=dict)
```

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_canonical_json_is_order_stable -q
```

Expected: PASS.

---

### Task 5: Full Bundle Export

**Files:**
- Create: `scripts/talent_sync.py`
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing export test**

Append to `tests/test_talent_sync.py`:

```python
from scripts.talent_db import TalentDB
from scripts.talent_sync import export_bundle


def test_export_full_bundle_contains_manifest_and_core_rows(tmp_path: Path):
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
                "work_experience": [{"company": "Acme"}],
            },
            platform="maimai",
        )
        db.save_match_score(candidate_id, "jd-1", "final", 88, {"skill": 90}, "good")
    finally:
        db.close()

    summary = export_bundle(db_path, bundle_path, mode="full")

    assert summary["tables"]["candidates"] == 1
    assert bundle_path.exists()
    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())
        assert "manifest.json" in names
        assert "checksums.sha256" in names
        assert "data/candidates.jsonl" in names
        assert "data/candidate_details.jsonl" in names
        manifest = json.loads(bundle.read("manifest.json").decode("utf-8"))
        candidate = json.loads(bundle.read("data/candidates.jsonl").decode("utf-8").splitlines()[0])

    assert manifest["bundle_schema_version"] == 1
    assert candidate["sync_id"].startswith("candidate:")
    assert "id" not in candidate
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_export_full_bundle_contains_manifest_and_core_rows -q
```

Expected: FAIL because `scripts.talent_sync` does not exist.

- [ ] **Step 3: Add read APIs to `TalentDB`**

Add methods that return JSON-ready rows without local ids:

```python
def export_sync_rows(self) -> dict[str, list[dict[str, Any]]]:
    return {
        "candidates": self._export_candidates(),
        "candidate_details": self._export_candidate_details(),
        "source_profiles": self._export_source_profiles(),
        "candidate_wechat_timelines": self._export_wechat_timelines(),
        "score_events": self._export_score_events(),
        "match_scores": self._export_match_scores(),
        "tombstones": self._export_tombstones(),
    }
```

Each child row should include `candidate_sync_id`, not `candidate_id`.

- [ ] **Step 4: Implement `export_bundle()`**

`export_bundle(db_path, bundle_path, mode="full", include_wechat_files=False)`:

1. Open `TalentDB`.
2. Read node id from `sync_meta`.
3. Write JSONL files into a temp directory.
4. Write manifest with table counts.
5. Write checksums for every payload file.
6. Zip into target path.

- [ ] **Step 5: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_export_full_bundle_contains_manifest_and_core_rows -q
```

Expected: PASS.

---

### Task 6: Bundle Verification

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing verification tests**

Append:

```python
from scripts.talent_sync import verify_bundle


def test_verify_bundle_rejects_tampered_payload(tmp_path: Path):
    db_path = tmp_path / "source.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(db_path)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()
    export_bundle(db_path, bundle_path, mode="full")

    tampered = tmp_path / "tampered.zip"
    with zipfile.ZipFile(bundle_path) as src, zipfile.ZipFile(tampered, "w") as dst:
        for name in src.namelist():
            data = src.read(name)
            if name == "data/candidates.jsonl":
                data = data.replace(b"Alice", b"Alicia")
            dst.writestr(name, data)

    result = verify_bundle(tampered)

    assert result["ok"] is False
    assert "data/candidates.jsonl" in result["errors"][0]
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_verify_bundle_rejects_tampered_payload -q
```

Expected: FAIL because `verify_bundle()` is missing.

- [ ] **Step 3: Implement checksum verification**

`verify_bundle(path)` should:

1. Require `manifest.json` and `checksums.sha256`.
2. Recompute SHA256 for each listed file.
3. Return `{"ok": True, "errors": []}` or `{"ok": False, "errors": [...]}`.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_verify_bundle_rejects_tampered_payload -q
```

Expected: PASS.

---

### Task 7: Full Bundle Import to Empty DB

**Files:**
- Modify: `scripts/talent_sync.py`
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing empty-import test**

Append:

```python
from scripts.talent_sync import import_bundle


def test_import_full_bundle_to_empty_db_remaps_local_ids(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    db = TalentDB(source_db)
    try:
        source_candidate_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "platform_id": "maimai-1",
                "work_experience": [{"company": "Acme"}],
            },
            platform="maimai",
        )
        source_sync_id = db._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (source_candidate_id,),
        ).fetchone()["sync_id"]
    finally:
        db.close()

    export_bundle(source_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        assert result["created"]["candidates"] == 1
        assert db.count() == 1
        target_candidate = db.fulltext_search("Alice")[0]
        target_sync_id = db._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (target_candidate.id,),
        ).fetchone()["sync_id"]
        detail = db.get_detail(target_candidate.id)
        source = db.get_sources(target_candidate.id)[0]
    finally:
        db.close()

    assert target_candidate.id != source_candidate_id or str(source_db) != str(target_db)
    assert target_sync_id == source_sync_id
    assert detail is not None
    assert source.platform_id == "maimai-1"
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_full_bundle_to_empty_db_remaps_local_ids -q
```

Expected: FAIL because import is missing.

- [ ] **Step 3: Implement import planner**

Add `plan_import(bundle_path, db_path)`:

1. Verify bundle checksums.
2. Read all JSONL payloads.
3. Build `candidate_sync_id -> local_candidate_id` map.
4. Resolve candidate by:
   - existing `candidates.sync_id`
   - `sync_entity_aliases`
   - existing source `(platform, platform_id)`
   - exact identity `(name, company, title, city, education)`
5. Produce plan counts: created, merged, conflicts, skipped, tombstoned.

- [ ] **Step 4: Implement apply**

Add `import_bundle(bundle_path, db_path, apply=False, confirm="")`:

- dry-run returns plan without writes.
- apply requires confirm text `确认同步人才库`.
- insert/merge parent candidates before children.
- maintain `sync_entity_aliases` when incoming sync id maps to existing local sync id.
- record `sync_imports(bundle_id, source_node_id, mode, summary)`.

- [ ] **Step 5: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_full_bundle_to_empty_db_remaps_local_ids -q
```

Expected: PASS.

---

### Task 8: Idempotent Import

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing idempotency test**

Append:

```python
def test_import_same_bundle_twice_is_idempotent(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"

    db = TalentDB(source_db)
    try:
        candidate_id = db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
        db.save_match_score(candidate_id, "jd-1", "final", 90)
    finally:
        db.close()

    export_bundle(source_db, bundle_path, mode="full")
    first = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")
    second = import_bundle(bundle_path, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        match_count = db._conn.execute("SELECT COUNT(*) FROM match_scores").fetchone()[0]
        import_count = db._conn.execute("SELECT COUNT(*) FROM sync_imports").fetchone()[0]
        candidate_count = db.count()
    finally:
        db.close()

    assert first["created"]["candidates"] == 1
    assert second["skipped"]["already_imported"] == 1
    assert candidate_count == 1
    assert match_count == 1
    assert import_count == 1
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_same_bundle_twice_is_idempotent -q
```

Expected: FAIL until bundle id is recorded and duplicate bundle import is skipped.

- [ ] **Step 3: Implement duplicate bundle handling**

If `manifest.export_id` already exists in `sync_imports`, return a skipped summary without applying rows.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_same_bundle_twice_is_idempotent -q
```

Expected: PASS.

---

### Task 9: Source-Key Merge Across Independent Nodes

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing source-key merge test**

Append:

```python
def test_import_uses_source_key_to_merge_independent_candidates(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left_id = left.ingest(
            {"name": "Alice", "current_company": "Acme", "platform_id": "maimai-1"},
            platform="maimai",
        )
        left_sync_id = left._conn.execute(
            "SELECT sync_id FROM candidates WHERE id = ?",
            (left_id,),
        ).fetchone()["sync_id"]
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "maimai-1",
            },
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm="确认同步人才库")

    left = TalentDB(left_db)
    try:
        assert left.count() == 1
        candidate = left.get(left_id)
        alias_count = left._conn.execute(
            "SELECT COUNT(*) FROM sync_entity_aliases WHERE local_sync_id = ?",
            (left_sync_id,),
        ).fetchone()[0]
    finally:
        left.close()

    assert result["merged"]["candidates"] == 1
    assert candidate.current_title == "AI PM"
    assert alias_count == 1
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_uses_source_key_to_merge_independent_candidates -q
```

Expected: FAIL until import resolution uses source keys and aliases.

- [ ] **Step 3: Implement source-key resolution**

Before inserting an incoming candidate, inspect incoming `source_profiles` for stable source keys. If local DB already has `(platform, platform_id)`, merge candidate and write `sync_entity_aliases`.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_uses_source_key_to_merge_independent_candidates -q
```

Expected: PASS.

---

### Task 10: Conflict Recording

**Files:**
- Modify: `scripts/talent_sync.py`
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing conflict test**

Append:

```python
def test_import_records_conflict_for_same_field_different_values(tmp_path: Path):
    left_db = tmp_path / "left.db"
    right_db = tmp_path / "right.db"
    bundle_path = tmp_path / "right.zip"

    left = TalentDB(left_db)
    try:
        left.ingest(
            {"name": "Alice", "city": "Shanghai", "platform_id": "maimai-1"},
            platform="maimai",
        )
    finally:
        left.close()

    right = TalentDB(right_db)
    try:
        right.ingest(
            {"name": "Alice", "city": "Beijing", "platform_id": "maimai-1"},
            platform="maimai",
        )
    finally:
        right.close()

    export_bundle(right_db, bundle_path, mode="full")
    result = import_bundle(bundle_path, left_db, apply=True, confirm="确认同步人才库")

    left = TalentDB(left_db)
    try:
        candidate = left.fulltext_search("Alice")[0]
        conflict = left._conn.execute(
            """
            SELECT field_name, local_value, remote_value
            FROM sync_conflicts
            WHERE entity_type = 'candidate'
            """,
        ).fetchone()
    finally:
        left.close()

    assert candidate.city == "Shanghai"
    assert result["conflicts"] == 1
    assert conflict["field_name"] == "city"
    assert json.loads(conflict["local_value"]) == "Shanghai"
    assert json.loads(conflict["remote_value"]) == "Beijing"
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_records_conflict_for_same_field_different_values -q
```

Expected: FAIL until conflict table is populated.

- [ ] **Step 3: Implement candidate merge policy**

Create a dedicated merge helper in `scripts/talent_sync.py`:

```python
def merge_candidate_payload(local: dict, remote: dict) -> tuple[dict, list[dict]]:
    ...
```

Use policy from `Conflict Policy`. Conflicts include `field_name`, canonical local JSON, canonical remote JSON, source node, bundle id.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_records_conflict_for_same_field_different_values -q
```

Expected: PASS.

---

### Task 11: Tombstone Import

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing tombstone sync test**

Append:

```python
def test_import_tombstone_deletes_local_candidate(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    seed_bundle = tmp_path / "seed.zip"
    delete_bundle = tmp_path / "delete.zip"

    db = TalentDB(source_db)
    try:
        candidate_id = db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()

    export_bundle(source_db, seed_bundle, mode="full")
    import_bundle(seed_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(source_db)
    try:
        local = db.fulltext_search("Alice")[0]
        db.delete_candidate(local.id)
    finally:
        db.close()

    export_bundle(source_db, delete_bundle, mode="full")
    result = import_bundle(delete_bundle, target_db, apply=True, confirm="确认同步人才库")

    db = TalentDB(target_db)
    try:
        assert db.count() == 0
    finally:
        db.close()

    assert result["deleted"]["candidates"] == 1
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_tombstone_deletes_local_candidate -q
```

Expected: FAIL until tombstones are exported and applied.

- [ ] **Step 3: Apply tombstones before upserts**

During import:

1. Load tombstones.
2. For each candidate tombstone, resolve local candidate by `sync_id` or alias.
3. Delete local candidate without creating a new local tombstone with this machine as origin.
4. Store incoming tombstone.
5. Skip incoming live rows whose sync id is tombstoned.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_import_tombstone_deletes_local_candidate -q
```

Expected: PASS.

---

### Task 12: CLI Commands

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing CLI tests**

Append:

```python
from scripts.talent_sync import main as sync_main


def test_sync_cli_export_and_dry_run_import(tmp_path: Path, capsys):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()

    assert sync_main(["export", "--db", str(source_db), "--out", str(bundle_path)]) == 0
    assert bundle_path.exists()
    assert sync_main(["import", "--db", str(target_db), "--bundle", str(bundle_path)]) == 0

    db = TalentDB(target_db)
    try:
        assert db.count() == 0
    finally:
        db.close()
    assert "dry-run" in capsys.readouterr().out


def test_sync_cli_apply_requires_confirm(tmp_path: Path):
    source_db = tmp_path / "source.db"
    target_db = tmp_path / "target.db"
    bundle_path = tmp_path / "bundle.zip"
    db = TalentDB(source_db)
    try:
        db.ingest({"name": "Alice", "platform_id": "maimai-1"}, platform="maimai")
    finally:
        db.close()
    export_bundle(source_db, bundle_path, mode="full")

    with pytest.raises(ValueError, match="确认同步人才库"):
        sync_main([
            "import",
            "--db",
            str(target_db),
            "--bundle",
            str(bundle_path),
            "--apply",
        ])
```

- [ ] **Step 2: Run red tests**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_sync_cli_export_and_dry_run_import tests/test_talent_sync.py::test_sync_cli_apply_requires_confirm -q
```

Expected: FAIL until CLI exists.

- [ ] **Step 3: Implement argparse**

Commands:

```bash
python scripts/talent_sync.py status --db data/talent.db
python scripts/talent_sync.py export --db data/talent.db --out data/sync/talent-sync-full.zip
python scripts/talent_sync.py verify-bundle --bundle data/sync/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/talent-sync-full.zip --apply --confirm "确认同步人才库"
```

- [ ] **Step 4: Run green tests**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_sync_cli_export_and_dry_run_import tests/test_talent_sync.py::test_sync_cli_apply_requires_confirm -q
```

Expected: PASS.

---

### Task 13: Optional WeChat Timeline Attachments

**Files:**
- Modify: `scripts/talent_sync.py`
- Test: `tests/test_talent_sync.py`

- [ ] **Step 1: Write failing attachment test**

Append:

```python
def test_export_can_include_wechat_timeline_attachments(tmp_path: Path):
    db_path = tmp_path / "source.db"
    timeline_dir = tmp_path / "data" / "wechat-timelines"
    timeline_dir.mkdir(parents=True)
    markdown = timeline_dir / "1-Alice-20260513000000.md"
    markdown.write_text("## 2026-05-13 10:00:00 Alice\nhello\n", encoding="utf-8")

    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice"}, platform="manual")
        db.add_wechat_timeline(
            candidate_id,
            {
                "chat_name": "Alice微信",
                "markdown_path": str(markdown),
                "start_time": "2026-05-13",
                "end_time": "2026-05-13",
            },
        )
    finally:
        db.close()

    bundle_path = tmp_path / "bundle.zip"
    export_bundle(db_path, bundle_path, mode="full", include_wechat_files=True)

    with zipfile.ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())

    assert any(name.startswith("attachments/wechat-timelines/") for name in names)
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_export_can_include_wechat_timeline_attachments -q
```

Expected: FAIL until attachments are supported.

- [ ] **Step 3: Implement safe attachment packaging**

Only include files whose resolved path exists and whose basename is copied under `attachments/wechat-timelines/`. Preserve the DB row's original path in JSONL; import should optionally restore attachments to `data/wechat-timelines/` and rewrite `markdown_path` to the restored path.

- [ ] **Step 4: Run green test**

Run:

```bash
python -m pytest tests/test_talent_sync.py::test_export_can_include_wechat_timeline_attachments -q
```

Expected: PASS.

---

### Task 14: Documentation

**Files:**
- Modify: `agents/workflows/talent-library/references/data-contract.md`
- Modify: `README.md`
- Test: `tests/test_talent_library_workflow.py`

- [ ] **Step 1: Add documentation test**

Append to `tests/test_talent_library_workflow.py`:

```python
def test_talent_library_documents_bundle_sync():
    text = (WORKFLOW / "references" / "data-contract.md").read_text(encoding="utf-8")
    assert "bundle 同步" in text
    assert "scripts/talent_sync.py export" in text
    assert "确认同步人才库" in text
```

- [ ] **Step 2: Run red test**

Run:

```bash
python -m pytest tests/test_talent_library_workflow.py::test_talent_library_documents_bundle_sync -q
```

Expected: FAIL until docs mention sync.

- [ ] **Step 3: Update docs**

Add a section:

```markdown
## 多端 bundle 同步

多台机器同时写入时，不直接复制 `data/talent.db` 覆盖另一台机器。使用：

```bash
python scripts/talent_sync.py export --db data/talent.db --out data/sync/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/talent-sync-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/talent-sync-full.zip --apply --confirm "确认同步人才库"
```

同步以 `sync_id` 和来源键为稳定身份；本地自增 id 不跨机器使用。冲突写入 `sync_conflicts`，不静默覆盖。
```

- [ ] **Step 4: Run docs test**

Run:

```bash
python -m pytest tests/test_talent_library_workflow.py::test_talent_library_documents_bundle_sync -q
```

Expected: PASS.

---

### Task 15: Full Verification

**Files:**
- All modified files

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_talent_sync.py tests/test_talent_db.py tests/test_talent_library_cli.py tests/test_talent_library_workflow.py -q
```

Expected: PASS.

- [ ] **Step 2: Run syntax checks**

Run:

```bash
python -m py_compile scripts/talent_sync.py scripts/talent_sync_models.py scripts/talent_db.py scripts/talent_models.py
```

Expected: PASS.

- [ ] **Step 3: Run full regression**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: PASS with only known baseline warnings.

- [ ] **Step 4: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: PASS.

---

## Operational Flow After Implementation

Machine A:

```bash
python scripts/talent_sync.py status --db data/talent.db
python scripts/talent_sync.py export --db data/talent.db --out data/sync/a-full.zip
```

Machine B:

```bash
python scripts/talent_sync.py verify-bundle --bundle data/sync/a-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/a-full.zip
python scripts/talent_sync.py import --db data/talent.db --bundle data/sync/a-full.zip --apply --confirm "确认同步人才库"
```

If conflicts appear:

```bash
python scripts/talent_sync.py conflicts --db data/talent.db
```

`conflicts` can be implemented in a follow-up task if the MVP only records conflicts and surfaces them in import reports.

---

## Deferred Phase: Incremental Bundles

After full bundle sync is proven:

1. Add `sync_operations` log table.
2. Add per-node import watermarks.
3. Wrap write APIs to record local operations.
4. Export `--mode incremental --since <cursor>`.
5. Let full snapshots compact old operations.

Do not implement incremental mode before full bundle import is idempotent and conflict-safe.

## Self-Review

- Spec coverage: initialization, export, verification, import, idempotency, source-key merge, conflicts, tombstones, CLI, docs, and verification are covered.
- Placeholder scan: no implementation step contains unfinished placeholder wording; deferred incremental phase is explicitly out of MVP scope.
- Type consistency: `sync_id`, `sync_meta`, `sync_entity_aliases`, `sync_conflicts`, `sync_tombstones`, and `sync_imports` are named consistently across tasks.
