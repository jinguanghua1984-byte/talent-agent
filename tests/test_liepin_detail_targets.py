import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.liepin_campaign import ensure_campaign
from scripts.liepin_detail_targets import plan_detail_packs, plan_detail_smoke_targets
from scripts.liepin_detail_live_gate import detail_job_path


SENSITIVE_REPORT_MARKERS = (
    "showresumedetail",
    "liepin.com",
    "/resume/showresumedetail",
    "secret-token",
    "ck-secret",
    '"ckId"',
    '"skId"',
    '"fkId"',
    "ckId=",
    "skId=",
    "fkId=",
    "?ck_id",
    "&ck_id",
    "ck_id=",
    "?sk_id",
    "&sk_id",
    "sk_id=",
    "?fk_id",
    "&fk_id",
    "fk_id=",
)


def _assert_report_text_is_sanitized(report_text: str) -> None:
    for marker in SENSITIVE_REPORT_MARKERS:
        assert marker not in report_text


def _write_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def _candidate(
    platform_id: str,
    *,
    title: str = "AI产品经理",
    company: str = "示例公司",
    user_id: str | None = None,
    profile_url: str | None = None,
    education: str = "硕士",
    work_years: int = 8,
    active_name: str = "今天活跃",
    card_index: int = 0,
    search_page: str = "raw/search/page-000.json",
) -> dict:
    resolved_user_id = user_id if user_id is not None else f"user-{platform_id}"
    resolved_profile_url = (
        profile_url
        if profile_url is not None
        else "https://h.liepin.com/resume/showresumedetail/"
        f"?res_id_encode={platform_id}&ck_id=secret-token"
    )
    return {
        "platform": "liepin",
        "platform_id": platform_id,
        "user_id_encode": resolved_user_id,
        "display_name": "张**",
        "current_company": company,
        "current_title": title,
        "city": "北京",
        "education": education,
        "work_years": work_years,
        "active_status": {"code": "1", "name": active_name},
        "profile_url": resolved_profile_url,
        "raw_ref": {
            "search_page": search_page,
            "card_index": card_index,
            "ckId": "ck-secret",
            "skId": "sk-secret",
            "fkId": "fk-secret",
        },
    }


def test_plan_detail_smoke_targets_selects_detail_p0_and_masks_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = [
        _candidate("res-1", card_index=0),
        _candidate("res-2", card_index=1),
        _candidate("res-low", title="学生", company="大学", work_years=1, card_index=2),
        _candidate("res-missing-url", profile_url="", card_index=3),
        _candidate("res-missing-user", user_id="", card_index=4),
    ]
    _write_rows(paths.candidate_summaries, rows)

    result = plan_detail_smoke_targets(paths.root, priority="detail_p0", limit=10)

    assert result["schema"] == "liepin_detail_smoke_targets_v1"
    assert result["pack_id"] == "liepin-detail-p0-smoke-001"
    assert result["selected_count"] == 2
    assert result["skipped_count"] == 3
    assert result["target_pack"].endswith("raw/detail-targets/liepin-detail-p0-smoke-001.json")
    pack = json.loads((paths.root / result["target_pack"]).read_text(encoding="utf-8-sig"))
    assert [item["platform_id"] for item in pack["contacts"]] == ["res-1", "res-2"]
    assert pack["contacts"][0]["priority"] == "detail_p0"
    assert pack["metadata"]["limit"] == 10
    assert pack["metadata"]["no_database_write"] is True
    report_json = (paths.reports_dir / "detail-smoke-targets.json").read_text(encoding="utf-8-sig")
    report_md = (paths.reports_dir / "detail-smoke-targets.md").read_text(encoding="utf-8")
    for report_text in (report_json, report_md):
        _assert_report_text_is_sanitized(report_text)


def test_plan_detail_smoke_targets_enforces_limit_bounds(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate(f"res-{index}", card_index=index) for index in range(25)])

    default_result = plan_detail_smoke_targets(paths.root)
    assert default_result["selected_count"] == 10

    max_result = plan_detail_smoke_targets(paths.root, limit=20)
    assert max_result["selected_count"] == 20

    with pytest.raises(ValueError, match="limit must be between 1 and 20"):
        plan_detail_smoke_targets(paths.root, limit=21)


