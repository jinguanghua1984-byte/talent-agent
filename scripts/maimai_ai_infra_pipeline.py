"""脉脉 AI Infra 搜索流水线编排。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.maimai_ai_infra_campaign import (
    CampaignPaths,
    append_import_ledger,
    ensure_campaign,
    import_ledger_has_apply,
    import_ledger_has_detail_apply,
    load_completed_pages,
    mark_detail_wave_state,
    page_raw_path,
)
from scripts.maimai_ai_infra_rank import rank_candidates
from scripts.maimai_ai_infra_search_plan import build_plan, build_search_units, load_strategy
from scripts.maimai_ai_infra_search_runner import DEFAULT_TEMPLATE, build_dry_run_result
from scripts.maimai_detail_import import CONFIRM_TEXT, apply_capture, build_dry_run, dry_run_capture
from scripts.maimai_detail_targets import export_targets
from scripts.talent_library import (
    _build_import_candidates,
    _result_to_dict,
    _run_batch_ingest,
    _write_import_outputs,
)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8-sig")


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in items)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8-sig")


def extract_contacts_payload(run_path: str | Path, out_path: str | Path) -> dict[str, Any]:
    source = Path(run_path)
    data = _load_json(source)
    if not isinstance(data, dict):
        raise ValueError("runner result must be a JSON object")
    contacts = data.get("contacts") or []
    if not isinstance(contacts, list):
        raise ValueError("runner result contacts must be a list")
    payload = {
        "exportTime": datetime.now().isoformat(timespec="seconds"),
        "metadata": {
            "export_type": "maimai_ai_infra_search_contacts",
            "source_run": str(source),
            "run_id": data.get("run_id", ""),
            "total_contacts": len(contacts),
        },
        "contacts": contacts,
    }
    _write_json(Path(out_path), payload)
    return payload


def extract_wave_contacts_from_pages(paths: CampaignPaths, wave_id: str) -> dict[str, Any]:
    contacts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unit_id, page in sorted(load_completed_pages(paths)):
        raw_path = page_raw_path(paths, unit_id, page)
        data = _load_json(raw_path)
        if data.get("wave_id") != wave_id:
            continue
        for contact in data.get("contacts") or []:
            if not isinstance(contact, dict):
                continue
            keys = {
                str(value).strip()
                for value in (contact.get("id"), contact.get("platform_id"))
                if str(value or "").strip()
            }
            if not keys or seen.intersection(keys):
                continue
            seen.update(keys)
            contacts.append(contact)
    payload = {
        "exportTime": datetime.now().isoformat(timespec="seconds"),
        "metadata": {
            "export_type": "maimai_ai_infra_v2_wave_contacts",
            "wave_id": wave_id,
            "total_contacts": len(contacts),
        },
        "contacts": contacts,
    }
    _write_json(paths.contacts_dir / f"contacts-{wave_id}.json", payload)
    return payload


def select_detail_candidate_ids(shortlist: dict[str, Any], max_b: int = 30) -> list[int]:
    ids: list[int] = []
    for item in shortlist.get("grades", {}).get("A", []):
        if item.get("candidate_id") is not None:
            ids.append(int(item["candidate_id"]))
    for item in shortlist.get("grades", {}).get("B", [])[:max_b]:
        if item.get("candidate_id") is not None:
            ids.append(int(item["candidate_id"]))
    seen: set[int] = set()
    result: list[int] = []
    for candidate_id in ids:
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        result.append(candidate_id)
    return result


def _status_count(batches: list[dict[str, Any]], status: str) -> int:
    return sum(1 for batch in batches if batch.get("status") == status)


def _candidate_line(item: dict[str, Any]) -> str:
    evidence = item.get("evidence") or {}
    tech = "、".join(evidence.get("tech_keywords") or [])
    return (
        f"- #{item.get('candidate_id')} {item.get('name', '')}｜{item.get('score', 0)} 分｜"
        f"{evidence.get('company', '')}｜{evidence.get('title', '')}｜{tech}"
    )


def write_initial_list_report(path: str | Path, shortlist: dict[str, Any], funnel: dict[str, Any]) -> None:
    summary = shortlist.get("summary") or {}
    grades = shortlist.get("grades") or {}
    coverage = funnel.get("coverage") or {}
    lines = [
        "# AI Infra 初版名单报告",
        "",
        "## raw/page/wave counts",
        f"- raw count: {funnel.get('raw_count', 0)}",
        f"- page count: {funnel.get('page_count', 0)}",
        f"- wave count: {funnel.get('wave_count', 0)}",
        "",
        "## A/B/C/淘汰 funnel",
        f"- A/B/C/淘汰: {summary.get('A', 0)}/{summary.get('B', 0)}/{summary.get('C', 0)}/{summary.get('淘汰', 0)}",
        "",
        "## A Top 100",
    ]
    lines.extend(_candidate_line(item) for item in grades.get("A", [])[:100])
    lines.extend(["", "## B Top 150", ""])
    lines.extend(_candidate_line(item) for item in grades.get("B", [])[:150])
    lines.extend([
        "",
        "## direction/company coverage",
        f"- direction count: {coverage.get('direction_count', 0)}",
        f"- company count: {coverage.get('company_count', 0)}",
    ])

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def write_final_search_report(path: str | Path, detailed_result: dict[str, Any], funnel: dict[str, Any]) -> None:
    detail = detailed_result.get("detail") or {}
    recommendations = detailed_result.get("recommendations") or {}
    gap_suggestions = detailed_result.get("gap_suggestions") or funnel.get("gap_suggestions") or []
    lines = [
        "# AI Infra 最终搜索报告",
        "",
        "## detail targets/success",
        f"- detail targets: {detail.get('targets', 0)}",
        f"- detail success: {detail.get('success', 0)}",
        "",
        "## 强推荐/推荐/观察/不推荐",
        f"- 强推荐: {recommendations.get('强推荐', 0)}",
        f"- 推荐: {recommendations.get('推荐', 0)}",
        f"- 观察: {recommendations.get('观察', 0)}",
        f"- 不推荐: {recommendations.get('不推荐', 0)}",
        "",
        f"- final recommended count: {detailed_result.get('final_recommended_count', 0)}",
        "",
        "## gap suggestions",
    ]
    if gap_suggestions:
        lines.extend(f"- {item}" for item in gap_suggestions)
    else:
        lines.append("- none")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def build_final_report(path: str | Path, context: dict[str, Any]) -> None:
    run = context.get("run") or {}
    batches = run.get("batches") or []
    shortlist = context.get("shortlist") or {}
    summary = shortlist.get("summary") or {}
    import_result = context.get("import_result") or {}
    detail = context.get("detail") or {}
    exceptions = context.get("exceptions") or []
    next_actions = context.get("next_actions") or []

    lines = [
        "# 脉脉 AI Infra 自动化搜索最终审查",
        "",
        f"- 策略版本：{context.get('strategy_version', '')}",
        f"- 策略确认时间：{context.get('confirmed_at') or '未确认'}",
        f"- 生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 执行批次",
        "",
        f"- 总批次：{len(batches)}",
        f"- 成功批次：{_status_count(batches, 'completed')}",
        f"- 熔断/阻塞批次：{len([batch for batch in batches if batch.get('status') not in {'completed', 'dry-run-template-only'}])}",
        f"- 搜索总联系人：{len(run.get('contacts') or [])}",
        "",
        "## 入库结果",
        "",
        f"- created：{import_result.get('created', 0)}",
        f"- merged：{import_result.get('merged', 0)}",
        f"- pending：{import_result.get('pending', 0)}",
        f"- errors：{import_result.get('errors', 0)}",
        "",
        "## 分层统计",
        "",
        f"- A：{summary.get('A', 0)}",
        f"- B：{summary.get('B', 0)}",
        f"- C：{summary.get('C', 0)}",
        f"- 淘汰：{summary.get('淘汰', 0)}",
        "",
        "## A 档候选",
        "",
    ]
    lines.extend(_candidate_line(item) for item in shortlist.get("grades", {}).get("A", [])[:30])
    lines.extend(["", "## B 档候选", ""])
    lines.extend(_candidate_line(item) for item in shortlist.get("grades", {}).get("B", [])[:30])
    lines.extend([
        "",
        "## 详情补全结果",
        "",
        f"- 详情目标：{detail.get('targets', 0)}",
        f"- 缺失目标：{detail.get('missing', 0)}",
        f"- 状态：{detail.get('status', '未执行')}",
        "",
        "## 异常批次",
        "",
    ])
    if exceptions:
        for item in exceptions:
            lines.append(f"- {item.get('batch_id', '')}：{item.get('reason', '')}")
    else:
        lines.append("- 无")
    lines.extend(["", "## 下一轮建议", ""])
    if next_actions:
        lines.extend(f"- {item}" for item in next_actions)
    else:
        lines.append("- 先完成 Phase 0 字段语义和扩展自动化桥校准。")

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8-sig")


def _clean_dry_run(result: dict[str, Any], metadata: dict[str, Any]) -> bool:
    return (
        result.get("errors", 0) == 0
        and result.get("pending", 0) == 0
        and metadata.get("pre_errors", 0) == 0
    )


def _ensure_campaign_plan_files(paths: CampaignPaths, config: Path) -> None:
    strategy = load_strategy(config)
    if not paths.strategy.exists():
        _write_json(paths.strategy, strategy)
    if not paths.search_plan.exists():
        _write_json(paths.search_plan, build_plan(strategy))
    if not paths.search_units.exists():
        _write_jsonl(paths.search_units, build_search_units(strategy))


def _apply_import_is_clean(import_result: dict[str, Any], metadata: dict[str, Any]) -> bool:
    return (
        metadata.get("pre_errors", 0) == 0
        and import_result.get("errors", 0) == 0
        and import_result.get("pending", 0) == 0
    )


def run_campaign_wave(
    campaign_root: str | Path,
    config: str | Path = "configs/maimai-ai-infra-v2-cold-start-strategy.json",
    wave: str = "",
    db_path: str | Path | None = None,
    apply: bool = False,
) -> dict[str, Path]:
    if not wave:
        raise ValueError("wave is required")

    paths = ensure_campaign(campaign_root)
    if apply and import_ledger_has_apply(paths, wave):
        raise RuntimeError(f"campaign wave already applied: {wave}")

    _ensure_campaign_plan_files(paths, Path(config))
    extract_wave_contacts_from_pages(paths, wave)
    contacts_path = paths.contacts_dir / f"contacts-{wave}.json"
    report_path = paths.reports_dir / f"import-list-{wave}-{'apply' if apply else 'dry-run'}.md"
    target_db = Path(db_path) if db_path is not None else paths.db

    candidates, metadata = _build_import_candidates([contacts_path], "maimai")
    if apply:
        append_import_ledger(
            paths,
            {
                "wave_id": wave,
                "action": "apply",
                "status": "started",
                "contacts": len(candidates),
                "report": str(report_path),
                "db": str(target_db),
            },
        )
    ingest_result = _run_batch_ingest(candidates, "maimai", target_db, apply=apply)
    import_result = _result_to_dict(ingest_result)
    import_summary = {
        "mode": "apply" if apply else "dry-run",
        "platform": "maimai",
        **metadata,
        "result": import_result,
    }
    _write_import_outputs(report_path, import_summary)
    if apply:
        clean_apply = _apply_import_is_clean(import_result, metadata)
        ledger_status = "completed" if clean_apply else "partial"
        append_import_ledger(
            paths,
            {
                "wave_id": wave,
                "action": "apply",
                "status": ledger_status,
                "contacts": len(candidates),
                "report": str(report_path),
                "db": str(target_db),
                "errors": import_result.get("errors", 0),
                "pending": import_result.get("pending", 0),
                "pre_errors": metadata.get("pre_errors", 0),
            },
        )
        if not clean_apply:
            raise RuntimeError(f"campaign wave apply was partial: {wave}")

    return {
        "contacts": contacts_path,
        "import_report": report_path,
        "db": target_db,
        "search_plan": paths.search_plan,
        "search_units": paths.search_units,
    }


def _detail_result_is_clean(result: dict[str, Any]) -> bool:
    matches = result.get("matches") or []
    return (
        result.get("matched", 0) > 0
        and result.get("failed_jobs", 0) == 0
        and result.get("unmatched", 0) == 0
        and len(matches) == result.get("matched", 0)
        and not result.get("apply_blockers")
        and all((item.get("new_work") or 0) > 0 and not item.get("apply_blockers") for item in matches)
    )


def _detail_dry_run_status(result: dict[str, Any]) -> str:
    if _detail_result_is_clean(result):
        return "dry_run_clean"
    if result.get("matched", 0) == 0 and result.get("failed_jobs", 0) == 0 and result.get("unmatched", 0) == 0:
        return "dry_run_empty"
    return "dry_run_dirty"


def _detail_state_extra(
    result: dict[str, Any],
    capture_file: Path,
    report_path: Path,
    result_path: Path | None = None,
) -> dict[str, Any]:
    extra = {
        "capture_file": str(capture_file),
        "report": str(report_path),
        "matched": result.get("matched", 0),
        "unmatched": result.get("unmatched", 0),
        "failed_jobs": result.get("failed_jobs", 0),
    }
    if result_path is not None:
        extra["result"] = str(result_path)
    if "written" in result:
        extra["written"] = result.get("written", 0)
    if result.get("apply_blockers"):
        extra["apply_blockers"] = result.get("apply_blockers")
    return extra


def run_detail_wave_dry_run(
    campaign_root: str | Path,
    wave: str,
    capture_file: str | Path,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not wave:
        raise ValueError("wave is required")
    paths = ensure_campaign(campaign_root)
    target_db = Path(db_path) if db_path is not None else paths.db
    capture_path = Path(capture_file)
    report_path = paths.reports_dir / f"detail-wave-{wave}-dry-run.md"
    result = dry_run_capture(capture_path, target_db, report_path)
    result_path = report_path.with_suffix(".json")
    status = _detail_dry_run_status(result)
    mark_detail_wave_state(
        paths,
        wave,
        status,
        _detail_state_extra(result, capture_path, report_path, result_path),
    )
    return {
        "status": status,
        "result": result,
        "report": report_path,
        "result_json": result_path,
        "db": target_db,
    }


def run_detail_wave_apply(
    campaign_root: str | Path,
    wave: str,
    capture_file: str | Path,
    db_path: str | Path | None = None,
    confirm: str = "",
) -> dict[str, Any]:
    if not wave:
        raise ValueError("wave is required")
    paths = ensure_campaign(campaign_root)
    if import_ledger_has_detail_apply(paths, wave):
        raise RuntimeError(f"detail wave already applied: {wave}")
    if confirm != CONFIRM_TEXT:
        raise ValueError(f"apply requires confirm text: {CONFIRM_TEXT}")

    target_db = Path(db_path) if db_path is not None else paths.db
    capture_path = Path(capture_file)
    preflight = build_dry_run(capture_path, target_db)
    report_path = paths.reports_dir / f"detail-wave-{wave}-apply.md"
    result_path = paths.reports_dir / f"detail-wave-{wave}-apply.json"
    if preflight.get("matched", 0) == 0 and preflight.get("failed_jobs", 0) == 0 and preflight.get("unmatched", 0) == 0:
        noop_report_path = paths.reports_dir / f"detail-wave-{wave}-apply-noop.md"
        noop_result = dry_run_capture(capture_path, target_db, noop_report_path)
        noop_result_path = noop_report_path.with_suffix(".json")
        mark_detail_wave_state(
            paths,
            wave,
            "apply_noop",
            _detail_state_extra(noop_result, capture_path, noop_report_path, noop_result_path),
        )
        return {
            "status": "apply_noop",
            "result": noop_result,
            "report": noop_report_path,
            "result_json": noop_result_path,
            "db": target_db,
        }
    if not _detail_result_is_clean(preflight):
        blocked_report_path = paths.reports_dir / f"detail-wave-{wave}-apply-blocked.md"
        blocked_result = dry_run_capture(capture_path, target_db, blocked_report_path)
        blocked_result_path = blocked_report_path.with_suffix(".json")
        mark_detail_wave_state(
            paths,
            wave,
            "apply_blocked",
            _detail_state_extra(blocked_result, capture_path, blocked_report_path, blocked_result_path),
        )
        raise RuntimeError(f"detail wave apply requires clean dry-run: {wave}")

    append_import_ledger(
        paths,
        {
            "wave_id": wave,
            "action": "detail_apply",
            "status": "started",
            "matched": preflight.get("matched", 0),
            "report": str(report_path),
            "result": str(result_path),
            "db": str(target_db),
        },
    )
    try:
        result = apply_capture(
            capture_path,
            target_db,
            report_path=report_path,
            result_path=result_path,
            confirm=confirm,
        )
    except Exception as exc:
        failed_report_path = paths.reports_dir / f"detail-wave-{wave}-apply-failed.md"
        failed_result = dry_run_capture(capture_path, target_db, failed_report_path)
        failed_result_path = failed_report_path.with_suffix(".json")
        append_import_ledger(
            paths,
            {
                "wave_id": wave,
                "action": "detail_apply",
                "status": "failed",
                "matched": failed_result.get("matched", 0),
                "error": str(exc),
                "report": str(failed_report_path),
                "result": str(failed_result_path),
                "db": str(target_db),
            },
        )
        mark_detail_wave_state(
            paths,
            wave,
            "apply_failed",
            _detail_state_extra(failed_result, capture_path, failed_report_path, failed_result_path),
        )
        raise
    append_import_ledger(
        paths,
        {
            "wave_id": wave,
            "action": "detail_apply",
            "status": "completed",
            "matched": result.get("matched", 0),
            "written": result.get("written", 0),
            "report": str(report_path),
            "result": str(result_path),
            "db": str(target_db),
        },
    )
    mark_detail_wave_state(
        paths,
        wave,
        "apply_completed",
        _detail_state_extra(result, capture_path, report_path, result_path),
    )
    return {
        "status": "apply_completed",
        "result": result,
        "report": report_path,
        "result_json": result_path,
        "db": target_db,
    }


def run_pipeline(
    config: Path,
    db_path: Path,
    out_dir: Path,
    dry_run_template_only: bool = True,
    template_path: Path | None = None,
) -> dict[str, Path]:
    today = date.today().isoformat()
    raw_dir = out_dir / "raw"
    strategy = load_strategy(config)
    plan = build_plan(strategy)
    plan_path = out_dir / f"maimai-ai-infra-search-plan-{today}.json"
    run_path = raw_dir / f"maimai-ai-infra-search-run-{today}.json"
    contacts_path = raw_dir / f"maimai-ai-infra-search-run-{today}.contacts.json"
    import_report_path = out_dir / f"talent-import-ai-infra-{today}-dry-run.md"
    shortlist_json = out_dir / f"maimai-ai-infra-shortlist-{today}.json"
    shortlist_md = out_dir / f"maimai-ai-infra-shortlist-{today}.md"
    detail_targets_path = out_dir / f"maimai-ai-infra-detail-targets-{today}.json"
    final_report_path = out_dir / f"maimai-ai-infra-final-review-{today}.md"

    _write_json(plan_path, plan)
    if not dry_run_template_only:
        raise RuntimeError("live search requires Phase 0 verification and is disabled by default")
    template = _load_json(template_path) if template_path else DEFAULT_TEMPLATE
    run_result = build_dry_run_result(plan, template)
    _write_json(run_path, run_result)
    extract_contacts_payload(run_path, contacts_path)

    candidates, metadata = _build_import_candidates([contacts_path], "maimai")
    ingest_result = _run_batch_ingest(candidates, "maimai", db_path, apply=False)
    import_summary = {
        "mode": "dry-run",
        "platform": "maimai",
        **metadata,
        "result": _result_to_dict(ingest_result),
    }
    _write_import_outputs(import_report_path, import_summary)

    if (
        strategy["human_gates"].get("strategy_confirmed")
        and strategy["human_gates"].get("auto_apply_after_clean_dry_run")
        and _clean_dry_run(import_summary["result"], metadata)
    ):
        apply_result = _run_batch_ingest(candidates, "maimai", db_path, apply=True)
        import_summary["mode"] = "apply"
        import_summary["result"] = _result_to_dict(apply_result)
        _write_import_outputs(import_report_path.with_name(import_report_path.stem.replace("dry-run", "apply") + ".md"), import_summary)

    shortlist = rank_candidates(db_path, strategy)
    _write_json(shortlist_json, shortlist)
    from scripts.maimai_ai_infra_rank import _write_markdown

    _write_markdown(shortlist_md, shortlist)

    detail_ids = select_detail_candidate_ids(shortlist)
    detail_result = export_targets(db_path, detail_targets_path, candidate_ids=detail_ids) if detail_ids else {
        "metadata": {"total_contacts": 0, "missing": 0},
        "contacts": [],
        "missing": [],
    }
    if not detail_ids:
        _write_json(detail_targets_path, detail_result)

    build_final_report(final_report_path, {
        "strategy_version": strategy["strategy_version"],
        "confirmed_at": "",
        "run": run_result,
        "import_result": import_summary["result"],
        "shortlist": shortlist,
        "detail": {
            "targets": detail_result.get("metadata", {}).get("total_contacts", 0),
            "missing": detail_result.get("metadata", {}).get("missing", 0),
            "status": "targets_generated_only",
        },
        "exceptions": [
            {"batch_id": batch.get("batch_id", ""), "reason": batch.get("ab_stop_reason", "")}
            for batch in run_result.get("batches", [])
            if batch.get("status") not in {"completed", "dry-run-template-only"}
        ],
        "next_actions": [
            "完成 Phase 0：扩展自动化桥、导出 saveAs:false、字段语义校准和会话健康检查。",
            "策略确认后再启用 clean dry-run 后自动 apply。",
        ],
    })

    return {
        "plan": plan_path,
        "run": run_path,
        "contacts": contacts_path,
        "shortlist_json": shortlist_json,
        "shortlist_md": shortlist_md,
        "detail_targets": detail_targets_path,
        "final_report": final_report_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="脉脉 AI Infra 搜索流水线")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--config", default="configs/maimai-ai-infra-search-strategy.json")
    run_parser.add_argument("--db", default="data/talent.db")
    run_parser.add_argument("--out-dir", default="data/output")
    run_parser.add_argument("--template")
    run_parser.add_argument("--live", action="store_true")
    campaign_parser = subparsers.add_parser("run-campaign")
    campaign_parser.add_argument("--campaign-root", required=True)
    campaign_parser.add_argument("--config", default="configs/maimai-ai-infra-v2-cold-start-strategy.json")
    campaign_parser.add_argument("--wave", required=True)
    campaign_parser.add_argument("--db")
    campaign_parser.add_argument("--apply", action="store_true")
    detail_parser = subparsers.add_parser("detail-wave")
    detail_subparsers = detail_parser.add_subparsers(dest="detail_command", required=True)
    detail_dry = detail_subparsers.add_parser("dry-run")
    detail_dry.add_argument("--campaign-root", required=True)
    detail_dry.add_argument("--wave", required=True)
    detail_dry.add_argument("--capture-file", required=True)
    detail_dry.add_argument("--db")
    detail_apply = detail_subparsers.add_parser("apply")
    detail_apply.add_argument("--campaign-root", required=True)
    detail_apply.add_argument("--wave", required=True)
    detail_apply.add_argument("--capture-file", required=True)
    detail_apply.add_argument("--db")
    detail_apply.add_argument("--confirm", required=True, help=f"must equal: {CONFIRM_TEXT}")
    args = parser.parse_args(argv)

    if args.command == "run":
        run_pipeline(
            Path(args.config),
            Path(args.db),
            Path(args.out_dir),
            dry_run_template_only=not args.live,
            template_path=Path(args.template) if args.template else None,
        )
        return 0
    if args.command == "run-campaign":
        run_campaign_wave(
            campaign_root=Path(args.campaign_root),
            config=Path(args.config),
            wave=args.wave,
            db_path=Path(args.db) if args.db else None,
            apply=args.apply,
        )
        return 0
    if args.command == "detail-wave":
        if args.detail_command == "dry-run":
            run_detail_wave_dry_run(
                campaign_root=Path(args.campaign_root),
                wave=args.wave,
                capture_file=Path(args.capture_file),
                db_path=Path(args.db) if args.db else None,
            )
            return 0
        if args.detail_command == "apply":
            run_detail_wave_apply(
                campaign_root=Path(args.campaign_root),
                wave=args.wave,
                capture_file=Path(args.capture_file),
                db_path=Path(args.db) if args.db else None,
                confirm=args.confirm,
            )
            return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
