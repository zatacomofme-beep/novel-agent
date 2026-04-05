"""Create story_room_cloud_draft_versions table

Revision ID: 20260328_0029
Revises: 20260328_0028
Create Date: 2026-03-28
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20260328_0029"
down_revision: Union[str, None] = "20260328_0028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "story_room_cloud_draft_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("draft_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("chapter_title", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("source_version_number", sa.Integer(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delta_length", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("save_trigger", sa.String(length=50), nullable=False, server_default="'auto'"),
    )
    op.create_index("ix_cloud_draft_versions_draft_id", "story_room_cloud_draft_versions", ["draft_id"])
    op.create_index("ix_cloud_draft_versions_created_at", "story_room_cloud_draft_versions", ["created_at"])


def downgrade() -> None:
    op.drop_table("story_room_cloud_draft_versions")
