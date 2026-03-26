from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.story_room_cloud_draft import StoryRoomCloudDraft
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
    get_owned_project,
)


def build_story_room_cloud_draft_scope_key(
    *,
    branch_id: Optional[UUID],
    volume_id: Optional[UUID],
    chapter_number: int,
) -> str:
    branch_key = str(branch_id) if branch_id else "default"
    volume_key = str(volume_id) if volume_id else "default"
    return f"{branch_key}:{volume_key}:{chapter_number}"


def _build_draft_excerpt(value: str) -> str:
    normalized = " ".join(segment.strip() for segment in value.splitlines() if segment.strip())
    if len(normalized) <= 56:
        return normalized
    return f"{normalized[:56].rstrip()}..."


def _serialize_cloud_draft_summary(draft: StoryRoomCloudDraft) -> dict[str, Any]:
    return {
        "draft_snapshot_id": draft.id,
        "project_id": draft.project_id,
        "branch_id": draft.branch_id,
        "volume_id": draft.volume_id,
        "scope_key": draft.scope_key,
        "chapter_number": draft.chapter_number,
        "chapter_title": draft.chapter_title,
        "outline_id": draft.outline_id,
        "source_chapter_id": draft.source_chapter_id,
        "source_version_number": draft.source_version_number,
        "updated_at": draft.updated_at,
        "created_at": draft.created_at,
        "excerpt": _build_draft_excerpt(draft.draft_text),
        "char_count": len((draft.draft_text or "").strip()),
    }


def _serialize_cloud_draft(draft: StoryRoomCloudDraft) -> dict[str, Any]:
    return {
        **_serialize_cloud_draft_summary(draft),
        "draft_text": draft.draft_text,
    }


async def list_story_room_cloud_drafts(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
) -> list[dict[str, Any]]:
    await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    result = await session.execute(
        select(StoryRoomCloudDraft)
        .where(StoryRoomCloudDraft.project_id == project_id)
        .where(StoryRoomCloudDraft.user_id == user_id)
        .order_by(StoryRoomCloudDraft.updated_at.desc(), StoryRoomCloudDraft.created_at.desc())
    )
    drafts = result.scalars().all()
    return [_serialize_cloud_draft_summary(draft) for draft in drafts]


async def get_story_room_cloud_draft(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    draft_snapshot_id: UUID,
) -> Optional[dict[str, Any]]:
    await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    result = await session.execute(
        select(StoryRoomCloudDraft)
        .where(StoryRoomCloudDraft.id == draft_snapshot_id)
        .where(StoryRoomCloudDraft.project_id == project_id)
        .where(StoryRoomCloudDraft.user_id == user_id)
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        return None
    return _serialize_cloud_draft(draft)


async def upsert_story_room_cloud_draft(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: Optional[UUID],
    volume_id: Optional[UUID],
    chapter_number: int,
    chapter_title: str,
    draft_text: str,
    outline_id: Optional[UUID],
    source_chapter_id: Optional[UUID],
    source_version_number: Optional[int],
) -> dict[str, Any]:
    if chapter_number <= 0:
        raise AppError(
            code="story_engine.cloud_draft.invalid_scope",
            message="Chapter number must be greater than 0.",
            status_code=400,
        )

    await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    normalized_title = chapter_title.strip()
    if not normalized_title and not draft_text.strip():
        raise AppError(
            code="story_engine.cloud_draft.empty",
            message="Cloud draft requires title or draft text.",
            status_code=400,
        )

    scope_key = build_story_room_cloud_draft_scope_key(
        branch_id=branch_id,
        volume_id=volume_id,
        chapter_number=chapter_number,
    )
    result = await session.execute(
        select(StoryRoomCloudDraft)
        .where(StoryRoomCloudDraft.project_id == project_id)
        .where(StoryRoomCloudDraft.user_id == user_id)
        .where(StoryRoomCloudDraft.scope_key == scope_key)
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        draft = StoryRoomCloudDraft(
            project_id=project_id,
            user_id=user_id,
            branch_id=branch_id,
            volume_id=volume_id,
            source_chapter_id=source_chapter_id,
            outline_id=outline_id,
            scope_key=scope_key,
            chapter_number=chapter_number,
            chapter_title=normalized_title,
            draft_text=draft_text,
            source_version_number=source_version_number,
        )
        session.add(draft)
    else:
        draft.branch_id = branch_id
        draft.volume_id = volume_id
        draft.source_chapter_id = source_chapter_id
        draft.outline_id = outline_id
        draft.chapter_number = chapter_number
        draft.chapter_title = normalized_title
        draft.draft_text = draft_text
        draft.source_version_number = source_version_number

    await session.commit()
    await session.refresh(draft)
    return _serialize_cloud_draft(draft)


async def delete_story_room_cloud_draft(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    draft_snapshot_id: UUID,
) -> bool:
    await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    result = await session.execute(
        select(StoryRoomCloudDraft)
        .where(StoryRoomCloudDraft.id == draft_snapshot_id)
        .where(StoryRoomCloudDraft.project_id == project_id)
        .where(StoryRoomCloudDraft.user_id == user_id)
    )
    draft = result.scalar_one_or_none()
    if draft is None:
        return False

    await session.delete(draft)
    await session.commit()
    return True
