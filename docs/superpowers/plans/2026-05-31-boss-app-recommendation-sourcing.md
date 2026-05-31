# BOSS App Recommendation Sourcing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runtime-neutral BOSS App recommendation-list sourcing workflow that uses Computer Use at execution time, stores every run in an independent campaign directory, supports dry-run contact decisions, supports small action-confirmed live-contact tests, and can backfill real names from communication pages.

**Architecture:** Add a new canonical skill and workflow under `agents/`, add a generic `computer.operate` capability, and implement a local Python helper module for contracts, JSONL state, candidate normalization, contact safety checks, real-name updates, continuation plans, and summaries. The Python code will not operate the BOSS App UI; the canonical workflow defines UI operations and the runtime adapter maps `computer.operate` to Computer Use.

**Tech Stack:** Python 3.12+, pytest, Markdown agent contracts, JSON/JSONL run artifacts.

**Spec:** `docs/superpowers/specs/2026-05-31-boss-app-recommendation-sourcing-design.md`

---

## File Structure

| File | Action | Responsibility |
| --- | --- | --- |
| `agents/capabilities.md` | Modify | Add `computer.operate` generic capability for local app UI operations. |
| `agents/skills/boss-app-recommendation-sourcing/SKILL.md` | Create | Business entry contract, default policy, output artifacts, handoff to canonical workflow. |
| `agents/workflows/boss-app-recommendation-sourcing/AGENT.md` | Create | Canonical S0-S8 workflow, Computer Use action boundaries, live-test confirmation gates, recovery rules. |
| `.claude/skills/boss-app-recommendation-sourcing/SKILL.md` | Create | Runtime adapter that maps `computer.operate` to Computer Use and points to canonical files. |
| `scripts/boss_app_sourcing.py` | Create | Importable helper and CLI for campaign initialization, JSON state, candidate updates, contact decisions, real-name backfill, reports. |
| `tests/test_boss_app_sourcing.py` | Create | Focused unit tests for contracts, policy guards, JSONL helpers, candidate lifecycle, reports, CLI. |
| `tests/test_agent_architecture.py` | Modify | Add new workflow/skill/adapter coverage and assert `computer.operate` is documented. |
| `docs/dev/script-inventory.md` | Modify | Register `scripts/boss_app_sourcing.py` as a runtime CLI. |
| `tasks/todo.md` | Modify | Track task progress and final verification evidence. |

## Data Contracts

Campaign root:

```text
data/campaigns/<campaign_id>/
  requirements.json
  strategy.json
  run-policy.json
  campaign-manifest.json
  raw/
    list-cards.jsonl
    detail-pages.jsonl
    communication-pages.jsonl
    screen-hashes.jsonl
  state/
    events.jsonl
    processed-cards.jsonl
    continuation-plan.json
  structured/
    candidates.jsonl
    contact-decisions.jsonl
  reports/
    sourcing-summary.md
    sourcing-summary.json
    interruption-*.json
```

Core policy defaults:

```json
{
  "execution_surface": "boss_app_computer_use",
  "contact_mode": "dry_run",
  "allow_real_contact": false,
  "allow_live_contact_test": false,
  "live_contact_test_limit": 0,
  "require_action_time_confirmation_for_real_contact": true,
  "capture_real_name_after_contact": true,
  "stop_on_login_or_security_page": true,
  "stop_on_captcha": true,
  "stop_on_ui_template_drift": true,
  "list_end_stall_scrolls": 3
}
```

---

### Task 1: Agent Architecture Contracts

**Files:**
- Modify: `agents/capabilities.md`
- Create: `agents/skills/boss-app-recommendation-sourcing/SKILL.md`
- Create: `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`
- Create: `.claude/skills/boss-app-recommendation-sourcing/SKILL.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Write failing architecture tests**

Modify `tests/test_agent_architecture.py`:

```python
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
```

Append this test:

```python
def test_capabilities_include_local_app_operations():
    text = (ROOT / "agents" / "capabilities.md").read_text(encoding="utf-8")
    assert "`computer.operate`" in text
    assert "本地 App" in text
```

- [ ] **Step 2: Run the focused architecture test and verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: FAIL with missing canonical workflow, missing canonical skill, missing Claude adapter, and missing `computer.operate`.

- [ ] **Step 3: Add `computer.operate` to capabilities**

Modify the capability table in `agents/capabilities.md` by adding this row after `browser.operate`:

```markdown
| `computer.operate` | 操作本地 App UI，例如读取屏幕、点击、滚动、输入、返回 | Computer Use / desktop automation | Computer Use |
```

Add this rule under “工作流规则”:

```markdown
4. 涉及第三方沟通、发送消息、上传文件、修改账号状态或其他外部副作用时，`computer.operate` 必须先经过 `human.confirm` 动作级确认。
```

- [ ] **Step 4: Create canonical skill**

Create `agents/skills/boss-app-recommendation-sourcing/SKILL.md`:

```markdown
---
name: boss-app-recommendation-sourcing
description: Use when the user wants to source candidates from the BOSS App recommendation list by operating the local BOSS App UI, screening cards and details, recording would-contact decisions, optionally running small confirmed live-contact tests, or backfilling real names from communication pages.
---

# boss-app-recommendation-sourcing

## 目标

把一次 BOSS App 推荐列表寻访整理成可执行、可恢复、可审计的任务合同。用户先打开本机 BOSS App 并进入目标职位的牛人推荐列表页；本 Skill 只负责需求抽取、合同生成、安全边界和 workflow 交接。

## 触发语义

用户表达以下意图时使用本 Skill：

- 从 BOSS App 推荐列表逐个看人选。
- 在 BOSS App 里按公司、职位、学历、年龄、技术栈等进一步筛选推荐人选。
- 用 Computer Use 操作 BOSS App 采集列表和详情。
- 对合适人选记录 `would_contact` 或做少量动作级确认的 `立即沟通` live-test。
- 从已沟通页面回采真实姓名。

