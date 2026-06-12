import csv
import json
from pathlib import Path

from scripts.second_brain_case import prepare_case
from scripts.second_brain_models import load_jsonl


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _fixture_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "data" / "output" / "jd-tencent-multimodal-2026-06-12"
    _write_json(
        run_root / "role-profile.json",
        {
            "role_id": "jd-tencent-multimodal",
            "target_role": "多模态视频算法",
            "summary": "多模态视频算法岗位，强调视频理解和工程落地。",
            "client_id": "client_tencent_games",
            "jd_family": "multi_modal_algorithm",
        },
    )
    _write_json(
        run_root / "scorecard.json",
        {
            "role_id": "jd-tencent-multimodal",
            "dimensions": [
                {"id": "video_algorithm", "label": "视频算法", "weight": 0.4},
                {"id": "engineering_delivery", "label": "工程落地", "weight": 0.3},
            ],
        },
    )
    outreach = run_root / "outreach.csv"
    outreach.parent.mkdir(parents=True, exist_ok=True)
    with outreach.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "candidate_id",
                "rank",
                "name",
                "current_company",
                "current_title",
                "recommendation_reason",
                "consultant_decision",
                "feedback_note",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "candidate_id": "cand-001",
                "rank": "1",
                "name": "张三",
                "current_company": "腾讯",
                "current_title": "视频算法专家",
                "recommendation_reason": "视频算法和工程落地都强。",
                "consultant_decision": "认可",
                "feedback_note": "这个不错，可以推荐。",
            }
        )
    return run_root


def test_prepare_case_writes_events_public_and_private_cases(tmp_path: Path) -> None:
    run_root = _fixture_run(tmp_path)
    result = prepare_case(
        run_root=run_root,
        repo_root=tmp_path,
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
    )

    public_case = tmp_path / "docs" / "second-brain" / "cases" / result["public_case"]
    private_case = tmp_path / "data" / "second-brain" / "private-cases" / result[
        "private_case"
    ]
    ledger = tmp_path / "data" / "second-brain" / "events.jsonl"

    assert public_case.exists()
    assert private_case.exists()
    assert "张三" not in public_case.read_text(encoding="utf-8")
    assert "腾讯" not in public_case.read_text(encoding="utf-8")
    assert "张三" in private_case.read_text(encoding="utf-8")
    assert "腾讯" in private_case.read_text(encoding="utf-8")

    events = load_jsonl(ledger)
    assert [event["event_type"] for event in events] == [
        "jd_profile_created",
        "scorecard_created",
        "candidate_recommended",
        "consultant_feedback_received",
        "batch_feedback_summarized",
    ]
