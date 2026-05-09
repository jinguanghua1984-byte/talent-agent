from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ["public-search", "platform-match", "screen", "report"]


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


def test_claude_skill_files_are_adapters_to_canonical_workflows():
    for name in WORKFLOWS:
        path = ROOT / ".claude" / "skills" / name / "SKILL.md"
        assert path.exists(), f"missing Claude adapter: {path}"
        text = path.read_text(encoding="utf-8")
        assert f"agents/workflows/{name}/AGENT.md" in text
        assert "Claude Code Adapter" in text
