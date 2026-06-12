"""Evaluation and reporting helpers for second-brain P0."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from scripts.second_brain_models import write_json


def _load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain an object")
    return data


def evaluate_replay(*, calibration_files: list[Path], out_path: str | Path) -> dict[str, Any]:
    suggestions: list[dict[str, Any]] = []
    for path in calibration_files:
        payload = _load(path)
        for suggestion in payload.get("suggestions", []):
            if isinstance(suggestion, dict):
                suggestions.append(suggestion)
    suggestion_count = len(suggestions)
    sourced = [suggestion for suggestion in suggestions if suggestion.get("source_refs")]
    l3_auto = [
        suggestion
        for suggestion in suggestions
        if suggestion.get("level") == "L3"
        and suggestion.get("auto_apply_decision") == "applied"
    ]
    metrics = {
        "suggestion_count": suggestion_count,
        "source_coverage_rate": round(len(sourced) / suggestion_count, 4)
        if suggestion_count
        else 0.0,
        "l3_auto_apply_count": len(l3_auto),
    }
    result = {"schema_version": "second_brain_evaluation_v1", "metrics": metrics}
    write_json(out_path, result)
    return result


def render_report(evaluation: dict[str, Any], out_path: str | Path) -> Path:
    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Second Brain Evaluation Report", "", "## Metrics"]
    for key, value in sorted((evaluation.get("metrics") or {}).items()):
        lines.append(f"- {key}: {value}")
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target
