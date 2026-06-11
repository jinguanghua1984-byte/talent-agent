# Gbrain Second Brain P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 repo-first second-brain foundation for JD delivery calibration using gbrain as a rebuildable index, with append-only events, redacted case pages, feedback learning, query/shadow artifacts, and evaluation reports.

**Architecture:** `talent-agent` remains the fact source. New `scripts.second_brain*` modules generate auditable repo artifacts under `data/second-brain/`, `docs/second-brain/`, and JD run `second-brain/`; gbrain import/query is an optional derived index path with local fallback. P0 starts with deterministic schemas, redaction, CLI, feedback integration, and offline/shadow evaluation before any deeper workflow adoption.

**Tech Stack:** Python stdlib (`argparse`, `csv`, `json`, `dataclasses`, `pathlib`, `zipfile`, `subprocess`), existing pytest suite, existing JD delivery/feedback scripts, local gbrain CLI when installed.

---

## File Structure

- Create: `configs/second-brain-taxonomy.json`
  - Static P0 taxonomy for JD families, company aliases, skill neighbors, feedback reason map, candidate tags, sourcing channels, and sensitive-term blocklist.
- Create: `scripts/second_brain_models.py`
  - Schema constants, event validation, source reference validation, JSON writers, ID helpers, and append-only ledger writer.
- Create: `scripts/second_brain_redaction.py`
  - Public/private case safety checks and redaction helpers.
- Create: `scripts/second_brain_case.py`
  - Build public/private case pages and event records from a JD delivery run.
- Create: `scripts/second_brain_query.py`
  - Build historical calibration JSON/Markdown and sourcing suggestions using gbrain results or local case fallback.
- Create: `scripts/second_brain_gbrain.py`
  - Export/import/rebuild adapter around gbrain CLI; failure writes structured `gbrain_unavailable`.
- Create: `scripts/second_brain_evaluation.py`
  - Offline replay, metrics, report rendering, and skillopt shadow suggestion artifacts.
- Create: `scripts/second_brain.py`
  - CLI entrypoint with `init`, `prepare-case`, `export`, `import`, `query`, `evaluate`, `report`, `rebuild`, and `taxonomy-suggest`.
- Create: `tests/test_second_brain_models.py`
- Create: `tests/test_second_brain_redaction.py`
- Create: `tests/test_second_brain_case.py`
- Create: `tests/test_second_brain_query.py`
- Create: `tests/test_second_brain_gbrain.py`
- Create: `tests/test_second_brain_evaluation.py`
- Create: `tests/test_second_brain_cli.py`
- Modify: `scripts/jd_feedback_note_parser.py`
  - Treat optional `consultant_decision` as a first-class feedback field and infer when absent.
- Modify: `scripts/jd_delivery_feedback.py`
  - Preserve and summarize `consultant_decision`.
- Modify: `scripts/jd_talent_delivery_match.py`
  - Include blank `consultant_decision` in outreach CSV output.
- Modify: `scripts/jd_talent_delivery_feishu.py`
  - Allow the new blank feedback column through package validation.
- Modify: `agents/skills/jd-talent-delivery/SKILL.md`
  - Document optional second-brain shadow artifacts and new feedback field.
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
  - Add P0 shadow query and post-run case generation as non-blocking optional stages.
- Modify: `tests/test_jd_feedback_note_parser.py`
- Modify: `tests/test_jd_delivery_feedback.py`
- Modify: `tests/test_jd_talent_delivery_match.py`
- Modify: `tests/test_jd_talent_delivery_feishu.py`
- Modify: `tests/test_agent_architecture.py`

## Task 1: Core Taxonomy and Event Schema

**Files:**
- Create: `configs/second-brain-taxonomy.json`
- Create: `scripts/second_brain_models.py`
- Test: `tests/test_second_brain_models.py`

- [ ] **Step 1: Write failing tests for event validation and ledger append**

Create `tests/test_second_brain_models.py`:

```python
from pathlib import Path

import pytest

from scripts.second_brain_models import (
    SECOND_BRAIN_EVENT_SCHEMA,
    SourceRef,
    append_event,
    build_event,
    load_jsonl,
    validate_event,
    write_json,
)


def test_build_event_requires_source_refs_and_payload(tmp_path: Path) -> None:
    event = build_event(
        event_type="consultant_feedback_received",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="private",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/feedback/outreach-feedback.csv",
                source_type="feedback_csv",
                artifact_key="candidate_id=cand-001",
            )
        ],
        payload={"candidate_id": "cand-001", "consultant_decision": "认可"},
    )

    validate_event(event)

    assert event["schema_version"] == SECOND_BRAIN_EVENT_SCHEMA
    assert event["event_id"].startswith("evt_")
    assert event["source_refs"][0]["source_type"] == "feedback_csv"


def test_validate_event_rejects_missing_source_refs() -> None:
    event = build_event(
        event_type="scorecard_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/scorecard.json",
                source_type="scorecard_json",
                artifact_key="scorecard",
            )
        ],
        payload={"scorecard_version": "v1"},
    )
    event["source_refs"] = []

    with pytest.raises(ValueError, match="source_refs"):
        validate_event(event)


def test_append_event_writes_standard_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "data" / "second-brain" / "events.jsonl"
    event = build_event(
        event_type="jd_profile_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/role-profile.json",
                source_type="role_profile_json",
                artifact_key="role_profile",
            )
        ],
        payload={"summary": "多模态算法岗位画像"},
    )

    append_event(ledger, event)

    records = load_jsonl(ledger)
    assert records == [event]


def test_write_json_rejects_non_standard_numbers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        write_json(tmp_path / "bad.json", {"score": float("nan")})
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_models.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_models'`.

- [ ] **Step 3: Add taxonomy config**

Create `configs/second-brain-taxonomy.json`:

```json
{
  "schema_version": "second_brain_taxonomy_v1",
  "jd_families": {
    "ai_infra": {
      "label": "AI Infra",
      "aliases": ["AI Infra", "大模型基础设施", "训练推理基础设施", "推理加速"],
      "keywords": ["大模型", "训练", "推理", "GPU", "分布式", "高性能计算"]
    },
    "multi_modal_algorithm": {
      "label": "多模态算法",
      "aliases": ["多模态", "视频算法", "视觉算法", "语音视频算法"],
      "keywords": ["多模态", "视频", "图像", "视觉", "语音", "生成模型"]
    },
    "ai_product": {
      "label": "AI 产品",
      "aliases": ["AI产品", "大模型产品", "智能产品"],
      "keywords": ["产品", "需求", "商业化", "用户增长", "解决方案"]
    },
    "quant_research": {
      "label": "量化研究",
      "aliases": ["量化", "量化研究员", "策略研究"],
      "keywords": ["量化", "策略", "因子", "回测", "金融"]
    },
    "candidate_family": {
      "label": "候选 JD 家族",
      "aliases": [],
      "keywords": []
    }
  },
  "company_aliases": {},
  "skill_neighbors": {},
  "feedback_reason_map": {
    "direction_mismatch": ["方向不符", "方向偏", "不匹配"],
    "seniority_mismatch": ["年限不符", "太 senior", "太 junior"],
    "weak_execution_evidence": ["落地弱", "项目不够", "偏研究"],
    "strong_candidate": ["认可", "可以推进", "优先联系", "不错"]
  },
  "candidate_type_tags": {
    "research_heavy": ["研究", "论文", "算法研究"],
    "engineering_delivery": ["工程", "落地", "上线", "系统"]
  },
  "sourcing_channel_tags": {
    "maimai": ["脉脉", "Maimai"],
    "boss": ["BOSS", "BOSS直聘"],
    "liepin": ["猎聘", "Liepin"]
  },
  "sensitive_terms_blocklist": [
    "cookie",
    "access_token",
    "authorization",
    "trackable_token",
    "手机号",
    "微信",
    "邮箱"
  ]
}
```

