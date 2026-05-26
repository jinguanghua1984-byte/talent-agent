# Maimai AI Infra Direct Detail Live Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 AI Infra V2 cold-start campaign 的 A/B 档联系人生成四个详情抓取任务包，并实现一个像搜索 live gate 一样在已打开人才银行页直接调用详情接口的受控详情抓取链路。

**Architecture:** 先从 12 个 wave 的人工评审草稿生成去重后的 A/B 详情目标清单和四个稳定切分包，再由新的 detail live gate 连接现有 CDP 人才银行页，通过页面上下文 `fetch(url, { credentials: "include" })` 顺序调用详情接口。成功详情先落 raw/capture 文件，只有整包完成且 `detail-wave dry-run` clean 后，才 apply 到 campaign DB；任何风控、登录、验证码、非 JSON、超时或模板不兼容都写 interruption/continuation 后暂停。

**Tech Stack:** Python 3、SQLite campaign DB、Chrome/Edge CDP、现有 `scripts.maimai_detail_targets`、`scripts.maimai_detail_import`、`scripts.maimai_ai_infra_pipeline detail-wave`、pytest。

---

## Current Audit

- Campaign root: `data/campaigns/ai-infra-v2-2026-05-15-dry-run`
- Campaign DB: `data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db`
- Review inputs: `review/initial-human-review-draft-wave-001.json` through `review/initial-human-review-draft-wave-012.json`
- A/B 原始评审行: `811`
- 按 `candidate_id` 去重后目标: `596`
- 重复 A/B 行: `215`
- 去重后 A 档: `235`
- 去重后 B 档: `361`
- 缺 `source_profiles`: `0`
- 缺 `platform_id`: `0`
- 缺 `trackable_token`: `0`

四个任务包采用 “A 优先、分数降序、candidate_id 升序” 的稳定排序，再 round-robin 切分，避免某一包集中承载全部高价值目标：

| Pack | Targets | A | B |
|---|---:|---:|---:|
| `detail-ab-pack-001` | 149 | 59 | 90 |
| `detail-ab-pack-002` | 149 | 59 | 90 |
| `detail-ab-pack-003` | 149 | 59 | 90 |
| `detail-ab-pack-004` | 149 | 58 | 91 |
| Total | 596 | 235 | 361 |

## Safety Contract

- 不修改 `data/talent.db`。
- 不自动导航、不刷新、不点击业务页面、不通过页面 UI 发布任务包。
- 只连接用户已经打开的人才银行页，页面健康必须满足 `hasLoginPrompt=false`、`hasCaptcha=false`、`hasTalentBank=true`。
- 详情接口只通过页面上下文调用，使用当前登录态 cookie，调用方式为 `GET` + `credentials: "include"`。
- 详情抓取按单个 pack 顺序执行；pack 未完整完成时不运行 `detail-wave dry-run/apply`。
- 熔断条件: 登录失效、页面验证码、API captcha、HTTP `401/403/429/432`、非 JSON、响应中存在 `block_info` captcha、详情接口结构漂移、超时、CDP 连接异常、dry-run 非 clean、apply 失败。
- 熔断后必须写成功 job raw、continuation plan、interruption report，然后停止等待人工介入。

## File Structure

- Create: `scripts/maimai_ai_infra_detail_plan.py`
  - 从 wave review 草稿收集 A/B 目标。
  - 按 `candidate_id` 去重，保留 A 优先、分数更高、wave 更早的条目。
  - 复用 `scripts.maimai_detail_targets.contact_from_item()` 解析 `platform_id`、`trackable_token`。
  - 输出 all manifest、四个 pack plan 和审计 summary。

- Create: `tests/test_maimai_ai_infra_detail_plan.py`
  - 覆盖 A/B 过滤、去重优先级、缺 token 阻断、四包 round-robin 分布。

- Create: `scripts/maimai_ai_infra_detail_live_gate.py`
  - 复用 search live gate 的 CDP target 查找、页面健康探测和 `CdpSession`。
  - 在页面上下文顺序调用 `basic`、`projects`、`job_preference`、`contact_btn` 四个接口。
  - 每个成功 job 原子写入 `raw/detail-live/<pack_id>/job-<index>-<platform_id>.json`。
  - 生成兼容 `maimai_detail_import.py` 的 capture: 顶层包含 `detailJobs`，每个 job 的 `detail.basic` 为可导入的 basic payload。
  - 熔断时写 continuation plan 和 interruption report。

