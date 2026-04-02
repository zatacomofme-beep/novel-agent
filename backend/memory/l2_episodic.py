from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base


class ChapterEpisode(Base):
    __tablename__ = "chapter_episodes"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, unique=True, index=True
    )

    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[list[str]] = mapped_column(JSONB, default=list)
    characters: Mapped[list[str]] = mapped_column(JSONB, default=list)
    locations: Mapped[list[str]] = mapped_column(JSONB, default=list)
    emotional_tone: Mapped[str] = mapped_column(String(50), default="neutral")
    themes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    open_threads: Mapped[list[str]] = mapped_column(JSONB, default=list)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    importance_score: Mapped[float] = mapped_column(JSONB, default=0.5)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class L2EpisodicMemory:
    def __init__(self, session: Optional["AsyncSession"] = None) -> None:
        self._session = session

    @staticmethod
    def compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    async def save_episode(
        self,
        project_id: UUID,
        chapter_id: UUID,
        chapter_number: int,
        summary: str,
        content: str,
        key_events: list[str] | None = None,
        characters: list[str] | None = None,
        locations: list[str] | None = None,
        emotional_tone: str = "neutral",
        themes: list[str] | None = None,
        open_threads: list[str] | None = None,
        importance_score: float = 0.5,
    ) -> ChapterEpisode:
        from uuid import uuid4
        content_hash = self.compute_content_hash(content)

        episode = ChapterEpisode(
            id=uuid4(),
            project_id=project_id,
            chapter_id=chapter_id,
            chapter_number=chapter_number,
            summary=summary,
            key_events=key_events or [],
            characters=characters or [],
            locations=locations or [],
            emotional_tone=emotional_tone,
            themes=themes or [],
            open_threads=open_threads or [],
            content_hash=content_hash,
            word_count=len(content),
            importance_score=importance_score,
        )
        if self._session is not None:
            self._session.add(episode)
            await self._session.flush()
        return episode

    async def get_episode(self, chapter_id: UUID) -> ChapterEpisode | None:
        from sqlalchemy import select
        if self._session is None:
            return None
        result = await self._session.execute(
            select(ChapterEpisode).where(ChapterEpisode.chapter_id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def get_project_episodes(
        self,
        project_id: UUID,
        limit: int = 10,
    ) -> list[ChapterEpisode]:
        from sqlalchemy import select
        if self._session is None:
            return []
        result = await self._session.execute(
            select(ChapterEpisode)
            .where(ChapterEpisode.project_id == project_id)
            .order_by(ChapterEpisode.chapter_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_episodes(
        self,
        project_id: UUID,
        before_chapter: int,
        limit: int = 5,
    ) -> list[ChapterEpisode]:
        from sqlalchemy import select
        if self._session is None:
            return []
        result = await self._session.execute(
            select(ChapterEpisode)
            .where(
                ChapterEpisode.project_id == project_id,
                ChapterEpisode.chapter_number < before_chapter,
            )
            .order_by(ChapterEpisode.chapter_number.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
