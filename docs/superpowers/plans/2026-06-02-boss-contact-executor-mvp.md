# BOSS Contact Executor MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repository-local `contact-current` executor that can safely process the currently open BOSS App candidate detail page through file handoff, audit logs, dry-run/mock verification, and macOS Accessibility-backed real execution.

**Architecture:** Codex remains the screening loop and writes `approved-contact-queue.jsonl` plus `current-contact-intent.json`; `scripts/boss_contact_executor.py` reads that intent and handles only the current detail page. Existing `scripts/boss_app_sourcing.py` remains the source of truth for campaign candidates, contact decisions, communication page records, validation, and summaries.

**Tech Stack:** Python standard library, pytest, JSON/JSONL campaign artifacts, macOS `osascript`/JXA through `subprocess`, existing `scripts/boss_app_sourcing.py` helpers.

---

## File Structure

- Create `scripts/boss_contact_executor.py`
  - CLI entrypoint for `contact-current`, `validate`, and `summarize`.
  - Pure validation for executor policy and current contact intent.
  - Fixture UI adapter for deterministic tests.
  - macOS Accessibility adapter shelling out to `osascript -l JavaScript`.
  - State machine for lock, UI preflight, click, communication-page capture, result, and audit.

- Modify `scripts/boss_app_sourcing.py`
  - Add executor artifact helpers:
    - `record_approved_contact_queue_item`
    - `write_current_contact_intent`
    - `consume_executor_result`
    - `validate_executor_artifacts`
    - `summarize_executor_results`
  - Extend real-name source validation to include `communication_page_after_external_executor`.
  - Keep existing live-test behavior unchanged.

- Create `tests/test_boss_contact_executor.py`
  - Unit tests for policy validation, intent validation, fixture UI, state machine, lock behavior, stopped/skipped/sent results, and CLI exit codes.

- Modify `tests/test_boss_app_sourcing.py`
  - Tests for approved queue, current intent, result consumption, external-executor real-name backfill, validation, and summary.

- Modify `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`
  - Add an external executor handoff stage after dry-run contact for explicitly authorized executor runs.
  - Clarify that Codex still does not click real contact buttons.

- Modify `agents/skills/boss-app-recommendation-sourcing/SKILL.md`
  - Add the new optional output artifacts and boundary wording.

- Modify `.claude/skills/boss-app-recommendation-sourcing/SKILL.md`
  - Keep adapter pointing at canonical skill/workflow; update only if canonical artifact names need mention in adapter checks.

- Modify `tests/test_agent_architecture.py`
  - Add assertions that canonical BOSS skill/workflow mention the external executor boundary and new artifacts.

- Modify `tasks/todo.md`
  - Track implementation progress and final review.

---

### Task 1: Add Executor Artifact Helpers To BOSS Sourcing

**Files:**
- Modify: `scripts/boss_app_sourcing.py`
- Modify: `tests/test_boss_app_sourcing.py`

- [ ] **Step 1: Write failing sourcing artifact tests**

Append these tests near the existing contact and real-name tests in `tests/test_boss_app_sourcing.py`:

```python
def _contact_candidate_for_executor(tmp_path: Path) -> tuple[Path, str]:
    manifest = boss_app_sourcing.init_campaign(
        campaign_id="boss-executor-artifacts",
        filters_text="AI Infra",
        out_base=tmp_path,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陶先生",
        "current_company": "上海华为技术有限公司",
        "current_title": "博士后研究员-大模型方向",
        "age": "34岁",
        "work_years": "4年",
        "education": "博士",
        "expected_salary": "50-80K",
        "screenshot_hash": "sha256:detail",
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {
            "profile_header": "陶先生；华为 · 博士后研究员-大模型方向",
            "contact_button_text": "立即沟通",
        },
        "contact",
        90,
        ["华为目标公司", "大模型推理框架方向匹配"],
        ["在职-暂不考虑"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    return root, candidate["candidate_key"]


def test_record_approved_contact_queue_item_and_current_intent(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)

    queue_item = boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    assert queue_item["schema"] == "boss_approved_contact_queue_v1"
    assert queue_item["candidate_key"] == candidate_key
    assert queue_item["approval_status"] == "approved_for_auto_contact"
    assert queue_item["button_seen"] == "立即沟通"

    queue_rows = boss_app_sourcing.load_jsonl(root / "structured/approved-contact-queue.jsonl")
    assert len(queue_rows) == 1
    assert queue_rows[0]["candidate_key"] == candidate_key

    intent = boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")
    assert intent["schema"] == "boss_current_contact_intent_v1"
    assert intent["intent_id"].startswith("20260602T100000-")
    assert intent["expected_button"] == "立即沟通"
    assert intent["expires_at"] == "2026-06-02T10:10:00+08:00"
    assert read_json(root / "state/current-contact-intent.json")["candidate_key"] == candidate_key


def test_approved_contact_queue_rejects_non_contact_candidate(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-executor-reject", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_company": "普通公司",
        "current_title": "测试经理",
    })
    boss_app_sourcing.record_detail_update(root, candidate["candidate_key"], {}, "skip", 20, ["方向不匹配"])

    with pytest.raises(ValueError, match="detail recommendation contact"):
        boss_app_sourcing.record_approved_contact_queue_item(root, candidate["candidate_key"])


def test_consume_executor_sent_result_updates_contact_and_real_name(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")
    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；AI Infra训练与推理研发；状态：送达",
        "next_action_for_codex": "record_contact_return_to_list_and_continue",
        "stopped_reason": None,
        "started_at": "2026-06-02T10:00:02+08:00",
        "finished_at": "2026-06-02T10:00:08+08:00",
    })

    consumed = boss_app_sourcing.consume_executor_result(root)
    assert consumed["result"] == "sent"

    latest = boss_app_sourcing.latest_candidate(root, candidate_key)
    assert latest["real_name"] == "陶壮"
    assert latest["real_name_source"] == "communication_page_after_external_executor"
    assert latest["contact"]["contacted"] is True
    assert latest["contact"]["contact_mode"] == "external_executor"

    decisions = boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")
    assert decisions[-1]["mode"] == "external_executor"
    assert decisions[-1]["message_status"] == "送达"
    assert decisions[-1]["preset_message_auto_sent"] is True


def test_consume_executor_continue_chat_and_stopped_paths(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    intent = boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "skipped_continue_chat",
        "button_before_click": "继续沟通",
        "next_action_for_codex": "record_skip_return_to_list_and_continue",
        "stopped_reason": None,
    })
    skipped = boss_app_sourcing.consume_executor_result(root)
    assert skipped["result"] == "skipped_continue_chat"
    assert boss_app_sourcing.load_jsonl(root / "structured/contact-decisions.jsonl")[-1]["skip_reason"] == "continue_chat"

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "stopped",
        "button_before_click": "立即联系牛人",
        "next_action_for_codex": "write_interruption_and_stop",
        "stopped_reason": "paid_search_chat_card",
    })
    stopped = boss_app_sourcing.consume_executor_result(root)
    assert stopped["result"] == "stopped"
    plan = read_json(root / "state/continuation-plan.json")
    assert plan["stage"] == "external_executor"
    assert plan["reason"] == "paid_search_chat_card"
    assert list((root / "reports").glob("interruption-executor-paid_search_chat_card-*.json"))


def test_validate_and_summarize_executor_artifacts(tmp_path: Path) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    intent = boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")
    boss_app_sourcing.append_jsonl(root / "raw/executor-contact-attempts.jsonl", {
        "schema": "boss_contact_attempt_event_v1",
        "event_type": "attempt_finished",
        "intent_id": intent["intent_id"],
        "candidate_key": candidate_key,
        "result": "sent",
        "message_status": "送达",
        "real_name": "陶壮",
    })

    validation = boss_app_sourcing.validate_executor_artifacts(root)
    assert validation["status"] == "passed"
    assert validation["approved_queue_count"] == 1
    assert validation["attempt_count"] == 1

    summary = boss_app_sourcing.summarize_executor_results(root)
    assert summary["sent_count"] == 1
    assert summary["result_distribution"] == {"sent": 1}
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py::test_record_approved_contact_queue_item_and_current_intent tests/test_boss_app_sourcing.py::test_consume_executor_sent_result_updates_contact_and_real_name -q
```

