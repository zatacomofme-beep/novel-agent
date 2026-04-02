from __future__ import annotations

import hashlib
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from models.chapter_snapshot import ChapterSnapshot, ChapterUndoStack, EditActionType


class UndoRedoService:
    MAX_STACK_SIZE = 50

    async def create_snapshot(
        self,
        session: AsyncSession,
        chapter_id: uuid.UUID,
        project_id: uuid.UUID,
        content: str,
        action_type: str,
        *,
        outline: str | None = None,
        trigger_agent: str | None = None,
        revision_round: int | None = None,
        user_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> ChapterSnapshot:
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        stack = await self._get_or_create_stack(session, chapter_id)
        current_pointer = stack.current_pointer
        total_snapshots = stack.total_snapshots

        new_version = total_snapshots

        snapshot = ChapterSnapshot(
            chapter_id=chapter_id,
            project_id=project_id,
            version_number=new_version,
            content=content,
            outline=outline,
            action_type=action_type,
            trigger_agent=trigger_agent,
            revision_round=revision_round,
            content_hash=content_hash,
            content_length=len(content),
            metadata=metadata or {},
            created_by_user_id=user_id,
        )
        session.add(snapshot)

        if current_pointer < new_version - 1:
            await session.execute(
                update(ChapterUndoStack)
                .where(ChapterUndoStack.chapter_id == chapter_id)
                .values(current_pointer=new_version)
            )

        await session.execute(
            update(ChapterUndoStack)
            .where(ChapterUndoStack.chapter_id == chapter_id)
            .values(
                current_pointer=new_version,
                total_snapshots=new_version + 1,
                updated_at=datetime.utcnow(),
            )
        )

        await session.flush()
        return snapshot

    async def undo(
        self,
        session: AsyncSession,
        chapter_id: uuid.UUID,
    ) -> ChapterSnapshot | None:
        stack = await self._get_or_create_stack(session, chapter_id)
        if stack.current_pointer <= 0:
            return None

        new_pointer = stack.current_pointer - 1
        result = await session.execute(
            select(ChapterSnapshot)
            .where(
                ChapterSnapshot.chapter_id == chapter_id,
                ChapterSnapshot.version_number == new_pointer,
            )
            .order_by(ChapterSnapshot.version_number)
        )
        snapshot = result.scalar_one_or_none()

        if snapshot:
            await session.execute(
                update(ChapterUndoStack)
                .where(ChapterUndoStack.chapter_id == chapter_id)
                .values(current_pointer=new_pointer)
            )
            await session.flush()

        return snapshot

    async def redo(
        self,
        session: AsyncSession,
        chapter_id: uuid.UUID,
    ) -> ChapterSnapshot | None:
        stack = await self._get_or_create_stack(session, chapter_id)
        max_version = stack.total_snapshots - 1

        if stack.current_pointer >= max_version:
            return None

        new_pointer = stack.current_pointer + 1
        result = await session.execute(
            select(ChapterSnapshot)
            .where(
                ChapterSnapshot.chapter_id == chapter_id,
                ChapterSnapshot.version_number == new_pointer,
            )
        )
        snapshot = result.scalar_one_or_none()

        if snapshot:
            await session.execute(
                update(ChapterUndoStack)
                .where(ChapterUndoStack.chapter_id == chapter_id)
                .values(current_pointer=new_pointer)
            )
            await session.flush()

        return snapshot

    async def can_undo(self, session: AsyncSession, chapter_id: uuid.UUID) -> bool:
        stack = await self._get_or_create_stack(session, chapter_id)
        return stack.current_pointer > 0

    async def can_redo(self, session: AsyncSession, chapter_id: uuid.UUID) -> bool:
        stack = await self._get_or_create_stack(session, chapter_id)
        return stack.current_pointer < stack.total_snapshots - 1

    async def get_snapshot_history(
        self,
        session: AsyncSession,
        chapter_id: uuid.UUID,
        limit: int = 20,
    ) -> list[ChapterSnapshot]:
        result = await session.execute(
            select(ChapterSnapshot)
            .where(ChapterSnapshot.chapter_id == chapter_id)
            .order_by(ChapterSnapshot.version_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def _get_or_create_stack(
        self,
        session: AsyncSession,
        chapter_id: uuid.UUID,
    ) -> ChapterUndoStack:
        result = await session.execute(
            select(ChapterUndoStack).where(
                ChapterUndoStack.chapter_id == chapter_id
            )
        )
        stack = result.scalar_one_or_none()
        if stack is None:
            stack = ChapterUndoStack(
                chapter_id=chapter_id,
                current_pointer=-1,
                max_stack_size=self.MAX_STACK_SIZE,
                total_snapshots=0,
            )
            session.add(stack)
            await session.flush()
        return stack


undo_redo_service = UndoRedoService()
