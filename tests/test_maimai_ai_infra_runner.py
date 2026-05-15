import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_campaign import (
    ensure_campaign,
    mark_page_completed,
    page_raw_path,
    read_search_progress,
)
from scripts.maimai_ai_infra_search_runner import (
    DEFAULT_TEMPLATE,
    build_page_task_dry_run,
    iter_pending_page_tasks,
    main,
    patch_search_body,
)


def _template_body():
    return {
        "sid": "sid-1",
        "sessionid": "session-1",
        "data_version": "dv",
        "highlight_exp": "1",
        "search": {
            "query": "old",
            "search_query": "old",
            "positions": "",
            "allcompanies": "一线互联网公司",
            "degrees": "2,3",
            "degrees_min": "",
            "degrees_max": "",
            "only_bachelor_degree": 0,
            "worktimes": "",
            "worktimes_min": "",
            "worktimes_max": "",
            "age": "",
            "min_age": "",
            "max_age": "",
            "query_relation": 0,
            "schools": "",
            "major": "",
            "paginationParam": {"page": 1, "size": 30},
            "page": 0,
            "size": 30,
            "sid": "sid-search",
            "sessionid": "session-search",
            "data_version": "4.1",
            "highlight_exp": 1,
        },
    }


def _batch():
    return {
        "batch_id": "tier1-bytedance-precision-001",
        "company": "字节跳动",
        "position": "大模型训练",
        "query": '"Seed" "训练框架"',
        "query_relation": 0,
        "page_size": 30,
    }


def test_patch_search_body_preserves_session_fields_and_patches_verified_fields():
    patched = patch_search_body(_template_body(), _batch(), page=2)

    assert patched["sid"] == "sid-1"
    assert patched["sessionid"] == "session-1"
    assert patched["data_version"] == "dv"
    assert patched["highlight_exp"] == "1"
    assert patched["search"]["query"] == '"Seed" "训练框架"'
    assert patched["search"]["search_query"] == '"Seed" "训练框架"'
    assert patched["search"]["paginationParam"]["page"] == 2
    assert patched["search"]["paginationParam"]["size"] == 30
    assert patched["search"]["page"] == 1
    assert patched["search"]["size"] == 30
    assert patched["search"]["positions"] == ""
    assert patched["search"]["allcompanies"] == "一线互联网公司"
    assert patched["search"]["degrees"] == "2,3"
    assert patched["search"]["sid"] == "sid-search"
    assert patched["search"]["sessionid"] == "session-search"
    assert patched["search"]["data_version"] == "4.1"
    assert patched["search"]["highlight_exp"] == 1


def test_patch_search_body_applies_explicit_confirmed_filters_only():
    batch = {
        **_batch(),
        "age": "32",
        "query_relation": 1,
        "search_filters": {
            "allcompanies": "字节跳动,阿里",
            "positions": "模型训练,推理引擎",
            "degrees": "1,2,3",
            "only_bachelor_degree": 1,
            "worktimes_min": "4",
            "worktimes_max": "8",
            "min_age": "16",
            "max_age": "40",
            "schools": "浙大,清华大学",
            "major": "软件工程",
        },
    }

    patched = patch_search_body(_template_body(), batch, page=1)

    assert patched["search"]["query_relation"] == 1
    assert patched["search"]["allcompanies"] == "字节跳动,阿里"
    assert patched["search"]["positions"] == "模型训练,推理引擎"
    assert patched["search"]["degrees"] == "1,2,3"
    assert patched["search"]["only_bachelor_degree"] == 1
    assert patched["search"]["worktimes_min"] == "4"
    assert patched["search"]["worktimes_max"] == "8"
    assert patched["search"]["min_age"] == "16"
    assert patched["search"]["max_age"] == "40"
    assert patched["search"]["schools"] == "浙大,清华大学"
    assert patched["search"]["major"] == "软件工程"
    assert patched["search"]["age"] == ""


def test_patch_search_body_rejects_unconfirmed_filter_fields():
    batch = {
        **_batch(),
        "search_filters": {"age": "32"},
    }

    try:
        patch_search_body(_template_body(), batch, page=1)
    except ValueError as exc:
        assert "unconfirmed search filter field: search.age" in str(exc)
    else:
        raise AssertionError("unconfirmed filter should fail")


def test_patch_search_body_rejects_incompatible_template():
    try:
        patch_search_body({"search": []}, _batch(), page=1)
    except ValueError as exc:
        assert "search must be an object" in str(exc)
    else:
        raise AssertionError("invalid template should fail")


