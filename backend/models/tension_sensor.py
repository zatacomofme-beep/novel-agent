from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from models.base import Base


class TensionLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class TensionCheckpoint(Base):
    __tablename__ = "tension_checkpoints"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_index: Mapped[int] = mapped_column(Integer, default=0)

    tension_level: Mapped[str] = mapped_column(String(20), nullable=False)
    tension_score: Mapped[float] = mapped_column(Float, default=0.0)

    tension_risers: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    tension_reducers: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    emotional_arc_position: Mapped[str] = mapped_column(String(50), nullable=True)
    hook_strength: Mapped[float] = mapped_column(Float, default=0.5)
    payoff_pending: Mapped[bool] = mapped_column(default=False)
    payoff_chapter: Mapped[int | None] = mapped_column(Integer, nullable=True)

    analysis_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_intervention: Mapped[str | None] = mapped_column(String(200), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChapterTensionProfile(Base):
    __tablename__ = "chapter_tension_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, unique=True, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    avg_tension: Mapped[float] = mapped_column(Float, default=0.0)
    peak_tension: Mapped[float] = mapped_column(Float, default=0.0)
    tension_trend: Mapped[str] = mapped_column(String(20), default="stable")
    pacing_score: Mapped[float] = mapped_column(Float, default=0.5)

    scene_count: Mapped[int] = mapped_column(Integer, default=0)
    high_tension_scene_count: Mapped[int] = mapped_column(Integer, default=0)
    low_tension_scene_count: Mapped[int] = mapped_column(Integer, default=0)

    chapter_emotional_arc: Mapped[list[float]] = mapped_column(JSONB, default=list)
    tension_curve_data: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    unresolved_tension_count: Mapped[int] = mapped_column(Integer, default=0)
    forced_payoff_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
