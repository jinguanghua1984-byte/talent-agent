import json
import subprocess
import sys
from pathlib import Path

from scripts.liepin_broad_recall_summary import build_broad_recall_summary, write_broad_recall_summary
from scripts.liepin_campaign import ensure_campaign


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_build_broad_recall_summary_aggregates_adaptive_reports_without_db_write(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(
        paths.reports_dir / "page-quality-search-wave-001.jsonl",
        [
            {"quality_band": "good", "candidate_count": 30, "detail_eligible_count": 12},
            {"quality_band": "low", "candidate_count": 20, "detail_eligible_count": 0},
        ],
    )
    _write_json(
        paths.search_summary_json,
        {"source": "adaptive_search", "candidate_count": 45, "pages_scanned": 2},
    )
    _write_json(
        paths.reports_dir / "search-import-dry-run.json",
        {"mode": "dry-run", "result": {"created": 45, "merged": 0, "pending": 0, "errors": 0}},
    )
    _write_json(
        paths.reports_dir / "campaign-summary.json",
        {"candidate_count": 45, "detail_count": 0, "detail_coverage_ratio": 0},
    )

    summary = build_broad_recall_summary(paths.root)

    assert summary["schema"] == "liepin_broad_recall_summary_v1"
    assert summary["campaign_id"] == "liepin-demo"
    assert summary["page_quality"]["total_pages"] == 2
    assert summary["page_quality"]["quality_bands"] == {"good": 1, "observe": 0, "low": 1}
    assert summary["page_quality"]["total_candidates_seen"] == 50
    assert summary["page_quality"]["detail_eligible_count"] == 12
    assert summary["search_summary"]["candidate_count"] == 45
    assert summary["search_import"]["dry_run"]["created"] == 45
    assert summary["campaign_db"]["candidate_count"] == 45
    assert summary["no_main_db_write"] is True
    assert summary["no_recommendation_report"] is True
    assert summary["no_feishu_delivery"] is True
    assert not (paths.root / "talent.db").exists()


def test_write_broad_recall_summary_writes_sanitized_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(
        paths.reports_dir / "page-quality-search-wave-001.jsonl",
        [{"quality_band": "good", "candidate_count": 1, "detail_eligible_count": 1}],
    )
    _write_json(paths.search_summary_json, {"candidate_count": 1, "pages_scanned": 1})

    summary = write_broad_recall_summary(paths.root)

    assert summary["page_quality"]["total_pages"] == 1
    report_json = paths.reports_dir / "broad-recall-summary.json"
    report_md = paths.reports_dir / "broad-recall-summary.md"
    assert report_json.exists()
    assert report_md.exists()
    dumped = report_json.read_text(encoding="utf-8-sig") + report_md.read_text(encoding="utf-8")
    assert "showresumedetail" not in dumped
    assert "ck_id=" not in dumped
    assert "rawPreview" not in dumped
    assert "secret" not in dumped


def test_broad_recall_summary_cli_prints_json(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_jsonl(
        paths.reports_dir / "page-quality-search-wave-001.jsonl",
        [{"quality_band": "observe", "candidate_count": 3, "detail_eligible_count": 1}],
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_campaign_orchestrator",
            "broad-recall-summary",
            "--campaign-root",
            str(paths.root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["schema"] == "liepin_broad_recall_summary_v1"
    assert payload["page_quality"]["quality_bands"]["observe"] == 1
