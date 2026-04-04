from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from schemas.chapter import ChapterRead
from schemas.project import ProjectChapterGenerationDispatchRead
from services.chapter_service import get_owned_chapter
from services.project_generation_service import (
    _ResolvedNextChapterCandidate,
    _materialize_candidate_chapter,
    _resolve_next_project_chapter_candidate,
)
from services.project_service import PROJECT_PERMISSION_EDIT


async def dispatch_next_project_chapter_generation(
    session: AsyncSession,
    project,
    *,
    actor_user_id: UUID,
    branch_id: UUID | None = None,
) -> ProjectChapterGenerationDispatchRead:
    candidate: _ResolvedNextChapterCandidate | None = _resolve_next_project_chapter_candidate(
        project,
        branch_id=branch_id,
    )
    if candidate is None:
        raise AppError(
            code="project.next_chapter_unavailable",
            message="Project next chapter is unavailable. Generate a novel blueprint first.",
            status_code=400,
        )

    chapter = await _materialize_candidate_chapter(session, project, candidate)
    chapter = await get_owned_chapter(
        session,
        chapter.id,
        actor_user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )

    from services.legacy_generation_dispatch_service import (
        dispatch_legacy_generation_for_chapter,
    )

    task_state = await dispatch_legacy_generation_for_chapter(
        session,
        chapter=chapter,
        user_id=actor_user_id,
    )

    return ProjectChapterGenerationDispatchRead(
        chapter=ChapterRead.model_validate(chapter),
        next_chapter=candidate.to_read(chapter_override=chapter),
        task_id=task_state.task_id,
        task_status=task_state.status,
        task=task_state,
    )
