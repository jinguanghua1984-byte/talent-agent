"""生成 AI Infra V2 A/B 档脉脉详情抓取任务包。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_detail_targets import parse_maimai_profile_url


SOURCE_GRADES = ("A", "B")
DEFAULT_WAVES = [f"wave-{index:03d}" for index in range(1, 13)]
GRADE_RANK = {"A": 0, "B": 1}


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _review_path(review_dir: Path, wave: str) -> Path:
    return review_dir / f"initial-human-review-draft-{wave}.json"


def _missing_review_files(review_dir: Path, waves: list[str]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for wave in waves:
        path = _review_path(review_dir, wave)
        if not path.exists():
            missing.append(
                {
                    "wave_id": wave,
                    "path": str(path),
                    "reason": "missing_review_file",
                }
            )
    return missing


def _review_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [item for item in data["items"] if isinstance(item, dict)]
    return []


def _candidate_id(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _score(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _wave_order(wave_id: Any) -> int:
    if isinstance(wave_id, str) and wave_id.startswith("wave-"):
        try:
            return int(wave_id.rsplit("-", 1)[1])
        except ValueError:
            pass
    return 9999


def _grade_rank(grade: Any) -> int:
    return GRADE_RANK.get(str(grade), 99)


def _item_strength_key(item: dict[str, Any]) -> tuple[int, float, int, int]:
    candidate_id = _candidate_id(item.get("candidate_id")) or 0
    return (
        _grade_rank(item.get("grade")),
        -_score(item.get("score")),
        _wave_order(item.get("wave_id")),
        candidate_id,
    )


def _target_sort_key(contact: dict[str, Any]) -> tuple[int, float, int, int]:
    candidate_id = _candidate_id(contact.get("candidate_id")) or 0
    return (
        _grade_rank(contact.get("grade")),
        -_score(contact.get("score")),
        _wave_order(contact.get("wave_id")),
        candidate_id,
    )


def collect_review_items(review_dir: Path, waves: list[str], grades: set[str]) -> list[dict[str, Any]]:
    """Return review items whose grade is in grades, with wave_id attached."""

    collected: list[dict[str, Any]] = []
    for wave in waves:
        path = _review_path(review_dir, wave)
        if not path.exists():
            continue
        for item in _review_items(_load_json(path)):
            grade = str(item.get("grade") or "")
            if grade not in grades:
                continue
            enriched = dict(item)
            enriched["grade"] = grade
            enriched["wave_id"] = wave
            collected.append(enriched)
    return collected


def dedupe_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one strongest review item per candidate_id."""

    best_by_candidate: dict[int, dict[str, Any]] = {}
    for item in items:
        candidate_id = _candidate_id(item.get("candidate_id"))
        if candidate_id is None:
            continue
        normalized = dict(item)
        normalized["candidate_id"] = candidate_id
        current = best_by_candidate.get(candidate_id)
        if current is None or _item_strength_key(normalized) < _item_strength_key(current):
            best_by_candidate[candidate_id] = normalized
    return sorted(best_by_candidate.values(), key=_item_strength_key)


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


