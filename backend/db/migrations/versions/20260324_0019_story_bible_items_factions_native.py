"""Promote Story Bible items and factions to native tables.

Revision ID: 20260324_0019
Revises: 20260323_0018
Create Date: 2026-03-24 12:00:00
"""

from __future__ import annotations

from typing import Any

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260324_0019"
down_revision = "20260323_0018"
branch_labels = None
depends_on = None


project_items_table = sa.table(
    "project_items",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("item_type", sa.String()),
    sa.column("rarity", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("effects", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("owner", sa.String()),
    sa.column("location", sa.String()),
    sa.column("status", sa.String()),
    sa.column("introduced_chapter", sa.Integer()),
    sa.column("forbidden_holders", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("version", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

project_factions_table = sa.table(
    "project_factions",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String()),
    sa.column("name", sa.String()),
    sa.column("faction_type", sa.String()),
    sa.column("scale", sa.String()),
    sa.column("description", sa.Text()),
    sa.column("goals", sa.Text()),
    sa.column("leader", sa.String()),
    sa.column("members", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("territory", sa.String()),
    sa.column("resources", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("ideology", sa.Text()),
    sa.column("version", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)

world_settings_table = sa.table(
    "world_settings",
    sa.column("id", postgresql.UUID(as_uuid=True)),
    sa.column("project_id", postgresql.UUID(as_uuid=True)),
    sa.column("key", sa.String()),
    sa.column("title", sa.String()),
    sa.column("data", postgresql.JSONB(astext_type=sa.Text())),
    sa.column("version", sa.Integer()),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def upgrade() -> None:
    op.create_table(
        "project_items",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("item_type", sa.String(length=100), nullable=True),
        sa.Column("rarity", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "effects",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("owner", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=100), nullable=True),
        sa.Column("introduced_chapter", sa.Integer(), nullable=True),
        sa.Column(
            "forbidden_holders",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_items_project_id"), "project_items", ["project_id"], unique=False)
    op.create_index(op.f("ix_project_items_key"), "project_items", ["key"], unique=False)

    op.create_table(
        "project_factions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("faction_type", sa.String(length=100), nullable=True),
        sa.Column("scale", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goals", sa.Text(), nullable=True),
        sa.Column("leader", sa.String(length=255), nullable=True),
        sa.Column(
            "members",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("territory", sa.String(length=255), nullable=True),
        sa.Column(
            "resources",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("ideology", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_project_factions_project_id"),
        "project_factions",
        ["project_id"],
        unique=False,
    )
    op.create_index(op.f("ix_project_factions_key"), "project_factions", ["key"], unique=False)

    _migrate_world_setting_wrappers_to_native_tables()


def downgrade() -> None:
    _migrate_native_tables_back_to_world_setting_wrappers()

    op.drop_index(op.f("ix_project_factions_key"), table_name="project_factions")
    op.drop_index(op.f("ix_project_factions_project_id"), table_name="project_factions")
    op.drop_table("project_factions")

    op.drop_index(op.f("ix_project_items_key"), table_name="project_items")
    op.drop_index(op.f("ix_project_items_project_id"), table_name="project_items")
    op.drop_table("project_items")


def _migrate_world_setting_wrappers_to_native_tables() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id, key, title, data, version, created_at, updated_at
            FROM world_settings
            """
        )
    ).mappings()

    item_rows: list[dict[str, Any]] = []
    faction_rows: list[dict[str, Any]] = []
    legacy_ids: list[Any] = []

    for row in rows:
        data = row.get("data") or {}
        entity_type = str(data.get("entity_type") or "").strip().lower() if isinstance(data, dict) else ""
        if entity_type == "item":
            item_rows.append(_extract_item_row(row))
            legacy_ids.append(row["id"])
        elif entity_type == "faction":
            faction_rows.append(_extract_faction_row(row))
            legacy_ids.append(row["id"])

    if item_rows:
        connection.execute(sa.insert(project_items_table), item_rows)
    if faction_rows:
        connection.execute(sa.insert(project_factions_table), faction_rows)
    if legacy_ids:
        connection.execute(
            sa.delete(world_settings_table).where(world_settings_table.c.id.in_(legacy_ids))
        )


def _migrate_native_tables_back_to_world_setting_wrappers() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id, key, name, item_type, rarity, description, effects,
                   owner, location, status, introduced_chapter, forbidden_holders,
                   version, created_at, updated_at
            FROM project_items
            """
        )
    ).mappings()
    item_wrappers = [_item_row_to_world_setting(row) for row in rows]
    if item_wrappers:
        connection.execute(sa.insert(world_settings_table), item_wrappers)

    rows = connection.execute(
        sa.text(
            """
            SELECT id, project_id, key, name, faction_type, scale, description, goals,
                   leader, members, territory, resources, ideology, version,
                   created_at, updated_at
            FROM project_factions
            """
        )
    ).mappings()
    faction_wrappers = [_faction_row_to_world_setting(row) for row in rows]
    if faction_wrappers:
        connection.execute(sa.insert(world_settings_table), faction_wrappers)


def _extract_item_row(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data") or {}
    nested_items = data.get("items") if isinstance(data, dict) else []
    nested_item = (
        nested_items[0]
        if isinstance(nested_items, list) and nested_items and isinstance(nested_items[0], dict)
        else {}
    )
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "key": (row.get("key") or nested_item.get("key") or nested_item.get("name") or "").strip(),
        "name": (
            nested_item.get("name")
            or nested_item.get("title")
            or row.get("title")
            or row.get("key")
            or ""
        ).strip(),
        "item_type": _optional_text(nested_item.get("type") or data.get("item_type")),
        "rarity": _optional_text(nested_item.get("rarity")),
        "description": _optional_text(nested_item.get("description") or data.get("description")),
        "effects": _clean_string_list(nested_item.get("effects")),
        "owner": _optional_text(nested_item.get("owner") or data.get("owner")),
        "location": _optional_text(nested_item.get("location") or data.get("location")),
        "status": _optional_text(nested_item.get("status") or data.get("status")),
        "introduced_chapter": _optional_int(
            nested_item.get("introduced_chapter") or data.get("introduced_chapter")
        ),
        "forbidden_holders": _clean_string_list(
            nested_item.get("forbidden_holders") or data.get("forbidden_holders")
        ),
        "version": int(row.get("version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _extract_faction_row(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data") or {}
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "key": (row.get("key") or data.get("key") or row.get("title") or "").strip(),
        "name": (data.get("name") or row.get("title") or row.get("key") or "").strip(),
        "faction_type": _optional_text(data.get("faction_type") or data.get("type")),
        "scale": _optional_text(data.get("scale")),
        "description": _optional_text(data.get("description")),
        "goals": _optional_text(data.get("goals")),
        "leader": _optional_text(data.get("leader")),
        "members": _clean_string_list(data.get("members")),
        "territory": _optional_text(data.get("territory")),
        "resources": _clean_string_list(data.get("resources")),
        "ideology": _optional_text(data.get("ideology")),
        "version": int(row.get("version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _item_row_to_world_setting(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "key": row["key"],
        "title": row["name"],
        "data": {
            "entity_type": "item",
            "item_type": row.get("item_type"),
            "description": row.get("description"),
            "owner": row.get("owner"),
            "location": row.get("location"),
            "status": row.get("status"),
            "introduced_chapter": row.get("introduced_chapter"),
            "forbidden_holders": _clean_string_list(row.get("forbidden_holders")),
            "items": [
                {
                    "name": row["name"],
                    "type": row.get("item_type"),
                    "rarity": row.get("rarity"),
                    "description": row.get("description"),
                    "effects": _clean_string_list(row.get("effects")),
                    "owner": row.get("owner"),
                    "location": row.get("location"),
                    "status": row.get("status"),
                    "introduced_chapter": row.get("introduced_chapter"),
                    "forbidden_holders": _clean_string_list(row.get("forbidden_holders")),
                }
            ],
        },
        "version": int(row.get("version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _faction_row_to_world_setting(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "key": row["key"],
        "title": row["name"],
        "data": {
            "entity_type": "faction",
            "name": row["name"],
            "faction_type": row.get("faction_type"),
            "scale": row.get("scale"),
            "description": row.get("description"),
            "goals": row.get("goals"),
            "leader": row.get("leader"),
            "members": _clean_string_list(row.get("members")),
            "territory": row.get("territory"),
            "resources": _clean_string_list(row.get("resources")),
            "ideology": row.get("ideology"),
        },
        "version": int(row.get("version") or 1),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in value:
        candidate = _optional_text(item)
        if not candidate:
            continue
        normalized = candidate.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(candidate)
    return cleaned
