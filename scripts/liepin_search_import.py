"""猎聘搜索摘要导入 campaign-local TalentDB。

dry-run 只在临时 DB 中模拟；apply 只写 campaign 目录下的 `talent.db`。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.liepin_campaign import append_jsonl, atomic_write_json, ensure_campaign  # noqa: E402
from scripts.talent_db import TalentDB  # noqa: E402
from scripts.talent_models import IngestResult  # noqa: E402


CONFIRM_TEXT = "确认写入猎聘搜索结果"
IMPORT_SCHEMA = "liepin_search_import_v1"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise ValueError("candidate summaries do not exist; run standardize first")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path} line {line_number}: invalid JSON: {exc.msg}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path} line {line_number}: must be an object")
        rows.append(item)
    return rows


def _strip_liepin_detail_tokens(url: Any) -> str:
    text = str(url or "")
    if not text:
        return ""
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return ""
    keep = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower() in {"ck_id", "sk_id", "fk_id", "sss", "pgref"}:
            continue
        keep.append((key, value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(keep), ""))


def _safe_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _sanitized_raw_profile(row: dict[str, Any]) -> dict[str, Any]:
    raw_ref = row.get("raw_ref") if isinstance(row.get("raw_ref"), dict) else {}
    safe_ref = {
        "search_page": raw_ref.get("search_page"),
        "card_index": raw_ref.get("card_index"),
    }
    return {
        "liepin_search_summary": {
            "platform_id": row.get("platform_id") or "",
            "user_id_encode": row.get("user_id_encode") or "",
            "display_name": row.get("display_name") or "",
            "name_confidence": row.get("name_confidence") or "masked",
            "current_company": row.get("current_company") or "",
            "current_title": row.get("current_title") or "",
            "city": row.get("city") or "",
            "education": row.get("education") or "",
            "work_years": row.get("work_years"),
            "expected_city": row.get("expected_city") or "",
            "expected_title": row.get("expected_title") or "",
            "active_status": row.get("active_status") if isinstance(row.get("active_status"), dict) else {},
            "resume_source": row.get("resume_source") or "",
            "resume_type": row.get("resume_type"),
            "raw_ref": {key: value for key, value in safe_ref.items() if value not in {None, ""}},
        }
    }


def search_summary_to_ingest_payload(row: dict[str, Any]) -> dict[str, Any]:
    platform_id = str(row.get("platform_id") or "").strip()
    if not platform_id:
        raise ValueError("platform_id is required")
    display_name = str(row.get("display_name") or "").strip()
    if display_name and "*" not in display_name:
        name = display_name
    elif display_name:
        name = f"{display_name}（猎聘{platform_id[-6:]}）"
    else:
        name = f"猎聘候选人-{platform_id[-6:]}"
    profile_url = _strip_liepin_detail_tokens(row.get("profile_url"))
    return {
        "name": name,
        "platform_id": platform_id,
        "profile_url": profile_url or None,
        "gender": None,
        "age": None,
        "city": str(row.get("city") or "") or None,
        "work_years": _safe_int(row.get("work_years")),
        "education": str(row.get("education") or "") or None,
        "current_company": str(row.get("current_company") or "") or None,
        "current_title": str(row.get("current_title") or "") or None,
        "expected_city": str(row.get("expected_city") or "") or None,
        "expected_title": str(row.get("expected_title") or "") or None,
        "hunting_status": None,
        "skill_tags": [],
        "data_level": "lead",
        "raw_profile": _sanitized_raw_profile(row),
    }


def _unique_payloads(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, list[str]]:
    payloads: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    duplicates = 0
    for index, row in enumerate(rows):
        try:
            payload = search_summary_to_ingest_payload(row)
        except ValueError as exc:
            errors.append(f"row {index}: {exc}")
            continue
        platform_id = str(payload["platform_id"])
        if platform_id in seen:
            duplicates += 1
            continue
        seen.add(platform_id)
        payloads.append(payload)
    return payloads, duplicates, errors


def _clone_db_for_dry_run(source_db: Path, target_db: Path) -> None:
    if not source_db.exists():
        return
    source = sqlite3.connect(str(source_db))
    target = sqlite3.connect(str(target_db))
    try:
        source.backup(target)
    finally:
        source.close()
        target.close()


def _run_batch(payloads: list[dict[str, Any]], db_path: Path) -> IngestResult:
    db = TalentDB(db_path)
    try:
        return db.batch_ingest(payloads, platform="liepin")
    finally:
        db.close()


def _result_to_dict(result: IngestResult) -> dict[str, Any]:
    return {
        "created": result.created,
        "merged": result.merged,
        "pending": result.pending,
        "errors": result.errors,
        "total": result.total,
        "error_details": result.error_details,
    }


def _build_summary(
    *,
    campaign_root: str | Path,
    mode: str,
    result: IngestResult,
    raw_count: int,
    unique_count: int,
    duplicates_skipped: int,
    pre_errors: list[str],
) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    return {
        "schema": IMPORT_SCHEMA,
        "mode": mode,
        "campaign_id": paths.campaign_id,
        "input": "structured/candidate-summaries.jsonl",
        "campaign_db": "talent.db",
        "raw_count": raw_count,
        "unique_count": unique_count,
        "duplicates_skipped": duplicates_skipped,
        "pre_errors": pre_errors,
        "result": _result_to_dict(result),
        "no_main_db_write": True,
        "generatedAt": _now(),
    }


def _write_report(paths: Any, stem: str, summary: dict[str, Any]) -> None:
    json_path = paths.reports_dir / f"{stem}.json"
    md_path = paths.reports_dir / f"{stem}.md"
    atomic_write_json(json_path, summary)
    result = summary["result"]
    lines = [
        "# 猎聘搜索结果 Campaign DB import",
        "",
        f"- mode：{summary['mode']}",
        f"- campaign：{summary['campaign_id']}",
        f"- 输入：{summary['input']}",
        f"- 原始摘要：{summary['raw_count']}",
        f"- 去重后：{summary['unique_count']}",
        f"- 跳过重复：{summary['duplicates_skipped']}",
        f"- 新建：{result['created']}",
        f"- 合并：{result['merged']}",
        f"- 待合并：{result['pending']}",
        f"- 错误：{result['errors']}",
        f"- no main db write：{str(summary['no_main_db_write']).lower()}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")


def dry_run_search_import(campaign_root: str | Path) -> dict[str, Any]:
    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    payloads, duplicates, pre_errors = _unique_payloads(rows)
    with tempfile.TemporaryDirectory(prefix="liepin-search-import-dry-run-") as tmp_dir:
        dry_db = Path(tmp_dir) / "talent.db"
        _clone_db_for_dry_run(paths.root / "talent.db", dry_db)
        result = _run_batch(payloads, dry_db)
    if pre_errors:
        result.errors += len(pre_errors)
        result.error_details.extend(pre_errors)
    summary = _build_summary(
        campaign_root=paths.root,
        mode="dry-run",
        result=result,
        raw_count=len(rows),
        unique_count=len(payloads),
        duplicates_skipped=duplicates,
        pre_errors=pre_errors,
    )
    _write_report(paths, "search-import-dry-run", summary)
    return summary


def apply_search_import(campaign_root: str | Path, confirm: str = "") -> dict[str, Any]:
    if confirm != CONFIRM_TEXT:
        raise ValueError(f"apply requires confirm text: {CONFIRM_TEXT}")
    paths = ensure_campaign(campaign_root)
    rows = _load_jsonl(paths.candidate_summaries)
    payloads, duplicates, pre_errors = _unique_payloads(rows)
    result = _run_batch(payloads, paths.root / "talent.db")
    if pre_errors:
        result.errors += len(pre_errors)
        result.error_details.extend(pre_errors)
    summary = _build_summary(
        campaign_root=paths.root,
        mode="apply",
        result=result,
        raw_count=len(rows),
        unique_count=len(payloads),
        duplicates_skipped=duplicates,
        pre_errors=pre_errors,
    )
    _write_report(paths, "search-import-apply", summary)
    append_jsonl(
        paths.state_dir / "import-ledger.jsonl",
        {
            "action": "search_import_apply",
            "status": "completed",
            "created": result.created,
            "merged": result.merged,
            "pending": result.pending,
            "errors": result.errors,
            "unique_count": len(payloads),
            "ts": _now(),
        },
    )
    return summary


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="猎聘搜索摘要导入 campaign-local TalentDB。")
    subparsers = parser.add_subparsers(dest="command", required=True)
    dry = subparsers.add_parser("dry-run")
    dry.add_argument("--campaign-root", required=True)
    apply = subparsers.add_parser("apply")
    apply.add_argument("--campaign-root", required=True)
    apply.add_argument("--confirm", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "dry-run":
            summary = dry_run_search_import(args.campaign_root)
        elif args.command == "apply":
            summary = apply_search_import(args.campaign_root, confirm=args.confirm)
        else:
            raise ValueError(f"unsupported command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError, sqlite3.Error, shutil.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
