from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Chapter(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "chapters"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "branch_id",
            "volume_id",
            "chapter_number",
            name="uq_chapters_project_branch_volume_number",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    volume_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_volumes.id", ondelete="SET NULL"),
        index=True,
    )
    branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_branches.id", ondelete="SET NULL"),
        index=True,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    outline: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)
    word_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    quality_metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB)

    project: Mapped["Project"] = relationship(back_populates="chapters")
    volume: Mapped["ProjectVolume | None"] = relationship(back_populates="chapters")
    branch: Mapped["ProjectBranch | None"] = relationship(back_populates="chapters")
    versions: Mapped[list["ChapterVersion"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterVersion.version_number",
    )
    evaluations: Mapped[list["Evaluation"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["ChapterComment"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterComment.created_at.desc()",
    )
    review_decisions: Mapped[list["ChapterReviewDecision"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterReviewDecision.created_at.desc()",
    )
    checkpoints: Mapped[list["ChapterCheckpoint"]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        order_by="ChapterCheckpoint.created_at.desc()",
    )
