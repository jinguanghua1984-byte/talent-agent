import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import cross_channel_import
from scripts.talent_db import TalentDB


BOUND_FILE = "structured/cross-channel-bound-candidates.jsonl"


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def _bound_row(status: str = "auto_bound") -> dict:
    return {
        "schema": "boss_maimai_bound_candidate_v1",
        "target": {
            "target_id": "boss-app-1",
            "candidate_key": "boss-app:1",
            "real_name": "陶壮",
            "current_company": "华为技术有限公司",
            "current_title": "大模型推理工程师",
            "city": "上海",
            "education": "硕士",
            "work_years": 8,
            "boss_payload": {
                "candidate_key": "boss-app:1",
                "real_name": "陶壮",
                "current_company": "华为技术有限公司",
                "current_title": "大模型推理工程师",
                "city": "上海",
                "education": "硕士",
                "work_years": 8,
                "skill_tags": ["推理加速"],
                "work_experience": [
                    {"company": "华为技术有限公司", "title": "大模型推理工程师"}
                ],
                "profile_url": "boss://candidate/boss-001",
            },
        },
        "decision": {
            "source_platform": "boss_app",
            "source_candidate_key": "boss-app:1",
            "target_platform": "maimai",
            "target_platform_id": "mm-001",
            "target_profile_url": (
                "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
            ),
            "query_text": "陶壮 华为技术有限公司 大模型推理工程师",
            "query_level": "name_company_title",
            "confidence": 98,
            "score_breakdown": {"total": 98},
            "match_status": status,
            "decision_reason": "高精度匹配",
        },
        "maimai_hit": {
            "platform_id": "mm-001",
            "name": "陶壮",
            "company": "华为云计算技术有限公司",
            "title": "AI Infra 研发",
            "city": "上海",
            "profile_url": (
                "https://maimai.cn/profile/detail?dstu=mm-001&trackable_token=tok"
            ),
            "hunting_status": "在看机会",
            "skill_tags": ["AI Infra"],
            "work_experience": [
                {"company": "华为云计算技术有限公司", "title": "AI Infra 研发"}
            ],
        },
    }


def test_import_bound_candidates_keeps_boss_primary_and_adds_maimai_source(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / BOUND_FILE, [_bound_row()])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["created"] == 1
    assert result["blocked"] == []
    assert result["errors"] == []
    db = TalentDB(db_path)
    try:
        candidates = db.search().items
        candidate = candidates[0]
        sources = db.get_sources(candidate.id)
        matches = db.identity_matches(candidate.id)
        fields = db.field_values(candidate.id)
        detail = db.get_detail(candidate.id)
    finally:
        db.close()

    assert candidate.name == "陶壮"
    assert candidate.current_company == "华为技术有限公司"
    assert candidate.current_title == "大模型推理工程师"
    assert candidate.city == "上海"
    assert candidate.work_years == 8
    assert candidate.education == "硕士"
    assert candidate.hunting_status == "在看机会"
    assert candidate.skill_tags == ("推理加速", "AI Infra")
    assert detail is not None
    assert detail.work_experience == (
        {"company": "华为技术有限公司", "title": "大模型推理工程师"},
        {"company": "华为云计算技术有限公司", "title": "AI Infra 研发"},
    )
    assert sorted(source.platform for source in sources) == ["boss_app", "maimai"]
    assert any(source.platform_id == "mm-001" for source in sources)
    assert matches[0].source_platform == "boss_app"
    assert matches[0].source_candidate_key == "boss-app:1"
    assert matches[0].target_platform == "maimai"
    assert matches[0].query_text == "陶壮 华为技术有限公司 大模型推理工程师"
    assert matches[0].query_level == "name_company_title"
    assert matches[0].score_breakdown == {"total": 98}
    assert matches[0].match_status == "auto_bound"
    assert any(
        field.field_name == "current_company"
        and field.merge_decision == "primary_kept"
        for field in fields
    )
    assert any(
        field.field_name == "profile_url"
        and field.merge_decision == "supplement_added"
        for field in fields
    )
    assert (root / "reports/cross-channel-import-result.json").exists()


def test_import_bound_candidates_dry_run_does_not_create_db_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / BOUND_FILE, [_bound_row()])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=True)

    assert result["would_import"] == 1
    assert result["created"] == 0
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
        assert db.identity_matches() == []
        assert db.field_values() == []
    finally:
        db.close()
    assert (root / "reports/cross-channel-import-dry-run.json").exists()


