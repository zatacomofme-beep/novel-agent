from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    genre: Mapped[Optional[str]] = mapped_column(String(100))
    theme: Mapped[Optional[str]] = mapped_column(Text)
    tone: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    bootstrap_profile: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    novel_blueprint: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    story_engine_settings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    initial_idea: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    world_building_completed: Mapped[bool] = mapped_column(default=False, nullable=False)
    current_phase: Mapped[str] = mapped_column(String(50), default="world-building", nullable=False)

    user: Mapped["User"] = relationship(back_populates="projects")
    characters: Mapped[list["Character"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    world_settings: Mapped[list["WorldSetting"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    items: Mapped[list["ProjectItem"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    factions: Mapped[list["ProjectFaction"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    locations: Mapped[list["Location"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    plot_threads: Mapped[list["PlotThread"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    foreshadowing_items: Mapped[list["Foreshadowing"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    timeline_events: Mapped[list["TimelineEvent"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
    volumes: Mapped[list["ProjectVolume"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectVolume.volume_number",
    )
    branches: Mapped[list["ProjectBranch"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectBranch.created_at",
    )
    collaborators: Mapped[list["ProjectCollaborator"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectCollaborator.created_at",
    )
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Chapter.chapter_number",
    )
    story_bible_versions: Mapped[list["StoryBibleVersion"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="StoryBibleVersion.version_number.desc()",
    )
    story_bible_pending_changes: Mapped[list["StoryBiblePendingChange"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="StoryBiblePendingChange.created_at.desc()",
    )
    world_building_sessions: Mapped[list["WorldBuildingSession"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )
