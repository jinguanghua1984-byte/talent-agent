"""Historical calibration query and local fallback for second-brain P0."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.second_brain_models import write_json

LANES = [
    "client_preference",
    "role_family_pattern",
    "candidate_feedback_pattern",
    "sourcing_strategy_pattern",
    "recommendation_narrative_pattern",
    "failure_reason_pattern",
]


def _case_matches(path: Path, client_id: str, jd_family: str) -> bool:
    name = path.name.lower()
    content = path.read_text(encoding="utf-8").lower()
    client_terms = {client_id.lower(), client_id.lower().replace("_", "-")}
    family_terms = {jd_family.lower(), jd_family.lower().replace("_", "-")}
    haystack = f"{name}\n{content}"
    return any(term in haystack for term in client_terms) and any(
        term in haystack for term in family_terms
    )


def _load_matching_cases(repo_root: Path, client_id: str, jd_family: str) -> list[Path]:
    case_dir = repo_root / "docs" / "second-brain" / "cases"
    if not case_dir.exists():
        return []
    return sorted(
        path for path in case_dir.glob("*.md") if _case_matches(path, client_id, jd_family)
    )


def _source_ref(path: Path, repo_root: Path) -> dict[str, str]:
    return {
        "source_path": str(path.relative_to(repo_root)),
        "source_type": "second_brain_case",
        "artifact_key": "case_summary",
    }


def _render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Historical Calibration",
        "",
        f"- client_id: `{payload['client_id']}`",
        f"- jd_family: `{payload['jd_family']}`",
        f"- status: `{payload['status']}`",
        "",
        "## 建议",
    ]
    for suggestion in payload["suggestions"]:
        lines.extend(
            [
                f"### {suggestion['suggestion_id']}",
                f"- level: `{suggestion['level']}`",
                f"- target: `{suggestion['target']}`",
                f"- statement: {suggestion['statement']}",
                f"- auto_apply_decision: `{suggestion['auto_apply_decision']}`",
                f"- guardrail_reason: {suggestion['guardrail_reason']}",
                "",
            ]
        )
    lines.append("## Evidence")
    for ref in payload["source_refs"]:
        lines.append(f"- `{ref['source_path']}` / {ref['artifact_key']}")
    return "\n".join(lines) + "\n"


def _render_sourcing(payload: dict[str, Any]) -> str:
    lines = [
        "# Sourcing Strategy Suggestions",
        "",
        "P0 只生成寻访策略建议，不自动执行平台动作。",
        "",
        "## 建议",
        "- 优先补充历史 feedback 中反复缺失的证据。",
        "- 对同客户同 JD family 的目标公司池进行人工或 agent review。",
        "- 平台执行仍必须走 canonical workflow 和安全门禁。",
        "",
        "## Evidence",
    ]
    for ref in payload["source_refs"]:
        lines.append(f"- `{ref['source_path']}`")
    return "\n".join(lines) + "\n"


def build_historical_calibration(
    *,
    repo_root: str | Path,
    jd_path: str | Path,
    client_id: str,
    jd_family: str,
    out_dir: str | Path,
    gbrain_results: list[dict[str, Any]],
) -> dict[str, Any]:
    repo = Path(repo_root)
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    case_paths = _load_matching_cases(repo, client_id, jd_family)
    source_refs = [_source_ref(path, repo) for path in case_paths]
    status = "gbrain" if gbrain_results else "fallback_local_cases"
    query_lanes = [{"lane": lane, "source_count": len(source_refs)} for lane in LANES]
    suggestions = [
        {
            "suggestion_id": "cal_l0_recommendation_context",
            "level": "L0",
            "target": "recommendation_narrative",
            "action": "enhance",
            "statement": "推荐理由需要显式连接历史 feedback 中的认可/不认可模式。",
            "confidence": 0.6 if source_refs else 0.2,
            "auto_apply_decision": "applied" if source_refs else "review",
            "guardrail_reason": "L0 解释层建议；来源为本地 case fallback。",
            "source_refs": source_refs,
        }
    ]
    payload = {
        "schema_version": "second_brain_historical_calibration_v1",
        "client_id": client_id,
        "jd_family": jd_family,
        "jd_path": str(Path(jd_path)),
        "status": status,
        "query_lanes": query_lanes,
        "source_refs": source_refs,
        "suggestions": suggestions,
    }
    write_json(output / "historical-calibration.json", payload)
    (output / "historical-calibration.md").write_text(
        _render_markdown(payload),
        encoding="utf-8",
    )
    (output / "sourcing-strategy-suggestions.md").write_text(
        _render_sourcing(payload),
        encoding="utf-8",
    )
    return payload