- Create: `tests/test_maimai_ai_infra_detail_live_gate.py`
  - 不发真实请求，只测试 plan 校验、endpoint URL 构造、成功 capture 结构、熔断报告结构、resume 跳过已完成 job。

- Modify: `scripts/maimai_ai_infra_rank.py`
  - 增加 CLI 参数 `--mode list|detailed`。
  - 增加 CLI 参数 `--candidate-ids-file`，让最终详情排行只覆盖 A/B 目标，不混入历史 wave 或 C/淘汰候选人。

- Modify: `tests/test_maimai_ai_infra_strategy.py`
  - 覆盖 detailed mode CLI 参数和 candidate id scope。

- Create: `scripts/maimai_ai_infra_detail_report.py`
  - 读取 targets manifest、四个 detail-wave apply result、detailed rank JSON。
  - 输出 `reports/final-detail-report-ab-packs-001-004.json` 和 `.md`。

- Create: `tests/test_maimai_ai_infra_detail_report.py`
  - 覆盖 coverage、pack apply 状态、A/B/C/淘汰分布和最终推荐数量字段。

---

## Task 1: A/B Target Pack Builder

**Files:**
- Create: `scripts/maimai_ai_infra_detail_plan.py`
- Create: `tests/test_maimai_ai_infra_detail_plan.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_maimai_ai_infra_detail_plan.py` with focused fixtures:

```python
import json
import sqlite3
from pathlib import Path

from scripts.maimai_ai_infra_detail_plan import build_ab_detail_packs


def write_review(path: Path, wave: str, items: list[dict]) -> None:
    path.write_text(
        json.dumps({"wave_id": wave, "items": items}, ensure_ascii=False),
        encoding="utf-8-sig",
    )


def seed_source_profile(db_path: Path, candidate_id: int, platform_id: str, token: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE candidates (id INTEGER PRIMARY KEY, name TEXT, current_company TEXT, current_title TEXT)")
    conn.execute(
        """
        CREATE TABLE source_profiles (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          candidate_id INTEGER,
          platform TEXT,
          platform_id TEXT,
          profile_url TEXT,
          raw_profile TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO candidates (id, name, current_company, current_title) VALUES (?, ?, ?, ?)",
        (candidate_id, f"候选人{candidate_id}", "字节跳动", "大模型推理工程师"),
    )
    conn.execute(
        """
        INSERT INTO source_profiles (candidate_id, platform, platform_id, profile_url, raw_profile)
        VALUES (?, 'maimai', ?, ?, ?)
        """,
        (
            candidate_id,
            platform_id,
            f"https://maimai.cn/u/{platform_id}?trackable_token={token}",
            json.dumps({"trackable_token": token}, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def test_build_ab_detail_packs_dedupes_and_splits_round_robin(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    for candidate_id in range(1, 9):
        seed_source_profile(db_path, candidate_id, f"u{candidate_id}", f"t{candidate_id}")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [
            {"candidate_id": 1, "grade": "B", "score": 80},
            {"candidate_id": 1, "grade": "A", "score": 90},
            {"candidate_id": 2, "grade": "C", "score": 70},
            {"candidate_id": 3, "grade": "A", "score": 95},
            {"candidate_id": 4, "grade": "B", "score": 88},
            {"candidate_id": 5, "grade": "B", "score": 87},
            {"candidate_id": 6, "grade": "A", "score": 86},
            {"candidate_id": 7, "grade": "B", "score": 85},
            {"candidate_id": 8, "grade": "A", "score": 84},
        ],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=4,
    )

    assert result["metadata"]["input_rows"] == 8
    assert result["metadata"]["unique_targets"] == 7
    assert result["metadata"]["missing"] == 0
    assert [pack["count"] for pack in result["packs"]] == [2, 2, 2, 1]
    assert result["packs"][0]["contacts"][0]["candidate_id"] == 3
    assert result["packs"][1]["contacts"][0]["candidate_id"] == 1
    assert (out_dir / "detail-targets-ab-all.json").exists()
    assert (out_dir / "detail-ab-pack-001.json").exists()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_plan.py -q
```

Expected: FAIL because `scripts.maimai_ai_infra_detail_plan` does not exist.

- [ ] **Step 3: Implement the pack builder**

Implement `build_ab_detail_packs()` with these exact public signatures:

