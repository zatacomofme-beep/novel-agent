"""Add generation resume fields to chapter_checkpoints.

Revision ID: 20260404_0001
Revises: 20260402_0002
Create Date: 2026-04-04 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260404_0001"
down_revision = "20260402_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_checkpoints",
        sa.Column("generation_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "chapter_checkpoints",
        sa.Column("generated_content", sa.Text(), nullable=True),
    )
    op.add_column(
        "chapter_checkpoints",
        sa.Column("progress", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chapter_checkpoints",
        sa.Column("segments_completed", sa.Integer(), nullable=True),
    )
    op.add_column(
        "chapter_checkpoints",
        sa.Column("segments_total", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chapter_checkpoints", "segments_total")
    op.drop_column("chapter_checkpoints", "segments_completed")
    op.drop_column("chapter_checkpoints", "progress")
    op.drop_column("chapter_checkpoints", "generated_content")
    op.drop_column("chapter_checkpoints", "generation_payload")
