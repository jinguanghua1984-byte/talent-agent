from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from tempfile import TemporaryDirectory
from pathlib import Path
from typing import Any

from scripts.jd_delivery_feedback import (
    VALID_FEEDBACK_LABELS,
    VALID_FEEDBACK_STAGES,
    VALID_GRADES,
    VALID_REASON_CODES,
    build_suggestions,
    compile_feedback_summary,
    load_feedback,
    write_json,
)
from scripts.llm_client import StructuredOutputSchema
from scripts.pipeline_utils import call_llm_with_retry, create_llm_client
from scripts.llm_usage import (
    LLMUsageLedger,
    LLMRoute,
    hash_artifact,
    hash_prompt,
    resolve_llm_route,
    usage_record_from_response,
    utc_now_iso,
)


LOW_CONFIDENCE_THRESHOLD = 0.7
FEEDBACK_SCHEMA = "jd_delivery_feedback_v1"
REVIEW_QUEUE_SCHEMA = "jd_delivery_feedback_parse_review_queue_v1"
REQUIRED_CSV_COLUMNS = {"candidate_id", "rank", "score", "grade", "feedback_note"}
BATCH_PARSE_SIZE = 50


def feedback_note_structured_schema() -> StructuredOutputSchema:
    return StructuredOutputSchema(
        name="jd_feedback_note_parse",
        schema={
            "type": "object",
            "properties": {
                "feedback_label": {"type": "string", "enum": sorted(VALID_FEEDBACK_LABELS)},
                "feedback_stage": {"type": "string", "enum": sorted(VALID_FEEDBACK_STAGES)},
                "reason_codes": {
                    "type": "array",
                    "items": {"type": "string", "enum": sorted(VALID_REASON_CODES)},
                },
                "hunter_note": {"type": "string"},
                "parse_confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "feedback_label",
                "feedback_stage",
                "reason_codes",
                "hunter_note",
                "parse_confidence",
            ],
            "additionalProperties": False,
        },
    )


def feedback_note_batch_structured_schema() -> StructuredOutputSchema:
    item_schema = dict(feedback_note_structured_schema().schema)
    item_schema["properties"] = {
        "index": {"type": "integer", "minimum": 0},
        **item_schema["properties"],
    }
    item_schema["required"] = ["index", *item_schema["required"]]
    return StructuredOutputSchema(
        name="jd_feedback_note_batch_parse",
        schema={
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "items": item_schema,
                }
            },
            "required": ["items"],
            "additionalProperties": False,
        },
    )


def build_feedback_prompt(feedback_note: str) -> str:
    labels = "、".join(sorted(VALID_FEEDBACK_LABELS))
    stages = "、".join(sorted(VALID_FEEDBACK_STAGES))
    reason_codes = "\n".join(f"- {code}" for code in sorted(VALID_REASON_CODES))
    return f"""你是 JD 推荐反馈解析助手。请把业务人员填写的自然语言反馈解析成严格 JSON。

字段含义：
- feedback_label：总体判断，只能是 {labels}。
- feedback_stage：问题或判断所属阶段，只能是 {stages}。
- reason_codes：原因码数组，只能从下列代码中选择；没有明确原因时返回空数组。
{reason_codes}
- hunter_note：保留给人工复盘的一句中文说明，应忠实概括原反馈。
- parse_confidence：0 到 1 的数字，表示你对解析结果的置信度。

只返回 JSON 对象，不要返回 Markdown 或解释文字。JSON 形状：
{{
  "feedback_label": "认可|待定|不认可",
  "feedback_stage": "画像|评分卡|匹配|报告|候选人状态",
  "reason_codes": ["reason_code"],
  "hunter_note": "中文备注",
  "parse_confidence": 0.0
}}

原始反馈：
{feedback_note}
"""


def build_feedback_batch_prompt(feedback_notes: list[str]) -> str:
    labels = "、".join(sorted(VALID_FEEDBACK_LABELS))
    stages = "、".join(sorted(VALID_FEEDBACK_STAGES))
    reason_codes = "\n".join(f"- {code}" for code in sorted(VALID_REASON_CODES))
    notes_json = json.dumps(
        [{"index": index, "feedback_note": note} for index, note in enumerate(feedback_notes)],
        ensure_ascii=False,
        indent=2,
    )
    return f"""你是 JD 推荐反馈批量解析助手。请把业务人员填写的多条自然语言反馈解析成严格 JSON。

字段含义：
- index：必须原样返回输入中的 index。
- feedback_label：总体判断，只能是 {labels}。
- feedback_stage：问题或判断所属阶段，只能是 {stages}。
- reason_codes：原因码数组，只能从下列代码中选择；没有明确原因时返回空数组。
{reason_codes}
- hunter_note：保留给人工复盘的一句中文说明，应忠实概括原反馈。
- parse_confidence：0 到 1 的数字，表示你对解析结果的置信度。

只返回 JSON 对象，不要返回 Markdown 或解释文字。JSON 形状：
{{
  "items": [
    {{
      "index": 0,
      "feedback_label": "认可|待定|不认可",
      "feedback_stage": "画像|评分卡|匹配|报告|候选人状态",
      "reason_codes": ["reason_code"],
      "hunter_note": "中文备注",
      "parse_confidence": 0.0
    }}
  ]
}}

原始反馈列表：
{notes_json}
"""


