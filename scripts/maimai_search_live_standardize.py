"""将搜索 live-run 结果标准化为 campaign canonical raw。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_campaign import ensure_campaign, mark_page_completed


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


def _skip(
    skipped_pages: list[dict[str, Any]],
    reason: str,
    batch_index: int,
    page_index: int | None = None,
    unit_id: str | None = None,
    page: Any = None,
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
    skipped_pages.append(item)


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
    batches = run.get("batches") or []
    if not isinstance(batches, list):
        raise ValueError("live-run batches must be a list")

    for batch_index, batch in enumerate(batches, start=1):
        if not isinstance(batch, dict):
            _skip(skipped_pages, "invalid_batch", batch_index)
            continue

        batch_id = batch.get("batch_id")
        unit_id = batch_id if isinstance(batch_id, str) and batch_id else None
        pages = batch.get("pages") or []
        if not isinstance(pages, list):
            _skip(skipped_pages, "invalid_pages", batch_index, unit_id=unit_id)
            continue

        for page_index, page_item in enumerate(pages, start=1):
            if not isinstance(page_item, dict):
                _skip(skipped_pages, "invalid_page", batch_index, page_index, unit_id=unit_id)
                continue

            page_number = page_item.get("page")
            if unit_id is None:
                _skip(skipped_pages, "missing_batch_id", batch_index, page_index, page=page_number)
                continue
            if page_item.get("ok") is not True:
                _skip(skipped_pages, "page_not_ok", batch_index, page_index, unit_id, page_number)
                continue
            if not isinstance(page_number, int) or page_number <= 0:
                _skip(skipped_pages, "invalid_page_number", batch_index, page_index, unit_id, page_number)
                continue

            contacts = page_item.get("contacts")
            if not isinstance(contacts, list):
                _skip(skipped_pages, "invalid_contacts", batch_index, page_index, unit_id, page_number)
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
