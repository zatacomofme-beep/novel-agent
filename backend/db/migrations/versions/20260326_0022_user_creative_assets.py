"""Add user creative asset library.

Revision ID: 20260326_0022
Revises: 20260326_0021
Create Date: 2026-03-26 20:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260326_0022"
down_revision = "20260326_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_creative_assets",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_kind", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_creative_assets")),
    )
    op.create_index(
        op.f("ix_user_creative_assets_asset_kind"),
        "user_creative_assets",
        ["asset_kind"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_creative_assets_user_id"),
        "user_creative_assets",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_user_creative_assets_user_id"), table_name="user_creative_assets")
    op.drop_index(op.f("ix_user_creative_assets_asset_kind"), table_name="user_creative_assets")
    op.drop_table("user_creative_assets")
