"""Add project collaborators.

Revision ID: 20260318_0008
Revises: 20260318_0007
Create Date: 2026-03-18 23:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260318_0008"
down_revision = "20260318_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_collaborators",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("added_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=50), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["added_by_user_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_project_collaborators"),
        sa.UniqueConstraint(
            "project_id",
            "user_id",
            name="uq_project_collaborators_project_user",
        ),
    )
    op.create_index(
        "ix_project_collaborators_project_id",
        "project_collaborators",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_collaborators_user_id",
        "project_collaborators",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_collaborators_added_by_user_id",
        "project_collaborators",
        ["added_by_user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_project_collaborators_added_by_user_id",
        table_name="project_collaborators",
    )
    op.drop_index(
        "ix_project_collaborators_user_id",
        table_name="project_collaborators",
    )
    op.drop_index(
        "ix_project_collaborators_project_id",
        table_name="project_collaborators",
    )
    op.drop_table("project_collaborators")