```python
def collect_review_items(review_dir: Path, waves: list[str], grades: set[str]) -> list[dict[str, Any]]:
    """Return review items whose grade is in grades, with wave_id attached."""

def dedupe_review_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return one strongest review item per candidate_id."""

def build_ab_detail_packs(
    campaign_root: str | Path,
    db_path: str | Path | None = None,
    waves: list[str] | None = None,
    out_dir: str | Path | None = None,
    pack_count: int = 4,
) -> dict[str, Any]:
    """Write the A/B target manifest and pack files, then return the summary."""
```

Rules:

- Default waves are `wave-001` through `wave-012`.
- Select only `grade in {"A", "B"}`.
- Deduplicate by integer `candidate_id`.
- Keep the stronger duplicate by tuple `(grade_rank, -score, wave_order, candidate_id)`, where `A` has grade rank `0` and `B` has grade rank `1`.
- Resolve contacts with `contact_from_item(TalentDB(db_path), item)`.
- Any missing `platform_id` or `trackable_token` makes the build status `blocked`; do not emit runnable pack files when blocked.
- Sort final runnable targets by `(grade_rank, -score, candidate_id)`.
- Split by `pack_index = sorted_index % pack_count`.
- Write UTF-8-sig JSON files:
  - `raw/detail-targets/detail-targets-ab-all.json`
  - `raw/detail-targets/detail-ab-pack-001.json`
  - `raw/detail-targets/detail-ab-pack-002.json`
  - `raw/detail-targets/detail-ab-pack-003.json`
  - `raw/detail-targets/detail-ab-pack-004.json`

Pack file shape:

```json
{
  "metadata": {
    "export_type": "maimai_ai_infra_detail_pack",
    "campaign_root": "data/campaigns/ai-infra-v2-2026-05-15-dry-run",
    "pack_id": "detail-ab-pack-001",
    "pack_index": 1,
    "pack_count": 4,
    "source_grades": ["A", "B"],
    "count": 149
  },
  "contacts": [
    {
      "id": "maimai-platform-id",
      "trackable_token": "token",
      "candidate_id": 573,
      "name": "候选人",
      "company": "字节跳动",
      "position": "大模型推理引擎研发",
      "grade": "A",
      "score": 100,
      "wave_id": "wave-001",
      "priority": "P0",
      "detail_url": "https://maimai.cn/u/u123?trackable_token=t123"
    }
  ]
}
```

- [ ] **Step 4: Add the CLI**

CLI command:

```powershell
python -m scripts.maimai_ai_infra_detail_plan build-ab-packs --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --pack-count 4
```

Expected real campaign output:

```text
status=ready input_rows=811 unique_targets=596 missing=0 packs=149,149,149,149
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_detail_targets.py -q
```

Expected: PASS.

---

## Task 2: Direct Detail Live Gate

**Files:**
- Create: `scripts/maimai_ai_infra_detail_live_gate.py`
- Create: `tests/test_maimai_ai_infra_detail_live_gate.py`

- [ ] **Step 1: Write the failing tests**

Create tests for pure functions, without CDP or network:

```python
from pathlib import Path

from scripts.maimai_ai_infra_detail_live_gate import (
    build_detail_urls,
    is_detail_block,
    job_capture_entry,
    next_resume_index,
)


def test_build_detail_urls_uses_expected_maimai_endpoints():
    urls = build_detail_urls({"id": "u123", "trackable_token": "tok"})
    assert urls["basic"].startswith("/api/ent/talent/basic?")
    assert "to_uid=u123" in urls["basic"]
    assert "trackable_token=tok" in urls["basic"]
    assert urls["projects"].startswith("/api/ent/candidate/associated/project/list?")
    assert urls["job_preference"].startswith("/api/ent/talent/job_preference?")
    assert urls["contact_btn"].startswith("/api/ent/v3/search/contact_btn?")


def test_is_detail_block_catches_captcha_and_status_codes():
    assert is_detail_block({"httpStatus": 429, "data": {}}) == "http_429"
    assert is_detail_block({"httpStatus": 200, "data": {"block_info": {"block_type": "captcha_yd"}}}) == "captcha_api"
    assert is_detail_block({"httpStatus": 200, "parseError": "non_json"}) == "non_json"
    assert is_detail_block({"httpStatus": 200, "data": {"data": {"id": "u1"}}}) is None


def test_job_capture_entry_matches_detail_import_contract():
    entry = job_capture_entry(
        contact={"id": "u1", "candidate_id": 1, "name": "张三"},
        index=0,
        result={
            "ok": True,
            "detail": {"id": "u1", "name": "张三"},
            "endpoints": {
                "basic": {"httpStatus": 200, "data": {"data": {"id": "u1", "name": "张三"}}},
                "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
                "job_preference": {"httpStatus": 200, "data": {"data": {}}},
                "contact_btn": {"httpStatus": 200, "data": {"data": {}}},
            },
            "errors": [],
        },
    )
    assert entry["id"] == "u1"
    assert entry["status"] == "done"
    assert entry["detail"]["basic"]["id"] == "u1"
    assert entry["detail"]["projects"]["httpStatus"] == 200
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py -q
```