Expected: FAIL with `AttributeError: module 'scripts.boss_app_sourcing' has no attribute 'record_approved_contact_queue_item'`.

- [ ] **Step 3: Implement executor artifact helpers**

Modify `scripts/boss_app_sourcing.py`:

1. Add imports:

```python
from datetime import date, datetime, timedelta
```

2. Add constants near existing policy constants:

```python
EXTERNAL_EXECUTOR_REAL_NAME_SOURCE = "communication_page_after_external_executor"
EXECUTOR_RESULT_SCHEMA = "boss_executor_result_v1"
CURRENT_CONTACT_INTENT_SCHEMA = "boss_current_contact_intent_v1"
APPROVED_CONTACT_QUEUE_SCHEMA = "boss_approved_contact_queue_v1"
EXECUTOR_ATTEMPT_SCHEMA = "boss_contact_attempt_event_v1"
```

3. Update `backfill_real_name` source validation:

```python
valid_sources = {
    "communication_page_after_live_contact_test",
    "manual_opened_communication_page",
    EXTERNAL_EXECUTOR_REAL_NAME_SOURCE,
}
if source not in valid_sources:
    raise ValueError("invalid real name source")
```

4. Keep the live-contact state guard only for the live-test source:

```python
if source == "communication_page_after_live_contact_test" and not contact_state.get("contacted"):
    raise ValueError("communication page live source requires live contacted candidate")
```

5. Add these helpers after `write_continuation_plan`:

```python
def _timestamp_for_id(value: str) -> str:
    parsed = datetime.fromisoformat(value)
    return parsed.strftime("%Y%m%dT%H%M%S")


def _executor_candidate_payload(candidate: dict[str, Any]) -> dict[str, Any]:
    screening = candidate.get("screening") or {}
    return {
        "candidate_key": candidate["candidate_key"],
        "display_name": candidate.get("display_name") or "",
        "current_company": candidate.get("current_company") or "",
        "current_title": candidate.get("current_title") or "",
        "age": candidate.get("age") or (candidate.get("list_snapshot") or {}).get("age") or "",
        "work_years": candidate.get("work_years") or "",
        "education": candidate.get("education") or "",
        "expected_salary": candidate.get("expected_salary") or "",
        "score": int(screening.get("score") or 0),
        "reasons": list(screening.get("reasons") or []),
        "risks": list(screening.get("risks") or []),
    }


def _require_executor_candidate(candidate: dict[str, Any]) -> None:
    screening = candidate.get("screening") or {}
    contact = candidate.get("contact") or {}
    detail_sections = candidate.get("detail_sections") or {}
    if screening.get("detail_decision") != "contact":
        raise ValueError("external executor requires detail recommendation contact")
    if not contact.get("would_contact"):
        raise ValueError("external executor requires existing would_contact decision")
    if detail_sections.get("contact_button_text") not in {"立即沟通", "立即联系牛人"}:
        raise ValueError("external executor requires visible contact button")


def record_approved_contact_queue_item(
    campaign_root: str | Path,
    candidate_key: str,
    message_template_id: str = "boss-current-preset",
) -> dict[str, Any]:
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    _require_executor_candidate(candidate)
    payload = _executor_candidate_payload(candidate)
    detail_sections = candidate.get("detail_sections") or {}
    item = {
        "schema": APPROVED_CONTACT_QUEUE_SCHEMA,
        "campaign_id": Path(campaign_root).name,
        **payload,
        "recommendation": "contact",
        "button_seen": detail_sections.get("contact_button_text") or "立即沟通",
        "already_contacted": bool((candidate.get("contact") or {}).get("contacted")),
        "approval_status": "approved_for_auto_contact",
        "message_template_id": message_template_id,
        "created_at": _now(),
    }
    append_jsonl(_campaign_path(campaign_root, "structured/approved-contact-queue.jsonl"), item)
    return item


def write_current_contact_intent(
    campaign_root: str | Path,
    candidate_key: str,
    message_template_id: str = "boss-current-preset",
    now_text: str | None = None,
    expires_minutes: int = 10,
) -> dict[str, Any]:
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    _require_executor_candidate(candidate)
    queue_rows = load_jsonl(_campaign_path(campaign_root, "structured/approved-contact-queue.jsonl"))
    if not any(row.get("candidate_key") == candidate_key for row in queue_rows):
        record_approved_contact_queue_item(campaign_root, candidate_key, message_template_id)
    now_value = now_text or datetime.now().astimezone().isoformat(timespec="seconds")
    expires_at = (datetime.fromisoformat(now_value) + timedelta(minutes=expires_minutes)).isoformat(timespec="seconds")
    payload = _executor_candidate_payload(candidate)
    intent = {
        "schema": CURRENT_CONTACT_INTENT_SCHEMA,
        "intent_id": f"{_timestamp_for_id(now_value)}-{candidate_key.replace(':', '-')[:24]}",
        "campaign_id": Path(campaign_root).name,
        **payload,
        "expected_button": "立即沟通",
        "current_page": "candidate_detail",
        "approval_status": "approved_for_auto_contact",
        "message_template_id": message_template_id,
        "created_by": "codex_screening_loop",
        "created_at": now_value,
        "expires_at": expires_at,
    }
    write_json(_campaign_path(campaign_root, "state/current-contact-intent.json"), intent)
    return intent


def consume_executor_result(campaign_root: str | Path, result_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(campaign_root)
    result = _load_required_json_object(Path(result_path) if result_path else root / "state/executor-result.json")
    if result.get("schema") != EXECUTOR_RESULT_SCHEMA:
        raise ValueError("executor result schema is invalid")
    candidate_key = str(result.get("candidate_key") or "")
    if not candidate_key:
        raise ValueError("executor result candidate_key is required")
    candidate = dict(latest_candidate(root, candidate_key))
    outcome = result.get("result")
    if outcome == "sent":
        decision = {
            "candidate_key": candidate_key,
            "mode": "external_executor",
            "would_contact": True,
            "button_seen": result.get("button_before_click") == "立即沟通",
            "action_confirmed": True,
            "contacted": True,
            "preset_message_auto_sent": True,
            "message_status": result.get("message_status"),
            "message_template_id": result.get("message_template_id"),
            "executor_intent_id": result.get("intent_id"),
            "decided_at": _now(),
        }
        append_jsonl(root / "structured/contact-decisions.jsonl", decision)
        candidate["contact"] = dict(candidate.get("contact") or {})
        candidate["contact"].update({
            "would_contact": True,
            "contact_mode": "external_executor",
            "contacted": True,
            "live_contact_test": False,
            "contact_button_seen": True,
            "communication_page_seen": True,
            "preset_message_auto_sent": True,
            "message_status": result.get("message_status"),
        })
        _append_candidate(root, candidate)
        backfill_real_name(
            root,
            candidate_key,
            str(result.get("real_name") or ""),
            EXTERNAL_EXECUTOR_REAL_NAME_SOURCE,
            page_text=str(result.get("communication_page_text") or ""),
        )
        return result
    if outcome == "skipped_continue_chat":
        append_jsonl(root / "structured/contact-decisions.jsonl", {
            "candidate_key": candidate_key,
            "mode": "external_executor",
            "would_contact": True,
            "button_seen": False,
            "action_confirmed": True,
            "contacted": False,
            "already_contacted": True,
            "skip_reason": "continue_chat",
            "executor_intent_id": result.get("intent_id"),
            "decided_at": _now(),
        })
        return result
    if outcome in {"sent_unverified", "stopped"}:
        reason = str(result.get("stopped_reason") or outcome)
        write_continuation_plan(root, "external_executor", "stopped", reason, "review_executor_result_before_resuming")
        write_json(root / "reports" / f"interruption-executor-{reason}-{datetime.now().strftime('%Y%m%dT%H%M%S')}.json", result)
        return result
    raise ValueError(f"unsupported executor result: {outcome}")


def validate_executor_artifacts(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    queue = load_jsonl(root / "structured/approved-contact-queue.jsonl")
    attempts = load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    result = load_json(root / "state/executor-result.json", default={}) or {}
    candidate_keys = set(_latest_candidates_by_key(root))
    queue_missing = sorted(str(row.get("candidate_key")) for row in queue if row.get("candidate_key") not in candidate_keys)
    attempt_missing = sorted(str(row.get("candidate_key")) for row in attempts if row.get("candidate_key") and row.get("candidate_key") not in candidate_keys)
    status = "failed" if queue_missing or attempt_missing else "passed"
    report = {
        "campaign_root": str(root),
        "status": status,
        "approved_queue_count": len(queue),
        "attempt_count": len(attempts),
        "latest_result": result.get("result"),
        "queue_missing_candidate_keys": queue_missing,
        "attempt_missing_candidate_keys": attempt_missing,
        "updated_at": _now(),
    }
    write_json(root / "reports/executor-validation.json", report)
    return report


def summarize_executor_results(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    attempts = load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    finished = [row for row in attempts if row.get("event_type") in {"attempt_finished", "attempt_dry_run"}]
    distribution = Counter(str(row.get("result") or "unknown") for row in finished)
    summary = {
        "campaign_root": str(root),
        "approved_queue_count": len(load_jsonl(root / "structured/approved-contact-queue.jsonl")),
        "attempt_count": len(finished),
        "sent_count": distribution.get("sent", 0),
        "skipped_continue_chat_count": distribution.get("skipped_continue_chat", 0),
        "stopped_count": distribution.get("stopped", 0) + distribution.get("sent_unverified", 0),
        "result_distribution": dict(sorted(distribution.items())),
        "updated_at": _now(),
    }
    write_json(root / "reports/executor-summary.json", summary)
    lines = ["# BOSS 触达执行器摘要", ""]
    for key in ["approved_queue_count", "attempt_count", "sent_count", "skipped_continue_chat_count", "stopped_count"]:
        lines.append(f"- {key}: {summary[key]}")
    lines.extend(["", "## 结果分布", ""])
    for result, count in summary["result_distribution"].items():
        lines.append(f"- {result}: {count}")
    (root / "reports/executor-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
```

