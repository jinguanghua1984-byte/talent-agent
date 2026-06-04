import json
import subprocess
import sys
from pathlib import Path

import scripts.liepin_campaign_orchestrator as orchestrator
from scripts.liepin_campaign import ensure_campaign, mark_page_completed


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "scripts.liepin_campaign_orchestrator", *args],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
    )


def _search_payload() -> dict:
    return {
        "flag": 1,
        "data": {
            "ckId": "ck-1",
            "skId": "sk-1",
            "fkId": "fk-1",
            "cardResList": [
                {
                    "usercIdEncode": "user-1",
                    "detailUrl": "/resume/showresumedetail/?res_id_encode=res-1",
                    "simpleResumeForm": {
                        "resIdEncode": "res-1",
                        "resName": "张**",
                        "resCompany": "示例公司",
                        "resTitle": "产品经理",
                    },
                }
            ],
        },
    }


def test_init_cli_writes_campaign_contracts(tmp_path: Path):
    root = tmp_path / "liepin-demo"

    completed = _run_cli("init", "--campaign-root", str(root), "--job-id", "75703601")

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["campaign_root"] == str(root)
    requirements = json.loads((root / "requirements.json").read_text(encoding="utf-8-sig"))
    strategy = json.loads((root / "strategy.json").read_text(encoding="utf-8-sig"))
    run_policy = json.loads((root / "run-policy.json").read_text(encoding="utf-8-sig"))
    manifest = json.loads((root / "campaign-manifest.json").read_text(encoding="utf-8-sig"))
    assert requirements["job_id"] == 75703601
    assert strategy["page_plan"] == {"start_cur_page": 0, "max_pages": 1}
    assert run_policy["execution_surface"] == "cdp_in_page_fetch"
    assert run_policy["allow_main_db_write"] is False
    assert manifest["schema"] == "liepin_talent_search_campaign_v1"


def test_plan_pages_writes_continuation_and_rejects_policy_limit(tmp_path: Path):
    root = tmp_path / "liepin-demo"
    assert _run_cli("init", "--campaign-root", str(root), "--job-id", "75703601").returncode == 0

    completed = _run_cli("plan-pages", "--campaign-root", str(root))

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["pages"] == [0]
    continuation = json.loads((root / "state" / "continuation-plan.json").read_text(encoding="utf-8-sig"))
    assert continuation["next_cur_page"] == 0
    assert continuation["reason"] == "planned"

    rejected = _run_cli("plan-pages", "--campaign-root", str(root), "--max-pages", "6")
    assert rejected.returncode == 2
    assert "max pages exceeds policy limit" in rejected.stderr


def test_standardize_and_summarize_commands(tmp_path: Path):
    root = tmp_path / "liepin-demo"
    paths = ensure_campaign(root)
    mark_page_completed(
        paths,
        cur_page=0,
        payload=_search_payload(),
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )

    standardized = _run_cli("standardize", "--campaign-root", str(root))

    assert standardized.returncode == 0, standardized.stderr
    standardize_payload = json.loads(standardized.stdout)
    assert standardize_payload["candidate_count"] == 1

    summarized = _run_cli("summarize", "--campaign-root", str(root))
    assert summarized.returncode == 0, summarized.stderr
    assert json.loads(summarized.stdout)["candidate_count"] == 1


def test_diagnose_pool_command_writes_candidate_pool_report(tmp_path: Path):
    root = tmp_path / "liepin-demo"
    paths = ensure_campaign(root)
    mark_page_completed(
        paths,
        cur_page=0,
        payload=_search_payload(),
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )
    assert _run_cli("standardize", "--campaign-root", str(root)).returncode == 0

    completed = _run_cli("diagnose-pool", "--campaign-root", str(root))

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["schema"] == "liepin_candidate_pool_diagnostic_v1"
    assert payload["candidate_count"] == 1
    assert (root / "reports" / "candidate-pool-diagnostic.json").exists()


def test_status_prints_empty_or_existing_stage_state(tmp_path: Path):
    root = tmp_path / "liepin-demo"
    assert _run_cli("init", "--campaign-root", str(root), "--job-id", "75703601").returncode == 0

    completed = _run_cli("status", "--campaign-root", str(root))

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["campaign_root"] == str(root)
    assert payload["has_continuation_plan"] is False


