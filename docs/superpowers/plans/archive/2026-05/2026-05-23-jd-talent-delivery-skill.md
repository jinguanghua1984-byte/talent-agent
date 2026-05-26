# JD Talent Delivery Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repo-local skill and workflow that turns a JD into a local talent recommendation package and publishes the package to Feishu Wiki `JD需求交付`.

**Architecture:** Add `skills/jd-talent-delivery` as the business entry, `agents/workflows/jd-talent-delivery` as the runtime-neutral workflow, and focused scripts under `scripts/` for scorecard generation, talent matching, outreach export, and Feishu publish orchestration. Keep the main DB read-only; all execution artifacts live under `data/output/<jd-slug>-<date>/`.

**Tech Stack:** Python 3.11, pytest, SQLite via existing `TalentDB`, Markdown/JSON/CSV artifacts, `lark-cli` for Feishu Docs/Sheets/Wiki.

---

## File Structure

- Create: `skills/jd-talent-delivery/SKILL.md`
  - Business-facing trigger and contract. It names the workflow, default output root, top_n default, scorecard consistency rule, and Feishu publish boundary.
- Create: `agents/workflows/jd-talent-delivery/AGENT.md`
  - Runtime-neutral orchestration. It defines stages, stop conditions, safety rules, and required artifacts.
- Modify: `tests/test_agent_architecture.py`
  - Add the new workflow to the runtime-neutral workflow list.
- Create: `scripts/jd_talent_delivery_profile.py`
  - Builds `role-profile.json` and `role-deep-dive.md` in the approved deep-dive section shape.
- Create: `scripts/jd_talent_delivery_scorecard.py`
  - Builds a deterministic `scorecard.json` from a role profile JSON or Markdown-derived profile dictionary.
- Create: `scripts/jd_talent_delivery_match.py`
  - Reads `data/talent.db` through `TalentDB`, applies the scorecard for coarse and detailed scoring, and writes recommendation JSON/Markdown plus outreach CSV/Markdown.
- Create: `scripts/jd_talent_delivery_feishu.py`
  - Builds safe publish manifests, executes Feishu preflight checks, runs import/move dry-runs, and then performs real publish.
- Create: `tests/test_jd_talent_delivery_skill.py`
  - Asserts skill text, semantic triggers, output contract, top_n default, and Feishu boundary.
- Create: `tests/test_jd_talent_delivery_workflow.py`
  - Asserts workflow text, runtime-neutral language, artifact list, and stop conditions.
- Create: `tests/test_jd_talent_delivery_profile.py`
  - Tests role profile extraction, deep-dive Markdown shape, and CLI output.
- Create: `tests/test_jd_talent_delivery_scorecard.py`
  - Tests scorecard schema and coarse/detailed dimension consistency.
- Create: `tests/test_jd_talent_delivery_match.py`
  - Tests read-only matching with a fake `TalentDB`.
- Create: `tests/test_jd_talent_delivery_feishu.py`
  - Tests safe manifest generation and the `drive +import`/`wiki +move` command shape.

---

### Task 1: Skill Contract

**Files:**
- Create: `skills/jd-talent-delivery/SKILL.md`
- Create: `tests/test_jd_talent_delivery_skill.py`

- [ ] **Step 1: Write the failing skill tests**

Create `tests/test_jd_talent_delivery_skill.py`:

```python
from pathlib import Path


SKILL = Path("skills/jd-talent-delivery/SKILL.md")


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_frontmatter_and_semantic_triggers() -> None:
    text = _text()

    assert "name: jd-talent-delivery" in text
    assert "description: Use when" in text
    for token in [
        "按 JD 做人才库推荐",
        "基于这个 JD 生成岗位画像和 Top30 人才推荐",
        "把 JD 推荐结果推送到飞书 JD需求交付",
        "用本地人才库匹配这个岗位",
        "生成岗位画像、人才推荐报告和外联表",
    ]:
        assert token in text


def test_skill_declares_output_root_and_artifacts() -> None:
    text = _text()

    for token in [
        "data/output/<jd-slug>-<YYYY-MM-DD>/",
        "source/jd.md",
        "profile/role-deep-dive.md",
        "profile/role-profile.json",
        "scoring/scorecard.json",
        "scoring/coarse-screen.json",
        "scoring/detailed-rank.json",
        "reports/talent-recommendation.md",
        "reports/outreach-queue.csv",
        "feishu/publish-manifest.json",
    ]:
        assert token in text


def test_skill_declares_defaults_and_handoff() -> None:
    text = _text()

    for token in [
        "top_n=30",
        "publish_feishu=true",
        "wiki_space_id=7642607697183001542",
        "agents/workflows/jd-talent-delivery/AGENT.md",
        "hr-talent",
        "docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md",
    ]:
        assert token in text


def test_skill_requires_scorecard_consistency_and_read_only_db() -> None:
    text = _text()

    for token in [
        "粗筛和精排必须引用同一个 `scorecard.json`",
        "data/talent.db 默认只读",
        "不写 `match_scores`",
        "不发起新的脉脉搜索",
        "不上传 SQLite DB、sync zip、raw search、raw detail、raw capture",
    ]:
        assert token in text


def test_skill_feishu_publish_boundary() -> None:
    text = _text()

    for token in [
        "默认真实发布",
        "lark-cli doctor",
        "lark-cli auth status",
        "drive +import --type docx",
        "drive +import --type sheet",
        "wiki +move",
        "不依赖 `sheets +append --file`",
    ]:
        assert token in text
```

- [ ] **Step 2: Run the skill tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_skill.py -q
```

Expected: FAIL with `FileNotFoundError` for `skills/jd-talent-delivery/SKILL.md`.

- [ ] **Step 3: Create the minimal skill document**

Create `skills/jd-talent-delivery/SKILL.md`:

```markdown
---
name: jd-talent-delivery
description: Use when the user asks to turn a JD into a local talent-library recommendation package, generate a role profile, produce TopN candidate recommendations and outreach queue, or publish the result to Feishu Wiki JD需求交付.
---

# jd-talent-delivery

## 目标

把一个 JD 从业务输入推进到本地人才库推荐和飞书知识库交付。Skill 负责识别入口、固定默认值、说明产物合同和交接到 canonical workflow；真实执行由 `agents/workflows/jd-talent-delivery/AGENT.md` 编排。

## 场景语义调用

用户没有显式写出 skill 名称时，只要语义是在“根据 JD 做本地人才库推荐并交付飞书”，也应使用本 Skill。典型触发包括：

- `按 JD 做人才库推荐`
- `基于这个 JD 生成岗位画像和 Top30 人才推荐`
- `把 JD 推荐结果推送到飞书 JD需求交付`
- `用本地人才库匹配这个岗位`
- `生成岗位画像、人才推荐报告和外联表`

## 默认参数

- `top_n=30`
- `publish_feishu=true`
- `wiki_space_id=7642607697183001542`
- 输出目录：`data/output/<jd-slug>-<YYYY-MM-DD>/`

## 输出产物

每次执行前创建独立输出目录，并写入以下产物：

- `source/jd.md`
- `profile/role-deep-dive.md`
- `profile/role-profile.json`
- `scoring/scorecard.json`
- `scoring/coarse-screen.json`
- `scoring/detailed-rank.json`
- `reports/talent-recommendation.md`
- `reports/talent-recommendation.json`
- `reports/outreach-queue.csv`
- `reports/outreach-queue.md`
- `feishu/publish-manifest.json`
- `feishu/dry-run-results.json`
- `feishu/publish-results.json`

## 岗位画像

岗位画像必须复用 `hr-talent` 的岗位分析框架，结构参考 `docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md`。画像至少包含结论摘要、岗位真实问题、能力模型、候选人类型、寻访关键点、公司池、关键词、排除项和风险项。

## 评分一致性

粗筛和精排必须引用同一个 `scorecard.json`。粗筛只做召回、硬过滤、风险预标记和粗分；精排不得重新解释 JD，只能使用岗位画像和评分卡。报告必须展示评分维度、权重、推荐阈值、TopN 证据和风险。

## 安全边界

