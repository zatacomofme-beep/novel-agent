from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoryBibleChangeType(str, Enum):
    ADDED = "added"
    UPDATED = "updated"
    REMOVED = "removed"


class StoryBibleSection(str, Enum):
    CHARACTERS = "characters"
    WORLD_SETTINGS = "world_settings"
    ITEMS = "items"
    FACTIONS = "factions"
    LOCATIONS = "locations"
    PLOT_THREADS = "plot_threads"
    FORESHADOWING = "foreshadowing"
    TIMELINE_EVENTS = "timeline_events"


class StoryBibleChangeSource(str, Enum):
    USER = "user"
    AI_PROPOSED = "ai_proposed"
    AUTO_TRIGGER = "auto_trigger"


class StoryBiblePendingChangeStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class StoryBibleVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_bible_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "branch_id",
            "version_number",
            name="uq_story_bible_versions_project_branch_version",
        ),
        Index(
            "ix_story_bible_versions_project_branch",
            "project_id",
            "branch_id",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    change_type: Mapped[str] = mapped_column(nullable=False)
    change_source: Mapped[str] = mapped_column(nullable=False, default=StoryBibleChangeSource.USER.value)
    changed_section: Mapped[str] = mapped_column(nullable=False)
    changed_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_entity_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    note: Mapped[Optional[str]] = mapped_column(nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="story_bible_versions")
    branch: Mapped["ProjectBranch"] = relationship(back_populates="story_bible_versions")


class StoryBiblePendingChange(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "story_bible_pending_changes"
    __table_args__ = (
        Index(
            "ix_story_bible_pending_changes_project_branch",
            "project_id",
            "branch_id",
        ),
        Index(
            "ix_story_bible_pending_changes_status",
            "status",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    branch_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        nullable=False,
        default=StoryBiblePendingChangeStatus.PENDING.value,
        index=True,
    )
    change_type: Mapped[str] = mapped_column(nullable=False)
    change_source: Mapped[str] = mapped_column(nullable=False, default=StoryBibleChangeSource.AI_PROPOSED.value)
    changed_section: Mapped[str] = mapped_column(nullable=False)
    changed_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    changed_entity_key: Mapped[Optional[str]] = mapped_column(nullable=True)
    old_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(nullable=True)
    triggered_by_chapter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    proposed_by_agent: Mapped[Optional[str]] = mapped_column(nullable=True)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped["Project"] = relationship(back_populates="story_bible_pending_changes")
    branch: Mapped["ProjectBranch"] = relationship(back_populates="story_bible_pending_changes")
    triggered_by_chapter: Mapped[Optional["Chapter"]] = relationship()
