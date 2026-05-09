# 通用 Agent 项目架构改造 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前以 Claude Code Skill 为中心的 Talent Agent 改造成运行时中立的通用 agent 项目，同时保留 Claude Code 作为一个兼容适配器。

**Architecture:** 建立 `agents/` 作为规范层，沉淀工作流、工具能力契约和运行时适配说明；把可执行 Python 逻辑从 `.claude/skills/` 迁到根目录包中；把 LLM 调用从 Anthropic 专用客户端抽象为可切换 provider。`.claude/skills/*/SKILL.md` 只保留薄适配层，读取并执行 `agents/workflows/*/AGENT.md`。

**Tech Stack:** Python 3.11+, pytest, Playwright, python-dotenv, Anthropic SDK（兼容保留）, stdlib `urllib`（OpenAI-compatible provider）, Markdown workflow specs.

**Scope:** 本计划做第一期架构改造：通用目录、可执行代码迁移、LLM provider 抽象、Claude adapter 薄化、文档和测试。历史设计文档不批量改写，只更新当前入口文档和活跃运行时文件。

---

## 当前耦合点

1. `README.md` 明确写死 `.claude/skills/` 和 Claude Code 安装方式。
2. `.env.example` 只暴露 `ANTHROPIC_API_KEY`。
3. `requirements.txt` 只包含 `anthropic` 作为 LLM SDK。
4. `scripts/pipeline_utils.py` 中 `create_llm_client()` 直接构造 `anthropic.Anthropic`，并读取 `ANTHROPIC_API_KEY` / `ANTHROPIC_BASE_URL`。
5. `scripts/jd_analyzer.py`、`scripts/llm_ranker.py`、`scripts/score_pipeline.py` 当前默认模型为 `intelligence`，但 provider 仍未抽象。
6. `scripts/pipeline_utils.py` 读取 `.claude/skills/platform-match/rules/company-aliases.json`。
7. `scripts/test_boss.py`、`scripts/test_maimai.py`、`scripts/test_enrich.py`、`scripts/test_rate_limiter.py` 通过 `sys.path` 导入 `.claude/skills/platform-match/scripts`。
8. `.claude/skills/*/SKILL.md` 是主工作流定义，内容中直接使用 Claude、Read、Write、Bash、WebSearch、MCP 工具名。
9. `.claude/skills/public-search/scripts/token-tracker.py` 只面向 Claude Code OpenTelemetry。

## 目标文件结构

```text
talent-agent/
├── AGENTS.md
├── agents/
│   ├── README.md
│   ├── capabilities.md
│   ├── adapters/
│   │   └── claude-code/
│   │       └── README.md
│   └── workflows/
│       ├── public-search/
│       │   ├── AGENT.md
│       │   ├── references/
│       │   └── scripts/
│       ├── platform-match/
│       │   ├── AGENT.md
│       │   ├── assets/
│       │   ├── evals/
│       │   └── references/
│       ├── screen/
│       │   ├── AGENT.md
│       │   └── references/
│       └── report/
│           ├── AGENT.md
│           └── references/
├── scripts/
│   ├── agent_paths.py
│   ├── llm_client.py
│   ├── platform_match/
│   │   ├── __init__.py
│   │   ├── batch_progress.py
│   │   ├── enrich.py
│   │   ├── rate_limiter.py
│   │   ├── search.py
│   │   ├── session.py
│   │   └── adapters/
│   └── public_search/
│       ├── __init__.py
│       └── token_tracker.py
├── rules/
│   ├── company-aliases.json
│   ├── scoring-config.json
│   └── platform-match/
│       ├── identity-rules.md
│       └── jd-match-rules.md
└── .claude/
    └── skills/
        ├── public-search/SKILL.md
        ├── platform-match/SKILL.md
        ├── screen/SKILL.md
        └── report/SKILL.md
```

---

### Task 1: 建立运行时中立的 agent 规范层

**Files:**
- Create: `AGENTS.md`
- Create: `agents/README.md`
- Create: `agents/capabilities.md`
- Create: `agents/adapters/claude-code/README.md`
- Create: `agents/workflows/public-search/AGENT.md`
- Create: `agents/workflows/platform-match/AGENT.md`
- Create: `agents/workflows/screen/AGENT.md`
- Create: `agents/workflows/report/AGENT.md`
- Create: `tests/test_agent_architecture.py`

- [ ] **Step 1.1: 写失败测试，约束规范层必须存在**

Create `tests/test_agent_architecture.py`:

```python
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
```

- [ ] **Step 1.2: 运行测试确认失败**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: FAIL，原因是 `agents/workflows/*/AGENT.md` 和 adapter wrapper 还不存在。

- [ ] **Step 1.3: 创建 `agents/capabilities.md`**

Write `agents/capabilities.md`:

