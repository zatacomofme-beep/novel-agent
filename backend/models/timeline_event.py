from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TimelineEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "timeline_events"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped["Project"] = relationship(back_populates="timeline_events")