def test_plan_detail_smoke_targets_prefers_high_scores_over_jsonl_order(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = [
        _candidate(f"res-low-{index}", education="本科", work_years=12, card_index=index)
        for index in range(4)
    ]
    rows.append(_candidate("res-high", education="硕士", work_years=8, card_index=9))
    _write_rows(paths.candidate_summaries, rows)

    result = plan_detail_smoke_targets(paths.root, limit=2)

    pack = json.loads((paths.root / result["target_pack"]).read_text(encoding="utf-8-sig"))
    assert [item["platform_id"] for item in pack["contacts"]] == ["res-high", "res-low-0"]
    assert pack["contacts"][0]["score"] > pack["contacts"][1]["score"]
    assert result["skipped_count"] == 3
    assert len(result["skipped"]) == 3


def test_plan_detail_smoke_targets_dedupes_platform_id_and_keeps_strongest(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = [
        _candidate("res-dupe", education="本科", work_years=12, card_index=0),
        _candidate("res-unique", education="硕士", work_years=8, card_index=1),
        _candidate("res-dupe", education="硕士", work_years=8, user_id="other-user", card_index=2),
    ]
    _write_rows(paths.candidate_summaries, rows)

    result = plan_detail_smoke_targets(paths.root, limit=10)

    pack = json.loads((paths.root / result["target_pack"]).read_text(encoding="utf-8-sig"))
    contacts_by_id = {item["platform_id"]: item for item in pack["contacts"]}
    assert [item["platform_id"] for item in pack["contacts"]] == ["res-dupe", "res-unique"]
    assert contacts_by_id["res-dupe"]["score"] == 95
    assert contacts_by_id["res-dupe"]["user_id_encode"] == "other-user"
    assert pack["metadata"]["dedupe_key"] == "platform_id"
    assert result["dedupe_key"] == "platform_id"
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["reason"] == "duplicate_platform_id"


def test_plan_detail_smoke_targets_trims_required_fields_before_dedupe_and_output(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = [
        _candidate(
            " res-trim ",
            user_id=" user-trim-low ",
            profile_url=" https://example.com/low ",
            active_name="30天内活跃",
        ),
        _candidate("res-trim", user_id=" user-trim-high ", education="博士", profile_url=" https://example.com/high "),
    ]
    _write_rows(paths.candidate_summaries, rows)

    result = plan_detail_smoke_targets(paths.root, limit=10)

    pack = json.loads((paths.root / result["target_pack"]).read_text(encoding="utf-8-sig"))
    assert len(pack["contacts"]) == 1
    assert pack["contacts"][0]["platform_id"] == "res-trim"
    assert pack["contacts"][0]["user_id_encode"] == "user-trim-high"
    assert pack["contacts"][0]["profile_url"] == "https://example.com/high"
    assert result["skipped_count"] == 1
    assert result["skipped"][0]["platform_id"] == "res-trim"


@pytest.mark.parametrize(
    "search_page",
    [
        "h.liepin.com/resume/showresumedetail/?ck_id=x",
        "resume/showresumedetail/?ck_id=x",
        "raw/search/page-000.json?ckId=x",
    ],
)
def test_plan_detail_smoke_reports_redact_suspicious_search_page_forms(
    tmp_path: Path,
    search_page: str,
):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate("res-1", search_page=search_page)])

    result = plan_detail_smoke_targets(paths.root)

    assert result["samples"][0]["raw_ref"]["search_page"] == "redacted-search-page"
    report_json = (paths.reports_dir / "detail-smoke-targets.json").read_text(encoding="utf-8-sig")
    report_md = (paths.reports_dir / "detail-smoke-targets.md").read_text(encoding="utf-8")
    for report_text in (report_json, report_md):
        _assert_report_text_is_sanitized(report_text)


def test_plan_detail_smoke_reports_keep_normal_search_page_visible(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate("res-1", search_page="raw/search/page-000.json")])

    result = plan_detail_smoke_targets(paths.root)

    assert result["samples"][0]["raw_ref"]["search_page"] == "raw/search/page-000.json"
    report_json = (paths.reports_dir / "detail-smoke-targets.json").read_text(encoding="utf-8-sig")
    assert "raw/search/page-000.json" in report_json


