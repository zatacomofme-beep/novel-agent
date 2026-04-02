"""Add chapter assignment fields for collaboration workflow.

Revision ID: 20260327_0025
Revises: 20260327_0024
Create Date: 2026-03-27 14:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260327_0025"
down_revision = "20260327_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_chapters_assignee_user_id_users"),
        "chapters",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_chapters_assigned_by_user_id_users"),
        "chapters",
        "users",
        ["assigned_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_chapters_assignee_user_id"),
        "chapters",
        ["assignee_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_chapters_assigned_by_user_id"),
        "chapters",
        ["assigned_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_chapters_assigned_by_user_id"), table_name="chapters")
    op.drop_index(op.f("ix_chapters_assignee_user_id"), table_name="chapters")
    op.drop_constraint(
        op.f("fk_chapters_assigned_by_user_id_users"),
        "chapters",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_chapters_assignee_user_id_users"),
        "chapters",
        type_="foreignkey",
    )
    op.drop_column("chapters", "assigned_at")
    op.drop_column("chapters", "assigned_by_user_id")
    op.drop_column("chapters", "assignee_user_id")
