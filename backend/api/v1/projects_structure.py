from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.project import (
    ProjectBranchCreate,
    ProjectBranchUpdate,
    ProjectStructureRead,
    ProjectVolumeCreate,
    ProjectVolumeUpdate,
)
from services.project_service import (
    create_project_branch,
    create_project_volume,
    get_owned_project,
    get_project_structure,
    PROJECT_PERMISSION_EDIT,
    update_project_branch,
    update_project_volume,
)


router = APIRouter(tags=["projects-structure"])


@router.post(
    "/{project_id}/volumes",
    response_model=ProjectStructureRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_volume_create(
    project_id: UUID,
    payload: ProjectVolumeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await create_project_volume(session, project, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.patch("/{project_id}/volumes/{volume_id}", response_model=ProjectStructureRead)
async def project_volume_patch(
    project_id: UUID,
    volume_id: UUID,
    payload: ProjectVolumeUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_volume(session, project, volume_id, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.post(
    "/{project_id}/branches",
    response_model=ProjectStructureRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_branch_create(
    project_id: UUID,
    payload: ProjectBranchCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await create_project_branch(session, project, payload)
    return await get_project_structure(session, project_id, current_user.id)


@router.patch("/{project_id}/branches/{branch_id}", response_model=ProjectStructureRead)
async def project_branch_patch(
    project_id: UUID,
    branch_id: UUID,
    payload: ProjectBranchUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectStructureRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_branch(session, project, branch_id, payload)
    return await get_project_structure(session, project_id, current_user.id)