def extract_json_object(text: str) -> dict[str, Any]:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fenced:
        return _loads_object(fenced.group(1))

    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return _loads_object(stripped)

    start = text.find("{")
    while start != -1:
        candidate = _balanced_json_slice(text, start)
        if candidate is not None:
            return _loads_object(candidate)
        start = text.find("{", start + 1)
    raise ValueError("LLM response did not contain a JSON object")


def parse_feedback_note(
    feedback_note: str,
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    rule_result = parse_feedback_note_by_rule(feedback_note)
    if rule_result is not None:
        return rule_result

    return _parse_feedback_note_with_llm(
        feedback_note,
        client=client,
        provider=provider,
        model=model,
    )


def parse_feedback_note_by_rule(feedback_note: str) -> dict[str, Any] | None:
    note = feedback_note.strip()
    if not note:
        return None

    if _contains_any(note, ["年限不符", "年限不匹配", "经验年限不符", "经验不符"]):
        return _rule_result(
            note,
            feedback_label="不认可",
            feedback_stage="匹配",
            reason_codes=["seniority_mismatch"],
        )
    if _contains_any(note, ["方向不符", "方向不匹配", "角色不符", "岗位不符"]):
        return _rule_result(
            note,
            feedback_label="不认可",
            feedback_stage="匹配",
            reason_codes=["wrong_role_type"],
        )
    if "不合适" in note and not _contains_any(note, ["可能", "不确定", "需要确认"]):
        return _rule_result(
            note,
            feedback_label="不认可",
            feedback_stage="匹配",
            reason_codes=[],
        )
    if _contains_any(note, ["已联系", "已沟通", "已经联系", "已经沟通"]):
        return _rule_result(
            note,
            feedback_label="待定",
            feedback_stage="候选人状态",
            reason_codes=[],
            parse_confidence=0.9,
        )
    if _contains_any(note, ["暂缓", "先放一放", "暂不推进"]):
        return _rule_result(
            note,
            feedback_label="待定",
            feedback_stage="候选人状态",
            reason_codes=[],
            parse_confidence=0.9,
        )
    if (
        _contains_any(note, ["认可", "可以推进", "建议推进", "优先联系", "建议优先联系"])
        and not _contains_any(note, ["不认可", "不合适", "暂缓", "需要确认"])
    ):
        return _rule_result(
            note,
            feedback_label="认可",
            feedback_stage="匹配",
            reason_codes=[],
        )
    return None


def parse_feedback_notes_batch(
    feedback_notes: list[str],
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> list[dict[str, Any]]:
    if not feedback_notes:
        return []

    route = resolve_llm_route("jd-feedback", "parse-low-confidence-batch")
    resolved_provider = provider or route.provider
    resolved_model = model or _client_model(client) or route.model
    resolved_client = client or create_llm_client(provider=resolved_provider, model=resolved_model)
    results: list[dict[str, Any]] = []
    for start in range(0, len(feedback_notes), BATCH_PARSE_SIZE):
        batch = feedback_notes[start : start + BATCH_PARSE_SIZE]
        results.extend(
            _parse_feedback_notes_batch_chunk(
                batch,
                resolved_client=resolved_client,
                resolved_model=resolved_model,
                route=route,
            )
        )
    return results


def parse_feedback_csv(
    run_root: str | Path,
    *,
    csv_path: str | Path | None = None,
    out_path: str | Path | None = None,
    review_out_path: str | Path | None = None,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(run_root)
    paths = _output_paths(root, csv_path, out_path, review_out_path)
    metadata = _load_run_metadata(root)

    rows_to_parse = _load_feedback_rows(paths["csv"])

    parsed_results = _parse_rows_rule_first_then_batch(
        rows_to_parse,
        client=client,
        provider=provider,
        model=model,
    )

    return _write_feedback_results(
        root,
        paths=paths,
        metadata=metadata,
        rows_to_parse=rows_to_parse,
        parsed_results=parsed_results,
        dry_run=dry_run,
    )


def _write_feedback_results(
    root: Path,
    *,
    paths: dict[str, Path],
    metadata: dict[str, str],
    rows_to_parse: list[dict[str, str | None]],
    parsed_results: list[dict[str, Any]],
    dry_run: bool,
) -> dict[str, Any]:
    candidate_feedback: list[dict[str, Any]] = []
    review_items: list[dict[str, Any]] = []

    for row, parsed in zip(rows_to_parse, parsed_results, strict=True):
        item = _candidate_item(row, parsed)
        if parsed["review_required"]:
            review_items.append(
                {
                    **item,
                    "review_status": "pending",
                    "review_reasons": parsed["review_reasons"],
                }
            )
        else:
            candidate_feedback.append(item)

    delivery_feedback = {
        "schema": FEEDBACK_SCHEMA,
        **metadata,
        "source_report": "reports/talent-recommendation.json",
        "source_outreach_sheet": str(paths["csv"]),
        "reviewer_role": "senior_hunter",
        "candidate_feedback": candidate_feedback,
    }
    validated_feedback = _validate_feedback_payload(delivery_feedback)
    review_queue = {
        "schema": REVIEW_QUEUE_SCHEMA,
        **metadata,
        "source_outreach_sheet": str(paths["csv"]),
        "items": review_items,
    }
    result = {
        "run_root": str(root),
        "csv_path": str(paths["csv"]),
        "out_path": str(paths["delivery"]),
        "review_out_path": str(paths["review"]),
        "parsed_count": len(rows_to_parse),
        "accepted_count": len(candidate_feedback),
        "review_count": len(review_items),
        "dry_run": dry_run,
    }

    if dry_run:
        return result

    write_json(paths["delivery"], validated_feedback)
    write_json(paths["review"], review_queue)
    summary = compile_feedback_summary(validated_feedback)
    write_json(paths["summary"], summary)
    write_json(paths["suggestions"], build_suggestions(summary))
    return result


def prepare_feedback_batch_job(
    run_root: str | Path,
    *,
    csv_path: str | Path | None = None,
    job_id: str | None = None,
    job_dir: str | Path | None = None,
    provider: str | None = None,
    model: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(run_root)
    paths = _output_paths(root, csv_path, None, None)
    rows_to_parse = _load_feedback_rows(paths["csv"])
    route = resolve_llm_route("jd-feedback", "parse-low-confidence-batch")
    resolved_provider = provider or route.provider
    resolved_model = model or route.model
    batch_job_id = job_id or _default_batch_job_id()
    output_dir = Path(job_dir) if job_dir is not None else root / "feedback" / "batch-jobs" / batch_job_id
    request_jsonl = output_dir / "requests.jsonl"
    rule_results_path = output_dir / "rule-results.json"
    manifest_path = output_dir / "batch-job-manifest.json"
    expected_output_jsonl = output_dir / "provider-output.jsonl"

    rule_results: list[dict[str, Any]] = []
    unresolved_rows: list[dict[str, str | None]] = []
    for row in rows_to_parse:
        note = (row.get("feedback_note") or "").strip()
        parsed = parse_feedback_note_by_rule(note)
        if parsed is None:
            unresolved_rows.append(row)
        else:
            rule_results.append({"row": row, "parsed": parsed})

    request_rows: list[dict[str, Any]] = []
    request_summaries: list[dict[str, Any]] = []
    for chunk_index, chunk in enumerate(_chunks(unresolved_rows, BATCH_PARSE_SIZE), start=1):
        feedback_notes = [(row.get("feedback_note") or "").strip() for row in chunk]
        messages = [{"role": "user", "content": build_feedback_batch_prompt(feedback_notes)}]
        prompt_hash = hash_prompt(messages)
        custom_id = f"jd-feedback:{batch_job_id}:chunk-{chunk_index:06d}"
        items = [
            {
                "index": index,
                "candidate_id": _required_text(row, "candidate_id"),
                "rank": _required_int(row, "rank"),
                "grade": _required_text(row, "grade"),
                "score": _required_text(row, "score"),
                "feedback_note": (row.get("feedback_note") or "").strip(),
            }
            for index, row in enumerate(chunk)
        ]
        request_rows.append(
            {
                "schema": "llm_batch_request_v1",
                "custom_id": custom_id,
                "provider": resolved_provider,
                "workflow": route.workflow,
                "stage": route.stage,
                "request": {
                    "model": resolved_model,
                    "max_tokens": route.max_tokens,
                    "messages": messages,
                },
                "metadata": {
                    "schema": "jd_feedback_batch_request_metadata_v1",
                    "batch_job_id": batch_job_id,
                    "chunk_index": chunk_index,
                    "prompt_hash": prompt_hash,
                    "items": items,
                },
            }
        )
        request_summaries.append(
            {
                "custom_id": custom_id,
                "prompt_hash": prompt_hash,
                "item_count": len(items),
            }
        )

    source_csv_hash = hash_artifact(paths["csv"])
    manifest = {
        "schema": "jd_feedback_batch_job_v1",
        "batch_job_id": batch_job_id,
        "created_at": utc_now_iso(),
        "provider": resolved_provider,
        "model": resolved_model,
        "tool_surface": route.tool_surface,
        "agent_runtime": route.agent_runtime,
        "workflow": route.workflow,
        "stage": route.stage,
        "max_tokens": route.max_tokens,
        "batch_parse_size": BATCH_PARSE_SIZE,
        "source_outreach_sheet": str(paths["csv"]),
        "source_csv_hash": source_csv_hash,
        "request_count": len(request_rows),
        "unresolved_count": len(unresolved_rows),
        "rule_parsed_count": len(rule_results),
        "request_jsonl": str(request_jsonl),
        "rule_results_path": str(rule_results_path),
        "expected_output_jsonl": str(expected_output_jsonl),
        "delivery_output": str(paths["delivery"]),
        "review_output": str(paths["review"]),
        "summary_output": str(paths["summary"]),
        "suggestions_output": str(paths["suggestions"]),
        "requests": request_summaries,
    }
    result = {
        "run_root": str(root),
        "job_dir": str(output_dir),
        "manifest_path": str(manifest_path),
        "request_jsonl": str(request_jsonl),
        "rule_results_path": str(rule_results_path),
        "expected_output_jsonl": str(expected_output_jsonl),
        "batch_job_id": batch_job_id,
        "request_count": len(request_rows),
        "unresolved_count": len(unresolved_rows),
        "rule_parsed_count": len(rule_results),
        "dry_run": dry_run,
    }
    if dry_run:
        return result

    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(manifest_path, manifest)
    write_json(
        rule_results_path,
        {
            "schema": "jd_feedback_batch_rule_results_v1",
            "batch_job_id": batch_job_id,
            "items": rule_results,
        },
    )
    with request_jsonl.open("w", encoding="utf-8") as handle:
        for row in request_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    return result


def apply_feedback_batch_job(
    run_root: str | Path,
    *,
    job_dir: str | Path,
    output_jsonl: str | Path | None = None,
    ledger: Any | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    root = Path(run_root)
    output_dir = Path(job_dir)
    manifest_path = output_dir / "batch-job-manifest.json"
    manifest = _read_json_object(manifest_path)
    provider_output = Path(output_jsonl) if output_jsonl is not None else Path(str(manifest["expected_output_jsonl"]))
    paths = _output_paths(
        root,
        manifest.get("source_outreach_sheet"),
        manifest.get("delivery_output"),
        manifest.get("review_output"),
    )
    metadata = _load_run_metadata(root)
    rows_to_parse = _load_feedback_rows(paths["csv"])
    parsed_by_candidate_id = _load_batch_rule_results(Path(str(manifest["rule_results_path"])))

    output_by_custom_id = {
        row.get("custom_id"): row
        for row in _read_jsonl(provider_output)
        if isinstance(row.get("custom_id"), str)
    }
    usage_record_count = 0
    output_artifact_hash = hash_artifact(provider_output)
    route = resolve_llm_route(str(manifest["workflow"]), str(manifest["stage"]))

    for request_row in _read_jsonl(Path(str(manifest["request_jsonl"]))):
        custom_id = str(request_row["custom_id"])
        output_row = output_by_custom_id.get(custom_id)
        if output_row is None:
            raise ValueError(f"batch output missing custom_id: {custom_id}")

        response_text = _extract_batch_output_text(output_row)
        parsed_payload = extract_json_object(response_text)
        raw_items = parsed_payload.get("items")
        if not isinstance(raw_items, list):
            raise ValueError(f"batch output {custom_id} must contain items list")
        parsed_items = {
            item.get("index"): item
            for item in raw_items
            if isinstance(item, dict) and isinstance(item.get("index"), int)
        }
        for item in request_row["metadata"]["items"]:
            index = int(item["index"])
            candidate_id = str(item["candidate_id"])
            note = str(item["feedback_note"])
            parsed = parsed_items.get(index)
            if parsed is None:
                parsed_by_candidate_id[candidate_id] = _fallback_result(
                    note,
                    parse_source="llm_batch_job",
                )
            else:
                parsed_by_candidate_id[candidate_id] = _normalize_result(
                    parsed,
                    note,
                    parse_source="llm_batch_job",
                )

        if ledger is not None:
            record = usage_record_from_response(
                provider=str(manifest["provider"]),
                tool_surface=str(manifest.get("tool_surface") or route.tool_surface),
                agent_runtime=str(manifest.get("agent_runtime") or route.agent_runtime),
                workflow=str(manifest["workflow"]),
                stage=str(manifest["stage"]),
                model=str(manifest["model"]),
                max_tokens=int(manifest["max_tokens"]),
                messages=request_row["request"]["messages"],
                usage=_extract_batch_output_usage(output_row),
                request_id=_extract_batch_output_request_id(output_row),
                stop_reason=_extract_batch_output_stop_reason(output_row),
                artifact_root=str(output_dir),
                input_artifact_hash=str(manifest.get("source_csv_hash") or ""),
                batch_discount_applied=True,
                batch_job_id=str(manifest["batch_job_id"]),
                batch_custom_id=custom_id,
                batch_output_artifact=str(provider_output),
                output_artifact_hash=output_artifact_hash,
            )
            ledger.append(record)
            usage_record_count += 1

    parsed_results: list[dict[str, Any]] = []
    for row in rows_to_parse:
        candidate_id = _required_text(row, "candidate_id")
        parsed = parsed_by_candidate_id.get(candidate_id)
        if parsed is None:
            raise ValueError(f"missing parsed feedback for candidate_id: {candidate_id}")
        parsed_results.append(parsed)

    result = _write_feedback_results(
        root,
        paths=paths,
        metadata=metadata,
        rows_to_parse=rows_to_parse,
        parsed_results=parsed_results,
        dry_run=dry_run,
    )
    result.update(
        {
            "batch_job_id": str(manifest["batch_job_id"]),
            "job_dir": str(output_dir),
            "output_jsonl": str(provider_output),
            "usage_record_count": usage_record_count,
        }
    )
    return result


def main(argv: list[str] | None = None, *, client: Any | None = None) -> int:
    parser = argparse.ArgumentParser(description="Parse JD delivery feedback notes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_parser = subparsers.add_parser("parse")
    parse_parser.add_argument("--note", required=True)
    parse_parser.add_argument("--out", required=True)
    parse_parser.add_argument("--provider")
    parse_parser.add_argument("--model")

    csv_parser = subparsers.add_parser("parse-csv")
    csv_parser.add_argument("--run-root", required=True)
    csv_parser.add_argument("--csv")
    csv_parser.add_argument("--out")
    csv_parser.add_argument("--review-out")
    csv_parser.add_argument("--provider")
    csv_parser.add_argument("--model")
    csv_parser.add_argument("--dry-run", action="store_true")

    prepare_parser = subparsers.add_parser("prepare-batch")
    prepare_parser.add_argument("--run-root", required=True)
    prepare_parser.add_argument("--csv")
    prepare_parser.add_argument("--job-id")
    prepare_parser.add_argument("--job-dir")
    prepare_parser.add_argument("--provider")
    prepare_parser.add_argument("--model")
    prepare_parser.add_argument("--dry-run", action="store_true")

    apply_parser = subparsers.add_parser("apply-batch")
    apply_parser.add_argument("--run-root", required=True)
    apply_parser.add_argument("--job-dir", required=True)
    apply_parser.add_argument("--output-jsonl")
    apply_parser.add_argument("--ledger-dir")
    apply_parser.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    try:
        if args.command == "parse":
            result = parse_feedback_note(
                args.note,
                client=client,
                provider=args.provider,
                model=args.model,
            )
            write_json(args.out, result)
            return 0
        if args.command == "parse-csv":
            result = parse_feedback_csv(
                args.run_root,
                csv_path=args.csv,
                out_path=args.out,
                review_out_path=args.review_out,
                client=client,
                provider=args.provider,
                model=args.model,
                dry_run=args.dry_run,
            )
            if args.dry_run:
                print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "prepare-batch":
            result = prepare_feedback_batch_job(
                args.run_root,
                csv_path=args.csv,
                job_id=args.job_id,
                job_dir=args.job_dir,
                provider=args.provider,
                model=args.model,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.command == "apply-batch":
            ledger = LLMUsageLedger(args.ledger_dir) if args.ledger_dir else None
            result = apply_feedback_batch_job(
                args.run_root,
                job_dir=args.job_dir,
                output_jsonl=args.output_jsonl,
                ledger=ledger,
                dry_run=args.dry_run,
            )
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1


def _loads_object(text: str) -> dict[str, Any]:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("LLM JSON response must be an object")
    return data


def _parse_feedback_note_with_llm(
    feedback_note: str,
    *,
    client: Any | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    route = resolve_llm_route("jd-feedback", "parse-single-note")
    resolved_provider = provider or route.provider
    resolved_model = model or _client_model(client) or route.model
    resolved_client = client or create_llm_client(provider=resolved_provider, model=resolved_model)
    messages = [{"role": "user", "content": build_feedback_prompt(feedback_note)}]

    structured = _try_complete_structured(
        resolved_client,
        messages,
        model=resolved_model,
        max_tokens=route.max_tokens,
        schema=feedback_note_structured_schema(),
        workflow=route.workflow,
        stage=route.stage,
        batch_discount_applied=False,
    )
    if structured is not None:
        return _normalize_result(
            structured,
            feedback_note,
            parse_source="llm_structured",
        )

    try:
        response = call_llm_with_retry(
            resolved_client,
            resolved_model,
            messages,
            max_tokens=route.max_tokens,
            workflow=route.workflow,
            stage=route.stage,
            batch_discount_applied=False,
        )
        parsed = extract_json_object(response)
    except Exception:
        return _fallback_result(feedback_note)

    return _normalize_result(parsed, feedback_note)


def _parse_feedback_notes_batch_chunk(
    feedback_notes: list[str],
    *,
    resolved_client: Any,
    resolved_model: str,
    route: LLMRoute,
) -> list[dict[str, Any]]:
    messages = [{"role": "user", "content": build_feedback_batch_prompt(feedback_notes)}]
    structured = _try_complete_structured(
        resolved_client,
        messages,
        model=resolved_model,
        max_tokens=route.max_tokens,
        schema=feedback_note_batch_structured_schema(),
        workflow=route.workflow,
        stage=route.stage,
        batch_discount_applied=False,
    )
    if structured is not None:
        items = structured.get("items")
        if not isinstance(items, list):
            return [_fallback_result(note, parse_source="llm_batch_structured") for note in feedback_notes]
        by_index = {
            item.get("index"): item
            for item in items
            if isinstance(item, dict) and isinstance(item.get("index"), int)
        }
        return [
            _normalize_result(
                by_index[index],
                note,
                parse_source="llm_batch_structured",
            )
            if index in by_index
            else _fallback_result(note, parse_source="llm_batch_structured")
            for index, note in enumerate(feedback_notes)
        ]

    try:
        response = call_llm_with_retry(
            resolved_client,
            resolved_model,
            messages,
            max_tokens=route.max_tokens,
            workflow=route.workflow,
            stage=route.stage,
            batch_discount_applied=False,
        )
        parsed = extract_json_object(response)
        items = parsed.get("items")
        if not isinstance(items, list):
            if feedback_notes:
                first = _normalize_result(parsed, feedback_notes[0])
                return [
                    first,
                    *[
                        _parse_feedback_note_with_llm(
                            note,
                            client=resolved_client,
                            model=resolved_model,
                        )
                        for note in feedback_notes[1:]
                    ],
                ]
            return []
    except Exception:
        return [_fallback_result(note, parse_source="llm_batch") for note in feedback_notes]

    by_index = {
        item.get("index"): item
        for item in items
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }
    return [
        _normalize_result(
            by_index[index],
            note,
            parse_source="llm_batch",
        )
        if index in by_index
        else _fallback_result(note, parse_source="llm_batch")
        for index, note in enumerate(feedback_notes)
    ]


def _parse_rows_rule_first_then_batch(
    rows: list[dict[str, str | None]],
    *,
    client: Any | None,
    provider: str | None,
    model: str | None,
) -> list[dict[str, Any]]:
    parsed_results: list[dict[str, Any] | None] = []
    unresolved_notes: list[str] = []
    unresolved_indexes: list[int] = []
    for index, row in enumerate(rows):
        note = (row.get("feedback_note") or "").strip()
        rule_result = parse_feedback_note_by_rule(note)
        parsed_results.append(rule_result)
        if rule_result is None:
            unresolved_indexes.append(index)
            unresolved_notes.append(note)

    if unresolved_notes:
        batch_results = parse_feedback_notes_batch(
            unresolved_notes,
            client=client,
            provider=provider,
            model=model,
        )
        for index, parsed in zip(unresolved_indexes, batch_results, strict=True):
            parsed_results[index] = parsed

    return [parsed for parsed in parsed_results if parsed is not None]


def _try_complete_structured(
    client: Any,
    messages: list[dict[str, Any]],
    *,
    model: str,
    max_tokens: int,
    schema: StructuredOutputSchema,
    workflow: str,
    stage: str,
    batch_discount_applied: bool,
) -> dict[str, Any] | None:
    complete_structured = getattr(client, "complete_structured", None)
    if complete_structured is None:
        return None
    try:
        result = complete_structured(
            messages,
            model=model,
            max_tokens=max_tokens,
            schema=schema,
            workflow=workflow,
            stage=stage,
            batch_discount_applied=batch_discount_applied,
        )
    except Exception:
        return None
    return result if isinstance(result, dict) else None


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle in text for needle in needles)


def _rule_result(
    feedback_note: str,
    *,
    feedback_label: str,
    feedback_stage: str,
    reason_codes: list[str],
    parse_confidence: float = 0.95,
) -> dict[str, Any]:
    return {
        "feedback_label": feedback_label,
        "feedback_stage": feedback_stage,
        "reason_codes": reason_codes,
        "hunter_note": feedback_note,
        "feedback_note": feedback_note,
        "parse_source": "rule",
        "parse_confidence": parse_confidence,
        "review_required": False,
        "review_reasons": [],
    }


def _validate_csv_columns(fieldnames: list[str] | None) -> None:
    missing = sorted(REQUIRED_CSV_COLUMNS - set(fieldnames or []))
    if missing:
        raise ValueError(
            "outreach CSV missing required columns: " + ", ".join(missing)
        )


def _load_feedback_rows(csv_path: Path) -> list[dict[str, str | None]]:
    seen_candidate_ids: set[str] = set()
    seen_ranks: set[int] = set()
    rows: list[dict[str, str | None]] = []

    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_csv_columns(reader.fieldnames)
        for row in reader:
            note = (row.get("feedback_note") or "").strip()
            if not note:
                continue
            _validate_unique_feedback_row(row, seen_candidate_ids, seen_ranks)
            rows.append(row)
    return rows


def _validate_feedback_payload(feedback: dict[str, Any]) -> dict[str, Any]:
    with TemporaryDirectory() as tmp_dir:
        path = Path(tmp_dir) / "delivery-feedback.json"
        write_json(path, feedback)
        return load_feedback(path)


def _output_paths(
    run_root: Path,
    csv_path: str | Path | None,
    out_path: str | Path | None,
    review_out_path: str | Path | None,
) -> dict[str, Path]:
    feedback_dir = run_root / "feedback"
    return {
        "csv": Path(csv_path) if csv_path is not None else run_root / "reports" / "outreach-queue.csv",
        "delivery": Path(out_path) if out_path is not None else feedback_dir / "delivery-feedback.json",
        "review": Path(review_out_path)
        if review_out_path is not None
        else feedback_dir / "parse-review-queue.json",
        "summary": feedback_dir / "feedback-summary.json",
        "suggestions": feedback_dir / "calibration-suggestions.json",
    }


def _load_run_metadata(run_root: Path) -> dict[str, str]:
    manifest = _read_optional_json(run_root / "run-manifest.json")
    profile = _read_optional_json(run_root / "profile" / "role-profile.json")
    scorecard = _read_optional_json(run_root / "scoring" / "scorecard.json")
    return {
        "role_id": str(profile.get("role_id") or ""),
        "run_id": str(manifest.get("output_dir") or run_root),
        "profile_version": str(profile.get("version") or profile.get("schema") or ""),
        "scorecard_version": str(scorecard.get("version") or scorecard.get("schema") or ""),
    }


def _read_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        data = json.loads(line)
        if not isinstance(data, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(data)
    return rows


def _load_batch_rule_results(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json_object(path)
    parsed_by_candidate_id: dict[str, dict[str, Any]] = {}
    for item in payload.get("items") or []:
        if not isinstance(item, dict):
            continue
        row = item.get("row")
        parsed = item.get("parsed")
        if isinstance(row, dict) and isinstance(parsed, dict):
            parsed_by_candidate_id[_required_text(row, "candidate_id")] = parsed
    return parsed_by_candidate_id


def _extract_batch_output_text(row: dict[str, Any]) -> str:
    text = row.get("text")
    if isinstance(text, str):
        return text
    body = _extract_batch_output_body(row)
    body_text = body.get("text")
    if isinstance(body_text, str):
        return body_text
    content = body.get("content")
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                return str(block["text"])
    message = body.get("message")
    if isinstance(message, dict):
        message_content = message.get("content")
        if isinstance(message_content, str):
            return message_content
        if isinstance(message_content, list):
            for block in message_content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    return str(block["text"])
    raise ValueError("batch output row did not contain response text")


def _extract_batch_output_usage(row: dict[str, Any]) -> Any | None:
    if "usage" in row:
        return row.get("usage")
    return _extract_batch_output_body(row).get("usage")


def _extract_batch_output_request_id(row: dict[str, Any]) -> str | None:
    for source in (row, _extract_batch_output_body(row)):
        value = source.get("request_id") or source.get("id")
        if isinstance(value, str) and value:
            return value
    return None


def _extract_batch_output_stop_reason(row: dict[str, Any]) -> str | None:
    for source in (row, _extract_batch_output_body(row)):
        value = source.get("stop_reason") or source.get("finish_reason")
        if isinstance(value, str) and value:
            return value
    return None


def _extract_batch_output_body(row: dict[str, Any]) -> dict[str, Any]:
    response = row.get("response")
    if isinstance(response, dict):
        body = response.get("body")
        if isinstance(body, dict):
            return body
        return response
    return row


def _chunks(rows: list[dict[str, str | None]], size: int) -> list[list[dict[str, str | None]]]:
    return [rows[start : start + size] for start in range(0, len(rows), size)]


def _default_batch_job_id() -> str:
    digits = re.sub(r"\D", "", utc_now_iso())
    return f"jd-feedback-batch-{digits[:14]}"


def _candidate_item(row: dict[str, str | None], parsed: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": _required_text(row, "candidate_id"),
        "rank": _required_int(row, "rank"),
        "original_grade": _required_text(row, "grade"),
        "original_score": _required_number(row, "score"),
        "feedback_label": parsed["feedback_label"],
        "feedback_stage": parsed["feedback_stage"],
        "reason_codes": parsed["reason_codes"],
        "hunter_note": parsed["hunter_note"],
        "feedback_note": parsed["feedback_note"],
        "parse_source": parsed["parse_source"],
        "parse_confidence": parsed["parse_confidence"],
    }


def _validate_unique_feedback_row(
    row: dict[str, str | None],
    seen_candidate_ids: set[str],
    seen_ranks: set[int],
) -> None:
    candidate_id = (row.get("candidate_id") or "").strip()
    if not candidate_id:
        raise ValueError("candidate_id is required")
    if candidate_id in seen_candidate_ids:
        raise ValueError(f"duplicate candidate_id: {candidate_id}")
    rank = _required_int(row, "rank")
    if rank in seen_ranks:
        raise ValueError(f"duplicate rank: {rank}")
    grade = _required_text(row, "grade")
    if grade not in VALID_GRADES:
        raise ValueError(f"invalid original grade: {grade}")
    _required_number(row, "score")
    seen_candidate_ids.add(candidate_id)
    seen_ranks.add(rank)


def _required_text(row: dict[str, str | None], field: str) -> str:
    value = row.get(field)
    if value is None or not value.strip():
        raise ValueError(f"outreach CSV missing required {field}")
    return value.strip()


def _required_int(row: dict[str, str | None], field: str) -> int:
    return _parse_int(_required_text(row, field), field)


def _parse_int(value: str, field: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise ValueError(f"outreach CSV {field} must be an integer") from exc
    if number <= 0:
        raise ValueError(f"outreach CSV {field} must be a positive integer")
    return number


def _required_number(row: dict[str, str | None], field: str) -> int | float:
    value = _required_text(row, field)
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"outreach CSV {field} must be a number") from exc
    if not math.isfinite(number):
        raise ValueError(f"outreach CSV {field} must be a finite number")
    return int(number) if number.is_integer() else number


def _balanced_json_slice(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _client_model(client: Any) -> str | None:
    settings = getattr(client, "settings", None)
    model = getattr(settings, "model", None)
    return model if isinstance(model, str) and model else None


def _fallback_result(feedback_note: str, *, parse_source: str = "llm") -> dict[str, Any]:
    return {
        "feedback_label": "待定",
        "feedback_stage": "匹配",
        "reason_codes": [],
        "hunter_note": feedback_note,
        "feedback_note": feedback_note,
        "parse_source": parse_source,
        "parse_confidence": 0.0,
        "review_required": True,
        "review_reasons": ["llm_error"],
    }


def _normalize_result(
    parsed: dict[str, Any],
    feedback_note: str,
    *,
    parse_source: str = "llm",
) -> dict[str, Any]:
    review_reasons: list[str] = []

    label = parsed.get("feedback_label")
    if label not in VALID_FEEDBACK_LABELS:
        label = "待定"
        review_reasons.append("invalid_feedback_label")

    stage = parsed.get("feedback_stage")
    if stage not in VALID_FEEDBACK_STAGES:
        stage = "匹配"
        review_reasons.append("invalid_feedback_stage")

    raw_reason_codes = parsed.get("reason_codes")
    if not isinstance(raw_reason_codes, list):
        reason_codes: list[str] = []
        review_reasons.append("invalid_reason_codes")
    else:
        reason_codes = [
            code for code in raw_reason_codes if isinstance(code, str) and code in VALID_REASON_CODES
        ]
        if len(reason_codes) != len(raw_reason_codes):
            review_reasons.append("invalid_reason_codes")

    confidence = parsed.get("parse_confidence")
    confidence_is_valid = True
    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
        or not math.isfinite(float(confidence))
        or confidence < 0
        or confidence > 1
    ):
        confidence = 0.0
        confidence_is_valid = False
        review_reasons.append("invalid_parse_confidence")

    if confidence_is_valid and confidence < LOW_CONFIDENCE_THRESHOLD:
        review_reasons.append("low_confidence")

    if "invalid_feedback_label" in review_reasons:
        confidence = 0.0

    hunter_note = parsed.get("hunter_note")
    if not isinstance(hunter_note, str) or not hunter_note.strip():
        hunter_note = feedback_note

    return {
        "feedback_label": label,
        "feedback_stage": stage,
        "reason_codes": reason_codes,
        "hunter_note": hunter_note,
        "feedback_note": feedback_note,
        "parse_source": parse_source,
        "parse_confidence": confidence,
        "review_required": bool(review_reasons),
        "review_reasons": review_reasons,
    }


if __name__ == "__main__":
    raise SystemExit(main())
