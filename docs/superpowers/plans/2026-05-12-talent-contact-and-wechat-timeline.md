# Talent Contact And WeChat Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add single-value candidate contact fields and a manually triggered WeChat chat sync flow that exports markdown with `wechat-cli` and indexes the archive in the local talent database.

**Architecture:** Extend the existing SQLite-first `TalentDB` model with four nullable contact columns and a lightweight `candidate_wechat_timelines` index table. Keep chat bodies outside SQLite under `data/wechat-timelines/*.md`; `scripts/talent_library.py wechat-sync` orchestrates candidate lookup, optional contact patching, `wechat-cli export`, markdown wrapping, and index writes. Add a runtime-neutral `wechat-chat-sync` workflow plus a thin `.claude/skills` adapter, matching the existing repository architecture.

**Tech Stack:** Python 3.13, SQLite, pytest, argparse, subprocess, existing `wechat-cli.exe`, markdown files.

---

## File Structure

Create:

- `agents/workflows/wechat-chat-sync/AGENT.md` — canonical workflow for manual WeChat chat synchronization.
- `agents/workflows/wechat-chat-sync/references/cli-contract.md` — `wechat-cli export` contract, parameters, and failure handling.
- `agents/workflows/wechat-chat-sync/references/timeline-format.md` — markdown archive format and privacy rules.
- `agents/workflows/wechat-chat-sync/assets/timeline-template.md` — front matter template for archived timelines.
- `.claude/skills/wechat-chat-sync/SKILL.md` — Claude Code adapter that points to the canonical workflow.
- `tests/test_wechat_chat_sync_workflow.py` — workflow resource and architecture tests.

Modify:

- `scripts/talent_models.py` — add contact fields to `Candidate`; add `WechatTimeline` dataclass.
- `scripts/talent_db.py` — add contact schema migration, contact ingest/merge/update support, timeline index table and API.
- `scripts/talent_library.py` — add `wechat-sync` command and helper functions around `wechat-cli export`.
- `schemas/candidate.schema.json` — document `email`, `phone`, `wechat`, and `wechat_id`.
- `tests/test_talent_models.py` — cover contact serialization and `WechatTimeline`.
- `tests/test_talent_db.py` — cover contact schema/update/ingest fill-only behavior and timeline cascade.
- `tests/test_talent_library_cli.py` — cover `wechat-sync` success/failure/time-range validation.
- `tests/test_agent_architecture.py` — include `wechat-chat-sync` in canonical workflow adapter checks.
- `tests/test_talent_library_workflow.py` — assert contact and WeChat sync references are declared.
- `agents/workflows/talent-library/AGENT.md` — declare `wechat-sync` as an adjacent workflow entry.
- `agents/workflows/talent-library/references/data-contract.md` — add contact fields and timeline API.
- `agents/workflows/talent-library/references/scenarios.md` — update `update` flow for contact fields and point chat sync to the new workflow.
- `agents/workflows/talent-library/references/safety-rules.md` — add privacy and time-range requirements.
- `.claude/skills/talent-library/SKILL.md` — extend trigger description to mention contact updates and WeChat sync routing.
- `tasks/todo.md` — mark design review complete and record this implementation plan.

Do not modify:

- `data/talent.db`, `data/talent.db-wal`, `data/talent.db-shm`.
- Existing platform scraper implementation.
- Existing legacy `data/candidates/*.json` files.

---

### Task 1: Contact Model And Schema

**Files:**
- Modify: `scripts/talent_models.py`
- Modify: `scripts/talent_db.py`
- Modify: `schemas/candidate.schema.json`
- Test: `tests/test_talent_models.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing model tests for contact fields**

Add this test to `tests/test_talent_models.py` inside `class TestCandidate`:

```python
    def test_contact_fields_round_trip(self):
        candidate = Candidate(
            id=1,
            name="张三",
            email="zhangsan@example.com",
            phone="13800138000",
            wechat="zhangsan-wx",
            wechat_id="wxid_zhangsan",
        )

        payload = candidate.to_dict()
        restored = Candidate.from_dict(payload)

        assert payload["email"] == "zhangsan@example.com"
        assert payload["phone"] == "13800138000"
        assert payload["wechat"] == "zhangsan-wx"
        assert payload["wechat_id"] == "wxid_zhangsan"
        assert restored.email == "zhangsan@example.com"
        assert restored.phone == "13800138000"
        assert restored.wechat == "zhangsan-wx"
        assert restored.wechat_id == "wxid_zhangsan"
```

- [ ] **Step 2: Run model test to verify it fails**

Run:

```bash
python -m pytest tests/test_talent_models.py::TestCandidate::test_contact_fields_round_trip -q
```

Expected: FAIL with `TypeError: Candidate.__init__() got an unexpected keyword argument 'email'`.

- [ ] **Step 3: Implement contact fields in `Candidate`**

In `scripts/talent_models.py`, update `Candidate`:

```python
@dataclass(frozen=True)
class Candidate:
    id: int
    name: str
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    work_years: int | None = None
    education: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    expected_salary: str | None = None
    expected_city: str | None = None
    expected_title: str | None = None
    hunting_status: str | None = None
    email: str | None = None
    phone: str | None = None
    wechat: str | None = None
    wechat_id: str | None = None
    skill_tags: tuple[str, ...] = ()
    data_level: str = "lead"
    overall_score: float = 0.0
    score_version: int = 0
    created_at: str = ""
    updated_at: str = ""
```

Add these entries to `Candidate.to_dict()` after `hunting_status`:

```python
            "email": self.email,
            "phone": self.phone,
            "wechat": self.wechat,
            "wechat_id": self.wechat_id,
```

Add these entries to `Candidate.from_dict()` after `hunting_status=data.get("hunting_status"),`:

```python
            email=data.get("email"),
            phone=data.get("phone"),
            wechat=data.get("wechat"),
            wechat_id=data.get("wechat_id"),
```

- [ ] **Step 4: Run model test to verify it passes**

Run:

```bash
python -m pytest tests/test_talent_models.py::TestCandidate::test_contact_fields_round_trip -q
```

Expected: PASS.

- [ ] **Step 5: Write failing database tests for contact schema and updates**

Add these tests to `tests/test_talent_db.py` near the existing `test_update_candidate_*` tests:

```python
def test_new_database_supports_candidate_contact_fields(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Contact Person",
            "email": "contact@example.com",
            "phone": "13900139000",
            "wechat": "contact-wx",
            "wechat_id": "wxid_contact",
        },
        platform="manual",
    )

    candidate = db.get(candidate_id)

    assert candidate is not None
    assert candidate.email == "contact@example.com"
    assert candidate.phone == "13900139000"
    assert candidate.wechat == "contact-wx"
    assert candidate.wechat_id == "wxid_contact"


