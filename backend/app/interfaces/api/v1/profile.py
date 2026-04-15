from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.profile.service import (
    beautify_and_upsert_manual_profile_text,
    create_profile,
    canonicalize_upwork_profile_url,
    extract_upwork_profile_id,
    extract_and_upsert_upwork_profile,
    get_profile_by_user_id,
    serialize_profile,
    update_profile,
)
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.errors.exceptions import AppException
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])
_UPWORK_EXTRACTION_RECOVERABLE_CODES = {
    "upwork_profile_extraction_failed",
    "upwork_profile_access_blocked",
    "upwork_profile_content_unreliable",
    "upwork_profile_markdown_empty",
}


class PromptBlockRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=10_000)
    enabled: bool = True

    @field_validator("title", "content")
    @classmethod
    def strip_and_require_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Value cannot be empty")
        return stripped


class ProfileCreateRequest(BaseModel):
    upwork_profile_url: HttpUrl | None = None
    upwork_profile_id: str | None = Field(default=None, max_length=120)
    upwork_profile_markdown: str | None = Field(default=None, max_length=50_000)
    proposal_template: str | None = Field(default=None, max_length=20_000)
    doc_template: str | None = Field(default=None, max_length=20_000)
    loom_template: str | None = Field(default=None, max_length=20_000)
    workflow_template_notes: str | None = Field(default=None, max_length=20_000)
    custom_global_instruction: str | None = Field(default=None, max_length=20_000)
    custom_prompt_blocks: list[PromptBlockRequest] = Field(default_factory=list, max_length=50)


class ProfileUpdateRequest(BaseModel):
    upwork_profile_url: HttpUrl | None = None
    upwork_profile_id: str | None = Field(default=None, max_length=120)
    upwork_profile_markdown: str | None = Field(default=None, max_length=50_000)
    proposal_template: str | None = Field(default=None, max_length=20_000)
    doc_template: str | None = Field(default=None, max_length=20_000)
    loom_template: str | None = Field(default=None, max_length=20_000)
    workflow_template_notes: str | None = Field(default=None, max_length=20_000)
    custom_global_instruction: str | None = Field(default=None, max_length=20_000)
    custom_prompt_blocks: list[PromptBlockRequest] | None = Field(default=None, max_length=50)


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    upwork_profile_url: str | None
    upwork_profile_id: str | None
    upwork_profile_markdown: str | None
    proposal_template: str | None
    doc_template: str | None
    loom_template: str | None
    workflow_template_notes: str | None
    custom_global_instruction: str | None
    custom_prompt_blocks: list[dict[str, Any]]


class ProfileUpworkExtractRequest(BaseModel):
    upwork_profile_url: HttpUrl | str


class ProfileUpworkRefreshRequest(BaseModel):
    upwork_profile_url: HttpUrl | str | None = None


class ProfileUpworkExtractResponse(BaseModel):
    profile: ProfileResponse
    extracted: bool
    message: str


class ProfileBeautifyManualRequest(BaseModel):
    raw_profile_text: str = Field(min_length=20, max_length=100_000)


class ProfileBeautifyManualResponse(BaseModel):
    profile: ProfileResponse
    beautified_markdown: str
    model_name: str
    input_tokens: int
    output_tokens: int
    message: str


