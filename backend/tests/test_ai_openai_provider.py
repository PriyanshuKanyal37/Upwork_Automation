import asyncio
import json

import httpx
import pytest

from app.application.ai.contracts import ProviderGenerateRequest
from app.application.ai.errors import AIException
from app.infrastructure.ai.providers.openai_provider import OpenAIProviderAdapter
from app.infrastructure.observability.metrics import metrics_state


def test_openai_provider_normalizes_success_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers.get("Authorization") == "Bearer test-key"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "gpt-5.4-mini"
        assert body["max_completion_tokens"] == 123
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl_test",
                "model": "gpt-5.4-mini",
                "choices": [{"message": {"content": "Generated proposal text"}}],
                "usage": {"prompt_tokens": 120, "completion_tokens": 45},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = OpenAIProviderAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        http_client=async_client,
    )

    request = ProviderGenerateRequest(
        model_name="gpt-5.4-mini",
        prompt="Generate proposal",
        system_prompt="You are a helpful assistant.",
        max_output_tokens=123,
    )
    result = asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert result.output_text == "Generated proposal text"
    assert result.input_tokens == 120
    assert result.output_tokens == 45


def test_openai_provider_maps_rate_limit_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = OpenAIProviderAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        max_retries=0,
        http_client=async_client,
    )

    request = ProviderGenerateRequest(model_name="gpt-5.4-mini", prompt="Generate proposal")
    with pytest.raises(AIException) as exc:
        asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert exc.value.code == "provider_rate_limited"
    assert exc.value.status_code == 429


def test_openai_provider_retries_on_server_error_and_succeeds() -> None:
    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": {"message": "temporary outage"}})
        return httpx.Response(
            200,
            json={
                "model": "gpt-5.4-mini",
                "choices": [{"message": {"content": "Recovered response"}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = OpenAIProviderAdapter(
        api_key="test-key",
        base_url="https://api.openai.com/v1",
        max_retries=1,
        retry_backoff_seconds=0.0,
        http_client=async_client,
    )

    request = ProviderGenerateRequest(model_name="gpt-5.4-mini", prompt="Generate proposal")
    result = asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert attempts["count"] == 2
    assert result.output_text == "Recovered response"


def test_openai_provider_blocks_when_circuit_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.ai.providers import openai_provider as openai_provider_module

    class _OpenCircuitProviderHealth:
        def is_circuit_open(self, *, provider: str, model_name: str | None) -> bool:  # noqa: ARG002
            return True

        def record_success(self, *, provider: str, model_name: str | None) -> None:  # noqa: ARG002
            return

        def record_failure(
            self,
            *,
            provider: str,  # noqa: ARG002
            model_name: str | None,  # noqa: ARG002
            error_code: str,  # noqa: ARG002
        ) -> bool:
            return False

    metrics_state.clear()
    monkeypatch.setattr(
        openai_provider_module,
        "provider_health_manager",
        _OpenCircuitProviderHealth(),
    )
    adapter = OpenAIProviderAdapter(api_key="test-key", base_url="https://api.openai.com/v1")

    request = ProviderGenerateRequest(model_name="gpt-5.4-mini", prompt="Generate proposal")
    with pytest.raises(AIException) as exc:
        asyncio.run(adapter.generate(request))

    assert exc.value.code == "provider_unavailable"
    assert metrics_state.snapshot()["ai_provider_circuit_open_total"] == 1
