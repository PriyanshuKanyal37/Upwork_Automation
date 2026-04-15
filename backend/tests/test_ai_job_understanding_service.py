import asyncio

import pytest

from app.application.ai.contracts import ProviderGenerateRequest, ProviderGenerateResult, ProviderName
from app.application.ai.errors import AIException
from app.application.ai.job_understanding_service import JobUnderstandingService
from app.application.ai.providers.base import AIProviderAdapter


class _FakeProvider(AIProviderAdapter):
    provider = ProviderName.OPENAI

    def __init__(self, response: ProviderGenerateResult) -> None:
        self._response = response
        self.last_request: ProviderGenerateRequest | None = None

    async def generate(self, request: ProviderGenerateRequest) -> ProviderGenerateResult:
        self.last_request = request
        return self._response


def test_job_understanding_service_parses_and_validates_json_text() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text=(
                '{"summary_short":"Automation build needed","deliverables_required":["proposal","workflow"],'
                '"screening_questions":["What is your n8n experience?"],"automation_platform_preference":"n8n",'
                '"constraints":{"tone":"professional"},"extraction_confidence":"high","missing_fields":[]}'
            ),
            input_tokens=50,
            output_tokens=20,
            latency_ms=100,
        )
    )
    service = JobUnderstandingService(provider_adapter=provider)

    result = asyncio.run(
        service.understand_job(
            job_markdown="Need n8n expert for CRM automation.",
            notes_markdown="User prefers concise responses.",
            profile_context="Automation engineer profile",
        )
    )

    assert result.contract.summary_short == "Automation build needed"
    assert result.contract.is_generation_allowed is True
    assert result.prompt_version == "job_understanding_v3"
    assert result.prompt_hash is not None
    assert provider.last_request is not None
    assert provider.last_request.model_name == "gpt-5.4-mini"


def test_job_understanding_service_blocks_on_low_confidence() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text=(
                '{"summary_short":"Unclear role","deliverables_required":[],"screening_questions":[],"automation_platform_preference":"unknown",'
                '"constraints":{},"extraction_confidence":"low","missing_fields":["scope","budget"]}'
            ),
        )
    )
    service = JobUnderstandingService(provider_adapter=provider)

    with pytest.raises(AIException) as exc:
        asyncio.run(service.understand_job(job_markdown="unclear text"))

    assert exc.value.code == "low_confidence_understanding"
    assert exc.value.status_code == 422


def test_job_understanding_service_rejects_non_json_output() -> None:
    provider = _FakeProvider(
        ProviderGenerateResult(
            provider=ProviderName.OPENAI,
            model_name="gpt-5.4-mini",
            output_text="This is not JSON.",
        )
    )
    service = JobUnderstandingService(provider_adapter=provider)

    with pytest.raises(AIException) as exc:
        asyncio.run(service.understand_job(job_markdown="Need workflow setup"))

    assert exc.value.code == "invalid_output"
    assert exc.value.status_code == 422
