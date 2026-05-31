from __future__ import annotations

import json
from pathlib import Path

from scripts.maimai_broad_recall_adaptive import (
    adaptive_policy_from_strategy,
    build_broad_recall_summary,
    build_broad_recall_search_units,
    build_detail_priority_outputs,
    evaluate_page_quality_run,
    is_broad_recall_strategy,
    next_unit_status,
    score_page_quality,
)
from scripts.talent_db import TalentDB


def _broad_strategy() -> dict:
    return {
        "strategy_mode": "broad_recall_adaptive_v1",
        "strategy_version": "hunyuan-broad-v1",
        "keyword_packages": [
            {
                "id": "p0-data",
                "priority": "P0",
                "position_terms": ["数据负责人", "数据产品", "数据策略"],
                "keywords": ["大模型", "数据质量", "标注"],
                "long_tail_keywords": ["后训练数据策略", "数据闭环"],
            }
        ],
        "company_pools": {"target": ["腾讯混元", "阿里千问"]},
        "position_aliases": ["数据负责人", "数据产品专家"],
        "adaptive_search": {
            "probe_pages": 2,
            "unit_max_pages": 15,
            "good_ratio_continue": 0.3,
        },
    }


def test_build_broad_recall_units_use_strategy_mode_and_probe_pages() -> None:
    strategy = _broad_strategy()

    units = build_broad_recall_search_units(strategy)

    assert is_broad_recall_strategy(strategy) is True
    assert adaptive_policy_from_strategy(strategy)["probe_pages"] == 2
    assert units
    assert all(unit["strategy_mode"] == "broad_recall_adaptive_v1" for unit in units)
    assert all(unit["adaptive_search"]["probe_pages"] == 2 for unit in units)
    assert all(unit["max_pages"] == 2 for unit in units)
    assert all(unit["unit_max_pages"] == 15 for unit in units)
    assert all(unit["search_filters"]["cities"] == "" for unit in units)
    assert all(unit["search_filters"]["positions"] == "" for unit in units)
    assert any("腾讯混元" in unit["query"] for unit in units)


def test_build_broad_recall_units_can_order_by_company_before_keyword() -> None:
    strategy = _broad_strategy()
    strategy["unit_order"] = "company_first"
    strategy["keyword_packages"].append(
        {
            "id": "p1-inference",
            "priority": "P1",
            "position_terms": ["推理框架工程师"],
            "keywords": ["推理框架"],
        }
    )

    units = build_broad_recall_search_units(strategy)

    assert [(unit["source_company_terms"][0], unit["keyword_package"]) for unit in units[:4]] == [
        ("腾讯混元", "p0-data"),
        ("腾讯混元", "p1-inference"),
        ("阿里千问", "p0-data"),
        ("阿里千问", "p1-inference"),
    ]


def _contact(platform_id: str, company: str, title: str, text: str = "") -> dict:
    return {
        "id": platform_id,
        "platform_id": platform_id,
        "name": f"候选人{platform_id}",
        "company": company,
        "position": title,
        "title": title,
        "description": text,
        "detail_url": f"https://maimai.cn/profile/detail?dstu={platform_id}",
    }


def test_score_page_quality_uses_good_candidate_ratio_and_duplicates() -> None:
    strategy = _broad_strategy()
    page = {
        "contacts": [
            _contact("1", "腾讯", "大模型数据负责人", "负责数据质量和标注体系"),
            _contact("2", "外包公司", "销售", "渠道销售"),
        ]
    }

    quality = score_page_quality(page, strategy, seen_candidate_keys={"1"})

    assert quality["candidate_count"] == 2
    assert quality["new_candidate_count"] == 1
    assert quality["duplicate_ratio"] == 0.5
    assert quality["detail_eligible_count"] == 1
    assert quality["quality_band"] in {"observe", "good"}


def test_next_unit_status_stops_after_consecutive_low_quality_pages() -> None:
    state = {
        "unit_id": "unit-000001",
        "status": "observing",
        "consecutive_low_quality_pages": 1,
    }
    quality = {"quality_band": "low", "next_page": 4}

    updated = next_unit_status(state, quality, adaptive_policy_from_strategy({}))

    assert updated["status"] == "stopped_low_quality"
    assert updated["stop_reason"] == "consecutive_low_quality_pages"


