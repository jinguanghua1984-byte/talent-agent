"""通用 LLM provider 客户端。

默认保留 Anthropic 兼容；新增 OpenAI-compatible HTTP provider，覆盖 OpenAI、
DeepSeek、Ollama、以及提供 /v1/chat/completions 的模型服务。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
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


class AnthropicMessagesClient:
    """Anthropic messages API 适配器。"""

    def __init__(self, settings: LLMSettings):
        import anthropic

        kwargs: dict[str, Any] = {"api_key": settings.api_key}
        if settings.base_url:
            kwargs["base_url"] = settings.base_url
        self._client = anthropic.Anthropic(**kwargs)
        self.settings = settings

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        response = self._client.messages.create(
            model=model or self.settings.model,
            max_tokens=max_tokens,
            messages=messages,
        )
        return response.content[0].text


class OpenAICompatibleClient:
    """OpenAI-compatible /v1/chat/completions HTTP 客户端。"""

    def __init__(self, settings: LLMSettings):
        if not settings.base_url:
            raise EnvironmentError("openai-compatible provider 需要设置 LLM_BASE_URL")
        self.settings = settings

    def complete(self, messages: list[dict], model: str, max_tokens: int) -> str:
        payload = json.dumps({
            "model": model or self.settings.model,
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
        return data["choices"][0]["message"]["content"]


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
