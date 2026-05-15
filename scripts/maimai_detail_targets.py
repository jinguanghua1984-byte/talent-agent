"""把 talent-library 推荐列表转换为 maimai-scraper 批量详情输入。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_review import load_review_decisions
from scripts.talent_db import TalentDB


CONTAINER_KEYS = ("top10", "candidates", "matches", "results", "items")


def parse_maimai_profile_url(url: str | None) -> dict[str, str]:
    if not url:
        return {}
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    result: dict[str, str] = {}
    if query.get("dstu"):
        result["id"] = query["dstu"][0]
    if query.get("to_uid"):
        result["id"] = query["to_uid"][0]
    if query.get("trackable_token"):
        result["trackable_token"] = query["trackable_token"][0]
    return result


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def extract_recommendation_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        raise ValueError("recommendation JSON must be an object or array")

    for key in CONTAINER_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]

    raise ValueError("recommendation JSON must contain one of: " + ", ".join(CONTAINER_KEYS))


def _source_for_candidate(db: TalentDB, candidate_id: int | None) -> dict[str, Any] | None:
    if candidate_id is None:
        return None
    row = db._conn.execute(
        """
        SELECT platform_id, profile_url, raw_profile
        FROM source_profiles
        WHERE candidate_id = ?
          AND platform = 'maimai'
        ORDER BY id
        LIMIT 1
        """,
        (candidate_id,),
    ).fetchone()
    if not row:
        return None
    raw_profile = None
    if row["raw_profile"]:
        try:
            raw_profile = json.loads(row["raw_profile"])
        except json.JSONDecodeError:
            raw_profile = None
    return {
        "platform_id": row["platform_id"],
        "profile_url": row["profile_url"],
        "raw_profile": raw_profile,
    }


def _candidate_summary(db: TalentDB, candidate_id: int | None) -> dict[str, Any]:
    if candidate_id is None:
        return {}
    candidate = db.get(candidate_id)
    if candidate is None:
        return {}
    return {
        "name": candidate.name,
        "company": candidate.current_company or "",
        "position": candidate.current_title or "",
    }


def _candidate_id(value: Any) -> int | None:
    try:
        return int(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def contact_from_item(db: TalentDB, item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidate_id = _candidate_id(item.get("candidate_id"))
    source = _source_for_candidate(db, candidate_id)
    summary = _candidate_summary(db, candidate_id)

    profile_url = _first(
        item.get("profile_url"),
        item.get("detail_url"),
        item.get("url"),
        source.get("profile_url") if source else None,
    )
    parsed_url = parse_maimai_profile_url(profile_url)
    raw_profile = source.get("raw_profile") if source else None
    raw_source = raw_profile.get("_source") if isinstance(raw_profile, dict) else {}

    platform_id = _first(
        item.get("platform_id"),
        item.get("maimai_id"),
        item.get("uid"),
        item.get("id"),
        item.get("dstu"),
        parsed_url.get("id"),
        source.get("platform_id") if source else None,
        raw_source.get("platform_id") if isinstance(raw_source, dict) else None,
    )
    token = _first(
        item.get("trackable_token"),
        item.get("trackableToken"),
        parsed_url.get("trackable_token"),
        raw_profile.get("trackable_token") if isinstance(raw_profile, dict) else None,
    )

    if not platform_id:
        return None, {
            "candidate_id": candidate_id,
            "name": item.get("name") or summary.get("name") or "",
            "reason": "missing_maimai_platform_id",
        }

    contact = {
        "id": str(platform_id),
        "trackable_token": str(token or ""),
        "name": str(_first(item.get("name"), summary.get("name"), "")),
        "company": str(_first(item.get("company"), item.get("current_company"), summary.get("company"), "")),
        "position": str(_first(item.get("position"), item.get("title"), item.get("current_title"), summary.get("position"), "")),
        "candidate_id": candidate_id,
        "detail_url": str(profile_url or f"https://maimai.cn/u/{platform_id}"),
    }
    return contact, None


def _items_from_candidate_ids(candidate_ids: list[int]) -> list[dict[str, Any]]:
    return [{"candidate_id": candidate_id} for candidate_id in candidate_ids]


def _dedupe_contacts(contacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for contact in contacts:
        key = str(contact["id"])
        if key in seen:
            continue
        seen.add(key)
        result.append(contact)
    return result


def export_targets(
    db_path: str | Path,
    out_path: str | Path,
    recommendation_file: str | Path | None = None,
    candidate_ids: list[int] | None = None,
    allow_empty_candidate_ids: bool = False,
) -> dict[str, Any]:
    if recommendation_file is None and candidate_ids is None:
        raise ValueError("recommendation_file or candidate_ids is required")
    if recommendation_file is None and candidate_ids == [] and not allow_empty_candidate_ids:
        raise ValueError("candidate_ids must not be empty")

    if recommendation_file is not None:
        data = _load_json(Path(recommendation_file))
        items = extract_recommendation_items(data)
        source_file = str(recommendation_file)
    else:
        items = _items_from_candidate_ids(candidate_ids)
        source_file = ""

    db = TalentDB(db_path)
    try:
        contacts: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for item in items:
            contact, miss = contact_from_item(db, item)
            if contact:
                contacts.append(contact)
            if miss:
                missing.append(miss)
    finally:
        db.close()

    contacts = _dedupe_contacts(contacts)
    result = {
        "exportTime": datetime.now().isoformat(timespec="seconds"),
        "metadata": {
            "export_type": "maimai_detail_targets",
            "source_type": "talent_recommendation",
            "source_file": source_file,
            "total_input": len(items),
            "total_contacts": len(contacts),
            "missing": len(missing),
        },
        "contacts": contacts,
        "totalContacts": len(contacts),
        "missing": missing,
    }

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def _parse_ids(value: str) -> list[int]:
    ids: list[int] = []
    for part in value.split(","):
        part = part.strip()
        if part:
            ids.append(int(part))
    return ids


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 maimai-scraper 批量详情联系人输入 JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_file = subparsers.add_parser("from-file")
    from_file.add_argument("--input", required=True)
    from_file.add_argument("--db", default="data/talent.db")
    from_file.add_argument("--out", required=True)

    from_ids = subparsers.add_parser("from-ids")
    from_ids.add_argument("--ids", required=True, help="逗号分隔的 candidate_id 列表")
    from_ids.add_argument("--db", default="data/talent.db")
    from_ids.add_argument("--out", required=True)

    from_review = subparsers.add_parser("from-review")
    from_review.add_argument("--review", required=True)
    from_review.add_argument("--db", default="data/talent.db")
    from_review.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    if args.command == "from-file":
        result = export_targets(args.db, args.out, recommendation_file=args.input)
    elif args.command == "from-review":
        decisions = load_review_decisions(args.review)
        result = export_targets(
            args.db,
            args.out,
            candidate_ids=decisions.detail_candidate_ids,
            allow_empty_candidate_ids=True,
        )
    else:
        result = export_targets(args.db, args.out, candidate_ids=_parse_ids(args.ids))
    print(json.dumps(result["metadata"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
