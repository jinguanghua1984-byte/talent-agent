import csv
import json
from pathlib import Path

from scripts.maimai_ai_infra_outreach_export import export_outreach_package


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8-sig")


def card(candidate_id: int, priority: str, name: str, **overrides):
    data = {
        "rank": candidate_id,
        "candidate_id": candidate_id,
        "name": name,
        "platform_id": f"p{candidate_id}",
        "profile_url": f"https://maimai.cn/profile/detail?dstu=p{candidate_id}",
        "company": "字节跳动",
        "title": "AI Infra",
        "city": "上海",
        "work_years": 6,
        "score": 96,
        "grade": "A",
        "recommendation_label": "强推荐",
        "priority": priority,
        "directions": ["推理引擎", "训练框架"],
        "key_evidence": ["评分证据：推理/GPU", "工作经历：负责 LLM 推理引擎"],
        "risk_flags": [],
        "risk_summary": "无明显硬风险",
        "suggested_outreach_angle": "确认推理引擎角色深度。",
    }
    data.update(overrides)
    return data


def test_export_outreach_package_writes_queue_csv_and_p0_p1_audit(tmp_path: Path):
    outreach_path = tmp_path / "final-outreach.json"
    write_json(
        outreach_path,
        {
            "metadata": {"export_type": "maimai_ai_infra_outreach_priority"},
            "queue_counts": {"P0": 2, "P1": 1, "P2": 1},
            "priority_queues": {
                "P0": [
                    card(1, "P0", "Alice"),
                    card(2, "P0", "Bob", profile_url=""),
                ],
                "P1": [
                    card(
                        3,
                        "P1",
                        "Carol",
                        recommendation_label="推荐",
                        score=80,
                        key_evidence=[],
                    )
                ],
                "P2": [card(4, "P2", "Dave", recommendation_label="观察", score=70)],
            },
            "excluded": [],
        },
    )

    result = export_outreach_package(
        outreach_json_path=outreach_path,
        out_csv=tmp_path / "outreach.csv",
        out_md=tmp_path / "outreach.md",
        out_audit_json=tmp_path / "audit.json",
        out_audit_md=tmp_path / "audit.md",
        audit_limit=2,
    )

    assert result["exported_rows"] == 4
    assert result["audit"]["sample_counts"] == {"P0": 2, "P1": 1}
    assert result["audit"]["issue_counts"]["missing_profile_url"] == 1
    assert result["audit"]["issue_counts"]["missing_key_evidence"] == 1

    with (tmp_path / "outreach.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert rows[0]["priority"] == "P0"
    assert rows[0]["candidate_id"] == "1"
    assert rows[0]["directions"] == "推理引擎、训练框架"
    assert rows[0]["profile_url"].startswith("https://maimai.cn/profile/detail")
    assert rows[-1]["priority"] == "P2"

    audit = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8-sig"))
    assert audit["samples"]["P0"][1]["candidate_id"] == 2
    assert "missing_profile_url" in audit["samples"]["P0"][1]["issues"]
    assert "missing_key_evidence" in audit["samples"]["P1"][0]["issues"]
    assert (tmp_path / "outreach.md").exists()
    assert (tmp_path / "audit.md").exists()