def test_update_candidate_updates_contact_fields(db_with_candidate):
    db, candidate_id = db_with_candidate

    updated = db.update_candidate(
        candidate_id,
        {
            "email": "alice@example.com",
            "phone": "13800138000",
            "wechat": "alice-wx",
            "wechat_id": "wxid_alice",
        },
    )

    assert updated.email == "alice@example.com"
    assert updated.phone == "13800138000"
    assert updated.wechat == "alice-wx"
    assert updated.wechat_id == "wxid_alice"
```

- [ ] **Step 6: Run database contact tests to verify they fail**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields -q
```

Expected: FAIL because contact columns and update fields are not implemented.

- [ ] **Step 7: Add contact columns and migration helper**

In `scripts/talent_db.py`, add this helper near `_json_dumps` helper functions at the bottom of the file:

```python
def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}
```

In `TalentDB`, add this method before `_init_fts`:

```python
    def _ensure_candidate_contact_columns(self) -> None:
        existing = _table_columns(self._conn, "candidates")
        for column in ("email", "phone", "wechat", "wechat_id"):
            if column not in existing:
                self._conn.execute(f"ALTER TABLE candidates ADD COLUMN {column} TEXT")
```

In `_init_schema`, add contact columns to `CREATE TABLE IF NOT EXISTS candidates` after `hunting_status TEXT,`:

```sql
                email TEXT,
                phone TEXT,
                wechat TEXT,
                wechat_id TEXT,
```

Call the migration helper immediately after `self._conn.executescript(...)` and before `_init_fts()`:

```python
        self._ensure_candidate_contact_columns()
        self._init_fts()
```

- [ ] **Step 8: Add contact fields to insert, merge, and update allowlist**

In `_CANDIDATE_UPDATE_FIELDS`, add:

```python
    "email",
    "phone",
    "wechat",
    "wechat_id",
```

In `_insert_candidate`, add columns after `hunting_status`:

```sql
                email, phone, wechat, wechat_id,
```

Add four placeholders to the `VALUES` list so it becomes:

```sql
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

Add values after `data.get("hunting_status"),`:

```python
                data.get("email"),
                data.get("phone"),
                data.get("wechat"),
                data.get("wechat_id"),
```

In `_merge_candidate`, extend `fill_only_fields`:

```python
            "email",
            "phone",
            "wechat",
            "wechat_id",
```

- [ ] **Step 9: Run database contact tests to verify they pass**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields -q
```

Expected: PASS.

- [ ] **Step 10: Write failing ingest fill-only contact test**

Add this test to `tests/test_talent_db.py` near `test_same_platform_id_merges_even_when_identity_fields_change`:

```python
def test_batch_ingest_contact_fields_fill_empty_without_overwriting(db: TalentDB):
    candidate_id = db.ingest(
        {
            "name": "Contact Merge",
            "current_company": "OldCo",
            "current_title": "PM",
            "city": "上海",
            "education": "本科",
            "platform_id": "contact-1",
            "email": "old@example.com",
        },
        platform="maimai",
    )

    result = db.batch_ingest(
        [
            {
                "name": "Contact Merge",
                "current_company": "NewCo",
                "current_title": "Director",
                "city": "北京",
                "education": "硕士",
                "platform_id": "contact-1",
                "email": "new@example.com",
                "phone": "13800138000",
                "wechat": "contact-wx",
                "wechat_id": "wxid_contact",
            }
        ],
        platform="maimai",
    )

    candidate = db.get(candidate_id)

    assert result.merged == 1
    assert candidate is not None
    assert candidate.email == "old@example.com"
    assert candidate.phone == "13800138000"
    assert candidate.wechat == "contact-wx"
    assert candidate.wechat_id == "wxid_contact"
```

- [ ] **Step 11: Run ingest fill-only contact test**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_batch_ingest_contact_fields_fill_empty_without_overwriting -q
```

Expected: PASS after Step 8 because `_merge_candidate` now uses fill-only behavior.

- [ ] **Step 12: Update candidate JSON schema**

In `schemas/candidate.schema.json`, add these properties after `hunting_status` or `status`:

```json
    "email": {
      "type": "string",
      "description": "当前可用邮箱"
    },
    "phone": {
      "type": "string",
      "description": "当前可用手机号"
    },
    "wechat": {
      "type": "string",
      "description": "当前微信号或顾问可识别的微信名片标识"
    },
    "wechat_id": {
      "type": "string",
      "description": "预留微信内部 id 或稳定 id"
    },
```

Keep these fields optional.

- [ ] **Step 13: Run focused model and database regression**

Run:

```bash
python -m pytest tests/test_talent_models.py tests/test_talent_db.py::test_new_database_supports_candidate_contact_fields tests/test_talent_db.py::test_update_candidate_updates_contact_fields tests/test_talent_db.py::test_batch_ingest_contact_fields_fill_empty_without_overwriting -q
```

Expected: PASS.

- [ ] **Step 14: Commit contact model and schema**

Run:

```bash
git add scripts/talent_models.py scripts/talent_db.py schemas/candidate.schema.json tests/test_talent_models.py tests/test_talent_db.py
git commit -m "feat: add candidate contact fields"
```

Expected: commit succeeds.

---

### Task 2: WeChat Timeline Index API

**Files:**
- Modify: `scripts/talent_models.py`
- Modify: `scripts/talent_db.py`
- Test: `tests/test_talent_models.py`
- Test: `tests/test_talent_db.py`

- [ ] **Step 1: Write failing model test for `WechatTimeline`**

Add `WechatTimeline` to the import list in `tests/test_talent_models.py`:

```python
    WechatTimeline,
```

Add this test to `class TestOtherModels`:

```python
    def test_create_wechat_timeline_model(self):
        timeline = WechatTimeline(
            id=1,
            candidate_id=10,
            chat_name="张三",
            chat_identifier="wxid_zhangsan",
            start_time="2026-05-01",
            end_time="2026-05-12",
            message_count=42,
            markdown_path="data/wechat-timelines/10-zhangsan-20260512120000.md",
            source_tool="wechat-cli",
            synced_at="2026-05-12T12:00:00",
        )

        assert timeline.candidate_id == 10
        assert timeline.chat_name == "张三"
        assert timeline.source_tool == "wechat-cli"
