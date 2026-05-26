# 脉脉无人值守 Campaign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建产品化、可恢复的脉脉寻访 campaign 工作流：从寻访业务需求出发，生成经确认的实施计划，通过现有门禁执行列表搜索和详情采集，完成人选排序，并交付本地与飞书产物，执行期间不要求负责人盯屏。

**Architecture:** 新增项目内 skill 和 canonical workflow 作为业务入口，再围绕现有 `maimai_ai_infra_*`、`maimai_detail_*`、`talent_sync.py` 增加薄 Python 胶水层。编排器只负责状态、预算、重试、中断报告、飞书 IM 通知和恢复决策；搜索、导入、评分、详情和报告逻辑继续以现有脚本为事实来源。

**Tech Stack:** Python 3.11、argparse、pathlib、subprocess、JSON/JSONL、现有 SQLite/TalentDB API、Chrome/Edge 启动参数、CDP endpoint health check、`lark-cli`、pytest。

---

## 范围护栏

- 实施本计划时不运行真实脉脉请求。真实阶段用单元测试、合成 fixture 或已有采集产物 replay 覆盖。
- 自动化测试不启动浏览器。浏览器 bootstrap 测试只断言启动参数和 mocked process 行为。
- 测试中不发布飞书文档、表格或 IM 消息。飞书相关测试使用 `--dry-run`、fake command runner 或生成命令 manifest。
- 真实候选人、raw capture 和 campaign DB 保留在 `data/campaigns/<campaign_id>/`；这些产物不提交。
- 500 次请求预算只统计列表搜索请求。详情请求由 health check、详情 pack 大小、停机规则和间隔设置约束。

## 文件结构

新增：

- `skills/maimai-talent-search-campaign/SKILL.md` - business-facing skill for requirement extraction, missing-info questions, and campaign artifact creation instructions.
- `agents/workflows/maimai-unattended-campaign/AGENT.md` - canonical workflow defining stages, state files, commands, safety stops, resume rules, and preauthorization boundaries.
- `templates/maimai-campaign/outreach-queue-fields.json` - standard outreach queue fields for CSV and Feishu delivery.
- `scripts/maimai_cdp_browser_bootstrap.py` - Chrome/Edge bootstrap CLI for `data/session/maimai-cdp-profile`, port `9888`, extension loading, and Maimai home page launch.
- `scripts/maimai_search_live_standardize.py` - converts search live-run JSON into canonical `raw/search/unit-*/page-*.json`.
- `scripts/campaign_notify.py` - Feishu IM notification helper with dry-run, test-message, idempotency key, and local manifest.
- `scripts/feishu_delivery_package.py` - formalized Feishu delivery helper for summary doc, candidate sheet, and outreach queue sheet.
- `scripts/maimai_campaign_orchestrator.py` - thin resumable state machine and command dispatcher.
- `tests/test_maimai_talent_search_campaign_skill.py` - static contract tests for the skill and workflow.
- `tests/test_maimai_cdp_browser_bootstrap.py` - bootstrap argument and process tests.
- `tests/test_maimai_search_live_standardize.py` - live-run to canonical raw tests.
- `tests/test_campaign_notify.py` - Feishu IM command and safety tests.
- `tests/test_feishu_delivery_package.py` - Feishu delivery dry-run tests.
- `tests/test_maimai_campaign_orchestrator.py` - state, policy, budget, wave split, resume, and command wiring tests.

修改：

- `scripts/maimai_ai_infra_detail_plan.py` - add optional `--pack-size` support so generated detail packs are capped at 100 contacts when requested.
- `tests/test_maimai_ai_infra_detail_plan.py` - add pack-size contract tests.
- `tasks/todo.md` - record implementation planning and review.

## Task 1: Skill, Workflow, and Outreach Template Contracts

**Files:**
- Create: `skills/maimai-talent-search-campaign/SKILL.md`
- Create: `agents/workflows/maimai-unattended-campaign/AGENT.md`
- Create: `templates/maimai-campaign/outreach-queue-fields.json`
- Create: `tests/test_maimai_talent_search_campaign_skill.py`

- [ ] **Step 1: Write static contract tests**

Add `tests/test_maimai_talent_search_campaign_skill.py`:

```python
from pathlib import Path
import json


SKILL = Path("skills/maimai-talent-search-campaign/SKILL.md")
WORKFLOW = Path("agents/workflows/maimai-unattended-campaign/AGENT.md")
OUTREACH_TEMPLATE = Path("templates/maimai-campaign/outreach-queue-fields.json")


def test_skill_extracts_first_and_asks_only_missing_fields():
    text = SKILL.read_text(encoding="utf-8")
    assert "优先从调用提示词、JD、职位描述或粘贴内容中自动抽取" in text
    assert "只对缺失或冲突的信息提问" in text
    assert "冷启动" in text
    assert "关键词包" in text
    assert "停止阈值" in text


def test_skill_bakes_in_confirmed_defaults():
    text = SKILL.read_text(encoding="utf-8")
    assert "每日搜索请求预算：500" in text
    assert "不包括详情请求" in text
    assert "搜索 wave 每组不超过 50 页" in text
    assert "详情 pack 每组上限 100 人" in text
    assert "只对 A/B 档人选抓详情" in text
    assert "本地 Markdown 报告、CSV、飞书云文档、飞书多维表格" in text


def test_workflow_keeps_live_safety_boundary_and_resume_sources():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "不自动导航、刷新、点击已进入执行态的脉脉业务页面" in text
    assert "raw/search/unit-" in text
    assert "raw/detail-live/<pack_id>/job-" in text
    assert "state/import-ledger.jsonl" in text
    assert "blocked_notification_failed" in text


def test_outreach_template_has_execution_fields():
    data = json.loads(OUTREACH_TEMPLATE.read_text(encoding="utf-8"))
    names = [field["name"] for field in data["fields"]]
    assert names[:5] == ["owner", "status", "last_touch_at", "next_followup_at", "notes"]
    assert "priority" in names
    assert "recommendation_label" in names
    assert "profile_url" in names
```

- [ ] **Step 2: Run tests and verify they fail because files do not exist**

Run:

