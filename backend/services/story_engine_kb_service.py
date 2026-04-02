from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import Select, delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.project import Project
from models.story_engine import (
    StoryChapterSummary,
    StoryCharacter,
    StoryForeshadow,
    StoryItem,
    StoryKnowledgeVersion,
    StoryOutline,
    StoryTimelineMapEvent,
    StoryWorldRule,
)
from services.story_engine_vector_store import vector_store
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
    build_story_bible_payload,
    get_owned_project,
)


@dataclass(frozen=True)
class StoryEntityRegistry:
    key: str
    model: type
    id_field: str
    order_by: Any


ENTITY_REGISTRY: dict[str, StoryEntityRegistry] = {
    "characters": StoryEntityRegistry(
        key="characters",
        model=StoryCharacter,
        id_field="character_id",
        order_by=StoryCharacter.updated_at.desc(),
    ),
    "foreshadows": StoryEntityRegistry(
        key="foreshadows",
        model=StoryForeshadow,
        id_field="foreshadow_id",
        order_by=StoryForeshadow.updated_at.desc(),
    ),
    "items": StoryEntityRegistry(
        key="items",
        model=StoryItem,
        id_field="item_id",
        order_by=StoryItem.updated_at.desc(),
    ),
    "world_rules": StoryEntityRegistry(
        key="world_rules",
        model=StoryWorldRule,
        id_field="rule_id",
        order_by=StoryWorldRule.updated_at.desc(),
    ),
    "timeline_events": StoryEntityRegistry(
        key="timeline_events",
        model=StoryTimelineMapEvent,
        id_field="event_id",
        order_by=StoryTimelineMapEvent.chapter_number.asc().nullslast(),
    ),
    "outlines": StoryEntityRegistry(
        key="outlines",
        model=StoryOutline,
        id_field="outline_id",
        order_by=(StoryOutline.level.asc(), StoryOutline.node_order.asc(), StoryOutline.created_at.asc()),
    ),
    "chapter_summaries": StoryEntityRegistry(
        key="chapter_summaries",
        model=StoryChapterSummary,
        id_field="summary_id",
        order_by=StoryChapterSummary.chapter_number.desc(),
    ),
}


WORKSPACE_PROVENANCE_SECTION_KEYS = (
    "characters",
    "foreshadows",
    "items",
    "locations",
    "factions",
    "plot_threads",
    "world_rules",
    "timeline_events",
)
STRUCTURED_PROVENANCE_ENTITY_TYPES = {
    "characters": "characters",
    "foreshadows": "foreshadows",
    "items": "items",
    "world_rules": "world_rules",
    "timeline_events": "timeline_events",
}


async def get_story_engine_project(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    *,
    permission: str = PROJECT_PERMISSION_READ,
) -> Project:
    return await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=False,
        permission=permission,
    )


async def list_entities(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    branch_id: UUID | None = None,
) -> list[Any]:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    registry = _get_registry(entity_type)
    statement = select(registry.model).where(registry.model.project_id == project_id)
    if _is_branch_scoped_entity(entity_type):
        resolved_branch_id = await _resolve_effective_branch_id(
            session,
            project_id=project_id,
            user_id=user_id,
            branch_id=branch_id,
            permission=PROJECT_PERMISSION_READ,
        )
        statement = statement.where(registry.model.branch_id == resolved_branch_id)
    order_by = registry.order_by
    if isinstance(order_by, tuple):
        statement = statement.order_by(*order_by)
    else:
        statement = statement.order_by(order_by)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def get_entity(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    permission: str = PROJECT_PERMISSION_READ,
) -> Any:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=permission,
    )
    registry = _get_registry(entity_type)
    statement = select(registry.model).where(
        registry.model.project_id == project_id,
        getattr(registry.model, registry.id_field) == entity_id,
    )
    result = await session.execute(statement)
    entity = result.scalar_one_or_none()
    if entity is None:
        raise AppError(
            code="story_engine.entity_not_found",
            message=f"{entity_type} entity not found.",
            status_code=404,
        )
    return entity


async def create_entity(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    payload: dict[str, Any],
    source_workflow: str = "manual",
) -> Any:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    registry = _get_registry(entity_type)
    normalized_payload = _normalize_create_payload(entity_type, payload)
    if _is_branch_scoped_entity(entity_type):
        normalized_payload["branch_id"] = await _resolve_effective_branch_id(
            session,
            project_id=project_id,
            user_id=user_id,
            branch_id=normalized_payload.get("branch_id"),
            permission=PROJECT_PERMISSION_EDIT,
        )
    await _guardian_validate_before_write(
        session,
        project_id=project_id,
        entity_type=entity_type,
        payload=normalized_payload,
        current_entity=None,
    )
    await _validate_branch_scoped_payload(
        session,
        project_id=project_id,
        entity_type=entity_type,
        payload=normalized_payload,
        current_entity=None,
    )
    entity = registry.model(project_id=project_id, **normalized_payload)
    session.add(entity)
    await session.flush()
    snapshot = _serialize_entity(entity_type, entity)
    await _create_version_record(
        session,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=getattr(entity, registry.id_field),
        version_number=snapshot["version"],
        action="created",
        snapshot=snapshot,
        summary=f"{entity_type} created",
        created_by=user_id,
        source_workflow=source_workflow,
    )
    await session.commit()
    await session.refresh(entity)
    await _sync_entity_vector(project_id, entity_type, entity)
    return entity


