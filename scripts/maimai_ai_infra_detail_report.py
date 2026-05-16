from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_PACK_IDS = [f"detail-ab-pack-{index:03d}" for index in range(1, 5)]
GRADE_KEYS = ["A", "B", "C", "淘汰"]


def _load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    return json.loads(file_path.read_text(encoding="utf-8-sig"))


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _ranked_items(rank_data: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = rank_data.get("ranked")
    if isinstance(ranked, list):
        return [item for item in ranked if isinstance(item, dict)]

    items: list[dict[str, Any]] = []
    grades = rank_data.get("grades")
    if isinstance(grades, dict):
        for grade in GRADE_KEYS:
            grade_items = grades.get(grade, [])
            if isinstance(grade_items, list):
                items.extend(item for item in grade_items if isinstance(item, dict))
    return items


def _target_count(targets: dict[str, Any]) -> int:
    metadata = targets.get("metadata") if isinstance(targets.get("metadata"), dict) else {}
    for key in ("unique_targets", "runnable_targets", "total_contacts", "count"):
        value = metadata.get(key)
        if value is not None:
            return int(value)
    contacts = targets.get("contacts")
    return len(contacts) if isinstance(contacts, list) else 0


def _target_candidate_ids(targets: dict[str, Any]) -> list[int]:
    contacts = targets.get("contacts")
    if not isinstance(contacts, list):
        return []
    candidate_ids: list[int] = []
    seen: set[int] = set()
    for contact in contacts:
        if not isinstance(contact, dict) or contact.get("candidate_id") is None:
            continue
        candidate_id = int(contact["candidate_id"])
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        candidate_ids.append(candidate_id)
    return candidate_ids


def _pack_documents(targets: dict[str, Any]) -> list[dict[str, Any]]:
    packs = targets.get("packs")
    if isinstance(packs, list) and packs:
        return [pack for pack in packs if isinstance(pack, dict)]
    contacts = targets.get("contacts")
    return [
        {
            "metadata": {
                "pack_id": "detail-ab-pack-001",
                "count": len(contacts) if isinstance(contacts, list) else 0,
            },
            "contacts": contacts if isinstance(contacts, list) else [],
        }
    ]


def _read_detail_progress(campaign_root: Path) -> dict[str, Any]:
    path = campaign_root / "state" / "detail-progress.json"
    if not path.exists():
        return {"waves": {}}
    return _load_json(path)


def _pack_status(campaign_root: Path, pack: dict[str, Any], progress: dict[str, Any]) -> dict[str, Any]:
    metadata = pack.get("metadata") if isinstance(pack.get("metadata"), dict) else {}
    pack_id = str(metadata.get("pack_id") or "")
    contacts = pack.get("contacts")
    target_count = int(metadata.get("count") or (len(contacts) if isinstance(contacts, list) else 0))
    result_path = campaign_root / "reports" / f"detail-wave-{pack_id}-apply.json"
    progress_state = progress.get("waves", {}).get(pack_id, {}) if isinstance(progress.get("waves"), dict) else {}
    result: dict[str, Any] = {}
    if result_path.exists():
        result = _load_json(result_path)

    matched = int(result.get("matched") or 0)
    written = int(result.get("written") or 0)
    completed = written or matched
    failed_jobs = int(result.get("failed_jobs") or 0)
    unmatched = int(result.get("unmatched") or 0)
    blockers = (result.get("apply_blockers") or []) + (result.get("capture_blockers") or [])

    if not result_path.exists():
        apply_status = "missing"
    elif completed >= target_count and failed_jobs == 0 and unmatched == 0 and not blockers:
        apply_status = "applied"
    elif completed > 0:
        apply_status = "partial"
    else:
        apply_status = "blocked"

    return {
        "pack_id": pack_id,
        "target_count": target_count,
        "apply_status": apply_status,
        "completed_detail_count": completed,
        "matched": matched,
        "written": written,
        "failed_jobs": failed_jobs,
        "unmatched": unmatched,
        "progress_status": progress_state.get("status"),
        "result_file": str(result_path) if result_path.exists() else "",
    }


def _grade_distribution(ranked: list[dict[str, Any]]) -> dict[str, int]:
    distribution = {grade: 0 for grade in GRADE_KEYS}
    for item in ranked:
        grade = str(item.get("grade") or "")
        distribution.setdefault(grade, 0)
        distribution[grade] += 1
    return distribution


def _write_markdown(path: str | Path, report: dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    coverage = report["coverage"]
    distribution = report["grade_distribution"]
    lines = [
        "# AI Infra A/B 详情寻访报告",
        "",
        f"- 目标人数: {coverage['target_count']}",
        f"- 已补充详情: {coverage['completed_detail_count']}",
        f"- 缺失详情: {coverage['missing_detail_count']}",
        f"- A/B/C/淘汰: {distribution.get('A', 0)}/{distribution.get('B', 0)}/{distribution.get('C', 0)}/{distribution.get('淘汰', 0)}",
        f"- 最终推荐候选: {report['final_recommended_count']}",
        "",
        "## Pack 状态",
        "",
        "| Pack | 目标 | 状态 | 已补充 | 失败 | 未匹配 |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for item in report["pack_statuses"]:
        lines.append(
            "| {pack_id} | {target_count} | {apply_status} | {completed_detail_count} | "
            "{failed_jobs} | {unmatched} |".format(**item)
        )

    lines.extend(["", "## Top Candidates", ""])
    for item in report["top_candidates"]:
        lines.append(
            "- #{candidate_id} {name} | {grade} | {score}".format(
                candidate_id=item.get("candidate_id", ""),
                name=item.get("name", ""),
                grade=item.get("grade", ""),
                score=item.get("score", ""),
            )
        )

    lines.extend([
        "",
        "## Source Files",
        "",
    ])
    for source in report["source_files"]:
        lines.append(f"- {source}")
    lines.extend(["", report["main_db_note"], ""])
    file_path.write_text("\n".join(lines), encoding="utf-8-sig")


def build_detail_report(
    campaign_root: str | Path,
    targets_path: str | Path,
    rank_json_path: str | Path,
    out_json: str | Path | None = None,
    out_md: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(campaign_root)
    targets_file = Path(targets_path)
    rank_file = Path(rank_json_path)
    targets = _load_json(targets_file)
    rank_data = _load_json(rank_file)
    progress = _read_detail_progress(root)

    pack_statuses = [_pack_status(root, pack, progress) for pack in _pack_documents(targets)]
    target_count = _target_count(targets)
    completed_detail_count = sum(item["completed_detail_count"] for item in pack_statuses)
    ranked = _ranked_items(rank_data)
    grade_distribution = _grade_distribution(ranked)
    final_recommended_count = grade_distribution.get("A", 0) + grade_distribution.get("B", 0)
    apply_files = [item["result_file"] for item in pack_statuses if item.get("result_file")]

    report = {
        "metadata": {
            "export_type": "maimai_ai_infra_final_detail_report",
            "campaign_root": str(root),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "coverage": {
            "target_count": target_count,
            "target_candidate_ids": _target_candidate_ids(targets),
            "completed_detail_count": completed_detail_count,
            "missing_detail_count": max(target_count - completed_detail_count, 0),
        },
        "pack_statuses": pack_statuses,
        "grade_distribution": grade_distribution,
        "final_recommended_count": final_recommended_count,
        "ranked_count": len(ranked),
        "top_candidates": ranked[:50],
        "source_files": [str(targets_file), str(rank_file), *apply_files],
        "main_db_note": "Main DB data/talent.db was not read or written by this report builder.",
    }

    if out_json is not None:
        _write_json(out_json, report)
    if out_md is not None:
        _write_markdown(out_md, report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成 AI Infra V2 A/B 详情最终寻访报告")
    parser.add_argument("--campaign-root", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--rank-json", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    args = parser.parse_args(argv)

    report = build_detail_report(
        campaign_root=args.campaign_root,
        targets_path=args.targets,
        rank_json_path=args.rank_json,
        out_json=args.out_json,
        out_md=args.out_md,
    )
    coverage = report["coverage"]
    print(
        "status=ready targets={targets} completed={completed} missing={missing} recommended={recommended}".format(
            targets=coverage["target_count"],
            completed=coverage["completed_detail_count"],
            missing=coverage["missing_detail_count"],
            recommended=report["final_recommended_count"],
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