不要使用 `platform-match` 网页搜索 workflow；本流程不操作 BOSS 网页端，不调用 BOSS API，不复用 CDP 搜索链路。

## 输入抽取

BOSS 推荐列表本身已经基于 JD 生成。用户通常只提供进一步筛选依据，例如：

- 目标公司或排除公司。
- 职位/职能/职级。
- 学历、年龄、城市、薪资。
- 技术栈、业务方向、行业背景。
- 必须项、加分项、排除项。

只对缺失或冲突的关键字段提问；能稳定抽取的字段直接写入 `requirements.json` 和 `strategy.json`。

## 默认运行策略

- `execution_surface="boss_app_computer_use"`
- `contact_mode="dry_run"`
- `allow_real_contact=false`
- `allow_live_contact_test=false`
- `live_contact_test_limit=0`
- `require_action_time_confirmation_for_real_contact=true`
- `capture_real_name_after_contact=true`
- 首版详情证据只保存结构化文本和截图哈希，不保存截图文件。
- 主人才库写入不在本 workflow 内执行。

## 输出产物

默认根目录：`data/campaigns/<campaign_id>/`。

必须生成：

- `requirements.json`
- `strategy.json`
- `run-policy.json`
- `campaign-manifest.json`
- `raw/list-cards.jsonl`
- `raw/detail-pages.jsonl`
- `raw/communication-pages.jsonl`
- `raw/screen-hashes.jsonl`
- `state/events.jsonl`
- `state/processed-cards.jsonl`
- `state/continuation-plan.json`
- `structured/candidates.jsonl`
- `structured/contact-decisions.jsonl`
- `reports/sourcing-summary.md`
- `reports/sourcing-summary.json`

## 安全边界

- 默认不点击 `立即沟通`。
- 少量 live-test 必须由 run-policy 开启、受测试上限限制，并且每次点击前通过 `human.confirm` 动作级确认。
- BOSS App 点击 `立即沟通` 会自动发送预设消息，必须把这一副作用告知用户后再确认。
- 不处理验证码，不绕过安全页，不修改 BOSS App 设置、职位设置、沟通话术或账号权限。
- 真实姓名来自 live-test 后沟通页，或用户手动打开的已沟通页面；不能用真实姓名覆盖 `display_name`。

## 自动交接

合同文件生成后，读取并执行 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。真实 App 操作由 canonical workflow 通过 `computer.operate` 描述，运行时适配器映射到对应桌面 UI 操作能力。
```

- [ ] **Step 5: Create canonical workflow**

Create `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`:

```markdown
---
name: boss-app-recommendation-sourcing
description: BOSS App 推荐列表寻访 canonical workflow，约束合同、Computer Use 操作、安全确认、真实姓名回填、恢复和报告。
---

# boss-app-recommendation-sourcing

## 触发入口

- 从 `agents/skills/boss-app-recommendation-sourcing/SKILL.md` 完成需求抽取和合同生成后交接执行。
- 用户要求继续、恢复、中断后接着扫 BOSS App 推荐列表、回采已沟通真实姓名或执行少量 live-test 时，读取本 workflow 并按当前状态继续。

## 能力边界

- 使用 `file.read`、`file.write`、`shell.run`、`computer.operate` 和 `human.confirm`。
- 不使用 BOSS 网页端、CDP、浏览器扩展或 BOSS API。
- Python 脚本只负责合同、状态、结构化和报告；App UI 操作由 `computer.operate` 执行。

## 安全边界

- 默认 `contact_mode=dry_run`，只定位 `立即沟通`，记录 `would_contact`，不点击。
- live-test 真实点击必须满足 `allow_live_contact_test=true`、未超过 `live_contact_test_limit`、候选人 `recommendation=contact`，并在点击前用 `human.confirm` 说明候选人、判定理由和自动发送预设消息的副作用。
- 登录失效、验证码、安全页、权限弹窗、系统遮挡、UI 模板漂移或疑似真实发送风险时必须停止并写 interruption report。
- 不处理验证码，不修改账号设置，不修改沟通话术，不删除/屏蔽/拉黑人选。

## 阶段

### S0 合同检查

读取 `requirements.json`、`strategy.json`、`run-policy.json` 和 `campaign-manifest.json`。确认 `execution_surface=boss_app_computer_use`，默认 `contact_mode=dry_run`。

### S1 App 预检

使用 `computer.operate` 读取当前前台 App 和页面。通过条件：

- 当前为 BOSS App。
- 用户已进入目标职位的推荐列表页。
- 可识别至少一个候选人卡片。

失败时写 `state/continuation-plan.json` 并请求用户手动回到推荐列表。

### S2 列表卡片采集

对当前可见卡片逐个读取展示名、公司、职位、学历、年龄、经验、薪资、城市、活跃状态和屏幕区域。把结构化结果追加到 `raw/list-cards.jsonl`，把截图哈希追加到 `raw/screen-hashes.jsonl`。

### S3 列表初筛

按 `strategy.json` 判断是否进入详情。低概率人选写入 `structured/candidates.jsonl`，状态为 `skip_list_stage`。高概率人选进入 S4。

### S4 详情采集

使用 `computer.operate` 点击卡片进入详情页。读取首屏文本，点击 `展开全部`、`查看更多` 或相近折叠入口，在详情页内部滚动到底。只保存结构化文本和截图哈希。完成后返回列表页。

### S5 详情精筛

基于详情结构化文本输出 `contact`、`hold` 或 `skip`，并写入证据、分数、缺失项和风险。

### S6 沟通 dry-run

对 `recommendation=contact` 的候选人定位 `立即沟通` 按钮，记录 `would_contact=true`、按钮位置和截图哈希，不点击按钮。

### S6b live-test 真实沟通

仅在 run-policy 开启 live-test 时执行。点击前必须用 `human.confirm` 说明：

- 展示名。
- 详情判定理由。
- live-test 剩余额度。
- 点击 `立即沟通` 会自动发送预设消息。

