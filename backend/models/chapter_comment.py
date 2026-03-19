from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChapterComment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_comments"

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
    parent_comment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapter_comments.id", ondelete="SET NULL"),
        index=True,
    )
    chapter_version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    selection_start: Mapped[Optional[int]] = mapped_column(Integer)
    selection_end: Mapped[Optional[int]] = mapped_column(Integer)
    selection_text: Mapped[Optional[str]] = mapped_column(Text)
    assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    assigned_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resolved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    chapter: Mapped["Chapter"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        back_populates="chapter_comments",
    )
    parent_comment: Mapped[Optional["ChapterComment"]] = relationship(
        remote_side="ChapterComment.id",
        foreign_keys=[parent_comment_id],
        back_populates="replies",
    )
    replies: Mapped[list["ChapterComment"]] = relationship(
        foreign_keys="ChapterComment.parent_comment_id",
        back_populates="parent_comment",
        order_by="ChapterComment.created_at.asc()",
    )
    assignee: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assignee_user_id],
        back_populates="assigned_chapter_comments",
    )
    assigned_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[assigned_by_user_id],
        back_populates="chapter_comment_assignments_created",
    )
    resolved_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[resolved_by_user_id],
        back_populates="chapter_comment_resolutions",
    )
