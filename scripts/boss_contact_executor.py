from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
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

    now = datetime.fromisoformat(now_text) if now_text else datetime.now().astimezone()
    expires_at = datetime.fromisoformat(str(intent["expires_at"]))
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
