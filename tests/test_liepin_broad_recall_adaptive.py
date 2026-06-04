import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_broad_recall_adaptive import (
    STRATEGY_MODE,
    adaptive_policy_from_strategy,
    build_search_units,
    plan_adaptive_search,
    split_units_into_waves,
    is_adaptive_strategy,
)


def _strategy() -> dict:
    return {
        "strategy_mode": STRATEGY_MODE,
        "strategy_version": "2026-06-04",
        "unit_order": "company_first",
        "company_pools": {"target": ["腾讯", "阿里云"]},
        "keyword_packages": [
            {
                "id": "ai-product",
                "priority": "P0",
                "position_terms": ["产品经理", "产品负责人"],
                "keywords": ["大模型", "AI 应用"],
                "long_tail_keywords": ["Agent"],
            }
        ],
        "condition_overrides": {
            "wantDqs": "010",
            "eduLevels": ["040"],
            "workYearsLow": "5",
            "workYearsHigh": "15",
            "sortType": "0",
            "resumetype": "0",
        },
        "adaptive_search": {
            "probe_pages": 2,
            "unit_max_pages": 15,
            "search_wave_max_pages": 50,
            "account_day_page_guardrail": 500,
        },
    }


def test_build_search_units_for_company_first_strategy() -> None:
    units = build_search_units(_strategy())

    assert len(units) == 2
    assert units[0]["schema"] == "liepin_search_unit_v1"
    assert units[0]["strategy_mode"] == STRATEGY_MODE
    assert units[0]["unit_id"] == "unit-000001"
    assert units[0]["source_company_terms"] == ["腾讯"]
    assert units[1]["source_company_terms"] == ["阿里云"]
    assert units[0]["keyword_package"] == "ai-product"
    assert units[0]["planned_pages"] == [0, 1]
    assert units[0]["probe_pages"] == 2
    assert units[0]["unit_max_pages"] == 15
    assert units[0]["search_params_overrides"]["keyword"] == "腾讯 产品经理 产品负责人 大模型 AI 应用"
    assert units[0]["search_params_overrides"]["wantDqs"] == "010"
    assert units[0]["search_params_overrides"]["pageSize"] == 30


def test_adaptive_policy_uses_safe_defaults_and_bounds() -> None:
    policy = adaptive_policy_from_strategy({"adaptive_search": {"probe_pages": 0, "unit_max_pages": 1}})

    assert policy["probe_pages"] == 1
    assert policy["unit_max_pages"] == 1
    assert policy["search_wave_max_pages"] == 50
    assert policy["account_day_page_guardrail"] == 500


def test_rejects_unknown_condition_override_key() -> None:
    strategy = _strategy()
    strategy["condition_overrides"] = {"cookie": "secret"}

    with pytest.raises(ValueError, match="unsupported condition_overrides key: cookie"):
        build_search_units(strategy)


def test_strategy_detection_is_explicit() -> None:
    assert is_adaptive_strategy({"strategy_mode": STRATEGY_MODE}) is True
    assert is_adaptive_strategy({"strategy_mode": "broad_recall_adaptive_v1"}) is False


def test_split_units_into_waves_respects_page_limit() -> None:
    units = build_search_units(_strategy())

    waves = split_units_into_waves(units, max_pages=2)

    assert [wave["wave_id"] for wave in waves] == ["search-wave-001", "search-wave-002"]
    assert [wave["page_count"] for wave in waves] == [2, 2]


def test_plan_adaptive_search_writes_units_waves_and_reports(tmp_path: Path) -> None:
    root = tmp_path / "liepin-demo"
    root.mkdir()
    (root / "strategy.json").write_text(json.dumps(_strategy(), ensure_ascii=False), encoding="utf-8")

    result = plan_adaptive_search(root)

    assert result["schema"] == "liepin_adaptive_search_plan_v1"
    assert result["unit_count"] == 2
    assert result["probe_page_count"] == 4
    assert result["no_live_request"] is True
    assert result["no_database_write"] is True
    assert (root / "search-units.jsonl").exists()
    aggregate = json.loads((root / "raw/search-live-runs/wave-plan.json").read_text(encoding="utf-8-sig"))
    assert aggregate["schema"] == "liepin_adaptive_search_wave_plan_v1"
    assert aggregate["wave_count"] == 1
    sidecar = Path(aggregate["waves"][0]["live_gate_plan_path"])
    assert sidecar.exists()
    assert json.loads(sidecar.read_text(encoding="utf-8-sig"))["wave_id"] == "search-wave-001"
    assert (root / "reports/broad-recall-plan.json").exists()
    md = (root / "reports/broad-recall-plan.md").read_text(encoding="utf-8-sig")
    assert "不触发猎聘请求" in md
    assert "不写数据库" in md


def test_plan_adaptive_search_rejects_invalid_strategy_without_partial_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "liepin-demo"
    root.mkdir()
    strategy = _strategy()
    strategy["condition_overrides"] = {"cookie": "secret"}
    (root / "strategy.json").write_text(json.dumps(strategy, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported condition_overrides key: cookie"):
        plan_adaptive_search(root)

    assert not (root / "campaign-manifest.json").exists()
    assert not (root / "search-units.jsonl").exists()
    assert not (root / "raw/search-live-runs/wave-plan.json").exists()
    assert not (root / "reports/broad-recall-plan.json").exists()


def test_plan_adaptive_search_cli_smoke(tmp_path: Path) -> None:
    root = tmp_path / "liepin-demo"
    root.mkdir()
    (root / "strategy.json").write_text(json.dumps(_strategy(), ensure_ascii=False), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_campaign_orchestrator",
            "plan-adaptive-search",
            "--campaign-root",
            str(root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["unit_count"] == 2
    assert payload["no_live_request"] is True
    assert payload["no_cdp_connection"] is True
    assert payload["no_database_write"] is True
    assert not (root / "talent.db").exists()
