import json
from pathlib import Path

from scripts.maimai_ai_infra_pipeline import (
    build_final_report,
    extract_contacts_payload,
    select_detail_candidate_ids,
)


def test_extract_contacts_payload_from_runner_result(tmp_path: Path):
    run_path = tmp_path / "run.json"
    out_path = tmp_path / "contacts.json"
    run_path.write_text(
        json.dumps(
            {
                "run_id": "smoke",
                "contacts": [
                    {"id": "1", "name": "Alice", "company": "字节跳动", "position": "AI Infra"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = extract_contacts_payload(run_path, out_path)

    assert payload["metadata"]["source_run"] == str(run_path)
    assert payload["contacts"][0]["name"] == "Alice"
    assert json.loads(out_path.read_text(encoding="utf-8-sig"))["contacts"][0]["id"] == "1"


def test_select_detail_candidate_ids_uses_all_a_and_top_b():
    shortlist = {
        "grades": {
            "A": [{"candidate_id": 1}, {"candidate_id": 2}],
            "B": [{"candidate_id": 3}, {"candidate_id": 4}],
            "C": [{"candidate_id": 5}],
        }
    }

    assert select_detail_candidate_ids(shortlist, max_b=1) == [1, 2, 3]


def test_build_final_report_contains_required_sections(tmp_path: Path):
    out_path = tmp_path / "review.md"

    build_final_report(
        out_path,
        {
            "strategy_version": "ai-infra-v1",
            "confirmed_at": "",
            "run": {"batches": [{"status": "completed"}, {"status": "blocked"}], "contacts": [{}, {}]},
            "import_result": {"created": 1, "merged": 1, "pending": 0, "errors": 0},
            "shortlist": {
                "summary": {"A": 1, "B": 1, "C": 0, "淘汰": 2},
                "grades": {
                    "A": [{"candidate_id": 1, "name": "Alice", "score": 88, "evidence": {"company": "字节跳动"}}],
                    "B": [{"candidate_id": 2, "name": "Bob", "score": 72, "evidence": {"company": "DeepSeek"}}],
                },
            },
            "detail": {"targets": 2, "missing": 0},
            "exceptions": [{"batch_id": "x", "reason": "blocked"}],
            "next_actions": ["继续校准字段语义"],
        },
    )

    text = out_path.read_text(encoding="utf-8-sig")
    assert "策略版本" in text
    assert "执行批次" in text
    assert "A 档候选" in text
    assert "B 档候选" in text
    assert "详情补全结果" in text
    assert "异常批次" in text
    assert "下一轮建议" in text
