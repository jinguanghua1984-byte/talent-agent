import json
from pathlib import Path

from scripts.maimai_ai_infra_detail_report import build_detail_report


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")


def test_build_detail_report_summarizes_coverage_and_rank_distribution(tmp_path: Path):
    root = tmp_path / "campaign"
    targets_path = root / "raw" / "detail-targets" / "detail-targets-ab-all.json"
    rank_path = root / "reports" / "final-detail-rank-ab-packs-001-004.json"
    out_json = root / "reports" / "final-detail-report-ab-packs-001-004.json"
    out_md = root / "reports" / "final-detail-report-ab-packs-001-004.md"
    write_json(
        targets_path,
        {
            "metadata": {"unique_targets": 596},
            "packs": [
                {
                    "metadata": {
                        "pack_id": "detail-ab-pack-001",
                        "count": 596,
                    },
                    "contacts": [{"candidate_id": 1}, {"candidate_id": 2}],
                }
            ],
            "contacts": [{"candidate_id": 1}, {"candidate_id": 2}],
        },
    )
    write_json(
        root / "reports" / "detail-wave-detail-ab-pack-001-apply.json",
        {
            "matched": 596,
            "written": 596,
            "failed_jobs": 0,
            "unmatched": 0,
        },
    )
    write_json(
        rank_path,
        {
            "ranked": [
                {"candidate_id": 1, "name": "Alice", "grade": "A", "score": 98},
                {"candidate_id": 2, "name": "Bob", "grade": "B", "score": 86},
            ]
        },
    )

    result = build_detail_report(
        campaign_root=root,
        targets_path=targets_path,
        rank_json_path=rank_path,
        out_json=out_json,
        out_md=out_md,
    )

    assert result["coverage"]["target_count"] == 596
    assert result["coverage"]["completed_detail_count"] == 596
    assert result["coverage"]["missing_detail_count"] == 0
    assert result["pack_statuses"][0]["pack_id"] == "detail-ab-pack-001"
    assert result["pack_statuses"][0]["apply_status"] == "applied"
    assert result["grade_distribution"]["A"] == 1
    assert result["grade_distribution"]["B"] == 1
    assert result["final_recommended_count"] == 2
    assert out_json.exists()
    assert out_md.exists()
