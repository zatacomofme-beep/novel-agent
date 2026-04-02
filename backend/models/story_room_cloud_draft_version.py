from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Index, String, Text, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoryRoomCloudDraftVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_room_cloud_draft_versions"
    __table_args__ = (
        Index("ix_cloud_draft_versions_draft_id", "draft_id"),
        Index("ix_cloud_draft_versions_created_at", "created_at"),
    )

    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_room_cloud_drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    chapter_title: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    source_version_number: Mapped[int] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delta_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    save_trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="auto")
