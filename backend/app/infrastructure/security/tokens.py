from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from jwt import InvalidTokenError

from app.infrastructure.config.settings import get_settings
from app.infrastructure.errors.exceptions import AppException

settings = get_settings()


def create_session_token(user_id: UUID) -> str:
    now = datetime.now(UTC)
    expires_at = now + timedelta(days=settings.auth_session_days)
    payload = {
        "sub": str(user_id),
        "typ": "session",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_session_token(token: str) -> UUID:
    try:
        payload = jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])
    except InvalidTokenError as exc:
        raise AppException(
            status_code=401,
            code="invalid_session",
            message="Session is invalid or expired",
        ) from exc

    subject = payload.get("sub")
    if not subject:
        raise AppException(status_code=401, code="invalid_session", message="Session subject missing")

    return UUID(subject)