- `data/talent.db 默认只读`。
- 不写 `match_scores`，除非用户未来单独明确授权。
- 不发起新的脉脉搜索。
- 不上传 SQLite DB、sync zip、raw search、raw detail、raw capture 或平台原始 payload。

## 飞书发布

默认真实发布到飞书知识库 `JD需求交付`。发布前必须先执行 `lark-cli doctor`、`lark-cli auth status`、Wiki 目录 dry-run 和导入 dry-run。Markdown 发布优先使用 `drive +import --type docx` 后 `wiki +move`；CSV 发布优先使用 `drive +import --type sheet` 后 `wiki +move`。当前流程不依赖 `sheets +append --file`。

## 自动交接

确认输入和默认值后，读取并执行 `agents/workflows/jd-talent-delivery/AGENT.md`。不要把真实执行逻辑写在 Skill 中。
```

- [ ] **Step 4: Run the skill tests and verify pass**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_skill.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add skills/jd-talent-delivery/SKILL.md tests/test_jd_talent_delivery_skill.py
git commit -m "Add JD talent delivery skill contract"
```

---

### Task 2: Canonical Workflow

**Files:**
- Create: `agents/workflows/jd-talent-delivery/AGENT.md`
- Create: `tests/test_jd_talent_delivery_workflow.py`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Inspect architecture test workflow list**

Run:

```powershell
Get-Content -Encoding UTF8 tests/test_agent_architecture.py -TotalCount 160
```

Expected: identify the `WORKFLOWS` list or equivalent workflow path collection.

- [ ] **Step 2: Write the failing workflow tests**

Create `tests/test_jd_talent_delivery_workflow.py`:

```python
from pathlib import Path


WORKFLOW = Path("agents/workflows/jd-talent-delivery/AGENT.md")


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_declares_runtime_neutral_entry_and_resources() -> None:
    text = _text()

    for token in [
        "jd-talent-delivery 工作流",
        "agents/capabilities.md",
        "agents/workflows/talent-library/AGENT.md",
        "agents/workflows/talent-library/references/data-contract.md",
        "agents/workflows/talent-library/references/safety-rules.md",
        "lark-cli",
        "JD需求交付",
    ]:
        assert token in text


def test_workflow_declares_stage_artifacts() -> None:
    text = _text()

    for token in [
        "S0：前置检查",
        "S1：建立输出目录",
        "S2：岗位画像",
        "S3：评分卡",
        "S4：人才库粗筛",
        "S5：人才库精排",
        "S6：报告和外联表",
        "S7：飞书发布",
        "data/output/<jd-slug>-<YYYY-MM-DD>/",
    ]:
        assert token in text


def test_workflow_enforces_scorecard_consistency() -> None:
    text = _text()

    for token in [
        "粗筛和精排必须读取同一个 `scoring/scorecard.json`",
        "粗筛不得新增精排不存在的评分维度",
        "精排不得重新解释 JD",
        "维度、权重、阈值必须写入报告",
    ]:
        assert token in text


def test_workflow_enforces_safety_and_stop_conditions() -> None:
    text = _text()

    for token in [
        "`data/talent.db` 只读",
        "不写 `match_scores`",
        "不上传 SQLite DB",
        "不上传 sync zip",
        "不上传 raw search",
        "不上传 raw detail",
        "不自动追加 `--yes`",
        "认证失败",
        "权限不足",
        "scope 缺失",
        "dry-run 失败",
    ]:
        assert token in text
```

- [ ] **Step 3: Run the workflow test and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_workflow.py -q
```

Expected: FAIL with `FileNotFoundError` for `agents/workflows/jd-talent-delivery/AGENT.md`.

- [ ] **Step 4: Create the workflow document**

Create `agents/workflows/jd-talent-delivery/AGENT.md`:

```markdown
---
name: jd-talent-delivery
description: "JD 本地人才库推荐和飞书知识库交付。用于读取 JD、生成岗位画像、构建评分卡、匹配 data/talent.db、输出 TopN 推荐和外联表，并发布到飞书知识库 JD需求交付。"
---

# jd-talent-delivery 工作流

本 workflow 是运行时中立的 canonical workflow。运行时适配器必须先读取 `agents/capabilities.md`，再把通用能力映射到当前环境。

## 资源索引

| 资源 | 用途 |
| --- | --- |
| `agents/capabilities.md` | 运行时中立能力契约 |
| `agents/workflows/talent-library/AGENT.md` | 本地人才库管理入口 |
| `agents/workflows/talent-library/references/data-contract.md` | 人才库数据契约 |
| `agents/workflows/talent-library/references/safety-rules.md` | 人才库安全规则 |
| `skills/jd-talent-delivery/SKILL.md` | 业务入口和默认合同 |
| `data/talent.db` | 只读人才库 |
| `lark-cli` | 飞书 Docs、Sheets、Wiki 发布 |

目标飞书知识库为 `JD需求交付`，默认 `space_id=7642607697183001542`。

## 阶段

### S0：前置检查

1. 解析 JD 输入、`top_n`、`publish_feishu` 和 `wiki_space_id`。
2. 确认 `data/talent.db` 存在。
3. 读取 talent-library 数据契约和安全规则。
4. 如果 `publish_feishu=true`，执行 `lark-cli doctor` 和 `lark-cli auth status`。

### S1：建立输出目录

创建 `data/output/<jd-slug>-<YYYY-MM-DD>/`，并写入 `source/jd.md`。所有后续过程输出都必须在该目录下。

### S2：岗位画像

复用 `hr-talent` 的岗位分析框架生成：

- `profile/role-deep-dive.md`
- `profile/role-profile.json`

岗位画像结构参考 `docs/business-requirements/2026-05-21-llm-inference-role-deep-dive.md`。

### S3：评分卡

从岗位画像生成 `scoring/scorecard.json`。评分卡至少包含维度、权重、must-have、nice-to-have、公司池、标题别名、排除项、风险规则、证据字段和推荐阈值。

### S4：人才库粗筛

读取 `data/talent.db`，输出 `scoring/coarse-screen.json`。粗筛和精排必须读取同一个 `scoring/scorecard.json`。粗筛不得新增精排不存在的评分维度。

### S5：人才库精排

对粗筛候选池生成 `scoring/detailed-rank.json`。精排不得重新解释 JD，只能使用岗位画像和评分卡。维度、权重、阈值必须写入报告。

### S6：报告和外联表

生成：

- `reports/talent-recommendation.md`
- `reports/talent-recommendation.json`
- `reports/outreach-queue.csv`
- `reports/outreach-queue.md`

外联优先级使用 P0/P1/P2/P3，推荐标签使用 强推荐/推荐/观察/不推荐。

### S7：飞书发布

发布前必须完成 Wiki 目录 dry-run、Markdown 导入 dry-run 和 CSV 导入 dry-run。Markdown 用 `drive +import --type docx` 后 `wiki +move`；CSV 用 `drive +import --type sheet` 后 `wiki +move`。发布后回读 Wiki 子节点、Doc outline 和 Sheet 前几行。

## 安全边界

- `data/talent.db` 只读。
- 不写 `match_scores`。
- 不发起新的脉脉搜索、Boss 搜索或浏览器抓取。
- 不上传 SQLite DB。
- 不上传 sync zip。
- 不上传 raw search。
- 不上传 raw detail。
- 不上传 raw capture 或平台原始 payload。
- 遇到高风险写操作确认门禁时，不自动追加 `--yes`。

## 停机条件

遇到以下情况必须停止，并写入 `feishu/publish-manifest.json` 或对应阶段错误证据：

- 认证失败。
- 权限不足。
- scope 缺失。
- Wiki 目标不存在且不能创建。
- dry-run 失败。
- CLI flag 漂移。
- 推荐报告或外联表缺少必要字段。
- manifest 中出现 SQLite、zip、raw search、raw detail 或 raw capture 路径。
```

- [ ] **Step 5: Add workflow to architecture test list**

Open `tests/test_agent_architecture.py`. Add the workflow path to the existing workflow list. If the file contains a list named `WORKFLOWS`, add this item:

```python
"agents/workflows/jd-talent-delivery/AGENT.md",
```

If the file uses `Path(...)` entries, add:

```python
Path("agents/workflows/jd-talent-delivery/AGENT.md"),
```

- [ ] **Step 6: Run workflow and architecture tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_workflow.py tests/test_agent_architecture.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```powershell
git add agents/workflows/jd-talent-delivery/AGENT.md tests/test_jd_talent_delivery_workflow.py tests/test_agent_architecture.py
git commit -m "Add JD talent delivery workflow"
```

---

### Task 3: Role Profile Builder

**Files:**
- Create: `scripts/jd_talent_delivery_profile.py`
- Create: `tests/test_jd_talent_delivery_profile.py`

- [ ] **Step 1: Write failing profile tests**

Create `tests/test_jd_talent_delivery_profile.py`:

```python
import json
from pathlib import Path