```

- [ ] **Step 2: Run model test to verify it fails**

Run:

```bash
python -m pytest tests/test_talent_models.py::TestOtherModels::test_create_wechat_timeline_model -q
```

Expected: FAIL with import error for `WechatTimeline`.

- [ ] **Step 3: Add `WechatTimeline` dataclass**

In `scripts/talent_models.py`, add this dataclass after `SourceProfile`:

```python
@dataclass(frozen=True)
class WechatTimeline:
    id: int
    candidate_id: int
    chat_name: str
    markdown_path: str
    chat_identifier: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    message_count: int | None = None
    source_tool: str = "wechat-cli"
    synced_at: str = ""
```

- [ ] **Step 4: Run model test to verify it passes**

Run:

```bash
python -m pytest tests/test_talent_models.py::TestOtherModels::test_create_wechat_timeline_model -q
```

Expected: PASS.

- [ ] **Step 5: Write failing database timeline tests**

Add `WechatTimeline` to the import list in `tests/test_talent_db.py`:

```python
    WechatTimeline,
```

Add these tests near the delete tests in `tests/test_talent_db.py`:

```python
def test_add_and_get_wechat_timeline(db_with_candidate):
    db, candidate_id = db_with_candidate

    timeline = db.add_wechat_timeline(
        candidate_id,
        {
            "chat_name": "张三",
            "chat_identifier": "wxid_zhangsan",
            "start_time": "2026-05-01",
            "end_time": "2026-05-12",
            "message_count": 42,
            "markdown_path": "data/wechat-timelines/1-zhangsan-20260512120000.md",
        },
    )

    timelines = db.get_wechat_timelines(candidate_id)

    assert isinstance(timeline, WechatTimeline)
    assert timeline.id > 0
    assert timeline.candidate_id == candidate_id
    assert timeline.chat_name == "张三"
    assert timeline.source_tool == "wechat-cli"
    assert len(timelines) == 1
    assert timelines[0].markdown_path == "data/wechat-timelines/1-zhangsan-20260512120000.md"


def test_add_wechat_timeline_rejects_missing_candidate(db: TalentDB):
    with pytest.raises(ValueError, match="Candidate does not exist"):
        db.add_wechat_timeline(
            999,
            {
                "chat_name": "张三",
                "markdown_path": "data/wechat-timelines/missing.md",
            },
        )
```

- [ ] **Step 6: Run timeline database tests to verify they fail**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_add_and_get_wechat_timeline tests/test_talent_db.py::test_add_wechat_timeline_rejects_missing_candidate -q
```

Expected: FAIL because `TalentDB.add_wechat_timeline` does not exist.

- [ ] **Step 7: Add timeline table to schema**

In `scripts/talent_db.py`, import `WechatTimeline`:

```python
    WechatTimeline,
```

Inside `_init_schema`, add this table after `source_profiles`:

```sql
            CREATE TABLE IF NOT EXISTS candidate_wechat_timelines (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                chat_name TEXT NOT NULL,
                chat_identifier TEXT,
                start_time TEXT,
                end_time TEXT,
                message_count INTEGER,
                markdown_path TEXT NOT NULL,
                source_tool TEXT DEFAULT 'wechat-cli',
                synced_at TEXT DEFAULT (datetime('now'))
            );
```

Add indexes near the existing indexes:

```sql
            CREATE INDEX IF NOT EXISTS idx_wechat_timelines_candidate
                ON candidate_wechat_timelines(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_wechat_timelines_chat_name
                ON candidate_wechat_timelines(chat_name);
```

- [ ] **Step 8: Add timeline API methods**

In `scripts/talent_db.py`, add these methods after `get_sources`:

```python
    def add_wechat_timeline(
        self, candidate_id: int, data: dict[str, Any]
    ) -> WechatTimeline:
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        chat_name = data.get("chat_name")
        markdown_path = data.get("markdown_path")
        if not chat_name:
            raise ValueError("chat_name is required")
        if not markdown_path:
            raise ValueError("markdown_path is required")

        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO candidate_wechat_timelines (
                    candidate_id, chat_name, chat_identifier, start_time,
                    end_time, message_count, markdown_path, source_tool
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    chat_name,
                    data.get("chat_identifier"),
                    data.get("start_time"),
                    data.get("end_time"),
                    data.get("message_count"),
                    markdown_path,
                    data.get("source_tool") or "wechat-cli",
                ),
            )
            self._conn.execute(
                "UPDATE candidates SET updated_at = datetime('now') WHERE id = ?",
                (candidate_id,),
            )
        return self._get_wechat_timeline(int(cursor.lastrowid))

    def get_wechat_timelines(self, candidate_id: int) -> list[WechatTimeline]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM candidate_wechat_timelines
            WHERE candidate_id = ?
            ORDER BY synced_at DESC, id DESC
            """,
            (candidate_id,),
        ).fetchall()
        return [_row_to_wechat_timeline(row) for row in rows]

    def _get_wechat_timeline(self, timeline_id: int) -> WechatTimeline:
        row = self._conn.execute(
            "SELECT * FROM candidate_wechat_timelines WHERE id = ?",
            (timeline_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"WeChat timeline does not exist: {timeline_id}")
        return _row_to_wechat_timeline(row)
```

Add this helper near `_row_to_candidate`:

```python
def _row_to_wechat_timeline(row: sqlite3.Row) -> WechatTimeline:
    return WechatTimeline(
        id=int(row["id"]),
        candidate_id=int(row["candidate_id"]),
        chat_name=row["chat_name"],
        chat_identifier=row["chat_identifier"],
        start_time=row["start_time"],
        end_time=row["end_time"],
        message_count=row["message_count"],
        markdown_path=row["markdown_path"],
        source_tool=row["source_tool"] or "wechat-cli",
        synced_at=row["synced_at"] or "",
    )
```

- [ ] **Step 9: Run timeline database tests to verify they pass**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_add_and_get_wechat_timeline tests/test_talent_db.py::test_add_wechat_timeline_rejects_missing_candidate -q
```

Expected: PASS.

- [ ] **Step 10: Write failing delete cascade count test**

Update `DeleteResult` expectations by adding this test near `test_delete_candidate_removes_candidate_and_related_rows`:

```python
def test_delete_candidate_removes_wechat_timeline_rows(db_with_candidate):
    db, candidate_id = db_with_candidate
    db.add_wechat_timeline(
        candidate_id,
        {
            "chat_name": "张三",
            "markdown_path": "data/wechat-timelines/1-zhangsan.md",
        },
    )

    result = db.delete_candidate(candidate_id)

    assert result.timelines_deleted == 1
    assert db.get_wechat_timelines(candidate_id) == []
