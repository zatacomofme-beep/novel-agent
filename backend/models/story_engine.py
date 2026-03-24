from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from db.base import Base, TimestampMixin


class StoryCharacter(TimestampMixin, Base):
    __tablename__ = "story_characters"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_story_characters_project_name"),
    )

    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    appearance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personality: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    micro_habits: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    abilities: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    relationships: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(100), nullable=False, default="active")
    arc_stage: Mapped[str] = mapped_column(String(100), nullable=False, default="initial")
    arc_boundaries: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryForeshadow(TimestampMixin, Base):
    __tablename__ = "story_foreshadows"

    foreshadow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chapter_planted: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    chapter_planned_reveal: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    related_characters: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    related_items: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryItem(TimestampMixin, Base):
    __tablename__ = "story_items"
    __table_args__ = (
        UniqueConstraint("project_id", "name", name="uq_story_items_project_name"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    features: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    owner: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    special_rules: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryWorldRule(TimestampMixin, Base):
    __tablename__ = "story_world_rules"
    __table_args__ = (
        UniqueConstraint("project_id", "rule_name", name="uq_story_world_rules_project_name"),
    )

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_content: Mapped[str] = mapped_column(Text, nullable=False)
    negative_list: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    scope: Mapped[str] = mapped_column(String(100), nullable=False, default="global")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryTimelineMapEvent(TimestampMixin, Base):
    __tablename__ = "story_timeline_map_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    in_universe_time: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    weather: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    core_event: Mapped[str] = mapped_column(Text, nullable=False)
    character_states: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryOutline(TimestampMixin, Base):
    __tablename__ = "story_outlines"

    outline_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("story_outlines.outline_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="todo")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    node_order: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    immutable_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    parent: Mapped[Optional["StoryOutline"]] = relationship(
        "StoryOutline",
        remote_side="StoryOutline.outline_id",
        back_populates="children",
    )
    children: Mapped[list["StoryOutline"]] = relationship(
        "StoryOutline",
        back_populates="parent",
        cascade="all, delete-orphan",
        order_by="StoryOutline.node_order",
    )


class StoryChapterSummary(TimestampMixin, Base):
    __tablename__ = "story_chapter_summaries"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "chapter_number",
            name="uq_story_chapter_summaries_project_chapter",
        ),
    )

    summary_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    core_progress: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    character_changes: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    foreshadow_updates: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    kb_update_suggestions: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class StoryKnowledgeVersion(Base):
    __tablename__ = "story_knowledge_versions"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "entity_type",
            "entity_id",
            "version_number",
            name="uq_story_knowledge_versions_entity_version",
        ),
    )

    version_record_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_workflow: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
