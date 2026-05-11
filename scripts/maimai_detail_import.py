"""脉脉批量详情导出入库工具。"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.platform_match.adapters.maimai import MaimaiAdapter
from scripts.talent_db import TalentDB


CONFIRM_TEXT = "确认写入脉脉详情"


@dataclass(frozen=True)
class DetailEntry:
    platform_id: str
    payload: dict[str, Any]
    raw_entry: dict[str, Any]
    mode: str
    record_url: str = ""
    record_id: str = ""
    endpoints: dict[str, Any] | None = None


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("capture file must be a JSON object")
    return data


def _unwrap_data(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("data"), dict):
        return value["data"]
    return value


def _payload_from_job(job: dict[str, Any]) -> dict[str, Any] | None:
    detail = job.get("detail") or {}
    basic = _unwrap_data(detail.get("basic"))
    if not isinstance(basic, dict):
        return None

    payload = dict(basic)
    projects = _unwrap_data(detail.get("projects"))
    if isinstance(projects, dict):
        project_items = (
            projects.get("list")
            or projects.get("items")
            or projects.get("projects")
            or projects.get("data")
        )
        if project_items and not payload.get("user_project"):
            payload["user_project"] = project_items
    elif isinstance(projects, list) and not payload.get("user_project"):
        payload["user_project"] = projects

    job_preferences = _unwrap_data(detail.get("job_preference"))
    if isinstance(job_preferences, dict) and not payload.get("job_preferences"):
        payload["job_preferences"] = job_preferences
    return payload


def _payload_from_detail(detail: dict[str, Any]) -> dict[str, Any] | None:
    payload = _unwrap_data(detail.get("data"))
    if isinstance(payload, dict):
        return dict(payload)
    return None


def extract_detail_entries(capture: dict[str, Any], capture_file: Path) -> tuple[list[DetailEntry], int]:
    if "detailJobs" not in capture and "details" not in capture:
        raise ValueError("capture file must contain details or detailJobs")

    mode = (capture.get("metadata") or {}).get("detail_mode") or "unknown"
    entries: list[DetailEntry] = []
    failed_jobs = 0

    for job in capture.get("detailJobs") or []:
        if not isinstance(job, dict):
            continue
        if job.get("status") == "failed":
            failed_jobs += 1
            continue
        platform_id = str(job.get("id") or "")
        payload = _payload_from_job(job)
        if not platform_id or not payload:
            continue
        if not payload.get("id"):
            payload["id"] = platform_id
        entries.append(
            DetailEntry(
                platform_id=platform_id,
                payload=payload,
                raw_entry=job,
                mode=mode,
                record_url="",
                record_id=str(job.get("id") or ""),
                endpoints=job.get("detail") or {},
            )
        )

    existing_ids = {entry.platform_id for entry in entries}
    for detail in capture.get("details") or []:
        if not isinstance(detail, dict):
            continue
        platform_id = str(detail.get("id") or "")
        if not platform_id or platform_id in existing_ids:
            continue
        payload = _payload_from_detail(detail)
        if not payload:
            continue
        if not payload.get("id"):
            payload["id"] = platform_id
        entries.append(
            DetailEntry(
                platform_id=platform_id,
                payload=payload,
                raw_entry=detail,
                mode=detail.get("mode") or mode,
                record_url=detail.get("url") or "",
                record_id=str(detail.get("recordId") or detail.get("id") or ""),
                endpoints=detail.get("endpoints") or {},
            )
        )

    return entries, failed_jobs


def _find_candidate(db: TalentDB, platform_id: str) -> dict[str, Any] | None:
    row = db._conn.execute(
        """
        SELECT source_profiles.candidate_id, source_profiles.profile_url, candidates.name
        FROM source_profiles
        JOIN candidates ON candidates.id = source_profiles.candidate_id
        WHERE source_profiles.platform = 'maimai'
          AND source_profiles.platform_id = ?
        """,
        (platform_id,),
    ).fetchone()
    return dict(row) if row else None


def _detail_counts(detail: Any) -> dict[str, int]:
    if detail is None:
        return {"work": 0, "education": 0, "project": 0}
    return {
        "work": len(detail.work_experience or ()),
        "education": len(detail.education_experience or ()),
        "project": len(detail.project_experience or ()),
    }


def _mapped_detail(entry: DetailEntry, capture_file: Path) -> dict[str, Any]:
    mapped = MaimaiAdapter().map_to_schema(entry.payload)
    raw_data = {
        "maimai_detail_capture": {
            "capture_file": str(capture_file),
            "platform_id": entry.platform_id,
            "record_url": entry.record_url,
            "record_id": entry.record_id,
            "mode": entry.mode,
            "endpoints": entry.endpoints or {},
            "payload": entry.payload,
            "raw_entry": entry.raw_entry,
        }
    }
    return {
        "work_experience": mapped.get("work_experience", []),
        "education_experience": mapped.get("education_experience", []),
        "project_experience": mapped.get("project_experience", []),
        "summary": mapped.get("summary", ""),
        "raw_data": raw_data,
    }


def _default_report_path(kind: str) -> Path:
    return Path("data") / "output" / f"talent-detail-{date.today().isoformat()}-maimai-batch-{kind}.md"


def _default_result_path() -> Path:
    return Path("data") / "output" / f"talent-detail-{date.today().isoformat()}-maimai-batch-result.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_report(path: Path, title: str, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# {title}",
        "",
        f"- 匹配人数：{result['matched']}",
        f"- 未匹配人数：{result['unmatched']}",
        f"- 失败 jobs：{result['failed_jobs']}",
        f"- 写入人数：{result.get('written', 0)}",
        "",
        "## 明细",
        "",
    ]
    for item in result.get("matches", []):
        lines.append(
            "- {name} (`{platform_id}`): work {old_work}->{new_work}, "
            "edu {old_education}->{new_education}, project {old_project}->{new_project}".format(**item)
        )
    for item in result.get("unmatched_entries", []):
        lines.append(f"- 未匹配 `{item['platform_id']}`")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def build_dry_run(capture_file: Path, db_path: Path) -> dict[str, Any]:
    capture_file = Path(capture_file)
    capture = _load_json(capture_file)
    entries, failed_jobs = extract_detail_entries(capture, capture_file)
    db = TalentDB(db_path)
    try:
        matches = []
        unmatched_entries = []
        for entry in entries:
            candidate = _find_candidate(db, entry.platform_id)
            if not candidate:
                unmatched_entries.append({"platform_id": entry.platform_id})
                continue
            current_detail = db.get_detail(int(candidate["candidate_id"]))
            old_counts = _detail_counts(current_detail)
            mapped = _mapped_detail(entry, capture_file)
            new_counts = {
                "work": len(mapped["work_experience"] or []),
                "education": len(mapped["education_experience"] or []),
                "project": len(mapped["project_experience"] or []),
            }
            matches.append(
                {
                    "candidate_id": int(candidate["candidate_id"]),
                    "name": candidate["name"],
                    "platform_id": entry.platform_id,
                    "profile_url": candidate.get("profile_url") or "",
                    "old_work": old_counts["work"],
                    "new_work": new_counts["work"],
                    "old_education": old_counts["education"],
                    "new_education": new_counts["education"],
                    "old_project": old_counts["project"],
                    "new_project": new_counts["project"],
                    "detail_data": mapped,
                }
            )

        return {
            "capture_file": str(capture_file),
            "matched": len(matches),
            "unmatched": len(unmatched_entries),
            "failed_jobs": failed_jobs,
            "matches": matches,
            "unmatched_entries": unmatched_entries,
        }
    finally:
        db.close()


def dry_run_capture(capture_file: str | Path, db_path: str | Path, out: str | Path | None = None) -> dict[str, Any]:
    report_path = Path(out) if out else _default_report_path("dry-run")
    result = build_dry_run(Path(capture_file), Path(db_path))
    _write_report(report_path, "脉脉批量详情 dry-run", result)
    json_path = report_path.with_suffix(".json")
    _write_json(json_path, result)
    return result


def apply_capture(
    capture_file: str | Path,
    db_path: str | Path,
    report_path: str | Path | None = None,
    result_path: str | Path | None = None,
    confirm: str = "",
) -> dict[str, Any]:
    if confirm != CONFIRM_TEXT:
        raise ValueError(f"apply requires confirm text: {CONFIRM_TEXT}")

    capture_path = Path(capture_file)
    db_file = Path(db_path)
    result = build_dry_run(capture_path, db_file)
    db = TalentDB(db_file)
    written = 0
    verified: list[int] = []
    try:
        for item in result["matches"]:
            candidate_id = int(item["candidate_id"])
            db.enrich(candidate_id, item["detail_data"])
            detail = db.get_detail(candidate_id)
            candidate = db.get(candidate_id)
            if (
                detail is None
                or candidate is None
                or candidate.data_level != "detailed"
                or "maimai_detail_capture" not in (detail.raw_data or {})
            ):
                raise RuntimeError(f"detail verification failed for candidate {candidate_id}")
            written += 1
            verified.append(candidate_id)
    finally:
        db.close()

    result["written"] = written
    result["verified_candidate_ids"] = verified
    report = Path(report_path) if report_path else _default_report_path("result")
    output_json = Path(result_path) if result_path else _default_result_path()
    _write_report(report, "脉脉批量详情写入结果", result)
    _write_json(output_json, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脉脉批量详情导出 dry-run/apply 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--capture-file", required=True)
    dry.add_argument("--db", default="data/talent.db")
    dry.add_argument("--out")

    apply_parser = subparsers.add_parser("apply")
    apply_parser.add_argument("--capture-file", required=True)
    apply_parser.add_argument("--db", default="data/talent.db")
    apply_parser.add_argument("--out")
    apply_parser.add_argument("--json-out")
    apply_parser.add_argument("--confirm", required=True)

    args = parser.parse_args(argv)
    if args.command == "dry-run":
        result = dry_run_capture(args.capture_file, args.db, args.out)
    else:
        result = apply_capture(args.capture_file, args.db, args.out, args.json_out, args.confirm)
    print(json.dumps({k: v for k, v in result.items() if k != "matches"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
