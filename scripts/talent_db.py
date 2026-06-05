"""SQLite storage layer for the local talent database."""

from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from scripts.talent_sync_models import canonical_json
from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFieldValue,
    CandidateFilter,
    CandidateIdentityMatch,
    DeleteResult,
    IngestResult,
    MatchScore,
    PageResult,
    PendingMerge,
    SearchHit,
    SortSpec,
    SourceProfile,
    VectorHit,
    WechatTimeline,
)


_DETAIL_FIELDS = (
    "work_experience",
    "education_experience",
    "project_experience",
    "raw_data",
    "summary",
)
_EXPERIENCE_FIELDS = (
    "work_experience",
    "education_experience",
    "project_experience",
)
_VECTOR_DIMENSIONS = 384
_VECTOR_BYTES = _VECTOR_DIMENSIONS * 4
_SORT_FIELDS = {
    "overall_score": "candidates.overall_score",
    "updated_at": "candidates.updated_at",
    "work_years": "candidates.work_years",
    "age": "candidates.age",
    "created_at": "candidates.created_at",
    "name": "candidates.name",
}
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
    "email",
    "phone",
    "wechat",
    "wechat_id",
    "skill_tags",
    "data_level",
}
_CANDIDATE_FILL_ONLY_FIELDS = (
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
    "email",
    "phone",
    "wechat",
    "wechat_id",
)
_SYNC_IMPORT_TABLES = (
    "candidates",
    "candidate_details",
    "source_profiles",
    "candidate_identity_matches",
    "candidate_field_values",
    "candidate_wechat_timelines",
    "score_events",
    "match_scores",
    "tombstones",
)


