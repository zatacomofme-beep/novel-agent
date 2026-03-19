"""Add preference_observations table.

Revision ID: 20260318_0005
Revises: 20260318_0004
Create Date: 2026-03-18 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0005"
down_revision = "20260318_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preference_observations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column(
            "observed_preferences",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "favored_elements",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "content_metrics",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence_score", sa.Float(), nullable=True),
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
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_preference_observations"),
    )
    op.create_index(
        "ix_preference_observations_user_id",
        "preference_observations",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_preference_observations_project_id",
        "preference_observations",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_preference_observations_chapter_id",
        "preference_observations",
        ["chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_preference_observations_source_type",
        "preference_observations",
        ["source_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_preference_observations_source_type",
        table_name="preference_observations",
    )
    op.drop_index(
        "ix_preference_observations_chapter_id",
        table_name="preference_observations",
    )
    op.drop_index(
        "ix_preference_observations_project_id",
        table_name="preference_observations",
    )
    op.drop_index(
        "ix_preference_observations_user_id",
        table_name="preference_observations",
    )
    op.drop_table("preference_observations")
