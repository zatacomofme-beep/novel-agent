"""Add project bootstrap profile and novel blueprint columns.

Revision ID: 20260323_0016
Revises: 20260322_0015
Create Date: 2026-03-23 10:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0016"
down_revision = "20260322_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("bootstrap_profile", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "projects",
        sa.Column("novel_blueprint", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "novel_blueprint")
    op.drop_column("projects", "bootstrap_profile")