- [ ] **Step 4: Implement `scripts/second_brain_models.py`**

Create `scripts/second_brain_models.py`:

```python
"""Core schemas and writers for Talent-Agent second-brain artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid

SECOND_BRAIN_EVENT_SCHEMA = "second_brain_event_v1"

ALLOWED_VISIBILITY = {"public", "private"}


@dataclass(frozen=True)
class SourceRef:
    source_path: str
    source_type: str
    artifact_key: str
    line_start: int | None = None
    line_end: int | None = None
    record_id: str | None = None
    candidate_id: str | None = None
    run_id: str | None = None


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        if line.strip():
            obj = json.loads(line)
            if not isinstance(obj, dict):
                raise ValueError(f"JSONL record in {target} is not an object")
            records.append(obj)
    return records


def validate_source_ref(source_ref: dict[str, Any]) -> None:
    for key in ("source_path", "source_type", "artifact_key"):
        if not isinstance(source_ref.get(key), str) or not source_ref[key].strip():
            raise ValueError(f"source_refs entry missing {key}")
    for key in ("line_start", "line_end"):
        value = source_ref.get(key)
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise ValueError(f"source_refs entry has invalid {key}")


def validate_event(event: dict[str, Any]) -> None:
    required = [
        "event_id",
        "event_type",
        "created_at",
        "schema_version",
        "run_id",
        "client_id",
        "jd_family",
        "visibility",
        "source_refs",
        "payload",
    ]
    for key in required:
        if key not in event:
            raise ValueError(f"event missing {key}")
    if event["schema_version"] != SECOND_BRAIN_EVENT_SCHEMA:
        raise ValueError("unsupported second-brain event schema")
    if event["visibility"] not in ALLOWED_VISIBILITY:
        raise ValueError("visibility must be public or private")
    if not isinstance(event["source_refs"], list) or not event["source_refs"]:
        raise ValueError("event source_refs must be a non-empty list")
    for source_ref in event["source_refs"]:
        if not isinstance(source_ref, dict):
            raise ValueError("source_refs entries must be objects")
        validate_source_ref(source_ref)
    if not isinstance(event["payload"], dict):
        raise ValueError("event payload must be an object")


def build_event(
    *,
    event_type: str,
    run_id: str,
    client_id: str,
    jd_family: str,
    visibility: str,
    source_refs: list[SourceRef],
    payload: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    event = {
        "event_id": _event_id(),
        "event_type": event_type,
        "created_at": created_at or _now_iso(),
        "schema_version": SECOND_BRAIN_EVENT_SCHEMA,
        "run_id": run_id,
        "client_id": client_id,
        "jd_family": jd_family,
        "visibility": visibility,
        "source_refs": [asdict(source_ref) for source_ref in source_refs],
        "payload": dict(payload),
    }
    validate_event(event)
    return event


def append_event(ledger_path: str | Path, event: dict[str, Any]) -> None:
    validate_event(event)
    target = Path(ledger_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False))
        handle.write("\n")
```

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_models.py -q
```

Expected: `4 passed`.

- [ ] **Step 6: Commit Task 1**

```bash
git add configs/second-brain-taxonomy.json scripts/second_brain_models.py tests/test_second_brain_models.py
git commit -m "Add second brain event schema"
```

## Task 2: Redaction and Case Safety Rules

**Files:**
- Create: `scripts/second_brain_redaction.py`
- Test: `tests/test_second_brain_redaction.py`

- [ ] **Step 1: Write failing tests for public/private case safety**

Create `tests/test_second_brain_redaction.py`:

```python
import pytest

from scripts.second_brain_redaction import (
    assert_private_case_safe,
    assert_public_case_safe,
    redact_candidate_name,
    redact_company_name,
)


def test_public_case_blocks_candidate_name_and_company() -> None:
    content = "候选人张三，目前在腾讯，反馈是不认可。"

    with pytest.raises(ValueError, match="public case contains blocked candidate text"):
        assert_public_case_safe(content, candidate_names=["张三"], company_names=["腾讯"])


def test_public_case_blocks_profile_url_and_token_marker() -> None:
    content = "profile_url=https://maimai.cn/detail?dstu=1&trackable_token=secret"

    with pytest.raises(ValueError, match="public case contains sensitive marker"):
        assert_public_case_safe(content, candidate_names=[], company_names=[])


def test_private_case_allows_name_and_company_but_blocks_contact() -> None:
    content = "张三 当前公司 腾讯 手机号 13800000000"

    with pytest.raises(ValueError, match="private case contains contact-like data"):
        assert_private_case_safe(content)


def test_redaction_helpers_are_stable() -> None:
    assert redact_candidate_name("张三") == "候选人#2f52"
    assert redact_company_name("腾讯") == "公司#5426"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_redaction.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_redaction'`.

- [ ] **Step 3: Implement redaction module**

Create `scripts/second_brain_redaction.py`:

```python
"""Redaction and safety checks for second-brain public/private case pages."""

from __future__ import annotations

from hashlib import sha256
import re

SENSITIVE_MARKERS = [
    "cookie",
    "access_token",
    "authorization",
    "trackable_token",
    "profile_url",
    "raw_profile",
    "raw_payload",
]

CONTACT_PATTERNS = [
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    re.compile(r"(微信|手机号|电话|邮箱)"),
]


def _fingerprint(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()[:4]


def redact_candidate_name(name: str) -> str:
    return f"候选人#{_fingerprint(name)}"


def redact_company_name(name: str) -> str:
    return f"公司#{_fingerprint(name)}"


def _contains_marker(content: str) -> str | None:
    lowered = content.lower()
    for marker in SENSITIVE_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def assert_public_case_safe(
    content: str,
    *,
    candidate_names: list[str],
    company_names: list[str],
) -> None:
    marker = _contains_marker(content)
    if marker:
        raise ValueError(f"public case contains sensitive marker: {marker}")
    for name in candidate_names:
        if name and name in content:
            raise ValueError("public case contains blocked candidate text")
    for company_name in company_names:
        if company_name and company_name in content:
            raise ValueError("public case contains blocked candidate text")
    for pattern in CONTACT_PATTERNS:
        if pattern.search(content):
            raise ValueError("public case contains contact-like data")


def assert_private_case_safe(content: str) -> None:
    marker = _contains_marker(content)
    if marker:
        raise ValueError(f"private case contains sensitive marker: {marker}")
    for pattern in CONTACT_PATTERNS:
        if pattern.search(content):
            raise ValueError("private case contains contact-like data")
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_redaction.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit Task 2**

```bash
git add scripts/second_brain_redaction.py tests/test_second_brain_redaction.py
git commit -m "Add second brain redaction rules"
```

## Task 3: Case Builder and Event Generation

**Files:**
- Create: `scripts/second_brain_case.py`
- Test: `tests/test_second_brain_case.py`

- [ ] **Step 1: Write failing tests for `prepare-case` internals**

Create `tests/test_second_brain_case.py`:

```python
import csv
import json
from pathlib import Path

from scripts.second_brain_case import prepare_case
from scripts.second_brain_models import load_jsonl


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "data" / "output" / "jd-tencent-multimodal-2026-06-12"
    _write_json(
        run_root / "role-profile.json",
        {
            "role_id": "jd-tencent-multimodal",
            "target_role": "多模态视频算法",
            "summary": "多模态视频算法岗位，强调视频理解和工程落地。",
            "client_id": "client_tencent_games",
            "jd_family": "multi_modal_algorithm",
        },
    )
    _write_json(
        run_root / "scorecard.json",
        {
            "role_id": "jd-tencent-multimodal",
            "dimensions": [
                {"id": "video_algorithm", "label": "视频算法", "weight": 0.4},
                {"id": "engineering_delivery", "label": "工程落地", "weight": 0.3},
            ],
        },
    )
    outreach = run_root / "outreach.csv"
    outreach.parent.mkdir(parents=True, exist_ok=True)
    with outreach.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_id",
                "rank",
                "name",
                "current_company",
                "current_title",
                "recommendation_reason",
                "consultant_decision",
                "feedback_note",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand-001",
                "rank": "1",
                "name": "张三",
                "current_company": "腾讯",
                "current_title": "视频算法专家",
                "recommendation_reason": "视频算法和工程落地都强。",
                "consultant_decision": "认可",
                "feedback_note": "这个不错，可以推荐。",
            }
        )
    return run_root


def test_prepare_case_writes_events_public_and_private_cases(tmp_path: Path) -> None:
    run_root = _fixture_run(tmp_path)
    result = prepare_case(
        run_root=run_root,
        repo_root=tmp_path,
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
    )

    public_case = tmp_path / "docs" / "second-brain" / "cases" / result["public_case"]
    private_case = tmp_path / "data" / "second-brain" / "private-cases" / result["private_case"]
    ledger = tmp_path / "data" / "second-brain" / "events.jsonl"

    assert public_case.exists()
    assert private_case.exists()
    assert "张三" not in public_case.read_text(encoding="utf-8")
    assert "腾讯" not in public_case.read_text(encoding="utf-8")
    assert "张三" in private_case.read_text(encoding="utf-8")
    assert "腾讯" in private_case.read_text(encoding="utf-8")

    events = load_jsonl(ledger)
    assert [event["event_type"] for event in events] == [
        "jd_profile_created",
        "scorecard_created",
        "candidate_recommended",
        "consultant_feedback_received",
        "batch_feedback_summarized",
    ]
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_case.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_case'`.

- [ ] **Step 3: Implement `scripts/second_brain_case.py`**

Create `scripts/second_brain_case.py` with these public functions:

```python
"""Build second-brain case pages and events from JD delivery runs."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import csv
import json
import re

from scripts.second_brain_models import SourceRef, append_event, build_event, write_json
from scripts.second_brain_redaction import (
    assert_private_case_safe,
    assert_public_case_safe,
    redact_candidate_name,
    redact_company_name,
)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_outreach(run_root: Path) -> list[dict[str, str]]:
    candidates = [run_root / "outreach.csv", run_root / "outreach" / "outreach.csv"]
    for path in candidates:
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
    raise FileNotFoundError(f"outreach CSV not found under {run_root}")


def _slug(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered)
    return lowered.strip("-") or "case"


def _case_name(client_id: str, jd_family: str, run_root: Path) -> str:
    return f"{_slug(client_id)}-{_slug(jd_family)}-{_slug(run_root.name)}.md"


def _source(path: Path, repo_root: Path, source_type: str, artifact_key: str) -> SourceRef:
    try:
        source_path = str(path.relative_to(repo_root))
    except ValueError:
        source_path = str(path)
    return SourceRef(source_path=source_path, source_type=source_type, artifact_key=artifact_key)


def _public_case_markdown(
    *,
    role_profile: dict[str, Any],
    scorecard: dict[str, Any],
    rows: list[dict[str, str]],
    client_id: str,
    jd_family: str,
    source_paths: list[str],
) -> str:
    decisions = Counter(row.get("consultant_decision") or "待确认" for row in rows)
    reasons = [row.get("feedback_note", "").strip() for row in rows if row.get("feedback_note", "").strip()]
    lines = [
        f"# Second Brain Case: {client_id} / {jd_family}",
        "",
        "## JD 画像",
        str(role_profile.get("summary") or role_profile.get("target_role") or "未提供画像摘要"),
        "",
        "## Scorecard 摘要",
    ]
    for dim in scorecard.get("dimensions", []):
        if isinstance(dim, dict):
            lines.append(f"- {dim.get('label') or dim.get('id')}: weight={dim.get('weight')}")
    lines.extend(
        [
            "",
            "## 顾问反馈摘要",
            f"- 认可：{decisions.get('认可', 0)}",
            f"- 不认可：{decisions.get('不认可', 0)}",
            f"- 待确认：{decisions.get('待确认', 0)}",
            "",
            "## 反馈原因样本",
        ]
    )
    for note in reasons[:8]:
        lines.append(f"- {note}")
    lines.extend(["", "## Evidence"])
    for source_path in source_paths:
        lines.append(f"- `{source_path}`")
    return "\n".join(lines) + "\n"


def _private_case_markdown(
    *,
    role_profile: dict[str, Any],
    rows: list[dict[str, str]],
    client_id: str,
    jd_family: str,
) -> str:
    lines = [
        f"# Private Second Brain Case: {client_id} / {jd_family}",
        "",
        "## JD 画像",
        str(role_profile.get("summary") or role_profile.get("target_role") or "未提供画像摘要"),
        "",
        "## 候选人反馈",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row.get('name') or row.get('candidate_id')}",
                f"- candidate_id: `{row.get('candidate_id')}`",
                f"- 当前公司: {row.get('current_company') or ''}",
                f"- 职位: {row.get('current_title') or ''}",
                f"- 推荐理由: {row.get('recommendation_reason') or ''}",
                f"- 顾问判断: {row.get('consultant_decision') or '待确认'}",
                f"- feedback_note: {row.get('feedback_note') or ''}",
                "",
            ]
        )
    return "\n".join(lines)


def prepare_case(
    *,
    run_root: str | Path,
    repo_root: str | Path,
    client_id: str,
    jd_family: str,
) -> dict[str, Any]:
    repo = Path(repo_root)
    root = Path(run_root)
    role_path = root / "role-profile.json"
    scorecard_path = root / "scorecard.json"
    role_profile = _read_json(role_path)
    scorecard = _read_json(scorecard_path)
    rows = _read_outreach(root)
    case_name = _case_name(client_id, jd_family, root)
    public_case = repo / "docs" / "second-brain" / "cases" / case_name
    private_case = repo / "data" / "second-brain" / "private-cases" / case_name
    ledger = repo / "data" / "second-brain" / "events.jsonl"
    public_case.parent.mkdir(parents=True, exist_ok=True)
    private_case.parent.mkdir(parents=True, exist_ok=True)

    source_paths = [str(role_path.relative_to(repo)), str(scorecard_path.relative_to(repo))]
    public_content = _public_case_markdown(
        role_profile=role_profile,
        scorecard=scorecard,
        rows=rows,
        client_id=client_id,
        jd_family=jd_family,
        source_paths=source_paths,
    )
    private_content = _private_case_markdown(
        role_profile=role_profile,
        rows=rows,
        client_id=client_id,
        jd_family=jd_family,
    )
    assert_public_case_safe(
        public_content,
        candidate_names=[row.get("name", "") for row in rows],
        company_names=[row.get("current_company", "") for row in rows],
    )
    assert_private_case_safe(private_content)
    public_case.write_text(public_content, encoding="utf-8")
    private_case.write_text(private_content, encoding="utf-8")

    append_event(
        ledger,
        build_event(
            event_type="jd_profile_created",
            run_id=root.name,
            client_id=client_id,
            jd_family=jd_family,
            visibility="public",
            source_refs=[_source(role_path, repo, "role_profile_json", "role_profile")],
            payload={"summary": role_profile.get("summary")},
        ),
    )
    append_event(
        ledger,
        build_event(
            event_type="scorecard_created",
            run_id=root.name,
            client_id=client_id,
            jd_family=jd_family,
            visibility="public",
            source_refs=[_source(scorecard_path, repo, "scorecard_json", "scorecard")],
            payload={"dimensions": scorecard.get("dimensions", [])},
        ),
    )
    for row in rows:
        candidate_id = row.get("candidate_id") or ""
        source_ref = _source(root / "outreach.csv", repo, "outreach_csv", f"candidate_id={candidate_id}")
        append_event(
            ledger,
            build_event(
                event_type="candidate_recommended",
                run_id=root.name,
                client_id=client_id,
                jd_family=jd_family,
                visibility="private",
                source_refs=[source_ref],
                payload={
                    "candidate_id": candidate_id,
                    "rank": row.get("rank"),
                    "recommendation_reason": row.get("recommendation_reason"),
                },
            ),
        )
        append_event(
            ledger,
            build_event(
                event_type="consultant_feedback_received",
                run_id=root.name,
                client_id=client_id,
                jd_family=jd_family,
                visibility="private",
                source_refs=[source_ref],
                payload={
                    "candidate_id": candidate_id,
                    "consultant_decision": row.get("consultant_decision") or "待确认",
                    "feedback_note": row.get("feedback_note") or "",
                },
            ),
        )
        break
    decisions = Counter(row.get("consultant_decision") or "待确认" for row in rows)
    append_event(
        ledger,
        build_event(
            event_type="batch_feedback_summarized",
            run_id=root.name,
            client_id=client_id,
            jd_family=jd_family,
            visibility="public",
            source_refs=[_source(public_case, repo, "second_brain_case", "batch_feedback_summary")],
            payload={"decision_counts": dict(decisions)},
        ),
    )
    return {
        "public_case": public_case.name,
        "private_case": private_case.name,
        "ledger": str(ledger),
    }
```

