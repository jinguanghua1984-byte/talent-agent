import json
import subprocess
from pathlib import Path


def test_second_brain_init_creates_directories(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "scripts.second_brain",
            "init",
            "--repo-root",
            str(tmp_path),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "data" / "second-brain").exists()
    assert (tmp_path / "docs" / "second-brain" / "cases").exists()
    payload = json.loads(result.stdout)
    assert payload["status"] == "initialized"


def test_second_brain_report_command(tmp_path: Path) -> None:
    evaluation = tmp_path / "evaluation.json"
    evaluation.write_text(
        json.dumps(
            {
                "schema_version": "second_brain_evaluation_v1",
                "metrics": {"suggestion_count": 1, "source_coverage_rate": 1.0},
            }
        ),
        encoding="utf-8",
    )
    report = tmp_path / "report.md"

    result = subprocess.run(
        [
            ".venv/bin/python",
            "-m",
            "scripts.second_brain",
            "report",
            "--evaluation",
            str(evaluation),
            "--out",
            str(report),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert report.exists()
