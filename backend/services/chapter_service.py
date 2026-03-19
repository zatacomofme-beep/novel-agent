from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.errors import AppError
from models.chapter import Chapter
from models.chapter_version import ChapterVersion
from models.project import Project
from schemas.chapter import ChapterCreate, ChapterUpdate
from services.chapter_gate_service import (
    CHAPTER_STATUS_FINAL,
    apply_chapter_gate_metadata,
    apply_chapter_gate_metadata_many,
)
from services.preference_service import record_preference_observation
from services.project_service import (
    ensure_project_structure,
    get_owned_project,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
    resolve_project_structure_scope,
)


async def list_project_chapters(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    volume_id: Optional[UUID] = None,
    branch_id: Optional[UUID] = None,
) -> list[Chapter]:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    statement = (
        select(Chapter)
        .where(Chapter.project_id == project_id)
        .options(
            selectinload(Chapter.volume),
            selectinload(Chapter.branch),
            selectinload(Chapter.checkpoints),
            selectinload(Chapter.review_decisions),
        )
    )

    if volume_id is not None or branch_id is not None:
        volume, branch = await resolve_project_structure_scope(
            session,
            project,
            volume_id=volume_id,
            branch_id=branch_id,
        )
        statement = statement.where(
            Chapter.volume_id == volume.id,
            Chapter.branch_id == branch.id,
        ).order_by(Chapter.chapter_number.asc())
    else:
        statement = statement.order_by(
            Chapter.branch_id.asc(),
            Chapter.volume_id.asc(),
            Chapter.chapter_number.asc(),
        )

    result = await session.execute(statement)
    chapters = list(result.scalars().all())
    apply_chapter_gate_metadata_many(chapters)
    return chapters


async def get_owned_chapter(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
    *,
    with_versions: bool = False,
    permission: str = PROJECT_PERMISSION_READ,
) -> Chapter:
    statement = select(Chapter).where(Chapter.id == chapter_id).options(
        selectinload(Chapter.volume),
        selectinload(Chapter.branch),
        selectinload(Chapter.checkpoints),
        selectinload(Chapter.review_decisions),
    )
    if with_versions:
        statement = statement.options(selectinload(Chapter.versions))

    result = await session.execute(statement)
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise AppError(
            code="chapter.not_found",
            message="Chapter not found.",
            status_code=404,
        )

    await get_owned_project(
        session,
        chapter.project_id,
        user_id,
        permission=permission,
    )

    project = await session.get(Project, chapter.project_id)
    if project is not None:
        changed = await ensure_project_structure(session, project)
        if changed:
            await session.commit()
            result = await session.execute(statement)
            chapter = result.scalar_one()
    apply_chapter_gate_metadata(chapter)
    return chapter


