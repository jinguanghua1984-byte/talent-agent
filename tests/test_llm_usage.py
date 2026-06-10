"""LLM usage ledger、成本估算和模型路由测试。"""

import json
from pathlib import Path

from scripts.llm_usage import (
    LLMUsageLedger,
    LLMUsageRecord,
    count_tokens_dry_run,
    estimate_cost_usd,
    hash_prompt,
    resolve_llm_route,
    summarize_usage,
    usage_record_from_response,
)


def test_usage_ledger_writes_monthly_provider_neutral_jsonl(tmp_path: Path) -> None:
    ledger = LLMUsageLedger(tmp_path)
    record = LLMUsageRecord(
        timestamp="2026-06-06T12:00:00+08:00",
        provider="anthropic",
        tool_surface="claude_api",
        agent_runtime="script",
        workflow="jd-talent-delivery",
        stage="detailed-rank",
        model="claude-sonnet-4-6",
        max_tokens=16000,
        input_tokens=12345,
        output_tokens=678,
        cache_read_input_tokens=9000,
        cache_creation_input_tokens=0,
        cache_ttl="5m",
        prompt_hash="prompt-hash",
        input_artifact_hash="artifact-hash",
        request_id="req_1",
        session_id="session-1",
        stop_reason="end_turn",
        artifact_root="data/output/run-1",
        api_cache_hit=True,
        local_cache_hit=False,
        batch_discount_applied=False,
        usage_source="api_usage",
        cost_formula="anthropic_messages_v1",
        estimated_cost_usd=0.1234,
    )

    output_path = ledger.append(record)

    assert output_path == tmp_path / "llm-usage-2026-06.jsonl"
    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert rows == [
        {
            "timestamp": "2026-06-06T12:00:00+08:00",
            "provider": "anthropic",
            "tool_surface": "claude_api",
            "agent_runtime": "script",
            "workflow": "jd-talent-delivery",
            "stage": "detailed-rank",
            "model": "claude-sonnet-4-6",
            "max_tokens": 16000,
            "input_tokens": 12345,
            "output_tokens": 678,
            "cache_read_input_tokens": 9000,
            "cache_creation_input_tokens": 0,
            "cache_ttl": "5m",
            "prompt_hash": "prompt-hash",
            "input_artifact_hash": "artifact-hash",
            "request_id": "req_1",
            "session_id": "session-1",
            "stop_reason": "end_turn",
            "artifact_root": "data/output/run-1",
            "api_cache_hit": True,
            "local_cache_hit": False,
            "batch_discount_applied": False,
            "usage_source": "api_usage",
            "cost_formula": "anthropic_messages_v1",
            "estimated_cost_usd": 0.1234,
            "batch_job_id": None,
            "batch_custom_id": None,
            "batch_output_artifact": None,
            "output_artifact_hash": None,
        }
    ]


def test_usage_record_carries_provider_batch_metadata() -> None:
    record = usage_record_from_response(
        provider="anthropic",
        tool_surface="claude_api",
        agent_runtime="script",
        workflow="jd-feedback",
        stage="parse-low-confidence-batch",
        model="claude-haiku-4-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": "batch prompt"}],
        usage={"input_tokens": 1000, "output_tokens": 100},
        request_id="msg_1",
        stop_reason="end_turn",
        artifact_root="data/output/run/feedback/batch-jobs/job-1",
        input_artifact_hash="csv-hash",
        batch_discount_applied=True,
        batch_job_id="job-1",
        batch_custom_id="jd-feedback:job-1:chunk-000001",
        batch_output_artifact="data/output/run/feedback/batch-jobs/job-1/output.jsonl",
        output_artifact_hash="out-hash",
    )

    assert record.batch_job_id == "job-1"
    assert record.batch_custom_id == "jd-feedback:job-1:chunk-000001"
    assert record.batch_output_artifact == "data/output/run/feedback/batch-jobs/job-1/output.jsonl"
    assert record.output_artifact_hash == "out-hash"
    assert record.input_artifact_hash == "csv-hash"
    assert record.batch_discount_applied is True
    assert record.usage_source == "api_usage"
    assert record.estimated_cost_usd == 0.00075


def test_anthropic_cost_uses_cache_multipliers_and_batch_discount() -> None:
    cost = estimate_cost_usd(
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=200_000,
        cache_creation_input_tokens=50_000,
        cache_ttl="5m",
        batch_discount_applied=True,
    )

    # Sonnet: $3 input / $15 output per 1M, cache read 0.1x, 5m write 1.25x.
    expected = (3.0 + 1.5 + 0.06 + 0.1875) * 0.5
    assert cost == expected


def test_openai_compatible_cost_does_not_reuse_anthropic_cache_fields() -> None:
    cost = estimate_cost_usd(
        provider="openai-compatible",
        model="deepseek-chat",
        input_tokens=1_000_000,
        output_tokens=100_000,
        cache_read_input_tokens=900_000,
        cache_creation_input_tokens=900_000,
    )

    # deepseek-chat defaults in the project table: $0.27 input / $1.10 output per 1M.
    assert cost == 0.27 + 0.11


