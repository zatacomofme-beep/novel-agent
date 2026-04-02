"""Add world building sessions for guided worldview creation.

Revision ID: 20260327_0026
Revises: 20260327_0025
Create Date: 2026-03-27 15:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260327_0026"
down_revision = "20260327_0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "world_building_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
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
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("current_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_active_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "session_data",
            postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="in_progress",
        ),
        sa.Column(
            "completed_steps",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
    )
    op.create_index(
        "ix_world_building_sessions_project_user",
        "world_building_sessions",
        ["project_id", "user_id"],
        unique=False,
    )
    op.create_index(
        "ix_world_building_sessions_status",
        "world_building_sessions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_world_building_sessions_status", table_name="world_building_sessions")
    op.drop_index("ix_world_building_sessions_project_user", table_name="world_building_sessions")
    op.drop_table("world_building_sessions")
