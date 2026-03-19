from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectVolume(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_volumes"
    __table_args__ = (
        UniqueConstraint("project_id", "volume_number", name="uq_project_volumes_project_number"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="planning", nullable=False)

    project: Mapped["Project"] = relationship(back_populates="volumes")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="volume")
