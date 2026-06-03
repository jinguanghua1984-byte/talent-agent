# 猎聘详情 Smoke Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为猎聘 CLI 增加 P1 小批详情 smoke：从 `detail_p0` 生成最多 10 人的 target pack，在已登录猎聘 CDP 页面内执行受控详情请求，逐人写 raw job，并在阻断时写 interruption 和 continuation。

**Architecture:** 复用现有 `scripts.liepin_search_live_gate` 的 CDP target、health check、`CdpSession` 和 request-template header 清洗边界；新增详情 target pack 与详情 live gate，避免把搜索执行逻辑继续塞进一个大文件。第一版只做 smoke capture summary，不写 Campaign DB，不写主库，不生成推荐报告。

**Tech Stack:** Python 3, pytest, Chrome DevTools Protocol `Runtime.evaluate`, JSON/JSONL campaign artifacts, existing `scripts.liepin_*` helpers.

---

## File Structure

- Create `scripts/liepin_detail_targets.py`: 读取 `structured/candidate-summaries.jsonl`，复用 `scripts.liepin_candidate_pool_diagnostic._score_candidate` 计算优先级，生成 `raw/detail-targets/liepin-detail-p0-smoke-001.json`、`reports/detail-smoke-targets.json` 和 `reports/detail-smoke-targets.md`。
- Create `tests/test_liepin_detail_targets.py`: 覆盖只选择 `detail_p0`、默认限制 10、上限 20、缺字段跳过、公开报告脱敏。
- Create `scripts/liepin_detail_live_gate.py`: 复用 `find_liepin_target`、`health_expression`、`is_blocking_health`、`CdpSession` 和 request-template header 清洗，构建详情页面 fetch 表达式，逐候选写 `raw/detail-live/<pack_id>/job-*.json`、`state/detail-request-ledger.jsonl`、`reports/detail-smoke-summary.*`，阻断时写 interruption 和 continuation。
- Create `tests/test_liepin_detail_live_gate.py`: 覆盖详情 URL allowlist、敏感存储负检查、成功 raw job、HTTP/业务阻断、partial capture、恢复跳过已完成 job、summary 脱敏。
- Modify `scripts/liepin_campaign_orchestrator.py`: 增加 `plan-detail-smoke` 和 `run-live-detail-smoke` 子命令。
- Modify `tests/test_liepin_campaign_orchestrator.py`: 覆盖新子命令委托与 JSON 输出。
- Modify `agents/workflows/liepin-unattended-campaign/AGENT.md`: 增加 P1 详情 smoke 阶段，保留单独确认、停机恢复和数据库边界。
- Modify `agents/skills/liepin-talent-search-campaign/SKILL.md`: 标明详情 smoke 需要单独确认，默认只允许 10 人。
- Modify `tests/test_agent_architecture.py`: 如 workflow/skill 文档需要新增约束断言，在既有架构测试中加入精确检查。

## Task 1: Detail Target Pack

**Files:**
- Create: `tests/test_liepin_detail_targets.py`
- Create: `scripts/liepin_detail_targets.py`

- [ ] **Step 1: Write failing target-pack tests**

Add `tests/test_liepin_detail_targets.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_targets import plan_detail_smoke_targets


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _candidate(
    platform_id: str,
    *,
    title: str = "AI产品经理",
    company: str = "示例公司",
    user_id: str | None = None,
    profile_url: str | None = None,
    education: str = "硕士",
    work_years: int = 8,
    active_name: str = "今天活跃",
    card_index: int = 0,
) -> dict:
    resolved_user_id = user_id if user_id is not None else f"user-{platform_id}"
    resolved_profile_url = (
        profile_url
        if profile_url is not None
        else "https://h.liepin.com/resume/showresumedetail/"
        f"?res_id_encode={platform_id}&ck_id=secret-token"
    )
    return {
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": resolved_user_id,
        "display_name": "张**",
        "current_company": company,
        "current_title": title,
        "city": "北京",
        "education": education,
        "work_years": work_years,
        "active_status": {"code": "1", "name": active_name},
        "profile_url": resolved_profile_url,
        "raw_ref": {
            "search_page": "raw/search/page-000.json",
            "card_index": card_index,
            "ckId": "ck-secret",
            "skId": "sk-secret",
            "fkId": "fk-secret",
        },
    }


def test_plan_detail_smoke_targets_selects_detail_p0_and_masks_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = [
        _candidate("res-1", card_index=0),
        _candidate("res-2", card_index=1),
        _candidate("res-low", title="学生", company="大学", work_years=1, card_index=2),
        _candidate("res-missing-url", profile_url="", card_index=3),
        _candidate("res-missing-user", user_id="", card_index=4),
    ]
    _write_rows(paths.candidate_summaries, rows)

    result = plan_detail_smoke_targets(paths.root, priority="detail_p0", limit=10)

    assert result["schema"] == "liepin_detail_smoke_targets_v1"
    assert result["pack_id"] == "liepin-detail-p0-smoke-001"
    assert result["selected_count"] == 2
    assert result["skipped_count"] == 3
    assert result["target_pack"].endswith("raw/detail-targets/liepin-detail-p0-smoke-001.json")
    pack = json.loads((paths.root / result["target_pack"]).read_text(encoding="utf-8-sig"))
    assert [item["platform_id"] for item in pack["contacts"]] == ["res-1", "res-2"]
    assert pack["contacts"][0]["priority"] == "detail_p0"
    assert pack["metadata"]["limit"] == 10
    assert pack["metadata"]["no_database_write"] is True
    report_md = (paths.reports_dir / "detail-smoke-targets.md").read_text(encoding="utf-8")
    assert "showresumedetail" not in report_md
    assert "ck-secret" not in report_md
    assert "ck_id=secret-token" not in report_md


def test_plan_detail_smoke_targets_enforces_limit_bounds(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate(f"res-{index}", card_index=index) for index in range(25)])

    default_result = plan_detail_smoke_targets(paths.root)
    assert default_result["selected_count"] == 10

    max_result = plan_detail_smoke_targets(paths.root, limit=20)
    assert max_result["selected_count"] == 20

    with pytest.raises(ValueError, match="limit must be between 1 and 20"):
        plan_detail_smoke_targets(paths.root, limit=21)


def test_plan_detail_smoke_cli_prints_json(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate("res-1")])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_detail_targets",
            "--campaign-root",
            str(paths.root),
            "--priority",
            "detail_p0",
            "--limit",
            "10",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["selected_count"] == 1
    assert payload["skipped_count"] == 0
```

