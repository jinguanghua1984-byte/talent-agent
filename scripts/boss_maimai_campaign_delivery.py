"""生成 BOSS-Maimai campaign 级交付报告、跟进表和飞书发布清单。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REPORT_SCHEMA = "boss_maimai_campaign_delivery_report_v1"
GATE_SCHEMA = "boss_maimai_campaign_delivery_quality_gates_v1"
MANIFEST_SCHEMA = "boss_maimai_campaign_delivery_feishu_manifest_v1"
MATCHED_STATUSES = {"auto_bound", "confirmed_bound"}
REPORT_JSON = "reports/boss-maimai-delivery-report.json"
REPORT_MD = "reports/boss-maimai-delivery-report.md"
FOLLOW_UP_CSV = "reports/boss-maimai-follow-up-queue.csv"
FOLLOW_UP_MD = "reports/boss-maimai-follow-up-queue.md"
GATES_JSON = "reports/boss-maimai-delivery-quality-gates.json"
MANIFEST_JSON = "feishu/boss-maimai-delivery-manifest.json"
HANDOFF_JSON = "state/boss-maimai-delivery-handoff.json"
LEGACY_JD_HANDOFF_JSON = "state/jd-delivery-handoff.json"
IM_NOTIFICATION_MESSAGE = "feishu/im-notification-message.txt"
IM_NOTIFICATION_RESULTS = "feishu/im-notification-results.json"
DEFAULT_NOTIFY_CHAT_NAME = "JD需求协同"
ALLOWED_MANIFEST_SOURCE_FILES = {
    REPORT_MD,
    FOLLOW_UP_CSV,
    GATES_JSON,
}
FORBIDDEN_MANIFEST_MARKERS = (
    "top30",
    "talent.db",
    ".db",
    ".sqlite",
    ".zip",
    "raw/",
    "raw_profile",
    "raw_payload",
    "talent-recommendation",
    "jd-talent-delivery",
)
FOLLOW_UP_FIELDS = [
    "candidate_key",
    "real_name",
    "boss_display_name",
    "boss_company",
    "boss_title",
    "city",
    "education",
    "boss_score",
    "contact_status",
    "message_status",
    "maimai_match_status",
    "maimai_profile_url",
    "maimai_platform_id",
    "main_db_candidate_id",
    "follow_up_required",
    "preferred_channel",
    "follow_up_action",
    "priority",
    "reasons",
    "risks",
]
REQUIRED_INPUT_FILES = [
    "reports/sourcing-summary.json",
    "reports/executor-summary.json",
    "reports/maimai-match-summary.json",
    "reports/main-db-sync-result.json",
    "structured/approved-contact-queue.jsonl",
    "structured/maimai-match-targets.jsonl",
    "state/cross-channel-identity-ledger.jsonl",
]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_no}: expected object")
        rows.append(value)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _latest_by_key(rows: list[dict[str, Any]], key_name: str = "candidate_key") -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _string(row.get(key_name))
        if key:
            latest[key] = row
    return latest


def _latest_contacted_candidates(root: Path) -> list[dict[str, Any]]:
    candidates = _latest_by_key(_load_jsonl(root / "structured/candidates.jsonl"))
    approvals = _latest_by_key(_load_jsonl(root / "structured/approved-contact-queue.jsonl"))
    decisions = _load_jsonl(root / "structured/contact-decisions.jsonl")
    contacted_keys = {
        _string(row.get("candidate_key"))
        for row in decisions
        if row.get("contacted") is True and _string(row.get("candidate_key"))
    }
    if not contacted_keys:
        contacted_keys = set(approvals)

    ordered_keys = [key for key in approvals if key in contacted_keys or not contacted_keys]
    for key in contacted_keys:
        if key not in ordered_keys:
            ordered_keys.append(key)

    decision_by_key = _latest_by_key(
        [row for row in decisions if row.get("contacted") is True]
    )
    rows: list[dict[str, Any]] = []
    for key in ordered_keys:
        approval = approvals.get(key) or {}
        base = candidates.get(key) or {}
        decision = decision_by_key.get(key) or {}
        merged = {**approval, **base}
        merged["candidate_key"] = key
        merged["_decision"] = decision
        rows.append(merged)
    return rows


def _latest_identity_by_candidate(root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(root / "state/cross-channel-identity-ledger.jsonl"):
        key = _string(row.get("source_candidate_key"))
        if not key:
            continue
        latest[key] = row

    for row in _load_jsonl(root / "structured/cross-channel-bound-candidates.jsonl"):
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        maimai_hit = row.get("maimai_hit") if isinstance(row.get("maimai_hit"), dict) else {}
        key = _string(decision.get("source_candidate_key") or target.get("candidate_key"))
        if not key:
            continue
        existing = latest.get(key, {})
        existing_status = _string(existing.get("match_status"))
        existing_platform_id = _string(existing.get("target_platform_id"))
        existing_profile_url = _string(existing.get("target_profile_url"))
        should_supplement = (
            not existing
            or (
                existing_status in MATCHED_STATUSES
                and (not existing_platform_id or not existing_profile_url)
            )
        )
        if not should_supplement:
            continue
        latest[key] = {
            **existing,
            "source_candidate_key": key,
            "match_status": _string(
                existing.get("match_status")
                or decision.get("match_status")
                or "confirmed_bound"
            ),
            "target_platform_id": _string(
                existing.get("target_platform_id")
                or decision.get("target_platform_id")
                or maimai_hit.get("platform_id")
            ),
            "target_profile_url": _string(
                existing.get("target_profile_url")
                or decision.get("target_profile_url")
                or maimai_hit.get("profile_url")
            ),
            "hit": maimai_hit,
        }
    return latest


def _main_db_ids_by_source(main_db_path: str | Path | None) -> dict[tuple[str, str], str]:
    if main_db_path is None:
        return {}
    db_path = Path(main_db_path)
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT candidate_id, platform, platform_id
            FROM source_profiles
            WHERE platform IN ('boss_app', 'maimai')
            """
        ).fetchall()
        return {
            (str(platform), str(platform_id)): str(candidate_id)
            for candidate_id, platform, platform_id in rows
            if platform_id
        }
    finally:
        conn.close()