- [ ] **Step 4: Run tests for Task 1**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py::test_record_approved_contact_queue_item_and_current_intent tests/test_boss_app_sourcing.py::test_approved_contact_queue_rejects_non_contact_candidate tests/test_boss_app_sourcing.py::test_consume_executor_sent_result_updates_contact_and_real_name tests/test_boss_app_sourcing.py::test_consume_executor_continue_chat_and_stopped_paths tests/test_boss_app_sourcing.py::test_validate_and_summarize_executor_artifacts -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit Task 1**

```bash
git add scripts/boss_app_sourcing.py tests/test_boss_app_sourcing.py
git commit -m "Add BOSS executor artifact helpers"
```

---

### Task 2: Create Executor Policy, Intent, Result, And Fixture UI Core

**Files:**
- Create: `scripts/boss_contact_executor.py`
- Create: `tests/test_boss_contact_executor.py`

- [ ] **Step 1: Write failing tests for policy and intent validation**

Create `tests/test_boss_contact_executor.py` with:

```python
import json
from pathlib import Path

import pytest

from scripts import boss_app_sourcing, boss_contact_executor


ACK = "I understand this sends real messages to third-party candidates."


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def make_executor_campaign(tmp_path: Path) -> tuple[Path, str]:
    root, candidate_key = _make_contact_candidate(tmp_path)
    boss_app_sourcing.record_approved_contact_queue_item(root, candidate_key)
    boss_app_sourcing.write_current_contact_intent(root, candidate_key, now_text="2026-06-02T10:00:00+08:00")
    write_json(root / "executor-policy.json", {
        "schema": "boss_contact_executor_policy_v1",
        "campaign_id": root.name,
        "allow_real_contact": True,
        "operator_acknowledgement": ACK,
        "max_contacts_per_run": 1,
        "max_contacts_per_day": 50,
        "message_template_id": "boss-current-preset",
        "require_execute_flag": True,
        "skip_continue_chat": True,
        "stop_on_paid_prompt": True,
        "stop_on_captcha": True,
        "stop_on_login_or_security_page": True,
        "stop_on_unknown_ui": True,
        "capture_real_name_after_contact": True,
        "kill_switch_path": str(root / "state/stop-executor.flag"),
    })
    return root, candidate_key


def _make_contact_candidate(tmp_path: Path) -> tuple[Path, str]:
    manifest = boss_app_sourcing.init_campaign("boss-contact-executor", "AI Infra", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陶先生",
        "current_company": "上海华为技术有限公司",
        "current_title": "博士后研究员-大模型方向",
        "age": "34岁",
        "work_years": "4年",
        "education": "博士",
        "expected_salary": "50-80K",
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"profile_header": "陶先生；上海华为技术有限公司；博士后研究员-大模型方向", "contact_button_text": "立即沟通"},
        "contact",
        90,
        ["华为目标公司"],
    )
    boss_app_sourcing.record_contact_decision(root, candidate["candidate_key"], "dry_run", True, False)
    return root, candidate["candidate_key"]


def test_validate_policy_requires_execute_flag_and_acknowledgement(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)

    dry = boss_contact_executor.validate_executor_policy(policy, execute=False)
    assert dry["execute"] is False

    execute = boss_contact_executor.validate_executor_policy(policy, execute=True)
    assert execute["execute"] is True

    policy["operator_acknowledgement"] = "wrong"
    with pytest.raises(ValueError, match="operator_acknowledgement"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)

    policy["operator_acknowledgement"] = ACK
    policy["allow_real_contact"] = False
    with pytest.raises(ValueError, match="allow_real_contact"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)


def test_validate_policy_rejects_batch_size_in_mvp(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    policy = boss_contact_executor.load_executor_policy(root)
    policy["max_contacts_per_run"] = 2
    with pytest.raises(ValueError, match="max_contacts_per_run"):
        boss_contact_executor.validate_executor_policy(policy, execute=True)


def test_load_and_validate_current_intent(tmp_path: Path) -> None:
    root, candidate_key = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    validated = boss_contact_executor.validate_current_intent(
        intent,
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert validated["candidate_key"] == candidate_key

    intent["approval_status"] = "pending"
    with pytest.raises(ValueError, match="approval_status"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00+08:00")


def test_validate_current_intent_rejects_expired_intent(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    with pytest.raises(ValueError, match="expired"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:11:00+08:00")
```