from scripts.jd_talent_delivery_profile import build_role_profile, render_profile_markdown, main


def test_build_role_profile_extracts_core_terms() -> None:
    jd_text = """
    # 大模型推理系统工程师

    负责 vLLM、SGLang、KV Cache、Prefill/Decode、量化和线上 SLA。
    需要熟悉字节、MiniMax、DeepSeek 等大模型业务场景。
    排除纯 RAG 应用和销售背景。
    """

    profile = build_role_profile(jd_text, source_path="jd.md", role_id="llm-inference")

    assert profile["schema"] == "jd_talent_delivery_role_profile_v1"
    assert profile["target_role"] == "大模型推理系统工程师"
    assert "vLLM" in profile["must_have"]
    assert "SGLang" in profile["must_have"]
    assert "KV Cache" in profile["must_have"]
    assert "SLA" in profile["nice_to_have"]
    assert "字节" in profile["company_pools"]["目标公司"]
    assert "纯 RAG 应用" in profile["exclusion_terms"]


def test_render_profile_markdown_matches_deep_dive_shape() -> None:
    profile = build_role_profile(
        "# 数据平台负责人\n负责数据质量、标注平台和团队管理。",
        source_path="jd.md",
        role_id="data-platform-lead",
    )

    markdown = render_profile_markdown(profile)

    for heading in [
        "# 数据平台负责人岗位深挖报告",
        "## 1. 结论摘要",
        "## 2. 岗位真实问题",
        "## 3. 能力模型",
        "## 4. 候选人类型",
        "## 5. 寻访关键点",
        "## 6. 公司池与团队优先级",
        "## 7. 匹配关键词建议",
        "## 8. 排除项与风险",
    ]:
        assert heading in markdown


def test_cli_writes_profile_json_and_markdown(tmp_path: Path) -> None:
    jd = tmp_path / "jd.md"
    out_json = tmp_path / "profile" / "role-profile.json"
    out_md = tmp_path / "profile" / "role-deep-dive.md"
    jd.write_text("# 大模型推理系统工程师\n负责 vLLM 和 KV Cache。", encoding="utf-8")

    code = main([
        "--jd",
        str(jd),
        "--role-id",
        "llm-inference",
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ])

    assert code == 0
    data = json.loads(out_json.read_text(encoding="utf-8-sig"))
    assert data["role_id"] == "llm-inference"
    assert out_md.read_text(encoding="utf-8-sig").startswith("# 大模型推理系统工程师岗位深挖报告")
```

- [ ] **Step 2: Run profile tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_profile.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.jd_talent_delivery_profile`.

- [ ] **Step 3: Implement deterministic profile builder**

Create `scripts/jd_talent_delivery_profile.py`:

```python
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_role_profile_v1"
KNOWN_TERMS = [
    "vLLM",
    "SGLang",
    "TensorRT-LLM",
    "KV Cache",
    "Prefill",
    "Decode",
    "量化",
    "CUDA",
    "GPU",
    "SLA",
    "数据质量",
    "标注平台",
    "团队管理",
    "后训练",
    "数据策略",
]
KNOWN_COMPANIES = ["字节", "字节跳动", "MiniMax", "DeepSeek", "月之暗面", "百度", "阿里", "腾讯"]
KNOWN_EXCLUSIONS = ["纯 RAG 应用", "销售", "招聘", "纯前端", "运营"]


def _contains(text: str, term: str) -> bool:
    if term.isascii():
        return term.casefold() in text.casefold()
    return term in text


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = value.strip()
        if text and text not in result:
            result.append(text)
    return result


def _title_from_jd(jd_text: str, role_id: str) -> str:
    for line in jd_text.splitlines():
        text = line.strip().lstrip("#").strip()
        if text:
            return text
    return role_id


def build_role_profile(jd_text: str, source_path: str, role_id: str) -> dict[str, Any]:
    title = _title_from_jd(jd_text, role_id)
    matched_terms = [term for term in KNOWN_TERMS if _contains(jd_text, term)]
    must_have = _unique(matched_terms[:6])
    nice_to_have = _unique(matched_terms[6:] + [term for term in ["SLA", "量化", "团队管理"] if _contains(jd_text, term)])
    companies = _unique([company for company in KNOWN_COMPANIES if _contains(jd_text, company)])
    exclusions = _unique([term for term in KNOWN_EXCLUSIONS if _contains(jd_text, term)])
    title_aliases = _unique([title, title.replace("负责人", "Lead"), title.replace("工程师", "专家")])
    return {
        "schema": SCHEMA,
        "role_id": role_id,
        "source_path": source_path,
        "target_role": title,
        "summary": f"{title} 的核心判断来自 JD 原文和 hr-talent 岗位分析框架。",
        "real_problem": "需要从业务问题、能力模型、公司池、风险项和外联切入点判断候选人匹配度。",
        "must_have": must_have,
        "nice_to_have": nice_to_have,
        "company_pools": {"目标公司": companies},
        "title_aliases": title_aliases,
        "exclusion_terms": exclusions,
        "risk_rules": ["求职状态偏低", "证据不足需人工复核"],
        "search_keywords": _unique(must_have + nice_to_have + title_aliases),
    }


def render_profile_markdown(profile: dict[str, Any]) -> str:
    title = str(profile["target_role"])
    lines = [
        f"# {title}岗位深挖报告",
        "",
        f"> 输入文件：`{profile.get('source_path', '')}`",
        "> 范围：岗位画像、人才库匹配策略和外联切入点；不执行平台搜索，不写数据库。",
        "",
        "## 1. 结论摘要",
        "",
        str(profile.get("summary", "")),
        "",
        "## 2. 岗位真实问题",
        "",
        str(profile.get("real_problem", "")),
        "",
        "## 3. 能力模型",
        "",
        "- 必须具备：" + "、".join(profile.get("must_have", [])),
        "- 加分能力：" + "、".join(profile.get("nice_to_have", [])),
        "",
        "## 4. 候选人类型",
        "",
        "- A 类：核心能力和岗位标题双命中。",
        "- B 类：核心能力命中但业务场景需复核。",
        "- C 类：有潜力但证据不足。",
        "",
        "## 5. 寻访关键点",
        "",
        "- 从岗位标题追问到真实职责。",
        "- 从关键词命中追问到项目深度和业务指标。",
        "- 从公司背景追问到团队边界和个人贡献。",
        "",
        "## 6. 公司池与团队优先级",
        "",
        "- 目标公司：" + "、".join(profile.get("company_pools", {}).get("目标公司", [])),
        "",
        "## 7. 匹配关键词建议",
        "",
        "- " + "、".join(profile.get("search_keywords", [])),
        "",
        "## 8. 排除项与风险",
        "",
        "- 排除项：" + "、".join(profile.get("exclusion_terms", [])),
        "- 风险项：" + "、".join(profile.get("risk_rules", [])),
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build JD role profile artifacts")
    parser.add_argument("--jd", required=True)
    parser.add_argument("--role-id", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    jd_path = Path(args.jd)
    jd_text = jd_path.read_text(encoding="utf-8-sig")
    profile = build_role_profile(jd_text, source_path=str(jd_path), role_id=args.role_id)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    out_md.write_text(render_profile_markdown(profile), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run profile tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_profile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery_profile.py tests/test_jd_talent_delivery_profile.py
git commit -m "Add JD talent delivery profile builder"
```

---

### Task 4: Scorecard Builder

**Files:**
- Create: `scripts/jd_talent_delivery_scorecard.py`
- Create: `tests/test_jd_talent_delivery_scorecard.py`

