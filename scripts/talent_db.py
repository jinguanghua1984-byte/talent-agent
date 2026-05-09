"""SQLite storage layer for the local talent database."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from scripts.talent_models import (
    Candidate,
    CandidateDetail,
    CandidateFilter,
    IngestResult,
    MatchScore,
    PageResult,
    PendingMerge,
    SearchHit,
    SortSpec,
    SourceProfile,
    VectorHit,
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
                        fetched_at = datetime('now')
                    WHERE id = ?
                    """,
                    (profile_url, raw_profile, existing_source_id),
                )
                return

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
                platform_id,
                profile_url,
                raw_profile,
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

    def update_overall_score(
        self,
        candidate_id: int,
        score: float,
        trigger: str,
        detail: dict[str, Any] | None = None,
    ) -> None:
        _validate_score(score)
        _validate_non_empty_string(trigger, "trigger")
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

        new_score = float(score)
        with self._conn:
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
                    candidate_id, old_score, new_score, trigger_type, trigger_detail
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    float(row["overall_score"]),
                    new_score,
                    trigger,
                    _json_dumps(detail),
                ),
            )

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
                    candidate_id, jd_id, match_type, score, dimensions, reason
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id, jd_id, match_type) DO UPDATE SET
                    score = excluded.score,
                    dimensions = excluded.dimensions,
                    reason = excluded.reason,
                    created_at = datetime('now')
                """,
                (
                    candidate_id,
                    jd_id,
                    match_type,
                    float(score),
                    _json_dumps(dimensions),
                    reason,
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


def _candidate_from_row(row: sqlite3.Row) -> Candidate:
    data = dict(row)
    data["skill_tags"] = _json_loads(data.get("skill_tags"), [], "candidates.skill_tags")
    return Candidate.from_dict(data)


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
    if score < 0 or score > 100:
        raise ValueError("score must be between 0 and 100")


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
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged or None


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
