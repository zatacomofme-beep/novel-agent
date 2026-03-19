"""Add chapter comment assignment fields.

Revision ID: 20260319_0012
Revises: 20260319_0011
Create Date: 2026-03-19 16:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0012"
down_revision = "20260319_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_comments",
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapter_comments",
        sa.Column("assigned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapter_comments",
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_chapter_comments_assignee_user_id",
        "chapter_comments",
        ["assignee_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_comments_assigned_by_user_id",
        "chapter_comments",
        ["assigned_by_user_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_chapter_comments_assignee_user_id_users",
        "chapter_comments",
        "users",
        ["assignee_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_chapter_comments_assigned_by_user_id_users",
        "chapter_comments",
        "users",
        ["assigned_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_chapter_comments_assigned_by_user_id_users",
        "chapter_comments",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_chapter_comments_assignee_user_id_users",
        "chapter_comments",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_chapter_comments_assigned_by_user_id",
        table_name="chapter_comments",
    )
    op.drop_index(
        "ix_chapter_comments_assignee_user_id",
        table_name="chapter_comments",
    )
    op.drop_column("chapter_comments", "assigned_at")
    op.drop_column("chapter_comments", "assigned_by_user_id")
    op.drop_column("chapter_comments", "assignee_user_id")
