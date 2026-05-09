"""项目路径约定。

运行时适配器和业务脚本都通过这里定位 canonical agent 资源。
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = PROJECT_ROOT / "agents"
WORKFLOWS_DIR = AGENTS_DIR / "workflows"
RULES_DIR = PROJECT_ROOT / "rules"


def workflow_dir(name: str) -> Path:
    """返回指定工作流的 canonical 目录。"""
    return WORKFLOWS_DIR / name


def rules_dir(name: str | None = None) -> Path:
    """返回规则目录。传入 name 时返回该工作流的规则子目录。"""
    if name is None:
        return RULES_DIR
    return RULES_DIR / name