Expected: FAIL because `scripts.maimai_ai_infra_detail_live_gate` does not exist.

- [ ] **Step 3: Implement pure helpers**

Public helpers:

```python
DETAIL_BLOCK_STATUSES = {401, 403, 429, 432}

def build_detail_urls(contact: dict[str, Any]) -> dict[str, str]:
    """Return the four relative maimai detail endpoint URLs for one contact."""

def is_detail_block(endpoint_result: dict[str, Any]) -> str | None:
    """Return a fuse reason for auth, captcha, block status, or non-JSON response."""

def job_capture_entry(contact: dict[str, Any], index: int, result: dict[str, Any]) -> dict[str, Any]:
    """Return one detailJobs entry compatible with maimai_detail_import."""

def next_resume_index(contacts: list[dict[str, Any]], job_dir: Path) -> int:
    """Return the first contact index without a successful job raw file."""
```

`job_capture_entry()` must produce `detailJobs` entries accepted by `scripts.maimai_detail_import.extract_detail_entries()`:

```json
{
  "id": "platform-id",
  "candidate_id": 573,
  "name": "候选人",
  "company": "字节跳动",
  "position": "大模型推理引擎研发",
  "status": "done",
  "attempts": 1,
  "started_at": "2026-05-16T00:00:00",
  "finished_at": "2026-05-16T00:00:10",
  "detail": {
    "basic": {"id": "platform-id"},
    "projects": {"httpStatus": 200, "data": {"data": {"list": []}}},
    "job_preference": {"httpStatus": 200, "data": {"data": {}}},
    "contact_btn": {"httpStatus": 200, "data": {"data": {}}}
  },
  "errors": [],
  "source_contact": {}
}
```

- [ ] **Step 4: Implement CDP runner**

Implement CLI:

```powershell
python -m scripts.maimai_ai_infra_detail_live_gate --plan <pack-json> --out <capture-json> --cdp-url http://127.0.0.1:9888 --delay-seconds 10 --timeout-seconds 45
```

Runner behavior:

- Load `contacts` from the pack JSON.
- Find existing talent bank page using `list_targets()` and `find_talent_target()` from `scripts.maimai_ai_infra_search_live_gate`.
- Run `health_expression()` before first job and after each failure.
- Evaluate an async JavaScript expression in page context for each job.
- The JavaScript calls endpoints in this order: `basic`, `projects`, `job_preference`, `contact_btn`.
- Use `fetch(url, { method: "GET", credentials: "include", headers: { Accept: "application/json, text/plain, */*" } })`.
- For `basic`, require HTTP 2xx and JSON data.
- For auxiliary endpoints, accept only HTTP 2xx JSON in the first implementation. Any auxiliary non-JSON or block status pauses the run. This is stricter than the extension batch runner and can be relaxed only after a real classified response is recorded.
- Write each successful job atomically to `raw/detail-live/<pack_id>/job-000001-<platform_id>.json`.
- Rebuild the capture file from successful job raw files after every success.
- Exit code `0` only when every contact in the pack has a successful job raw file.
- Exit code `2` when stopped by a known fuse.
- Exit code `1` for local script/config errors before any request.

Capture file shape:

```json
{
  "metadata": {
    "export_type": "maimai_ai_infra_direct_detail_live_gate",
    "detail_mode": "direct_page_fetch",
    "pack_id": "detail-ab-pack-001",
    "total_contacts": 149,
    "completed_jobs": 149,
    "write_db": false,
    "apply": false
  },
  "detailJobs": []
}
```

- [ ] **Step 5: Implement interruption and continuation**

On any fuse, write:

- `detail-live-<pack_id>-continuation-after-<reason>-plan.json`
- `reports/interruption-detail-<pack_id>-2026-05-16.json`

Interruption report fields:

```json
{
  "stopReason": "captcha_api",
  "pack_id": "detail-ab-pack-001",
  "failedIndex": 37,
  "failedCandidateId": 123,
  "failedPlatformId": "u123",
  "lastSuccessIndex": 36,
  "standardizedJobs": 37,
  "remainingJobs": 112,
  "beforeHealth": {},
  "afterHealth": {},
  "failedEndpoint": "basic",
  "httpStatus": 429,
  "responseSummary": {},
  "responseRawPreview": "{\"block_info\":{\"block_type\":\"captcha_yd\"}}",
  "block_info": {},
  "captcha_type": "text_click",
  "downstreamNotRun": {
    "detailWaveDryRun": true,
    "detailWaveApply": true,
    "finalReport": true
  }
}
```

Continuation plan keeps the original contacts and adds:

```json
{
  "resume_from": {
    "index": 37,
    "candidate_id": 123,
    "platform_id": "u123"
  },
  "completed_job_dir": "data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live/detail-ab-pack-001"
}
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_live_gate.py -q
python -m py_compile scripts/maimai_ai_infra_detail_live_gate.py
```

Expected: PASS.

---

## Task 3: Detailed Rank Scope

**Files:**
- Modify: `scripts/maimai_ai_infra_rank.py`
- Modify: `tests/test_maimai_ai_infra_strategy.py`

- [ ] **Step 1: Write failing tests for CLI scope**

Add tests that call `rank_candidates(db_path, strategy, mode="detailed", candidate_ids=[target_a_id, target_b_id])` and verify non-target candidates are excluded even when present in DB.

Expected assertion:

```python
assert {item["candidate_id"] for item in result["ranked"]} == {target_a_id, target_b_id}
assert all(item["score_mode"] == "detailed" for item in result["ranked"])
```

- [ ] **Step 2: Implement scoped ranking**

Change function signature:

```python
def rank_candidates(
    db_path: str | Path,
    strategy: dict[str, Any],
    limit: int = 5000,
    mode: str = "list",
    candidate_ids: list[int] | None = None,
) -> dict[str, Any]:
    """Rank either the default maimai search page or an explicit candidate id scope."""
```

Rules:

- When `candidate_ids` is `None`, keep the existing `db.search()` behavior.
- When `candidate_ids` is provided, fetch candidates by `db.get(candidate_id)` in the provided order, skip missing IDs, and apply the same score/sort logic.
- CLI adds:

```powershell
--mode list|detailed
--candidate-ids-file <json>
```

`--candidate-ids-file` accepts either:

```json
{"candidate_ids": [1, 2, 3]}
```

or a detail target manifest with:

```json
{"contacts": [{"candidate_id": 1}, {"candidate_id": 2}]}
```

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_strategy.py -q
python -m py_compile scripts/maimai_ai_infra_rank.py
```

Expected: PASS.

---

## Task 4: Final Detail Report

**Files:**
- Create: `scripts/maimai_ai_infra_detail_report.py`
- Create: `tests/test_maimai_ai_infra_detail_report.py`

- [ ] **Step 1: Write failing tests**

Test fixture inputs:

```json
{
  "targets": 596,
  "packs": [
    {"pack_id": "detail-ab-pack-001", "count": 149, "apply_status": "applied"}
  ],
  "ranked": [
    {"candidate_id": 1, "grade": "A", "score": 98},
    {"candidate_id": 2, "grade": "B", "score": 86}
  ]
}
```

Expected report fields:

```python
assert result["coverage"]["target_count"] == 596
assert result["coverage"]["completed_detail_count"] == 596
assert result["grade_distribution"]["A"] >= 0
assert result["grade_distribution"]["B"] >= 0
assert "final_recommended_count" in result
```

- [ ] **Step 2: Implement report builder**

CLI:

```powershell
python -m scripts.maimai_ai_infra_detail_report --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --targets data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-targets-ab-all.json --rank-json data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-rank-ab-packs-001-004.json --out-json data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-report-ab-packs-001-004.json --out-md data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-report-ab-packs-001-004.md
```

Report must include:

- target count
- completed detail count
- missing detail count
- pack statuses
- A/B/C/淘汰 distribution after detailed ranking
- Top candidates table
- source files used
- main DB unchanged note

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_report.py -q
python -m py_compile scripts/maimai_ai_infra_detail_report.py
```

