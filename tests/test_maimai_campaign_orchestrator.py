import json
from pathlib import Path

import pytest

from scripts.maimai_campaign_orchestrator import (
    DEFAULT_RUN_POLICY,
    _load_jsonl_objects,
    append_event,
    count_search_requests,
    load_json,
    main,
    split_search_units_into_live_waves,
    write_json,
    write_stage_state,
)


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
    assert first_batch["start_page"] == 1
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
    assert not (tmp_path / "state" / "events.jsonl").exists()


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