- [ ] **Step 2: Run tests and verify module is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_validate_policy_requires_execute_flag_and_acknowledgement -q
```

Expected: FAIL with `ImportError` or `ModuleNotFoundError` for `scripts.boss_contact_executor`.

- [ ] **Step 3: Create executor module with validation core**

Create `scripts/boss_contact_executor.py`:

```python
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
PAID_MARKERS = ["搜索畅聊卡", "剩余次数不足", "立即开聊", "还需支付", "直豆"]
SECURITY_MARKERS = ["验证码", "安全验证", "登录", "请先登录"]
MARKETING_MARKERS = ["热搜牛人推荐", "查看更多牛人", "去看看"]


@dataclass(frozen=True)
class BossPageSnapshot:
    front_app: str
    window_title: str
    page_text: str
    buttons: list[str]
    screenshot_hash: str = ""


@dataclass(frozen=True)
class ContactButtonState:
    label: str
    count: int


@dataclass(frozen=True)
class CommunicationResult:
    real_name: str
    message_status: str
    page_text: str


def _campaign_path(campaign_root: str | Path, relative: str) -> Path:
    return Path(campaign_root) / relative


def load_executor_policy(campaign_root: str | Path) -> dict[str, Any]:
    policy = boss_app_sourcing.load_json(_campaign_path(campaign_root, "executor-policy.json"), default=None)
    if not isinstance(policy, dict):
        raise ValueError("executor-policy.json is required")
    if policy.get("schema") != POLICY_SCHEMA:
        raise ValueError("executor policy schema is invalid")
    return policy


def validate_executor_policy(policy: dict[str, Any], execute: bool) -> dict[str, Any]:
    boolean_fields = [
        "allow_real_contact",
        "require_execute_flag",
        "skip_continue_chat",
        "stop_on_paid_prompt",
        "stop_on_captcha",
        "stop_on_login_or_security_page",
        "stop_on_unknown_ui",
        "capture_real_name_after_contact",
    ]
    for field in boolean_fields:
        if not isinstance(policy.get(field), bool):
            raise ValueError(f"{field} must be boolean")
    for field in ["max_contacts_per_run", "max_contacts_per_day"]:
        if isinstance(policy.get(field), bool) or not isinstance(policy.get(field), int):
            raise ValueError(f"{field} must be integer")
    if policy["max_contacts_per_run"] != 1:
        raise ValueError("max_contacts_per_run must be 1 for MVP contact-current")
    if execute:
        if not policy["allow_real_contact"]:
            raise ValueError("allow_real_contact must be true for --execute")
        if policy.get("operator_acknowledgement") != ACKNOWLEDGEMENT:
            raise ValueError("operator_acknowledgement is invalid")
    merged = dict(policy)
    merged["execute"] = bool(execute)
    return merged


def load_current_intent(campaign_root: str | Path) -> dict[str, Any]:
    intent = boss_app_sourcing.load_json(_campaign_path(campaign_root, "state/current-contact-intent.json"), default=None)
    if not isinstance(intent, dict):
        raise ValueError("current-contact-intent.json is required")
    return intent