def _sync_counts(sync_result: dict[str, Any]) -> dict[str, int]:
    apply_result = sync_result.get("apply_result") if isinstance(sync_result.get("apply_result"), dict) else {}
    created = apply_result.get("created") if isinstance(apply_result.get("created"), dict) else {}
    merged = apply_result.get("merged") if isinstance(apply_result.get("merged"), dict) else {}
    conflicts = apply_result.get("conflicts") if isinstance(apply_result.get("conflicts"), dict) else {}
    skipped = apply_result.get("skipped") if isinstance(apply_result.get("skipped"), dict) else {}
    deleted = apply_result.get("deleted") if isinstance(apply_result.get("deleted"), dict) else {}
    return {
        "created_candidates": _int(created.get("candidates")),
        "created_details": _int(created.get("candidate_details")),
        "created_source_profiles": _int(created.get("source_profiles")),
        "created_field_values": _int(created.get("candidate_field_values")),
        "merged_candidates": _int(merged.get("candidates")),
        "conflicts": sum(_int(value) for value in conflicts.values()),
        "skipped": sum(_int(value) for value in skipped.values()),
        "deleted": sum(_int(value) for value in deleted.values()),
    }


def build_delivery_report(
    campaign_root: str | Path,
    main_db_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    sourcing = _load_json(root / "reports/sourcing-summary.json")
    executor = _load_json(root / "reports/executor-summary.json", default={})
    match_summary = _load_json(root / "reports/maimai-match-summary.json", default={})
    sync_result = _load_json(root / "reports/main-db-sync-result.json", default={"status": "not_run"})
    contacted = _latest_contacted_candidates(root)
    identity_by_key = _latest_identity_by_candidate(root)
    main_ids = _main_db_ids_by_source(main_db_path)

    candidate_rows: list[dict[str, Any]] = []
    auto_bound_count = 0
    confirmed_bound_count = 0
    no_match_count = 0
    pending_count = 0
    for row in contacted:
        key = _string(row.get("candidate_key"))
        identity = identity_by_key.get(key, {})
        status = _string(identity.get("match_status") or "no_match")
        if status == "auto_bound":
            auto_bound_count += 1
        elif status == "confirmed_bound":
            confirmed_bound_count += 1
        elif status == "pending_confirmation":
            pending_count += 1
        else:
            no_match_count += 1

        platform_id = _string(identity.get("target_platform_id"))
        profile_url = _string(identity.get("target_profile_url"))
        main_id = main_ids.get(("boss_app", key)) or (
            main_ids.get(("maimai", platform_id)) if platform_id else ""
        )
        decision = row.get("_decision") if isinstance(row.get("_decision"), dict) else {}
        screening = row.get("screening") if isinstance(row.get("screening"), dict) else {}
        candidate_rows.append(
            {
                "candidate_key": key,
                "real_name": _string(row.get("real_name")),
                "boss_display_name": _string(row.get("display_name")),
                "boss_company": _string(row.get("current_company")),
                "boss_title": _string(row.get("current_title")),
                "city": _string(row.get("city")),
                "education": _string(row.get("education")),
                "boss_score": _int(row.get("score") or screening.get("score")),
                "message_status": _string(
                    decision.get("message_status")
                    or row.get("message_status")
                    or (row.get("contact") or {}).get("message_status")
                ),
                "maimai_match_status": status,
                "maimai_profile_url": profile_url,
                "maimai_platform_id": platform_id,
                "main_db_candidate_id": main_id,
                "reasons": row.get("reasons") or screening.get("reasons") or [],
                "risks": row.get("risks") or screening.get("risks") or [],
            }
        )

    return {
        "schema": REPORT_SCHEMA,
        "campaign_id": root.name,
        "generated_at": _now(),
        "source_files": {
            "sourcing_summary": "reports/sourcing-summary.json",
            "executor_summary": "reports/executor-summary.json",
            "maimai_match_summary": "reports/maimai-match-summary.json",
            "identity_ledger": "state/cross-channel-identity-ledger.jsonl",
            "main_db_sync_result": "reports/main-db-sync-result.json",
        },
        "boss_funnel": {
            "candidate_count": _int(sourcing.get("candidate_count")),
            "list_card_count": _int(sourcing.get("list_card_count")),
            "detail_count": _int(sourcing.get("detail_count")),
            "would_contact_count": _int(sourcing.get("would_contact_count")),
            "real_contact_count": _int(sourcing.get("real_contact_count")),
            "real_name_captured_count": _int(sourcing.get("real_name_captured_count")),
            "approved_queue_count": _int(executor.get("approved_queue_count")),
            "attempt_count": _int(executor.get("attempt_count")),
            "sent_count": _int(executor.get("sent_count")),
            "message_status_distribution": executor.get("message_status_distribution", {}),
        },
        "maimai_funnel": {
            "target_count": _int(match_summary.get("target_count")),
            "selected_count": _int(match_summary.get("selected_count")),
            "missing_real_name_count": _int(match_summary.get("missing_real_name_count")),
            "matched_count": auto_bound_count + confirmed_bound_count,
            "auto_bound_count": auto_bound_count,
            "confirmed_bound_count": confirmed_bound_count,
            "pending_confirmation_count": pending_count,
            "no_match_count": no_match_count,
        },
        "main_db_sync": {
            "status": _string(sync_result.get("status") or "not_run"),
            **_sync_counts(sync_result),
        },
        "candidate_rows": candidate_rows,
    }


def _join_values(values: Any) -> str:
    if isinstance(values, list):
        return "；".join(_string(value) for value in values if _string(value))
    return _string(values)


def build_follow_up_rows(
    campaign_root: str | Path,
    report: dict[str, Any],
) -> list[dict[str, str]]:
    del campaign_root
    rows: list[dict[str, str]] = []
    for item in report["candidate_rows"]:
        status = _string(item.get("maimai_match_status") or "no_match")
        preferred_channel = "maimai" if status in MATCHED_STATUSES else "boss"
        if status in MATCHED_STATUSES:
            action = "优先脉脉触达，并同步记录 BOSS 会话回复"
            priority = "P1"
        elif status == "pending_confirmation":
            action = "先人工确认脉脉身份，同时保留 BOSS 会话跟进"
            priority = "P1"
        else:
            action = "继续 BOSS 会话跟进，必要时后续补充人工脉脉搜索"
            priority = "P2"
        rows.append(
            {
                "candidate_key": _string(item.get("candidate_key")),
                "real_name": _string(item.get("real_name")),
                "boss_display_name": _string(item.get("boss_display_name")),
                "boss_company": _string(item.get("boss_company")),
                "boss_title": _string(item.get("boss_title")),
                "city": _string(item.get("city")),
                "education": _string(item.get("education")),
                "boss_score": _string(item.get("boss_score")),
                "contact_status": "contacted",
                "message_status": _string(item.get("message_status") or "送达"),
                "maimai_match_status": status,
                "maimai_profile_url": _string(item.get("maimai_profile_url")),
                "maimai_platform_id": _string(item.get("maimai_platform_id")),
                "main_db_candidate_id": _string(item.get("main_db_candidate_id")),
                "follow_up_required": "true",
                "preferred_channel": preferred_channel,
                "follow_up_action": action,
                "priority": priority,
                "reasons": _join_values(item.get("reasons")),
                "risks": _join_values(item.get("risks")),
            }
        )
    return rows


def _md_cell(value: Any) -> str:
    text = _join_values(value).replace("|", "/")
    return " ".join(text.split())


def _render_report_md(report: dict[str, Any]) -> str:
    boss = report["boss_funnel"]
    maimai = report["maimai_funnel"]
    sync = report["main_db_sync"]
    lines = [
        "# BOSS-Maimai 寻访交付报告",
        "",
        f"- Campaign：{report['campaign_id']}",
        f"- BOSS 看过：{boss['list_card_count']} 人",
        f"- BOSS 详情：{boss['detail_count']} 人",
        f"- 已沟通：{boss['real_contact_count']} 人",
        f"- 脉脉匹配目标：{maimai['target_count']} 人",
        f"- 脉脉命中：{maimai['matched_count']} 人",
        f"- 主库新增：{sync['created_candidates']} 人",
        "",
        "## 漏斗",
        "",
        f"- 沟通送达：{boss['message_status_distribution']}",
        f"- 自动绑定：{maimai['auto_bound_count']}",
        f"- 用户确认绑定：{maimai['confirmed_bound_count']}",
        f"- 未命中：{maimai['no_match_count']}",
        "",
        "## 候选人状态",
        "",
        "| 姓名 | BOSS 公司 | BOSS 职位 | 脉脉状态 | 主库 ID | 跟进渠道 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["candidate_rows"]:
        lines.append(
            "| {real_name} | {company} | {title} | {status} | {main_id} | {channel} |".format(
                real_name=_md_cell(item.get("real_name")),
                company=_md_cell(item.get("boss_company")),
                title=_md_cell(item.get("boss_title")),
                status=_md_cell(item.get("maimai_match_status")),
                main_id=_md_cell(item.get("main_db_candidate_id")),
                channel=(
                    "maimai"
                    if _string(item.get("maimai_match_status")) in MATCHED_STATUSES
                    else "boss"
                ),
            )
        )
    lines.extend(
        [
            "",
            "## 后续跟进",
            "",
            "所有已沟通 BOSS 人选都进入跟进表；脉脉命中只影响优先触达渠道，不影响是否需要跟进。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_follow_up_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "# BOSS-Maimai 后续跟进表",
        "",
        "| 姓名 | 公司 | 职位 | 脉脉状态 | 优先渠道 | 下一步 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {_md_cell(row['real_name'])} | {_md_cell(row['boss_company'])} | "
            f"{_md_cell(row['boss_title'])} | {_md_cell(row['maimai_match_status'])} | "
            f"{_md_cell(row['preferred_channel'])} | {_md_cell(row['follow_up_action'])} |"
        )
    lines.append("")
    return "\n".join(lines)


def _validate_required_inputs(root: Path) -> tuple[list[str], list[dict[str, str]]]:
    missing: list[str] = []
    invalid: list[dict[str, str]] = []
    for relative_path in REQUIRED_INPUT_FILES:
        path = root / relative_path
        if not path.exists():
            missing.append(relative_path)
            continue
        try:
            if relative_path.endswith(".jsonl"):
                _load_jsonl(path)
            else:
                _load_json(path)
        except (json.JSONDecodeError, ValueError) as exc:
            invalid.append({"path": relative_path, "error": str(exc)})
    return missing, invalid


def validate_delivery_quality_gates(
    campaign_root: str | Path,
    report: dict[str, Any],
    follow_up_rows: list[dict[str, str]],
) -> dict[str, Any]:
    root = Path(campaign_root)
    blockers: list[str] = []
    missing, invalid = _validate_required_inputs(root)
    if missing:
        blockers.append("missing_required_inputs")
    if invalid:
        blockers.append("invalid_required_inputs")

    real_contact_count = _int(report["boss_funnel"].get("real_contact_count"))
    follow_up_row_count = len(follow_up_rows)
    target_count = _int(report["maimai_funnel"].get("target_count"))
    real_name_count = _int(report["boss_funnel"].get("real_name_captured_count"))
    matched_count = _int(report["maimai_funnel"].get("matched_count"))
    main_db_created = _int(report["main_db_sync"].get("created_candidates"))
    if follow_up_row_count != real_contact_count:
        blockers.append("follow_up_row_count_mismatch")
    if target_count != real_name_count:
        blockers.append("maimai_target_count_mismatch")
    if matched_count > target_count:
        blockers.append("maimai_matched_exceeds_targets")
    if main_db_created > matched_count:
        blockers.append("main_db_created_exceeds_matched")
    if any(row.get("follow_up_required") != "true" for row in follow_up_rows):
        blockers.append("follow_up_required_not_true")
    if any(
        row.get("preferred_channel") == "maimai" and not row.get("maimai_profile_url")
        for row in follow_up_rows
    ):
        blockers.append("maimai_channel_without_profile_url")
    if any(
        row.get("maimai_match_status") in MATCHED_STATUSES
        and not row.get("maimai_profile_url")
        for row in follow_up_rows
    ):
        blockers.append("matched_maimai_missing_profile_url")

    follow_up_keys = {row["candidate_key"] for row in follow_up_rows}
    candidate_keys = {_string(row.get("candidate_key")) for row in report["candidate_rows"]}
    if follow_up_keys != candidate_keys:
        blockers.append("candidate_rows_follow_up_mismatch")
    no_match_keys = {
        _string(row.get("candidate_key"))
        for row in report["candidate_rows"]
        if _string(row.get("maimai_match_status")) == "no_match"
    }
    if not no_match_keys.issubset(follow_up_keys):
        blockers.append("no_match_candidates_missing_from_follow_up")

    gates = {
        "schema": GATE_SCHEMA,
        "checked_at": _now(),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "missing_required_inputs": missing,
        "invalid_required_inputs": invalid,
        "real_contact_count": real_contact_count,
        "follow_up_row_count": follow_up_row_count,
        "maimai_target_count": target_count,
        "real_name_captured_count": real_name_count,
        "maimai_matched_count": matched_count,
        "main_db_created_candidates": main_db_created,
    }
    _write_json(root / GATES_JSON, gates)
    return gates


def _write_required_input_blocked_gates(
    root: Path,
    missing: list[str],
    invalid: list[dict[str, str]],
) -> dict[str, Any]:
    blockers: list[str] = []
    if missing:
        blockers.append("missing_required_inputs")
    if invalid:
        blockers.append("invalid_required_inputs")
    gates = {
        "schema": GATE_SCHEMA,
        "checked_at": _now(),
        "status": "blocked",
        "blockers": blockers,
        "missing_required_inputs": missing,
        "invalid_required_inputs": invalid,
        "real_contact_count": 0,
        "follow_up_row_count": 0,
        "maimai_target_count": 0,
        "real_name_captured_count": 0,
        "maimai_matched_count": 0,
        "main_db_created_candidates": 0,
    }
    _write_json(root / GATES_JSON, gates)
    return gates


def _write_follow_up_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FOLLOW_UP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _assert_manifest_safe(manifest: dict[str, Any]) -> None:
    source_files = manifest.get("source_files")
    if isinstance(source_files, dict):
        for path in source_files.values():
            _assert_manifest_file_safe(_string(path))

    for command in manifest.get("commands") or []:
        if not isinstance(command, list):
            continue
        for index, value in enumerate(command):
            if value == "--file" and index + 1 < len(command):
                _assert_manifest_file_safe(_string(command[index + 1]))


def _assert_manifest_file_safe(path: str) -> None:
    normalized = path.replace("\\", "/")
    if normalized not in ALLOWED_MANIFEST_SOURCE_FILES:
        raise ValueError(f"manifest references disallowed file: {path}")
    lowered = normalized.lower()
    for marker in FORBIDDEN_MANIFEST_MARKERS:
        if marker in lowered:
            raise ValueError(f"manifest file contains forbidden marker: {marker}")


def _safe_blocker_name(value: Any) -> str:
    blocker = _string(value)
    serialized = blocker.lower().replace("\\", "/")
    if not blocker or any(marker in serialized for marker in FORBIDDEN_MANIFEST_MARKERS):
        return "redacted_blocker"
    return blocker


def _quality_gate_manifest_summary(gates: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    for blocker in gates.get("blockers") or []:
        safe = _safe_blocker_name(blocker)
        if safe not in blockers:
            blockers.append(safe)
    summary: dict[str, Any] = {
        "status": _string(gates.get("status") or "unknown"),
        "blockers": blockers,
        "missing_required_input_count": len(gates.get("missing_required_inputs") or []),
        "invalid_required_input_count": len(gates.get("invalid_required_inputs") or []),
    }
    for key in [
        "real_contact_count",
        "follow_up_row_count",
        "maimai_target_count",
        "real_name_captured_count",
        "maimai_matched_count",
        "main_db_created_candidates",
    ]:
        if key in gates:
            summary[key] = _int(gates.get(key))
    return summary


def _notification_idempotency_key(root: Path) -> str:
    digest = hashlib.sha1(root.name.encode("utf-8")).hexdigest()[:12]
    return f"boss-maimai-{digest}"


def build_feishu_manifest(campaign_root: str | Path, *, dry_run: bool) -> dict[str, Any]:
    root = Path(campaign_root)
    report_path = root / REPORT_MD
    follow_up_path = root / FOLLOW_UP_CSV
    gates_path = root / GATES_JSON
    for path in [report_path, follow_up_path, gates_path]:
        if not path.exists():
            raise FileNotFoundError(path)
    gates = _load_json(gates_path)
    if gates.get("status") != "passed":
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "campaign_id": root.name,
            "dry_run": bool(dry_run),
            "status": "blocked",
            "reason": "quality_gates_not_passed",
            "legacy_package_policy": "keep_existing_package_unchanged",
            "quality_gates": _quality_gate_manifest_summary(gates),
        }
        _assert_manifest_safe(manifest)
        return manifest

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "campaign_id": root.name,
        "dry_run": bool(dry_run),
        "status": "ready",
        "legacy_package_policy": "keep_existing_package_unchanged",
        "source_files": {
            "delivery_report": _relative(report_path, root),
            "follow_up_queue": _relative(follow_up_path, root),
            "quality_gates": _relative(gates_path, root),
        },
        "commands": [
            [
                "lark-cli",
                "drive",
                "+import",
                "--type",
                "docx",
                "--as",
                "user",
                "--file",
                _relative(report_path, root),
                "--name",
                f"{root.name} BOSS寻访交付报告",
            ],
            [
                "lark-cli",
                "sheets",
                "+create",
                "--title",
                f"{root.name} BOSS跟进表",
            ],
            [
                "lark-cli",
                "sheets",
                "+append",
                "--spreadsheet-token",
                "<new_boss_follow_up_sheet_token>",
                "--range",
                "<first_sheet_id>",
                "--file",
                _relative(follow_up_path, root),
            ],
            [
                "lark-cli",
                "im",
                "+chat-search",
                "--as",
                "user",
                "--query",
                DEFAULT_NOTIFY_CHAT_NAME,
                "--disable-search-by-user",
                "--search-types",
                "private,public_joined,external",
                "--page-size",
                "10",
                "--format",
                "json",
            ],
            [
                "lark-cli",
                "im",
                "+messages-send",
                "--as",
                "user",
                "--chat-id",
                f"<{DEFAULT_NOTIFY_CHAT_NAME}_chat_id>",
                "--idempotency-key",
                _notification_idempotency_key(root),
                "--text",
                f"<contents of {IM_NOTIFICATION_MESSAGE}>",
            ],
        ],
        "notification": {
            "send_after": "feishu_publish_readback_passed",
            "target_name": DEFAULT_NOTIFY_CHAT_NAME,
            "message_file": IM_NOTIFICATION_MESSAGE,
            "result_file": IM_NOTIFICATION_RESULTS,
            "idempotency_key": _notification_idempotency_key(root),
        },
        "readback_expectations": {
            "new_report_title_contains": "BOSS寻访交付报告",
            "new_sheet_title_contains": "BOSS跟进表",
            "follow_up_row_count": gates["follow_up_row_count"],
            "legacy_package": "not_modified",
            "im_notification_status": "sent",
            "im_notification_target": DEFAULT_NOTIFY_CHAT_NAME,
        },
    }
    if dry_run:
        for command in manifest["commands"]:
            command.append("--dry-run")
    _assert_manifest_safe(manifest)
    return manifest


def write_feishu_manifest(campaign_root: str | Path, *, dry_run: bool) -> dict[str, Any]:
    root = Path(campaign_root)
    manifest = build_feishu_manifest(root, dry_run=dry_run)
    _write_json(root / MANIFEST_JSON, manifest)
    return manifest


def _delivery_outputs() -> dict[str, str]:
    return {
        "report_json": REPORT_JSON,
        "report_md": REPORT_MD,
        "follow_up_csv": FOLLOW_UP_CSV,
        "follow_up_md": FOLLOW_UP_MD,
        "quality_gates": GATES_JSON,
        "feishu_manifest": MANIFEST_JSON,
        "im_notification_message": IM_NOTIFICATION_MESSAGE,
        "im_notification_results": IM_NOTIFICATION_RESULTS,
    }


def _main_db_path_from_sync_result(
    root: Path,
    main_db_path: str | Path | None,
) -> str:
    if main_db_path:
        return str(main_db_path)
    sync_result = _load_json(root / "reports/main-db-sync-result.json", default={})
    handoff = sync_result.get("handoff") if isinstance(sync_result.get("handoff"), dict) else {}
    return _string(handoff.get("main_db_path") or "data/talent.db")


def _write_campaign_delivery_handoff(
    root: Path,
    *,
    main_db_path: str | Path | None,
) -> dict[str, Any]:
    handoff = {
        "schema": "boss_maimai_campaign_delivery_handoff_v1",
        "created_at": _now(),
        "main_db_path": _main_db_path_from_sync_result(root, main_db_path),
        "delivery_kind": "boss_maimai_campaign_delivery",
        "delivery_script": "scripts/boss_maimai_campaign_delivery.py",
        "outputs": _delivery_outputs(),
        "legacy_jd_delivery_default": False,
    }
    _write_json(root / HANDOFF_JSON, handoff)

    legacy_handoff = root / LEGACY_JD_HANDOFF_JSON
    if legacy_handoff.exists():
        legacy_handoff.unlink()

    sync_result_path = root / "reports/main-db-sync-result.json"
    if sync_result_path.exists():
        sync_result = _load_json(sync_result_path)
        sync_result["handoff"] = handoff
        _write_json(sync_result_path, sync_result)
    return handoff


def write_delivery_package(
    campaign_root: str | Path,
    *,
    main_db_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    missing, invalid = _validate_required_inputs(root)
    if missing or invalid:
        gates = _write_required_input_blocked_gates(root, missing, invalid)
        return {
            "schema": "boss_maimai_campaign_delivery_write_result_v1",
            "status": "blocked",
            "campaign_id": root.name,
            "quality_gates": gates,
            "outputs": {
                "quality_gates": GATES_JSON,
            },
        }
    report = build_delivery_report(root, main_db_path=main_db_path)
    follow_up_rows = build_follow_up_rows(root, report)
    gates = validate_delivery_quality_gates(root, report, follow_up_rows)
    _write_json(root / REPORT_JSON, report)
    (root / REPORT_MD).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_MD).write_text(_render_report_md(report), encoding="utf-8")
    _write_follow_up_csv(root / FOLLOW_UP_CSV, follow_up_rows)
    (root / FOLLOW_UP_MD).write_text(_render_follow_up_md(follow_up_rows), encoding="utf-8")
    manifest = write_feishu_manifest(root, dry_run=True)
    handoff = _write_campaign_delivery_handoff(root, main_db_path=main_db_path)
    return {
        "schema": "boss_maimai_campaign_delivery_write_result_v1",
        "status": gates["status"],
        "campaign_id": root.name,
        "quality_gates": gates,
        "feishu_manifest": manifest,
        "handoff": handoff,
        "outputs": _delivery_outputs(),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 BOSS-Maimai campaign 交付包")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--campaign-root", required=True)
    build.add_argument("--main-db", default="")

    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--campaign-root", required=True)
    manifest.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        result = write_delivery_package(
            args.campaign_root,
            main_db_path=args.main_db or None,
        )
    else:
        result = write_feishu_manifest(args.campaign_root, dry_run=bool(args.dry_run))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
