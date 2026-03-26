from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoryRoomCloudDraft(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_room_cloud_drafts"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            "scope_key",
            name="uq_story_room_cloud_drafts_project_user_scope",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_branches.id", ondelete="SET NULL"),
        index=True,
    )
    volume_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_volumes.id", ondelete="SET NULL"),
        index=True,
    )
    source_chapter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    outline_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    scope_key: Mapped[str] = mapped_column(String(180), nullable=False, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    source_version_number: Mapped[Optional[int]] = mapped_column(Integer)

    project: Mapped["Project"] = relationship()
    user: Mapped["User"] = relationship()
    branch: Mapped[Optional["ProjectBranch"]] = relationship()
    volume: Mapped[Optional["ProjectVolume"]] = relationship()
    source_chapter: Mapped[Optional["Chapter"]] = relationship()
