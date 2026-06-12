"""Build second-brain case pages and events from JD delivery runs."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import csv
import json
import re

from scripts.second_brain_models import SourceRef, append_event, build_event
from scripts.second_brain_redaction import (
    CONTACT_PATTERNS,
    SENSITIVE_MARKERS,
    assert_private_case_safe,
    assert_public_case_safe,
    redact_candidate_name,
    redact_company_name,
)


URL_PATTERN = re.compile(r"https?://\S+")
SENSITIVE_VALUE_PATTERN = re.compile(
    r"\b("
    + "|".join(re.escape(marker) for marker in sorted(SENSITIVE_MARKERS, key=len, reverse=True))
    + r")\b\s*[:=]?\s*\S*",
    re.IGNORECASE,
)


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _first_existing(run_root: Path, relative_paths: list[str], label: str) -> Path:
    for relative_path in relative_paths:
        path = run_root / relative_path
        if path.exists():
            return path
    raise FileNotFoundError(f"{label} not found under {run_root}")


def _read_outreach(run_root: Path) -> tuple[Path, list[dict[str, str]]]:
    candidates = [
        run_root / "outreach.csv",
        run_root / "outreach" / "outreach.csv",
        run_root / "reports" / "outreach-queue.csv",
    ]
    for path in candidates:
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return path, [dict(row) for row in csv.DictReader(handle)]
    raise FileNotFoundError(f"outreach CSV not found under {run_root}")


def _slug(value: str) -> str:
    lowered = value.lower().strip()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered)
    return lowered.strip("-") or "case"


def _case_name(client_id: str, jd_family: str, run_root: Path) -> str:
    return f"{_slug(client_id)}-{_slug(jd_family)}-{_slug(run_root.name)}.md"


def _source(path: Path, repo_root: Path, source_type: str, artifact_key: str) -> SourceRef:
    try:
        source_path = str(path.relative_to(repo_root))
    except ValueError:
        source_path = str(path)
    return SourceRef(
        source_path=source_path,
        source_type=source_type,
        artifact_key=artifact_key,
    )


def _outreach_source(
    path: Path,
    repo_root: Path,
    *,
    row_index: int,
    candidate_id: str,
    run_id: str,
) -> SourceRef:
    try:
        source_path = str(path.relative_to(repo_root))
    except ValueError:
        source_path = str(path)
    line_number = row_index + 2
    return SourceRef(
        source_path=source_path,
        source_type="outreach_csv",
        artifact_key=f"candidate_id={candidate_id}",
        line_start=line_number,
        line_end=line_number,
        candidate_id=candidate_id,
        run_id=run_id,
    )


def _source_path(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _sanitize_sensitive_text(value: Any) -> str:
    text = str(value or "")
    text = SENSITIVE_VALUE_PATTERN.sub("[已脱敏]", text)
    text = URL_PATTERN.sub("[已脱敏]", text)
    for pattern in CONTACT_PATTERNS:
        text = pattern.sub("[已脱敏]", text)
    return text.strip()


def _sanitize_public_text(
    value: Any,
    *,
    candidate_names: list[str],
    company_names: list[str],
) -> str:
    text = _sanitize_sensitive_text(value)
    for name in candidate_names:
        if name:
            text = text.replace(name, redact_candidate_name(name))
    for company_name in company_names:
        if company_name:
            text = text.replace(company_name, redact_company_name(company_name))
    return text


def _public_case_markdown(
    *,
    role_profile: dict[str, Any],
    scorecard: dict[str, Any],
    rows: list[dict[str, str]],
    client_id: str,
    jd_family: str,
    source_paths: list[str],
) -> str:
    candidate_names = [row.get("name", "") for row in rows]
    company_names = [row.get("current_company", "") for row in rows]
    decisions = Counter((row.get("consultant_decision") or "").strip() or "待确认" for row in rows)
    reasons = [
        _sanitize_public_text(
            row.get("feedback_note", ""),
            candidate_names=candidate_names,
            company_names=company_names,
        )
        for row in rows
        if row.get("feedback_note", "").strip()
    ]
    lines = [
        f"# Second Brain Case: {client_id} / {jd_family}",
        "",
        "## JD 画像",
        _sanitize_public_text(
            role_profile.get("summary") or role_profile.get("target_role") or "未提供画像摘要",
            candidate_names=candidate_names,
            company_names=company_names,
        ),
        "",
        "## Scorecard 摘要",
    ]
    for dim in scorecard.get("dimensions", []):
        if isinstance(dim, dict):
            lines.append(f"- {dim.get('label') or dim.get('id')}: weight={dim.get('weight')}")
    lines.extend(
        [
            "",
            "## 顾问反馈摘要",
            f"- 认可：{decisions.get('认可', 0)}",
            f"- 不认可：{decisions.get('不认可', 0)}",
            f"- 待确认：{decisions.get('待确认', 0)}",
            "",
            "## 反馈原因样本",
        ]
    )
    for note in reasons[:8]:
        lines.append(f"- {note}")
    lines.extend(["", "## Evidence"])
    for source_path in source_paths:
        lines.append(f"- `{source_path}`")
    return "\n".join(lines) + "\n"


def _private_case_markdown(
    *,
    role_profile: dict[str, Any],
    rows: list[dict[str, str]],
    client_id: str,
    jd_family: str,
) -> str:
    lines = [
        f"# Private Second Brain Case: {client_id} / {jd_family}",
        "",
        "## JD 画像",
        str(role_profile.get("summary") or role_profile.get("target_role") or "未提供画像摘要"),
        "",
        "## 候选人反馈",
    ]
    for row in rows:
        lines.extend(
            [
                f"### {row.get('name') or row.get('candidate_id')}",
                f"- candidate_id: `{row.get('candidate_id')}`",
                f"- 当前公司: {row.get('current_company') or ''}",
                f"- 职位: {row.get('current_title') or ''}",
                f"- 推荐理由: {_sanitize_sensitive_text(row.get('recommendation_reason'))}",
                f"- 顾问判断: {(row.get('consultant_decision') or '').strip() or '待确认'}",
                f"- feedback_note: {_sanitize_sensitive_text(row.get('feedback_note'))}",
                "",
            ]
        )
    return "\n".join(lines)


def _append_run_event(
    *,
    ledger: Path,
    event_type: str,
    run_id: str,
    client_id: str,
    jd_family: str,
    visibility: str,
    source_refs: list[SourceRef],
    payload: dict[str, Any],
) -> None:
    append_event(
        ledger,
        build_event(
            event_type=event_type,
            run_id=run_id,
            client_id=client_id,
            jd_family=jd_family,
            visibility=visibility,
            source_refs=source_refs,
            payload=payload,
        ),
    )


def prepare_case(
    *,
    run_root: str | Path,
    repo_root: str | Path,
    client_id: str,
    jd_family: str,
) -> dict[str, Any]:
    repo = Path(repo_root)
    root = Path(run_root)
    role_path = _first_existing(
        root, ["role-profile.json", "profile/role-profile.json"], "role profile"
    )
    scorecard_path = _first_existing(
        root, ["scorecard.json", "scoring/scorecard.json"], "scorecard"
    )
    role_profile = _read_json(role_path)
    scorecard = _read_json(scorecard_path)
    outreach_path, rows = _read_outreach(root)
    case_name = _case_name(client_id, jd_family, root)
    public_case = repo / "docs" / "second-brain" / "cases" / case_name
    private_case = repo / "data" / "second-brain" / "private-cases" / case_name
    ledger = repo / "data" / "second-brain" / "events.jsonl"
    public_case.parent.mkdir(parents=True, exist_ok=True)
    private_case.parent.mkdir(parents=True, exist_ok=True)

    source_paths = [
        _source_path(role_path, repo),
        _source_path(scorecard_path, repo),
        _source_path(outreach_path, repo),
    ]
    public_content = _public_case_markdown(
        role_profile=role_profile,
        scorecard=scorecard,
        rows=rows,
        client_id=client_id,
        jd_family=jd_family,
        source_paths=source_paths,
    )
    private_content = _private_case_markdown(
        role_profile=role_profile,
        rows=rows,
        client_id=client_id,
        jd_family=jd_family,
    )
    assert_public_case_safe(
        public_content,
        candidate_names=[row.get("name", "") for row in rows],
        company_names=[row.get("current_company", "") for row in rows],
    )
    assert_private_case_safe(private_content)
    public_case.write_text(public_content, encoding="utf-8")
    private_case.write_text(private_content, encoding="utf-8")

    run_id = root.name
    _append_run_event(
        ledger=ledger,
        event_type="jd_profile_created",
        run_id=run_id,
        client_id=client_id,
        jd_family=jd_family,
        visibility="public",
        source_refs=[_source(role_path, repo, "role_profile_json", "role_profile")],
        payload={"summary": role_profile.get("summary")},
    )
    _append_run_event(
        ledger=ledger,
        event_type="scorecard_created",
        run_id=run_id,
        client_id=client_id,
        jd_family=jd_family,
        visibility="public",
        source_refs=[_source(scorecard_path, repo, "scorecard_json", "scorecard")],
        payload={"dimensions": scorecard.get("dimensions", [])},
    )
    for row_index, row in enumerate(rows):
        candidate_id = row.get("candidate_id") or ""
        source_ref = _outreach_source(
            outreach_path,
            repo,
            row_index=row_index,
            candidate_id=candidate_id,
            run_id=run_id,
        )
        _append_run_event(
            ledger=ledger,
            event_type="candidate_recommended",
            run_id=run_id,
            client_id=client_id,
            jd_family=jd_family,
            visibility="private",
            source_refs=[source_ref],
            payload={
                "candidate_id": candidate_id,
                "rank": row.get("rank"),
                "recommendation_reason": row.get("recommendation_reason"),
            },
        )
        _append_run_event(
            ledger=ledger,
            event_type="consultant_feedback_received",
            run_id=run_id,
            client_id=client_id,
            jd_family=jd_family,
            visibility="private",
            source_refs=[source_ref],
            payload={
                "candidate_id": candidate_id,
                "consultant_decision": (row.get("consultant_decision") or "").strip()
                or "待确认",
                "feedback_note": _sanitize_sensitive_text(row.get("feedback_note")),
            },
        )
    decisions = Counter((row.get("consultant_decision") or "").strip() or "待确认" for row in rows)
    _append_run_event(
        ledger=ledger,
        event_type="batch_feedback_summarized",
        run_id=run_id,
        client_id=client_id,
        jd_family=jd_family,
        visibility="public",
        source_refs=[_source(public_case, repo, "second_brain_case", "batch_feedback_summary")],
        payload={"decision_counts": dict(decisions)},
    )
    return {
        "public_case": public_case.name,
        "private_case": private_case.name,
        "ledger": str(ledger),
    }
