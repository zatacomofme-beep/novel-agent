from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class TaskRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "task_runs"

    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    error: Mapped[Optional[str]] = mapped_column(Text)

    chapter_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="SET NULL"),
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    chapter: Mapped[Optional["Chapter"]] = relationship()
    project: Mapped[Optional["Project"]] = relationship()
    user: Mapped[Optional["User"]] = relationship()
