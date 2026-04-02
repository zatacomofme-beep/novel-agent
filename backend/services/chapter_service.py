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
    CHAPTER_STATUS_REVIEW,
    apply_chapter_gate_metadata,
    apply_chapter_gate_metadata_many,
    mark_quality_metrics_stale,
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
    from services.cache_service import cache_service

    cache_key = f"chapter:{chapter_id}"
    cached = await cache_service.get(cache_key)
    if cached is not None:
        return Chapter.model_validate(cached)

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
    await cache_service.set(cache_key, chapter.model_dump(mode="json"), ttl=600)
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
        current_version_number=1,
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
    result = await session.execute(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .options(selectinload(Chapter.checkpoints), selectinload(Chapter.review_decisions))
    )
    chapter = result.scalar_one()
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
    await _invalidate_chapter_cache(chapter.id)
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
    previous_title = chapter.title
    previous_branch_id = chapter.branch_id
    content_changed = (
        "content" in data
        and data["content"] is not None
        and data["content"] != chapter.content
    )
    title_changed = "title" in data and data["title"] != chapter.title
    branch_scope_changed = False
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
            branch_scope_changed = branch.id != previous_branch_id

    for field in ("title", "content", "outline", "status", "quality_metrics"):
        if field in data:
            setattr(chapter, field, data[field])

    if content_changed or title_changed or branch_scope_changed:
        chapter.quality_metrics = mark_quality_metrics_stale(
            chapter.quality_metrics,
            reason=_build_evaluation_stale_reason(
                content_changed=content_changed,
                title_changed=title_changed,
                branch_scope_changed=branch_scope_changed,
            ),
        )
        if "status" not in data and chapter.status == CHAPTER_STATUS_FINAL:
            chapter.status = CHAPTER_STATUS_REVIEW

    if chapter.status == CHAPTER_STATUS_FINAL:
        gate_summary = apply_chapter_gate_metadata(chapter)
        if not gate_summary.final_ready:
            raise AppError(
                code="chapter.final_gate_blocked",
                message=gate_summary.final_gate_reason
                or "Checkpoint gate blocks final status.",
                status_code=409,
            )

    next_version_number: Optional[int] = None
    if content_changed:
        next_version_number = int(getattr(chapter, "current_version_number", 1) or 1) + 1
        chapter.current_version_number = next_version_number
        chapter.word_count = _count_words(chapter.content)

    if content_changed and next_version_number is not None and payload.create_version:
        session.add(
            ChapterVersion(
                chapter_id=chapter.id,
                version_number=next_version_number,
                content=chapter.content,
                change_reason=payload.change_reason or "Manual content update",
            )
        )

    await session.commit()
    result = await session.execute(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .options(selectinload(Chapter.checkpoints), selectinload(Chapter.review_decisions))
    )
    chapter = result.scalar_one()
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
    await _invalidate_chapter_cache(chapter.id)
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
    next_version_number = int(getattr(chapter, "current_version_number", 1) or 1) + 1
    chapter.current_version_number = next_version_number
    chapter.quality_metrics = mark_quality_metrics_stale(
        chapter.quality_metrics,
        reason=(
            "The chapter was rolled back to a different saved version after the latest evaluation."
        ),
    )

    restored_version = ChapterVersion(
        chapter_id=chapter.id,
        version_number=next_version_number,
        content=version.content,
        change_reason=f"Rollback to version {version.version_number}",
    )
    session.add(restored_version)
    await session.commit()
    result = await session.execute(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .options(selectinload(Chapter.checkpoints), selectinload(Chapter.review_decisions))
    )
    chapter = result.scalar_one()
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
    await _invalidate_chapter_cache(chapter.id)
    return chapter, restored_version


async def _invalidate_chapter_cache(chapter_id: UUID) -> None:
    from services.cache_service import cache_service
    await cache_service.delete(f"chapter:{chapter_id}")


def _build_evaluation_stale_reason(
    *,
    content_changed: bool,
    title_changed: bool,
    branch_scope_changed: bool,
) -> str:
    changed_parts: list[str] = []
    if content_changed:
        changed_parts.append("content")
    if title_changed:
        changed_parts.append("title")
    if branch_scope_changed:
        changed_parts.append("branch scope")

    if not changed_parts:
        return "The latest evaluation no longer matches the current chapter state."
    if len(changed_parts) == 1:
        return (
            "The latest evaluation is outdated because the chapter "
            f"{changed_parts[0]} changed."
        )
    if len(changed_parts) == 2:
        joined = " and ".join(changed_parts)
        return f"The latest evaluation is outdated because the chapter {joined} changed."
    joined = ", ".join(changed_parts[:-1]) + f", and {changed_parts[-1]}"
    return f"The latest evaluation is outdated because the chapter {joined} changed."


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
