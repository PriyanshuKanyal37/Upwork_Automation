from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.models.user import User
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.security.login_rate_limiter import login_rate_limiter
from app.infrastructure.security.passwords import hash_password, verify_password


def _normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(
    *,
    session: AsyncSession,
    display_name: str,
    email: str,
    password: str,
) -> User:
    normalized_email = _normalize_email(email)
    existing_user = await session.scalar(select(User).where(User.email == normalized_email))
    if existing_user:
        raise AppException(
            status_code=409,
            code="email_already_exists",
            message="An account with this email already exists",
        )

    user = User(
        display_name=display_name.strip(),
        email=normalized_email,
        password_hash=hash_password(password),
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def _rate_limit_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{_normalize_email(email)}"


async def login_user(
    *,
    session: AsyncSession,
    request: Request,
    email: str,
    password: str,
) -> User:
    normalized_email = _normalize_email(email)
    key = _rate_limit_key(request, normalized_email)
    rate_limit = login_rate_limiter.check_and_record(key)
    if not rate_limit.allowed:
        raise AppException(
            status_code=429,
            code="too_many_login_attempts",
            message="Too many login attempts. Please try again later.",
            details={"retry_after_seconds": rate_limit.retry_after_seconds},
        )

    user = await session.scalar(select(User).where(User.email == normalized_email))
    if not user or not verify_password(password, user.password_hash):
        raise AppException(
            status_code=401,
            code="invalid_credentials",
            message="Email or password is incorrect",
        )

    login_rate_limiter.reset(key)
    return user


async def get_user_by_id(*, session: AsyncSession, user_id: UUID) -> User:
    user = await session.get(User, user_id)
    if not user:
        raise AppException(status_code=401, code="user_not_found", message="User session is invalid")
    return user


def serialize_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "display_name": user.display_name,
        "email": user.email,
    }