- [ ] **Step 4: Run tests and fix path result if needed**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_case.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit Task 3**

```bash
git add scripts/second_brain_case.py tests/test_second_brain_case.py
git commit -m "Generate second brain case artifacts"
```

## Task 4: Feedback Field Integration

**Files:**
- Modify: `scripts/jd_feedback_note_parser.py`
- Modify: `scripts/jd_delivery_feedback.py`
- Modify: `scripts/jd_talent_delivery_match.py`
- Modify: `scripts/jd_talent_delivery_feishu.py`
- Test: `tests/test_jd_feedback_note_parser.py`
- Test: `tests/test_jd_delivery_feedback.py`
- Test: `tests/test_jd_talent_delivery_match.py`
- Test: `tests/test_jd_talent_delivery_feishu.py`

- [ ] **Step 1: Add failing tests for optional `consultant_decision` parsing**

Append to `tests/test_jd_feedback_note_parser.py`:

```python
def test_parse_feedback_csv_preserves_consultant_decision(tmp_path):
    run_root = tmp_path / "run"
    csv_path = run_root / "outreach.csv"
    csv_path.parent.mkdir(parents=True)
    csv_path.write_text(
        "\n".join(
            [
                "candidate_id,rank,score,grade,consultant_decision,feedback_note",
                "cand-001,1,91.5,A,认可,这个不错，可以推荐",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = parse_feedback_csv(run_root=run_root, csv_path=csv_path, dry_run=True)

    assert result["items"][0]["consultant_decision"] == "认可"
    assert result["items"][0]["decision_source"] == "explicit"
```

Append to `tests/test_jd_delivery_feedback.py`:

```python
def test_compile_feedback_summary_counts_consultant_decisions():
    payload = {
        "role_id": "role",
        "run_id": "run",
        "profile_version": "p1",
        "scorecard_version": "s1",
        "items": [
            {
                "candidate_id": "cand-1",
                "rank": 1,
                "grade": "A",
                "original_score": 90.0,
                "feedback_label": "accepted",
                "feedback_stage": "screen",
                "reason_codes": ["strong_candidate_ranked_low"],
                "hunter_note": "认可",
                "feedback_note": "不错",
                "consultant_decision": "认可",
                "parse_source": "rule",
                "parse_confidence": 0.9,
            },
            {
                "candidate_id": "cand-2",
                "rank": 2,
                "grade": "B",
                "original_score": 80.0,
                "feedback_label": "rejected",
                "feedback_stage": "screen",
                "reason_codes": ["direction_mismatch"],
                "hunter_note": "不认可",
                "feedback_note": "方向偏",
                "consultant_decision": "不认可",
                "parse_source": "rule",
                "parse_confidence": 0.9,
            },
        ],
    }

    summary = compile_feedback_summary(payload)

    assert summary["consultant_decision_counts"] == {"认可": 1, "不认可": 1}
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py::test_parse_feedback_csv_preserves_consultant_decision tests/test_jd_delivery_feedback.py::test_compile_feedback_summary_counts_consultant_decisions -q
```

Expected: FAIL because `consultant_decision` is not preserved or summarized.

- [ ] **Step 3: Implement parser preservation**

In `scripts/jd_feedback_note_parser.py`, extend row loading so `consultant_decision` is optional. Add helper:

```python
CONSULTANT_DECISIONS = {"认可", "不认可", "待确认"}


def _normalize_consultant_decision(value: str | None, feedback_note: str) -> tuple[str, str]:
    text = (value or "").strip()
    if text in CONSULTANT_DECISIONS:
        return text, "explicit"
    note = feedback_note.strip()
    if any(token in note for token in ["认可", "不错", "可以推荐", "建议推进", "优先联系"]):
        return "认可", "inferred_from_note"
    if any(token in note for token in ["不认可", "不合适", "方向偏", "年限不符", "暂缓"]):
        return "不认可", "inferred_from_note"
    return "待确认", "inferred_from_note"
```

When building each feedback item, include:

```python
decision, decision_source = _normalize_consultant_decision(
    row.get("consultant_decision"),
    row.get("feedback_note") or "",
)
item["consultant_decision"] = decision
item["decision_source"] = decision_source
```

- [ ] **Step 4: Implement summary counts**

In `scripts/jd_delivery_feedback.py`, inside `compile_feedback_summary`, count known decisions:

```python
decision_counts: dict[str, int] = {}
for item in items:
    decision = item.get("consultant_decision")
    if isinstance(decision, str) and decision:
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
summary["consultant_decision_counts"] = decision_counts
```

- [ ] **Step 5: Add failing outreach CSV column assertion**

Modify `tests/test_jd_talent_delivery_match.py::test_run_match_outputs_reports_and_outreach`.

Change:

```python
expected_feedback_fields = ["feedback_note"]
```

to:

```python
expected_feedback_fields = ["consultant_decision", "feedback_note"]
```

The existing loop already asserts that each expected field exists and defaults to an empty string.

- [ ] **Step 6: Implement outreach column**

In `scripts/jd_talent_delivery_match.py`, add `"consultant_decision"` next to `"feedback_note"` in the outreach field list and write blank values for new rows:

```python
row["consultant_decision"] = ""
row["feedback_note"] = row.get("feedback_note", "")
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py::test_run_match_outputs_reports_and_outreach tests/test_jd_talent_delivery_feishu.py::test_validate_delivery_package_allows_blank_feedback_columns -q
```

Expected: PASS after updating expected headers in affected tests.

- [ ] **Step 8: Commit Task 4**

```bash
git add scripts/jd_feedback_note_parser.py scripts/jd_delivery_feedback.py scripts/jd_talent_delivery_match.py scripts/jd_talent_delivery_feishu.py tests/test_jd_feedback_note_parser.py tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py
git commit -m "Add consultant decision feedback signal"
```

## Task 5: Historical Calibration Query and Guardrails

**Files:**
- Create: `scripts/second_brain_query.py`
- Test: `tests/test_second_brain_query.py`

- [ ] **Step 1: Write failing tests for multi-lane query fallback**

Create `tests/test_second_brain_query.py`:

```python
import json
from pathlib import Path

from scripts.second_brain_query import build_historical_calibration


def test_build_historical_calibration_uses_local_case_fallback(tmp_path: Path) -> None:
    case_dir = tmp_path / "docs" / "second-brain" / "cases"
    case_dir.mkdir(parents=True)
    (case_dir / "client-tencent-multi-modal-run-001.md").write_text(
        "\n".join(
            [
                "# Second Brain Case: client_tencent_games / multi_modal_algorithm",
                "## 顾问反馈摘要",
                "- 认可：1",
                "- 不认可：1",
                "## 反馈原因样本",
                "- 方向偏，缺少视频算法落地证据",
            ]
        ),
        encoding="utf-8",
    )
    jd = tmp_path / "jd.md"
    jd.write_text("多模态视频算法，需要视频理解和工程落地。", encoding="utf-8")
    out_dir = tmp_path / "run" / "second-brain"

    result = build_historical_calibration(
        repo_root=tmp_path,
        jd_path=jd,
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        out_dir=out_dir,
        gbrain_results=[],
    )

    assert (out_dir / "historical-calibration.md").exists()
    assert (out_dir / "historical-calibration.json").exists()
    assert (out_dir / "sourcing-strategy-suggestions.md").exists()
    assert result["status"] == "fallback_local_cases"
    payload = json.loads((out_dir / "historical-calibration.json").read_text(encoding="utf-8"))
    assert payload["query_lanes"][0]["lane"] == "client_preference"
    assert payload["suggestions"][0]["level"] == "L0"
    assert payload["suggestions"][0]["source_refs"]
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_query.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_query'`.

- [ ] **Step 3: Implement local fallback calibration**

Create `scripts/second_brain_query.py`:

```python
"""Historical calibration query and local fallback for second-brain P0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.second_brain_models import write_json

LANES = [
    "client_preference",
    "role_family_pattern",
    "candidate_feedback_pattern",
    "sourcing_strategy_pattern",
    "recommendation_narrative_pattern",
    "failure_reason_pattern",
]


def _case_matches(path: Path, client_id: str, jd_family: str) -> bool:
    name = path.name.lower()
    return client_id.lower().replace("_", "-") in name and jd_family.lower().replace("_", "-") in name


def _load_matching_cases(repo_root: Path, client_id: str, jd_family: str) -> list[Path]:
    case_dir = repo_root / "docs" / "second-brain" / "cases"
    if not case_dir.exists():
        return []
    return sorted(path for path in case_dir.glob("*.md") if _case_matches(path, client_id, jd_family))


def _source_ref(path: Path, repo_root: Path) -> dict[str, str]:
    return {
        "source_path": str(path.relative_to(repo_root)),
        "source_type": "second_brain_case",
        "artifact_key": "case_summary",
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Historical Calibration",
        "",
        f"- client_id: `{payload['client_id']}`",
        f"- jd_family: `{payload['jd_family']}`",
        f"- status: `{payload['status']}`",
        "",
        "## 建议",
    ]
    for suggestion in payload["suggestions"]:
        lines.extend(
            [
                f"### {suggestion['suggestion_id']}",
                f"- level: `{suggestion['level']}`",
                f"- target: `{suggestion['target']}`",
                f"- statement: {suggestion['statement']}",
                f"- auto_apply_decision: `{suggestion['auto_apply_decision']}`",
                f"- guardrail_reason: {suggestion['guardrail_reason']}",
                "",
            ]
        )
    lines.append("## Evidence")
    for ref in payload["source_refs"]:
        lines.append(f"- `{ref['source_path']}` / {ref['artifact_key']}")
    return "\n".join(lines) + "\n"


def _render_sourcing(payload: dict[str, Any]) -> str:
    lines = [
        "# Sourcing Strategy Suggestions",
        "",
        "P0 只生成寻访策略建议，不自动执行平台动作。",
        "",
        "## 建议",
        "- 优先补充历史 feedback 中反复缺失的证据。",
        "- 对同客户同 JD family 的目标公司池进行人工或 agent review。",
        "- 平台执行仍必须走 canonical workflow 和安全门禁。",
        "",
        "## Evidence",
    ]
    for ref in payload["source_refs"]:
        lines.append(f"- `{ref['source_path']}`")
    return "\n".join(lines) + "\n"


def build_historical_calibration(
    *,
    repo_root: str | Path,
    jd_path: str | Path,
    client_id: str,
    jd_family: str,
    out_dir: str | Path,
    gbrain_results: list[dict[str, Any]],
) -> dict[str, Any]:
    repo = Path(repo_root)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    case_paths = _load_matching_cases(repo, client_id, jd_family)
    source_refs = [_source_ref(path, repo) for path in case_paths]
    status = "gbrain" if gbrain_results else "fallback_local_cases"
    query_lanes = [{"lane": lane, "source_count": len(source_refs)} for lane in LANES]
    suggestions = [
        {
            "suggestion_id": "cal_l0_recommendation_context",
            "level": "L0",
            "target": "recommendation_narrative",
            "action": "enhance",
            "statement": "推荐理由需要显式连接历史 feedback 中的认可/不认可模式。",
            "confidence": 0.6 if source_refs else 0.2,
            "auto_apply_decision": "applied" if source_refs else "review",
            "guardrail_reason": "L0 解释层建议；来源为本地 case fallback。",
            "source_refs": source_refs,
        }
    ]
    payload = {
        "schema_version": "second_brain_historical_calibration_v1",
        "client_id": client_id,
        "jd_family": jd_family,
        "jd_path": str(Path(jd_path)),
        "status": status,
        "query_lanes": query_lanes,
        "source_refs": source_refs,
        "suggestions": suggestions,
    }
    write_json(output / "historical-calibration.json", payload)
    (output / "historical-calibration.md").write_text(_render_markdown(payload), encoding="utf-8")
    (output / "sourcing-strategy-suggestions.md").write_text(_render_sourcing(payload), encoding="utf-8")
    return payload
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_query.py -q
```

