import json
import subprocess
import sys
from pathlib import Path

from scripts.liepin_campaign import ensure_campaign, mark_page_completed
from scripts.liepin_search_standardize import standardize_campaign


def _liepin_search_payload() -> dict:
    return {
        "flag": 1,
        "data": {
            "ckId": "ck-1",
            "skId": "sk-1",
            "fkId": "fk-1",
            "cardResList": [
                {
                    "usercIdEncode": "user-1",
                    "resSource": "h_search",
                    "wantDq": "北京",
                    "wantJobTitle": "运营经理/主管",
                    "activeStatus": {"code": "5", "name": ""},
                    "detailUrl": (
                        "/resume/showresumedetail/?res_id_encode=res-1"
                        "&ck_id=ck-1&sk_id=sk-1&fk_id=fk-1"
                    ),
                    "simpleResumeForm": {
                        "resIdEncode": "res-1",
                        "resName": "于**",
                        "resCompany": "富藏甲(北京)科技发展有限公司",
                        "resTitle": "运营经理",
                        "resDqName": "北京",
                        "resEdulevelName": "本科",
                        "resWorkyearAge": 18,
                        "wantDq": "北京",
                        "wantJobTitle": "运营经理/主管",
                        "resType": 0,
                    },
                }
            ],
        },
    }


def test_standardize_campaign_writes_candidate_summaries(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    mark_page_completed(
        paths,
        cur_page=0,
        payload=_liepin_search_payload(),
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )

    summary = standardize_campaign(paths.root)

    assert summary["status"] == "standardized"
    assert summary["candidate_count"] == 1
    rows = [
        json.loads(line)
        for line in paths.candidate_summaries.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["platform"] == "liepin"
    assert rows[0]["platform_id"] == "res-1"
    assert rows[0]["user_id_encode"] == "user-1"
    assert rows[0]["display_name"] == "于**"
    assert rows[0]["current_company"] == "富藏甲(北京)科技发展有限公司"
    assert rows[0]["current_title"] == "运营经理"
    assert rows[0]["profile_url"].startswith("https://h.liepin.com/resume/showresumedetail/")
    assert rows[0]["raw_ref"] == {
        "search_page": "raw/search/page-000.json",
        "card_index": 0,
        "ckId": "ck-1",
        "skId": "sk-1",
        "fkId": "fk-1",
    }


def test_standardize_campaign_uses_res_list_when_card_res_list_is_empty(tmp_path: Path):
    payload = _liepin_search_payload()
    payload["data"]["resList"] = payload["data"]["cardResList"]
    payload["data"]["cardResList"] = []
    paths = ensure_campaign(tmp_path / "liepin-demo")
    mark_page_completed(
        paths,
        cur_page=1,
        payload=payload,
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )

    summary = standardize_campaign(paths.root)

    assert summary["status"] == "standardized"
    assert summary["candidate_count"] == 1
    rows = [
        json.loads(line)
        for line in paths.candidate_summaries.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows[0]["platform_id"] == "res-1"
    assert rows[0]["raw_ref"]["search_page"] == "raw/search/page-001.json"


def test_standardize_campaign_reports_template_drift_without_rows(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    mark_page_completed(
        paths,
        cur_page=0,
        payload={"flag": 1, "data": {"items": []}},
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )

    summary = standardize_campaign(paths.root)

    assert summary["status"] == "template_drift"
    assert summary["candidate_count"] == 0
    assert summary["skipped_pages"][0]["reason"] == "missing_cardResList"
    assert not paths.candidate_summaries.exists()


def test_standardize_cli_writes_summary_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    mark_page_completed(
        paths,
        cur_page=0,
        payload=_liepin_search_payload(),
        request={"endpoint": "search-resumes"},
        run_id="run-001",
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_search_standardize",
            "--campaign-root",
            str(paths.root),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    stdout_summary = json.loads(completed.stdout)
    file_summary = json.loads(paths.search_summary_json.read_text(encoding="utf-8-sig"))
    assert stdout_summary["candidate_count"] == 1
    assert file_summary["candidate_count"] == 1
    assert "候选人摘要数：1" in paths.search_summary_md.read_text(encoding="utf-8")
