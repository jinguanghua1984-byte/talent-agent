from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "dev" / "script-inventory.md"


def test_script_inventory_exists_and_names_cleanup_boundaries() -> None:
    text = INVENTORY.read_text(encoding="utf-8")
    required_markers = [
        "## Runtime CLI",
        "## Library Modules",
        "## Legacy Compatibility",
        "## Removed Or Approval-Gated Scripts",
        "score_candidates.py",
        "hunyuan_abc_detail_tasks.py",
        "hunyuan_abc_parallel_supervisor.ps1",
        "maimai_ai_infra_search_plan.py",
        "data-manager.py",
    ]
    missing = [marker for marker in required_markers if marker not in text]
    assert missing == []


def test_runtime_scripts_do_not_contain_pytest_modules() -> None:
    offenders = sorted(path.name for path in (ROOT / "scripts").glob("test_*.py"))
    assert offenders == []
