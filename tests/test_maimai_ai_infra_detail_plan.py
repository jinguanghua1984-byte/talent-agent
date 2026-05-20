import json
import sqlite3
from pathlib import Path

import pytest

from scripts.maimai_ai_infra_detail_plan import (
    build_ab_detail_packs,
    collect_review_items,
    compute_pack_count,
    dedupe_review_items,
)
from scripts.talent_db import TalentDB


def write_review(path: Path, wave: str, items: list[dict]) -> None:
    path.write_text(
        json.dumps({"wave_id": wave, "items": items}, ensure_ascii=False),
        encoding="utf-8-sig",
    )


def seed_source_profile(db_path: Path, candidate_id: int, platform_id: str, token: str) -> None:
    db = TalentDB(db_path)
    try:
        created_id = db.ingest(
            {
                "name": f"候选人{candidate_id}",
                "current_company": "字节跳动",
                "current_title": "大模型推理工程师",
                "platform_id": platform_id,
                "profile_url": f"https://maimai.cn/profile/detail?dstu={platform_id}&trackable_token={token}",
                "trackable_token": token,
            },
            platform="maimai",
        )
        assert created_id == candidate_id
    finally:
        db.close()
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE source_profiles
            SET raw_profile = ?
            WHERE candidate_id = ?
            """,
            (json.dumps({"trackable_token": token}, ensure_ascii=False), candidate_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_compute_pack_count_caps_detail_pack_size():
    assert compute_pack_count(total_contacts=0, pack_size=100) == 1
    assert compute_pack_count(total_contacts=100, pack_size=100) == 1
    assert compute_pack_count(total_contacts=101, pack_size=100) == 2
    assert compute_pack_count(total_contacts=596, pack_size=100) == 6

    for pack_size in (0, -1):
        with pytest.raises(ValueError, match="pack_size must be positive"):
            compute_pack_count(total_contacts=10, pack_size=pack_size)


def test_collect_review_items_filters_ab_and_attaches_wave(tmp_path: Path):
    review_dir = tmp_path / "review"
    review_dir.mkdir()
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "ignored",
        [
            {"candidate_id": 1, "grade": "A", "score": 90},
            {"candidate_id": 2, "grade": "B", "score": 80},
            {"candidate_id": 3, "grade": "C", "score": 70},
            {"candidate_id": 4, "grade": "淘汰", "score": 30},
        ],
    )

    items = collect_review_items(review_dir, ["wave-001"], {"A", "B"})

    assert [item["candidate_id"] for item in items] == [1, 2]
    assert all(item["wave_id"] == "wave-001" for item in items)


def test_dedupe_review_items_keeps_a_then_score_then_early_wave_then_id():
    result = dedupe_review_items(
        [
            {"candidate_id": 1, "grade": "B", "score": 100, "wave_id": "wave-001"},
            {"candidate_id": 1, "grade": "A", "score": 80, "wave_id": "wave-002"},
            {"candidate_id": 2, "grade": "B", "score": 81, "wave_id": "wave-003"},
            {"candidate_id": 2, "grade": "B", "score": 82, "wave_id": "wave-004"},
            {"candidate_id": 3, "grade": "B", "score": 70, "wave_id": "wave-005"},
            {"candidate_id": 3, "grade": "B", "score": 70, "wave_id": "wave-001"},
        ]
    )

    by_id = {item["candidate_id"]: item for item in result}
    assert by_id[1]["grade"] == "A"
    assert by_id[2]["score"] == 82
    assert by_id[3]["wave_id"] == "wave-001"


def test_build_ab_detail_packs_dedupes_and_splits_round_robin(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    for candidate_id in range(1, 9):
        seed_source_profile(db_path, candidate_id, f"u{candidate_id}", f"t{candidate_id}")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [
            {"candidate_id": 1, "grade": "B", "score": 80},
            {"candidate_id": 1, "grade": "A", "score": 90},
            {"candidate_id": 2, "grade": "C", "score": 70},
            {"candidate_id": 3, "grade": "A", "score": 95},
            {"candidate_id": 4, "grade": "B", "score": 88},
            {"candidate_id": 5, "grade": "B", "score": 87},
            {"candidate_id": 6, "grade": "A", "score": 86},
            {"candidate_id": 7, "grade": "B", "score": 85},
            {"candidate_id": 8, "grade": "A", "score": 84},
        ],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=4,
    )

    assert result["metadata"]["status"] == "ready"
    assert result["metadata"]["input_rows"] == 9
    assert result["metadata"]["unique_targets"] == 8
    assert result["metadata"]["source_grades"] == ["A", "B", "C"]
    assert result["metadata"]["selection_reason"] == "abc_total_lte_threshold"
    assert result["metadata"]["missing"] == 0
    assert [pack["count"] for pack in result["packs"]] == [2, 2, 2, 2]
    assert result["packs"][0]["contacts"][0]["candidate_id"] == 3
    assert result["packs"][1]["contacts"][0]["candidate_id"] == 1
    assert any(contact["grade"] == "C" for contact in result["contacts"])
    assert (out_dir / "detail-targets-ab-all.json").exists()
    assert (out_dir / "detail-ab-pack-001.json").exists()


def test_build_ab_detail_packs_excludes_c_when_abc_total_exceeds_threshold(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    for candidate_id in range(1, 104):
        seed_source_profile(db_path, candidate_id, f"u{candidate_id}", f"t{candidate_id}")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [
            {"candidate_id": candidate_id, "grade": "A" if candidate_id <= 2 else "C", "score": 1000 - candidate_id}
            for candidate_id in range(1, 104)
        ],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=1,
        pack_size=100,
    )

    assert result["metadata"]["status"] == "ready"
    assert result["metadata"]["source_grades"] == ["A", "B"]
    assert result["metadata"]["selection_reason"] == "ab_default"
    assert result["metadata"]["abc_total"] == 103
    assert result["metadata"]["unique_targets"] == 2
    assert [contact["grade"] for contact in result["contacts"]] == ["A", "A"]


def test_build_ab_detail_packs_caps_ready_targets_by_pack_size(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    for candidate_id in range(1, 206):
        seed_source_profile(db_path, candidate_id, f"u{candidate_id}", f"t{candidate_id}")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [
            {"candidate_id": candidate_id, "grade": "A", "score": 1000 - candidate_id}
            for candidate_id in range(1, 206)
        ],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=1,
        pack_size=100,
    )

    assert result["metadata"]["status"] == "ready"
    assert result["metadata"]["pack_count"] == 3
    assert len(result["packs"]) == 3
    assert sum(pack["count"] for pack in result["packs"]) == 205
    assert all(pack["count"] <= 100 for pack in result["packs"])
    assert all((out_dir / f"detail-ab-pack-{index:03d}.json").exists() for index in range(1, 4))


def test_build_ab_detail_packs_blocks_missing_trackable_token(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    seed_source_profile(db_path, 1, "u1", "")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=4,
    )

    assert result["metadata"]["status"] == "blocked"
    assert result["metadata"]["missing"] == 1
    assert result["missing"][0]["reason"] == "missing_trackable_token"
    assert (out_dir / "detail-targets-ab-all.json").exists()
    assert not (out_dir / "detail-ab-pack-001.json").exists()


def test_build_ab_detail_packs_does_not_create_missing_db(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    review_dir.mkdir(parents=True)
    db_path = root / "missing.db"
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=root / "raw" / "detail-targets",
    )

    assert result["metadata"]["status"] == "blocked"
    assert {item["reason"] for item in result["missing"]} == {"missing_db_file"}
    assert not db_path.exists()


def test_build_ab_detail_packs_handles_escaped_readonly_db_uri(tmp_path: Path):
    root = tmp_path / "campaign#with%chars"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent#db%readonly.db"
    seed_source_profile(db_path, 1, "u1", "t1")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=1,
    )

    assert result["metadata"]["status"] == "ready"
    assert result["metadata"]["missing"] == 0
    assert result["packs"][0]["contacts"][0]["id"] == "u1"
    assert result["packs"][0]["contacts"][0]["trackable_token"] == "t1"
    assert (out_dir / "detail-ab-pack-001.json").exists()


def test_build_ab_detail_packs_blocks_when_review_file_missing(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    seed_source_profile(db_path, 1, "u1", "t1")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001", "wave-002"],
        out_dir=root / "raw" / "detail-targets",
    )

    assert result["metadata"]["status"] == "blocked"
    assert any(item["reason"] == "missing_review_file" for item in result["missing"])
    assert not (root / "raw" / "detail-targets" / "detail-ab-pack-001.json").exists()


def test_blocked_build_removes_all_existing_pack_glob(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    seed_source_profile(db_path, 1, "u1", "")
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )
    for index in range(1, 5):
        (out_dir / f"detail-ab-pack-{index:03d}.json").write_text("{}", encoding="utf-8")

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
        pack_count=2,
    )

    assert result["metadata"]["status"] == "blocked"
    assert not list(out_dir.glob("detail-ab-pack-*.json"))


def test_build_ab_detail_packs_blocks_missing_platform_id(tmp_path: Path):
    root = tmp_path / "campaign"
    review_dir = root / "review"
    out_dir = root / "raw" / "detail-targets"
    review_dir.mkdir(parents=True)
    db_path = root / "talent.db"
    seed_source_profile(db_path, 1, "u1", "t1")
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """
            UPDATE source_profiles
            SET platform_id = NULL,
                profile_url = NULL,
                raw_profile = ?
            WHERE candidate_id = 1
            """,
            (json.dumps({"trackable_token": "t1"}, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()
    write_review(
        review_dir / "initial-human-review-draft-wave-001.json",
        "wave-001",
        [{"candidate_id": 1, "grade": "A", "score": 99}],
    )

    result = build_ab_detail_packs(
        campaign_root=root,
        db_path=db_path,
        waves=["wave-001"],
        out_dir=out_dir,
    )

    assert result["metadata"]["status"] == "blocked"
    assert result["missing"][0]["reason"] == "missing_maimai_platform_id"
    assert not (out_dir / "detail-ab-pack-001.json").exists()
