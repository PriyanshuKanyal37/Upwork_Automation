from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_generation_run import JobGenerationRun
from app.infrastructure.database.models.job_output import JobOutput


def _to_decimal(value: Decimal | float | int | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


async def _get_or_create_job_output(*, session: AsyncSession, job_id: UUID) -> JobOutput:
    job = await session.get(Job, job_id)
    if job is None:
        raise AppException(status_code=404, code="job_not_found", message="Job not found")

    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job_id))
    if output is not None:
        return output
    output = JobOutput(job_id=job_id)
    session.add(output)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(status_code=404, code="job_not_found", message="Job not found") from exc
    return output


def _summarize_usage(
    *,
    existing_summary: dict[str, Any],
    success: bool,
    input_tokens: int,
    output_tokens: int,
    estimated_cost_usd: Decimal,
) -> dict[str, Any]:
    summary = {
        "total_calls": int(existing_summary.get("total_calls", 0)),
        "successful_calls": int(existing_summary.get("successful_calls", 0)),
        "failed_calls": int(existing_summary.get("failed_calls", 0)),
        "total_input_tokens": int(existing_summary.get("total_input_tokens", 0)),
        "total_output_tokens": int(existing_summary.get("total_output_tokens", 0)),
        "total_estimated_cost_usd": float(existing_summary.get("total_estimated_cost_usd", 0.0)),
    }

    summary["total_calls"] += 1
    if success:
        summary["successful_calls"] += 1
    else:
        summary["failed_calls"] += 1
    summary["total_input_tokens"] += max(0, input_tokens)
    summary["total_output_tokens"] += max(0, output_tokens)
    summary["total_estimated_cost_usd"] += float(estimated_cost_usd)
    summary["last_updated_at"] = datetime.now(UTC).isoformat()
    return summary


async def create_generation_run(
    *,
    session: AsyncSession,
    job_id: UUID,
    user_id: UUID,
    run_type: str = "generate",
    artifact_type: str | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    routing_mode: str | None = None,
    prompt_version: str | None = None,
    prompt_hash: str | None = None,
) -> JobGenerationRun:
    run = JobGenerationRun(
        job_id=job_id,
        user_id=user_id,
        run_type=run_type,
        artifact_type=artifact_type,
        provider=provider,
        model_name=model_name,
        routing_mode=routing_mode,
        prompt_version=prompt_version,
        prompt_hash=prompt_hash,
        status="running",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    session.add(run)
    await session.commit()
    return run


async def mark_generation_run_success(
    *,
    session: AsyncSession,
    run_id: UUID,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: Decimal | float | int | str | None = None,
    latency_ms: int | None = None,
    retry_count: int = 0,
) -> JobGenerationRun:
    run = await session.get(JobGenerationRun, run_id)
    if run is None:
        raise ValueError("generation run not found")

    cost_value = _to_decimal(estimated_cost_usd)
    run.status = "success"
    run.input_tokens = max(0, input_tokens)
    run.output_tokens = max(0, output_tokens)
    run.estimated_cost_usd = cost_value
    run.latency_ms = latency_ms
    run.retry_count = max(0, retry_count)
    run.failure_code = None
    run.failure_message = None
    run.updated_at = datetime.now(UTC)

    try:
        output = await _get_or_create_job_output(session=session, job_id=run.job_id)
        output.ai_usage_summary_json = _summarize_usage(
            existing_summary=output.ai_usage_summary_json or {},
            success=True,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            estimated_cost_usd=cost_value,
        )
    except AppException as exc:
        if exc.code != "job_not_found":
            raise

    await session.commit()
    return run


async def mark_generation_run_failed(
    *,
    session: AsyncSession,
    run_id: UUID,
    failure_code: str,
    failure_message: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: Decimal | float | int | str | None = None,
    latency_ms: int | None = None,
    retry_count: int = 0,
) -> JobGenerationRun:
    run = await session.get(JobGenerationRun, run_id)
    if run is None:
        raise ValueError("generation run not found")

    cost_value = _to_decimal(estimated_cost_usd)
    run.status = "failed"
    run.failure_code = failure_code
    run.failure_message = failure_message
    run.input_tokens = max(0, input_tokens)
    run.output_tokens = max(0, output_tokens)
    run.estimated_cost_usd = cost_value
    run.latency_ms = latency_ms
    run.retry_count = max(0, retry_count)
    run.updated_at = datetime.now(UTC)

    try:
        output = await _get_or_create_job_output(session=session, job_id=run.job_id)
        output.ai_usage_summary_json = _summarize_usage(
            existing_summary=output.ai_usage_summary_json or {},
            success=False,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            estimated_cost_usd=cost_value,
        )
    except AppException as exc:
        if exc.code != "job_not_found":
            raise

    await session.commit()
    return run


async def append_artifact_version(
    *,
    session: AsyncSession,
    job_id: UUID,
    artifact_type: str,
    content_text: str | None = None,
    content_json: dict[str, Any] | list[Any] | None = None,
    instruction: str | None = None,
    generation_run_id: UUID | None = None,
    is_selected: bool = False,
) -> dict[str, Any]:
    output = await _get_or_create_job_output(session=session, job_id=job_id)
    versions = list(output.artifact_versions_json or [])
    existing_for_artifact = [item for item in versions if item.get("artifact_type") == artifact_type]
    latest_version = max((int(item.get("version_number", 0)) for item in existing_for_artifact), default=0)
    next_version = latest_version + 1

    record = {
        "artifact_type": artifact_type,
        "version_number": next_version,
        "content_text": content_text,
        "content_json": content_json,
        "instruction": instruction,
        "generation_run_id": str(generation_run_id) if generation_run_id else None,
        "is_selected": is_selected,
        "created_at": datetime.now(UTC).isoformat(),
    }
    versions.append(record)
    output.artifact_versions_json = versions

    await session.commit()
    await session.refresh(output)
    return record
