from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from core.errors import AppError
from models.user import User
from schemas.story_bible_version import (
    ConflictCheckRequest,
    ConflictCheckResult,
    StoryBibleApprovalRequest,
    StoryBiblePendingChangeCreate,
    StoryBiblePendingChangeList,
    StoryBiblePendingChangeRead,
    StoryBibleRollbackRequest,
    StoryBibleVersionList,
    StoryBibleVersionRead,
)
from services.project_service import (
    get_owned_project,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
)
from services.story_bible_version_service import (
    approve_pending_change,
    check_conflict,
    create_pending_change,
    get_pending_changes,
    get_story_bible_versions,
    reject_pending_change,
    rollback_story_bible,
)


router = APIRouter(tags=["projects-bible-versions"])


class StoryBiblePendingChangeCountResponse(BaseModel):
    pending_count: int


@router.get("/{project_id}/bible/versions", response_model=StoryBibleVersionList)
async def story_bible_version_list(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleVersionList:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    resolved_branch_id = branch_id
    if not resolved_branch_id:
        project = await get_owned_project(
            session,
            project_id,
            current_user.id,
            with_relations=True,
        )
        default_branch = next((b for b in project.branches if b.is_default), None)
        if default_branch:
            resolved_branch_id = default_branch.id

    if not resolved_branch_id:
        return StoryBibleVersionList(items=[], total=0, page=page, page_size=page_size)

    return await get_story_bible_versions(
        session,
        project_id,
        resolved_branch_id,
        page=page,
        page_size=page_size,
    )


@router.post("/{project_id}/bible/rollback", response_model=StoryBibleVersionRead)
async def story_bible_rollback(
    project_id: UUID,
    request: StoryBibleRollbackRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleVersionRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    resolved_branch_id = branch_id
    if not resolved_branch_id:
        default_branch = next((b for b in project.branches if b.is_default), None)
        if default_branch:
            resolved_branch_id = default_branch.id

    if not resolved_branch_id:
        raise AppError(
            code="story_bible.branch_required",
            message="A target branch is required for Story Bible rollback.",
            status_code=400,
        )

    version = await rollback_story_bible(
        session,
        project,
        resolved_branch_id,
        request,
        current_user.id,
    )
    await session.commit()
    return StoryBibleVersionRead.model_validate(version)


@router.get(
    "/{project_id}/bible/pending-changes",
    response_model=StoryBiblePendingChangeList,
)
async def story_bible_pending_changes(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeList:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return await get_pending_changes(session, project_id, branch_id)


@router.get(
    "/{project_id}/bible/pending-changes/count",
    response_model=StoryBiblePendingChangeCountResponse,
)
async def story_bible_pending_change_count(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeCountResponse:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    pending = await get_pending_changes(session, project_id, branch_id)
    return StoryBiblePendingChangeCountResponse(pending_count=pending.pending_count)


@router.post(
    "/{project_id}/bible/pending-changes",
    response_model=StoryBiblePendingChangeRead,
    status_code=status.HTTP_201_CREATED,
)
async def story_bible_pending_change_create(
    project_id: UUID,
    request: StoryBiblePendingChangeCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    pending = await create_pending_change(
        session,
        project_id,
        request.branch_id,
        request,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/pending-changes/{change_id}/approve",
    response_model=StoryBiblePendingChangeRead,
)
async def story_bible_pending_change_approve(
    project_id: UUID,
    change_id: UUID,
    request: StoryBibleApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    pending = await approve_pending_change(
        session,
        change_id,
        current_user.id,
        request.comment,
        expected_project_id=project_id,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/pending-changes/{change_id}/reject",
    response_model=StoryBiblePendingChangeRead,
)
async def story_bible_pending_change_reject(
    project_id: UUID,
    change_id: UUID,
    request: StoryBibleApprovalRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBiblePendingChangeRead:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    if not request.comment:
        raise AppError(
            code="story_bible.rejection_reason_required",
            message="Rejection reason is required.",
            status_code=400,
        )
    pending = await reject_pending_change(
        session,
        change_id,
        current_user.id,
        request.comment,
        expected_project_id=project_id,
    )
    await session.commit()
    return StoryBiblePendingChangeRead.model_validate(pending)


@router.post(
    "/{project_id}/bible/check-conflict",
    response_model=ConflictCheckResult,
)
async def story_bible_check_conflict(
    project_id: UUID,
    request: ConflictCheckRequest,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ConflictCheckResult:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return await check_conflict(
        session,
        project,
        request,
        branch_id=branch_id,
    )
