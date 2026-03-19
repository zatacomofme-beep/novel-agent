from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProjectCollaborator(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_collaborators"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_collaborators_project_user",
        ),
    )

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
    added_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    role: Mapped[str] = mapped_column(String(50), nullable=False)

    project: Mapped["Project"] = relationship(back_populates="collaborators")
    user: Mapped["User"] = relationship(
        foreign_keys=[user_id],
        back_populates="project_collaborations",
    )
    added_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[added_by_user_id],
        back_populates="project_collaborations_added",
    )
