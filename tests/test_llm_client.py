"""llm_client 通用 LLM provider 抽象测试"""

import json
from types import SimpleNamespace

import pytest

from scripts.llm_client import LLMSettings, OpenAICompatibleClient, create_llm_client
from scripts.llm_usage import LLMUsageLedger
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


def test_call_llm_with_retry_forwards_usage_metadata_to_complete_client():
    ledger = object()

    class FakeClient:
        def __init__(self):
            self.call: dict | None = None

        def complete(self, messages, model, max_tokens, **kwargs):
            self.call = {
                "messages": messages,
                "model": model,
                "max_tokens": max_tokens,
                "kwargs": kwargs,
            }
            return "ok"

    client = FakeClient()

    result = call_llm_with_retry(
        client,
        "model-x",
        [{"role": "user", "content": "hi"}],
        max_tokens=123,
        workflow="jd-feedback",
        stage="parse-low-confidence-batch",
        ledger=ledger,
        artifact_root="data/output/run",
        input_artifact_hash="hash",
        session_id="session-1",
        batch_discount_applied=True,
    )

    assert result == "ok"
    assert client.call == {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "model-x",
        "max_tokens": 123,
        "kwargs": {
            "workflow": "jd-feedback",
            "stage": "parse-low-confidence-batch",
            "ledger": ledger,
            "artifact_root": "data/output/run",
            "input_artifact_hash": "hash",
            "session_id": "session-1",
            "local_cache_hit": False,
            "batch_discount_applied": True,
        },
    }


def test_anthropic_client_records_api_usage_when_ledger_is_provided(tmp_path):
    class FakeMessages:
        def create(self, **kwargs):
            assert kwargs["model"] == "claude-sonnet-4-6"
            assert kwargs["max_tokens"] == 16000
            return SimpleNamespace(
                id="msg_1",
                stop_reason="end_turn",
                content=[SimpleNamespace(text="ok")],
                usage=SimpleNamespace(
                    input_tokens=100,
                    output_tokens=5,
                    cache_read_input_tokens=20,
                    cache_creation_input_tokens=10,
                    cache_ttl="5m",
                ),
            )

    client = object.__new__(__import__("scripts.llm_client").llm_client.AnthropicMessagesClient)
    client.settings = LLMSettings(provider="anthropic", model="claude-sonnet-4-6", api_key="key")
    client._client = SimpleNamespace(messages=FakeMessages())

    result = client.complete(
        [{"role": "user", "content": "hi"}],
        model="claude-sonnet-4-6",
        max_tokens=16000,
        workflow="jd-talent-delivery",
        stage="detailed-rank",
        ledger=LLMUsageLedger(tmp_path),
        artifact_root="data/output/run-1",
    )

    assert result == "ok"
    rows = [
        json.loads(line)
        for line in (tmp_path / "llm-usage-2026-06.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 1
    assert rows[0]["provider"] == "anthropic"
    assert rows[0]["tool_surface"] == "claude_api"
    assert rows[0]["workflow"] == "jd-talent-delivery"
    assert rows[0]["stage"] == "detailed-rank"
    assert rows[0]["input_tokens"] == 100
    assert rows[0]["output_tokens"] == 5
    assert rows[0]["cache_read_input_tokens"] == 20
    assert rows[0]["cache_creation_input_tokens"] == 10
    assert rows[0]["api_cache_hit"] is True
    assert rows[0]["request_id"] == "msg_1"
    assert rows[0]["stop_reason"] == "end_turn"
    assert rows[0]["usage_source"] == "api_usage"
    assert rows[0]["cost_formula"] == "anthropic_messages_v1"


def test_openai_compatible_client_records_api_usage_without_anthropic_cache_fields(
    tmp_path,
    monkeypatch,
):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self):
            return json.dumps({
                "id": "chatcmpl_1",
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1000, "completion_tokens": 20},
            }).encode("utf-8")

    monkeypatch.setattr("scripts.llm_client.request.urlopen", lambda req, timeout: FakeResponse())
    settings = LLMSettings(
        provider="openai-compatible",
        model="deepseek-chat",
        api_key="key",
        base_url="https://api.example.com/v1",
    )
    client = OpenAICompatibleClient(settings)

    result = client.complete(
        [{"role": "user", "content": "hi"}],
        model="deepseek-chat",
        max_tokens=512,
        workflow="jd-feedback",
        stage="parse-low-confidence-batch",
        ledger=LLMUsageLedger(tmp_path),
    )

    assert result == "ok"
    row = json.loads((tmp_path / "llm-usage-2026-06.jsonl").read_text(encoding="utf-8"))
    assert row["provider"] == "openai-compatible"
    assert row["tool_surface"] == "openai_api"
    assert row["model"] == "deepseek-chat"
    assert row["input_tokens"] == 1000
    assert row["output_tokens"] == 20
    assert row["cache_read_input_tokens"] == 0
    assert row["cache_creation_input_tokens"] == 0
    assert row["api_cache_hit"] is False
    assert row["request_id"] == "chatcmpl_1"
    assert row["stop_reason"] == "stop"
    assert row["cost_formula"] == "openai_compatible_chat_v1"
