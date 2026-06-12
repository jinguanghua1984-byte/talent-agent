from pathlib import Path

from scripts.second_brain_evaluation import evaluate_replay, render_report


def test_evaluate_replay_computes_core_metrics(tmp_path: Path) -> None:
    calibration = tmp_path / "historical-calibration.json"
    calibration.write_text(
        """
{
  "schema_version": "second_brain_historical_calibration_v1",
  "suggestions": [
    {
      "suggestion_id": "cal_l0",
      "level": "L0",
      "auto_apply_decision": "applied",
      "source_refs": [{"source_path": "docs/second-brain/cases/a.md"}]
    },
    {
      "suggestion_id": "cal_l3",
      "level": "L3",
      "auto_apply_decision": "review",
      "source_refs": [{"source_path": "docs/second-brain/cases/a.md"}]
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )

    result = evaluate_replay(
        calibration_files=[calibration],
        out_path=tmp_path / "evaluation.json",
    )

    assert result["metrics"]["source_coverage_rate"] == 1.0
    assert result["metrics"]["suggestion_count"] == 2
    assert result["metrics"]["l3_auto_apply_count"] == 0


def test_render_report_writes_markdown(tmp_path: Path) -> None:
    evaluation = {
        "schema_version": "second_brain_evaluation_v1",
        "metrics": {
            "source_coverage_rate": 1.0,
            "suggestion_count": 2,
            "l3_auto_apply_count": 0,
        },
    }

    report = render_report(evaluation, tmp_path / "report.md")

    assert report.exists()
    text = report.read_text(encoding="utf-8")
    assert "# Second Brain Evaluation Report" in text
    assert "source_coverage_rate" in text