def test_plan_detail_smoke_reports_sanitize_polluted_search_page(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(
        paths.candidate_summaries,
        [
            _candidate(
                "res-1",
                search_page=(
                    "https://h.liepin.com/resume/showresumedetail/"
                    "?ck_id=secret-token&sk_id=s&fk_id=f&ckId=raw&skId=raw&fkId=raw"
                ),
            )
        ],
    )

    result = plan_detail_smoke_targets(paths.root)

    assert result["samples"][0]["raw_ref"]["search_page"] == "redacted-search-page"
    report_json = (paths.reports_dir / "detail-smoke-targets.json").read_text(encoding="utf-8-sig")
    report_md = (paths.reports_dir / "detail-smoke-targets.md").read_text(encoding="utf-8")
    for report_text in (report_json, report_md):
        _assert_report_text_is_sanitized(report_text)


def test_plan_detail_smoke_cli_prints_json(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(paths.candidate_summaries, [_candidate("res-1")])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.liepin_detail_targets",
            "--campaign-root",
            str(paths.root),
            "--priority",
            "detail_p0",
            "--limit",
            "10",
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["selected_count"] == 1
    assert payload["skipped_count"] == 0


def test_plan_detail_packs_selects_priorities_splits_and_excludes_terminal_jobs(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    rows = []
    for index in range(7):
        rows.append(_candidate(f"res-p0-{index}", card_index=index))
    for index in range(5):
        rows.append(
            _candidate(
                f"res-p1-{index}",
                education="本科",
                work_years=2,
                active_name="30天内活跃",
                card_index=20 + index,
            )
        )
    rows.append(_candidate("res-skip", title="学生", company="大学", work_years=1, card_index=99))
    _write_rows(paths.candidate_summaries, rows)
    completed_dir = paths.raw_dir / "detail-live" / "liepin-detail-p0-smoke-001"
    completed_dir.mkdir(parents=True)
    detail_job_path(completed_dir, 0).write_text(
        json.dumps({"schema": "liepin_detail_smoke_job_v1", "status": "done", "platform_id": "res-p0-0"}),
        encoding="utf-8",
    )
    detail_job_path(completed_dir, 1).write_text(
        json.dumps({"schema": "liepin_detail_smoke_job_v1", "status": "privacy_protected", "platform_id": "res-p0-1"}),
        encoding="utf-8",
    )

    result = plan_detail_packs(
        paths.root,
        priorities=["detail_p0", "detail_p1"],
        pack_size=5,
        scope="p0-p1",
        exclude_completed=True,
    )

    assert result["schema"] == "liepin_detail_pack_plan_v1"
    assert result["selected_count"] == 10
    assert result["excluded_completed_count"] == 2
    assert result["priority_counts"] == {"detail_p0": 5, "detail_p1": 5}
    assert result["pack_count"] == 2
    assert [pack["contact_count"] for pack in result["packs"]] == [5, 5]
    all_pack = json.loads((paths.root / result["all_targets_path"]).read_text(encoding="utf-8-sig"))
    assert all(contact["platform_id"] != "res-p0-0" for contact in all_pack["contacts"])
    assert all(contact["platform_id"] != "res-p0-1" for contact in all_pack["contacts"])
    first_pack = json.loads((paths.root / result["packs"][0]["path"]).read_text(encoding="utf-8-sig"))
    assert first_pack["metadata"]["no_live_request"] is True
    assert first_pack["metadata"]["no_database_write"] is True
    assert first_pack["contacts"][0]["priority"] == "detail_p0"


def test_plan_detail_packs_writes_sanitized_reports(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "liepin-demo")
    _write_rows(
        paths.candidate_summaries,
        [
            _candidate(
                "res-1",
                search_page=(
                    "https://h.liepin.com/resume/showresumedetail/"
                    "?ck_id=secret-token&sk_id=s&fk_id=f&rawPreview=x"
                ),
            )
        ],
    )

    result = plan_detail_packs(paths.root, priorities=["detail_p0"], pack_size=100, scope="p0")

    assert result["selected_count"] == 1
    report_json = (paths.reports_dir / "detail-pack-plan.json").read_text(encoding="utf-8-sig")
    report_md = (paths.reports_dir / "detail-pack-plan.md").read_text(encoding="utf-8")
    for report_text in (report_json, report_md):
        _assert_report_text_is_sanitized(report_text)
        assert "rawPreview" not in report_text