class TalentDB:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._last_ingest_action: str | None = None
        self._sqlite_vec: Any | None = None
        self._vec_available = self._load_vec_extension()
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
                email TEXT,
                phone TEXT,
                wechat TEXT,
                wechat_id TEXT,
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

            CREATE TABLE IF NOT EXISTS candidate_identity_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER REFERENCES candidates(id) ON DELETE SET NULL,
                source_platform TEXT NOT NULL,
                source_candidate_key TEXT NOT NULL,
                target_platform TEXT NOT NULL,
                target_platform_id TEXT,
                target_profile_url TEXT,
                query_text TEXT NOT NULL,
                query_level TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0,
                score_breakdown TEXT NOT NULL DEFAULT '{}',
                match_status TEXT NOT NULL,
                decision_reason TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS candidate_field_values (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
                field_name TEXT NOT NULL,
                platform TEXT NOT NULL,
                source_profile_id INTEGER REFERENCES source_profiles(id) ON DELETE SET NULL,
                field_value TEXT NOT NULL,
                confidence REAL,
                merge_decision TEXT,
                decision_reason TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

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

            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sync_entity_aliases (
                entity_type TEXT NOT NULL,
                remote_sync_id TEXT NOT NULL,
                local_sync_id TEXT NOT NULL,
                source_node_id TEXT NOT NULL,
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
            CREATE INDEX IF NOT EXISTS idx_identity_matches_candidate
                ON candidate_identity_matches(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_identity_matches_source
                ON candidate_identity_matches(source_platform, source_candidate_key);
            CREATE INDEX IF NOT EXISTS idx_identity_matches_target
                ON candidate_identity_matches(target_platform, target_platform_id);
            CREATE INDEX IF NOT EXISTS idx_identity_matches_status
                ON candidate_identity_matches(match_status);
            CREATE INDEX IF NOT EXISTS idx_field_values_candidate
                ON candidate_field_values(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_field_values_field
                ON candidate_field_values(field_name);
            CREATE INDEX IF NOT EXISTS idx_field_values_platform
                ON candidate_field_values(platform);
            CREATE INDEX IF NOT EXISTS idx_field_values_source_profile
                ON candidate_field_values(source_profile_id);
            CREATE INDEX IF NOT EXISTS idx_wechat_timelines_candidate
                ON candidate_wechat_timelines(candidate_id);
            CREATE INDEX IF NOT EXISTS idx_wechat_timelines_chat_name
                ON candidate_wechat_timelines(chat_name);
            CREATE INDEX IF NOT EXISTS idx_match_scores_jd ON match_scores(jd_id);
            CREATE INDEX IF NOT EXISTS idx_match_scores_candidate_jd ON match_scores(candidate_id, jd_id);
            CREATE INDEX IF NOT EXISTS idx_score_events_candidate ON score_events(candidate_id);
            """
        )
        self._ensure_candidate_contact_columns()
        self._ensure_sync_schema()
        self._init_fts()
        self._init_vectors()
        self._conn.commit()

    def _load_vec_extension(self) -> bool:
        try:
            import sqlite_vec

            self._conn.enable_load_extension(True)
            try:
                sqlite_vec.load(self._conn)
            finally:
                self._conn.enable_load_extension(False)
        except (ImportError, AttributeError, sqlite3.Error):
            self._sqlite_vec = None
            return False

        self._sqlite_vec = sqlite_vec
        return True

    def _ensure_candidate_contact_columns(self) -> None:
        existing = _table_columns(self._conn, "candidates")
        for column in ("email", "phone", "wechat", "wechat_id"):
            if column not in existing:
                self._conn.execute(f"ALTER TABLE candidates ADD COLUMN {column} TEXT")

    def _ensure_sync_schema(self) -> None:
        self._ensure_columns(
            "candidates",
            {
                "sync_id": "TEXT",
                "sync_origin_node_id": "TEXT",
                "sync_updated_at": "TEXT",
            },
        )
        self._ensure_columns("candidate_details", {"sync_id": "TEXT"})
        self._ensure_columns("source_profiles", {"sync_id": "TEXT"})
        self._ensure_columns("candidate_identity_matches", {"sync_id": "TEXT"})
        self._ensure_columns("candidate_field_values", {"sync_id": "TEXT"})
        self._ensure_columns("candidate_wechat_timelines", {"sync_id": "TEXT"})
        self._ensure_columns("score_events", {"sync_id": "TEXT"})
        self._ensure_columns("match_scores", {"sync_id": "TEXT"})
        self._ensure_sync_indexes()
        self._ensure_node_id()
        self._backfill_sync_ids()

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        existing = _table_columns(self._conn, table)
        for column, definition in columns.items():
            if column not in existing:
                self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _ensure_sync_indexes(self) -> None:
        self._conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_sync_id ON candidates(sync_id);
            CREATE INDEX IF NOT EXISTS idx_candidate_details_sync_id ON candidate_details(sync_id);
            CREATE INDEX IF NOT EXISTS idx_source_profiles_sync_id ON source_profiles(sync_id);
            CREATE INDEX IF NOT EXISTS idx_candidate_identity_matches_sync_id
                ON candidate_identity_matches(sync_id);
            CREATE INDEX IF NOT EXISTS idx_candidate_field_values_sync_id
                ON candidate_field_values(sync_id);
            CREATE INDEX IF NOT EXISTS idx_wechat_timelines_sync_id ON candidate_wechat_timelines(sync_id);
            CREATE INDEX IF NOT EXISTS idx_score_events_sync_id ON score_events(sync_id);
            CREATE INDEX IF NOT EXISTS idx_match_scores_sync_id ON match_scores(sync_id);
            """
        )

    def _ensure_node_id(self) -> None:
        self._conn.execute(
            """
            INSERT OR IGNORE INTO sync_meta(key, value)
            VALUES ('node_id', ?)
            """,
            (str(uuid.uuid4()),),
        )

    def _node_id(self) -> str:
        row = self._conn.execute(
            "SELECT value FROM sync_meta WHERE key = 'node_id'"
        ).fetchone()
        if row is not None:
            return str(row["value"])

        node_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO sync_meta(key, value)
            VALUES ('node_id', ?)
            """,
            (node_id,),
        )
        return node_id

    def _new_sync_id(self, entity_type: str) -> str:
        return f"{entity_type}:{uuid.uuid4()}"

    def _ensure_candidate_sync_id(self, candidate_id: int) -> None:
        self._conn.execute(
            """
            UPDATE candidates
            SET sync_id = COALESCE(NULLIF(sync_id, ''), ?),
                sync_origin_node_id = COALESCE(NULLIF(sync_origin_node_id, ''), ?),
                sync_updated_at = COALESCE(NULLIF(sync_updated_at, ''), datetime('now'))
            WHERE id = ?
            """,
            (self._new_sync_id("candidate"), self._node_id(), candidate_id),
        )

    def _backfill_sync_ids(self) -> None:
        entity_tables = (
            ("candidate_details", "candidate_id", "detail"),
            ("source_profiles", "id", "source_profile"),
            ("candidate_identity_matches", "id", "identity_match"),
            ("candidate_field_values", "id", "field_value"),
            ("candidate_wechat_timelines", "id", "wechat_timeline"),
            ("score_events", "id", "score_event"),
            ("match_scores", "id", "match_score"),
        )

        candidate_rows = self._conn.execute(
            """
            SELECT id
            FROM candidates
            WHERE sync_id IS NULL OR sync_id = ''
               OR sync_origin_node_id IS NULL OR sync_origin_node_id = ''
               OR sync_updated_at IS NULL OR sync_updated_at = ''
            """
        ).fetchall()
        for row in candidate_rows:
            self._ensure_candidate_sync_id(int(row["id"]))

        for table, key_column, prefix in entity_tables:
            rows = self._conn.execute(
                f"""
                SELECT {key_column} AS row_id
                FROM {table}
                WHERE sync_id IS NULL OR sync_id = ''
                """
            ).fetchall()
            for row in rows:
                self._conn.execute(
                    f"""
                    UPDATE {table}
                    SET sync_id = ?
                    WHERE {key_column} = ?
                    """,
                    (self._new_sync_id(prefix), row["row_id"]),
                )

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
        self._conn.execute("INSERT INTO candidate_fts(candidate_fts) VALUES('rebuild')")

    def _init_vectors(self) -> None:
        if not self._vec_available:
            return
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
            self._vec_available = False

    def save_embedding(self, candidate_id: int, embedding: bytes | list[float]) -> None:
        if not self._vec_available:
            raise NotImplementedError("sqlite-vec extension is not available")

        row = self._conn.execute(
            "SELECT id FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        embedding_value = self._serialize_embedding(embedding)
        with self._conn:
            self._conn.execute(
                "DELETE FROM candidate_vectors WHERE candidate_id = ?",
                (candidate_id,),
            )
            self._conn.execute(
                """
                INSERT INTO candidate_vectors(candidate_id, embedding)
                VALUES (?, ?)
                """,
                (candidate_id, embedding_value),
            )

    def vector_search(
        self, query_vector: bytes | list[float], limit: int = 20
    ) -> list[VectorHit]:
        if not _is_positive_int(limit):
            raise ValueError("limit must be a positive integer")
        if not self._vec_available:
            raise NotImplementedError("sqlite-vec extension is not available")

        query_value = self._serialize_embedding(query_vector)
        count = self._conn.execute("SELECT COUNT(*) FROM candidate_vectors").fetchone()[0]
        if count == 0:
            return []

        rows = self._conn.execute(
            """
            SELECT
                nearest.candidate_id AS id,
                nearest.distance,
                candidates.name,
                candidates.current_company,
                candidates.current_title
            FROM (
                SELECT candidate_id, distance
                FROM candidate_vectors
                WHERE embedding MATCH ? AND k = ?
                ORDER BY distance
            ) AS nearest
            JOIN candidates ON candidates.id = nearest.candidate_id
            """,
            (query_value, limit),
        ).fetchall()
        return [
            VectorHit(
                id=int(row["id"]),
                similarity=1.0 / (1.0 + float(row["distance"])),
                name=row["name"],
                current_company=row["current_company"],
                current_title=row["current_title"],
            )
            for row in rows
        ]

    def _serialize_embedding(self, embedding: bytes | list[float]) -> bytes:
        if isinstance(embedding, bytes):
            if len(embedding) != _VECTOR_BYTES:
                raise ValueError(
                    f"embedding bytes must be {_VECTOR_BYTES} bytes "
                    f"for {_VECTOR_DIMENSIONS} float32 dimensions"
                )
            return embedding
        if not isinstance(embedding, list):
            raise TypeError("embedding must be bytes or list[float]")
        if len(embedding) != _VECTOR_DIMENSIONS:
            raise ValueError(
                f"embedding list must contain {_VECTOR_DIMENSIONS} dimensions"
            )
        for value in embedding:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError("embedding list values must be int or float")
        if self._sqlite_vec is None:
            raise NotImplementedError("sqlite-vec extension is not available")
        return self._sqlite_vec.serialize_float32([float(value) for value in embedding])

    def ingest(self, data: dict[str, Any], platform: str) -> int:
        with self._conn:
            candidate_id, action = self._ingest_with_result(data, platform)
            self._last_ingest_action = action
            return candidate_id

    def _ingest_with_result(self, data: dict[str, Any], platform: str) -> tuple[int, str]:
        source_candidate_id = self._candidate_id_for_source(data, platform)
        if source_candidate_id is not None:
            self._merge_candidate(source_candidate_id, data, platform)
            return source_candidate_id, "merged"

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
        if row["status"] != "pending":
            raise ValueError(f"Pending merge is already resolved: {pending_id}")

        with self._conn:
            if action == "reject":
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

    def _candidate_id_for_source(self, data: dict[str, Any], platform: str) -> int | None:
        platform_id = data.get("platform_id")
        if not platform_id:
            return None
        row = self._conn.execute(
            """
            SELECT candidate_id
            FROM source_profiles
            WHERE platform = ? AND platform_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (platform, platform_id),
        ).fetchone()
        return int(row["candidate_id"]) if row is not None else None

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
                email, phone, wechat, wechat_id,
                skill_tags, data_level,
                sync_id, sync_origin_node_id, sync_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
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
                data.get("email"),
                data.get("phone"),
                data.get("wechat"),
                data.get("wechat_id"),
                _json_dumps(skill_tags or []),
                data_level,
                self._new_sync_id("candidate"),
                self._node_id(),
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
        for field in _CANDIDATE_FILL_ONLY_FIELDS:
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
        platform_id = data.get("platform_id") or None
        profile_url = data.get("profile_url") or None
        raw_profile = _json_dumps(data.get("raw_profile", _public_ingest_data(data)))
        if platform_id is None:
            existing_source_id = self._find_source_without_platform_id(
                candidate_id, platform, profile_url
            )
            if existing_source_id is not None:
                self._conn.execute(
                    """
                    UPDATE source_profiles
                    SET profile_url = COALESCE(?, profile_url),
                        raw_profile = COALESCE(?, raw_profile),
                        sync_id = COALESCE(NULLIF(sync_id, ''), ?),
                        fetched_at = datetime('now')
                    WHERE id = ?
                    """,
                    (
                        profile_url,
                        raw_profile,
                        self._new_sync_id("source_profile"),
                        existing_source_id,
                    ),
                )
                return

        self._conn.execute(
            """
            INSERT INTO source_profiles (
                candidate_id, platform, platform_id, profile_url, raw_profile, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, platform_id) DO UPDATE SET
                profile_url = COALESCE(excluded.profile_url, source_profiles.profile_url),
                raw_profile = COALESCE(excluded.raw_profile, source_profiles.raw_profile),
                sync_id = COALESCE(NULLIF(source_profiles.sync_id, ''), excluded.sync_id),
                fetched_at = datetime('now')
            """,
            (
                candidate_id,
                platform,
                platform_id,
                profile_url,
                raw_profile,
                self._new_sync_id("source_profile"),
            ),
        )

    def _find_source_without_platform_id(
        self, candidate_id: int, platform: str, profile_url: str | None
    ) -> int | None:
        if profile_url:
            row = self._conn.execute(
                """
                SELECT id
                FROM source_profiles
                WHERE candidate_id = ?
                  AND platform = ?
                  AND platform_id IS NULL
                  AND profile_url = ?
                ORDER BY id
                LIMIT 1
                """,
                (candidate_id, platform, profile_url),
            ).fetchone()
        else:
            row = self._conn.execute(
                """
                SELECT id
                FROM source_profiles
                WHERE candidate_id = ?
                  AND platform = ?
                  AND platform_id IS NULL
                  AND (profile_url IS NULL OR profile_url = '')
                ORDER BY id
                LIMIT 1
                """,
                (candidate_id, platform),
            ).fetchone()
        return int(row["id"]) if row is not None else None

    def _merge_detail(self, candidate_id: int, detail_data: dict[str, Any]) -> None:
        existing = self.get_detail(candidate_id)
        existing_data = existing.to_dict() if existing is not None else {}
        merged: dict[str, Any] = {}
        for field in _DETAIL_FIELDS:
            incoming = detail_data.get(field)
            current = existing_data.get(field)
            if field in _EXPERIENCE_FIELDS:
                merged[field] = _merge_detail_list(current, incoming)
            else:
                merged[field] = (
                    incoming if _is_empty(current) and not _is_empty(incoming) else current
                )

        self._enrich_no_commit(candidate_id, merged)

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

    def merge_candidate_source(
        self,
        candidate_id: int,
        data: dict[str, Any],
        platform: str,
    ) -> None:
        with self._conn:
            self._merge_candidate(candidate_id, data, platform)
            self._last_ingest_action = "merged"

    def record_identity_match(self, data: dict[str, Any]) -> int:
        candidate_id = data.get("candidate_id")
        if candidate_id is not None and not self._candidate_exists(int(candidate_id)):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        _validate_non_empty_string(data.get("source_platform"), "source_platform")
        _validate_non_empty_string(
            data.get("source_candidate_key"),
            "source_candidate_key",
        )
        _validate_non_empty_string(data.get("target_platform"), "target_platform")
        _validate_non_empty_string(data.get("query_text"), "query_text")
        _validate_non_empty_string(data.get("query_level"), "query_level")
        _validate_non_empty_string(data.get("match_status"), "match_status")
        _validate_optional_number(data.get("confidence"), "confidence")
        score_breakdown = _score_breakdown_json(data.get("score_breakdown"))

        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO candidate_identity_matches (
                    candidate_id, source_platform, source_candidate_key,
                    target_platform, target_platform_id, target_profile_url,
                    query_text, query_level, confidence, score_breakdown,
                    match_status, decision_reason, confirmed_by, confirmed_at,
                    sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(candidate_id) if candidate_id is not None else None,
                    data["source_platform"],
                    data["source_candidate_key"],
                    data["target_platform"],
                    data.get("target_platform_id"),
                    data.get("target_profile_url"),
                    data["query_text"],
                    data["query_level"],
                    data.get("confidence") if data.get("confidence") is not None else 0,
                    score_breakdown,
                    data["match_status"],
                    data.get("decision_reason"),
                    data.get("confirmed_by"),
                    data.get("confirmed_at"),
                    self._new_sync_id("identity_match"),
                ),
            )
        return int(cursor.lastrowid)

    def identity_matches(
        self,
        candidate_id: int | None = None,
    ) -> list[CandidateIdentityMatch]:
        if candidate_id is None:
            rows = self._conn.execute(
                """
                SELECT *
                FROM candidate_identity_matches
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT *
                FROM candidate_identity_matches
                WHERE candidate_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (candidate_id,),
            ).fetchall()
        return [_row_to_identity_match(row) for row in rows]

    def record_field_value(self, data: dict[str, Any]) -> int:
        if "candidate_id" not in data or data.get("candidate_id") is None:
            raise ValueError("candidate_id is required")
        candidate_id = int(data["candidate_id"])
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")
        _validate_non_empty_string(data.get("field_name"), "field_name")
        _validate_non_empty_string(data.get("platform"), "platform")
        if "field_value" not in data:
            raise ValueError("field_value is required")
        _validate_optional_number(data.get("confidence"), "confidence")
        source_profile_id = _optional_int(
            data.get("source_profile_id"),
            "source_profile_id",
        )
        if source_profile_id is not None and not self._source_profile_id_exists(
            source_profile_id
        ):
            raise ValueError(f"Source profile does not exist: {source_profile_id}")

        with self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO candidate_field_values (
                    candidate_id, field_name, platform, source_profile_id,
                    field_value, confidence, merge_decision, decision_reason,
                    sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    data["field_name"],
                    data["platform"],
                    source_profile_id,
                    _json_dumps_literal(data.get("field_value")),
                    data.get("confidence"),
                    data.get("merge_decision"),
                    data.get("decision_reason"),
                    self._new_sync_id("field_value"),
                ),
            )
        return int(cursor.lastrowid)

    def field_values(
        self,
        candidate_id: int | None = None,
    ) -> list[CandidateFieldValue]:
        if candidate_id is None:
            rows = self._conn.execute(
                """
                SELECT *
                FROM candidate_field_values
                ORDER BY created_at ASC, id ASC
                """
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT *
                FROM candidate_field_values
                WHERE candidate_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (candidate_id,),
            ).fetchall()
        return [_row_to_field_value(row) for row in rows]

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
                    end_time, message_count, markdown_path, source_tool, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    self._new_sync_id("wechat_timeline"),
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

    def delete_candidate(self, candidate_id: int) -> DeleteResult:
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        details_deleted = _count_rows(
            self._conn, "candidate_details", "candidate_id", candidate_id
        )
        sources_deleted = _count_rows(
            self._conn, "source_profiles", "candidate_id", candidate_id
        )
        timelines_deleted = _count_rows(
            self._conn, "candidate_wechat_timelines", "candidate_id", candidate_id
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
            self._ensure_candidate_sync_id(candidate_id)
            row = self._conn.execute(
                "SELECT sync_id FROM candidates WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            sync_id = str(row["sync_id"]) if row is not None else ""
            if not sync_id:
                raise ValueError(f"Candidate does not exist: {candidate_id}")

            self._conn.execute(
                """
                INSERT INTO sync_tombstones(
                    entity_type, entity_sync_id, source_node_id, reason
                )
                VALUES ('candidate', ?, ?, 'local_delete')
                ON CONFLICT(entity_type, entity_sync_id) DO UPDATE SET
                    deleted_at = excluded.deleted_at,
                    source_node_id = excluded.source_node_id,
                    reason = excluded.reason
                """,
                (sync_id, self._node_id()),
            )
            if self._vec_available:
                self._conn.execute(
                    "DELETE FROM candidate_vectors WHERE candidate_id = ?",
                    (candidate_id,),
                )
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
            timelines_deleted=timelines_deleted,
        )

    def update_overall_score(
        self,
        candidate_id: int,
        score: float,
        trigger: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        _validate_score(score)
        _validate_non_empty_string(trigger, "trigger")
        new_score = float(score)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                """
                SELECT overall_score
                FROM candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Candidate does not exist: {candidate_id}")

            self._conn.execute(
                """
                UPDATE candidates
                SET overall_score = ?,
                    score_version = score_version + 1,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (new_score, candidate_id),
            )
            self._conn.execute(
                """
                INSERT INTO score_events(
                    candidate_id, old_score, new_score, trigger_type, trigger_detail,
                    sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    float(row["overall_score"]),
                    new_score,
                    trigger,
                    _json_dumps(detail),
                    self._new_sync_id("score_event"),
                ),
            )
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()

    def save_match_score(
        self,
        candidate_id: int,
        jd_id: str,
        match_type: str,
        score: float,
        dimensions: dict[str, Any] | None = None,
        reason: str | None = None,
    ) -> None:
        _validate_non_empty_string(jd_id, "jd_id")
        _validate_non_empty_string(match_type, "match_type")
        _validate_score(score)
        if not self._candidate_exists(candidate_id):
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        with self._conn:
            self._conn.execute(
                """
                INSERT INTO match_scores(
                    candidate_id, jd_id, match_type, score, dimensions, reason, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id, jd_id, match_type) DO UPDATE SET
                    score = excluded.score,
                    dimensions = excluded.dimensions,
                    reason = excluded.reason,
                    sync_id = COALESCE(NULLIF(match_scores.sync_id, ''), excluded.sync_id)
                """,
                (
                    candidate_id,
                    jd_id,
                    match_type,
                    float(score),
                    _json_dumps(dimensions),
                    reason,
                    self._new_sync_id("match_score"),
                ),
            )

    def get_match_scores(
        self,
        jd_id: str,
        match_type: str | None = None,
    ) -> list[MatchScore]:
        _validate_non_empty_string(jd_id, "jd_id")
        if match_type is not None:
            _validate_non_empty_string(match_type, "match_type")
            rows = self._conn.execute(
                """
                SELECT *
                FROM match_scores
                WHERE jd_id = ? AND match_type = ?
                ORDER BY score DESC, id ASC
                """,
                (jd_id, match_type),
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT *
                FROM match_scores
                WHERE jd_id = ?
                ORDER BY score DESC, id ASC
                """,
                (jd_id,),
            ).fetchall()

        return [_match_score_from_row(row) for row in rows]

    def get_top_candidates(self, jd_id: str, top_n: int = 10) -> list[Candidate]:
        _validate_non_empty_string(jd_id, "jd_id")
        if not _is_positive_int(top_n):
            raise ValueError("top_n must be a positive integer")

        rows = self._conn.execute(
            """
            SELECT candidates.*
            FROM match_scores
            JOIN candidates ON candidates.id = match_scores.candidate_id
            WHERE match_scores.jd_id = ?
              AND match_scores.match_type = 'final'
            ORDER BY match_scores.score DESC, candidates.id ASC
            LIMIT ?
            """,
            (jd_id, top_n),
        ).fetchall()
        return [_candidate_from_row(row) for row in rows]

    def apply_sync_import(
        self,
        manifest: dict[str, Any],
        table_rows: dict[str, list[dict[str, Any]]],
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        summary = _new_sync_import_summary(manifest, table_rows)
        candidate_id_map: dict[str, int] = {}
        source_profile_id_map: dict[str, int] = {}
        candidate_actions = plan.get("_candidate_actions", {})

        with self._conn:
            if not self._reserve_sync_import(manifest):
                return _already_imported_sync_import_summary(manifest, table_rows)

            self._apply_sync_tombstones(table_rows.get("tombstones", []), summary)
            tombstoned_candidate_sync_ids = (
                _candidate_tombstone_sync_ids(table_rows)
                | _local_candidate_tombstone_sync_ids(self._conn)
            )

            for row in table_rows.get("candidates", []):
                sync_id = str(row.get("sync_id") or "")
                if sync_id in tombstoned_candidate_sync_ids:
                    summary["skipped"]["candidates"] += 1
                    continue

                action = candidate_actions.get(sync_id, {})
                action_name = action.get("action")
                if action_name == "create":
                    candidate_id_map[sync_id] = self._insert_sync_candidate(row, manifest)
                    summary["created"]["candidates"] += 1
                elif action_name == "merge":
                    local_candidate_id = int(action["local_candidate_id"])
                    conflict_count = self._merge_sync_candidate(
                        local_candidate_id,
                        row,
                        manifest,
                    )
                    candidate_id_map[sync_id] = local_candidate_id
                    summary["merged"]["candidates"] += 1
                    summary["conflicts"]["candidates"] += conflict_count
                    local_sync_id = str(action.get("local_sync_id") or "")
                    if local_sync_id and local_sync_id != sync_id:
                        self._upsert_sync_alias(
                            "candidate",
                            sync_id,
                            local_sync_id,
                            str(manifest.get("source_node_id") or ""),
                        )
                elif action_name == "conflict":
                    summary["conflicts"]["candidates"] = (
                        summary["conflicts"].get("candidates", 0) + 1
                    )
                else:
                    summary["skipped"]["candidates"] += 1

            self._import_sync_candidate_details(
                table_rows.get("candidate_details", []),
                candidate_id_map,
                summary,
                manifest,
            )
            self._import_sync_source_profiles(
                table_rows.get("source_profiles", []),
                candidate_id_map,
                source_profile_id_map,
                summary,
            )
            self._import_sync_identity_matches(
                table_rows.get("candidate_identity_matches", []),
                candidate_id_map,
                summary,
            )
            self._import_sync_field_values(
                table_rows.get("candidate_field_values", []),
                candidate_id_map,
                source_profile_id_map,
                summary,
            )
            self._import_sync_wechat_timelines(
                table_rows.get("candidate_wechat_timelines", []),
                candidate_id_map,
                summary,
            )
            self._import_sync_score_events(
                table_rows.get("score_events", []),
                candidate_id_map,
                summary,
            )
            self._import_sync_match_scores(
                table_rows.get("match_scores", []),
                candidate_id_map,
                summary,
                manifest,
            )
            self._record_sync_import(manifest, summary)

        return summary

    def _reserve_sync_import(self, manifest: dict[str, Any]) -> bool:
        cursor = self._conn.execute(
            """
            INSERT INTO sync_imports(bundle_id, source_node_id, mode, summary)
            VALUES (?, ?, ?, NULL)
            ON CONFLICT(bundle_id) DO NOTHING
            """,
            (
                manifest.get("export_id"),
                manifest.get("source_node_id"),
                manifest.get("export_mode"),
            ),
        )
        return cursor.rowcount == 1

    def _insert_sync_candidate(
        self,
        row: dict[str, Any],
        manifest: dict[str, Any],
    ) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO candidates (
                name, gender, age, city, work_years, education,
                current_company, current_title, expected_salary,
                expected_city, expected_title, hunting_status,
                email, phone, wechat, wechat_id,
                skill_tags, data_level, overall_score, score_version,
                created_at, updated_at,
                sync_id, sync_origin_node_id, sync_updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["name"],
                row.get("gender"),
                row.get("age"),
                row.get("city"),
                row.get("work_years"),
                row.get("education"),
                row.get("current_company"),
                row.get("current_title"),
                row.get("expected_salary"),
                row.get("expected_city"),
                row.get("expected_title"),
                row.get("hunting_status"),
                row.get("email"),
                row.get("phone"),
                row.get("wechat"),
                row.get("wechat_id"),
                _json_dumps(row.get("skill_tags") or []),
                row.get("data_level") or "lead",
                row.get("overall_score") or 0,
                row.get("score_version") or 0,
                row.get("created_at"),
                row.get("updated_at"),
                row["sync_id"],
                row.get("sync_origin_node_id") or manifest.get("source_node_id"),
                row.get("sync_updated_at"),
            ),
        )
        return int(cursor.lastrowid)

    def _merge_sync_candidate(
        self,
        candidate_id: int,
        row: dict[str, Any],
        manifest: dict[str, Any],
    ) -> int:
        existing_row = self._conn.execute(
            "SELECT * FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        if existing_row is None:
            raise ValueError(f"Candidate does not exist: {candidate_id}")

        existing = dict(existing_row)
        existing["skill_tags"] = _json_loads(
            existing.get("skill_tags"), [], "candidates.skill_tags"
        )
        merged, conflicts = merge_candidate_payload(existing, row)
        updates: dict[str, Any] = {}
        for field in _CANDIDATE_FILL_ONLY_FIELDS:
            if merged.get(field) != existing.get(field):
                updates[field] = merged.get(field)

        if merged.get("skill_tags") != existing.get("skill_tags"):
            updates["skill_tags"] = _json_dumps(merged.get("skill_tags") or [])

        if merged.get("data_level") != existing.get("data_level"):
            updates["data_level"] = merged.get("data_level")

        if updates:
            set_clause = ", ".join(f"{field} = ?" for field in updates)
            self._conn.execute(
                f"""
                UPDATE candidates
                SET {set_clause}
                WHERE id = ?
                """,
                (*updates.values(), candidate_id),
            )
        self._record_sync_candidate_conflicts(existing, conflicts, manifest)
        return len(conflicts)

    def _record_sync_candidate_conflicts(
        self,
        existing: dict[str, Any],
        conflicts: list[dict[str, Any]],
        manifest: dict[str, Any],
    ) -> None:
        if not conflicts:
            return

        for conflict in conflicts:
            self._conn.execute(
                """
                INSERT INTO sync_conflicts (
                    entity_type, entity_sync_id, field_name,
                    local_value, remote_value, source_node_id, bundle_id
                )
                VALUES ('candidate', ?, ?, ?, ?, ?, ?)
                """,
                (
                    existing["sync_id"],
                    conflict["field_name"],
                    conflict["local_value"],
                    conflict["remote_value"],
                    manifest.get("source_node_id"),
                    manifest.get("export_id"),
                ),
            )

    def _record_sync_conflict(
        self,
        entity_type: str,
        entity_sync_id: str,
        field_name: str,
        local_value: Any,
        remote_value: Any,
        manifest: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO sync_conflicts (
                entity_type, entity_sync_id, field_name,
                local_value, remote_value, source_node_id, bundle_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_type,
                entity_sync_id,
                field_name,
                canonical_json(local_value),
                canonical_json(remote_value),
                manifest.get("source_node_id"),
                manifest.get("export_id"),
            ),
        )

    def _import_sync_candidate_details(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["candidate_details"] += 1
                continue

            existed = (
                self._sync_row_exists("candidate_details", row.get("sync_id"))
                or self._candidate_detail_exists(candidate_id)
            )
            conflict_count = self._merge_sync_candidate_detail(candidate_id, row, manifest)
            self._count_imported_row(summary, "candidate_details", existed)
            summary["conflicts"]["candidate_details"] += conflict_count

    def _merge_sync_candidate_detail(
        self,
        candidate_id: int,
        row: dict[str, Any],
        manifest: dict[str, Any],
    ) -> int:
        existing = self.get_detail(candidate_id)
        if existing is None:
            self._conn.execute(
                """
                INSERT INTO candidate_details (
                    candidate_id, work_experience, education_experience,
                    project_experience, raw_data, summary, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    _json_dumps(row.get("work_experience")),
                    _json_dumps(row.get("education_experience")),
                    _json_dumps(row.get("project_experience")),
                    _json_dumps(row.get("raw_data")),
                    row.get("summary"),
                    row.get("sync_id"),
                ),
            )
            self._touch_candidate_after_detail_import(candidate_id, row.get("work_experience"))
            return 0

        existing_data = existing.to_dict()
        merged: dict[str, Any] = {}
        conflicts: list[tuple[str, Any, Any]] = []
        for field in _DETAIL_FIELDS:
            incoming = row.get(field)
            current = existing_data.get(field)
            if field in _EXPERIENCE_FIELDS:
                merged[field] = _merge_detail_list(current, incoming)
            elif field == "summary":
                merged[field] = current
                if _is_empty(current) and not _is_empty(incoming):
                    merged[field] = incoming
                elif _both_present_and_different(current, incoming):
                    conflicts.append(("candidate_detail.summary", current, incoming))
            elif field == "raw_data":
                merged_raw_data, raw_conflicts = _merge_detail_raw_data(current, incoming)
                merged[field] = merged_raw_data
                conflicts.extend(raw_conflicts)
            else:
                merged[field] = (
                    incoming if _is_empty(current) and not _is_empty(incoming) else current
                )

        self._conn.execute(
            """
            UPDATE candidate_details
            SET work_experience = ?,
                education_experience = ?,
                project_experience = ?,
                raw_data = ?,
                summary = ?,
                sync_id = COALESCE(NULLIF(sync_id, ''), ?)
            WHERE candidate_id = ?
            """,
            (
                _json_dumps(merged.get("work_experience")),
                _json_dumps(merged.get("education_experience")),
                _json_dumps(merged.get("project_experience")),
                _json_dumps(merged.get("raw_data")),
                merged.get("summary"),
                row.get("sync_id"),
                candidate_id,
            ),
        )
        detail_sync_id = self._detail_sync_id(candidate_id) or str(row.get("sync_id") or "")
        for field_name, local_value, remote_value in conflicts:
            self._record_sync_conflict(
                "candidate_detail",
                detail_sync_id,
                field_name,
                local_value,
                remote_value,
                manifest,
            )
        self._touch_candidate_after_detail_import(candidate_id, merged.get("work_experience"))
        return len(conflicts)

    def _detail_sync_id(self, candidate_id: int) -> str:
        row = self._conn.execute(
            """
            SELECT sync_id
            FROM candidate_details
            WHERE candidate_id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return ""
        return str(row["sync_id"] or "")

    def _touch_candidate_after_detail_import(
        self,
        candidate_id: int,
        work_experience: Any,
    ) -> None:
        if work_experience:
            self._conn.execute(
                """
                UPDATE candidates
                SET data_level = 'detailed', updated_at = datetime('now')
                WHERE id = ?
                """,
                (candidate_id,),
            )
            return

        self._conn.execute(
            "UPDATE candidates SET updated_at = datetime('now') WHERE id = ?",
            (candidate_id,),
        )

    def _import_sync_source_profiles(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        source_profile_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["source_profiles"] += 1
                continue

            source_by_sync = self._source_profile_by_sync_id(row.get("sync_id"))
            if source_by_sync is not None:
                if int(source_by_sync["candidate_id"]) != candidate_id:
                    summary["skipped"]["source_profiles"] += 1
                    continue
                source_id = int(source_by_sync["id"])
                self._update_sync_source_profile(source_id, row)
                _map_sync_id(source_profile_id_map, row.get("sync_id"), source_id)
                summary["merged"]["source_profiles"] += 1
                continue

            existing_source = self._matching_source_profile(candidate_id, row)
            if existing_source is not None:
                if int(existing_source["candidate_id"]) != candidate_id:
                    summary["skipped"]["source_profiles"] += 1
                    continue
                source_id = int(existing_source["id"])
                self._update_sync_source_profile(source_id, row)
                _map_sync_id(source_profile_id_map, row.get("sync_id"), source_id)
                summary["merged"]["source_profiles"] += 1
                continue

            source_id = self._insert_sync_source_profile(candidate_id, row)
            _map_sync_id(source_profile_id_map, row.get("sync_id"), source_id)
            summary["created"]["source_profiles"] += 1

    def _insert_sync_source_profile(
        self,
        candidate_id: int,
        row: dict[str, Any],
    ) -> int:
        cursor = self._conn.execute(
            """
            INSERT INTO source_profiles (
                candidate_id, platform, platform_id, profile_url,
                raw_profile, fetched_at, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                row["platform"],
                row.get("platform_id"),
                row.get("profile_url"),
                _json_dumps(row.get("raw_profile")),
                row.get("fetched_at"),
                row.get("sync_id"),
            ),
        )
        return int(cursor.lastrowid)

    def _update_sync_source_profile(
        self,
        source_id: int,
        row: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            UPDATE source_profiles
            SET profile_url = COALESCE(?, profile_url),
                raw_profile = COALESCE(?, raw_profile),
                fetched_at = COALESCE(?, fetched_at),
                sync_id = COALESCE(NULLIF(sync_id, ''), ?)
            WHERE id = ?
            """,
            (
                row.get("profile_url"),
                _json_dumps(row.get("raw_profile")),
                row.get("fetched_at"),
                row.get("sync_id"),
                source_id,
            ),
        )

    def _matching_source_profile(
        self,
        candidate_id: int,
        row: dict[str, Any],
    ) -> sqlite3.Row | None:
        platform = str(row["platform"])
        platform_id = row.get("platform_id")
        if platform_id:
            return self._source_profile_by_platform_key(platform, str(platform_id))

        source_id = self._find_source_without_platform_id(
            candidate_id,
            platform,
            row.get("profile_url"),
        )
        if source_id is None:
            return None
        return self._conn.execute(
            """
            SELECT id, candidate_id
            FROM source_profiles
            WHERE id = ?
            """,
            (source_id,),
        ).fetchone()

    def _import_sync_identity_matches(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_sync_id = str(row.get("candidate_sync_id") or "")
            if candidate_sync_id:
                candidate_id = candidate_id_map.get(candidate_sync_id)
                if candidate_id is None:
                    summary["skipped"]["candidate_identity_matches"] += 1
                    continue
            else:
                candidate_id = None

            match_by_sync = self._identity_match_by_sync_id(row.get("sync_id"))
            if match_by_sync is not None:
                self._update_sync_identity_match(int(match_by_sync["id"]), candidate_id, row)
                summary["merged"]["candidate_identity_matches"] += 1
                continue

            self._insert_sync_identity_match(candidate_id, row)
            summary["created"]["candidate_identity_matches"] += 1

    def _insert_sync_identity_match(
        self,
        candidate_id: int | None,
        row: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO candidate_identity_matches (
                candidate_id, source_platform, source_candidate_key,
                target_platform, target_platform_id, target_profile_url,
                query_text, query_level, confidence, score_breakdown,
                match_status, decision_reason, confirmed_by, confirmed_at,
                created_at, updated_at, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                row["source_platform"],
                row["source_candidate_key"],
                row["target_platform"],
                row.get("target_platform_id"),
                row.get("target_profile_url"),
                row.get("query_text"),
                row.get("query_level"),
                row.get("confidence"),
                _score_breakdown_json(row.get("score_breakdown")),
                row["match_status"],
                row.get("decision_reason"),
                row.get("confirmed_by"),
                row.get("confirmed_at"),
                row.get("created_at"),
                row.get("updated_at"),
                row.get("sync_id"),
            ),
        )

    def _update_sync_identity_match(
        self,
        match_id: int,
        candidate_id: int | None,
        row: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            UPDATE candidate_identity_matches
            SET candidate_id = COALESCE(?, candidate_id),
                target_platform_id = COALESCE(?, target_platform_id),
                target_profile_url = COALESCE(?, target_profile_url),
                query_text = COALESCE(?, query_text),
                query_level = COALESCE(?, query_level),
                confidence = COALESCE(?, confidence),
                score_breakdown = COALESCE(?, score_breakdown),
                match_status = COALESCE(?, match_status),
                decision_reason = COALESCE(?, decision_reason),
                confirmed_by = COALESCE(?, confirmed_by),
                confirmed_at = COALESCE(?, confirmed_at),
                updated_at = COALESCE(?, updated_at),
                sync_id = COALESCE(NULLIF(sync_id, ''), ?)
            WHERE id = ?
            """,
            (
                candidate_id,
                row.get("target_platform_id"),
                row.get("target_profile_url"),
                row.get("query_text"),
                row.get("query_level"),
                row.get("confidence"),
                _score_breakdown_json(row.get("score_breakdown")),
                row.get("match_status"),
                row.get("decision_reason"),
                row.get("confirmed_by"),
                row.get("confirmed_at"),
                row.get("updated_at"),
                row.get("sync_id"),
                match_id,
            ),
        )

    def _import_sync_field_values(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        source_profile_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["candidate_field_values"] += 1
                continue

            value_by_sync = self._field_value_by_sync_id(row.get("sync_id"))
            source_profile_id = self._sync_field_value_source_profile_id(
                candidate_id,
                row,
                source_profile_id_map,
            )
            if value_by_sync is not None:
                self._update_sync_field_value(
                    int(value_by_sync["id"]),
                    candidate_id,
                    source_profile_id,
                    row,
                )
                summary["merged"]["candidate_field_values"] += 1
                continue

            self._insert_sync_field_value(candidate_id, source_profile_id, row)
            summary["created"]["candidate_field_values"] += 1

    def _insert_sync_field_value(
        self,
        candidate_id: int,
        source_profile_id: int | None,
        row: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO candidate_field_values (
                candidate_id, field_name, platform, source_profile_id,
                field_value, confidence, merge_decision, decision_reason,
                created_at, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                candidate_id,
                row["field_name"],
                row["platform"],
                source_profile_id,
                _json_dumps_literal(row.get("field_value")),
                row.get("confidence"),
                row.get("merge_decision"),
                row.get("decision_reason"),
                row.get("created_at"),
                row.get("sync_id"),
            ),
        )

    def _update_sync_field_value(
        self,
        value_id: int,
        candidate_id: int,
        source_profile_id: int | None,
        row: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            UPDATE candidate_field_values
            SET candidate_id = ?,
                source_profile_id = ?,
                field_value = ?,
                confidence = COALESCE(?, confidence),
                merge_decision = COALESCE(?, merge_decision),
                decision_reason = COALESCE(?, decision_reason),
                sync_id = COALESCE(NULLIF(sync_id, ''), ?)
            WHERE id = ?
            """,
            (
                candidate_id,
                source_profile_id,
                _json_dumps_literal(row.get("field_value")),
                row.get("confidence"),
                row.get("merge_decision"),
                row.get("decision_reason"),
                row.get("sync_id"),
                value_id,
            ),
        )

    def _sync_field_value_source_profile_id(
        self,
        candidate_id: int,
        row: dict[str, Any],
        source_profile_id_map: dict[str, int],
    ) -> int | None:
        source_profile_sync_id = str(row.get("source_profile_sync_id") or "")
        if source_profile_sync_id:
            mapped_id = source_profile_id_map.get(source_profile_sync_id)
            if mapped_id is not None:
                return mapped_id
            source_row = self._source_profile_by_sync_id(source_profile_sync_id)
            if source_row is not None and int(source_row["candidate_id"]) == candidate_id:
                return int(source_row["id"])
        return None

    def _import_sync_wechat_timelines(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["candidate_wechat_timelines"] += 1
                continue

            existed = self._sync_row_exists(
                "candidate_wechat_timelines",
                row.get("sync_id"),
            )
            if existed:
                summary["merged"]["candidate_wechat_timelines"] += 1
                continue
            existing_timeline = self._matching_wechat_timeline(candidate_id, row)
            if existing_timeline is not None:
                self._conn.execute(
                    """
                    UPDATE candidate_wechat_timelines
                    SET sync_id = COALESCE(NULLIF(sync_id, ''), ?)
                    WHERE id = ?
                    """,
                    (row.get("sync_id"), existing_timeline["id"]),
                )
                summary["merged"]["candidate_wechat_timelines"] += 1
                continue
            self._conn.execute(
                """
                INSERT INTO candidate_wechat_timelines (
                    candidate_id, chat_name, chat_identifier, start_time,
                    end_time, message_count, markdown_path, source_tool,
                    synced_at, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row["chat_name"],
                    row.get("chat_identifier"),
                    row.get("start_time"),
                    row.get("end_time"),
                    row.get("message_count"),
                    row["markdown_path"],
                    row.get("source_tool") or "wechat-cli",
                    row.get("synced_at"),
                    row.get("sync_id"),
                ),
            )
            summary["created"]["candidate_wechat_timelines"] += 1

    def _matching_wechat_timeline(
        self,
        candidate_id: int,
        row: dict[str, Any],
    ) -> sqlite3.Row | None:
        start_time = str(row.get("start_time") or "")
        end_time = str(row.get("end_time") or "")
        markdown_path = row.get("markdown_path")
        chat_identifier = str(row.get("chat_identifier") or "")
        if chat_identifier:
            match = self._matching_wechat_timeline_by_identifier(
                candidate_id,
                chat_identifier,
                start_time,
                end_time,
                markdown_path,
            )
            if match is not None:
                return match

        chat_name = str(row.get("chat_name") or "")
        if not chat_name:
            return None
        return self._matching_wechat_timeline_by_chat_name(
            candidate_id,
            chat_name,
            start_time,
            end_time,
            markdown_path,
        )

    def _matching_wechat_timeline_by_identifier(
        self,
        candidate_id: int,
        chat_identifier: str,
        start_time: str,
        end_time: str,
        markdown_path: Any,
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT id, sync_id
            FROM candidate_wechat_timelines
            WHERE candidate_id = ?
              AND chat_identifier = ?
              AND COALESCE(start_time, '') = ?
              AND COALESCE(end_time, '') = ?
              AND markdown_path = ?
            ORDER BY id
            LIMIT 1
            """,
            (
                candidate_id,
                chat_identifier,
                start_time,
                end_time,
                markdown_path,
            ),
        ).fetchone()

    def _matching_wechat_timeline_by_chat_name(
        self,
        candidate_id: int,
        chat_name: str,
        start_time: str,
        end_time: str,
        markdown_path: Any,
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT id, sync_id
            FROM candidate_wechat_timelines
            WHERE candidate_id = ?
              AND chat_name = ?
              AND COALESCE(start_time, '') = ?
              AND COALESCE(end_time, '') = ?
              AND markdown_path = ?
            ORDER BY id
            LIMIT 1
            """,
            (
                candidate_id,
                chat_name,
                start_time,
                end_time,
                markdown_path,
            ),
        ).fetchone()

    def _import_sync_score_events(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["score_events"] += 1
                continue

            existed = self._sync_row_exists("score_events", row.get("sync_id"))
            if existed:
                summary["merged"]["score_events"] += 1
                continue
            self._conn.execute(
                """
                INSERT INTO score_events (
                    candidate_id, old_score, new_score, trigger_type,
                    trigger_detail, computed_at, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row.get("old_score"),
                    row.get("new_score"),
                    row["trigger_type"],
                    _json_dumps(row.get("trigger_detail")),
                    row.get("computed_at"),
                    row.get("sync_id"),
                ),
            )
            summary["created"]["score_events"] += 1

    def _import_sync_match_scores(
        self,
        rows: list[dict[str, Any]],
        candidate_id_map: dict[str, int],
        summary: dict[str, Any],
        manifest: dict[str, Any],
    ) -> None:
        for row in rows:
            candidate_id = candidate_id_map.get(str(row.get("candidate_sync_id") or ""))
            if candidate_id is None:
                summary["skipped"]["match_scores"] += 1
                continue

            existed = self._sync_row_exists("match_scores", row.get("sync_id"))
            if existed:
                summary["merged"]["match_scores"] += 1
                continue
            if self._match_score_exists(
                candidate_id,
                str(row["jd_id"]),
                str(row["match_type"]),
            ):
                existing_score = self._match_score_by_stable_key(
                    candidate_id,
                    str(row["jd_id"]),
                    str(row["match_type"]),
                )
                if existing_score is not None and _match_score_conflicts(
                    existing_score,
                    row,
                ):
                    self._record_sync_conflict(
                        "match_score",
                        str(existing_score["sync_id"] or ""),
                        "match_score",
                        _match_score_conflict_payload(existing_score),
                        _remote_match_score_conflict_payload(row),
                        manifest,
                    )
                    summary["conflicts"]["match_scores"] += 1
                summary["merged"]["match_scores"] += 1
                continue
            self._conn.execute(
                """
                INSERT INTO match_scores (
                    candidate_id, jd_id, match_type, score,
                    dimensions, reason, created_at, sync_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row["jd_id"],
                    row["match_type"],
                    row.get("score"),
                    _json_dumps(row.get("dimensions")),
                    row.get("reason"),
                    row.get("created_at"),
                    row.get("sync_id"),
                ),
            )
            summary["created"]["match_scores"] += 1

    def _apply_sync_tombstones(
        self,
        rows: list[dict[str, Any]],
        summary: dict[str, Any],
    ) -> None:
        for row in rows:
            if row.get("entity_type") == "candidate":
                candidate = self._candidate_for_tombstone(row)
                if candidate is not None:
                    self._delete_candidate_without_tombstone(int(candidate["id"]))
                    summary["deleted"]["candidates"] += 1

            self._conn.execute(
                """
                INSERT INTO sync_tombstones (
                    entity_type, entity_sync_id, deleted_at, source_node_id, reason
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_sync_id) DO UPDATE SET
                    deleted_at = excluded.deleted_at,
                    source_node_id = excluded.source_node_id,
                    reason = excluded.reason
                """,
                (
                    row["entity_type"],
                    row["entity_sync_id"],
                    row.get("deleted_at"),
                    row["source_node_id"],
                    row.get("reason"),
                ),
            )
            summary["tombstoned"]["tombstones"] += 1

    def _candidate_for_tombstone(self, row: dict[str, Any]) -> sqlite3.Row | None:
        sync_id = str(row.get("entity_sync_id") or "")
        if not sync_id:
            return None

        candidate = self._conn.execute(
            """
            SELECT id, sync_id
            FROM candidates
            WHERE sync_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (sync_id,),
        ).fetchone()
        if candidate is not None:
            return candidate

        source_node_id = str(row.get("source_node_id") or "")
        if not source_node_id:
            return None
        return self._conn.execute(
            """
            SELECT candidates.id, candidates.sync_id
            FROM sync_entity_aliases
            JOIN candidates ON candidates.sync_id = sync_entity_aliases.local_sync_id
            WHERE sync_entity_aliases.entity_type = 'candidate'
              AND sync_entity_aliases.remote_sync_id = ?
              AND sync_entity_aliases.source_node_id = ?
            ORDER BY candidates.id
            LIMIT 1
            """,
            (sync_id, source_node_id),
        ).fetchone()

    def _delete_candidate_without_tombstone(self, candidate_id: int) -> None:
        if self._vec_available:
            self._conn.execute(
                "DELETE FROM candidate_vectors WHERE candidate_id = ?",
                (candidate_id,),
            )
        self._conn.execute(
            "DELETE FROM candidates WHERE id = ?",
            (candidate_id,),
        )

    def _record_sync_import(
        self,
        manifest: dict[str, Any],
        summary: dict[str, Any],
    ) -> None:
        self._conn.execute(
            """
            UPDATE sync_imports
            SET summary = ?
            WHERE bundle_id = ?
            """,
            (
                _json_dumps(summary),
                manifest.get("export_id"),
            ),
        )

    def _upsert_sync_alias(
        self,
        entity_type: str,
        remote_sync_id: str,
        local_sync_id: str,
        source_node_id: str,
    ) -> None:
        if not source_node_id:
            return
        self._conn.execute(
            """
            INSERT INTO sync_entity_aliases(
                entity_type, remote_sync_id, local_sync_id, source_node_id
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(entity_type, remote_sync_id, source_node_id) DO UPDATE SET
                local_sync_id = excluded.local_sync_id
            """,
            (entity_type, remote_sync_id, local_sync_id, source_node_id),
        )

    def _sync_row_exists(self, table: str, sync_id: Any) -> bool:
        if not sync_id:
            return False
        row = self._conn.execute(
            f"SELECT 1 FROM {table} WHERE sync_id = ? LIMIT 1",
            (sync_id,),
        ).fetchone()
        return row is not None

    def _candidate_detail_exists(self, candidate_id: int) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM candidate_details
            WHERE candidate_id = ?
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        return row is not None

    def _source_profile_by_sync_id(self, sync_id: Any) -> sqlite3.Row | None:
        if not sync_id:
            return None
        return self._conn.execute(
            """
            SELECT id, candidate_id
            FROM source_profiles
            WHERE sync_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (sync_id,),
        ).fetchone()

    def _source_profile_id_exists(self, source_profile_id: int) -> bool:
        return self._source_profile_by_id(source_profile_id) is not None

    def _source_profile_by_id(self, source_profile_id: int) -> sqlite3.Row | None:
        row = self._conn.execute(
            """
            SELECT id, candidate_id, sync_id
            FROM source_profiles
            WHERE id = ?
            LIMIT 1
            """,
            (source_profile_id,),
        ).fetchone()
        return row

    def _identity_match_by_sync_id(self, sync_id: Any) -> sqlite3.Row | None:
        if not sync_id:
            return None
        return self._conn.execute(
            """
            SELECT id, candidate_id
            FROM candidate_identity_matches
            WHERE sync_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (sync_id,),
        ).fetchone()

    def _field_value_by_sync_id(self, sync_id: Any) -> sqlite3.Row | None:
        if not sync_id:
            return None
        return self._conn.execute(
            """
            SELECT id, candidate_id
            FROM candidate_field_values
            WHERE sync_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (sync_id,),
        ).fetchone()

    def _source_profile_by_platform_key(
        self,
        platform: str,
        platform_id: str,
    ) -> sqlite3.Row | None:
        return self._conn.execute(
            """
            SELECT id, candidate_id
            FROM source_profiles
            WHERE platform = ? AND platform_id = ?
            ORDER BY id
            LIMIT 1
            """,
            (platform, platform_id),
        ).fetchone()

    def _source_profile_exists(self, platform: str, platform_id: str) -> bool:
        row = self._conn.execute(
            """
            SELECT 1
            FROM source_profiles
            WHERE platform = ? AND platform_id = ?
            LIMIT 1
            """,
            (platform, platform_id),
        ).fetchone()
        return row is not None

    def _match_score_exists(
        self,
        candidate_id: int,
        jd_id: str,
        match_type: str,
    ) -> bool:
        return self._match_score_by_stable_key(candidate_id, jd_id, match_type) is not None

    def _match_score_by_stable_key(
        self,
        candidate_id: int,
        jd_id: str,
        match_type: str,
    ) -> sqlite3.Row | None:
        row = self._conn.execute(
            """
            SELECT id, sync_id, score, dimensions, reason
            FROM match_scores
            WHERE candidate_id = ? AND jd_id = ? AND match_type = ?
            ORDER BY id
            LIMIT 1
            """,
            (candidate_id, jd_id, match_type),
        ).fetchone()
        return row

    @staticmethod
    def _count_imported_row(
        summary: dict[str, Any],
        table: str,
        existed: bool,
    ) -> None:
        bucket = "merged" if existed else "created"
        summary[bucket][table] += 1

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

    def _export_candidates(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                sync_id, sync_origin_node_id, sync_updated_at,
                name, gender, age, city, work_years, education,
                current_company, current_title, expected_salary,
                expected_city, expected_title, hunting_status,
                email, phone, wechat, wechat_id, skill_tags,
                data_level, overall_score, score_version,
                created_at, updated_at
            FROM candidates
            ORDER BY sync_id
            """
        ).fetchall()
        return [
            _export_row(
                row,
                json_fields={"skill_tags": []},
            )
            for row in rows
        ]

    def _export_candidate_details(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_details.sync_id,
                candidates.sync_id AS candidate_sync_id,
                candidate_details.work_experience,
                candidate_details.education_experience,
                candidate_details.project_experience,
                candidate_details.raw_data,
                candidate_details.summary
            FROM candidate_details
            JOIN candidates ON candidates.id = candidate_details.candidate_id
            ORDER BY candidate_details.sync_id
            """
        ).fetchall()
        return [
            _export_row(
                row,
                json_fields={
                    "work_experience": None,
                    "education_experience": None,
                    "project_experience": None,
                    "raw_data": None,
                },
            )
            for row in rows
        ]

    def _export_source_profiles(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                source_profiles.sync_id,
                candidates.sync_id AS candidate_sync_id,
                source_profiles.platform,
                source_profiles.platform_id,
                source_profiles.profile_url,
                source_profiles.raw_profile,
                source_profiles.fetched_at
            FROM source_profiles
            JOIN candidates ON candidates.id = source_profiles.candidate_id
            ORDER BY source_profiles.sync_id
            """
        ).fetchall()
        return [
            _export_row(row, json_fields={"raw_profile": None})
            for row in rows
        ]

    def _export_identity_matches(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_identity_matches.sync_id,
                candidates.sync_id AS candidate_sync_id,
                candidate_identity_matches.source_platform,
                candidate_identity_matches.source_candidate_key,
                candidate_identity_matches.target_platform,
                candidate_identity_matches.target_platform_id,
                candidate_identity_matches.target_profile_url,
                candidate_identity_matches.query_text,
                candidate_identity_matches.query_level,
                candidate_identity_matches.confidence,
                candidate_identity_matches.score_breakdown,
                candidate_identity_matches.match_status,
                candidate_identity_matches.decision_reason,
                candidate_identity_matches.confirmed_by,
                candidate_identity_matches.confirmed_at,
                candidate_identity_matches.created_at,
                candidate_identity_matches.updated_at
            FROM candidate_identity_matches
            LEFT JOIN candidates ON candidates.id = candidate_identity_matches.candidate_id
            ORDER BY candidate_identity_matches.sync_id
            """
        ).fetchall()
        return [
            _export_row(row, json_fields={"score_breakdown": None})
            for row in rows
        ]

    def _export_field_values(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_field_values.sync_id,
                candidates.sync_id AS candidate_sync_id,
                candidate_field_values.field_name,
                candidate_field_values.platform,
                candidate_field_values.source_profile_id,
                source_profiles.sync_id AS source_profile_sync_id,
                candidate_field_values.field_value,
                candidate_field_values.confidence,
                candidate_field_values.merge_decision,
                candidate_field_values.decision_reason,
                candidate_field_values.created_at
            FROM candidate_field_values
            JOIN candidates ON candidates.id = candidate_field_values.candidate_id
            LEFT JOIN source_profiles
              ON source_profiles.id = candidate_field_values.source_profile_id
            ORDER BY candidate_field_values.sync_id
            """
        ).fetchall()
        return [
            _export_row(row, json_fields={"field_value": None})
            for row in rows
        ]

    def _export_wechat_timelines(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                candidate_wechat_timelines.sync_id,
                candidates.sync_id AS candidate_sync_id,
                candidate_wechat_timelines.chat_name,
                candidate_wechat_timelines.chat_identifier,
                candidate_wechat_timelines.start_time,
                candidate_wechat_timelines.end_time,
                candidate_wechat_timelines.message_count,
                candidate_wechat_timelines.markdown_path,
                candidate_wechat_timelines.source_tool,
                candidate_wechat_timelines.synced_at
            FROM candidate_wechat_timelines
            JOIN candidates ON candidates.id = candidate_wechat_timelines.candidate_id
            ORDER BY candidate_wechat_timelines.sync_id
            """
        ).fetchall()
        return [_export_row(row) for row in rows]

    def _export_score_events(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                score_events.sync_id,
                candidates.sync_id AS candidate_sync_id,
                score_events.old_score,
                score_events.new_score,
                score_events.trigger_type,
                score_events.trigger_detail,
                score_events.computed_at
            FROM score_events
            JOIN candidates ON candidates.id = score_events.candidate_id
            ORDER BY score_events.sync_id
            """
        ).fetchall()
        return [
            _export_row(row, json_fields={"trigger_detail": None})
            for row in rows
        ]

    def _export_match_scores(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT
                match_scores.sync_id,
                candidates.sync_id AS candidate_sync_id,
                match_scores.jd_id,
                match_scores.match_type,
                match_scores.score,
                match_scores.dimensions,
                match_scores.reason,
                match_scores.created_at
            FROM match_scores
            JOIN candidates ON candidates.id = match_scores.candidate_id
            ORDER BY match_scores.sync_id
            """
        ).fetchall()
        return [
            _export_row(row, json_fields={"dimensions": None})
            for row in rows
        ]

    def _export_tombstones(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT entity_type, entity_sync_id, deleted_at, source_node_id, reason
            FROM sync_tombstones
            ORDER BY entity_type, entity_sync_id
            """
        ).fetchall()
        return [_export_row(row) for row in rows]

    def _candidate_exists(self, candidate_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        return row is not None

    def search(
        self,
        filters: CandidateFilter | None = None,
        sort: SortSpec | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PageResult:
        if not _is_positive_int(page):
            raise ValueError("page must be a positive integer")
        if not _is_positive_int(page_size):
            raise ValueError("page_size must be a positive integer")

        order_by = self._order_by_clause(sort)
        where_clause, params = _candidate_where_clause(filters)
        total = self.count(filters)
        offset = (page - 1) * page_size
        rows = self._conn.execute(
            f"""
            SELECT candidates.*
            FROM candidates
            {where_clause}
            ORDER BY {order_by}, candidates.id ASC
            LIMIT ? OFFSET ?
            """,
            (*params, page_size, offset),
        ).fetchall()
        items = [_candidate_from_row(row) for row in rows]
        return PageResult(items=items, total=total, page=page, page_size=page_size)

    def count(self, filters: CandidateFilter | None = None) -> int:
        where_clause, params = _candidate_where_clause(filters)
        row = self._conn.execute(
            f"""
            SELECT COUNT(*)
            FROM candidates
            {where_clause}
            """,
            params,
        ).fetchone()
        return int(row[0])

    def fulltext_search(self, query: str, limit: int = 50) -> list[SearchHit]:
        if not _is_positive_int(limit):
            raise ValueError("limit must be a positive integer")

        normalized_query = query.strip()
        if not normalized_query:
            return []

        try:
            return self._fulltext_search(normalized_query, limit)
        except sqlite3.OperationalError as exc:
            if not _is_fts_query_error(exc):
                raise
            safe_query = _safe_fts_query(normalized_query)
            if not safe_query:
                return []
            try:
                return self._fulltext_search(safe_query, limit)
            except sqlite3.OperationalError as fallback_exc:
                if not _is_fts_query_error(fallback_exc):
                    raise
                return []

    def _fulltext_search(self, query: str, limit: int) -> list[SearchHit]:
        rows = self._conn.execute(
            """
            SELECT
                rowid AS id,
                rank,
                snippet(candidate_fts, -1, '<b>', '</b>', '...', 20) AS snippet
            FROM candidate_fts
            WHERE candidate_fts MATCH ?
            ORDER BY rank ASC, rowid ASC
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()
        return [
            SearchHit(id=int(row["id"]), rank=float(row["rank"]), snippet=row["snippet"])
            for row in rows
        ]

    @staticmethod
    def _order_by_clause(sort: SortSpec | None) -> str:
        spec = sort or SortSpec(field="overall_score", direction="desc")
        field = _SORT_FIELDS.get(spec.field)
        if field is None:
            raise ValueError(f"Unsupported sort field: {spec.field}")
        if spec.direction not in {"asc", "desc"}:
            raise ValueError(f"Unsupported sort direction: {spec.direction}")
        return f"{field} {spec.direction.upper()}"

    def enrich(self, candidate_id: int, detail_data: dict[str, Any]) -> None:
        with self._conn:
            self._enrich_no_commit(candidate_id, detail_data)

    def _enrich_no_commit(self, candidate_id: int, detail_data: dict[str, Any]) -> None:
        values = {field: detail_data.get(field) for field in _DETAIL_FIELDS}
        work_experience = values.get("work_experience")
        self._conn.execute(
            """
            INSERT INTO candidate_details (
                candidate_id, work_experience, education_experience,
                project_experience, raw_data, summary, sync_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                work_experience = excluded.work_experience,
                education_experience = excluded.education_experience,
                project_experience = excluded.project_experience,
                raw_data = excluded.raw_data,
                summary = excluded.summary,
                sync_id = COALESCE(NULLIF(candidate_details.sync_id, ''), excluded.sync_id)
            """,
            (
                candidate_id,
                _json_dumps(values["work_experience"]),
                _json_dumps(values["education_experience"]),
                _json_dumps(values["project_experience"]),
                _json_dumps(values["raw_data"]),
                values["summary"],
                self._new_sync_id("detail"),
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


def merge_candidate_payload(
    local: dict[str, Any],
    remote: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    merged = dict(local)
    conflicts: list[dict[str, Any]] = []

    if _both_present_and_different(local.get("name"), remote.get("name")):
        conflicts.append(_candidate_conflict("name", local.get("name"), remote.get("name")))

    for field in _CANDIDATE_FILL_ONLY_FIELDS:
        local_value = local.get(field)
        remote_value = remote.get(field)
        if _is_empty(local_value) and not _is_empty(remote_value):
            merged[field] = remote_value
        elif _both_present_and_different(local_value, remote_value):
            conflicts.append(_candidate_conflict(field, local_value, remote_value))

    local_tags = _candidate_skill_tags(local.get("skill_tags"))
    remote_tags = _candidate_skill_tags(remote.get("skill_tags"))
    merged["skill_tags"] = _merge_skill_tags(local_tags, remote_tags)

    local_level = local.get("data_level") or "lead"
    remote_level = remote.get("data_level") or "lead"
    merged["data_level"] = (
        remote_level
        if _data_level_rank(remote_level) > _data_level_rank(local_level)
        else local_level
    )

    return merged, conflicts


def _json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_dumps_literal(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _score_breakdown_json(value: Any) -> str:
    if value is None:
        return "{}"
    if not isinstance(value, dict):
        raise ValueError("score_breakdown must be a dict")
    return _json_dumps(value) or "{}"


def _empty_sync_import_counts() -> dict[str, int]:
    return {table: 0 for table in _SYNC_IMPORT_TABLES}


def _new_sync_import_summary(
    manifest: dict[str, Any],
    table_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    return {
        "bundle_id": manifest.get("export_id"),
        "source_node_id": manifest.get("source_node_id"),
        "mode": manifest.get("export_mode"),
        "created": _empty_sync_import_counts(),
        "merged": _empty_sync_import_counts(),
        "conflicts": _empty_sync_import_counts(),
        "skipped": _empty_sync_import_counts(),
        "deleted": _empty_sync_import_counts(),
        "tombstoned": _empty_sync_import_counts(),
        "tables": {
            table: len(table_rows.get(table, []))
            for table in _SYNC_IMPORT_TABLES
        },
    }


def _already_imported_sync_import_summary(
    manifest: dict[str, Any],
    table_rows: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    summary = _new_sync_import_summary(manifest, table_rows)
    summary["skipped"]["already_imported"] = 1
    return summary


def _candidate_tombstone_sync_ids(
    table_rows: dict[str, list[dict[str, Any]]],
) -> set[str]:
    sync_ids: set[str] = set()
    for row in table_rows.get("tombstones", []):
        if row.get("entity_type") != "candidate":
            continue
        sync_id = str(row.get("entity_sync_id") or "")
        if sync_id:
            sync_ids.add(sync_id)
    return sync_ids


def _local_candidate_tombstone_sync_ids(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        """
        SELECT entity_sync_id AS sync_id
        FROM sync_tombstones
        WHERE entity_type = 'candidate'

        UNION

        SELECT sync_entity_aliases.remote_sync_id AS sync_id
        FROM sync_tombstones
        JOIN sync_entity_aliases
          ON sync_entity_aliases.entity_type = 'candidate'
         AND sync_entity_aliases.local_sync_id = sync_tombstones.entity_sync_id
        WHERE sync_tombstones.entity_type = 'candidate'
        """
    ).fetchall()
    return {str(row["sync_id"]) for row in rows if row["sync_id"]}


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _json_loads(value: str | None, default: Any, field_name: str) -> Any:
    if value is None:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in TalentDB field {field_name}") from exc


def _export_row(
    row: sqlite3.Row,
    json_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = dict(row)
    for field_name, default in (json_fields or {}).items():
        data[field_name] = _json_loads(data.get(field_name), default, field_name)
    return data


def _map_sync_id(mapping: dict[str, int], sync_id: Any, local_id: int) -> None:
    sync_id_text = str(sync_id or "")
    if sync_id_text:
        mapping[sync_id_text] = local_id


def _count_rows(conn: sqlite3.Connection, table: str, column: str, value: Any) -> int:
    row = conn.execute(
        f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
        (value,),
    ).fetchone()
    return int(row[0])


def _candidate_from_row(row: sqlite3.Row) -> Candidate:
    data = dict(row)
    data["skill_tags"] = _json_loads(data.get("skill_tags"), [], "candidates.skill_tags")
    return Candidate.from_dict(data)


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


def _row_to_identity_match(row: sqlite3.Row) -> CandidateIdentityMatch:
    return CandidateIdentityMatch(
        id=int(row["id"]),
        candidate_id=(
            int(row["candidate_id"]) if row["candidate_id"] is not None else None
        ),
        source_platform=row["source_platform"],
        source_candidate_key=row["source_candidate_key"],
        target_platform=row["target_platform"],
        target_platform_id=row["target_platform_id"],
        target_profile_url=row["target_profile_url"],
        query_text=row["query_text"],
        query_level=row["query_level"],
        confidence=(
            float(row["confidence"]) if row["confidence"] is not None else None
        ),
        score_breakdown=_json_loads(
            row["score_breakdown"],
            None,
            "candidate_identity_matches.score_breakdown",
        ),
        match_status=row["match_status"],
        decision_reason=row["decision_reason"],
        confirmed_by=row["confirmed_by"],
        confirmed_at=row["confirmed_at"],
        created_at=row["created_at"] or "",
        updated_at=row["updated_at"] or "",
    )


def _row_to_field_value(row: sqlite3.Row) -> CandidateFieldValue:
    return CandidateFieldValue(
        id=int(row["id"]),
        candidate_id=int(row["candidate_id"]),
        field_name=row["field_name"],
        platform=row["platform"],
        source_profile_id=(
            int(row["source_profile_id"])
            if row["source_profile_id"] is not None
            else None
        ),
        field_value=_json_loads(
            row["field_value"],
            None,
            "candidate_field_values.field_value",
        ),
        confidence=(
            float(row["confidence"]) if row["confidence"] is not None else None
        ),
        merge_decision=row["merge_decision"],
        decision_reason=row["decision_reason"],
        created_at=row["created_at"] or "",
    )


def _match_score_from_row(row: sqlite3.Row) -> MatchScore:
    return MatchScore(
        id=int(row["id"]),
        candidate_id=int(row["candidate_id"]),
        jd_id=row["jd_id"],
        match_type=row["match_type"],
        score=float(row["score"]),
        dimensions=_json_loads(row["dimensions"], None, "match_scores.dimensions"),
        reason=row["reason"],
        created_at=row["created_at"],
    )


def _candidate_where_clause(filters: CandidateFilter | None) -> tuple[str, tuple[Any, ...]]:
    if filters is None:
        return "", ()

    clauses: list[str] = []
    params: list[Any] = []

    _add_in_filter(clauses, params, "candidates.current_company", filters.companies)
    _add_in_filter(clauses, params, "candidates.current_title", filters.titles)
    _add_in_filter(clauses, params, "candidates.city", filters.cities)
    _add_in_filter(clauses, params, "candidates.education", filters.education_levels)
    _add_in_filter(clauses, params, "candidates.hunting_status", filters.hunting_status)

    if filters.min_work_years is not None:
        clauses.append("candidates.work_years >= ?")
        params.append(filters.min_work_years)
    if filters.max_work_years is not None:
        clauses.append("candidates.work_years <= ?")
        params.append(filters.max_work_years)
    if filters.data_level is not None:
        clauses.append("candidates.data_level = ?")
        params.append(filters.data_level)
    if filters.min_score is not None:
        clauses.append("candidates.overall_score >= ?")
        params.append(filters.min_score)
    if filters.max_score is not None:
        clauses.append("candidates.overall_score <= ?")
        params.append(filters.max_score)
    if filters.updated_after is not None:
        clauses.append("candidates.updated_at > ?")
        params.append(filters.updated_after)

    if filters.skills_any:
        placeholders = _placeholders(filters.skills_any)
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM json_each(candidates.skill_tags) AS skill
                WHERE skill.value IN ({placeholders})
            )
            """.format(placeholders=placeholders)
        )
        params.extend(filters.skills_any)

    for skill in filters.skills_all or []:
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM json_each(candidates.skill_tags) AS skill
                WHERE skill.value = ?
            )
            """
        )
        params.append(skill)

    if filters.platforms:
        placeholders = _placeholders(filters.platforms)
        clauses.append(
            """
            EXISTS (
                SELECT 1
                FROM source_profiles
                WHERE source_profiles.candidate_id = candidates.id
                  AND source_profiles.platform IN ({placeholders})
            )
            """.format(placeholders=placeholders)
        )
        params.extend(filters.platforms)

    if not clauses:
        return "", ()
    return "WHERE " + " AND ".join(clauses), tuple(params)


def _add_in_filter(
    clauses: list[str],
    params: list[Any],
    column: str,
    values: list[Any] | None,
) -> None:
    if not values:
        return
    clauses.append(f"{column} IN ({_placeholders(values)})")
    params.extend(values)


def _placeholders(values: list[Any]) -> str:
    return ", ".join("?" for _ in values)


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _validate_non_empty_string(value: Any, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _validate_score(score: Any) -> None:
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError("score must be a number between 0 and 100")
    if not math.isfinite(float(score)):
        raise ValueError("score must be finite")
    if score < 0 or score > 100:
        raise ValueError("score must be between 0 and 100")


def _validate_optional_number(value: Any, field_name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a finite number")
    if not math.isfinite(float(value)):
        raise ValueError(f"{field_name} must be a finite number")


def _optional_int(value: Any, field_name: str) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be an integer") from exc
    raise ValueError(f"{field_name} must be an integer")


def _safe_fts_query(query: str) -> str:
    operators = {"AND", "OR", "NEAR", "NOT"}
    tokens = [
        token
        for token in re.findall(r"\w+", query, flags=re.UNICODE)
        if token.upper() not in operators
    ]
    return " OR ".join(f'"{token}"' for token in tokens)


def _is_fts_query_error(exc: sqlite3.OperationalError) -> bool:
    message = str(exc).lower()
    return (
        "fts5: syntax error" in message
        or "malformed match expression" in message
        or "unterminated string" in message
    )


def _identity_value(value: Any) -> str:
    return "" if value is None else str(value)


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _both_present_and_different(local: Any, remote: Any) -> bool:
    if _is_empty(local) or _is_empty(remote):
        return False
    return _normalized_merge_value(local) != _normalized_merge_value(remote)


def _normalized_merge_value(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    return value


def _candidate_conflict(
    field_name: str,
    local_value: Any,
    remote_value: Any,
) -> dict[str, Any]:
    return {
        "field_name": field_name,
        "local_value": canonical_json(local_value),
        "remote_value": canonical_json(remote_value),
    }


def _candidate_skill_tags(value: Any) -> list[str]:
    if _is_empty(value):
        return []
    if isinstance(value, str):
        loaded = _json_loads(value, [], "candidates.skill_tags")
        return [str(tag) for tag in _as_list(loaded)]
    return [str(tag) for tag in _as_list(value)]


def _merge_skill_tags(existing: list[str], incoming: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for tag in [*existing, *incoming]:
        if tag in seen:
            continue
        seen.add(tag)
        merged.append(tag)
    return merged


def _merge_detail_list(existing: Any, incoming: Any) -> list[Any] | None:
    merged: list[Any] = []
    seen: set[str] = set()
    for item in [*_as_list(existing), *_as_list(incoming)]:
        key = canonical_json(item)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged or None


def _merge_detail_raw_data(
    existing: Any,
    incoming: Any,
) -> tuple[dict[str, Any] | None, list[tuple[str, Any, Any]]]:
    if _is_empty(existing) and _is_empty(incoming):
        return None, []
    if _is_empty(existing):
        return dict(incoming) if isinstance(incoming, dict) else incoming, []
    if _is_empty(incoming):
        return dict(existing) if isinstance(existing, dict) else existing, []
    if not isinstance(existing, dict) or not isinstance(incoming, dict):
        if canonical_json(existing) == canonical_json(incoming):
            return existing, []
        return existing, [("candidate_detail.raw_data", existing, incoming)]

    merged = dict(existing)
    conflicts: list[tuple[str, Any, Any]] = []
    for namespace, remote_value in incoming.items():
        if namespace not in merged or _is_empty(merged.get(namespace)):
            merged[namespace] = remote_value
            continue
        local_value = merged.get(namespace)
        if namespace == _MAIMAI_DETAIL_CAPTURE_NAMESPACE and _maimai_detail_capture_compatible(
            local_value,
            remote_value,
        ):
            merged[namespace] = _merge_maimai_detail_capture_value(
                local_value,
                remote_value,
            )
            continue
        if canonical_json(local_value) != canonical_json(remote_value):
            conflicts.append(
                (f"candidate_detail.raw_data.{namespace}", local_value, remote_value)
            )
    return merged, conflicts


_MAIMAI_DETAIL_CAPTURE_NAMESPACE = "maimai_detail_capture"
_MAIMAI_VOLATILE_RAW_KEYS = {
    "active_state",
    "active_state_v1",
    "active_state_v2",
    "age",
    "avatar",
    "candidate_id",
    "capture_file",
    "created_at",
    "crtime",
    "fid",
    "file_md5",
    "finished_at",
    "friends",
    "hover",
    "id",
    "index",
    "logo",
    "mode",
    "record_url",
    "second",
    "source_contact",
    "started_at",
    "timestamp",
    "updated_at",
    "uptime",
    "viewed",
}
_MAIMAI_RESPONSE_WRAPPER_KEYS = {
    "authFailure",
    "contentType",
    "error",
    "parseError",
    "raw",
    "rawLength",
    "rawPreview",
}


def _maimai_detail_capture_compatible(local: Any, remote: Any) -> bool:
    return canonical_json(_normalize_maimai_detail_capture(local)) == canonical_json(
        _normalize_maimai_detail_capture(remote)
    )


def _normalize_maimai_detail_capture(value: Any) -> Any:
    if isinstance(value, dict):
        if _is_maimai_response_wrapper(value):
            return _normalize_maimai_response_wrapper(value)

        normalized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            normalized_key = _normalize_maimai_raw_key(key_text)
            if _ignore_maimai_detail_key(key_text):
                continue
            if normalized_key == "job_preferences":
                normalized_value = _normalize_maimai_job_preferences(item)
            elif normalized_key == "user_project":
                continue
            else:
                normalized_value = _normalize_maimai_detail_capture(item)
            if not _is_empty(normalized_value):
                normalized[normalized_key] = normalized_value
        return normalized

    if isinstance(value, list):
        normalized_items = [
            item
            for item in (_normalize_maimai_detail_capture(item) for item in value)
            if not _is_empty(item)
        ]
        if all(not isinstance(item, (dict, list)) for item in normalized_items):
            return sorted(normalized_items, key=lambda item: str(item))
        return normalized_items

    if isinstance(value, str):
        return value.strip()
    return value


def _normalize_maimai_raw_key(key: str) -> str:
    if key == "job_preference":
        return "job_preferences"
    return key


def _ignore_maimai_detail_key(key: str) -> bool:
    key_lower = key.lower()
    if key in _MAIMAI_VOLATILE_RAW_KEYS or key_lower in _MAIMAI_VOLATILE_RAW_KEYS:
        return True
    if "token" in key_lower or "url" in key_lower:
        return True
    if "avatar" in key_lower or "logo" in key_lower or "image" in key_lower:
        return True
    if key.endswith("_at"):
        return True
    return key in _MAIMAI_RESPONSE_WRAPPER_KEYS


def _is_maimai_response_wrapper(value: dict[str, Any]) -> bool:
    return (
        "data" in value
        and ("ok" in value or "httpStatus" in value)
        and (
            "name" in value
            or any(key in value for key in _MAIMAI_RESPONSE_WRAPPER_KEYS)
        )
    )


def _normalize_maimai_response_wrapper(value: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key in ("name", "ok", "httpStatus", "data"):
        if key in value:
            normalized[key] = _normalize_maimai_detail_capture(value[key])
    return {key: item for key, item in normalized.items() if not _is_empty(item)}


def _normalize_maimai_job_preferences(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"value": _normalize_maimai_detail_capture(value)}

    source = value.get("job_preference")
    if not isinstance(source, dict):
        source = value

    normalized: dict[str, Any] = {}
    positions = _maimai_text_list(source.get("positions"))
    cities = _maimai_text_list(
        source.get("regions") or source.get("province_cities"),
        normalize_locations=True,
    )
    salary = source.get("salary")
    if positions:
        normalized["positions"] = positions
    if cities:
        normalized["province_cities"] = cities
    if not _is_empty(salary):
        normalized["salary"] = str(salary).strip()
    return normalized


def _maimai_text_list(value: Any, normalize_locations: bool = False) -> list[str]:
    if _is_empty(value):
        return []
    if isinstance(value, list):
        return sorted(
            {
                _maimai_location_key(str(item).strip())
                if normalize_locations
                else str(item).strip()
                for item in value
                if str(item).strip()
            }
        )
    text = str(value).strip()
    if not text:
        return []
    for separator in ("、", "|", "，", ",", "；", ";"):
        text = text.replace(separator, "\n")
    parts = {part.strip() for part in text.splitlines() if part.strip()}
    if normalize_locations:
        parts = {_maimai_location_key(part) for part in parts}
    return sorted(parts)


_MAIMAI_LOCATION_PREFIXES = (
    "黑龙江",
    "内蒙古",
    "北京",
    "天津",
    "上海",
    "重庆",
    "河北",
    "山西",
    "辽宁",
    "吉林",
    "江苏",
    "浙江",
    "安徽",
    "福建",
    "江西",
    "山东",
    "河南",
    "湖北",
    "湖南",
    "广东",
    "海南",
    "四川",
    "贵州",
    "云南",
    "陕西",
    "甘肃",
    "青海",
    "台湾",
    "广西",
    "西藏",
    "宁夏",
    "新疆",
    "香港",
    "澳门",
)


def _maimai_location_key(value: str) -> str:
    if value in {"北京", "上海", "天津", "重庆", "香港", "澳门"}:
        return value
    for prefix in _MAIMAI_LOCATION_PREFIXES:
        if value.startswith(prefix) and len(value) > len(prefix):
            return value[len(prefix) :]
    return value


def _merge_maimai_detail_capture_value(local: Any, remote: Any) -> Any:
    if _is_empty(local):
        return remote
    if _is_empty(remote):
        return local
    if isinstance(local, dict) and isinstance(remote, dict):
        merged = dict(local)
        for key, remote_value in remote.items():
            if key not in merged or _is_empty(merged.get(key)):
                merged[key] = remote_value
                continue
            merged[key] = _merge_maimai_detail_capture_value(merged[key], remote_value)
        return merged
    if _maimai_value_richness(remote) > _maimai_value_richness(local):
        return remote
    return local


def _maimai_value_richness(value: Any) -> int:
    if _is_empty(value):
        return 0
    if isinstance(value, dict) and set(value) == {"total"} and not value.get("total"):
        return 0
    return len(canonical_json(value))


def _match_score_conflict_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "score": row["score"],
        "reason": row["reason"],
        "dimensions": _json_loads(
            row["dimensions"],
            None,
            "match_scores.dimensions",
        ),
    }


def _remote_match_score_conflict_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "score": row.get("score"),
        "reason": row.get("reason"),
        "dimensions": row.get("dimensions"),
    }


def _match_score_conflicts(local: sqlite3.Row, remote: dict[str, Any]) -> bool:
    return canonical_json(_match_score_conflict_payload(local)) != canonical_json(
        _remote_match_score_conflict_payload(remote)
    )


def _as_list(value: Any) -> list[Any]:
    if _is_empty(value):
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


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
