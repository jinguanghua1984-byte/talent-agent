import json
import sqlite3
from pathlib import Path

from scripts.maimai_ai_infra_delivery_report import build_delivery_reports


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")


def create_minimal_campaign_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE candidates (
              id INTEGER PRIMARY KEY,
              name TEXT,
              age INTEGER,
              city TEXT,
              work_years INTEGER,
              education TEXT,
              current_company TEXT,
              current_title TEXT,
              skill_tags TEXT,
              data_level TEXT
            );
            CREATE TABLE candidate_details (
              candidate_id INTEGER PRIMARY KEY,
              work_experience TEXT,
              education_experience TEXT,
              project_experience TEXT,
              raw_data TEXT,
              summary TEXT
            );
            CREATE TABLE source_profiles (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              candidate_id INTEGER,
              platform TEXT,
              platform_id TEXT,
              profile_url TEXT,
              raw_profile TEXT,
              fetched_at TEXT
            );
            """
        )
        rows = [
            (
                1,
                "Alice",
                30,
                "上海",
                6,
                "硕士",
                "字节跳动",
                "大模型推理引擎研发",
                ["TensorRT", "GPU"],
                [
                    {
                        "company": "字节跳动",
                        "title": "大模型推理引擎研发",
                        "description": "负责 LLM 推理引擎、TensorRT 加速和 GPU 性能优化",
                    }
                ],
            ),
            (
                2,
                "Bob",
                34,
                "北京",
                8,
                "本科",
                "阿里云",
                "AI 平台工程师",
                ["训练平台"],
                [
                    {
                        "company": "阿里云",
                        "title": "AI 平台工程师",
                        "description": "建设分布式训练平台和 GPU 集群调度",
                    }
                ],
            ),
            (
                3,
                "Carol",
                37,
                "深圳",
                10,
                "本科",
                "腾讯",
                "算法工程师",
                ["机器学习"],
                [
                    {
                        "company": "腾讯",
                        "title": "算法工程师",
                        "description": "参与推荐算法和少量模型部署工作",
                    }
                ],
            ),
            (
                4,
                "Dave",
                31,
                "杭州",
                7,
                "大专",
                "阿里巴巴",
                "算法工程师",
                ["机器学习"],
                [
                    {
                        "company": "阿里巴巴",
                        "title": "算法工程师",
                        "description": "业务算法策略优化",
                    }
                ],
            ),
        ]
        for row in rows:
            (
                candidate_id,
                name,
                age,
                city,
                work_years,
                education,
                company,
                title,
                skill_tags,
                work_experience,
            ) = row
            conn.execute(
                """
                INSERT INTO candidates(
                  id, name, age, city, work_years, education, current_company,
                  current_title, skill_tags, data_level
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'detailed')
                """,
                (
                    candidate_id,
                    name,
                    age,
                    city,
                    work_years,
                    education,
                    company,
                    title,
                    json.dumps(skill_tags, ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                INSERT INTO candidate_details(
                  candidate_id, work_experience, education_experience,
                  project_experience, raw_data, summary
                ) VALUES (?, ?, '[]', '[]', '{}', '')
                """,
                (candidate_id, json.dumps(work_experience, ensure_ascii=False)),
            )
            conn.execute(
                """
                INSERT INTO source_profiles(
                  candidate_id, platform, platform_id, profile_url, raw_profile, fetched_at
                ) VALUES (?, 'maimai', ?, ?, '{}', '2026-05-17')
                """,
                (
                    candidate_id,
                    f"p{candidate_id}",
                    f"https://maimai.cn/profile/detail?dstu=p{candidate_id}",
                ),
            )
        conn.commit()
    finally:
        conn.close()