Expected: PASS.

---

## Task 5: Build Real Four Pack Plans

**Files:**
- Write generated artifacts under `data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/`

- [ ] **Step 1: Preflight**

Run:

```powershell
git status --short --branch
Get-Item data\talent.db | Select-Object FullName,Length,LastWriteTime
Get-Item data\campaigns\ai-infra-v2-2026-05-15-dry-run\talent.db | Select-Object FullName,Length,LastWriteTime
Get-Process | Where-Object { $_.CommandLine -like '*maimai_ai_infra_detail_live_gate*' -or $_.CommandLine -like '*maimai_ai_infra_search_live_gate*' }
```

Expected:

- Dirty tracked files are acknowledged and not reverted.
- `data/talent.db` timestamp remains unchanged from the preflight baseline.
- No detail/search live gate process remains.

- [ ] **Step 2: Build pack files**

Run:

```powershell
python -m scripts.maimai_ai_infra_detail_plan build-ab-packs --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --pack-count 4
```

Expected:

```text
status=ready input_rows=811 unique_targets=596 missing=0 packs=149,149,149,149
```

- [ ] **Step 3: Inspect generated manifest**

Run:

```powershell
python - <<'PY'
import json
from pathlib import Path
root = Path("data/campaigns/ai-infra-v2-2026-05-15-dry-run")
manifest = json.loads((root / "raw/detail-targets/detail-targets-ab-all.json").read_text(encoding="utf-8-sig"))
print(manifest["metadata"]["unique_targets"])
for path in sorted((root / "raw/detail-targets").glob("detail-ab-pack-*.json")):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    print(path.name, len(data["contacts"]))
PY
```

Expected:

```text
596
detail-ab-pack-001.json 149
detail-ab-pack-002.json 149
detail-ab-pack-003.json 149
detail-ab-pack-004.json 149
```

---

## Task 6: Direct Detail Execution Procedure

**Files:**
- Read plans from `raw/detail-targets/detail-ab-pack-00N.json`
- Write captures to `raw/detail-live-detail-ab-pack-00N-run-2026-05-16.json`
- Write job raw to `raw/detail-live/detail-ab-pack-00N/`
- Write interruption reports to `reports/interruption-detail-detail-ab-pack-00N-2026-05-16.json`

- [ ] **Step 1: Page health check only**

Run:

```powershell
python -m scripts.maimai_ai_infra_detail_live_gate --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-ab-pack-001.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-healthcheck-2026-05-16.json --cdp-url http://127.0.0.1:9888 --timeout-seconds 45 --health-check-only
```

Expected: `status=health_ok`, `hasLoginPrompt=false`, `hasCaptcha=false`, `hasTalentBank=true`.

- [ ] **Step 2: One-contact probe**

Run only after explicit user authorization for a real detail API request:

```powershell
python -m scripts.maimai_ai_infra_detail_live_gate --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-ab-pack-001.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-probe-2026-05-16.json --cdp-url http://127.0.0.1:9888 --delay-seconds 10 --timeout-seconds 45 --max-jobs 1
```

Expected success criteria:

- exit code `0`
- `completed_jobs=1`
- first job raw exists under `raw/detail-live/detail-ab-pack-001/`
- no `stopReason`
- no `captcha_api`
- no `http_401/http_403/http_429/http_432`

- [ ] **Step 3: Full pack 001**

Run:

```powershell
python -m scripts.maimai_ai_infra_detail_live_gate --plan data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-ab-pack-001.json --out data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-run-2026-05-16.json --cdp-url http://127.0.0.1:9888 --delay-seconds 10 --timeout-seconds 45
```

Expected success criteria:

- exit code `0`
- capture has `detailJobs=149`
- job raw count is `149`
- no interruption report for pack 001

- [ ] **Step 4: Pack 001 dry-run**

Run:

```powershell
python -m scripts.maimai_ai_infra_pipeline detail-wave dry-run --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --wave detail-ab-pack-001 --capture-file data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-run-2026-05-16.json
```

Expected:

- status `dry_run_clean`
- `failed_jobs=0`
- `unmatched=0`
- `apply_blockers=0`

- [ ] **Step 5: Pack 001 apply to campaign DB**

Run only after Step 4 is clean:

```powershell
python -m scripts.maimai_ai_infra_pipeline detail-wave apply --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --wave detail-ab-pack-001 --capture-file data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-live-detail-ab-pack-001-run-2026-05-16.json --confirm "确认写入脉脉详情"
```

