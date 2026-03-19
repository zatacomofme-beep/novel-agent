from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChapterCheckpoint(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_checkpoints"

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    checkpoint_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    decision_note: Mapped[Optional[str]] = mapped_column(Text)
    decided_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    chapter: Mapped["Chapter"] = relationship(back_populates="checkpoints")
    requester: Mapped["User"] = relationship(
        foreign_keys=[requester_user_id],
        back_populates="requested_checkpoints",
    )
    decided_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[decided_by_user_id],
        back_populates="decided_checkpoints",
    )
