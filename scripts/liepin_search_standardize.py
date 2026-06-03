"""将猎聘搜索 raw 标准化为候选人摘要。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import LiepinCampaignPaths, ensure_campaign  # noqa: E402
from scripts.liepin_api_contract import classify_api_result  # noqa: E402


LIEPIN_H_HOST = "https://h.liepin.com"


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: str | Path, data: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
        + ("\n" if rows else ""),
        encoding="utf-8",
    )


def _raw_payload(raw: dict[str, Any]) -> dict[str, Any]:
    payload = raw.get("payload")
    return payload if isinstance(payload, dict) else raw


def _raw_request(raw: dict[str, Any]) -> dict[str, Any]:
    request = raw.get("request")
    return request if isinstance(request, dict) else {}


def _page_number(raw: dict[str, Any], raw_path: Path) -> int:
    page = raw.get("curPage")
    if type(page) is int:
        return page
    try:
        return int(raw_path.stem.rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return -1


def candidate_summary_from_card(
    card: dict[str, Any],
    *,
    page_path: Path,
    card_index: int,
    ck_id: str,
    sk_id: str,
    fk_id: str,
    campaign_root: Path,
) -> dict[str, Any]:
    form = card.get("simpleResumeForm")
    if not isinstance(form, dict):
        form = {}
    detail_url = str(card.get("detailUrl") or "")
    profile_url = urljoin(LIEPIN_H_HOST, detail_url) if detail_url else ""
    rel_page = page_path.relative_to(campaign_root).as_posix()
    active_status = card.get("activeStatus") if isinstance(card.get("activeStatus"), dict) else {}

    return {
        "platform": "liepin",
        "platform_id": str(form.get("resIdEncode") or ""),
        "user_id_encode": str(card.get("usercIdEncode") or ""),
        "display_name": str(form.get("resName") or ""),
        "name_confidence": "masked",
        "current_company": str(form.get("resCompany") or ""),
        "current_title": str(form.get("resTitle") or card.get("highLightJobTitle") or ""),
        "city": str(form.get("resDqName") or ""),
        "education": str(form.get("resEdulevelName") or ""),
        "work_years": form.get("resWorkyearAge"),
        "expected_city": str(form.get("wantDq") or card.get("wantDq") or ""),
        "expected_title": str(form.get("wantJobTitle") or card.get("wantJobTitle") or ""),
        "active_status": active_status,
        "profile_url": profile_url,
        "resume_source": str(card.get("resSource") or ""),
        "resume_type": form.get("resType"),
        "raw_ref": {
            "search_page": rel_page,
            "card_index": card_index,
            "ckId": ck_id,
            "skId": sk_id,
            "fkId": fk_id,
        },
    }


def _standardize_raw_page(
    paths: LiepinCampaignPaths,
    raw_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    raw = _load_json(raw_path)
    if not isinstance(raw, dict):
        return [], {"raw_path": raw_path.as_posix(), "reason": "raw_not_object"}

    payload = _raw_payload(raw)
    request = _raw_request(raw)
    classification = classify_api_result(
        http_status=request.get("http_status"),
        content_type=request.get("content_type") or "application/json",
        raw_text=json.dumps(payload, ensure_ascii=False) if isinstance(payload, dict) else "",
        parsed=payload,
    )
    if not classification["ok"]:
        return [], {
            "raw_path": raw_path.as_posix(),
            "curPage": _page_number(raw, raw_path),
            "reason": classification["reason"],
        }

    data = payload.get("data")
    if not isinstance(data, dict):
        return [], {"raw_path": raw_path.as_posix(), "reason": "missing_data"}
    cards = data.get("cardResList")
    if isinstance(cards, list) and not cards and isinstance(data.get("resList"), list):
        cards = data["resList"]
    if not isinstance(cards, list):
        return [], {
            "raw_path": raw_path.as_posix(),
            "curPage": _page_number(raw, raw_path),
            "reason": "missing_cardResList",
        }

    ck_id = str(data.get("ckId") or "")
    sk_id = str(data.get("skId") or "")
    fk_id = str(data.get("fkId") or "")
    rows = [
        candidate_summary_from_card(
            card,
            page_path=raw_path,
            card_index=index,
            ck_id=ck_id,
            sk_id=sk_id,
            fk_id=fk_id,
            campaign_root=paths.root,
        )
        for index, card in enumerate(cards)
        if isinstance(card, dict)
    ]
    return rows, None


def _write_markdown_summary(paths: LiepinCampaignPaths, summary: dict[str, Any]) -> None:
    lines = [
        "# 猎聘搜索摘要",
        "",
        f"- 状态：{summary['status']}",
        f"- 扫描页数：{summary['pages_scanned']}",
        f"- 候选人摘要数：{summary['candidate_count']}",
        f"- 跳过页数：{len(summary['skipped_pages'])}",
        "",
    ]
    paths.search_summary_md.write_text("\n".join(lines), encoding="utf-8")


def standardize_campaign(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    rows: list[dict[str, Any]] = []
    skipped_pages: list[dict[str, Any]] = []
    raw_pages = sorted(paths.raw_search_dir.glob("page-*.json"))
    for raw_path in raw_pages:
        page_rows, skip = _standardize_raw_page(paths, raw_path)
        rows.extend(page_rows)
        if skip:
            skipped_pages.append(skip)

    if rows:
        _write_jsonl(paths.candidate_summaries, rows)
    elif paths.candidate_summaries.exists():
        paths.candidate_summaries.unlink()

    status = "standardized"
    if skipped_pages and not rows:
        status = "template_drift"
    elif skipped_pages:
        status = "partial"

    summary = {
        "status": status,
        "campaign_root": paths.root.as_posix(),
        "pages_scanned": len(raw_pages),
        "candidate_count": len(rows),
        "skipped_pages": skipped_pages,
    }
    _write_json(paths.search_summary_json, summary)
    _write_markdown_summary(paths, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="标准化猎聘搜索 raw")
    parser.add_argument("--campaign-root", required=True)
    args = parser.parse_args(argv)
    try:
        summary = standardize_campaign(args.campaign_root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
