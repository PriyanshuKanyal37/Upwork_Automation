from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.job.history_service import (
    delete_job_for_user,
    get_job_detail_for_user,
    list_jobs_for_user,
    serialize_job_detail,
    update_job_status_and_outcome,
    update_job_submission_flags,
)
from app.application.ai.orchestrator_service import (
    approve_output_versions,
    list_generation_runs_for_job,
    run_generation_pipeline,
    serialize_generation_run,
)
from app.application.connector.publish_service import publish_job_outputs
from app.application.job.service import (
    create_job_intake,
    execute_job_extraction,
    get_job_for_user,
    prepare_job_extraction,
    regenerate_job_explanation,
    save_manual_job_markdown,
    serialize_job,
    update_duplicate_decision,
)
from app.application.project.service import assign_job_to_project, get_project_for_user
from app.application.output.service import serialize_job_output
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.queue.dispatch import enqueue_job_extraction, enqueue_job_generation
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobIntakeRequest(BaseModel):
    job_url: HttpUrl | str
    notes_markdown: str | None = Field(default=None, max_length=50_000)
    project_id: UUID | None = None


class DuplicateSummary(BaseModel):
    duplicate_count: int
    user_ids: list[str]
    job_ids: list[str]
    display_names: list[str]


class JobIntakeResponse(BaseModel):
    job: dict
    duplicate: DuplicateSummary


class DuplicateDecisionRequest(BaseModel):
    action: str = Field(pattern="^(continue|stop)$")


class DuplicateDecisionResponse(BaseModel):
    job: dict
    should_process: bool


class JobExtractionResponse(BaseModel):
    job: dict
    queued: bool
    extracted: bool
    fallback_required: bool
    message: str


class ManualMarkdownRequest(BaseModel):
    job_markdown: str = Field(min_length=20, max_length=100_000)


class JobListResponse(BaseModel):
    jobs: list[dict[str, Any]]
    count: int


class JobDetailResponse(BaseModel):
    job: dict[str, Any]
    output: dict[str, Any] | None
    duplicates: list[str] | None = None


class JobStatusOutcomeUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=64)
    outcome: str | None = Field(default=None, max_length=64)


class JobSubmissionUpdateRequest(BaseModel):
    is_submitted_to_upwork: bool
    submitted_at: datetime | None = None


class JobProjectUpdateRequest(BaseModel):
    project_id: UUID | None = None


class JobGenerateRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=5000)
    queue_if_available: bool = True


class JobGenerateResponse(BaseModel):
    queued: bool
    run: dict[str, Any] | None
    message: str


class JobExplainResponse(BaseModel):
    job: dict[str, Any]
    used_fallback: bool
    message: str


class GenerationRunsResponse(BaseModel):
    runs: list[dict[str, Any]]
    count: int


class JobApproveRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=5000)


class JobApproveResponse(BaseModel):
    job: dict[str, Any]
    output: dict[str, Any]
    message: str


class JobPublishRequest(BaseModel):
    connectors: list[str] | None = Field(default=None, max_length=10)
    title: str | None = Field(default=None, max_length=240)


class JobPublishResponse(BaseModel):
    job_id: str
    published_at: str
    results: list[dict[str, Any]]
    google_doc_url: str | None
    google_doc_open_url: str | None = None