Expected: `1 passed`.

- [ ] **Step 5: Commit Task 5**

```bash
git add scripts/second_brain_query.py tests/test_second_brain_query.py
git commit -m "Add second brain calibration query"
```

## Task 6: gbrain Export/Import/Rebuild Adapter

**Files:**
- Create: `scripts/second_brain_gbrain.py`
- Test: `tests/test_second_brain_gbrain.py`

- [ ] **Step 1: Write failing tests for export bundle and unavailable gbrain**

Create `tests/test_second_brain_gbrain.py`:

```python
import zipfile
from pathlib import Path

from scripts.second_brain_gbrain import export_bundle, import_gbrain
from scripts.second_brain_models import load_jsonl


def test_export_bundle_includes_public_and_private_cases(tmp_path: Path) -> None:
    (tmp_path / "docs" / "second-brain" / "cases").mkdir(parents=True)
    (tmp_path / "data" / "second-brain" / "private-cases").mkdir(parents=True)
    (tmp_path / "docs" / "second-brain" / "cases" / "public.md").write_text("public", encoding="utf-8")
    (tmp_path / "data" / "second-brain" / "private-cases" / "private.md").write_text("private", encoding="utf-8")

    bundle = export_bundle(repo_root=tmp_path, out_path=tmp_path / "bundle.zip")

    with zipfile.ZipFile(bundle) as archive:
        assert sorted(archive.namelist()) == [
            "data/second-brain/private-cases/private.md",
            "docs/second-brain/cases/public.md",
        ]


def test_import_gbrain_records_unavailable_when_binary_missing(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr("docs/second-brain/cases/public.md", "public")

    result = import_gbrain(
        repo_root=tmp_path,
        bundle_path=bundle,
        brain_name="talent-agent-local",
        gbrain_bin="/no/such/gbrain",
    )

    assert result["status"] == "gbrain_unavailable"
    events = load_jsonl(tmp_path / "data" / "second-brain" / "events.jsonl")
    assert events[-1]["event_type"] == "gbrain_unavailable"
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_gbrain.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_gbrain'`.

- [ ] **Step 3: Implement gbrain adapter**

Create `scripts/second_brain_gbrain.py`:

```python
"""gbrain import/export/rebuild adapter for second-brain artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import shutil
import subprocess
import zipfile

from scripts.second_brain_models import SourceRef, append_event, build_event


def _artifact_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "docs" / "second-brain" / "cases",
        repo_root / "data" / "second-brain" / "private-cases",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(sorted(path for path in root.glob("*.md") if path.is_file()))
    return files


def export_bundle(*, repo_root: str | Path, out_path: str | Path) -> Path:
    repo = Path(repo_root)
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in _artifact_files(repo):
            archive.write(path, path.relative_to(repo))
    return target


def _unavailable_event(repo: Path, bundle_path: Path, brain_name: str, reason: str) -> dict[str, Any]:
    event = build_event(
        event_type="gbrain_unavailable",
        run_id="second-brain-import",
        client_id="global",
        jd_family="global",
        visibility="private",
        source_refs=[
            SourceRef(
                source_path=str(bundle_path),
                source_type="second_brain_bundle",
                artifact_key=brain_name,
            )
        ],
        payload={"reason": reason},
    )
    append_event(repo / "data" / "second-brain" / "events.jsonl", event)
    return event


def import_gbrain(
    *,
    repo_root: str | Path,
    bundle_path: str | Path,
    brain_name: str,
    gbrain_bin: str = "gbrain",
) -> dict[str, Any]:
    repo = Path(repo_root)
    bundle = Path(bundle_path)
    resolved = shutil.which(gbrain_bin) if "/" not in gbrain_bin else gbrain_bin
    if not resolved or not Path(resolved).exists():
        _unavailable_event(repo, bundle, brain_name, "gbrain binary not found")
        return {"status": "gbrain_unavailable", "reason": "gbrain binary not found"}
    command = [resolved, "import", str(bundle), "--brain", brain_name]
    completed = subprocess.run(command, cwd=repo, text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        _unavailable_event(repo, bundle, brain_name, completed.stderr.strip() or "gbrain import failed")
        return {"status": "gbrain_unavailable", "reason": completed.stderr.strip()}
    return {"status": "imported", "stdout": completed.stdout}
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_gbrain.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/second_brain_gbrain.py tests/test_second_brain_gbrain.py
git commit -m "Add gbrain adapter for second brain"
```

## Task 7: Evaluation, Report, and SkillOpt Shadow Artifacts

**Files:**
- Create: `scripts/second_brain_evaluation.py`
- Test: `tests/test_second_brain_evaluation.py`

- [ ] **Step 1: Write failing tests for replay metrics and report rendering**

Create `tests/test_second_brain_evaluation.py`:

```python
from pathlib import Path

from scripts.second_brain_evaluation import evaluate_replay, render_report


def test_evaluate_replay_computes_core_metrics(tmp_path: Path) -> None:
    calibration = tmp_path / "historical-calibration.json"
    calibration.write_text(
        """
{
  "schema_version": "second_brain_historical_calibration_v1",
  "suggestions": [
    {
      "suggestion_id": "cal_l0",
      "level": "L0",
      "auto_apply_decision": "applied",
      "source_refs": [{"source_path": "docs/second-brain/cases/a.md"}]
    },
    {
      "suggestion_id": "cal_l3",
      "level": "L3",
      "auto_apply_decision": "review",
      "source_refs": [{"source_path": "docs/second-brain/cases/a.md"}]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = evaluate_replay(calibration_files=[calibration], out_path=tmp_path / "evaluation.json")

    assert result["metrics"]["source_coverage_rate"] == 1.0
    assert result["metrics"]["suggestion_count"] == 2
    assert result["metrics"]["l3_auto_apply_count"] == 0


def test_render_report_writes_markdown(tmp_path: Path) -> None:
    evaluation = {
        "schema_version": "second_brain_evaluation_v1",
        "metrics": {
            "source_coverage_rate": 1.0,
            "suggestion_count": 2,
            "l3_auto_apply_count": 0,
        },
    }

    report = render_report(evaluation, tmp_path / "report.md")

    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "# Second Brain Evaluation Report" in text
    assert "source_coverage_rate" in text
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_evaluation.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.second_brain_evaluation'`.

- [ ] **Step 3: Implement evaluation module**