```markdown
# Agent Capabilities Contract

本项目的工作流只描述通用能力，不绑定具体 agent 运行时。

| 通用能力 | 语义 | Claude Code 映射 | Codex 映射 |
| --- | --- | --- | --- |
| `file.read` | 读取项目内文本文件 | Read | shell / filesystem |
| `file.write` | 创建或更新项目内文本文件 | Write / Edit | apply_patch |
| `shell.run` | 执行本地命令 | Bash | shell_command |
| `web.search` | 搜索公开网页 | WebSearch / MCP search | web search / browser skill |
| `web.fetch` | 抓取网页正文 | MCP fetch / reader | web open / browser skill |
| `browser.operate` | 操作本地浏览器或调试端口 | MCP browser / Playwright | browser plugin / Playwright |
| `human.confirm` | 需要用户确认后继续 | 直接询问用户 | 直接询问用户 |

工作流规则：

1. `agents/workflows/*/AGENT.md` 只使用上表中的通用能力名称。
2. 运行时私有工具名称只能出现在 `agents/adapters/*` 或对应运行时目录中。
3. 可执行 Python 代码必须放在项目根目录 `scripts/` 包内，不能放在运行时私有目录中。
```

- [ ] **Step 1.4: 创建 `agents/README.md`**

Write `agents/README.md`:

```markdown
# Talent Agent Runtime-Neutral Architecture

`agents/` 是 Talent Agent 的规范层，定义所有 agent 都能执行的工作流、工具能力契约和运行时适配方式。

## 目录

- `capabilities.md`：通用能力名称与各运行时工具映射。
- `workflows/`：运行时中立的业务工作流。
- `adapters/`：面向具体 agent 运行时的适配说明。

## 分层约定

1. 业务流程写在 `agents/workflows/<name>/AGENT.md`。
2. 可执行逻辑写在 `scripts/`。
3. 配置和规则写在 `rules/`、`schemas/`、`data/search-strategies/`。
4. 运行时目录只做入口适配，例如 `.claude/skills/*/SKILL.md`。
```

- [ ] **Step 1.5: 从现有 Skill 复制生成 canonical workflow**

对四个工作流执行内容迁移：

| Source | Target |
| --- | --- |
| `.claude/skills/public-search/SKILL.md` | `agents/workflows/public-search/AGENT.md` |
| `.claude/skills/platform-match/SKILL.md` | `agents/workflows/platform-match/AGENT.md` |
| `.claude/skills/screen/SKILL.md` | `agents/workflows/screen/AGENT.md` |
| `.claude/skills/report/SKILL.md` | `agents/workflows/report/AGENT.md` |

每个 target 保留 YAML frontmatter 中的 `name` 和 `description`，并进行以下精确替换：

```text
Claude Code -> agent runtime
Claude -> agent
WebSearch -> web.search
mcp__ddg-search__search -> web.search
mcp__ddg-search__fetch_content -> web.fetch
mcp__jina-reader__jina_reader -> web.fetch
mcp__github__search_users -> web.search.github_users
mcp__github__search_code -> web.search.github_code
Read -> file.read
Write -> file.write
Bash -> shell.run
.claude/skills/platform-match/references -> agents/workflows/platform-match/references
.claude/skills/screen/references -> agents/workflows/screen/references
.claude/skills/public-search/scripts/token-tracker.py -> scripts/public_search/token_tracker.py
python scripts/search.py -> python -m scripts.platform_match.search
python scripts/session.py -> python -m scripts.platform_match.session
python scripts/enrich.py -> python -m scripts.platform_match.enrich
python scripts/rate_limiter.py -> python -m scripts.platform_match.rate_limiter
```

- [ ] **Step 1.6: 创建 `agents/adapters/claude-code/README.md`**

Write `agents/adapters/claude-code/README.md`:

```markdown
# Claude Code Adapter

Claude Code 通过 `.claude/skills/*/SKILL.md` 进入工作流。每个 Skill 文件只负责：

1. 保留 Claude Code 需要的 frontmatter。
2. 读取对应的 `agents/workflows/<name>/AGENT.md`。
3. 按 `agents/capabilities.md` 将通用能力映射到 Claude Code 工具。

Claude Code 私有配置保留在 `.claude/settings.local.json`，不进入通用规范层。
```

- [ ] **Step 1.7: 创建顶层 `AGENTS.md`**

Write `AGENTS.md`:

```markdown
# AGENTS.md

本仓库采用运行时中立的 agent 架构。

## 工作流入口

通用工作流位于 `agents/workflows/<name>/AGENT.md`。运行时适配器必须读取 canonical workflow 后再执行。

## 可执行代码

Python 代码位于 `scripts/`。运行时目录不得保存业务脚本，只能保存入口适配文件。

## 验证

完成改造后运行：

```bash
python -m pytest tests scripts -q
```

## 沟通

默认使用中文交流；代码注释和文档也使用中文。
```

- [ ] **Step 1.8: 运行规范层测试**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: PASS。

- [ ] **Step 1.9: Commit**

```bash
git add AGENTS.md agents tests/test_agent_architecture.py
git commit -m "docs: 建立运行时中立的 agent 规范层"
```

---

### Task 2: 将 platform-match 可执行代码迁出 `.claude`

**Files:**
- Create: `scripts/platform_match/__init__.py`
- Move: `.claude/skills/platform-match/scripts/batch_progress.py` -> `scripts/platform_match/batch_progress.py`
- Move: `.claude/skills/platform-match/scripts/enrich.py` -> `scripts/platform_match/enrich.py`
- Move: `.claude/skills/platform-match/scripts/rate_limiter.py` -> `scripts/platform_match/rate_limiter.py`
- Move: `.claude/skills/platform-match/scripts/search.py` -> `scripts/platform_match/search.py`
- Move: `.claude/skills/platform-match/scripts/session.py` -> `scripts/platform_match/session.py`
- Move: `.claude/skills/platform-match/scripts/adapters/` -> `scripts/platform_match/adapters/`
- Modify: `scripts/test_boss.py`
- Modify: `scripts/test_maimai.py`
- Modify: `scripts/test_enrich.py`
- Modify: `scripts/test_rate_limiter.py`

- [ ] **Step 2.1: 修改测试导入路径，让测试先失败**

在 `scripts/test_boss.py` 删除 `SCRIPTS_DIR` / `sys.path.insert` 逻辑，并替换导入：

```python
from scripts.platform_match.adapters.base import SearchParams
from scripts.platform_match.adapters import ADAPTERS
from scripts.platform_match.enrich import cmd_map
from scripts.platform_match.session import PLATFORM_VERIFY_URLS
from scripts.platform_match.rate_limiter import DEFAULT_LIMITS
from scripts.platform_match.adapters.boss import BossAdapter
```

在测试方法中把 `from adapters...`、`from enrich...`、`from session...`、`from rate_limiter...` 全部替换为 `from scripts.platform_match...`。

对 `scripts/test_maimai.py` 执行同样替换：

```python
from scripts.platform_match.adapters.maimai import MaimaiAdapter, _normalize_period, _parse_work_years
```

对 `scripts/test_enrich.py` 执行同样替换：

```python
from scripts.platform_match.enrich import merge_fields, append_source, enrich_enrichment_level
```

对 `scripts/test_rate_limiter.py` 执行同样替换：

```python
from scripts.platform_match import rate_limiter
from scripts.platform_match.rate_limiter import check_search, record_search
```

- [ ] **Step 2.2: 运行迁移测试确认失败**

Run: `python -m pytest scripts/test_boss.py scripts/test_maimai.py scripts/test_enrich.py scripts/test_rate_limiter.py -q`

Expected: FAIL，原因是 `scripts.platform_match` 还不存在。

- [ ] **Step 2.3: 创建包目录并迁移文件**

使用精确文件移动，不做递归删除：

```powershell
New-Item -ItemType Directory -Force scripts\platform_match\adapters
Move-Item -LiteralPath .claude\skills\platform-match\scripts\batch_progress.py -Destination scripts\platform_match\batch_progress.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\enrich.py -Destination scripts\platform_match\enrich.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\rate_limiter.py -Destination scripts\platform_match\rate_limiter.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\search.py -Destination scripts\platform_match\search.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\session.py -Destination scripts\platform_match\session.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\adapters\base.py -Destination scripts\platform_match\adapters\base.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\adapters\boss.py -Destination scripts\platform_match\adapters\boss.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\adapters\maimai.py -Destination scripts\platform_match\adapters\maimai.py
Move-Item -LiteralPath .claude\skills\platform-match\scripts\adapters\__init__.py -Destination scripts\platform_match\adapters\__init__.py
```

Create `scripts/platform_match/__init__.py`:

```python
"""平台匹配运行时代码包。"""
```

- [ ] **Step 2.4: 修正包内导入**

在 `scripts/platform_match/search.py`、`scripts/platform_match/enrich.py`、`scripts/platform_match/session.py` 中执行这些替换：

```text
from adapters -> from scripts.platform_match.adapters
import adapters -> from scripts.platform_match import adapters
from rate_limiter -> from scripts.platform_match.rate_limiter
import rate_limiter -> from scripts.platform_match import rate_limiter
```

如果文件里存在基于 `__file__` 推导 `.claude/skills/platform-match/scripts` 的注释或路径，改为项目根目录相对路径。

- [ ] **Step 2.5: 运行 platform-match 测试**

Run: `python -m pytest scripts/test_boss.py scripts/test_maimai.py scripts/test_enrich.py scripts/test_rate_limiter.py -q`

Expected: PASS。

- [ ] **Step 2.6: 确认 `.claude` 不再保存业务脚本**

Run: `Get-ChildItem -Recurse -File .claude\skills\platform-match\scripts`

Expected: 只允许目录不存在，或只剩兼容说明文件；不允许存在 `.py` 业务脚本。

- [ ] **Step 2.7: Commit**

```bash
git add scripts/platform_match scripts/test_boss.py scripts/test_maimai.py scripts/test_enrich.py scripts/test_rate_limiter.py .claude/skills/platform-match/scripts
git commit -m "refactor: 将 platform-match 代码迁出 Claude 私有目录"
```

---

### Task 3: 统一资源、规则和路径解析

**Files:**
- Create: `scripts/agent_paths.py`
- Move: `.claude/skills/platform-match/assets/` -> `agents/workflows/platform-match/assets/`
- Move: `.claude/skills/platform-match/evals/` -> `agents/workflows/platform-match/evals/`
- Move: `.claude/skills/platform-match/references/` -> `agents/workflows/platform-match/references/`
- Move: `.claude/skills/public-search/references/` -> `agents/workflows/public-search/references/`
- Move: `.claude/skills/screen/references/` -> `agents/workflows/screen/references/`
- Move: `.claude/skills/report/references/` -> `agents/workflows/report/references/`
- Move: `.claude/skills/platform-match/rules/identity-rules.md` -> `rules/platform-match/identity-rules.md`
- Move: `.claude/skills/platform-match/rules/jd-match-rules.md` -> `rules/platform-match/jd-match-rules.md`
- Modify: `scripts/pipeline_utils.py`
- Modify: `tests/test_pipeline_utils.py`

- [ ] **Step 3.1: 写路径测试**

Append to `tests/test_pipeline_utils.py`:

```python
def test_load_company_aliases_does_not_depend_on_claude_private_dir(tmp_path, monkeypatch):
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    (rules_dir / "company-aliases.json").write_text(
        json.dumps({"测试公司": ["testco"]}), encoding="utf-8"
    )

    import scripts.pipeline_utils as pipeline_utils
    monkeypatch.setattr(pipeline_utils, "RULES_DIR", rules_dir)
    monkeypatch.setattr(pipeline_utils, "PROJECT_ROOT", tmp_path)

    aliases = pipeline_utils.load_company_aliases()
    assert aliases == {"测试公司": ["testco"]}
```

Create `tests/test_agent_paths.py`:

```python
from pathlib import Path

from scripts.agent_paths import PROJECT_ROOT, workflow_dir, rules_dir


def test_project_root_points_to_repo():
    assert (PROJECT_ROOT / "README.md").exists()


def test_workflow_dir_points_to_agents_workflows():
    assert workflow_dir("platform-match") == PROJECT_ROOT / "agents" / "workflows" / "platform-match"


def test_rules_dir_points_to_root_rules():
    assert rules_dir("platform-match") == PROJECT_ROOT / "rules" / "platform-match"
```

- [ ] **Step 3.2: 运行路径测试确认失败**

Run: `python -m pytest tests/test_agent_paths.py tests/test_pipeline_utils.py -q`

Expected: FAIL，原因是 `scripts.agent_paths` 不存在，`pipeline_utils.load_company_aliases()` 仍读取 `.claude` 规则目录。

- [ ] **Step 3.3: 创建 `scripts/agent_paths.py`**

Write `scripts/agent_paths.py`:

```python
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
```

- [ ] **Step 3.4: 迁移资源文件**

使用精确目录移动前先创建目标目录：

```powershell
New-Item -ItemType Directory -Force agents\workflows\platform-match
New-Item -ItemType Directory -Force agents\workflows\public-search
New-Item -ItemType Directory -Force agents\workflows\screen
New-Item -ItemType Directory -Force agents\workflows\report
New-Item -ItemType Directory -Force rules\platform-match
Move-Item -LiteralPath .claude\skills\platform-match\assets -Destination agents\workflows\platform-match\assets
Move-Item -LiteralPath .claude\skills\platform-match\evals -Destination agents\workflows\platform-match\evals
Move-Item -LiteralPath .claude\skills\platform-match\references -Destination agents\workflows\platform-match\references
Move-Item -LiteralPath .claude\skills\public-search\references -Destination agents\workflows\public-search\references
Move-Item -LiteralPath .claude\skills\screen\references -Destination agents\workflows\screen\references
Move-Item -LiteralPath .claude\skills\report\references -Destination agents\workflows\report\references
Move-Item -LiteralPath .claude\skills\platform-match\rules\identity-rules.md -Destination rules\platform-match\identity-rules.md
Move-Item -LiteralPath .claude\skills\platform-match\rules\jd-match-rules.md -Destination rules\platform-match\jd-match-rules.md
```

合并 `.claude/skills/platform-match/rules/company-aliases.json` 到 `rules/company-aliases.json`：保留根目录现有 key，补充 `.claude` 中仅有的 key 和 alias。

- [ ] **Step 3.5: 修改 `scripts/pipeline_utils.py` 的规则读取**

Remove `SKILLS_RULES_DIR` and replace `load_company_aliases()` with:

```python
def load_company_aliases() -> dict[str, list[str]]:
    """加载公司别名映射。规则只从项目根目录 rules/company-aliases.json 读取。"""
    path = RULES_DIR / "company-aliases.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return {str(company): list(alias_list) for company, alias_list in data.items()}
```

- [ ] **Step 3.6: 运行资源路径测试**

Run: `python -m pytest tests/test_agent_paths.py tests/test_pipeline_utils.py -q`

Expected: PASS。

- [ ] **Step 3.7: 扫描业务代码中的 `.claude` 路径**

Run: `rg -n "\.claude" scripts tests agents/workflows`

Expected: no output。

- [ ] **Step 3.8: Commit**

```bash
git add scripts/agent_paths.py scripts/pipeline_utils.py tests/test_agent_paths.py tests/test_pipeline_utils.py agents/workflows rules .claude/skills
git commit -m "refactor: 统一 agent 资源和规则路径"
```

---

### Task 4: 增加通用 LLM provider 抽象

**Files:**
- Create: `scripts/llm_client.py`
- Modify: `scripts/pipeline_utils.py`
- Create: `tests/test_llm_client.py`
- Modify: `tests/test_jd_analyzer.py`
- Modify: `tests/test_llm_ranker.py`

- [ ] **Step 4.1: 写 LLM client 单元测试**

Create `tests/test_llm_client.py`:

```python
import json
import os

import pytest

from scripts.llm_client import LLMSettings, OpenAICompatibleClient, create_llm_client
from scripts.pipeline_utils import call_llm_with_retry


def test_settings_prefers_generic_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")

    settings = LLMSettings.from_env()

    assert settings.provider == "openai-compatible"
    assert settings.model == "deepseek-chat"
    assert settings.api_key == "generic-key"
    assert settings.base_url == "https://api.example.com/v1"


def test_settings_keeps_anthropic_backward_compatibility(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic.example")

    settings = LLMSettings.from_env(provider="anthropic")

    assert settings.provider == "anthropic"
    assert settings.api_key == "anthropic-key"
    assert settings.base_url == "https://anthropic.example"


def test_create_llm_client_openai_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "model-x")
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")

    client = create_llm_client()

    assert isinstance(client, OpenAICompatibleClient)
    assert client.settings.model == "model-x"


def test_call_llm_with_retry_supports_generic_complete_client():
    class FakeClient:
        def complete(self, messages, model, max_tokens):
            assert model == "model-x"
            assert max_tokens == 123
            assert messages == [{"role": "user", "content": "hi"}]
            return "ok"

    result = call_llm_with_retry(
        FakeClient(),
        "model-x",
        [{"role": "user", "content": "hi"}],
        max_tokens=123,
    )

    assert result == "ok"
```

- [ ] **Step 4.2: 运行 LLM 测试确认失败**

Run: `python -m pytest tests/test_llm_client.py -q`

Expected: FAIL，原因是 `scripts.llm_client` 不存在。

- [ ] **Step 4.3: 创建 `scripts/llm_client.py`**

Write `scripts/llm_client.py`:

```python
"""通用 LLM provider 客户端。

默认保留 Anthropic 兼容；新增 OpenAI-compatible HTTP provider，覆盖 OpenAI、
DeepSeek、Ollama、以及提供 /v1/chat/completions 的模型服务。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import request


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        model: str | None = None,
    ) -> "LLMSettings":
        resolved_provider = provider or os.environ.get("LLM_PROVIDER", "anthropic")
        resolved_model = model or os.environ.get("LLM_MODEL", "intelligence")

        if resolved_provider == "anthropic":
            api_key = os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
            base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
        else:
            api_key = os.environ.get("LLM_API_KEY", "")
            base_url = os.environ.get("LLM_BASE_URL")

        if not api_key:
            raise EnvironmentError(
                "未设置 LLM_API_KEY；Anthropic 兼容模式也支持 ANTHROPIC_API_KEY"
            )

        return cls(
            provider=resolved_provider,
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
        )


class AnthropicMessagesClient:
    """Anthropic messages API 适配器。"""

    def __init__(self, settings: LLMSettings):
        import anthropic

        kwargs: dict[str, Any] = {"api_key": settings.api_key}
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self.settings = settings

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=model or self.settings.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.content[0].text


class OpenAICompatibleClient:
    """OpenAI-compatible /v1/chat/completions HTTP 客户端。"""

    def __init__(self, settings: LLMSettings):
        if not settings.base_url:
            raise EnvironmentError("openai-compatible provider 需要设置 LLM_BASE_URL")
        self.settings = settings

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        payload = json.dumps({
            "model": model or self.settings.model,
            "messages": messages,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        req = request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


def create_llm_client(
    provider: str | None = None,
    model: str | None = None,
) -> AnthropicMessagesClient | OpenAICompatibleClient:
    settings = LLMSettings.from_env(provider=provider, model=model)
    if settings.provider == "anthropic":
        return AnthropicMessagesClient(settings)
    if settings.provider in {"openai-compatible", "openai"}:
        return OpenAICompatibleClient(settings)
    raise ValueError(f"不支持的 LLM_PROVIDER: {settings.provider!r}")
```

- [ ] **Step 4.4: 修改 `scripts/pipeline_utils.py` 保持旧调用兼容**

Replace `create_llm_client()` with an import wrapper:

```python
def create_llm_client(provider: str | None = None, model: str | None = None) -> Any:
    """创建通用 LLM 客户端。"""
    from scripts.llm_client import create_llm_client as _create

    return _create(provider=provider, model=model)
```

Replace the API call block inside `call_llm_with_retry()` with:

```python
            if hasattr(client, "complete"):
                return client.complete(messages, model=model, max_tokens=max_tokens)

            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
            return response.content[0].text
```

Update authentication error text:

```python
"API Key 无效或缺失，请检查 LLM_API_KEY；Anthropic 兼容模式也支持 ANTHROPIC_API_KEY"
```

- [ ] **Step 4.5: 运行 LLM 兼容测试**

Run: `python -m pytest tests/test_llm_client.py tests/test_jd_analyzer.py tests/test_llm_ranker.py -q`

Expected: PASS。

- [ ] **Step 4.6: Commit**

```bash
git add scripts/llm_client.py scripts/pipeline_utils.py tests/test_llm_client.py tests/test_jd_analyzer.py tests/test_llm_ranker.py
git commit -m "feat: 增加通用 LLM provider 抽象"
```

---

### Task 5: 让评分 pipeline 支持 provider/model 参数

**Files:**
- Modify: `scripts/score_pipeline.py`
- Modify: `scripts/jd_analyzer.py`
- Modify: `scripts/llm_ranker.py`
- Modify: `tests/test_score_pipeline.py`

- [ ] **Step 5.1: 写 CLI 参数测试**

Append to `tests/test_score_pipeline.py`:

```python
def test_run_pipeline_passes_provider_to_client(mocker):
    from scripts.score_pipeline import run_pipeline
    from scripts.jd_analyzer import JDAnalysis

    fake_client = mocker.MagicMock()
    create_client = mocker.patch("scripts.score_pipeline.create_llm_client", return_value=fake_client)
    mocker.patch("scripts.score_pipeline.load_or_analyze", return_value=JDAnalysis(
        core_skills=["AI"],
        supplement_skills=[],
        position_type="AI产品经理",
        experience_range=(3, 10),
        education_requirement="本科",
        industry_preference=[],
        exclusion_criteria=[],
        raw_jd="jd",
        jd_hash="hash",
    ))
    mocker.patch("scripts.score_pipeline.screen_candidates", return_value=[])

    result = run_pipeline(
        jd_id="jd-test",
        jd_text="jd",
        candidates=[],
        provider="openai-compatible",
        model="deepseek-chat",
    )

    create_client.assert_called_once_with(provider="openai-compatible", model="deepseek-chat")
    assert result["ranked"] == []
```

- [ ] **Step 5.2: 运行测试确认失败**

Run: `python -m pytest tests/test_score_pipeline.py -q`

Expected: FAIL，原因是 `run_pipeline()` 还没有 `provider` 参数。

- [ ] **Step 5.3: 修改默认模型读取**

In `scripts/score_pipeline.py`:

```python
import os
```

Replace:

```python
DEFAULT_MODEL = "intelligence"
```

With:

```python
DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "anthropic")
DEFAULT_MODEL = os.environ.get("LLM_MODEL", "intelligence")
```

- [ ] **Step 5.4: 修改 `run_pipeline()` 签名和 client 创建**

Change signature:

```python
def run_pipeline(
    jd_id: str,
    jd_text: str,
    candidates: list[dict],
    coarse_limit: int = DEFAULT_COARSE_LIMIT,
    final_top: int = DEFAULT_FINAL_TOP,
    batch_size: int = DEFAULT_BATCH_SIZE,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    cache_dir: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
```

Replace:

```python
client = create_llm_client()
```

With:

```python
client = create_llm_client(provider=provider, model=model)
```

- [ ] **Step 5.5: 给 run/resume CLI 添加 `--provider`**

For `run_parser` and `resume_parser`, add:

```python
run_parser.add_argument("--provider", default=DEFAULT_PROVIDER)
resume_parser.add_argument("--provider", default=DEFAULT_PROVIDER)
```

Pass `provider=args.provider` in `cmd_run()` and `cmd_resume()`.

- [ ] **Step 5.6: 更新 analyzer/ranker 默认模型**

In `scripts/jd_analyzer.py` and `scripts/llm_ranker.py`, add:

```python
import os

DEFAULT_MODEL = os.environ.get("LLM_MODEL", "intelligence")
```

Replace function defaults `model: str = "intelligence"` with `model: str = DEFAULT_MODEL`.

- [ ] **Step 5.7: 运行 pipeline 测试**

Run: `python -m pytest tests/test_score_pipeline.py tests/test_jd_analyzer.py tests/test_llm_ranker.py -q`

Expected: PASS。

- [ ] **Step 5.8: Commit**

```bash
git add scripts/score_pipeline.py scripts/jd_analyzer.py scripts/llm_ranker.py tests/test_score_pipeline.py
git commit -m "feat: 评分 pipeline 支持可配置 LLM provider"
```

---

### Task 6: 薄化 `.claude/skills` 为兼容 adapter

**Files:**
- Modify: `.claude/skills/public-search/SKILL.md`
- Modify: `.claude/skills/platform-match/SKILL.md`
- Modify: `.claude/skills/screen/SKILL.md`
- Modify: `.claude/skills/report/SKILL.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 6.1: 写 adapter 内容测试**

Extend `test_claude_skill_files_are_adapters_to_canonical_workflows()` in `tests/test_agent_architecture.py`:

```python
        assert "## Adapter Steps" in text
        assert "agents/capabilities.md" in text
        assert "运行时私有入口" in text
```

- [ ] **Step 6.2: 运行 adapter 测试确认失败**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: FAIL，原因是旧 `SKILL.md` 仍是完整 Claude 工作流。

- [ ] **Step 6.3: 改写每个 `.claude/skills/*/SKILL.md`**

For `public-search`, use:

```markdown
---
name: public-search
description: 公域搜索候选人——根据JD或搜索策略，在公开渠道搜索候选人信息，支持策略归因、多轮迭代和经验沉淀
---

