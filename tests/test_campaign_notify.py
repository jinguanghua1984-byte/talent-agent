import json
from pathlib import Path

import pytest

from scripts.campaign_notify import build_message_text, build_send_argv, main


def _event() -> dict[str, object]:
    return {
        "campaign_id": "ai-infra-demo",
        "blocked_stage": "detail_live",
        "reason": "captcha_api",
        "completed": 46,
        "total": 149,
        "evidence_file": "data/campaigns/demo/reports/interruption.json",
        "resume_command": "python -m scripts.maimai_campaign_orchestrator resume --campaign-root data/campaigns/demo",
    }


def test_build_message_text_includes_checkpoint_progress_and_resume_command():
    text = build_message_text(_event())

    assert "ai-infra-demo" in text
    assert "detail_live" in text
    assert "captcha_api" in text
    assert "46/149" in text
    assert "data/campaigns/demo/reports/interruption.json" in text
    assert "resume --campaign-root" in text
    assert "处理平台验证/登录/安全页面后" in text
    assert "不刷新页面" in text


def test_build_message_text_does_not_include_sensitive_raw_fields():
    event = {
        **_event(),
        "raw_capture": {"contacts": [{"name": "不应出现"}]},
        "cookie": "session=secret-cookie",
        "token": "secret-token",
    }

    text = build_message_text(event)

    assert "不应出现" not in text
    assert "secret-cookie" not in text
    assert "secret-token" not in text


def test_build_send_argv_uses_lark_messages_send_dry_run_and_idempotency_key():
    argv = build_send_argv(
        identity="bot",
        chat_id="oc_xxx",
        user_id="",
        text="Campaign blocked",
        idempotency_key="ai-infra-demo-detail_live-captcha",
        dry_run=True,
    )

    assert argv == [
        "lark-cli",
        "im",
        "+messages-send",
        "--as",
        "bot",
        "--chat-id",
        "oc_xxx",
        "--text",
        "Campaign blocked",
        "--idempotency-key",
        "ai-infra-demo-detail_live-captcha",
        "--dry-run",
    ]


def test_build_send_argv_supports_user_id_target():
    argv = build_send_argv(
        identity="user",
        chat_id="",
        user_id="ou_xxx",
        text="Campaign blocked",
        idempotency_key="ai-infra-demo-detail_live-captcha",
        dry_run=False,
    )

    assert "--user-id" in argv
    assert "ou_xxx" in argv
    assert "--chat-id" not in argv
    assert "--dry-run" not in argv


@pytest.mark.parametrize(
    ("identity", "chat_id", "user_id"),
    [
        ("app", "oc_xxx", ""),
        ("bot", "", ""),
        ("bot", "oc_xxx", "ou_xxx"),
    ],
)
def test_build_send_argv_rejects_invalid_identity_or_target(identity, chat_id, user_id):
    with pytest.raises(ValueError):
        build_send_argv(
            identity=identity,
            chat_id=chat_id,
            user_id=user_id,
            text="Campaign blocked",
            idempotency_key="ai-infra-demo-detail_live-captcha",
            dry_run=True,
        )


def test_cli_dry_run_prints_preview_without_subprocess(tmp_path: Path, monkeypatch, capsys):
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(_event(), ensure_ascii=False), encoding="utf-8-sig")

    def fail_run(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called in dry-run")

    monkeypatch.setattr("scripts.campaign_notify.subprocess.run", fail_run)

    code = main([
        "--event",
        str(event_path),
        "--identity",
        "bot",
        "--chat-id",
        "oc_xxx",
        "--dry-run",
    ])

    assert code == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["argv"][:3] == ["lark-cli", "im", "+messages-send"]
    assert preview["text"] == build_message_text(_event())
    assert preview["idempotency_key"] == "ai-infra-demo-detail_live-captcha_api"
