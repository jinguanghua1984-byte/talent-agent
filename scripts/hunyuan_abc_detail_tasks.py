from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_detail_live_gate import run_gate
from scripts.maimai_ai_infra_pipeline import _detail_dry_run_status
from scripts.maimai_detail_import import dry_run_capture
from scripts.maimai_detail_targets import parse_maimai_profile_url


DEFAULT_RANK_SUMMARY = Path("data/output/hunyuan-8jd-main-db-match-2026-05-22/main-db-detailed-rank-summary.json")
DEFAULT_CAMPAIGN_ROOT = Path("data/campaigns/hunyuan-8jd-abc-detail-2026-05-22")
DEFAULT_DB_PATH = Path("data/talent.db")
GRADE_ORDER = {"A": 0, "B": 1, "C": 2}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _today() -> str:
    return datetime.now().date().isoformat()


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write_json(path: str | Path, data: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8-sig")


def _write_text(path: str | Path, text: str) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8-sig")


def _append_event(campaign_root: Path, event: dict[str, Any]) -> None:
    path = campaign_root / "state" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(event)
    record["at"] = _now()
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_stage_state(campaign_root: Path, stage: str, status: str, extra: dict[str, Any] | None = None) -> None:
    state = {
        "stage": stage,
        "status": status,
        "updated_at": _now(),
    }
    if extra:
        state.update(extra)
    _write_json(campaign_root / "state" / "stage-state.json", state)
    _append_event(campaign_root, state)


def _as_int(value: Any) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _grade_rank(value: Any) -> int:
    return GRADE_ORDER.get(str(value), 99)


def _best_source_key(source: dict[str, Any]) -> tuple[int, float, int]:
    return (
        _grade_rank(source.get("grade")),
        -_as_float(source.get("score")),
        int(source.get("rank_index") or 999999),
    )


def _target_sort_key(item: dict[str, Any]) -> tuple[int, float, int, int]:
    return (
        _grade_rank(item.get("best_grade")),
        -_as_float(item.get("best_score")),
        -int(item.get("source_role_count") or 0),
        int(item.get("candidate_id") or 0),
    )


def _first(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def _low_confidence_campaign(campaign_id: str) -> bool:
    return campaign_id.startswith("hunyuan-03-") or campaign_id.startswith("hunyuan-04-")


def _extract_rank_sources(rank_summary_path: Path, grades: set[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summary = _load_json(rank_summary_path)
    if not isinstance(summary, dict):
        raise ValueError("rank summary must be a JSON object")

    rows: list[dict[str, Any]] = []
    campaign_summaries: list[dict[str, Any]] = []
    for campaign in summary.get("campaigns") or []:
        if not isinstance(campaign, dict):
            continue
        campaign_id = str(campaign.get("campaign_id") or "")
        out_json = campaign.get("out_json")
        if not campaign_id or not out_json:
            continue
        rank_path = Path(out_json)
        rank = _load_json(rank_path)
        grade_map = rank.get("grades") if isinstance(rank, dict) else {}
        campaign_counts: dict[str, int] = {}
        for grade in sorted(grades, key=_grade_rank):
            items = grade_map.get(grade) if isinstance(grade_map, dict) else None
            if not isinstance(items, list):
                campaign_counts[grade] = 0
                continue
            campaign_counts[grade] = len(items)
            for rank_index, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    continue
                candidate_id = _as_int(item.get("candidate_id"))
                if candidate_id is None:
                    continue
                rows.append(
                    {
                        "candidate_id": candidate_id,
                        "campaign_id": campaign_id,
                        "grade": grade,
                        "score": _as_float(item.get("score")),
                        "rank_index": rank_index,
                        "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
                        "risk_flags": item.get("risk_flags") if isinstance(item.get("risk_flags"), list) else [],
                        "low_confidence_jd": _low_confidence_campaign(campaign_id),
                    }
                )
        campaign_summaries.append(
            {
                "campaign_id": campaign_id,
                "rank_json": str(rank_path),
                "counts": campaign_counts,
                "low_confidence_jd": _low_confidence_campaign(campaign_id),
            }
        )
    return rows, campaign_summaries


def _aggregate_sources(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_candidate: dict[int, dict[str, Any]] = {}
    for row in rows:
        candidate_id = int(row["candidate_id"])
        entry = by_candidate.setdefault(
            candidate_id,
            {
                "candidate_id": candidate_id,
                "sources": [],
            },
        )
        entry["sources"].append(row)

    targets: list[dict[str, Any]] = []
    for entry in by_candidate.values():
        sources = sorted(entry["sources"], key=_best_source_key)
        best = sources[0]
        target = {
            "candidate_id": entry["candidate_id"],
            "best_grade": best["grade"],
            "best_score": best["score"],
            "best_campaign_id": best["campaign_id"],
            "source_role_count": len({source["campaign_id"] for source in sources}),
            "source_grade_counts": {
                grade: sum(1 for source in sources if source.get("grade") == grade)
                for grade in GRADE_ORDER
            },
            "low_confidence_only": all(bool(source.get("low_confidence_jd")) for source in sources),
            "sources": sources,
        }
        targets.append(target)
    return sorted(targets, key=_target_sort_key)


class MainDbResolver:
    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(str(db_path))
        uri = db_path.resolve().as_uri() + "?mode=ro"
        self.conn = sqlite3.connect(uri, uri=True)
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def resolve(self, candidate_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            """
            SELECT
              candidates.id,
              candidates.name,
              candidates.current_company,
              candidates.current_title,
              candidates.data_level,
              source_profiles.platform_id,
              source_profiles.profile_url,
              source_profiles.raw_profile,
              candidate_details.raw_data
            FROM candidates
            LEFT JOIN source_profiles
              ON source_profiles.candidate_id = candidates.id
             AND source_profiles.platform = 'maimai'
            LEFT JOIN candidate_details
              ON candidate_details.candidate_id = candidates.id
            WHERE candidates.id = ?
            ORDER BY source_profiles.id
            LIMIT 1
            """,
            (candidate_id,),
        ).fetchone()
        return dict(row) if row else None


def _json_object(text: Any) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(str(text))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _has_detail_capture(raw_data: Any) -> bool:
    parsed = _json_object(raw_data)
    if "maimai_detail_capture" in parsed:
        return True
    return "maimai_detail_capture" in str(raw_data or "")


def _raw_source(raw_profile: Any) -> dict[str, Any]:
    parsed = _json_object(raw_profile)
    if isinstance(parsed.get("_source"), dict):
        return parsed["_source"]
    if isinstance(parsed.get("maimai_contact"), dict):
        return parsed["maimai_contact"]
    return parsed


def _token_from_raw(raw_profile: Any) -> str:
    raw = _raw_source(raw_profile)
    for key in ("trackable_token", "trackableToken", "trackable"):
        value = raw.get(key)
        if value:
            return str(value)
    detail_url = raw.get("detail_url") or raw.get("profile_url") or ""
    parsed = parse_maimai_profile_url(str(detail_url))
    return str(parsed.get("trackable_token") or "")


def _platform_id_from_raw(raw_profile: Any) -> str:
    raw = _raw_source(raw_profile)
    for key in ("platform_id", "id", "uid", "dstu", "to_uid"):
        value = raw.get(key)
        if value:
            return str(value)
    detail_url = raw.get("detail_url") or raw.get("profile_url") or ""
    parsed = parse_maimai_profile_url(str(detail_url))
    return str(parsed.get("id") or "")


def _detail_url(profile_url: str, platform_id: str, token: str) -> str:
    url = profile_url or f"https://maimai.cn/u/{platform_id}"
    if token and "trackable_token=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}trackable_token={token}"
    return url


def _priority(grade: str) -> str:
    if grade == "A":
        return "P0"
    if grade == "B":
        return "P1"
    return "P2"


def _enrich_targets(
    targets: list[dict[str, Any]],
    db_path: Path,
    include_existing_capture: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    manifest_items: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    resolver = MainDbResolver(db_path)
    try:
        for target in targets:
            candidate_id = int(target["candidate_id"])
            row = resolver.resolve(candidate_id)
            if row is None:
                item = {**target, "detail_task_status": "missing_db_candidate"}
                manifest_items.append(item)
                missing.append({"candidate_id": candidate_id, "reason": "missing_db_candidate"})
                continue

            raw_profile = row.get("raw_profile")
            platform_id = str(_first(row.get("platform_id"), _platform_id_from_raw(raw_profile), ""))
            parsed_url = parse_maimai_profile_url(row.get("profile_url"))
            platform_id = str(_first(platform_id, parsed_url.get("id"), ""))
            token = str(_first(parsed_url.get("trackable_token"), _token_from_raw(raw_profile), ""))
            has_capture = _has_detail_capture(row.get("raw_data"))
            base = {
                **target,
                "name": row.get("name") or "",
                "company": row.get("current_company") or "",
                "position": row.get("current_title") or "",
                "candidate_data_level": row.get("data_level") or "",
                "platform_id": platform_id,
                "profile_url": row.get("profile_url") or "",
                "has_maimai_detail_capture": has_capture,
                "priority": _priority(str(target.get("best_grade") or "")),
            }

            if not platform_id:
                item = {**base, "detail_task_status": "missing_maimai_platform_id"}
                manifest_items.append(item)
                missing.append({"candidate_id": candidate_id, "reason": "missing_maimai_platform_id"})
                continue
            if not token:
                item = {**base, "detail_task_status": "missing_trackable_token"}
                manifest_items.append(item)
                missing.append({"candidate_id": candidate_id, "platform_id": platform_id, "reason": "missing_trackable_token"})
                continue
            if has_capture and not include_existing_capture:
                item = {**base, "trackable_token": token, "detail_url": _detail_url(base["profile_url"], platform_id, token), "detail_task_status": "already_captured_skipped"}
                manifest_items.append(item)
                continue

            contact = {
                "id": platform_id,
                "trackable_token": token,
                "name": str(base["name"]),
                "company": str(base["company"]),
                "position": str(base["position"]),
                "candidate_id": candidate_id,
                "detail_url": _detail_url(base["profile_url"], platform_id, token),
                "grade": target.get("best_grade"),
                "score": target.get("best_score"),
                "priority": base["priority"],
                "best_campaign_id": target.get("best_campaign_id"),
                "source_role_count": target.get("source_role_count"),
                "source_grade_counts": target.get("source_grade_counts"),
                "low_confidence_only": target.get("low_confidence_only"),
            }
            item = {
                **base,
                "trackable_token": token,
                "detail_url": contact["detail_url"],
                "detail_task_status": "runnable",
            }
            manifest_items.append(item)
            runnable.append(contact)
    finally:
        resolver.close()

    runnable.sort(key=lambda item: (_grade_rank(item.get("grade")), -_as_float(item.get("score")), -int(item.get("source_role_count") or 0), int(item.get("candidate_id") or 0)))
    return manifest_items, runnable, missing


def _pack_document(campaign_root: Path, pack_id: str, pack_index: int, pack_count: int, contacts: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metadata": {
            "export_type": "hunyuan_8jd_abc_detail_pack",
            "compatible_with": "maimai_ai_infra_detail_live_gate",
            "campaign_root": str(campaign_root),
            "pack_id": pack_id,
            "pack_index": pack_index,
            "pack_count": pack_count,
            "source_grades": ["A", "B", "C"],
            "count": len(contacts),
            "main_db_write": "manual_only",
        },
        "count": len(contacts),
        "contacts": contacts,
    }


def _write_run_policy(campaign_root: Path, pack_size: int, include_existing_capture: bool) -> None:
    policy = {
        "campaign_id": campaign_root.name,
        "allow_detail_live_after_health_ok": True,
        "allow_detail_campaign_db_auto_apply_after_clean_dry_run": False,
        "allow_main_db_write": False,
        "main_db_sync_mode": "manual_only",
        "detail_target_grades": ["A", "B", "C"],
        "detail_pack_max_contacts": pack_size,
        "include_existing_maimai_detail_capture": include_existing_capture,
        "stop_on_platform_security_signal": True,
        "stop_conditions": ["login", "captcha", "security_page", "403", "429", "432", "non_json", "html_response", "template_drift", "partial_detail_capture"],
        "generated_at": _now(),
    }
    _write_json(campaign_root / "run-policy.json", policy)


def _write_manifest(campaign_root: Path, rank_summary: Path, db_path: Path, campaign_summaries: list[dict[str, Any]]) -> None:
    manifest = {
        "campaign_id": campaign_root.name,
        "purpose": "hunyuan_8jd_abc_detail_capture",
        "rank_summary": str(rank_summary),
        "db_path": str(db_path),
        "source_campaigns": campaign_summaries,
        "main_db_write": "manual_only",
        "generated_at": _now(),
    }
    _write_json(campaign_root / "campaign-manifest.json", manifest)


def _summary_markdown(metadata: dict[str, Any], pack_counts: list[int], missing: list[dict[str, Any]]) -> str:
    lines = [
        "# 混元 8JD ABC 详情抓取任务摘要",
        "",
        f"- 目标根目录：`{metadata['campaign_root']}`",
        f"- 主库：`{metadata['db_path']}`",
        f"- ABC 输入行：{metadata['input_rows']}",
        f"- ABC 去重候选人：{metadata['unique_abc_candidates']}",
        f"- 可执行详情目标：{metadata['runnable_targets']}",
        f"- 已有 maimai_detail_capture 跳过：{metadata['already_captured_skipped']}",
        f"- 缺失/不可执行：{metadata['missing']}",
        f"- pack 数：{metadata['pack_count']}，pack 上限：{metadata['pack_size']}",
        f"- 主库写入策略：{metadata['main_db_write']}",
        "",
        "## Pack 分布",
        "",
    ]
    for index, count in enumerate(pack_counts, start=1):
        lines.append(f"- detail-abc-pack-{index:03d}: {count}")
    if missing:
        lines.extend(["", "## 缺失原因", ""])
        reason_counts: dict[str, int] = {}
        for item in missing:
            reason = str(item.get("reason") or "unknown")
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
        for reason, count in sorted(reason_counts.items()):
            lines.append(f"- {reason}: {count}")
    lines.append("")
    return "\n".join(lines)


def build_tasks(
    rank_summary: Path,
    db_path: Path,
    campaign_root: Path,
    pack_size: int,
    include_existing_capture: bool,
) -> dict[str, Any]:
    rows, campaign_summaries = _extract_rank_sources(rank_summary, {"A", "B", "C"})
    targets = _aggregate_sources(rows)
    manifest_items, runnable, missing = _enrich_targets(targets, db_path, include_existing_capture)

    target_dir = campaign_root / "raw" / "detail-targets"
    target_dir.mkdir(parents=True, exist_ok=True)
    for old_pack in target_dir.glob("detail-abc-pack-*.json"):
        old_pack.unlink()

    pack_count = max(1, ceil(len(runnable) / pack_size)) if runnable else 0
    packs: list[dict[str, Any]] = []
    for index in range(pack_count):
        contacts = runnable[index * pack_size : (index + 1) * pack_size]
        pack_id = f"detail-abc-pack-{index + 1:03d}"
        pack = _pack_document(campaign_root, pack_id, index + 1, pack_count, contacts)
        packs.append(pack)
        _write_json(target_dir / f"{pack_id}.json", pack)

    already_captured = sum(1 for item in manifest_items if item.get("detail_task_status") == "already_captured_skipped")
    metadata = {
        "export_type": "hunyuan_8jd_abc_detail_targets",
        "campaign_root": str(campaign_root),
        "rank_summary": str(rank_summary),
        "db_path": str(db_path),
        "source_grades": ["A", "B", "C"],
        "input_rows": len(rows),
        "unique_abc_candidates": len(targets),
        "runnable_targets": len(runnable),
        "already_captured_skipped": already_captured,
        "missing": len(missing),
        "pack_size": pack_size,
        "pack_count": pack_count,
        "include_existing_maimai_detail_capture": include_existing_capture,
        "main_db_write": "manual_only",
        "generated_at": _now(),
    }
    all_targets = {
        "metadata": metadata,
        "targets": manifest_items,
        "contacts": runnable,
        "missing": missing,
    }
    pack_index = {
        "metadata": metadata,
        "packs": [
            {
                "pack_id": pack["metadata"]["pack_id"],
                "path": str(target_dir / f"{pack['metadata']['pack_id']}.json"),
                "count": pack["count"],
                "status": "pending",
            }
            for pack in packs
        ],
    }
    _write_run_policy(campaign_root, pack_size, include_existing_capture)
    _write_manifest(campaign_root, rank_summary, db_path, campaign_summaries)
    _write_json(target_dir / "detail-targets-abc-all.json", all_targets)
    _write_json(target_dir / "pack-index.json", pack_index)
    _write_text(campaign_root / "reports" / "detail-target-summary.md", _summary_markdown(metadata, [pack["count"] for pack in packs], missing))
    _write_stage_state(
        campaign_root,
        "detail_targets",
        "ready" if runnable else "blocked",
        {
            "target_manifest": str(target_dir / "detail-targets-abc-all.json"),
            "pack_index": str(target_dir / "pack-index.json"),
            "runnable_targets": len(runnable),
            "pack_count": pack_count,
            "main_db_write": "manual_only",
        },
    )
    return {"metadata": metadata, "pack_index": pack_index}


def _load_pack_index(campaign_root: Path) -> dict[str, Any]:
    path = campaign_root / "raw" / "detail-targets" / "pack-index.json"
    data = _load_json(path)
    if not isinstance(data, dict):
        raise ValueError("pack-index must be a JSON object")
    return data


def _completed_capture(capture_path: Path, expected_count: int) -> bool:
    if not capture_path.exists():
        return False
    data = _load_json(capture_path)
    metadata = data.get("metadata") if isinstance(data, dict) else {}
    if not isinstance(metadata, dict):
        return False
    return metadata.get("status") == "completed" and int(metadata.get("completed_jobs") or 0) >= expected_count


def run_unattended(
    campaign_root: Path,
    db_path: Path,
    cdp_url: str,
    delay_seconds: float,
    timeout_seconds: float,
    max_packs: int | None = None,
    start_pack: str | None = None,
    pack_ids: list[str] | None = None,
    runner_id: str = "",
) -> dict[str, Any]:
    pack_index = _load_pack_index(campaign_root)
    packs = [item for item in pack_index.get("packs") or [] if isinstance(item, dict)]
    if pack_ids:
        wanted = set(pack_ids)
        packs = [pack for pack in packs if str(pack.get("pack_id") or "") in wanted]
    if start_pack:
        started = False
        filtered = []
        for pack in packs:
            if pack.get("pack_id") == start_pack:
                started = True
            if started:
                filtered.append(pack)
        packs = filtered
    if max_packs is not None:
        packs = packs[: max(0, max_packs)]

    run_summary = {
        "campaign_root": str(campaign_root),
        "db_path": str(db_path),
        "cdp_url": cdp_url,
        "started_at": _now(),
        "main_db_write": "manual_only",
        "runner_id": runner_id or "default",
        "packs": [],
        "status": "running",
    }
    state_name = f"abc-detail-run-state-{runner_id}.json" if runner_id else "abc-detail-run-state.json"
    state_path = campaign_root / "state" / state_name
    _write_stage_state(
        campaign_root,
        "detail_live",
        "running",
        {
            "runner_id": runner_id or "default",
            "total_packs_in_scope": len(packs),
            "pack_ids": [str(pack.get("pack_id") or "") for pack in packs],
        },
    )

    for pack in packs:
        pack_id = str(pack.get("pack_id") or "")
        pack_path = Path(str(pack.get("path") or ""))
        expected_count = int(pack.get("count") or 0)
        capture_path = campaign_root / "raw" / f"detail-live-{pack_id}-run-{_today()}.json"
        report_path = campaign_root / "reports" / f"detail-wave-{pack_id}-dry-run.md"

        if _completed_capture(capture_path, expected_count):
            capture_status = "completed"
        else:
            gate_result = run_gate(
                plan_path=pack_path,
                out_path=capture_path,
                cdp_url=cdp_url,
                delay_seconds=delay_seconds,
                timeout_seconds=timeout_seconds,
            )
            capture_status = str(gate_result.get("status") or "")
            if capture_status != "completed":
                item = {
                    "pack_id": pack_id,
                    "status": capture_status,
                    "stopReason": gate_result.get("stopReason"),
                    "capture": str(capture_path),
                    "interruptionReport": gate_result.get("interruptionReport"),
                    "continuationPlan": gate_result.get("continuationPlan"),
                }
                run_summary["packs"].append(item)
                run_summary["status"] = "stopped"
                _write_json(state_path, run_summary)
                _write_stage_state(campaign_root, "detail_live", "blocked", item)
                return run_summary

        dry_result = dry_run_capture(capture_path, db_path, report_path)
        dry_status = _detail_dry_run_status(dry_result)
        item = {
            "pack_id": pack_id,
            "status": "completed",
            "capture": str(capture_path),
            "dry_run_status": dry_status,
            "dry_run_report": str(report_path),
            "dry_run_result": str(report_path.with_suffix(".json")),
            "matched": dry_result.get("matched", 0),
            "unmatched": dry_result.get("unmatched", 0),
            "failed_jobs": dry_result.get("failed_jobs", 0),
            "main_db_apply": "not_run_manual_only",
        }
        run_summary["packs"].append(item)
        _write_json(state_path, run_summary)
        _append_event(campaign_root, {"stage": "detail_dry_run", "runner_id": runner_id or "default", **item})
        if dry_status != "dry_run_clean":
            run_summary["status"] = "stopped"
            _write_json(state_path, run_summary)
            _write_stage_state(campaign_root, "detail_dry_run", "blocked", item)
            return run_summary

    run_summary["status"] = "completed"
    run_summary["finished_at"] = _now()
    _write_json(state_path, run_summary)
    if runner_id:
        _append_event(
            campaign_root,
            {
                "stage": "detail_live",
                "status": "runner_completed",
                "runner_id": runner_id,
                "completed_packs": len(run_summary["packs"]),
                "main_db_apply": "not_run_manual_only",
            },
        )
    else:
        _write_stage_state(
            campaign_root,
            "detail_live",
            "completed",
            {
                "completed_packs": len(run_summary["packs"]),
                "main_db_apply": "not_run_manual_only",
            },
        )
    return run_summary


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and run Hunyuan 8JD ABC detail tasks.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--rank-summary", default=str(DEFAULT_RANK_SUMMARY))
    build.add_argument("--db", default=str(DEFAULT_DB_PATH))
    build.add_argument("--campaign-root", default=str(DEFAULT_CAMPAIGN_ROOT))
    build.add_argument("--pack-size", type=int, default=100)
    build.add_argument("--include-existing-capture", action="store_true")

    run = subparsers.add_parser("run")
    run.add_argument("--campaign-root", default=str(DEFAULT_CAMPAIGN_ROOT))
    run.add_argument("--db", default=str(DEFAULT_DB_PATH))
    run.add_argument("--cdp-url", default="http://127.0.0.1:9888")
    run.add_argument("--delay-seconds", type=float, default=10)
    run.add_argument("--timeout-seconds", type=float, default=45)
    run.add_argument("--max-packs", type=int)
    run.add_argument("--start-pack")
    run.add_argument("--pack-ids", nargs="*", help="Only run the listed detail pack ids.")
    run.add_argument("--runner-id", default="", help="Write per-runner state file when running shards in parallel.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        result = build_tasks(
            rank_summary=Path(args.rank_summary),
            db_path=Path(args.db),
            campaign_root=Path(args.campaign_root),
            pack_size=args.pack_size,
            include_existing_capture=bool(args.include_existing_capture),
        )
        print(json.dumps(result["metadata"], ensure_ascii=False, indent=2))
        return 0 if result["metadata"]["runnable_targets"] > 0 else 2

    result = run_unattended(
        campaign_root=Path(args.campaign_root),
        db_path=Path(args.db),
        cdp_url=args.cdp_url,
        delay_seconds=args.delay_seconds,
        timeout_seconds=args.timeout_seconds,
        max_packs=args.max_packs,
        start_pack=args.start_pack,
        pack_ids=args.pack_ids,
        runner_id=args.runner_id,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "packs"}, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
