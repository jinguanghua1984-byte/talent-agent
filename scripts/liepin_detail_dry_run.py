"""猎聘详情 raw 离线 dry-run。

只读取 campaign 本地 target pack 和 detail job raw，不连接浏览器，不发起猎聘请求，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_detail_live_gate import (  # noqa: E402
    DETAIL_JOB_SCHEMA,
    DETAIL_PACK_TARGET_SCHEMA,
    DETAIL_TARGET_SCHEMA,
    classify_detail_result,
    detail_job_path,
)
from scripts.talent_db import TalentDB  # noqa: E402


DRY_RUN_SCHEMA = "liepin_detail_dry_run_v1"
APPLY_SCHEMA = "liepin_detail_apply_v1"
CONFIRM_TEXT = "确认写入猎聘详情"
PACK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _relative_path(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _target_pack_path(campaign_root: str | Path, target_pack: str | Path) -> Path:
    pack_path = Path(target_pack)
    if pack_path.is_absolute():
        return pack_path
    return Path(campaign_root) / pack_path


def _validate_pack_id(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("pack_id must be a string")
    pack_id = value.strip()
    if not pack_id or pack_id != value or not PACK_ID_RE.fullmatch(pack_id):
        raise ValueError("pack_id contains unsafe characters")
    return pack_id


def _pack_id(plan: Mapping[str, Any], plan_path: Path) -> str:
    metadata = plan.get("metadata")
    if isinstance(metadata, Mapping) and metadata.get("pack_id"):
        return _validate_pack_id(metadata["pack_id"])
    if plan.get("pack_id"):
        return _validate_pack_id(plan["pack_id"])
    return _validate_pack_id(plan_path.stem)


def _validate_target_pack(plan: Any) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("target pack must be an object")
    if plan.get("schema") not in {DETAIL_TARGET_SCHEMA, DETAIL_PACK_TARGET_SCHEMA}:
        raise ValueError(f"target pack schema must be one of: {DETAIL_TARGET_SCHEMA}, {DETAIL_PACK_TARGET_SCHEMA}")
    contacts = plan.get("contacts")
    if not isinstance(contacts, list):
        raise ValueError("target pack contacts must be a list")
    return plan


def _contact_index(contact: Mapping[str, Any], fallback: int) -> int:
    raw_index = contact.get("index", fallback)
    if type(raw_index) is not int or raw_index < 0:
        raise ValueError(f"target pack contact {fallback} index must be a non-negative int")
    return raw_index


def _detail_request(job: Mapping[str, Any]) -> dict[str, Any]:
    requests = job.get("requests")
    if not isinstance(requests, list):
        return {}
    for request in reversed(requests):
        if isinstance(request, dict) and request.get("type") == "detail":
            return request
    for request in reversed(requests):
        if isinstance(request, dict):
            return request
    return {}


def _nested_detail_data(response_data: Any) -> dict[str, Any]:
    if not isinstance(response_data, dict):
        return {}
    nested = response_data.get("data")
    if isinstance(nested, dict):
        return nested
    return response_data


def _resume_detail_vo(response_data: Any) -> dict[str, Any]:
    detail_data = _nested_detail_data(response_data)
    resume = detail_data.get("resumeDetailVo")
    return resume if isinstance(resume, dict) else {}


def _captured_field_groups(response_data: Any) -> list[str]:
    detail_data = _nested_detail_data(response_data)
    if not isinstance(detail_data, dict):
        return []
    return sorted(str(key) for key in detail_data.keys())


def _detail_counts(resume: Mapping[str, Any]) -> dict[str, int]:
    def count_list(key: str) -> int:
        value = resume.get(key)
        return len(value) if isinstance(value, list) else 0

    return {
        "work": count_list("workExperiences"),
        "education": count_list("eduExperiences"),
        "project": count_list("projectExperiences"),
    }


def _load_detail_job_for_match(paths: Any, pack_id: str, match: Mapping[str, Any]) -> dict[str, Any]:
    raw_path = paths.root / str(match.get("raw_path") or "")
    if not raw_path.exists():
        raise RuntimeError(f"detail raw does not exist: {raw_path}")
    job = _load_json(raw_path)
    if not isinstance(job, dict):
        raise RuntimeError(f"detail raw is not an object: {raw_path}")
    return job


def _map_liepin_experience_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [dict(item) for item in items if isinstance(item, dict)]


def _detail_data_from_job(job: Mapping[str, Any], match: Mapping[str, Any], pack_id: str) -> dict[str, Any]:
    request = _detail_request(job)
    response_data = request.get("data")
    resume = _resume_detail_vo(response_data)
    nested = _nested_detail_data(response_data)
    return {
        "work_experience": _map_liepin_experience_items(resume.get("workExperiences")),
        "education_experience": _map_liepin_experience_items(resume.get("eduExperiences")),
        "project_experience": _map_liepin_experience_items(resume.get("projectExperiences")),
        "summary": "",
        "raw_data": {
            "liepin_detail_capture": {
                "platform_id": str(match.get("platform_id") or ""),
                "pack_id": pack_id,
                "job_index": match.get("job_index"),
                "raw_path": match.get("raw_path"),
                "captured_field_groups": match.get("captured_field_groups") or [],
                "detail_counts": match.get("detail_counts") or {},
                "resumeDetailVo": resume,
                "resumeAnalysisModelVo": nested.get("resumeAnalysisModelVo") if isinstance(nested, dict) else None,
            }
        },
    }


def _apply_blockers_for_match(match: Mapping[str, Any]) -> list[str]:
    counts = match.get("detail_counts") if isinstance(match.get("detail_counts"), dict) else {}
    blockers: list[str] = []
    if int(counts.get("work") or 0) == 0:
        blockers.append("missing_work_experience")
    if "resumeDetailVo" not in set(match.get("captured_field_groups") or []):
        blockers.append("missing_resume_detail")
    return blockers


def _job_indexes(job_dir: Path) -> set[int]:
    indexes: set[int] = set()
    for path in job_dir.glob("job-*.json"):
        try:
            indexes.add(int(path.stem.rsplit("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return indexes


def build_detail_dry_run(campaign_root: str | Path, target_pack: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    plan_path = _target_pack_path(paths.root, target_pack)
    plan = _validate_target_pack(_load_json(plan_path))
    pack_id = _pack_id(plan, plan_path)
    contacts = [contact for contact in plan["contacts"] if isinstance(contact, dict)]
    job_dir = paths.raw_dir / "detail-live" / pack_id

    matches: list[dict[str, Any]] = []
    privacy_protected: list[dict[str, Any]] = []
    missing_raw: list[dict[str, Any]] = []
    failed_jobs: list[dict[str, Any]] = []
    capture_blockers: list[dict[str, Any]] = []
    apply_blockers: list[dict[str, Any]] = []
    target_indexes: set[int] = set()

    for fallback, contact in enumerate(contacts):
        job_index = _contact_index(contact, fallback)
        target_indexes.add(job_index)
        platform_id = str(contact.get("platform_id") or "")
        raw_path = detail_job_path(job_dir, job_index)
        target_ref = {
            "job_index": job_index,
            "platform_id": platform_id,
        }
        if not raw_path.exists():
            missing_raw.append({**target_ref, "reason": "missing_raw"})
            continue

        try:
            job = _load_json(raw_path)
        except json.JSONDecodeError as exc:
            capture_blockers.append({**target_ref, "reason": "invalid_json", "message": exc.msg})
            continue
        if not isinstance(job, dict):
            capture_blockers.append({**target_ref, "reason": "job_not_object"})
            continue
        if job.get("schema") != DETAIL_JOB_SCHEMA:
            capture_blockers.append({**target_ref, "reason": "schema_mismatch", "schema": job.get("schema")})
            continue

        job_platform_id = str(job.get("platform_id") or "")
        if job_platform_id != platform_id:
            capture_blockers.append(
                {
                    **target_ref,
                    "reason": "platform_id_mismatch",
                    "job_platform_id": job_platform_id,
                }
            )
            continue

        status = str(job.get("status") or "")
        request = _detail_request(job)
        response = {
            "httpStatus": request.get("httpStatus"),
            "contentType": request.get("contentType"),
            "parseError": request.get("parseError"),
            "rawPreview": request.get("rawPreview"),
            "data": request.get("data"),
        }

        if status == "privacy_protected":
            privacy_protected.append({**target_ref, "raw_path": _relative_path(raw_path, paths.root)})
            continue
        if status != "done":
            failed_jobs.append({**target_ref, "status": status or "unknown", "raw_path": _relative_path(raw_path, paths.root)})
            continue

        reason = classify_detail_result(response)
        if reason:
            capture_blockers.append({**target_ref, "reason": reason, "raw_path": _relative_path(raw_path, paths.root)})
            continue

        response_data = request.get("data")
        resume = _resume_detail_vo(response_data)
        match = {
            **target_ref,
            "raw_path": _relative_path(raw_path, paths.root),
            "captured_field_groups": _captured_field_groups(response_data),
            "detail_counts": _detail_counts(resume),
            "ready_for_campaign_db": True,
        }
        blockers = _apply_blockers_for_match(match)
        if blockers:
            match["ready_for_campaign_db"] = False
            match["apply_blockers"] = blockers
            apply_blockers.append({**target_ref, "blockers": blockers})
        matches.append(match)

    unexpected_raw = [
        {"job_index": index, "reason": "unexpected_raw"}
        for index in sorted(_job_indexes(job_dir) - target_indexes)
    ]
    clean = not (missing_raw or unexpected_raw or failed_jobs or capture_blockers or apply_blockers)
    ready_count = sum(1 for match in matches if match.get("ready_for_campaign_db") is True)
    return {
        "schema": DRY_RUN_SCHEMA,
        "mode": "dry-run",
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "target_pack": _relative_path(plan_path, paths.root),
        "target_count": len(contacts),
        "job_count": len(_job_indexes(job_dir)),
        "matched": len(matches),
        "ready_for_campaign_db_count": ready_count,
        "privacy_protected_count": len(privacy_protected),
        "missing_raw_count": len(missing_raw),
        "unexpected_raw_count": len(unexpected_raw),
        "failed_job_count": len(failed_jobs),
        "capture_blocker_count": len(capture_blockers),
        "apply_blocker_count": len(apply_blockers),
        "clean": clean,
        "no_database_write": True,
        "matches": matches,
        "privacy_protected": privacy_protected,
        "missing_raw": missing_raw,
        "unexpected_raw": unexpected_raw,
        "failed_jobs": failed_jobs,
        "capture_blockers": capture_blockers,
        "apply_blockers": apply_blockers,
        "generatedAt": _now(),
    }


def _summary_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# 猎聘详情 raw dry-run",
        "",
        f"- campaign：{result['campaign_id']}",
        f"- target pack：{result['pack_id']}",
        f"- target 数：{result['target_count']}",
        f"- 可进入 Campaign DB apply 的详情数：{result['ready_for_campaign_db_count']}",
        f"- 隐私保护：{result['privacy_protected_count']}",
        f"- 缺 raw：{result['missing_raw_count']}",
        f"- 失败 job：{result['failed_job_count']}",
        f"- capture blockers：{result['capture_blocker_count']}",
        f"- apply blockers：{result['apply_blocker_count']}",
        f"- clean：{str(result['clean']).lower()}",
        f"- no database write：{str(result['no_database_write']).lower()}",
        "",
    ]
    if result.get("capture_blockers"):
        lines.extend(["## Capture blockers", ""])
        for item in result["capture_blockers"]:
            lines.append(f"- job-{item['job_index']:03d} `{item['platform_id']}`：{item['reason']}")
        lines.append("")
    if result.get("apply_blockers"):
        lines.extend(["## Apply blockers", ""])
        for item in result["apply_blockers"]:
            lines.append(f"- job-{item['job_index']:03d} `{item['platform_id']}`：{', '.join(item['blockers'])}")
        lines.append("")
    return "\n".join(lines)


def dry_run_detail_jobs(campaign_root: str | Path, target_pack: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    result = build_detail_dry_run(paths.root, target_pack)
    atomic_write_json(paths.reports_dir / "detail-dry-run.json", result)
    (paths.reports_dir / "detail-dry-run.md").write_text(_summary_markdown(result), encoding="utf-8")
    return result


def _find_campaign_candidate_id(db: TalentDB, platform_id: str) -> int | None:
    row = db._conn.execute(
        """
        SELECT candidate_id
        FROM source_profiles
        WHERE platform = 'liepin'
          AND platform_id = ?
        ORDER BY id
        LIMIT 1
        """,
        (platform_id,),
    ).fetchone()
    return int(row["candidate_id"]) if row is not None else None


def _apply_summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# 猎聘详情 apply",
        "",
        f"- campaign：{summary['campaign_id']}",
        f"- target pack：{summary['pack_id']}",
        f"- matched：{summary['matched']}",
        f"- written：{summary['written']}",
        f"- unmatched：{summary['unmatched']}",
        f"- privacy protected：{summary['privacy_protected_count']}",
        f"- no main db write：{str(summary['no_main_db_write']).lower()}",
        "",
    ]
    if summary.get("unmatched_entries"):
        lines.extend(["## Unmatched", ""])
        for item in summary["unmatched_entries"]:
            lines.append(f"- `{item['platform_id']}`")
        lines.append("")
    return "\n".join(lines)


def apply_detail_jobs(campaign_root: str | Path, target_pack: str | Path, confirm: str = "") -> dict[str, Any]:
    if confirm != CONFIRM_TEXT:
        raise ValueError(f"apply requires confirm text: {CONFIRM_TEXT}")
    paths = ensure_campaign(campaign_root)
    db_path = paths.root / "talent.db"
    if not db_path.exists():
        raise RuntimeError("campaign db does not exist; run import-search-apply first")

    dry_run = build_detail_dry_run(paths.root, target_pack)
    if not dry_run.get("clean"):
        raise RuntimeError("detail dry-run is not clean")

    db = TalentDB(db_path)
    written = 0
    unmatched_entries: list[dict[str, Any]] = []
    verified_candidate_ids: list[int] = []
    try:
        for match in dry_run["matches"]:
            if not match.get("ready_for_campaign_db"):
                continue
            platform_id = str(match.get("platform_id") or "")
            candidate_id = _find_campaign_candidate_id(db, platform_id)
            if candidate_id is None:
                unmatched_entries.append({"platform_id": platform_id, "job_index": match.get("job_index")})
                continue
            job = _load_detail_job_for_match(paths, str(dry_run["pack_id"]), match)
            detail_data = _detail_data_from_job(job, match, str(dry_run["pack_id"]))
            db._enrich_no_commit(candidate_id, detail_data)
            detail = db.get_detail(candidate_id)
            candidate = db.get(candidate_id)
            if (
                detail is None
                or candidate is None
                or candidate.data_level != "detailed"
                or "liepin_detail_capture" not in (detail.raw_data or {})
            ):
                raise RuntimeError(f"detail verification failed for candidate {candidate_id}")
            written += 1
            verified_candidate_ids.append(candidate_id)
        db._conn.commit()
    except Exception:
        db._conn.rollback()
        raise
    finally:
        db.close()

    summary = {
        "schema": APPLY_SCHEMA,
        "mode": "apply",
        "campaign_id": paths.campaign_id,
        "pack_id": dry_run["pack_id"],
        "target_pack": dry_run["target_pack"],
        "matched": dry_run["ready_for_campaign_db_count"],
        "written": written,
        "unmatched": len(unmatched_entries),
        "privacy_protected_count": dry_run["privacy_protected_count"],
        "verified_candidate_ids": verified_candidate_ids,
        "unmatched_entries": unmatched_entries,
        "no_main_db_write": True,
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-apply.json", summary)
    (paths.reports_dir / "detail-apply.md").write_text(_apply_summary_markdown(summary), encoding="utf-8")
    from scripts.liepin_campaign import append_jsonl  # local import avoids widening module API

    append_jsonl(
        paths.state_dir / "import-ledger.jsonl",
        {
            "action": "detail_apply",
            "status": "completed",
            "pack_id": dry_run["pack_id"],
            "matched": dry_run["ready_for_campaign_db_count"],
            "written": written,
            "unmatched": len(unmatched_entries),
            "privacy_protected_count": dry_run["privacy_protected_count"],
            "ts": _now(),
        },
    )
    return summary


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="猎聘详情 raw 离线 dry-run/apply。")
    subparsers = parser.add_subparsers(dest="command")
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--campaign-root", required=True)
    dry.add_argument("--target-pack", required=True)
    apply = subparsers.add_parser("apply")
    apply.add_argument("--campaign-root", required=True)
    apply.add_argument("--target-pack", required=True)
    apply.add_argument("--confirm", default="")
    parser.add_argument("--campaign-root", required=False)
    parser.add_argument("--target-pack", required=False)
    parsed = parser.parse_args(argv)
    if parsed.command is None:
        if not parsed.campaign_root or not parsed.target_pack:
            parser.error("--campaign-root and --target-pack are required")
        parsed.command = "dry-run"
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "dry-run":
            result = dry_run_detail_jobs(args.campaign_root, args.target_pack)
        elif args.command == "apply":
            result = apply_detail_jobs(args.campaign_root, args.target_pack, confirm=args.confirm)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
