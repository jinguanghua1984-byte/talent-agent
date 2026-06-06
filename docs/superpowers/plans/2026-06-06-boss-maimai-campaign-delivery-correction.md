# BOSS-Maimai Campaign Delivery Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the default BOSS-Maimai final delivery from whole-library JD Top30 handoff to a campaign-specific task summary, delivery report, follow-up queue, and optional new Feishu campaign package.

**Architecture:** Add one focused campaign delivery script that reads existing campaign artifacts, builds report and follow-up outputs, validates quality gates, and generates a Feishu-safe manifest. Update the cross-channel skill/workflow and main-sync handoff semantics so S10 points to BOSS campaign delivery, while `jd-talent-delivery` remains an independent later workflow. Keep `data/talent.db` read-only during report generation and never touch the old Top30 Feishu package.

**Tech Stack:** Python standard library, CSV/JSON/JSONL campaign artifacts, optional read-only SQLite lookup, existing `TalentDB`, `lark-cli` command manifests, pytest.

---

## Execution Notes

- Work in `/Users/eric/workspace/talent-agent`.
- Use `.venv/bin/python` for tests and CLIs.
- Do not run platform automation, Chrome/CDP, BOSS, or Maimai collection.
- Do not write `data/talent.db`; the new script may read it only when resolving `main_db_candidate_id`.
- Do not modify, move, delete, or annotate the old Top30 Feishu package.
- The worktree is already dirty. Do not stage or commit unless the user explicitly asks for git publication.

## File Structure

- Create `scripts/boss_maimai_campaign_delivery.py`
  - Reads campaign artifacts.
  - Writes `reports/boss-maimai-delivery-report.json`.
  - Writes `reports/boss-maimai-delivery-report.md`.
  - Writes `reports/boss-maimai-follow-up-queue.csv`.
  - Writes `reports/boss-maimai-follow-up-queue.md`.
  - Writes `reports/boss-maimai-delivery-quality-gates.json`.
  - Writes `feishu/boss-maimai-delivery-manifest.json` in dry-run/manifest mode.

- Create `tests/test_boss_maimai_campaign_delivery.py`
  - Unit coverage for report construction, follow-up row completeness, subset counts, quality gates, manifest safety, and CLI behavior.

- Modify `scripts/campaign_to_delivery.py`
  - Stop writing default `state/jd-delivery-handoff.json`.
  - Write `state/boss-maimai-delivery-handoff.json` after main DB sync succeeds.
  - Keep main DB sync validation and bundle flow unchanged.

- Modify `tests/test_campaign_to_delivery.py`
  - Update handoff assertions to campaign delivery handoff.
  - Assert JD handoff is not created by default.

- Modify `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
  - Replace default JD delivery wording with campaign delivery wording.
  - Add new report, follow-up queue, quality gate, and Feishu package outputs.

- Modify `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`
  - Replace S10 with BOSS campaign delivery / Feishu package.
  - Add follow-up completeness gate.
  - Mention `jd-talent-delivery` only as an optional independent later workflow, outside S10.

- Modify `tests/test_agent_architecture.py`
  - Add contract checks that S10 is campaign delivery and does not default to `jd-talent-delivery`.

- Modify `tasks/todo.md`
  - Track implementation progress and final verification evidence.

---

### Task 1: Add Campaign Delivery Tests

**Files:**
- Create: `tests/test_boss_maimai_campaign_delivery.py`

- [ ] **Step 1: Create failing campaign delivery tests**

Create `tests/test_boss_maimai_campaign_delivery.py` with this content:

```python
import csv
import json
import sqlite3
from pathlib import Path

import pytest

