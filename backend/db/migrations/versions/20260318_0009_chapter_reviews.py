"""Add chapter review comments and decisions.

Revision ID: 20260318_0009
Revises: 20260318_0008
Create Date: 2026-03-18 23:58:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0009"
down_revision = "20260318_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_comments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_version_number", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("selection_start", sa.Integer(), nullable=True),
        sa.Column("selection_end", sa.Integer(), nullable=True),
        sa.Column("selection_text", sa.Text(), nullable=True),
        sa.Column("resolved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapter_comments"),
    )
    op.create_index(
        "ix_chapter_comments_chapter_id",
        "chapter_comments",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_comments_user_id",
        "chapter_comments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_comments_resolved_by_user_id",
        "chapter_comments",
        ["resolved_by_user_id"],
        unique=False,
    )

    op.create_table(
        "chapter_review_decisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_version_number", sa.Integer(), nullable=False),
        sa.Column("verdict", sa.String(length=50), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "focus_points",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
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
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_chapter_review_decisions"),
    )
    op.create_index(
        "ix_chapter_review_decisions_chapter_id",
        "chapter_review_decisions",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_review_decisions_user_id",
        "chapter_review_decisions",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chapter_review_decisions_user_id",
        table_name="chapter_review_decisions",
    )
    op.drop_index(
        "ix_chapter_review_decisions_chapter_id",
        table_name="chapter_review_decisions",
    )
    op.drop_table("chapter_review_decisions")

    op.drop_index(
        "ix_chapter_comments_resolved_by_user_id",
        table_name="chapter_comments",
    )
    op.drop_index(
        "ix_chapter_comments_user_id",
        table_name="chapter_comments",
    )
    op.drop_index(
        "ix_chapter_comments_chapter_id",
        table_name="chapter_comments",
    )
    op.drop_table("chapter_comments")
