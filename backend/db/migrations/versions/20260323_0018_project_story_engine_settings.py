"""Add project-level story engine settings.

Revision ID: 20260323_0018
Revises: 20260323_0017
Create Date: 2026-03-23 22:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0018"
down_revision = "20260323_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("story_engine_settings", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "story_engine_settings")
