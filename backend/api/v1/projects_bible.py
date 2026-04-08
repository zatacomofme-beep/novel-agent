from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from canon.service import build_canon_snapshot_payload
from memory.story_bible import load_story_bible_context
from models.user import User
from schemas.canon import CanonSnapshotRead
from schemas.project import (
    StoryBibleBranchItemDelete,
    StoryBibleBranchItemUpsert,
    StoryBibleRead,
    StoryBibleScopeRead,
    StoryBibleUpdate,
)
from services.export_service import (
    ExportFormat,
    build_export_response,
    build_project_export_filename,
    render_project_export,
)
from services.project_service import (
    delete_story_bible_branch_item,
    get_owned_project,
    get_story_bible,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
    replace_story_bible,
    upsert_story_bible_branch_item,
)


router = APIRouter(tags=["projects-bible"])


@router.get("/{project_id}/bible", response_model=StoryBibleRead)
async def story_bible_detail(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    return await get_story_bible(
        session,
        project_id,
        current_user.id,
        branch_id=branch_id,
    )


@router.put("/{project_id}/bible", response_model=StoryBibleRead)
async def story_bible_replace(
    project_id: UUID,
    payload: StoryBibleUpdate,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await replace_story_bible(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )
    return updated


@router.post("/{project_id}/bible/item", response_model=StoryBibleRead)
async def story_bible_item_upsert(
    project_id: UUID,
    payload: StoryBibleBranchItemUpsert,
    branch_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await upsert_story_bible_branch_item(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.post("/{project_id}/bible/item/remove", response_model=StoryBibleRead)
async def story_bible_item_remove(
    project_id: UUID,
    payload: StoryBibleBranchItemDelete,
    branch_id: UUID = Query(...),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryBibleRead:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await delete_story_bible_branch_item(
        session,
        project,
        payload,
        actor_user_id=current_user.id,
        branch_id=branch_id,
    )


@router.get("/{project_id}/canon-snapshot", response_model=CanonSnapshotRead)
async def project_canon_snapshot(
    project_id: UUID,
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> CanonSnapshotRead:
    story_bible = await load_story_bible_context(
        session,
        project_id,
        current_user.id,
        branch_id=branch_id,
    )
    snapshot_payload = build_canon_snapshot_payload(story_bible)
    return CanonSnapshotRead(
        project_id=story_bible.project_id,
        title=story_bible.title,
        branch_id=story_bible.branch_id,
        branch_title=story_bible.branch_title,
        branch_key=story_bible.branch_key,
        scope=StoryBibleScopeRead.model_validate(story_bible.model_dump()),
        plugin_snapshots=snapshot_payload["plugin_snapshots"],
        total_entity_count=snapshot_payload["total_entity_count"],
        integrity_report=snapshot_payload["integrity_report"],
    )


@router.get("/{project_id}/export")
async def project_export(
    project_id: UUID,
    export_format: ExportFormat = Query(default="md", alias="format"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project = await get_owned_project(
        session,
        project_id,
        current_user.id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    return build_export_response(
        content=render_project_export(project=project, export_format=export_format),
        filename=build_project_export_filename(project.title, export_format),
    )