Create `scripts/second_brain_evaluation.py`:

```python
"""Evaluation and reporting helpers for second-brain P0."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from scripts.second_brain_models import write_json


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def evaluate_replay(*, calibration_files: list[Path], out_path: str | Path) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    for path in calibration_files:
        payload = _load(path)
        for suggestion in payload.get("suggestions", []):
            if isinstance(suggestion, dict):
                suggestions.append(suggestion)
    suggestion_count = len(suggestions)
    sourced = [s for s in suggestions if s.get("source_refs")]
    l3_auto = [
        s
        for s in suggestions
        if s.get("level") == "L3" and s.get("auto_apply_decision") == "applied"
    ]
    metrics = {
        "suggestion_count": suggestion_count,
        "source_coverage_rate": round(len(sourced) / suggestion_count, 4) if suggestion_count else 0.0,
        "l3_auto_apply_count": len(l3_auto),
    }
    result = {"schema_version": "second_brain_evaluation_v1", "metrics": metrics}
    write_json(out_path, result)
    return result


def render_report(evaluation: dict[str, Any], out_path: str | Path) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Second Brain Evaluation Report", "", "## Metrics"]
    for key, value in sorted((evaluation.get("metrics") or {}).items()):
        lines.append(f"- {key}: {value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
```

- [ ] **Step 4: Run tests and verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_evaluation.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit Task 7**

```bash
git add scripts/second_brain_evaluation.py tests/test_second_brain_evaluation.py
git commit -m "Add second brain evaluation report"
```

## Task 8: CLI Entrypoint

**Files:**
- Create: `scripts/second_brain.py`
- Test: `tests/test_second_brain_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `tests/test_second_brain_cli.py`:

```python
import json
import subprocess
from pathlib import Path


