import json
from pathlib import Path

import pytest

from scripts.boss_maimai_targets import export_targets, load_jsonl, main


def _append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _campaign_root(tmp_path: Path) -> Path:
    root = tmp_path / "campaign"
    (root / "structured").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    return root


def test_export_selects_contact_candidates_latest_row_and_writes_query_plans(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    candidates = root / "structured/candidates.jsonl"
    _append_jsonl(
        candidates,
        {
            "candidate_key": "boss-app:old",
            "real_name": "旧名",
            "real_name_status": "captured",
            "current_company": "旧公司",
            "current_title": "旧职位",
            "recommendation": "contact",
        },
    )
    _append_jsonl(
        candidates,
        {
            "candidate_key": "boss-app:old",
            "real_name": "旧名",
            "real_name_status": "captured",
            "current_company": "旧公司",
            "current_title": "旧职位",
            "recommendation": "hold",
        },
    )
    _append_jsonl(
        candidates,
        {
            "candidate_key": "boss-app:selected/1",
            "real_name": "张三",
            "real_name_status": "captured",
            "current_company": "字节跳动",
            "current_title": "高级 AI 产品负责人",
            "city": "北京",
            "education": "硕士",
            "recommendation": "would_contact",
            "detail_sections": {
                "recent_companies": ["腾讯"],
                "schools": ["清华大学"],
            },
            "boss_payload": {"encryptGeekId": "boss-1"},
        },
    )

    summary = export_targets(root)

    assert summary["selected_count"] == 1
    assert summary["target_count"] == 1
    assert summary["missing_real_name_count"] == 0
    rows = [
        json.loads(line)
        for line in (root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["schema"] == "boss_maimai_match_target_v1"
    assert rows[0]["candidate_key"] == "boss-app:selected/1"
    assert rows[0]["target_id"] == "boss-app-selected-1"
    assert rows[0]["query_plan"][0]["text"] == "张三 字节跳动 高级 AI 产品负责人"
    assert rows[0]["query_plan"][-1]["allow_auto_bind"] is False
    assert rows[0]["recent_companies"] == ["腾讯"]
    assert rows[0]["schools"] == ["清华大学"]
    assert json.loads((root / "reports/maimai-match-summary.json").read_text(encoding="utf-8")) == summary
    assert "target_count: 1" in (root / "reports/maimai-match-summary.md").read_text(encoding="utf-8")


def test_export_selects_nested_contact_and_would_contact_candidate(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:nested",
            "real_name": "李四",
            "real_name_status": "captured",
            "current_company": "腾讯",
            "current_title": "技术负责人",
            "screening": {"detail_decision": "contact"},
            "contact": {"would_contact": True},
            "detail": {
                "recent_companies": ["百度"],
                "schools": ["浙江大学"],
            },
        },
    )

    summary = export_targets(root)
    row = json.loads((root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8").strip())

    assert summary["selected_count"] == 1
    assert summary["target_count"] == 1
    assert row["recent_companies"] == ["百度"]
    assert row["schools"] == ["浙江大学"]


def test_export_extracts_school_from_boss_detail_text_and_adds_school_queries(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:school-text",
            "real_name": "周超",
            "real_name_status": "captured",
            "current_company": "亥姆霍兹信息安全中心",
            "current_title": "安全研究员",
            "recommendation": "contact",
            "detail_sections": {
                "basic_info": "博士；伦敦大学学院；电子电气工程",
                "education_experience": "博士；伦敦大学学院；电子电气工程",
                "work_experience": [
                    {
                        "company": "亥姆霍兹信息安全中心",
                        "title": "安全研究员",
                        "description": "伦敦大学学院电子电气工程博士",
                    }
                ],
            },
            "boss_payload": {"encryptGeekId": "boss-school-text"},
        },
    )

    export_targets(root)
    row = json.loads((root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8").strip())
    query_plan = row["query_plan"]

    assert row["schools"] == []
    assert row["school_fallbacks"] == ["伦敦大学学院"]
    assert row["company_aliases"] == ["海姆霍兹信息安全中心"]
    assert row["boss_payload"] == {"encryptGeekId": "boss-school-text"}
    assert not any(item["level"] == "name_school_title_core" for item in query_plan)
    assert {
        "level": "name_school_fallback",
        "text": "周超 伦敦大学学院",
        "allow_auto_bind": False,
        "evidence_type": "school",
    } in query_plan
    assert any(
        query["text"] == "周超 海姆霍兹信息安全中心"
        and query["allow_auto_bind"] is False
        and query.get("evidence_type") == "company_alias"
        for query in query_plan
    )


def test_export_preserves_full_source_row_when_boss_payload_is_missing(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:full-row",
            "real_name": "赵六",
            "real_name_status": "captured",
            "current_company": "美团",
            "current_title": "算法工程师",
            "city": "上海",
            "education": "本科",
            "recommendation": "contact",
            "detail": {"work_years": "6年", "recent_companies": ["快手"], "schools": ["上海交通大学"]},
            "screening": {"recommendation": "contact", "evidence_path": "reports/evidence.json"},
            "work_years": "6年",
            "evidence_path": "structured/details/boss-app-full-row.json",
        },
    )

    export_targets(root)
    row = json.loads((root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8").strip())

    assert row["boss_payload"]["candidate_key"] == "boss-app:full-row"
    assert row["boss_payload"]["recommendation"] == "contact"
    assert row["boss_payload"]["detail"]["work_years"] == "6年"
    assert row["boss_payload"]["screening"]["evidence_path"] == "reports/evidence.json"
    assert row["boss_payload"]["work_years"] == "6年"
    assert row["boss_payload"]["evidence_path"] == "structured/details/boss-app-full-row.json"
    assert "_source_index" not in row["boss_payload"]


def test_missing_real_name_is_reported_and_not_exported(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:missing",
            "real_name": "",
            "real_name_status": "missing",
            "current_company": "腾讯",
            "current_title": "产品经理",
            "recommendation": "contact",
        },
    )

    summary = export_targets(root)

    assert summary["selected_count"] == 1
    assert summary["target_count"] == 0
    assert summary["missing_real_name_count"] == 1
    assert summary["missing_real_name"] == ["boss-app:missing"]
    assert (root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8") == ""


def test_dry_run_real_name_status_blocks_even_with_non_empty_real_name(tmp_path: Path) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:dry-run-name",
            "real_name": "张三",
            "real_name_status": "not_available_dry_run",
            "current_company": "字节跳动",
            "current_title": "产品经理",
            "recommendation": "contact",
        },
    )

    summary = export_targets(root)

    assert summary["selected_count"] == 1
    assert summary["target_count"] == 0
    assert summary["missing_real_name_count"] == 1
    assert summary["missing_real_name"] == ["boss-app:dry-run-name"]
    assert (root / "structured/maimai-match-targets.jsonl").read_text(encoding="utf-8") == ""


def test_missing_campaign_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_targets(tmp_path / "missing-campaign")


def test_load_jsonl_rejects_non_object_rows(tmp_path: Path) -> None:
    path = tmp_path / "rows.jsonl"
    path.write_text('{"ok": true}\n["not", "object"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match=r"line 2: expected object"):
        load_jsonl(path)


def test_cli_export_prints_summary_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _campaign_root(tmp_path)
    _append_jsonl(
        root / "structured/candidates.jsonl",
        {
            "candidate_key": "boss-app:cli",
            "real_name": "王五",
            "real_name_status": "captured",
            "current_company": "阿里",
            "current_title": "算法工程师",
            "recommendation": "contact",
        },
    )

    assert main(["export", "--campaign-root", str(root)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["target_count"] == 1