@router.post("", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_user_profile(
    payload: ProfileCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    response: Response,
) -> ProfileResponse:
    payload_data = payload.model_dump(mode="python", exclude_unset=True)
    existing_profile = await get_profile_by_user_id(session=session, user_id=current_user.id)
    if existing_profile:
        profile = await update_profile(
            session=session,
            user_id=current_user.id,
            payload=payload_data,
        )
        response.status_code = status.HTTP_200_OK
    else:
        profile = await create_profile(
            session=session,
            user_id=current_user.id,
            payload=payload_data,
        )
    return ProfileResponse(**serialize_profile(profile))


@router.get("", response_model=ProfileResponse)
async def get_user_profile(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileResponse:
    profile = await get_profile_by_user_id(session=session, user_id=current_user.id)
    if not profile:
        raise AppException(status_code=404, code="profile_not_found", message="User profile not found")
    return ProfileResponse(**serialize_profile(profile))


@router.patch("", response_model=ProfileResponse)
async def patch_user_profile(
    payload: ProfileUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileResponse:
    updated_profile = await update_profile(
        session=session,
        user_id=current_user.id,
        payload=payload.model_dump(mode="python", exclude_unset=True),
    )
    return ProfileResponse(**serialize_profile(updated_profile))


@router.post("/extract-upwork", response_model=ProfileUpworkExtractResponse)
async def extract_upwork_profile(
    payload: ProfileUpworkExtractRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileUpworkExtractResponse:
    raw_url = str(payload.upwork_profile_url)
    try:
        profile = await extract_and_upsert_upwork_profile(
            session=session,
            user_id=current_user.id,
            upwork_profile_url=raw_url,
            require_existing_profile=False,
        )
        return ProfileUpworkExtractResponse(
            profile=ProfileResponse(**serialize_profile(profile)),
            extracted=True,
            message="Upwork profile extracted and saved",
        )
    except AppException as exc:
        if exc.code not in _UPWORK_EXTRACTION_RECOVERABLE_CODES:
            raise
        profile = await get_profile_by_user_id(session=session, user_id=current_user.id)
        if profile is None:
            canonical_url = canonicalize_upwork_profile_url(raw_url)
            profile = await create_profile(
                session=session,
                user_id=current_user.id,
                payload={
                    "upwork_profile_url": canonical_url,
                    "upwork_profile_id": extract_upwork_profile_id(canonical_url),
                },
            )
        return ProfileUpworkExtractResponse(
            profile=ProfileResponse(**serialize_profile(profile)),
            extracted=False,
            message=exc.message,
        )


@router.patch("/extract-upwork", response_model=ProfileUpworkExtractResponse)
async def refresh_upwork_profile(
    payload: ProfileUpworkRefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileUpworkExtractResponse:
    target_url = str(payload.upwork_profile_url) if payload.upwork_profile_url else None
    if not target_url:
        existing_profile = await get_profile_by_user_id(session=session, user_id=current_user.id)
        if not existing_profile:
            raise AppException(status_code=404, code="profile_not_found", message="User profile not found")
        if not existing_profile.upwork_profile_url:
            raise AppException(
                status_code=422,
                code="upwork_profile_url_missing",
                message="No Upwork profile URL exists to refresh",
            )
        target_url = existing_profile.upwork_profile_url

    try:
        profile = await extract_and_upsert_upwork_profile(
            session=session,
            user_id=current_user.id,
            upwork_profile_url=target_url,
            require_existing_profile=True,
        )
        return ProfileUpworkExtractResponse(
            profile=ProfileResponse(**serialize_profile(profile)),
            extracted=True,
            message="Upwork profile extracted and updated",
        )
    except AppException as exc:
        if exc.code not in _UPWORK_EXTRACTION_RECOVERABLE_CODES:
            raise
        profile = await get_profile_by_user_id(session=session, user_id=current_user.id)
        if profile is None:
            raise
        return ProfileUpworkExtractResponse(
            profile=ProfileResponse(**serialize_profile(profile)),
            extracted=False,
            message=exc.message,
        )


@router.post("/beautify-manual", response_model=ProfileBeautifyManualResponse)
async def beautify_manual_profile(
    payload: ProfileBeautifyManualRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProfileBeautifyManualResponse:
    profile, usage = await beautify_and_upsert_manual_profile_text(
        session=session,
        user_id=current_user.id,
        raw_profile_text=payload.raw_profile_text,
    )
    serialized = ProfileResponse(**serialize_profile(profile))
    return ProfileBeautifyManualResponse(
        profile=serialized,
        beautified_markdown=serialized.upwork_profile_markdown or "",
        model_name=str(usage["model_name"]),
        input_tokens=int(usage["input_tokens"]),
        output_tokens=int(usage["output_tokens"]),
        message="Manual profile text beautified and saved",
    )
