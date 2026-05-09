"""agent_paths 统一路径解析模块测试"""

from pathlib import Path

from scripts.agent_paths import PROJECT_ROOT, workflow_dir, rules_dir


def test_project_root_points_to_repo():
    assert (PROJECT_ROOT / "README.md").exists()


def test_workflow_dir_points_to_agents_workflows():
    assert workflow_dir("platform-match") == PROJECT_ROOT / "agents" / "workflows" / "platform-match"


def test_rules_dir_points_to_root_rules():
    assert rules_dir("platform-match") == PROJECT_ROOT / "rules" / "platform-match"
