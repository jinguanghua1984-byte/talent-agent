import json
from pathlib import Path

import pytest

from scripts.maimai_campaign_orchestrator import (
    CommandResult,
    DEFAULT_RUN_POLICY,
    _load_jsonl_objects,
    append_event,
    build_live_gate_wave_plan,
    build_stage_command_plan,
    build_stage_commands,
    count_search_requests,
    is_retriable_error,
    load_json,
    main,
    run_command,
    split_search_units_into_live_waves,
    write_blocked_continuation,
    write_json,
    write_stage_state,
)
from scripts.maimai_ai_infra_campaign import ensure_campaign
from scripts.maimai_ai_infra_pipeline import extract_wave_contacts_from_pages
from scripts.maimai_ai_infra_search_live_gate import iter_batch_pages
from scripts.maimai_search_live_standardize import standardize_live_run
from scripts.campaign_notify import build_idempotency_key


def _unit(index: int, pages: object = 3) -> dict[str, object]:
    return {
        "unit_id": f"unit-{index:06d}",
        "query": "ai infra",
        "max_pages": pages,
        "page_size": 30,
        "search_filters": {},
    }


def test_default_policy_counts_search_budget_only():
    assert DEFAULT_RUN_POLICY["daily_search_request_budget"] == 500
    assert DEFAULT_RUN_POLICY["search_wave_max_pages"] == 50
    assert DEFAULT_RUN_POLICY["detail_pack_max_contacts"] == 100
    assert DEFAULT_RUN_POLICY["detail_target_grades"] == ["A", "B"]
    assert DEFAULT_RUN_POLICY["detail_include_c_when_abc_total_lte"] == 100
    assert DEFAULT_RUN_POLICY["auto_bootstrap_browser_after_plan_confirmation"] is True
    assert DEFAULT_RUN_POLICY["auto_continue_after_search_plan_confirmation"] is True
    assert DEFAULT_RUN_POLICY["auto_run_detail_after_list_funnel"] is True
    assert DEFAULT_RUN_POLICY["auto_publish_feishu_delivery_after_detail_rank"] is True
    assert DEFAULT_RUN_POLICY["delivery_language"] == "zh-CN"
    assert DEFAULT_RUN_POLICY["main_db_sync_mode"] == "manual_only"
    assert DEFAULT_RUN_POLICY["allow_feishu_delivery_publish"] is True
    assert DEFAULT_RUN_POLICY["notify_channel"] == "feishu_im"
    assert DEFAULT_RUN_POLICY["allow_main_db_write"] is False

    assert count_search_requests({"stage": "search_live", "pages": 12}) == 12
    assert count_search_requests({"stage": "search_live", "pages": True}) == 0
    assert count_search_requests({"stage": "search_live", "pages": "abc"}) == 0
    assert count_search_requests({"stage": "detail_live", "pages": 99}) == 0
    assert count_search_requests({"stage": "search_plan", "pages": 99}) == 0


def test_split_search_units_limits_each_live_wave_to_50_pages():
    units = [_unit(index) for index in range(1, 42)]

    waves = split_search_units_into_live_waves(units, max_pages=50, daily_budget=500)

    assert len(waves) == 3
    assert [wave["wave_id"] for wave in waves] == [
        "search-wave-001",
        "search-wave-002",
        "search-wave-003",
    ]
    assert [wave["page_count"] for wave in waves] == [48, 48, 27]
    assert all(wave["page_count"] <= 50 for wave in waves)
    first_batch = waves[0]["batches"][0]
    assert first_batch["unit_id"] == "unit-000001"
    assert first_batch["batch_id"] == "unit-000001"
    assert first_batch["start_page"] == 1
    assert first_batch["max_pages"] == 3
    assert first_batch["max_page"] == 3


