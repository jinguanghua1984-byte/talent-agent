import json
from pathlib import Path

import pytest

from scripts.boss_maimai_targets import export_targets, main


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


def test_missing_campaign_file_raises_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_targets(tmp_path / "missing-campaign")


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