def test_iter_pending_page_tasks_skips_completed_raw_pages(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    units = [
        {"unit_id": "unit-000001", "max_pages": 3},
        {"unit_id": "unit-000002", "max_pages": 2},
    ]
    mark_page_completed(paths, "unit-000001", 1, {"contacts": []})

    tasks = list(iter_pending_page_tasks(paths, units))

    assert [(task.unit_id, task.page) for task in tasks] == [
        ("unit-000001", 2),
        ("unit-000001", 3),
        ("unit-000002", 1),
        ("unit-000002", 2),
    ]


def test_build_page_task_dry_run_patches_unit_body(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    unit = {
        "unit_id": "unit-000001",
        "wave_id": "wave-a",
        "query": '"Seed" "training"',
        "page_size": 20,
        "search_filters": {
            "allcompanies": "ByteDance,Alibaba",
            "positions": "Training Engineer,Infra Engineer",
            "query_relation": 1,
        },
    }

    payload = build_page_task_dry_run(paths, unit, page=2, template=DEFAULT_TEMPLATE)

    assert payload["campaign_id"] == paths.campaign_id
    assert payload["unit_id"] == "unit-000001"
    assert payload["wave_id"] == "wave-a"
    assert payload["page"] == 2
    assert payload["status"] == "dry-run-template-only"
    assert payload["contacts"] == []
    search = payload["body"]["search"]
    assert search["query"] == '"Seed" "training"'
    assert search["search_query"] == '"Seed" "training"'
    assert search["allcompanies"] == "ByteDance,Alibaba"
    assert search["positions"] == "Training Engineer,Infra Engineer"
    assert search["query_relation"] == 1
    assert search["paginationParam"]["page"] == 2
    assert search["paginationParam"]["size"] == 20
    assert search["page"] == 1
    assert search["size"] == 20


def _write_units(path: Path, units: list[dict[str, object]]) -> None:
    path.write_text(
        "\n".join(json.dumps(unit, ensure_ascii=False) for unit in units) + "\n\n",
        encoding="utf-8",
    )


def _unit(unit_id: str, wave_id: str = "wave-a", max_pages: int = 1) -> dict[str, object]:
    return {
        "unit_id": unit_id,
        "wave_id": wave_id,
        "query": f"query {unit_id}",
        "page_size": 10,
        "max_pages": max_pages,
        "search_filters": {
            "allcompanies": "Company",
            "positions": "Engineer",
            "query_relation": 1,
        },
    }


def test_campaign_mode_writes_raw_pages_without_plan_or_out(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001", max_pages=2)])

    assert main([
        "--campaign-root",
        str(campaign_root),
        "--units",
        str(units_path),
        "--dry-run-template-only",
    ]) == 0

    paths = ensure_campaign(campaign_root)
    first = json.loads(page_raw_path(paths, "unit-000001", 1).read_text(encoding="utf-8-sig"))
    second = json.loads(page_raw_path(paths, "unit-000001", 2).read_text(encoding="utf-8-sig"))
    assert first["status"] == "dry-run-template-only"
    assert first["body"]["search"]["paginationParam"]["page"] == 1
    assert second["body"]["search"]["paginationParam"]["page"] == 2
    assert read_search_progress(paths)["units"]["unit-000001"]["pages"]["2"]["status"] == "completed"


def test_search_runner_direct_script_entrypoint_supports_campaign_mode(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001", max_pages=1)])

    result = subprocess.run(
        [
            sys.executable,
            "scripts/maimai_ai_infra_search_runner.py",
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    paths = ensure_campaign(campaign_root)
    assert page_raw_path(paths, "unit-000001", 1).exists()


def test_campaign_mode_resume_skips_existing_raw_page(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    paths = ensure_campaign(campaign_root)
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001", max_pages=3)])
    mark_page_completed(paths, "unit-000001", 1, {"contacts": [], "sentinel": "keep"})

    assert main([
        "--campaign-root",
        str(campaign_root),
        "--units",
        str(units_path),
        "--dry-run-template-only",
        "--resume",
        "--max-pages",
        "1",
    ]) == 0

    first = json.loads(page_raw_path(paths, "unit-000001", 1).read_text(encoding="utf-8-sig"))
    assert first["sentinel"] == "keep"
    assert not page_raw_path(paths, "unit-000001", 3).exists()
    second = json.loads(page_raw_path(paths, "unit-000001", 2).read_text(encoding="utf-8-sig"))
    assert second["page"] == 2


def test_campaign_mode_filters_wave_and_limits_units_and_pages(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(
        units_path,
        [
            _unit("unit-000001", wave_id="wave-a", max_pages=2),
            _unit("unit-000002", wave_id="wave-a", max_pages=2),
            _unit("unit-000003", wave_id="wave-b", max_pages=2),
        ],
    )

    assert main([
        "--campaign-root",
        str(campaign_root),
        "--units",
        str(units_path),
        "--dry-run-template-only",
        "--wave",
        "wave-a",
        "--max-units",
        "1",
        "--max-pages",
        "1",
    ]) == 0

    paths = ensure_campaign(campaign_root)
    assert page_raw_path(paths, "unit-000001", 1).exists()
    assert not page_raw_path(paths, "unit-000001", 2).exists()
    assert not page_raw_path(paths, "unit-000002", 1).exists()
    assert not page_raw_path(paths, "unit-000003", 1).exists()


def test_campaign_mode_filters_single_unit(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(
        units_path,
        [
            _unit("unit-000001", wave_id="wave-a"),
            _unit("unit-000002", wave_id="wave-b"),
        ],
    )

    assert main([
        "--campaign-root",
        str(campaign_root),
        "--units",
        str(units_path),
        "--dry-run-template-only",
        "--unit",
        "unit-000002",
    ]) == 0

    paths = ensure_campaign(campaign_root)
    assert not page_raw_path(paths, "unit-000001", 1).exists()
    assert page_raw_path(paths, "unit-000002", 1).exists()


def test_campaign_mode_rejects_negative_max_pages_without_writing_raw(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001", max_pages=2)])

    with pytest.raises(SystemExit):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
            "--max-pages",
            "-1",
        ])

    paths = ensure_campaign(campaign_root)
    assert not page_raw_path(paths, "unit-000001", 1).exists()


def test_campaign_mode_rejects_negative_max_units_without_writing_raw(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001"), _unit("unit-000002")])

    with pytest.raises(SystemExit):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
            "--max-units",
            "-1",
        ])

    paths = ensure_campaign(campaign_root)
    assert not page_raw_path(paths, "unit-000001", 1).exists()
    assert not page_raw_path(paths, "unit-000002", 1).exists()


def test_campaign_mode_allows_zero_max_pages_and_writes_summary(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    out_path = tmp_path / "summary.json"
    _write_units(units_path, [_unit("unit-000001", max_pages=2)])

    assert main([
        "--campaign-root",
        str(campaign_root),
        "--units",
        str(units_path),
        "--out",
        str(out_path),
        "--dry-run-template-only",
        "--max-pages",
        "0",
    ]) == 0

    paths = ensure_campaign(campaign_root)
    summary = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert summary["pages_written"] == 0
    assert summary["tasks_written"] == 0
    assert not page_raw_path(paths, "unit-000001", 1).exists()


@pytest.mark.parametrize("bad_unit_id", ["abc", "../unit-000001"])
def test_campaign_mode_rejects_non_canonical_unit_id_without_writing_raw(
    tmp_path: Path,
    bad_unit_id: str,
):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [{**_unit("unit-000001"), "unit_id": bad_unit_id}])

    with pytest.raises(ValueError, match="units JSONL line 1: unit_id must match"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])

    paths = ensure_campaign(campaign_root)
    assert not any(paths.raw_search_dir.glob("**/*.json"))


def test_campaign_mode_rejects_duplicate_unit_id(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001"), _unit("unit-000001")])

    with pytest.raises(ValueError, match="units JSONL line 2: duplicate unit_id unit-000001"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])


def test_campaign_mode_invalid_json_includes_line_number(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    units_path.write_text(
        json.dumps(_unit("unit-000001"), ensure_ascii=False) + "\n{not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="units JSONL line 2: invalid JSON"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])


def test_campaign_mode_missing_unit_id_includes_line_number(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [{"wave_id": "wave-a"}])

    with pytest.raises(ValueError, match="units JSONL line 1: unit_id is required"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])


def test_campaign_mode_rejects_negative_unit_max_pages_without_writing_raw(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [_unit("unit-000001", max_pages=-1)])

    with pytest.raises(ValueError, match="units JSONL line 1: max_pages"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])

    paths = ensure_campaign(campaign_root)
    assert not page_raw_path(paths, "unit-000001", 1).exists()


def test_campaign_mode_rejects_non_integer_unit_max_pages_with_line_number(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    _write_units(units_path, [{**_unit("unit-000001"), "max_pages": "many"}])

    with pytest.raises(ValueError, match="units JSONL line 1: max_pages"):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--dry-run-template-only",
        ])


def test_campaign_mode_rejects_negative_max_runtime_minutes(tmp_path: Path):
    campaign_root = tmp_path / "campaign"
    units_path = tmp_path / "units.jsonl"
    out_path = tmp_path / "summary.json"
    _write_units(units_path, [_unit("unit-000001")])

    with pytest.raises(SystemExit):
        main([
            "--campaign-root",
            str(campaign_root),
            "--units",
            str(units_path),
            "--out",
            str(out_path),
            "--dry-run-template-only",
            "--max-runtime-minutes",
            "-5",
        ])

    paths = ensure_campaign(campaign_root)
    assert not out_path.exists()
    assert not page_raw_path(paths, "unit-000001", 1).exists()


def test_runner_dry_run_template_only_outputs_patched_body(tmp_path: Path):
    plan_path = tmp_path / "plan.json"
    template_path = tmp_path / "template.json"
    out_path = tmp_path / "run.json"
    plan_path.write_text(
        json.dumps({"run_id": "smoke", "batches": [_batch()]}, ensure_ascii=False),
        encoding="utf-8",
    )
    template_path.write_text(json.dumps(_template_body(), ensure_ascii=False), encoding="utf-8")

    assert main([
        "--plan",
        str(plan_path),
        "--template",
        str(template_path),
        "--out",
        str(out_path),
        "--dry-run-template-only",
    ]) == 0

    data = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert data["status"] == "dry-run-template-only"
    assert data["batches"][0]["patched_pages"][0]["body"]["search"]["paginationParam"]["page"] == 1
    assert data["contacts"] == []
