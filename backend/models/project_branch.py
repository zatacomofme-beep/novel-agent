from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectBranch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_branches"
    __table_args__ = (
        UniqueConstraint("project_id", "key", name="uq_project_branches_project_key"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_branch_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("project_branches.id", ondelete="SET NULL"),
        index=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="branches")
    source_branch: Mapped[Optional["ProjectBranch"]] = relationship(
        remote_side="ProjectBranch.id",
    )
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="branch")
    story_bible_versions: Mapped[list["StoryBibleVersion"]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="StoryBibleVersion.version_number.desc()",
    )
    story_bible_pending_changes: Mapped[list["StoryBiblePendingChange"]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan",
        order_by="StoryBiblePendingChange.created_at.desc()",
    )
