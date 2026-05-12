from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "agents" / "workflows" / "wechat-chat-sync"


def test_wechat_chat_sync_workflow_resources_exist():
    expected = [
        WORKFLOW / "AGENT.md",
        WORKFLOW / "references" / "cli-contract.md",
        WORKFLOW / "references" / "timeline-format.md",
        WORKFLOW / "assets" / "timeline-template.md",
        ROOT / ".claude" / "skills" / "wechat-chat-sync" / "SKILL.md",
    ]

    for path in expected:
        assert path.exists(), f"missing wechat-chat-sync resource: {path}"


def test_wechat_chat_sync_workflow_declares_safety_boundaries():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    cli_contract = (WORKFLOW / "references" / "cli-contract.md").read_text(
        encoding="utf-8"
    )
    timeline_format = (WORKFLOW / "references" / "timeline-format.md").read_text(
        encoding="utf-8"
    )

    assert "不得默认导出全量聊天" in text
    assert "wechat-cli export" in cli_contract
    assert "不把正文复制到 `candidate_details.raw_data`" in timeline_format
