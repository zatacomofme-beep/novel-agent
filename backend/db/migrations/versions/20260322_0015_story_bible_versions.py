"""Add Story Bible versions and pending changes tables.

Revision ID: 20260322_0015
Revises: 20260321_0014
Create Date: 2026-03-22 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260322_0015"
down_revision = "20260321_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_bible_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("change_source", sa.Text(), nullable=False),
        sa.Column("changed_section", sa.Text(), nullable=False),
        sa.Column("changed_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_entity_key", sa.Text(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_story_bible_versions"),
        sa.UniqueConstraint(
            "project_id",
            "branch_id",
            "version_number",
            name="uq_story_bible_versions_project_branch_version",
        ),
    )
    op.create_index(
        "ix_story_bible_versions_project_id",
        "story_bible_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_bible_versions_branch_id",
        "story_bible_versions",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_bible_versions_project_branch",
        "story_bible_versions",
        ["project_id", "branch_id"],
        unique=False,
    )

    op.create_table(
        "story_bible_pending_changes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("change_type", sa.Text(), nullable=False),
        sa.Column("change_source", sa.Text(), nullable=False),
        sa.Column("changed_section", sa.Text(), nullable=False),
        sa.Column("changed_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("changed_entity_key", sa.Text(), nullable=True),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("triggered_by_chapter_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("proposed_by_agent", sa.Text(), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["triggered_by_chapter_id"],
            ["chapters.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_story_bible_pending_changes"),
    )
    op.create_index(
        "ix_story_bible_pending_changes_project_id",
        "story_bible_pending_changes",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_bible_pending_changes_branch_id",
        "story_bible_pending_changes",
        ["branch_id"],
        unique=False,
    )
    op.create_index(
        "ix_story_bible_pending_changes_status",
        "story_bible_pending_changes",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_story_bible_pending_changes_project_branch",
        "story_bible_pending_changes",
        ["project_id", "branch_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_story_bible_pending_changes_project_branch",
        table_name="story_bible_pending_changes",
    )
    op.drop_index(
        "ix_story_bible_pending_changes_status",
        table_name="story_bible_pending_changes",
    )
    op.drop_index(
        "ix_story_bible_pending_changes_branch_id",
        table_name="story_bible_pending_changes",
    )
    op.drop_index(
        "ix_story_bible_pending_changes_project_id",
        table_name="story_bible_pending_changes",
    )
    op.drop_table("story_bible_pending_changes")

    op.drop_index(
        "ix_story_bible_versions_project_branch",
        table_name="story_bible_versions",
    )
    op.drop_index(
        "ix_story_bible_versions_branch_id",
        table_name="story_bible_versions",
    )
    op.drop_index(
        "ix_story_bible_versions_project_id",
        table_name="story_bible_versions",
    )
    op.drop_table("story_bible_versions")
