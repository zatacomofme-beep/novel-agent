"""Scope story engine outlines and chapter summaries to branches.

Revision ID: 20260325_0020
Revises: 20260324_0019
Create Date: 2026-03-25 11:30:00
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260325_0020"
down_revision = "20260324_0019"
branch_labels = None
depends_on = None


project_branches_table = sa.table(
    "project_branches",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("source_branch_id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String()),
    sa.column("title", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("status", sa.String()),
    sa.column("is_default", sa.Boolean()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

story_outlines_table = sa.table(
    "story_outlines",
    sa.column("outline_id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("branch_id", postgresql.UUID(as_uuid=True)),
)

story_chapter_summaries_table = sa.table(
    "story_chapter_summaries",
    sa.column("summary_id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("branch_id", postgresql.UUID(as_uuid=True)),
)


def upgrade() -> None:
    op.add_column(
        "story_outlines",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_story_outlines_branch_id",
        "story_outlines",
        ["branch_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_story_outlines_branch_id_project_branches",
        "story_outlines",
        "project_branches",
        ["branch_id"],
        ["id"],
        ondelete="CASCADE",
    )

    op.add_column(
        "story_chapter_summaries",
        sa.Column("branch_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_story_chapter_summaries_branch_id",
        "story_chapter_summaries",
        ["branch_id"],
        unique=False,
    )
    op.create_foreign_key(
        "fk_story_chapter_summaries_branch_id_project_branches",
        "story_chapter_summaries",
        "project_branches",
        ["branch_id"],
        ["id"],
        ondelete="CASCADE",
    )

    _ensure_projects_have_at_least_one_branch()
    branch_map = _build_project_branch_map()
    _backfill_story_scope(branch_map)

    op.alter_column("story_outlines", "branch_id", nullable=False)
    op.alter_column("story_chapter_summaries", "branch_id", nullable=False)

    op.drop_constraint(
        "uq_story_chapter_summaries_project_chapter",
        "story_chapter_summaries",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_story_chapter_summaries_project_branch_chapter",
        "story_chapter_summaries",
        ["project_id", "branch_id", "chapter_number"],
    )


def downgrade() -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DELETE FROM story_chapter_summaries
            WHERE summary_id IN (
                SELECT summary_id
                FROM (
                    SELECT summary_id,
                           row_number() OVER (
                               PARTITION BY project_id, chapter_number
                               ORDER BY updated_at DESC, created_at DESC, summary_id DESC
                           ) AS rn
                    FROM story_chapter_summaries
                ) ranked
                WHERE ranked.rn > 1
            )
            """
        )
    )

    op.drop_constraint(
        "uq_story_chapter_summaries_project_branch_chapter",
        "story_chapter_summaries",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_story_chapter_summaries_project_chapter",
        "story_chapter_summaries",
        ["project_id", "chapter_number"],
    )

    op.drop_constraint(
        "fk_story_chapter_summaries_branch_id_project_branches",
        "story_chapter_summaries",
        type_="foreignkey",
    )
    op.drop_index("ix_story_chapter_summaries_branch_id", table_name="story_chapter_summaries")
    op.drop_column("story_chapter_summaries", "branch_id")

    op.drop_constraint(
        "fk_story_outlines_branch_id_project_branches",
        "story_outlines",
        type_="foreignkey",
    )
    op.drop_index("ix_story_outlines_branch_id", table_name="story_outlines")
    op.drop_column("story_outlines", "branch_id")


def _ensure_projects_have_at_least_one_branch() -> None:
    connection = op.get_bind()
    project_rows = connection.execute(
        sa.text(
            """
            SELECT project_id
            FROM (
                SELECT DISTINCT project_id FROM story_outlines
                UNION
                SELECT DISTINCT project_id FROM story_chapter_summaries
            ) scoped_projects
            """
        )
    ).mappings()

    existing_branch_rows = connection.execute(
        sa.text("SELECT DISTINCT project_id FROM project_branches")
    ).mappings()
    existing_project_ids = {row["project_id"] for row in existing_branch_rows}

    now = datetime.now(timezone.utc)
    rows_to_insert: list[dict[str, Any]] = []
    for row in project_rows:
        project_id = row["project_id"]
        if project_id in existing_project_ids:
            continue
        rows_to_insert.append(
            {
                "id": uuid.uuid4(),
                "project_id": project_id,
                "source_branch_id": None,
                "key": "mainline",
                "title": "默认主线",
                "description": "为旧版故事数据迁移自动补建的主线。",
                "status": "active",
                "is_default": True,
                "created_at": now,
                "updated_at": now,
            }
        )

    if rows_to_insert:
        connection.execute(sa.insert(project_branches_table), rows_to_insert)


def _build_project_branch_map() -> dict[Any, Any]:
    connection = op.get_bind()
    branch_rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id, is_default, created_at
            FROM project_branches
            ORDER BY project_id, is_default DESC, created_at ASC, id ASC
            """
        )
    ).mappings()

    branch_map: dict[Any, Any] = {}
    for row in branch_rows:
        branch_map.setdefault(row["project_id"], row["id"])
    return branch_map


def _backfill_story_scope(branch_map: dict[Any, Any]) -> None:
    connection = op.get_bind()
    for project_id, branch_id in branch_map.items():
        connection.execute(
            sa.update(story_outlines_table)
            .where(story_outlines_table.c.project_id == project_id)
            .where(story_outlines_table.c.branch_id.is_(None))
            .values(branch_id=branch_id)
        )
        connection.execute(
            sa.update(story_chapter_summaries_table)
            .where(story_chapter_summaries_table.c.project_id == project_id)
            .where(story_chapter_summaries_table.c.branch_id.is_(None))
            .values(branch_id=branch_id)
        )