- [ ] **Step 2: Run red target-pack tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_targets.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'scripts.liepin_detail_targets'
```

- [ ] **Step 3: Implement target-pack module**

Create `scripts/liepin_detail_targets.py`:

```python
"""猎聘详情 smoke 目标包生成。

只读取已标准化候选摘要，不发起猎聘请求，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_candidate_pool_diagnostic import _score_candidate  # noqa: E402


TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
PACK_ID = "liepin-detail-p0-smoke-001"
DEFAULT_PRIORITY = "detail_p0"
DEFAULT_LIMIT = 10
MAX_LIMIT = 20


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError("candidate summaries do not exist; run standardize first")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"candidate summary line {line_number} must be an object")
            rows.append(payload)
    return rows


def _raw_ref(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("raw_ref")
    if isinstance(value, dict):
        return {
            "search_page": value.get("search_page"),
            "card_index": value.get("card_index"),
        }
    return {}


def _missing_fields(row: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for key in ("platform_id", "user_id_encode", "profile_url"):
        if not str(row.get(key) or "").strip():
            missing.append(key)
    return missing


def _contact_from_row(index: int, row: dict[str, Any], priority: str, score: int, reasons: list[str]) -> dict[str, Any]:
    return {
        "index": index,
        "platform": "liepin",
        "platform_id": str(row.get("platform_id") or ""),
        "user_id_encode": str(row.get("user_id_encode") or ""),
        "profile_url": str(row.get("profile_url") or ""),
        "display_name": str(row.get("display_name") or ""),
        "current_company": str(row.get("current_company") or ""),
        "current_title": str(row.get("current_title") or ""),
        "priority": priority,
        "score": score,
        "reasons": reasons,
        "raw_ref": _raw_ref(row),
    }


def _public_sample(contact: dict[str, Any]) -> dict[str, Any]:
    return {
        "platform_id": contact["platform_id"],
        "display_name": contact["display_name"],
        "current_company": contact["current_company"],
        "current_title": contact["current_title"],
        "priority": contact["priority"],
        "score": contact["score"],
        "raw_ref": contact["raw_ref"],
    }


def _build_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 猎聘详情 smoke 目标包",
        "",
        f"- 目标优先级：{report['priority']}",
        f"- 选择候选：{report['selected_count']}",
        f"- 跳过候选：{report['skipped_count']}",
        f"- target pack：{report['target_pack']}",
        "",
        "## 样本",
    ]
    for sample in report["samples"]:
        lines.append(
            "- "
            f"{sample['display_name']} | {sample['current_company']} | "
            f"{sample['current_title']} | score={sample['score']}"
        )
    lines.append("")
    return "\n".join(lines)


def plan_detail_smoke_targets(
    campaign_root: str | Path,
    *,
    priority: str = DEFAULT_PRIORITY,
    limit: int = DEFAULT_LIMIT,
) -> dict[str, Any]:
    if priority != DEFAULT_PRIORITY:
        raise ValueError("only detail_p0 is supported for Liepin detail smoke")
    if type(limit) is not int or limit < 1 or limit > MAX_LIMIT:
        raise ValueError("limit must be between 1 and 20")

    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for row_index, row in enumerate(rows):
        scoring = _score_candidate(row)
        row_priority = str(scoring["priority"])
        missing = _missing_fields(row)
        if row_priority != priority:
            skipped.append({
                "row_index": row_index,
                "platform_id": str(row.get("platform_id") or ""),
                "reason": f"priority_{row_priority}",
            })
            continue
        if missing:
            skipped.append({
                "row_index": row_index,
                "platform_id": str(row.get("platform_id") or ""),
                "reason": "missing_required_fields",
                "missing_fields": missing,
            })
            continue
        if len(selected) < limit:
            selected.append(
                _contact_from_row(
                    len(selected),
                    row,
                    priority,
                    int(scoring["score"]),
                    [str(reason) for reason in scoring["reasons"]],
                )
            )

    pack_path = paths.raw_dir / "detail-targets" / f"{PACK_ID}.json"
    pack = {
        "schema": TARGET_SCHEMA,
        "metadata": {
            "export_type": "liepin_detail_smoke_targets",
            "campaign_id": paths.campaign_id,
            "pack_id": PACK_ID,
            "source_priority": priority,
            "limit": limit,
            "created_at": _now(),
            "no_database_write": True,
        },
        "contacts": selected,
    }
    atomic_write_json(pack_path, pack)

    report = {
        "schema": TARGET_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": PACK_ID,
        "priority": priority,
        "limit": limit,
        "selected_count": len(selected),
        "skipped_count": len(skipped),
        "target_pack": pack_path.relative_to(paths.root).as_posix(),
        "skipped": skipped[:50],
        "samples": [_public_sample(contact) for contact in selected[:10]],
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-smoke-targets.json", report)
    (paths.reports_dir / "detail-smoke-targets.md").write_text(_build_markdown(report), encoding="utf-8")
    return report


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成猎聘详情 smoke 目标包。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--priority", default=DEFAULT_PRIORITY)
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = plan_detail_smoke_targets(
            args.campaign_root,
            priority=args.priority,
            limit=args.limit,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run green target-pack tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_targets.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit target-pack work**

Run:

```bash
git add scripts/liepin_detail_targets.py tests/test_liepin_detail_targets.py
git commit -m "Add Liepin detail smoke target planning"
```

Expected:

```text
[main <hash>] Add Liepin detail smoke target planning
```

## Task 2: Detail Live Gate Fetch Builder and Block Classification

**Files:**
- Create: `tests/test_liepin_detail_live_gate.py`
- Create: `scripts/liepin_detail_live_gate.py`

- [ ] **Step 1: Write failing live-gate unit tests**

Add `tests/test_liepin_detail_live_gate.py`:

```python
import json
from pathlib import Path

import pytest

import scripts.liepin_detail_live_gate as live_gate
from scripts.liepin_detail_live_gate import (
    DETAIL_BLOCK_STATUSES,
    build_detail_fetch_expression,
    classify_detail_result,
    detail_job_path,
    load_completed_detail_jobs,
    sanitize_detail_result_for_report,
    validate_detail_url,
)


def test_validate_detail_url_accepts_only_liepin_detail_pages():
    url = "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1"
    assert validate_detail_url(url) == url

    with pytest.raises(ValueError, match="not allowed"):
        validate_detail_url("https://example.com/resume/showresumedetail/?res_id_encode=res-1")

    with pytest.raises(ValueError, match="not allowed"):
        validate_detail_url("https://h.liepin.com/search/getConditionItem")


def test_detail_fetch_expression_uses_credentials_and_no_sensitive_storage_reads():
    expression = build_detail_fetch_expression(
        "https://h.liepin.com/resume/showresumedetail/?res_id_encode=res-1",
        headers={"Accept": "application/json", "Cookie": "sid=secret"},
    )

    assert "fetch(" in expression
    assert 'credentials: "include"' in expression
    assert "showresumedetail" in expression
    assert "Cookie" not in expression
    assert "sid=secret" not in expression
    assert "document.cookie" not in expression
    assert "localStorage" not in expression
    assert "sessionStorage" not in expression


def test_classify_detail_result_catches_http_non_json_business_blocks_and_partial():
    assert DETAIL_BLOCK_STATUSES == {401, 403, 429, 432}
    assert classify_detail_result({"httpStatus": 429, "data": {}}) == "http_429"
    assert classify_detail_result({"httpStatus": 200, "parseError": "Unexpected token <"}) == "non_json"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 0, "msg": "无权限"}}) == "business_block"
    assert classify_detail_result({"httpStatus": 200, "data": {"code": 403, "msg": "受限"}}) == "business_block"
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {"name": "张三"}}}) is None
    assert classify_detail_result({"httpStatus": 200, "data": {"flag": 1, "data": {}}}) == "partial_detail"


def test_detail_job_paths_and_completion_scan(tmp_path: Path):
    job_dir = tmp_path / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    detail_job_path(job_dir, 0).write_text(
        json.dumps({"status": "done", "platform_id": "res-1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    detail_job_path(job_dir, 1).write_text(
        json.dumps({"status": "blocked", "platform_id": "res-2"}, ensure_ascii=False),
        encoding="utf-8",
    )

    completed = load_completed_detail_jobs(job_dir)

    assert completed == {0: "res-1"}
    assert detail_job_path(job_dir, 2).name == "job-002.json"


def test_sanitize_detail_result_for_report_removes_urls_and_tokens():
    sanitized = sanitize_detail_result_for_report(
        {
            "profile_url": "https://h.liepin.com/resume/showresumedetail/?ck_id=secret",
            "requests": [
                {
                    "url": "https://h.liepin.com/resume/showresumedetail/?ck_id=secret",
                    "httpStatus": 200,
                    "rawPreview": "ck_id=secret",
                }
            ],
        }
    )

    dumped = json.dumps(sanitized, ensure_ascii=False)
    assert "showresumedetail" not in dumped
    assert "ck_id=secret" not in dumped
    assert sanitized["requests"][0]["httpStatus"] == 200
```

- [ ] **Step 2: Run red live-gate unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_live_gate.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'scripts.liepin_detail_live_gate'
```

- [ ] **Step 3: Implement fetch builder and classifiers**

Create the first version of `scripts/liepin_detail_live_gate.py`:

```python
"""猎聘详情 smoke CDP live gate。