from scripts import boss_maimai_campaign_delivery as delivery


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _append_jsonl(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _candidate(
    root: Path,
    key: str,
    real_name: str,
    display_name: str,
    company: str,
    title: str,
    score: int,
) -> None:
    payload = {
        "candidate_key": key,
        "real_name": real_name,
        "real_name_status": "captured",
        "display_name": display_name,
        "current_company": company,
        "current_title": title,
        "city": "北京",
        "education": "博士",
        "contact": {
            "contacted": True,
            "message_status": "送达",
        },
        "screening": {
            "score": score,
            "reasons": [f"{real_name} 推荐理由"],
            "risks": [f"{real_name} 待确认风险"],
        },
    }
    _append_jsonl(root / "structured/candidates.jsonl", payload)
    _append_jsonl(
        root / "structured/approved-contact-queue.jsonl",
        {
            "candidate_key": key,
            "display_name": display_name,
            "current_company": company,
            "current_title": title,
            "score": score,
            "recommendation": "contact",
            "reasons": [f"{real_name} 推荐理由"],
            "risks": [f"{real_name} 待确认风险"],
            "approval_status": "approved_for_auto_contact",
        },
    )
    _append_jsonl(
        root / "structured/contact-decisions.jsonl",
        {
            "candidate_key": key,
            "contacted": True,
            "message_status": "送达",
        },
    )
    _append_jsonl(
        root / "structured/maimai-match-targets.jsonl",
        {
            "schema": "boss_maimai_match_target_v1",
            "candidate_key": key,
            "target_id": key.replace(":", "-"),
            "real_name": real_name,
            "current_company": company,
            "current_title": title,
            "city": "北京",
            "education": "博士",
            "query_plan": [
                {
                    "level": "name_company_title",
                    "text": f"{real_name} {company} {title}",
                    "allow_auto_bind": True,
                }
            ],
        },
    )


def _campaign_root(tmp_path: Path) -> Path:
    root = tmp_path / "boss-campaign"
    (root / "structured").mkdir(parents=True)
    (root / "reports").mkdir()
    (root / "state").mkdir()
    _write_json(
        root / "reports/sourcing-summary.json",
        {
            "candidate_count": 16,
            "list_card_count": 16,
            "detail_count": 16,
            "would_contact_count": 5,
            "real_contact_count": 5,
            "external_executor_contact_count": 5,
            "real_name_captured_count": 5,
        },
    )
    _write_json(
        root / "reports/executor-summary.json",
        {
            "approved_queue_count": 5,
            "attempt_count": 5,
            "sent_count": 5,
            "message_status_distribution": {"送达": 5},
        },
    )
    _write_json(
        root / "reports/maimai-match-summary.json",
        {
            "target_count": 5,
            "selected_count": 5,
            "missing_real_name_count": 0,
        },
    )
    for key, real_name, display_name, company, title, score in [
        ("boss-app:sun", "孙同", "孙先生", "启元实验室", "大模型算法", 93),
        ("boss-app:luo", "罗力睿", "罗先生", "北京通用人工智能研究院（BIGAI）", "算法研究员", 88),
        ("boss-app:wang-jy", "汪婧昀", "汪女士", "小红书 hilab post-train", "大模型算法工程师", 95),
        ("boss-app:zhou", "周超", "周先生", "亥姆霍兹信息安全中心", "大模型算法", 90),
        ("boss-app:wang-rf", "王若帆", "王先生", "华泰证券", "算法工程师", 98),
    ]:
        _candidate(root, key, real_name, display_name, company, title, score)
    for key in ["boss-app:sun", "boss-app:luo", "boss-app:wang-jy"]:
        _append_jsonl(
            root / "state/cross-channel-identity-ledger.jsonl",
            {
                "source_candidate_key": key,
                "match_status": "no_match",
                "decision_reason": "no_hits",
                "confidence": 0,
                "target_platform_id": "",
                "target_profile_url": "",
            },
        )
    for key, name, status, platform_id in [
        ("boss-app:zhou", "周超", "confirmed_bound", "239360802"),
        ("boss-app:wang-rf", "王若帆", "auto_bound", "247772709"),
    ]:
        url = f"https://maimai.cn/profile/detail?dstu={platform_id}&trackable_token=tok"
        _append_jsonl(
            root / "state/cross-channel-identity-ledger.jsonl",
            {
                "source_candidate_key": key,
                "match_status": status,
                "decision_reason": status,
                "confidence": 100 if status == "auto_bound" else 82,
                "target_platform_id": platform_id,
                "target_profile_url": url,
                "hit": {
                    "name": name,
                    "platform_id": platform_id,
                    "profile_url": url,
                },
            },
        )
        _append_jsonl(
            root / "structured/cross-channel-bound-candidates.jsonl",
            {
                "target": {
                    "candidate_key": key,
                    "real_name": name,
                },
                "maimai_hit": {
                    "name": name,
                    "platform_id": platform_id,
                    "profile_url": url,
                },
                "decision": {
                    "source_candidate_key": key,
                    "match_status": status,
                    "target_platform_id": platform_id,
                    "target_profile_url": url,
                },
            },
        )
    _write_json(
        root / "reports/main-db-sync-result.json",
        {
            "schema": "main_db_sync_result_v1",
            "status": "applied",
            "apply_result": {
                "created": {
                    "candidates": 2,
                    "candidate_details": 2,
                    "source_profiles": 4,
                    "candidate_field_values": 14,
                },
                "merged": {"candidates": 0},
                "conflicts": {"candidates": 0},
                "skipped": {"candidates": 0},
                "deleted": {"candidates": 0},
            },
        },
    )
    return root


def _main_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE candidates (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE source_profiles (
            id INTEGER PRIMARY KEY,
            candidate_id INTEGER,
            platform TEXT NOT NULL,
            platform_id TEXT,
            profile_url TEXT
        );
        """
    )
    conn.executemany(
        "INSERT INTO candidates(id, name) VALUES (?, ?)",
        [(56194, "王若帆"), (56195, "周超")],
    )
    conn.executemany(
        """
        INSERT INTO source_profiles(candidate_id, platform, platform_id, profile_url)
        VALUES (?, ?, ?, ?)
        """,
        [
            (56194, "boss_app", "boss-app:wang-rf", ""),
            (56194, "maimai", "247772709", "https://maimai.cn/profile/detail?dstu=247772709&trackable_token=tok"),
            (56195, "boss_app", "boss-app:zhou", ""),
            (56195, "maimai", "239360802", "https://maimai.cn/profile/detail?dstu=239360802&trackable_token=tok"),
        ],
    )
    conn.commit()
    conn.close()


def test_write_delivery_package_includes_all_contacted_candidates_and_subset_statuses(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    main_db = tmp_path / "main.db"
    _main_db(main_db)

    result = delivery.write_delivery_package(root, main_db_path=main_db)

    assert result["quality_gates"]["status"] == "passed"
    report = json.loads((root / "reports/boss-maimai-delivery-report.json").read_text(encoding="utf-8"))
    assert report["boss_funnel"]["list_card_count"] == 16
    assert report["boss_funnel"]["real_contact_count"] == 5
    assert report["maimai_funnel"]["target_count"] == 5
    assert report["maimai_funnel"]["matched_count"] == 2
    assert report["main_db_sync"]["created_candidates"] == 2
    rows = _read_csv(root / "reports/boss-maimai-follow-up-queue.csv")
    assert [row["real_name"] for row in rows] == ["孙同", "罗力睿", "汪婧昀", "周超", "王若帆"]
    assert all(row["follow_up_required"] == "true" for row in rows)
    by_name = {row["real_name"]: row for row in rows}
    assert by_name["王若帆"]["preferred_channel"] == "maimai"
    assert by_name["王若帆"]["main_db_candidate_id"] == "56194"
    assert by_name["周超"]["maimai_match_status"] == "confirmed_bound"
    assert by_name["孙同"]["preferred_channel"] == "boss"
    assert by_name["孙同"]["maimai_match_status"] == "no_match"
    assert "jd-talent-delivery" not in (root / "reports/boss-maimai-delivery-report.md").read_text(encoding="utf-8")


def test_quality_gate_blocks_when_follow_up_rows_do_not_equal_contacted_count(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    report = delivery.build_delivery_report(root)
    rows = delivery.build_follow_up_rows(root, report)[:4]

    gates = delivery.validate_delivery_quality_gates(root, report, rows)

    assert gates["status"] == "blocked"
    assert "follow_up_row_count_mismatch" in gates["blockers"]


def test_feishu_manifest_rejects_legacy_top30_and_sensitive_paths(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    delivery.write_delivery_package(root)

    manifest = delivery.build_feishu_manifest(root, dry_run=True)

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["schema"] == "boss_maimai_campaign_delivery_feishu_manifest_v1"
    assert manifest["dry_run"] is True
    assert "boss-maimai-delivery-report.md" in serialized
    assert "boss-maimai-follow-up-queue.csv" in serialized
    assert "jd-talent-delivery" not in serialized
    assert "talent-recommendation" not in serialized
    assert "talent.db" not in serialized
    assert ".zip" not in serialized


def test_cli_build_writes_outputs_and_prints_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _campaign_root(tmp_path)

    assert delivery.main(["build", "--campaign-root", str(root)]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["status"] == "passed"
    assert (root / "reports/boss-maimai-delivery-report.json").exists()
    assert (root / "reports/boss-maimai-follow-up-queue.csv").exists()
    assert (root / "reports/boss-maimai-delivery-quality-gates.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_campaign_delivery.py -q
```

Expected: collection fails with `ImportError` or `ModuleNotFoundError` because `scripts/boss_maimai_campaign_delivery.py` does not exist.

---

### Task 2: Implement Campaign Delivery Report and Quality Gates

**Files:**
- Create: `scripts/boss_maimai_campaign_delivery.py`
- Test: `tests/test_boss_maimai_campaign_delivery.py`

- [ ] **Step 1: Create the delivery script skeleton and constants**

Create `scripts/boss_maimai_campaign_delivery.py` with imports, constants, and file helpers:

```python
"""生成 BOSS-Maimai campaign 级交付报告、跟进表和飞书发布清单。"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


REPORT_SCHEMA = "boss_maimai_campaign_delivery_report_v1"
GATE_SCHEMA = "boss_maimai_campaign_delivery_quality_gates_v1"
MANIFEST_SCHEMA = "boss_maimai_campaign_delivery_feishu_manifest_v1"
MATCHED_STATUSES = {"auto_bound", "confirmed_bound"}
REPORT_JSON = "reports/boss-maimai-delivery-report.json"
REPORT_MD = "reports/boss-maimai-delivery-report.md"
FOLLOW_UP_CSV = "reports/boss-maimai-follow-up-queue.csv"
FOLLOW_UP_MD = "reports/boss-maimai-follow-up-queue.md"
GATES_JSON = "reports/boss-maimai-delivery-quality-gates.json"
MANIFEST_JSON = "feishu/boss-maimai-delivery-manifest.json"
FORBIDDEN_MANIFEST_MARKERS = (
    "talent.db",
    ".db",
    ".sqlite",
    ".zip",
    "raw/",
    "raw_profile",
    "raw_payload",
    "talent-recommendation",
    "jd-talent-delivery",
)
FOLLOW_UP_FIELDS = [
    "candidate_key",
    "real_name",
    "boss_display_name",
    "boss_company",
    "boss_title",
    "city",
    "education",
    "boss_score",
    "contact_status",
    "message_status",
    "maimai_match_status",
    "maimai_profile_url",
    "maimai_platform_id",
    "main_db_candidate_id",
    "follow_up_required",
    "preferred_channel",
    "follow_up_action",
    "priority",
    "reasons",
    "risks",
]


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _load_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        text = line.strip()
        if not text:
            continue
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError(f"{path}: line {line_no}: expected object")
        rows.append(value)
    return rows


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _string(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default
```

- [ ] **Step 2: Add candidate and matching aggregation helpers**

Append these helpers:

```python
def _latest_by_key(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _string(row.get("candidate_key"))
        if key:
            latest[key] = row
    return latest


def _latest_contacted_candidates(root: Path) -> list[dict[str, Any]]:
    candidates = _latest_by_key(_load_jsonl(root / "structured/candidates.jsonl"))
    approvals = _latest_by_key(_load_jsonl(root / "structured/approved-contact-queue.jsonl"))
    decisions = _load_jsonl(root / "structured/contact-decisions.jsonl")
    contacted_keys = {
        _string(row.get("candidate_key"))
        for row in decisions
        if row.get("contacted") is True and _string(row.get("candidate_key"))
    }
    if not contacted_keys:
        contacted_keys = set(approvals)
    ordered_keys = [key for key in approvals if key in contacted_keys or not contacted_keys]
    for key in contacted_keys:
        if key not in ordered_keys:
            ordered_keys.append(key)

    rows: list[dict[str, Any]] = []
    decision_by_key = _latest_by_key([row for row in decisions if row.get("contacted") is True])
    for key in ordered_keys:
        base = dict(candidates.get(key) or {})
        approval = approvals.get(key) or {}
        decision = decision_by_key.get(key) or {}
        merged = {**approval, **base}
        merged["candidate_key"] = key
        merged["_decision"] = decision
        rows.append(merged)
    return rows


def _latest_identity_by_candidate(root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    rank = {"confirmed_bound": 4, "auto_bound": 3, "pending_confirmation": 2, "no_match": 1, "rejected": 1}
    for row in _load_jsonl(root / "state/cross-channel-identity-ledger.jsonl"):
        key = _string(row.get("source_candidate_key"))
        if not key:
            continue
        existing = latest.get(key)
        if existing is None or rank.get(_string(row.get("match_status")), 0) >= rank.get(_string(existing.get("match_status")), 0):
            latest[key] = row
    for row in _load_jsonl(root / "structured/cross-channel-bound-candidates.jsonl"):
        decision = row.get("decision") if isinstance(row.get("decision"), dict) else {}
        target = row.get("target") if isinstance(row.get("target"), dict) else {}
        maimai_hit = row.get("maimai_hit") if isinstance(row.get("maimai_hit"), dict) else {}
        key = _string(decision.get("source_candidate_key") or target.get("candidate_key"))
        if not key:
            continue
        latest[key] = {
            **latest.get(key, {}),
            "source_candidate_key": key,
            "match_status": _string(decision.get("match_status") or latest.get(key, {}).get("match_status") or "confirmed_bound"),
            "target_platform_id": _string(decision.get("target_platform_id") or maimai_hit.get("platform_id")),
            "target_profile_url": _string(decision.get("target_profile_url") or maimai_hit.get("profile_url")),
            "hit": maimai_hit,
        }
    return latest


def _main_db_ids_by_source(main_db_path: str | Path | None) -> dict[tuple[str, str], str]:
    if main_db_path is None:
        return {}
    db_path = Path(main_db_path)
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            """
            SELECT candidate_id, platform, platform_id
            FROM source_profiles
            WHERE platform IN ('boss_app', 'maimai')
            """
        ).fetchall()
        return {(str(platform), str(platform_id)): str(candidate_id) for candidate_id, platform, platform_id in rows if platform_id}
    finally:
        conn.close()
```

- [ ] **Step 3: Add report construction**

Append `build_delivery_report`:

```python
def _sync_counts(sync_result: dict[str, Any]) -> dict[str, int]:
    apply_result = sync_result.get("apply_result") if isinstance(sync_result.get("apply_result"), dict) else {}
    created = apply_result.get("created") if isinstance(apply_result.get("created"), dict) else {}
    merged = apply_result.get("merged") if isinstance(apply_result.get("merged"), dict) else {}
    conflicts = apply_result.get("conflicts") if isinstance(apply_result.get("conflicts"), dict) else {}
    skipped = apply_result.get("skipped") if isinstance(apply_result.get("skipped"), dict) else {}
    deleted = apply_result.get("deleted") if isinstance(apply_result.get("deleted"), dict) else {}
    return {
        "created_candidates": _int(created.get("candidates")),
        "created_details": _int(created.get("candidate_details")),
        "created_source_profiles": _int(created.get("source_profiles")),
        "created_field_values": _int(created.get("candidate_field_values")),
        "merged_candidates": _int(merged.get("candidates")),
        "conflicts": sum(_int(value) for value in conflicts.values()),
        "skipped": sum(_int(value) for value in skipped.values()),
        "deleted": sum(_int(value) for value in deleted.values()),
    }


def build_delivery_report(campaign_root: str | Path, main_db_path: str | Path | None = None) -> dict[str, Any]:
    root = Path(campaign_root)
    sourcing = _load_json(root / "reports/sourcing-summary.json")
    executor = _load_json(root / "reports/executor-summary.json", default={})
    match_summary = _load_json(root / "reports/maimai-match-summary.json", default={})
    sync_result = _load_json(root / "reports/main-db-sync-result.json", default={"status": "not_run"})
    contacted = _latest_contacted_candidates(root)
    identity_by_key = _latest_identity_by_candidate(root)
    main_ids = _main_db_ids_by_source(main_db_path)

    candidate_rows: list[dict[str, Any]] = []
    auto_bound_count = 0
    confirmed_bound_count = 0
    no_match_count = 0
    pending_count = 0
    for row in contacted:
        key = _string(row.get("candidate_key"))
        identity = identity_by_key.get(key, {})
        status = _string(identity.get("match_status") or "no_match")
        if status == "auto_bound":
            auto_bound_count += 1
        elif status == "confirmed_bound":
            confirmed_bound_count += 1
        elif status == "pending_confirmation":
            pending_count += 1
        else:
            no_match_count += 1
        platform_id = _string(identity.get("target_platform_id"))
        profile_url = _string(identity.get("target_profile_url"))
        main_id = main_ids.get(("boss_app", key)) or (main_ids.get(("maimai", platform_id)) if platform_id else "")
        decision = row.get("_decision") if isinstance(row.get("_decision"), dict) else {}
        screening = row.get("screening") if isinstance(row.get("screening"), dict) else {}
        candidate_rows.append(
            {
                "candidate_key": key,
                "real_name": _string(row.get("real_name")),
                "boss_display_name": _string(row.get("display_name")),
                "boss_company": _string(row.get("current_company")),
                "boss_title": _string(row.get("current_title")),
                "city": _string(row.get("city")),
                "education": _string(row.get("education")),
                "boss_score": _int(row.get("score") or screening.get("score")),
                "message_status": _string(decision.get("message_status") or row.get("message_status")),
                "maimai_match_status": status,
                "maimai_profile_url": profile_url,
                "maimai_platform_id": platform_id,
                "main_db_candidate_id": main_id,
                "reasons": row.get("reasons") or screening.get("reasons") or [],
                "risks": row.get("risks") or screening.get("risks") or [],
            }
        )

    return {
        "schema": REPORT_SCHEMA,
        "campaign_id": root.name,
        "generated_at": _now(),
        "source_files": {
            "sourcing_summary": "reports/sourcing-summary.json",
            "executor_summary": "reports/executor-summary.json",
            "maimai_match_summary": "reports/maimai-match-summary.json",
            "identity_ledger": "state/cross-channel-identity-ledger.jsonl",
            "main_db_sync_result": "reports/main-db-sync-result.json",
        },
        "boss_funnel": {
            "candidate_count": _int(sourcing.get("candidate_count")),
            "list_card_count": _int(sourcing.get("list_card_count")),
            "detail_count": _int(sourcing.get("detail_count")),
            "would_contact_count": _int(sourcing.get("would_contact_count")),
            "real_contact_count": _int(sourcing.get("real_contact_count")),
            "real_name_captured_count": _int(sourcing.get("real_name_captured_count")),
            "approved_queue_count": _int(executor.get("approved_queue_count")),
            "attempt_count": _int(executor.get("attempt_count")),
            "sent_count": _int(executor.get("sent_count")),
            "message_status_distribution": executor.get("message_status_distribution", {}),
        },
        "maimai_funnel": {
            "target_count": _int(match_summary.get("target_count")),
            "selected_count": _int(match_summary.get("selected_count")),
            "missing_real_name_count": _int(match_summary.get("missing_real_name_count")),
            "matched_count": auto_bound_count + confirmed_bound_count,
            "auto_bound_count": auto_bound_count,
            "confirmed_bound_count": confirmed_bound_count,
            "pending_confirmation_count": pending_count,
            "no_match_count": no_match_count,
        },
        "main_db_sync": {
            "status": _string(sync_result.get("status") or "not_run"),
            **_sync_counts(sync_result),
        },
        "candidate_rows": candidate_rows,
    }
```

- [ ] **Step 4: Add follow-up rows and renderers**

Append follow-up and Markdown rendering:

```python
def _join_values(values: Any) -> str:
    if isinstance(values, list):
        return "；".join(_string(value) for value in values if _string(value))
    return _string(values)


def build_follow_up_rows(campaign_root: str | Path, report: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in report["candidate_rows"]:
        status = _string(item.get("maimai_match_status") or "no_match")
        has_maimai = status in MATCHED_STATUSES and bool(_string(item.get("maimai_profile_url")))
        preferred_channel = "maimai" if has_maimai else "boss"
        if status in MATCHED_STATUSES:
            action = "优先脉脉触达，并同步记录 BOSS 会话回复"
            priority = "P1"
        elif status == "pending_confirmation":
            action = "先人工确认脉脉身份，同时保留 BOSS 会话跟进"
            priority = "P1"
        else:
            action = "继续 BOSS 会话跟进，必要时后续补充人工脉脉搜索"
            priority = "P2"
        rows.append(
            {
                "candidate_key": _string(item.get("candidate_key")),
                "real_name": _string(item.get("real_name")),
                "boss_display_name": _string(item.get("boss_display_name")),
                "boss_company": _string(item.get("boss_company")),
                "boss_title": _string(item.get("boss_title")),
                "city": _string(item.get("city")),
                "education": _string(item.get("education")),
                "boss_score": _string(item.get("boss_score")),
                "contact_status": "contacted",
                "message_status": _string(item.get("message_status") or "送达"),
                "maimai_match_status": status,
                "maimai_profile_url": _string(item.get("maimai_profile_url")),
                "maimai_platform_id": _string(item.get("maimai_platform_id")),
                "main_db_candidate_id": _string(item.get("main_db_candidate_id")),
                "follow_up_required": "true",
                "preferred_channel": preferred_channel,
                "follow_up_action": action,
                "priority": priority,
                "reasons": _join_values(item.get("reasons")),
                "risks": _join_values(item.get("risks")),
            }
        )
    return rows


def _render_report_md(report: dict[str, Any]) -> str:
    boss = report["boss_funnel"]
    maimai = report["maimai_funnel"]
    sync = report["main_db_sync"]
    lines = [
        "# BOSS-Maimai 寻访交付报告",
        "",
        f"- Campaign：{report['campaign_id']}",
        f"- BOSS 看过：{boss['list_card_count']} 人",
        f"- BOSS 详情：{boss['detail_count']} 人",
        f"- 已沟通：{boss['real_contact_count']} 人",
        f"- 脉脉匹配目标：{maimai['target_count']} 人",
        f"- 脉脉命中：{maimai['matched_count']} 人",
        f"- 主库新增：{sync['created_candidates']} 人",
        "",
        "## 漏斗",
        "",
        f"- 沟通送达：{boss['message_status_distribution']}",
        f"- 自动绑定：{maimai['auto_bound_count']}",
        f"- 用户确认绑定：{maimai['confirmed_bound_count']}",
        f"- 未命中：{maimai['no_match_count']}",
        "",
        "## 候选人状态",
        "",
        "| 姓名 | BOSS 公司 | BOSS 职位 | 脉脉状态 | 主库 ID | 跟进渠道 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in report["candidate_rows"]:
        channel = "maimai" if item.get("maimai_match_status") in MATCHED_STATUSES else "boss"
        lines.append(
            "| {real_name} | {company} | {title} | {status} | {main_id} | {channel} |".format(
                real_name=_string(item.get("real_name")),
                company=_string(item.get("boss_company")),
                title=_string(item.get("boss_title")),
                status=_string(item.get("maimai_match_status")),
                main_id=_string(item.get("main_db_candidate_id")),
                channel=channel,
            )
        )
    lines.extend(
        [
            "",
            "## 后续跟进",
            "",
            "所有已沟通 BOSS 人选都进入跟进表；脉脉命中只影响优先触达渠道，不影响是否需要跟进。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_follow_up_md(rows: list[dict[str, str]]) -> str:
    lines = [
        "# BOSS-Maimai 后续跟进表",
        "",
        "| 姓名 | 公司 | 职位 | 脉脉状态 | 优先渠道 | 下一步 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['real_name']} | {row['boss_company']} | {row['boss_title']} | {row['maimai_match_status']} | {row['preferred_channel']} | {row['follow_up_action']} |"
        )
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 5: Add quality gates and writers**

Append validation, file writing, and CLI:

```python
def validate_delivery_quality_gates(
    campaign_root: str | Path,
    report: dict[str, Any],
    follow_up_rows: list[dict[str, str]],
) -> dict[str, Any]:
    root = Path(campaign_root)
    blockers: list[str] = []
    required_files = [
        "reports/sourcing-summary.json",
        "structured/approved-contact-queue.jsonl",
        "structured/maimai-match-targets.jsonl",
        "state/cross-channel-identity-ledger.jsonl",
    ]
    missing = [path for path in required_files if not (root / path).exists()]
    if missing:
        blockers.append("missing_required_inputs")
    real_contact_count = _int(report["boss_funnel"].get("real_contact_count"))
    follow_up_row_count = len(follow_up_rows)
    target_count = _int(report["maimai_funnel"].get("target_count"))
    real_name_count = _int(report["boss_funnel"].get("real_name_captured_count"))
    matched_count = _int(report["maimai_funnel"].get("matched_count"))
    main_db_created = _int(report["main_db_sync"].get("created_candidates"))
    if follow_up_row_count != real_contact_count:
        blockers.append("follow_up_row_count_mismatch")
    if target_count != real_name_count:
        blockers.append("maimai_target_count_mismatch")
    if matched_count > target_count:
        blockers.append("maimai_matched_exceeds_targets")
    if main_db_created > matched_count:
        blockers.append("main_db_created_exceeds_matched")
    if any(row.get("follow_up_required") != "true" for row in follow_up_rows):
        blockers.append("follow_up_required_not_true")
    if any(row.get("preferred_channel") == "maimai" and not row.get("maimai_profile_url") for row in follow_up_rows):
        blockers.append("maimai_channel_without_profile_url")
    matched_keys = {row["candidate_key"] for row in follow_up_rows}
    candidate_keys = {_string(row.get("candidate_key")) for row in report["candidate_rows"]}
    if matched_keys != candidate_keys:
        blockers.append("candidate_rows_follow_up_mismatch")
    gates = {
        "schema": GATE_SCHEMA,
        "checked_at": _now(),
        "status": "blocked" if blockers else "passed",
        "blockers": blockers,
        "missing_required_inputs": missing,
        "real_contact_count": real_contact_count,
        "follow_up_row_count": follow_up_row_count,
        "maimai_target_count": target_count,
        "real_name_captured_count": real_name_count,
        "maimai_matched_count": matched_count,
        "main_db_created_candidates": main_db_created,
    }
    _write_json(root / GATES_JSON, gates)
    return gates


def _write_follow_up_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FOLLOW_UP_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def write_delivery_package(
    campaign_root: str | Path,
    *,
    main_db_path: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    report = build_delivery_report(root, main_db_path=main_db_path)
    follow_up_rows = build_follow_up_rows(root, report)
    gates = validate_delivery_quality_gates(root, report, follow_up_rows)
    _write_json(root / REPORT_JSON, report)
    (root / REPORT_MD).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT_MD).write_text(_render_report_md(report), encoding="utf-8")
    _write_follow_up_csv(root / FOLLOW_UP_CSV, follow_up_rows)
    (root / FOLLOW_UP_MD).write_text(_render_follow_up_md(follow_up_rows), encoding="utf-8")
    return {
        "schema": "boss_maimai_campaign_delivery_write_result_v1",
        "status": gates["status"],
        "campaign_id": root.name,
        "quality_gates": gates,
        "outputs": {
            "report_json": REPORT_JSON,
            "report_md": REPORT_MD,
            "follow_up_csv": FOLLOW_UP_CSV,
            "follow_up_md": FOLLOW_UP_MD,
            "quality_gates": GATES_JSON,
        },
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 BOSS-Maimai campaign 交付包")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--campaign-root", required=True)
    build.add_argument("--main-db", default="")
    manifest = subparsers.add_parser("manifest")
    manifest.add_argument("--campaign-root", required=True)
    manifest.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        result = write_delivery_package(
            args.campaign_root,
            main_db_path=args.main_db or None,
        )
    else:
        result = write_feishu_manifest(args.campaign_root, dry_run=bool(args.dry_run))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 1 if result.get("status") == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_campaign_delivery.py -q
```

Expected: tests still fail only for undefined Feishu manifest functions.

---

### Task 3: Add Feishu-Safe Manifest for the New Campaign Package

**Files:**
- Modify: `scripts/boss_maimai_campaign_delivery.py`
- Test: `tests/test_boss_maimai_campaign_delivery.py`

- [ ] **Step 1: Add manifest functions**

Insert these functions before `_parser` in `scripts/boss_maimai_campaign_delivery.py`:

```python
def _relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _assert_manifest_safe(manifest: dict[str, Any]) -> None:
    serialized = json.dumps(manifest, ensure_ascii=False).lower().replace("\\", "/")
    for marker in FORBIDDEN_MANIFEST_MARKERS:
        if marker in serialized:
            raise ValueError(f"manifest contains forbidden marker: {marker}")


def build_feishu_manifest(campaign_root: str | Path, *, dry_run: bool) -> dict[str, Any]:
    root = Path(campaign_root)
    report_path = root / REPORT_MD
    follow_up_path = root / FOLLOW_UP_CSV
    gates_path = root / GATES_JSON
    for path in [report_path, follow_up_path, gates_path]:
        if not path.exists():
            raise FileNotFoundError(path)
    gates = _load_json(gates_path)
    if gates.get("status") != "passed":
        return {
            "schema": MANIFEST_SCHEMA,
            "campaign_id": root.name,
            "dry_run": bool(dry_run),
            "status": "blocked",
            "reason": "quality_gates_not_passed",
            "quality_gates": gates,
        }
    manifest = {
        "schema": MANIFEST_SCHEMA,
        "campaign_id": root.name,
        "dry_run": bool(dry_run),
        "status": "ready",
        "old_top30_package_policy": "keep_unchanged",
        "source_files": {
            "delivery_report": _relative(report_path, root),
            "follow_up_queue": _relative(follow_up_path, root),
            "quality_gates": _relative(gates_path, root),
        },
        "commands": [
            [
                "lark-cli",
                "drive",
                "+import",
                "--type",
                "docx",
                "--as",
                "user",
                "--file",
                _relative(report_path, root),
                "--name",
                f"{root.name} BOSS寻访交付报告",
            ],
            [
                "lark-cli",
                "sheets",
                "+create",
                "--title",
                f"{root.name} BOSS跟进表",
            ],
            [
                "lark-cli",
                "sheets",
                "+append",
                "--spreadsheet-token",
                "<new_boss_follow_up_sheet_token>",
                "--range",
                "<first_sheet_id>",
                "--file",
                _relative(follow_up_path, root),
            ],
        ],
        "readback_expectations": {
            "new_report_title_contains": "BOSS寻访交付报告",
            "new_sheet_title_contains": "BOSS跟进表",
            "follow_up_row_count": gates["follow_up_row_count"],
            "old_top30_package": "not_modified",
        },
    }
    if dry_run:
        for command in manifest["commands"]:
            if command[0:2] != ["lark-cli", "sheets"] or "+append" not in command:
                command.append("--dry-run")
    _assert_manifest_safe(manifest)
    return manifest


def write_feishu_manifest(campaign_root: str | Path, *, dry_run: bool) -> dict[str, Any]:
    root = Path(campaign_root)
    manifest = build_feishu_manifest(root, dry_run=dry_run)
    _write_json(root / MANIFEST_JSON, manifest)
    return manifest
```

- [ ] **Step 2: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_boss_maimai_campaign_delivery.py -q
```

Expected: all tests in `tests/test_boss_maimai_campaign_delivery.py` pass.

---

### Task 4: Update Main Sync Handoff Away from JD Delivery

**Files:**
- Modify: `tests/test_campaign_to_delivery.py`
- Modify: `scripts/campaign_to_delivery.py`

- [ ] **Step 1: Update failing test expectations**

In `tests/test_campaign_to_delivery.py`, rename `test_sync_main_exports_bundle_applies_and_writes_handoff` to:

```python
def test_sync_main_exports_bundle_applies_and_writes_campaign_delivery_handoff(tmp_path: Path) -> None:
```

Inside that test, replace the handoff assertions with:

```python
    handoff = json.loads(
        (root / "state/boss-maimai-delivery-handoff.json").read_text(encoding="utf-8")
    )
    assert handoff["schema"] == "boss_maimai_campaign_delivery_handoff_v1"
    assert handoff["main_db_path"] == str(main_db)
    assert handoff["delivery_kind"] == "boss_maimai_campaign_delivery"
    assert handoff["delivery_context"]["top_n"] == 30
    assert handoff["outputs"]["report_json"] == "reports/boss-maimai-delivery-report.json"
    assert not (root / "state/jd-delivery-handoff.json").exists()
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_campaign_to_delivery.py::test_sync_main_exports_bundle_applies_and_writes_campaign_delivery_handoff -q
```

Expected: failure because `state/boss-maimai-delivery-handoff.json` is not created.

- [ ] **Step 3: Modify `campaign_to_delivery.py` handoff constants and writer**

In `scripts/campaign_to_delivery.py`, replace:

```python
HANDOFF_PATH = "state/jd-delivery-handoff.json"
```

with:

```python
HANDOFF_PATH = "state/boss-maimai-delivery-handoff.json"
```

Replace `_write_handoff` with:

```python
def _write_handoff(
    root: Path,
    main_db_path: Path,
    delivery_context: dict[str, Any],
) -> dict[str, Any]:
    handoff = {
        "schema": "boss_maimai_campaign_delivery_handoff_v1",
        "created_at": _now(),
        "main_db_path": str(main_db_path),
        "delivery_kind": "boss_maimai_campaign_delivery",
        "delivery_script": "scripts/boss_maimai_campaign_delivery.py",
        "delivery_context": delivery_context,
        "outputs": {
            "report_json": "reports/boss-maimai-delivery-report.json",
            "report_md": "reports/boss-maimai-delivery-report.md",
            "follow_up_csv": "reports/boss-maimai-follow-up-queue.csv",
            "quality_gates": "reports/boss-maimai-delivery-quality-gates.json",
        },
        "legacy_jd_delivery_default": False,
    }
    _write_json(root / HANDOFF_PATH, handoff)
    return handoff
```

- [ ] **Step 4: Run campaign-to-delivery tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_campaign_to_delivery.py -q
```

Expected: all campaign-to-delivery tests pass.

---

### Task 5: Update Agent Contracts and Architecture Tests

**Files:**
- Modify: `tests/test_agent_architecture.py`
- Modify: `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`
- Modify: `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`

- [ ] **Step 1: Add failing architecture test**

Append this test near the existing BOSS-Maimai contract tests in `tests/test_agent_architecture.py`:

```python
def test_boss_maimai_cross_channel_s10_is_campaign_delivery_not_jd_default():
    skill = (
        ROOT
        / "agents"
        / "skills"
        / "boss-maimai-cross-channel-delivery"
        / "SKILL.md"
    ).read_text(encoding="utf-8")
    workflow = (
        ROOT
        / "agents"
        / "workflows"
        / "boss-maimai-cross-channel-delivery"
        / "AGENT.md"
    ).read_text(encoding="utf-8")
    s10_text = markdown_section(workflow, "S10 BOSS campaign delivery / 飞书交付")

    for text in (skill, workflow):
        assert "`reports/boss-maimai-delivery-report.json`" in text
        assert "`reports/boss-maimai-follow-up-queue.csv`" in text
        assert "`reports/boss-maimai-delivery-quality-gates.json`" in text
        assert "已沟通 BOSS 人选" in text
        assert "旧 Top30 飞书包保持不动" in text
        assert "不默认交接 `jd-talent-delivery`" in text

    assert "follow_up_row_count == real_contact_count" in s10_text
    assert "`scripts/boss_maimai_campaign_delivery.py build`" in s10_text
    assert "`scripts/boss_maimai_campaign_delivery.py manifest`" in s10_text
    assert "旧 Top30 飞书包保持不动" in s10_text
    assert "jd-talent-delivery" not in s10_text
```

- [ ] **Step 2: Run the architecture test to verify it fails**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_maimai_cross_channel_s10_is_campaign_delivery_not_jd_default -q
```

Expected: failure because the S10 section still references JD delivery.

- [ ] **Step 3: Update skill contract**

In `agents/skills/boss-maimai-cross-channel-delivery/SKILL.md`:

- Change frontmatter description to:

```markdown
description: "BOSS App 已筛优质人选补脉脉主页匹配、多渠道 Campaign DB 整合、主库同步和 BOSS campaign 交付。"
```

- Replace the goal paragraph ending with `继续交接给 jd-talent-delivery 做 JD/飞书交付。` with:

```markdown
把 BOSS App 已筛出的优质人选作为主线，补充脉脉主页和详情证据，形成可审计、可回滚、可同步的多渠道 Campaign DB，并在授权后同步到 `data/talent.db`。主库同步后生成本次 BOSS campaign 的任务摘要、交付报告和后续跟进表；不默认交接 `jd-talent-delivery`，不把全库 Top30 当作本次寻访交付。
```

- In output artifacts, add:

```markdown
- `reports/boss-maimai-delivery-report.json`：本次 BOSS-Maimai campaign 交付报告。
- `reports/boss-maimai-delivery-report.md`：面向飞书阅读的交付报告。
- `reports/boss-maimai-follow-up-queue.csv`：所有已沟通 BOSS 人选的后续跟进表。
- `reports/boss-maimai-delivery-quality-gates.json`：交付报告与跟进表质量门禁。
- `feishu/boss-maimai-delivery-manifest.json`：只发布新 BOSS campaign 交付包的飞书 manifest。
```

- Replace the `## 自动交接` section with:

```markdown
## 自动交接

执行入口为 `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`。workflow 完成 S9 主库 sync dry-run 与 apply 后，写入 `state/boss-maimai-delivery-handoff.json`，并进入 S10 BOSS campaign delivery。

S10 必须生成 `reports/boss-maimai-delivery-report.json`、`reports/boss-maimai-follow-up-queue.csv` 和 `reports/boss-maimai-delivery-quality-gates.json`。跟进表以已沟通 BOSS 人选为全集；脉脉匹配成功只影响优先触达渠道，不影响是否需要跟进。

旧 Top30 飞书包保持不动。`jd-talent-delivery` 只能作为后续独立 JD 推荐任务手动触发，不默认作为 BOSS-Maimai workflow 的交付闭环。
```

- [ ] **Step 4: Update workflow S10**

In `agents/workflows/boss-maimai-cross-channel-delivery/AGENT.md`, replace the entire `### S10 JD delivery / 飞书交付` section with:

```markdown
### S10 BOSS campaign delivery / 飞书交付

主库同步完成后，写 `state/boss-maimai-delivery-handoff.json`，列出本次 campaign 的主库同步结果、候选人范围和交付产物目标。随后执行本次 BOSS campaign 级交付，不默认交接 `jd-talent-delivery`。

交付包必须回答：

- BOSS 看过多少人、进入多少详情、计划沟通多少人、实际沟通多少人。
- 沟通了哪些已沟通 BOSS 人选。
- 哪些人进入脉脉匹配目标。
- 哪些人脉脉命中、自动绑定或用户确认绑定。
- 哪些人最终写入主库。
- 所有已沟通人选的后续跟进动作和优先触达渠道。

执行：

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery build \
  --campaign-root <campaign_root> \
  --main-db data/talent.db
```

质量门禁必须包含：

- `follow_up_row_count == real_contact_count`
- `maimai_target_count == real_name_captured_count`
- `maimai_matched_count <= maimai_target_count`
- `main_db_created_candidates <= maimai_matched_count`
- 所有 follow-up 行 `follow_up_required=true`
- 未命中脉脉的人选仍出现在跟进表
- 交付包不读取、不引用全库 Top30 推荐目录

飞书发布只创建新的 BOSS campaign 交付包：

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery manifest \
  --campaign-root <campaign_root> \
  --dry-run
```

旧 Top30 飞书包保持不动，不追加说明、不移动、不删除。飞书真实发布前必须确认 `reports/boss-maimai-delivery-quality-gates.json` 为 `passed`，并完成 dry-run manifest 检查。

`jd-talent-delivery` 只可作为后续独立 JD 推荐任务由用户另行触发，不作为本 workflow 的默认 S10。
```

- [ ] **Step 5: Run architecture tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_agent_architecture.py::test_boss_maimai_cross_channel_s10_is_campaign_delivery_not_jd_default tests/test_agent_architecture.py::test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates -q
```

Expected: selected architecture tests pass. If `test_boss_maimai_cross_channel_contracts_define_merge_and_sync_gates` still asserts `jd-talent-delivery`, update that assertion to the new handoff file and campaign delivery outputs.

---

### Task 6: Run Current Campaign Read-Only Package Generation

**Files:**
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-delivery-report.json`
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-delivery-report.md`
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-follow-up-queue.csv`
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-follow-up-queue.md`
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-delivery-quality-gates.json`
- Generated: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/feishu/boss-maimai-delivery-manifest.json`

- [ ] **Step 1: Build the campaign package locally**

Run:

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery build \
  --campaign-root data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05 \
  --main-db data/talent.db
```

Expected output includes:

```json
{"status": "passed"}
```

- [ ] **Step 2: Verify key counts**

Run:

```bash
jq '{boss: .boss_funnel, maimai: .maimai_funnel, main_db: .main_db_sync, names: [.candidate_rows[].real_name]}' \
  data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-delivery-report.json
```

Expected evidence:

```json
{
  "boss": {
    "list_card_count": 16,
    "detail_count": 16,
    "real_contact_count": 5
  },
  "maimai": {
    "target_count": 5,
    "matched_count": 2
  },
  "main_db": {
    "created_candidates": 2
  },
  "names": ["孙同", "罗力睿", "汪婧昀", "周超", "王若帆"]
}
```

- [ ] **Step 3: Verify follow-up table row count and channels**

Run:

```bash
.venv/bin/python - <<'PY'
import csv
from pathlib import Path
path = Path("data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-follow-up-queue.csv")
rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
print(len(rows))
print([(r["real_name"], r["maimai_match_status"], r["preferred_channel"], r["main_db_candidate_id"]) for r in rows])
PY
```

Expected:

```text
5
[('孙同', 'no_match', 'boss', ''), ('罗力睿', 'no_match', 'boss', ''), ('汪婧昀', 'no_match', 'boss', ''), ('周超', 'confirmed_bound', 'maimai', '56195'), ('王若帆', 'auto_bound', 'maimai', '56194')]
```

- [ ] **Step 4: Generate dry-run Feishu manifest**

Run:

```bash
.venv/bin/python -m scripts.boss_maimai_campaign_delivery manifest \
  --campaign-root data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05 \
  --dry-run
```

Expected: `status` is `ready`, and the manifest references only:

- `reports/boss-maimai-delivery-report.md`
- `reports/boss-maimai-follow-up-queue.csv`
- `reports/boss-maimai-delivery-quality-gates.json`

- [ ] **Step 5: Verify the old Top30 package was not touched**

Run:

```bash
git diff -- data/output/jd-tencent-game-ai-infra-training-inference-2026-06-06
```

Expected: no output.

---

### Task 7: Full Verification

**Files:**
- All modified files from earlier tasks

- [ ] **Step 1: Run focused tests**

Run:

```bash
.venv/bin/python -m pytest \
  tests/test_boss_maimai_campaign_delivery.py \
  tests/test_campaign_to_delivery.py \
  tests/test_agent_architecture.py \
  -q
```

Expected: selected tests pass.

- [ ] **Step 2: Run full tests**

Run:

```bash
.venv/bin/python -m pytest tests -q
```

Expected: full suite passes. Existing warning from `tests/test_boss.py::TestBossGetDetailUnavailable::test_get_detail_returns_none` may remain.

- [ ] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Update task ledger review**

Update `tasks/todo.md` Active Task with:

```markdown
#### Review

- 已修正 BOSS-Maimai S10 交付语义：默认生成 campaign 级交付报告和跟进表，不再默认交接全库 `jd-talent-delivery`。
- 当前 campaign 已生成 BOSS 寻访交付报告和 5 行跟进表；脉脉命中 2 人，未命中 3 人仍保留 BOSS 跟进。
- 验证：记录 focused tests、full tests 和 `git diff --check` 的实际输出。
```

---

### Task 8: Optional New Feishu Campaign Package Publish

**Files:**
- Uses: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/feishu/boss-maimai-delivery-manifest.json`
- Generated only after live publish: `data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/feishu/boss-maimai-delivery-publish-results.json`

- [ ] **Step 1: Confirm quality gates are passed**

Run:

```bash
jq '.status, .follow_up_row_count, .real_contact_count' \
  data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/reports/boss-maimai-delivery-quality-gates.json
```

Expected:

```text
"passed"
5
5
```

- [ ] **Step 2: Check Feishu CLI auth without writing cloud state**

Run:

```bash
lark-cli auth status
```

Expected: logged-in user status. If auth is expired, stop and ask user to reauthenticate.

- [ ] **Step 3: Execute only the new package commands from the manifest**

Use the manifest commands to create a new BOSS delivery doc and a new BOSS follow-up sheet. Do not run any command against the old Top30 doc, old recommendation doc, old outreach Sheet, or `data/output/jd-tencent-game-ai-infra-training-inference-2026-06-06`.

Record every `lark-cli` command result in:

```text
data/campaigns/tencent-game-ai-infra-boss-maimai-2026-06-05/feishu/boss-maimai-delivery-publish-results.json
```

- [ ] **Step 4: Read back the new Feishu artifacts**

Verify:

- New document title contains `BOSS寻访交付报告`.
- New Sheet title contains `BOSS跟进表`.
- New Sheet has 5 data rows.
- Old Top30 Feishu package was not modified.

Stop and report exact command output if any cloud write or readback fails.

---

## Self-Review Checklist

- Spec coverage: Tasks 1-3 implement report, follow-up table, quality gates, and new manifest. Task 4 removes default JD handoff. Task 5 updates canonical contracts. Task 6 verifies current campaign counts. Task 8 covers optional new Feishu package publishing while leaving the old Top30 package unchanged.
- Placeholder scan: no placeholder task remains; all tests, commands, and expected outputs are concrete.
- Type consistency: script functions used by tests are `build_delivery_report`, `build_follow_up_rows`, `validate_delivery_quality_gates`, `write_delivery_package`, `build_feishu_manifest`, `write_feishu_manifest`, and `main`; the plan defines each before use.