@router.post("/intake", response_model=JobIntakeResponse, status_code=status.HTTP_201_CREATED)
async def intake_job(
    payload: JobIntakeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobIntakeResponse:
    if payload.project_id is not None:
        await get_project_for_user(
            session=session,
            user_id=current_user.id,
            project_id=payload.project_id,
        )
    job, duplicates, duplicate_names = await create_job_intake(
        session=session,
        user_id=current_user.id,
        job_url=str(payload.job_url),
        notes_markdown=payload.notes_markdown,
        project_id=payload.project_id,
    )
    duplicate_summary = DuplicateSummary(
        duplicate_count=len(duplicates),
        user_ids=[str(duplicate.user_id) for duplicate in duplicates],
        job_ids=[str(duplicate.id) for duplicate in duplicates],
        display_names=duplicate_names,
    )
    return JobIntakeResponse(job=serialize_job(job), duplicate=duplicate_summary)


@router.get("", response_model=JobListResponse)
async def list_jobs(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    status: Annotated[str | None, Query(max_length=64)] = None,
    outcome: Annotated[str | None, Query(max_length=64)] = None,
    project_id: UUID | None = None,
    is_submitted_to_upwork: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> JobListResponse:
    jobs = await list_jobs_for_user(
        session=session,
        user_id=current_user.id,
        status=status,
        outcome=outcome,
        is_submitted_to_upwork=is_submitted_to_upwork,
        project_id=project_id,
        limit=limit,
        offset=offset,
    )
    serialized = [serialize_job(job) for job in jobs]
    return JobListResponse(jobs=serialized, count=len(serialized))


@router.get("/{job_id}", response_model=JobDetailResponse)
async def job_detail(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobDetailResponse:
    job, output, duplicate_names = await get_job_detail_for_user(session=session, user_id=current_user.id, job_id=job_id)
    detail = serialize_job_detail(job=job, output=output, duplicate_names=duplicate_names)
    return JobDetailResponse(job=detail["job"], output=detail["output"], duplicates=detail.get("duplicates"))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await delete_job_for_user(session=session, user_id=current_user.id, job_id=job_id)


@router.post("/{job_id}/duplicate-decision", response_model=DuplicateDecisionResponse)
async def duplicate_decision(
    job_id: UUID,
    payload: DuplicateDecisionRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DuplicateDecisionResponse:
    job = await update_duplicate_decision(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        action=payload.action,
    )
    return DuplicateDecisionResponse(job=serialize_job(job), should_process=payload.action == "continue")


@router.post("/{job_id}/extract", response_model=JobExtractionResponse)
async def extract_job_markdown(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobExtractionResponse:
    queued_job = await prepare_job_extraction(session=session, user_id=current_user.id, job_id=job_id)
    queued = enqueue_job_extraction(user_id=current_user.id, job_id=job_id)
    if queued:
        return JobExtractionResponse(
            job=serialize_job(queued_job),
            queued=True,
            extracted=False,
            fallback_required=False,
            message="Extraction queued",
        )

    processed_job = await execute_job_extraction(session=session, user_id=current_user.id, job_id=job_id)
    fallback_required = processed_job.status == "failed"
    return JobExtractionResponse(
        job=serialize_job(processed_job),
        queued=False,
        extracted=not fallback_required,
        fallback_required=fallback_required,
        message=(
            "Firecrawl failed. Please paste the job text manually."
            if fallback_required
            else "Job markdown extracted successfully"
        ),
    )


@router.post("/{job_id}/manual-markdown", response_model=JobExtractionResponse)
async def set_manual_job_markdown(
    job_id: UUID,
    payload: ManualMarkdownRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobExtractionResponse:
    job = await save_manual_job_markdown(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        job_markdown=payload.job_markdown,
    )
    return JobExtractionResponse(
        job=serialize_job(job),
        queued=False,
        extracted=True,
        fallback_required=False,
        message="Manual markdown saved successfully",
    )


@router.post("/{job_id}/explain", response_model=JobExplainResponse)
async def explain_job(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobExplainResponse:
    job, used_fallback = await regenerate_job_explanation(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
    )
    return JobExplainResponse(
        job=serialize_job(job),
        used_fallback=used_fallback,
        message=(
            "Job explanation regenerated with fallback summary"
            if used_fallback
            else "Job explanation regenerated successfully"
        ),
    )


@router.patch("/{job_id}/status-outcome", response_model=JobDetailResponse)
async def patch_job_status_outcome(
    job_id: UUID,
    payload: JobStatusOutcomeUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobDetailResponse:
    job = await update_job_status_and_outcome(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        status=payload.status,
        outcome=payload.outcome,
    )
    detail = serialize_job_detail(job=job, output=None, duplicate_names=[])
    return JobDetailResponse(job=detail["job"], output=detail["output"])


@router.post("/{job_id}/generate", response_model=JobGenerateResponse)
async def generate_job_outputs(
    job_id: UUID,
    payload: JobGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobGenerateResponse:
    queued = (
        enqueue_job_generation(
            user_id=current_user.id,
            job_id=job_id,
            run_type="generate",
            instruction=payload.instruction,
        )
        if payload.queue_if_available
        else False
    )
    if queued:
        return JobGenerateResponse(
            queued=True,
            run=None,
            message="Generation queued",
        )

    run = await run_generation_pipeline(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        run_type="generate",
        instruction=payload.instruction,
    )
    return JobGenerateResponse(
        queued=False,
        run=serialize_generation_run(run),
        message="Generation completed",
    )


@router.get("/{job_id}/generation-runs", response_model=GenerationRunsResponse)
async def list_generation_runs(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> GenerationRunsResponse:
    runs = await list_generation_runs_for_job(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
    )
    serialized = [serialize_generation_run(run) for run in runs]
    return GenerationRunsResponse(runs=serialized, count=len(serialized))


@router.post("/{job_id}/approve", response_model=JobApproveResponse)
async def approve_job_outputs(
    job_id: UUID,
    payload: JobApproveRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobApproveResponse:
    output = await approve_output_versions(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        notes=payload.notes,
    )
    job = await get_job_for_user(session=session, user_id=current_user.id, job_id=job_id)
    return JobApproveResponse(
        job=serialize_job(job),
        output=serialize_job_output(output),
        message="Output versions approved",
    )


@router.post("/{job_id}/publish", response_model=JobPublishResponse)
async def publish_job(
    job_id: UUID,
    payload: JobPublishRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobPublishResponse:
    publish_result = await publish_job_outputs(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        connectors=payload.connectors,
        title=payload.title,
    )
    return JobPublishResponse(**publish_result)


@router.patch("/{job_id}/submission", response_model=JobDetailResponse)
async def patch_job_submission(
    job_id: UUID,
    payload: JobSubmissionUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobDetailResponse:
    job = await update_job_submission_flags(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        is_submitted_to_upwork=payload.is_submitted_to_upwork,
        submitted_at=payload.submitted_at,
    )
    detail = serialize_job_detail(job=job, output=None, duplicate_names=[])
    return JobDetailResponse(job=detail["job"], output=detail["output"])


@router.patch("/{job_id}/project", response_model=JobDetailResponse)
async def patch_job_project(
    job_id: UUID,
    payload: JobProjectUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobDetailResponse:
    job = await assign_job_to_project(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        project_id=payload.project_id,
    )
    detail = serialize_job_detail(job=job, output=None, duplicate_names=[])
    return JobDetailResponse(job=detail["job"], output=detail["output"])