# Claude Code Adapter: public-search

这是运行时私有入口。Canonical workflow 位于 `agents/workflows/public-search/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/workflows/public-search/AGENT.md`。
3. 将 canonical workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `web.search` -> WebSearch 或可用搜索 MCP
   - `web.fetch` -> 可用网页读取 MCP
   - `human.confirm` -> 直接询问用户
4. 严格按 canonical workflow 执行；本文件不保存业务流程。
```

For `platform-match`, use the same structure with:

```markdown
Canonical workflow 位于 `agents/workflows/platform-match/AGENT.md`。
```

For `screen`, use:

```markdown
Canonical workflow 位于 `agents/workflows/screen/AGENT.md`。
```

For `report`, use:

```markdown
Canonical workflow 位于 `agents/workflows/report/AGENT.md`。
```

- [ ] **Step 6.4: 运行 adapter 测试**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: PASS。

- [ ] **Step 6.5: Commit**

```bash
git add .claude/skills tests/test_agent_architecture.py
git commit -m "refactor: 将 Claude skills 薄化为运行时 adapter"
```

---

### Task 7: 迁移 public-search token tracker

**Files:**
- Create: `scripts/public_search/__init__.py`
- Move: `.claude/skills/public-search/scripts/token-tracker.py` -> `scripts/public_search/token_tracker.py`
- Modify: `agents/workflows/public-search/AGENT.md`
- Modify: `.gitignore`
- Create: `tests/test_public_search_token_tracker.py`

- [ ] **Step 7.1: 写导入测试**

Create `tests/test_public_search_token_tracker.py`:

```python
from scripts.public_search import token_tracker