```

- [ ] **Step 11: Run delete cascade count test to verify it fails**

Run:

```bash
python -m pytest tests/test_talent_db.py::test_delete_candidate_removes_wechat_timeline_rows -q
```

Expected: FAIL because `DeleteResult.timelines_deleted` is missing.

- [ ] **Step 12: Add timeline delete count to `DeleteResult` and `delete_candidate`**

In `scripts/talent_models.py`, add a field to `DeleteResult`:

```python
    timelines_deleted: int = 0
```

Add it to `related_rows_deleted`:

```python
            + self.timelines_deleted
```

Add it to `to_dict()`:

```python
            "timelines_deleted": self.timelines_deleted,
```

In `scripts/talent_db.py`, in `delete_candidate`, count rows before score events:

```python
        timelines_deleted = _count_rows(
            self._conn, "candidate_wechat_timelines", "candidate_id", candidate_id
        )
```

Pass it into `DeleteResult`:

```python
            timelines_deleted=timelines_deleted,
```

- [ ] **Step 13: Run focused timeline regression**

Run:

```bash
python -m pytest tests/test_talent_models.py::TestOtherModels::test_create_wechat_timeline_model tests/test_talent_db.py::test_add_and_get_wechat_timeline tests/test_talent_db.py::test_add_wechat_timeline_rejects_missing_candidate tests/test_talent_db.py::test_delete_candidate_removes_wechat_timeline_rows -q
```

Expected: PASS.

- [ ] **Step 14: Commit timeline index API**

Run:

```bash
git add scripts/talent_models.py scripts/talent_db.py tests/test_talent_models.py tests/test_talent_db.py
git commit -m "feat: index wechat timeline archives"
```

Expected: commit succeeds.

---

### Task 3: `talent_library.py wechat-sync` CLI

**Files:**
- Modify: `scripts/talent_library.py`
- Test: `tests/test_talent_library_cli.py`

- [ ] **Step 1: Write failing CLI test for successful sync**

Add these imports at the top of `tests/test_talent_library_cli.py`:

```python
import subprocess
```

Add this test near the existing CLI tests:

```python
def test_wechat_sync_exports_markdown_and_indexes_timeline(tmp_path: Path, monkeypatch):
    from scripts.talent_library import main

    db_path = tmp_path / "talent.db"
    output_dir = tmp_path / "wechat-timelines"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice Chen"}, platform="manual")
    finally:
        db.close()

    def fake_which(name):
        if name in {"wechat-cli.exe", "wechat-cli"}:
            return "wechat-cli.exe"
        return None

    def fake_run(command, check, capture_output, text, encoding):
        output_index = command.index("--output") + 1
        Path(command[output_index]).write_text(
            "## 2026-05-01 10:00:00 Alice\n你好\n\n"
            "## 2026-05-01 10:01:00 顾问\n你好，方便聊聊吗？\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("scripts.talent_library.shutil.which", fake_which)
    monkeypatch.setattr("scripts.talent_library.subprocess.run", fake_run)

    assert main(
        [
            "wechat-sync",
            "--candidate-id",
            str(candidate_id),
            "--chat-name",
            "Alice微信",
            "--start-time",
            "2026-05-01",
            "--end-time",
            "2026-05-12",
            "--db",
            str(db_path),
            "--out-dir",
            str(output_dir),
            "--wechat",
            "alice-wx",
        ]
    ) == 0

    files = list(output_dir.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "candidate_id: " + str(candidate_id) in text
    assert "chat_name: Alice微信" in text
    assert "## 2026-05-01 10:00:00 Alice" in text

    db = TalentDB(db_path)
    try:
        candidate = db.get(candidate_id)
        timelines = db.get_wechat_timelines(candidate_id)
    finally:
        db.close()

    assert candidate is not None
    assert candidate.wechat == "alice-wx"
    assert len(timelines) == 1
    assert timelines[0].chat_name == "Alice微信"
    assert timelines[0].message_count == 2
```

- [ ] **Step 2: Run successful sync test to verify it fails**

Run:

```bash
python -m pytest tests/test_talent_library_cli.py::test_wechat_sync_exports_markdown_and_indexes_timeline -q
```

Expected: FAIL because the `wechat-sync` subcommand does not exist.

- [ ] **Step 3: Add imports and constants to `scripts/talent_library.py`**

At the top of `scripts/talent_library.py`, add:

```python
import re
import shutil
import subprocess
```

Update the datetime import:

```python
from datetime import date, datetime
```

Add constants after `IMPORT_CONFIRM_TEXT`:

```python
WECHAT_SOURCE_TOOL = "wechat-cli"
WECHAT_MESSAGE_HEADING = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}", re.MULTILINE)
```

- [ ] **Step 4: Add WeChat helper functions**

Add these helpers before `cmd_import`:

```python
def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE)
    return cleaned.strip("-._") or "wechat"


def _default_wechat_timeline_dir() -> Path:
    return Path("data") / "wechat-timelines"


def _wechat_cli_path() -> str:
    executable = shutil.which("wechat-cli.exe") or shutil.which("wechat-cli")
    if executable is None:
        raise RuntimeError("wechat-cli is not available in PATH")
    return executable


def _count_wechat_markdown_messages(markdown: str) -> int | None:
    count = len(WECHAT_MESSAGE_HEADING.findall(markdown))
    return count if count > 0 else None


def _build_wechat_export_command(
    chat_name: str,
    output_path: Path,
    start_time: str,
    end_time: str,
    limit: int | None,
) -> list[str]:
    command = [
        _wechat_cli_path(),
        "export",
        chat_name,
        "--format",
        "markdown",
        "--output",
        str(output_path),
        "--start-time",
        start_time,
        "--end-time",
        end_time,
    ]
    if limit is not None:
        command.extend(["--limit", str(limit)])
    return command


def _render_wechat_timeline(
    candidate_id: int,
    candidate_name: str,
    chat_name: str,
    chat_identifier: str | None,
    start_time: str,
    end_time: str,
    export_command: list[str],
    body: str,
) -> str:
    synced_at = datetime.now().isoformat(timespec="seconds")
    lines = [
        "---",
        f"candidate_id: {candidate_id}",
        f"candidate_name: {candidate_name}",
        f"chat_name: {chat_name}",
        f"chat_identifier: {chat_identifier or ''}",
        f"start_time: {start_time}",
        f"end_time: {end_time}",
        f"source_tool: {WECHAT_SOURCE_TOOL}",
        f"synced_at: {synced_at}",
        "export_command:",
    ]
    lines.extend(f"  - {part}" for part in export_command)
    lines.extend(["---", "", body.rstrip(), ""])
    return "\n".join(lines)
