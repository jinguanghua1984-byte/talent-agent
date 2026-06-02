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
CONTACT_BUTTON_LABELS = ["立即沟通", "继续沟通", "立即联系牛人"]
COMMUNICATION_PAGE_MARKERS = ["沟通的职位", "求简历", "换电话"]
JXA_READ_UI = r"""
function run() {
  const systemEvents = Application("System Events");
  const frontProcesses = systemEvents.processes.whose({frontmost: true})();
  if (frontProcesses.length === 0) {
    return JSON.stringify({front_app: "", window_title: "", texts: [], buttons: []});
  }

  const process = frontProcesses[0];
  const windows = process.windows();
  const window = windows.length > 0 ? windows[0] : null;
  const texts = [];
  const buttons = [];

  function valueOf(element) {
    const candidates = ["value", "description", "title", "name"];
    for (const key of candidates) {
      try {
        const value = element[key]();
        if (value !== null && value !== undefined && String(value).trim() !== "") {
          return String(value).trim();
        }
      } catch (error) {}
    }
    return "";
  }

  function collect(element) {
    let role = "";
    try {
      role = String(element.role());
    } catch (error) {}
    const value = valueOf(element);
    if (value) {
      if (role === "AXButton") {
        buttons.push(value);
      } else {
        texts.push(value);
      }
    }
    try {
      const children = element.entireContents();
      for (const child of children) {
        collect(child);
      }
    } catch (error) {}
  }

  if (window) {
    collect(window);
  }

  let windowTitle = "";
  try {
    windowTitle = window ? String(window.name()) : "";
  } catch (error) {}

  return JSON.stringify({
    front_app: String(process.name()),
    window_title: windowTitle,
    texts: texts,
    buttons: buttons,
  });
}
"""
JXA_CLICK_EXACT_BUTTON = r"""
function run() {
  const targetLabel = __BUTTON_LABEL__;
  const systemEvents = Application("System Events");
  const frontProcesses = systemEvents.processes.whose({frontmost: true})();
  if (frontProcesses.length === 0) {
    return JSON.stringify({clicked: false, reason: "no_front_app"});
  }

  const process = frontProcesses[0];
  if (String(process.name()) !== "BOSS直聘") {
    return JSON.stringify({
      clicked: false,
      reason: "front_app_not_boss",
      front_app: String(process.name()),
      match_count: 0,
    });
  }

  const windows = process.windows();
  if (windows.length === 0) {
    return JSON.stringify({clicked: false, reason: "no_window", match_count: 0});
  }
  const matches = [];

  function labelOf(element) {
    const candidates = ["title", "name", "description", "value"];
    for (const key of candidates) {
      try {
        const value = element[key]();
        if (value !== null && value !== undefined && String(value).trim() !== "") {
          return String(value).trim();
        }
      } catch (error) {}
    }
    return "";
  }

  function collectExact(element) {
    let role = "";
    try {
      role = String(element.role());
    } catch (error) {}
    if (role === "AXButton" && labelOf(element) === targetLabel) {
      matches.push(element);
    }
    try {
      const children = element.entireContents();
      for (const child of children) {
        collectExact(child);
      }
    } catch (error) {}
  }

  collectExact(windows[0]);
  if (matches.length !== 1) {
    return JSON.stringify({
      clicked: false,
      reason: matches.length === 0 ? "button_not_found" : "ambiguous_button_count",
      match_count: matches.length,
    });
  }
  matches[0].click();
  return JSON.stringify({clicked: true, match_count: 1});
}
"""

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


class UIStopError(ValueError):
    """Raised when the current BOSS UI cannot be safely acted on."""


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
            raise UIStopError("fixture can only click 立即沟通")
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


