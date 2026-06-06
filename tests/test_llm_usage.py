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
        }
    ]


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
    route = resolve_llm_route("jd-feedback", "parse-low-confidence-batch")

    assert route.model == "claude-haiku-4-5"
    assert route.max_tokens == 512
    assert route.batch_eligible is True
    assert route.structured_output == "json_schema"


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