```

- [ ] **Step 5: Add `cmd_wechat_sync`**

Add this function before `cmd_detail`:

```python
def cmd_wechat_sync(args: argparse.Namespace) -> int:
    if not args.start_time or not args.end_time:
        raise ValueError("wechat-sync requires both --start-time and --end-time")

    db = TalentDB(args.db)
    try:
        candidate = db.get(args.candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate does not exist: {args.candidate_id}")

        contact_patch = {
            key: value
            for key, value in {
                "email": args.email,
                "phone": args.phone,
                "wechat": args.wechat,
                "wechat_id": args.wechat_id,
            }.items()
            if value is not None
        }
        if contact_patch:
            candidate = db.update_candidate(args.candidate_id, contact_patch)

        out_dir = Path(args.out_dir) if args.out_dir else _default_wechat_timeline_dir()
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = (
            f"{args.candidate_id}-"
            f"{_safe_filename_part(candidate.name)}-"
            f"{stamp}.md"
        )
        final_path = out_dir / filename
        temp_path = out_dir / f".{filename}.export.tmp"
        command = _build_wechat_export_command(
            args.chat_name,
            temp_path,
            args.start_time,
            args.end_time,
            args.limit,
        )
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "wechat-cli export failed: " + (exc.stderr or exc.stdout or str(exc))
            ) from exc

        body = temp_path.read_text(encoding="utf-8-sig")
        message_count = _count_wechat_markdown_messages(body)
        final_path.write_text(
            _render_wechat_timeline(
                args.candidate_id,
                candidate.name,
                args.chat_name,
                args.chat_identifier,
                args.start_time,
                args.end_time,
                command,
                body,
            ),
            encoding="utf-8",
        )
        temp_path.unlink(missing_ok=True)

        timeline = db.add_wechat_timeline(
            args.candidate_id,
            {
                "chat_name": args.chat_name,
                "chat_identifier": args.chat_identifier,
                "start_time": args.start_time,
                "end_time": args.end_time,
                "message_count": message_count,
                "markdown_path": str(final_path),
                "source_tool": WECHAT_SOURCE_TOOL,
            },
        )
    finally:
        db.close()

    print(
        "微信聊天同步完成：候选人 {candidate_id}，聊天 {chat_name}，消息 {message_count}，"
        "归档 {path}，索引 {timeline_id}".format(
            candidate_id=args.candidate_id,
            chat_name=args.chat_name,
            message_count=message_count if message_count is not None else "未知",
            path=final_path,
            timeline_id=timeline.id,
        )
    )
    return 0