确认后用 `computer.operate` 点击 `立即沟通`，进入沟通页后读取真实姓名，写入 `real_name` 和 `real_name_source=communication_page_after_live_contact_test`，再记录是否观察到预设消息已发送。

### S6c 人工已沟通页面回采

用户手动打开已沟通页面后，使用 `computer.operate` 读取真实姓名，写入 `real_name_source=manual_opened_communication_page`。本阶段不发送新消息。

### S7 列表滚动与结束

当前屏处理完成后滚动列表。连续 `list_end_stall_scrolls` 次滚动无新卡片，或识别到列表底部时停止。

### S8 报告与关闭

运行：

```bash
.venv/bin/python -m scripts.boss_app_sourcing summarize --campaign-root data/campaigns/<campaign_id>
```

报告必须包含列表扫描数、详情数、`would_contact` 数、live-test 数、真实姓名补全状态、跳过原因和恢复入口。

## 恢复入口

恢复时只信本地文件：

- `state/processed-cards.jsonl`
- `structured/candidates.jsonl`
- `structured/contact-decisions.jsonl`
- `state/continuation-plan.json`

如果当前 App 不在原推荐列表页，请用户手动回到列表页后继续。

## 验收

- dry-run 不点击 `立即沟通`。
- live-test 每次真实点击都有动作级确认记录。
- 详情只保存结构化文本和截图哈希。
- `display_name` 与 `real_name` 同时保留。
- 中断后可从 continuation plan 恢复。
```

- [ ] **Step 6: Create Claude adapter**

Create `.claude/skills/boss-app-recommendation-sourcing/SKILL.md`:

```markdown
---
name: boss-app-recommendation-sourcing
description: "BOSS App 推荐列表寻访。用于通过 Computer Use 操作本机 BOSS App，采集推荐列表和详情，记录 would-contact，执行动作级确认的少量 live-test，并回采真实姓名。"
---

# Claude Code Adapter: boss-app-recommendation-sourcing

这是运行时私有入口。Canonical skill contract 位于 `agents/skills/boss-app-recommendation-sourcing/SKILL.md`；canonical workflow 位于 `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。

## Adapter Steps

1. Read `agents/capabilities.md`。
2. Read `agents/skills/boss-app-recommendation-sourcing/SKILL.md`，取得业务入口、默认参数、输出 contract、安全边界和 workflow 交接规则。
3. Read `agents/workflows/boss-app-recommendation-sourcing/AGENT.md`。
4. 将 canonical skill 和 workflow 中的通用能力映射到 Claude Code 工具：
   - `file.read` -> Read
   - `file.write` -> Write/Edit
   - `shell.run` -> Bash
   - `computer.operate` -> Computer Use
   - `human.confirm` -> 直接询问用户
5. 严格按 canonical skill 和 workflow 执行；本文件不保存业务流程、规则或脚本。
```

- [ ] **Step 7: Run the focused architecture test and verify it passes**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit architecture contracts**

```bash
git add agents/capabilities.md agents/skills/boss-app-recommendation-sourcing/SKILL.md agents/workflows/boss-app-recommendation-sourcing/AGENT.md .claude/skills/boss-app-recommendation-sourcing/SKILL.md tests/test_agent_architecture.py
git commit -m "feat: add BOSS App sourcing agent contracts"
```

---

### Task 2: Core Campaign Helper

**Files:**
- Create: `scripts/boss_app_sourcing.py`
- Create: `tests/test_boss_app_sourcing.py`
- Modify: `docs/dev/script-inventory.md`

- [ ] **Step 1: Write failing tests for campaign initialization and helpers**

Create `tests/test_boss_app_sourcing.py`:

```python
import json
from pathlib import Path

import pytest

from scripts import boss_app_sourcing


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def test_slugify_keeps_chinese_and_ascii_word_chars() -> None:
    assert boss_app_sourcing.slugify("大模型 产品 / 北京") == "大模型-产品-北京"
    assert boss_app_sourcing.slugify(" !@# ") == "boss-app-sourcing"


def test_screen_hash_is_stable_and_prefixed() -> None:
    assert boss_app_sourcing.screen_hash("张先生|产品经理") == boss_app_sourcing.screen_hash("张先生|产品经理")
    assert boss_app_sourcing.screen_hash("张先生|产品经理").startswith("sha256:")


def test_build_candidate_key_uses_visible_fields_and_hash() -> None:
    card = {
        "display_name": "张先生",
        "current_company": "字节跳动",
        "current_title": "产品经理",
        "education": "硕士",
        "city": "北京",
        "expected_salary": "40-60K",
        "screenshot_hash": "sha256:abc",
    }
    key = boss_app_sourcing.build_candidate_key(card)
    assert key.startswith("boss-app:")
    assert key == boss_app_sourcing.build_candidate_key(dict(card))


def test_init_campaign_creates_contract_tree(tmp_path: Path) -> None:
    result = boss_app_sourcing.init_campaign(
        campaign_id="boss-app-test",
        filters_text="优先 AI 产品，985 本科以上，年龄 28-35",
        out_base=tmp_path,
        date_text="2026-05-31",
    )

    root = Path(result["campaign_root"])
    assert root == tmp_path / "boss-app-test"
    for relative in [
        "requirements.json",
        "strategy.json",
        "run-policy.json",
        "campaign-manifest.json",
        "raw/list-cards.jsonl",
        "raw/detail-pages.jsonl",
        "raw/communication-pages.jsonl",
        "raw/screen-hashes.jsonl",
        "state/events.jsonl",
        "state/processed-cards.jsonl",
        "state/continuation-plan.json",
        "structured/candidates.jsonl",
        "structured/contact-decisions.jsonl",
        "reports/sourcing-summary.md",
        "reports/sourcing-summary.json",
    ]:
        assert (root / relative).exists(), relative

    policy = read_json(root / "run-policy.json")
    assert policy["execution_surface"] == "boss_app_computer_use"
    assert policy["contact_mode"] == "dry_run"
    assert policy["allow_live_contact_test"] is False
    assert policy["live_contact_test_limit"] == 0

    requirements = read_json(root / "requirements.json")
    assert requirements["filters_text"] == "优先 AI 产品，985 本科以上，年龄 28-35"
    assert requirements["input_mode"] == "post_jd_recommendation_filters"


def test_init_campaign_rejects_real_contact_without_limit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="live_contact_test_limit"):
        boss_app_sourcing.init_campaign(
            campaign_id="bad",
            filters_text="AI 产品",
            out_base=tmp_path,
            allow_live_contact_test=True,
            live_contact_test_limit=0,
        )


def test_init_cli_prints_manifest_json(tmp_path: Path, capsys) -> None:
    exit_code = boss_app_sourcing.main([
        "init",
        "--campaign-id",
        "boss-app-cli",
        "--filters-text",
        "看 AI 产品和 985",
        "--out-base",
        str(tmp_path),
        "--date",
        "2026-05-31",
        "--allow-live-contact-test",
        "--live-contact-test-limit",
        "2",
    ])

    assert exit_code == 0
    manifest = json.loads(capsys.readouterr().out)
    root = Path(manifest["campaign_root"])
    assert root == tmp_path / "boss-app-cli"
    assert read_json(root / "run-policy.json")["live_contact_test_limit"] == 2
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: FAIL because `scripts.boss_app_sourcing` does not exist.

- [ ] **Step 3: Implement campaign helper**

Create `scripts/boss_app_sourcing.py`:

```python
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "boss_app_recommendation_sourcing_manifest_v1"

