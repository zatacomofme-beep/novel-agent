from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Evaluation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "evaluations"

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    overall_score: Mapped[float] = mapped_column(Float, nullable=False)
    ai_taste_score: Mapped[float] = mapped_column(Float, nullable=False)

    chapter: Mapped["Chapter"] = relationship(back_populates="evaluations")
