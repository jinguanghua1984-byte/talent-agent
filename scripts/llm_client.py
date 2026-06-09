"""通用 LLM provider 客户端。

默认保留 Anthropic 兼容；新增 OpenAI-compatible HTTP provider，覆盖 OpenAI、
DeepSeek、Ollama、以及提供 /v1/chat/completions 的模型服务。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import request


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        model: str | None = None,
    ) -> "LLMSettings":
        resolved_provider = provider or os.environ.get("LLM_PROVIDER", "anthropic")
        resolved_model = model or os.environ.get("LLM_MODEL", "intelligence")

        if resolved_provider == "anthropic":
            api_key = os.environ.get("LLM_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")
            base_url = os.environ.get("LLM_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL")
        else:
            api_key = os.environ.get("LLM_API_KEY", "")
            base_url = os.environ.get("LLM_BASE_URL")

        if not api_key:
            raise EnvironmentError(
                "未设置 LLM_API_KEY；Anthropic 兼容模式也支持 ANTHROPIC_API_KEY"
            )

        return cls(
            provider=resolved_provider,
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
        )


@dataclass(frozen=True)
class StructuredOutputSchema:
    name: str
    schema: dict[str, Any]


class AnthropicMessagesClient:
    """Anthropic messages API 适配器。"""

    def __init__(self, settings: LLMSettings):
        import anthropic

        kwargs: dict[str, Any] = {"api_key": settings.api_key}
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self.settings = settings

    def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        *,
        workflow: str | None = None,
        stage: str | None = None,
        ledger: Any | None = None,
        artifact_root: str | None = None,
        input_artifact_hash: str | None = None,
        session_id: str | None = None,
        local_cache_hit: bool = False,
        batch_discount_applied: bool = False,
    ) -> str:
        resolved_model = model or self.settings.model
        response = self._client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
        )
        _record_usage_if_requested(
            ledger=ledger,
            provider="anthropic",
            tool_surface="claude_api",
            agent_runtime="script",
            workflow=workflow,
            stage=stage,
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
            usage=getattr(response, "usage", None),
            request_id=getattr(response, "id", None),
            session_id=session_id,
            stop_reason=getattr(response, "stop_reason", None),
            artifact_root=artifact_root,
            input_artifact_hash=input_artifact_hash,
            local_cache_hit=local_cache_hit,
            batch_discount_applied=batch_discount_applied,
        )
        return response.content[0].text

    def complete_structured(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        *,
        schema: StructuredOutputSchema,
        workflow: str | None = None,
        stage: str | None = None,
        ledger: Any | None = None,
        artifact_root: str | None = None,
        input_artifact_hash: str | None = None,
        session_id: str | None = None,
        local_cache_hit: bool = False,
        batch_discount_applied: bool = False,
    ) -> dict[str, Any]:
        resolved_model = model or self.settings.model
        response = self._client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
            output_format={
                "type": "json_schema",
                "name": schema.name,
                "schema": schema.schema,
            },
        )
        _record_usage_if_requested(
            ledger=ledger,
            provider="anthropic",
            tool_surface="claude_api",
            agent_runtime="script",
            workflow=workflow,
            stage=stage,
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
            usage=getattr(response, "usage", None),
            request_id=getattr(response, "id", None),
            session_id=session_id,
            stop_reason=getattr(response, "stop_reason", None),
            artifact_root=artifact_root,
            input_artifact_hash=input_artifact_hash,
            local_cache_hit=local_cache_hit,
            batch_discount_applied=batch_discount_applied,
        )
        return _loads_structured_response_text(response.content[0].text)


class OpenAICompatibleClient:
    """OpenAI-compatible /v1/chat/completions HTTP 客户端。"""

    def __init__(self, settings: LLMSettings):
        if not settings.base_url:
            raise EnvironmentError("openai-compatible provider 需要设置 LLM_BASE_URL")
        self.settings = settings

    def complete(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        *,
        workflow: str | None = None,
        stage: str | None = None,
        ledger: Any | None = None,
        artifact_root: str | None = None,
        input_artifact_hash: str | None = None,
        session_id: str | None = None,
        local_cache_hit: bool = False,
        batch_discount_applied: bool = False,
    ) -> str:
        resolved_model = model or self.settings.model
        payload = json.dumps({
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
        }).encode("utf-8")
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        req = request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = data["choices"][0]
        _record_usage_if_requested(
            ledger=ledger,
            provider=self.settings.provider,
            tool_surface="openai_api",
            agent_runtime="script",
            workflow=workflow,
            stage=stage,
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
            usage=data.get("usage"),
            request_id=data.get("id"),
            session_id=session_id,
            stop_reason=choice.get("finish_reason"),
            artifact_root=artifact_root,
            input_artifact_hash=input_artifact_hash,
            local_cache_hit=local_cache_hit,
            batch_discount_applied=batch_discount_applied,
        )
        return choice["message"]["content"]

    def complete_structured(
        self,
        messages: list[dict],
        model: str,
        max_tokens: int,
        *,
        schema: StructuredOutputSchema,
        workflow: str | None = None,
        stage: str | None = None,
        ledger: Any | None = None,
        artifact_root: str | None = None,
        input_artifact_hash: str | None = None,
        session_id: str | None = None,
        local_cache_hit: bool = False,
        batch_discount_applied: bool = False,
    ) -> dict[str, Any]:
        resolved_model = model or self.settings.model
        payload = json.dumps({
            "model": resolved_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema.name,
                    "schema": schema.schema,
                    "strict": True,
                },
            },
        }).encode("utf-8")
        url = self.settings.base_url.rstrip("/") + "/chat/completions"
        req = request.Request(
            url,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
        )
        with request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        choice = data["choices"][0]
        _record_usage_if_requested(
            ledger=ledger,
            provider=self.settings.provider,
            tool_surface="openai_api",
            agent_runtime="script",
            workflow=workflow,
            stage=stage,
            model=resolved_model,
            max_tokens=max_tokens,
            messages=messages,
            usage=data.get("usage"),
            request_id=data.get("id"),
            session_id=session_id,
            stop_reason=choice.get("finish_reason"),
            artifact_root=artifact_root,
            input_artifact_hash=input_artifact_hash,
            local_cache_hit=local_cache_hit,
            batch_discount_applied=batch_discount_applied,
        )
        return _loads_structured_response_text(choice["message"]["content"])


def create_llm_client(
    provider: str | None = None,
    model: str | None = None,
) -> AnthropicMessagesClient | OpenAICompatibleClient:
    settings = LLMSettings.from_env(provider=provider, model=model)
    if settings.provider == "anthropic":
        return AnthropicMessagesClient(settings)
    if settings.provider in {"openai-compatible", "openai"}:
        return OpenAICompatibleClient(settings)
    raise ValueError(f"不支持的 LLM_PROVIDER: {settings.provider!r}")


def _record_usage_if_requested(
    *,
    ledger: Any | None,
    provider: str,
    tool_surface: str,
    agent_runtime: str,
    workflow: str | None,
    stage: str | None,
    model: str,
    max_tokens: int,
    messages: list[dict],
    usage: Any | None,
    request_id: str | None,
    session_id: str | None,
    stop_reason: str | None,
    artifact_root: str | None,
    input_artifact_hash: str | None,
    local_cache_hit: bool,
    batch_discount_applied: bool,
) -> None:
    resolved_ledger = ledger or _ledger_from_env()
    if resolved_ledger is None or workflow is None or stage is None:
        return

    from scripts.llm_usage import usage_record_from_response

    record = usage_record_from_response(
        provider=provider,
        tool_surface=tool_surface,
        agent_runtime=agent_runtime,
        workflow=workflow,
        stage=stage,
        model=model,
        max_tokens=max_tokens,
        messages=messages,
        usage=usage,
        request_id=request_id,
        session_id=session_id,
        stop_reason=stop_reason,
        artifact_root=artifact_root,
        input_artifact_hash=input_artifact_hash,
        local_cache_hit=local_cache_hit,
        batch_discount_applied=batch_discount_applied,
    )
    resolved_ledger.append(record)


def _ledger_from_env() -> Any | None:
    if os.environ.get("LLM_USAGE_LEDGER") not in {"1", "true", "TRUE", "yes"}:
        return None

    from scripts.llm_usage import LLMUsageLedger

    output_dir = os.environ.get("LLM_USAGE_LEDGER_DIR")
    if output_dir:
        return LLMUsageLedger(Path(output_dir))
    return LLMUsageLedger()


def _loads_structured_response_text(text: str) -> dict[str, Any]:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("structured output response must be a JSON object")
    return payload
