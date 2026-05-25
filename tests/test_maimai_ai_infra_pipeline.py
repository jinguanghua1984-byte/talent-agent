import json
from pathlib import Path

import pytest

import scripts.maimai_ai_infra_pipeline as pipeline
from scripts.maimai_ai_infra_campaign import (
    append_import_ledger,
    ensure_campaign,
    import_ledger_has_apply,
    import_ledger_has_detail_apply,
    mark_page_completed,
    mark_detail_wave_state,
    read_detail_progress,
)
from scripts.maimai_ai_infra_pipeline import (
    build_final_report,
    extract_contacts_payload,
    extract_wave_contacts_from_pages,
    run_detail_wave_apply,
    run_detail_wave_dry_run,
    run_campaign_wave,
    run_pipeline,
    select_detail_candidate_ids,
    write_final_search_report,
    write_initial_list_report,
)
from scripts.maimai_detail_import import CONFIRM_TEXT
from scripts.talent_models import IngestResult
from scripts.talent_db import TalentDB


def _make_detail_db(path: Path) -> int:
    db = TalentDB(path)
    try:
        return db.ingest(
            {
                "name": "Alice",
                "current_company": "OldCo",
                "current_title": "AI PM",
                "platform_id": "166812124",
                "profile_url": "https://maimai.cn/u/166812124",
            },
            platform="maimai",
        )
    finally:
        db.close()


def _write_detail_capture(
    path: Path,
    *,
    include_unmatched: bool = False,
    include_failed: bool = False,
) -> None:
    jobs = [
        {
            "id": "166812124",
            "status": "done",
            "detail": {
                "basic": {
                    "id": "166812124",
                    "name": "Alice",
                    "company": "OpenAI",
                    "position": "AI PM",
                    "exp": [{"company": "OpenAI", "position": "AI PM"}],
                    "edu": [{"school": "Fudan", "major": "CS"}],
                }
            },
        }
    ]
    if include_unmatched:
        jobs.append(
            {
                "id": "unmatched-1",
                "status": "done",
                "detail": {"basic": {"id": "unmatched-1", "name": "Unknown"}},
            }
        )
    if include_failed:
        jobs.append({"id": "failed-1", "status": "failed", "errors": ["403"]})
    path.write_text(
        json.dumps(
            {
                "exportTime": "2026-05-15T00:00:00.000Z",
                "metadata": {"detail_mode": "batch_replay"},
                "detailJobs": jobs,
                "details": [],
                "contacts": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_empty_detail_capture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "exportTime": "2026-05-15T00:00:00.000Z",
                "metadata": {"detail_mode": "batch_replay"},
                "detailJobs": [],
                "details": [],
                "contacts": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_no_work_detail_capture(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "exportTime": "2026-05-15T00:00:00.000Z",
                "metadata": {"detail_mode": "batch_replay"},
                "detailJobs": [
                    {
                        "id": "166812124",
                        "status": "done",
                        "detail": {
                            "basic": {
                                "id": "166812124",
                                "name": "Alice",
                                "company": "OpenAI",
                                "position": "AI PM",
                                "edu": [{"school": "Fudan", "major": "CS"}],
                            }
                        },
                    }
                ],
                "details": [],
                "contacts": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_extract_contacts_payload_from_runner_result(tmp_path: Path):
    run_path = tmp_path / "run.json"
    out_path = tmp_path / "contacts.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": "smoke",
                "contacts": [
                    {"id": "1", "name": "Alice", "company": "字节跳动", "position": "AI Infra"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = extract_contacts_payload(run_path, out_path)

    assert payload["metadata"]["source_run"] == str(run_path)
    assert payload["contacts"][0]["name"] == "Alice"
    assert json.loads(out_path.read_text(encoding="utf-8-sig"))["contacts"][0]["id"] == "1"


def test_extract_wave_contacts_from_page_raw_dedupes_platform_ids(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
        },
    )
    mark_page_completed(
        paths,
        "unit-000002",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"id": "u1", "name": "A again"}],
        },
    )

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["wave_id"] == "wave-001"
    assert payload["metadata"]["total_contacts"] == 2
    assert [item["id"] for item in payload["contacts"]] == ["u1", "u2"]


def test_extract_wave_contacts_dedupes_when_one_contact_has_id_and_platform_id(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"id": "internal-1", "platform_id": "p1", "name": "A"}],
        },
    )
    mark_page_completed(
        paths,
        "unit-000002",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"platform_id": "p1", "name": "A duplicate"}],
        },
    )

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["total_contacts"] == 1
    assert payload["contacts"][0]["name"] == "A"


