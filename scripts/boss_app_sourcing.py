from __future__ import annotations

import argparse
import hashlib
import json
import re
from copy import deepcopy
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "boss_app_recommendation_sourcing_manifest_v1"
EXTERNAL_EXECUTOR_REAL_NAME_SOURCE = "communication_page_after_external_executor"
EXECUTOR_RESULT_SCHEMA = "boss_executor_result_v1"
CURRENT_CONTACT_INTENT_SCHEMA = "boss_current_contact_intent_v1"
APPROVED_CONTACT_QUEUE_SCHEMA = "boss_approved_contact_queue_v1"
EXECUTOR_ATTEMPT_SCHEMA = "boss_contact_attempt_event_v1"
EXECUTOR_LOCK_SCHEMA = "boss_executor_lock_v1"

DEFAULT_RUN_POLICY: dict[str, Any] = {
    "execution_surface": "boss_app_computer_use",
    "contact_mode": "dry_run",
    "allow_real_contact": False,
    "allow_live_contact_test": False,
    "live_contact_test_limit": 0,
    "require_action_time_confirmation_for_real_contact": True,
    "capture_real_name_after_contact": True,
    "stop_on_login_or_security_page": True,
    "stop_on_captcha": True,
    "stop_on_ui_template_drift": True,
    "list_end_stall_scrolls": 3,
}

REQUIRED_EMPTY_FILES = [
    "raw/list-cards.jsonl",
    "raw/detail-pages.jsonl",
    "raw/communication-pages.jsonl",
    "raw/screen-hashes.jsonl",
    "state/events.jsonl",
    "state/processed-cards.jsonl",
    "structured/candidates.jsonl",
    "structured/contact-decisions.jsonl",
]

BOOLEAN_POLICY_FIELDS = [
    "allow_real_contact",
    "allow_live_contact_test",
    "require_action_time_confirmation_for_real_contact",
    "capture_real_name_after_contact",
    "stop_on_login_or_security_page",
    "stop_on_captcha",
    "stop_on_ui_template_drift",
]

INTEGER_POLICY_FIELDS = [
    "live_contact_test_limit",
    "list_end_stall_scrolls",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE).strip("-._")
    return slug or "boss-app-sourcing"


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_json(path: str | Path, data: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json_dumps(data), encoding="utf-8")


def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def append_jsonl(path: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = False
    if out.exists() and out.stat().st_size > 0:
        with out.open("rb") as handle:
            handle.seek(-1, 2)
            needs_separator = handle.read(1) != b"\n"
    with out.open("a", encoding="utf-8") as handle:
        if needs_separator:
            handle.write("\n")
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file} line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{file} line {line_number}: must be an object")
        rows.append(value)
    return rows


def screen_hash(text: str | bytes) -> str:
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def build_candidate_key(card: dict[str, Any]) -> str:
    parts = [
        str(card.get("display_name") or "").strip(),
        str(card.get("current_company") or "").strip(),
        str(card.get("current_title") or "").strip(),
        str(card.get("education") or "").strip(),
        str(card.get("city") or "").strip(),
        str(card.get("expected_salary") or "").strip(),
        str(card.get("screenshot_hash") or "").strip(),
        str(card.get("list_scroll_batch") or "").strip(),
        str(card.get("card_position") or "").strip(),
    ]
    return "boss-app:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def build_candidate_signature(card: dict[str, Any]) -> str:
    """Stable visible-person signature for cross-scroll duplicate detection."""
    parts = [
        _clean_text(card.get("display_name")),
        _clean_text(card.get("current_company")),
        _clean_text(card.get("current_title")),
        _clean_text(card.get("age")),
        _clean_text(card.get("work_years")),
        _clean_text(card.get("education")),
        _clean_text(card.get("city")),
        _clean_text(card.get("expected_salary")),
    ]
    return "boss-app-signature:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def validate_run_policy(policy: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_RUN_POLICY)
    merged.update(policy)
    for field in BOOLEAN_POLICY_FIELDS:
        if not isinstance(merged[field], bool):
            raise ValueError(f"{field} must be boolean")
    for field in INTEGER_POLICY_FIELDS:
        if isinstance(merged[field], bool) or not isinstance(merged[field], int):
            raise ValueError(f"{field} must be integer")
    if merged["execution_surface"] != "boss_app_computer_use":
        raise ValueError("execution_surface must be boss_app_computer_use")
    if merged["contact_mode"] not in {"dry_run", "live_test"}:
        raise ValueError("contact_mode must be dry_run or live_test")
    if merged["contact_mode"] == "live_test":
        if not merged["allow_real_contact"]:
            raise ValueError("contact_mode live_test requires allow_real_contact")
        if not merged["allow_live_contact_test"]:
            raise ValueError("contact_mode live_test requires allow_live_contact_test")
        if merged["live_contact_test_limit"] <= 0:
            raise ValueError("contact_mode live_test requires live_contact_test_limit")
    if merged["allow_real_contact"] and not merged["require_action_time_confirmation_for_real_contact"]:
        raise ValueError("real contact requires action-time confirmation")
    if merged["allow_live_contact_test"] and not merged["allow_real_contact"]:
        raise ValueError("allow_live_contact_test requires allow_real_contact")
    if merged["allow_live_contact_test"] and merged["live_contact_test_limit"] <= 0:
        raise ValueError("live_contact_test_limit must be positive when live-contact test is enabled")
    if merged["live_contact_test_limit"] < 0:
        raise ValueError("live_contact_test_limit must be non-negative")
    if merged["list_end_stall_scrolls"] <= 0:
        raise ValueError("list_end_stall_scrolls must be positive")
    if merged["allow_live_contact_test"]:
        merged["contact_mode"] = "live_test"
    if not merged["allow_live_contact_test"]:
        merged["live_contact_test_limit"] = 0
    return merged


def _initial_requirements(filters_text: str, campaign_id: str, date_text: str) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "input_mode": "post_jd_recommendation_filters",
        "filters_text": filters_text,
        "confirmed_defaults": {
            "source_list": "boss_app_jd_recommendation_list",
            "details_store": "structured_text_and_screenshot_hash",
            "real_name_backfill": "live_test_or_manual_communication_page",
        },
        "created_date": date_text,
    }


def _initial_strategy(filters_text: str) -> dict[str, Any]:
    return {
        "strategy_version": "boss_app_recommendation_sourcing_v1",
        "list_screening": {
            "input_text": filters_text,
            "enter_detail_when": "candidate appears likely to satisfy the filters",
        },
        "detail_screening": {
            "recommendation_values": ["contact", "hold", "skip"],
            "would_contact_requires": ["positive evidence", "no hard exclusion"],
        },
    }


