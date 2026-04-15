from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.service import get_user_by_id
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.errors.exceptions import AppException
from app.infrastructure.security.tokens import decode_session_token

settings = get_settings()


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    session_token: Annotated[str | None, Cookie(alias=settings.auth_cookie_name)] = None,
) -> User:
    if not session_token:
        raise AppException(status_code=401, code="unauthorized", message="Authentication required")

    user_id = decode_session_token(session_token)
    return await get_user_by_id(session=session, user_id=user_id)