async def create_chapter(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    payload: ChapterCreate,
) -> Chapter:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    volume, branch = await resolve_project_structure_scope(
        session,
        project,
        volume_id=payload.volume_id,
        branch_id=payload.branch_id,
    )

    existing = await session.execute(
        select(Chapter.id).where(
            Chapter.project_id == project_id,
            Chapter.volume_id == volume.id,
            Chapter.branch_id == branch.id,
            Chapter.chapter_number == payload.chapter_number,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise AppError(
            code="chapter.number_conflict",
            message="Chapter number already exists in this project.",
            status_code=409,
        )

    content = payload.content or ""
    chapter = Chapter(
        project_id=project_id,
        volume_id=volume.id,
        branch_id=branch.id,
        chapter_number=payload.chapter_number,
        title=payload.title,
        content=content,
        outline=payload.outline,
        status=payload.status,
        word_count=_count_words(content),
    )
    session.add(chapter)
    await session.flush()

    session.add(
        ChapterVersion(
            chapter_id=chapter.id,
            version_number=1,
            content=chapter.content,
            change_reason=payload.change_reason or "Initial version",
        )
    )
    await session.commit()
    await session.refresh(chapter)
    apply_chapter_gate_metadata(chapter)
    await record_preference_observation(
        session,
        user_id=user_id,
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        source_type="chapter_create",
        content=chapter.content,
        change_reason=payload.change_reason or "Initial version",
    )
    return chapter


async def update_chapter(
    session: AsyncSession,
    chapter: Chapter,
    payload: ChapterUpdate,
    *,
    preference_learning_user_id: Optional[UUID] = None,
    preference_learning_source: str = "manual_update",
) -> Chapter:
    data = payload.model_dump(exclude_unset=True)
    previous_content = chapter.content
    content_changed = "content" in data and data["content"] is not None and data["content"] != chapter.content
    project = await session.get(Project, chapter.project_id)

    if project is not None and ("volume_id" in data or "branch_id" in data):
        target_volume_id = data["volume_id"] if "volume_id" in data else chapter.volume_id
        target_branch_id = data["branch_id"] if "branch_id" in data else chapter.branch_id
        volume, branch = await resolve_project_structure_scope(
            session,
            project,
            volume_id=target_volume_id,
            branch_id=target_branch_id,
        )
        if volume.id != chapter.volume_id or branch.id != chapter.branch_id:
            existing = await session.execute(
                select(Chapter.id).where(
                    Chapter.project_id == chapter.project_id,
                    Chapter.volume_id == volume.id,
                    Chapter.branch_id == branch.id,
                    Chapter.chapter_number == chapter.chapter_number,
                    Chapter.id != chapter.id,
                )
            )
            if existing.scalar_one_or_none() is not None:
                raise AppError(
                    code="chapter.number_conflict",
                    message="Chapter number already exists in this branch and volume.",
                    status_code=409,
                )
            chapter.volume_id = volume.id
            chapter.branch_id = branch.id

    if data.get("status") == CHAPTER_STATUS_FINAL:
        gate_summary = apply_chapter_gate_metadata(chapter)
        if not gate_summary.final_ready:
            raise AppError(
                code="chapter.final_gate_blocked",
                message=gate_summary.final_gate_reason
                or "Checkpoint gate blocks final status.",
                status_code=409,
            )

    for field in ("title", "content", "outline", "status", "quality_metrics"):
        if field in data:
            setattr(chapter, field, data[field])

    if content_changed:
        chapter.word_count = _count_words(chapter.content)

    if payload.create_version and content_changed:
        next_version_number = await _next_version_number(session, chapter.id)
        session.add(
            ChapterVersion(
                chapter_id=chapter.id,
                version_number=next_version_number,
                content=chapter.content,
                change_reason=payload.change_reason or "Manual content update",
            )
        )

    await session.commit()
    await session.refresh(chapter)
    apply_chapter_gate_metadata(chapter)
    if content_changed and preference_learning_user_id is not None:
        await record_preference_observation(
            session,
            user_id=preference_learning_user_id,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            source_type=preference_learning_source,
            content=chapter.content,
            change_reason=payload.change_reason,
            previous_content=previous_content,
        )
    return chapter


async def list_versions(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> list[ChapterVersion]:
    await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    result = await session.execute(
        select(ChapterVersion)
        .where(ChapterVersion.chapter_id == chapter_id)
        .order_by(ChapterVersion.version_number.asc())
    )
    return list(result.scalars().all())


async def rollback_to_version(
    session: AsyncSession,
    chapter_id: UUID,
    version_id: UUID,
    user_id: UUID,
) -> tuple[Chapter, ChapterVersion]:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    previous_content = chapter.content
    version = await session.get(ChapterVersion, version_id)
    if version is None or version.chapter_id != chapter.id:
        raise AppError(
            code="chapter.version_not_found",
            message="Chapter version not found.",
            status_code=404,
        )

    chapter.content = version.content
    chapter.word_count = _count_words(version.content)

    restored_version = ChapterVersion(
        chapter_id=chapter.id,
        version_number=await _next_version_number(session, chapter.id),
        content=version.content,
        change_reason=f"Rollback to version {version.version_number}",
    )
    session.add(restored_version)
    await session.commit()
    await session.refresh(chapter)
    apply_chapter_gate_metadata(chapter)
    await session.refresh(restored_version)
    await record_preference_observation(
        session,
        user_id=user_id,
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        source_type="rollback",
        content=chapter.content,
        change_reason=restored_version.change_reason,
        previous_content=previous_content,
    )
    return chapter, restored_version


async def _next_version_number(session: AsyncSession, chapter_id: UUID) -> int:
    result = await session.execute(
        select(func.max(ChapterVersion.version_number)).where(
            ChapterVersion.chapter_id == chapter_id
        )
    )
    current = result.scalar_one_or_none() or 0
    return int(current) + 1


def _count_words(content: str) -> int:
    stripped = content.strip()
    if not stripped:
        return 0
    return len(stripped.split())
