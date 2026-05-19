import csv
import json
from pathlib import Path
from types import SimpleNamespace

from scripts import feishu_delivery_package
from scripts.feishu_delivery_package import (
    build_delivery_manifest,
    main,
    render_summary_xml,
    run_publish_commands,
    write_source_files,
)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")


def _write_outreach_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "candidate_id",
        "name",
        "priority",
        "recommendation_label",
        "profile_url",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _fixture_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    campaign_root = tmp_path / "campaign"
    final_report = tmp_path / "inputs" / "final-report.json"
    outreach_csv = tmp_path / "inputs" / "outreach.csv"
    audit_json = tmp_path / "inputs" / "audit.json"
    _write_json(
        final_report,
        {
            "campaign_id": "demo&campaign",
            "summary": {
                "final_recommended_count": "2<3",
                "raw_path": "data/campaigns/demo/raw/search/unit-001/page-001.json",
                "database": "data/campaigns/demo/talent.db",
            },
        },
    )
    _write_outreach_csv(
        outreach_csv,
        [
            {
                "candidate_id": "1",
                "name": "张三 & <top>",
                "priority": "P0",
                "recommendation_label": "强推荐",
                "profile_url": "https://example.com/profile/1",
                "notes": "来自筛后外联队列",
            }
        ],
    )
    _write_json(
        audit_json,
        {
            "issue_counts": {"duplicate_candidate_ids": "0&clean"},
            "raw_capture": "data/campaigns/demo/raw/detail-live/job-001.json",
            "sync_zip": "data/output/talent-sync-full.zip",
        },
    )
    return campaign_root, final_report, outreach_csv, audit_json


def test_build_delivery_manifest_excludes_raw_db_and_sync_paths_and_marks_dry_run(tmp_path: Path):
    campaign_root, final_report, outreach_csv, audit_json = _fixture_inputs(tmp_path)

    manifest = build_delivery_manifest(
        campaign_root=campaign_root,
        final_report=final_report,
        outreach_csv=outreach_csv,
        audit_json=audit_json,
        dry_run=True,
    )

    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["schema"] == "maimai_feishu_delivery_package_v1"
    assert manifest["campaign_id"] == "demo&campaign"
    assert manifest["dry_run"] is True
    assert manifest["source_counts"]["outreach_rows"] == 1
    assert manifest["commands"][0][:5] == ["lark-cli", "docs", "+create", "--api-version", "v2"]
    assert all("--dry-run" in command for command in manifest["commands"])
    assert any("candidates" in command for command in manifest["commands"][1])
    assert any("outreach queue" in command for command in manifest["commands"][2])
    for forbidden in [
        "raw/search",
        "raw/detail",
        "raw capture",
        "raw live run",
        "talent.db",
        ".sqlite",
        ".db",
        ".zip",
        "talent-sync-full.zip",
    ]:
        assert forbidden not in serialized


def test_write_source_files_outputs_summary_and_csvs_without_reading_raw_or_db(tmp_path: Path, monkeypatch):
    campaign_root, final_report, outreach_csv, audit_json = _fixture_inputs(tmp_path)
    manifest = build_delivery_manifest(campaign_root, final_report, outreach_csv, audit_json, dry_run=True)
    report = feishu_delivery_package._load_json(final_report)
    audit = feishu_delivery_package._load_json(audit_json)
    rows = feishu_delivery_package._read_csv(outreach_csv)

    original_open = Path.open
    opened: list[str] = []

    def guarded_open(self, *args, **kwargs):
        opened.append(self.as_posix())
        path = self.as_posix()
        assert "/raw/" not in path
        assert not path.endswith(".db")
        assert not path.endswith(".sqlite")
        assert not path.endswith(".zip")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)

    write_source_files(manifest, report, audit, rows)

    generated = manifest["generated_files"]
    summary_xml = Path(generated["summary_xml"])
    candidate_csv = Path(generated["candidate_csv"])
    outreach_source_csv = Path(generated["outreach_csv"])
    assert summary_xml.exists()
    assert candidate_csv.exists()
    assert outreach_source_csv.exists()
    assert "敏感数据边界" in summary_xml.read_text(encoding="utf-8-sig")
    assert "张三 &amp; &lt;top&gt;" in summary_xml.read_text(encoding="utf-8-sig")

    with candidate_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        candidate_rows = list(csv.DictReader(handle))
    with outreach_source_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        outreach_rows = list(csv.DictReader(handle))

    assert candidate_rows == outreach_rows
    assert candidate_rows[0]["name"] == "张三 & <top>"
    assert all("/raw/" not in path for path in opened)


def test_render_summary_xml_escapes_campaign_metrics_and_candidate_names():
    xml = render_summary_xml(
        report={"campaign_id": "demo&<campaign>", "summary": {"final_recommended_count": "2&<3>"}},
        audit={"issue_counts": {"bad&key": "<none>"}},
        outreach_rows=[{"candidate_id": "1", "name": "王&<五>", "priority": "P0"}],
    )

    assert "demo&amp;&lt;campaign&gt;" in xml
    assert "2&amp;&lt;3&gt;" in xml
    assert "bad&amp;key" in xml
    assert "&lt;none&gt;" in xml
    assert "王&amp;&lt;五&gt;" in xml
    assert "demo&<campaign>" not in xml
    assert "王&<五>" not in xml


def test_cli_dry_run_writes_manifest_and_sources_without_publish_executor(tmp_path: Path, monkeypatch, capsys):
    campaign_root, final_report, outreach_csv, audit_json = _fixture_inputs(tmp_path)
    manifest_out = campaign_root / "reports" / "feishu-manifest.json"

    def fail_publish(commands):
        raise AssertionError("dry-run must not call publish executor")

    monkeypatch.setattr(feishu_delivery_package, "run_publish_commands", fail_publish)

    code = main([
        "--campaign-root",
        str(campaign_root),
        "--final-report",
        str(final_report),
        "--outreach-csv",
        str(outreach_csv),
        "--audit-json",
        str(audit_json),
        "--manifest-out",
        str(manifest_out),
        "--dry-run",
    ])

    assert code == 0
    printed = json.loads(capsys.readouterr().out)
    stored = json.loads(manifest_out.read_text(encoding="utf-8-sig"))
    assert printed == stored
    assert Path(stored["generated_files"]["summary_xml"]).exists()
    assert "publish_results" not in stored


def test_run_publish_commands_stops_after_first_failure(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(command, text, capture_output, check):
        calls.append(command)
        if command == ["second"]:
            return SimpleNamespace(returncode=2, stdout="", stderr="failed")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(feishu_delivery_package.subprocess, "run", fake_run)

    results = run_publish_commands([["first"], ["second"], ["third"]])

    assert calls == [["first"], ["second"]]
    assert [result["returncode"] for result in results] == [0, 2]
    assert results[1]["stderr"] == "failed"