Expected:

- status `applied`
- result JSON exists at `reports/detail-wave-detail-ab-pack-001-apply.json`
- campaign DB detail count increases by `149`
- main DB `data/talent.db` timestamp unchanged

- [ ] **Step 6: Repeat for packs 002-004**

Use the same command pattern with pack IDs:

```powershell
detail-ab-pack-002
detail-ab-pack-003
detail-ab-pack-004
```

Between packs, wait at least 20 minutes or ask the user before continuing. Any fuse pauses the whole sequence and writes continuation.

---

## Task 7: Final Detailed Ranking And Report

**Files:**
- Write `reports/final-detail-rank-ab-packs-001-004.json`
- Write `reports/final-detail-rank-ab-packs-001-004.md`
- Write `reports/final-detail-report-ab-packs-001-004.json`
- Write `reports/final-detail-report-ab-packs-001-004.md`

- [ ] **Step 1: Detailed ranking scoped to A/B targets**

Run:

```powershell
python -m scripts.maimai_ai_infra_rank --db data/campaigns/ai-infra-v2-2026-05-15-dry-run/talent.db --config configs/maimai-ai-infra-v2-cold-start-strategy.json --mode detailed --candidate-ids-file data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-targets-ab-all.json --out-json data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-rank-ab-packs-001-004.json --out-md data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-rank-ab-packs-001-004.md --limit 596
```

Expected:

- rank JSON candidate count is `596`
- every item has `score_mode="detailed"`
- no C/淘汰-only review candidates outside A/B target manifest are present

- [ ] **Step 2: Final detail report**

Run:

```powershell
python -m scripts.maimai_ai_infra_detail_report --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --targets data/campaigns/ai-infra-v2-2026-05-15-dry-run/raw/detail-targets/detail-targets-ab-all.json --rank-json data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-rank-ab-packs-001-004.json --out-json data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-report-ab-packs-001-004.json --out-md data/campaigns/ai-infra-v2-2026-05-15-dry-run/reports/final-detail-report-ab-packs-001-004.md
```

Expected:

- coverage target count is `596`
- completed detail count is `596`
- missing detail count is `0`
- four pack apply statuses are present
- final recommended count is within the campaign target range after detailed scoring

---

## Verification

After implementation:

```powershell
python -m pytest tests/test_maimai_ai_infra_detail_plan.py tests/test_maimai_ai_infra_detail_live_gate.py tests/test_maimai_ai_infra_detail_report.py tests/test_maimai_detail_targets.py tests/test_maimai_detail_import.py tests/test_maimai_ai_infra_pipeline.py tests/test_maimai_ai_infra_strategy.py -q
python -m py_compile scripts/maimai_ai_infra_detail_plan.py scripts/maimai_ai_infra_detail_live_gate.py scripts/maimai_ai_infra_detail_report.py scripts/maimai_detail_targets.py scripts/maimai_detail_import.py scripts/maimai_ai_infra_pipeline.py scripts/maimai_ai_infra_rank.py
git diff --check
```

After each live pack:

```powershell
Get-Process | Where-Object { $_.CommandLine -like '*maimai_ai_infra_detail_live_gate*' }
Get-Item data\talent.db | Select-Object FullName,Length,LastWriteTime
python -m scripts.maimai_ai_infra_pipeline detail-wave dry-run --campaign-root data/campaigns/ai-infra-v2-2026-05-15-dry-run --wave <pack-id> --capture-file <capture-json>
```

Expected:

- no live gate process remains
- main DB unchanged
- dry-run clean before apply
- no partial interrupted capture applied

## Rollback

- Generated pack/capture/report files live under the campaign root and can be left as audit evidence.
- Campaign DB detail apply is tracked by `detail-progress.json` and import ledger. Do not delete or hand-edit those records.
- If a pack apply fails after dry-run clean, stop and inspect `reports/detail-wave-<pack-id>-apply-failed.*`; do not re-run apply until the failed state is understood.

## Self-Review

- Spec coverage: covers A/B scope, four task packages, direct page API detail fetch, no manual plan publishing, interruption/resume, campaign DB-only apply, final detailed report.
- 占位符扫描: no unresolved markers are present.
- Type consistency: pack files use `contacts`, capture files use `detailJobs`, and import uses existing `detail-wave` commands with pack IDs as wave IDs.
