import json
from pathlib import Path

import pytest

from scripts.maimai_detail_targets import export_targets, main as detail_targets_main
from scripts.talent_db import TalentDB


def _make_db(path: Path) -> tuple[int, int]:
    db = TalentDB(path)
    try:
        maimai_id = db.ingest(
            {
                "name": "Alice",
                "current_company": "Acme",
                "current_title": "AI PM",
                "platform_id": "166812124",
                "profile_url": "https://maimai.cn/profile/detail?dstu=166812124&trackable_token=token-alice",
            },
            platform="maimai",
        )
        boss_id = db.ingest(
            {
                "name": "Bob",
                "current_company": "Beta",
                "current_title": "Backend",
                "platform_id": "boss-1",
            },
            platform="boss",
        )
        return maimai_id, boss_id
    finally:
        db.close()


def test_export_targets_from_match_top10_json(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id, _ = _make_db(db_path)
    recommendation = {
        "top10": [
            {
                "candidate_id": candidate_id,
                "name": "Alice",
                "company": "Acme",
                "title": "AI PM",
            }
        ]
    }
    input_path = tmp_path / "match.json"
    output_path = tmp_path / "targets.json"
    input_path.write_text(json.dumps(recommendation, ensure_ascii=False), encoding="utf-8")

    result = export_targets(db_path=db_path, out_path=output_path, recommendation_file=input_path)

    assert result["metadata"]["total_input"] == 1
    assert result["metadata"]["total_contacts"] == 1
    assert result["metadata"]["missing"] == 0
    assert result["contacts"] == [
        {
            "id": "166812124",
            "trackable_token": "token-alice",
            "name": "Alice",
            "company": "Acme",
            "position": "AI PM",
            "candidate_id": candidate_id,
            "detail_url": "https://maimai.cn/profile/detail?dstu=166812124&trackable_token=token-alice",
        }
    ]

    written = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert written["contacts"][0]["id"] == "166812124"


def test_export_targets_from_candidate_ids_skips_non_maimai(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    maimai_id, boss_id = _make_db(db_path)
    output_path = tmp_path / "targets.json"

    result = export_targets(db_path=db_path, out_path=output_path, candidate_ids=[maimai_id, boss_id, 999])

    assert result["metadata"]["total_input"] == 3
    assert result["metadata"]["total_contacts"] == 1
    assert result["metadata"]["missing"] == 2
    assert result["contacts"][0]["candidate_id"] == maimai_id
    assert {item["candidate_id"] for item in result["missing"]} == {boss_id, 999}


def test_export_targets_uses_profile_url_from_recommendation_when_present(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    _make_db(db_path)
    recommendation = {
        "results": [
            {
                "name": "Carol",
                "company": "Gamma",
                "title": "Product",
                "profile_url": "https://maimai.cn/profile/detail?dstu=222&trackable_token=token-carol",
            }
        ]
    }
    input_path = tmp_path / "search.json"
    output_path = tmp_path / "targets.json"
    input_path.write_text(json.dumps(recommendation, ensure_ascii=False), encoding="utf-8")

    result = export_targets(db_path=db_path, out_path=output_path, recommendation_file=input_path)

    assert result["contacts"][0]["id"] == "222"
    assert result["contacts"][0]["trackable_token"] == "token-carol"
    assert result["contacts"][0]["candidate_id"] is None


def test_detail_targets_from_review_cli_exports_detail_now_ids(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    candidate_id, boss_id = _make_db(db_path)
    review_path = tmp_path / "review.json"
    output_path = tmp_path / "targets.json"
    review_path.write_text(
        json.dumps(
            {
                "campaign_id": "ai-infra-v2-smoke",
                "items": [
                    {"candidate_id": candidate_id, "decision": "detail_now", "priority": "P0"},
                    {"candidate_id": boss_id, "decision": "hold", "priority": "P1"},
                    {"candidate_id": 999, "decision": "reject", "priority": "P2"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert (
        detail_targets_main(
            [
                "from-review",
                "--review",
                str(review_path),
                "--db",
                str(db_path),
                "--out",
                str(output_path),
            ]
        )
        == 0
    )

    result = json.loads(output_path.read_text(encoding="utf-8-sig"))
    assert result["metadata"]["total_input"] == 1
    assert result["metadata"]["total_contacts"] == 1
    assert result["metadata"]["missing"] == 0
    assert [item["candidate_id"] for item in result["contacts"]] == [candidate_id]


def test_detail_targets_from_review_cli_rejects_invalid_input(tmp_path: Path):
    db_path = tmp_path / "talent.db"
    _make_db(db_path)
    review_path = tmp_path / "review.json"
    output_path = tmp_path / "targets.json"
    review_path.write_text(
        json.dumps({"items": [{"candidate_id": 1, "decision": "maybe"}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid review decision"):
        detail_targets_main(
            [
                "from-review",
                "--review",
                str(review_path),
                "--db",
                str(db_path),
                "--out",
                str(output_path),
            ]
        )
