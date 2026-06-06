"""Provider-neutral LLM usage ledger、成本估算和模型路由。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER_DIR = PROJECT_ROOT / "data" / "token-tracker"
DEFAULT_ROUTING_PATH = PROJECT_ROOT / "configs" / "llm-routing.json"


@dataclass(frozen=True)
class LLMUsageRecord:
    timestamp: str
    provider: str
    tool_surface: str
    agent_runtime: str
    workflow: str
    stage: str
    model: str
    max_tokens: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cache_creation_input_tokens: int
    cache_ttl: str | None
    prompt_hash: str
    input_artifact_hash: str | None
    request_id: str | None
    session_id: str | None
    stop_reason: str | None
    artifact_root: str | None
    api_cache_hit: bool
    local_cache_hit: bool
    batch_discount_applied: bool
    usage_source: str
    cost_formula: str
    estimated_cost_usd: float


@dataclass(frozen=True)
class LLMRoute:
    provider: str
    tool_surface: str
    agent_runtime: str
    model: str
    max_tokens: int
    streaming: bool
    batch_eligible: bool
    structured_output: str
    usage_parser: str
    workflow: str
    stage: str


@dataclass(frozen=True)
class TokenDryRunResult:
    provider: str
    model: str
    input_tokens: int
    usage_source: str
    confidence: str
    prompt_hash: str


class LLMUsageLedger:
    """按月份追加写入 provider-neutral LLM usage JSONL。"""

    def __init__(self, base_dir: str | Path = DEFAULT_LEDGER_DIR):
        self.base_dir = Path(base_dir)

    def append(self, record: LLMUsageRecord) -> Path:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / f"llm-usage-{_month_from_timestamp(record.timestamp)}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), ensure_ascii=False, sort_keys=True) + "\n")
        return path


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def hash_prompt(messages: Any) -> str:
    payload = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hash_artifact(value: str | bytes | Path | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, Path):
        data = value.read_bytes()
    elif isinstance(value, bytes):
        data = value
    else:
        data = value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_routing_config(path: str | Path = DEFAULT_ROUTING_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8-sig") as handle:
        return json.load(handle)


def resolve_llm_route(
    workflow: str,
    stage: str,
    *,
    config_path: str | Path = DEFAULT_ROUTING_PATH,
) -> LLMRoute:
    config = load_routing_config(config_path)
    merged: dict[str, Any] = dict(config.get("defaults", {}))
    workflow_config = config.get("workflows", {}).get(workflow, {})
    merged.update(workflow_config.get("defaults", {}))
    merged.update(workflow_config.get("stages", {}).get(stage, {}))
    return LLMRoute(
        provider=str(merged["provider"]),
        tool_surface=str(merged["tool_surface"]),
        agent_runtime=str(merged["agent_runtime"]),
        model=str(merged["model"]),
        max_tokens=int(merged["max_tokens"]),
        streaming=bool(merged["streaming"]),
        batch_eligible=bool(merged["batch_eligible"]),
        structured_output=str(merged["structured_output"]),
        usage_parser=str(merged["usage_parser"]),
        workflow=workflow,
        stage=stage,
    )


def estimate_cost_usd(
    *,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_input_tokens: int = 0,
    cache_creation_input_tokens: int = 0,
    cache_ttl: str | None = None,
    batch_discount_applied: bool = False,
    config_path: str | Path = DEFAULT_ROUTING_PATH,
) -> float:
    config = load_routing_config(config_path)
    prices = config.get("prices_per_million_tokens", {}).get(provider, {}).get(model, {})
    input_price = float(prices.get("input", 0.0))
    output_price = float(prices.get("output", 0.0))

    cost = (input_tokens / 1_000_000) * input_price
    cost += (output_tokens / 1_000_000) * output_price

    if provider == "anthropic":
        cost += (cache_read_input_tokens / 1_000_000) * input_price * 0.1
        cost += (
            (cache_creation_input_tokens / 1_000_000)
            * input_price
            * _anthropic_cache_write_multiplier(cache_ttl)
        )

    if batch_discount_applied:
        cost *= 0.5
    return round(cost, 10)


def cost_formula_for_provider(provider: str) -> str:
    if provider == "anthropic":
        return "anthropic_messages_v1"
    if provider in {"openai", "openai-compatible"}:
        return "openai_compatible_chat_v1"
    return "manual_estimate_v1"


def count_tokens_dry_run(
    messages: list[dict[str, Any]],
    *,
    route: LLMRoute,
    native_counter: Any | None = None,
) -> TokenDryRunResult:
    prompt_hash = hash_prompt(messages)
    if native_counter is not None and hasattr(native_counter, "count_tokens"):
        counted = native_counter.count_tokens(messages=messages, model=route.model)
        return TokenDryRunResult(
            provider=route.provider,
            model=route.model,
            input_tokens=_extract_input_tokens(counted),
            usage_source="api_usage",
            confidence="high",
            prompt_hash=prompt_hash,
        )

    return TokenDryRunResult(
        provider=route.provider,
        model=route.model,
        input_tokens=_estimate_tokens_locally(messages),
        usage_source="manual_estimate",
        confidence="low",
        prompt_hash=prompt_hash,
    )


def usage_record_from_response(
    *,
    provider: str,
    tool_surface: str,
    agent_runtime: str,
    workflow: str,
    stage: str,
    model: str,
    max_tokens: int,
    messages: list[dict[str, Any]],
    usage: Any | None = None,
    request_id: str | None = None,
    session_id: str | None = None,
    stop_reason: str | None = None,
    artifact_root: str | None = None,
    input_artifact_hash: str | None = None,
    local_cache_hit: bool = False,
    batch_discount_applied: bool = False,
    usage_source: str | None = None,
) -> LLMUsageRecord:
    parsed = parse_usage(usage)
    source = usage_source or ("api_usage" if usage is not None else "manual_estimate")
    estimated_cost = estimate_cost_usd(
        provider=provider,
        model=model,
        input_tokens=parsed["input_tokens"],
        output_tokens=parsed["output_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_creation_input_tokens=parsed["cache_creation_input_tokens"],
        cache_ttl=parsed["cache_ttl"],
        batch_discount_applied=batch_discount_applied,
    )
    return LLMUsageRecord(
        timestamp=utc_now_iso(),
        provider=provider,
        tool_surface=tool_surface,
        agent_runtime=agent_runtime,
        workflow=workflow,
        stage=stage,
        model=model,
        max_tokens=max_tokens,
        input_tokens=parsed["input_tokens"],
        output_tokens=parsed["output_tokens"],
        cache_read_input_tokens=parsed["cache_read_input_tokens"],
        cache_creation_input_tokens=parsed["cache_creation_input_tokens"],
        cache_ttl=parsed["cache_ttl"],
        prompt_hash=hash_prompt(messages),
        input_artifact_hash=input_artifact_hash,
        request_id=request_id,
        session_id=session_id,
        stop_reason=stop_reason,
        artifact_root=artifact_root,
        api_cache_hit=parsed["cache_read_input_tokens"] > 0,
        local_cache_hit=local_cache_hit,
        batch_discount_applied=batch_discount_applied,
        usage_source=source,
        cost_formula=cost_formula_for_provider(provider),
        estimated_cost_usd=estimated_cost,
    )


def parse_usage(usage: Any | None) -> dict[str, Any]:
    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
            "cache_ttl": None,
        }
    return {
        "input_tokens": _usage_value(usage, "input_tokens", "prompt_tokens"),
        "output_tokens": _usage_value(usage, "output_tokens", "completion_tokens"),
        "cache_read_input_tokens": _usage_value(
            usage,
            "cache_read_input_tokens",
            "cache_read_tokens",
        ),
        "cache_creation_input_tokens": _usage_value(
            usage,
            "cache_creation_input_tokens",
            "cache_creation_tokens",
        ),
        "cache_ttl": _usage_text(usage, "cache_ttl"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM usage ledger 和 token dry-run 工具")
    subparsers = parser.add_subparsers(dest="command", required=True)

    route_parser = subparsers.add_parser("route", help="输出 workflow/stage 模型路由")
    route_parser.add_argument("--workflow", required=True)
    route_parser.add_argument("--stage", required=True)

    count_parser = subparsers.add_parser("count-dry-run", help="估算 messages JSON token")
    count_parser.add_argument("--workflow", required=True)
    count_parser.add_argument("--stage", required=True)
    count_parser.add_argument("--messages", required=True, help="messages JSON 文件路径")

    args = parser.parse_args(argv)
    route = resolve_llm_route(args.workflow, args.stage)
    if args.command == "route":
        print(json.dumps(asdict(route), ensure_ascii=False, indent=2))
        return 0

    messages_path = Path(args.messages)
    messages = json.loads(messages_path.read_text(encoding="utf-8-sig"))
    result = count_tokens_dry_run(messages, route=route)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0


def _month_from_timestamp(timestamp: str) -> str:
    try:
        return datetime.fromisoformat(timestamp).strftime("%Y-%m")
    except ValueError:
        return timestamp[:7]


def _anthropic_cache_write_multiplier(cache_ttl: str | None) -> float:
    if cache_ttl == "1h":
        return 2.0
    return 1.25


def _extract_input_tokens(value: Any) -> int:
    if isinstance(value, int):
        return value
    return _usage_value(value, "input_tokens")


def _usage_value(usage: Any, *keys: str) -> int:
    for key in keys:
        if isinstance(usage, dict) and key in usage:
            return int(usage[key] or 0)
        if hasattr(usage, key):
            return int(getattr(usage, key) or 0)
    return 0


def _usage_text(usage: Any, key: str) -> str | None:
    if isinstance(usage, dict):
        value = usage.get(key)
    else:
        value = getattr(usage, key, None)
    if value is None:
        return None
    return str(value)


def _estimate_tokens_locally(messages: list[dict[str, Any]]) -> int:
    payload = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return max(1, len(payload.encode("utf-8")) // 4)


if __name__ == "__main__":
    raise SystemExit(main())