async def update_entity(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    payload: dict[str, Any],
    source_workflow: str = "manual",
) -> Any:
    entity = await get_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await _guardian_validate_before_write(
        session,
        project_id=project_id,
        entity_type=entity_type,
        payload=payload,
        current_entity=entity,
    )
    await _validate_branch_scoped_payload(
        session,
        project_id=project_id,
        entity_type=entity_type,
        payload=payload,
        current_entity=entity,
    )
    old_snapshot = _serialize_entity(entity_type, entity)
    if entity_type == "outlines" and getattr(entity, "locked", False):
        raise AppError(
            code="story_engine.outline_locked",
            message="一级大纲已锁定，不能直接修改。",
            status_code=409,
        )
    for field, value in payload.items():
        if value is not None:
            setattr(entity, field, value)
    if hasattr(entity, "version"):
        entity.version = int(getattr(entity, "version") or 1) + 1
    await session.flush()
    new_snapshot = _serialize_entity(entity_type, entity)
    await _create_version_record(
        session,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=new_snapshot["version"],
        action="updated",
        snapshot={"before": old_snapshot, "after": new_snapshot},
        summary=f"{entity_type} updated",
        created_by=user_id,
        source_workflow=source_workflow,
    )
    await session.commit()
    await session.refresh(entity)
    await _sync_entity_vector(project_id, entity_type, entity)
    return entity


async def delete_entity(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: str,
    entity_id: UUID,
    source_workflow: str = "manual",
) -> None:
    entity = await get_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    if entity_type == "outlines" and getattr(entity, "locked", False):
        raise AppError(
            code="story_engine.outline_locked",
            message="一级大纲已锁定，不能删除。",
            status_code=409,
        )
    snapshot = _serialize_entity(entity_type, entity)
    await _create_version_record(
        session,
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=snapshot["version"],
        action="deleted",
        snapshot=snapshot,
        summary=f"{entity_type} deleted",
        created_by=user_id,
        source_workflow=source_workflow,
    )
    await session.delete(entity)
    await session.commit()
    await _delete_entity_vector(project_id, entity_type, entity_id)


async def list_versions(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    limit: int = 50,
) -> list[StoryKnowledgeVersion]:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    statement: Select = select(StoryKnowledgeVersion).where(
        StoryKnowledgeVersion.project_id == project_id
    )
    if entity_type:
        statement = statement.where(StoryKnowledgeVersion.entity_type == entity_type)
    if entity_id:
        statement = statement.where(StoryKnowledgeVersion.entity_id == entity_id)
    statement = statement.order_by(desc(StoryKnowledgeVersion.created_at)).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def rollback_entity_version(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    version_record_id: UUID,
) -> dict[str, Any]:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    version_record = await session.get(StoryKnowledgeVersion, version_record_id)
    if version_record is None or version_record.project_id != project_id:
        raise AppError(
            code="story_engine.version_not_found",
            message="版本记录不存在。",
            status_code=404,
        )
    registry = _get_registry(version_record.entity_type)
    snapshot = version_record.snapshot
    entity_snapshot = snapshot.get("after") if isinstance(snapshot, dict) and "after" in snapshot else snapshot
    entity_id = UUID(str(version_record.entity_id))
    current = await get_entity_or_none(
        session,
        project_id=project_id,
        entity_type=version_record.entity_type,
        entity_id=entity_id,
    )
    restored_payload = {
        key: _deserialize_snapshot_value(key, value)
        for key, value in dict(entity_snapshot).items()
        if key not in {registry.id_field, "project_id", "created_at", "updated_at"}
    }
    if current is None:
        entity = registry.model(
            project_id=project_id,
            **{registry.id_field: entity_id},
            **restored_payload,
        )
        session.add(entity)
    else:
        entity = current
        for field, value in restored_payload.items():
            setattr(entity, field, value)
        if hasattr(entity, "version"):
            entity.version = int(getattr(entity, "version") or 1) + 1
    await session.flush()
    current_snapshot = _serialize_entity(version_record.entity_type, entity)
    await _create_version_record(
        session,
        project_id=project_id,
        entity_type=version_record.entity_type,
        entity_id=entity_id,
        version_number=current_snapshot["version"],
        action="rollback",
        snapshot=current_snapshot,
        summary=f"{version_record.entity_type} rollback",
        created_by=user_id,
        source_workflow="rollback",
    )
    await session.commit()
    await session.refresh(entity)
    await _sync_entity_vector(project_id, version_record.entity_type, entity)
    return {
        "restored_entity_type": version_record.entity_type,
        "restored_entity_id": entity_id,
        "restored_version_number": current_snapshot["version"],
        "snapshot": current_snapshot,
    }


async def get_entity_or_none(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    entity_id: UUID,
) -> Any | None:
    registry = _get_registry(entity_type)
    statement = select(registry.model).where(
        registry.model.project_id == project_id,
        getattr(registry.model, registry.id_field) == entity_id,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def build_workspace(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: UUID | None = None,
) -> dict[str, Any]:
    project = await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    characters = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="characters",
    )
    foreshadows = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="foreshadows",
    )
    items = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="items",
    )
    world_rules = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="world_rules",
    )
    timeline_events = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="timeline_events",
    )
    outlines = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="outlines",
        branch_id=branch_id,
    )
    chapter_summaries = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="chapter_summaries",
        branch_id=branch_id,
    )
    story_bible = await _build_workspace_story_bible(
        session,
        project_id=project_id,
        user_id=user_id,
        branch_id=branch_id,
    )
    knowledge_provenance = await _build_workspace_knowledge_provenance(
        session,
        project_id=project_id,
        characters=characters,
        foreshadows=foreshadows,
        items=items,
        world_rules=world_rules,
        timeline_events=timeline_events,
        chapter_summaries=chapter_summaries,
        story_bible=story_bible,
    )
    return {
        "project": {
            "project_id": project.id,
            "title": project.title,
            "genre": project.genre,
            "theme": project.theme,
            "tone": project.tone,
        },
        "characters": characters,
        "foreshadows": foreshadows,
        "items": items,
        "world_rules": world_rules,
        "timeline_events": timeline_events,
        "outlines": outlines,
        "chapter_summaries": chapter_summaries,
        "relationship_graph": build_character_graph(characters),
        "latest_guardian_alerts": [],
        "latest_final_package": None,
        "story_bible": story_bible,
        "knowledge_provenance": knowledge_provenance,
    }