def test_evaluate_page_quality_skips_failed_live_pages(tmp_path: Path) -> None:
    run_path = tmp_path / "run.json"
    run_path.write_text(
        json.dumps(
            {
                "batches": [
                    {
                        "batch_id": "unit-000001",
                        "pages": [
                            {"page": 1, "ok": False, "error": "captcha_api", "contacts": []},
                            {"page": 2, "ok": True, "contacts": [_contact("1", "腾讯", "大模型数据负责人")]},
                        ],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    rows = evaluate_page_quality_run(
        campaign_root=tmp_path,
        run_path=run_path,
        strategy=_broad_strategy(),
        out_jsonl=tmp_path / "reports" / "page-quality.jsonl",
        state_out=tmp_path / "state" / "adaptive-unit-state.json",
        seen_out=tmp_path / "state" / "seen-candidates.jsonl",
    )

    assert len(rows) == 1
    assert rows[0]["page"] == 2


def test_build_detail_priority_outputs_writes_review_file(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    db = TalentDB(db_path)
    try:
        db.ingest(
            {
                "name": "候选人1",
                "current_company": "腾讯",
                "current_title": "大模型数据负责人",
                "skill_tags": ["大模型", "数据质量"],
                "platform_id": "p1",
                "profile_url": "https://maimai.cn/profile/detail?dstu=p1",
            },
            platform="maimai",
        )
        db.ingest(
            {
                "name": "候选人2",
                "current_company": "外包公司",
                "current_title": "销售",
                "platform_id": "p2",
                "profile_url": "https://maimai.cn/profile/detail?dstu=p2",
            },
            platform="maimai",
        )
    finally:
        db.close()

    out_json = root / "reports" / "detail-priority.json"
    out_md = root / "reports" / "detail-priority.md"
    review_out = root / "review" / "initial-human-review-draft-search-wave-001.json"

    result = build_detail_priority_outputs(
        campaign_root=root,
        db_path=db_path,
        strategy=_broad_strategy(),
        out_json=out_json,
        out_md=out_md,
        review_out=review_out,
        wave_id="search-wave-001",
    )

    review = json.loads(review_out.read_text(encoding="utf-8-sig"))
    assert result["summary"]["detail_p0"] + result["summary"]["detail_p1"] >= 1
    assert out_json.exists()
    assert out_md.exists()
    assert any(item["grade"] in {"A", "B"} for item in review["items"])
    assert all("recommendation_label" not in item for item in result["items"])


def test_build_broad_recall_summary_excludes_outreach_recommendations(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    (root / "reports").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "reports" / "page-quality.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"unit_id": "unit-000001", "quality_band": "good", "candidate_count": 30, "detail_eligible_count": 12}, ensure_ascii=False),
                json.dumps({"unit_id": "unit-000002", "quality_band": "low", "candidate_count": 30, "detail_eligible_count": 1}, ensure_ascii=False),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "reports" / "detail-priority.json").write_text(
        json.dumps({"summary": {"detail_p0": 2, "detail_p1": 3, "detail_p2": 1, "skip": 4}}, ensure_ascii=False),
        encoding="utf-8",
    )

    out_json = root / "reports" / "broad-recall-summary.json"
    out_md = root / "reports" / "broad-recall-summary.md"

    summary = build_broad_recall_summary(root, out_json=out_json, out_md=out_md)

    text = out_md.read_text(encoding="utf-8-sig")
    assert summary["page_quality"]["total_pages"] == 2
    assert "寻访摘要" in text
    assert "外联队列" not in text
    assert "强推荐" not in text


def test_build_broad_recall_summary_accepts_bom_prefixed_jsonl_lines(tmp_path: Path) -> None:
    root = tmp_path / "campaign"
    (root / "reports").mkdir(parents=True)
    row_1 = json.dumps(
        {"unit_id": "unit-000001", "quality_band": "good", "candidate_count": 30, "detail_eligible_count": 12},
        ensure_ascii=False,
    )
    row_2 = json.dumps(
        {"unit_id": "unit-000002", "quality_band": "observe", "candidate_count": 20, "detail_eligible_count": 5},
        ensure_ascii=False,
    )
    (root / "reports" / "page-quality.jsonl").write_text(f"{row_1}\n\ufeff{row_2}\n", encoding="utf-8")

    summary = build_broad_recall_summary(
        root,
        out_json=root / "reports" / "broad-recall-summary.json",
        out_md=root / "reports" / "broad-recall-summary.md",
    )

    assert summary["page_quality"]["total_pages"] == 2
    assert summary["page_quality"]["quality_bands"]["observe"] == 1