def init_campaign(
    campaign_id: str,
    filters_text: str,
    out_base: str | Path = "data/campaigns",
    date_text: str | None = None,
    allow_real_contact: bool = False,
    allow_live_contact_test: bool = False,
    live_contact_test_limit: int = 0,
) -> dict[str, Any]:
    if not campaign_id.strip():
        raise ValueError("campaign_id is required")
    if not filters_text.strip():
        raise ValueError("filters_text is required")

    date_value = date_text or date.today().isoformat()
    normalized_campaign_id = slugify(campaign_id)
    root = Path(out_base) / normalized_campaign_id
    if root.exists() and ((root / "campaign-manifest.json").exists() or any(root.iterdir())):
        raise ValueError(f"campaign already exists: {root}")
    root.mkdir(parents=True, exist_ok=True)

    policy = validate_run_policy({
        "allow_real_contact": allow_real_contact,
        "allow_live_contact_test": allow_live_contact_test,
        "live_contact_test_limit": live_contact_test_limit,
    })
    requirements = _initial_requirements(filters_text, normalized_campaign_id, date_value)
    strategy = _initial_strategy(filters_text)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "campaign_id": normalized_campaign_id,
        "campaign_root": str(root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "requirements_path": str(root / "requirements.json"),
        "strategy_path": str(root / "strategy.json"),
        "run_policy_path": str(root / "run-policy.json"),
        "status": "initialized",
    }

    write_json(root / "requirements.json", requirements)
    write_json(root / "strategy.json", strategy)
    write_json(root / "run-policy.json", policy)
    write_json(root / "campaign-manifest.json", manifest)
    write_json(root / "state/continuation-plan.json", {
        "stage": "initialized",
        "status": "ready_for_app_preflight",
        "campaign_root": str(root),
    })
    write_json(root / "reports/sourcing-summary.json", {
        "campaign_id": normalized_campaign_id,
        "status": "initialized",
    })
    (root / "reports/sourcing-summary.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "reports/sourcing-summary.md").write_text("# BOSS App 寻访摘要\n\n状态：initialized\n", encoding="utf-8")
    for relative in REQUIRED_EMPTY_FILES:
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch(exist_ok=True)
    append_jsonl(root / "state/events.jsonl", {
        "stage": "init",
        "status": "ready",
        "at": datetime.now().isoformat(timespec="seconds"),
    })
    return manifest


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _campaign_path(campaign_root: str | Path, relative: str) -> Path:
    return Path(campaign_root) / relative


def _base_candidate(card: dict[str, Any], candidate_key: str) -> dict[str, Any]:
    now = _now()
    return {
        "candidate_key": candidate_key,
        "candidate_signature": card.get("candidate_signature") or build_candidate_signature(card),
        "platform": "boss_app",
        "display_name": card.get("display_name"),
        "real_name": None,
        "real_name_status": "not_available_dry_run",
        "real_name_source": None,
        "name_confidence": "masked",
        "current_company": card.get("current_company", ""),
        "current_title": card.get("current_title", ""),
        "city": card.get("city", ""),
        "work_years": card.get("work_years"),
        "education": card.get("education", ""),
        "expected_salary": card.get("expected_salary", ""),
        "active_state": card.get("active_state", ""),
        "list_snapshot": dict(card),
        "detail_sections": {},
        "screen_evidence": [
            {
                "page": "list",
                "screenshot_hash": card.get("screenshot_hash", ""),
                "screen_region": card.get("screen_region"),
                "captured_at": now,
            }
        ],
        "screening": {
            "list_decision": card.get("list_decision", ""),
            "detail_decision": "",
            "score": 0,
            "reasons": [],
            "risks": [],
        },
        "contact": {
            "would_contact": False,
            "contact_mode": "dry_run",
            "contacted": False,
            "live_contact_test": False,
            "contact_button_seen": False,
            "communication_page_seen": False,
            "preset_message_auto_sent": False,
        },
        "updated_at": now,
    }


def _all_candidates(campaign_root: str | Path) -> list[dict[str, Any]]:
    return load_jsonl(_campaign_path(campaign_root, "structured/candidates.jsonl"))


def latest_candidate(campaign_root: str | Path, candidate_key: str) -> dict[str, Any]:
    matches = [row for row in _all_candidates(campaign_root) if row.get("candidate_key") == candidate_key]
    if not matches:
        raise ValueError(f"candidate not found: {candidate_key}")
    return matches[-1]


def _append_candidate(campaign_root: str | Path, candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["updated_at"] = _now()
    append_jsonl(_campaign_path(campaign_root, "structured/candidates.jsonl"), candidate)
    return candidate


def record_list_card(campaign_root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    if not str(card.get("display_name") or "").strip():
        raise ValueError("display_name is required")
    enriched_card = dict(card)
    enriched_card["candidate_signature"] = (
        enriched_card.get("candidate_signature") or build_candidate_signature(enriched_card)
    )
    if not enriched_card.get("screenshot_hash"):
        enriched_card["screenshot_hash"] = screen_hash(json.dumps(enriched_card, ensure_ascii=False, sort_keys=True))
    candidate_key = build_candidate_key(enriched_card)
    now = _now()
    list_evidence = {
        "page": "list",
        "screenshot_hash": enriched_card["screenshot_hash"],
        "screen_region": enriched_card.get("screen_region"),
        "captured_at": now,
    }
    try:
        candidate = deepcopy(latest_candidate(campaign_root, candidate_key))
        candidate["candidate_signature"] = enriched_card["candidate_signature"]
        candidate["list_snapshot"] = dict(enriched_card)
        candidate["screen_evidence"] = list(candidate.get("screen_evidence") or [])
        candidate["screen_evidence"].append(list_evidence)
        for field in ["current_company", "current_title", "city", "work_years", "education", "expected_salary", "active_state"]:
            if enriched_card.get(field) not in (None, ""):
                candidate[field] = enriched_card.get(field)
        if enriched_card.get("list_decision"):
            candidate["screening"] = dict(candidate.get("screening") or {})
            candidate["screening"]["list_decision"] = enriched_card["list_decision"]
    except ValueError:
        candidate = _base_candidate(enriched_card, candidate_key)
        candidate["screen_evidence"] = [list_evidence]
    append_jsonl(_campaign_path(campaign_root, "raw/list-cards.jsonl"), enriched_card | {
        "candidate_key": candidate_key,
        "captured_at": now,
    })
    append_jsonl(_campaign_path(campaign_root, "raw/screen-hashes.jsonl"), {
        "candidate_key": candidate_key,
        "page": "list",
        "screenshot_hash": enriched_card["screenshot_hash"],
        "captured_at": now,
    })
    append_jsonl(_campaign_path(campaign_root, "state/processed-cards.jsonl"), {
        "candidate_key": candidate_key,
        "stage": "list",
        "status": "captured",
        "captured_at": now,
    })
    return _append_candidate(campaign_root, candidate)


def record_detail_update(
    campaign_root: str | Path,
    candidate_key: str,
    detail_sections: dict[str, Any],
    recommendation: str,
    score: int,
    reasons: list[str],
    risks: list[str] | None = None,
) -> dict[str, Any]:
    if recommendation not in {"contact", "hold", "skip"}:
        raise ValueError("recommendation must be contact, hold, or skip")
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    candidate["detail_sections"] = dict(detail_sections)
    candidate["screening"] = dict(candidate.get("screening") or {})
    candidate["screening"].update({
        "detail_decision": recommendation,
        "score": int(score),
        "reasons": list(reasons),
        "risks": list(risks or []),
    })
    append_jsonl(_campaign_path(campaign_root, "raw/detail-pages.jsonl"), {
        "candidate_key": candidate_key,
        "detail_sections": detail_sections,
        "recommendation": recommendation,
        "score": int(score),
        "reasons": list(reasons),
        "risks": list(risks or []),
        "captured_at": _now(),
    })
    return _append_candidate(campaign_root, candidate)


def _live_contact_count(campaign_root: str | Path) -> int:
    return sum(
        1
        for row in load_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"))
        if row.get("mode") == "live_test" and row.get("contacted")
    )


def record_contact_decision(
    campaign_root: str | Path,
    candidate_key: str,
    mode: str,
    button_seen: bool,
    action_confirmed: bool,
    preset_message_auto_sent: bool = False,
) -> dict[str, Any]:
    if mode not in {"dry_run", "live_test"}:
        raise ValueError("mode must be dry_run or live_test")
    policy = validate_run_policy(load_json(_campaign_path(campaign_root, "run-policy.json"), default={}))
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    contact_state = candidate.get("contact") or {}
    if mode == "live_test":
        if not policy["allow_live_contact_test"]:
            raise ValueError("live contact test is not enabled")
        if not action_confirmed:
            raise ValueError("live contact requires action confirmation")
        if _live_contact_count(campaign_root) >= policy["live_contact_test_limit"]:
            raise ValueError("live contact test limit reached")
        if contact_state.get("contacted") or any(
            row.get("candidate_key") == candidate_key and row.get("mode") == "live_test" and row.get("contacted")
            for row in load_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"))
        ):
            raise ValueError("candidate already contacted")
        screening = candidate.get("screening") or {}
        if screening.get("detail_decision") != "contact":
            raise ValueError("live contact requires detail recommendation contact")
        if not contact_state.get("would_contact"):
            raise ValueError("live contact requires existing would_contact decision")

    decision = {
        "candidate_key": candidate_key,
        "mode": mode,
        "would_contact": True,
        "button_seen": bool(button_seen),
        "action_confirmed": bool(action_confirmed),
        "contacted": mode == "live_test",
        "preset_message_auto_sent": bool(preset_message_auto_sent),
        "decided_at": _now(),
    }
    append_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"), decision)

    candidate["contact"] = dict(candidate.get("contact") or {})
    previous_contacted = bool(candidate["contact"].get("contacted"))
    current_contacted = previous_contacted or mode == "live_test"
    current_live_test = bool(candidate["contact"].get("live_contact_test")) or mode == "live_test"
    current_auto_sent = bool(candidate["contact"].get("preset_message_auto_sent")) or bool(preset_message_auto_sent)
    contact_mode = candidate["contact"].get("contact_mode") if previous_contacted and mode == "dry_run" else mode
    candidate["contact"].update({
        "would_contact": True,
        "contact_mode": contact_mode,
        "contacted": current_contacted,
        "live_contact_test": current_live_test,
        "contact_button_seen": bool(button_seen),
        "preset_message_auto_sent": current_auto_sent,
    })
    _append_candidate(campaign_root, candidate)
    return decision


def backfill_real_name(
    campaign_root: str | Path,
    candidate_key: str,
    real_name: str,
    source: str,
    page_text: str | None = None,
    screenshot_hash: str | None = None,
) -> dict[str, Any]:
    if source not in {
        "communication_page_after_live_contact_test",
        "manual_opened_communication_page",
        EXTERNAL_EXECUTOR_REAL_NAME_SOURCE,
    }:
        raise ValueError("invalid real name source")
    normalized_real_name = real_name.strip()
    if not normalized_real_name:
        raise ValueError("real_name is required")
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    contact_state = candidate.get("contact") or {}
    if source == "communication_page_after_live_contact_test" and not contact_state.get("contacted"):
        raise ValueError("communication page live source requires live contacted candidate")
    existing_real_name = candidate.get("real_name")
    existing_source = candidate.get("real_name_source")
    if existing_real_name and (existing_real_name != normalized_real_name or existing_source != source):
        raise ValueError("real_name already captured")
    if screenshot_hash is None and page_text:
        screenshot_hash = screen_hash(page_text)
    candidate["real_name"] = normalized_real_name
    candidate["real_name_status"] = "captured"
    candidate["real_name_source"] = source
    candidate["contact"] = dict(contact_state)
    candidate["contact"]["communication_page_seen"] = True
    append_jsonl(_campaign_path(campaign_root, "raw/communication-pages.jsonl"), {
        "candidate_key": candidate_key,
        "real_name": normalized_real_name,
        "real_name_source": source,
        "page_text": page_text,
        "screenshot_hash": screenshot_hash,
        "captured_at": _now(),
    })
    return _append_candidate(campaign_root, candidate)


def _contact_button_text(candidate: dict[str, Any], fallback: str = "") -> str:
    detail_sections = candidate.get("detail_sections") or {}
    button_text = _clean_text(detail_sections.get("contact_button_text"))
    if button_text:
        return button_text
    if (candidate.get("contact") or {}).get("contact_button_seen"):
        return "立即沟通"
    return fallback


def _approved_contact_queue_rows(campaign_root: str | Path) -> list[dict[str, Any]]:
    return load_jsonl(_campaign_path(campaign_root, "structured/approved-contact-queue.jsonl"))


def _executor_candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    screening = candidate.get("screening") or {}
    return {
        "candidate_key": candidate.get("candidate_key"),
        "display_name": candidate.get("display_name"),
        "current_company": candidate.get("current_company"),
        "current_title": candidate.get("current_title"),
        "score": screening.get("score"),
        "reasons": list(screening.get("reasons") or []),
        "risks": list(screening.get("risks") or []),
    }


def _has_dry_run_would_contact_decision(campaign_root: str | Path, candidate_key: str) -> bool:
    return any(
        row.get("candidate_key") == candidate_key
        and row.get("mode") == "dry_run"
        and row.get("would_contact") is True
        for row in load_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"))
    )


def _require_executor_candidate(campaign_root: str | Path, candidate: dict[str, Any]) -> None:
    candidate_key = str(candidate.get("candidate_key") or "")
    screening = candidate.get("screening") or {}
    if screening.get("detail_decision") != "contact":
        raise ValueError("approved contact queue requires detail recommendation contact")
    detail_button_text = _clean_text((candidate.get("detail_sections") or {}).get("contact_button_text"))
    if detail_button_text != "立即沟通":
        raise ValueError("approved contact queue requires 立即沟通 button")
    contact_state = candidate.get("contact") or {}
    if not contact_state.get("would_contact"):
        raise ValueError("approved contact queue requires would_contact candidate")
    if not _has_dry_run_would_contact_decision(campaign_root, candidate_key):
        raise ValueError("approved contact queue requires dry-run would-contact decision")


def record_approved_contact_queue_item(
    campaign_root: str | Path,
    candidate_key: str,
    message_template_id: str = "boss-current-preset",
) -> dict[str, Any]:
    candidate = latest_candidate(campaign_root, candidate_key)
    _require_executor_candidate(campaign_root, candidate)
    payload = _executor_candidate_payload(candidate)

    item = {
        "schema": APPROVED_CONTACT_QUEUE_SCHEMA,
        "campaign_id": Path(campaign_root).name,
        **payload,
        "recommendation": "contact",
        "message_template_id": message_template_id,
        "approval_status": "approved_for_auto_contact",
        "button_seen": "立即沟通",
        "already_contacted": bool((candidate.get("contact") or {}).get("contacted")),
        "created_at": _now(),
        "approved_at": _now(),
    }
    return append_jsonl(_campaign_path(campaign_root, "structured/approved-contact-queue.jsonl"), item)


def write_current_contact_intent(
    campaign_root: str | Path,
    candidate_key: str,
    message_template_id: str = "boss-current-preset",
    now_text: str | None = None,
    expires_minutes: int = 10,
) -> dict[str, Any]:
    candidate = latest_candidate(campaign_root, candidate_key)
    _require_executor_candidate(campaign_root, candidate)
    queue_rows = _approved_contact_queue_rows(campaign_root)
    queue_item = next((row for row in queue_rows if row.get("candidate_key") == candidate_key), None)
    if queue_item is None:
        record_approved_contact_queue_item(campaign_root, candidate_key, message_template_id)

    now = datetime.fromisoformat(now_text) if now_text else datetime.now().astimezone()
    expires_at = now + timedelta(minutes=expires_minutes)
    intent_id = f"{now.strftime('%Y%m%dT%H%M%S')}-{candidate_key.split(':')[-1][:12]}"
    intent = {
        "schema": CURRENT_CONTACT_INTENT_SCHEMA,
        "intent_id": intent_id,
        "campaign_id": Path(campaign_root).name,
        **_executor_candidate_payload(candidate),
        "message_template_id": message_template_id,
        "expected_button": "立即沟通",
        "current_page": "candidate_detail",
        "approval_status": "approved_for_auto_contact",
        "created_by": "codex_screening_loop",
        "created_at": now.isoformat(timespec="seconds"),
        "expires_at": expires_at.isoformat(timespec="seconds"),
    }
    write_json(_campaign_path(campaign_root, "state/current-contact-intent.json"), intent)
    append_jsonl(_campaign_path(campaign_root, "state/events.jsonl"), {
        "schema": CURRENT_CONTACT_INTENT_SCHEMA,
        "stage": "external_executor",
        "status": "intent_written",
        "intent_id": intent_id,
        "candidate_key": candidate_key,
        "at": _now(),
    })
    return intent


def _append_executor_attempt(campaign_root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    attempt = {
        "schema": EXECUTOR_ATTEMPT_SCHEMA,
        "event_type": "attempt_finished",
        "intent_id": result.get("intent_id"),
        "candidate_key": result.get("candidate_key"),
        "result": result.get("result"),
        "button_before_click": result.get("button_before_click"),
        "message_template_id": result.get("message_template_id"),
        "message_status": result.get("message_status"),
        "real_name": result.get("real_name"),
        "stopped_reason": result.get("stopped_reason"),
        "next_action_for_codex": result.get("next_action_for_codex"),
        "started_at": result.get("started_at"),
        "finished_at": result.get("finished_at") or _now(),
    }
    return append_jsonl(_campaign_path(campaign_root, "raw/executor-contact-attempts.jsonl"), attempt)


def _append_external_executor_decision(
    campaign_root: str | Path,
    candidate_key: str,
    result: dict[str, Any],
    contacted: bool,
    preset_message_auto_sent: bool,
    skip_reason: str | None = None,
    already_contacted: bool = False,
) -> dict[str, Any]:
    decision = {
        "candidate_key": candidate_key,
        "mode": "external_executor",
        "would_contact": True,
        "button_seen": result.get("button_before_click"),
        "action_confirmed": True,
        "contacted": contacted,
        "already_contacted": already_contacted,
        "preset_message_auto_sent": preset_message_auto_sent,
        "message_template_id": result.get("message_template_id", "boss-current-preset"),
        "message_status": result.get("message_status"),
        "executor_intent_id": result.get("intent_id"),
        "executor_result": result.get("result"),
        "skip_reason": skip_reason,
        "decided_at": _now(),
    }
    append_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"), decision)

    candidate = dict(latest_candidate(campaign_root, candidate_key))
    candidate["contact"] = dict(candidate.get("contact") or {})
    candidate["contact"].update({
        "would_contact": True,
        "contact_mode": "external_executor" if contacted else candidate["contact"].get("contact_mode", "dry_run"),
        "contacted": bool(candidate["contact"].get("contacted")) or contacted,
        "live_contact_test": bool(candidate["contact"].get("live_contact_test")),
        "contact_button_seen": True,
        "already_contacted": bool(candidate["contact"].get("already_contacted")) or already_contacted,
        "preset_message_auto_sent": (
            bool(candidate["contact"].get("preset_message_auto_sent")) or preset_message_auto_sent
        ),
        "executor_result": result.get("result"),
        "message_status": result.get("message_status"),
    })
    _append_candidate(campaign_root, candidate)
    return decision


def _current_contact_intent(campaign_root: str | Path) -> dict[str, Any]:
    return load_json(_campaign_path(campaign_root, "state/current-contact-intent.json"), default={}) or {}


def consume_executor_result(campaign_root: str | Path, result_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(result_path) if result_path is not None else _campaign_path(campaign_root, "state/executor-result.json")
    result = _load_required_json_object(path)
    if result.get("schema") != EXECUTOR_RESULT_SCHEMA:
        raise ValueError("executor result schema must be boss_executor_result_v1")
    candidate_key = str(result.get("candidate_key") or "")
    if not candidate_key:
        raise ValueError("executor result candidate_key is required")
    current_intent = _current_contact_intent(campaign_root)
    if current_intent and result.get("intent_id") != current_intent.get("intent_id"):
        raise ValueError("executor result intent_id does not match current contact intent")

    _append_executor_attempt(campaign_root, result)
    result_value = result.get("result")
    if result_value == "sent":
        _append_external_executor_decision(
            campaign_root,
            candidate_key,
            result,
            contacted=True,
            preset_message_auto_sent=True,
        )
        if _clean_text(result.get("real_name")):
            backfill_real_name(
                campaign_root,
                candidate_key,
                str(result["real_name"]),
                EXTERNAL_EXECUTOR_REAL_NAME_SOURCE,
                page_text=result.get("communication_page_text"),
            )
    elif result_value == "skipped_continue_chat":
        _append_external_executor_decision(
            campaign_root,
            candidate_key,
            result,
            contacted=False,
            preset_message_auto_sent=False,
            skip_reason="continue_chat",
            already_contacted=True,
        )
    elif result_value in {"sent_unverified", "stopped"}:
        stopped_reason = str(result.get("stopped_reason") or result_value)
        write_continuation_plan(
            campaign_root,
            stage="external_executor",
            status="stopped",
            reason=stopped_reason,
            next_action="review_executor_result_before_resuming",
        )
        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        write_json(
            _campaign_path(campaign_root, f"reports/interruption-executor-{slugify(stopped_reason)}-{timestamp}.json"),
            result,
        )
    else:
        raise ValueError("unsupported executor result")
    return result


def write_continuation_plan(
    campaign_root: str | Path,
    stage: str,
    status: str,
    reason: str,
    next_action: str,
) -> dict[str, Any]:
    plan = {
        "stage": stage,
        "status": status,
        "reason": reason,
        "next_action": next_action,
        "updated_at": _now(),
    }
    write_json(_campaign_path(campaign_root, "state/continuation-plan.json"), plan)
    append_jsonl(_campaign_path(campaign_root, "state/events.jsonl"), plan)
    return plan


def _latest_candidates_by_key(campaign_root: str | Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _all_candidates(campaign_root):
        latest[str(row.get("candidate_key"))] = row
    return latest


def _candidate_signature(candidate: dict[str, Any]) -> str:
    return str(
        candidate.get("candidate_signature")
        or build_candidate_signature(candidate.get("list_snapshot") or candidate)
    )


def _distribution(candidates: list[dict[str, Any]], field: str, limit: int | None = None) -> dict[str, int]:
    counter = Counter(_clean_text(item.get(field)) or "未显示" for item in candidates)
    ordered = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if limit is not None:
        ordered = ordered[:limit]
    return dict(ordered)


def validate_executor_artifacts(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates_by_key = _latest_candidates_by_key(root)
    approved_queue = load_jsonl(root / "structured/approved-contact-queue.jsonl")
    attempts = load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    decisions = load_jsonl(root / "structured/contact-decisions.jsonl")
    current_intent = load_json(root / "state/current-contact-intent.json", default={}) or {}
    latest_result = load_json(root / "state/executor-result.json", default={}) or {}
    executor_lock = load_json(root / "state/executor.lock", default={}) or {}
    issues: list[str] = []

    invalid_queue_rows: list[str] = []
    dangling_queue_candidate_keys: list[str] = []
    for row in approved_queue:
        candidate_key = str(row.get("candidate_key") or "")
        if row.get("schema") != APPROVED_CONTACT_QUEUE_SCHEMA:
            invalid_queue_rows.append(candidate_key or "<missing>")
            issues.append("approved_queue.schema")
        candidate = candidates_by_key.get(candidate_key)
        if candidate is None:
            dangling_queue_candidate_keys.append(candidate_key or "<missing>")
            issues.append("approved_queue.candidate_key")
            continue
        if (candidate.get("screening") or {}).get("detail_decision") != "contact":
            invalid_queue_rows.append(candidate_key)
            issues.append("approved_queue.detail_decision")
        if not (candidate.get("contact") or {}).get("would_contact"):
            invalid_queue_rows.append(candidate_key)
            issues.append("approved_queue.would_contact")
        if row.get("button_seen") != "立即沟通":
            invalid_queue_rows.append(candidate_key)
            issues.append("approved_queue.button_seen")

    invalid_attempt_rows: list[str] = []
    dangling_attempt_candidate_keys: list[str] = []
    for row in attempts:
        candidate_key = str(row.get("candidate_key") or "")
        if row.get("schema") != EXECUTOR_ATTEMPT_SCHEMA:
            invalid_attempt_rows.append(candidate_key or "<missing>")
            issues.append("executor_attempt.schema")
        if candidate_key and candidate_key not in candidates_by_key:
            dangling_attempt_candidate_keys.append(candidate_key)
            issues.append("executor_attempt.candidate_key")

    invalid_current_intent = bool(current_intent) and (
        current_intent.get("schema") != CURRENT_CONTACT_INTENT_SCHEMA
        or current_intent.get("candidate_key") not in candidates_by_key
        or current_intent.get("approval_status") != "approved_for_auto_contact"
        or current_intent.get("expected_button") != "立即沟通"
        or current_intent.get("current_page") != "candidate_detail"
    )
    if current_intent:
        if current_intent.get("schema") != CURRENT_CONTACT_INTENT_SCHEMA:
            issues.append("current_intent.schema")
        if current_intent.get("candidate_key") not in candidates_by_key:
            issues.append("current_intent.candidate_key")
        if current_intent.get("approval_status") != "approved_for_auto_contact":
            issues.append("current_intent.approval_status")
        if current_intent.get("expected_button") != "立即沟通":
            issues.append("current_intent.expected_button")
        if current_intent.get("current_page") != "candidate_detail":
            issues.append("current_intent.current_page")

    if latest_result:
        if latest_result.get("schema") != EXECUTOR_RESULT_SCHEMA:
            issues.append("executor_result.schema")
        result_candidate_key = str(latest_result.get("candidate_key") or "")
        if result_candidate_key and result_candidate_key not in candidates_by_key:
            issues.append("executor_result.candidate_key")
        matching_attempt = any(
            row.get("intent_id") == latest_result.get("intent_id")
            and row.get("candidate_key") == latest_result.get("candidate_key")
            and row.get("result") == latest_result.get("result")
            for row in attempts
        )
        if not matching_attempt:
            issues.append("executor_result.missing_attempt")
        if latest_result.get("result") == "sent":
            has_sent_decision = any(
                row.get("candidate_key") == latest_result.get("candidate_key")
                and row.get("mode") == "external_executor"
                and row.get("contacted") is True
                for row in decisions
            )
            if not has_sent_decision:
                issues.append("executor_result.sent_missing_external_executor_decision")

    for row in attempts:
        if row.get("result") != "sent":
            continue
        has_sent_decision = any(
            decision.get("candidate_key") == row.get("candidate_key")
            and decision.get("mode") == "external_executor"
            and decision.get("contacted") is True
            for decision in decisions
        )
        if not has_sent_decision:
            issues.append("executor_attempt.sent_missing_external_executor_decision")

    if executor_lock:
        if executor_lock.get("schema") != EXECUTOR_LOCK_SCHEMA:
            issues.append("executor_lock.schema")
        if executor_lock.get("status") not in {"running", "finished", "stopped", "stale_lock_requires_review"}:
            issues.append("executor_lock.status")
        if executor_lock.get("candidate_key") and executor_lock.get("candidate_key") not in candidates_by_key:
            issues.append("executor_lock.candidate_key")

    status = "failed" if (
        invalid_queue_rows
        or dangling_queue_candidate_keys
        or invalid_attempt_rows
        or dangling_attempt_candidate_keys
        or invalid_current_intent
        or issues
    ) else "passed"
    report = {
        "campaign_root": str(root),
        "status": status,
        "approved_queue_count": len(approved_queue),
        "attempt_count": len(attempts),
        "latest_result": latest_result.get("result"),
        "issues": sorted(set(issues)),
        "invalid_queue_rows": sorted(set(invalid_queue_rows)),
        "dangling_queue_candidate_keys": sorted(set(dangling_queue_candidate_keys)),
        "invalid_attempt_rows": sorted(set(invalid_attempt_rows)),
        "dangling_attempt_candidate_keys": sorted(set(dangling_attempt_candidate_keys)),
        "invalid_current_intent": invalid_current_intent,
        "updated_at": _now(),
    }
    write_json(root / "reports/executor-validation.json", report)
    return report


def summarize_executor_results(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    attempts = [
        row
        for row in load_jsonl(root / "raw/executor-contact-attempts.jsonl")
        if row.get("event_type") in {"attempt_finished", "attempt_dry_run"}
    ]
    result_distribution = Counter(str(row.get("result") or "unknown") for row in attempts)
    summary = {
        "campaign_root": str(root),
        "approved_queue_count": len(load_jsonl(root / "structured/approved-contact-queue.jsonl")),
        "attempt_count": len(attempts),
        "sent_count": result_distribution.get("sent", 0),
        "skipped_continue_chat_count": result_distribution.get("skipped_continue_chat", 0),
        "stopped_count": result_distribution.get("stopped", 0) + result_distribution.get("sent_unverified", 0),
        "result_distribution": dict(sorted(result_distribution.items())),
        "message_status_distribution": dict(sorted(
            Counter(str(row.get("message_status") or "unknown") for row in attempts).items()
        )),
        "real_name_captured_count": sum(1 for row in attempts if _clean_text(row.get("real_name"))),
        "updated_at": _now(),
    }
    write_json(root / "reports/executor-summary.json", summary)
    return summary


def campaign_stats(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates = list(_latest_candidates_by_key(root).values())
    return {
        "campaign_root": str(root),
        "candidate_count": len(candidates),
        "education_distribution": _distribution(candidates, "education"),
        "work_years_distribution": _distribution(candidates, "work_years"),
        "expected_salary_distribution": _distribution(candidates, "expected_salary"),
        "active_state_distribution": _distribution(candidates, "active_state"),
        "current_company_distribution": _distribution(candidates, "current_company", limit=20),
        "current_title_distribution": _distribution(candidates, "current_title", limit=20),
        "updated_at": _now(),
    }


def validate_campaign(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates_by_key = _latest_candidates_by_key(root)
    candidates = list(candidates_by_key.values())
    decisions = load_jsonl(root / "structured/contact-decisions.jsonl")
    run_policy = validate_run_policy(_load_required_json_object(root / "run-policy.json"))

    missing_detail = [
        str(candidate.get("candidate_key"))
        for candidate in candidates
        if not (candidate.get("screening") or {}).get("detail_decision")
    ]
    missing_contact = [
        str(candidate.get("candidate_key"))
        for candidate in candidates
        if (candidate.get("screening") or {}).get("detail_decision") == "contact"
        and not (candidate.get("contact") or {}).get("would_contact")
    ]
    signatures: dict[str, list[str]] = {}
    for candidate in candidates:
        signatures.setdefault(_candidate_signature(candidate), []).append(str(candidate.get("candidate_key")))
    duplicate_signatures = {
        signature: keys
        for signature, keys in sorted(signatures.items())
        if len(set(keys)) > 1
    }
    live_contact_count = sum(1 for item in candidates if (item.get("contact") or {}).get("contacted"))
    live_contact_policy_violation = (
        live_contact_count > 0
        and (not run_policy["allow_live_contact_test"] or live_contact_count > run_policy["live_contact_test_limit"])
    )
    contact_decision_keys = {str(item.get("candidate_key")) for item in decisions}
    dangling_contact_decisions = sorted(key for key in contact_decision_keys if key not in candidates_by_key)
    status = "failed" if (
        missing_detail
        or missing_contact
        or duplicate_signatures
        or live_contact_policy_violation
        or dangling_contact_decisions
    ) else "passed"

    report = {
        "campaign_root": str(root),
        "status": status,
        "candidate_count": len(candidates),
        "list_card_count": len(load_jsonl(root / "raw/list-cards.jsonl")),
        "detail_count": sum(1 for item in candidates if (item.get("screening") or {}).get("detail_decision")),
        "contact_decision_count": len(decisions),
        "would_contact_count": sum(1 for item in candidates if (item.get("contact") or {}).get("would_contact")),
        "live_contact_count": live_contact_count,
        "missing_detail_candidate_keys": missing_detail,
        "missing_contact_candidate_keys": missing_contact,
        "duplicate_signature_count": len(duplicate_signatures),
        "duplicate_signatures": duplicate_signatures,
        "dangling_contact_decision_candidate_keys": dangling_contact_decisions,
        "live_contact_policy_violation": live_contact_policy_violation,
        "updated_at": _now(),
    }
    write_json(root / "reports/validation.json", report)
    return report


def _load_required_json_object(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    if not file.exists():
        raise ValueError(f"required JSON file is missing: {file}")
    try:
        value = json.loads(file.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{file}: invalid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{file}: must be a JSON object")
    return value


def summarize_campaign(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates = list(_latest_candidates_by_key(root).values())
    decisions = load_jsonl(root / "structured/contact-decisions.jsonl")
    continuation_plan = load_json(root / "state/continuation-plan.json", default={})
    run_policy = validate_run_policy(_load_required_json_object(root / "run-policy.json"))
    real_name_status_distribution = Counter(str(item.get("real_name_status") or "unknown") for item in candidates)
    skipped_candidates = [
        item for item in candidates if (item.get("screening") or {}).get("detail_decision") == "skip"
    ]
    skip_reason_distribution: Counter[str] = Counter()
    for item in skipped_candidates:
        reasons = (item.get("screening") or {}).get("reasons") or ["未记录原因"]
        for reason in reasons:
            skip_reason_distribution[str(reason)] += 1
    manual_review_candidates = [
        {
            "candidate_key": item.get("candidate_key"),
            "display_name": item.get("display_name"),
            "detail_decision": (item.get("screening") or {}).get("detail_decision"),
            "reasons": (item.get("screening") or {}).get("reasons", []),
        }
        for item in candidates
        if (item.get("screening") or {}).get("detail_decision") in {"hold", "skip"}
        or not (item.get("screening") or {}).get("detail_decision")
    ]
    live_contact_count = sum(1 for item in candidates if (item.get("contact") or {}).get("contacted"))
    detail_count = sum(1 for item in candidates if (item.get("screening") or {}).get("detail_decision"))
    summary = {
        "campaign_root": str(root),
        "candidate_count": len(candidates),
        "list_card_count": len(load_jsonl(root / "raw/list-cards.jsonl")),
        "detail_count": detail_count,
        "would_contact_count": sum(1 for item in candidates if (item.get("contact") or {}).get("would_contact")),
        "live_contact_count": live_contact_count,
        "live_contact_limit": run_policy["live_contact_test_limit"],
        "live_contact_remaining": max(0, run_policy["live_contact_test_limit"] - live_contact_count),
        "real_name_captured_count": sum(1 for item in candidates if item.get("real_name_status") == "captured"),
        "real_name_status_distribution": dict(sorted(real_name_status_distribution.items())),
        "skip_count": len(skipped_candidates),
        "skip_reason_distribution": dict(sorted(skip_reason_distribution.items())),
        "manual_review_candidates": manual_review_candidates,
        "contact_decision_count": len(decisions),
        "continuation": continuation_plan,
        "updated_at": _now(),
    }
    write_json(root / "reports/sourcing-summary.json", summary)
    manual_review_lines = [
        f"- {item['display_name']} ({item['candidate_key']}): {item['detail_decision'] or 'pending'}"
        for item in manual_review_candidates
    ] or ["- 无"]
    skip_reason_lines = [
        f"- {reason}：{count}" for reason, count in summary["skip_reason_distribution"].items()
    ] or ["- 无"]
    real_name_status_lines = [
        f"- {status}：{count}" for status, count in summary["real_name_status_distribution"].items()
    ] or ["- 无"]
    markdown = "\n".join([
        "# BOSS App 寻访摘要",
        "",
        f"- 候选人总数：{summary['candidate_count']}",
        f"- 列表卡片采集：{summary['list_card_count']}",
        f"- 详情采集：{summary['detail_count']}",
        f"- Would contact：{summary['would_contact_count']}",
        f"- Live-test 真实沟通：{summary['live_contact_count']}",
        f"- Live-test 剩余额度：{summary['live_contact_remaining']}",
        f"- 真实姓名补全：{summary['real_name_captured_count']}",
        f"- 详情淘汰：{summary['skip_count']}",
        f"- 恢复状态：{continuation_plan.get('status', '')}",
        f"- 下一步：{continuation_plan.get('next_action', '')}",
        "",
        "## 跳过原因分布",
        "",
        *skip_reason_lines,
        "",
        "## 真实姓名补全状态",
        "",
        *real_name_status_lines,
        "",
        "## 人工复核清单",
        "",
        *manual_review_lines,
        "",
    ])
    (root / "reports/sourcing-summary.md").write_text(markdown, encoding="utf-8")
    return summary


ACTIVE_STATE_MARKERS = [
    "刚刚活跃",
    "今日活跃",
    "本周活跃",
    "3日内活跃",
    "月内活跃",
    "在线",
]


def _extract_descriptions(accessibility_text: str) -> list[str]:
    descriptions: list[str] = []
    current: str | None = None
    for raw_line in accessibility_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if "Description:" in line:
            if current:
                descriptions.append(current.strip())
            current = line.split("Description:", 1)[1].split(", Secondary Actions:", 1)[0].strip()
        elif current is not None and not re.match(r"^\d+\s+", line):
            current += "\n" + line
    if current:
        descriptions.append(current.strip())
    return descriptions


CARD_PATTERN = re.compile(
    r"(?:^|[，,]\s*)(?P<display_name>[^,，\n]+?),\s*"
    r"(?P<age>\d+岁)\s*\|\s*"
    r"(?P<work_years>[^|]+?)\s*\|\s*"
    r"(?P<education>[^|]+?)\s*\|\s*"
    r"(?P<expected_salary>[^,，\n]+)"
)


def _split_company_title(value: str) -> tuple[str, str] | None:
    text = _clean_text(value).replace("·", " · ")
    if " · " not in text:
        return None
    company, title = [part.strip() for part in text.rsplit(" · ", 1)]
    if not company or not title:
        return None
    if "求职期望" in company or "岁" in company:
        return None
    return company, title


def _active_state_from_text(value: str) -> str:
    for marker in ACTIVE_STATE_MARKERS:
        if marker in value:
            return marker
    return ""


def parse_list_cards_from_accessibility_text(
    accessibility_text: str,
    list_scroll_batch: int | None = None,
) -> list[dict[str, Any]]:
    descriptions = _extract_descriptions(accessibility_text)
    cards: list[dict[str, Any]] = []
    for index, description in enumerate(descriptions):
        match = CARD_PATTERN.search(description)
        if not match:
            continue
        card_position = len(cards) + 1
        card = {
            "display_name": match.group("display_name").strip(),
            "age": match.group("age").strip(),
            "work_years": match.group("work_years").strip(),
            "education": match.group("education").strip(),
            "expected_salary": match.group("expected_salary").strip(),
            "active_state": _active_state_from_text(description),
            "list_scroll_batch": list_scroll_batch,
            "card_position": card_position,
            "list_decision": "detail_for_all",
            "raw_text": description,
            "screen_region": f"visible_card_{card_position}",
        }
        for next_description in descriptions[index + 1:]:
            if CARD_PATTERN.search(next_description):
                break
            company_title = _split_company_title(next_description)
            if company_title:
                card["current_company"], card["current_title"] = company_title
                break
        cards.append(card)
    return cards


SECTION_MARKERS = ["求职期望", "工作经历", "项目经历", "教育经历", "所获荣誉"]


def _section_text(descriptions: list[str], start_marker: str, end_markers: list[str]) -> str:
    try:
        start = next(index for index, value in enumerate(descriptions) if value == start_marker)
    except StopIteration:
        return ""
    end = len(descriptions)
    for index in range(start + 1, len(descriptions)):
        if descriptions[index] in end_markers or descriptions[index] == "立即沟通":
            end = index
            break
    return "；".join(value for value in descriptions[start + 1:end] if value and value not in SECTION_MARKERS)


def parse_detail_sections_from_accessibility_text(accessibility_text: str) -> dict[str, Any]:
    descriptions = _extract_descriptions(accessibility_text)
    first_section_index = next(
        (index for index, value in enumerate(descriptions) if value in SECTION_MARKERS),
        len(descriptions),
    )
    profile_header = "；".join(
        value for value in descriptions[:first_section_index] if value and value != "立即沟通"
    )
    expectation = _section_text(descriptions, "求职期望", ["工作经历", "项目经历", "教育经历", "所获荣誉"])
    work = _section_text(descriptions, "工作经历", ["项目经历", "教育经历", "所获荣誉"])
    project = _section_text(descriptions, "项目经历", ["教育经历", "所获荣誉"])
    education = _section_text(descriptions, "教育经历", ["所获荣誉"])
    honors = _section_text(descriptions, "所获荣誉", [])
    return {
        "bottom_reached": bool(education or honors),
        "contact_button_text": "立即沟通" if "立即沟通" in descriptions else "",
        "profile_header": profile_header,
        "expectation": expectation,
        "work_experience": work,
        "project_experience": project,
        "education": education,
        "honors": honors,
    }


def build_all_match_detail_decision(detail_sections: dict[str, Any]) -> dict[str, Any]:
    text = "\n".join(str(value) for value in detail_sections.values())
    risks: list[str] = []
    if "暂不考虑" in text:
        risks.append("候选状态显示暂不考虑；本轮按用户要求仍只做 dry-run would-contact")
    if re.search(r"只看\s*CTO|CTO\s*岗位", text, flags=re.IGNORECASE):
        risks.append("候选人个人描述限定 CTO 岗位，后续真实沟通前需复核岗位匹配")
    if "测试经理" in text or "测试总监" in text:
        risks.append("候选人期望测试经理/测试总监，后续真实沟通前需复核岗位匹配")
    reasons = ["无筛选条件，列表中全部人选视为匹配", "详情页已采集"]
    if detail_sections.get("contact_button_text") == "立即沟通":
        reasons.append("立即沟通按钮可见")
    return {
        "recommendation": "contact",
        "score": 100,
        "reasons": reasons,
        "risks": risks,
    }


def _json_arg(value: str) -> dict[str, Any]:
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("--json must be a JSON object")
    return data


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOSS App recommendation sourcing helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--campaign-id", required=True)
    init_parser.add_argument("--filters-text", required=True)
    init_parser.add_argument("--out-base", default="data/campaigns")
    init_parser.add_argument("--date", default=date.today().isoformat())
    init_parser.add_argument("--allow-real-contact", action="store_true")
    init_parser.add_argument("--allow-live-contact-test", action="store_true")
    init_parser.add_argument("--live-contact-test-limit", type=int, default=0)

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--campaign-root", required=True)

    record_list_parser = subparsers.add_parser("record-list-card")
    record_list_parser.add_argument("--campaign-root", required=True)
    record_list_parser.add_argument("--json", required=True)

    record_detail_parser = subparsers.add_parser("record-detail")
    record_detail_parser.add_argument("--campaign-root", required=True)
    record_detail_parser.add_argument("--candidate-key", required=True)
    record_detail_parser.add_argument("--json", required=True)

    dry_run_parser = subparsers.add_parser("record-dry-run-contact")
    dry_run_parser.add_argument("--campaign-root", required=True)
    dry_run_parser.add_argument("--candidate-key", required=True)
    dry_run_parser.add_argument("--button-seen", action="store_true")

    complete_parser = subparsers.add_parser("complete")
    complete_parser.add_argument("--campaign-root", required=True)
    complete_parser.add_argument("--reason", required=True)
    complete_parser.add_argument("--next-action", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--campaign-root", required=True)

    stats_parser = subparsers.add_parser("stats")
    stats_parser.add_argument("--campaign-root", required=True)

    parse_list_parser = subparsers.add_parser("parse-list-state")
    parse_list_parser.add_argument("--text", default="")
    parse_list_parser.add_argument("--text-file")
    parse_list_parser.add_argument("--list-scroll-batch", type=int)

    parse_detail_parser = subparsers.add_parser("parse-detail-state")
    parse_detail_parser.add_argument("--text", default="")
    parse_detail_parser.add_argument("--text-file")

    return parser


def _load_text_arg(text: str, text_file: str | None) -> str:
    if text_file:
        return Path(text_file).read_text(encoding="utf-8-sig")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        manifest = init_campaign(
            campaign_id=args.campaign_id,
            filters_text=args.filters_text,
            out_base=args.out_base,
            date_text=args.date,
            allow_real_contact=args.allow_real_contact,
            allow_live_contact_test=args.allow_live_contact_test,
            live_contact_test_limit=args.live_contact_test_limit,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    if args.command == "summarize":
        summary = summarize_campaign(args.campaign_root)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if args.command == "record-list-card":
        candidate = record_list_card(args.campaign_root, _json_arg(args.json))
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
        return 0
    if args.command == "record-detail":
        payload = _json_arg(args.json)
        candidate = record_detail_update(
            args.campaign_root,
            args.candidate_key,
            payload.get("detail_sections") or {},
            payload.get("recommendation", "contact"),
            int(payload.get("score", 0)),
            list(payload.get("reasons") or []),
            list(payload.get("risks") or []),
        )
        print(json.dumps(candidate, ensure_ascii=False, indent=2))
        return 0
    if args.command == "record-dry-run-contact":
        decision = record_contact_decision(
            args.campaign_root,
            args.candidate_key,
            mode="dry_run",
            button_seen=bool(args.button_seen),
            action_confirmed=False,
        )
        print(json.dumps(decision, ensure_ascii=False, indent=2))
        return 0
    if args.command == "complete":
        plan = write_continuation_plan(
            args.campaign_root,
            "detail_capture",
            "completed_after_dry_run",
            args.reason,
            args.next_action,
        )
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if args.command == "validate":
        report = validate_campaign(args.campaign_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "passed" else 1
    if args.command == "stats":
        stats = campaign_stats(args.campaign_root)
        print(json.dumps(stats, ensure_ascii=False, indent=2))
        return 0
    if args.command == "parse-list-state":
        cards = parse_list_cards_from_accessibility_text(
            _load_text_arg(args.text, args.text_file),
            list_scroll_batch=args.list_scroll_batch,
        )
        print(json.dumps(cards, ensure_ascii=False, indent=2))
        return 0
    if args.command == "parse-detail-state":
        detail = parse_detail_sections_from_accessibility_text(_load_text_arg(args.text, args.text_file))
        print(json.dumps(detail, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