DEFAULT_RUN_POLICY: dict[str, Any] = {
    "execution_surface": "boss_app_computer_use",
    "contact_mode": "dry_run",
    "allow_real_contact": False,
    "allow_live_contact_test": False,
    "live_contact_test_limit": 0,
    "require_action_time_confirmation_for_real_contact": True,
    "capture_real_name_after_contact": True,
    "stop_on_login_or_security_page": True,
    "stop_on_captcha": True,
    "stop_on_ui_template_drift": True,
    "list_end_stall_scrolls": 3,
}


REQUIRED_EMPTY_FILES = [
    "raw/list-cards.jsonl",
    "raw/detail-pages.jsonl",
    "raw/communication-pages.jsonl",
    "raw/screen-hashes.jsonl",
    "state/events.jsonl",
    "state/processed-cards.jsonl",
    "structured/candidates.jsonl",
    "structured/contact-decisions.jsonl",
]


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff.-]+", "-", value, flags=re.UNICODE).strip("-._")
    return slug or "boss-app-sourcing"


def _json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_json(path: str | Path, data: Any) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(_json_dumps(data), encoding="utf-8")


def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def append_jsonl(path: str | Path, record: dict[str, Any]) -> dict[str, Any]:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    file = Path(path)
    if not file.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(file.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{file} line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"{file} line {line_number}: must be an object")
        rows.append(value)
    return rows


def screen_hash(text: str | bytes) -> str:
    data = text if isinstance(text, bytes) else text.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()


def build_candidate_key(card: dict[str, Any]) -> str:
    parts = [
        str(card.get("display_name") or "").strip(),
        str(card.get("current_company") or "").strip(),
        str(card.get("current_title") or "").strip(),
        str(card.get("education") or "").strip(),
        str(card.get("city") or "").strip(),
        str(card.get("expected_salary") or "").strip(),
        str(card.get("screenshot_hash") or "").strip(),
    ]
    return "boss-app:" + hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def validate_run_policy(policy: dict[str, Any]) -> dict[str, Any]:
    merged = dict(DEFAULT_RUN_POLICY)
    merged.update(policy)
    if merged["execution_surface"] != "boss_app_computer_use":
        raise ValueError("execution_surface must be boss_app_computer_use")
    if merged["contact_mode"] not in {"dry_run", "live_test"}:
        raise ValueError("contact_mode must be dry_run or live_test")
    if merged["allow_real_contact"] and not merged["require_action_time_confirmation_for_real_contact"]:
        raise ValueError("real contact requires action-time confirmation")
    if merged["allow_live_contact_test"] and int(merged["live_contact_test_limit"]) <= 0:
        raise ValueError("live_contact_test_limit must be positive when live-contact test is enabled")
    if not merged["allow_live_contact_test"]:
        merged["live_contact_test_limit"] = 0
    return merged


def _initial_requirements(filters_text: str, campaign_id: str, date_text: str) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "input_mode": "post_jd_recommendation_filters",
        "filters_text": filters_text,
        "confirmed_defaults": {
            "source_list": "boss_app_jd_recommendation_list",
            "details_store": "structured_text_and_screenshot_hash",
            "real_name_backfill": "live_test_or_manual_communication_page",
        },
        "created_date": date_text,
    }


def _initial_strategy(filters_text: str) -> dict[str, Any]:
    return {
        "strategy_version": "boss_app_recommendation_sourcing_v1",
        "list_screening": {
            "input_text": filters_text,
            "enter_detail_when": "candidate appears likely to satisfy the filters",
        },
        "detail_screening": {
            "recommendation_values": ["contact", "hold", "skip"],
            "would_contact_requires": ["positive evidence", "no hard exclusion"],
        },
    }


