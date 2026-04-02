"""Add chapter editing sessions for collaboration awareness.

Revision ID: 20260326_0023
Revises: 20260326_0022
Create Date: 2026-03-26 21:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260326_0023"
down_revision = "20260326_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_editing_sessions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("last_seen_version_number", sa.Integer(), nullable=True),
        sa.Column(
            "last_heartbeat_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_chapter_editing_sessions")),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            "source",
            name="uq_chapter_editing_sessions_project_user_source",
        ),
    )
    op.create_index(
        op.f("ix_chapter_editing_sessions_project_id"),
        "chapter_editing_sessions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapter_editing_sessions_chapter_id"),
        "chapter_editing_sessions",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapter_editing_sessions_user_id"),
        "chapter_editing_sessions",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapter_editing_sessions_last_heartbeat_at"),
        "chapter_editing_sessions",
        ["last_heartbeat_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_chapter_editing_sessions_last_heartbeat_at"),
        table_name="chapter_editing_sessions",
    )
    op.drop_index(op.f("ix_chapter_editing_sessions_user_id"), table_name="chapter_editing_sessions")
    op.drop_index(
        op.f("ix_chapter_editing_sessions_chapter_id"),
        table_name="chapter_editing_sessions",
    )
    op.drop_index(
        op.f("ix_chapter_editing_sessions_project_id"),
        table_name="chapter_editing_sessions",
    )
    op.drop_table("chapter_editing_sessions")
