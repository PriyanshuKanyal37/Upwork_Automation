import asyncio
import json

import httpx
import pytest

from app.application.ai.contracts import ProviderAgentRequest, ProviderGenerateRequest, ToolDefinition
from app.application.ai.errors import AIException
from app.infrastructure.ai.providers.anthropic_provider import AnthropicProviderAdapter
from app.infrastructure.observability.metrics import metrics_state


def test_anthropic_provider_normalizes_success_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/v1/messages")
        assert request.headers.get("x-api-key") == "test-key"
        assert request.headers.get("anthropic-version") == "2023-06-01"
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "claude-sonnet-4-5"
        return httpx.Response(
            200,
            json={
                "id": "msg_test",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "Generated n8n workflow explanation"}],
                "usage": {"input_tokens": 210, "output_tokens": 85},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = AnthropicProviderAdapter(
        api_key="test-key",
        base_url="https://api.anthropic.com",
        anthropic_version="2023-06-01",
        http_client=async_client,
    )

    request = ProviderGenerateRequest(
        model_name="claude-sonnet-4-5",
        prompt="Generate n8n workflow json",
        system_prompt="You are a workflow assistant.",
    )
    result = asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert result.output_text == "Generated n8n workflow explanation"
    assert result.input_tokens == 210
    assert result.output_tokens == 85


def test_anthropic_provider_maps_rate_limit_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = AnthropicProviderAdapter(
        api_key="test-key",
        base_url="https://api.anthropic.com",
        max_retries=0,
        http_client=async_client,
    )

    request = ProviderGenerateRequest(model_name="claude-sonnet-4-5", prompt="Generate workflow")
    with pytest.raises(AIException) as exc:
        asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert exc.value.code == "provider_rate_limited"
    assert exc.value.status_code == 429


def test_anthropic_provider_retries_on_server_error_and_succeeds() -> None:
    attempts = {"count": 0}

    def handler(_: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503, json={"error": {"message": "temporary outage"}})
        return httpx.Response(
            200,
            json={
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "Recovered workflow response"}],
                "usage": {"input_tokens": 120, "output_tokens": 40},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = AnthropicProviderAdapter(
        api_key="test-key",
        base_url="https://api.anthropic.com",
        max_retries=1,
        retry_backoff_seconds=0.0,
        http_client=async_client,
    )

    request = ProviderGenerateRequest(model_name="claude-sonnet-4-5", prompt="Generate workflow")
    result = asyncio.run(adapter.generate(request))
    asyncio.run(async_client.aclose())

    assert attempts["count"] == 2
    assert result.output_text == "Recovered workflow response"


def test_anthropic_provider_blocks_when_circuit_is_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.infrastructure.ai.providers import anthropic_provider as anthropic_provider_module

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
        anthropic_provider_module,
        "provider_health_manager",
        _OpenCircuitProviderHealth(),
    )
    adapter = AnthropicProviderAdapter(api_key="test-key", base_url="https://api.anthropic.com")

    request = ProviderGenerateRequest(model_name="claude-sonnet-4-5", prompt="Generate workflow")
    with pytest.raises(AIException) as exc:
        asyncio.run(adapter.generate(request))

    assert exc.value.code == "provider_unavailable"
    assert metrics_state.snapshot()["ai_provider_circuit_open_total"] == 1


def test_anthropic_provider_generate_with_tools_returns_tool_use() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body["model"] == "claude-sonnet-4-6"
        assert body["tools"][0]["name"] == "get_node_schema"
        return httpx.Response(
            200,
            json={
                "id": "msg_tool",
                "model": "claude-sonnet-4-6",
                "stop_reason": "tool_use",
                "content": [
                    {
                        "type": "tool_use",
                        "id": "toolu_01",
                        "name": "get_node_schema",
                        "input": {"type_string": "n8n-nodes-base.httpRequest"},
                    }
                ],
                "usage": {"input_tokens": 180, "output_tokens": 40},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = AnthropicProviderAdapter(
        api_key="test-key",
        base_url="https://api.anthropic.com",
        anthropic_version="2023-06-01",
        http_client=async_client,
    )

    request = ProviderAgentRequest(
        messages=[{"role": "user", "content": "Build workflow"}],
        system_prompt="You are an n8n agent.",
        model_name="claude-sonnet-4-6",
        tools=[
            ToolDefinition(
                name="get_node_schema",
                description="Get schema",
                input_schema={"type": "object", "properties": {"type_string": {"type": "string"}}},
            )
        ],
    )
    turn = asyncio.run(adapter.generate_with_tools(request))
    asyncio.run(async_client.aclose())

    assert turn.output_text is None
    assert turn.stop_reason == "tool_use"
    assert len(turn.tool_uses) == 1
    assert turn.tool_uses[0].name == "get_node_schema"
    assert turn.tool_uses[0].input["type_string"] == "n8n-nodes-base.httpRequest"
    assert turn.input_tokens == 180
    assert turn.output_tokens == 40


def test_anthropic_provider_generate_with_tools_returns_end_turn_text() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "msg_end",
                "model": "claude-sonnet-4-6",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "## WRITTEN PLAN\nShort plan"}],
                "usage": {"input_tokens": 150, "output_tokens": 70},
            },
        )

    transport = httpx.MockTransport(handler)
    async_client = httpx.AsyncClient(transport=transport, timeout=5.0)
    adapter = AnthropicProviderAdapter(
        api_key="test-key",
        base_url="https://api.anthropic.com",
        anthropic_version="2023-06-01",
        http_client=async_client,
    )

    request = ProviderAgentRequest(
        messages=[{"role": "user", "content": "Finalize workflow"}],
        system_prompt="You are an n8n agent.",
        model_name="claude-sonnet-4-6",
        tools=[],
    )
    turn = asyncio.run(adapter.generate_with_tools(request))
    asyncio.run(async_client.aclose())

    assert "WRITTEN PLAN" in (turn.output_text or "")
    assert turn.tool_uses == []
    assert turn.stop_reason == "end_turn"
    assert turn.input_tokens == 150
    assert turn.output_tokens == 70