```bash
python -m pytest tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: FAIL with `FileNotFoundError` for the new skill, workflow, or template.

- [ ] **Step 3: Create the skill entry**

Create `skills/maimai-talent-search-campaign/SKILL.md` with these required sections and wording:

```markdown
---
name: maimai-talent-search-campaign
description: "脉脉无人值守寻访 campaign：从寻访业务需求/JD 生成实施计划、创建 campaign artifacts，并把执行交给 maimai-unattended-campaign workflow。"
---

# 脉脉无人值守寻访 Campaign

## 入口边界

优先从调用提示词、JD、职位描述或粘贴内容中自动抽取目标岗位、业务方向、资深度、交付数量、地域、公司池、岗位词、技术关键词和排除条件。只对缺失或冲突的信息提问；不要重复询问已经可从输入中抽取并可让负责人确认的信息。

本 skill 不直接执行真实脉脉请求，不写主库 `data/talent.db`，不上传 raw capture 或 SQLite DB。真实执行必须交给 `agents/workflows/maimai-unattended-campaign/AGENT.md`。

## 固定默认值

- 每日搜索请求预算：500 次；该预算只统计列表搜索请求，不包括详情请求。
- 搜索 wave 每组不超过 50 页。
- 详情预算不设总人数上限，只对 A/B 档人选抓详情。
- 详情 pack 每组上限 100 人。
- 交付格式：本地 Markdown 报告、CSV、飞书云文档、飞书多维表格。
- 外联队列字段使用 `templates/maimai-campaign/outreach-queue-fields.json`。

## 提问规则

每个问题必须说明为什么需要该信息，并解释问题里的业务术语：

- 冷启动：本轮 campaign 不依赖主库历史候选人，从独立 campaign DB 和本轮搜索 raw 开始。负责人没有明确指定续跑历史 campaign 时，默认冷启动。
- 关键词包：一组会组合到搜索条件里的技术词，例如大模型训练、分布式训练、推理框架、GPU、算子。JD 技术栈足够明确时自动生成。
- 停止阈值：在结果明显不足、已达到交付目标或平台出现安全信号时触发停机或转阶段的规则。默认保留平台安全停机和达到足够 A/B 候选后进入详情。

## 输出文件

确认需求后，在 `data/campaigns/<campaign_id>/` 写入：

- `requirements.json`
- `strategy.json`
- `run-policy.json`
- `search-implementation-plan.md`
- `campaign-manifest.json`

`run-policy.json` 必须包含 `daily_search_request_budget=500`、`search_wave_max_pages=50`、`detail_pack_max_contacts=100`、`detail_target_grades=["A","B"]`、`notify_channel="feishu_im"`、`allow_main_db_write=false`。
```

- [ ] **Step 4: Create the canonical workflow**

Create `agents/workflows/maimai-unattended-campaign/AGENT.md` with sections for:

```markdown
---
name: maimai-unattended-campaign
description: "脉脉长任务 campaign canonical workflow。运行时必须先读本文件，再调用项目脚本。"
---

# maimai-unattended-campaign 工作流

## 核心边界

无人值守表示无需负责人在屏幕前监控；遇到登录、验证码、安全页、403、429、432、非 JSON、HTML 响应、模板漂移或详情 partial capture 时停止、记录断点并通知负责人。

真实执行阶段不自动导航、刷新、点击已进入执行态的脉脉业务页面；不使用 CDP `Runtime.evaluate` 启动真实详情抓取；不让扩展 popup、side panel、service worker 直接请求脉脉业务接口。

## 阶段

S0 requirement_confirmed -> S1 browser_bootstrap -> S2 compile_plan -> S3 search_preflight -> S4 search_live -> S5 import_wave -> S6 list_rank -> S7 detail_pack -> S8 detail_health -> S9 detail_live -> S10 detail_import -> S11 detailed_rank -> S12 local_delivery -> S13 feishu_delivery。

## 事实来源

- 搜索恢复以 `raw/search/unit-*/page-*.json` 为事实来源。
- 详情恢复以 `raw/detail-live/<pack_id>/job-*.json` 为事实来源。
- Wave apply 和 detail apply 以 `state/import-ledger.jsonl` 为防重事实来源。
- 中断恢复命令写入 `state/continuation-plan.json`。

## 通知

第一版通知接入飞书 IM。中断时写 `reports/interruption-*.json` 和 `state/events.jsonl`，再调用 `scripts/campaign_notify.py`。通知失败时进入 `blocked_notification_failed`，不继续真实平台请求。
```

- [ ] **Step 5: Create the outreach queue field template**

Create `templates/maimai-campaign/outreach-queue-fields.json`:

```json
{
  "schema": "maimai_outreach_queue_fields_v1",
  "fields": [
    {"name": "owner", "label": "负责人", "type": "text", "required": false},
    {"name": "status", "label": "状态", "type": "select", "default": "待联系"},
    {"name": "last_touch_at", "label": "最后触达时间", "type": "date", "required": false},
    {"name": "next_followup_at", "label": "下次跟进时间", "type": "date", "required": false},
    {"name": "notes", "label": "备注", "type": "text", "required": false},
    {"name": "candidate_id", "label": "候选人 ID", "type": "text", "required": true},
    {"name": "name", "label": "姓名", "type": "text", "required": true},
    {"name": "priority", "label": "外联优先级", "type": "select", "required": true},
    {"name": "recommendation_label", "label": "推荐标签", "type": "select", "required": true},
    {"name": "evidence_summary", "label": "证据摘要", "type": "text", "required": true},
    {"name": "profile_url", "label": "Profile URL", "type": "url", "required": false}
  ]
}
```

- [ ] **Step 6: Run contract tests**

Run:

```bash
python -m pytest tests/test_maimai_talent_search_campaign_skill.py -q
```

Expected: `4 passed`.

- [ ] **Step 7: Commit Task 1**

```bash
git add skills/maimai-talent-search-campaign/SKILL.md agents/workflows/maimai-unattended-campaign/AGENT.md templates/maimai-campaign/outreach-queue-fields.json tests/test_maimai_talent_search_campaign_skill.py
git commit -m "feat: add maimai campaign skill workflow contracts"
```

## Task 2: CDP Browser Bootstrap CLI

**Files:**
- Create: `scripts/maimai_cdp_browser_bootstrap.py`
- Create: `tests/test_maimai_cdp_browser_bootstrap.py`

- [ ] **Step 1: Write bootstrap tests**

Add `tests/test_maimai_cdp_browser_bootstrap.py`:

```python
from pathlib import Path

