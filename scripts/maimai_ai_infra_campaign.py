"""AI Infra V2 campaign runtime helpers."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "maimai_ai_infra_v2_campaign"
RAW_UNIT_PATTERN = re.compile(r"^unit-\d{6}$")
RAW_PAGE_PATTERN = re.compile(r"^page-(\d{3})\.json$")


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


def page_raw_path(paths: CampaignPaths, unit_id: str, page: int) -> Path:
    return paths.raw_search_dir / unit_id / f"page-{page:03d}.json"


def read_search_progress(paths: CampaignPaths) -> dict[str, Any]:
    if not paths.search_progress.exists():
        return {"campaign_id": paths.campaign_id, "units": {}}
    return json.loads(paths.search_progress.read_text(encoding="utf-8-sig"))


def write_search_progress(paths: CampaignPaths, progress: dict[str, Any]) -> None:
    atomic_write_json(paths.search_progress, progress)


def append_search_event(paths: CampaignPaths, item: dict[str, Any]) -> None:
    event = {**item, "ts": datetime.now(UTC).isoformat(timespec="seconds")}
    append_jsonl(paths.search_events, event)


def append_import_ledger(paths: CampaignPaths, item: dict[str, Any]) -> None:
    ledger_item = {**item, "ts": datetime.now(UTC).isoformat(timespec="seconds")}
    append_jsonl(paths.import_ledger, ledger_item)


def import_ledger_has_apply(paths: CampaignPaths, wave_id: str) -> bool:
    if not paths.import_ledger.exists():
        return False
    for line_number, line in enumerate(paths.import_ledger.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed import ledger line {line_number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"malformed import ledger line {line_number}: expected object")
        if (
            item.get("wave_id") == wave_id
            and item.get("action") == "apply"
            and item.get("status") == "completed"
        ):
            return True
    return False


def mark_page_completed(
    paths: CampaignPaths,
    unit_id: str,
    page: int,
    payload: dict[str, Any],
) -> None:
    if not isinstance(payload.get("contacts"), list):
        raise ValueError("page payload contacts must be a list")
    normalized_payload = {**payload, "unit_id": unit_id, "page": page}
    raw_path = page_raw_path(paths, unit_id, page)
    atomic_write_json(raw_path, normalized_payload)
    progress = read_search_progress(paths)
    unit = progress.setdefault("units", {}).setdefault(
        unit_id,
        {"pages": {}, "status": "running"},
    )
    unit.setdefault("pages", {})[str(page)] = {
        "status": "completed",
        "raw_path": str(raw_path),
        "completed_at": datetime.now().isoformat(timespec="seconds"),
    }
    write_search_progress(paths, progress)
    append_search_event(paths, {"event": "page_completed", "unit_id": unit_id, "page": page})


def load_completed_pages(paths: CampaignPaths) -> set[tuple[str, int]]:
    completed: set[tuple[str, int]] = set()
    for raw_path in paths.raw_search_dir.glob("unit-*/page-*.json"):
        unit_id = raw_path.parent.name
        page_match = RAW_PAGE_PATTERN.fullmatch(raw_path.name)
        if RAW_UNIT_PATTERN.fullmatch(unit_id) is None or page_match is None:
            continue
        page = int(page_match.group(1))
        if page <= 0:
            continue
        try:
            payload = json.loads(raw_path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("unit_id") != unit_id:
            continue
        if payload.get("page") != page:
            continue
        if not isinstance(payload.get("contacts"), list):
            continue
        completed.add((unit_id, page))
    return completed


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
