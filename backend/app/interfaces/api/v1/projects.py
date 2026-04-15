from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.project.service import (
    create_project_for_user,
    delete_project_for_user,
    list_projects_for_user,
    rename_project_for_user,
    serialize_project,
)
from app.infrastructure.database.models.user import User
from app.infrastructure.database.session import get_db_session
from app.interfaces.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectPayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class ProjectResponse(BaseModel):
    project: dict


class ProjectListResponse(BaseModel):
    projects: list[dict]
    count: int


@router.get("", response_model=ProjectListResponse)
async def list_projects(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectListResponse:
    projects = await list_projects_for_user(session=session, user_id=current_user.id)
    serialized = [serialize_project(project) for project in projects]
    return ProjectListResponse(projects=serialized, count=len(serialized))


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectPayload,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectResponse:
    project = await create_project_for_user(
        session=session,
        user_id=current_user.id,
        name=payload.name,
    )
    return ProjectResponse(project=serialize_project(project))


@router.patch("/{project_id}", response_model=ProjectResponse)
async def rename_project(
    project_id: UUID,
    payload: ProjectPayload,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ProjectResponse:
    project = await rename_project_for_user(
        session=session,
        user_id=current_user.id,
        project_id=project_id,
        name=payload.name,
    )
    return ProjectResponse(project=serialize_project(project))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> None:
    await delete_project_for_user(
        session=session,
        user_id=current_user.id,
        project_id=project_id,
    )