- [ ] **Step 1: Write failing scorecard tests**

Create `tests/test_jd_talent_delivery_scorecard.py`:

```python
import json
from pathlib import Path

from scripts.jd_talent_delivery_scorecard import (
    DEFAULT_LABEL_THRESHOLDS,
    build_scorecard,
    validate_scorecard,
)


def _profile() -> dict:
    return {
        "target_role": "大模型推理系统工程师",
        "must_have": ["vLLM", "SGLang", "KV Cache", "Prefill", "Decode"],
        "nice_to_have": ["TensorRT-LLM", "CUDA Graph", "量化", "SLA"],
        "company_pools": {
            "基模公司": ["MiniMax", "月之暗面", "DeepSeek"],
            "大厂AI平台": ["字节跳动", "百度", "阿里云"],
        },
        "title_aliases": ["推理框架工程师", "模型服务工程师", "AI Infra"],
        "exclusion_terms": ["纯前端", "销售", "招聘"],
        "risk_rules": ["求职状态偏低", "只有应用层 RAG 经验"],
    }


def test_build_scorecard_has_required_schema() -> None:
    scorecard = build_scorecard(_profile(), role_id="llm-inference", version="v1")

    assert scorecard["schema"] == "jd_talent_delivery_scorecard_v1"
    assert scorecard["role_id"] == "llm-inference"
    assert scorecard["version"] == "v1"
    assert scorecard["label_thresholds"] == DEFAULT_LABEL_THRESHOLDS
    assert [item["id"] for item in scorecard["dimensions"]] == [
        "company_context",
        "title_focus",
        "must_have",
        "nice_to_have",
        "seniority",
        "education",
        "risk",
    ]
    assert sum(item["weight"] for item in scorecard["dimensions"]) == 100


def test_validate_scorecard_rejects_missing_dimension_weight() -> None:
    scorecard = build_scorecard(_profile(), role_id="demo", version="v1")
    scorecard["dimensions"][0].pop("weight")

    try:
        validate_scorecard(scorecard)
    except ValueError as exc:
        assert "dimension missing weight" in str(exc)
    else:
        raise AssertionError("validate_scorecard should fail")


def test_cli_writes_scorecard_json(tmp_path: Path) -> None:
    profile_path = tmp_path / "role-profile.json"
    out_path = tmp_path / "scorecard.json"
    profile_path.write_text(json.dumps(_profile(), ensure_ascii=False), encoding="utf-8")

    from scripts.jd_talent_delivery_scorecard import main

    code = main([
        "--profile-json",
        str(profile_path),
        "--role-id",
        "llm-inference",
        "--version",
        "v1",
        "--out",
        str(out_path),
    ])

    assert code == 0
    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["role_id"] == "llm-inference"
    assert data["terms"]["must_have"] == ["vLLM", "SGLang", "KV Cache", "Prefill", "Decode"]
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_scorecard.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.jd_talent_delivery_scorecard'`.

- [ ] **Step 3: Implement scorecard builder**

Create `scripts/jd_talent_delivery_scorecard.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_scorecard_v1"
DEFAULT_LABEL_THRESHOLDS = {
    "strong_recommend": 82,
    "recommend": 72,
    "observe": 60,
}


DEFAULT_DIMENSIONS = [
    {"id": "company_context", "label": "公司与业务上下文", "weight": 16},
    {"id": "title_focus", "label": "岗位方向", "weight": 16},
    {"id": "must_have", "label": "核心能力", "weight": 28},
    {"id": "nice_to_have", "label": "加分能力", "weight": 14},
    {"id": "seniority", "label": "资历匹配", "weight": 10},
    {"id": "education", "label": "教育背景", "weight": 8},
    {"id": "risk", "label": "风险扣分", "weight": 8},
]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _company_pools(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, items in value.items():
        values = _strings(items)
        if values:
            result[str(key)] = values
    return result


def build_scorecard(profile: dict[str, Any], role_id: str, version: str) -> dict[str, Any]:
    scorecard = {
        "schema": SCHEMA,
        "role_id": role_id,
        "version": version,
        "target_role": str(profile.get("target_role") or role_id),
        "dimensions": [dict(item) for item in DEFAULT_DIMENSIONS],
        "terms": {
            "must_have": _strings(profile.get("must_have")),
            "nice_to_have": _strings(profile.get("nice_to_have")),
            "title_aliases": _strings(profile.get("title_aliases")),
            "exclusion_terms": _strings(profile.get("exclusion_terms")),
            "risk_rules": _strings(profile.get("risk_rules")),
        },
        "company_pools": _company_pools(profile.get("company_pools")),
        "evidence_fields": [
            "current_company",
            "current_title",
            "skill_tags",
            "work_experience",
            "education_experience",
            "project_experience",
            "hunting_status",
        ],
        "label_thresholds": dict(DEFAULT_LABEL_THRESHOLDS),
    }
    validate_scorecard(scorecard)
    return scorecard


def validate_scorecard(scorecard: dict[str, Any]) -> None:
    if scorecard.get("schema") != SCHEMA:
        raise ValueError("invalid scorecard schema")
    dimensions = scorecard.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise ValueError("scorecard dimensions must be a non-empty list")
    for dimension in dimensions:
        if "id" not in dimension:
            raise ValueError("dimension missing id")
        if "weight" not in dimension:
            raise ValueError("dimension missing weight")
    total_weight = sum(int(item["weight"]) for item in dimensions)
    if total_weight != 100:
        raise ValueError(f"dimension weights must sum to 100, got {total_weight}")
    thresholds = scorecard.get("label_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("label_thresholds must be an object")


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("profile JSON must be an object")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build JD talent delivery scorecard")
    parser.add_argument("--profile-json", required=True)
    parser.add_argument("--role-id", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    profile = _load_json(args.profile_json)
    scorecard = build_scorecard(profile, role_id=args.role_id, version=args.version)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run scorecard tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_scorecard.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery_scorecard.py tests/test_jd_talent_delivery_scorecard.py
git commit -m "Add JD talent delivery scorecard builder"
```

---

### Task 5: Talent Matching and Reports

**Files:**
- Create: `scripts/jd_talent_delivery_match.py`
- Create: `tests/test_jd_talent_delivery_match.py`

- [ ] **Step 1: Write failing match tests**

Create `tests/test_jd_talent_delivery_match.py`:

