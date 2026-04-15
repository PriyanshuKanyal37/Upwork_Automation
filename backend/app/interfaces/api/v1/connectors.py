from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.connector.service import (
    connector_health_status,
    create_connector_for_user,
    delete_connector_for_user,
    get_connector_for_user,
    list_connectors_for_user,
    serialize_connector,
    upsert_connector_for_user,
    update_connector_for_user,
)
from app.application.connector.publish_service import run_live_connector_health_check, serialize_live_health
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.integrations.google_oauth import build_google_credential_ref
from app.infrastructure.integrations.google_oauth_flow import (
    build_google_authorization_url,
    decode_google_oauth_state,
    exchange_google_auth_code,
)
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/connectors", tags=["connectors"])
settings = get_settings()


class ConnectorCreateRequest(BaseModel):
    connector_name: str = Field(min_length=2, max_length=64)
    credential_ref: str = Field(min_length=8, max_length=512)
    status: str = Field(default="connected", min_length=3, max_length=64)


class ConnectorUpdateRequest(BaseModel):
    credential_ref: str | None = Field(default=None, min_length=8, max_length=512)
    status: str | None = Field(default=None, min_length=3, max_length=64)


class ConnectorResponse(BaseModel):
    connector: dict[str, Any]


class ConnectorListResponse(BaseModel):
    connectors: list[dict[str, Any]]


class ConnectorStatusResponse(BaseModel):
    connector_status: dict[str, Any]


class GoogleOAuthStartResponse(BaseModel):
    authorization_url: str
    state: str
    redirect_uri: str
    expires_in_seconds: int


class GoogleOAuthCallbackResponse(BaseModel):
    connector: dict[str, Any]
    message: str


@router.post("", response_model=ConnectorResponse, status_code=status.HTTP_201_CREATED)
async def create_connector(
    payload: ConnectorCreateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    connector = await create_connector_for_user(
        session=session,
        user_id=current_user.id,
        connector_name=payload.connector_name,
        credential_ref=payload.credential_ref,
        status=payload.status,
    )
    return ConnectorResponse(connector=serialize_connector(connector))


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorListResponse:
    connectors = await list_connectors_for_user(session=session, user_id=current_user.id)
    return ConnectorListResponse(connectors=[serialize_connector(item) for item in connectors])


@router.get("/{connector_name}", response_model=ConnectorResponse)
async def get_connector(
    connector_name: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    connector = await get_connector_for_user(
        session=session,
        user_id=current_user.id,
        connector_name=connector_name,
    )
    return ConnectorResponse(connector=serialize_connector(connector))


@router.patch("/{connector_name}", response_model=ConnectorResponse)
async def patch_connector(
    connector_name: str,
    payload: ConnectorUpdateRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ConnectorResponse:
    connector = await update_connector_for_user(
        session=session,
        user_id=current_user.id,
        connector_name=connector_name,
        credential_ref=payload.credential_ref,
        status=payload.status,
    )
    return ConnectorResponse(connector=serialize_connector(connector))


@router.delete("/{connector_name}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def remove_connector(
    connector_name: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    await delete_connector_for_user(
        session=session,
        user_id=current_user.id,
        connector_name=connector_name,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{connector_name}/status", response_model=ConnectorStatusResponse)
async def connector_status(
    connector_name: str,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    live: bool = Query(default=False),
) -> ConnectorStatusResponse:
    connector = await get_connector_for_user(
        session=session,
        user_id=current_user.id,
        connector_name=connector_name,
    )
    if not live:
        return ConnectorStatusResponse(connector_status=connector_health_status(connector))
    live_result = await run_live_connector_health_check(
        connector_name=connector.connector_name,
        credential_ref=connector.credential_ref,
        current_status=connector.status,
    )
    return ConnectorStatusResponse(connector_status=serialize_live_health(live_result))


@router.get("/google/oauth/start", response_model=GoogleOAuthStartResponse)
async def start_google_oauth(
    current_user: Annotated[User, Depends(get_current_user)],
) -> GoogleOAuthStartResponse:
    authorization_url, state = build_google_authorization_url(user_id=current_user.id)
    return GoogleOAuthStartResponse(
        authorization_url=authorization_url,
        state=state,
        redirect_uri=settings.google_oauth_redirect_uri,
        expires_in_seconds=settings.google_oauth_state_ttl_seconds,
    )


@router.get("/google/callback", response_model=GoogleOAuthCallbackResponse)
async def google_oauth_callback(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> GoogleOAuthCallbackResponse:
    if error:
        raise AppException(
            status_code=400,
            code="google_oauth_denied",
            message=error_description or f"Google OAuth failed: {error}",
            details={"provider_error": error},
        )
    if not code:
        raise AppException(
            status_code=422,
            code="google_oauth_code_missing",
            message="Google OAuth callback did not include authorization code",
        )
    if not state:
        raise AppException(
            status_code=422,
            code="google_oauth_state_missing",
            message="Google OAuth callback did not include state",
        )

    user_id = decode_google_oauth_state(state)
    tokens = await exchange_google_auth_code(code=code, redirect_uri=settings.google_oauth_redirect_uri)
    credential_ref = build_google_credential_ref(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )
    connector = await upsert_connector_for_user(
        session=session,
        user_id=user_id,
        connector_name="google_docs",
        credential_ref=credential_ref,
        status="connected",
    )
    return GoogleOAuthCallbackResponse(
        connector=serialize_connector(connector),
        message="Google Docs connected successfully",
    )