from scripts.maimai_cdp_browser_bootstrap import BrowserLaunchConfig, build_browser_args, build_session_manifest


def test_build_browser_args_uses_confirmed_profile_port_extension_and_url(tmp_path: Path):
    config = BrowserLaunchConfig(
        browser=Path("C:/Chrome/chrome.exe"),
        profile=Path("data/session/maimai-cdp-profile"),
        remote_debugging_port=9888,
        extension=Path("extensions/maimai-scraper"),
        url="https://maimai.cn/",
    )

    args = build_browser_args(config)

    assert args[0] == str(config.browser)
    assert "--remote-debugging-port=9888" in args
    assert "--user-data-dir=data/session/maimai-cdp-profile" in args
    assert "--load-extension=extensions/maimai-scraper" in args
    assert args[-1] == "https://maimai.cn/"


def test_session_manifest_records_manual_handoff():
    manifest = build_session_manifest(
        profile=Path("data/session/maimai-cdp-profile"),
        remote_debugging_port=9888,
        extension=Path("extensions/maimai-scraper"),
        url="https://maimai.cn/",
    )

    assert manifest["cdp_url"] == "http://127.0.0.1:9888"
    assert manifest["manual_steps"] == ["login_maimai", "enter_talent_bank", "execute_one_search"]
    assert manifest["automation_boundary"] == "launch_only"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_maimai_cdp_browser_bootstrap.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement bootstrap argument builder and CLI**

Create `scripts/maimai_cdp_browser_bootstrap.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BrowserLaunchConfig:
    browser: Path
    profile: Path
    remote_debugging_port: int
    extension: Path
    url: str


def build_browser_args(config: BrowserLaunchConfig) -> list[str]:
    return [
        str(config.browser),
        f"--remote-debugging-port={config.remote_debugging_port}",
        f"--user-data-dir={config.profile.as_posix()}",
        f"--load-extension={config.extension.as_posix()}",
        "--no-first-run",
        "--no-default-browser-check",
        config.url,
    ]


def build_session_manifest(profile: Path, remote_debugging_port: int, extension: Path, url: str) -> dict[str, Any]:
    return {
        "schema": "maimai_cdp_browser_session_v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": profile.as_posix(),
        "remote_debugging_port": remote_debugging_port,
        "cdp_url": f"http://127.0.0.1:{remote_debugging_port}",
        "extension": extension.as_posix(),
        "url": url,
        "manual_steps": ["login_maimai", "enter_talent_bank", "execute_one_search"],
        "automation_boundary": "launch_only",
    }


def default_browser_candidates() -> list[Path]:
    return [
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
        Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
        Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
    ]


def find_browser(explicit: str | None = None) -> Path:
    if explicit:
        browser = Path(explicit)
        if browser.exists():
            return browser
        raise FileNotFoundError(str(browser))
    for browser in default_browser_candidates():
        if browser.exists():
            return browser
    raise FileNotFoundError("Chrome or Edge executable was not found")


def write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="启动脉脉 campaign 专用 CDP 浏览器")
    parser.add_argument("--browser")
    parser.add_argument("--profile", default="data/session/maimai-cdp-profile")
    parser.add_argument("--remote-debugging-port", type=int, default=9888)
    parser.add_argument("--extension", default="extensions/maimai-scraper")
    parser.add_argument("--url", default="https://maimai.cn/")
    parser.add_argument("--manifest-out", default="data/session/maimai-cdp-browser-session.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    config = BrowserLaunchConfig(
        browser=find_browser(args.browser),
        profile=Path(args.profile),
        remote_debugging_port=args.remote_debugging_port,
        extension=Path(args.extension),
        url=args.url,
    )
    manifest = build_session_manifest(config.profile, config.remote_debugging_port, config.extension, config.url)
    manifest["argv"] = build_browser_args(config)
    write_manifest(Path(args.manifest_out), manifest)
    if args.dry_run:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 0
    config.profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(build_browser_args(config), close_fds=True)
    print(f"opened {config.url} with CDP port {config.remote_debugging_port}")
    print("请人工登录脉脉，进入人才银行页面，并执行一次搜索。完成后运行 workflow health check。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run bootstrap tests**

Run:

```bash
python -m pytest tests/test_maimai_cdp_browser_bootstrap.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/maimai_cdp_browser_bootstrap.py tests/test_maimai_cdp_browser_bootstrap.py
git commit -m "feat: add maimai cdp browser bootstrap"
```

## Task 3: Search Live-Run Standardizer

**Files:**
- Create: `scripts/maimai_search_live_standardize.py`
- Create: `tests/test_maimai_search_live_standardize.py`

- [ ] **Step 1: Write standardizer tests**

Add `tests/test_maimai_search_live_standardize.py`:

```python
import json
from pathlib import Path

from scripts.maimai_ai_infra_campaign import ensure_campaign, load_completed_pages, page_raw_path
from scripts.maimai_search_live_standardize import standardize_live_run


def test_standardize_live_run_writes_successful_pages_to_canonical_raw(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps({
        "status": "completed",
        "run_id": "run-001",
        "batches": [
            {
                "batch_id": "unit-000001",
                "pages": [
                    {
                        "page": 1,
                        "ok": True,
                        "request": {"url": "/api/ent/v3/search/basic"},
                        "responseSummary": {"total": 1},
                        "responseData": {"data": {"contacts": [{"id": "p1", "name": "张三"}]}},
                        "contacts": [{"id": "p1", "name": "张三"}],
                    }
                ],
            }
        ],
    }, ensure_ascii=False), encoding="utf-8")

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 1
    raw = page_raw_path(campaign, "unit-000001", 1)
    payload = json.loads(raw.read_text(encoding="utf-8-sig"))
    assert payload["source_run"] == str(run_path)
    assert payload["contacts"][0]["name"] == "张三"
    assert load_completed_pages(campaign) == {("unit-000001", 1)}