```python
import csv
import json
from pathlib import Path

from scripts import jd_talent_delivery_match as match
from scripts.talent_models import Candidate, CandidateDetail, PageResult


def _scorecard() -> dict:
    return {
        "schema": "jd_talent_delivery_scorecard_v1",
        "role_id": "demo",
        "version": "v1",
        "target_role": "大模型推理系统工程师",
        "dimensions": [
            {"id": "company_context", "label": "公司与业务上下文", "weight": 16},
            {"id": "title_focus", "label": "岗位方向", "weight": 16},
            {"id": "must_have", "label": "核心能力", "weight": 28},
            {"id": "nice_to_have", "label": "加分能力", "weight": 14},
            {"id": "seniority", "label": "资历匹配", "weight": 10},
            {"id": "education", "label": "教育背景", "weight": 8},
            {"id": "risk", "label": "风险扣分", "weight": 8},
        ],
        "terms": {
            "must_have": ["vLLM", "KV Cache", "Prefill", "Decode"],
            "nice_to_have": ["SGLang", "CUDA Graph", "量化"],
            "title_aliases": ["推理框架工程师", "模型服务工程师"],
            "exclusion_terms": ["销售"],
            "risk_rules": ["求职状态偏低"],
        },
        "company_pools": {"目标公司": ["字节跳动", "MiniMax"]},
        "label_thresholds": {"strong_recommend": 82, "recommend": 72, "observe": 60},
    }


def _candidate() -> Candidate:
    return Candidate(
        id=101,
        name="候选人A",
        current_company="字节跳动",
        current_title="推理框架工程师",
        education="上海交通大学 硕士",
        work_years=5,
        skill_tags=("vLLM", "KV Cache"),
        hunting_status="在职观望",
    )


class FakeTalentDB:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def search(self, **kwargs) -> PageResult:
        return PageResult(items=[_candidate()], total=1, page=1, page_size=1)

    def get_detail(self, candidate_id: int) -> CandidateDetail:
        return CandidateDetail(
            candidate_id=candidate_id,
            work_experience=[
                {
                    "company": "字节跳动",
                    "title": "推理框架工程师",
                    "description": "负责 vLLM KV Cache Prefill Decode SGLang 量化和 CUDA Graph 优化。",
                }
            ],
            education_experience=[{"school": "上海交通大学", "description": "硕士"}],
        )

    def get_sources(self, candidate_id: int) -> list:
        return [
            type(
                "Source",
                (),
                {
                    "platform": "maimai",
                    "platform_id": "p101",
                    "profile_url": "https://maimai.cn/profile/detail?dstu=p101",
                    "fetched_at": "2026-05-23",
                },
            )()
        ]

    def save_match_score(self, *args, **kwargs) -> None:
        raise AssertionError("matching must be read-only")

    def close(self) -> None:
        pass


def test_run_match_outputs_reports_and_outreach(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(match, "TalentDB", FakeTalentDB)
    scorecard_path = tmp_path / "scorecard.json"
    scorecard_path.write_text(json.dumps(_scorecard(), ensure_ascii=False), encoding="utf-8")
    out_dir = tmp_path / "delivery"

    result = match.run_match(
        db_path=tmp_path / "talent.db",
        scorecard_path=scorecard_path,
        out_dir=out_dir,
        top_n=1,
        limit=10,
    )

    assert result["read_only"] is True
    assert result["summary"]["total_scored"] == 1
    assert result["top_n"] == 1
    assert (out_dir / "scoring" / "coarse-screen.json").exists()
    assert (out_dir / "scoring" / "detailed-rank.json").exists()
    assert (out_dir / "reports" / "talent-recommendation.md").exists()
    assert (out_dir / "reports" / "outreach-queue.csv").exists()

    with (out_dir / "reports" / "outreach-queue.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["candidate_id"] == "101"
    assert rows[0]["priority"] in {"P0", "P1"}
    assert rows[0]["profile_url"].startswith("https://maimai.cn/profile/detail")


def test_coarse_and_detailed_share_dimension_ids() -> None:
    scorecard = _scorecard()
    bundle = match.CandidateBundle(candidate=_candidate(), detail=None, sources=[])

    coarse = match.score_candidate(bundle, scorecard, mode="coarse")
    detailed = match.score_candidate(bundle, scorecard, mode="detailed")

    assert set(coarse["dimensions"]) == set(detailed["dimensions"])
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_match.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.jd_talent_delivery_match`.

- [ ] **Step 3: Implement matching script**

Create `scripts/jd_talent_delivery_match.py`:

```python
from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.talent_db import TalentDB
from scripts.talent_models import Candidate, CandidateDetail, SortSpec


CSV_FIELDS = [
    "priority",
    "rank",
    "candidate_id",
    "name",
    "platform_id",
    "company",
    "title",
    "city",
    "work_years",
    "score",
    "recommendation_label",
    "directions",
    "key_evidence",
    "risk_summary",
    "suggested_outreach_angle",
    "profile_url",
]


@dataclass(frozen=True)
class CandidateBundle:
    candidate: Candidate
    detail: CandidateDetail | None
    sources: list[Any]


def _load_json(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("JSON must be an object")
    return data


def _text_join(values: list[Any]) -> str:
    parts: list[str] = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            parts.append(_text_join(list(value.values())))
        elif isinstance(value, (list, tuple, set)):
            parts.append(_text_join(list(value)))
        else:
            parts.append(str(value))
    return " ".join(part for part in parts if part)


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    if term.isascii():
        return term.casefold() in text.casefold()
    return term in text


def _matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if _contains(text, term)]


def _dimension_ids(scorecard: dict[str, Any]) -> list[str]:
    return [str(item["id"]) for item in scorecard.get("dimensions", [])]


def _candidate_text(bundle: CandidateBundle, include_detail: bool) -> str:
    candidate = bundle.candidate
    detail = bundle.detail if include_detail else None
    return _text_join([
        candidate.name,
        candidate.current_company,
        candidate.current_title,
        candidate.education,
        list(candidate.skill_tags),
        detail.work_experience if detail else [],
        detail.education_experience if detail else [],
        detail.project_experience if detail else [],
        detail.summary if detail else "",
        detail.raw_data if detail else {},
    ])


def _company_terms(scorecard: dict[str, Any]) -> list[str]:
    terms: list[str] = []
    pools = scorecard.get("company_pools") if isinstance(scorecard.get("company_pools"), dict) else {}
    for values in pools.values():
        if isinstance(values, list):
            terms.extend(str(item) for item in values)
    return list(dict.fromkeys(term for term in terms if term))


def _source_url(bundle: CandidateBundle) -> str:
    for source in bundle.sources:
        url = getattr(source, "profile_url", "") or ""
        if url:
            return url
    return ""


def _platform_id(bundle: CandidateBundle) -> str:
    for source in bundle.sources:
        value = getattr(source, "platform_id", "") or ""
        if value:
            return str(value)
    return ""


def score_candidate(bundle: CandidateBundle, scorecard: dict[str, Any], mode: str) -> dict[str, Any]:
    if mode not in {"coarse", "detailed"}:
        raise ValueError("mode must be coarse or detailed")
    candidate = bundle.candidate
    text = _candidate_text(bundle, include_detail=mode == "detailed")
    terms = scorecard.get("terms") if isinstance(scorecard.get("terms"), dict) else {}
    company_hits = _matched_terms(_text_join([candidate.current_company, text]), _company_terms(scorecard))
    title_hits = _matched_terms(candidate.current_title or "", list(terms.get("title_aliases") or []))
    must_hits = _matched_terms(text, list(terms.get("must_have") or []))
    nice_hits = _matched_terms(text, list(terms.get("nice_to_have") or []))
    exclusion_hits = _matched_terms(text, list(terms.get("exclusion_terms") or []))

    dimensions = {dimension_id: 0 for dimension_id in _dimension_ids(scorecard)}
    dimensions["company_context"] = 16 if company_hits else 0
    dimensions["title_focus"] = 16 if title_hits else 0
    dimensions["must_have"] = min(28, len(must_hits) * 7)
    dimensions["nice_to_have"] = min(14, len(nice_hits) * 5)
    dimensions["seniority"] = 10 if candidate.work_years and 2 <= candidate.work_years <= 12 else 5
    dimensions["education"] = 8 if any(school in (candidate.education or "") for school in ["清华", "北京大学", "上海交通", "浙江大学", "复旦", "985", "211"]) else 4
    dimensions["risk"] = -8 if exclusion_hits else 0
    score = max(0, min(100, sum(dimensions.values())))

    thresholds = scorecard.get("label_thresholds") or {}
    if exclusion_hits:
        label = "不推荐"
    elif score >= int(thresholds.get("strong_recommend", 82)):
        label = "强推荐"
    elif score >= int(thresholds.get("recommend", 72)):
        label = "推荐"
    elif score >= int(thresholds.get("observe", 60)):
        label = "观察"
    else:
        label = "不推荐"

    risk_flags = []
    if exclusion_hits:
        risk_flags.append("exclusion_terms:" + ",".join(exclusion_hits))
    if candidate.hunting_status and "不看" in candidate.hunting_status:
        risk_flags.append("low_hunting_status")

    evidence_terms = company_hits + title_hits + must_hits + nice_hits
    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "score": score,
        "score_mode": mode,
        "recommendation_label": label,
        "current_company": candidate.current_company or "",
        "current_title": candidate.current_title or "",
        "city": candidate.city or "",
        "work_years": candidate.work_years,
        "education": candidate.education or "",
        "dimensions": dimensions,
        "matched_terms": evidence_terms,
        "risk_flags": risk_flags,
        "profile_url": _source_url(bundle),
        "platform_id": _platform_id(bundle),
    }


def _load_bundles(db_path: str | Path, limit: int) -> list[CandidateBundle]:
    db = TalentDB(db_path)
    try:
        page = db.search(sort=SortSpec(field="updated_at", direction="desc"), page=1, page_size=limit)
        return [
            CandidateBundle(candidate=item, detail=db.get_detail(item.id), sources=db.get_sources(item.id))
            for item in page.items
        ]
    finally:
        db.close()


def _sort_scores(scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    label_order = {"强推荐": 0, "推荐": 1, "观察": 2, "不推荐": 3}
    return sorted(scores, key=lambda item: (label_order.get(item["recommendation_label"], 9), -item["score"], item["candidate_id"]))


def _priority(item: dict[str, Any]) -> str:
    if item["recommendation_label"] == "强推荐" and not item["risk_flags"]:
        return "P0"
    if item["recommendation_label"] in {"强推荐", "推荐"}:
        return "P1"
    if item["recommendation_label"] == "观察":
        return "P2"
    return "P3"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _md_cell(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).replace("|", "/")


def _write_report(path: Path, ranked: list[dict[str, Any]], scorecard: dict[str, Any], top_n: int) -> None:
    lines = [
        f"# {scorecard.get('target_role', scorecard.get('role_id', 'JD'))} 人才库推荐报告",
        "",
        f"- 评分卡：{scorecard.get('role_id', '')} / {scorecard.get('version', '')}",
        f"- TopN：{top_n}",
        "- 执行边界：只读 `data/talent.db`，未写入 `match_scores`，未触发平台搜索。",
        "",
        "## 评分维度",
        "",
        "| 维度 | 权重 |",
        "| --- | ---: |",
    ]
    for dimension in scorecard.get("dimensions", []):
        lines.append(f"| {dimension.get('label', dimension.get('id', ''))} | {dimension.get('weight', '')} |")
    lines.extend([
        "",
        "## Top 推荐总览",
        "",
        "| 排名 | ID | 姓名 | 评分 | 推荐 | 公司 | 职位 | 证据 | 风险 |",
        "| ---: | ---: | --- | ---: | --- | --- | --- | --- | --- |",
    ])
    for rank, item in enumerate(ranked[:top_n], start=1):
        lines.append(
            f"| {rank} | {item['candidate_id']} | {_md_cell(item['name'])} | {item['score']} | "
            f"{item['recommendation_label']} | {_md_cell(item['current_company'])} | {_md_cell(item['current_title'])} | "
            f"{_md_cell('、'.join(item['matched_terms'][:8]))} | {_md_cell('、'.join(item['risk_flags']))} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")


def _write_outreach(path: Path, ranked: list[dict[str, Any]], top_n: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for rank, item in enumerate(ranked[:top_n], start=1):
            writer.writerow({
                "priority": _priority(item),
                "rank": rank,
                "candidate_id": item["candidate_id"],
                "name": item["name"],
                "platform_id": item.get("platform_id", ""),
                "company": item.get("current_company", ""),
                "title": item.get("current_title", ""),
                "city": item.get("city", ""),
                "work_years": item.get("work_years") or "",
                "score": item.get("score", ""),
                "recommendation_label": item.get("recommendation_label", ""),
                "directions": "、".join(item.get("matched_terms", [])[:4]),
                "key_evidence": "；".join(item.get("matched_terms", [])[:8]),
                "risk_summary": "；".join(item.get("risk_flags", [])) or "无明显硬风险",
                "suggested_outreach_angle": f"围绕 {item.get('current_company', '')} 的 {item.get('current_title', '')} 经历确认岗位匹配深度。",
                "profile_url": item.get("profile_url", ""),
            })


def run_match(db_path: str | Path, scorecard_path: str | Path, out_dir: str | Path, top_n: int, limit: int = 5000) -> dict[str, Any]:
    scorecard = _load_json(scorecard_path)
    root = Path(out_dir)
    bundles = _load_bundles(db_path, limit=limit)
    coarse = _sort_scores([score_candidate(bundle, scorecard, mode="coarse") for bundle in bundles])
    detailed_ids = {item["candidate_id"] for item in coarse if item["recommendation_label"] != "不推荐"}
    detailed = _sort_scores([
        score_candidate(bundle, scorecard, mode="detailed")
        for bundle in bundles
        if bundle.candidate.id in detailed_ids
    ])
    result = {
        "read_only": True,
        "top_n": top_n,
        "summary": {"total_scored": len(detailed), "coarse_total": len(coarse)},
        "ranked": detailed,
    }
    _write_json(root / "scoring" / "coarse-screen.json", {"scorecard": scorecard, "ranked": coarse})
    _write_json(root / "scoring" / "detailed-rank.json", result)
    _write_json(root / "reports" / "talent-recommendation.json", result)
    _write_report(root / "reports" / "talent-recommendation.md", detailed, scorecard, top_n=top_n)
    _write_outreach(root / "reports" / "outreach-queue.csv", detailed, top_n=top_n)
    (root / "reports" / "outreach-queue.md").write_text("# 外联队列\n\n详见 `outreach-queue.csv`。\n", encoding="utf-8-sig")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run JD talent delivery match")
    parser.add_argument("--db", required=True)
    parser.add_argument("--scorecard", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--top-n", type=int, default=30)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args(argv)
    run_match(args.db, args.scorecard, args.out_dir, args.top_n, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run match tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_match.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery_match.py tests/test_jd_talent_delivery_match.py
git commit -m "Add JD talent delivery matching reports"
```

