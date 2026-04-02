"""Create prompt_templates table

Revision ID: 20260328_0028
Revises: 20260327_0027_chapter_writing_intent
Create Date: 2026-03-28
"""
from __future__ import annotations
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

revision: str = "20260328_0028"
down_revision: Union[str, None] = "20260327_0027_chapter_writing_intent"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("tagline", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False, index=True),
        sa.Column("sub_category", sa.String(length=50), nullable=True),
        sa.Column("tags", JSON(), nullable=False, server_default="[]"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("variables", JSON(), nullable=False, server_default="[]"),
        sa.Column("use_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("recommended_scenes", JSON(), nullable=False, server_default="[]"),
        sa.Column("difficulty_level", sa.String(length=20), nullable=False, server_default="'intermediate'"),
    )
    op.create_index("ix_prompt_templates_category", "prompt_templates", ["category"])
    op.create_index("ix_prompt_templates_is_system", "prompt_templates", ["is_system"])
    op.create_index("ix_prompt_templates_name_search", "prompt_templates", ["name"])


def downgrade() -> None:
    op.drop_table("prompt_templates")
