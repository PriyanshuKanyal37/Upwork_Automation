from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.job.service import get_job_for_user, serialize_job, find_duplicate_names
from app.application.output.service import serialize_job_output
from app.infrastructure.audit.events import log_status_change
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.job_output import JobOutput
from app.infrastructure.errors.exceptions import AppException

_ALLOWED_JOB_STATUSES = frozenset(
    {
        "draft",
        "duplicate_notified",
        "clarification",
        "processing",
        "ready",
        "failed",
        "closed",
        "sent",
    }
)

_ALLOWED_JOB_OUTCOMES = frozenset(
    {
        "sent",
        "not_sent",
        "hired",
    }
)


def _normalize_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in _ALLOWED_JOB_STATUSES:
        raise AppException(
            status_code=422,
            code="invalid_job_status",
            message=f"Job status '{status}' is not supported",
            details={"allowed_statuses": sorted(_ALLOWED_JOB_STATUSES)},
        )
    return normalized


def _normalize_outcome(outcome: str) -> str:
    normalized = outcome.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized not in _ALLOWED_JOB_OUTCOMES:
        raise AppException(
            status_code=422,
            code="invalid_job_outcome",
            message=f"Job outcome '{outcome}' is not supported",
            details={"allowed_outcomes": sorted(_ALLOWED_JOB_OUTCOMES)},
        )
    return normalized


def _list_query(*, user_id: UUID) -> Select[tuple[Job]]:
    return select(Job).where(Job.user_id == user_id)


async def list_jobs_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    status: str | None,
    outcome: str | None,
    is_submitted_to_upwork: bool | None,
    project_id: UUID | None,
    limit: int,
    offset: int,
) -> list[Job]:
    query = _list_query(user_id=user_id)
    if status:
        query = query.where(Job.status == _normalize_status(status))
    if outcome:
        query = query.where(Job.outcome == _normalize_outcome(outcome))
    if is_submitted_to_upwork is not None:
        query = query.where(Job.is_submitted_to_upwork == is_submitted_to_upwork)
    if project_id is not None:
        query = query.where(Job.project_id == project_id)
    rows = await session.scalars(
        query.order_by(Job.created_at.desc()).offset(offset).limit(limit)
    )
    return list(rows)


async def get_job_detail_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
) -> tuple[Job, JobOutput | None, list[str]]:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    output = await session.scalar(select(JobOutput).where(JobOutput.job_id == job.id))
    
    duplicate_names = []
    if job.status == "duplicate_notified":
        duplicate_names = await find_duplicate_names(
            session=session,
            current_user_id=user_id,
            upwork_job_id=job.upwork_job_id,
            canonical_url=job.job_url,
        )
        
    return job, output, duplicate_names


async def update_job_status_and_outcome(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    status: str | None,
    outcome: str | None,
) -> Job:
    if status is None and outcome is None:
        raise AppException(
            status_code=422,
            code="no_job_fields",
            message="At least one field (status/outcome) must be provided",
        )
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    previous_status = job.status
    if status is not None:
        job.status = _normalize_status(status)
    if outcome is not None:
        job.outcome = _normalize_outcome(outcome)
    await session.commit()
    await session.refresh(job)
    if status is not None and previous_status != job.status:
        log_status_change(
            entity="job",
            entity_id=job.id,
            user_id=job.user_id,
            previous_status=previous_status,
            next_status=job.status,
            source="update_job_status_and_outcome",
            metadata={"outcome": job.outcome},
        )
    return job


async def update_job_submission_flags(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    is_submitted_to_upwork: bool,
    submitted_at: datetime | None,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    job.is_submitted_to_upwork = is_submitted_to_upwork
    if is_submitted_to_upwork:
        job.submitted_at = submitted_at or datetime.now(UTC)
    else:
        if submitted_at is not None:
            raise AppException(
                status_code=422,
                code="invalid_submitted_at",
                message="submitted_at cannot be set when is_submitted_to_upwork is false",
            )
        job.submitted_at = None
    await session.commit()
    await session.refresh(job)
    return job


def serialize_job_detail(*, job: Job, output: JobOutput | None, duplicate_names: list[str]) -> dict[str, Any]:
    return {
        "job": serialize_job(job),
        "output": serialize_job_output(output) if output else None,
        "duplicates": duplicate_names,
    }


async def delete_job_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
) -> None:
    """Hard-delete a job (and its cascaded output rows) owned by user_id."""
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    await session.delete(job)
    await session.commit()
