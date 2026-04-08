from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from core.errors import AppError
from models.user import User
from schemas.project import ProjectCreate, ProjectRead, ProjectStructureRead, ProjectUpdate
from services.project_service import (
    build_project_stats_payload,
    create_project,
    delete_project,
    get_owned_project,
    get_project_structure,
    list_projects,
    PROJECT_PERMISSION_DELETE,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
    update_project,
)


router = APIRouter(tags=["projects-crud"])


class ProjectStatsResponse(BaseModel):
    total_word_count: int
    chapter_count: int
    character_count: int
    item_count: int
    faction_count: int
    location_count: int
    plot_thread_count: int
    volume_count: int
    branch_count: int


@router.get("", response_model=list[ProjectRead])
async def project_list(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ProjectRead]:
    projects = await list_projects(session, current_user.id)
    return [ProjectRead.model_validate(project) for project in projects]


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
async def project_create(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await create_project(session, current_user.id, payload)
    return ProjectRead.model_validate(project)


@router.get("/{project_id}", response_model=ProjectRead)
async def project_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return ProjectRead.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectRead)
async def project_patch(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await update_project(session, project, payload)
    return ProjectRead.model_validate(updated)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def project_delete(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_DELETE,
    )
    await delete_project(session, project)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/structure", response_model=ProjectStructureRead)
async def project_structure_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    return await get_project_structure(session, project_id, current_user.id)


@router.get("/{project_id}/stats", response_model=ProjectStatsResponse)
async def project_stats(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStatsResponse:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
    )
    return ProjectStatsResponse(**build_project_stats_payload(project))
