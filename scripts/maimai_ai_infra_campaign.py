"""AI Infra V2 campaign runtime helpers."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CampaignPaths:
    root: Path
    campaign_id: str
    manifest: Path
    db: Path
    strategy: Path
    search_plan: Path
    search_units: Path
    state_dir: Path
    raw_dir: Path
    raw_search_dir: Path
    contacts_dir: Path
    reports_dir: Path
    review_dir: Path
    search_progress: Path
    search_events: Path
    import_ledger: Path
    detail_progress: Path


def campaign_paths(root: str | Path, campaign_id: str | None = None) -> CampaignPaths:
    root_path = Path(root)
    resolved_id = campaign_id or root_path.name
    state_dir = root_path / "state"
    raw_dir = root_path / "raw"
    return CampaignPaths(
        root=root_path,
        campaign_id=resolved_id,
        manifest=root_path / "campaign-manifest.json",
        db=root_path / "talent.db",
        strategy=root_path / "strategy.json",
        search_plan=root_path / "search-plan.json",
        search_units=root_path / "search-units.jsonl",
        state_dir=state_dir,
        raw_dir=raw_dir,
        raw_search_dir=raw_dir / "search",
        contacts_dir=raw_dir / "contacts",
        reports_dir=root_path / "reports",
        review_dir=root_path / "review",
        search_progress=state_dir / "search-progress.json",
        search_events=state_dir / "search-events.jsonl",
        import_ledger=state_dir / "import-ledger.jsonl",
        detail_progress=state_dir / "detail-progress.json",
    )


def atomic_write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    os.replace(tmp, target)


def append_jsonl(path: str | Path, item: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def ensure_campaign(root: str | Path, campaign_id: str | None = None) -> CampaignPaths:
    paths = campaign_paths(root, campaign_id)
    for directory in (
        paths.root,
        paths.state_dir,
        paths.raw_dir,
        paths.raw_search_dir,
        paths.contacts_dir,
        paths.reports_dir,
        paths.review_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    if not paths.manifest.exists():
        atomic_write_json(
            paths.manifest,
            {
                "campaign_id": paths.campaign_id,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "schema": "maimai_ai_infra_v2_campaign",
            },
        )
    return paths
