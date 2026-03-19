"""Add project volumes and branches.

Revision ID: 20260318_0007
Revises: 20260318_0006
Create Date: 2026-03-18 21:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0007"
down_revision = "20260318_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_volumes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_project_volumes"),
        sa.UniqueConstraint(
            "project_id",
            "volume_number",
            name="uq_project_volumes_project_number",
        ),
    )
    op.create_index(
        "ix_project_volumes_project_id",
        "project_volumes",
        ["project_id"],
        unique=False,
    )

    op.create_table(
        "project_branches",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_branch_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_branch_id"],
            ["project_branches.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_branches"),
        sa.UniqueConstraint("project_id", "key", name="uq_project_branches_project_key"),
    )
    op.create_index(
        "ix_project_branches_project_id",
        "project_branches",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_branches_source_branch_id",
        "project_branches",
        ["source_branch_id"],
        unique=False,
    )

    op.add_column(
        "chapters",
        sa.Column("volume_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_chapters_volume_id", "chapters", ["volume_id"], unique=False)
    op.create_index("ix_chapters_branch_id", "chapters", ["branch_id"], unique=False)
    op.create_foreign_key(
        "fk_chapters_volume_id_project_volumes",
        "chapters",
        "project_volumes",
        ["volume_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_chapters_branch_id_project_branches",
        "chapters",
        "project_branches",
        ["branch_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_chapters_project_number", "chapters", type_="unique")
    op.create_unique_constraint(
        "uq_chapters_project_branch_volume_number",
        "chapters",
        ["project_id", "branch_id", "volume_id", "chapter_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_chapters_project_branch_volume_number",
        "chapters",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_chapters_project_number",
        "chapters",
        ["project_id", "chapter_number"],
    )
    op.drop_constraint("fk_chapters_branch_id_project_branches", "chapters", type_="foreignkey")
    op.drop_constraint("fk_chapters_volume_id_project_volumes", "chapters", type_="foreignkey")
    op.drop_index("ix_chapters_branch_id", table_name="chapters")
    op.drop_index("ix_chapters_volume_id", table_name="chapters")
    op.drop_column("chapters", "branch_id")
    op.drop_column("chapters", "volume_id")

    op.drop_index("ix_project_branches_source_branch_id", table_name="project_branches")
    op.drop_index("ix_project_branches_project_id", table_name="project_branches")
    op.drop_table("project_branches")

    op.drop_index("ix_project_volumes_project_id", table_name="project_volumes")
    op.drop_table("project_volumes")
