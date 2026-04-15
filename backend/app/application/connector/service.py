from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.user_connector import UserConnector
from app.infrastructure.errors.exceptions import AppException

_ALLOWED_CONNECTOR_NAMES = frozenset(
    {
        "airtable",
        "firecrawl",
        "google_docs",
        "n8n",
    }
)

_ALLOWED_CONNECTOR_STATUSES = frozenset(
    {
        "connected",
        "disconnected",
        "expired",
        "error",
        "pending_oauth",
    }
)

_CREDENTIAL_REF_PREFIXES = (
    "vault://",
    "oauth://",
    "secret://",
    "kms://",
    "render://",
    "firecrawl://",
)


def normalize_connector_name(connector_name: str) -> str:
    normalized = connector_name.strip().lower().replace("-", "_")
    if normalized not in _ALLOWED_CONNECTOR_NAMES:
        raise AppException(
            status_code=422,
            code="invalid_connector_name",
            message=f"Connector '{connector_name}' is not supported",
            details={"allowed_connectors": sorted(_ALLOWED_CONNECTOR_NAMES)},
        )
    return normalized


def normalize_connector_status(status: str) -> str:
    normalized = status.strip().lower()
    if normalized not in _ALLOWED_CONNECTOR_STATUSES:
        raise AppException(
            status_code=422,
            code="invalid_connector_status",
            message=f"Connector status '{status}' is not supported",
            details={"allowed_statuses": sorted(_ALLOWED_CONNECTOR_STATUSES)},
        )
    return normalized


def validate_credential_ref(credential_ref: str) -> str:
    value = credential_ref.strip()
    if not value:
        raise AppException(
            status_code=422,
            code="invalid_credential_ref",
            message="Credential reference cannot be empty",
        )
    if len(value) > 512:
        raise AppException(
            status_code=422,
            code="invalid_credential_ref",
            message="Credential reference exceeds maximum allowed length",
        )
    if " " in value or "\n" in value or "\r" in value:
        raise AppException(
            status_code=422,
            code="invalid_credential_ref",
            message="Credential reference cannot contain whitespace",
        )
    if not value.startswith(_CREDENTIAL_REF_PREFIXES):
        raise AppException(
            status_code=422,
            code="invalid_credential_ref",
            message="Credential reference must use a secure ref scheme",
            details={"allowed_prefixes": list(_CREDENTIAL_REF_PREFIXES)},
        )
    return value


def normalize_credential_ref_for_connector(*, connector_name: str, credential_ref: str) -> str:
    value = credential_ref.strip()
    if connector_name == "firecrawl" and not value.startswith(_CREDENTIAL_REF_PREFIXES):
        return f"firecrawl://{value}"
    return value


def _base_query(*, user_id: UUID) -> Select[tuple[UserConnector]]:
    return select(UserConnector).where(UserConnector.user_id == user_id)


async def get_connector_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    connector_name: str,
) -> UserConnector:
    normalized_name = normalize_connector_name(connector_name)
    connector = await session.scalar(
        _base_query(user_id=user_id).where(UserConnector.connector_name == normalized_name)
    )
    if connector is None:
        raise AppException(
            status_code=404,
            code="connector_not_found",
            message=f"Connector '{normalized_name}' not found",
        )
    return connector


async def list_connectors_for_user(*, session: AsyncSession, user_id: UUID) -> list[UserConnector]:
    rows = await session.scalars(_base_query(user_id=user_id).order_by(UserConnector.connector_name.asc()))
    return list(rows)


async def create_connector_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    connector_name: str,
    credential_ref: str,
    status: str,
) -> UserConnector:
    normalized_name = normalize_connector_name(connector_name)
    normalized_ref = normalize_credential_ref_for_connector(
        connector_name=normalized_name,
        credential_ref=credential_ref,
    )
    connector = UserConnector(
        user_id=user_id,
        connector_name=normalized_name,
        credential_ref=validate_credential_ref(normalized_ref),
        status=normalize_connector_status(status),
    )
    session.add(connector)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(
            status_code=409,
            code="connector_already_exists",
            message=f"Connector '{connector.connector_name}' already exists",
        ) from exc
    await session.refresh(connector)
    return connector


async def update_connector_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    connector_name: str,
    credential_ref: str | None = None,
    status: str | None = None,
) -> UserConnector:
    connector = await get_connector_for_user(
        session=session, user_id=user_id, connector_name=connector_name
    )
    if credential_ref is None and status is None:
        raise AppException(
            status_code=422,
            code="no_connector_fields",
            message="At least one connector field must be provided",
        )
    if credential_ref is not None:
        normalized_ref = normalize_credential_ref_for_connector(
            connector_name=connector.connector_name,
            credential_ref=credential_ref,
        )
        connector.credential_ref = validate_credential_ref(normalized_ref)
    if status is not None:
        connector.status = normalize_connector_status(status)
    connector.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(connector)
    return connector


async def upsert_connector_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    connector_name: str,
    credential_ref: str,
    status: str,
) -> UserConnector:
    normalized_name = normalize_connector_name(connector_name)
    normalized_status = normalize_connector_status(status)
    normalized_ref = normalize_credential_ref_for_connector(
        connector_name=normalized_name,
        credential_ref=credential_ref,
    )
    validated_ref = validate_credential_ref(normalized_ref)

    connector = await session.scalar(
        _base_query(user_id=user_id).where(UserConnector.connector_name == normalized_name)
    )
    if connector is None:
        connector = UserConnector(
            user_id=user_id,
            connector_name=normalized_name,
            credential_ref=validated_ref,
            status=normalized_status,
        )
        session.add(connector)
    else:
        connector.credential_ref = validated_ref
        connector.status = normalized_status
        connector.updated_at = datetime.now(UTC)

    await session.commit()
    await session.refresh(connector)
    return connector


async def delete_connector_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    connector_name: str,
) -> None:
    connector = await get_connector_for_user(
        session=session, user_id=user_id, connector_name=connector_name
    )
    await session.delete(connector)
    await session.commit()


def serialize_connector(connector: UserConnector) -> dict[str, str]:
    return {
        "id": str(connector.id),
        "user_id": str(connector.user_id),
        "connector_name": connector.connector_name,
        "credential_ref": connector.credential_ref,
        "status": connector.status,
        "updated_at": connector.updated_at.isoformat() if connector.updated_at else "",
    }


def connector_health_status(connector: UserConnector) -> dict[str, str | bool]:
    action_required = connector.status in {"expired", "error", "disconnected"}
    is_connected = connector.status == "connected"
    message = {
        "connected": "Connector is healthy",
        "pending_oauth": "Connector is waiting for OAuth completion",
        "disconnected": "Connector is disconnected and requires reconnect",
        "expired": "Connector credentials expired and require refresh",
        "error": "Connector reported an error and requires re-authentication",
    }.get(connector.status, "Connector status unknown")
    return {
        "connector_name": connector.connector_name,
        "status": connector.status,
        "is_connected": is_connected,
        "action_required": action_required,
        "message": message,
    }
