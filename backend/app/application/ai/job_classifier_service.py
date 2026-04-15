from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.application.ai.contracts import (
    AutomationPlatform,
    JobClassification,
    JobType,
    ProviderGenerateRequest,
    ProviderName,
)
from app.application.ai.errors import AIErrorCode, AIException
from app.application.ai.providers.base import AIProviderAdapter
from app.infrastructure.ai.providers.factory import build_provider_adapter

_CODE_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

_SYSTEM_PROMPT = (
    "You classify Upwork jobs into strict JSON output with no markdown. "
    "Return only the required schema fields."
)


class JobClassificationExecution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    classification: JobClassification
    provider: ProviderName | None = None
    model_name: str | None = None
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    latency_ms: int = Field(default=0, ge=0)
    source: str = Field(default="fallback", min_length=1, max_length=32)


def _fallback_classification(reason: str = "Classifier fallback") -> JobClassification:
    return JobClassification(
        job_type=JobType.OTHER,
        automation_platform=None,
        confidence="low",
        reasoning=reason,
    )


def _parse_json_payload(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    without_fences = _CODE_FENCE_PATTERN.sub("", stripped).strip()
    try:
        parsed = json.loads(without_fences)
    except json.JSONDecodeError as exc:
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Job classifier output is not valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise AIException(
            code=AIErrorCode.INVALID_OUTPUT,
            message="Job classifier output must be a JSON object",
        )
    return parsed


def _normalize_classification(payload: dict[str, Any]) -> JobClassification:
    classification = JobClassification.model_validate(payload)
    if classification.job_type != JobType.AUTOMATION:
        classification.automation_platform = None
    elif classification.automation_platform is None:
        classification.automation_platform = AutomationPlatform.UNKNOWN
    return classification


def _classify_by_rules(*, job_markdown: str, notes_markdown: str | None) -> JobClassification | None:
    text = f"{job_markdown}\n{notes_markdown or ''}".lower()

    if "n8n" in text:
        return JobClassification(
            job_type=JobType.AUTOMATION,
            automation_platform=AutomationPlatform.N8N,
            confidence="high",
            reasoning="Explicit n8n mention detected in job context.",
        )
    if "make.com" in text or "integromat" in text:
        return JobClassification(
            job_type=JobType.AUTOMATION,
            automation_platform=AutomationPlatform.MAKE,
            confidence="high",
            reasoning="Explicit Make.com mention detected in job context.",
        )
    if (
        "gohighlevel" in text
        or "highlevel" in text
        or "high level" in text
        or " ghl " in f" {text} "
        or "ghl workflow" in text
        or "ghl automation" in text
    ):
        return JobClassification(
            job_type=JobType.AUTOMATION,
            automation_platform=AutomationPlatform.GHL,
            confidence="high",
            reasoning="Explicit GoHighLevel / GHL mention detected in job context.",
        )
    if "zapier" in text:
        return JobClassification(
            job_type=JobType.AUTOMATION,
            automation_platform=AutomationPlatform.ZAPIER,
            confidence="high",
            reasoning="Explicit Zapier mention detected in job context.",
        )

    automation_keywords = ("automation", "workflow", "integrat", "webhook", "trigger", "api sync")
    if any(keyword in text for keyword in automation_keywords):
        return JobClassification(
            job_type=JobType.AUTOMATION,
            automation_platform=AutomationPlatform.UNKNOWN,
            confidence="medium",
            reasoning="Automation signals detected but platform not explicit.",
        )
    return None


def _build_user_prompt(*, job_markdown: str, notes_markdown: str | None) -> str:
    return (
        "Classify the job and return one JSON object with this exact schema:\n"
        "{\n"
        '  "job_type": "automation|ai_ml|web_dev|other",\n'
        '  "automation_platform": "n8n|make|ghl|zapier|other_automation|unknown|null",\n'
        '  "confidence": "high|medium|low",\n'
        '  "reasoning": "one sentence"\n'
        "}\n"
        "Rules:\n"
        "1) If n8n appears, choose automation+n8n.\n"
        "2) If Make.com / Integromat appears without n8n, choose automation+make.\n"
        "3) If GoHighLevel / GHL / HighLevel appears without n8n/Make, choose automation+ghl.\n"
        "4) If Zapier appears without any of the above, choose automation+zapier.\n"
        "5) Set automation_platform to null when job_type is not automation.\n"
        "6) Return JSON only.\n\n"
        f"Job markdown:\n{job_markdown}\n\n"
        f"User notes:\n{notes_markdown or 'None'}"
    )


async def classify_job(
    *,
    job_markdown: str,
    notes_markdown: str | None = None,
    provider: AIProviderAdapter | None = None,
    model_name: str = "gpt-5.4-mini",
) -> JobClassificationExecution:
    rule_based = _classify_by_rules(job_markdown=job_markdown, notes_markdown=notes_markdown)
    if rule_based is not None:
        return JobClassificationExecution(classification=rule_based, source="rules")

    adapter = provider or build_provider_adapter(ProviderName.OPENAI)
    request = ProviderGenerateRequest(
        prompt=_build_user_prompt(job_markdown=job_markdown, notes_markdown=notes_markdown),
        system_prompt=_SYSTEM_PROMPT,
        model_name=model_name,
        temperature=0.0,
        max_output_tokens=400,
        metadata={"task": "job_classification"},
    )

    try:
        result = await adapter.generate(request)
        payload = result.output_json if isinstance(result.output_json, dict) else _parse_json_payload(result.output_text or "")
        classification = _normalize_classification(payload)
        return JobClassificationExecution(
            classification=classification,
            provider=result.provider,
            model_name=result.model_name,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            latency_ms=result.latency_ms,
            source="llm",
        )
    except (AIException, ValidationError, ValueError):
        return JobClassificationExecution(classification=_fallback_classification(), source="fallback")
