from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChapterReviewDecision(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_review_decisions"

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    verdict: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    focus_points: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="review_decisions")
    user: Mapped["User"] = relationship(back_populates="chapter_review_decisions")
