"""Core schemas and writers for Talent-Agent second-brain artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import uuid

SECOND_BRAIN_EVENT_SCHEMA = "second_brain_event_v1"

ALLOWED_VISIBILITY = {"public", "private"}


@dataclass(frozen=True)
class SourceRef:
    source_path: str
    source_type: str
    artifact_key: str
    line_start: int | None = None
    line_end: int | None = None
    record_id: str | None = None
    candidate_id: str | None = None
    run_id: str | None = None


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _event_id() -> str:
    return f"evt_{uuid.uuid4().hex}"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL record in {target} line {line_number}") from exc
            if not isinstance(obj, dict):
                raise ValueError(
                    f"JSONL record in {target} line {line_number} is not an object"
                )
            records.append(obj)
    return records


def validate_source_ref(source_ref: dict[str, Any]) -> None:
    for key in ("source_path", "source_type", "artifact_key"):
        if not isinstance(source_ref.get(key), str) or not source_ref[key].strip():
            raise ValueError(f"source_refs entry missing {key}")
    for key in ("line_start", "line_end"):
        value = source_ref.get(key)
        if value is not None and (not isinstance(value, int) or value <= 0):
            raise ValueError(f"source_refs entry has invalid {key}")


def validate_event(event: dict[str, Any]) -> None:
    required = [
        "event_id",
        "event_type",
        "created_at",
        "schema_version",
        "run_id",
        "client_id",
        "jd_family",
        "visibility",
        "source_refs",
        "payload",
    ]
    for key in required:
        if key not in event:
            raise ValueError(f"event missing {key}")
    if event["schema_version"] != SECOND_BRAIN_EVENT_SCHEMA:
        raise ValueError("unsupported second-brain event schema")
    if event["visibility"] not in ALLOWED_VISIBILITY:
        raise ValueError("visibility must be public or private")
    if not isinstance(event["source_refs"], list) or not event["source_refs"]:
        raise ValueError("event source_refs must be a non-empty list")
    for source_ref in event["source_refs"]:
        if not isinstance(source_ref, dict):
            raise ValueError("source_refs entries must be objects")
        validate_source_ref(source_ref)
    if not isinstance(event["payload"], dict):
        raise ValueError("event payload must be an object")


def build_event(
    *,
    event_type: str,
    run_id: str,
    client_id: str,
    jd_family: str,
    visibility: str,
    source_refs: list[SourceRef],
    payload: dict[str, Any],
    created_at: str | None = None,
) -> dict[str, Any]:
    event = {
        "event_id": _event_id(),
        "event_type": event_type,
        "created_at": created_at or _now_iso(),
        "schema_version": SECOND_BRAIN_EVENT_SCHEMA,
        "run_id": run_id,
        "client_id": client_id,
        "jd_family": jd_family,
        "visibility": visibility,
        "source_refs": [asdict(source_ref) for source_ref in source_refs],
        "payload": dict(payload),
    }
    validate_event(event)
    return event


def append_event(ledger_path: str | Path, event: dict[str, Any]) -> None:
    validate_event(event)
    target = Path(ledger_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.stat().st_size > 0:
        with target.open("rb+") as handle:
            handle.seek(target.stat().st_size - 1)
            if handle.read(1) != b"\n":
                handle.write(b"\n")
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True, allow_nan=False))
        handle.write("\n")
