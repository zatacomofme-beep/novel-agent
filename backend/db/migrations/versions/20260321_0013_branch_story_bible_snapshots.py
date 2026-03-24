"""Add branch story bible snapshots.

Revision ID: 20260321_0013
Revises: 20260319_0012
Create Date: 2026-03-21 10:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260321_0013"
down_revision = "20260319_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_branch_story_bibles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
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
        sa.ForeignKeyConstraint(["branch_id"], ["project_branches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_project_branch_story_bibles"),
        sa.UniqueConstraint(
            "project_id",
            "branch_id",
            name="uq_project_branch_story_bibles_project_branch",
        ),
    )
    op.create_index(
        "ix_project_branch_story_bibles_project_id",
        "project_branch_story_bibles",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_branch_story_bibles_branch_id",
        "project_branch_story_bibles",
        ["branch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_branch_story_bibles_branch_id",
        table_name="project_branch_story_bibles",
    )
    op.drop_index(
        "ix_project_branch_story_bibles_project_id",
        table_name="project_branch_story_bibles",
    )
    op.drop_table("project_branch_story_bibles")