def test_build_delivery_reports_maps_final_labels_and_priority_queues(tmp_path: Path):
    root = tmp_path / "campaign"
    db_path = root / "talent.db"
    create_minimal_campaign_db(db_path)
    targets_path = root / "raw" / "detail-targets" / "detail-targets-ab-all.json"
    rank_path = root / "reports" / "final-detail-rank-ab-packs-001-004.json"
    write_json(
        targets_path,
        {
            "metadata": {"input_rows": 5, "unique_targets": 4, "runnable_targets": 4},
            "packs": [
                {"metadata": {"pack_id": "detail-ab-pack-001", "count": 4}, "contacts": []}
            ],
            "contacts": [
                {"candidate_id": 1, "grade": "A", "score": 96, "wave_id": "wave-001"},
                {"candidate_id": 2, "grade": "B", "score": 80, "wave_id": "wave-001"},
                {"candidate_id": 3, "grade": "B", "score": 72, "wave_id": "wave-001"},
                {"candidate_id": 4, "grade": "A", "score": 88, "wave_id": "wave-001"},
            ],
        },
    )
    write_json(
        root / "reports" / "detail-wave-detail-ab-pack-001-apply.json",
        {"matched": 4, "written": 4, "failed_jobs": 0, "unmatched": 0},
    )
    write_json(
        rank_path,
        {
            "ranked": [
                {
                    "candidate_id": 1,
                    "name": "Alice",
                    "grade": "A",
                    "score": 96,
                    "score_mode": "detailed",
                    "evidence": {
                        "company": "字节跳动",
                        "title": "大模型推理引擎研发",
                        "title_level": "precision",
                        "tech_keywords": ["推理", "GPU", "TensorRT"],
                    },
                    "risk_flags": [],
                },
                {
                    "candidate_id": 2,
                    "name": "Bob",
                    "grade": "B",
                    "score": 80,
                    "score_mode": "detailed",
                    "evidence": {
                        "company": "阿里云",
                        "title": "AI 平台工程师",
                        "title_level": "technical",
                        "tech_keywords": ["训练", "分布式", "GPU"],
                    },
                    "risk_flags": [],
                },
                {
                    "candidate_id": 3,
                    "name": "Carol",
                    "grade": "B",
                    "score": 72,
                    "score_mode": "detailed",
                    "evidence": {
                        "company": "腾讯",
                        "title": "算法工程师",
                        "title_level": "generic",
                        "tech_keywords": ["模型部署"],
                    },
                    "risk_flags": [],
                },
                {
                    "candidate_id": 4,
                    "name": "Dave",
                    "grade": "淘汰",
                    "score": 88,
                    "score_mode": "detailed",
                    "evidence": {
                        "company": "阿里巴巴",
                        "title": "算法工程师",
                        "title_level": "generic",
                        "tech_keywords": ["机器学习"],
                    },
                    "risk_flags": ["excluded_education"],
                },
            ]
        },
    )

    result = build_delivery_reports(
        campaign_root=root,
        db_path=db_path,
        targets_path=targets_path,
        rank_json_path=rank_path,
        out_report_json=root / "reports" / "final-search-report.json",
        out_report_md=root / "reports" / "final-search-report.md",
        out_outreach_json=root / "reports" / "final-outreach-priority.json",
        out_outreach_md=root / "reports" / "final-outreach-priority.md",
    )

    report = result["search_report"]
    outreach = result["outreach_priority"]
    assert report["funnel"]["target_count"] == 4
    assert report["funnel"]["detail_completed"] == 4
    assert report["recommendation_distribution"] == {
        "强推荐": 1,
        "推荐": 1,
        "观察": 1,
        "不推荐": 1,
    }
    assert report["funnel"]["final_recommended_count"] == 2
    assert outreach["queue_counts"] == {"P0": 1, "P1": 1, "P2": 1}
    assert outreach["priority_queues"]["P0"][0]["candidate_id"] == 1
    assert outreach["priority_queues"]["P1"][0]["candidate_id"] == 2
    assert outreach["priority_queues"]["P2"][0]["candidate_id"] == 3
    assert outreach["excluded"][0]["candidate_id"] == 4
    assert set(report["direction_coverage"]) >= {"推理引擎", "训练框架"}
    assert report["company_coverage"][0]["company"] == "字节跳动"
    assert report["misclassification_analysis"]["detail_overruled_count"] == 1
    assert "TensorRT" in " ".join(outreach["priority_queues"]["P0"][0]["key_evidence"])
    assert (root / "reports" / "final-search-report.json").exists()
    assert (root / "reports" / "final-outreach-priority.md").exists()
