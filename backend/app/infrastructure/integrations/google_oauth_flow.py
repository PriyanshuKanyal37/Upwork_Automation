from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
import jwt
from jwt import InvalidTokenError

from app.infrastructure.config.settings import get_settings
from app.infrastructure.errors.exceptions import AppException


@dataclass(frozen=True, slots=True)
class GoogleOAuthTokens:
    access_token: str | None
    refresh_token: str | None


def _require_google_oauth_config() -> None:
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise AppException(
            status_code=503,
            code="google_oauth_not_configured",
            message="Google OAuth is not configured",
        )


def _normalize_scopes() -> str:
    settings = get_settings()
    scopes = [scope.strip() for scope in settings.google_oauth_scopes.split() if scope.strip()]
    if not scopes:
        raise AppException(
            status_code=503,
            code="google_oauth_not_configured",
            message="Google OAuth scopes are not configured",
        )
    return " ".join(scopes)


def create_google_oauth_state(*, user_id: UUID) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=settings.google_oauth_state_ttl_seconds)
    payload = {
        "sub": str(user_id),
        "typ": "google_oauth_state",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_google_oauth_state(state: str) -> UUID:
    settings = get_settings()
    try:
        payload = jwt.decode(state, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
    except InvalidTokenError as exc:
        raise AppException(
            status_code=400,
            code="invalid_google_oauth_state",
            message="Google OAuth state is invalid or expired",
        ) from exc

    token_type = payload.get("typ")
    if token_type != "google_oauth_state":
        raise AppException(
            status_code=400,
            code="invalid_google_oauth_state",
            message="Google OAuth state token type is invalid",
        )

    subject = payload.get("sub")
    if not subject:
        raise AppException(
            status_code=400,
            code="invalid_google_oauth_state",
            message="Google OAuth state subject is missing",
        )
    return UUID(subject)


def build_google_authorization_url(*, user_id: UUID) -> tuple[str, str]:
    settings = get_settings()
    _require_google_oauth_config()

    state = create_google_oauth_state(user_id=user_id)
    query = urlencode(
        {
            "client_id": settings.google_oauth_client_id,
            "redirect_uri": settings.google_oauth_redirect_uri,
            "response_type": "code",
            "scope": _normalize_scopes(),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
    )
    return f"{settings.google_oauth_authorize_url}?{query}", state


async def exchange_google_auth_code(*, code: str, redirect_uri: str) -> GoogleOAuthTokens:
    settings = get_settings()
    _require_google_oauth_config()

    async with httpx.AsyncClient(timeout=settings.connector_live_health_timeout_seconds) as client:
        response = await client.post(
            settings.google_oauth_token_url,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        )

    if response.status_code >= 400:
        raise AppException(
            status_code=502,
            code="google_token_exchange_failed",
            message="Failed to exchange Google OAuth code for tokens",
            details={"status_code": response.status_code},
        )

    payload = response.json()
    access_token = str(payload.get("access_token") or "").strip() or None
    refresh_token = str(payload.get("refresh_token") or "").strip() or None

    if not access_token and not refresh_token:
        raise AppException(
            status_code=502,
            code="google_token_exchange_failed",
            message="Google token exchange returned no usable tokens",
        )
    return GoogleOAuthTokens(access_token=access_token, refresh_token=refresh_token)
