from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class EditActionType(str, Enum):
    GENERATION = "generation"
    REVISION = "revision"
    MANUAL_EDIT = "manual_edit"
    REWRITE = "rewrite"
    IMPORT = "import"


class ChapterSnapshot(Base):
    __tablename__ = "chapter_snapshots"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    project_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )

    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    outline: Mapped[str | None] = mapped_column(Text, nullable=True)

    action_type: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    revision_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    content_length: Mapped[int] = mapped_column(Integer, default=0)

    diff_from_previous: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)

    created_by_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ChapterUndoStack(Base):
    __tablename__ = "chapter_undo_stacks"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, unique=True, index=True
    )

    current_pointer: Mapped[int] = mapped_column(Integer, default=-1)
    max_stack_size: Mapped[int] = mapped_column(Integer, default=50)
    total_snapshots: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