只在已登录猎聘页面上下文内执行白名单详情请求。
不读取浏览器敏感存储，不写数据库。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_browser_runner import sanitize_liepin_request_headers  # noqa: E402
from scripts.liepin_campaign import append_jsonl, atomic_write_json, ensure_campaign  # noqa: E402
from scripts.liepin_search_live_gate import (  # noqa: E402
    DEFAULT_CDP_URL,
    DEFAULT_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    CdpSession,
    find_liepin_target,
    health_expression,
    is_blocking_health,
    list_targets,
)


DETAIL_BLOCK_STATUSES = {401, 403, 429, 432}
DETAIL_TARGET_SCHEMA = "liepin_detail_smoke_targets_v1"
DETAIL_RUN_SCHEMA = "liepin_detail_smoke_run_v1"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_detail_url(url: str) -> str:
    parsed = urlsplit(str(url))
    if (
        parsed.scheme == "https"
        and parsed.netloc == "h.liepin.com"
        and parsed.path.startswith("/resume/showresumedetail")
        and not parsed.fragment
    ):
        return str(url)
    raise ValueError(f"Liepin detail URL is not allowed: {url}")


def build_detail_fetch_expression(url: str, headers: Mapping[str, Any] | None = None) -> str:
    safe_url = validate_detail_url(url)
    safe_headers = sanitize_liepin_request_headers(headers)
    safe_headers["Accept"] = safe_headers.get("Accept", "application/json, text/plain, */*")
    url_json = json.dumps(safe_url, ensure_ascii=False)
    headers_json = json.dumps(safe_headers, ensure_ascii=False)
    return f"""
(async () => {{
  const response = await fetch({url_json}, {{
    method: "GET",
    headers: {headers_json},
    credentials: "include"
  }});
  const raw = await response.text();
  let data = null;
  let parseError = null;
  try {{
    data = JSON.parse(raw);
  }} catch (err) {{
    parseError = err && err.message ? err.message : String(err);
  }}
  return {{
    status: "ok",
    httpStatus: response.status,
    contentType: response.headers.get("content-type") || "",
    rawLength: raw.length,
    parseError,
    data,
    rawPreview: raw.slice(0, 2000)
  }};
}})()
""".strip()


