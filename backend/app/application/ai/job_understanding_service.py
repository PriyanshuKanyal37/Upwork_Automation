from __future__ import annotations

import json
import re

from pydantic import ValidationError

from app.application.ai.contracts import (
    JobUnderstandingContract,
    JobUnderstandingExecution,
    ProviderGenerateRequest,
    RouteTask,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.prompt_builder import build_prompt
from app.application.ai.providers.base import AIProviderAdapter
from app.application.ai.routing import get_route_for_task
from app.infrastructure.ai.providers.factory import build_provider_adapter

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)


def _parse_json_payload(raw_text: str) -> dict:
    stripped = raw_text.strip()
    without_fences = _CODE_FENCE_PATTERN.sub("", stripped).strip()
    try:
        parsed = json.loads(without_fences)
    except json.JSONDecodeError as exc:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Job understanding model output is not valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Job understanding model output must be a JSON object",
        )
    return parsed


class JobUnderstandingService:
    def __init__(self, *, provider_adapter: AIProviderAdapter | None = None) -> None:
        self._provider_adapter = provider_adapter

    async def understand_job(
        self,
        *,
        job_markdown: str,
        notes_markdown: str | None = None,
        profile_context: str | None = None,
    ) -> JobUnderstandingExecution:
        route = get_route_for_task(RouteTask.JOB_UNDERSTANDING)
        provider = self._provider_adapter or build_provider_adapter(route.primary_provider)
        built_prompt = build_prompt(
            task=RouteTask.JOB_UNDERSTANDING,
            context={
                "job_markdown": job_markdown,
                "notes_markdown": notes_markdown,
                "profile_context": profile_context,
            },
        )
        provider_request = ProviderGenerateRequest(
            prompt=built_prompt.user_prompt,
            system_prompt=built_prompt.system_prompt,
            model_name=route.primary_model,
            temperature=0.0,
            max_output_tokens=1200,
            metadata={"task": RouteTask.JOB_UNDERSTANDING.value},
        )
        provider_result = await provider.generate(provider_request)
        payload = (
            provider_result.output_json
            if isinstance(provider_result.output_json, dict)
            else _parse_json_payload(provider_result.output_text or "")
        )
        try:
            contract = JobUnderstandingContract.model_validate(payload)
        except ValidationError as exc:
            raise AIException(
                code=AIErrorCode.INVALID_OUTPUT,
                message="Job understanding output does not match required schema",
                details={"validation_errors": exc.errors()},
            ) from exc

        if not contract.is_generation_allowed:
            raise AIException(
                code=AIErrorCode.LOW_CONFIDENCE_UNDERSTANDING,
                message="Job understanding confidence is too low for generation",
                details={"missing_fields": contract.missing_fields},
            )

        return JobUnderstandingExecution(
            contract=contract,
            provider=provider_result.provider,
            model_name=provider_result.model_name,
            input_tokens=provider_result.input_tokens,
            output_tokens=provider_result.output_tokens,
            latency_ms=provider_result.latency_ms,
            prompt_version=built_prompt.prompt_version,
            prompt_hash=built_prompt.prompt_hash,
        )
