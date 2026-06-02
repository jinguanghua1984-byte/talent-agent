from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = [
    "public-search",
    "platform-match",
    "screen",
    "report",
    "talent-library",
    "wechat-chat-sync",
    "jd-talent-delivery",
    "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing",
]

CANONICAL_SKILL_WORKFLOWS = {
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
}

CLAUDE_ADAPTER_WORKFLOWS = {
    "public-search": "public-search",
    "platform-match": "platform-match",
    "screen": "screen",
    "report": "report",
    "talent-library": "talent-library",
    "wechat-chat-sync": "wechat-chat-sync",
    "jd-talent-delivery": "jd-talent-delivery",
    "maimai-talent-search-campaign": "maimai-unattended-campaign",
    "boss-app-recommendation-sourcing": "boss-app-recommendation-sourcing",
}


def markdown_section(text: str, heading: str) -> str:
    marker = f"### {heading}"
    start = text.index(marker)
    next_heading = text.find("\n### ", start + len(marker))
    if next_heading == -1:
        return text[start:]
    return text[start:next_heading]


def test_canonical_workflow_files_exist():
    for name in WORKFLOWS:
        path = ROOT / "agents" / "workflows" / name / "AGENT.md"
        assert path.exists(), f"missing canonical workflow: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"name: {name}" in text
        assert "## 触发入口" in text or "## 触发" in text


def test_canonical_workflows_do_not_reference_runtime_private_paths():
    forbidden = [
        ".claude/skills",
        "Claude Code",
        "Claude 在内存",
        "Claude 解析",
        "Claude 抽象",
        "WebSearch",
        "mcp__",
        "`Read`",
        "`Write`",
        "`Bash`",
    ]
    for name in WORKFLOWS:
        path = ROOT / "agents" / "workflows" / name / "AGENT.md"
        text = path.read_text(encoding="utf-8")
        hits = [word for word in forbidden if word in text]
        assert hits == [], f"{path} contains runtime-specific terms: {hits}"


def test_runtime_neutral_skill_contracts_live_under_agents():
    for skill_name, workflow_name in CANONICAL_SKILL_WORKFLOWS.items():
        path = ROOT / "agents" / "skills" / skill_name / "SKILL.md"
        text = path.read_text(encoding="utf-8")
        assert f"name: {skill_name}" in text
        assert f"agents/workflows/{workflow_name}/AGENT.md" in text
        assert "## 目标" in text

    assert not (ROOT / "skills").exists()


def test_claude_skill_files_are_adapters_to_canonical_workflows():
    for name, workflow_name in CLAUDE_ADAPTER_WORKFLOWS.items():
        path = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert path.exists(), f"missing Claude adapter: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"agents/workflows/{workflow_name}/AGENT.md" in text
        assert "Claude Code Adapter" in text
        assert "## Adapter Steps" in text
        assert "agents/capabilities.md" in text
        assert "运行时私有入口" in text
        if name in CANONICAL_SKILL_WORKFLOWS:
            assert f"agents/skills/{name}/SKILL.md" in text


def test_readme_describes_runtime_neutral_architecture():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "运行时中立" in text
    assert "agents/skills/" in text
    assert "agents/workflows/" in text
    assert ".claude/skills/ — Claude Code 兼容适配器" in text


def test_env_example_uses_generic_llm_settings():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LLM_PROVIDER=" in text
    assert "LLM_MODEL=" in text
    assert "LLM_API_KEY=" in text
    assert "ANTHROPIC_API_KEY" in text


def test_capabilities_include_local_app_operations():
    text = (ROOT / "agents" / "capabilities.md").read_text(encoding="utf-8")
    assert "`computer.operate`" in text
    assert "本地 App" in text


def test_boss_app_sourcing_contracts_define_contact_audit_gates():
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
    s6b = markdown_section(workflow, "S6b live-test 真实沟通")
    s6c = markdown_section(workflow, "S6c 人工已沟通页面回采")

    for text in (skill, workflow):
        assert "`allow_real_contact=true`" in text
        assert "`allow_live_contact_test=true`" in text
        assert "默认绝不点击" in text

    assert "`allow_real_contact=true`" in s6b
    assert "`allow_live_contact_test=true`" in s6b
    assert "`live_contact_test_limit`" in s6b
    assert "`human.confirm`" in s6b
    assert "动作级确认" in s6b
    assert "自动发送预设消息" in s6b
    assert "`raw/communication-pages.jsonl`" in s6b
    assert "`structured/contact-decisions.jsonl`" in s6b
    assert "`structured/candidates.jsonl`" in s6b
    assert "real_name_source=communication_page_after_live_contact_test" in s6b

    assert "`raw/communication-pages.jsonl`" in s6c
    assert "`structured/contact-decisions.jsonl`" in s6c
    assert "`structured/candidates.jsonl`" in s6c
    assert "real_name_source=manual_opened_communication_page" in s6c
    assert "不发送新消息" in s6c

    assert "`reports/interruption-<stage>-<reason>-<timestamp>.json`" in workflow
    assert "`state/continuation-plan.json`" in workflow
    assert "`state/events.jsonl`" in workflow


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