@pytest.mark.parametrize(
    "status",
    ["pending_confirmation", "no_match", "rejected"],
)
def test_import_bound_candidates_blocks_unconfirmed_rows_without_writing(
    tmp_path: Path,
    status: str,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / BOUND_FILE, [_bound_row(status=status)])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["created"] == 0
    assert result["blocked"] == [
        {
            "line": 1,
            "candidate_key": "boss-app:1",
            "reason": "identity_not_confirmed",
            "match_status": status,
        }
    ]
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_import_bound_candidates_clean_gate_blocks_mixed_unconfirmed_rows(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    pending = _bound_row(status="pending_confirmation")
    pending["target"]["candidate_key"] = "boss-app:2"
    pending["decision"]["source_candidate_key"] = "boss-app:2"
    _write_jsonl(root / BOUND_FILE, [_bound_row(), pending])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["would_import"] == 1
    assert result["created"] == 0
    assert result["blocked"][0]["reason"] == "identity_not_confirmed"
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
        assert db.identity_matches() == []
        assert db.field_values() == []
    finally:
        db.close()
    report = json.loads(
        (root / "reports/cross-channel-import-result.json").read_text(encoding="utf-8")
    )
    assert report["created"] == 0


def test_import_bound_candidates_clean_gate_blocks_mixed_schema_errors(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    bad = _bound_row()
    bad["target"]["candidate_key"] = "boss-app:2"
    bad["decision"]["source_candidate_key"] = "boss-app:2"
    bad["decision"]["confidence"] = "bad"
    _write_jsonl(root / BOUND_FILE, [_bound_row(), bad])

    result = cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    assert result["would_import"] == 1
    assert result["created"] == 0
    assert result["errors"] == [
        {
            "line": 2,
            "candidate_key": "boss-app:2",
            "errors": ["decision.confidence must be a number"],
        }
    ]
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_import_bound_candidates_rejects_missing_bound_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="cross-channel-bound-candidates.jsonl"):
        cross_channel_import.import_bound_candidates(
            tmp_path / "campaign",
            tmp_path / "campaign/talent.db",
        )


def test_import_bound_candidates_field_audit_uses_maimai_source_profile_id(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / BOUND_FILE, [_bound_row()])

    cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    db = TalentDB(db_path)
    try:
        candidate = db.search().items[0]
        maimai_source = next(
            source
            for source in db.get_sources(candidate.id)
            if source.platform == "maimai"
        )
        fields = db.field_values(candidate.id)
    finally:
        db.close()

    maimai_audits = [
        field for field in fields if field.field_name in {"current_company", "profile_url"}
    ]
    assert maimai_audits
    assert all(field.source_profile_id == maimai_source.id for field in maimai_audits)


def test_import_bound_candidates_audits_maimai_name_conflict_with_source_id(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    row = _bound_row()
    row["maimai_hit"]["name"] = "陶壮-Maimai"
    _write_jsonl(root / BOUND_FILE, [row])

    cross_channel_import.import_bound_candidates(root, db_path, dry_run=False)

    db = TalentDB(db_path)
    try:
        candidate = db.search().items[0]
        maimai_source = next(
            source
            for source in db.get_sources(candidate.id)
            if source.platform == "maimai"
        )
        fields = db.field_values(candidate.id)
    finally:
        db.close()

    name_audit = next(field for field in fields if field.field_name == "name")
    assert candidate.name == "陶壮"
    assert name_audit.merge_decision == "primary_kept"
    assert name_audit.source_profile_id == maimai_source.id
    assert name_audit.field_value == {
        "boss_primary": "陶壮",
        "maimai_value": "陶壮-Maimai",
    }


def test_cross_channel_import_cli_returns_nonzero_for_blocked_without_writing(
    tmp_path: Path,
) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    _write_jsonl(root / BOUND_FILE, [_bound_row(status="pending_confirmation")])

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.cross_channel_import",
            "import",
            "--campaign-root",
            str(root),
            "--db",
            str(db_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 1
    output = json.loads(completed.stdout)
    assert output["blocked"][0]["reason"] == "identity_not_confirmed"
    db = TalentDB(db_path)
    try:
        assert db.count() == 0
    finally:
        db.close()


def test_load_bound_candidates_rejects_non_object_jsonl(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    path = root / BOUND_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1, 2, 3]\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        cross_channel_import.import_bound_candidates(root, root / "talent.db")
