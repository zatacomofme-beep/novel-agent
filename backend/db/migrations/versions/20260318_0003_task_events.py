"""Add task_events table.

Revision ID: 20260318_0003
Revises: 20260318_0002
Create Date: 2026-03-18 03:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0003"
down_revision = "20260318_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_task_events"),
    )
    op.create_index("ix_task_events_task_id", "task_events", ["task_id"], unique=False)
    op.create_index("ix_task_events_event_type", "task_events", ["event_type"], unique=False)
    op.create_index("ix_task_events_chapter_id", "task_events", ["chapter_id"], unique=False)
    op.create_index("ix_task_events_project_id", "task_events", ["project_id"], unique=False)
    op.create_index("ix_task_events_user_id", "task_events", ["user_id"], unique=False)
    op.create_index("ix_task_events_created_at", "task_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_events_created_at", table_name="task_events")
    op.drop_index("ix_task_events_user_id", table_name="task_events")
    op.drop_index("ix_task_events_project_id", table_name="task_events")
    op.drop_index("ix_task_events_chapter_id", table_name="task_events")
    op.drop_index("ix_task_events_event_type", table_name="task_events")
    op.drop_index("ix_task_events_task_id", table_name="task_events")
    op.drop_table("task_events")
