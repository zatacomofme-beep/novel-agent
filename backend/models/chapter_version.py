from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ChapterVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapter_versions"
    __table_args__ = (
        UniqueConstraint(
            "chapter_id",
            "version_number",
            name="uq_chapter_versions_chapter_version_number",
        ),
    )

    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(Text)

    chapter: Mapped["Chapter"] = relationship(back_populates="versions")
