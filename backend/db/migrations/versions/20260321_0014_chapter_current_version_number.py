"""Add current chapter version number.

Revision ID: 20260321_0014
Revises: 20260321_0013
Create Date: 2026-03-21 13:35:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260321_0014"
down_revision = "20260321_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column(
            "current_version_number",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.execute(
        """
        UPDATE chapters
        SET current_version_number = COALESCE(version_data.max_version_number, 1)
        FROM (
            SELECT chapter_id, MAX(version_number) AS max_version_number
            FROM chapter_versions
            GROUP BY chapter_id
        ) AS version_data
        WHERE chapters.id = version_data.chapter_id
        """
    )
    op.alter_column(
        "chapters",
        "current_version_number",
        server_default=None,
    )


def downgrade() -> None:
    op.drop_column("chapters", "current_version_number")
