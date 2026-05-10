from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "agents" / "workflows" / "talent-library"


def test_talent_library_workflow_resources_exist():
    expected = [
        WORKFLOW / "AGENT.md",
        WORKFLOW / "references" / "scenarios.md",
        WORKFLOW / "references" / "data-contract.md",
        WORKFLOW / "references" / "safety-rules.md",
        WORKFLOW / "assets" / "candidate-table-template.md",
        WORKFLOW / "assets" / "import-report-template.md",
        WORKFLOW / "assets" / "delete-confirmation-template.md",
    ]

    for path in expected:
        assert path.exists(), f"missing talent-library resource: {path}"


def test_talent_library_workflow_declares_all_scenes():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    scenarios = (WORKFLOW / "references" / "scenarios.md").read_text(encoding="utf-8")

    for scene in ["import", "search", "match", "score", "detail", "update", "delete"]:
        assert scene in text
        assert f"## {scene}" in scenarios


def test_talent_library_workflow_is_sqlite_first():
    text = (WORKFLOW / "AGENT.md").read_text(encoding="utf-8")
    data_contract = (WORKFLOW / "references" / "data-contract.md").read_text(
        encoding="utf-8"
    )

    assert "data/talent.db" in text
    assert "data/talent.db" in data_contract
    assert "旧 `data/candidates/*.json` 只作为迁移和兼容入口" in data_contract


def test_talent_library_safety_mentions_hard_delete_confirmation():
    safety = (WORKFLOW / "references" / "safety-rules.md").read_text(encoding="utf-8")
    delete_template = (
        WORKFLOW / "assets" / "delete-confirmation-template.md"
    ).read_text(encoding="utf-8")

    assert "删除必须二次确认" in safety
    assert "确认删除候选人 <candidate_id>" in delete_template