---

### Task 6: Feishu Publish Manifest

**Files:**
- Create: `scripts/jd_talent_delivery_feishu.py`
- Create: `tests/test_jd_talent_delivery_feishu.py`

- [ ] **Step 1: Write failing Feishu tests**

Create `tests/test_jd_talent_delivery_feishu.py`:

```python
import json
from pathlib import Path

from scripts.jd_talent_delivery_feishu import build_publish_manifest


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig")


def test_manifest_uses_drive_import_and_wiki_move(tmp_path: Path) -> None:
    root = tmp_path / "demo-role-2026-05-23"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# 岗位画像\n")
    _write(root / "reports" / "talent-recommendation.md", "# 推荐报告\n")
    _write(root / "reports" / "outreach-queue.csv", "candidate_id,name\n1,A\n")

    manifest = build_publish_manifest(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        dry_run=True,
    )

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["schema"] == "jd_talent_delivery_feishu_manifest_v1"
    assert manifest["wiki_space_id"] == "7642607697183001542"
    assert "drive" in serialized
    assert "+import" in serialized
    assert "--type" in serialized
    assert "docx" in serialized
    assert "sheet" in serialized
    assert "wiki" in serialized
    assert "+move" in serialized
    assert "sheets +append --file" not in serialized


def test_manifest_rejects_sensitive_paths(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# 岗位画像\n")
    _write(root / "reports" / "talent-recommendation.md", "# 推荐报告\n")
    _write(root / "reports" / "outreach-queue.csv", "database\nraw/search/unit-1.json\n")

    try:
        build_publish_manifest(root, jd_title="Demo", wiki_space_id="7642607697183001542", dry_run=True)
    except ValueError as exc:
        assert "sensitive marker" in str(exc)
    else:
        raise AssertionError("manifest should reject sensitive CSV content")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_feishu.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.jd_talent_delivery_feishu`.

- [ ] **Step 3: Implement manifest builder**