def test_hash_prompt_is_stable_for_equivalent_json_order() -> None:
    left = [{"role": "user", "content": {"b": 2, "a": 1}}]
    right = [{"content": {"a": 1, "b": 2}, "role": "user"}]

    assert hash_prompt(left) == hash_prompt(right)


def test_resolve_llm_route_merges_defaults_workflow_and_stage() -> None:
    route = resolve_llm_route("jd-talent-delivery", "detailed-rank")

    assert route.provider == "anthropic"
    assert route.tool_surface == "claude_api"
    assert route.agent_runtime == "script"
    assert route.model == "claude-sonnet-4-6"
    assert route.max_tokens == 16000
    assert route.streaming is True
    assert route.batch_eligible is False
    assert route.structured_output == "json_schema"
    assert route.usage_parser == "anthropic_messages"


def test_feedback_route_is_low_budget_and_batch_eligible() -> None:
    single_route = resolve_llm_route("jd-feedback", "parse-single-note")
    batch_route = resolve_llm_route("jd-feedback", "parse-low-confidence-batch")

    assert single_route.model == "claude-haiku-4-5"
    assert single_route.max_tokens == 512
    assert single_route.batch_eligible is False
    assert batch_route.model == "claude-haiku-4-5"
    assert batch_route.max_tokens == 2048
    assert batch_route.batch_eligible is True
    assert batch_route.structured_output == "json_schema"


def test_count_tokens_dry_run_uses_native_counter_when_available() -> None:
    class NativeCounter:
        def count_tokens(self, *, messages, model):
            assert messages == [{"role": "user", "content": "hello"}]
            assert model == "claude-sonnet-4-6"
            return {"input_tokens": 7}

    route = resolve_llm_route("jd-talent-delivery", "role-profile")
    result = count_tokens_dry_run(
        [{"role": "user", "content": "hello"}],
        route=route,
        native_counter=NativeCounter(),
    )

    assert result.input_tokens == 7
    assert result.usage_source == "api_usage"
    assert result.provider == "anthropic"
    assert result.model == "claude-sonnet-4-6"


def test_count_tokens_dry_run_marks_local_estimate_as_manual_estimate() -> None:
    route = resolve_llm_route("codex-cli", "session-estimate")
    result = count_tokens_dry_run(
        [{"role": "user", "content": "abcd" * 20}],
        route=route,
    )

    assert result.input_tokens > 0
    assert result.usage_source == "manual_estimate"
    assert result.confidence == "low"


def test_summarize_usage_groups_monthly_records_by_route(tmp_path: Path) -> None:
    path = tmp_path / "llm-usage-2026-06.jsonl"
    rows = [
        {
            "timestamp": "2026-06-06T12:00:00+00:00",
            "provider": "anthropic",
            "tool_surface": "claude_api",
            "agent_runtime": "script",
            "workflow": "jd-feedback",
            "stage": "parse-low-confidence-batch",
            "model": "claude-haiku-4-5",
            "max_tokens": 2048,
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_ttl": None,
            "prompt_hash": "p1",
            "input_artifact_hash": None,
            "request_id": "req-1",
            "session_id": None,
            "stop_reason": "end_turn",
            "artifact_root": None,
            "api_cache_hit": False,
            "local_cache_hit": False,
            "batch_discount_applied": False,
            "usage_source": "api_usage",
            "cost_formula": "anthropic_messages_v1",
            "estimated_cost_usd": 0.1,
        },
        {
            "timestamp": "2026-06-06T12:01:00+00:00",
            "provider": "anthropic",
            "tool_surface": "claude_api",
            "agent_runtime": "script",
            "workflow": "jd-feedback",
            "stage": "parse-low-confidence-batch",
            "model": "claude-haiku-4-5",
            "max_tokens": 2048,
            "input_tokens": 200,
            "output_tokens": 30,
            "cache_read_input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "cache_ttl": "5m",
            "prompt_hash": "p2",
            "input_artifact_hash": None,
            "request_id": "req-2",
            "session_id": None,
            "stop_reason": "end_turn",
            "artifact_root": None,
            "api_cache_hit": True,
            "local_cache_hit": False,
            "batch_discount_applied": False,
            "usage_source": "manual_estimate",
            "cost_formula": "anthropic_messages_v1",
            "estimated_cost_usd": 0.2,
        },
    ]
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )

    summary = summarize_usage("2026-06", ledger_dir=tmp_path)

    assert summary["month"] == "2026-06"
    assert summary["totals"] == {
        "calls": 2,
        "input_tokens": 300,
        "output_tokens": 50,
        "cache_read_input_tokens": 10,
        "cache_creation_input_tokens": 5,
        "estimated_cost_usd": 0.3,
    }
    assert summary["groups"] == [
        {
            "workflow": "jd-feedback",
            "stage": "parse-low-confidence-batch",
            "provider": "anthropic",
            "model": "claude-haiku-4-5",
            "calls": 2,
            "input_tokens": 300,
            "output_tokens": 50,
            "cache_read_input_tokens": 10,
            "cache_creation_input_tokens": 5,
            "estimated_cost_usd": 0.3,
            "usage_sources": {
                "api_usage": 1,
                "manual_estimate": 1,
            },
        }
    ]
