from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.service import login_user, register_user, serialize_user
from app.infrastructure.config.settings import get_settings
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.infrastructure.security.tokens import create_session_token
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


class RegisterRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    display_name: str
    email: EmailStr


class AuthResponse(BaseModel):
    user: UserResponse


def _set_session_cookie(response: Response, token: str) -> None:
    max_age = settings.auth_session_days * 24 * 60 * 60
    same_site = "none" if settings.auth_cookie_secure else "lax"
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=max_age,
        expires=datetime.now(UTC) + timedelta(seconds=max_age),
        httponly=True,
        secure=settings.auth_cookie_secure,
        # Cross-origin HTTPS deployments need SameSite=None, but browsers reject
        # SameSite=None cookies unless Secure is also set.
        samesite=same_site,
        path="/",
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    user = await register_user(
        session=session,
        display_name=payload.display_name,
        email=payload.email,
        password=payload.password,
    )
    _set_session_cookie(response, create_session_token(user.id))
    return AuthResponse(user=UserResponse(**serialize_user(user)))


@router.post("/login", response_model=AuthResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    user = await login_user(
        session=session,
        request=request,
        email=payload.email,
        password=payload.password,
    )
    _set_session_cookie(response, create_session_token(user.id))
    return AuthResponse(user=UserResponse(**serialize_user(user)))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> None:
    response.delete_cookie(key=settings.auth_cookie_name, path="/")


@router.get("/me", response_model=AuthResponse)
async def me(current_user: Annotated[User, Depends(get_current_user)]) -> AuthResponse:
    return AuthResponse(user=UserResponse(**serialize_user(current_user)))


class UpdateMeRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)


@router.patch("/me", response_model=AuthResponse)
async def update_me(
    payload: UpdateMeRequest,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AuthResponse:
    current_user.display_name = payload.display_name.strip()
    await session.commit()
    await session.refresh(current_user)
    return AuthResponse(user=UserResponse(**serialize_user(current_user)))
