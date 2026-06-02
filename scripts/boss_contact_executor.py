from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scripts import boss_app_sourcing


POLICY_SCHEMA = "boss_contact_executor_policy_v1"
INTENT_SCHEMA = "boss_current_contact_intent_v1"
RESULT_SCHEMA = "boss_executor_result_v1"
ATTEMPT_SCHEMA = "boss_contact_attempt_event_v1"
LOCK_SCHEMA = "boss_executor_lock_v1"
ACKNOWLEDGEMENT = "I understand this sends real messages to third-party candidates."
SUCCESS_MESSAGE_STATUSES = {"送达", "已读", "已触达"}
PAID_MARKERS = {
    "搜索畅聊卡",
    "剩余次数不足",
    "立即开聊",
    "立即联系牛人",
    "付费",
    "畅聊卡",
}
SECURITY_MARKERS = {
    "验证码",
    "安全验证",
    "登录",
    "重新登录",
    "账号异常",
    "身份验证",
}
MARKETING_MARKERS = {
    "热搜牛人推荐",
    "查看更多牛人",
    "去看看",
}

BOOLEAN_POLICY_FIELDS = [
    "allow_real_contact",
    "require_execute_flag",
    "skip_continue_chat",
    "stop_on_paid_prompt",
    "stop_on_captcha",
    "stop_on_login_or_security_page",
    "stop_on_unknown_ui",
    "capture_real_name_after_contact",
]

INTEGER_POLICY_FIELDS = [
    "max_contacts_per_run",
    "max_contacts_per_day",
]


@dataclass
class BossPageSnapshot:
    front_app: str
    window_title: str
    page_text: str
    buttons: list[str]
    screenshot_hash: str = ""


@dataclass
class ContactButtonState:
    label: str
    count: int


@dataclass
class CommunicationResult:
    real_name: str
    message_status: str
    page_text: str


def _campaign_path(campaign_root: str | Path, relative: str) -> Path:
    return Path(campaign_root) / relative


def _load_required_json_object(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    try:
        data = json.loads(file.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing JSON file: {file}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{file}: invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{file}: JSON object is required")
    return data


def _require_schema(data: dict[str, Any], expected_schema: str, label: str) -> None:
    if data.get("schema") != expected_schema:
        raise ValueError(f"{label}.schema must be {expected_schema}")


def load_executor_policy(campaign_root: str | Path) -> dict[str, Any]:
    policy = _load_required_json_object(_campaign_path(campaign_root, "executor-policy.json"))
    _require_schema(policy, POLICY_SCHEMA, "executor_policy")
    return policy


def validate_executor_policy(policy: dict[str, Any], execute: bool) -> dict[str, Any]:
    if not isinstance(policy, dict):
        raise ValueError("executor_policy must be a dict")
    _require_schema(policy, POLICY_SCHEMA, "executor_policy")

    for field in BOOLEAN_POLICY_FIELDS:
        if not isinstance(policy.get(field), bool):
            raise ValueError(f"{field} must be a bool")

    for field in INTEGER_POLICY_FIELDS:
        value = policy.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field} must be an int")

    if policy["max_contacts_per_run"] != 1:
        raise ValueError("max_contacts_per_run must be 1 for MVP")

    if execute:
        if policy["allow_real_contact"] is not True:
            raise ValueError("allow_real_contact must be true when execute is true")
        if policy.get("operator_acknowledgement") != ACKNOWLEDGEMENT:
            raise ValueError("operator_acknowledgement must exactly match the required acknowledgement")

    validated = dict(policy)
    validated["execute"] = bool(execute)
    return validated


def load_current_intent(campaign_root: str | Path) -> dict[str, Any]:
    intent = _load_required_json_object(_campaign_path(campaign_root, "state/current-contact-intent.json"))
    return intent


def _require_non_empty_fields(data: dict[str, Any], fields: list[str], label: str) -> None:
    missing = [field for field in fields if not str(data.get(field) or "").strip()]
    if missing:
        raise ValueError(f"{label} requires non-empty {', '.join(missing)}")


def _parse_aware_iso_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO datetime") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include timezone info")
    return parsed


