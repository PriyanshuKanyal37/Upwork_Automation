from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ai.errors import AIErrorCode, AIException
from app.infrastructure.config.settings import get_settings


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str | None = None
    details: dict[str, str | int | float] | None = None


def _estimate_input_tokens(job_markdown: str, notes_markdown: str | None, instruction: str | None) -> int:
    source = f"{job_markdown}\n{notes_markdown or ''}\n{instruction or ''}"
    return max(1, len(source) // 4)


def estimate_output_token_budget(*, artifact_count: int) -> int:
    # Conservative first-pass output envelope used only for policy gating.
    return max(500, artifact_count * 1200)


async def enforce_generation_policy(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_markdown: str,
    notes_markdown: str | None,
    instruction: str | None,
    artifact_count_hint: int,
) -> PolicyDecision:
    settings = get_settings()
    estimated_input_tokens = _estimate_input_tokens(job_markdown, notes_markdown, instruction)
    if estimated_input_tokens > settings.ai_max_input_tokens_per_run:
        return PolicyDecision(
            allowed=False,
            reason=AIErrorCode.BUDGET_EXCEEDED.value,
            details={
                "estimated_input_tokens": estimated_input_tokens,
                "limit": settings.ai_max_input_tokens_per_run,
            },
        )

    estimated_output_tokens = estimate_output_token_budget(artifact_count=artifact_count_hint)
    if estimated_output_tokens > settings.ai_max_output_tokens_per_run:
        return PolicyDecision(
            allowed=False,
            reason=AIErrorCode.BUDGET_EXCEEDED.value,
            details={
                "estimated_output_tokens": estimated_output_tokens,
                "limit": settings.ai_max_output_tokens_per_run,
            },
        )

    return PolicyDecision(
        allowed=True,
        details={
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
        },
    )


def assert_output_token_budget(*, total_output_tokens: int) -> None:
    settings = get_settings()
    if total_output_tokens > settings.ai_max_output_tokens_per_run:
        raise AIException(
            code=AIErrorCode.BUDGET_EXCEEDED,
            message="Output token budget exceeded for generation run",
            details={
                "total_output_tokens": total_output_tokens,
                "limit": settings.ai_max_output_tokens_per_run,
            },
        )

