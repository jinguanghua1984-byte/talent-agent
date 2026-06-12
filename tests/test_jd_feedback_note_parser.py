import json
from pathlib import Path

import pytest

from scripts.jd_feedback_note_parser import (
    apply_feedback_batch_job,
    build_feedback_prompt,
    extract_json_object,
    main,
    prepare_feedback_batch_job,
    parse_feedback_csv,
    parse_feedback_note,
    parse_feedback_notes_batch,
)
from scripts.llm_usage import LLMUsageLedger


class FakeClient:
    def __init__(self, response: str | Exception):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, messages, model, max_tokens, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class QueueClient:
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls: list[dict] = []

    def complete(self, messages, model, max_tokens, **kwargs):
        self.calls.append(
            {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        return self.responses.pop(0)


class StructuredClient:
    def __init__(self, response: dict | Exception):
        self.response = response
        self.structured_calls: list[dict] = []
        self.complete_calls: list[dict] = []

    def complete_structured(self, messages, model, max_tokens, *, schema, **kwargs):
        self.structured_calls.append(
            {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "schema": schema,
                "kwargs": kwargs,
            }
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def complete(self, messages, model, max_tokens, **kwargs):
        self.complete_calls.append(
            {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
        )
        return _response()


def _response(**overrides) -> str:
    data = {
        "feedback_label": "认可",
        "feedback_stage": "匹配",
        "reason_codes": ["strong_candidate_ranked_low"],
        "hunter_note": "候选人方向准确，可以沟通。",
        "parse_confidence": 0.91,
    }
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def _batch_response(items: list[dict]) -> str:
    payload = {"items": []}
    for index, overrides in enumerate(items):
        data = {
            "index": index,
            "feedback_label": "认可",
            "feedback_stage": "匹配",
            "reason_codes": ["strong_candidate_ranked_low"],
            "hunter_note": "候选人方向准确，可以沟通。",
            "parse_confidence": 0.91,
        }
        data.update(overrides)
        payload["items"].append(data)
    return json.dumps(payload, ensure_ascii=False)


def _run_root(tmp_path: Path) -> Path:
    root = tmp_path / "run"
    (root / "profile").mkdir(parents=True)
    (root / "scoring").mkdir()
    (root / "reports").mkdir()
    (root / "run-manifest.json").write_text(
        json.dumps({"output_dir": "data/output/demo-run"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (root / "profile" / "role-profile.json").write_text(
        json.dumps(
            {
                "schema": "role_profile_v1",
                "version": "profile-v1",
                "role_id": "demo-role",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "scoring" / "scorecard.json").write_text(
        json.dumps(
            {
                "schema": "scorecard_v1",
                "version": "v1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,候选人方向准确，可以沟通。\n"
            "102,2,A,84,看起来相关，但证据不够。\n"
            "103,3,C,61,\n"
        ),
        encoding="utf-8-sig",
    )
    return root


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_build_feedback_prompt_includes_field_meanings_and_note() -> None:
    prompt = build_feedback_prompt("方向匹配，有大模型平台经验，建议优先联系。")

    assert "feedback_label" in prompt
    assert "feedback_stage" in prompt
    assert "reason_codes" in prompt
    assert "hunter_note" in prompt
    assert "parse_confidence" in prompt
    assert "认可" in prompt
    assert "待定" in prompt
    assert "不认可" in prompt
    assert "方向匹配，有大模型平台经验，建议优先联系。" in prompt


@pytest.mark.parametrize(
    "text",
    [
        _response(),
        "```json\n" + _response() + "\n```",
        "解析结果如下：\n" + _response() + "\n请参考。",
    ],
)
def test_extract_json_object_accepts_common_llm_wrappers(text: str) -> None:
    result = extract_json_object(text)

    assert result["feedback_label"] == "认可"
    assert result["feedback_stage"] == "匹配"
    assert result["reason_codes"] == ["strong_candidate_ranked_low"]
    assert result["parse_confidence"] == 0.91


def test_parse_feedback_note_uses_rule_for_clear_rejection_without_llm() -> None:
    client = FakeClient(RuntimeError("should not call llm"))

    result = parse_feedback_note(
        "不合适，年限不符。", client=client, model="model-x"
    )

    assert client.calls == []
    assert result == {
        "feedback_label": "不认可",
        "feedback_stage": "匹配",
        "reason_codes": ["seniority_mismatch"],
        "hunter_note": "不合适，年限不符。",
        "feedback_note": "不合适，年限不符。",
        "parse_source": "rule",
        "parse_confidence": 0.95,
        "review_required": False,
        "review_reasons": [],
    }


def test_parse_feedback_note_returns_valid_high_confidence_llm_result() -> None:
    client = FakeClient(_response())

    result = parse_feedback_note(
        "候选人有相关平台经验，但需要综合判断客户是否接受当前方向。",
        client=client,
        model="model-x",
    )

    assert client.calls
    assert result == {
        "feedback_label": "认可",
        "feedback_stage": "匹配",
        "reason_codes": ["strong_candidate_ranked_low"],
        "hunter_note": "候选人方向准确，可以沟通。",
        "feedback_note": "候选人有相关平台经验，但需要综合判断客户是否接受当前方向。",
        "parse_source": "llm",
        "parse_confidence": 0.91,
        "review_required": False,
        "review_reasons": [],
    }


def test_parse_feedback_note_passes_single_route_metadata() -> None:
    client = FakeClient(_response())

    parse_feedback_note("需要综合判断。", client=client, model="model-x")

    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "model-x"
    assert client.calls[0]["max_tokens"] == 512
    assert client.calls[0]["kwargs"]["workflow"] == "jd-feedback"
    assert client.calls[0]["kwargs"]["stage"] == "parse-single-note"
    assert client.calls[0]["kwargs"]["batch_discount_applied"] is False


def test_parse_feedback_note_uses_structured_output_when_available() -> None:
    client = StructuredClient(
        {
            "feedback_label": "认可",
            "feedback_stage": "匹配",
            "reason_codes": ["strong_candidate_ranked_low"],
            "hunter_note": "候选人方向准确，可以沟通。",
            "parse_confidence": 0.91,
        }
    )

    result = parse_feedback_note("需要综合判断。", client=client, model="model-x")

    assert client.complete_calls == []
    assert len(client.structured_calls) == 1
    call = client.structured_calls[0]
    assert call["model"] == "model-x"
    assert call["max_tokens"] == 512
    assert call["kwargs"]["workflow"] == "jd-feedback"
    assert call["kwargs"]["stage"] == "parse-single-note"
    assert call["kwargs"]["batch_discount_applied"] is False
    assert call["schema"].name == "jd_feedback_note_parse"
    assert set(call["schema"].schema["properties"]) >= {
        "feedback_label",
        "feedback_stage",
        "reason_codes",
        "hunter_note",
        "parse_confidence",
    }
    assert result["parse_source"] == "llm_structured"
    assert result["feedback_label"] == "认可"


def test_parse_feedback_notes_batch_passes_batch_route_metadata() -> None:
    client = QueueClient(
        [
            _batch_response(
                [
                    {
                        "feedback_label": "待定",
                        "reason_codes": ["evidence_too_shallow"],
                        "parse_confidence": 0.72,
                    }
                ]
            )
        ]
    )

    parse_feedback_notes_batch(["需要确认证据深度。"], client=client, model="model-x")

    assert len(client.calls) == 1
    assert client.calls[0]["model"] == "model-x"
    assert client.calls[0]["max_tokens"] == 2048
    assert client.calls[0]["kwargs"]["workflow"] == "jd-feedback"
    assert client.calls[0]["kwargs"]["stage"] == "parse-low-confidence-batch"
    assert client.calls[0]["kwargs"]["batch_discount_applied"] is False


def test_parse_feedback_notes_batch_uses_structured_output_when_available() -> None:
    client = StructuredClient(
        {
            "items": [
                {
                    "index": 0,
                    "feedback_label": "待定",
                    "feedback_stage": "匹配",
                    "reason_codes": ["wrong_role_type"],
                    "hunter_note": "可能偏算法研究，需要确认工程落地经验。",
                    "parse_confidence": 0.74,
                },
                {
                    "index": 1,
                    "feedback_label": "待定",
                    "feedback_stage": "匹配",
                    "reason_codes": ["evidence_too_shallow"],
                    "hunter_note": "证据偏浅，需要人工确认。",
                    "parse_confidence": 0.52,
                },
            ]
        }
    )

    results = parse_feedback_notes_batch(
        [
            "候选人有相关平台经验，但需要确认是否偏算法研究而不是工程落地。",
            "整体相关，不过证据偏浅，需要确认是否只是关键词命中。",
        ],
        client=client,
        model="model-x",
    )

    assert client.complete_calls == []
    assert len(client.structured_calls) == 1
    call = client.structured_calls[0]
    assert call["model"] == "model-x"
    assert call["max_tokens"] == 2048
    assert call["kwargs"]["workflow"] == "jd-feedback"
    assert call["kwargs"]["stage"] == "parse-low-confidence-batch"
    assert call["schema"].name == "jd_feedback_note_batch_parse"
    assert "items" in call["schema"].schema["properties"]
    assert results[0]["parse_source"] == "llm_batch_structured"
    assert results[0]["reason_codes"] == ["wrong_role_type"]
    assert results[1]["review_required"] is True


def test_parse_feedback_note_falls_back_when_structured_output_fails() -> None:
    client = StructuredClient(RuntimeError("structured down"))

    result = parse_feedback_note("需要综合判断。", client=client, model="model-x")

    assert len(client.structured_calls) == 1
    assert len(client.complete_calls) == 1
    assert result["parse_source"] == "llm"
    assert result["feedback_label"] == "认可"


def test_parse_feedback_note_downgrades_invalid_fields_to_review_queue() -> None:
    client = FakeClient(
        _response(
            feedback_label="强烈认可",
            feedback_stage="外联",
            reason_codes=["strong_candidate_ranked_low", "unknown_reason"],
            parse_confidence=0.88,
        )
    )

    result = parse_feedback_note("看起来不错。", client=client, model="model-x")

    assert result["feedback_label"] == "待定"
    assert result["feedback_stage"] == "匹配"
    assert result["reason_codes"] == ["strong_candidate_ranked_low"]
    assert result["parse_confidence"] == 0.0
    assert result["review_required"] is True
    assert result["review_reasons"] == [
        "invalid_feedback_label",
        "invalid_feedback_stage",
        "invalid_reason_codes",
    ]


def test_parse_feedback_note_low_confidence_requires_review() -> None:
    client = FakeClient(_response(parse_confidence=0.69))

    result = parse_feedback_note("需要确认。", client=client, model="model-x")

    assert result["parse_confidence"] == 0.69
    assert result["review_required"] is True
    assert result["review_reasons"] == ["low_confidence"]


def test_parse_feedback_note_handles_llm_failure_as_review_required() -> None:
    client = FakeClient(RuntimeError("boom"))

    result = parse_feedback_note("原始反馈。", client=client, model="model-x")

    assert result == {
        "feedback_label": "待定",
        "feedback_stage": "匹配",
        "reason_codes": [],
        "hunter_note": "原始反馈。",
        "feedback_note": "原始反馈。",
        "parse_source": "llm",
        "parse_confidence": 0.0,
        "review_required": True,
        "review_reasons": ["llm_error"],
    }


def test_parse_feedback_csv_writes_delivery_feedback_and_review_queue(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    client = QueueClient(
        [
            _response(parse_confidence=0.91),
            _response(
                feedback_label="待定",
                reason_codes=["evidence_too_shallow"],
                parse_confidence=0.52,
            ),
        ]
    )

    result = parse_feedback_csv(root, client=client, model="model-x")

    assert result["parsed_count"] == 2
    assert result["accepted_count"] == 1
    assert result["review_count"] == 1
    delivery = json.loads(
        (root / "feedback" / "delivery-feedback.json").read_text(encoding="utf-8-sig")
    )
    assert delivery["schema"] == "jd_delivery_feedback_v1"
    assert delivery["role_id"] == "demo-role"
    assert delivery["scorecard_version"] == "v1"
    assert len(delivery["candidate_feedback"]) == 1
    item = delivery["candidate_feedback"][0]
    assert item["candidate_id"] == "101"
    assert item["original_grade"] == "A"
    assert item["original_score"] == 88
    review = json.loads(
        (root / "feedback" / "parse-review-queue.json").read_text(encoding="utf-8-sig")
    )
    assert review["schema"] == "jd_delivery_feedback_parse_review_queue_v1"
    assert len(review["items"]) == 1
    assert review["items"][0]["candidate_id"] == "102"
    assert review["items"][0]["review_status"] == "pending"
    summary = json.loads(
        (root / "feedback" / "feedback-summary.json").read_text(encoding="utf-8-sig")
    )
    assert summary["metrics"]["accepted_at_10"] == 1


def test_parse_feedback_csv_uses_rules_and_batches_unresolved_notes(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,认可，可以推进沟通。\n"
            "102,2,A,84,候选人有相关平台经验，但需要确认是否偏算法研究而不是工程落地。\n"
            "103,3,B,76,整体相关，不过证据偏浅，需要确认是否只是关键词命中。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient(
        [
            _batch_response(
                [
                    {
                        "feedback_label": "待定",
                        "reason_codes": ["wrong_role_type"],
                        "hunter_note": "可能偏算法研究，需要确认工程落地经验。",
                        "parse_confidence": 0.74,
                    },
                    {
                        "feedback_label": "待定",
                        "reason_codes": ["evidence_too_shallow"],
                        "hunter_note": "证据偏浅，需要人工确认。",
                        "parse_confidence": 0.52,
                    },
                ]
            )
        ]
    )

    result = parse_feedback_csv(root, client=client, model="model-x")

    assert result["parsed_count"] == 3
    assert result["accepted_count"] == 2
    assert result["review_count"] == 1
    assert len(client.calls) == 1
    prompt = client.calls[0]["messages"][0]["content"]
    assert "候选人有相关平台经验" in prompt
    assert "整体相关，不过证据偏浅" in prompt
    assert "认可，可以推进沟通" not in prompt
    assert client.calls[0]["max_tokens"] == 2048

    delivery = json.loads(
        (root / "feedback" / "delivery-feedback.json").read_text(encoding="utf-8-sig")
    )
    items_by_id = {
        item["candidate_id"]: item for item in delivery["candidate_feedback"]
    }
    assert items_by_id["101"]["parse_source"] == "rule"
    assert items_by_id["101"]["feedback_label"] == "认可"
    assert items_by_id["102"]["parse_source"] == "llm_batch"
    assert items_by_id["102"]["reason_codes"] == ["wrong_role_type"]

    review = json.loads(
        (root / "feedback" / "parse-review-queue.json").read_text(encoding="utf-8-sig")
    )
    assert review["items"][0]["candidate_id"] == "103"
    assert review["items"][0]["parse_source"] == "llm_batch"
    assert review["items"][0]["review_reasons"] == ["low_confidence"]


def test_parse_feedback_csv_preserves_consultant_decision(tmp_path: Path) -> None:
    run_root = tmp_path / "run"
    (run_root / "profile").mkdir(parents=True)
    (run_root / "scoring").mkdir()
    (run_root / "run-manifest.json").write_text(
        json.dumps({"output_dir": "data/output/run"}, ensure_ascii=False),
        encoding="utf-8",
    )
    (run_root / "profile" / "role-profile.json").write_text(
        json.dumps(
            {"schema": "role_profile_v1", "version": "profile-v1", "role_id": "role"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (run_root / "scoring" / "scorecard.json").write_text(
        json.dumps({"schema": "scorecard_v1", "version": "s1"}, ensure_ascii=False),
        encoding="utf-8",
    )
    csv_path = run_root / "outreach.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    csv_path.write_text(
        "\n".join(
            [
                "candidate_id,rank,score,grade,consultant_decision,feedback_note",
                "cand-001,1,91.5,A,认可,这个不错，可以推荐",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = parse_feedback_csv(run_root=run_root, csv_path=csv_path, dry_run=True)

    assert result["items"][0]["consultant_decision"] == "认可"
    assert result["items"][0]["decision_source"] == "explicit"


def test_prepare_feedback_batch_job_writes_manifest_requests_and_rule_results(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,认可，可以推进沟通。\n"
            "102,2,A,84,候选人有相关平台经验，但需要确认是否偏算法研究而不是工程落地。\n"
            "103,3,B,76,整体相关，不过证据偏浅，需要确认是否只是关键词命中。\n"
        ),
        encoding="utf-8-sig",
    )

    result = prepare_feedback_batch_job(root, job_id="job-1")

    job_dir = root / "feedback" / "batch-jobs" / "job-1"
    assert result == {
        "run_root": str(root),
        "job_dir": str(job_dir),
        "manifest_path": str(job_dir / "batch-job-manifest.json"),
        "request_jsonl": str(job_dir / "requests.jsonl"),
        "rule_results_path": str(job_dir / "rule-results.json"),
        "expected_output_jsonl": str(job_dir / "provider-output.jsonl"),
        "batch_job_id": "job-1",
        "request_count": 1,
        "unresolved_count": 2,
        "rule_parsed_count": 1,
        "dry_run": False,
    }
    manifest = json.loads(
        (job_dir / "batch-job-manifest.json").read_text(encoding="utf-8-sig")
    )
    assert manifest["schema"] == "jd_feedback_batch_job_v1"
    assert manifest["batch_job_id"] == "job-1"
    assert manifest["provider"] == "anthropic"
    assert manifest["model"] == "claude-haiku-4-5"
    assert manifest["workflow"] == "jd-feedback"
    assert manifest["stage"] == "parse-low-confidence-batch"
    assert manifest["max_tokens"] == 2048
    assert manifest["request_count"] == 1
    assert manifest["unresolved_count"] == 2
    assert manifest["rule_parsed_count"] == 1
    assert len(manifest["source_csv_hash"]) == 64
    assert manifest["expected_output_jsonl"] == str(job_dir / "provider-output.jsonl")
    assert manifest["requests"][0]["custom_id"] == "jd-feedback:job-1:chunk-000001"
    assert manifest["requests"][0]["item_count"] == 2
    assert len(manifest["requests"][0]["prompt_hash"]) == 64

    requests = _read_jsonl(job_dir / "requests.jsonl")
    assert len(requests) == 1
    request = requests[0]
    assert request["schema"] == "llm_batch_request_v1"
    assert request["custom_id"] == "jd-feedback:job-1:chunk-000001"
    assert request["request"]["model"] == "claude-haiku-4-5"
    assert request["request"]["max_tokens"] == 2048
    prompt = request["request"]["messages"][0]["content"]
    assert "候选人有相关平台经验" in prompt
    assert "整体相关，不过证据偏浅" in prompt
    assert "认可，可以推进沟通" not in prompt
    assert request["metadata"]["items"][0]["candidate_id"] == "102"
    assert request["metadata"]["items"][1]["candidate_id"] == "103"
    assert request["metadata"]["prompt_hash"] == manifest["requests"][0]["prompt_hash"]

    rule_results = json.loads(
        (job_dir / "rule-results.json").read_text(encoding="utf-8-sig")
    )
    assert rule_results["schema"] == "jd_feedback_batch_rule_results_v1"
    assert rule_results["items"][0]["row"]["candidate_id"] == "101"
    assert rule_results["items"][0]["parsed"]["parse_source"] == "rule"
    assert not (root / "feedback" / "delivery-feedback.json").exists()


def test_apply_feedback_batch_job_output_combines_rule_and_batch_results_and_records_usage(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,认可，可以推进沟通。\n"
            "102,2,A,84,候选人有相关平台经验，但需要确认是否偏算法研究而不是工程落地。\n"
            "103,3,B,76,整体相关，不过证据偏浅，需要确认是否只是关键词命中。\n"
        ),
        encoding="utf-8-sig",
    )
    prepare_feedback_batch_job(root, job_id="job-1")
    job_dir = root / "feedback" / "batch-jobs" / "job-1"
    output_jsonl = job_dir / "provider-output.jsonl"
    output_jsonl.write_text(
        json.dumps(
            {
                "custom_id": "jd-feedback:job-1:chunk-000001",
                "response": {
                    "body": {
                        "id": "msg_1",
                        "stop_reason": "end_turn",
                        "content": [
                            {
                                "text": _batch_response(
                                    [
                                        {
                                            "feedback_label": "待定",
                                            "reason_codes": ["wrong_role_type"],
                                            "hunter_note": "可能偏算法研究，需要确认工程落地经验。",
                                            "parse_confidence": 0.74,
                                        },
                                        {
                                            "feedback_label": "待定",
                                            "reason_codes": ["evidence_too_shallow"],
                                            "hunter_note": "证据偏浅，需要人工确认。",
                                            "parse_confidence": 0.52,
                                        },
                                    ]
                                )
                            }
                        ],
                        "usage": {"input_tokens": 1200, "output_tokens": 160},
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    ledger_dir = tmp_path / "ledger"

    result = apply_feedback_batch_job(
        root,
        job_dir=job_dir,
        output_jsonl=output_jsonl,
        ledger=LLMUsageLedger(ledger_dir),
    )

    assert result["parsed_count"] == 3
    assert result["accepted_count"] == 2
    assert result["review_count"] == 1
    assert result["usage_record_count"] == 1
    delivery = json.loads(
        (root / "feedback" / "delivery-feedback.json").read_text(encoding="utf-8-sig")
    )
    items_by_id = {
        item["candidate_id"]: item for item in delivery["candidate_feedback"]
    }
    assert items_by_id["101"]["parse_source"] == "rule"
    assert items_by_id["102"]["parse_source"] == "llm_batch_job"
    assert items_by_id["102"]["reason_codes"] == ["wrong_role_type"]
    review = json.loads(
        (root / "feedback" / "parse-review-queue.json").read_text(encoding="utf-8-sig")
    )
    assert review["items"][0]["candidate_id"] == "103"
    assert review["items"][0]["parse_source"] == "llm_batch_job"
    assert review["items"][0]["review_reasons"] == ["low_confidence"]

    ledger_paths = sorted(ledger_dir.glob("llm-usage-*.jsonl"))
    assert len(ledger_paths) == 1
    ledger_row = json.loads(ledger_paths[0].read_text(encoding="utf-8"))
    manifest = json.loads((job_dir / "batch-job-manifest.json").read_text(encoding="utf-8-sig"))
    assert ledger_row["workflow"] == "jd-feedback"
    assert ledger_row["stage"] == "parse-low-confidence-batch"
    assert ledger_row["input_tokens"] == 1200
    assert ledger_row["output_tokens"] == 160
    assert ledger_row["usage_source"] == "api_usage"
    assert ledger_row["batch_discount_applied"] is True
    assert ledger_row["batch_job_id"] == "job-1"
    assert ledger_row["batch_custom_id"] == "jd-feedback:job-1:chunk-000001"
    assert ledger_row["batch_output_artifact"] == str(output_jsonl)
    assert len(ledger_row["output_artifact_hash"]) == 64
    assert ledger_row["input_artifact_hash"] == manifest["source_csv_hash"]
    assert ledger_row["prompt_hash"] == manifest["requests"][0]["prompt_hash"]


def test_parse_feedback_csv_dry_run_does_not_write_outputs(tmp_path: Path) -> None:
    root = _run_root(tmp_path)
    client = QueueClient([_response(), _response(parse_confidence=0.52)])

    result = parse_feedback_csv(root, client=client, model="model-x", dry_run=True)

    assert result["parsed_count"] == 2
    assert result["accepted_count"] == 1
    assert result["review_count"] == 1
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()
    assert not (root / "feedback" / "feedback-summary.json").exists()
    assert not (root / "feedback" / "calibration-suggestions.json").exists()


def test_parse_feedback_csv_rejects_missing_feedback_note_column(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score\n"
            "101,1,A,88\n"
        ),
        encoding="utf-8-sig",
    )

    with pytest.raises(
        ValueError, match="outreach CSV missing required columns: feedback_note"
    ):
        parse_feedback_csv(root, client=QueueClient([]), model="model-x")

    assert not (root / "feedback" / "delivery-feedback.json").exists()


def test_parse_feedback_csv_rejects_duplicate_candidate_before_writing_outputs(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,候选人方向准确，可以沟通。\n"
            "101,2,A,84,候选人也很匹配，可以继续沟通。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient([_response(), _response()])

    with pytest.raises(ValueError, match="duplicate candidate_id"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()
    assert not (root / "feedback" / "feedback-summary.json").exists()
    assert not (root / "feedback" / "calibration-suggestions.json").exists()


def test_parse_feedback_csv_rejects_duplicate_review_candidate_before_writing_outputs(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,看起来相关，但证据不够。\n"
            "101,2,A,84,也需要继续确认。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient(
        [
            _response(feedback_label="待定", parse_confidence=0.52),
            _response(feedback_label="待定", parse_confidence=0.52),
        ]
    )

    with pytest.raises(ValueError, match="duplicate candidate_id"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert client.calls == []
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()


def test_parse_feedback_csv_rejects_duplicate_rank_across_accepted_and_review_rows(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,88,候选人方向准确，可以沟通。\n"
            "102,1,A,84,看起来相关，但证据不够。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient(
        [
            _response(),
            _response(feedback_label="待定", parse_confidence=0.52),
        ]
    )

    with pytest.raises(ValueError, match="duplicate rank"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert client.calls == []
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()


def test_parse_feedback_csv_rejects_invalid_review_rank_before_writing_outputs(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,0,A,88,看起来相关，但证据不够。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient([_response(feedback_label="待定", parse_confidence=0.52)])

    with pytest.raises(ValueError, match="rank must be a positive integer"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert client.calls == []
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()
    assert not (root / "feedback" / "feedback-summary.json").exists()
    assert not (root / "feedback" / "calibration-suggestions.json").exists()


def test_parse_feedback_csv_rejects_invalid_review_grade_before_writing_outputs(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,Z,88,看起来相关，但证据不够。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient([_response(feedback_label="待定", parse_confidence=0.52)])

    with pytest.raises(ValueError, match="invalid original grade: Z"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert client.calls == []
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()
    assert not (root / "feedback" / "feedback-summary.json").exists()
    assert not (root / "feedback" / "calibration-suggestions.json").exists()


def test_parse_feedback_csv_rejects_non_finite_score_before_writing_outputs(
    tmp_path: Path,
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score,feedback_note\n"
            "101,1,A,nan,候选人方向准确，可以沟通。\n"
        ),
        encoding="utf-8-sig",
    )
    client = QueueClient([_response()])

    with pytest.raises(ValueError, match="score must be a finite number"):
        parse_feedback_csv(root, client=client, model="model-x")

    assert client.calls == []
    assert not (root / "feedback" / "delivery-feedback.json").exists()
    assert not (root / "feedback" / "parse-review-queue.json").exists()
    assert not (root / "feedback" / "feedback-summary.json").exists()
    assert not (root / "feedback" / "calibration-suggestions.json").exists()


def test_cli_parse_csv_uses_run_root(tmp_path: Path) -> None:
    root = _run_root(tmp_path)
    client = QueueClient([_response(), _response(parse_confidence=0.52)])

    exit_code = main(["parse-csv", "--run-root", str(root)], client=client)

    assert exit_code == 0
    assert (root / "feedback" / "delivery-feedback.json").exists()
    assert (root / "feedback" / "parse-review-queue.json").exists()


def test_cli_prepare_batch_writes_job_artifacts(tmp_path: Path) -> None:
    root = _run_root(tmp_path)

    exit_code = main(["prepare-batch", "--run-root", str(root), "--job-id", "job-cli"])

    job_dir = root / "feedback" / "batch-jobs" / "job-cli"
    assert exit_code == 0
    assert (job_dir / "batch-job-manifest.json").exists()
    assert (job_dir / "requests.jsonl").exists()
    assert (job_dir / "rule-results.json").exists()


def test_cli_apply_batch_writes_outputs_and_usage_ledger(tmp_path: Path) -> None:
    root = _run_root(tmp_path)
    prepare_feedback_batch_job(root, job_id="job-cli")
    job_dir = root / "feedback" / "batch-jobs" / "job-cli"
    output_jsonl = job_dir / "provider-output.jsonl"
    output_jsonl.write_text(
        json.dumps(
            {
                "custom_id": "jd-feedback:job-cli:chunk-000001",
                "response": {
                    "body": {
                        "id": "msg_cli",
                        "stop_reason": "end_turn",
                        "content": [
                            {
                                "text": _batch_response(
                                    [
                                        {"parse_confidence": 0.91},
                                        {
                                            "feedback_label": "待定",
                                            "reason_codes": ["evidence_too_shallow"],
                                            "parse_confidence": 0.52,
                                        },
                                    ]
                                )
                            }
                        ],
                        "usage": {"input_tokens": 100, "output_tokens": 20},
                    }
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    ledger_dir = tmp_path / "ledger"

    exit_code = main(
        [
            "apply-batch",
            "--run-root",
            str(root),
            "--job-dir",
            str(job_dir),
            "--output-jsonl",
            str(output_jsonl),
            "--ledger-dir",
            str(ledger_dir),
        ]
    )

    assert exit_code == 0
    assert (root / "feedback" / "delivery-feedback.json").exists()
    assert (root / "feedback" / "parse-review-queue.json").exists()
    assert list(ledger_dir.glob("llm-usage-*.jsonl"))


def test_cli_parse_csv_reports_validation_error_without_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _run_root(tmp_path)
    (root / "reports" / "outreach-queue.csv").write_text(
        (
            "candidate_id,rank,grade,score\n"
            "101,1,A,88\n"
        ),
        encoding="utf-8-sig",
    )

    exit_code = main(
        ["parse-csv", "--run-root", str(root), "--model", "test"],
        client=QueueClient([]),
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "error:" in captured.err
    assert "Traceback" not in captured.err


def test_cli_parse_single_note_writes_json(tmp_path: Path) -> None:
    out_path = tmp_path / "note.json"
    client = QueueClient([_response()])

    exit_code = main(
        ["parse", "--note", "候选人方向准确，可以沟通。", "--out", str(out_path)],
        client=client,
    )

    assert exit_code == 0
    result = json.loads(out_path.read_text(encoding="utf-8-sig"))
    assert result["feedback_label"] == "认可"
    assert result["feedback_note"] == "候选人方向准确，可以沟通。"
