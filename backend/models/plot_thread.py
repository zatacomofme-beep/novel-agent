from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PlotThread(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "plot_threads"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="planned", nullable=False)
    importance: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    project: Mapped["Project"] = relationship(back_populates="plot_threads")