def validate_current_intent(intent: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    if intent.get("schema") != INTENT_SCHEMA:
        raise ValueError("current contact intent schema is invalid")
    if intent.get("approval_status") != "approved_for_auto_contact":
        raise ValueError("approval_status must be approved_for_auto_contact")
    if intent.get("expected_button") != "立即沟通":
        raise ValueError("expected_button must be 立即沟通")
    if intent.get("current_page") != "candidate_detail":
        raise ValueError("current_page must be candidate_detail")
    for field in ["intent_id", "campaign_id", "candidate_key", "display_name", "current_company", "current_title", "expires_at"]:
        if not str(intent.get(field) or "").strip():
            raise ValueError(f"{field} is required")
    now_value = datetime.fromisoformat(now_text) if now_text else datetime.now().astimezone()
    expires_at = datetime.fromisoformat(str(intent["expires_at"]))
    if now_value > expires_at:
        raise ValueError("current contact intent expired")
    return intent


def write_executor_result(campaign_root: str | Path, result: dict[str, Any]) -> dict[str, Any]:
    payload = {"schema": RESULT_SCHEMA, **result}
    boss_app_sourcing.write_json(_campaign_path(campaign_root, "state/executor-result.json"), payload)
    return payload


def append_attempt_event(campaign_root: str | Path, event: dict[str, Any]) -> dict[str, Any]:
    payload = {"schema": ATTEMPT_SCHEMA, **event}
    boss_app_sourcing.append_jsonl(_campaign_path(campaign_root, "raw/executor-contact-attempts.jsonl"), payload)
    return payload
```

- [ ] **Step 4: Run Task 2 validation tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_validate_policy_requires_execute_flag_and_acknowledgement tests/test_boss_contact_executor.py::test_validate_policy_rejects_batch_size_in_mvp tests/test_boss_contact_executor.py::test_load_and_validate_current_intent tests/test_boss_contact_executor.py::test_validate_current_intent_rejects_expired_intent -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/boss_contact_executor.py tests/test_boss_contact_executor.py
git commit -m "Add BOSS contact executor validation core"
```

---

### Task 3: Implement Fixture UI And `contact-current` State Machine

**Files:**
- Modify: `scripts/boss_contact_executor.py`
- Modify: `tests/test_boss_contact_executor.py`

- [ ] **Step 1: Add fixture UI tests**

Append to `tests/test_boss_contact_executor.py`:

```python
def write_fixture(path: Path, data: dict) -> Path:
    write_json(path, data)
    return path


def ready_fixture(tmp_path: Path) -> Path:
    return write_fixture(tmp_path / "detail-ready.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
        "communication": {
            "front_app": "BOSS直聘",
            "window_title": "陶壮",
            "page_text": "沟通页顶部：陶壮；AI Infra训练与推理研发；消息状态：送达",
            "buttons": ["求简历", "换电话/微信"],
        },
    })


def test_contact_current_fixture_dry_run_does_not_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    result = boss_contact_executor.contact_current(
        root,
        execute=False,
        ui=boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path)),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "dry_run_ready"
    assert result["would_click"] is True
    assert boss_app_sourcing.load_json(root / "state/executor-result.json")["result"] == "dry_run_ready"


def test_contact_current_fixture_execute_sends_and_writes_audit(tmp_path: Path) -> None:
    root, candidate_key = make_executor_campaign(tmp_path)
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(ready_fixture(tmp_path)),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "sent"
    assert result["candidate_key"] == candidate_key
    assert result["real_name"] == "陶壮"
    assert result["message_status"] == "送达"
    attempts = boss_app_sourcing.load_jsonl(root / "raw/executor-contact-attempts.jsonl")
    assert [row["event_type"] for row in attempts] == ["attempt_started", "attempt_finished"]


def test_contact_current_skips_continue_chat_without_click(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "continue-chat.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 继续沟通",
            "buttons": ["继续沟通"],
        }
    })
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(fixture),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "skipped_continue_chat"
    assert result["button_before_click"] == "继续沟通"


def test_contact_current_stops_on_paid_contact_button(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "paid.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 搜索畅聊卡 剩余次数不足 立即联系牛人",
            "buttons": ["立即联系牛人"],
        }
    })
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(fixture),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "stopped"
    assert result["stopped_reason"] == "paid_search_chat_card"


def test_contact_current_sent_unverified_when_communication_result_missing(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = write_fixture(tmp_path / "unverified.json", {
        "detail": {
            "front_app": "BOSS直聘",
            "window_title": "陶先生",
            "page_text": "陶先生 上海华为技术有限公司 博士后研究员-大模型方向 立即沟通",
            "buttons": ["立即沟通"],
        },
        "communication": {
            "front_app": "BOSS直聘",
            "window_title": "沟通页",
            "page_text": "沟通页顶部：未知；没有状态",
            "buttons": [],
        },
    })
    result = boss_contact_executor.contact_current(
        root,
        execute=True,
        ui=boss_contact_executor.FixtureBossUI(fixture),
        now_text="2026-06-02T10:05:00+08:00",
    )
    assert result["result"] == "sent_unverified"
    assert result["stopped_reason"] == "communication_result_unverified"
```

- [ ] **Step 2: Run fixture tests and verify class is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_contact_current_fixture_dry_run_does_not_click -q
```

Expected: FAIL with `AttributeError` for `FixtureBossUI` or `contact_current`.

- [ ] **Step 3: Implement fixture UI, state helpers, and contact-current**

Append to `scripts/boss_contact_executor.py`:

```python
class FixtureBossUI:
    def __init__(self, fixture_path: str | Path):
        self.fixture_path = Path(fixture_path)
        self.data = json.loads(self.fixture_path.read_text(encoding="utf-8-sig"))
        self.clicked = False

    def read_current_page(self) -> BossPageSnapshot:
        detail = self.data["detail"]
        return BossPageSnapshot(
            front_app=str(detail.get("front_app") or ""),
            window_title=str(detail.get("window_title") or ""),
            page_text=str(detail.get("page_text") or ""),
            buttons=list(detail.get("buttons") or []),
            screenshot_hash=str(detail.get("screenshot_hash") or ""),
        )

    def find_contact_button(self, snapshot: BossPageSnapshot) -> ContactButtonState:
        labels = [button for button in snapshot.buttons if button in {"立即沟通", "继续沟通", "立即联系牛人"}]
        if not labels:
            return ContactButtonState("", 0)
        return ContactButtonState(labels[0], len(labels))

    def click_contact(self, button: ContactButtonState) -> dict[str, Any]:
        if button.label != "立即沟通":
            raise ValueError("only 立即沟通 can be clicked")
        self.clicked = True
        return {"clicked": True}

    def wait_for_communication_page(self) -> BossPageSnapshot:
        communication = self.data.get("communication") or {}
        return BossPageSnapshot(
            front_app=str(communication.get("front_app") or ""),
            window_title=str(communication.get("window_title") or ""),
            page_text=str(communication.get("page_text") or ""),
            buttons=list(communication.get("buttons") or []),
            screenshot_hash=str(communication.get("screenshot_hash") or ""),
        )

    def extract_communication_result(self, snapshot: BossPageSnapshot) -> CommunicationResult:
        text = snapshot.page_text
        real_name = snapshot.window_title if snapshot.window_title and snapshot.window_title != "沟通页" else ""
        for marker in SUCCESS_MESSAGE_STATUSES:
            if marker in text:
                return CommunicationResult(real_name=real_name, message_status=marker, page_text=text)
        return CommunicationResult(real_name=real_name, message_status="", page_text=text)


def _contains_any(text: str, markers: list[str]) -> bool:
    return any(marker in text for marker in markers)


def validate_page_match(snapshot: BossPageSnapshot, intent: dict[str, Any]) -> None:
    text = " ".join([snapshot.front_app, snapshot.window_title, snapshot.page_text, " ".join(snapshot.buttons)])
    if "BOSS" not in snapshot.front_app and "BOSS" not in text and "直聘" not in text:
        raise ValueError("front app is not BOSS")
    if _contains_any(text, MARKETING_MARKERS):
        raise ValueError("marketing module detected")
    if _contains_any(text, SECURITY_MARKERS):
        raise ValueError("login_or_security_page")
    if str(intent["display_name"]) not in text:
        raise ValueError("page_mismatch")
    if str(intent["current_company"]) not in text and str(intent["current_title"]) not in text:
        raise ValueError("page_mismatch")


def classify_button(snapshot: BossPageSnapshot, button: ContactButtonState) -> tuple[str, str | None]:
    text = snapshot.page_text + " " + " ".join(snapshot.buttons)
    if _contains_any(text, PAID_MARKERS) or button.label == "立即联系牛人":
        return "stopped", "paid_search_chat_card"
    if button.count == 0:
        return "stopped", "button_not_found"
    if button.count > 1:
        return "stopped", "ambiguous_contact_button"
    if button.label == "继续沟通":
        return "skipped_continue_chat", None
    if button.label != "立即沟通":
        return "stopped", "button_not_found"
    return "ready", None


def acquire_lock(campaign_root: str | Path, intent: dict[str, Any], now_text: str | None = None) -> dict[str, Any]:
    path = _campaign_path(campaign_root, "state/executor.lock")
    if path.exists():
        lock = boss_app_sourcing.load_json(path, default={}) or {}
        if lock.get("status") == "running":
            raise RuntimeError("stale_lock_requires_review")
    payload = {
        "schema": LOCK_SCHEMA,
        "lock_id": intent["intent_id"],
        "intent_id": intent["intent_id"],
        "candidate_key": intent["candidate_key"],
        "status": "running",
        "created_at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
        "pid": os.getpid(),
    }
    boss_app_sourcing.write_json(path, payload)
    return payload


def finish_lock(campaign_root: str | Path, result: str) -> None:
    path = _campaign_path(campaign_root, "state/executor.lock")
    lock = boss_app_sourcing.load_json(path, default={}) or {}
    lock.update({
        "status": "finished",
        "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "result": result,
    })
    boss_app_sourcing.write_json(path, lock)


def _base_result(intent: dict[str, Any], result: str, now_text: str | None) -> dict[str, Any]:
    return {
        "intent_id": intent["intent_id"],
        "campaign_id": intent["campaign_id"],
        "candidate_key": intent["candidate_key"],
        "result": result,
        "started_at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def contact_current(
    campaign_root: str | Path,
    execute: bool = False,
    ui: Any | None = None,
    now_text: str | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    policy = validate_executor_policy(load_executor_policy(root), execute=execute)
    intent = validate_current_intent(load_current_intent(root), now_text=now_text)
    if Path(str(policy.get("kill_switch_path") or root / "state/stop-executor.flag")).exists():
        result = _base_result(intent, "stopped", now_text)
        result.update({"stopped_reason": "kill_switch", "next_action_for_codex": "write_interruption_and_stop"})
        return write_executor_result(root, result)
    ui = ui or MacAccessibilityBossUI()
    acquire_lock(root, intent, now_text=now_text)
    append_attempt_event(root, {
        "event_type": "attempt_started",
        "attempt_id": intent["intent_id"],
        "intent_id": intent["intent_id"],
        "candidate_key": intent["candidate_key"],
        "started_at": now_text or datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    try:
        snapshot = ui.read_current_page()
        validate_page_match(snapshot, intent)
        button = ui.find_contact_button(snapshot)
        classification, stopped_reason = classify_button(snapshot, button)
        if classification == "skipped_continue_chat":
            result = _base_result(intent, "skipped_continue_chat", now_text)
            result.update({
                "button_before_click": button.label,
                "next_action_for_codex": "record_skip_return_to_list_and_continue",
                "stopped_reason": None,
            })
        elif classification == "stopped":
            result = _base_result(intent, "stopped", now_text)
            result.update({
                "button_before_click": button.label,
                "next_action_for_codex": "write_interruption_and_stop",
                "stopped_reason": stopped_reason,
            })
        elif not execute:
            result = _base_result(intent, "dry_run_ready", now_text)
            result.update({
                "button_before_click": button.label,
                "would_click": True,
                "next_action_for_codex": "external_executor_execute_required",
                "stopped_reason": None,
            })
        else:
            ui.click_contact(button)
            communication_page = ui.wait_for_communication_page()
            communication = ui.extract_communication_result(communication_page)
            if communication.real_name and communication.message_status in SUCCESS_MESSAGE_STATUSES:
                result = _base_result(intent, "sent", now_text)
                result.update({
                    "button_before_click": button.label,
                    "message_template_id": policy.get("message_template_id"),
                    "message_status": communication.message_status,
                    "real_name": communication.real_name,
                    "communication_page_text": communication.page_text,
                    "next_action_for_codex": "record_contact_return_to_list_and_continue",
                    "stopped_reason": None,
                })
            else:
                result = _base_result(intent, "sent_unverified", now_text)
                result.update({
                    "button_before_click": button.label,
                    "real_name": communication.real_name,
                    "message_status": communication.message_status,
                    "communication_page_text": communication.page_text,
                    "next_action_for_codex": "write_interruption_and_stop",
                    "stopped_reason": "communication_result_unverified",
                })
        result["finished_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_executor_result(root, result)
        append_attempt_event(root, {
            "event_type": "attempt_finished",
            "attempt_id": intent["intent_id"],
            "intent_id": intent["intent_id"],
            "candidate_key": intent["candidate_key"],
            "button_before_click": result.get("button_before_click"),
            "action": "click_contact" if result["result"] in {"sent", "sent_unverified"} else "no_click",
            "result": result["result"],
            "message_status": result.get("message_status"),
            "real_name": result.get("real_name"),
            "stopped_reason": result.get("stopped_reason"),
            "finished_at": result["finished_at"],
        })
        finish_lock(root, result["result"])
        return result
    except Exception as exc:
        result = _base_result(intent, "stopped", now_text)
        result.update({
            "button_before_click": "",
            "next_action_for_codex": "write_interruption_and_stop",
            "stopped_reason": str(exc),
            "finished_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        })
        write_executor_result(root, result)
        append_attempt_event(root, {
            "event_type": "attempt_finished",
            "attempt_id": intent["intent_id"],
            "intent_id": intent["intent_id"],
            "candidate_key": intent["candidate_key"],
            "action": "no_click",
            "result": "stopped",
            "stopped_reason": str(exc),
            "finished_at": result["finished_at"],
        })
        finish_lock(root, "stopped")
        return result
```

- [ ] **Step 4: Run fixture state machine tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_contact_current_fixture_dry_run_does_not_click tests/test_boss_contact_executor.py::test_contact_current_fixture_execute_sends_and_writes_audit tests/test_boss_contact_executor.py::test_contact_current_skips_continue_chat_without_click tests/test_boss_contact_executor.py::test_contact_current_stops_on_paid_contact_button tests/test_boss_contact_executor.py::test_contact_current_sent_unverified_when_communication_result_missing -q
```

Expected: `5 passed`.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/boss_contact_executor.py tests/test_boss_contact_executor.py
git commit -m "Add BOSS contact-current fixture executor"
```

---

### Task 4: Add macOS Accessibility UI Adapter

**Files:**
- Modify: `scripts/boss_contact_executor.py`
- Modify: `tests/test_boss_contact_executor.py`

- [ ] **Step 1: Add subprocess-backed UI adapter tests**

Append to `tests/test_boss_contact_executor.py`:

```python
def test_mac_accessibility_ui_reads_snapshot_from_osascript(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        calls.append(cmd)
        class Result:
            stdout = json.dumps({
                "front_app": "BOSS直聘",
                "window_title": "陶先生",
                "texts": ["陶先生", "上海华为技术有限公司", "博士后研究员-大模型方向"],
                "buttons": ["立即沟通"],
            }, ensure_ascii=False)
            stderr = ""
        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    snapshot = ui.read_current_page()
    assert snapshot.front_app == "BOSS直聘"
    assert "上海华为技术有限公司" in snapshot.page_text
    assert snapshot.buttons == ["立即沟通"]
    assert calls[0][0] == "osascript"


def test_mac_accessibility_ui_clicks_exact_contact_button(monkeypatch: pytest.MonkeyPatch) -> None:
    scripts: list[str] = []

    def fake_run(cmd: list[str], capture_output: bool, text: bool, check: bool, timeout: int):
        scripts.append(cmd[-1])
        class Result:
            stdout = '{"clicked": true}'
            stderr = ""
        return Result()

    monkeypatch.setattr(boss_contact_executor.subprocess, "run", fake_run)
    ui = boss_contact_executor.MacAccessibilityBossUI()
    result = ui.click_contact(boss_contact_executor.ContactButtonState("立即沟通", 1))
    assert result == {"clicked": True}
    assert "立即沟通" in scripts[0]
```

- [ ] **Step 2: Run mac adapter tests and verify class is missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_mac_accessibility_ui_reads_snapshot_from_osascript -q
```

Expected: FAIL with `NameError` or `AttributeError` for `MacAccessibilityBossUI`.

- [ ] **Step 3: Implement macOS adapter**

Append to `scripts/boss_contact_executor.py` before `contact_current` or above CLI code:

```python
JXA_READ_UI = r'''
function collectStrings(value, out) {
  try {
    if (value.name && value.name()) out.push(String(value.name()));
  } catch (e) {}
  try {
    if (value.description && value.description()) out.push(String(value.description()));
  } catch (e) {}
  try {
    var children = value.uiElements();
    for (var i = 0; i < children.length; i++) collectStrings(children[i], out);
  } catch (e) {}
}

var se = Application("System Events");
var proc = se.applicationProcesses.whose({frontmost: true})[0];
var texts = [];
var buttons = [];
var windowTitle = "";
try {
  windowTitle = String(proc.windows[0].name());
  collectStrings(proc.windows[0], texts);
  var allButtons = proc.windows[0].buttons();
  for (var i = 0; i < allButtons.length; i++) {
    try {
      var label = String(allButtons[i].name());
      if (label) buttons.push(label);
    } catch (e) {}
  }
} catch (e) {}
JSON.stringify({
  front_app: String(proc.name()),
  window_title: windowTitle,
  texts: texts,
  buttons: buttons
});
'''

JXA_CLICK_EXACT_BUTTON = r'''
var target = "立即沟通";
function clickButton(value) {
  try {
    var buttons = value.buttons();
    for (var i = 0; i < buttons.length; i++) {
      var label = "";
      try { label = String(buttons[i].name()); } catch (e) {}
      if (label === target) {
        buttons[i].click();
        return true;
      }
    }
  } catch (e) {}
  try {
    var children = value.uiElements();
    for (var j = 0; j < children.length; j++) {
      if (clickButton(children[j])) return true;
    }
  } catch (e) {}
  return false;
}
var se = Application("System Events");
var proc = se.applicationProcesses.whose({frontmost: true})[0];
var clicked = clickButton(proc.windows[0]);
JSON.stringify({clicked: clicked});
'''


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
        return json.loads(result.stdout or "{}")

    def read_current_page(self) -> BossPageSnapshot:
        payload = self._run_jxa(JXA_READ_UI)
        texts = [str(value) for value in payload.get("texts") or [] if str(value).strip()]
        buttons = [str(value) for value in payload.get("buttons") or [] if str(value).strip()]
        page_text = " ".join(dict.fromkeys(texts))
        return BossPageSnapshot(
            front_app=str(payload.get("front_app") or ""),
            window_title=str(payload.get("window_title") or ""),
            page_text=page_text,
            buttons=buttons,
            screenshot_hash=boss_app_sourcing.screen_hash(page_text),
        )

    def find_contact_button(self, snapshot: BossPageSnapshot) -> ContactButtonState:
        labels = [button for button in snapshot.buttons if button in {"立即沟通", "继续沟通", "立即联系牛人"}]
        if not labels:
            text = snapshot.page_text
            for label in ["立即沟通", "继续沟通", "立即联系牛人"]:
                if label in text:
                    labels.append(label)
        if not labels:
            return ContactButtonState("", 0)
        return ContactButtonState(labels[0], len(labels))

    def click_contact(self, button: ContactButtonState) -> dict[str, Any]:
        if button.label != "立即沟通":
            raise ValueError("only 立即沟通 can be clicked")
        payload = self._run_jxa(JXA_CLICK_EXACT_BUTTON)
        if not payload.get("clicked"):
            raise ValueError("contact button click failed")
        return {"clicked": True}

    def wait_for_communication_page(self) -> BossPageSnapshot:
        deadline = time.monotonic() + self.max_wait_seconds
        last = self.read_current_page()
        while time.monotonic() < deadline:
            snapshot = self.read_current_page()
            if "沟通的职位" in snapshot.page_text or "求简历" in snapshot.page_text or "换电话" in snapshot.page_text:
                return snapshot
            last = snapshot
            time.sleep(self.poll_seconds)
        return last

    def extract_communication_result(self, snapshot: BossPageSnapshot) -> CommunicationResult:
        text = snapshot.page_text
        message_status = ""
        for marker in SUCCESS_MESSAGE_STATUSES:
            if marker in text:
                message_status = marker
                break
        real_name = snapshot.window_title.strip()
        if not real_name or real_name in {"沟通页", "BOSS直聘"}:
            parts = [part.strip(" ：;；") for part in text.split() if part.strip()]
            real_name = parts[0] if parts else ""
        return CommunicationResult(real_name=real_name, message_status=message_status, page_text=text)
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_mac_accessibility_ui_reads_snapshot_from_osascript tests/test_boss_contact_executor.py::test_mac_accessibility_ui_clicks_exact_contact_button -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/boss_contact_executor.py tests/test_boss_contact_executor.py
git commit -m "Add macOS accessibility adapter for BOSS contact executor"
```

---

### Task 5: Add Executor CLI Commands And Sourcing CLI Integration

**Files:**
- Modify: `scripts/boss_contact_executor.py`
- Modify: `scripts/boss_app_sourcing.py`
- Modify: `tests/test_boss_contact_executor.py`
- Modify: `tests/test_boss_app_sourcing.py`

- [ ] **Step 1: Add CLI tests**

Append to `tests/test_boss_contact_executor.py`:

```python
def test_contact_current_cli_with_fixture_returns_zero_and_prints_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "dry_run_ready"


def test_contact_current_cli_execute_with_fixture_sends(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    exit_code = boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--execute",
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    assert exit_code == 0
    output = json.loads(capsys.readouterr().out)
    assert output["result"] == "sent"


def test_validate_and_summarize_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, _ = make_executor_campaign(tmp_path)
    fixture = ready_fixture(tmp_path)
    boss_contact_executor.main([
        "contact-current",
        "--campaign-root",
        str(root),
        "--execute",
        "--mock-ui-fixture",
        str(fixture),
        "--now",
        "2026-06-02T10:05:00+08:00",
    ])
    capsys.readouterr()

    assert boss_contact_executor.main(["validate", "--campaign-root", str(root)]) == 0
    validation = json.loads(capsys.readouterr().out)
    assert validation["status"] == "passed"

    assert boss_contact_executor.main(["summarize", "--campaign-root", str(root)]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["sent_count"] == 1
```

Append to `tests/test_boss_app_sourcing.py`:

```python
def test_boss_app_sourcing_cli_writes_intent_and_consumes_executor_result(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, candidate_key = _contact_candidate_for_executor(tmp_path)
    assert boss_app_sourcing.main([
        "approve-contact",
        "--campaign-root",
        str(root),
        "--candidate-key",
        candidate_key,
    ]) == 0
    queue_item = json.loads(capsys.readouterr().out)
    assert queue_item["candidate_key"] == candidate_key

    assert boss_app_sourcing.main([
        "write-contact-intent",
        "--campaign-root",
        str(root),
        "--candidate-key",
        candidate_key,
        "--now",
        "2026-06-02T10:00:00+08:00",
    ]) == 0
    intent = json.loads(capsys.readouterr().out)

    boss_app_sourcing.write_json(root / "state/executor-result.json", {
        "schema": "boss_executor_result_v1",
        "intent_id": intent["intent_id"],
        "campaign_id": root.name,
        "candidate_key": candidate_key,
        "result": "sent",
        "button_before_click": "立即沟通",
        "message_template_id": "boss-current-preset",
        "message_status": "送达",
        "real_name": "陶壮",
        "communication_page_text": "沟通页顶部：陶壮；状态：送达",
        "next_action_for_codex": "record_contact_return_to_list_and_continue",
        "stopped_reason": None,
    })
    assert boss_app_sourcing.main(["consume-executor-result", "--campaign-root", str(root)]) == 0
    consumed = json.loads(capsys.readouterr().out)
    assert consumed["result"] == "sent"
```

- [ ] **Step 2: Run CLI tests and verify parser commands are missing**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_contact_current_cli_with_fixture_returns_zero_and_prints_json tests/test_boss_app_sourcing.py::test_boss_app_sourcing_cli_writes_intent_and_consumes_executor_result -q
```

Expected: FAIL with parser errors for missing CLI commands.

- [ ] **Step 3: Implement executor CLI**

Append to `scripts/boss_contact_executor.py`:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOSS current detail contact executor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    contact = subparsers.add_parser("contact-current")
    contact.add_argument("--campaign-root", required=True)
    contact.add_argument("--execute", action="store_true")
    contact.add_argument("--mock-ui-fixture")
    contact.add_argument("--now")

    validate = subparsers.add_parser("validate")
    validate.add_argument("--campaign-root", required=True)

    summarize = subparsers.add_parser("summarize")
    summarize.add_argument("--campaign-root", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "contact-current":
        ui = FixtureBossUI(args.mock_ui_fixture) if args.mock_ui_fixture else None
        result = contact_current(args.campaign_root, execute=bool(args.execute), ui=ui, now_text=args.now)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["result"] in {"dry_run_ready", "sent", "skipped_continue_chat"}:
            return 0
        if result["result"] == "stopped" and result.get("stopped_reason") in {"stale_lock_requires_review"}:
            return 4
        return 3
    if args.command == "validate":
        report = boss_app_sourcing.validate_executor_artifacts(args.campaign_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "passed" else 1
    if args.command == "summarize":
        summary = boss_app_sourcing.summarize_executor_results(args.campaign_root)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add sourcing CLI commands**

Modify `scripts/boss_app_sourcing.py` parser:

```python
    approve_contact_parser = subparsers.add_parser("approve-contact")
    approve_contact_parser.add_argument("--campaign-root", required=True)
    approve_contact_parser.add_argument("--candidate-key", required=True)
    approve_contact_parser.add_argument("--message-template-id", default="boss-current-preset")

    intent_parser = subparsers.add_parser("write-contact-intent")
    intent_parser.add_argument("--campaign-root", required=True)
    intent_parser.add_argument("--candidate-key", required=True)
    intent_parser.add_argument("--message-template-id", default="boss-current-preset")
    intent_parser.add_argument("--now")

    consume_parser = subparsers.add_parser("consume-executor-result")
    consume_parser.add_argument("--campaign-root", required=True)

    executor_validate_parser = subparsers.add_parser("validate-executor")
    executor_validate_parser.add_argument("--campaign-root", required=True)

    executor_summary_parser = subparsers.add_parser("summarize-executor")
    executor_summary_parser.add_argument("--campaign-root", required=True)
```

Modify `main()` before the final `raise`:

```python
    if args.command == "approve-contact":
        item = record_approved_contact_queue_item(
            args.campaign_root,
            args.candidate_key,
            message_template_id=args.message_template_id,
        )
        print(json.dumps(item, ensure_ascii=False, indent=2))
        return 0
    if args.command == "write-contact-intent":
        intent = write_current_contact_intent(
            args.campaign_root,
            args.candidate_key,
            message_template_id=args.message_template_id,
            now_text=args.now,
        )
        print(json.dumps(intent, ensure_ascii=False, indent=2))
        return 0
    if args.command == "consume-executor-result":
        result = consume_executor_result(args.campaign_root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("result") in {"sent", "skipped_continue_chat"} else 1
    if args.command == "validate-executor":
        report = validate_executor_artifacts(args.campaign_root)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "passed" else 1
    if args.command == "summarize-executor":
        summary = summarize_executor_results(args.campaign_root)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 5: Run CLI tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_contact_executor.py::test_contact_current_cli_with_fixture_returns_zero_and_prints_json tests/test_boss_contact_executor.py::test_contact_current_cli_execute_with_fixture_sends tests/test_boss_contact_executor.py::test_validate_and_summarize_cli tests/test_boss_app_sourcing.py::test_boss_app_sourcing_cli_writes_intent_and_consumes_executor_result -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 5**

```bash
git add scripts/boss_contact_executor.py scripts/boss_app_sourcing.py tests/test_boss_contact_executor.py tests/test_boss_app_sourcing.py
git commit -m "Add BOSS contact executor CLI"
```

---

### Task 6: Update Canonical Workflow Docs, Architecture Tests, And Full Verification

**Files:**
- Modify: `agents/skills/boss-app-recommendation-sourcing/SKILL.md`
- Modify: `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`
- Modify: `tests/test_agent_architecture.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add architecture tests for external executor boundary**

Append to `tests/test_agent_architecture.py`:

```python
def test_boss_app_sourcing_contracts_define_external_executor_handoff():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-app-recommendation-sourcing"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-app-recommendation-sourcing"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    for text in (skill, workflow):
        assert "`structured/approved-contact-queue.jsonl`" in text
        assert "`state/current-contact-intent.json`" in text
        assert "`state/executor-result.json`" in text
        assert "外部执行器" in text
        assert "Codex" in text
        assert "不点击" in text

    assert "contact-current" in workflow
    assert "`--execute`" in workflow
    assert "macOS Accessibility" in workflow
```

- [ ] **Step 2: Run architecture test and verify docs are missing the new boundary**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_app_sourcing_contracts_define_external_executor_handoff -q
```

Expected: FAIL because the canonical skill/workflow do not yet mention executor handoff artifacts.

- [ ] **Step 3: Update canonical skill**

Edit `agents/skills/boss-app-recommendation-sourcing/SKILL.md` output artifacts section to include:

```markdown
可选外部触达执行器产物：

- `structured/approved-contact-queue.jsonl`
- `state/current-contact-intent.json`
- `state/executor.lock`
- `state/executor-result.json`
- `state/stop-executor.flag`
- `raw/executor-contact-attempts.jsonl`
- `reports/executor-summary.md`
- `reports/executor-summary.json`

这些产物只用于用户显式启动的外部执行器。Codex/Computer Use 不因这些文件存在而无人值守点击 `立即沟通`。
```

Edit the safety boundary section to include:

```markdown
- 若用户采用外部触达执行器，Codex 只写 `approved-contact-queue` 和 `current-contact-intent`，不点击真实触达按钮；真实点击只能由用户显式启动的独立 CLI 执行，例如 `scripts.boss_contact_executor contact-current --execute`。
```

- [ ] **Step 4: Update canonical workflow**

Insert after S6 dry-run and before S6b live-test:

```markdown
### S6a 外部执行器 handoff

当候选人 `recommendation=contact`，且当前详情页按钮为 `立即沟通` 时，可写入外部执行器 handoff 产物：

- `structured/approved-contact-queue.jsonl`
- `state/current-contact-intent.json`

Codex 仍不点击 `立即沟通`。用户可在独立终端显式启动：

```bash
.venv/bin/python -m scripts.boss_contact_executor contact-current \
  --campaign-root data/campaigns/<campaign_id> \
  --execute
```

执行器使用 macOS Accessibility / 本机 UI 自动化校验当前详情页、按钮状态和 intent。执行器返回后，Codex 读取 `state/executor-result.json`，通过 sourcing helper 回写 `structured/contact-decisions.jsonl`、`raw/communication-pages.jsonl` 和 `structured/candidates.jsonl`。

如果执行器返回 `stopped` 或 `sent_unverified`，本 workflow 必须写 `reports/interruption-executor-*.json` 和 `state/continuation-plan.json`，停止自动推进。
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_app_sourcing_contracts_define_external_executor_handoff tests/test_boss_contact_executor.py tests/test_boss_app_sourcing.py -q
```

Expected: all selected tests pass.

- [ ] **Step 6: Run full verification**

Run:

```bash
git diff --check
.venv/bin/python -m pytest tests -q
```

Expected:

- `git diff --check` exits `0`.
- Full pytest exits `0`. Existing warning count is acceptable only if it matches current known warnings and no new warning category comes from this implementation.

- [ ] **Step 7: Update task ledger review**

In `tasks/todo.md`, update the active implementation task with:

```markdown
Review：
- 已实现 BOSS 当前详情页触达执行器 MVP：`scripts/boss_contact_executor.py contact-current`。
- 已新增 approved queue、current intent、executor result、audit、summary 和 validation 产物。
- 已接入 existing sourcing 回写：external executor 触达可写入 contact decisions、communication pages 和 candidates snapshot。
- 已更新 canonical BOSS skill/workflow，明确 Codex 不点击真实触达按钮，真实点击由用户显式启动的外部 CLI 执行。
- 验证：`git diff --check` 通过；`.venv/bin/python -m pytest tests -q` 通过。
```

- [ ] **Step 8: Commit Task 6**

```bash
git add agents/skills/boss-app-recommendation-sourcing/SKILL.md agents/workflows/boss-app-recommendation-sourcing/AGENT.md tests/test_agent_architecture.py tasks/todo.md
git commit -m "Document BOSS contact executor handoff"
```

---

## Final Verification

After all tasks are complete, run:

```bash
git status --short
git diff --check
.venv/bin/python -m pytest tests/test_boss_contact_executor.py tests/test_boss_app_sourcing.py tests/test_agent_architecture.py -q
.venv/bin/python -m pytest tests -q
```

Expected:

- `git status --short` shows only intentional uncommitted changes, or is clean after final commit.
- `git diff --check` exits `0`.
- Focused tests pass.
- Full tests pass.

Do not run a live `--execute` against BOSS App as part of automated verification. A real BOSS contact smoke test requires separate user authorization and a current detail page intent.

## Self-Review Checklist

- Spec coverage:
  - Current detail-page-only MVP: Tasks 2, 3, 5.
  - Repository-local executor: Tasks 2-5.
  - macOS Accessibility first: Task 4.
  - Per-run explicit authorization: Task 2 policy tests and Task 5 CLI.
  - Approved queue / current intent / result / audit / lock: Tasks 1-3.
  - Existing sourcing result consumption: Task 1 and Task 5.
  - Error handling for paid, continue chat, unverified communication, stale lock: Tasks 3 and 4.
  - Canonical workflow documentation: Task 6.
- Placeholder scan: no plan step uses placeholder text; all tests, commands, file paths, and expected outcomes are explicit.
- Type consistency:
  - `boss_current_contact_intent_v1`, `boss_executor_result_v1`, `boss_approved_contact_queue_v1`, and `boss_contact_attempt_event_v1` match the approved spec.
  - `communication_page_after_external_executor` is the only new real-name source.
  - `external_executor` is the contact decision mode for successful executor sends.
