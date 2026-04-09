from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from models.base import Base


class CharacterLinguisticProfile(Base):
    __tablename__ = "character_linguistic_profiles"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    character_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    avg_sentence_length: Mapped[float] = mapped_column(Float, default=0.0)
    avg_paragraph_length: Mapped[float] = mapped_column(Float, default=0.0)
    unique_word_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    dialogue_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    question_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    exclamation_ratio: Mapped[float] = mapped_column(Float, default=0.0)

    common_phrases: Mapped[list[str]] = mapped_column(JSONB, default=list)
    speech_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    vocabulary_level: Mapped[int] = mapped_column(Integer, default=3)

    sample_dialogue: Mapped[str | None] = mapped_column(Text, nullable=True)
    personality_tags: Mapped[list[str]] = mapped_column(JSONB, default=list)
    linguistic_signature: Mapped[str | None] = mapped_column(Text, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    character: Mapped[Character] = relationship("Character", back_populates="linguistic_profile")  # noqa: F821,E501


class LinguisticConsistencyLog(Base):
    __tablename__ = "linguistic_consistency_logs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    character_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False, index=True
    )
    profile_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("character_linguistic_profiles.id"), nullable=False
    )

    consistency_score: Mapped[float] = mapped_column(Float, default=0.0)
    issues: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    detected_deviations: Mapped[list[dict]] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