def init_campaign(
    campaign_id: str,
    filters_text: str,
    out_base: str | Path = "data/campaigns",
    date_text: str | None = None,
    allow_live_contact_test: bool = False,
    live_contact_test_limit: int = 0,
) -> dict[str, Any]:
    if not campaign_id.strip():
        raise ValueError("campaign_id is required")
    if not filters_text.strip():
        raise ValueError("filters_text is required")

    date_value = date_text or date.today().isoformat()
    root = Path(out_base) / slugify(campaign_id)
    root.mkdir(parents=True, exist_ok=True)

    policy = validate_run_policy({
        "allow_live_contact_test": allow_live_contact_test,
        "live_contact_test_limit": int(live_contact_test_limit),
    })
    requirements = _initial_requirements(filters_text, slugify(campaign_id), date_value)
    strategy = _initial_strategy(filters_text)
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "campaign_id": slugify(campaign_id),
        "campaign_root": str(root),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "requirements_path": str(root / "requirements.json"),
        "strategy_path": str(root / "strategy.json"),
        "run_policy_path": str(root / "run-policy.json"),
        "status": "initialized",
    }

    write_json(root / "requirements.json", requirements)
    write_json(root / "strategy.json", strategy)
    write_json(root / "run-policy.json", policy)
    write_json(root / "campaign-manifest.json", manifest)
    write_json(root / "state/continuation-plan.json", {
        "stage": "initialized",
        "status": "ready_for_app_preflight",
        "campaign_root": str(root),
    })
    write_json(root / "reports/sourcing-summary.json", {
        "campaign_id": slugify(campaign_id),
        "status": "initialized",
    })
    (root / "reports/sourcing-summary.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "reports/sourcing-summary.md").write_text("# BOSS App 寻访摘要\n\n状态：initialized\n", encoding="utf-8")
    for relative in REQUIRED_EMPTY_FILES:
        file = root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch(exist_ok=True)
    append_jsonl(root / "state/events.jsonl", {
        "stage": "init",
        "status": "ready",
        "at": datetime.now().isoformat(timespec="seconds"),
    })
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BOSS App recommendation sourcing helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--campaign-id", required=True)
    init_parser.add_argument("--filters-text", required=True)
    init_parser.add_argument("--out-base", default="data/campaigns")
    init_parser.add_argument("--date", default=date.today().isoformat())
    init_parser.add_argument("--allow-live-contact-test", action="store_true")
    init_parser.add_argument("--live-contact-test-limit", type=int, default=0)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "init":
        manifest = init_campaign(
            campaign_id=args.campaign_id,
            filters_text=args.filters_text,
            out_base=args.out_base,
            date_text=args.date,
            allow_live_contact_test=args.allow_live_contact_test,
            live_contact_test_limit=args.live_contact_test_limit,
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Register script in inventory**

Modify `docs/dev/script-inventory.md` under `## Runtime CLI`:

```markdown
- `scripts/boss_app_sourcing.py`：BOSS App 推荐列表寻访合同、状态、真实姓名回填和报告入口。
```

- [ ] **Step 5: Run focused tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit campaign helper**

```bash
git add scripts/boss_app_sourcing.py tests/test_boss_app_sourcing.py docs/dev/script-inventory.md
git commit -m "feat: add BOSS App sourcing campaign helper"
```

---

### Task 3: Candidate Lifecycle and Contact Safety

**Files:**
- Modify: `scripts/boss_app_sourcing.py`
- Modify: `tests/test_boss_app_sourcing.py`

- [ ] **Step 1: Add failing tests for candidate recording and real-name lifecycle**

Append to `tests/test_boss_app_sourcing.py`:

```python
def test_record_list_card_appends_candidate_and_processed_key(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-card", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    card = {
        "display_name": "张先生",
        "current_company": "某大厂",
        "current_title": "AI 产品经理",
        "education": "硕士",
        "city": "北京",
        "expected_salary": "40-60K",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-1"),
    }

    candidate = boss_app_sourcing.record_list_card(root, card)

    assert candidate["candidate_key"].startswith("boss-app:")
    assert candidate["display_name"] == "张先生"
    assert candidate["real_name"] is None
    assert candidate["real_name_status"] == "not_available_dry_run"
    candidates = boss_app_sourcing.load_jsonl(root / "structured/candidates.jsonl")
    processed = boss_app_sourcing.load_jsonl(root / "state/processed-cards.jsonl")
    assert candidates[-1]["candidate_key"] == candidate["candidate_key"]
    assert processed[-1]["candidate_key"] == candidate["candidate_key"]


def test_record_detail_update_merges_detail_sections(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-detail", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "李女士",
        "current_title": "产品负责人",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-2"),
    })

    updated = boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {
            "work_experience": [{"company": "A 公司", "title": "产品负责人"}],
            "education_experience": [{"school": "清华大学", "degree": "硕士"}],
        },
        recommendation="contact",
        score=86,
        reasons=["AI 产品经验强"],
    )

    assert updated["screening"]["detail_decision"] == "contact"
    assert updated["screening"]["score"] == 86
    assert updated["detail_sections"]["work_experience"][0]["company"] == "A 公司"


def test_record_contact_dry_run_never_marks_contacted(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-contact", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "王先生",
        "current_title": "算法产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-3"),
    })

    decision = boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="dry_run",
        button_seen=True,
        action_confirmed=False,
    )

    assert decision["would_contact"] is True
    assert decision["contacted"] is False
    assert decision["action_confirmed"] is False
    updated = boss_app_sourcing.latest_candidate(root, candidate["candidate_key"])
    assert updated["contact"]["would_contact"] is True
    assert updated["contact"]["contacted"] is False


def test_live_contact_requires_policy_limit_and_confirmation(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-live",
        "看 AI 产品",
        out_base=tmp_path,
        allow_live_contact_test=True,
        live_contact_test_limit=1,
    )
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "赵女士",
        "current_title": "AI PM",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-4"),
    })

    with pytest.raises(ValueError, match="action confirmation"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=False,
        )

    decision = boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="live_test",
        button_seen=True,
        action_confirmed=True,
        preset_message_auto_sent=True,
    )

    assert decision["contacted"] is True
    assert decision["preset_message_auto_sent"] is True

    with pytest.raises(ValueError, match="live contact test limit"):
        boss_app_sourcing.record_contact_decision(
            root,
            candidate["candidate_key"],
            mode="live_test",
            button_seen=True,
            action_confirmed=True,
        )


def test_backfill_real_name_preserves_display_name(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-real-name", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_title": "产品经理",
        "screenshot_hash": boss_app_sourcing.screen_hash("card-5"),
    })

    updated = boss_app_sourcing.backfill_real_name(
        root,
        candidate["candidate_key"],
        real_name="张 XX",
        source="manual_opened_communication_page",
    )

    assert updated["display_name"] == "张先生"
    assert updated["real_name"] == "张 XX"
    assert updated["real_name_source"] == "manual_opened_communication_page"
    assert updated["real_name_status"] == "captured"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: FAIL because lifecycle functions are not implemented.

- [ ] **Step 3: Implement lifecycle functions**

Append these functions to `scripts/boss_app_sourcing.py` before `build_parser()`:

```python
def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _campaign_path(campaign_root: str | Path, relative: str) -> Path:
    return Path(campaign_root) / relative


def _base_candidate(card: dict[str, Any], candidate_key: str) -> dict[str, Any]:
    return {
        "candidate_key": candidate_key,
        "platform": "boss_app",
        "display_name": card.get("display_name"),
        "real_name": None,
        "real_name_status": "not_available_dry_run",
        "real_name_source": None,
        "name_confidence": "masked",
        "current_company": card.get("current_company", ""),
        "current_title": card.get("current_title", ""),
        "city": card.get("city", ""),
        "work_years": card.get("work_years"),
        "education": card.get("education", ""),
        "expected_salary": card.get("expected_salary", ""),
        "active_state": card.get("active_state", ""),
        "list_snapshot": dict(card),
        "detail_sections": {},
        "screen_evidence": [
            {
                "page": "list",
                "screenshot_hash": card.get("screenshot_hash", ""),
                "screen_region": card.get("screen_region"),
                "captured_at": _now(),
            }
        ],
        "screening": {
            "list_decision": card.get("list_decision", ""),
            "detail_decision": "",
            "score": 0,
            "reasons": [],
            "risks": [],
        },
        "contact": {
            "would_contact": False,
            "contact_mode": "dry_run",
            "contacted": False,
            "live_contact_test": False,
            "contact_button_seen": False,
            "communication_page_seen": False,
            "preset_message_auto_sent": False,
        },
        "updated_at": _now(),
    }


def _all_candidates(campaign_root: str | Path) -> list[dict[str, Any]]:
    return load_jsonl(_campaign_path(campaign_root, "structured/candidates.jsonl"))


def latest_candidate(campaign_root: str | Path, candidate_key: str) -> dict[str, Any]:
    matches = [row for row in _all_candidates(campaign_root) if row.get("candidate_key") == candidate_key]
    if not matches:
        raise ValueError(f"candidate not found: {candidate_key}")
    return matches[-1]


def _append_candidate(campaign_root: str | Path, candidate: dict[str, Any]) -> dict[str, Any]:
    candidate["updated_at"] = _now()
    append_jsonl(_campaign_path(campaign_root, "structured/candidates.jsonl"), candidate)
    return candidate


def record_list_card(campaign_root: str | Path, card: dict[str, Any]) -> dict[str, Any]:
    if not str(card.get("display_name") or "").strip():
        raise ValueError("display_name is required")
    enriched_card = dict(card)
    if not enriched_card.get("screenshot_hash"):
        enriched_card["screenshot_hash"] = screen_hash(json.dumps(enriched_card, ensure_ascii=False, sort_keys=True))
    candidate_key = build_candidate_key(enriched_card)
    candidate = _base_candidate(enriched_card, candidate_key)
    append_jsonl(_campaign_path(campaign_root, "raw/list-cards.jsonl"), enriched_card | {"candidate_key": candidate_key, "captured_at": _now()})
    append_jsonl(_campaign_path(campaign_root, "raw/screen-hashes.jsonl"), {
        "candidate_key": candidate_key,
        "page": "list",
        "screenshot_hash": enriched_card["screenshot_hash"],
        "captured_at": _now(),
    })
    append_jsonl(_campaign_path(campaign_root, "state/processed-cards.jsonl"), {
        "candidate_key": candidate_key,
        "stage": "list",
        "status": "captured",
        "captured_at": _now(),
    })
    return _append_candidate(campaign_root, candidate)


def record_detail_update(
    campaign_root: str | Path,
    candidate_key: str,
    detail_sections: dict[str, Any],
    recommendation: str,
    score: int,
    reasons: list[str],
    risks: list[str] | None = None,
) -> dict[str, Any]:
    if recommendation not in {"contact", "hold", "skip"}:
        raise ValueError("recommendation must be contact, hold, or skip")
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    candidate["detail_sections"] = dict(detail_sections)
    candidate["screening"] = dict(candidate.get("screening") or {})
    candidate["screening"].update({
        "detail_decision": recommendation,
        "score": int(score),
        "reasons": list(reasons),
        "risks": list(risks or []),
    })
    append_jsonl(_campaign_path(campaign_root, "raw/detail-pages.jsonl"), {
        "candidate_key": candidate_key,
        "detail_sections": detail_sections,
        "recommendation": recommendation,
        "score": int(score),
        "captured_at": _now(),
    })
    return _append_candidate(campaign_root, candidate)


def _live_contact_count(campaign_root: str | Path) -> int:
    return sum(1 for row in load_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl")) if row.get("mode") == "live_test" and row.get("contacted"))


def record_contact_decision(
    campaign_root: str | Path,
    candidate_key: str,
    mode: str,
    button_seen: bool,
    action_confirmed: bool,
    preset_message_auto_sent: bool = False,
) -> dict[str, Any]:
    if mode not in {"dry_run", "live_test"}:
        raise ValueError("mode must be dry_run or live_test")
    policy = validate_run_policy(load_json(_campaign_path(campaign_root, "run-policy.json"), default={}))
    if mode == "live_test":
        if not policy["allow_live_contact_test"]:
            raise ValueError("live contact test is not enabled")
        if not action_confirmed:
            raise ValueError("live contact requires action confirmation")
        if _live_contact_count(campaign_root) >= int(policy["live_contact_test_limit"]):
            raise ValueError("live contact test limit reached")

    decision = {
        "candidate_key": candidate_key,
        "mode": mode,
        "would_contact": True,
        "button_seen": bool(button_seen),
        "action_confirmed": bool(action_confirmed),
        "contacted": mode == "live_test",
        "preset_message_auto_sent": bool(preset_message_auto_sent),
        "decided_at": _now(),
    }
    append_jsonl(_campaign_path(campaign_root, "structured/contact-decisions.jsonl"), decision)

    candidate = dict(latest_candidate(campaign_root, candidate_key))
    candidate["contact"] = dict(candidate.get("contact") or {})
    candidate["contact"].update({
        "would_contact": True,
        "contact_mode": mode,
        "contacted": mode == "live_test",
        "live_contact_test": mode == "live_test",
        "contact_button_seen": bool(button_seen),
        "preset_message_auto_sent": bool(preset_message_auto_sent),
    })
    return _append_candidate(campaign_root, candidate)


def backfill_real_name(campaign_root: str | Path, candidate_key: str, real_name: str, source: str) -> dict[str, Any]:
    if source not in {"communication_page_after_live_contact_test", "manual_opened_communication_page"}:
        raise ValueError("invalid real name source")
    if not real_name.strip():
        raise ValueError("real_name is required")
    candidate = dict(latest_candidate(campaign_root, candidate_key))
    candidate["real_name"] = real_name.strip()
    candidate["real_name_status"] = "captured"
    candidate["real_name_source"] = source
    candidate["contact"] = dict(candidate.get("contact") or {})
    candidate["contact"]["communication_page_seen"] = True
    append_jsonl(_campaign_path(campaign_root, "raw/communication-pages.jsonl"), {
        "candidate_key": candidate_key,
        "real_name": real_name.strip(),
        "real_name_source": source,
        "captured_at": _now(),
    })
    return _append_candidate(campaign_root, candidate)
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit lifecycle and safety logic**

```bash
git add scripts/boss_app_sourcing.py tests/test_boss_app_sourcing.py
git commit -m "feat: add BOSS App candidate lifecycle"
```

---

### Task 4: Continuation Plans and Reports

**Files:**
- Modify: `scripts/boss_app_sourcing.py`
- Modify: `tests/test_boss_app_sourcing.py`

- [ ] **Step 1: Add failing tests for continuation and summary reports**

Append to `tests/test_boss_app_sourcing.py`:

```python
def test_write_continuation_plan_records_next_action(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-resume", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    plan = boss_app_sourcing.write_continuation_plan(
        root,
        stage="S4",
        status="blocked",
        reason="ui_template_drift",
        next_action="请用户手动回到 BOSS 推荐列表页后继续",
    )

    saved = read_json(root / "state/continuation-plan.json")
    assert saved == plan
    assert saved["reason"] == "ui_template_drift"
    assert saved["next_action"] == "请用户手动回到 BOSS 推荐列表页后继续"


def test_summarize_campaign_counts_candidates_contacts_and_real_names(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign(
        "boss-summary",
        "看 AI 产品",
        out_base=tmp_path,
        allow_live_contact_test=True,
        live_contact_test_limit=2,
    )
    root = Path(manifest["campaign_root"])
    a = boss_app_sourcing.record_list_card(root, {
        "display_name": "张先生",
        "current_title": "AI 产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("a"),
    })
    b = boss_app_sourcing.record_list_card(root, {
        "display_name": "李女士",
        "current_title": "算法产品",
        "screenshot_hash": boss_app_sourcing.screen_hash("b"),
    })
    boss_app_sourcing.record_detail_update(root, a["candidate_key"], {}, "contact", 88, ["强匹配"])
    boss_app_sourcing.record_contact_decision(root, a["candidate_key"], "live_test", True, True, True)
    boss_app_sourcing.backfill_real_name(root, a["candidate_key"], "张 XX", "communication_page_after_live_contact_test")
    boss_app_sourcing.record_detail_update(root, b["candidate_key"], {}, "skip", 42, ["学历不符"])

    summary = boss_app_sourcing.summarize_campaign(root)

    assert summary["candidate_count"] == 2
    assert summary["would_contact_count"] == 1
    assert summary["live_contact_count"] == 1
    assert summary["real_name_captured_count"] == 1
    assert summary["skip_count"] == 1
    assert (root / "reports/sourcing-summary.json").exists()
    text = (root / "reports/sourcing-summary.md").read_text(encoding="utf-8")
    assert "BOSS App 寻访摘要" in text
    assert "真实姓名补全：1" in text


def test_summarize_cli_prints_summary_json(tmp_path: Path, capsys) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-summary-cli", "看 AI 产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])

    exit_code = boss_app_sourcing.main(["summarize", "--campaign-root", str(root)])

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["campaign_root"] == str(root)
    assert summary["candidate_count"] == 0
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: FAIL because continuation and summary functions are not implemented.

- [ ] **Step 3: Implement continuation and summary functions**

Append these functions before `build_parser()`:

```python
def write_continuation_plan(
    campaign_root: str | Path,
    stage: str,
    status: str,
    reason: str,
    next_action: str,
) -> dict[str, Any]:
    plan = {
        "stage": stage,
        "status": status,
        "reason": reason,
        "next_action": next_action,
        "updated_at": _now(),
    }
    write_json(_campaign_path(campaign_root, "state/continuation-plan.json"), plan)
    append_jsonl(_campaign_path(campaign_root, "state/events.jsonl"), plan)
    return plan


def _latest_candidates_by_key(campaign_root: str | Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in _all_candidates(campaign_root):
        latest[str(row.get("candidate_key"))] = row
    return latest


def summarize_campaign(campaign_root: str | Path) -> dict[str, Any]:
    root = Path(campaign_root)
    candidates = list(_latest_candidates_by_key(root).values())
    decisions = load_jsonl(root / "structured/contact-decisions.jsonl")
    summary = {
        "campaign_root": str(root),
        "candidate_count": len(candidates),
        "detail_count": sum(1 for item in candidates if item.get("detail_sections")),
        "would_contact_count": sum(1 for item in candidates if (item.get("contact") or {}).get("would_contact")),
        "live_contact_count": sum(1 for item in candidates if (item.get("contact") or {}).get("contacted")),
        "real_name_captured_count": sum(1 for item in candidates if item.get("real_name_status") == "captured"),
        "skip_count": sum(1 for item in candidates if (item.get("screening") or {}).get("detail_decision") == "skip"),
        "contact_decision_count": len(decisions),
        "updated_at": _now(),
    }
    write_json(root / "reports/sourcing-summary.json", summary)
    markdown = "\n".join([
        "# BOSS App 寻访摘要",
        "",
        f"- 候选人总数：{summary['candidate_count']}",
        f"- 详情采集：{summary['detail_count']}",
        f"- Would contact：{summary['would_contact_count']}",
        f"- Live-test 真实沟通：{summary['live_contact_count']}",
        f"- 真实姓名补全：{summary['real_name_captured_count']}",
        f"- 详情淘汰：{summary['skip_count']}",
        "",
    ])
    (root / "reports/sourcing-summary.md").write_text(markdown, encoding="utf-8")
    return summary
```

Modify `build_parser()`:

```python
    summarize_parser = subparsers.add_parser("summarize")
    summarize_parser.add_argument("--campaign-root", required=True)
```

Modify `main()` before the final `raise`:

```python
    if args.command == "summarize":
        summary = summarize_campaign(args.campaign_root)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
```

- [ ] **Step 4: Run focused tests and verify they pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit continuation and report logic**

```bash
git add scripts/boss_app_sourcing.py tests/test_boss_app_sourcing.py
git commit -m "feat: add BOSS App sourcing reports"
```

---

### Task 5: CLI Coverage and Workflow Smoke Verification

**Files:**
- Modify: `tests/test_boss_app_sourcing.py`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Add CLI smoke test for full non-UI flow**

Append to `tests/test_boss_app_sourcing.py`:

```python
def test_non_ui_flow_can_initialize_record_and_summarize(tmp_path: Path) -> None:
    manifest = boss_app_sourcing.init_campaign("boss-flow", "优先大模型产品", out_base=tmp_path)
    root = Path(manifest["campaign_root"])
    candidate = boss_app_sourcing.record_list_card(root, {
        "display_name": "陈先生",
        "current_company": "大模型公司",
        "current_title": "产品经理",
        "education": "本科",
        "city": "北京",
        "expected_salary": "30-50K",
        "screenshot_hash": boss_app_sourcing.screen_hash("flow-card"),
    })
    boss_app_sourcing.record_detail_update(
        root,
        candidate["candidate_key"],
        {"work_experience": [{"company": "大模型公司", "title": "产品经理"}]},
        recommendation="contact",
        score=90,
        reasons=["公司和职位匹配"],
    )
    boss_app_sourcing.record_contact_decision(
        root,
        candidate["candidate_key"],
        mode="dry_run",
        button_seen=True,
        action_confirmed=False,
    )

    summary = boss_app_sourcing.summarize_campaign(root)

    assert summary["candidate_count"] == 1
    assert summary["detail_count"] == 1
    assert summary["would_contact_count"] == 1
    assert summary["live_contact_count"] == 0
```

- [ ] **Step 2: Run all focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_app_sourcing.py tests/test_agent_architecture.py tests/test_script_hygiene.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: PASS, with any existing warning explicitly reported.

- [ ] **Step 4: Run Python compile check**

Run:

```bash
.venv/bin/python -m py_compile scripts/boss_app_sourcing.py
```

Expected: exit code 0.

- [ ] **Step 5: Run diff hygiene check**

Run:

```bash
git diff --check
```

Expected: exit code 0.

- [ ] **Step 6: Update task ledger with evidence**

Modify `tasks/todo.md` under the BOSS active task:

```markdown
当前结果：
- 已新增 BOSS App canonical skill/workflow、Claude adapter、`computer.operate` 能力合同。
- 已新增 `scripts/boss_app_sourcing.py`，覆盖任务初始化、候选人生命周期、dry-run 联系决策、live-test 安全门、真实姓名回填、continuation plan 和摘要报告。
- 验证：`tests/test_boss_app_sourcing.py tests/test_agent_architecture.py tests/test_script_hygiene.py` 通过；全量 `.venv/bin/python -m pytest tests -q` 通过；`py_compile` 和 `git diff --check` 通过。
```

- [ ] **Step 7: Commit final implementation**

```bash
git add agents/capabilities.md agents/skills/boss-app-recommendation-sourcing/SKILL.md agents/workflows/boss-app-recommendation-sourcing/AGENT.md .claude/skills/boss-app-recommendation-sourcing/SKILL.md scripts/boss_app_sourcing.py tests/test_boss_app_sourcing.py tests/test_agent_architecture.py docs/dev/script-inventory.md tasks/todo.md
git commit -m "feat: implement BOSS App recommendation sourcing workflow"
```

---

## Plan Self-Review

- Spec coverage: The plan covers App-only execution, no `platform-match` execution reuse, structured contracts, independent campaign root, structured text plus screenshot hash, dry-run contact decisions, small live-test with action-time confirmation, real-name backfill, continuation plan, reports, tests, and architecture registration.
- Placeholder scan: The plan contains no incomplete implementation markers.
- Type consistency: Function names used in tests match the implementation snippets: `init_campaign`, `screen_hash`, `build_candidate_key`, `record_list_card`, `record_detail_update`, `record_contact_decision`, `backfill_real_name`, `write_continuation_plan`, `summarize_campaign`, and `main`.
- Execution boundary: The Python helper does not click or read the BOSS App. UI operation stays in the canonical workflow via `computer.operate`, mapped by the runtime adapter to Computer Use.
