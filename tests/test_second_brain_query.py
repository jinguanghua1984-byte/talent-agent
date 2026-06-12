import json
from pathlib import Path

from scripts.second_brain_query import build_historical_calibration


def test_build_historical_calibration_uses_local_case_fallback(tmp_path: Path) -> None:
    case_dir = tmp_path / "docs" / "second-brain" / "cases"
    case_dir.mkdir(parents=True)
    (case_dir / "client-tencent-multi-modal-run-001.md").write_text(
        "\n".join(
            [
                "# Second Brain Case: client_tencent_games / multi_modal_algorithm",
                "## 顾问反馈摘要",
                "- 认可：1",
                "- 不认可：1",
                "## 反馈原因样本",
                "- 方向偏，缺少视频算法落地证据",
            ]
        ),
        encoding="utf-8",
    )
    jd = tmp_path / "jd.md"
    jd.write_text("多模态视频算法，需要视频理解和工程落地。", encoding="utf-8")
    out_dir = tmp_path / "run" / "second-brain"

    result = build_historical_calibration(
        repo_root=tmp_path,
        jd_path=jd,
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        out_dir=out_dir,
        gbrain_results=[],
    )

    assert (out_dir / "historical-calibration.md").exists()
    assert (out_dir / "historical-calibration.json").exists()
    assert (out_dir / "sourcing-strategy-suggestions.md").exists()
    assert result["status"] == "fallback_local_cases"
    payload = json.loads(
        (out_dir / "historical-calibration.json").read_text(encoding="utf-8")
    )
    assert payload["query_lanes"][0]["lane"] == "client_preference"
    assert payload["suggestions"][0]["level"] == "L0"
    assert payload["suggestions"][0]["source_refs"]
