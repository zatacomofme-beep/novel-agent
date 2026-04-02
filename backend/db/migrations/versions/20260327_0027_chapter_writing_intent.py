"""Add writing intent fields to chapters for user confirmation workflow.

Revision ID: 20260327_0027
Revises: 20260327_0026
Create Date: 2026-03-27 16:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260327_0027"
down_revision = "20260327_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column("writing_intent", sa.Text(), nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("writing_intent_approved", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("chapters", "writing_intent_approved")
    op.drop_column("chapters", "writing_intent")
