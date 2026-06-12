from pathlib import Path
import json

import pytest

from scripts.second_brain_models import (
    SECOND_BRAIN_EVENT_SCHEMA,
    SourceRef,
    append_event,
    build_event,
    load_jsonl,
    validate_event,
    write_json,
)


def test_build_event_requires_source_refs_and_payload(tmp_path: Path) -> None:
    event = build_event(
        event_type="consultant_feedback_received",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="private",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/feedback/outreach-feedback.csv",
                source_type="feedback_csv",
                artifact_key="candidate_id=cand-001",
            )
        ],
        payload={"candidate_id": "cand-001", "consultant_decision": "认可"},
    )

    validate_event(event)

    assert event["schema_version"] == SECOND_BRAIN_EVENT_SCHEMA
    assert event["event_id"].startswith("evt_")
    assert event["source_refs"][0]["source_type"] == "feedback_csv"


def test_validate_event_rejects_missing_source_refs() -> None:
    event = build_event(
        event_type="scorecard_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/scorecard.json",
                source_type="scorecard_json",
                artifact_key="scorecard",
            )
        ],
        payload={"scorecard_version": "v1"},
    )
    event["source_refs"] = []

    with pytest.raises(ValueError, match="source_refs"):
        validate_event(event)


def test_append_event_writes_standard_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "data" / "second-brain" / "events.jsonl"
    event = build_event(
        event_type="jd_profile_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/role-profile.json",
                source_type="role_profile_json",
                artifact_key="role_profile",
            )
        ],
        payload={"summary": "多模态算法岗位画像"},
    )

    append_event(ledger, event)

    records = load_jsonl(ledger)
    assert records == [event]


def test_append_event_preserves_jsonl_when_existing_file_has_no_trailing_newline(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "data" / "second-brain" / "events.jsonl"
    existing_event = build_event(
        event_type="jd_profile_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/role-profile.json",
                source_type="role_profile_json",
                artifact_key="role_profile",
            )
        ],
        payload={"summary": "多模态算法岗位画像"},
    )
    new_event = build_event(
        event_type="scorecard_created",
        run_id="run-001",
        client_id="client_tencent_games",
        jd_family="multi_modal_algorithm",
        visibility="public",
        source_refs=[
            SourceRef(
                source_path="data/output/run-001/scorecard.json",
                source_type="scorecard_json",
                artifact_key="scorecard",
            )
        ],
        payload={"scorecard_version": "v1"},
    )
    ledger.parent.mkdir(parents=True)
    ledger.write_text(
        json.dumps(existing_event, ensure_ascii=False, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )

    append_event(ledger, new_event)

    records = load_jsonl(ledger)
    assert records == [existing_event, new_event]


def test_write_json_rejects_non_standard_numbers(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        write_json(tmp_path / "bad.json", {"score": float("nan")})
