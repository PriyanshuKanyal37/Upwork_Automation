from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from app.infrastructure.config.settings import get_settings
from app.infrastructure.errors.exceptions import AppException


@dataclass(frozen=True, slots=True)
class GoogleTokenBundle:
    access_token: str
    refresh_token: str | None


def parse_google_credential_ref(credential_ref: str) -> GoogleTokenBundle:
    parsed = urlparse(credential_ref)
    if parsed.scheme != "oauth" or parsed.netloc not in {"google", "google_docs"}:
        raise AppException(
            status_code=422,
            code="invalid_google_credential_ref",
            message="Google connector credential_ref must use oauth://google scheme",
        )

    query_values = parse_qs(parsed.query)
    access_token = (query_values.get("access_token") or [""])[0]
    refresh_token = (query_values.get("refresh_token") or [None])[0]

    # Backward compatible path format: oauth://google/access/<token>
    if not access_token:
        path = (parsed.path or "").strip("/")
        parts = path.split("/") if path else []
        if len(parts) >= 2 and parts[0] == "access":
            access_token = parts[1]
        if len(parts) >= 4 and parts[2] == "refresh":
            refresh_token = parts[3]

    if not access_token and not refresh_token:
        raise AppException(
            status_code=422,
            code="google_access_token_missing",
            message="Google connector credential_ref does not include usable token",
        )

    return GoogleTokenBundle(access_token=access_token, refresh_token=refresh_token)


def build_google_credential_ref(*, access_token: str | None, refresh_token: str | None) -> str:
    trimmed_access = (access_token or "").strip() or None
    trimmed_refresh = (refresh_token or "").strip() or None
    if not trimmed_access and not trimmed_refresh:
        raise AppException(
            status_code=422,
            code="google_access_token_missing",
            message="Google OAuth response did not include usable tokens",
        )

    candidates: list[dict[str, str]] = []
    if trimmed_access and trimmed_refresh:
        candidates.append({"access_token": trimmed_access, "refresh_token": trimmed_refresh})
    if trimmed_refresh:
        candidates.append({"refresh_token": trimmed_refresh})
    if trimmed_access:
        candidates.append({"access_token": trimmed_access})

    for params in candidates:
        value = f"oauth://google_docs?{urlencode(params)}"
        if len(value) <= 512:
            return value

    raise AppException(
        status_code=422,
        code="invalid_credential_ref",
        message="Google OAuth credential payload is too large to store",
    )


async def refresh_google_access_token(*, refresh_token: str) -> str:
    settings = get_settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise AppException(
            status_code=503,
            code="google_oauth_not_configured",
            message="Google OAuth refresh is not configured",
        )

    async with httpx.AsyncClient(timeout=settings.connector_live_health_timeout_seconds) as client:
        response = await client.post(
            settings.google_oauth_token_url,
            data={
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if response.status_code >= 400:
        raise AppException(
            status_code=503,
            code="google_token_refresh_failed",
            message="Google token refresh failed",
            details={"status_code": response.status_code},
        )
    payload = response.json()
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise AppException(
            status_code=503,
            code="google_token_refresh_failed",
            message="Google token refresh returned no access token",
        )
    return access_token


async def resolve_google_access_token(credential_ref: str) -> str:
    token_bundle = parse_google_credential_ref(credential_ref)
    if token_bundle.refresh_token:
        try:
            return await refresh_google_access_token(refresh_token=token_bundle.refresh_token)
        except AppException:
            if token_bundle.access_token:
                return token_bundle.access_token
            raise
    if token_bundle.access_token:
        return token_bundle.access_token
    raise AppException(
        status_code=503,
        code="google_access_token_missing",
        message="Google connector has no usable access token",
    )