def test_split_search_units_truncates_by_used_daily_budget():
    units = [_unit(index) for index in range(1, 42)]

    waves = split_search_units_into_live_waves(
        units,
        max_pages=50,
        daily_budget=60,
        used_today=0,
    )

    assert [wave["page_count"] for wave in waves] == [48, 12]
    assert sum(wave["page_count"] for wave in waves) == 60

    waves = split_search_units_into_live_waves(
        units,
        max_pages=50,
        daily_budget=60,
        used_today=55,
    )

    assert [wave["page_count"] for wave in waves] == [3]
    assert count_search_requests({"stage": "detail_live", "pages": 200}) == 0


def test_split_search_units_rejects_single_unit_over_wave_limit():
    with pytest.raises(ValueError, match="single unit exceeds max_pages"):
        split_search_units_into_live_waves([_unit(1, pages=51)], max_pages=50, daily_budget=500)


@pytest.mark.parametrize("bad_pages", [0, -1, False, "", "abc"])
def test_split_search_units_rejects_invalid_explicit_unit_pages(bad_pages: object):
    with pytest.raises(ValueError, match="unit-000001.*max_pages"):
        split_search_units_into_live_waves([_unit(1, pages=bad_pages)], max_pages=50, daily_budget=500)


def test_split_search_units_handles_wave_parameter_boundaries():
    with pytest.raises(ValueError, match="max_pages must be positive"):
        split_search_units_into_live_waves([_unit(1)], max_pages=0, daily_budget=500)

    assert split_search_units_into_live_waves([_unit(1)], max_pages=50, daily_budget=0) == []
    assert split_search_units_into_live_waves(
        [_unit(1)],
        max_pages=50,
        daily_budget=5,
        used_today=5,
    ) == []

    assert split_search_units_into_live_waves([_unit(1)], max_pages=50, daily_budget=2) == []


