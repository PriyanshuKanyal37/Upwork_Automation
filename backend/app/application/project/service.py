from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.job.service import get_job_for_user
from app.infrastructure.database.models.job import Job
from app.infrastructure.database.models.project import Project
from app.infrastructure.errors.exceptions import AppException


def _normalize_project_name(name: str) -> str:
    normalized = " ".join(name.strip().split())
    if not normalized:
        raise AppException(
            status_code=422,
            code="invalid_project_name",
            message="Project name cannot be empty",
        )
    if len(normalized) > 120:
        raise AppException(
            status_code=422,
            code="invalid_project_name",
            message="Project name cannot exceed 120 characters",
        )
    return normalized


def serialize_project(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "user_id": str(project.user_id),
        "name": project.name,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
    }


async def get_project_for_user(*, session: AsyncSession, user_id: UUID, project_id: UUID) -> Project:
    project = await session.get(Project, project_id)
    if not project or project.user_id != user_id:
        raise AppException(status_code=404, code="project_not_found", message="Project not found")
    return project


async def list_projects_for_user(*, session: AsyncSession, user_id: UUID) -> list[Project]:
    rows = await session.scalars(
        select(Project).where(Project.user_id == user_id).order_by(Project.created_at.asc())
    )
    return list(rows)


async def create_project_for_user(*, session: AsyncSession, user_id: UUID, name: str) -> Project:
    project = Project(user_id=user_id, name=_normalize_project_name(name))
    session.add(project)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(
            status_code=409,
            code="project_name_exists",
            message="A project with this name already exists",
        ) from exc
    await session.refresh(project)
    return project


async def rename_project_for_user(
    *,
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    name: str,
) -> Project:
    project = await get_project_for_user(session=session, user_id=user_id, project_id=project_id)
    project.name = _normalize_project_name(name)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise AppException(
            status_code=409,
            code="project_name_exists",
            message="A project with this name already exists",
        ) from exc
    await session.refresh(project)
    return project


async def delete_project_for_user(*, session: AsyncSession, user_id: UUID, project_id: UUID) -> None:
    project = await get_project_for_user(session=session, user_id=user_id, project_id=project_id)
    # Explicit unassign to keep behavior consistent across databases.
    await session.execute(
        update(Job)
        .where(Job.user_id == user_id, Job.project_id == project.id)
        .values(project_id=None)
    )
    await session.delete(project)
    await session.commit()


async def assign_job_to_project(
    *,
    session: AsyncSession,
    user_id: UUID,
    job_id: UUID,
    project_id: UUID | None,
) -> Job:
    job = await get_job_for_user(session=session, user_id=user_id, job_id=job_id)
    if project_id is None:
        job.project_id = None
        await session.commit()
        await session.refresh(job)
        return job

    project = await get_project_for_user(session=session, user_id=user_id, project_id=project_id)
    job.project_id = project.id
    await session.commit()
    await session.refresh(job)
    return job

