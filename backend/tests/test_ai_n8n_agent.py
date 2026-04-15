import asyncio
import json
from typing import Any

from app.application.ai.agents.n8n_agent import run_n8n_agent
from app.application.ai.contracts import (
    ArtifactType,
    ProviderAgentTurnResult,
    ProviderGenerateResult,
    ProviderName,
    ToolUse,
)
from app.application.ai.errors import AIException


def _valid_workflow_json() -> dict[str, Any]:
    return {
        "nodes": [
            {
                "id": "1",
                "name": "Webhook",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2.1,
                "position": [260, 260],
            },
            {
                "id": "2",
                "name": "HTTP Request",
                "type": "n8n-nodes-base.httpRequest",
                "typeVersion": 4.4,
                "position": [520, 260],
            },
        ],
        "connections": {
            "Webhook": {
                "main": [
                    [
                        {
                            "node": "HTTP Request",
                            "type": "main",
                            "index": 0,
                        }
                    ]
                ]
            }
        },
        "settings": {"executionOrder": "v1"},
    }


class _FakeAgentProvider:
    def __init__(self) -> None:
        self.iteration = 0
        self.generate_called = False

    async def generate_with_tools(self, request):  # noqa: ANN001
        self.iteration += 1
        if self.iteration == 1:
            return ProviderAgentTurnResult(
                provider=ProviderName.ANTHROPIC,
                model_name="claude-sonnet-4-6",
                output_text=None,
                tool_uses=[
                    ToolUse(
                        id="toolu_1",
                        name="get_node_schema",
                        input={"type_string": "n8n-nodes-base.httpRequest"},
                    )
                ],
                stop_reason="tool_use",
                input_tokens=160,
                output_tokens=30,
                latency_ms=12,
            )
        workflow = _valid_workflow_json()
        return ProviderAgentTurnResult(
            provider=ProviderName.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_text=None,
            tool_uses=[
                ToolUse(
                    id="toolu_2",
                    name="finalize_workflow",
                    input={
                        "workflow_json": workflow,
                        "workflow_explanation": "Use webhook then HTTP request.",
                    },
                )
            ],
            stop_reason="tool_use",
            input_tokens=220,
            output_tokens=120,
            latency_ms=18,
        )

    async def generate(self, request):  # noqa: ANN001
        self.generate_called = True
        return ProviderGenerateResult(
            provider=ProviderName.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_text=json.dumps(_valid_workflow_json()),
            input_tokens=100,
            output_tokens=200,
            latency_ms=10,
        )


class _FallbackOnlyProvider:
    async def generate_with_tools(self, request):  # noqa: ANN001
        return (None, [], "max_tokens")

    async def generate(self, request):  # noqa: ANN001
        return ProviderGenerateResult(
            provider=ProviderName.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_text=json.dumps(_valid_workflow_json()),
            input_tokens=120,
            output_tokens=240,
            latency_ms=15,
        )


def test_n8n_agent_tool_loop_end_turn_returns_payload() -> None:
    provider = _FakeAgentProvider()
    payload = asyncio.run(
        run_n8n_agent(
            job_context={"job_markdown": "Need n8n webhook to send API requests."},
            provider=provider,  # type: ignore[arg-type]
            max_iterations=3,
        )
    )

    assert payload.artifact_type == ArtifactType.WORKFLOW
    assert payload.content_text == "Use webhook then HTTP request."
    assert isinstance(payload.content_json, dict)
    assert payload.content_json["settings"]["executionOrder"] == "v1"
    assert provider.iteration == 2
    usage = payload.metadata.get("usage", {})
    assert usage["input_tokens"] == 380
    assert usage["output_tokens"] == 150
    assert isinstance(payload.metadata.get("agent_trace"), list)


def test_n8n_agent_raises_after_iteration_limit_when_not_finalized() -> None:
    provider = _FallbackOnlyProvider()

    try:
        asyncio.run(
            run_n8n_agent(
                job_context={"job_markdown": "Need n8n scheduled reporting workflow."},
                provider=provider,  # type: ignore[arg-type]
                max_iterations=1,
            )
        )
        raise AssertionError("Expected AIException for non-finalized workflow")
    except AIException as exc:
        assert exc.code == "invalid_output"
