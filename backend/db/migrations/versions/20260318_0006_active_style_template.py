"""Add active template key to user_preferences.

Revision ID: 20260318_0006
Revises: 20260318_0005
Create Date: 2026-03-18 20:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260318_0006"
down_revision = "20260318_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_preferences",
        sa.Column("active_template_key", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_preferences", "active_template_key")
