import json
from pathlib import Path

import pytest

from scripts import boss_app_sourcing, boss_contact_executor


ACK = "I understand this sends real messages to third-party candidates."


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def test_validate_current_intent_rejects_naive_expires_at(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)
    intent["expires_at"] = "2026-06-02T10:10:00"

    with pytest.raises(ValueError, match="expires_at.*timezone"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00+08:00")


def test_validate_current_intent_rejects_naive_now_text(tmp_path: Path) -> None:
    root, _ = make_executor_campaign(tmp_path)
    intent = boss_contact_executor.load_current_intent(root)

    with pytest.raises(ValueError, match="now_text.*timezone"):
        boss_contact_executor.validate_current_intent(intent, now_text="2026-06-02T10:05:00")