def test_launch_browser_command_dry_run_writes_manifest(tmp_path: Path):
    browser = tmp_path / "chrome"
    browser.write_text("", encoding="utf-8")
    manifest_path = tmp_path / "liepin-session.json"

    completed = _run_cli(
        "launch-browser",
        "--browser",
        str(browser),
        "--manifest-out",
        str(manifest_path),
        "--dry-run",
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["status"] == "dry_run"
    assert payload["cdp_url"] == "http://127.0.0.1:9898"
    assert payload["manifest_out"] == str(manifest_path)
    assert manifest["schema"] == "liepin_cdp_browser_session_v1"


def test_launch_browser_uses_detached_bootstrap_launcher(tmp_path: Path, monkeypatch):
    browser = tmp_path / "chrome"
    browser.write_text("", encoding="utf-8")
    calls = []

    def fake_launch_browser_process(config):
        calls.append(config)
        return object()

    monkeypatch.setattr(orchestrator, "launch_browser_process", fake_launch_browser_process)

    result = orchestrator.launch_browser(
        browser=browser,
        profile=tmp_path / "profile",
        manifest_out=tmp_path / "session.json",
        dry_run=False,
    )

    assert result["status"] == "launched"
    assert calls
    assert calls[0].profile == tmp_path / "profile"


def test_run_live_search_command_delegates_to_live_gate(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_run_live_search(**kwargs):
        calls.append(kwargs)
        return {
            "status": "completed",
            "campaign_id": Path(kwargs["campaign_root"]).name,
            "pagesCompleted": [0],
        }

    monkeypatch.setattr(orchestrator, "run_live_search", fake_run_live_search)

    result = orchestrator.main(
        [
            "run-live-search",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--cdp-url",
            "http://127.0.0.1:9898",
            "--max-pages",
            "1",
            "--delay-seconds",
            "0",
            "--timeout-seconds",
            "1",
            "--run-id",
            "run-test",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "cdp_url": "http://127.0.0.1:9898",
            "delay_seconds": 0,
            "timeout_seconds": 1,
            "max_pages": 1,
            "run_id": "run-test",
        }
    ]
    assert json.loads(capsys.readouterr().out)["pagesCompleted"] == [0]


def test_plan_detail_smoke_command_delegates_to_target_planner(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_plan_detail_smoke_targets(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_smoke_targets_v1",
            "selected_count": 10,
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
        }

    monkeypatch.setattr(orchestrator, "plan_detail_smoke_targets", fake_plan_detail_smoke_targets)

    result = orchestrator.main(
        [
            "plan-detail-smoke",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--priority",
            "detail_p0",
            "--limit",
            "10",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "priority": "detail_p0",
            "limit": 10,
        }
    ]
    assert json.loads(capsys.readouterr().out)["selected_count"] == 10


def test_run_live_detail_smoke_command_delegates_to_live_gate(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_run_live_detail_smoke(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_smoke_summary_v1",
            "status": "completed",
            "completed_count": 2,
        }

    monkeypatch.setattr(orchestrator, "run_live_detail_smoke", fake_run_live_detail_smoke)

    result = orchestrator.main(
        [
            "run-live-detail-smoke",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--target-pack",
            "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "--cdp-url",
            "http://127.0.0.1:9898",
            "--limit",
            "10",
            "--delay-seconds",
            "0",
            "--timeout-seconds",
            "1",
            "--run-id",
            "detail-run-test",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "cdp_url": "http://127.0.0.1:9898",
            "limit": 10,
            "delay_seconds": 0,
            "timeout_seconds": 1,
            "run_id": "detail-run-test",
        }
    ]
    assert json.loads(capsys.readouterr().out)["completed_count"] == 2


def test_run_live_detail_pack_command_delegates_to_live_gate(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_run_live_detail_pack(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_pack_summary_v1",
            "status": "completed",
            "completed": 3,
        }

    monkeypatch.setattr(orchestrator, "run_live_detail_pack", fake_run_live_detail_pack)

    result = orchestrator.main(
        [
            "run-live-detail-pack",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--target-pack",
            "raw/detail-targets/detail-p0-p1-pack-001.json",
            "--cdp-url",
            "http://127.0.0.1:9898",
            "--limit",
            "100",
            "--delay-seconds",
            "0",
            "--timeout-seconds",
            "1",
            "--run-id",
            "detail-pack-test",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "target_pack": "raw/detail-targets/detail-p0-p1-pack-001.json",
            "cdp_url": "http://127.0.0.1:9898",
            "limit": 100,
            "delay_seconds": 0,
            "timeout_seconds": 1,
            "run_id": "detail-pack-test",
        }
    ]
    assert json.loads(capsys.readouterr().out)["completed"] == 3


def test_calibrate_detail_api_command_delegates_to_calibrator(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_calibrate_detail_api(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_api_calibration_v1",
            "status": "captured",
            "candidate_count": 1,
        }

    monkeypatch.setattr(orchestrator, "calibrate_detail_api", fake_calibrate_detail_api)

    result = orchestrator.main(
        [
            "calibrate-detail-api",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--cdp-url",
            "http://127.0.0.1:9898",
            "--listen-seconds",
            "0",
            "--timeout-seconds",
            "1",
            "--run-id",
            "calib-test",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "cdp_url": "http://127.0.0.1:9898",
            "listen_seconds": 0,
            "timeout_seconds": 1,
            "run_id": "calib-test",
        }
    ]
    assert json.loads(capsys.readouterr().out)["candidate_count"] == 1


def test_detail_dry_run_command_delegates_to_dry_run(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_dry_run_detail_jobs(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_dry_run_v1",
            "mode": "dry-run",
            "ready_for_campaign_db_count": 1,
        }

    monkeypatch.setattr(orchestrator, "dry_run_detail_jobs", fake_dry_run_detail_jobs)

    result = orchestrator.main(
        [
            "detail-dry-run",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--target-pack",
            "raw/detail-targets/liepin-detail-p0-smoke-001.json",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
        }
    ]
    assert json.loads(capsys.readouterr().out)["ready_for_campaign_db_count"] == 1


def test_import_search_commands_delegate_to_importer(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_dry_run_search_import(**kwargs):
        calls.append(("dry", kwargs))
        return {
            "schema": "liepin_search_import_v1",
            "mode": "dry-run",
            "result": {"created": 1},
        }

    def fake_apply_search_import(**kwargs):
        calls.append(("apply", kwargs))
        return {
            "schema": "liepin_search_import_v1",
            "mode": "apply",
            "result": {"created": 1},
        }

    monkeypatch.setattr(orchestrator, "dry_run_search_import", fake_dry_run_search_import)
    monkeypatch.setattr(orchestrator, "apply_search_import", fake_apply_search_import)

    dry_result = orchestrator.main(
        [
            "import-search-dry-run",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
        ]
    )
    apply_result = orchestrator.main(
        [
            "import-search-apply",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--confirm",
            "确认写入猎聘搜索结果",
        ]
    )

    assert dry_result == 0
    assert apply_result == 0
    assert calls == [
        ("dry", {"campaign_root": str(tmp_path / "liepin-demo")}),
        ("apply", {"campaign_root": str(tmp_path / "liepin-demo"), "confirm": "确认写入猎聘搜索结果"}),
    ]
    assert '"mode": "dry-run"' in capsys.readouterr().out


def test_detail_apply_command_delegates_to_detail_import(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_apply_detail_jobs(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_apply_v1",
            "mode": "apply",
            "written": 1,
        }

    monkeypatch.setattr(orchestrator, "apply_detail_jobs", fake_apply_detail_jobs)

    result = orchestrator.main(
        [
            "detail-apply",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--target-pack",
            "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "--confirm",
            "确认写入猎聘详情",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "target_pack": "raw/detail-targets/liepin-detail-p0-smoke-001.json",
            "confirm": "确认写入猎聘详情",
        }
    ]
    assert json.loads(capsys.readouterr().out)["written"] == 1


def test_campaign_summary_command_delegates_to_summary(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_write_campaign_summary(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_campaign_summary_v1",
            "candidate_count": 3,
        }

    monkeypatch.setattr(orchestrator, "write_campaign_summary", fake_write_campaign_summary)

    result = orchestrator.main(
        [
            "campaign-summary",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
        ]
    )

    assert result == 0
    assert calls == [{"campaign_root": str(tmp_path / "liepin-demo")}]
    assert json.loads(capsys.readouterr().out)["candidate_count"] == 3


def test_plan_detail_packs_command_delegates_to_planner(tmp_path: Path, monkeypatch, capsys):
    calls = []

    def fake_plan_detail_packs(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "liepin_detail_pack_plan_v1",
            "selected_count": 10,
        }

    monkeypatch.setattr(orchestrator, "plan_detail_packs", fake_plan_detail_packs)

    result = orchestrator.main(
        [
            "plan-detail-packs",
            "--campaign-root",
            str(tmp_path / "liepin-demo"),
            "--priorities",
            "detail_p0,detail_p1",
            "--pack-size",
            "100",
            "--scope",
            "p0-p1",
            "--include-completed",
        ]
    )

    assert result == 0
    assert calls == [
        {
            "campaign_root": str(tmp_path / "liepin-demo"),
            "priorities": ["detail_p0", "detail_p1"],
            "pack_size": 100,
            "scope": "p0-p1",
            "exclude_completed": False,
        }
    ]
    assert json.loads(capsys.readouterr().out)["selected_count"] == 10