def _looks_like_detail_payload(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    payload = data.get("data") if isinstance(data.get("data"), dict) else data
    if not isinstance(payload, dict):
        return False
    return any(key in payload for key in ("name", "baseInfo", "resume", "workList", "workExperience", "educations"))


def classify_detail_result(response: dict[str, Any]) -> str | None:
    status = response.get("httpStatus")
    if status in DETAIL_BLOCK_STATUSES:
        return f"http_{status}"
    if response.get("parseError"):
        return "non_json"
    data = response.get("data")
    if not isinstance(data, dict):
        return "partial_detail"
    flag = data.get("flag")
    code = data.get("code")
    if flag not in (None, 1, "1", True):
        return "business_block"
    if code in (401, 403, 429, 432, "401", "403", "429", "432"):
        return "business_block"
    text = json.dumps(data, ensure_ascii=False)
    if any(marker in text for marker in ("验证码", "安全验证", "访问异常", "无权限", "余额不足", "受限")):
        return "business_block"
    if not _looks_like_detail_payload(data):
        return "partial_detail"
    return None


def detail_job_path(job_dir: Path, index: int) -> Path:
    if type(index) is not int or index < 0:
        raise ValueError("detail job index must be non-negative")
    return job_dir / f"job-{index:03d}.json"


def load_completed_detail_jobs(job_dir: Path) -> dict[int, str]:
    completed: dict[int, str] = {}
    for path in sorted(job_dir.glob("job-*.json")):
        try:
            index = int(path.stem.rsplit("-", 1)[1])
            payload = _load_json(path)
        except (IndexError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("status") == "done":
            completed[index] = str(payload.get("platform_id") or "")
    return completed


def sanitize_detail_result_for_report(payload: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        if key in {"profile_url", "url", "rawPreview"}:
            continue
        if key == "requests" and isinstance(value, list):
            sanitized["requests"] = [
                {
                    "name": item.get("name"),
                    "httpStatus": item.get("httpStatus"),
                    "contentType": item.get("contentType"),
                    "rawLength": item.get("rawLength"),
                    "parseError": item.get("parseError"),
                }
                for item in value
                if isinstance(item, dict)
            ]
        else:
            sanitized[key] = value
    return sanitized
```

- [ ] **Step 4: Run green live-gate unit tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_live_gate.py -q
```

Expected:

```text
5 passed
```

## Task 3: Detail Live Gate Execution and Recovery

**Files:**
- Modify: `tests/test_liepin_detail_live_gate.py`
- Modify: `scripts/liepin_detail_live_gate.py`

- [ ] **Step 1: Append failing execution tests**

Append to `tests/test_liepin_detail_live_gate.py`:

```python
import scripts.liepin_detail_live_gate as live_gate
from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_live_gate import run_live_detail_smoke


def _write_target_pack(root: Path, contacts: list[dict]) -> Path:
    pack_path = root / "raw" / "detail-targets" / "liepin-detail-p0-smoke-001.json"
    pack_path.parent.mkdir(parents=True, exist_ok=True)
    pack_path.write_text(
        json.dumps(
            {
                "schema": "liepin_detail_smoke_targets_v1",
                "metadata": {
                    "campaign_id": root.name,
                    "pack_id": "liepin-detail-p0-smoke-001",
                    "limit": len(contacts),
                    "no_database_write": True,
                },
                "contacts": contacts,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return pack_path


def _contact(platform_id: str, index: int = 0) -> dict:
    return {
        "index": index,
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": f"user-{platform_id}",
        "profile_url": f"https://h.liepin.com/resume/showresumedetail/?res_id_encode={platform_id}",
        "display_name": "张**",
        "current_company": "示例公司",
        "current_title": "AI产品经理",
        "priority": "detail_p0",
        "raw_ref": {"search_page": "raw/search/page-000.json", "card_index": index},
    }


def test_run_live_detail_smoke_writes_per_candidate_jobs_and_summary(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return {
                "status": "ok",
                "httpStatus": 200,
                "contentType": "application/json",
                "rawLength": 120,
                "parseError": None,
                "data": {"flag": 1, "data": {"name": "张三", "workExperience": []}},
                "rawPreview": '{"flag":1}',
            }

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        limit=10,
        run_id="detail-run-001",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 2
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    assert json.loads((job_dir / "job-000.json").read_text(encoding="utf-8-sig"))["status"] == "done"
    assert json.loads((job_dir / "job-001.json").read_text(encoding="utf-8-sig"))["platform_id"] == "res-2"
    summary = json.loads((paths.reports_dir / "detail-smoke-summary.json").read_text(encoding="utf-8-sig"))
    assert summary["completed"] == 2
    assert "showresumedetail" not in (paths.reports_dir / "detail-smoke-summary.md").read_text(encoding="utf-8")
    assert '"event": "detail_completed"' in (paths.state_dir / "detail-request-ledger.jsonl").read_text(encoding="utf-8")


def test_run_live_detail_smoke_stops_on_block_and_writes_continuation(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            self.calls = 0

        def evaluate(self, expression, timeout=30):
            self.calls += 1
            if self.calls == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return {
                "status": "ok",
                "httpStatus": 429,
                "contentType": "application/json",
                "rawLength": 80,
                "parseError": None,
                "data": {"flag": 0, "msg": "too many requests"},
                "rawPreview": '{"flag":0}',
            }

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        limit=10,
        run_id="detail-run-002",
    )

    assert result["status"] == "blocked"
    assert result["stopReason"] == "http_429"
    assert result["completed"] == 0
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    assert not (job_dir / "job-000.json").exists()
    continuation = json.loads((paths.state_dir / "detail-live-liepin-detail-p0-smoke-001-continuation-after-http_429.json").read_text(encoding="utf-8-sig"))
    assert continuation["resume_from"]["platform_id"] == "res-1"
    interruptions = sorted(paths.reports_dir.glob("interruption-detail-liepin-detail-p0-smoke-001-*.json"))
    assert len(interruptions) == 1
    assert "showresumedetail" not in json.dumps(json.loads(interruptions[0].read_text(encoding="utf-8-sig")), ensure_ascii=False)


def test_run_live_detail_smoke_skips_completed_jobs_on_resume(tmp_path: Path, monkeypatch):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    pack_path = _write_target_pack(paths.root, [_contact("res-1", 0), _contact("res-2", 1)])
    job_dir = paths.root / "raw" / "detail-live" / "liepin-detail-p0-smoke-001"
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "job-000.json").write_text(
        json.dumps({"status": "done", "platform_id": "res-1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    expressions = []

    class FakeSession:
        def __init__(self, websocket_url, timeout=30):
            pass

        def evaluate(self, expression, timeout=30):
            expressions.append(expression)
            if len(expressions) == 1:
                return {"hasLiepinSearch": True, "hasLoginPrompt": False, "hasCaptcha": False}
            return {
                "status": "ok",
                "httpStatus": 200,
                "contentType": "application/json",
                "rawLength": 120,
                "parseError": None,
                "data": {"flag": 1, "data": {"name": "李四", "workExperience": []}},
                "rawPreview": '{"flag":1}',
            }

        def close(self):
            pass

    monkeypatch.setattr(
        live_gate,
        "list_targets",
        lambda cdp_url: [
            {
                "type": "page",
                "title": "找简历",
                "url": "https://h.liepin.com/search/getConditionItem",
                "webSocketDebuggerUrl": "ws://127.0.0.1/devtools/page/1",
            }
        ],
    )
    monkeypatch.setattr(live_gate, "CdpSession", FakeSession)

    result = run_live_detail_smoke(
        campaign_root=paths.root,
        target_pack=pack_path,
        cdp_url="http://127.0.0.1:9898",
        delay_seconds=0,
        timeout_seconds=1,
        limit=10,
        run_id="detail-run-003",
    )

    assert result["status"] == "completed"
    assert result["completed"] == 1
    assert (job_dir / "job-001.json").exists()
    assert "res_id_encode=res-1" not in "\n".join(expressions)
```

- [ ] **Step 2: Run red execution tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_live_gate.py -q
```

Expected:

```text
AttributeError: module 'scripts.liepin_detail_live_gate' has no attribute 'run_live_detail_smoke'
```

- [ ] **Step 3: Implement live execution helpers**

Append these functions to `scripts/liepin_detail_live_gate.py`:

```python
def _target_pack_path(campaign_root: Path, target_pack: str | Path) -> Path:
    path = Path(target_pack)
    if path.is_absolute():
        return path
    return campaign_root / path


def _pack_id(plan: dict[str, Any], plan_path: Path) -> str:
    metadata = plan.get("metadata") if isinstance(plan.get("metadata"), dict) else {}
    return str(metadata.get("pack_id") or plan.get("pack_id") or plan_path.stem)


def _detail_ledger_path(paths: Any) -> Path:
    return paths.state_dir / "detail-request-ledger.jsonl"


def _append_detail_ledger(paths: Any, item: dict[str, Any]) -> None:
    append_jsonl(_detail_ledger_path(paths), {**item, "ts": _now()})


def _write_detail_job(
    job_dir: Path,
    *,
    index: int,
    contact: dict[str, Any],
    response: dict[str, Any],
    run_id: str,
) -> Path:
    path = detail_job_path(job_dir, index)
    payload = {
        "schema": "liepin_detail_smoke_job_v1",
        "status": "done",
        "run_id": run_id,
        "index": index,
        "platform": "liepin",
        "platform_id": str(contact.get("platform_id") or ""),
        "user_id_encode": str(contact.get("user_id_encode") or ""),
        "profile_url_ref": True,
        "raw_ref": contact.get("raw_ref") if isinstance(contact.get("raw_ref"), dict) else {},
        "requests": [
            {
                "name": "detail",
                "url": str(contact.get("profile_url") or ""),
                "httpStatus": response.get("httpStatus"),
                "contentType": response.get("contentType") or "",
                "rawLength": response.get("rawLength") or 0,
                "parseError": response.get("parseError"),
                "data": response.get("data"),
                "rawPreview": response.get("rawPreview") or "",
            }
        ],
        "captured_at": _now(),
    }
    atomic_write_json(path, payload)
    return path


def _write_continuation(
    paths: Any,
    *,
    pack_id: str,
    target_pack: Path,
    contact: dict[str, Any],
    job_index: int,
    reason: str,
    completed_job_dir: Path,
    run_id: str,
) -> Path:
    path = paths.state_dir / f"detail-live-{pack_id}-continuation-after-{reason}.json"
    payload = {
        "schema": "liepin_detail_smoke_continuation_v1",
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "target_pack": target_pack.relative_to(paths.root).as_posix(),
        "reason": reason,
        "run_id": run_id,
        "resume_from": {
            "job_index": job_index,
            "platform_id": str(contact.get("platform_id") or ""),
        },
        "completed_job_dir": completed_job_dir.as_posix(),
        "updated_at": _now(),
    }
    atomic_write_json(path, payload)
    return path


def _write_interruption(
    paths: Any,
    *,
    pack_id: str,
    reason: str,
    contact: dict[str, Any],
    job_index: int,
    response: dict[str, Any] | None,
    continuation_path: Path,
    run_id: str,
) -> Path:
    path = paths.reports_dir / f"interruption-detail-{pack_id}-{_timestamp()}.json"
    payload = {
        "schema": "liepin_detail_smoke_interruption_v1",
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": run_id,
        "reason": reason,
        "job_index": job_index,
        "platform_id": str(contact.get("platform_id") or ""),
        "response": sanitize_detail_result_for_report(response or {}),
        "continuation_path": continuation_path.as_posix(),
        "downstreamNotRun": {
            "campaignDbWrite": True,
            "mainDbWrite": True,
            "recommendationReport": True,
        },
        "generatedAt": _now(),
    }
    atomic_write_json(path, payload)
    return path


def _write_summary(
    paths: Any,
    *,
    pack_id: str,
    run_id: str,
    target_count: int,
    completed: int,
    failed: int,
    status: str,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    summary = {
        "schema": "liepin_detail_smoke_summary_v1",
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": run_id,
        "targets": target_count,
        "completed": completed,
        "failed": failed,
        "blocked": 1 if status == "blocked" else 0,
        "template_drift": 1 if stop_reason == "partial_detail" else 0,
        "captured_field_groups": ["detail_raw_json"] if completed else [],
        "status": status,
        "stopReason": stop_reason,
        "next_step": "review_smoke_summary_before_any_full_detail_or_database_work",
        "generatedAt": _now(),
    }
    atomic_write_json(paths.reports_dir / "detail-smoke-summary.json", summary)
    lines = [
        "# 猎聘详情 smoke 摘要",
        "",
        f"- 目标数：{target_count}",
        f"- 完成数：{completed}",
        f"- 失败数：{failed}",
        f"- 状态：{status}",
        f"- 停机原因：{stop_reason or '无'}",
        "",
        "本摘要只描述捕获状态，不包含详情 URL、推荐结论、数据库写入或外联队列。",
        "",
    ]
    (paths.reports_dir / "detail-smoke-summary.md").write_text("\n".join(lines), encoding="utf-8")
    return summary
```

- [ ] **Step 4: Implement `run_live_detail_smoke` and CLI**

Append to `scripts/liepin_detail_live_gate.py`:

```python
def run_live_detail_smoke(
    *,
    campaign_root: str | Path,
    target_pack: str | Path,
    cdp_url: str = DEFAULT_CDP_URL,
    delay_seconds: float = DEFAULT_DELAY_SECONDS,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    limit: int = 10,
    run_id: str | None = None,
) -> dict[str, Any]:
    if type(limit) is not int or limit < 1 or limit > 20:
        raise ValueError("limit must be between 1 and 20")
    paths = ensure_campaign(campaign_root)
    resolved_pack_path = _target_pack_path(paths.root, target_pack)
    plan = _load_json(resolved_pack_path)
    if not isinstance(plan, dict) or plan.get("schema") != DETAIL_TARGET_SCHEMA:
        raise ValueError(f"target pack schema must be {DETAIL_TARGET_SCHEMA}")
    contacts = plan.get("contacts")
    if not isinstance(contacts, list):
        raise ValueError("target pack contacts must be a list")
    selected_contacts = [contact for contact in contacts if isinstance(contact, dict)][:limit]
    pack_id = _pack_id(plan, resolved_pack_path)
    job_dir = paths.raw_dir / "detail-live" / pack_id
    job_dir.mkdir(parents=True, exist_ok=True)
    completed_jobs = load_completed_detail_jobs(job_dir)
    resolved_run_id = run_id or f"liepin-detail-smoke-{datetime.now().date().isoformat()}"
    result: dict[str, Any] = {
        "schema": DETAIL_RUN_SCHEMA,
        "campaign_id": paths.campaign_id,
        "pack_id": pack_id,
        "run_id": resolved_run_id,
        "target_count": len(selected_contacts),
        "completed": 0,
        "failed": 0,
        "status": "running",
        "generatedAt": _now(),
    }

    target = find_liepin_target(list_targets(cdp_url))
    session = CdpSession(str(target["webSocketDebuggerUrl"]), timeout=timeout_seconds)
    try:
        health = session.evaluate(health_expression(), timeout_seconds)
        result["beforeHealth"] = health
        health_block = is_blocking_health(health or {})
        if health_block:
            first_contact = selected_contacts[0] if selected_contacts else {}
            continuation = _write_continuation(
                paths,
                pack_id=pack_id,
                target_pack=resolved_pack_path,
                contact=first_contact,
                job_index=0,
                reason=health_block,
                completed_job_dir=job_dir,
                run_id=resolved_run_id,
            )
            _write_interruption(
                paths,
                pack_id=pack_id,
                reason=health_block,
                contact=first_contact,
                job_index=0,
                response={"health": health},
                continuation_path=continuation,
                run_id=resolved_run_id,
            )
            result["status"] = "blocked"
            result["stopReason"] = health_block
            _write_summary(
                paths,
                pack_id=pack_id,
                run_id=resolved_run_id,
                target_count=len(selected_contacts),
                completed=0,
                failed=0,
                status="blocked",
                stop_reason=health_block,
            )
            return result

        for index, contact in enumerate(selected_contacts):
            if index in completed_jobs:
                continue
            response = session.evaluate(
                build_detail_fetch_expression(str(contact.get("profile_url") or "")),
                timeout_seconds,
            )
            if not isinstance(response, dict):
                response = {"httpStatus": None, "parseError": "detail response was not an object"}
            block_reason = classify_detail_result(response)
            if block_reason:
                continuation = _write_continuation(
                    paths,
                    pack_id=pack_id,
                    target_pack=resolved_pack_path,
                    contact=contact,
                    job_index=index,
                    reason=block_reason,
                    completed_job_dir=job_dir,
                    run_id=resolved_run_id,
                )
                interruption = _write_interruption(
                    paths,
                    pack_id=pack_id,
                    reason=block_reason,
                    contact=contact,
                    job_index=index,
                    response=response,
                    continuation_path=continuation,
                    run_id=resolved_run_id,
                )
                _append_detail_ledger(
                    paths,
                    {
                        "event": "detail_blocked",
                        "pack_id": pack_id,
                        "job_index": index,
                        "platform_id": str(contact.get("platform_id") or ""),
                        "reason": block_reason,
                        "report_path": interruption.as_posix(),
                        "run_id": resolved_run_id,
                    },
                )
                result["status"] = "blocked"
                result["stopReason"] = block_reason
                result["failed"] = 1
                _write_summary(
                    paths,
                    pack_id=pack_id,
                    run_id=resolved_run_id,
                    target_count=len(selected_contacts),
                    completed=result["completed"],
                    failed=result["failed"],
                    status="blocked",
                    stop_reason=block_reason,
                )
                return result

            raw_path = _write_detail_job(
                job_dir,
                index=index,
                contact=contact,
                response=response,
                run_id=resolved_run_id,
            )
            _append_detail_ledger(
                paths,
                {
                    "event": "detail_completed",
                    "pack_id": pack_id,
                    "job_index": index,
                    "platform_id": str(contact.get("platform_id") or ""),
                    "raw_path": raw_path.as_posix(),
                    "run_id": resolved_run_id,
                },
            )
            result["completed"] += 1
            if index < len(selected_contacts) - 1 and delay_seconds > 0:
                time.sleep(delay_seconds)

        result["status"] = "completed"
        _write_summary(
            paths,
            pack_id=pack_id,
            run_id=resolved_run_id,
            target_count=len(selected_contacts),
            completed=result["completed"],
            failed=0,
            status="completed",
        )
        return result
    finally:
        session.close()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="执行猎聘详情 smoke CDP live gate。")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--target-pack", required=True)
    parser.add_argument("--cdp-url", default=DEFAULT_CDP_URL)
    parser.add_argument("--delay-seconds", type=float, default=DEFAULT_DELAY_SECONDS)
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = run_live_detail_smoke(
            campaign_root=args.campaign_root,
            target_pack=args.target_pack,
            cdp_url=args.cdp_url,
            delay_seconds=args.delay_seconds,
            timeout_seconds=args.timeout_seconds,
            limit=args.limit,
            run_id=args.run_id,
        )
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run green live-gate execution tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_detail_live_gate.py -q
```

Expected:

```text
8 passed
```

- [ ] **Step 6: Commit live gate work**

Run:

```bash
git add scripts/liepin_detail_live_gate.py tests/test_liepin_detail_live_gate.py
git commit -m "Add Liepin detail smoke live gate"
```

Expected:

```text
[main <hash>] Add Liepin detail smoke live gate
```

## Task 4: Orchestrator and Workflow Integration

**Files:**
- Modify: `tests/test_liepin_campaign_orchestrator.py`
- Modify: `scripts/liepin_campaign_orchestrator.py`
- Modify: `agents/workflows/liepin-unattended-campaign/AGENT.md`
- Modify: `agents/skills/liepin-talent-search-campaign/SKILL.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Add failing orchestrator tests**

Append to `tests/test_liepin_campaign_orchestrator.py`:

```python
def test_plan_detail_smoke_command_delegates_to_target_planner(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_plan_detail_smoke_targets(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_smoke_targets_v1",
            "selected_count": 10,
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
        }

    monkeypatch.setattr(orchestrator, "plan_detail_smoke_targets", fake_plan_detail_smoke_targets)

    result = orchestrator.main(
        [
            "plan-detail-smoke",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--priority",
            "detail_p0",
            "--limit",
            "10",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "priority": "detail_p0",
            "limit": 10,
        }
    ]
    assert json.loads(capsys.readouterr().out)["selected_count"] == 10


def test_run_live_detail_smoke_command_delegates_to_live_gate(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_run_live_detail_smoke(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_smoke_run_v1",
            "status": "completed",
            "completed": 10,
        }

    monkeypatch.setattr(orchestrator, "run_live_detail_smoke", fake_run_live_detail_smoke)

    result = orchestrator.main(
        [
            "run-live-detail-smoke",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--target-pack",
            "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "--cdp-url",
            "http://127.0.0.1:9898",
            "--limit",
            "10",
            "--delay-seconds",
            "0",
            "--timeout-seconds",
            "1",
            "--run-id",
            "detail-run-test",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "cdp_url": "http://127.0.0.1:9898",
            "delay_seconds": 0,
            "timeout_seconds": 1,
            "limit": 10,
            "run_id": "detail-run-test",
        }
    ]
    assert json.loads(capsys.readouterr().out)["completed"] == 10
```

- [ ] **Step 2: Run red orchestrator tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py -q
```

Expected:

```text
AttributeError: module 'scripts.liepin_campaign_orchestrator' has no attribute 'plan_detail_smoke_targets'
```

- [ ] **Step 3: Modify orchestrator imports and parser**

Patch `scripts/liepin_campaign_orchestrator.py`:

```python
from scripts.liepin_detail_live_gate import run_live_detail_smoke  # noqa: E402
from scripts.liepin_detail_targets import plan_detail_smoke_targets  # noqa: E402
```

Add parser definitions inside `main`:

```python
    detail_plan = subparsers.add_parser("plan-detail-smoke")
    detail_plan.add_argument("--campaign-root", required=True)
    detail_plan.add_argument("--priority", default="detail_p0")
    detail_plan.add_argument("--limit", type=int, default=10)

    detail_live = subparsers.add_parser("run-live-detail-smoke")
    detail_live.add_argument("--campaign-root", required=True)
    detail_live.add_argument("--target-pack", required=True)
    detail_live.add_argument("--cdp-url", default=f"http://127.0.0.1:{DEFAULT_PORT}")
    detail_live.add_argument("--delay-seconds", type=float, default=DEFAULT_RUN_POLICY["request_interval_seconds"])
    detail_live.add_argument("--timeout-seconds", type=float, default=30)
    detail_live.add_argument("--limit", type=int, default=10)
    detail_live.add_argument("--run-id")
```

Add command dispatch:

```python
        elif args.command == "plan-detail-smoke":
            result = plan_detail_smoke_targets(
                campaign_root=args.campaign_root,
                priority=args.priority,
                limit=args.limit,
            )
        elif args.command == "run-live-detail-smoke":
            result = run_live_detail_smoke(
                campaign_root=args.campaign_root,
                target_pack=args.target_pack,
                cdp_url=args.cdp_url,
                delay_seconds=args.delay_seconds,
                timeout_seconds=args.timeout_seconds,
                limit=args.limit,
                run_id=args.run_id,
            )
```

- [ ] **Step 4: Update workflow and skill docs**

In `agents/workflows/liepin-unattended-campaign/AGENT.md`, replace the S8 close section with:

~~~markdown
### S8 详情 smoke 计划

P1 详情 smoke 必须在候选池诊断后单独确认。默认只选择 `detail_p0` 前 10 人，上限 20 人：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-smoke --campaign-root data/campaigns/<campaign_id> --priority detail_p0 --limit 10
```

该阶段只生成 `raw/detail-targets/liepin-detail-p0-smoke-001.json` 和 `reports/detail-smoke-targets.*`，不触发猎聘请求。

### S9 详情 smoke 执行与恢复

真实详情 smoke 通过 CDP 页面内受控 fetch 执行：

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-smoke --campaign-root data/campaigns/<campaign_id> --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json --cdp-url http://127.0.0.1:9898 --limit 10
```

成功详情写入 `raw/detail-live/<pack_id>/job-*.json`，请求账本写入 `state/detail-request-ledger.jsonl`。恢复只信 target pack、job raw、detail ledger 和 continuation plan；已完成 job 不重复请求。

### S10 详情 smoke 摘要

详情 smoke 只输出 `reports/detail-smoke-summary.json` 和 `.md`，字段限于 targets、completed、failed、blocked、template_drift、captured_field_groups 和 next_step。不生成推荐结论、不写 Campaign DB、不写主库、不生成外联队列。

### S11 关闭

P1 小批 smoke 到详情捕获摘要即止。后续 `detail_p0` 全量、`detail_p1` 扩展、Campaign DB detail import、主库同步或候选推荐交付必须另起设计和实施计划，并经过 dry-run、备份、apply 和完整性验证。
~~~

In `agents/skills/liepin-talent-search-campaign/SKILL.md`, add a concise section:

```markdown
## 详情 smoke 边界

- 详情 smoke 必须在候选池诊断后单独确认。
- 默认只允许 `detail_p0` 前 10 人，上限 20 人。
- 目标包生成不触发猎聘请求；live 执行遇登录、验证码、安全页、401/403/429/432、非 JSON、业务阻断或 partial capture 立即停机。
- 详情 smoke 不写 Campaign DB，不写主库 `data/talent.db`，不生成推荐报告、外联队列或飞书交付包。
```

- [ ] **Step 5: Add architecture assertions**

Append to `tests/test_agent_architecture.py`:

```python
def test_liepin_contracts_define_detail_smoke_boundary():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "liepin-talent-search-campaign"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "liepin-unattended-campaign"
        / "AGENT.md"
    ).read_text(encoding="utf-8")

    for text in (skill, workflow):
        assert "详情 smoke" in text
        assert "detail_p0" in text
        assert "上限 20" in text
        assert "不写 Campaign DB" in text
        assert "不写主库" in text

    assert "plan-detail-smoke" in workflow
    assert "run-live-detail-smoke" in workflow
    assert "raw/detail-live/<pack_id>/job-*.json" in workflow
    assert "state/detail-request-ledger.jsonl" in workflow
```

- [ ] **Step 6: Run green orchestrator and architecture tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_campaign_orchestrator.py tests/test_agent_architecture.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 7: Commit integration work**

Run:

```bash
git add scripts/liepin_campaign_orchestrator.py tests/test_liepin_campaign_orchestrator.py agents/workflows/liepin-unattended-campaign/AGENT.md agents/skills/liepin-talent-search-campaign/SKILL.md tests/test_agent_architecture.py
git commit -m "Wire Liepin detail smoke workflow"
```

Expected:

```text
[main <hash>] Wire Liepin detail smoke workflow
```

## Task 5: Verification, Safety Scan, and First Offline Pack

**Files:**
- All files changed above.
- Campaign artifacts under `data/campaigns/liepin-smoke-2026-06-03-job-75703601` are ignored and must not be committed.

- [ ] **Step 1: Run focused Liepin tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_liepin_* tests/test_agent_architecture.py -q
```

Expected:

```text
all selected tests pass
```

- [ ] **Step 2: Run full test suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected:

```text
all repo tests pass, allowing only the existing warning already present before this work
```

- [ ] **Step 3: Run sensitive storage scan**

Run:

```bash
rg -n "cookies\(|context\.cookies|document\.cookie|localStorage|sessionStorage" scripts/liepin_*.py tests/test_liepin_*.py agents/skills/liepin-talent-search-campaign agents/workflows/liepin-unattended-campaign
```

Expected:

```text
only negative test assertions and documentation boundary statements may match; production code must not read browser sensitive storage
```

- [ ] **Step 4: Run diff check**

Run:

```bash
git diff --check
```

Expected:

```text
no output, exit code 0
```

- [ ] **Step 5: Generate offline detail target pack for the existing smoke campaign**

Run:

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator plan-detail-smoke \
  --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 \
  --priority detail_p0 \
  --limit 10
```

Expected:

```json
{
  "schema": "liepin_detail_smoke_targets_v1",
  "pack_id": "liepin-detail-p0-smoke-001",
  "selected_count": 10,
  "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json"
}
```

- [ ] **Step 6: Verify offline pack does not leak sensitive URL tokens in reports**

Run:

```bash
rg -n "showresumedetail|ckId|skId|fkId|ck_id|sk_id|fk_id" \
  data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/detail-smoke-targets.md \
  data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/detail-smoke-targets.json
```

Expected:

```text
no output, exit code 1
```

- [ ] **Step 7: Commit final verification docs if needed**

If Task 5 required only ignored campaign artifacts and no tracked file changes, do not commit. If tracked docs changed during verification, stage only those tracked files:

```bash
git status --short
git add <tracked-files-from-this-task-only>
git commit -m "Verify Liepin detail smoke planning"
```

Expected:

```text
no unrelated tasks/todo.md or docs/research files are staged
```

## Task 6: First Live Smoke Gate

**Files:**
- No tracked code changes expected.
- Writes ignored campaign artifacts under `data/campaigns/liepin-smoke-2026-06-03-job-75703601`.

- [ ] **Step 1: Confirm dedicated Chrome health**

Run:

```bash
.venv/bin/python - <<'PY'
import json
from scripts.liepin_search_live_gate import CdpSession, find_liepin_target, health_expression, is_blocking_health, list_targets

target = find_liepin_target(list_targets('http://127.0.0.1:9898'))
session = CdpSession(target['webSocketDebuggerUrl'], timeout=5)
try:
    health = session.evaluate(health_expression(), timeout=5)
finally:
    session.close()
print(json.dumps({'block': is_blocking_health(health or {}), 'health': health}, ensure_ascii=False, indent=2))
PY
```

Expected healthy result:

```json
{
  "block": null,
  "health": {
    "hasLoginPrompt": false,
    "hasCaptcha": false,
    "hasLiepinSearch": true
  }
}
```

If `block` is not null, stop and ask the user to handle the browser state. Do not run live detail.

- [ ] **Step 2: Run first live detail smoke with 10 candidates**

Run only after Step 1 is healthy:

```bash
.venv/bin/python -m scripts.liepin_campaign_orchestrator run-live-detail-smoke \
  --campaign-root data/campaigns/liepin-smoke-2026-06-03-job-75703601 \
  --target-pack raw/detail-targets/liepin-detail-p0-smoke-001.json \
  --cdp-url http://127.0.0.1:9898 \
  --limit 10 \
  --delay-seconds 3 \
  --timeout-seconds 20 \
  --run-id liepin-detail-smoke-20260604-0001
```

Expected completed result:

```json
{
  "schema": "liepin_detail_smoke_run_v1",
  "status": "completed",
  "completed": 10
}
```

Acceptable blocked result:

```json
{
  "schema": "liepin_detail_smoke_run_v1",
  "status": "blocked",
  "stopReason": "http_429"
}
```

On any blocked result, stop immediately and report the interruption and continuation paths.

- [ ] **Step 3: Inspect live smoke summary**

Run:

```bash
cat data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/detail-smoke-summary.json
```

Expected:

```text
summary contains targets/completed/failed/blocked/template_drift/captured_field_groups/next_step and no recommendation conclusion
```

- [ ] **Step 4: Re-run safety scan after live smoke**

Run:

```bash
rg -n "showresumedetail|ckId|skId|fkId|ck_id|sk_id|fk_id" \
  data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/detail-smoke-summary.md \
  data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/detail-smoke-summary.json \
  data/campaigns/liepin-smoke-2026-06-03-job-75703601/reports/interruption-detail-*.json
```

Expected:

```text
no output if only summary/interruption reports exist; raw/detail-live may contain profile URL references and is ignored campaign evidence
```

- [ ] **Step 5: Final report to user**

Report:

```text
状态：completed 或 blocked
target pack：<path>
raw job dir：<path>
summary：<path>
interruption：<path 或 无>
continuation：<path 或 无>
测试：focused/full/security/diff evidence
边界：未写 Campaign DB，未写 data/talent.db，未生成推荐报告
```

Do not run `detail_p0` full pack, `detail_p1`, Campaign DB import, main DB sync, Feishu publishing, or recommendation report generation in this task.

## Self-Review

- Spec coverage: target pack, live gate, per-candidate raw job, interruption, continuation, summary, docs, tests, offline pack, and first live gate are covered by Tasks 1-6.
- Scope check: the plan stops at P1 smoke. Full detail expansion, Campaign DB import, main DB sync, recommendation report, and Feishu delivery are explicitly excluded.
- Type consistency: pack schema is `liepin_detail_smoke_targets_v1`; run schema is `liepin_detail_smoke_run_v1`; pack id is `liepin-detail-p0-smoke-001`; job path is `raw/detail-live/<pack_id>/job-*.json`; ledger path is `state/detail-request-ledger.jsonl`.
- Safety check: production code uses CDP page-context fetch only and does not read browser sensitive storage; reports sanitize detail URLs and `ck/sk/fk` markers.
