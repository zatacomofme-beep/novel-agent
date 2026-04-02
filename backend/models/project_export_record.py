from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectExportRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_export_records"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    export_format: Mapped[str] = mapped_column(String(20), nullable=False)
    scope_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    volume_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    chapter_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)
    chapter_numbers: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    chapter_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    include_cover_page: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    include_metadata: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    package_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    package_subtitle: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    author_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    synopsis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    project: Mapped["Project"] = relationship(back_populates="export_records")
    user: Mapped["User"] = relationship(back_populates="project_export_records")
