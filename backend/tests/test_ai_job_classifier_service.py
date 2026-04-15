import asyncio

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.job_classifier_service import classify_job
from app.application.ai.providers.base import AIProviderAdapter


class _FakeProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    def __init__(self, response: ProviderGenerateResult) -> None:
        self._response = response
        self.called = False
        self.last_request: ProviderGenerateRequest | None = None

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        self.called = True
        self.last_request = request
        return self._response


def test_classifier_prefers_rule_for_n8n() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text='{"job_type":"other","automation_platform":null,"confidence":"low","reasoning":"unused"}',
        )
    )
    result = asyncio.run(
        classify_job(
            job_markdown="Need an n8n expert for lead routing automation.",
            notes_markdown=None,
            provider=provider,
        )
    )

    assert result.classification.job_type == "automation"
    assert result.classification.automation_platform == "n8n"
    assert result.source == "rules"
    assert provider.called is False


def test_classifier_uses_llm_for_non_rule_text() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text=(
                '{"job_type":"web_dev","automation_platform":null,'
                '"confidence":"high","reasoning":"Frontend React implementation request."}'
            ),
            input_tokens=120,
            output_tokens=35,
            latency_ms=80,
        )
    )
    result = asyncio.run(
        classify_job(
            job_markdown="Build a React dashboard with authentication and charts.",
            notes_markdown=None,
            provider=provider,
        )
    )

    assert result.classification.job_type == "web_dev"
    assert result.classification.automation_platform is None
    assert result.source == "llm"
    assert provider.called is True
    assert provider.last_request is not None


def test_classifier_falls_back_on_invalid_llm_output() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text="not json",
        )
    )
    result = asyncio.run(
        classify_job(
            job_markdown="Need a custom internal portal.",
            notes_markdown=None,
            provider=provider,
        )
    )

    assert result.classification.job_type == "other"
    assert result.classification.automation_platform is None
    assert result.source == "fallback"