async def search_knowledge(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    query: str,
    entity_type: Optional[str] = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    hits = await vector_store.search(
        project_id=str(project_id),
        query=query,
        limit=limit,
        entity_type=entity_type,
    )
    return [
        {
            "entity_type": hit.entity_type,
            "entity_id": hit.entity_id,
            "score": hit.score,
            "content": hit.content,
            "metadata": hit.metadata,
        }
        for hit in hits
    ]


async def _build_workspace_story_bible(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: UUID | None = None,
) -> dict[str, Any] | None:
    # workspace 需要直接带上当前默认主线的可见设定，前台才能真正只认一套入口。
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_READ,
    )
    branches = sorted(
        list(project.branches),
        key=lambda item: (0 if item.is_default else 1, item.created_at),
    )
    target_branch = (
        next((item for item in branches if item.id == branch_id), None)
        if branch_id is not None
        else None
    )
    if target_branch is None:
        target_branch = next((item for item in branches if item.is_default), None)
    if target_branch is None and branches:
        target_branch = branches[0]
    if target_branch is None:
        return None
    story_bible = await build_story_bible_payload(
        session,
        project,
        branch_id=target_branch.id,
    )
    return story_bible.model_dump(mode="json")


async def _build_workspace_knowledge_provenance(
    session: AsyncSession,
    *,
    project_id: UUID,
    characters: list[StoryCharacter],
    foreshadows: list[StoryForeshadow],
    items: list[StoryItem],
    world_rules: list[StoryWorldRule],
    timeline_events: list[StoryTimelineMapEvent],
    chapter_summaries: list[StoryChapterSummary],
    story_bible: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    story_bible_payload = story_bible if isinstance(story_bible, dict) else {}
    section_override_lookup = _build_story_bible_override_lookup(story_bible_payload)
    scope_kind = str((story_bible_payload.get("scope") or {}).get("scope_kind") or "project")

    section_sources: dict[str, list[Any]] = {
        "characters": list(characters),
        "foreshadows": list(foreshadows),
        "items": list(items),
        "locations": list(story_bible_payload.get("locations") or []),
        "factions": list(story_bible_payload.get("factions") or []),
        "plot_threads": list(story_bible_payload.get("plot_threads") or []),
        "world_rules": list(world_rules),
        "timeline_events": list(timeline_events),
    }

    nodes: dict[str, dict[str, Any]] = {}
    for section_key in WORKSPACE_PROVENANCE_SECTION_KEYS:
        for item in section_sources.get(section_key, []):
            node = _build_provenance_node(
                section_key=section_key,
                item=item,
                scope_kind=scope_kind,
                override_entity_keys=section_override_lookup.get(section_key, set()),
            )
            if node is not None:
                nodes[node["_node_key"]] = node

    if not nodes:
        return []

    await _attach_latest_version_metadata(
        session,
        project_id=project_id,
        nodes=nodes,
    )
    indexes = _build_provenance_indexes(nodes)
    _attach_workspace_relations(section_sources=section_sources, nodes=nodes, indexes=indexes)
    _attach_chapter_summary_provenance(
        chapter_summaries=chapter_summaries,
        nodes=nodes,
        indexes=indexes,
    )

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        section_order = WORKSPACE_PROVENANCE_SECTION_KEYS.index(item["section_key"])
        return section_order, str(item["label"])

    serialized_nodes: list[dict[str, Any]] = []
    for node in sorted(nodes.values(), key=sort_key):
        serialized_nodes.append(
            {
                "section_key": node["section_key"],
                "entity_key": node["entity_key"],
                "entity_id": node["entity_id"],
                "label": node["label"],
                "scope_origin": node["scope_origin"],
                "last_source_workflow": node.get("last_source_workflow"),
                "last_action": node.get("last_action"),
                "last_updated_at": node.get("last_updated_at"),
                "recent_chapters": sorted(node["recent_chapters"]),
                "inbound_relations": node["inbound_relations"],
                "outbound_relations": node["outbound_relations"],
            }
        )
    return serialized_nodes


def _build_story_bible_override_lookup(story_bible: dict[str, Any]) -> dict[str, set[str]]:
    scope = story_bible.get("scope") if isinstance(story_bible, dict) else {}
    details = scope.get("section_override_details") if isinstance(scope, dict) else []
    lookup: dict[str, set[str]] = defaultdict(set)
    if not isinstance(details, list):
        return {}
    for section in details:
        if not isinstance(section, dict):
            continue
        section_key = str(section.get("section_key") or "").strip()
        if not section_key:
            continue
        for item in section.get("items") or []:
            if not isinstance(item, dict):
                continue
            entity_key = str(item.get("entity_key") or "").strip()
            if entity_key:
                lookup[section_key].add(entity_key)
    return dict(lookup)


def _build_provenance_node(
    *,
    section_key: str,
    item: Any,
    scope_kind: str,
    override_entity_keys: set[str],
) -> dict[str, Any] | None:
    entity_key = _resolve_provenance_entity_key(section_key, item)
    label = _resolve_provenance_label(section_key, item)
    if not entity_key or not label:
        return None

    entity_uuid = _resolve_provenance_entity_uuid(section_key, item)
    scope_origin = "project"
    if section_key in {"locations", "factions", "plot_threads"} and scope_kind == "branch":
        scope_origin = "branch_override" if entity_key in override_entity_keys else "project_inherited"

    recent_chapters: set[int] = set()
    if section_key == "foreshadows":
        for field in ("chapter_planted", "chapter_planned_reveal"):
            value = _read_item_value(item, field)
            if isinstance(value, int) and value > 0:
                recent_chapters.add(value)
    elif section_key == "timeline_events":
        chapter_number = _read_item_value(item, "chapter_number")
        if isinstance(chapter_number, int) and chapter_number > 0:
            recent_chapters.add(chapter_number)

    return {
        "_node_key": f"{section_key}::{entity_key}",
        "_entity_uuid": entity_uuid,
        "section_key": section_key,
        "entity_key": entity_key,
        "entity_id": str(entity_uuid) if entity_uuid is not None else None,
        "label": label,
        "scope_origin": scope_origin,
        "last_source_workflow": None,
        "last_action": None,
        "last_updated_at": None,
        "recent_chapters": recent_chapters,
        "inbound_relations": [],
        "outbound_relations": [],
        "_inbound_seen": set(),
        "_outbound_seen": set(),
    }


async def _attach_latest_version_metadata(
    session: AsyncSession,
    *,
    project_id: UUID,
    nodes: dict[str, dict[str, Any]],
) -> None:
    entity_ids: set[UUID] = {
        node["_entity_uuid"]
        for node in nodes.values()
        if node.get("_entity_uuid") is not None
        and node["section_key"] in STRUCTURED_PROVENANCE_ENTITY_TYPES
    }
    if not entity_ids:
        return

    statement = (
        select(StoryKnowledgeVersion)
        .where(
            StoryKnowledgeVersion.project_id == project_id,
            StoryKnowledgeVersion.entity_id.in_(entity_ids),
            StoryKnowledgeVersion.entity_type.in_(tuple(STRUCTURED_PROVENANCE_ENTITY_TYPES.values())),
        )
        .order_by(StoryKnowledgeVersion.created_at.desc())
    )
    result = await session.execute(statement)
    latest_records: dict[tuple[str, UUID], StoryKnowledgeVersion] = {}
    for record in result.scalars().all():
        key = (record.entity_type, record.entity_id)
        if key not in latest_records:
            latest_records[key] = record

    for node in nodes.values():
        entity_type = STRUCTURED_PROVENANCE_ENTITY_TYPES.get(node["section_key"])
        entity_uuid = node.get("_entity_uuid")
        if entity_type is None or entity_uuid is None:
            continue
        record = latest_records.get((entity_type, entity_uuid))
        if record is None:
            continue
        node["last_source_workflow"] = record.source_workflow
        node["last_action"] = record.action
        node["last_updated_at"] = record.created_at


def _build_provenance_indexes(
    nodes: dict[str, dict[str, Any]],
) -> dict[str, dict[str, dict[str, str]]]:
    by_label: dict[str, dict[str, str]] = defaultdict(dict)
    by_entity_id: dict[str, dict[str, str]] = defaultdict(dict)
    by_entity_key: dict[str, dict[str, str]] = defaultdict(dict)

    for node_key, node in nodes.items():
        section_key = node["section_key"]
        normalized_label = _normalize_relation_label(node["label"])
        if normalized_label:
            by_label[section_key][normalized_label] = node_key
        if node.get("entity_id"):
            by_entity_id[section_key][str(node["entity_id"])] = node_key
        by_entity_key[section_key][node["entity_key"]] = node_key

    return {
        "by_label": dict(by_label),
        "by_entity_id": dict(by_entity_id),
        "by_entity_key": dict(by_entity_key),
    }


def _attach_workspace_relations(
    *,
    section_sources: dict[str, list[Any]],
    nodes: dict[str, dict[str, Any]],
    indexes: dict[str, dict[str, dict[str, str]]],
) -> None:
    for character in section_sources.get("characters", []):
        source_node_key = _find_node_key_for_item("characters", character, indexes)
        if source_node_key is None:
            continue
        for relation in _read_item_value(character, "relationships") or []:
            if not isinstance(relation, dict):
                continue
            target_node_key = _resolve_target_node_key(
                section_key="characters",
                entity_id=relation.get("target_id"),
                entity_key=None,
                label=relation.get("target_name"),
                indexes=indexes,
            )
            _link_provenance_nodes(
                nodes,
                source_node_key=source_node_key,
                target_node_key=target_node_key,
                relation_type=str(relation.get("relation") or relation.get("type") or "relationship"),
                detail=str(relation.get("note") or relation.get("description") or "").strip() or None,
            )

    for foreshadow in section_sources.get("foreshadows", []):
        source_node_key = _find_node_key_for_item("foreshadows", foreshadow, indexes)
        if source_node_key is None:
            continue
        for target_name in _read_item_value(foreshadow, "related_characters") or []:
            _link_by_label(
                nodes,
                indexes=indexes,
                source_node_key=source_node_key,
                target_section="characters",
                label=target_name,
                relation_type="related_character",
            )
        for target_name in _read_item_value(foreshadow, "related_items") or []:
            _link_by_label(
                nodes,
                indexes=indexes,
                source_node_key=source_node_key,
                target_section="items",
                label=target_name,
                relation_type="related_item",
            )

    for item in section_sources.get("items", []):
        source_node_key = _find_node_key_for_item("items", item, indexes)
        if source_node_key is None:
            continue
        _link_by_label(
            nodes,
            indexes=indexes,
            source_node_key=source_node_key,
            target_section="characters",
            label=_read_item_value(item, "owner"),
            relation_type="owner",
        )
        _link_by_label(
            nodes,
            indexes=indexes,
            source_node_key=source_node_key,
            target_section="locations",
            label=_read_item_value(item, "location"),
            relation_type="located_at",
        )

    for event in section_sources.get("timeline_events", []):
        source_node_key = _find_node_key_for_item("timeline_events", event, indexes)
        if source_node_key is None:
            continue
        _link_by_label(
            nodes,
            indexes=indexes,
            source_node_key=source_node_key,
            target_section="locations",
            label=_read_item_value(event, "location"),
            relation_type="happens_at",
        )
        for state in _read_item_value(event, "character_states") or []:
            if not isinstance(state, dict):
                continue
            _link_by_label(
                nodes,
                indexes=indexes,
                source_node_key=source_node_key,
                target_section="characters",
                label=state.get("name") or state.get("character_name") or state.get("character"),
                relation_type="tracks_character_state",
            )

    for faction in section_sources.get("factions", []):
        source_node_key = _find_node_key_for_item("factions", faction, indexes)
        if source_node_key is None:
            continue
        _link_by_label(
            nodes,
            indexes=indexes,
            source_node_key=source_node_key,
            target_section="characters",
            label=_read_item_value(faction, "leader"),
            relation_type="leader",
        )
        for member in _read_item_value(faction, "members") or []:
            _link_by_label(
                nodes,
                indexes=indexes,
                source_node_key=source_node_key,
                target_section="characters",
                label=member,
                relation_type="member",
            )
        _link_by_label(
            nodes,
            indexes=indexes,
            source_node_key=source_node_key,
            target_section="locations",
            label=_read_item_value(faction, "territory"),
            relation_type="territory",
        )

    for plot_thread in section_sources.get("plot_threads", []):
        source_node_key = _find_node_key_for_item("plot_threads", plot_thread, indexes)
        if source_node_key is None:
            continue
        data = _read_item_value(plot_thread, "data")
        if not isinstance(data, dict):
            continue
        for field in ("focus_characters", "main_characters", "characters", "related_characters"):
            for name in data.get(field) or []:
                _link_by_label(
                    nodes,
                    indexes=indexes,
                    source_node_key=source_node_key,
                    target_section="characters",
                    label=name,
                    relation_type="focus_character",
                )
        for field in ("locations", "key_locations", "related_locations"):
            for name in data.get(field) or []:
                _link_by_label(
                    nodes,
                    indexes=indexes,
                    source_node_key=source_node_key,
                    target_section="locations",
                    label=name,
                    relation_type="focus_location",
                )


def _attach_chapter_summary_provenance(
    *,
    chapter_summaries: list[StoryChapterSummary],
    nodes: dict[str, dict[str, Any]],
    indexes: dict[str, dict[str, dict[str, str]]],
) -> None:
    for summary in chapter_summaries:
        chapter_number = getattr(summary, "chapter_number", None)
        if not isinstance(chapter_number, int) or chapter_number <= 0:
            continue
        for raw_suggestion in getattr(summary, "kb_update_suggestions", []) or []:
            if not isinstance(raw_suggestion, dict):
                continue
            if str(raw_suggestion.get("status") or "").strip().lower() != "applied":
                continue
            section_key = _normalize_workspace_section_key(
                raw_suggestion.get("applied_entity_type") or raw_suggestion.get("entity_type")
            )
            if section_key is None:
                continue
            target_node_key = _resolve_target_node_key(
                section_key=section_key,
                entity_id=raw_suggestion.get("applied_entity_id"),
                entity_key=raw_suggestion.get("applied_entity_key"),
                label=raw_suggestion.get("applied_entity_label")
                or raw_suggestion.get("name")
                or raw_suggestion.get("title")
                or raw_suggestion.get("content")
                or raw_suggestion.get("rule_name")
                or raw_suggestion.get("core_event"),
                indexes=indexes,
            )
            if target_node_key is None:
                continue
            nodes[target_node_key]["recent_chapters"].add(chapter_number)
            _append_external_relation(
                nodes[target_node_key],
                direction="inbound",
                signature=f"chapter-summary::{chapter_number}::{raw_suggestion.get('suggestion_id')}",
                relation={
                    "relation_type": "applied_update",
                    "section_key": "chapter_summaries",
                    "entity_key": f"chapter:{chapter_number}",
                    "entity_id": str(getattr(summary, "summary_id", "")) or None,
                    "label": f"第{chapter_number}章总结",
                    "detail": "这条设定由章节总结里的更新建议落库。",
                },
            )


def _find_node_key_for_item(
    section_key: str,
    item: Any,
    indexes: dict[str, dict[str, dict[str, str]]],
) -> str | None:
    return _resolve_target_node_key(
        section_key=section_key,
        entity_id=_resolve_provenance_entity_uuid(section_key, item),
        entity_key=_resolve_provenance_entity_key(section_key, item),
        label=_resolve_provenance_label(section_key, item),
        indexes=indexes,
    )


def _resolve_target_node_key(
    *,
    section_key: str,
    entity_id: Any,
    entity_key: Any,
    label: Any,
    indexes: dict[str, dict[str, dict[str, str]]],
) -> str | None:
    if entity_id is not None:
        key = indexes.get("by_entity_id", {}).get(section_key, {}).get(str(entity_id))
        if key is not None:
            return key
    if entity_key is not None:
        key = indexes.get("by_entity_key", {}).get(section_key, {}).get(str(entity_key))
        if key is not None:
            return key
    normalized_label = _normalize_relation_label(label)
    if normalized_label:
        return indexes.get("by_label", {}).get(section_key, {}).get(normalized_label)
    return None


def _link_by_label(
    nodes: dict[str, dict[str, Any]],
    *,
    indexes: dict[str, dict[str, dict[str, str]]],
    source_node_key: str,
    target_section: str,
    label: Any,
    relation_type: str,
) -> None:
    target_node_key = _resolve_target_node_key(
        section_key=target_section,
        entity_id=None,
        entity_key=None,
        label=label,
        indexes=indexes,
    )
    _link_provenance_nodes(
        nodes,
        source_node_key=source_node_key,
        target_node_key=target_node_key,
        relation_type=relation_type,
        detail=None,
    )


def _link_provenance_nodes(
    nodes: dict[str, dict[str, Any]],
    *,
    source_node_key: str | None,
    target_node_key: str | None,
    relation_type: str,
    detail: str | None,
) -> None:
    if source_node_key is None or target_node_key is None or source_node_key == target_node_key:
        return
    source_node = nodes.get(source_node_key)
    target_node = nodes.get(target_node_key)
    if source_node is None or target_node is None:
        return

    outbound_signature = (
        relation_type,
        target_node["section_key"],
        target_node["entity_key"],
        detail or "",
    )
    if outbound_signature not in source_node["_outbound_seen"]:
        source_node["_outbound_seen"].add(outbound_signature)
        source_node["outbound_relations"].append(
            {
                "relation_type": relation_type,
                "section_key": target_node["section_key"],
                "entity_key": target_node["entity_key"],
                "entity_id": target_node["entity_id"],
                "label": target_node["label"],
                "detail": detail,
            }
        )

    inbound_signature = (
        relation_type,
        source_node["section_key"],
        source_node["entity_key"],
        detail or "",
    )
    if inbound_signature not in target_node["_inbound_seen"]:
        target_node["_inbound_seen"].add(inbound_signature)
        target_node["inbound_relations"].append(
            {
                "relation_type": relation_type,
                "section_key": source_node["section_key"],
                "entity_key": source_node["entity_key"],
                "entity_id": source_node["entity_id"],
                "label": source_node["label"],
                "detail": detail,
            }
        )


def _append_external_relation(
    node: dict[str, Any],
    *,
    direction: str,
    signature: str,
    relation: dict[str, Any],
) -> None:
    seen_key = "_inbound_seen" if direction == "inbound" else "_outbound_seen"
    target_key = "inbound_relations" if direction == "inbound" else "outbound_relations"
    if signature in node[seen_key]:
        return
    node[seen_key].add(signature)
    node[target_key].append(relation)


def _resolve_provenance_entity_uuid(section_key: str, item: Any) -> UUID | None:
    if isinstance(item, dict):
        raw_value = item.get("id")
    elif section_key == "characters":
        raw_value = getattr(item, "character_id", None)
    elif section_key == "foreshadows":
        raw_value = getattr(item, "foreshadow_id", None)
    elif section_key == "items":
        raw_value = getattr(item, "item_id", None)
    elif section_key == "world_rules":
        raw_value = getattr(item, "rule_id", None)
    elif section_key == "timeline_events":
        raw_value = getattr(item, "event_id", None)
    else:
        raw_value = getattr(item, "id", None)
    if isinstance(raw_value, UUID):
        return raw_value
    try:
        return UUID(str(raw_value)) if raw_value else None
    except (TypeError, ValueError):
        return None


def _resolve_provenance_entity_key(section_key: str, item: Any) -> str | None:
    candidates: tuple[str, ...]
    if section_key == "world_rules":
        candidates = ("rule_id", "rule_name")
    elif section_key == "timeline_events":
        candidates = ("event_id", "core_event")
    elif section_key == "foreshadows":
        candidates = ("foreshadow_id", "content")
    else:
        candidates = ("id", "key", "name", "title", "content")

    for field in candidates:
        value = _read_item_value(item, field)
        if value is None:
            continue
        value_text = str(value).strip()
        if value_text:
            return f"{field}:{value_text}"
    return None


def _resolve_provenance_label(section_key: str, item: Any) -> str | None:
    if section_key == "world_rules":
        fields = ("rule_name",)
    elif section_key == "timeline_events":
        fields = ("core_event",)
    elif section_key == "foreshadows":
        fields = ("content",)
    else:
        fields = ("name", "title", "key")
    for field in fields:
        value = _read_item_value(item, field)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _read_item_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _normalize_relation_label(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_workspace_section_key(value: Any) -> str | None:
    normalized = str(value or "").strip().lower()
    aliases = {
        "character": "characters",
        "characters": "characters",
        "foreshadow": "foreshadows",
        "foreshadows": "foreshadows",
        "item": "items",
        "items": "items",
        "location": "locations",
        "locations": "locations",
        "faction": "factions",
        "factions": "factions",
        "plot_thread": "plot_threads",
        "plot_threads": "plot_threads",
        "world_rule": "world_rules",
        "world_rules": "world_rules",
        "timeline": "timeline_events",
        "timeline_event": "timeline_events",
        "timeline_events": "timeline_events",
    }
    return aliases.get(normalized)


def build_character_graph(characters: list[StoryCharacter]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for character in characters:
        nodes.append(
            {
                "id": str(character.character_id),
                "label": character.name,
                "status": character.status,
                "arc_stage": character.arc_stage,
            }
        )
        for relation in character.relationships or []:
            edges.append(
                {
                    "source": str(character.character_id),
                    "target": str(relation.get("target_id") or relation.get("target_name") or ""),
                    "relation": str(relation.get("relation") or relation.get("type") or "关联"),
                    "intensity": relation.get("intensity"),
                }
            )
    return {"nodes": nodes, "edges": edges}


async def _guardian_validate_before_write(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    payload: dict[str, Any],
    current_entity: Any | None,
) -> None:
    if entity_type == "foreshadows":
        planted = payload.get("chapter_planted")
        reveal = payload.get("chapter_planned_reveal")
        if planted is not None and reveal is not None and reveal < planted:
            raise AppError(
                code="story_engine.foreshadow_invalid",
                message="伏笔回收章节不能早于埋设章节。",
                status_code=422,
            )

    if entity_type == "characters":
        relationships = payload.get("relationships")
        if relationships:
            characters = await list_entity_names(session, project_id=project_id)
            known_names = set(characters)
            missing_targets = sorted(
                {
                    str(item.get("target_name")).strip()
                    for item in relationships
                    if item.get("target_name") and str(item.get("target_name")).strip() not in known_names
                }
            )
            if missing_targets:
                raise AppError(
                    code="story_engine.relationship_target_missing",
                    message=f"人物关系引用了不存在的目标人物：{', '.join(missing_targets)}",
                    status_code=422,
                )

    if entity_type == "outlines":
        level = payload.get("level") or getattr(current_entity, "level", None)
        if current_entity is None and level == "level_1":
            payload["locked"] = True
            payload.setdefault("immutable_reason", "一级大纲为全本主线圣经，创建后锁定。")


async def list_entity_names(session: AsyncSession, *, project_id: UUID) -> list[str]:
    statement = select(StoryCharacter.name).where(StoryCharacter.project_id == project_id)
    result = await session.execute(statement)
    return [row[0] for row in result.all()]


async def _create_version_record(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    entity_id: UUID,
    version_number: int,
    action: str,
    snapshot: dict[str, Any],
    summary: str,
    created_by: UUID | None,
    source_workflow: str,
) -> None:
    record = StoryKnowledgeVersion(
        project_id=project_id,
        entity_type=entity_type,
        entity_id=entity_id,
        version_number=version_number,
        action=action,
        snapshot=snapshot,
        summary=summary,
        created_by=created_by,
        source_workflow=source_workflow,
    )
    session.add(record)
    await session.flush()


async def _sync_entity_vector(project_id: UUID, entity_type: str, entity: Any) -> None:
    try:
        await vector_store.upsert_document(
            project_id=str(project_id),
            entity_type=entity_type,
            entity_id=str(_entity_id(entity_type, entity)),
            content=_entity_to_searchable_text(entity_type, entity),
            metadata={
                "label": _entity_label(entity_type, entity),
                "version": getattr(entity, "version", 1),
                "branch_id": (
                    str(getattr(entity, "branch_id"))
                    if getattr(entity, "branch_id", None) is not None
                    else None
                ),
            },
        )
    except Exception:
        # 向量层不是主真相源，索引失败不能影响结构化数据写入。
        return


async def _delete_entity_vector(project_id: UUID, entity_type: str, entity_id: UUID) -> None:
    try:
        await vector_store.delete_document(
            project_id=str(project_id),
            entity_type=entity_type,
            entity_id=str(entity_id),
        )
    except Exception:
        return


def _get_registry(entity_type: str) -> StoryEntityRegistry:
    registry = ENTITY_REGISTRY.get(entity_type)
    if registry is None:
        raise AppError(
            code="story_engine.unsupported_entity",
            message=f"Unsupported story entity type: {entity_type}",
            status_code=400,
        )
    return registry


def _is_branch_scoped_entity(entity_type: str) -> bool:
    return entity_type in {"outlines", "chapter_summaries"}


async def _resolve_effective_branch_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: UUID | None,
    permission: str,
) -> UUID:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=permission,
    )
    branches = sorted(
        list(project.branches),
        key=lambda item: (0 if item.is_default else 1, item.created_at),
    )
    if not branches:
        raise AppError(
            code="story_engine.branch_scope_missing",
            message="当前项目还没有可用分线，暂时不能保存这类内容。",
            status_code=409,
        )
    if branch_id is not None:
        matched_branch = next((item for item in branches if item.id == branch_id), None)
        if matched_branch is None:
            raise AppError(
                code="story_engine.branch_scope_not_found",
                message="当前分线不存在或已经被删除，请刷新后重试。",
                status_code=404,
            )
        return matched_branch.id
    default_branch = next((item for item in branches if item.is_default), None)
    return (default_branch or branches[0]).id


async def _validate_branch_scoped_payload(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    payload: dict[str, Any],
    current_entity: Any | None,
) -> None:
    if entity_type != "outlines":
        return

    parent_id = payload.get("parent_id")
    if parent_id is None:
        return

    branch_id = payload.get("branch_id") or getattr(current_entity, "branch_id", None)
    if branch_id is None:
        raise AppError(
            code="story_engine.branch_scope_required",
            message="当前大纲缺少分线范围，暂时不能建立父子节点关系。",
            status_code=422,
        )

    statement = select(StoryOutline).where(
        StoryOutline.project_id == project_id,
        StoryOutline.outline_id == parent_id,
    )
    result = await session.execute(statement)
    parent_outline = result.scalar_one_or_none()
    if parent_outline is None:
        raise AppError(
            code="story_engine.outline_parent_not_found",
            message="父级大纲不存在，请刷新后重试。",
            status_code=404,
        )
    if parent_outline.branch_id != branch_id:
        raise AppError(
            code="story_engine.outline_cross_branch_parent",
            message="不能把当前分线的大纲节点挂到另一条分线下面。",
            status_code=422,
        )


def _normalize_create_payload(entity_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if entity_type == "outlines" and normalized.get("level") == "level_1":
        normalized["locked"] = True
        normalized.setdefault("immutable_reason", "一级大纲为锁死主线。")
    return normalized


def _entity_id(entity_type: str, entity: Any) -> Any:
    registry = _get_registry(entity_type)
    return getattr(entity, registry.id_field)


def _entity_label(entity_type: str, entity: Any) -> str:
    if entity_type == "characters":
        return entity.name
    if entity_type == "items":
        return entity.name
    if entity_type == "world_rules":
        return entity.rule_name
    if entity_type == "outlines":
        return entity.title
    if entity_type == "chapter_summaries":
        return f"第{entity.chapter_number}章总结"
    if entity_type == "timeline_events":
        return entity.core_event[:24]
    return getattr(entity, "content", "")[:24]


def _entity_to_searchable_text(entity_type: str, entity: Any) -> str:
    if entity_type == "characters":
        return "\n".join(
            [
                f"人物：{entity.name}",
                f"外貌：{entity.appearance or ''}",
                f"性格：{entity.personality or ''}",
                f"微习惯：{'、'.join(entity.micro_habits or [])}",
                f"能力：{entity.abilities}",
                f"关系：{entity.relationships}",
                f"状态：{entity.status}",
                f"弧光阶段：{entity.arc_stage}",
                f"边界：{entity.arc_boundaries}",
            ]
        )
    if entity_type == "foreshadows":
        return "\n".join(
            [
                f"伏笔：{entity.content}",
                f"埋设章节：{entity.chapter_planted}",
                f"计划回收章节：{entity.chapter_planned_reveal}",
                f"状态：{entity.status}",
                f"关联人物：{entity.related_characters}",
                f"关联物品：{entity.related_items}",
            ]
        )
    if entity_type == "items":
        return "\n".join(
            [
                f"物品：{entity.name}",
                f"特征：{entity.features or ''}",
                f"当前归属：{entity.owner or ''}",
                f"当前位置：{entity.location or ''}",
                f"特殊规则：{entity.special_rules}",
            ]
        )
    if entity_type == "world_rules":
        return "\n".join(
            [
                f"规则：{entity.rule_name}",
                f"内容：{entity.rule_content}",
                f"禁令：{entity.negative_list}",
                f"范围：{entity.scope}",
            ]
        )
    if entity_type == "timeline_events":
        return "\n".join(
            [
                f"章节：{entity.chapter_number}",
                f"剧中时间：{entity.in_universe_time or ''}",
                f"地点：{entity.location or ''}",
                f"天气：{entity.weather or ''}",
                f"事件：{entity.core_event}",
                f"人物状态：{entity.character_states}",
            ]
        )
    if entity_type == "outlines":
        return "\n".join(
            [
                f"分线：{entity.branch_id}",
                f"大纲层级：{entity.level}",
                f"标题：{entity.title}",
                f"内容：{entity.content}",
                f"状态：{entity.status}",
                f"锁定：{entity.locked}",
            ]
        )
    if entity_type == "chapter_summaries":
        return "\n".join(
            [
                f"分线：{entity.branch_id}",
                f"章节：{entity.chapter_number}",
                f"总结：{entity.content}",
                f"核心推进：{entity.core_progress}",
                f"人物变化：{entity.character_changes}",
                f"伏笔更新：{entity.foreshadow_updates}",
                f"知识库建议：{entity.kb_update_suggestions}",
            ]
        )
    return str(entity)


def _serialize_entity(entity_type: str, entity: Any) -> dict[str, Any]:
    if entity_type == "characters":
        return {
            "character_id": str(entity.character_id),
            "project_id": str(entity.project_id),
            "name": entity.name,
            "appearance": entity.appearance,
            "personality": entity.personality,
            "micro_habits": entity.micro_habits,
            "abilities": entity.abilities,
            "relationships": entity.relationships,
            "status": entity.status,
            "arc_stage": entity.arc_stage,
            "arc_boundaries": entity.arc_boundaries,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "foreshadows":
        return {
            "foreshadow_id": str(entity.foreshadow_id),
            "project_id": str(entity.project_id),
            "content": entity.content,
            "chapter_planted": entity.chapter_planted,
            "chapter_planned_reveal": entity.chapter_planned_reveal,
            "status": entity.status,
            "related_characters": entity.related_characters,
            "related_items": entity.related_items,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "items":
        return {
            "item_id": str(entity.item_id),
            "project_id": str(entity.project_id),
            "name": entity.name,
            "features": entity.features,
            "owner": entity.owner,
            "location": entity.location,
            "special_rules": entity.special_rules,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "world_rules":
        return {
            "rule_id": str(entity.rule_id),
            "project_id": str(entity.project_id),
            "rule_name": entity.rule_name,
            "rule_content": entity.rule_content,
            "negative_list": entity.negative_list,
            "scope": entity.scope,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "timeline_events":
        return {
            "event_id": str(entity.event_id),
            "project_id": str(entity.project_id),
            "chapter_number": entity.chapter_number,
            "in_universe_time": entity.in_universe_time,
            "location": entity.location,
            "weather": entity.weather,
            "core_event": entity.core_event,
            "character_states": entity.character_states,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "outlines":
        return {
            "outline_id": str(entity.outline_id),
            "project_id": str(entity.project_id),
            "branch_id": str(entity.branch_id),
            "parent_id": str(entity.parent_id) if entity.parent_id is not None else None,
            "level": entity.level,
            "title": entity.title,
            "content": entity.content,
            "status": entity.status,
            "version": entity.version,
            "node_order": entity.node_order,
            "locked": entity.locked,
            "immutable_reason": entity.immutable_reason,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    if entity_type == "chapter_summaries":
        return {
            "summary_id": str(entity.summary_id),
            "project_id": str(entity.project_id),
            "branch_id": str(entity.branch_id),
            "chapter_number": entity.chapter_number,
            "content": entity.content,
            "core_progress": entity.core_progress,
            "character_changes": entity.character_changes,
            "foreshadow_updates": entity.foreshadow_updates,
            "kb_update_suggestions": entity.kb_update_suggestions,
            "version": entity.version,
            "created_at": entity.created_at.isoformat(),
            "updated_at": entity.updated_at.isoformat(),
        }
    raise AppError(
        code="story_engine.unsupported_entity",
        message=f"Unsupported story entity type: {entity_type}",
        status_code=400,
    )


def _deserialize_snapshot_value(field: str, value: Any) -> Any:
    if field.endswith("_id") and isinstance(value, str) and value:
        try:
            return UUID(value)
        except ValueError:
            return value
    return value
