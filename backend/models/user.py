from __future__ import annotations

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from models.refresh_token import RefreshToken


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    projects: Mapped[list["Project"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preference_profile: Mapped[Optional["UserPreference"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    preference_observations: Mapped[list["PreferenceObservation"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="PreferenceObservation.created_at.desc()",
    )
    project_collaborations: Mapped[list["ProjectCollaborator"]] = relationship(
        foreign_keys="ProjectCollaborator.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ProjectCollaborator.created_at.desc()",
    )
    project_collaborations_added: Mapped[list["ProjectCollaborator"]] = relationship(
        foreign_keys="ProjectCollaborator.added_by_user_id",
        back_populates="added_by",
        order_by="ProjectCollaborator.created_at.desc()",
    )
    chapter_comments: Mapped[list["ChapterComment"]] = relationship(
        foreign_keys="ChapterComment.user_id",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ChapterComment.created_at.desc()",
    )
    assigned_chapter_comments: Mapped[list["ChapterComment"]] = relationship(
        foreign_keys="ChapterComment.assignee_user_id",
        back_populates="assignee",
        order_by="ChapterComment.created_at.desc()",
    )
    chapter_comment_assignments_created: Mapped[list["ChapterComment"]] = relationship(
        foreign_keys="ChapterComment.assigned_by_user_id",
        back_populates="assigned_by",
        order_by="ChapterComment.created_at.desc()",
    )
    chapter_comment_resolutions: Mapped[list["ChapterComment"]] = relationship(
        foreign_keys="ChapterComment.resolved_by_user_id",
        back_populates="resolved_by",
        order_by="ChapterComment.created_at.desc()",
    )
    chapter_review_decisions: Mapped[list["ChapterReviewDecision"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="ChapterReviewDecision.created_at.desc()",
    )
    requested_checkpoints: Mapped[list["ChapterCheckpoint"]] = relationship(
        foreign_keys="ChapterCheckpoint.requester_user_id",
        back_populates="requester",
        cascade="all, delete-orphan",
        order_by="ChapterCheckpoint.created_at.desc()",
    )
    decided_checkpoints: Mapped[list["ChapterCheckpoint"]] = relationship(
        foreign_keys="ChapterCheckpoint.decided_by_user_id",
        back_populates="decided_by",
        order_by="ChapterCheckpoint.created_at.desc()",
    )
    refresh_tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="RefreshToken.created_at.desc()",
    )
    world_building_sessions: Mapped[list["WorldBuildingSession"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
