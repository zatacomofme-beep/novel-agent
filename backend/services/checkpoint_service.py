from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.chapter_checkpoint import (
    CHECKPOINT_TYPE_GENERATION,
    ChapterCheckpoint,
)


class CheckpointService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_generation_checkpoint(
        self,
        *,
        chapter_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_version_number: int,
        title: str,
        generation_payload: dict[str, Any],
        generated_content: str,
        progress: int,
        segments_completed: int,
        segments_total: int,
        description: Optional[str] = None,
    ) -> ChapterCheckpoint:
        checkpoint = ChapterCheckpoint(
            chapter_id=chapter_id,
            requester_user_id=user_id,
            chapter_version_number=chapter_version_number,
            checkpoint_type=CHECKPOINT_TYPE_GENERATION,
            title=title,
            description=description,
            status="completed",
            generation_payload=generation_payload,
            generated_content=generated_content,
            progress=progress,
            segments_completed=segments_completed,
            segments_total=segments_total,
        )
        self.session.add(checkpoint)
        await self.session.flush()
        return checkpoint

    async def get_latest_generation_checkpoint(
        self,
        chapter_id: uuid.UUID,
    ) -> Optional[ChapterCheckpoint]:
        result = await self.session.execute(
            select(ChapterCheckpoint)
            .where(
                ChapterCheckpoint.chapter_id == chapter_id,
                ChapterCheckpoint.checkpoint_type == CHECKPOINT_TYPE_GENERATION,
                ChapterCheckpoint.status == "completed",
            )
            .order_by(ChapterCheckpoint.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_checkpoint_by_id(
        self,
        checkpoint_id: uuid.UUID,
    ) -> Optional[ChapterCheckpoint]:
        result = await self.session.execute(
            select(ChapterCheckpoint).where(ChapterCheckpoint.id == checkpoint_id)
        )
        return result.scalar_one_or_none()

    def can_resume(self, checkpoint: ChapterCheckpoint) -> bool:
        if checkpoint.checkpoint_type != CHECKPOINT_TYPE_GENERATION:
            return False
        if checkpoint.segments_completed is None or checkpoint.segments_total is None:
            return False
        return checkpoint.segments_completed < checkpoint.segments_total