def test_extract_wave_contacts_skips_non_object_contacts(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": ["bad", {"id": "u1", "name": "A"}],
        },
    )

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["total_contacts"] == 1
    assert payload["contacts"][0]["id"] == "u1"


def test_extract_wave_contacts_skips_contacts_missing_name(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [
                {"id": "u1", "name": ""},
                {"id": "u2", "name": "B"},
            ],
        },
    )

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["total_contacts"] == 1
    assert payload["metadata"]["skipped_missing_name"] == 1
    assert payload["contacts"][0]["id"] == "u2"


def test_import_ledger_blocks_duplicate_wave_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    append_import_ledger(paths, {"wave_id": "wave-001", "action": "apply", "status": "completed"})

    assert import_ledger_has_apply(paths, "wave-001")


def test_import_ledger_rejects_malformed_json_with_line_number(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    paths.import_ledger.write_text("\n{bad}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="malformed import ledger line 2"):
        import_ledger_has_apply(paths, "wave-001")


def test_detail_wave_progress_records_recovery_state(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    mark_detail_wave_state(paths, "wave-001", "dry_run_clean", {"matched": 100})

    progress = read_detail_progress(paths)
    assert progress["campaign_id"] == paths.campaign_id
    assert progress["waves"]["wave-001"]["status"] == "dry_run_clean"
    assert progress["waves"]["wave-001"]["matched"] == 100
    assert "updated_at" in progress["waves"]["wave-001"]


def test_detail_wave_dry_run_updates_progress_and_reports_clean_status(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "capture.json"
    _write_detail_capture(capture_path)

    result = run_detail_wave_dry_run(
        campaign_root=paths.root,
        wave="wave-001",
        capture_file=capture_path,
        db_path=paths.db,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "dry_run_clean"
    assert result["result"]["matched"] == 1
    assert result["result"]["unmatched"] == 0
    assert result["result"]["failed_jobs"] == 0
    assert progress["waves"]["wave-001"]["status"] == "dry_run_clean"
    assert progress["waves"]["wave-001"]["matched"] == 1
    assert progress["waves"]["wave-001"]["unmatched"] == 0
    assert (paths.reports_dir / "detail-wave-wave-001-dry-run.md").exists()


def test_detail_wave_dry_run_marks_dirty_when_capture_is_not_clean(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "capture.json"
    _write_detail_capture(capture_path, include_unmatched=True, include_failed=True)

    result = run_detail_wave_dry_run(
        campaign_root=paths.root,
        wave="wave-001",
        capture_file=capture_path,
        db_path=paths.db,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "dry_run_dirty"
    assert result["result"]["matched"] == 1
    assert result["result"]["unmatched"] == 1
    assert result["result"]["failed_jobs"] == 1
    assert progress["waves"]["wave-001"]["status"] == "dry_run_dirty"


def test_detail_wave_dry_run_marks_dirty_when_capture_has_apply_blockers(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "no-work-capture.json"
    _write_no_work_detail_capture(capture_path)

    result = run_detail_wave_dry_run(
        campaign_root=paths.root,
        wave="wave-001",
        capture_file=capture_path,
        db_path=paths.db,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "dry_run_dirty"
    assert result["result"]["matched"] == 1
    assert result["result"]["apply_blockers"][0]["blockers"] == ["missing_work_experience"]
    assert progress["waves"]["wave-001"]["status"] == "dry_run_dirty"
    assert progress["waves"]["wave-001"]["apply_blockers"][0]["platform_id"] == "166812124"


def test_detail_wave_dry_run_marks_dirty_when_direct_capture_is_partial(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "partial-direct-capture.json"
    _write_detail_capture(capture_path)
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    payload["metadata"] = {
        "export_type": "maimai_ai_infra_direct_detail_live_gate",
        "detail_mode": "direct_page_fetch",
        "status": "completed_limited",
        "partial": True,
        "total_contacts": 2,
        "completed_jobs": 1,
    }
    capture_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    result = run_detail_wave_dry_run(
        campaign_root=paths.root,
        wave="detail-ab-pack-001",
        capture_file=capture_path,
        db_path=paths.db,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "dry_run_dirty"
    assert result["result"]["capture_blockers"][0]["reason"] == "partial_detail_capture"
    assert progress["waves"]["detail-ab-pack-001"]["status"] == "dry_run_dirty"
    assert progress["waves"]["detail-ab-pack-001"]["capture_blockers"][0]["reason"] == "partial_detail_capture"


def test_detail_wave_apply_writes_ledger_and_blocks_duplicate_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    candidate_id = _make_detail_db(paths.db)
    capture_path = tmp_path / "capture.json"
    _write_detail_capture(capture_path)

    result = run_detail_wave_apply(
        campaign_root=paths.root,
        wave="wave-001",
        capture_file=capture_path,
        db_path=paths.db,
        confirm=CONFIRM_TEXT,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "apply_completed"
    assert result["result"]["written"] == 1
    assert import_ledger_has_detail_apply(paths, "wave-001")
    assert progress["waves"]["wave-001"]["status"] == "apply_completed"
    assert (paths.reports_dir / "detail-wave-wave-001-apply.md").exists()

    db = TalentDB(paths.db)
    try:
        candidate = db.get(candidate_id)
        detail = db.get_detail(candidate_id)
        assert candidate is not None
        assert candidate.data_level == "detailed"
        assert detail is not None
    finally:
        db.close()

    with pytest.raises(RuntimeError, match="already applied"):
        run_detail_wave_apply(
            campaign_root=paths.root,
            wave="wave-001",
            capture_file=capture_path,
            db_path=paths.db,
            confirm=CONFIRM_TEXT,
        )


def test_detail_wave_apply_rejects_unclean_capture(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "capture.json"
    _write_detail_capture(capture_path, include_unmatched=True, include_failed=True)

    with pytest.raises(RuntimeError, match="requires clean dry-run"):
        run_detail_wave_apply(
            campaign_root=paths.root,
            wave="wave-001",
            capture_file=capture_path,
            db_path=paths.db,
            confirm=CONFIRM_TEXT,
        )

    progress = read_detail_progress(paths)
    assert progress["waves"]["wave-001"]["status"] == "apply_blocked"
    assert Path(progress["waves"]["wave-001"]["report"]).exists()
    assert Path(progress["waves"]["wave-001"]["result"]).exists()
    assert not import_ledger_has_detail_apply(paths, "wave-001")


def test_detail_wave_apply_rejects_partial_direct_capture(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "partial-direct-capture.json"
    _write_detail_capture(capture_path)
    payload = json.loads(capture_path.read_text(encoding="utf-8"))
    payload["metadata"] = {
        "export_type": "maimai_ai_infra_direct_detail_live_gate",
        "detail_mode": "direct_page_fetch",
        "status": "completed_limited",
        "partial": True,
        "total_contacts": 2,
        "completed_jobs": 1,
    }
    capture_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires clean dry-run"):
        run_detail_wave_apply(
            campaign_root=paths.root,
            wave="detail-ab-pack-001",
            capture_file=capture_path,
            db_path=paths.db,
            confirm=CONFIRM_TEXT,
        )

    progress = read_detail_progress(paths)
    assert progress["waves"]["detail-ab-pack-001"]["status"] == "apply_blocked"
    assert progress["waves"]["detail-ab-pack-001"]["capture_blockers"][0]["reason"] == "partial_detail_capture"
    assert not import_ledger_has_detail_apply(paths, "detail-ab-pack-001")


def test_detail_wave_apply_noops_empty_capture_without_completed_ledger(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "empty-capture.json"
    _write_empty_detail_capture(capture_path)

    result = run_detail_wave_apply(
        campaign_root=paths.root,
        wave="wave-001",
        capture_file=capture_path,
        db_path=paths.db,
        confirm=CONFIRM_TEXT,
    )

    progress = read_detail_progress(paths)
    assert result["status"] == "apply_noop"
    assert result["result"]["matched"] == 0
    assert progress["waves"]["wave-001"]["status"] == "apply_noop"
    assert Path(progress["waves"]["wave-001"]["report"]).exists()
    assert not import_ledger_has_detail_apply(paths, "wave-001")


def test_detail_wave_apply_blocks_no_work_capture_before_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    candidate_id = _make_detail_db(paths.db)
    capture_path = tmp_path / "no-work-capture.json"
    _write_no_work_detail_capture(capture_path)

    with pytest.raises(RuntimeError, match="requires clean dry-run"):
        run_detail_wave_apply(
            campaign_root=paths.root,
            wave="wave-001",
            capture_file=capture_path,
            db_path=paths.db,
            confirm=CONFIRM_TEXT,
        )

    progress = read_detail_progress(paths)
    assert progress["waves"]["wave-001"]["status"] == "apply_blocked"
    assert progress["waves"]["wave-001"]["apply_blockers"][0]["blockers"] == ["missing_work_experience"]
    assert Path(progress["waves"]["wave-001"]["report"]).exists()
    assert Path(progress["waves"]["wave-001"]["result"]).exists()
    assert not paths.import_ledger.exists()
    assert not import_ledger_has_detail_apply(paths, "wave-001")

    db = TalentDB(paths.db)
    try:
        candidate = db.get(candidate_id)
        assert candidate is not None
        assert candidate.data_level != "detailed"
        assert db.get_detail(candidate_id) is None
    finally:
        db.close()


def test_detail_wave_cli_dry_run_returns_zero_and_updates_progress(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    _make_detail_db(paths.db)
    capture_path = tmp_path / "capture.json"
    _write_detail_capture(capture_path)

    assert pipeline.main(
        [
            "detail-wave",
            "dry-run",
            "--campaign-root",
            str(paths.root),
            "--wave",
            "wave-001",
            "--capture-file",
            str(capture_path),
            "--db",
            str(paths.db),
        ]
    ) == 0

    assert read_detail_progress(paths)["waves"]["wave-001"]["status"] == "dry_run_clean"


def test_run_campaign_wave_dry_run_writes_contacts_and_report(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [
                {"id": "u1", "name": "A", "company": "ByteDance", "position": "AI Infra"},
                {"id": "u2", "name": "B", "company": "Huawei", "position": "ML Infra"},
            ],
        },
    )
    mark_page_completed(
        paths,
        "unit-000002",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"platform_id": "u1", "name": "A again"}],
        },
    )

    result = run_campaign_wave(
        campaign_root=paths.root,
        config=Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"),
        wave="wave-001",
        db_path=tmp_path / "campaign.db",
    )

    contacts_path = paths.contacts_dir / "contacts-wave-001.json"
    report_path = paths.reports_dir / "import-list-wave-001-dry-run.md"
    contacts = json.loads(contacts_path.read_text(encoding="utf-8-sig"))
    assert result["contacts"] == contacts_path
    assert contacts["metadata"]["total_contacts"] == 2
    assert [item["name"] for item in contacts["contacts"]] == ["A", "B"]
    assert report_path.exists()
    assert paths.search_plan.exists()
    assert paths.search_units.exists()
    assert not import_ledger_has_apply(paths, "wave-001")


def test_run_campaign_wave_generates_plan_files_for_generic_jd_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    paths = ensure_campaign(tmp_path / "campaign")
    strategy = {
        "strategy_version": "generic-jd-v1",
        "keyword_packages": [
            {
                "id": "data_strategy",
                "priority": "P0",
                "keywords": ["data strategy", "data quality"],
                "position_terms": ["data lead"],
            }
        ],
        "company_pools": {"p0_direct": ["ByteDance DMC"]},
        "position_aliases": ["data strategy lead"],
        "screening_rules": {"reject": ["BI"]},
        "delivery_targets": {
            "report_title": "Generic JD report",
            "direction_rules": {"data_strategy": ["data strategy"]},
        },
    }
    paths.strategy.write_text(json.dumps(strategy, ensure_ascii=False), encoding="utf-8")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "search-wave-001",
            "contacts": [
                {
                    "id": "u1",
                    "name": "Alice",
                    "company": "ByteDance",
                    "position": "Data Strategy Lead",
                }
            ],
        },
    )

    def fail_legacy_loader(config: Path):  # noqa: ANN001
        raise AssertionError(f"legacy strategy loader should not run for generic JD strategy: {config}")

    monkeypatch.setattr(pipeline, "load_strategy", fail_legacy_loader)

    result = run_campaign_wave(
        campaign_root=paths.root,
        config=paths.strategy,
        wave="search-wave-001",
        db_path=tmp_path / "campaign.db",
    )

    assert result["search_plan"] == paths.search_plan
    assert result["search_units"] == paths.search_units
    assert paths.search_plan.exists()
    assert paths.search_units.exists()
    units = [
        json.loads(line)
        for line in paths.search_units.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    assert units
    assert units[0]["search_filters"]["allcompanies"] == ""
    assert units[0]["search_filters"]["positions"] == ""
    assert units[0]["query_relation"] == 0
    assert (paths.reports_dir / "import-list-search-wave-001-dry-run.md").exists()


def test_run_campaign_wave_apply_aborts_when_wave_already_applied(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    append_import_ledger(paths, {"wave_id": "wave-001", "action": "apply", "status": "completed"})
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {"wave_id": "wave-001", "contacts": [{"id": "u1", "name": "A"}]},
    )

    with pytest.raises(RuntimeError, match="already applied"):
        run_campaign_wave(
            campaign_root=paths.root,
            config=Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"),
            wave="wave-001",
            db_path=tmp_path / "campaign.db",
            apply=True,
        )

    assert not (paths.contacts_dir / "contacts-wave-001.json").exists()


def test_run_campaign_wave_apply_partial_does_not_mark_completed_ledger(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [
                {"id": "u1", "name": "A", "company": "ByteDance", "position": "AI Infra"}
            ],
        },
    )

    def fake_ingest(candidates, platform, db_path, apply):  # noqa: ANN001
        assert apply is True
        return IngestResult(created=1, errors=1, error_details=["bad candidate"])

    monkeypatch.setattr(pipeline, "_run_batch_ingest", fake_ingest)

    with pytest.raises(RuntimeError, match="partial"):
        run_campaign_wave(
            campaign_root=paths.root,
            config=Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"),
            wave="wave-001",
            db_path=tmp_path / "campaign.db",
            apply=True,
        )

    ledger = [
        json.loads(line)
        for line in paths.import_ledger.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [item["status"] for item in ledger] == ["started", "partial"]
    assert not import_ledger_has_apply(paths, "wave-001")


def test_select_detail_candidate_ids_uses_all_a_and_top_b():
    shortlist = {
        "grades": {
            "A": [{"candidate_id": 1}, {"candidate_id": 2}],
            "B": [{"candidate_id": 3}, {"candidate_id": 4}],
            "C": [{"candidate_id": 5}],
        }
    }

    assert select_detail_candidate_ids(shortlist, max_b=1) == [1, 2, 3]


def test_build_final_report_contains_required_sections(tmp_path: Path):
    out_path = tmp_path / "review.md"

    build_final_report(
        out_path,
        {
            "strategy_version": "ai-infra-v1",
            "confirmed_at": "",
            "run": {"batches": [{"status": "completed"}, {"status": "blocked"}], "contacts": [{}, {}]},
            "import_result": {"created": 1, "merged": 1, "pending": 0, "errors": 0},
            "shortlist": {
                "summary": {"A": 1, "B": 1, "C": 0, "淘汰": 2},
                "grades": {
                    "A": [{"candidate_id": 1, "name": "Alice", "score": 88, "evidence": {"company": "字节跳动"}}],
                    "B": [{"candidate_id": 2, "name": "Bob", "score": 72, "evidence": {"company": "DeepSeek"}}],
                },
            },
            "detail": {"targets": 2, "missing": 0},
            "exceptions": [{"batch_id": "x", "reason": "blocked"}],
            "next_actions": ["继续校准字段语义"],
        },
    )

    text = out_path.read_text(encoding="utf-8-sig")
    assert "策略版本" in text
    assert "执行批次" in text
    assert "A 档候选" in text
    assert "B 档候选" in text
    assert "详情补全结果" in text
    assert "异常批次" in text
    assert "下一轮建议" in text


def test_write_initial_list_report_contains_funnel_and_coverage(tmp_path: Path):
    out_path = tmp_path / "initial.md"

    write_initial_list_report(
        out_path,
        shortlist={
            "summary": {"A": 2, "B": 3, "C": 4, "淘汰": 5},
            "grades": {
                "A": [{"candidate_id": 1, "name": "Alice", "score": 90, "evidence": {"company": "瀛楄妭璺冲姩"}}],
                "B": [{"candidate_id": 2, "name": "Bob", "score": 75, "evidence": {"company": "DeepSeek"}}],
            },
        },
        funnel={
            "raw_count": 120,
            "page_count": 12,
            "wave_count": 3,
            "coverage": {"direction_count": 5, "company_count": 8},
        },
    )

    text = out_path.read_text(encoding="utf-8-sig")
    assert "raw/page/wave" in text
    assert "A/B/C/淘汰: 2/3/4/5" in text
    assert "A Top 100" in text
    assert "B Top 150" in text
    assert "direction/company coverage" in text


def test_write_final_search_report_contains_recommendation_sections(tmp_path: Path):
    out_path = tmp_path / "final.md"

    write_final_search_report(
        out_path,
        detailed_result={
            "detail": {"targets": 10, "success": 8},
            "recommendations": {
                "强推荐": 2,
                "推荐": 3,
                "观察": 1,
                "不推荐": 4,
            },
            "final_recommended_count": 5,
            "gap_suggestions": ["补充 985/211", "补充 detailed profile"],
        },
        funnel={},
    )

    text = out_path.read_text(encoding="utf-8-sig")
    assert "detail targets/success" in text
    assert "强推荐/推荐/观察/不推荐" in text
    assert "final recommended count" in text
    assert "gap suggestions" in text


def test_run_pipeline_uses_real_request_template_and_writes_outputs(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    out_dir = tmp_path / "output"
    template_path = tmp_path / "template.json"
    db = TalentDB(db_path)
    try:
        db.ingest(
            {
                "name": "Alice",
                "current_company": "字节跳动",
                "current_title": "大模型训练框架工程师",
                "education": "硕士",
                "work_years": 5,
                "platform_id": "166812124",
                "profile_url": (
                    "https://maimai.cn/profile/detail?dstu=166812124&"
                    "trackable_token=token-alice"
                ),
                "skill_tags": ["GPU", "vLLM", "分布式训练"],
            },
            platform="maimai",
        )
    finally:
        db.close()
    template_path.write_text(
        json.dumps(
            {
                "search": {
                    "query": "old",
                    "search_query": "old",
                    "paginationParam": {"page": 1, "size": 30},
                    "page": 0,
                    "size": 30,
                    "sid": "real-sid",
                    "sessionid": "real-session",
                    "highlight_exp": 1,
                    "data_version": "4.1",
                    "allcompanies": "一线互联网公司",
                    "positions": "",
                    "degrees": "2,3",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outputs = run_pipeline(
        Path("configs/maimai-ai-infra-search-strategy.json"),
        db_path,
        out_dir,
        template_path=template_path,
    )

    run = json.loads(outputs["run"].read_text(encoding="utf-8-sig"))
    patched_search = run["batches"][0]["patched_pages"][0]["body"]["search"]
    assert patched_search["sid"] == "real-sid"
    assert patched_search["sessionid"] == "real-session"
    assert patched_search["highlight_exp"] == 1
    assert patched_search["data_version"] == "4.1"
    assert patched_search["query"] != "old"
    assert outputs["contacts"].exists()
    assert outputs["shortlist_json"].exists()
    assert outputs["detail_targets"].exists()
    assert outputs["final_report"].exists()