def test_load_jsonl_objects_ignores_empty_lines_and_wraps_bad_json(tmp_path: Path):
    units_path = tmp_path / "units.jsonl"
    units_path.write_text(
        "\n"
        + json.dumps(_unit(1), ensure_ascii=False)
        + "\n\n"
        + json.dumps(_unit(2), ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )

    assert [unit["unit_id"] for unit in _load_jsonl_objects(units_path)] == [
        "unit-000001",
        "unit-000002",
    ]

    bad_path = tmp_path / "bad-units.jsonl"
    bad_path.write_text('{"unit_id": "unit-000001"\n', encoding="utf-8")

    with pytest.raises(ValueError, match="bad-units.jsonl line 1: invalid JSON"):
        _load_jsonl_objects(bad_path)


def test_json_state_helpers_write_stage_state_and_append_events(tmp_path: Path):
    missing_default = {"status": "empty"}
    assert load_json(tmp_path / "missing.json", default=missing_default) == missing_default

    bom_json = tmp_path / "bom.json"
    bom_json.write_text('\ufeff{"ok": true}', encoding="utf-8")
    assert load_json(bom_json) == {"ok": True}

    write_json(tmp_path / "state" / "custom.json", {"name": "campaign"})
    assert json.loads((tmp_path / "state" / "custom.json").read_text(encoding="utf-8")) == {
        "name": "campaign",
    }

    state = write_stage_state(
        tmp_path,
        "search_live",
        "planned",
        {"pages": 6},
    )
    append_event(tmp_path, {"stage": "detail_live", "pages": 99})

    saved_state = load_json(tmp_path / "state" / "stage-state.json")
    assert saved_state == state
    assert saved_state["stage"] == "search_live"
    assert saved_state["status"] == "planned"
    assert saved_state["pages"] == 6
    assert "updated_at" in saved_state

    event_lines = (tmp_path / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    assert len(events) == 2
    assert events[0]["stage"] == "search_live"
    assert events[0]["status"] == "planned"
    assert events[1]["stage"] == "detail_live"
    assert all("at" in event for event in events)


def test_status_cli_prints_empty_or_existing_stage_state(tmp_path: Path, capsys):
    assert main(["status", "--campaign-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out) == {}

    write_stage_state(tmp_path, "search_live", "planned")

    assert main(["status", "--campaign-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "search_live"


def test_plan_waves_cli_writes_plan_without_live_side_effects(tmp_path: Path, capsys):
    units_path = tmp_path / "units.jsonl"
    units_path.write_text(
        "\n".join(json.dumps(_unit(index)) for index in range(1, 42)) + "\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "wave-plan.json"

    assert main([
        "plan-waves",
        "--campaign-root",
        str(tmp_path),
        "--units",
        str(units_path),
        "--out",
        str(out_path),
    ]) == 0

    printed = json.loads(capsys.readouterr().out)
    saved = load_json(out_path)
    assert printed == saved
    assert saved["wave_count"] == 3
    assert [wave["page_count"] for wave in saved["waves"]] == [48, 48, 27]
    first_wave = saved["waves"][0]
    sidecar_path = Path(first_wave["live_gate_plan_path"])
    sidecar = load_json(sidecar_path)
    assert sidecar["wave_id"] == "search-wave-001"
    assert sidecar["gate"] == "S2"
    assert sidecar["page_count"] == 48
    assert sidecar["batches"][0]["unit_id"] == "unit-000001"
    assert sidecar["batches"][0]["batch_id"] == "unit-000001"
    assert sidecar["batches"][0]["start_page"] == 1
    assert sidecar["batches"][0]["max_pages"] == 3
    assert sidecar["batches"][0]["max_page"] == 3
    assert not (tmp_path / "state" / "events.jsonl").exists()


def test_plan_waves_to_standardize_preserves_wave_id_for_pipeline_filter(tmp_path: Path, capsys):
    campaign = ensure_campaign(tmp_path / "campaign")
    units_path = tmp_path / "units.jsonl"
    units_path.write_text(
        "\n".join(
            [
                json.dumps(_unit(1, pages=2), ensure_ascii=False),
                json.dumps(_unit(2, pages=1), ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    aggregate_path = tmp_path / "plans" / "wave-plan.json"

    assert main([
        "plan-waves",
        "--campaign-root",
        str(campaign.root),
        "--units",
        str(units_path),
        "--out",
        str(aggregate_path),
    ]) == 0
    capsys.readouterr()

    aggregate = load_json(aggregate_path)
    wave = aggregate["waves"][0]
    wave_id = wave["wave_id"]
    assert build_live_gate_wave_plan(wave)["wave_id"] == wave_id

    sidecar = load_json(wave["live_gate_plan_path"])
    assert set(sidecar) >= {"wave_id", "gate", "page_count", "batches"}
    assert sidecar["wave_id"] == wave_id
    assert [iter_batch_pages(batch) for batch in sidecar["batches"]] == [[1, 2], [1]]

    run_path = tmp_path / "fake-live-run.json"
    run_path.write_text(
        json.dumps(
            {
                "status": "completed",
                "run_id": "fake-run-001",
                "batches": [
                    {
                        "batch_id": sidecar["batches"][0]["batch_id"],
                        "pages": [
                            {"page": 1, "ok": True, "contacts": [{"id": "p1", "name": "one"}]},
                            {"page": 2, "ok": True, "contacts": [{"id": "p2", "name": "two"}]},
                        ],
                    },
                    {
                        "batch_id": sidecar["batches"][1]["batch_id"],
                        "pages": [{"page": 1, "ok": True, "contacts": [{"id": "p3", "name": "three"}]}],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    summary = standardize_live_run(campaign.root, run_path, wave_id=wave_id)
    extracted = extract_wave_contacts_from_pages(campaign, wave_id)
    wrong_wave = extract_wave_contacts_from_pages(campaign, "wave-001")

    assert summary["wave_id"] == wave_id
    assert summary["written_pages"] == 3
    assert extracted["metadata"]["wave_id"] == wave_id
    assert extracted["metadata"]["total_contacts"] == 3
    assert [contact["id"] for contact in extracted["contacts"]] == ["p1", "p2", "p3"]
    assert wrong_wave["metadata"]["total_contacts"] == 0


def test_plan_waves_cli_reports_bad_jsonl_without_traceback_or_side_effects(
    tmp_path: Path,
    capsys,
):
    units_path = tmp_path / "bad-units.jsonl"
    units_path.write_text('{"unit_id": "unit-000001"\n', encoding="utf-8")
    out_path = tmp_path / "wave-plan.json"

    return_code = main([
        "plan-waves",
        "--campaign-root",
        str(tmp_path),
        "--units",
        str(units_path),
        "--out",
        str(out_path),
    ])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert return_code != 0
    assert "error: invalid search units JSONL" in captured.err
    assert "bad-units.jsonl line 1: invalid JSON" in captured.err
    assert "Traceback" not in combined_output
    assert not out_path.exists()
    assert not (tmp_path / "state" / "events.jsonl").exists()


def test_plan_waves_cli_reports_missing_units_without_traceback_or_side_effects(
    tmp_path: Path,
    capsys,
):
    out_path = tmp_path / "wave-plan.json"

    return_code = main([
        "plan-waves",
        "--campaign-root",
        str(tmp_path),
        "--units",
        str(tmp_path / "missing-units.jsonl"),
        "--out",
        str(out_path),
    ])

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    assert return_code == 2
    assert captured.out == ""
    assert "error:" in captured.err
    assert "Traceback" not in combined_output
    assert not out_path.exists()
    assert not (tmp_path / "search-wave-001-plan.json").exists()
    assert not (tmp_path / "state" / "events.jsonl").exists()


def test_resume_cli_prefers_continuation_plan_then_stage_state(tmp_path: Path, capsys):
    write_stage_state(tmp_path, "search_live", "blocked")
    assert main(["resume", "--campaign-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["stage"] == "search_live"

    write_json(
        tmp_path / "state" / "continuation-plan.json",
        {"blocked_stage": "search_live", "resume_command": "dry only"},
    )

    assert main(["resume", "--campaign-root", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["blocked_stage"] == "search_live"


def test_build_stage_commands_uses_existing_scripts_and_standardizer():
    commands = build_stage_commands(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={"notify_chat_id": "oc_demo"},
    )

    flattened = [" ".join(command) for command in commands]
    assert any("python -m scripts.maimai_ai_infra_search_plan" in command for command in flattened)
    assert any("maimai_campaign_orchestrator" in command and "plan-waves" in command for command in flattened)
    assert any("maimai_ai_infra_search_live_gate" in command for command in flattened)
    assert any("maimai_search_live_standardize" in command for command in flattened)
    assert any("maimai_ai_infra_pipeline" in command and "run-campaign" in command for command in flattened)
    assert any("maimai_ai_infra_rank" in command and "--mode list" in command for command in flattened)
    assert any(
        "maimai_ai_infra_detail_plan" in command and "--pack-size 100" in command
        for command in flattened
    )
    assert any(
        "campaign_notify" in command
        and "--event data\\campaigns\\demo\\state\\continuation-plan.json" in command
        and "--chat-id oc_demo" in command
        for command in flattened
    )


def test_build_stage_command_plan_links_wave_plan_producer_to_live_gate_consumer():
    plan = build_stage_command_plan(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={},
    )
    by_stage = {command["stage"]: command for command in plan}

    search_plan_argv = by_stage["compile_search_plan"]["argv"]
    plan_waves_argv = by_stage["plan_search_waves"]["argv"]
    live_gate_argv = by_stage["search_live"]["argv"]

    assert plan_waves_argv[plan_waves_argv.index("--units") + 1] == search_plan_argv[
        search_plan_argv.index("--out-units") + 1
    ]
    aggregate_plan = Path(plan_waves_argv[plan_waves_argv.index("--out") + 1])
    live_gate_plan = Path(live_gate_argv[live_gate_argv.index("--plan") + 1])
    assert aggregate_plan.name == "wave-plan.json"
    assert live_gate_plan.name == "search-wave-001-plan.json"
    assert live_gate_plan.parent == aggregate_plan.parent
    assert str(live_gate_plan) in by_stage["plan_search_waves"]["produces"]

    standardize_argv = by_stage["standardize_search_live"]["argv"]
    import_argv = by_stage["import_wave"]["argv"]
    assert standardize_argv[standardize_argv.index("--wave-id") + 1] == "search-wave-001"
    assert import_argv[import_argv.index("--wave") + 1] == "search-wave-001"
    assert Path(standardize_argv[standardize_argv.index("--run") + 1]).name == "search-wave-001-run.json"


def test_build_stage_command_plan_carries_unattended_policy_metadata():
    plan = build_stage_command_plan(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy=DEFAULT_RUN_POLICY,
    )
    by_stage = {command["stage"]: command for command in plan}

    detail_pack = by_stage["detail_pack"]
    assert detail_pack["detail_target_grades"] == ["A", "B"]
    assert detail_pack["detail_include_c_when_abc_total_lte"] == 100
    assert "A/B" in detail_pack["description"]
    assert "C" in detail_pack["description"]

    list_rank = by_stage["list_rank"]
    assert list_rank["auto_next_stage"] == "detail_pack"
    assert list_rank["funnel_labels"] == ["A", "B", "C", "淘汰"]

    delivery = by_stage["delivery_package"]
    assert delivery["requires_policy_gate"] == "allow_feishu_delivery_publish"
    assert delivery["delivery_language"] == "zh-CN"
    assert delivery["main_db_sync_mode"] == "manual_only"


def test_live_gate_command_requires_explicit_policy_gate_metadata():
    plan = build_stage_command_plan(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={},
    )

    live_gate = next(command for command in plan if command["stage"] == "search_live")
    assert live_gate["live_action"] is True
    assert live_gate["requires_policy_gate"] == "allow_live_search"
    assert "maimai_ai_infra_search_live_gate" in " ".join(live_gate["argv"])


def test_build_stage_commands_honors_policy_pack_size_and_notify_targets():
    commands = build_stage_commands(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={"detail_pack_max_contacts": 25, "notify_identity": "user", "notify_chat_id": "oc_demo"},
    )

    flattened = [" ".join(command) for command in commands]
    assert any("maimai_ai_infra_detail_plan" in command and "--pack-size 25" in command for command in flattened)
    assert any(
        "campaign_notify" in command
        and "--identity user" in command
        and "--chat-id oc_demo" in command
        for command in flattened
    )

    user_commands = build_stage_commands(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={"notify_user_id": "ou_demo"},
    )
    user_flattened = [" ".join(command) for command in user_commands]
    assert any("campaign_notify" in command and "--user-id ou_demo" in command for command in user_flattened)


def test_build_stage_commands_skips_notify_argv_when_target_missing():
    plan = build_stage_command_plan(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={},
    )
    commands = build_stage_commands(
        campaign_root="data/campaigns/demo",
        strategy="data/campaigns/demo/strategy.json",
        policy={},
    )

    notify = next(command for command in plan if command["stage"] == "notify_blocked")
    assert notify["argv"] == []
    assert notify["skipped"] is True
    assert notify["blocked_reason"] == "notify_target_missing"
    assert not any("campaign_notify" in " ".join(command) for command in commands)


def test_build_stage_commands_rejects_ambiguous_notify_target():
    with pytest.raises(ValueError, match="mutually exclusive"):
        build_stage_commands(
            campaign_root="data/campaigns/demo",
            strategy="data/campaigns/demo/strategy.json",
            policy={"notify_chat_id": "oc_demo", "notify_user_id": "ou_demo"},
        )


def test_blocked_continuation_plan_contains_resume_command_and_event(tmp_path: Path):
    plan = write_blocked_continuation(
        campaign_root=tmp_path,
        stage="detail_live",
        reason="captcha_api",
        evidence_file="reports/interruption.json",
        resume_from={"pack_id": "detail-ab-pack-001", "job_index": 9},
        completed=8,
        total=149,
        stage_argv=["python", "-m", "scripts.maimai_ai_infra_detail_live_gate"],
    )

    saved = load_json(tmp_path / "state" / "continuation-plan.json")
    assert saved == plan
    assert plan["campaign_id"] == tmp_path.name
    assert plan["blocked_event_id"].startswith(f"blocked-{tmp_path.name}-detail_live-captcha_api-")
    assert plan["event_id"] == plan["blocked_event_id"]
    assert plan["blocked_stage"] == "detail_live"
    assert plan["reason"] == "captcha_api"
    assert plan["evidence_file"] == "reports/interruption.json"
    assert plan["checkpoint_source"] == "raw/detail-live/<pack_id>/job-*.json"
    assert plan["resume_from"] == {"pack_id": "detail-ab-pack-001", "job_index": 9}
    assert plan["completed"] == 8
    assert plan["total"] == 149
    assert plan["stage_argv"] == ["python", "-m", "scripts.maimai_ai_infra_detail_live_gate"]
    assert plan["continuation_path"] == (tmp_path / "state" / "continuation-plan.json").as_posix()
    assert "\u8d1f\u8d23\u4eba" in plan["safe_to_resume_after"]
    assert "maimai_campaign_orchestrator resume" in plan["resume_command"]
    assert f"--campaign-root {tmp_path.as_posix()}" in plan["resume_command"]
    assert build_idempotency_key(plan) == f"{tmp_path.name}-detail_live-{plan['blocked_event_id']}"

    state = load_json(tmp_path / "state" / "stage-state.json")
    assert state["stage"] == "detail_live"
    assert state["status"] == "blocked"
    assert state["reason"] == "captcha_api"
    assert state["blocked_event_id"] == plan["blocked_event_id"]
    assert state["continuation_path"] == plan["continuation_path"]

    event_lines = (tmp_path / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in event_lines]
    assert any(
        event["stage"] == "detail_live"
        and event["status"] == "blocked"
        and event["reason"] == "captcha_api"
        and event["blocked_event_id"] == plan["blocked_event_id"]
        and event["continuation_path"] == plan["continuation_path"]
        for event in events
    )

    search_root = tmp_path / "search-case"
    search_plan = write_blocked_continuation(
        campaign_root=search_root,
        stage="search_live",
        reason="http_429",
        evidence_file="reports/search-interruption.json",
    )
    assert search_plan["checkpoint_source"] == "raw/search/unit-*/page-*.json"
    assert search_plan["resume_from"] == {}
    assert search_plan["completed"] == 0
    assert search_plan["total"] == 0


def test_retry_classification_treats_platform_security_as_non_retriable():
    assert is_retriable_error("Connection timed out") is True
    assert is_retriable_error("temporarily unavailable") is True
    assert is_retriable_error("file is being used by another process") is True
    assert is_retriable_error("captcha_api") is False
    assert is_retriable_error("需要登录后继续") is False
    assert is_retriable_error("安全页面") is False


def test_run_command_uses_subprocess_without_shell(monkeypatch):
    calls: list[dict[str, object]] = []

    class Completed:
        returncode = 7
        stdout = "out"
        stderr = "err"

    def fake_run(argv: list[str], *, text: bool, capture_output: bool, check: bool) -> Completed:
        calls.append({
            "argv": argv,
            "text": text,
            "capture_output": capture_output,
            "check": check,
        })
        return Completed()

    monkeypatch.setattr("scripts.maimai_campaign_orchestrator.subprocess.run", fake_run)

    result = run_command(["python", "-m", "scripts.demo"])

    assert result == CommandResult(
        argv=["python", "-m", "scripts.demo"],
        returncode=7,
        stdout="out",
        stderr="err",
    )
    assert calls == [
        {
            "argv": ["python", "-m", "scripts.demo"],
            "text": True,
            "capture_output": True,
            "check": False,
        }
    ]