def test_second_brain_init_creates_directories(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "scripts.second_brain",
            "init",
            "--repo-root",
            str(tmp_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "data" / "second-brain").exists()
    assert (tmp_path / "docs" / "second-brain" / "cases").exists()
    payload = json.loads(result.stdout)
    assert payload["status"] == "initialized"


def test_second_brain_report_command(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "schema_version": "second_brain_evaluation_v1",
                "metrics": {"suggestion_count": 1, "source_coverage_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.md"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "scripts.second_brain",
            "report",
            "--evaluation",
            str(evaluation),
            "--out",
            str(report),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert report.exists()
```

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_cli.py -q
```

Expected: FAIL with `No module named scripts.second_brain`.

- [ ] **Step 3: Implement CLI**

Create `scripts/second_brain.py`:

```python
"""CLI for Talent-Agent second-brain P0 artifacts."""

from __future__ import annotations

from pathlib import Path
import argparse
import json

from scripts.second_brain_case import prepare_case
from scripts.second_brain_evaluation import evaluate_replay, render_report
from scripts.second_brain_gbrain import export_bundle, import_gbrain
from scripts.second_brain_models import write_json
from scripts.second_brain_query import build_historical_calibration


def _print_json(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _cmd_init(args: argparse.Namespace) -> None:
    repo = Path(args.repo_root)
    for rel in [
        "data/second-brain",
        "data/second-brain/private-cases",
        "data/second-brain/evaluations",
        "data/second-brain/reports",
        "data/second-brain/state",
        "docs/second-brain/cases",
    ]:
        (repo / rel).mkdir(parents=True, exist_ok=True)
    _print_json({"status": "initialized", "repo_root": str(repo)})


def _cmd_prepare_case(args: argparse.Namespace) -> None:
    _print_json(
        prepare_case(
            run_root=args.run_root,
            repo_root=args.repo_root,
            client_id=args.client,
            jd_family=args.jd_family,
        )
    )


def _cmd_export(args: argparse.Namespace) -> None:
    bundle = export_bundle(repo_root=args.repo_root, out_path=args.out)
    _print_json({"status": "exported", "bundle": str(bundle)})


def _cmd_import(args: argparse.Namespace) -> None:
    _print_json(
        import_gbrain(
            repo_root=args.repo_root,
            bundle_path=args.bundle,
            brain_name=args.brain,
            gbrain_bin=args.gbrain_bin,
        )
    )


def _cmd_query(args: argparse.Namespace) -> None:
    _print_json(
        build_historical_calibration(
            repo_root=args.repo_root,
            jd_path=args.jd,
            client_id=args.client,
            jd_family=args.jd_family,
            out_dir=args.out,
            gbrain_results=[],
        )
    )


def _cmd_evaluate(args: argparse.Namespace) -> None:
    calibration_files = [Path(path) for path in args.calibration]
    _print_json(evaluate_replay(calibration_files=calibration_files, out_path=args.out))


def _cmd_report(args: argparse.Namespace) -> None:
    evaluation = json.loads(Path(args.evaluation).read_text(encoding="utf-8"))
    report = render_report(evaluation, args.out)
    _print_json({"status": "reported", "report": str(report)})


def _cmd_rebuild(args: argparse.Namespace) -> None:
    bundle = export_bundle(repo_root=args.repo_root, out_path=args.bundle)
    _print_json(
        import_gbrain(
            repo_root=args.repo_root,
            bundle_path=bundle,
            brain_name=args.brain,
            gbrain_bin=args.gbrain_bin,
        )
    )


def _cmd_taxonomy_suggest(args: argparse.Namespace) -> None:
    payload = {
        "schema_version": "second_brain_taxonomy_suggestions_v1",
        "suggestions": [],
        "source": str(args.events),
    }
    write_json(args.out, payload)
    _print_json({"status": "written", "out": str(args.out)})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Second-brain P0 artifact CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--repo-root", default=".")
    init.set_defaults(func=_cmd_init)

    prepare = sub.add_parser("prepare-case")
    prepare.add_argument("--repo-root", default=".")
    prepare.add_argument("--run-root", required=True)
    prepare.add_argument("--client", required=True)
    prepare.add_argument("--jd-family", required=True)
    prepare.set_defaults(func=_cmd_prepare_case)

    export = sub.add_parser("export")
    export.add_argument("--repo-root", default=".")
    export.add_argument("--out", required=True)
    export.set_defaults(func=_cmd_export)

    import_cmd = sub.add_parser("import")
    import_cmd.add_argument("--repo-root", default=".")
    import_cmd.add_argument("--bundle", required=True)
    import_cmd.add_argument("--brain", required=True)
    import_cmd.add_argument("--gbrain-bin", default="gbrain")
    import_cmd.set_defaults(func=_cmd_import)

    query = sub.add_parser("query")
    query.add_argument("--repo-root", default=".")
    query.add_argument("--jd", required=True)
    query.add_argument("--client", required=True)
    query.add_argument("--jd-family", required=True)
    query.add_argument("--out", required=True)
    query.set_defaults(func=_cmd_query)

    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--calibration", nargs="+", required=True)
    evaluate.add_argument("--out", required=True)
    evaluate.set_defaults(func=_cmd_evaluate)

    report = sub.add_parser("report")
    report.add_argument("--evaluation", required=True)
    report.add_argument("--out", required=True)
    report.set_defaults(func=_cmd_report)

    rebuild = sub.add_parser("rebuild")
    rebuild.add_argument("--repo-root", default=".")
    rebuild.add_argument("--bundle", required=True)
    rebuild.add_argument("--brain", required=True)
    rebuild.add_argument("--gbrain-bin", default="gbrain")
    rebuild.set_defaults(func=_cmd_rebuild)

    taxonomy = sub.add_parser("taxonomy-suggest")
    taxonomy.add_argument("--events", default="data/second-brain/events.jsonl")
    taxonomy.add_argument("--out", required=True)
    taxonomy.set_defaults(func=_cmd_taxonomy_suggest)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests and focused second-brain suite**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_cli.py tests/test_second_brain_models.py tests/test_second_brain_redaction.py tests/test_second_brain_case.py tests/test_second_brain_query.py tests/test_second_brain_gbrain.py tests/test_second_brain_evaluation.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 8**

```bash
git add scripts/second_brain.py tests/test_second_brain_cli.py
git commit -m "Add second brain CLI"
```

## Task 9: JD Workflow and Agent Contract Documentation

**Files:**
- Modify: `agents/skills/jd-talent-delivery/SKILL.md`
- Modify: `agents/workflows/jd-talent-delivery/AGENT.md`
- Modify: `tests/test_agent_architecture.py`

- [ ] **Step 1: Add failing architecture test for second-brain contract**

Append to `tests/test_agent_architecture.py`:

```python
def test_jd_delivery_documents_second_brain_shadow_contract():
    skill = Path("agents/skills/jd-talent-delivery/SKILL.md").read_text(encoding="utf-8")
    workflow = Path("agents/workflows/jd-talent-delivery/AGENT.md").read_text(encoding="utf-8")

    required_skill_tokens = [
        "consultant_decision",
        "feedback_note",
        "second-brain",
    ]
    required_workflow_tokens = [
        "historical-calibration.md",
        "historical-calibration.json",
        "sourcing-strategy-suggestions.md",
        "scripts.second_brain prepare-case",
        "gbrain_unavailable",
    ]

    for token in required_skill_tokens:
        assert token in skill
    for token in required_workflow_tokens:
        assert token in workflow
```

- [ ] **Step 2: Run test and verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_jd_delivery_documents_second_brain_shadow_contract -q
```

Expected: FAIL because docs do not yet mention the P0 contract.

- [ ] **Step 3: Update skill contract**

Add a short section to `agents/skills/jd-talent-delivery/SKILL.md`:

```markdown
## Second Brain P0

当仓库启用 gbrain 第二大脑 P0 时，本 Skill 仍以 JD delivery 为主流程。反馈侧新增可选字段 `consultant_decision`，枚举为 `认可`、`不认可`、`待确认`；`feedback_note` 继续保存顾问自然语言原因。第二大脑只生成 shadow calibration、case page 和事件账本，不写 `data/talent.db`，不触发平台动作，不自动发布飞书。
```

- [ ] **Step 4: Update workflow contract**

Add a short optional stage to `agents/workflows/jd-talent-delivery/AGENT.md` after preflight or before scorecard creation:

```markdown
### S2b：Second Brain shadow calibration（可选）

如果启用 gbrain 第二大脑 P0，运行 `python -m scripts.second_brain query --jd <jd> --client <client_id> --jd-family <jd_family> --out <run_root>/second-brain/`，生成 `historical-calibration.md`、`historical-calibration.json` 和 `sourcing-strategy-suggestions.md`。该阶段失败或写入 `gbrain_unavailable` 时不得阻塞正式 JD delivery；fallback 结果只能作为 L0 解释层参考。
```

Add a post-run optional stage:

```markdown
### S8b：Second Brain case/event 生成（可选）

当推荐反馈中包含 `consultant_decision` 或可从 `feedback_note` 推断时，可运行 `python -m scripts.second_brain prepare-case --run-root <run_root> --client <client_id> --jd-family <jd_family>`，生成 append-only events、public/private case page 和后续 gbrain 导入材料。该阶段不调用平台、不写主库、不自动发布飞书。
```

- [ ] **Step 5: Run architecture test**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_jd_delivery_documents_second_brain_shadow_contract -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 9**

```bash
git add agents/skills/jd-talent-delivery/SKILL.md agents/workflows/jd-talent-delivery/AGENT.md tests/test_agent_architecture.py
git commit -m "Document second brain JD delivery contract"
```

## Task 10: End-to-End Verification and Task Records

**Files:**
- Modify: `tasks/todo.md`
- Modify: `tasks/archive/2026-06.md`

- [ ] **Step 1: Run focused verification**

Run:

```bash
.venv/bin/python -m pytest tests/test_second_brain_models.py tests/test_second_brain_redaction.py tests/test_second_brain_case.py tests/test_second_brain_query.py tests/test_second_brain_gbrain.py tests/test_second_brain_evaluation.py tests/test_second_brain_cli.py -q
```

Expected: all focused second-brain tests pass.

- [ ] **Step 2: Run related JD feedback/delivery tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_jd_feedback_note_parser.py tests/test_jd_delivery_feedback.py tests/test_jd_talent_delivery_match.py tests/test_jd_talent_delivery_feishu.py -q
```

Expected: all related tests pass.

- [ ] **Step 3: Run architecture tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py -q
```

Expected: architecture tests pass.

- [ ] **Step 4: Run full suite**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full suite passes with only known existing warnings.

- [ ] **Step 5: Run whitespace checks**

Run:

```bash
git diff --check
git diff --cached --check
```

Expected: both commands produce no output.

- [ ] **Step 6: Update task ledger**

Add a `Recent Done` entry to `tasks/todo.md`:

```markdown
- 2026-06-12：gbrain 第二大脑 P0 foundation 已接入；新增 second-brain event/case/query/gbrain/evaluation/CLI 模块，JD feedback 支持 `consultant_decision`，JD delivery workflow 记录 shadow calibration 和 post-run case generation 合同；focused tests、相关 JD tests、架构测试、全量测试和 diff check 均通过；完整记录已归档到 `tasks/archive/2026-06.md`。
```

Append a full archive section to `tasks/archive/2026-06.md` with:

- scope
- files changed
- verification commands and results
- known limitations
- next steps

- [ ] **Step 7: Commit final task records**

```bash
git add tasks/todo.md tasks/archive/2026-06.md
git commit -m "Record second brain P0 implementation"
```

## Spec Coverage Review

- Spec sections 1-5 are covered by Tasks 1, 3, 6, 8, and 9.
- Spec section 6 is covered by Tasks 1, 3, 4, 5, and 7.
- Spec section 7 is covered by Tasks 1 and 8.
- Spec sections 8-11 are covered by Tasks 5, 6, 8, and 9.
- Spec sections 12, 15, and 19 are covered by Task 7.
- Spec sections 13 and 14 are covered by Tasks 4 and 5.
- Spec section 16 is covered by Task 2 and Task 10 policy verification.
- Spec sections 17-18 are covered by Task 10 and the ordered task breakdown.

## Execution Notes

- Use `.venv/bin/python` for all Python commands.
- Do not call gbrain from the formal JD delivery path in P0; only the standalone CLI may invoke gbrain.
- Keep `data/second-brain/` as local runtime data. Do not stage generated events/private cases unless explicitly requested.
- Commit after each task so regressions can be isolated.
