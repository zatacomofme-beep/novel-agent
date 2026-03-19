from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PreferenceObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "preference_observations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    chapter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)
    observed_preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    favored_elements: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    content_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)

    user: Mapped["User"] = relationship(back_populates="preference_observations")
    project: Mapped[Optional["Project"]] = relationship()
    chapter: Mapped[Optional["Chapter"]] = relationship()
