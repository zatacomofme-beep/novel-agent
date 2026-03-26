"""Add story room cloud drafts.

Revision ID: 20260326_0021
Revises: 20260325_0020
Create Date: 2026-03-26 20:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260326_0021"
down_revision = "20260325_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_room_cloud_drafts",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("outline_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("scope_key", sa.String(length=180), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("chapter_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("draft_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_version_number", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["project_branches.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["volume_id"], ["project_volumes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_story_room_cloud_drafts"),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            "scope_key",
            name="uq_story_room_cloud_drafts_project_user_scope",
        ),
    )
    op.create_index(
        "ix_story_room_cloud_drafts_project_id",
        "story_room_cloud_drafts",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_user_id",
        "story_room_cloud_drafts",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_branch_id",
        "story_room_cloud_drafts",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_volume_id",
        "story_room_cloud_drafts",
        ["volume_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_source_chapter_id",
        "story_room_cloud_drafts",
        ["source_chapter_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_outline_id",
        "story_room_cloud_drafts",
        ["outline_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_room_cloud_drafts_scope_key",
        "story_room_cloud_drafts",
        ["scope_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_story_room_cloud_drafts_scope_key", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_outline_id", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_source_chapter_id", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_volume_id", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_branch_id", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_user_id", table_name="story_room_cloud_drafts")
    op.drop_index("ix_story_room_cloud_drafts_project_id", table_name="story_room_cloud_drafts")
    op.drop_table("story_room_cloud_drafts")
