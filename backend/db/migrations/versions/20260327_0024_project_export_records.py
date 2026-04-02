"""Add project export records for delivery center history.

Revision ID: 20260327_0024
Revises: 20260326_0023
Create Date: 2026-03-27 10:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260327_0024"
down_revision = "20260326_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_export_records",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("export_format", sa.String(length=20), nullable=False),
        sa.Column("scope_kind", sa.String(length=50), nullable=False),
        sa.Column("scope_label", sa.String(length=255), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("chapter_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chapter_numbers", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("chapter_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("include_cover_page", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("include_metadata", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("package_title", sa.String(length=255), nullable=True),
        sa.Column("package_subtitle", sa.String(length=255), nullable=True),
        sa.Column("author_name", sa.String(length=255), nullable=True),
        sa.Column("synopsis", sa.Text(), nullable=True),
        sa.Column("metadata_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_export_records")),
    )
    op.create_index(
        op.f("ix_project_export_records_project_id"),
        "project_export_records",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_export_records_user_id"),
        "project_export_records",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_export_records_created_at"),
        "project_export_records",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_project_export_records_created_at"),
        table_name="project_export_records",
    )
    op.drop_index(
        op.f("ix_project_export_records_user_id"),
        table_name="project_export_records",
    )
    op.drop_index(
        op.f("ix_project_export_records_project_id"),
        table_name="project_export_records",
    )
    op.drop_table("project_export_records")