def test_standardize_live_run_rejects_partial_or_failed_pages(tmp_path: Path):
    campaign = ensure_campaign(tmp_path / "campaign")
    run_path = tmp_path / "run.json"
    run_path.write_text(json.dumps({
        "status": "stopped",
        "stopReason": "captcha_api",
        "batches": [{"batch_id": "unit-000001", "pages": [{"page": 1, "ok": False, "contacts": []}]}],
    }), encoding="utf-8")

    result = standardize_live_run(campaign.root, run_path)

    assert result["written_pages"] == 0
    assert result["skipped_pages"][0]["reason"] == "page_not_ok"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_maimai_search_live_standardize.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement standardizer**

Create `scripts/maimai_search_live_standardize.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.maimai_ai_infra_campaign import ensure_campaign, mark_page_completed


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _page_payload(unit_id: str, page: dict[str, Any], run_path: Path, run: dict[str, Any]) -> dict[str, Any]:
    page_number = int(page["page"])
    contacts = page.get("contacts")
    if not isinstance(contacts, list):
        raise ValueError("page contacts must be a list")
    return {
        "unit_id": unit_id,
        "wave_id": run.get("wave_id") or run.get("gate") or "",
        "page": page_number,
        "source_run": str(run_path),
        "source_run_id": run.get("run_id"),
        "request": page.get("request") or {},
        "responseSummary": page.get("responseSummary") or {},
        "responseData": page.get("responseData"),
        "responseRawPreview": page.get("responseRawPreview") or "",
        "contacts": contacts,
    }


def standardize_live_run(campaign_root: str | Path, run_path: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    run_file = Path(run_path)
    run = _load_json(run_file)
    written_pages = 0
    skipped_pages: list[dict[str, Any]] = []
    for batch in run.get("batches") or []:
        if not isinstance(batch, dict):
            continue
        unit_id = str(batch.get("batch_id") or "")
        if not unit_id:
            skipped_pages.append({"reason": "missing_batch_id"})
            continue
        for page in batch.get("pages") or []:
            if not isinstance(page, dict):
                continue
            page_number = page.get("page")
            if page.get("ok") is not True:
                skipped_pages.append({"unit_id": unit_id, "page": page_number, "reason": "page_not_ok"})
                continue
            payload = _page_payload(unit_id, page, run_file, run)
            mark_page_completed(paths, unit_id, int(payload["page"]), payload)
            written_pages += 1
    return {
        "status": "standardized",
        "campaign_root": str(paths.root),
        "run": str(run_file),
        "written_pages": written_pages,
        "skipped_pages": skipped_pages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="标准化脉脉搜索 live-run 为 campaign 页级 raw")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)
    result = standardize_live_run(args.campaign_root, args.run)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run standardizer tests**

Run:

```bash
python -m pytest tests/test_maimai_search_live_standardize.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/maimai_search_live_standardize.py tests/test_maimai_search_live_standardize.py
git commit -m "feat: standardize maimai search live runs"
```

## Task 4: Detail Pack Size Cap

**Files:**
- Modify: `scripts/maimai_ai_infra_detail_plan.py`
- Modify: `tests/test_maimai_ai_infra_detail_plan.py`

- [ ] **Step 1: Add pack-size unit tests**

Append to `tests/test_maimai_ai_infra_detail_plan.py`:

```python
from scripts.maimai_ai_infra_detail_plan import compute_pack_count


def test_compute_pack_count_caps_detail_pack_size():
    assert compute_pack_count(total_contacts=0, pack_size=100) == 1
    assert compute_pack_count(total_contacts=100, pack_size=100) == 1
    assert compute_pack_count(total_contacts=101, pack_size=100) == 2
    assert compute_pack_count(total_contacts=596, pack_size=100) == 6
```

- [ ] **Step 2: Run the new test and verify it fails**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_detail_plan.py::test_compute_pack_count_caps_detail_pack_size -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `compute_pack_count`.

- [ ] **Step 3: Implement `compute_pack_count` and `--pack-size`**

Modify `scripts/maimai_ai_infra_detail_plan.py`:

```python
from math import ceil


def compute_pack_count(total_contacts: int, pack_size: int) -> int:
    if pack_size <= 0:
        raise ValueError("pack_size must be positive")
    if total_contacts <= 0:
        return 1
    return max(1, ceil(total_contacts / pack_size))
```

Change `build_ab_detail_packs` signature:

```python
def build_ab_detail_packs(
    campaign_root: str | Path,
    db_path: str | Path | None = None,
    waves: list[str] | None = None,
    out_dir: str | Path | None = None,
    pack_count: int = 4,
    pack_size: int | None = None,
) -> dict[str, Any]:
```

After `contacts.sort(key=_target_sort_key)`, add:

```python
    if pack_size is not None:
        pack_count = max(pack_count, compute_pack_count(len(contacts), pack_size))
```

Add CLI flag and pass it through:

```python
    build.add_argument("--pack-size", type=int)
```

```python
            pack_size=args.pack_size,
```

- [ ] **Step 4: Run detail plan tests**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_detail_plan.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit Task 4**

```bash
git add scripts/maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_plan.py
git commit -m "feat: cap maimai detail pack size"
```

## Task 5: Feishu IM Notification Helper

**Files:**
- Create: `scripts/campaign_notify.py`
- Create: `tests/test_campaign_notify.py`

- [ ] **Step 1: Write notification tests**

Add `tests/test_campaign_notify.py`:

```python
from scripts.campaign_notify import build_message_text, build_send_argv


def test_build_message_text_includes_checkpoint_and_resume_command():
    text = build_message_text({
        "campaign_id": "ai-infra-demo",
        "blocked_stage": "detail_live",
        "reason": "captcha_api",
        "completed": 46,
        "total": 149,
        "evidence_file": "data/campaigns/demo/reports/interruption.json",
        "resume_command": "python -m scripts.maimai_campaign_orchestrator resume --campaign-root data/campaigns/demo",
    })

    assert "ai-infra-demo" in text
    assert "detail_live" in text
    assert "captcha_api" in text
    assert "46/149" in text
    assert "resume --campaign-root" in text