class ReadOnlyContactResolver:
    """只读解析 campaign DB 里的脉脉 source profile 和候选人摘要。"""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None
        if db_path.exists():
            uri = db_path.resolve().as_uri() + "?mode=ro"
            self._conn = sqlite3.connect(uri, uri=True)
            self._conn.row_factory = sqlite3.Row

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()

    def source_for_candidate(self, candidate_id: int | None) -> dict[str, Any] | None:
        if self._conn is None or candidate_id is None:
            return None
        row = self._conn.execute(
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
        if row is None:
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

    def candidate_summary(self, candidate_id: int | None) -> dict[str, str]:
        if self._conn is None or candidate_id is None:
            return {}
        row = self._conn.execute(
            """
            SELECT name, current_company, current_title
            FROM candidates
            WHERE id = ?
            """,
            (candidate_id,),
        ).fetchone()
        if row is None:
            return {}
        return {
            "name": row["name"] or "",
            "company": row["current_company"] or "",
            "position": row["current_title"] or "",
        }

    def contact_from_item(self, item: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        candidate_id = _candidate_id(item.get("candidate_id"))
        source = self.source_for_candidate(candidate_id)
        summary = self.candidate_summary(candidate_id)

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
            "company": str(
                _first(item.get("company"), item.get("current_company"), summary.get("company"), "")
            ),
            "position": str(
                _first(item.get("position"), item.get("title"), item.get("current_title"), summary.get("position"), "")
            ),
            "candidate_id": candidate_id,
            "detail_url": str(profile_url or f"https://maimai.cn/u/{platform_id}"),
        }
        return contact, None


def _contact_for_item(
    resolver: ReadOnlyContactResolver,
    item: dict[str, Any],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    contact, missing = resolver.contact_from_item(item)
    if missing:
        return None, missing
    if contact is None:
        return None, {
            "candidate_id": _candidate_id(item.get("candidate_id")),
            "name": str(item.get("name") or ""),
            "reason": "missing_maimai_platform_id",
        }
    if not contact.get("id"):
        return None, {
            "candidate_id": contact.get("candidate_id"),
            "name": contact.get("name") or "",
            "reason": "missing_maimai_platform_id",
        }
    if not contact.get("trackable_token"):
        return None, {
            "candidate_id": contact.get("candidate_id"),
            "name": contact.get("name") or "",
            "platform_id": contact.get("id"),
            "reason": "missing_trackable_token",
        }

    detail_url = str(contact.get("detail_url") or f"https://maimai.cn/u/{contact['id']}")
    if "trackable_token=" not in detail_url:
        separator = "&" if "?" in detail_url else "?"
        detail_url = f"{detail_url}{separator}trackable_token={contact['trackable_token']}"

    enriched = {
        **contact,
        "grade": item.get("grade"),
        "score": item.get("score", 0),
        "wave_id": item.get("wave_id"),
        "priority": item.get("priority") or ("P0" if item.get("grade") == "A" else "P1"),
        "detail_url": detail_url,
    }
    return enriched, None


def _pack_document(
    campaign_root: Path,
    pack_id: str,
    pack_index: int,
    pack_count: int,
    contacts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "metadata": {
            "export_type": "maimai_ai_infra_detail_pack",
            "campaign_root": str(campaign_root),
            "pack_id": pack_id,
            "pack_index": pack_index,
            "pack_count": pack_count,
            "source_grades": list(SOURCE_GRADES),
            "count": len(contacts),
        },
        "count": len(contacts),
        "contacts": contacts,
    }


def _remove_runnable_pack_files(out_dir: Path) -> None:
    for path in out_dir.glob("detail-ab-pack-*.json"):
        if path.is_file():
            path.unlink()


def build_ab_detail_packs(
    campaign_root: str | Path,
    db_path: str | Path | None = None,
    waves: list[str] | None = None,
    out_dir: str | Path | None = None,
    pack_count: int = 4,
) -> dict[str, Any]:
    """Write the A/B target manifest and pack files, then return the summary."""

    if pack_count <= 0:
        raise ValueError("pack_count must be positive")

    root = Path(campaign_root)
    db_file = Path(db_path) if db_path is not None else root / "talent.db"
    wave_ids = waves or DEFAULT_WAVES
    target_dir = Path(out_dir) if out_dir is not None else root / "raw" / "detail-targets"

    review_dir = root / "review"
    missing: list[dict[str, Any]] = _missing_review_files(review_dir, wave_ids)
    if not db_file.exists():
        missing.append(
            {
                "path": str(db_file),
                "reason": "missing_db_file",
            }
        )

    review_items = collect_review_items(review_dir, wave_ids, set(SOURCE_GRADES))
    unique_items = dedupe_review_items(review_items)

    resolver = ReadOnlyContactResolver(db_file)
    try:
        contacts: list[dict[str, Any]] = []
        if resolver._conn is not None:
            for item in unique_items:
                contact, miss = _contact_for_item(resolver, item)
                if contact is not None:
                    contacts.append(contact)
                if miss is not None:
                    missing.append(miss)
    finally:
        resolver.close()

    contacts.sort(key=_target_sort_key)
    status = "blocked" if missing else "ready"
    packs: list[dict[str, Any]] = []
    for pack_index in range(pack_count):
        pack_contacts = contacts[pack_index::pack_count] if status == "ready" else []
        pack_id = f"detail-ab-pack-{pack_index + 1:03d}"
        packs.append(_pack_document(root, pack_id, pack_index + 1, pack_count, pack_contacts))

    metadata = {
        "export_type": "maimai_ai_infra_detail_targets",
        "status": status,
        "campaign_root": str(root),
        "db_path": str(db_file),
        "source_grades": list(SOURCE_GRADES),
        "waves": wave_ids,
        "input_rows": len(review_items),
        "unique_targets": len(unique_items),
        "runnable_targets": len(contacts) if status == "ready" else 0,
        "missing": len(missing),
        "pack_count": pack_count,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    result = {
        "metadata": metadata,
        "contacts": contacts,
        "packs": packs,
        "missing": missing,
    }

    _write_json(target_dir / "detail-targets-ab-all.json", result)
    if status == "ready":
        for pack in packs:
            _write_json(target_dir / f"{pack['metadata']['pack_id']}.json", pack)
    else:
        _remove_runnable_pack_files(target_dir)

    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 AI Infra V2 A/B 档脉脉详情任务包")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-ab-packs")
    build.add_argument("--campaign-root", required=True)
    build.add_argument("--db-path")
    build.add_argument("--out-dir")
    build.add_argument("--pack-count", type=int, default=4)
    build.add_argument("--waves", nargs="*", help="默认 wave-001 到 wave-012")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "build-ab-packs":
        result = build_ab_detail_packs(
            campaign_root=args.campaign_root,
            db_path=args.db_path,
            waves=args.waves,
            out_dir=args.out_dir,
            pack_count=args.pack_count,
        )
        metadata = result["metadata"]
        pack_counts = ",".join(str(pack["metadata"]["count"]) for pack in result["packs"])
        print(
            "status={status} input_rows={input_rows} unique_targets={unique_targets} "
            "missing={missing} packs={packs}".format(
                status=metadata["status"],
                input_rows=metadata["input_rows"],
                unique_targets=metadata["unique_targets"],
                missing=metadata["missing"],
                packs=pack_counts,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
