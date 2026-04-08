from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.project import (
    ProjectCollaborationRead,
    ProjectCollaboratorCreate,
    ProjectCollaboratorUpdate,
)
from services.project_service import (
    add_project_collaborator,
    get_owned_project,
    get_project_collaboration,
    PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    remove_project_collaborator,
    update_project_collaborator,
)


router = APIRouter(tags=["projects-collab"])


@router.get("/{project_id}/collaborators", response_model=ProjectCollaborationRead)
async def project_collaboration_detail(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    return await get_project_collaboration(session, project_id, current_user.id)


@router.post(
    "/{project_id}/collaborators",
    response_model=ProjectCollaborationRead,
    status_code=status.HTTP_201_CREATED,
)
async def project_collaborator_create(
    project_id: UUID,
    payload: ProjectCollaboratorCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await add_project_collaborator(
        session,
        project,
        actor_user_id=current_user.id,
        payload=payload,
    )
    return await get_project_collaboration(session, project_id, current_user.id)


@router.patch(
    "/{project_id}/collaborators/{collaborator_id}",
    response_model=ProjectCollaborationRead,
)
async def project_collaborator_patch(
    project_id: UUID,
    collaborator_id: UUID,
    payload: ProjectCollaboratorUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await update_project_collaborator(session, project, collaborator_id, payload)
    return await get_project_collaboration(session, project_id, current_user.id)


@router.delete(
    "/{project_id}/collaborators/{collaborator_id}",
    response_model=ProjectCollaborationRead,
)
async def project_collaborator_delete(
    project_id: UUID,
    collaborator_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectCollaborationRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_MANAGE_COLLABORATORS,
    )
    await remove_project_collaborator(session, project, collaborator_id)
    return await get_project_collaboration(session, project_id, current_user.id)
