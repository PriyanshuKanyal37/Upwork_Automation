from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.output.service import (
    generate_doc_flowchart_for_user,
    get_job_output_for_user,
    regenerate_single_output,
    serialize_job_output,
    upsert_job_output,
)
from app.application.ai.orchestrator_service import run_generation_pipeline, serialize_generation_run
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.queue.dispatch import enqueue_job_generation
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/jobs", tags=["outputs"])


class WorkflowJSONItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    workflow_json: dict[str, Any] = Field(default_factory=dict)


class JobOutputUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    google_doc_url: str | None = Field(default=None, max_length=2048)
    google_doc_markdown: str | None = Field(default=None, max_length=300_000)
    workflow_jsons: list[WorkflowJSONItem] | None = Field(default=None, max_length=25)
    workflow_explanation: str | None = Field(default=None, max_length=120_000)
    loom_script: str | None = Field(default=None, max_length=120_000)
    proposal_text: str | None = Field(default=None, max_length=120_000)


class JobOutputResponse(BaseModel):
    output: dict[str, Any]


class OutputRegenerateRequest(BaseModel):
    target_output: Literal["google_doc_markdown", "workflow_jsons", "loom_script", "proposal_text"]
    instruction: str | None = Field(default=None, max_length=5000)
    generated_text: str | None = Field(default=None, max_length=300_000)
    generated_workflow_jsons: list[WorkflowJSONItem] | None = Field(default=None, max_length=25)

    @model_validator(mode="after")
    def validate_target_payload(self) -> "OutputRegenerateRequest":
        if self.target_output == "workflow_jsons":
            if self.generated_workflow_jsons is None:
                raise ValueError("generated_workflow_jsons is required for workflow_jsons target")
            if self.generated_text is not None:
                raise ValueError("generated_text must not be provided for workflow_jsons target")
        else:
            if self.generated_text is None:
                raise ValueError("generated_text is required for this target")
            if self.generated_workflow_jsons is not None:
                raise ValueError(
                    "generated_workflow_jsons must not be provided for text targets"
                )
        return self


class OutputRegenerateResponse(BaseModel):
    output: dict[str, Any]
    regenerated_output: str
    message: str


class TargetedRegenerateRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=5000)
    queue_if_available: bool = True
    proposal_loom_video_url: str | None = Field(default=None, max_length=2048)
    proposal_loom_video_summary: str | None = Field(default=None, max_length=20_000)
    proposal_doc_summary: str | None = Field(default=None, max_length=50_000)
    proposal_extra_notes: str | None = Field(default=None, max_length=10_000)


class TargetedRegenerateResponse(BaseModel):
    queued: bool
    run: dict[str, Any] | None
    output: dict[str, Any] | None
    regenerated_output: str
    message: str


class DocFlowchartGenerateRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=5000)
    connection_style: Literal["clean", "orthogonal", "curved"] | None = None
    # Backward-compat: older clients send this key.
    flowchart_instruction: str | None = Field(default=None, max_length=5000)

    @model_validator(mode="after")
    def normalize_instruction(self) -> "DocFlowchartGenerateRequest":
        if self.instruction is None and self.flowchart_instruction is not None:
            self.instruction = self.flowchart_instruction
        return self


class DocFlowchartGenerateResponse(BaseModel):
    output: dict[str, Any]
    doc_flowchart: dict[str, Any] | None
    message: str


@router.get("/{job_id}/outputs", response_model=JobOutputResponse)
async def get_job_output(
    job_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobOutputResponse:
    output = await get_job_output_for_user(session=session, user_id=current_user.id, job_id=job_id)
    return JobOutputResponse(output=serialize_job_output(output))


@router.patch("/{job_id}/outputs", response_model=JobOutputResponse)
async def patch_job_output(
    job_id: UUID,
    payload: JobOutputUpsertRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> JobOutputResponse:
    output = await upsert_job_output(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        google_doc_url=payload.google_doc_url,
        google_doc_markdown=payload.google_doc_markdown,
        workflow_jsons=(
            [{"name": item.name, "workflow_json": item.workflow_json} for item in payload.workflow_jsons]
            if payload.workflow_jsons is not None
            else None
        ),
        workflow_explanation=payload.workflow_explanation,
        loom_script=payload.loom_script,
        proposal_text=payload.proposal_text,
    )
    return JobOutputResponse(output=serialize_job_output(output))


@router.post("/{job_id}/outputs/regenerate", response_model=OutputRegenerateResponse)
async def regenerate_job_output(
    job_id: UUID,
    payload: OutputRegenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> OutputRegenerateResponse:
    output = await regenerate_single_output(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        target_output=payload.target_output,
        generated_text=payload.generated_text,
        generated_workflow_jsons=(
            [
                {"name": item.name, "workflow_json": item.workflow_json}
                for item in payload.generated_workflow_jsons
            ]
            if payload.generated_workflow_jsons is not None
            else None
        ),
        instruction=payload.instruction,
    )
    return OutputRegenerateResponse(
        output=serialize_job_output(output),
        regenerated_output=payload.target_output,
        message=f"{payload.target_output} regenerated successfully",
    )


@router.post(
    "/{job_id}/outputs/{output_type}/regenerate",
    response_model=TargetedRegenerateResponse,
)
async def regenerate_job_output_v2(
    job_id: UUID,
    output_type: Literal[
        "proposal",
        "cover_letter",
        "loom_script",
        "workflow",
        "doc",
    ],
    payload: TargetedRegenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> TargetedRegenerateResponse:
    additional_context: dict[str, Any] = {}
    if payload.proposal_loom_video_url:
        additional_context["proposal_loom_video_url"] = payload.proposal_loom_video_url
    if payload.proposal_loom_video_summary:
        additional_context["proposal_loom_video_summary"] = payload.proposal_loom_video_summary
    if payload.proposal_doc_summary:
        additional_context["proposal_doc_summary"] = payload.proposal_doc_summary
    if payload.proposal_extra_notes:
        additional_context["proposal_extra_notes"] = payload.proposal_extra_notes

    queued = (
        enqueue_job_generation(
            user_id=current_user.id,
            job_id=job_id,
            run_type="regenerate",
            target_artifact=output_type,
            instruction=payload.instruction,
            additional_context=additional_context or None,
        )
        if payload.queue_if_available
        else False
    )
    if queued:
        return TargetedRegenerateResponse(
            queued=True,
            run=None,
            output=None,
            regenerated_output=output_type,
            message="Regeneration queued",
        )

    run = await run_generation_pipeline(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        run_type="regenerate",
        target_artifact=output_type,
        instruction=payload.instruction,
        additional_context=additional_context or None,
    )
    output = await get_job_output_for_user(session=session, user_id=current_user.id, job_id=job_id)
    return TargetedRegenerateResponse(
        queued=False,
        run=serialize_generation_run(run),
        output=serialize_job_output(output),
        regenerated_output=output_type,
        message=f"{output_type} regenerated successfully",
    )


@router.post("/{job_id}/outputs/doc-flowchart/generate", response_model=DocFlowchartGenerateResponse)
async def generate_doc_flowchart(
    job_id: UUID,
    payload: DocFlowchartGenerateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> DocFlowchartGenerateResponse:
    output = await generate_doc_flowchart_for_user(
        session=session,
        user_id=current_user.id,
        job_id=job_id,
        flowchart_instruction=payload.instruction,
        connection_style=payload.connection_style,
    )
    serialized = serialize_job_output(output)
    return DocFlowchartGenerateResponse(
        output=serialized,
        doc_flowchart=serialized.get("doc_flowchart"),
        message="Diagram generated and staged for publishing",
    )
