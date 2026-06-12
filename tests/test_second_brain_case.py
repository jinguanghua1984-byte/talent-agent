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


def _fixture_canonical_run(tmp_path: Path) -> Path:
    run_root = tmp_path / "data" / "output" / "jd-tencent-multimodal-2026-06-13"
    _write_json(
        run_root / "profile" / "role-profile.json",
        {
            "role_id": "jd-tencent-multimodal",
            "target_role": "多模态视频算法",
            "summary": "多模态视频算法岗位，强调视频理解和工程落地。",
            "client_id": "client_tencent_games",
            "jd_family": "multi_modal_algorithm",
        },
    )
    _write_json(
        run_root / "scoring" / "scorecard.json",
        {
            "role_id": "jd-tencent-multimodal",
            "dimensions": [
                {"id": "video_algorithm", "label": "视频算法", "weight": 0.4},
            ],
        },
    )
    outreach = run_root / "reports" / "outreach-queue.csv"
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
                "recommendation_reason": "视频算法和工程落地都强，profile_url=https://example.test/a",
                "consultant_decision": "认可",
                "feedback_note": "张三在腾讯不错，可以推荐；trackable_token=abc",
            }
        )
        writer.writerow(
            {
                "candidate_id": "cand-002",
                "rank": "2",
                "name": "李四",
                "current_company": "字节",
                "current_title": "多模态算法",
                "recommendation_reason": "视频理解经验匹配。",
                "consultant_decision": "不认可",
                "feedback_note": "方向偏，暂不推荐。",
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


def test_prepare_case_reads_canonical_jd_outputs_and_sanitizes_cases(
    tmp_path: Path,
) -> None:
    run_root = _fixture_canonical_run(tmp_path)

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
    public_content = public_case.read_text(encoding="utf-8")
    private_content = private_case.read_text(encoding="utf-8")

    assert "profile/role-profile.json" in public_content
    assert "scoring/scorecard.json" in public_content
    assert "reports/outreach-queue.csv" in public_content
    assert "张三" not in public_content
    assert "腾讯" not in public_content
    assert "trackable_token" not in public_content
    assert "profile_url" not in public_content
    assert "https://example.test/a" not in public_content
    assert "张三" in private_content
    assert "腾讯" in private_content
    assert "trackable_token" not in private_content
    assert "profile_url" not in private_content
    assert "https://example.test/a" not in private_content


def test_prepare_case_emits_events_for_each_outreach_row_with_line_refs(
    tmp_path: Path,
) -> None:
    run_root = _fixture_canonical_run(tmp_path)

    prepare_case(
        run_root=run_root,
        repo_root=tmp_path,
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
    )

    events = load_jsonl(tmp_path / "data" / "second-brain" / "events.jsonl")
    recommended = [
        event for event in events if event["event_type"] == "candidate_recommended"
    ]
    feedback = [
        event
        for event in events
        if event["event_type"] == "consultant_feedback_received"
    ]

    assert [event["payload"]["candidate_id"] for event in recommended] == [
        "cand-001",
        "cand-002",
    ]
    assert [event["payload"]["candidate_id"] for event in feedback] == [
        "cand-001",
        "cand-002",
    ]
    first_ref = recommended[0]["source_refs"][0]
    assert first_ref["source_path"].endswith("reports/outreach-queue.csv")
    assert first_ref["line_start"] == 2
    assert first_ref["line_end"] == 2
    assert first_ref["candidate_id"] == "cand-001"
    assert first_ref["run_id"] == run_root.name
