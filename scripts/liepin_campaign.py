"""猎聘 P0 campaign 文件系统辅助函数。"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "liepin_talent_search_campaign_v1"


@dataclass(frozen=True)
class LiepinCampaignPaths:
    root: Path
    campaign_id: str
    manifest: Path
    requirements: Path
    strategy: Path
    run_policy: Path
    state_dir: Path
    raw_dir: Path
    raw_condition_dir: Path
    raw_search_dir: Path
    structured_dir: Path
    reports_dir: Path
    request_ledger: Path
    continuation_plan: Path
    events: Path
    candidate_summaries: Path
    search_summary_json: Path
    search_summary_md: Path


def campaign_paths(root: str | Path, campaign_id: str | None = None) -> LiepinCampaignPaths:
    root_path = Path(root)
    resolved_id = campaign_id or root_path.name
    state_dir = root_path / "state"
    raw_dir = root_path / "raw"
    structured_dir = root_path / "structured"
    reports_dir = root_path / "reports"
    return LiepinCampaignPaths(
        root=root_path,
        campaign_id=resolved_id,
        manifest=root_path / "campaign-manifest.json",
        requirements=root_path / "requirements.json",
        strategy=root_path / "strategy.json",
        run_policy=root_path / "run-policy.json",
        state_dir=state_dir,
        raw_dir=raw_dir,
        raw_condition_dir=raw_dir / "condition",
        raw_search_dir=raw_dir / "search",
        structured_dir=structured_dir,
        reports_dir=reports_dir,
        request_ledger=state_dir / "request-ledger.jsonl",
        continuation_plan=state_dir / "continuation-plan.json",
        events=state_dir / "events.jsonl",
        candidate_summaries=structured_dir / "candidate-summaries.jsonl",
        search_summary_json=reports_dir / "search-summary.json",
        search_summary_md=reports_dir / "search-summary.md",
    )


def atomic_write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            delete=False,
            dir=target.parent,
            encoding="utf-8-sig",
            prefix=target.name + ".",
            suffix=".tmp",
        ) as tmp:
            tmp_path = Path(tmp.name)
            tmp.write(json.dumps(data, ensure_ascii=False, indent=2))
        os.replace(tmp_path, target)
    except Exception:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
        raise


def append_jsonl(path: str | Path, item: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def ensure_campaign(root: str | Path, campaign_id: str | None = None) -> LiepinCampaignPaths:
    paths = campaign_paths(root, campaign_id)
    for directory in (
        paths.root,
        paths.state_dir,
        paths.raw_dir,
        paths.raw_condition_dir,
        paths.raw_search_dir,
        paths.structured_dir,
        paths.reports_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    if not paths.manifest.exists():
        atomic_write_json(
            paths.manifest,
            {
                "campaign_id": paths.campaign_id,
                "created_at": _now(),
                "schema": MANIFEST_SCHEMA,
            },
        )
    else:
        manifest = json.loads(paths.manifest.read_text(encoding="utf-8-sig"))
        if manifest.get("campaign_id") != paths.campaign_id:
            raise ValueError(
                "campaign manifest campaign_id mismatch: "
                f"expected {paths.campaign_id!r}, got {manifest.get('campaign_id')!r}"
            )
        if manifest.get("schema") != MANIFEST_SCHEMA:
            raise ValueError(
                "campaign manifest schema mismatch: "
                f"expected {MANIFEST_SCHEMA!r}, got {manifest.get('schema')!r}"
            )
    return paths


def page_raw_path(paths: LiepinCampaignPaths, cur_page: int) -> Path:
    if type(cur_page) is not int or cur_page < 0:
        raise ValueError("cur_page must be non-negative")
    return paths.raw_search_dir / f"page-{cur_page:03d}.json"


def append_request_ledger(paths: LiepinCampaignPaths, item: dict[str, Any]) -> dict[str, Any]:
    record = {**item, "ts": _now()}
    append_jsonl(paths.request_ledger, record)
    return record


def mark_page_completed(
    paths: LiepinCampaignPaths,
    *,
    cur_page: int,
    payload: dict[str, Any],
    request: dict[str, Any],
    run_id: str = "",
) -> Path:
    raw_path = page_raw_path(paths, cur_page)
    atomic_write_json(
        raw_path,
        {
            "curPage": cur_page,
            "payload": payload,
            "request": request,
            "run_id": run_id,
            "completed_at": _now(),
        },
    )
    append_request_ledger(
        paths,
        {
            "event": "page_completed",
            "curPage": cur_page,
            "raw_path": raw_path.as_posix(),
            "run_id": run_id,
        },
    )
    return raw_path


def load_completed_pages(paths: LiepinCampaignPaths) -> set[int]:
    completed: set[int] = set()
    for raw_path in paths.raw_search_dir.glob("page-*.json"):
        stem = raw_path.stem
        try:
            page = int(stem.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            continue
        if page < 0:
            continue
        try:
            payload = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("curPage") == page:
            completed.add(page)
    return completed


def write_continuation_plan(
    paths: LiepinCampaignPaths,
    *,
    next_cur_page: int,
    reason: str,
    ck_id: str = "",
    sk_id: str = "",
    fk_id: str = "",
) -> dict[str, Any]:
    if type(next_cur_page) is not int or next_cur_page < 0:
        raise ValueError("next_cur_page must be non-negative")
    plan = {
        "campaign_id": paths.campaign_id,
        "reason": reason,
        "next_cur_page": next_cur_page,
        "ckId": ck_id,
        "skId": sk_id,
        "fkId": fk_id,
        "updated_at": _now(),
    }
    atomic_write_json(paths.continuation_plan, plan)
    return plan