def test_token_tracker_exposes_main():
    assert callable(token_tracker.main)
```

- [ ] **Step 7.2: 运行测试确认失败**

Run: `python -m pytest tests/test_public_search_token_tracker.py -q`

Expected: FAIL，原因是 `scripts.public_search` 不存在。

- [ ] **Step 7.3: 迁移 token tracker**

```powershell
New-Item -ItemType Directory -Force scripts\public_search
Move-Item -LiteralPath .claude\skills\public-search\scripts\token-tracker.py -Destination scripts\public_search\token_tracker.py
```

Create `scripts/public_search/__init__.py`:

```python
"""公域搜索辅助脚本包。"""
```

- [ ] **Step 7.4: 更新 token tracker 文档路径**

In `agents/workflows/public-search/AGENT.md`, replace all:

```text
python .claude/skills/public-search/scripts/token-tracker.py
```

with:

```text
python -m scripts.public_search.token_tracker
```

Replace:

```text
.claude/skills/public-search/scripts/token-tracker.py
```

with:

```text
scripts/public_search/token_tracker.py
```

- [ ] **Step 7.5: 更新 `.gitignore`**

Keep `data/token-tracker/*.jsonl` ignored. No `.claude/skills/public-search/scripts` ignore rule should be needed.

- [ ] **Step 7.6: 运行 token tracker 测试**

Run: `python -m pytest tests/test_public_search_token_tracker.py tests/test_agent_architecture.py -q`

Expected: PASS。

- [ ] **Step 7.7: Commit**

```bash
git add scripts/public_search agents/workflows/public-search/AGENT.md .claude/skills/public-search .gitignore tests/test_public_search_token_tracker.py
git commit -m "refactor: 迁移 public-search token tracker 到通用脚本包"
```

---

### Task 8: 更新 README、环境变量和依赖说明

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Modify: `requirements.txt`

- [ ] **Step 8.1: 写 README/env smoke 测试**

Append to `tests/test_agent_architecture.py`:

```python
def test_readme_describes_runtime_neutral_architecture():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "运行时中立" in text
    assert "agents/workflows/" in text
    assert ".claude/skills/ — Claude Code 兼容适配器" in text


def test_env_example_uses_generic_llm_settings():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "LLM_PROVIDER=" in text
    assert "LLM_MODEL=" in text
    assert "LLM_API_KEY=" in text
    assert "ANTHROPIC_API_KEY" in text
```

- [ ] **Step 8.2: 运行文档测试确认失败**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: FAIL，原因是 README/env 仍是 Claude 专用文案。

- [ ] **Step 8.3: 更新 `.env.example`**

Replace current content with:

```env
# 通用 LLM API 配置
LLM_PROVIDER=anthropic
LLM_MODEL=intelligence
LLM_API_KEY=sk-xxx
LLM_BASE_URL=

# Anthropic 兼容保留；未设置 LLM_API_KEY 时会读取此变量
ANTHROPIC_API_KEY=sk-ant-xxx
ANTHROPIC_BASE_URL=

# Pipeline 默认参数
PIPELINE_COARSE_LIMIT=50
PIPELINE_FINAL_TOP=10
PIPELINE_BATCH_SIZE=10
```

- [ ] **Step 8.4: 更新 `README.md` 目录结构和快速开始**

Replace `README.md` 的「目录结构」段落 with:

```markdown
## 目录结构

- agents/workflows/ — 运行时中立的 agent 工作流定义
- agents/capabilities.md — 通用能力契约和运行时工具映射
- .claude/skills/ — Claude Code 兼容适配器
- scripts/ — 可执行 Python 代码和 CLI
- rules/ — 评分、公司别名、平台匹配规则
- data/ — 运行时数据存储（JD、候选人、筛选结果、报告）
- schemas/ — 数据校验 Schema
```

Replace `README.md` 的「快速开始」段落 with:

```markdown
## 快速开始

1. 复制 `.env.example` 为 `.env`，配置 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_API_KEY`
2. 创建 JD: `python scripts/data-manager.py jd create jd.json`
3. 使用任意支持本仓库工作流的 agent 读取 `agents/workflows/`
4. Claude Code 用户可继续使用 `/public-search`、`/platform-match`、`/screen`、`/report`
5. 评分 pipeline: `python scripts/score_pipeline.py run --jd-id <id> --source boss --search-keyword <keyword>`
```

Add a short architecture paragraph under product positioning:

```markdown
项目已改造为运行时中立架构：业务工作流沉淀在 `agents/workflows/`，具体 agent 运行时只作为 adapter。Claude Code 仍受支持，但不再是唯一入口。
```

- [ ] **Step 8.5: 更新 `requirements.txt` 注释**

Keep existing dependencies. Do not remove `anthropic` in this phase because Anthropic remains a supported provider. No new runtime dependency is required for OpenAI-compatible HTTP calls.

- [ ] **Step 8.6: 运行文档测试**

Run: `python -m pytest tests/test_agent_architecture.py -q`

Expected: PASS。

- [ ] **Step 8.7: Commit**

```bash
git add README.md .env.example requirements.txt tests/test_agent_architecture.py
git commit -m "docs: 更新通用 agent 架构入口文档"
```

---

### Task 9: 全量验证与架构扫描

**Files:**
- Modify: `tasks/todo.md`

- [ ] **Step 9.1: 运行全量测试**

Run: `python -m pytest tests scripts -q`

Expected: PASS。

- [ ] **Step 9.2: 扫描业务代码中的 Claude 私有路径**

Run: `rg -n "\.claude" scripts agents/workflows rules README.md`

Expected: only `README.md` may mention `.claude/skills/ — Claude Code 兼容适配器`。`scripts`、`agents/workflows`、`rules` 无输出。

- [ ] **Step 9.3: 扫描 canonical workflow 中的运行时私有工具名**

Run: `rg -n "Claude Code|WebSearch|mcp__|Read|Write|Bash" agents/workflows`

Expected: no output。

- [ ] **Step 9.4: 扫描 LLM 专用默认值**

Run: `rg -n "ANTHROPIC_API_KEY|ANTHROPIC_BASE_URL|claude-sonnet-4-6|anthropic|intelligence" scripts tests README.md .env.example requirements.txt`

Expected allowed hits:

```text
scripts/llm_client.py          # Anthropic provider 兼容代码
tests/test_llm_client.py       # 兼容测试
.env.example                   # 兼容环境变量示例
requirements.txt               # Anthropic SDK 仍是支持 provider
```

Any hit in `scripts/pipeline_utils.py`, `scripts/score_pipeline.py`, `scripts/jd_analyzer.py`, `scripts/llm_ranker.py` must be reviewed. `intelligence` as project default is acceptable only if paired with `LLM_MODEL` override in the same file after Task 5.

- [ ] **Step 9.5: 运行一个无网络 smoke**

Run: `python scripts/score_pipeline.py --help`

Expected: help text includes `--provider` and `--model` for `run` and `resume` commands.

- [ ] **Step 9.6: 更新 `tasks/todo.md` Review**

Append results:

```markdown
## Review

- 全量测试：`python -m pytest tests scripts -q`，结果 `<填入实际结果>`。
- 架构扫描：`rg -n "\.claude" scripts agents/workflows rules README.md`，结果 `<填入实际结果>`。
- Canonical workflow 私有工具扫描：`rg -n "Claude Code|WebSearch|mcp__|Read|Write|Bash" agents/workflows`，结果 `<填入实际结果>`。
- CLI smoke：`python scripts/score_pipeline.py --help`，结果 `<填入实际结果>`。
```

- [ ] **Step 9.7: Commit**

```bash
git add tasks/todo.md
git commit -m "chore: 记录通用 agent 架构验证结果"
```

---

## 自检

**Spec coverage:** 覆盖了 Claude Code 目录耦合、Anthropic 客户端耦合、Claude 默认模型、Skill 主工作流耦合、规则路径耦合、测试导入耦合、README/env 入口耦合。

**Placeholder scan:** 未发现占位式待补内容；所有任务都有明确文件、命令、预期结果和关键代码片段。

**Type consistency:** 新增 `scripts.llm_client.create_llm_client(provider, model)` 与 `scripts.pipeline_utils.create_llm_client(provider, model)` 签名一致；`call_llm_with_retry(client, model, messages, max_tokens, ...)` 对新旧 client 都兼容；`run_pipeline(provider, model, ...)` 将 provider/model 传给 client 创建和后续分析/精排。

## 执行建议

优先选择 `superpowers:subagent-driven-development`。Task 1、2、4 可并行探索，但落地时建议按顺序合并：先规范层，再代码迁移，再路径统一，再 LLM provider，再 adapter 薄化和文档验证。