Create `scripts/jd_talent_delivery_feishu.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


SCHEMA = "jd_talent_delivery_feishu_manifest_v1"
SENSITIVE_MARKERS = (
    "talent.db",
    ".db",
    ".sqlite",
    ".zip",
    "raw/search",
    "raw/detail",
    "raw capture",
    "raw_capture",
    "sync_bundle",
    "database",
)


def _assert_safe_text(value: str) -> None:
    lowered = value.lower().replace("\\", "/")
    for marker in SENSITIVE_MARKERS:
        if marker in lowered:
            raise ValueError(f"sensitive marker found: {marker}")


def _rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _required_files(root: Path) -> dict[str, Path]:
    return {
        "jd": root / "source" / "jd.md",
        "profile": root / "profile" / "role-deep-dive.md",
        "recommendation": root / "reports" / "talent-recommendation.md",
        "outreach": root / "reports" / "outreach-queue.csv",
    }


def _import_doc_command(path: Path, title: str, dry_run: bool) -> list[str]:
    command = ["lark-cli", "drive", "+import", "--as", "user", "--file", str(path), "--type", "docx", "--name", title]
    if dry_run:
        command.append("--dry-run")
    return command


def _import_sheet_command(path: Path, title: str, dry_run: bool) -> list[str]:
    command = ["lark-cli", "drive", "+import", "--as", "user", "--file", str(path), "--type", "sheet", "--name", title]
    if dry_run:
        command.append("--dry-run")
    return command


def _move_command(obj_type: str, obj_token_marker: str, wiki_space_id: str, parent_node_marker: str, dry_run: bool) -> list[str]:
    command = [
        "lark-cli",
        "wiki",
        "+move",
        "--as",
        "user",
        "--obj-type",
        obj_type,
        "--obj-token",
        obj_token_marker,
        "--target-space-id",
        wiki_space_id,
        "--target-parent-token",
        parent_node_marker,
    ]
    if dry_run:
        command.append("--dry-run")
    return command


def build_publish_manifest(output_root: str | Path, jd_title: str, wiki_space_id: str, dry_run: bool = True) -> dict[str, Any]:
    root = Path(output_root)
    files = _required_files(root)
    for path in files.values():
        if not path.exists():
            raise FileNotFoundError(path)
        _assert_safe_text(path.as_posix())
        _assert_safe_text(path.read_text(encoding="utf-8-sig"))

    commands = [
        ["lark-cli", "doctor"],
        ["lark-cli", "auth", "status"],
        ["lark-cli", "wiki", "+node-create", "--as", "user", "--space-id", wiki_space_id, "--title", jd_title, "--obj-type", "docx", "--dry-run"],
        _import_doc_command(files["jd"], f"{jd_title} JD需求", dry_run),
        _move_command("docx", "<jd_doc_token>", wiki_space_id, "<jd_parent_node_token>", dry_run),
        _import_doc_command(files["profile"], f"{jd_title} 岗位画像", dry_run),
        _move_command("docx", "<profile_doc_token>", wiki_space_id, "<jd_parent_node_token>", dry_run),
        _import_doc_command(files["recommendation"], f"{jd_title} 人才推荐报告", dry_run),
        _move_command("docx", "<recommendation_doc_token>", wiki_space_id, "<jd_parent_node_token>", dry_run),
        _import_sheet_command(files["outreach"], f"{jd_title} 外联表", dry_run),
        _move_command("sheet", "<outreach_sheet_token>", wiki_space_id, "<jd_parent_node_token>", dry_run),
    ]
    manifest = {
        "schema": SCHEMA,
        "output_root": str(root),
        "jd_title": jd_title,
        "wiki_space_id": wiki_space_id,
        "dry_run": dry_run,
        "source_files": {key: _rel(path, root) for key, path in files.items()},
        "commands": commands,
        "publish_ready": False,
        "notes": [
            "CSV uses drive +import --type sheet and wiki +move.",
            "Do not use sheets +append --file.",
        ],
    }
    _assert_safe_text(json.dumps(manifest, ensure_ascii=False))
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build JD talent delivery Feishu manifest")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--jd-title", required=True)
    parser.add_argument("--wiki-space-id", default="7642607697183001542")
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    manifest = build_publish_manifest(args.output_root, args.jd_title, args.wiki_space_id, dry_run=args.dry_run)
    out = Path(args.manifest_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run Feishu tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_feishu.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_feishu.py
git commit -m "Add JD talent delivery Feishu manifest"
```

---

### Task 7: Feishu Preflight and Publish Executor

**Files:**
- Modify: `scripts/jd_talent_delivery_feishu.py`
- Modify: `tests/test_jd_talent_delivery_feishu.py`

- [ ] **Step 1: Extend Feishu tests with a fake runner**

Append to `tests/test_jd_talent_delivery_feishu.py`:

```python
import subprocess

from scripts.jd_talent_delivery_feishu import publish_output


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
        self.calls.append(argv)
        joined = " ".join(argv)
        if argv == ["lark-cli", "doctor"]:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true}', "")
        if argv == ["lark-cli", "auth", "status"]:
            return subprocess.CompletedProcess(argv, 0, '{"tokenStatus":"valid"}', "")
        if "wiki +node-create" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +node-create" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"parent_node","obj_token":"parent_doc"}', "")
        if "drive +import" in joined and "--type docx" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "drive +import" in joined and "--type sheet" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "drive +import" in joined and "--type docx" in joined:
            token = "doc_" + str(len(self.calls))
            return subprocess.CompletedProcess(argv, 0, json.dumps({"obj_token": token}), "")
        if "drive +import" in joined and "--type sheet" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"obj_token":"sheet_token"}', "")
        if "wiki +move" in joined and "--dry-run" in argv:
            return subprocess.CompletedProcess(argv, 0, '{"ok":true,"dry_run":true}', "")
        if "wiki +move" in joined:
            return subprocess.CompletedProcess(argv, 0, '{"node_token":"moved_node","ready":true}', "")
        return subprocess.CompletedProcess(argv, 1, "", "unexpected command")


def _safe_output_root(tmp_path: Path) -> Path:
    root = tmp_path / "demo-role-2026-05-23"
    _write(root / "source" / "jd.md", "# JD\n")
    _write(root / "profile" / "role-deep-dive.md", "# 岗位画像\n")
    _write(root / "reports" / "talent-recommendation.md", "# 推荐报告\n")
    _write(root / "reports" / "outreach-queue.csv", "candidate_id,name\n1,A\n")
    return root


def test_publish_output_runs_preflight_dry_run_then_real_publish(tmp_path: Path) -> None:
    root = _safe_output_root(tmp_path)
    runner = FakeRunner()

    result = publish_output(
        output_root=root,
        jd_title="Demo Role",
        wiki_space_id="7642607697183001542",
        runner=runner,
    )

    assert result["status"] == "published"
    assert result["parent_node_token"] == "parent_node"
    assert (root / "feishu" / "publish-results.json").exists()
    calls = [" ".join(call) for call in runner.calls]
    assert calls[0] == "lark-cli doctor"
    assert calls[1] == "lark-cli auth status"
    assert any("wiki +node-create" in call and "--dry-run" in call for call in calls)
    assert any("drive +import" in call and "--dry-run" in call for call in calls)
    assert any("wiki +move" in call and "--target-parent-token parent_node" in call for call in calls)
```

- [ ] **Step 2: Run Feishu tests and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_feishu.py -q
```

Expected: FAIL because `publish_output` is not defined.

- [ ] **Step 3: Implement the publish executor**

Extend `scripts/jd_talent_delivery_feishu.py` with these imports:

```python
import subprocess
from collections.abc import Callable
```

Add these functions below `build_publish_manifest`:

```python
Runner = Callable[[list[str], str | None], subprocess.CompletedProcess]


def default_runner(argv: list[str], cwd: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, check=False)


def _run(argv: list[str], runner: Runner, cwd: str | None = None) -> dict[str, Any]:
    completed = runner(argv, cwd)
    result = {
        "argv": argv,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(argv)}: {completed.stderr}")
    return result


def _stdout_json(result: dict[str, Any]) -> dict[str, Any]:
    text = str(result.get("stdout") or "{}")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("command stdout JSON must be an object")
    return data