def validate_current_intent(intent: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    if not isinstance(intent, dict):
        raise ValueError("current_intent must be a dict")
    _require_schema(intent, INTENT_SCHEMA, "current_intent")
    if intent.get("approval_status") != "approved_for_auto_contact":
        raise ValueError("approval_status must be approved_for_auto_contact")
    if intent.get("expected_button") != "立即沟通":
        raise ValueError("expected_button must be 立即沟通")
    if intent.get("current_page") != "candidate_detail":
        raise ValueError("current_page must be candidate_detail")

    _require_non_empty_fields(
        intent,
        [
            "intent_id",
            "campaign_id",
            "candidate_key",
            "display_name",
            "current_company",
            "current_title",
            "expires_at",
        ],
        "current_intent",
    )

    if now_text:
        now = _parse_aware_iso_datetime(now_text, "now_text")
    else:
        now = datetime.now().astimezone()
    expires_at = _parse_aware_iso_datetime(str(intent["expires_at"]), "expires_at")
    if now > expires_at:
        raise ValueError("current contact intent expired")
    return intent


def write_executor_result(campaign_root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("executor result must be a dict")
    payload = {**result, "schema": RESULT_SCHEMA}
    boss_app_sourcing.write_json(_campaign_path(campaign_root, "state/executor-result.json"), payload)
    return payload


def append_attempt_event(campaign_root: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict):
        raise ValueError("attempt event must be a dict")
    payload = {**event, "schema": ATTEMPT_SCHEMA}
    return boss_app_sourcing.append_jsonl(_campaign_path(campaign_root, "raw/executor-contact-attempts.jsonl"), payload)


def _contains_any(text: str, markers: set[str] | list[str] | tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _snapshot_from_mapping(data: dict[str, Any]) -> BossPageSnapshot:
    return BossPageSnapshot(
        front_app=_clean(data.get("front_app")),
        window_title=_clean(data.get("window_title")),
        page_text=_clean(data.get("page_text")),
        buttons=[_clean(button) for button in data.get("buttons") or [] if _clean(button)],
        screenshot_hash=_clean(data.get("screenshot_hash")),
    )


class FixtureBossUI:
    def __init__(self, fixture_path: str | Path):
        self.fixture_path = Path(fixture_path)
        self.fixture = _load_required_json_object(self.fixture_path)
        self.clicked = False

    def read_current_page(self) -> BossPageSnapshot:
        detail = self.fixture.get("detail")
        if not isinstance(detail, dict):
            raise ValueError("fixture detail must be a JSON object")
        return _snapshot_from_mapping(detail)

    def find_contact_button(self, page: BossPageSnapshot) -> ContactButtonState:
        contact_labels = ["立即沟通", "继续沟通", "立即联系牛人", "立即开聊"]
        matches = [button for button in page.buttons if button in contact_labels]
        if matches:
            return ContactButtonState(label=matches[0], count=len(matches))
        return ContactButtonState(label="", count=0)

    def click_contact(self, button: ContactButtonState) -> None:
        if button.label != "立即沟通":
            raise ValueError("fixture can only click 立即沟通")
        self.clicked = True

    def wait_for_communication_page(self) -> BossPageSnapshot:
        communication = self.fixture.get("communication")
        if not isinstance(communication, dict):
            raise ValueError("fixture communication must be a JSON object")
        return _snapshot_from_mapping(communication)

    def extract_communication_result(self, page: BossPageSnapshot) -> CommunicationResult:
        real_name = ""
        name_match = re.search(r"沟通页顶部[:：]\s*([^；;，,\s]+)", page.page_text)
        if name_match:
            real_name = name_match.group(1).strip()
            if real_name == "未知":
                real_name = ""
        if not real_name and page.window_title not in {"沟通页", "未知"}:
            real_name = page.window_title

        message_status = ""
        status_match = re.search(r"消息状态[:：]\s*([^；;，,\s]+)", page.page_text)
        if status_match:
            message_status = status_match.group(1).strip()
        return CommunicationResult(real_name=real_name, message_status=message_status, page_text=page.page_text)


def validate_page_match(page: BossPageSnapshot, intent: dict[str, Any]) -> None:
    if page.front_app != "BOSS直聘":
        raise ValueError("front_app must be BOSS直聘")
    page_text = page.page_text
    for field in ["display_name", "current_company", "current_title"]:
        expected = _clean(intent.get(field))
        if expected and expected not in page_text and expected not in page.window_title:
            raise ValueError(f"current page does not match intent {field}")


def classify_button(page: BossPageSnapshot, button: ContactButtonState) -> dict[str, str]:
    combined_text = " ".join([page.page_text, *page.buttons])
    if _contains_any(combined_text, SECURITY_MARKERS):
        return {"classification": "stopped", "stopped_reason": "login_or_security_page"}
    if _contains_any(combined_text, PAID_MARKERS):
        return {"classification": "stopped", "stopped_reason": "paid_search_chat_card"}
    if _contains_any(combined_text, MARKETING_MARKERS):
        return {"classification": "stopped", "stopped_reason": "marketing_or_unknown_ui"}
    if button.count != 1:
        return {"classification": "stopped", "stopped_reason": "contact_button_count_anomaly"}
    if button.label == "继续沟通":
        return {"classification": "continue_chat", "stopped_reason": ""}
    if button.label == "立即沟通":
        return {"classification": "ready", "stopped_reason": ""}
    return {"classification": "stopped", "stopped_reason": "unknown_contact_button"}


def acquire_lock(
    campaign_root: str | Path,
    intent: dict[str, Any],
    now_text: str | None = None,
) -> dict[str, Any]:
    lock_path = _campaign_path(campaign_root, "state/executor.lock")
    if lock_path.exists():
        existing = boss_app_sourcing.load_json(lock_path)
        if isinstance(existing, dict) and existing.get("status") == "running":
            raise RuntimeError("stale_lock_requires_review")
        try:
            lock_path.replace(lock_path.with_name("executor.lock.previous"))
        except FileNotFoundError:
            pass
    payload = {
        "schema": LOCK_SCHEMA,
        "lock_id": uuid.uuid4().hex,
        "intent_id": intent.get("intent_id"),
        "candidate_key": intent.get("candidate_key"),
        "pid": os.getpid(),
        "status": "running",
        "created_at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    except FileExistsError as exc:
        raise RuntimeError("stale_lock_requires_review") from exc
    return payload


def finish_lock(campaign_root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    lock_path = _campaign_path(campaign_root, "state/executor.lock")
    lock = boss_app_sourcing.load_json(lock_path, default={}) or {}
    if not isinstance(lock, dict):
        lock = {}
    payload = {
        **lock,
        "schema": LOCK_SCHEMA,
        "status": "finished",
        "finished_at": result.get("created_at") or datetime.now().astimezone().isoformat(timespec="seconds"),
        "result": result.get("result"),
    }
    boss_app_sourcing.write_json(lock_path, payload)
    return payload


def _base_result(intent: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    return {
        "intent_id": intent.get("intent_id"),
        "campaign_id": intent.get("campaign_id"),
        "candidate_key": intent.get("candidate_key"),
        "display_name": intent.get("display_name"),
        "current_company": intent.get("current_company"),
        "current_title": intent.get("current_title"),
        "message_template_id": intent.get("message_template_id"),
        "created_at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _attempt_payload(event_type: str, result: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "intent_id": result.get("intent_id"),
        "campaign_id": result.get("campaign_id"),
        "candidate_key": result.get("candidate_key"),
        "result": result.get("result"),
        "action": result.get("action"),
        "button_before_click": result.get("button_before_click"),
        "message_template_id": result.get("message_template_id"),
        "at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def _require_ui(ui: Any | None) -> Any:
    if ui is not None:
        return ui
    adapter = globals().get("MacAccessibilityBossUI")
    if adapter is not None:
        return adapter()
    raise ValueError("ui is required until MacAccessibilityBossUI is implemented")


def _check_kill_switch(policy: dict[str, Any]) -> None:
    kill_switch_path = _clean(policy.get("kill_switch_path"))
    if kill_switch_path and Path(kill_switch_path).exists():
        raise RuntimeError("executor_kill_switch_enabled")


def contact_current(
    campaign_root: str | Path,
    execute: bool = False,
    ui: Any | None = None,
    now_text: str | None = None,
) -> dict[str, Any]:
    policy = validate_executor_policy(load_executor_policy(campaign_root), execute=execute)
    intent = validate_current_intent(load_current_intent(campaign_root), now_text=now_text)
    _check_kill_switch(policy)
    ui = _require_ui(ui)

    locked = False
    attempt_started = False
    clicked_contact = False
    result = _base_result(intent, now_text=now_text)
    try:
        acquire_lock(campaign_root, intent, now_text=now_text)
        locked = True
        append_attempt_event(campaign_root, _attempt_payload("attempt_started", result, now_text=now_text))
        attempt_started = True

        page = ui.read_current_page()
        validate_page_match(page, intent)
        button = ui.find_contact_button(page)
        classification = classify_button(page, button)
        result["button_before_click"] = button.label

        if classification["classification"] == "continue_chat":
            result.update({"result": "skipped_continue_chat", "would_click": False})
        elif classification["classification"] == "stopped":
            result.update({
                "result": "stopped",
                "stopped_reason": classification["stopped_reason"],
                "would_click": False,
            })
        elif not execute:
            result.update({"result": "dry_run_ready", "would_click": True})
        else:
            ui.click_contact(button)
            clicked_contact = True
            result["action"] = "click_contact"
            try:
                communication_page = ui.wait_for_communication_page()
                communication_result = ui.extract_communication_result(communication_page)
            except Exception as exc:
                result.update({
                    "result": "sent_unverified",
                    "stopped_reason": str(exc),
                    "would_click": True,
                })
            else:
                result.update({
                    "real_name": communication_result.real_name,
                    "message_status": communication_result.message_status,
                    "communication_page_text": communication_result.page_text,
                    "would_click": True,
                })
                if (
                    communication_result.real_name
                    and communication_result.message_status in SUCCESS_MESSAGE_STATUSES
                ):
                    result["result"] = "sent"
                else:
                    result["result"] = "sent_unverified"
                    result["stopped_reason"] = "communication_result_unverified"

        write_executor_result(campaign_root, result)
        append_attempt_event(campaign_root, _attempt_payload("attempt_finished", result, now_text=now_text))
        return result
    except Exception as exc:
        if clicked_contact:
            result.update({
                "result": "sent_unverified",
                "stopped_reason": str(exc),
            })
        else:
            result.update({
                "result": "stopped",
                "stopped_reason": str(exc),
            })
        write_executor_result(campaign_root, result)
        if attempt_started:
            append_attempt_event(campaign_root, _attempt_payload("attempt_finished", result, now_text=now_text))
        raise
    finally:
        if locked:
            finish_lock(campaign_root, result)
