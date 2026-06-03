import json
import subprocess
import sys
from pathlib import Path

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_candidate_pool_diagnostic import diagnose_candidate_pool


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _candidate(
    platform_id: str,
    *,
    title: str,
    company: str = "示例公司",
    education: str = "本科",
    work_years: int = 8,
    active_name: str = "今天活跃",
    page: str = "raw/search/page-000.json",
) -> dict:
    return {
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": f"user-{platform_id}",
        "display_name": "张**",
        "current_company": company,
        "current_title": title,
        "city": "北京",
        "education": education,
        "work_years": work_years,
        "expected_city": "北京",
        "expected_title": "",
        "active_status": {"code": "1", "name": active_name},
        "profile_url": (
            "https://h.liepin.com/resume/showresumedetail/"
            f"?res_id_encode={platform_id}&ck_id=secret-token"
        ),
        "raw_ref": {
            "search_page": page,
            "card_index": 0,
            "ckId": "ck-secret",
            "skId": "sk-secret",
            "fkId": "fk-secret",
        },
    }


def test_diagnose_candidate_pool_writes_distribution_and_priority_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(
        paths.candidate_summaries,
        [
            _candidate("res-1", title="AI产品经理", education="硕士", work_years=7),
            _candidate(
                "res-2",
                title="学生",
                company="大学",
                education="本科",
                work_years=1,
                active_name="",
                page="raw/search/page-001.json",
            ),
            _candidate("res-1", title="AI产品经理", education="硕士", work_years=7),
        ],
    )

    report = diagnose_candidate_pool(paths.root)

    assert report["schema"] == "liepin_candidate_pool_diagnostic_v1"
    assert report["candidate_count"] == 3
    assert report["unique_candidate_count"] == 2
    assert report["duplicate_candidate_count"] == 1
    assert report["page_distribution"] == {
        "raw/search/page-000.json": 2,
        "raw/search/page-001.json": 1,
    }
    assert sum(report["priority_counts"].values()) == 3
    assert report["priority_counts"]["detail_p0"] >= 1
    assert report["samples"]["detail_p0"][0]["platform_id"] == "res-1"
    assert "profile_url" not in report["samples"]["detail_p0"][0]
    assert "ckId" not in json.dumps(report["samples"], ensure_ascii=False)
    assert paths.reports_dir.joinpath("candidate-pool-diagnostic.json").exists()
    md = paths.reports_dir.joinpath("candidate-pool-diagnostic.md").read_text(encoding="utf-8")
    assert "猎聘候选池离线诊断" in md
    assert "候选总数：3" in md


def test_diagnose_pool_cli_prints_report(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate("res-1", title="技术专家")])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_candidate_pool_diagnostic",
            "--campaign-root",
            str(paths.root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["candidate_count"] == 1
    assert payload["priority_counts"]["detail_p0"] == 1
