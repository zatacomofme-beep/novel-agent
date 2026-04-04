from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from tasks.schemas import TaskState


async def dispatch_legacy_generation_for_chapter(
    session: AsyncSession,
    *,
    chapter,
    user_id: UUID,
    payload: dict[str, Any] | None = None,
) -> TaskState:
    """Compatibility wrapper around the legacy chapter generation pipeline."""

    from services.legacy_generation_service import build_generation_payload
    from tasks.chapter_generation import (
        dispatch_generation_task,
        enqueue_chapter_generation_task,
    )

    generation_payload = payload or await build_generation_payload(session, chapter.id, user_id)
    task_state = await enqueue_chapter_generation_task(
        str(chapter.id),
        str(user_id),
        str(chapter.project_id),
        generation_payload,
    )
    return await dispatch_generation_task(
        task_id=task_state.task_id,
        chapter_id=str(chapter.id),
        project_id=str(chapter.project_id),
        user_id=str(user_id),
    )
