from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from models.base import Base


class RelationshipType(str, Enum):
    FAMILY = "family"
    FRIEND = "friend"
    ENEMY = "enemy"
    ROMANTIC = "romantic"
    MENTOR = "mentor"
    RIVAL = "rival"
    COLLEAGUE = "colleague"
    STRANGER = "stranger"


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    from_character_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True
    )
    to_character_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True
    )

    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    strength: Mapped[float] = mapped_column(Float, default=0.5)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CharacterSocialTopology(Base):
    __tablename__ = "character_social_topologies"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, unique=True, index=True
    )

    centrality_scores: Mapped[dict] = mapped_column(JSONB, default=dict)
    cluster_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    influence_graph: Mapped[dict] = mapped_column(JSONB, default=dict)
    social_dynamics: Mapped[dict] = mapped_column(JSONB, default=dict)

    last_chapter_analyzed: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class InteractionLog(Base):
    __tablename__ = "character_interaction_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    character_a_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    character_b_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)

    interaction_type: Mapped[str] = mapped_column(String(100), nullable=False)
    emotional_tone: Mapped[str] = mapped_column(String(50), nullable=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
