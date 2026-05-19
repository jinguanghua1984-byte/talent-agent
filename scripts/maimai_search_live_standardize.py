"""将搜索 live-run 结果标准化为 campaign canonical raw。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_campaign import ensure_campaign, mark_page_completed, page_raw_path


UNIT_ID_PATTERN = re.compile(r"^unit-\d{6}$")
PAYLOAD_COMPARE_KEYS = {
    "unit_id",
    "wave_id",
    "page",
    "source_run",
    "source_run_id",
    "request",
    "responseSummary",
    "responseData",
    "responseRawPreview",
    "contacts",
}


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_wave_id(run: dict[str, Any]) -> str:
    for key in ("wave_id", "gate"):
        value = run.get(key)
        if isinstance(value, str) and value:
            return value
        if value is not None and not isinstance(value, (dict, list)):
            return str(value)
    return ""


def _page_value(page: dict[str, Any], batch: dict[str, Any], key: str, default: Any) -> Any:
    if key in page:
        return page[key]
    return batch.get(key, default)


def _skip_evidence(
    run: dict[str, Any],
    batch: dict[str, Any] | None = None,
    page_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {}
    if "status" in run:
        evidence["run_status"] = run.get("status")
    if "stopReason" in run:
        evidence["run_stop_reason"] = run.get("stopReason")
    if batch is not None and "error" in batch:
        evidence["batch_error"] = batch.get("error")
    if page_item is not None and "error" in page_item:
        evidence["page_error"] = page_item.get("error")
    if page_item is not None and "responseSummary" in page_item:
        evidence["responseSummary"] = page_item.get("responseSummary")
    elif batch is not None and "responseSummary" in batch:
        evidence["responseSummary"] = batch.get("responseSummary")
    return {key: value for key, value in evidence.items() if value is not None}


def _skip(
    skipped_pages: list[dict[str, Any]],
    reason: str,
    batch_index: int,
    page_index: int | None = None,
    unit_id: str | None = None,
    page: Any = None,
    evidence: dict[str, Any] | None = None,
) -> None:
    item: dict[str, Any] = {
        "reason": reason,
        "batch_index": batch_index,
    }
    if page_index is not None:
        item["page_index"] = page_index
    if unit_id is not None:
        item["unit_id"] = unit_id
    if page is not None:
        item["page"] = page
    if evidence:
        item.update(evidence)
    skipped_pages.append(item)


def _is_equivalent_raw(existing: Any, payload: dict[str, Any]) -> bool:
    if not isinstance(existing, dict):
        return False
    for key in PAYLOAD_COMPARE_KEYS:
        if existing.get(key) != payload.get(key):
            return False
    return True


def _existing_raw_matches(raw_path: Path, payload: dict[str, Any]) -> bool:
    try:
        existing = _load_json(raw_path)
    except json.JSONDecodeError:
        return False
    return _is_equivalent_raw(existing, payload)


def standardize_live_run(campaign_root: str | Path, run_path: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    source_run = Path(run_path)
    run = _load_json(source_run)
    if not isinstance(run, dict):
        raise ValueError("live-run JSON must be an object")

    written_pages = 0
    skipped_pages: list[dict[str, Any]] = []
    wave_id = _run_wave_id(run)
    source_run_id = str(run.get("run_id") or "")
    batches = run.get("batches", [])
    if not isinstance(batches, list):
        raise ValueError("live-run batches must be a list")

    for batch_index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            _skip(skipped_pages, "invalid_batch", batch_index, evidence=_skip_evidence(run))
            continue

        batch_id = batch.get("batch_id")
        unit_id = batch_id if isinstance(batch_id, str) and UNIT_ID_PATTERN.fullmatch(batch_id) else None
        invalid_batch_id = isinstance(batch_id, str) and batch_id != "" and unit_id is None
        pages = batch.get("pages", [])
        if not isinstance(pages, list):
            _skip(
                skipped_pages,
                "invalid_pages",
                batch_index,
                unit_id=batch_id if isinstance(batch_id, str) else None,
                evidence=_skip_evidence(run, batch),
            )
            continue

        for page_index, page_item in enumerate(pages, start=1):
            if not isinstance(page_item, dict):
                _skip(
                    skipped_pages,
                    "invalid_page",
                    batch_index,
                    page_index,
                    unit_id=unit_id,
                    evidence=_skip_evidence(run, batch),
                )
                continue

            page_number = page_item.get("page")
            evidence = _skip_evidence(run, batch, page_item)
            if invalid_batch_id:
                _skip(
                    skipped_pages,
                    "invalid_batch_id",
                    batch_index,
                    page_index,
                    str(batch_id),
                    page_number,
                    evidence,
                )
                continue
            if unit_id is None:
                _skip(skipped_pages, "missing_batch_id", batch_index, page_index, page=page_number, evidence=evidence)
                continue
            if page_item.get("ok") is not True:
                _skip(skipped_pages, "page_not_ok", batch_index, page_index, unit_id, page_number, evidence)
                continue
            if type(page_number) is not int or page_number <= 0:
                _skip(skipped_pages, "invalid_page_number", batch_index, page_index, unit_id, page_number, evidence)
                continue

            contacts = page_item.get("contacts")
            if not isinstance(contacts, list):
                _skip(skipped_pages, "invalid_contacts", batch_index, page_index, unit_id, page_number, evidence)
                continue

            payload = {
                "unit_id": unit_id,
                "wave_id": wave_id,
                "page": page_number,
                "source_run": str(source_run),
                "source_run_id": source_run_id,
                "request": _page_value(page_item, batch, "request", {}),
                "responseSummary": _page_value(page_item, batch, "responseSummary", {}),
                "responseData": _page_value(page_item, batch, "responseData", None),
                "responseRawPreview": _page_value(page_item, batch, "responseRawPreview", ""),
                "contacts": contacts,
            }
            raw_path = page_raw_path(paths, unit_id, page_number)
            if raw_path.exists():
                reason = "already_completed" if _existing_raw_matches(raw_path, payload) else "conflict_existing_raw"
                _skip(skipped_pages, reason, batch_index, page_index, unit_id, page_number, evidence)
                continue

            mark_page_completed(paths, unit_id, page_number, payload)
            written_pages += 1

    return {
        "status": "standardized",
        "campaign_root": str(paths.root),
        "run": str(source_run),
        "written_pages": written_pages,
        "skipped_pages": skipped_pages,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="标准化脉脉搜索 live-run canonical raw")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--out")
    args = parser.parse_args(argv)

    result = standardize_live_run(args.campaign_root, args.run)
    if args.out:
        _write_json(args.out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
