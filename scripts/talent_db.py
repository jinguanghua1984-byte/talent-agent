"""SQLite storage layer for the local talent database."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from scripts.talent_models import Candidate, CandidateDetail, PendingMerge, SourceProfile


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
        skill_tags = data.get("skill_tags")
        data_level = self._data_level_for(data)
        with self._conn:
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
            self._conn.execute(
                """
                INSERT INTO source_profiles (
                    candidate_id, platform, platform_id, profile_url, raw_profile
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    platform,
                    data.get("platform_id"),
                    data.get("profile_url"),
                    _json_dumps(data.get("raw_profile", data)),
                ),
            )
        if any(field in data for field in _DETAIL_FIELDS):
            self.enrich(candidate_id, {field: data.get(field) for field in _DETAIL_FIELDS})
        return candidate_id

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
                new_data=_json_loads(row["new_data"], {}, "pending_merges.new_data"),
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
