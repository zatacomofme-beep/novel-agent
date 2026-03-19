"""Add chapter comment thread support.

Revision ID: 20260319_0011
Revises: 20260319_0010
Create Date: 2026-03-19 14:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0011"
down_revision = "20260319_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_comments",
        sa.Column("parent_comment_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_chapter_comments_parent_comment_id",
        "chapter_comments",
        ["parent_comment_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_chapter_comments_parent_comment_id_chapter_comments",
        "chapter_comments",
        "chapter_comments",
        ["parent_comment_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_chapter_comments_parent_comment_id_chapter_comments",
        "chapter_comments",
        type_="foreignkey",
    )
    op.drop_index(
        "ix_chapter_comments_parent_comment_id",
        table_name="chapter_comments",
    )
    op.drop_column("chapter_comments", "parent_comment_id")