def _token(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return value
    nested = data.get("data")
    if isinstance(nested, dict):
        for key in keys:
            value = nested.get(key)
            if isinstance(value, str) and value:
                return value
    raise ValueError(f"missing token keys: {keys}")


def _without_dry_run(argv: list[str]) -> list[str]:
    return [item for item in argv if item != "--dry-run"]


def publish_output(
    output_root: str | Path,
    jd_title: str,
    wiki_space_id: str,
    runner: Runner = default_runner,
) -> dict[str, Any]:
    root = Path(output_root)
    manifest = build_publish_manifest(root, jd_title=jd_title, wiki_space_id=wiki_space_id, dry_run=True)
    results: list[dict[str, Any]] = []

    def run(argv: list[str]) -> dict[str, Any]:
        result = _run(argv, runner)
        results.append(result)
        return result

    run(["lark-cli", "doctor"])
    run(["lark-cli", "auth", "status"])

    parent_dry = ["lark-cli", "wiki", "+node-create", "--as", "user", "--space-id", wiki_space_id, "--title", jd_title, "--obj-type", "docx", "--dry-run"]
    run(parent_dry)
    parent_real = run(_without_dry_run(parent_dry))
    parent_node_token = _token(_stdout_json(parent_real), "node_token", "wiki_token")

    files = _required_files(root)
    publish_items = [
        ("docx", files["jd"], f"{jd_title} JD需求"),
        ("docx", files["profile"], f"{jd_title} 岗位画像"),
        ("docx", files["recommendation"], f"{jd_title} 人才推荐报告"),
        ("sheet", files["outreach"], f"{jd_title} 外联表"),
    ]
    published: list[dict[str, Any]] = []
    for obj_type, path, title in publish_items:
        import_cmd = _import_sheet_command(path, title, dry_run=True) if obj_type == "sheet" else _import_doc_command(path, title, dry_run=True)
        run(import_cmd)
        import_real = run(_without_dry_run(import_cmd))
        obj_token = _token(_stdout_json(import_real), "obj_token", "token", "file_token", "spreadsheet_token")
        move_cmd = _move_command(obj_type, obj_token, wiki_space_id, parent_node_token, dry_run=True)
        run(move_cmd)
        move_real = run(_without_dry_run(move_cmd))
        published.append({
            "title": title,
            "obj_type": obj_type,
            "obj_token": obj_token,
            "move": _stdout_json(move_real),
        })

    publish_result = {
        "schema": "jd_talent_delivery_feishu_publish_result_v1",
        "status": "published",
        "wiki_space_id": wiki_space_id,
        "parent_node_token": parent_node_token,
        "published": published,
        "command_results": results,
    }
    out = root / "feishu" / "publish-results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(publish_result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return publish_result
```

- [ ] **Step 4: Run Feishu tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_feishu.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_feishu.py
git commit -m "Add JD talent delivery Feishu publisher"
```

---

### Task 8: End-to-End Workflow Wiring

**Files:**
- Modify: `skills/jd-talent-delivery/SKILL.md`
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Create: `scripts/jd_talent_delivery.py`
- Create: `tests/test_jd_talent_delivery_cli.py`

- [ ] **Step 1: Write failing CLI orchestration test**

Create `tests/test_jd_talent_delivery_cli.py`:

```python
import json
from pathlib import Path

from scripts import jd_talent_delivery


def test_prepare_creates_output_tree_and_jd_copy(tmp_path: Path) -> None:
    jd = tmp_path / "LLM推理工程师.md"
    jd.write_text("# LLM推理工程师\n\n负责 vLLM 和 KV Cache。\n", encoding="utf-8")
    out_root = tmp_path / "output"

    result = jd_talent_delivery.prepare_workspace(
        jd_path=jd,
        output_base=out_root,
        date_text="2026-05-23",
        top_n=30,
    )

    output_dir = Path(result["output_dir"])
    assert output_dir.name.endswith("2026-05-23")
    assert (output_dir / "source" / "jd.md").read_text(encoding="utf-8-sig").startswith("# LLM推理工程师")
    assert (output_dir / "profile").exists()
    assert (output_dir / "scoring").exists()
    assert (output_dir / "reports").exists()
    assert (output_dir / "feishu").exists()
    manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8-sig"))
    assert manifest["top_n"] == 30
    assert manifest["source_jd_path"] == str(jd)
```

- [ ] **Step 2: Run test and verify failure**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_cli.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `scripts.jd_talent_delivery`.

- [ ] **Step 3: Implement workspace preparation CLI**

Create `scripts/jd_talent_delivery.py`:

```python
from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any


def slugify(value: str) -> str:
    text = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE).strip("-._")
    return text or "jd"


def prepare_workspace(jd_path: str | Path, output_base: str | Path, date_text: str, top_n: int) -> dict[str, Any]:
    source_path = Path(jd_path)
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    slug = slugify(source_path.stem)
    output_dir = Path(output_base) / f"{slug}-{date_text}"
    for child in ["source", "profile", "scoring", "reports", "feishu"]:
        (output_dir / child).mkdir(parents=True, exist_ok=True)
    jd_text = source_path.read_text(encoding="utf-8-sig")
    (output_dir / "source" / "jd.md").write_text(jd_text, encoding="utf-8-sig")
    manifest = {
        "schema": "jd_talent_delivery_run_manifest_v1",
        "source_jd_path": str(source_path),
        "output_dir": str(output_dir),
        "top_n": top_n,
        "date": date_text,
    }
    (output_dir / "run-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JD talent delivery workspace helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--jd-path", required=True)
    prepare.add_argument("--output-base", default="data/output")
    prepare.add_argument("--date", default=date.today().isoformat())
    prepare.add_argument("--top-n", type=int, default=30)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_workspace(args.jd_path, args.output_base, args.date, args.top_n)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Update skill and workflow with CLI command examples**

Add this command example to `skills/jd-talent-delivery/SKILL.md` under automatic handoff:

```markdown
首个运行时检查命令：

```powershell
python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> --output-base data/output --top-n 30
```
```

Add this command example to `agents/workflows/jd-talent-delivery/AGENT.md` under S1:

```markdown
运行时入口：

```powershell
python -m scripts.jd_talent_delivery prepare --jd-path <jd_path> --output-base data/output --top-n <N>
```
```

- [ ] **Step 5: Run CLI and focused docs tests**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_cli.py tests/test_jd_talent_delivery_skill.py tests/test_jd_talent_delivery_workflow.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```powershell
git add scripts/jd_talent_delivery.py tests/test_jd_talent_delivery_cli.py skills/jd-talent-delivery/SKILL.md agents/workflows/jd-talent-delivery/AGENT.md
git commit -m "Add JD talent delivery workspace CLI"
```

---

### Task 9: Focused and Full Verification

**Files:**
- Modify only files touched by earlier tasks if verification exposes a defect.

- [ ] **Step 1: Run focused test suite**

Run:

```powershell
python -m pytest tests/test_jd_talent_delivery_skill.py tests/test_jd_talent_delivery_workflow.py tests/test_jd_talent_delivery_profile.py tests/test_jd_talent_delivery_scorecard.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py tests/test_jd_talent_delivery_cli.py -q
```

Expected: all tests PASS.

- [ ] **Step 2: Run architecture and related regression tests**

Run:

```powershell
python -m pytest tests/test_agent_architecture.py tests/test_talent_library_workflow.py tests/test_feishu_delivery_package.py tests/test_maimai_ai_infra_outreach_export.py -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run full repository verification**

Run:

```powershell
python -m pytest tests scripts -q
```

Expected: all tests PASS, allowing only pre-existing unrelated warnings such as known event-loop deprecation warnings.

- [ ] **Step 4: Run diff hygiene**

Run:

```powershell
git diff --check
```

Expected: no output and exit code 0.

- [ ] **Step 5: Inspect final diff**

Run:

```powershell
git status --short --branch
git diff --stat HEAD
```

Expected: only JD talent delivery implementation files are modified or added, plus any pre-existing unrelated dirty files remain clearly separate.

- [ ] **Step 6: Commit final fixes if any**

If Step 1-4 required fixes, commit them:

```powershell
git add <fixed-files>
git commit -m "Stabilize JD talent delivery workflow"
```

If no fixes were needed, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Output folder and all process outputs are covered by Tasks 1, 2, and 6.
- `hr-talent` role profile requirement is represented in Skill and Workflow, and Task 3 creates deterministic role profile artifacts with the same section shape as the approved deep-dive template.
- Shared `scorecard.json` consistency is covered by Tasks 3 and 4.
- Local talent DB read-only matching is covered by Task 4.
- TopN default and parameter support are covered by Tasks 1, 4, and 6.
- Feishu Wiki `JD需求交付` publish boundary is covered by Tasks 1, 2, and 5.
- Sensitive artifact exclusion is covered by Tasks 2 and 5.

Known implementation constraint:

- The first automated profile builder extracts structured terms deterministically and renders the required deep-dive shape. During actual skill execution, the agent still uses `hr-talent` judgment to review and improve `profile/role-deep-dive.md` before generating the scorecard.
