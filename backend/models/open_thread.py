from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ThreadStatus:
    OPEN = "open"
    TRACKING = "tracking"
    RESOLUTION_PENDING = "resolution_pending"
    RESOLVED = "resolved"
    ABANDONED = "abandoned"


class EntityType:
    ITEM = "item"
    CHARACTER = "character"
    EVENT = "event"
    RELATIONSHIP = "relationship"
    LOCATION = "location"
    WORLD_RULE = "world_rule"


class OpenThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "open_threads"
    __table_args__ = (
        Index("ix_open_threads_project_status", "project_id", "status"),
        Index("ix_open_threads_project_tracking", "project_id", "payoff_priority"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    planted_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    entity_ref: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    potential_tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    status: Mapped[str] = mapped_column(
        String(30),
        default=ThreadStatus.OPEN,
        nullable=False,
    )

    payoff_chapter: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payoff_priority: Mapped[float] = mapped_column(
        default=0.0,
        nullable=False,
    )
    resolution_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    planted_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planted_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    last_tracked_chapter: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    metadata_: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSONB, default=dict
    )

    version: Mapped[int] = mapped_column(default=1, nullable=False)

    def mark_tracking(self) -> None:
        if self.status == ThreadStatus.OPEN:
            self.status = ThreadStatus.TRACKING

    def mark_resolution_pending(self, chapter: int) -> None:
        self.status = ThreadStatus.RESOLUTION_PENDING
        self.payoff_chapter = chapter

    def mark_resolved(self, summary: str) -> None:
        self.status = ThreadStatus.RESOLVED
        self.resolution_summary = summary

    def mark_abandoned(self, reason: Optional[str] = None) -> None:
        self.status = ThreadStatus.ABANDONED
        if reason:
            self.metadata_ = self.metadata_ or {}
            self.metadata_["abandoned_reason"] = reason

    def bump_priority(self, delta: float) -> None:
        self.payoff_priority = min(1.0, self.payoff_priority + delta)

    def update_tracking_chapter(self, chapter: int) -> None:
        self.last_tracked_chapter = chapter
        self.version += 1


class OpenThreadHistory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "open_thread_history"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("open_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    old_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    new_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    delta_priority: Mapped[Optional[float]] = mapped_column(nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
