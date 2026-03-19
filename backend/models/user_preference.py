from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class UserPreference(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    active_template_key: Mapped[Optional[str]] = mapped_column(String(100))
    prose_style: Mapped[str] = mapped_column(String(50), default="precise", nullable=False)
    narrative_mode: Mapped[str] = mapped_column(
        String(50),
        default="close_third",
        nullable=False,
    )
    pacing_preference: Mapped[str] = mapped_column(
        String(50),
        default="balanced",
        nullable=False,
    )
    dialogue_preference: Mapped[str] = mapped_column(
        String(50),
        default="balanced",
        nullable=False,
    )
    tension_preference: Mapped[str] = mapped_column(
        String(50),
        default="balanced",
        nullable=False,
    )
    sensory_density: Mapped[str] = mapped_column(
        String(50),
        default="focused",
        nullable=False,
    )
    favored_elements: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    banned_patterns: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    custom_style_notes: Mapped[Optional[str]] = mapped_column(Text)

    user: Mapped["User"] = relationship(back_populates="preference_profile")
