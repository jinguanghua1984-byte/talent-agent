"""旧版候选人 JSON 到本地 SQLite 人才库的迁移脚本。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.talent_db import TalentDB
from scripts.talent_models import IngestResult


_CORE_FIELDS = (
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
    "skill_tags",
)
_DETAIL_FIELDS = (
    "work_experience",
    "education_experience",
    "project_experience",
    "summary",
)


def migrate_candidates(json_dir: Path, db_path: Path) -> IngestResult:
    """迁移目录下的旧版候选人 JSON 文件到 TalentDB。"""
    result = IngestResult()
    db = TalentDB(db_path)
    try:
        if not json_dir.exists():
            return result

        for json_file in sorted(json_dir.glob("*.json")):
            if _should_skip(json_file):
                continue
            try:
                legacy = _load_legacy_json(json_file)
                sources = _normalize_sources(legacy.get("sources"))
                primary_source = sources[0] if sources else {}
                candidate_data = _to_ingest_data(legacy, primary_source)
                db.ingest(candidate_data, platform=_platform_for(primary_source))
                _count_action(result, getattr(db, "_last_ingest_action", None))
                for source in sources[1:]:
                    db.ingest(_to_ingest_data(legacy, source), platform=_platform_for(source))
            except Exception as exc:  # noqa: BLE001 - 单文件失败不阻断批量迁移。
                result.errors += 1
                result.error_details.append(f"{json_file.name}: {exc}")
        return result
    finally:
        db.close()


def _should_skip(path: Path) -> bool:
    name = path.name
    return name.endswith(".merged.json") or ".tmp" in name or name.startswith(".")


def _load_legacy_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)
    if not isinstance(payload, dict):
        raise ValueError("candidate JSON must be an object")
    return payload


def _normalize_sources(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _to_ingest_data(legacy: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    data = {field: legacy[field] for field in _CORE_FIELDS if field in legacy}
    if "hunting_status" in legacy:
        data["hunting_status"] = legacy["hunting_status"]
    elif "status" in legacy:
        data["hunting_status"] = legacy["status"]

    data["platform_id"] = source.get("platform_id") or source.get("id")
    data["profile_url"] = source.get("url") or source.get("profile_url")
    data["raw_profile"] = {
        "source": source,
        "legacy_json": legacy,
    }

    detail = {field: legacy[field] for field in _DETAIL_FIELDS if field in legacy}
    raw_data = {
        "legacy_json": legacy,
    }
    if "raw_data" in legacy:
        raw_data["legacy"] = {"raw_data": legacy["raw_data"]}
    if "active_state" in legacy:
        raw_data["active_state"] = legacy["active_state"]
    data["detail"] = {**detail, "raw_data": raw_data}
    return data


def _platform_for(source: dict[str, Any]) -> str:
    platform = source.get("channel") or source.get("platform") or source.get("source")
    if platform is None:
        return "legacy_json"
    return str(platform)


def _count_action(result: IngestResult, action: str | None) -> None:
    if action == "created":
        result.created += 1
    elif action == "merged":
        result.merged += 1
    elif action == "pending":
        result.pending += 1


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate legacy candidate JSON to SQLite.")
    parser.add_argument("--json-dir", required=True, type=Path)
    parser.add_argument("--db-path", required=True, type=Path)
    args = parser.parse_args()

    result = migrate_candidates(args.json_dir, args.db_path)
    print(
        "Migration summary: "
        f"created={result.created}, "
        f"merged={result.merged}, "
        f"pending={result.pending}, "
        f"errors={result.errors}"
    )
    for detail in result.error_details:
        print(f"ERROR: {detail}")


if __name__ == "__main__":
    main()