class MacAccessibilityBossUI:
    def __init__(self, timeout_seconds: int = 10, poll_seconds: float = 0.5, max_wait_seconds: int = 8):
        self.timeout_seconds = timeout_seconds
        self.poll_seconds = poll_seconds
        self.max_wait_seconds = max_wait_seconds

    def _run_jxa(self, script: str) -> dict[str, Any]:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            check=True,
            timeout=self.timeout_seconds,
        )
        payload = json.loads(result.stdout or "{}")
        if not isinstance(payload, dict):
            raise ValueError("JXA result must be a JSON object")
        return payload

    def read_current_page(self) -> BossPageSnapshot:
        payload = self._run_jxa(JXA_READ_UI)
        texts = self._clean_list(payload.get("texts"))
        buttons = self._clean_list(payload.get("buttons"))
        page_text = " ".join(dict.fromkeys([*texts, *buttons]))
        return BossPageSnapshot(
            front_app=_clean(payload.get("front_app")),
            window_title=_clean(payload.get("window_title")),
            page_text=page_text,
            buttons=buttons,
            screenshot_hash=boss_app_sourcing.screen_hash(page_text),
        )

    def find_contact_button(self, page: BossPageSnapshot) -> ContactButtonState:
        matches = [button for button in page.buttons if button in CONTACT_BUTTON_LABELS]
        if matches:
            return ContactButtonState(label=matches[0], count=len(matches))
        return ContactButtonState(label="", count=0)

    def click_contact(self, button: ContactButtonState) -> dict[str, Any]:
        if button.label != "立即沟通":
            raise ValueError("MacAccessibilityBossUI can only click 立即沟通")
        script = JXA_CLICK_EXACT_BUTTON.replace("__BUTTON_LABEL__", json.dumps(button.label, ensure_ascii=False))
        result = self._run_jxa(script)
        if result.get("clicked") is not True:
            reason = _clean(result.get("reason")) or "exact contact button was not clicked"
            raise UIStopError(reason)
        return result

    def wait_for_communication_page(self) -> BossPageSnapshot:
        deadline = time.monotonic() + self.max_wait_seconds
        last_snapshot = self.read_current_page()
        while True:
            if _contains_any(last_snapshot.page_text, COMMUNICATION_PAGE_MARKERS):
                return last_snapshot
            if time.monotonic() >= deadline:
                raise ValueError("communication page not confirmed")
            time.sleep(self.poll_seconds)
            last_snapshot = self.read_current_page()

    def extract_communication_result(self, page: BossPageSnapshot) -> CommunicationResult:
        if not _contains_any(page.page_text, COMMUNICATION_PAGE_MARKERS):
            return CommunicationResult(real_name="", message_status="", page_text=page.page_text)

        message_status = ""
        for status in SUCCESS_MESSAGE_STATUSES:
            if status in page.page_text:
                message_status = status
                break

        real_name = ""
        if page.window_title.strip() not in {"", "沟通页", "BOSS直聘"}:
            real_name = page.window_title.strip()
        if not real_name:
            name_match = re.search(r"(?:沟通页顶部|候选人|姓名)[:：]\s*([^；;，,\s]+)", page.page_text)
            if name_match:
                parsed_name = name_match.group(1).strip()
                if parsed_name not in {"未知", "沟通页", "BOSS直聘"}:
                    real_name = parsed_name
        return CommunicationResult(real_name=real_name, message_status=message_status, page_text=page.page_text)

    @staticmethod
    def _clean_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [_clean(item) for item in value if _clean(item)]


def validate_page_match(page: BossPageSnapshot, intent: dict[str, Any]) -> None:
    if page.front_app != "BOSS直聘":
        raise UIStopError("front_app must be BOSS直聘")
    page_text = page.page_text
    for field in ["display_name", "current_company", "current_title"]:
        expected = _clean(intent.get(field))
        if expected and expected not in page_text and expected not in page.window_title:
            raise UIStopError(f"current page does not match intent {field}")


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOSS contact executor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    contact_parser = subparsers.add_parser("contact-current")
    contact_parser.add_argument("--campaign-root", required=True)
    contact_parser.add_argument("--execute", action="store_true")
    contact_parser.add_argument("--mock-ui-fixture")
    contact_parser.add_argument("--now")

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--campaign-root", required=True)

    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--campaign-root", required=True)

    return parser


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _contact_current_exit_code(result: dict[str, Any]) -> int:
    result_value = result.get("result")
    if result_value in {"dry_run_ready", "sent", "skipped_continue_chat"}:
        return 0
    if result_value == "sent_unverified":
        return 4
    if result_value == "stopped":
        stopped_reason = str(result.get("stopped_reason") or "")
        if "stale_lock" in stopped_reason or "lock" in stopped_reason:
            return 4
        return 3
    return 3


def _exception_exit_code(exc: Exception) -> int:
    text = str(exc)
    if "stale_lock" in text or "lock" in text:
        return 4
    if isinstance(exc, UIStopError):
        return 3
    if isinstance(exc, ValueError):
        return 2
    return 3


def _exception_result(exc: Exception) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "result": "stopped",
        "stopped_reason": str(exc),
        "error_class": type(exc).__name__,
        "next_action_for_codex": "write_interruption_and_stop",
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "contact-current":
        ui = FixtureBossUI(args.mock_ui_fixture) if args.mock_ui_fixture else None
        try:
            result = contact_current(
                args.campaign_root,
                execute=bool(args.execute),
                ui=ui,
                now_text=args.now,
            )
        except Exception as exc:
            _print_json(_exception_result(exc))
            return _exception_exit_code(exc)
        _print_json(result)
        return _contact_current_exit_code(result)
    if args.command == "validate":
        report = boss_app_sourcing.validate_executor_artifacts(args.campaign_root)
        _print_json(report)
        return 0 if report["status"] == "passed" else 1
    if args.command == "summarize":
        summary = boss_app_sourcing.summarize_executor_results(args.campaign_root)
        _print_json(summary)
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
