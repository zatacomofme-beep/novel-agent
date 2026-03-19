"""Add chapter checkpoints.

Revision ID: 20260319_0010
Revises: 20260318_0009
Create Date: 2026-03-19 00:45:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260319_0010"
down_revision = "20260318_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chapter_checkpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("requester_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_version_number", sa.Integer(), nullable=False),
        sa.Column("checkpoint_type", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("decided_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["requester_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_chapter_checkpoints"),
    )
    op.create_index(
        "ix_chapter_checkpoints_chapter_id",
        "chapter_checkpoints",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_checkpoints_requester_user_id",
        "chapter_checkpoints",
        ["requester_user_id"],
        unique=False,
    )
    op.create_index(
        "ix_chapter_checkpoints_decided_by_user_id",
        "chapter_checkpoints",
        ["decided_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_chapter_checkpoints_decided_by_user_id",
        table_name="chapter_checkpoints",
    )
    op.drop_index(
        "ix_chapter_checkpoints_requester_user_id",
        table_name="chapter_checkpoints",
    )
    op.drop_index(
        "ix_chapter_checkpoints_chapter_id",
        table_name="chapter_checkpoints",
    )
    op.drop_table("chapter_checkpoints")