def test_build_send_argv_uses_lark_messages_send_dry_run_and_idempotency_key():
    argv = build_send_argv(
        identity="bot",
        chat_id="oc_xxx",
        user_id="",
        text="Campaign blocked",
        idempotency_key="ai-infra-demo-detail_live-captcha",
        dry_run=True,
    )

    assert argv[:3] == ["lark-cli", "im", "+messages-send"]
    assert "--as" in argv and "bot" in argv
    assert "--chat-id" in argv and "oc_xxx" in argv
    assert "--text" in argv and "Campaign blocked" in argv
    assert "--idempotency-key" in argv
    assert "--dry-run" in argv
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_campaign_notify.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement notification helper**

Create `scripts/campaign_notify.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any


def build_message_text(event: dict[str, Any]) -> str:
    completed = event.get("completed", 0)
    total = event.get("total", 0)
    return "\n".join([
        f"Campaign blocked: {event.get('campaign_id', '')}",
        f"Stage: {event.get('blocked_stage', '')}",
        f"Reason: {event.get('reason', '')}",
        f"Progress: {completed}/{total}",
        f"Evidence: {event.get('evidence_file', '')}",
        f"Action: {event.get('operator_action', '处理平台验证后回到人才银行页面，不刷新页面，再运行恢复命令')}",
        f"Resume: {event.get('resume_command', '')}",
    ])


def build_send_argv(
    identity: str,
    chat_id: str,
    user_id: str,
    text: str,
    idempotency_key: str,
    dry_run: bool,
) -> list[str]:
    if identity not in {"bot", "user"}:
        raise ValueError("identity must be bot or user")
    if bool(chat_id) == bool(user_id):
        raise ValueError("exactly one of chat_id or user_id is required")
    argv = ["lark-cli", "im", "+messages-send", "--as", identity]
    if chat_id:
        argv.extend(["--chat-id", chat_id])
    else:
        argv.extend(["--user-id", user_id])
    argv.extend(["--text", text, "--idempotency-key", idempotency_key])
    if dry_run:
        argv.append("--dry-run")
    return argv


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="发送 campaign 中断飞书 IM 通知")
    parser.add_argument("--event", required=True)
    parser.add_argument("--identity", choices=["bot", "user"], default="bot")
    parser.add_argument("--chat-id", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    event = load_json(args.event)
    text = build_message_text(event)
    key = f"{event.get('campaign_id', 'campaign')}-{event.get('blocked_stage', 'stage')}-{event.get('reason', 'reason')}"
    cmd = build_send_argv(args.identity, args.chat_id, args.user_id, text, key, args.dry_run)
    if args.dry_run:
        print(json.dumps({"argv": cmd, "text": text}, ensure_ascii=False, indent=2))
        return 0
    completed = subprocess.run(cmd, check=False, text=True, capture_output=True)
    print(completed.stdout)
    if completed.returncode != 0:
        print(completed.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run notification tests**

Run:

```bash
python -m pytest tests/test_campaign_notify.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/campaign_notify.py tests/test_campaign_notify.py
git commit -m "feat: add campaign feishu im notifications"
```

## Task 6: Feishu Delivery Package Helper

**Files:**
- Create: `scripts/feishu_delivery_package.py`
- Create: `tests/test_feishu_delivery_package.py`

- [ ] **Step 1: Write Feishu delivery dry-run tests**

Add `tests/test_feishu_delivery_package.py`:

```python
import csv
import json
from pathlib import Path

from scripts.feishu_delivery_package import build_delivery_manifest


