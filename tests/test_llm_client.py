"""llm_client 通用 LLM provider 抽象测试"""

import pytest

from scripts.llm_client import LLMSettings, OpenAICompatibleClient, create_llm_client
from scripts.pipeline_utils import call_llm_with_retry


def test_settings_prefers_generic_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("LLM_API_KEY", "generic-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")

    settings = LLMSettings.from_env()

    assert settings.provider == "openai-compatible"
    assert settings.model == "deepseek-chat"
    assert settings.api_key == "generic-key"
    assert settings.base_url == "https://api.example.com/v1"


def test_settings_keeps_anthropic_backward_compatibility(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "anthropic-key")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://anthropic.example")

    settings = LLMSettings.from_env(provider="anthropic")

    assert settings.provider == "anthropic"
    assert settings.api_key == "anthropic-key"
    assert settings.base_url == "https://anthropic.example"


def test_create_llm_client_openai_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "model-x")
    monkeypatch.setenv("LLM_API_KEY", "key")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.com/v1")

    client = create_llm_client()

    assert isinstance(client, OpenAICompatibleClient)
    assert client.settings.model == "model-x"


def test_call_llm_with_retry_supports_generic_complete_client():
    class FakeClient:
        def complete(self, messages, model, max_tokens):
            assert model == "model-x"
            assert max_tokens == 123
            assert messages == [{"role": "user", "content": "hi"}]
            return "ok"

    result = call_llm_with_retry(
        FakeClient(),
        "model-x",
        [{"role": "user", "content": "hi"}],
        max_tokens=123,
    )

    assert result == "ok"
