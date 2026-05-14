import json
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_campaign import (
    append_import_ledger,
    ensure_campaign,
    import_ledger_has_apply,
    mark_page_completed,
)
from scripts.maimai_ai_infra_pipeline import (
    build_final_report,
    extract_contacts_payload,
    extract_wave_contacts_from_pages,
    run_campaign_wave,
    run_pipeline,
    select_detail_candidate_ids,
)
from scripts.talent_db import TalentDB


def test_extract_contacts_payload_from_runner_result(tmp_path: Path):
    run_path = tmp_path / "run.json"
    out_path = tmp_path / "contacts.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": "smoke",
                "contacts": [
                    {"id": "1", "name": "Alice", "company": "字节跳动", "position": "AI Infra"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = extract_contacts_payload(run_path, out_path)

    assert payload["metadata"]["source_run"] == str(run_path)
    assert payload["contacts"][0]["name"] == "Alice"
    assert json.loads(out_path.read_text(encoding="utf-8-sig"))["contacts"][0]["id"] == "1"


def test_extract_wave_contacts_from_page_raw_dedupes_platform_ids(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"id": "u1", "name": "A"}, {"id": "u2", "name": "B"}],
        },
    )
    mark_page_completed(
        paths,
        "unit-000002",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"id": "u1", "name": "A again"}],
        },
    )

    payload = extract_wave_contacts_from_pages(paths, "wave-001")

    assert payload["metadata"]["wave_id"] == "wave-001"
    assert payload["metadata"]["total_contacts"] == 2
    assert [item["id"] for item in payload["contacts"]] == ["u1", "u2"]


def test_import_ledger_blocks_duplicate_wave_apply(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")

    append_import_ledger(paths, {"wave_id": "wave-001", "action": "apply", "status": "completed"})

    assert import_ledger_has_apply(paths, "wave-001")


def test_run_campaign_wave_dry_run_writes_contacts_and_report(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [
                {"id": "u1", "name": "A", "company": "ByteDance", "position": "AI Infra"},
                {"id": "u2", "name": "B", "company": "Huawei", "position": "ML Infra"},
            ],
        },
    )
    mark_page_completed(
        paths,
        "unit-000002",
        1,
        {
            "wave_id": "wave-001",
            "contacts": [{"platform_id": "u1", "name": "A again"}],
        },
    )

    result = run_campaign_wave(
        campaign_root=paths.root,
        config=Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"),
        wave="wave-001",
        db_path=tmp_path / "campaign.db",
    )

    contacts_path = paths.contacts_dir / "contacts-wave-001.json"
    report_path = paths.reports_dir / "import-list-wave-001-dry-run.md"
    contacts = json.loads(contacts_path.read_text(encoding="utf-8-sig"))
    assert result["contacts"] == contacts_path
    assert contacts["metadata"]["total_contacts"] == 2
    assert [item["name"] for item in contacts["contacts"]] == ["A", "B"]
    assert report_path.exists()
    assert paths.search_plan.exists()
    assert paths.search_units.exists()
    assert not import_ledger_has_apply(paths, "wave-001")


def test_run_campaign_wave_apply_aborts_when_wave_already_applied(tmp_path: Path):
    paths = ensure_campaign(tmp_path / "campaign")
    append_import_ledger(paths, {"wave_id": "wave-001", "action": "apply", "status": "completed"})
    mark_page_completed(
        paths,
        "unit-000001",
        1,
        {"wave_id": "wave-001", "contacts": [{"id": "u1", "name": "A"}]},
    )

    with pytest.raises(RuntimeError, match="already applied"):
        run_campaign_wave(
            campaign_root=paths.root,
            config=Path("configs/maimai-ai-infra-v2-cold-start-strategy.json"),
            wave="wave-001",
            db_path=tmp_path / "campaign.db",
            apply=True,
        )

    assert not (paths.contacts_dir / "contacts-wave-001.json").exists()


def test_select_detail_candidate_ids_uses_all_a_and_top_b():
    shortlist = {
        "grades": {
            "A": [{"candidate_id": 1}, {"candidate_id": 2}],
            "B": [{"candidate_id": 3}, {"candidate_id": 4}],
            "C": [{"candidate_id": 5}],
        }
    }

    assert select_detail_candidate_ids(shortlist, max_b=1) == [1, 2, 3]


def test_build_final_report_contains_required_sections(tmp_path: Path):
    out_path = tmp_path / "review.md"

    build_final_report(
        out_path,
        {
            "strategy_version": "ai-infra-v1",
            "confirmed_at": "",
            "run": {"batches": [{"status": "completed"}, {"status": "blocked"}], "contacts": [{}, {}]},
            "import_result": {"created": 1, "merged": 1, "pending": 0, "errors": 0},
            "shortlist": {
                "summary": {"A": 1, "B": 1, "C": 0, "淘汰": 2},
                "grades": {
                    "A": [{"candidate_id": 1, "name": "Alice", "score": 88, "evidence": {"company": "字节跳动"}}],
                    "B": [{"candidate_id": 2, "name": "Bob", "score": 72, "evidence": {"company": "DeepSeek"}}],
                },
            },
            "detail": {"targets": 2, "missing": 0},
            "exceptions": [{"batch_id": "x", "reason": "blocked"}],
            "next_actions": ["继续校准字段语义"],
        },
    )

    text = out_path.read_text(encoding="utf-8-sig")
    assert "策略版本" in text
    assert "执行批次" in text
    assert "A 档候选" in text
    assert "B 档候选" in text
    assert "详情补全结果" in text
    assert "异常批次" in text
    assert "下一轮建议" in text


def test_run_pipeline_uses_real_request_template_and_writes_outputs(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    out_dir = tmp_path / "output"
    template_path = tmp_path / "template.json"
    db = TalentDB(db_path)
    try:
        db.ingest(
            {
                "name": "Alice",
                "current_company": "字节跳动",
                "current_title": "大模型训练框架工程师",
                "education": "硕士",
                "work_years": 5,
                "platform_id": "166812124",
                "profile_url": (
                    "https://maimai.cn/profile/detail?dstu=166812124&"
                    "trackable_token=token-alice"
                ),
                "skill_tags": ["GPU", "vLLM", "分布式训练"],
            },
            platform="maimai",
        )
    finally:
        db.close()
    template_path.write_text(
        json.dumps(
            {
                "search": {
                    "query": "old",
                    "search_query": "old",
                    "paginationParam": {"page": 1, "size": 30},
                    "page": 0,
                    "size": 30,
                    "sid": "real-sid",
                    "sessionid": "real-session",
                    "highlight_exp": 1,
                    "data_version": "4.1",
                    "allcompanies": "一线互联网公司",
                    "positions": "",
                    "degrees": "2,3",
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    outputs = run_pipeline(
        Path("configs/maimai-ai-infra-search-strategy.json"),
        db_path,
        out_dir,
        template_path=template_path,
    )

    run = json.loads(outputs["run"].read_text(encoding="utf-8-sig"))
    patched_search = run["batches"][0]["patched_pages"][0]["body"]["search"]
    assert patched_search["sid"] == "real-sid"
    assert patched_search["sessionid"] == "real-session"
    assert patched_search["highlight_exp"] == 1
    assert patched_search["data_version"] == "4.1"
    assert patched_search["query"] != "old"
    assert outputs["contacts"].exists()
    assert outputs["shortlist_json"].exists()
    assert outputs["detail_targets"].exists()
    assert outputs["final_report"].exists()