def test_build_delivery_manifest_excludes_raw_and_db_paths(tmp_path: Path):
    final_report = tmp_path / "final-report.json"
    final_report.write_text(json.dumps({"campaign_id": "demo", "summary": {"final_recommended_count": 2}}), encoding="utf-8")
    outreach_csv = tmp_path / "outreach.csv"
    with outreach_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "name", "priority", "recommendation_label", "profile_url"])
        writer.writeheader()
        writer.writerow({"candidate_id": "1", "name": "张三", "priority": "P0", "recommendation_label": "强推荐", "profile_url": "https://example.com"})
    audit_json = tmp_path / "audit.json"
    audit_json.write_text(json.dumps({"issue_counts": {}, "duplicate_candidate_ids": []}), encoding="utf-8")

    manifest = build_delivery_manifest(
        campaign_root=tmp_path,
        final_report=final_report,
        outreach_csv=outreach_csv,
        audit_json=audit_json,
        dry_run=True,
    )

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["dry_run"] is True
    assert "sqlite" not in serialized.lower()
    assert "raw/search" not in serialized
    assert "raw/detail" not in serialized
    assert manifest["commands"][0][:3] == ["lark-cli", "docs", "+create"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_feishu_delivery_package.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement dry-run manifest builder and CLI shape**

Create `scripts/feishu_delivery_package.py` with:

```python
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_delivery_manifest(
    campaign_root: str | Path,
    final_report: str | Path,
    outreach_csv: str | Path,
    audit_json: str | Path,
    dry_run: bool,
) -> dict[str, Any]:
    root = Path(campaign_root)
    report = _load_json(Path(final_report))
    outreach_rows = _read_csv(Path(outreach_csv))
    audit = _load_json(Path(audit_json))
    summary_xml = root / "reports" / "feishu-delivery-summary.xml"
    candidate_csv = root / "reports" / "feishu-candidates.csv"
    outreach_source_csv = root / "reports" / "feishu-outreach-queue.csv"
    commands = [
        ["lark-cli", "docs", "+create", "--api-version", "v2", "--parent-position", "my_library", "--content", f"@{summary_xml.as_posix()}"],
        ["lark-cli", "sheets", "+create", "--title", f"{report.get('campaign_id', root.name)} candidates"],
        ["lark-cli", "sheets", "+create", "--title", f"{report.get('campaign_id', root.name)} outreach queue"],
    ]
    if dry_run:
        for command in commands:
            command.append("--dry-run")
    return {
        "schema": "maimai_feishu_delivery_package_v1",
        "campaign_root": root.as_posix(),
        "campaign_id": report.get("campaign_id", root.name),
        "dry_run": dry_run,
        "source_counts": {
            "outreach_rows": len(outreach_rows),
            "audit_issues": audit.get("issue_counts", {}),
        },
        "generated_files": {
            "summary_xml": summary_xml.as_posix(),
            "candidate_csv": candidate_csv.as_posix(),
            "outreach_csv": outreach_source_csv.as_posix(),
        },
        "commands": commands,
        "excluded_inputs": ["sqlite_db", "sync_zip", "raw_capture", "raw_live_run"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成或发布脉脉 campaign 飞书交付包")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--final-report", required=True)
    parser.add_argument("--outreach-csv", required=True)
    parser.add_argument("--audit-json", required=True)
    parser.add_argument("--outreach-template", default="templates/maimai-campaign/outreach-queue-fields.json")
    parser.add_argument("--manifest-out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    manifest = build_delivery_manifest(args.campaign_root, args.final_report, args.outreach_csv, args.audit_json, args.dry_run)
    out = Path(args.manifest_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add source file generation and publish executor**

Add these functions to `scripts/feishu_delivery_package.py` and call `write_source_files(...)` before writing the manifest:

```python
def render_summary_xml(report: dict[str, Any], audit: dict[str, Any], outreach_rows: list[dict[str, str]]) -> str:
    campaign_id = str(report.get("campaign_id") or "maimai-campaign")
    recommended = report.get("summary", {}).get("final_recommended_count", "")
    issue_counts = json.dumps(audit.get("issue_counts", {}), ensure_ascii=False)
    return "\n".join([
        f"<title>{campaign_id} 飞书交付包</title>",
        "<h1>交付范围</h1>",
        "<p>本交付包只包含筛选后的报告、候选人表格和外联队列，不包含 SQLite DB、sync zip、raw capture 或 raw live run。</p>",
        "<h1>关键指标</h1>",
        f"<p>最终推荐人数：{recommended}</p>",
        f"<p>外联队列行数：{len(outreach_rows)}</p>",
        "<h1>质量审计</h1>",
        f"<pre>{issue_counts}</pre>",
    ])


def write_source_files(manifest: dict[str, Any], report: dict[str, Any], audit: dict[str, Any], outreach_rows: list[dict[str, str]]) -> None:
    generated = manifest["generated_files"]
    Path(generated["summary_xml"]).parent.mkdir(parents=True, exist_ok=True)
    Path(generated["summary_xml"]).write_text(render_summary_xml(report, audit, outreach_rows), encoding="utf-8")
    fieldnames = list(outreach_rows[0].keys()) if outreach_rows else ["candidate_id", "name", "priority", "recommendation_label", "profile_url"]
    for key in ["candidate_csv", "outreach_csv"]:
        with Path(generated[key]).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(outreach_rows)


def run_publish_commands(commands: list[list[str]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for command in commands:
        completed = subprocess.run(command, text=True, capture_output=True, check=False)
        results.append({
            "argv": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        })
        if completed.returncode != 0:
            break
    return results
```

Import `subprocess` at the top. When `--dry-run` is not supplied, call `run_publish_commands(manifest["commands"])`, save results under `manifest["publish_results"]`, and return nonzero if any command fails.

- [ ] **Step 5: Run Feishu delivery tests**

Run:

```bash
python -m pytest tests/test_feishu_delivery_package.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit Task 6**

```bash
git add scripts/feishu_delivery_package.py tests/test_feishu_delivery_package.py
git commit -m "feat: formalize maimai feishu delivery package"
```

## Task 7: Orchestrator Policy, State, and Wave Splitting

**Files:**
- Create: `scripts/maimai_campaign_orchestrator.py`
- Create: `tests/test_maimai_campaign_orchestrator.py`

- [ ] **Step 1: Write orchestrator policy tests**

Add `tests/test_maimai_campaign_orchestrator.py`:

```python
from scripts.maimai_campaign_orchestrator import (
    DEFAULT_RUN_POLICY,
    count_search_requests,
    split_search_units_into_live_waves,
)


def test_default_policy_counts_search_budget_only():
    assert DEFAULT_RUN_POLICY["daily_search_request_budget"] == 500
    assert DEFAULT_RUN_POLICY["search_wave_max_pages"] == 50
    assert DEFAULT_RUN_POLICY["detail_pack_max_contacts"] == 100
    assert count_search_requests({"stage": "search_live", "pages": 12}) == 12
    assert count_search_requests({"stage": "detail_live", "pages": 99}) == 0


def test_split_search_units_limits_each_live_wave_to_50_pages():
    units = [
        {"unit_id": f"unit-{i:06d}", "query": "ai", "max_pages": 3, "page_size": 30, "search_filters": {}}
        for i in range(1, 42)
    ]

    waves = split_search_units_into_live_waves(units, max_pages=50, daily_budget=500)

    assert len(waves) == 3
    assert [wave["page_count"] for wave in waves] == [48, 48, 27]
    assert all(wave["page_count"] <= 50 for wave in waves)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
python -m pytest tests/test_maimai_campaign_orchestrator.py -q
```

Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement policy constants and wave splitter**

Create `scripts/maimai_campaign_orchestrator.py` with the first core helpers:

```python
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_RUN_POLICY: dict[str, Any] = {
    "allow_live_search": True,
    "allow_campaign_db_auto_apply_after_clean_dry_run": True,
    "allow_detail_live_after_health_ok": True,
    "allow_detail_campaign_db_auto_apply_after_clean_dry_run": True,
    "allow_main_db_write": False,
    "allow_feishu_delivery_publish": True,
    "daily_search_request_budget": 500,
    "search_wave_max_pages": 50,
    "detail_pack_max_contacts": 100,
    "detail_target_grades": ["A", "B"],
    "delivery_outputs": ["local_md", "csv", "feishu_doc", "feishu_base"],
    "notify_channel": "feishu_im",
    "notify_identity": "bot",
    "stop_on_platform_security_signal": True,
    "max_auto_retries": 3,
}


def count_search_requests(event: dict[str, Any]) -> int:
    if event.get("stage") != "search_live":
        return 0
    return int(event.get("pages") or 0)


def _unit_pages(unit: dict[str, Any]) -> int:
    return max(1, int(unit.get("max_pages") or 1))


def split_search_units_into_live_waves(
    units: list[dict[str, Any]],
    max_pages: int,
    daily_budget: int,
    used_today: int = 0,
) -> list[dict[str, Any]]:
    waves: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_pages = 0
    remaining = max(0, daily_budget - used_today)
    for unit in units:
        pages = _unit_pages(unit)
        if pages > max_pages:
            raise ValueError(f"single unit exceeds max_pages: {unit.get('unit_id')}")
        if current and current_pages + pages > max_pages:
            waves.append({"wave_id": f"search-wave-{len(waves) + 1:03d}", "page_count": current_pages, "batches": current})
            current = []
            current_pages = 0
        if current_pages + pages > remaining:
            break
        batch = dict(unit)
        batch["start_page"] = 1
        batch["max_page"] = pages
        current.append(batch)
        current_pages += pages
    if current:
        waves.append({"wave_id": f"search-wave-{len(waves) + 1:03d}", "page_count": current_pages, "batches": current})
    return waves
```

- [ ] **Step 4: Run orchestrator policy tests**

Run:

```bash
python -m pytest tests/test_maimai_campaign_orchestrator.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Add state writing helpers and CLI skeleton**

Extend `scripts/maimai_campaign_orchestrator.py`:

```python
def load_json(path: str | Path, default: Any = None) -> Any:
    file = Path(path)
    if not file.exists():
        return default
    return json.loads(file.read_text(encoding="utf-8-sig"))


def write_json(path: str | Path, data: Any) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_event(campaign_root: str | Path, event: dict[str, Any]) -> None:
    events = Path(campaign_root) / "state" / "events.jsonl"
    events.parent.mkdir(parents=True, exist_ok=True)
    event = {"at": datetime.now().isoformat(timespec="seconds"), **event}
    with events.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def write_stage_state(campaign_root: str | Path, stage: str, status: str, extra: dict[str, Any] | None = None) -> None:
    state = {"stage": stage, "status": status, "updated_at": datetime.now().isoformat(timespec="seconds")}
    if extra:
        state.update(extra)
    write_json(Path(campaign_root) / "state" / "stage-state.json", state)
    append_event(campaign_root, state)
```

Add a parser with `status`, `plan-waves`, and `resume` subcommands. The first implementation may print state and generate wave plans without running live commands.

- [ ] **Step 6: Commit Task 7**

```bash
git add scripts/maimai_campaign_orchestrator.py tests/test_maimai_campaign_orchestrator.py
git commit -m "feat: add maimai campaign orchestrator policy"
```

## Task 8: Orchestrator Command Wiring, Resume, and Blocking

**Files:**
- Modify: `scripts/maimai_campaign_orchestrator.py`
- Modify: `tests/test_maimai_campaign_orchestrator.py`

- [ ] **Step 1: Add fake-runner command wiring tests**

Append to `tests/test_maimai_campaign_orchestrator.py`:

```python
from scripts.maimai_campaign_orchestrator import build_stage_commands


def test_build_stage_commands_uses_existing_scripts_and_standardizer():
    commands = build_stage_commands(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy=DEFAULT_RUN_POLICY,
    )

    flattened = [" ".join(command) for command in commands]
    assert any("maimai_ai_infra_search_plan" in command for command in flattened)
    assert any("maimai_ai_infra_search_live_gate" in command for command in flattened)
    assert any("maimai_search_live_standardize" in command for command in flattened)
    assert any("maimai_ai_infra_pipeline" in command and "run-campaign" in command for command in flattened)
    assert any("maimai_ai_infra_detail_plan" in command and "--pack-size 100" in command for command in flattened)
    assert any("campaign_notify" in command for command in flattened)


def test_blocked_continuation_plan_contains_resume_command(tmp_path):
    from scripts.maimai_campaign_orchestrator import write_blocked_continuation

    plan = write_blocked_continuation(
        campaign_root=tmp_path,
        stage="detail_live",
        reason="captcha_api",
        evidence_file="reports/interruption.json",
    )

    assert plan["blocked_stage"] == "detail_live"
    assert plan["reason"] == "captcha_api"
    assert "maimai_campaign_orchestrator resume" in plan["resume_command"]
    assert (tmp_path / "state" / "continuation-plan.json").exists()
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
python -m pytest tests/test_maimai_campaign_orchestrator.py -q
```

Expected: FAIL because `build_stage_commands` and `write_blocked_continuation` do not exist.

- [ ] **Step 3: Implement command builders and continuation writer**

Add to `scripts/maimai_campaign_orchestrator.py`:

```python
def build_stage_commands(campaign_root: str, strategy: str, policy: dict[str, Any]) -> list[list[str]]:
    root = Path(campaign_root)
    return [
        ["python", "-m", "scripts.maimai_ai_infra_search_plan", "--config", strategy, "--out", str(root / "search-plan.json"), "--out-units", str(root / "search-units.jsonl")],
        ["python", "scripts/maimai_ai_infra_search_runner.py", "--dry-run-template-only", "--campaign-root", campaign_root, "--units", str(root / "search-units.jsonl"), "--resume", "--max-runtime-minutes", "180"],
        ["python", "-m", "scripts.maimai_ai_infra_search_live_gate", "--plan", str(root / "raw" / "search-live-runs" / "wave-plan.json"), "--out", str(root / "raw" / "search-live-runs" / "run.json"), "--cdp-url", "http://127.0.0.1:9888"],
        ["python", "-m", "scripts.maimai_search_live_standardize", "--campaign-root", campaign_root, "--run", str(root / "raw" / "search-live-runs" / "run.json")],
        ["python", "-m", "scripts.maimai_ai_infra_pipeline", "run-campaign", "--campaign-root", campaign_root, "--config", strategy, "--wave", "wave-001", "--db", str(root / "talent.db")],
        ["python", "-m", "scripts.maimai_ai_infra_rank", "--db", str(root / "talent.db"), "--config", strategy, "--mode", "list", "--out-json", str(root / "reports" / "list-rank.json"), "--out-md", str(root / "reports" / "list-rank.md")],
        ["python", "-m", "scripts.maimai_ai_infra_detail_plan", "build-ab-packs", "--campaign-root", campaign_root, "--pack-size", str(policy["detail_pack_max_contacts"])],
        ["python", "-m", "scripts.campaign_notify", "--event", str(root / "state" / "continuation-plan.json"), "--identity", str(policy.get("notify_identity", "bot")), "--dry-run"],
    ]


def write_blocked_continuation(campaign_root: str | Path, stage: str, reason: str, evidence_file: str) -> dict[str, Any]:
    root = Path(campaign_root)
    plan = {
        "campaign_id": root.name,
        "blocked_stage": stage,
        "reason": reason,
        "evidence_file": evidence_file,
        "safe_to_resume_after": "负责人处理平台验证后回到人才银行页面，确认页面 health clean",
        "resume_command": f"python -m scripts.maimai_campaign_orchestrator resume --campaign-root {root.as_posix()}",
    }
    write_json(root / "state" / "continuation-plan.json", plan)
    write_stage_state(root, stage, "blocked", {"reason": reason, "evidence_file": evidence_file})
    return plan
```

- [ ] **Step 4: Add subprocess runner with retry classification**

Add:

```python
@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def is_retriable_error(text: str) -> bool:
    needles = ["Connection timed out", "temporarily unavailable", "file is being used by another process"]
    return any(needle in text for needle in needles)


def run_command(argv: list[str]) -> CommandResult:
    completed = subprocess.run(argv, text=True, capture_output=True, check=False)
    return CommandResult(argv=argv, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr)
```

Add tests for `is_retriable_error("Connection timed out") is True` and `is_retriable_error("captcha_api") is False`.

- [ ] **Step 5: Run orchestrator tests**

Run:

```bash
python -m pytest tests/test_maimai_campaign_orchestrator.py -q
```

Expected: all orchestrator tests pass.

- [ ] **Step 6: Commit Task 8**

```bash
git add scripts/maimai_campaign_orchestrator.py tests/test_maimai_campaign_orchestrator.py
git commit -m "feat: wire maimai campaign orchestrator stages"
```

## Task 9: Replay Verification, Docs, and Final Review

**Files:**
- Modify: `tasks/todo.md`
- Modify: `docs/superpowers/specs/2026-05-19-maimai-unattended-campaign-design.md` if implementation reveals a concrete contract mismatch.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_maimai_talent_search_campaign_skill.py tests/test_maimai_cdp_browser_bootstrap.py tests/test_maimai_search_live_standardize.py tests/test_campaign_notify.py tests/test_feishu_delivery_package.py tests/test_maimai_campaign_orchestrator.py -q
```

Expected: all focused tests pass.

- [ ] **Step 2: Run related regression tests**

Run:

```bash
python -m pytest tests/test_maimai_ai_infra_campaign.py tests/test_maimai_ai_infra_search_live_gate.py tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_delivery_report.py tests/test_maimai_ai_infra_outreach_export.py -q
```

Expected: all related regression tests pass.

- [ ] **Step 3: Run full regression**

Run:

```bash
python -m pytest tests scripts -q
```

Expected: full suite passes. Existing unrelated warning from `scripts/test_boss.py` is acceptable if it remains the only warning.

- [ ] **Step 4: Run syntax and whitespace checks**

Run:

```bash
python -m py_compile scripts/maimai_cdp_browser_bootstrap.py scripts/maimai_search_live_standardize.py scripts/campaign_notify.py scripts/feishu_delivery_package.py scripts/maimai_campaign_orchestrator.py
git diff --check
```

Expected: both commands pass.

- [ ] **Step 5: Update `tasks/todo.md` review**

Add a Review entry containing:

- Implemented files and their responsibilities.
- Focused, related, and full regression results.
- Statement that no live Maimai requests were run during tests.
- Statement that Feishu IM and delivery tests used dry-run or fake command runners.
- Remaining operational setup for Feishu IM: target `chat_id` or `user_id`, bot membership, scopes, and test message.

- [ ] **Step 6: Final commit**

```bash
git add skills/maimai-talent-search-campaign/SKILL.md agents/workflows/maimai-unattended-campaign/AGENT.md templates/maimai-campaign/outreach-queue-fields.json scripts/maimai_cdp_browser_bootstrap.py scripts/maimai_search_live_standardize.py scripts/campaign_notify.py scripts/feishu_delivery_package.py scripts/maimai_campaign_orchestrator.py scripts/maimai_ai_infra_detail_plan.py tests/test_maimai_talent_search_campaign_skill.py tests/test_maimai_cdp_browser_bootstrap.py tests/test_maimai_search_live_standardize.py tests/test_campaign_notify.py tests/test_feishu_delivery_package.py tests/test_maimai_campaign_orchestrator.py tests/test_maimai_ai_infra_detail_plan.py tasks/todo.md
git commit -m "feat: add unattended maimai campaign workflow"
```

## Self-Review Checklist

- Spec coverage: Task 1 covers the productized skill and workflow; Task 2 covers browser bootstrap with `data/session/maimai-cdp-profile` and port `9888`; Task 3 covers live-run standardization; Task 4 covers detail pack size `100`; Task 5 covers Feishu IM notification; Task 6 covers Feishu delivery package; Tasks 7 and 8 cover orchestrator state, budget, wave split, retry, blocking, and resume; Task 9 covers verification and task record.
- Safety coverage: No task authorizes automatic platform-security bypass, main DB writes, raw capture upload, or unattended Feishu permission changes.
- Type consistency: `campaign_root`, `strategy`, `policy`, `wave_id`, `pack_id`, `stage`, `reason`, and `resume_command` names are consistent across tests and snippets.
- Request budget: `daily_search_request_budget` and `count_search_requests()` count list search pages only; detail live stages return zero for this budget.
- Operational handoff: before a real run, collect Feishu IM target (`chat_id` or `user_id`), identity (`bot` recommended), bot group membership, required scopes, and send one dry-run plus one test message.
