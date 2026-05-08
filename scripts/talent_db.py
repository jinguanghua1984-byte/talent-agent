"""SQLite storage layer for the local talent database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    IngestResult,
    PendingMerge,
    SourceProfile,
)


_DETAIL_FIELDS = (
    "work_experience",
    "education_experience",
    "project_experience",
    "raw_data",
    "summary",
)


class TalentDB:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._last_ingest_action: str | None = None
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.OperationalError:
            pass
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT,
                age INTEGER,
                city TEXT,
                work_years INTEGER,
                education TEXT,
                current_company TEXT,
                current_title TEXT,
                expected_salary TEXT,
                expected_city TEXT,
                expected_title TEXT,
                hunting_status TEXT,
                skill_tags TEXT,
                data_level TEXT DEFAULT 'lead',
                overall_score REAL DEFAULT 0,
                score_version INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS candidate_details (
                candidate_id INTEGER PRIMARY KEY REFERENCES candidates(id) ON DELETE CASCADE,
                work_experience TEXT,
                education_experience TEXT,
                project_experience TEXT,
                raw_data TEXT,
                summary TEXT
            );

            CREATE TABLE IF NOT EXISTS source_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                platform TEXT NOT NULL,
                platform_id TEXT,
                profile_url TEXT,
                raw_profile TEXT,
                fetched_at TEXT DEFAULT (datetime('now')),
                UNIQUE(platform, platform_id)
            );

            CREATE TABLE IF NOT EXISTS score_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                old_score REAL,
                new_score REAL,
                trigger_type TEXT NOT NULL,
                trigger_detail TEXT,
                computed_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS match_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                jd_id TEXT NOT NULL,
                match_type TEXT NOT NULL,
                score REAL,
                dimensions TEXT,
                reason TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(candidate_id, jd_id, match_type)
            );

            CREATE TABLE IF NOT EXISTS merge_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survivor_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                merged_id INTEGER,
                match_type TEXT,
                merged_fields TEXT,
                merged_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS pending_merges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                existing_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,
                new_data TEXT NOT NULL,
                match_fields TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now')),
                resolved_at TEXT,
                resolved_by TEXT
            );

            CREATE TABLE IF NOT EXISTS company_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                canonical_name TEXT NOT NULL,
                alias TEXT NOT NULL,
                UNIQUE(canonical_name, alias)
            );

            CREATE INDEX IF NOT EXISTS idx_candidates_company ON candidates(current_company);
            CREATE INDEX IF NOT EXISTS idx_candidates_title ON candidates(current_title);
            CREATE INDEX IF NOT EXISTS idx_candidates_city ON candidates(city);
            CREATE INDEX IF NOT EXISTS idx_candidates_education ON candidates(education);
            CREATE INDEX IF NOT EXISTS idx_candidates_work_years ON candidates(work_years);
            CREATE INDEX IF NOT EXISTS idx_candidates_data_level ON candidates(data_level);
            CREATE INDEX IF NOT EXISTS idx_candidates_score ON candidates(overall_score DESC);
            CREATE UNIQUE INDEX IF NOT EXISTS idx_candidates_identity
                ON candidates(
                    name,
                    COALESCE(current_company, ''),
                    COALESCE(current_title, ''),
                    COALESCE(city, ''),
                    COALESCE(education, '')
                );
            CREATE INDEX IF NOT EXISTS idx_source_platform ON source_profiles(platform);
            CREATE INDEX IF NOT EXISTS idx_source_candidate ON source_profiles(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_match_scores_jd ON match_scores(jd_id);
            CREATE INDEX IF NOT EXISTS idx_match_scores_candidate_jd ON match_scores(candidate_id, jd_id);
            CREATE INDEX IF NOT EXISTS idx_score_events_candidate ON score_events(candidate_id);
            """
        )
        self._init_fts()
        self._init_vectors()
        self._conn.commit()

    def _init_fts(self) -> None:
        self._conn.executescript(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS candidate_fts USING fts5(
                name,
                current_company,
                current_title,
                skill_tags,
                education,
                city,
                content='candidates',
                content_rowid='id'
            );

            CREATE TRIGGER IF NOT EXISTS candidates_ai AFTER INSERT ON candidates BEGIN
                INSERT INTO candidate_fts(
                    rowid, name, current_company, current_title, skill_tags, education, city
                )
                VALUES (
                    new.id, new.name, new.current_company, new.current_title,
                    new.skill_tags, new.education, new.city
                );
            END;

            CREATE TRIGGER IF NOT EXISTS candidates_ad AFTER DELETE ON candidates BEGIN
                INSERT INTO candidate_fts(
                    candidate_fts, rowid, name, current_company, current_title,
                    skill_tags, education, city
                )
                VALUES (
                    'delete', old.id, old.name, old.current_company, old.current_title,
                    old.skill_tags, old.education, old.city
                );
            END;

            CREATE TRIGGER IF NOT EXISTS candidates_au AFTER UPDATE ON candidates BEGIN
                INSERT INTO candidate_fts(
                    candidate_fts, rowid, name, current_company, current_title,
                    skill_tags, education, city
                )
                VALUES (
                    'delete', old.id, old.name, old.current_company, old.current_title,
                    old.skill_tags, old.education, old.city
                );
                INSERT INTO candidate_fts(
                    rowid, name, current_company, current_title, skill_tags, education, city
                )
                VALUES (
                    new.id, new.name, new.current_company, new.current_title,
                    new.skill_tags, new.education, new.city
                );
            END;
            """
        )

    def _init_vectors(self) -> None:
        try:
            self._conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS candidate_vectors USING vec0(
                    candidate_id INTEGER PRIMARY KEY,
                    embedding float[384]
                )
                """
            )
        except sqlite3.OperationalError:
            pass

    def ingest(self, data: dict[str, Any], platform: str) -> int:
        with self._conn:
            candidate_id, action = self._ingest_with_result(data, platform)
            self._last_ingest_action = action
            return candidate_id

    def _ingest_with_result(self, data: dict[str, Any], platform: str) -> tuple[int, str]:
        existing_id = self._find_exact_match(data)
        if existing_id is not None:
            self._merge_candidate(existing_id, data, platform)
            return existing_id, "merged"

        canonical_company = self._canonical_for_alias(data.get("current_company"))
        if canonical_company:
            alias_match_data = {**data, "current_company": canonical_company}
            alias_existing_id = self._find_exact_match(alias_match_data)
            if alias_existing_id is not None:
                new_id = self._insert_candidate(data, platform)
                self._create_pending_merge(
                    existing_id=alias_existing_id,
                    new_id=new_id,
                    data=data,
                    platform=platform,
                    match_fields={
                        "name": "exact",
                        "current_company": {
                            "alias": data.get("current_company"),
                            "canonical": canonical_company,
                        },
                        "current_title": "exact",
                        "city": "exact",
                        "education": "exact",
                    },
                )
                return new_id, "pending"

        candidate_id = self._insert_candidate(data, platform)
        return candidate_id, "created"

    def batch_ingest(
        self, candidates: list[dict[str, Any]], platform: str
    ) -> IngestResult:
        result = IngestResult()
        for index, data in enumerate(candidates):
            try:
                self.ingest(data, platform)
            except Exception as exc:  # noqa: BLE001 - batch import should keep going.
                result.errors += 1
                name = data.get("name", f"#{index}")
                result.error_details.append(f"{name}: {exc}")
                continue

            if self._last_ingest_action == "created":
                result.created += 1
            elif self._last_ingest_action == "merged":
                result.merged += 1
            elif self._last_ingest_action == "pending":
                result.pending += 1
        return result

    def resolve_merge(self, pending_id: int, action: str) -> None:
        if action not in {"merge", "reject"}:
            raise ValueError(f"Unsupported merge action: {action}")

        row = self._conn.execute(
            "SELECT * FROM pending_merges WHERE id = ?", (pending_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Pending merge does not exist: {pending_id}")

        if action == "reject":
            with self._conn:
                self._conn.execute(
                    """
                    UPDATE pending_merges
                    SET status = 'rejected', resolved_at = datetime('now')
                    WHERE id = ?
                    """,
                    (pending_id,),
                )
            return

        pending_data = _json_loads(row["new_data"], {}, "pending_merges.new_data")
        existing_id = int(row["existing_id"])
        new_id = pending_data.get("_candidate_id")
        if new_id is None:
            raise ValueError(f"Pending merge has no new candidate id: {pending_id}")

        new_candidate = self.get(int(new_id))
        if new_candidate is None:
            raise ValueError(f"Pending merge candidate does not exist: {new_id}")

        merge_data = new_candidate.to_dict()
        merge_data.update(_public_ingest_data(pending_data))
        detail = self.get_detail(int(new_id))
        if detail is not None:
            merge_data["detail"] = detail.to_dict()

        with self._conn:
            self._merge_candidate(existing_id, merge_data, pending_data.get("_platform", ""))
            self._move_sources(int(new_id), existing_id)
            self._conn.execute("DELETE FROM candidates WHERE id = ?", (int(new_id),))
            self._conn.execute(
                """
                UPDATE pending_merges
                SET status = 'approved', resolved_at = datetime('now')
                WHERE id = ?
                """,
                (pending_id,),
            )
            self._conn.execute(
                """
                INSERT INTO merge_log(survivor_id, merged_id, match_type, merged_fields)
                VALUES (?, ?, ?, ?)
                """,
                (
                    existing_id,
                    int(new_id),
                    "company_alias",
                    _json_dumps(
                        _json_loads(row["match_fields"], {}, "pending_merges.match_fields")
                    ),
                ),
            )

    def _find_exact_match(self, data: dict[str, Any]) -> int | None:
        row = self._conn.execute(
            """
            SELECT id
            FROM candidates
            WHERE name = ?
              AND COALESCE(current_company, '') = ?
              AND COALESCE(current_title, '') = ?
              AND COALESCE(city, '') = ?
              AND COALESCE(education, '') = ?
            ORDER BY id
            LIMIT 1
            """,
            (
                data["name"],
                _identity_value(data.get("current_company")),
                _identity_value(data.get("current_title")),
                _identity_value(data.get("city")),
                _identity_value(data.get("education")),
            ),
        ).fetchone()
        return int(row["id"]) if row is not None else None

    def _canonical_for_alias(self, company: Any) -> str | None:
        if not company:
            return None
        row = self._conn.execute(
            """
            SELECT canonical_name
            FROM company_aliases
            WHERE alias = ?
            ORDER BY id
            LIMIT 1
            """,
            (company,),
        ).fetchone()
        return row["canonical_name"] if row is not None else None

    def _insert_candidate(self, data: dict[str, Any], platform: str) -> int:
        skill_tags = data.get("skill_tags")
        data_level = self._data_level_for(data)
        cursor = self._conn.execute(
            """
            INSERT INTO candidates (
                name, gender, age, city, work_years, education,
                current_company, current_title, expected_salary,
                expected_city, expected_title, hunting_status,
                skill_tags, data_level
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data.get("gender"),
                data.get("age"),
                data.get("city"),
                data.get("work_years"),
                data.get("education"),
                data.get("current_company"),
                data.get("current_title"),
                data.get("expected_salary"),
                data.get("expected_city"),
                data.get("expected_title"),
                data.get("hunting_status"),
                _json_dumps(skill_tags or []),
                data_level,
            ),
        )
        candidate_id = int(cursor.lastrowid)
        self._add_source_profile(candidate_id, data, platform)
        detail_data = _detail_payload(data)
        if detail_data:
            self._merge_detail(candidate_id, detail_data)
        return candidate_id

    def _merge_candidate(
        self, existing_id: int, data: dict[str, Any], platform: str
    ) -> None:
        row = self._conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (existing_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"Candidate does not exist: {existing_id}")

        existing = dict(row)
        updates: dict[str, Any] = {}
        fill_only_fields = (
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
        )
        for field in fill_only_fields:
            incoming = data.get(field)
            if _is_empty(existing.get(field)) and not _is_empty(incoming):
                updates[field] = incoming

        existing_tags = _json_loads(
            existing.get("skill_tags"), [], "candidates.skill_tags"
        )
        merged_tags = _merge_skill_tags(existing_tags, data.get("skill_tags") or [])
        if merged_tags != existing_tags:
            updates["skill_tags"] = _json_dumps(merged_tags)

        incoming_level = self._data_level_for(data)
        if _data_level_rank(incoming_level) > _data_level_rank(existing.get("data_level")):
            updates["data_level"] = incoming_level

        if updates:
            set_clause = ", ".join(f"{field} = ?" for field in updates)
            self._conn.execute(
                f"""
                UPDATE candidates
                SET {set_clause}, updated_at = datetime('now')
                WHERE id = ?
                """,
                (*updates.values(), existing_id),
            )
        else:
            self._conn.execute(
                "UPDATE candidates SET updated_at = datetime('now') WHERE id = ?",
                (existing_id,),
            )

        if platform:
            self._add_source_profile(existing_id, data, platform)
        detail_data = _detail_payload(data)
        if detail_data:
            self._merge_detail(existing_id, detail_data)

    def _add_source_profile(
        self, candidate_id: int, data: dict[str, Any], platform: str
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO source_profiles (
                candidate_id, platform, platform_id, profile_url, raw_profile
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(platform, platform_id) DO UPDATE SET
                profile_url = COALESCE(excluded.profile_url, source_profiles.profile_url),
                raw_profile = COALESCE(excluded.raw_profile, source_profiles.raw_profile),
                fetched_at = datetime('now')
            """,
            (
                candidate_id,
                platform,
                data.get("platform_id"),
                data.get("profile_url"),
                _json_dumps(data.get("raw_profile", _public_ingest_data(data))),
            ),
        )

    def _merge_detail(self, candidate_id: int, detail_data: dict[str, Any]) -> None:
        existing = self.get_detail(candidate_id)
        existing_data = existing.to_dict() if existing is not None else {}
        merged: dict[str, Any] = {}
        for field in _DETAIL_FIELDS:
            incoming = detail_data.get(field)
            current = existing_data.get(field)
            merged[field] = (
                incoming if _is_empty(current) and not _is_empty(incoming) else current
            )

        self.enrich(candidate_id, merged)

    def _create_pending_merge(
        self,
        existing_id: int,
        new_id: int,
        data: dict[str, Any],
        platform: str,
        match_fields: dict[str, Any],
    ) -> None:
        pending_data = {**data, "_candidate_id": new_id, "_platform": platform}
        self._conn.execute(
            """
            INSERT INTO pending_merges(existing_id, new_data, match_fields, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (existing_id, _json_dumps(pending_data), _json_dumps(match_fields)),
        )

    def _move_sources(self, from_candidate_id: int, to_candidate_id: int) -> None:
        rows = self._conn.execute(
            """
            SELECT id, platform, platform_id, profile_url, raw_profile
            FROM source_profiles
            WHERE candidate_id = ?
            ORDER BY id
            """,
            (from_candidate_id,),
        ).fetchall()
        for row in rows:
            try:
                self._conn.execute(
                    "UPDATE source_profiles SET candidate_id = ? WHERE id = ?",
                    (to_candidate_id, row["id"]),
                )
            except sqlite3.IntegrityError:
                self._conn.execute(
                    "DELETE FROM source_profiles WHERE id = ?", (row["id"],)
                )

    def get(self, candidate_id: int) -> Candidate | None:
        row = self._conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        data["skill_tags"] = _json_loads(data.get("skill_tags"), [], "candidates.skill_tags")
        return Candidate.from_dict(data)

    def get_detail(self, candidate_id: int) -> CandidateDetail | None:
        row = self._conn.execute(
            "SELECT * FROM candidate_details WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        if row is None:
            return None
        data = dict(row)
        for field in ("work_experience", "education_experience", "project_experience"):
            data[field] = _json_loads(data.get(field), None, f"candidate_details.{field}")
        data["raw_data"] = _json_loads(data.get("raw_data"), None, "candidate_details.raw_data")
        return CandidateDetail.from_dict(data)

    def get_sources(self, candidate_id: int) -> list[SourceProfile]:
        rows = self._conn.execute(
            """
            SELECT * FROM source_profiles
            WHERE candidate_id = ?
            ORDER BY id
            """,
            (candidate_id,),
        ).fetchall()
        return [
            SourceProfile(
                id=row["id"],
                candidate_id=row["candidate_id"],
                platform=row["platform"],
                platform_id=row["platform_id"],
                profile_url=row["profile_url"],
                raw_profile=_json_loads(row["raw_profile"], None, "source_profiles.raw_profile"),
                fetched_at=row["fetched_at"],
            )
            for row in rows
        ]

    def enrich(self, candidate_id: int, detail_data: dict[str, Any]) -> None:
        values = {field: detail_data.get(field) for field in _DETAIL_FIELDS}
        work_experience = values.get("work_experience")
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO candidate_details (
                    candidate_id, work_experience, education_experience,
                    project_experience, raw_data, summary
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                    work_experience = excluded.work_experience,
                    education_experience = excluded.education_experience,
                    project_experience = excluded.project_experience,
                    raw_data = excluded.raw_data,
                    summary = excluded.summary
                """,
                (
                    candidate_id,
                    _json_dumps(values["work_experience"]),
                    _json_dumps(values["education_experience"]),
                    _json_dumps(values["project_experience"]),
                    _json_dumps(values["raw_data"]),
                    values["summary"],
                ),
            )
            if work_experience:
                self._conn.execute(
                    """
                    UPDATE candidates
                    SET data_level = 'detailed', updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (candidate_id,),
                )
            else:
                self._conn.execute(
                    "UPDATE candidates SET updated_at = datetime('now') WHERE id = ?",
                    (candidate_id,),
                )

    def add_company_alias(self, canonical: str, alias: str) -> None:
        with self._conn:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO company_aliases(canonical_name, alias)
                VALUES (?, ?)
                """,
                (canonical, alias),
            )

    def pending_merges(self) -> list[PendingMerge]:
        rows = self._conn.execute(
            """
            SELECT * FROM pending_merges
            WHERE status = 'pending'
            ORDER BY id
            """
        ).fetchall()
        return [
            PendingMerge(
                id=row["id"],
                existing_id=row["existing_id"],
                new_data=_public_ingest_data(
                    _json_loads(row["new_data"], {}, "pending_merges.new_data")
                ),
                match_fields=_json_loads(
                    row["match_fields"], None, "pending_merges.match_fields"
                ),
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    @staticmethod
    def _data_level_for(data: dict[str, Any]) -> str:
        if data.get("work_experience"):
            return "detailed"
        if data.get("skill_tags") or data.get("education") or data.get("work_years") is not None:
            return "core"
        return "lead"


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_loads(value: str | None, default: Any, field_name: str) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in TalentDB field {field_name}") from exc


def _identity_value(value: Any) -> str:
    return "" if value is None else str(value)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _merge_skill_tags(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for tag in [*existing, *incoming]:
        if tag in seen:
            continue
        seen.add(tag)
        merged.append(tag)
    return merged


def _detail_payload(data: dict[str, Any]) -> dict[str, Any]:
    detail: dict[str, Any] = {}
    nested = data.get("detail")
    if isinstance(nested, dict):
        detail.update({field: nested.get(field) for field in _DETAIL_FIELDS if field in nested})
    detail.update({field: data.get(field) for field in _DETAIL_FIELDS if field in data})
    return {field: value for field, value in detail.items() if not _is_empty(value)}


def _public_ingest_data(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if not key.startswith("_")}


def _data_level_rank(value: str | None) -> int:
    return {"lead": 0, "core": 1, "detailed": 2}.get(value or "lead", 0)
