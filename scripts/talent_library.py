"""talent-library 统一业务入口。"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_detail_targets import export_targets
from scripts.platform_match.adapters.maimai import MaimaiAdapter
from scripts.talent_db import TalentDB
from scripts.talent_models import IngestResult


IMPORT_CONFIRM_TEXT = "确认导入人才"


def _default_detail_targets_path() -> Path:
    return Path("data") / "output" / f"maimai-detail-targets-{date.today().isoformat()}.json"


def _default_import_report_path() -> Path:
    return Path("data") / "output" / f"talent-import-{date.today().isoformat()}-maimai-capture.md"


def _parse_ids(value: str) -> list[int]:
    ids: list[int] = []
    for part in value.split(","):
        text = part.strip()
        if text:
            ids.append(int(text))
    return ids


def _write_result_with_entry_metadata(path: Path, result: dict) -> dict:
    result["metadata"]["entry"] = "talent-library detail"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    return result


def _collect_import_files(args: argparse.Namespace) -> list[Path]:
    files: list[Path] = []
    for item in args.input or []:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob(args.pattern)))
        else:
            files.append(path)
    if args.input_dir:
        files.extend(sorted(Path(args.input_dir).glob(args.pattern)))

    unique_files: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_files.append(path)
    return unique_files


def _load_import_payload(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _items_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("contacts", "candidates", "items", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return [payload]


def _normalize_text_value(value: Any) -> Any:
    if isinstance(value, (list, tuple)):
        return json.dumps(list(value), ensure_ascii=False)
    return value


def _normalize_mapped_candidate(
    mapped: dict[str, Any],
    raw_item: dict[str, Any],
    source_file: Path,
) -> dict[str, Any]:
    data = {key: value for key, value in mapped.items() if not key.startswith("_")}
    source = mapped.get("_source") if isinstance(mapped.get("_source"), dict) else {}

    if "status" in data and "hunting_status" not in data:
        data["hunting_status"] = data.pop("status")

    for field in ("expected_city", "expected_title", "expected_salary"):
        if field in data:
            data[field] = _normalize_text_value(data[field])

    platform_id = source.get("platform_id") or raw_item.get("id")
    profile_url = source.get("url") or raw_item.get("detail_url")
    if platform_id is not None:
        data["platform_id"] = str(platform_id)
    if profile_url:
        data["profile_url"] = profile_url
    data["raw_profile"] = {
        "source": {**source, "capture_file": str(source_file)},
        "maimai_contact": raw_item,
    }
    return data


def _dedupe_key(platform: str, raw_item: dict[str, Any], mapped: dict[str, Any]) -> str:
    source = mapped.get("_source") if isinstance(mapped.get("_source"), dict) else {}
    platform_id = source.get("platform_id") or raw_item.get("id")
    if platform_id:
        return f"{platform}:{platform_id}"
    return json.dumps(
        {
            "name": mapped.get("name") or raw_item.get("name"),
            "company": mapped.get("current_company") or raw_item.get("company"),
            "title": mapped.get("current_title") or raw_item.get("position"),
            "city": mapped.get("city") or raw_item.get("city"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _build_import_candidates(
    files: list[Path],
    platform: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if platform != "maimai":
        raise ValueError(f"unsupported import platform: {platform}")

    adapter = MaimaiAdapter()
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    errors: list[str] = []
    per_file: list[dict[str, Any]] = []
    raw_contacts = 0
    duplicates = 0

    for path in files:
        try:
            payload = _load_import_payload(path)
            items = _items_from_payload(payload)
        except Exception as exc:  # noqa: BLE001 - 单文件解析失败不阻塞其它文件。
            errors.append(f"{path}: {exc}")
            per_file.append({"path": str(path), "raw": 0, "unique": 0, "errors": 1})
            continue

        unique_in_file = 0
        for raw_item in items:
            raw_contacts += 1
            mapped = adapter.map_to_schema(raw_item)
            if not mapped.get("name"):
                errors.append(f"{path}: missing name")
                continue
            key = _dedupe_key(platform, raw_item, mapped)
            if key in seen:
                duplicates += 1
                continue
            seen.add(key)
            candidates.append(_normalize_mapped_candidate(mapped, raw_item, path))
            unique_in_file += 1
        per_file.append({
            "path": str(path),
            "raw": len(items),
            "unique": unique_in_file,
            "errors": 0,
        })

    metadata = {
        "files": [str(path) for path in files],
        "per_file": per_file,
        "raw_contacts": raw_contacts,
        "unique_contacts": len(candidates),
        "duplicates_skipped": duplicates,
        "pre_errors": len(errors),
        "pre_error_details": errors,
    }
    return candidates, metadata


def _merge_ingest_result(primary: IngestResult, secondary: IngestResult) -> IngestResult:
    primary.created += secondary.created
    primary.merged += secondary.merged
    primary.pending += secondary.pending
    primary.errors += secondary.errors
    primary.error_details.extend(secondary.error_details)
    return primary


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


def _run_batch_ingest(
    candidates: list[dict[str, Any]],
    platform: str,
    db_path: Path,
    apply: bool,
) -> IngestResult:
    if apply:
        db = TalentDB(db_path)
        try:
            return db.batch_ingest(candidates, platform=platform)
        finally:
            db.close()

    with tempfile.TemporaryDirectory(prefix="talent-import-dry-run-") as tmp_dir:
        dry_db_path = Path(tmp_dir) / "talent.db"
        _clone_db_for_dry_run(db_path, dry_db_path)
        db = TalentDB(dry_db_path)
        try:
            return db.batch_ingest(candidates, platform=platform)
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


def _write_import_outputs(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = summary["result"]
    lines = [
        "# 人才导入报告",
        "",
        "## 输入",
        f"- 平台：{summary['platform']}",
        f"- 模式：{summary['mode']}",
        f"- 文件数：{len(summary['files'])}",
        f"- 原始联系人：{summary['raw_contacts']}",
        f"- 去重后联系人：{summary['unique_contacts']}",
        f"- 跳过重复：{summary['duplicates_skipped']}",
        "",
        "## 结果",
        f"- 新建：{result['created']}",
        f"- 合并：{result['merged']}",
        f"- 待确认合并：{result['pending']}",
        f"- 失败：{result['errors']}",
        "",
        "## 文件明细",
    ]
    for item in summary["per_file"]:
        lines.append(
            f"- {item['path']}：原始 {item['raw']}，本批新增唯一 {item['unique']}，解析错误 {item['errors']}"
        )
    if summary.get("pre_error_details") or result.get("error_details"):
        lines.extend(["", "## 失败明细"])
        for detail in summary.get("pre_error_details", []):
            lines.append(f"- {detail}")
        for detail in result.get("error_details", []):
            lines.append(f"- {detail}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")
    path.with_suffix(".json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8-sig",
    )


def cmd_import(args: argparse.Namespace) -> int:
    if args.apply and args.confirm != IMPORT_CONFIRM_TEXT:
        raise ValueError(f"apply requires confirm text: {IMPORT_CONFIRM_TEXT}")

    files = _collect_import_files(args)
    if not files:
        raise ValueError("import requires at least one input file")

    candidates, metadata = _build_import_candidates(files, args.platform)
    result = _run_batch_ingest(
        candidates,
        platform=args.platform,
        db_path=Path(args.db),
        apply=args.apply,
    )
    result = _merge_ingest_result(
        result,
        IngestResult(errors=metadata["pre_errors"], error_details=metadata["pre_error_details"]),
    )
    summary = {
        "entry": "talent-library import",
        "mode": "apply" if args.apply else "dry-run",
        "platform": args.platform,
        **metadata,
        "result": _result_to_dict(result),
    }
    out_path = Path(args.out) if args.out else _default_import_report_path()
    _write_import_outputs(out_path, summary)
    print(
        "导入{mode}完成：文件 {files}，原始 {raw}，去重后 {unique}，"
        "新建 {created}，合并 {merged}，待确认 {pending}，失败 {errors}。报告：{path}".format(
            mode="写库" if args.apply else "dry-run",
            files=len(files),
            raw=summary["raw_contacts"],
            unique=summary["unique_contacts"],
            created=summary["result"]["created"],
            merged=summary["result"]["merged"],
            pending=summary["result"]["pending"],
            errors=summary["result"]["errors"],
            path=out_path,
        )
    )
    return 0


def cmd_detail(args: argparse.Namespace) -> int:
    out_path = Path(args.out) if args.out else _default_detail_targets_path()
    if args.ids:
        result = export_targets(
            db_path=args.db,
            out_path=out_path,
            candidate_ids=_parse_ids(args.ids),
        )
    else:
        recommendation_file = args.top10_file or args.recommendation_file
        result = export_targets(
            db_path=args.db,
            out_path=out_path,
            recommendation_file=recommendation_file,
        )
    result = _write_result_with_entry_metadata(out_path, result)
    print(
        "已生成脉脉批量详情目标文件：{path}\n"
        "联系人：{contacts}，缺失：{missing}\n"
        "下一步：在 maimai-scraper 的“批量详情”中导入该 JSON。".format(
            path=out_path,
            contacts=result["metadata"]["total_contacts"],
            missing=result["metadata"]["missing"],
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="talent-library 业务入口")
    subparsers = parser.add_subparsers(dest="scene", required=True)

    import_parser = subparsers.add_parser("import", help="人才导入入口")
    import_parser.add_argument("--input", action="append", help="导入文件或目录，可重复")
    import_parser.add_argument("--input-dir", help="导入目录")
    import_parser.add_argument("--pattern", default="*.json", help="目录导入文件匹配模式")
    import_parser.add_argument("--platform", default="maimai", choices=["maimai"], help="平台来源")
    import_parser.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    import_parser.add_argument("--out", help="导入报告输出路径")
    import_parser.add_argument("--apply", action="store_true", help="确认后写入真实人才库")
    import_parser.add_argument("--confirm", default="", help=f"写库确认语：{IMPORT_CONFIRM_TEXT}")
    import_parser.set_defaults(func=cmd_import)

    detail = subparsers.add_parser("detail", help="详情补全入口")
    source = detail.add_mutually_exclusive_group(required=True)
    source.add_argument("--ids", help="逗号分隔的候选人 candidate_id，例如 440,747,727")
    source.add_argument("--top10-file", help="talent-library match/search 输出的 TopN JSON 文件")
    source.add_argument("--recommendation-file", help="包含 top10/candidates/matches/results/items 的推荐 JSON 文件")
    detail.add_argument("--db", default="data/talent.db", help="人才库路径，默认 data/talent.db")
    detail.add_argument("--out", help="输出 maimai-scraper 可导入的目标 JSON")
    detail.set_defaults(func=cmd_detail)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
