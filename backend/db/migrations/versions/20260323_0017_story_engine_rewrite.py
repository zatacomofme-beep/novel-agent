"""Create story engine rewrite knowledge base tables.

Revision ID: 20260323_0017
Revises: 20260323_0016
Create Date: 2026-03-23 18:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260323_0017"
down_revision = "20260323_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "story_characters",
        sa.Column("character_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("appearance", sa.Text(), nullable=True),
        sa.Column("personality", sa.Text(), nullable=True),
        sa.Column("micro_habits", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("abilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("relationships", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False, server_default="active"),
        sa.Column("arc_stage", sa.String(length=100), nullable=False, server_default="initial"),
        sa.Column("arc_boundaries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("character_id", name="pk_story_characters"),
        sa.UniqueConstraint("project_id", "name", name="uq_story_characters_project_name"),
    )
    op.create_index("ix_story_characters_project_id", "story_characters", ["project_id"])

    op.create_table(
        "story_foreshadows",
        sa.Column("foreshadow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chapter_planted", sa.Integer(), nullable=True),
        sa.Column("chapter_planned_reveal", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("related_characters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("related_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("foreshadow_id", name="pk_story_foreshadows"),
    )
    op.create_index("ix_story_foreshadows_project_id", "story_foreshadows", ["project_id"])

    op.create_table(
        "story_items",
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("features", sa.Text(), nullable=True),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("special_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("item_id", name="pk_story_items"),
        sa.UniqueConstraint("project_id", "name", name="uq_story_items_project_name"),
    )
    op.create_index("ix_story_items_project_id", "story_items", ["project_id"])

    op.create_table(
        "story_world_rules",
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("rule_content", sa.Text(), nullable=False),
        sa.Column("negative_list", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scope", sa.String(length=100), nullable=False, server_default="global"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("rule_id", name="pk_story_world_rules"),
        sa.UniqueConstraint("project_id", "rule_name", name="uq_story_world_rules_project_name"),
    )
    op.create_index("ix_story_world_rules_project_id", "story_world_rules", ["project_id"])

    op.create_table(
        "story_timeline_map_events",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=True),
        sa.Column("in_universe_time", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("weather", sa.String(length=100), nullable=True),
        sa.Column("core_event", sa.Text(), nullable=False),
        sa.Column("character_states", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id", name="pk_story_timeline_map_events"),
    )
    op.create_index(
        "ix_story_timeline_map_events_project_id",
        "story_timeline_map_events",
        ["project_id"],
    )

    op.create_table(
        "story_outlines",
        sa.Column("outline_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="todo"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("node_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("immutable_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["story_outlines.outline_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("outline_id", name="pk_story_outlines"),
    )
    op.create_index("ix_story_outlines_project_id", "story_outlines", ["project_id"])
    op.create_index("ix_story_outlines_parent_id", "story_outlines", ["parent_id"])

    op.create_table(
        "story_chapter_summaries",
        sa.Column("summary_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("core_progress", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("character_changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("foreshadow_updates", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("kb_update_suggestions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("summary_id", name="pk_story_chapter_summaries"),
        sa.UniqueConstraint(
            "project_id",
            "chapter_number",
            name="uq_story_chapter_summaries_project_chapter",
        ),
    )
    op.create_index(
        "ix_story_chapter_summaries_project_id",
        "story_chapter_summaries",
        ["project_id"],
    )

    op.create_table(
        "story_knowledge_versions",
        sa.Column("version_record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=50), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("source_workflow", sa.String(length=100), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("version_record_id", name="pk_story_knowledge_versions"),
        sa.UniqueConstraint(
            "project_id",
            "entity_type",
            "entity_id",
            "version_number",
            name="uq_story_knowledge_versions_entity_version",
        ),
    )
    op.create_index(
        "ix_story_knowledge_versions_project_id",
        "story_knowledge_versions",
        ["project_id"],
    )
    op.create_index(
        "ix_story_knowledge_versions_entity_type",
        "story_knowledge_versions",
        ["entity_type"],
    )
    op.create_index(
        "ix_story_knowledge_versions_entity_id",
        "story_knowledge_versions",
        ["entity_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_story_knowledge_versions_entity_id", table_name="story_knowledge_versions")
    op.drop_index("ix_story_knowledge_versions_entity_type", table_name="story_knowledge_versions")
    op.drop_index("ix_story_knowledge_versions_project_id", table_name="story_knowledge_versions")
    op.drop_table("story_knowledge_versions")

    op.drop_index("ix_story_chapter_summaries_project_id", table_name="story_chapter_summaries")
    op.drop_table("story_chapter_summaries")

    op.drop_index("ix_story_outlines_parent_id", table_name="story_outlines")
    op.drop_index("ix_story_outlines_project_id", table_name="story_outlines")
    op.drop_table("story_outlines")

    op.drop_index("ix_story_timeline_map_events_project_id", table_name="story_timeline_map_events")
    op.drop_table("story_timeline_map_events")

    op.drop_index("ix_story_world_rules_project_id", table_name="story_world_rules")
    op.drop_table("story_world_rules")

    op.drop_index("ix_story_items_project_id", table_name="story_items")
    op.drop_table("story_items")

    op.drop_index("ix_story_foreshadows_project_id", table_name="story_foreshadows")
    op.drop_table("story_foreshadows")

    op.drop_index("ix_story_characters_project_id", table_name="story_characters")
    op.drop_table("story_characters")
