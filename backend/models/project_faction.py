from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectFaction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_factions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    faction_type: Mapped[Optional[str]] = mapped_column(String(100))
    scale: Mapped[Optional[str]] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(Text)
    goals: Mapped[Optional[str]] = mapped_column(Text)
    leader: Mapped[Optional[str]] = mapped_column(String(255))
    members: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    territory: Mapped[Optional[str]] = mapped_column(String(255))
    resources: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    ideology: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="factions")
