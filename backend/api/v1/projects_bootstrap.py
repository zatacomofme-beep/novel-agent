from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.project import (
    ProjectBlueprintGenerateRequest,
    ProjectBootstrapProfileUpdate,
    ProjectBootstrapRead,
    ProjectChapterGenerationDispatchRead,
)
from services.project_bootstrap_service import (
    generate_project_blueprint,
    get_project_bootstrap_state,
    update_project_bootstrap_profile,
)
from services.project_service import get_owned_project, PROJECT_PERMISSION_EDIT, PROJECT_PERMISSION_READ
from services.legacy_project_generation_service import dispatch_next_project_chapter_generation


router = APIRouter(tags=["projects-bootstrap"])


@router.get("/{project_id}/bootstrap", response_model=ProjectBootstrapRead)
async def project_bootstrap_detail(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return await get_project_bootstrap_state(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.put("/{project_id}/bootstrap", response_model=ProjectBootstrapRead)
async def project_bootstrap_replace(
    project_id: UUID,
    payload: ProjectBootstrapProfileUpdate,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await update_project_bootstrap_profile(session, project, payload)
    refreshed = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await get_project_bootstrap_state(
        session,
        refreshed,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.post("/{project_id}/bootstrap/generate", response_model=ProjectBootstrapRead)
async def project_bootstrap_generate(
    project_id: UUID,
    payload: ProjectBlueprintGenerateRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectBootstrapRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await generate_project_blueprint(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
        create_missing_chapters=payload.create_missing_chapters,
    )


@router.post(
    "/{project_id}/generate-next-chapter",
    response_model=ProjectChapterGenerationDispatchRead,
    deprecated=True,
    include_in_schema=False,
)
async def project_generate_next_chapter(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectChapterGenerationDispatchRead:
    from schemas.project import ProjectChapterGenerationDispatchRead

    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_next_project_chapter_generation(
        session,
        project,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )
