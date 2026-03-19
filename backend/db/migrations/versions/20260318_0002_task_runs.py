"""Add task_runs table.

Revision ID: 20260318_0002
Revises: 20260318_0001
Create Date: 2026-03-18 00:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0002"
down_revision = "20260318_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("result", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_task_runs"),
        sa.UniqueConstraint("task_id", name="uq_task_runs_task_id"),
    )
    op.create_index("ix_task_runs_task_id", "task_runs", ["task_id"], unique=False)
    op.create_index("ix_task_runs_chapter_id", "task_runs", ["chapter_id"], unique=False)
    op.create_index("ix_task_runs_project_id", "task_runs", ["project_id"], unique=False)
    op.create_index("ix_task_runs_user_id", "task_runs", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_runs_user_id", table_name="task_runs")
    op.drop_index("ix_task_runs_project_id", table_name="task_runs")
    op.drop_index("ix_task_runs_chapter_id", table_name="task_runs")
    op.drop_index("ix_task_runs_task_id", table_name="task_runs")
    op.drop_table("task_runs")
