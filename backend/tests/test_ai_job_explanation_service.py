import asyncio

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.job_explanation_service import explain_job_markdown
from app.application.ai.providers.base import AIProviderAdapter


class _FakeProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:  # noqa: ARG002
        return ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text=(
                "## Job understanding\n"
                "The client wants an automation workflow for lead capture and CRM updates.\n\n"
                "- Capture leads from form/webhook input\n"
                "- Validate and transform data\n"
                "- Sync records to CRM with retries and alerts\n"
                "- Clarify edge cases and ownership before build"
            ),
            input_tokens=40,
            output_tokens=30,
            latency_ms=70,
        )


class _FailingProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:  # noqa: ARG002
        raise RuntimeError("provider unavailable")


def test_explain_job_markdown_normalizes_ai_output() -> None:
    execution = asyncio.run(
        explain_job_markdown(
            job_markdown="Need n8n workflow automation for lead intake and CRM sync.",
            notes_markdown="Client prefers simple and reliable flow.",
            provider=_FakeProvider(),
        )
    )

    assert execution.used_fallback is False
    assert "The client wants an automation workflow" in execution.explanation
    assert "```" not in execution.explanation


def test_explain_job_markdown_falls_back_when_provider_fails() -> None:
    execution = asyncio.run(
        explain_job_markdown(
            job_markdown="Build automation with webhook trigger and CRM update.",
            notes_markdown=None,
            provider=_FailingProvider(),
        )
    )

    assert execution.used_fallback is True
    assert "🧠 Quick summary:" in execution.explanation
    assert "🎯 Client goal:" in execution.explanation
