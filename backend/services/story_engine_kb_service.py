from __future__ import annotations

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
from services.chroma_service import StoryEngineChromaService
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


vector_store = StoryEngineChromaService()


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
) -> list[Any]:
    await get_story_engine_project(
        session,
        project_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    registry = _get_registry(entity_type)
    statement = select(registry.model).where(registry.model.project_id == project_id)
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
    await _guardian_validate_before_write(
        session,
        project_id=project_id,
        entity_type=entity_type,
        payload=payload,
        current_entity=None,
    )
    normalized_payload = _normalize_create_payload(entity_type, payload)
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
    )
    chapter_summaries = await list_entities(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="chapter_summaries",
    )
    story_bible = await _build_workspace_story_bible(
        session,
        project_id=project_id,
        user_id=user_id,
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
    default_branch = next((item for item in branches if item.is_default), None)
    if default_branch is None and branches:
        default_branch = branches[0]
    if default_branch is None:
        return None
    story_bible = await build_story_bible_payload(
        session,
        project,
        branch_id=default_branch.id,
    )
    return story_bible.model_dump(mode="json")


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