```

- [ ] **Step 6: Add parser for `wechat-sync`**

In `build_parser()`, add this subparser before `detail`:

```python
    wechat_sync = subparsers.add_parser("wechat-sync", help="手动同步微信聊天记录")
    wechat_sync.add_argument("--candidate-id", type=int, required=True, help="候选人 ID")
    wechat_sync.add_argument("--chat-name", required=True, help="微信联系人名或群名")
    wechat_sync.add_argument("--chat-identifier", help="可选微信稳定标识")
    wechat_sync.add_argument("--start-time", required=True, help="起始时间 YYYY-MM-DD [HH:MM[:SS]]")
    wechat_sync.add_argument("--end-time", required=True, help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
    wechat_sync.add_argument("--limit", type=int, help="最大导出消息数")
    wechat_sync.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    wechat_sync.add_argument("--out-dir", help="聊天 markdown 归档目录")
    wechat_sync.add_argument("--email", help="同步前更新候选人邮箱")
    wechat_sync.add_argument("--phone", help="同步前更新候选人手机号")
    wechat_sync.add_argument("--wechat", help="同步前更新候选人微信号")
    wechat_sync.add_argument("--wechat-id", help="同步前更新候选人微信 id")
    wechat_sync.set_defaults(func=cmd_wechat_sync)
```

- [ ] **Step 7: Run successful sync test to verify it passes**

Run:

```bash
python -m pytest tests/test_talent_library_cli.py::test_wechat_sync_exports_markdown_and_indexes_timeline -q
```

Expected: PASS.

- [ ] **Step 8: Write failing CLI validation tests**

Add these tests to `tests/test_talent_library_cli.py`:

```python
def test_wechat_sync_requires_existing_candidate(tmp_path: Path, monkeypatch):
    from scripts.talent_library import main

    monkeypatch.setattr("scripts.talent_library.shutil.which", lambda name: "wechat-cli.exe")

    with pytest.raises(ValueError, match="Candidate does not exist"):
        main(
            [
                "wechat-sync",
                "--candidate-id",
                "999",
                "--chat-name",
                "张三",
                "--start-time",
                "2026-05-01",
                "--end-time",
                "2026-05-12",
                "--db",
                str(tmp_path / "talent.db"),
            ]
        )


def test_wechat_sync_reports_cli_failure(tmp_path: Path, monkeypatch):
    from scripts.talent_library import main

    db_path = tmp_path / "talent.db"
    db = TalentDB(db_path)
    try:
        candidate_id = db.ingest({"name": "Alice Chen"}, platform="manual")
    finally:
        db.close()

    def fake_run(command, check, capture_output, text, encoding):
        raise subprocess.CalledProcessError(
            1,
            command,
            output="",
            stderr="wechat database locked",
        )

    monkeypatch.setattr("scripts.talent_library.shutil.which", lambda name: "wechat-cli.exe")
    monkeypatch.setattr("scripts.talent_library.subprocess.run", fake_run)

    with pytest.raises(RuntimeError, match="wechat-cli export failed"):
        main(
            [
                "wechat-sync",
                "--candidate-id",
                str(candidate_id),
                "--chat-name",
                "Alice微信",
                "--start-time",
                "2026-05-01",
                "--end-time",
                "2026-05-12",
                "--db",
                str(db_path),
                "--out-dir",
                str(tmp_path / "wechat-timelines"),
            ]
        )

    db = TalentDB(db_path)
    try:
        assert db.get_wechat_timelines(candidate_id) == []
    finally:
        db.close()
```

- [ ] **Step 9: Run CLI validation tests**

Run:

```bash
python -m pytest tests/test_talent_library_cli.py::test_wechat_sync_requires_existing_candidate tests/test_talent_library_cli.py::test_wechat_sync_reports_cli_failure -q
```

Expected: PASS.

- [ ] **Step 10: Run CLI help smoke**

Run:

```bash
python scripts/talent_library.py wechat-sync --help
```

Expected: output includes `--candidate-id`, `--chat-name`, `--start-time`, `--end-time`, and `--out-dir`.

- [ ] **Step 11: Run focused CLI regression**

Run:

```bash
python -m pytest tests/test_talent_library_cli.py -q
```

Expected: PASS.

- [ ] **Step 12: Commit WeChat sync CLI**

Run:

```bash
git add scripts/talent_library.py tests/test_talent_library_cli.py
git commit -m "feat: add wechat chat sync cli"
```

Expected: commit succeeds.

---

### Task 4: Canonical Workflow And Skill Adapter

**Files:**
- Create: `agents/workflows/wechat-chat-sync/AGENT.md`
- Create: `agents/workflows/wechat-chat-sync/references/cli-contract.md`
- Create: `agents/workflows/wechat-chat-sync/references/timeline-format.md`
- Create: `agents/workflows/wechat-chat-sync/assets/timeline-template.md`
- Create: `.claude/skills/wechat-chat-sync/SKILL.md`
- Modify: `tests/test_agent_architecture.py`
- Create: `tests/test_wechat_chat_sync_workflow.py`

- [ ] **Step 1: Write failing architecture test by adding workflow name**

In `tests/test_agent_architecture.py`, update `WORKFLOWS`:

```python
WORKFLOWS = [
    "public-search",
    "platform-match",
    "screen",
    "report",
    "talent-library",
    "wechat-chat-sync",
]
```

- [ ] **Step 2: Run architecture test to verify it fails**

Run:

```bash
python -m pytest tests/test_agent_architecture.py::test_canonical_workflow_files_exist -q
```

Expected: FAIL with missing canonical workflow for `wechat-chat-sync`.

- [ ] **Step 3: Create canonical workflow**

Create `agents/workflows/wechat-chat-sync/AGENT.md`:

```markdown
---
name: wechat-chat-sync
description: "微信聊天记录手动同步。用于顾问指定候选人、微信联系人或群名、时间范围，通过 wechat-cli 导出 markdown 聊天记录，并把归档索引写回本地人才库。触发词：同步微信聊天、微信聊天记录、wechat sync、聊天时间线。"
---

# wechat-chat-sync 工作流

`wechat-chat-sync` 是运行时中立的微信聊天记录手动同步 workflow。它只描述业务编排和安全边界，具体运行时必须先读取 `agents/capabilities.md`，再把通用能力映射到当前环境。

## 触发入口

以下意图进入本工作流：

- 同步某位候选人的微信聊天记录。
- 指定微信联系人或群名、时间范围，把聊天导出为 markdown。
- 将微信聊天时间线归档到 `data/wechat-timelines/` 并写入 `data/talent.db` 索引。

如果用户没有提供候选人和时间范围，只问一个最小澄清问题。不得默认导出全量聊天。

## 前置检查

1. 读取 `agents/capabilities.md`。
2. 读取 `agents/workflows/talent-library/references/data-contract.md`。
3. 确认主数据源 `data/talent.db` 存在。
4. 确认本机可调用 `wechat-cli export`。
5. 确认用户提供了候选人、微信联系人或群名、起始时间和结束时间。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `agents/workflows/wechat-chat-sync/references/cli-contract.md` | `wechat-cli export` 参数和错误处理 |
| `agents/workflows/wechat-chat-sync/references/timeline-format.md` | markdown 时间线归档格式 |
| `agents/workflows/wechat-chat-sync/assets/timeline-template.md` | 时间线文件头模板 |
| `agents/workflows/talent-library/AGENT.md` | 人才库候选人定位和写库安全规则 |
| `scripts/talent_library.py` | 统一业务入口 |
| `data/wechat-timelines/` | 聊天 markdown 归档目录 |

## 执行流程

1. 用候选人 id 或查询条件定位候选人；命中多条时让用户选择。
2. 展示候选人、微信联系人或群名、起止时间、消息上限和输出目录。
3. 如果用户要求同时更新邮箱、手机号、微信号或微信 id，展示旧值和新值。
4. 调用 `scripts/talent_library.py wechat-sync` 执行导出、归档和索引写入。
5. 输出同步摘要：候选人、聊天名、时间范围、消息数、markdown 路径和索引 id。

## 安全规则

1. 未提供起止时间时不得执行导出。
2. 不在对话中默认展示聊天全文。
3. 不把聊天正文写入 SQLite；SQLite 只保存归档索引。
4. 批量同步多个候选人时必须先展示 dry-run。
5. 删除候选人不隐式删除 markdown 归档文件；删除归档文件必须单独确认。
```

- [ ] **Step 4: Create workflow references and asset**

Create `agents/workflows/wechat-chat-sync/references/cli-contract.md`:

```markdown
# wechat-cli 契约

## 导出命令

```bash
wechat-cli export "<联系人或群名>" --format markdown --output <path> --start-time "YYYY-MM-DD [HH:MM[:SS]]" --end-time "YYYY-MM-DD [HH:MM[:SS]]" --limit <N>
```

## 必填参数

- `CHAT_NAME`：微信联系人名或群名。
- `--format markdown`：第一版固定使用 markdown。
- `--output`：导出到临时文件，再由业务入口写入正式归档文件。
- `--start-time` 和 `--end-time`：必须由用户提供。

## 可选参数

- `--limit`：限制导出消息数。
- `--config`：如用户提供特定配置路径，由运行时透传给 `wechat-cli`。

## 失败处理

- 命令不可用：报告依赖缺失，不写库。
- 返回非零：报告 stderr 摘要，不写索引。
- 输出为空：报告 0 条消息，由用户决定是否重试。
```

Create `agents/workflows/wechat-chat-sync/references/timeline-format.md`:

```markdown
# 微信聊天时间线格式

聊天正文归档到：

```text
data/wechat-timelines/<candidate_id>-<safe-name>-<YYYYMMDDHHMMSS>.md
```

文件由 front matter 和 `wechat-cli export --format markdown` 原始正文组成。

## Front Matter 字段

- `candidate_id`
- `candidate_name`
- `chat_name`
- `chat_identifier`
- `start_time`
- `end_time`
- `source_tool`
- `synced_at`
- `export_command`

## 隐私规则

- 报告默认只展示路径和消息数量。
- 不把正文复制到 `candidate_details.raw_data`。
- 不把手机号、微信号加入全文索引。
```

Create `agents/workflows/wechat-chat-sync/assets/timeline-template.md`:

```markdown
---
candidate_id: <candidate_id>
candidate_name: <candidate_name>
chat_name: <chat_name>
chat_identifier: <chat_identifier>
start_time: <start_time>
end_time: <end_time>
source_tool: wechat-cli
synced_at: <synced_at>
export_command:
  - wechat-cli
  - export
---

<wechat-cli markdown body>
```

- [ ] **Step 5: Create Claude Code adapter**

Create `.claude/skills/wechat-chat-sync/SKILL.md`:

```markdown
---
name: wechat-chat-sync
description: "微信聊天记录手动同步。用于顾问指定候选人、微信联系人或群名、时间范围，通过 wechat-cli 导出 markdown 聊天记录，并把归档索引写回本地人才库。触发词：同步微信聊天、微信聊天记录、wechat sync、聊天时间线。"
---

# Claude Code Adapter: wechat-chat-sync

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/wechat-chat-sync/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/wechat-chat-sync/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
```

- [ ] **Step 6: Add workflow-specific tests**

Create `tests/test_wechat_chat_sync_workflow.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "agents" / "workflows" / "wechat-chat-sync"


def test_wechat_chat_sync_workflow_resources_exist():
    expected = [
        WORKFLOW / "AGENT.md",
        WORKFLOW / "references" / "cli-contract.md",
        WORKFLOW / "references" / "timeline-format.md",
        WORKFLOW / "assets" / "timeline-template.md",
        ROOT / ".claude" / "skills" / "wechat-chat-sync" / "SKILL.md",
    ]

    for path in expected:
        assert path.exists(), f"missing wechat-chat-sync resource: {path}"


def test_wechat_chat_sync_workflow_declares_safety_boundaries():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    cli_contract = (WORKFLOW / "references" / "cli-contract.md").read_text(
        encoding="utf-8"
    )
    timeline_format = (WORKFLOW / "references" / "timeline-format.md").read_text(
        encoding="utf-8"
    )

    assert "不得默认导出全量聊天" in text
    assert "wechat-cli export" in cli_contract
    assert "不把正文复制到 `candidate_details.raw_data`" in timeline_format
```

- [ ] **Step 7: Run workflow architecture tests**

Run:

```bash
python -m pytest tests/test_agent_architecture.py tests/test_wechat_chat_sync_workflow.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit workflow and adapter**

Run:

```bash
git add agents/workflows/wechat-chat-sync .claude/skills/wechat-chat-sync tests/test_agent_architecture.py tests/test_wechat_chat_sync_workflow.py
git commit -m "docs: add wechat chat sync workflow"
```

Expected: commit succeeds.

---

### Task 5: Talent Library Workflow Integration

**Files:**
- Modify: `agents/workflows/talent-library/AGENT.md`
- Modify: `agents/workflows/talent-library/references/data-contract.md`
- Modify: `agents/workflows/talent-library/references/scenarios.md`
- Modify: `agents/workflows/talent-library/references/safety-rules.md`
- Modify: `.claude/skills/talent-library/SKILL.md`
- Modify: `tests/test_talent_library_workflow.py`

- [ ] **Step 1: Write failing workflow integration tests**

Add this test to `tests/test_talent_library_workflow.py`:

```python
def test_talent_library_mentions_contacts_and_wechat_sync():
    agent = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    data_contract = (WORKFLOW / "references" / "data-contract.md").read_text(
        encoding="utf-8"
    )
    scenarios = (WORKFLOW / "references" / "scenarios.md").read_text(encoding="utf-8")
    safety = (WORKFLOW / "references" / "safety-rules.md").read_text(encoding="utf-8")

    for field in ["email", "phone", "wechat", "wechat_id"]:
        assert field in data_contract
        assert field in scenarios
    assert "wechat-chat-sync" in agent
    assert "candidate_wechat_timelines" in data_contract
    assert "TalentDB.add_wechat_timeline" in data_contract
    assert "未提供起止时间时不得执行微信聊天导出" in safety
```

- [ ] **Step 2: Run workflow integration test to verify it fails**

Run:

```bash
python -m pytest tests/test_talent_library_workflow.py::test_talent_library_mentions_contacts_and_wechat_sync -q
```

Expected: FAIL because the workflow docs do not mention the new fields and API.

- [ ] **Step 3: Update `talent-library` AGENT resource index and routes**

In `agents/workflows/talent-library/AGENT.md`, add this row to `资源索引`:

```markdown
| `agents/workflows/wechat-chat-sync/AGENT.md` | 微信聊天记录手动同步、markdown 归档和时间线索引 |
```

Add this row to `场景路由`:

```markdown
| `wechat-sync` | 同步微信聊天记录、归档聊天时间线 | `agents/workflows/wechat-chat-sync/AGENT.md`、`TalentDB.add_wechat_timeline()` |
```

Add this paragraph after the `detail` parameter section:

```markdown
`wechat-sync` 场景由 `agents/workflows/wechat-chat-sync/AGENT.md` 承接。运行时应调用 `scripts/talent_library.py wechat-sync`，并要求用户提供候选人、微信联系人或群名、起始时间和结束时间；不得默认导出全量聊天。
```

- [ ] **Step 4: Update data contract**

In `agents/workflows/talent-library/references/data-contract.md`, add `candidate_wechat_timelines` to the core table list:

```markdown
- `candidate_wechat_timelines`
```

Add this section before `## 核心 TalentDB API`:

```markdown
## 联系方式字段

`candidates` 第一版保留单值联系方式：

| 字段 | 含义 |
| --- | --- |
| `email` | 当前可用邮箱 |
| `phone` | 当前可用手机号 |
| `wechat` | 当前微信号或顾问可识别的微信名片标识 |
| `wechat_id` | 预留微信内部 id 或稳定 id |

联系方式可通过 `TalentDB.update_candidate(candidate_id, patch)` 更新。批量导入时只填补空值，不静默覆盖已有联系方式。

## 微信聊天时间线

微信聊天正文归档到 `data/wechat-timelines/*.md`。SQLite 只在 `candidate_wechat_timelines` 保存索引，包括候选人、微信联系人或群名、起止时间、消息数、归档路径和同步时间。
```

Add this row to the API table:

```markdown
| `TalentDB.add_wechat_timeline(candidate_id, data)` | 写入微信聊天 markdown 归档索引 |
```

- [ ] **Step 5: Update scenarios**

In `agents/workflows/talent-library/references/scenarios.md`, update the `## update：人才更新` first sentence:

```markdown
适用于更新结构化字段、联系方式、补充履历、合并来源、修正综合分、修正 JD 匹配分或处理待确认合并。
```

Add this step after current update step 3:

```markdown
4. 联系方式字段仅支持单值更新：`email`、`phone`、`wechat`、`wechat_id`；更新前展示旧值和新值。
```

Renumber the following steps in that section by one.

Add this new section before `## delete：人才删除`:

```markdown
## wechat-sync：微信聊天时间线同步

适用于顾问已经知道候选人对应微信联系人或群名，并希望把指定时间范围内的聊天记录归档到人才库。

流程：

1. 读取 `agents/workflows/wechat-chat-sync/AGENT.md`。
2. 根据候选人 ID 或查询条件定位候选人；命中多条时先让用户选择。
3. 用户必须提供微信联系人或群名、起始时间和结束时间；缺少时间范围时不执行导出。
4. 如需同时更新 `email`、`phone`、`wechat`、`wechat_id`，先展示旧值和新值。
5. 调用 `scripts/talent_library.py wechat-sync`。
6. 写入后展示候选人、聊天名、时间范围、消息数、markdown 路径和索引 id。
7. 默认不展示聊天全文；如用户要求查看，先提示内容可能包含敏感信息。
```

- [ ] **Step 6: Update safety rules**

Append these rules to `agents/workflows/talent-library/references/safety-rules.md`:

```markdown
11. 未提供起止时间时不得执行微信聊天导出。
12. 微信聊天正文只归档到 markdown 文件；SQLite 只保存索引路径和同步元数据。
13. 聊天同步报告默认不展示聊天全文。
14. 删除候选人不会隐式删除 `data/wechat-timelines/*.md`，删除归档文件必须单独确认。
```

- [ ] **Step 7: Update talent-library adapter description**

In `.claude/skills/talent-library/SKILL.md`, replace the `description` value with:

```yaml
description: "猎头顾问人才库管理。用于人才导入、人才查询、人才匹配、人才综合评分、JD 匹配评分、人才详情抓取、联系方式更新、微信聊天记录同步、人才信息更新、人才删除，以及围绕本地 SQLite 人才库 data/talent.db 的候选人管理任务。触发词: 人才库、候选人库、导入人才、查询人才、匹配人才、人才评分、抓取详情、更新联系方式、同步微信聊天、删除人才、talent library、/talent-library"
```

- [ ] **Step 8: Run workflow integration tests**

Run:

```bash
python -m pytest tests/test_talent_library_workflow.py tests/test_agent_architecture.py tests/test_wechat_chat_sync_workflow.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit workflow integration**

Run:

```bash
git add agents/workflows/talent-library .claude/skills/talent-library tests/test_talent_library_workflow.py
git commit -m "docs: integrate contacts and wechat sync workflow"
```

Expected: commit succeeds.

---

### Task 6: Final Verification And Task Log

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run focused regression suite**

Run:

```bash
python -m pytest tests/test_talent_models.py tests/test_talent_db.py tests/test_talent_library_cli.py tests/test_talent_library_workflow.py tests/test_wechat_chat_sync_workflow.py tests/test_agent_architecture.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full regression suite**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: PASS with the existing warning profile.

- [ ] **Step 3: Run static command smoke checks**

Run:

```bash
python -m py_compile scripts/talent_models.py scripts/talent_db.py scripts/talent_library.py
python scripts/talent_library.py wechat-sync --help
git diff --check
```

Expected:

- `py_compile` exits 0.
- help output includes `--candidate-id`, `--chat-name`, `--start-time`, and `--end-time`.
- `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Update `tasks/todo.md` implementation section**

Append this section to `tasks/todo.md`:

```markdown
---

# 人才库联系方式与微信聊天记录实施（2026-05-12）

> 当前状态：已完成实现与验证。
> 设计文档：`docs/superpowers/specs/2026-05-12-talent-contact-and-wechat-timeline-design.md`
> 实施计划：`docs/superpowers/plans/2026-05-12-talent-contact-and-wechat-timeline.md`

## 任务清单

- [x] Task 1：扩展候选人联系方式模型、SQLite schema、导入合并和更新契约。
- [x] Task 2：新增微信聊天 markdown 归档索引表和 TalentDB API。
- [x] Task 3：新增 `scripts/talent_library.py wechat-sync`，封装 `wechat-cli export`。
- [x] Task 4：新增 `wechat-chat-sync` canonical workflow 和薄适配 skill。
- [x] Task 5：更新 `talent-library` workflow 的联系方式和微信同步契约。
- [x] Task 6：运行聚焦回归、全量测试和静态检查。

## Review

- 聚焦回归记录 Task 6 Step 1 的命令、通过数量和失败数量。
- 全量测试记录 Task 6 Step 2 的命令、通过数量和 warning 数量。
- 静态检查记录 Task 6 Step 3 的 `py_compile`、`wechat-sync --help` 和 `git diff --check` 结果。
- 已知限制记录未覆盖的真实微信环境手工验证范围。
```

Then replace the final review line with actual command results from Steps 1-3.

- [ ] **Step 5: Commit final task log**

Run:

```bash
git add tasks/todo.md
git commit -m "docs: record talent contact implementation results"
```

Expected: commit succeeds.

- [ ] **Step 6: Final status check**

Run:

```bash
git status --short
```

Expected: only pre-existing unrelated files may remain, such as `memory/error-log.md` or SQLite WAL/SHM files. No implementation files should be unstaged.

---

## Self-Review

Spec coverage:

- Contact fields: Task 1 covers model, SQLite schema, update allowlist, ingest fill-only behavior, and JSON schema.
- WeChat markdown archive: Task 3 covers `wechat-cli export`, front matter, message counting, output path, and CLI failure handling.
- SQLite timeline index: Task 2 covers table, dataclass, API, retrieval, and delete cascade count.
- Skill/workflow: Task 4 covers canonical workflow, references, asset, and `.claude` adapter.
- Talent-library integration: Task 5 covers data contract, scenarios, safety rules, and adapter triggers.
- Verification: Task 6 covers focused tests, full suite, compile checks, help smoke, whitespace check, and task log.

Placeholder scan:

- No placeholder markers or vague implementation steps are intentionally left in this plan.
- Each code-changing step includes concrete code or exact text to add.

Type consistency:

- Contact fields use `email`, `phone`, `wechat`, `wechat_id` consistently across dataclass, SQLite columns, update patches, tests, JSON schema, and docs.
- Timeline model and API use `WechatTimeline`, `candidate_wechat_timelines`, `TalentDB.add_wechat_timeline()`, and `TalentDB.get_wechat_timelines()` consistently.
- CLI command is consistently named `wechat-sync`.
