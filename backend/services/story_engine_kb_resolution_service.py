from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.story_engine import (
    StoryCharacter,
    StoryChapterSummary,
    StoryForeshadow,
    StoryItem,
    StoryTimelineMapEvent,
    StoryWorldRule,
)
from services.project_service import PROJECT_PERMISSION_EDIT
from services.story_engine_kb_service import create_entity, get_entity, update_entity
from services.story_engine_unified_knowledge_service import save_story_knowledge

KB_SUGGESTION_STATUS_PENDING = "pending"
KB_SUGGESTION_STATUS_APPLIED = "applied"
KB_SUGGESTION_STATUS_IGNORED = "ignored"

SECTION_KEY_ALIASES = {
    "character": "characters",
    "characters": "characters",
    "foreshadow": "foreshadows",
    "foreshadows": "foreshadows",
    "item": "items",
    "items": "items",
    "world_rule": "world_rules",
    "world_rules": "world_rules",
    "timeline": "timeline_events",
    "timeline_event": "timeline_events",
    "timeline_events": "timeline_events",
    "location": "locations",
    "locations": "locations",
    "faction": "factions",
    "factions": "factions",
    "plot_thread": "plot_threads",
    "plot_threads": "plot_threads",
}


async def resolve_chapter_summary_kb_suggestion(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    summary_id: UUID,
    suggestion_id: str,
    action: str,
) -> dict[str, Any]:
    chapter_summary = await get_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="chapter_summaries",
        entity_id=summary_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    suggestions = _normalize_kb_update_suggestions(
        getattr(chapter_summary, "kb_update_suggestions", []),
        chapter_number=chapter_summary.chapter_number,
    )
    suggestion_index = next(
        (index for index, item in enumerate(suggestions) if item["suggestion_id"] == suggestion_id),
        None,
    )
    if suggestion_index is None:
        raise AppError(
            code="story_engine.kb_suggestion_not_found",
            message="没有找到这条待处理的设定更新。",
            status_code=404,
        )

    current_suggestion = suggestions[suggestion_index]
    target_status = _resolve_target_status(action)
    current_status = str(current_suggestion.get("status") or KB_SUGGESTION_STATUS_PENDING)
    if current_status == target_status:
        return _build_resolution_response(
            chapter_summary=chapter_summary,
            resolved_suggestion=current_suggestion,
            message=(
                "这条设定已经记进去了。"
                if target_status == KB_SUGGESTION_STATUS_APPLIED
                else "这条设定已经被你忽略了。"
            ),
        )
    if current_status != KB_SUGGESTION_STATUS_PENDING:
        raise AppError(
            code="story_engine.kb_suggestion_already_resolved",
            message="这条设定更新已经处理过了，暂时不能重复改状态。",
            status_code=409,
        )

    resolved_suggestion = dict(current_suggestion)
    resolved_suggestion["status"] = target_status
    resolved_suggestion["resolved_at"] = datetime.now(timezone.utc).isoformat()

    response_meta: dict[str, Any] = {}
    if target_status == KB_SUGGESTION_STATUS_APPLIED:
        response_meta = await _apply_pending_kb_suggestion(
            session,
            project_id=project_id,
            user_id=user_id,
            branch_id=chapter_summary.branch_id,
            suggestion=current_suggestion,
        )
        resolved_suggestion.update(
            {
                key: value
                for key, value in {
                    "applied_entity_type": response_meta.get("applied_entity_type"),
                    "applied_entity_id": (
                        str(response_meta["applied_entity_id"])
                        if response_meta.get("applied_entity_id") is not None
                        else None
                    ),
                    "applied_entity_key": response_meta.get("applied_entity_key"),
                    "applied_entity_label": response_meta.get("applied_entity_label"),
                }.items()
                if value is not None
            }
        )

    suggestions[suggestion_index] = resolved_suggestion
    updated_summary = await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="chapter_summaries",
        entity_id=summary_id,
        payload={"kb_update_suggestions": suggestions},
        source_workflow="kb_update_resolution",
    )
    return _build_resolution_response(
        chapter_summary=updated_summary,
        resolved_suggestion=resolved_suggestion,
        message=(
            response_meta.get("message")
            if target_status == KB_SUGGESTION_STATUS_APPLIED
            else "这条设定先不记，已经从待处理列表里标记为忽略。"
        ),
        applied_entity_type=response_meta.get("applied_entity_type"),
        applied_entity_id=response_meta.get("applied_entity_id"),
        applied_entity_key=response_meta.get("applied_entity_key"),
        applied_entity_label=response_meta.get("applied_entity_label"),
    )


def _build_resolution_response(
    *,
    chapter_summary: StoryChapterSummary,
    resolved_suggestion: dict[str, Any],
    message: str,
    applied_entity_type: Optional[str] = None,
    applied_entity_id: Optional[UUID] = None,
    applied_entity_key: Optional[str] = None,
    applied_entity_label: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "chapter_summary": chapter_summary,
        "resolved_suggestion": resolved_suggestion,
        "applied_entity_type": applied_entity_type,
        "applied_entity_id": applied_entity_id,
        "applied_entity_key": applied_entity_key,
        "applied_entity_label": applied_entity_label,
        "message": message,
    }


def _resolve_target_status(action: str) -> str:
    normalized = str(action or "").strip().lower()
    if normalized == "apply":
        return KB_SUGGESTION_STATUS_APPLIED
    if normalized == "ignore":
        return KB_SUGGESTION_STATUS_IGNORED
    raise AppError(
        code="story_engine.kb_suggestion_action_invalid",
        message="这次处理动作不合法，请刷新后重试。",
        status_code=422,
    )


def _normalize_kb_update_suggestions(
    raw_updates: Any,
    *,
    chapter_number: int,
) -> list[dict[str, Any]]:
    if not isinstance(raw_updates, list):
        return []
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(raw_updates):
        if not isinstance(item, dict):
            continue
        suggestion = {
            key: value for key, value in item.items() if value is not None
        }
        suggestion_id = str(suggestion.get("suggestion_id") or "").strip() or f"kb-{chapter_number}-{index + 1}"
        suggestion["suggestion_id"] = suggestion_id
        suggestion["entity_type"] = _resolve_section_key(suggestion.get("entity_type"))
        suggestion["action"] = str(suggestion.get("action") or "upsert").strip() or "upsert"
        suggestion["status"] = _normalize_status(suggestion.get("status"))
        suggestion.setdefault("chapter_number", chapter_number)
        normalized.append(suggestion)
    return normalized


def _normalize_status(raw_status: Any) -> str:
    status = str(raw_status or KB_SUGGESTION_STATUS_PENDING).strip().lower()
    if status not in {
        KB_SUGGESTION_STATUS_PENDING,
        KB_SUGGESTION_STATUS_APPLIED,
        KB_SUGGESTION_STATUS_IGNORED,
    }:
        return KB_SUGGESTION_STATUS_PENDING
    return status


def _resolve_section_key(raw_value: Any) -> str:
    raw_key = str(raw_value or "timeline_events").strip().lower()
    return SECTION_KEY_ALIASES.get(raw_key, raw_key or "timeline_events")


async def _apply_pending_kb_suggestion(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    branch_id: UUID,
    suggestion: dict[str, Any],
) -> dict[str, Any]:
    section_key = _resolve_section_key(suggestion.get("entity_type"))
    if section_key == "timeline_events":
        entity = await _upsert_timeline_event(
            session,
            project_id=project_id,
            user_id=user_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_id": entity.event_id,
            "applied_entity_label": entity.core_event,
            "message": f"{entity.core_event[:32]} 已记入时间线。",
        }
    if section_key == "foreshadows":
        entity = await _upsert_foreshadow(
            session,
            project_id=project_id,
            user_id=user_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_id": entity.foreshadow_id,
            "applied_entity_label": entity.content[:32],
            "message": "这条伏笔已经记进伏笔库。",
        }
    if section_key == "world_rules":
        entity = await _upsert_world_rule(
            session,
            project_id=project_id,
            user_id=user_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_id": entity.rule_id,
            "applied_entity_label": entity.rule_name,
            "message": f"规则《{entity.rule_name}》已经记进设定。",
        }
    if section_key == "items":
        entity = await _upsert_item(
            session,
            project_id=project_id,
            user_id=user_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_id": entity.item_id,
            "applied_entity_label": entity.name,
            "message": f"{entity.name} 已记进物品库。",
        }
    if section_key == "characters":
        entity = await _upsert_character(
            session,
            project_id=project_id,
            user_id=user_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_id": entity.character_id,
            "applied_entity_label": entity.name,
            "message": f"{entity.name} 已记进人物库。",
        }
    if section_key in {"locations", "factions", "plot_threads"}:
        entity_key, entity_label = await _upsert_story_bible_section(
            session,
            project_id=project_id,
            user_id=user_id,
            section_key=section_key,
            branch_id=branch_id,
            suggestion=suggestion,
        )
        return {
            "applied_entity_type": section_key,
            "applied_entity_key": entity_key,
            "applied_entity_label": entity_label,
            "message": f"{entity_label} 已记进主设定。",
        }
    raise AppError(
        code="story_engine.kb_suggestion_unsupported",
        message="这条设定更新暂时还不能自动记入，请先手动补进设定圣经。",
        status_code=422,
        metadata={"entity_type": section_key},
    )


async def _upsert_character(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    suggestion: dict[str, Any],
):
    name = _required_text(
        suggestion,
        fields=("name", "character_name", "title"),
        error_message="这条人物更新缺少名字，暂时不能自动记入。",
    )
    create_payload = {
        "name": name,
        "appearance": _optional_text(suggestion.get("appearance")),
        "personality": _optional_text(suggestion.get("personality"))
        or _optional_text(suggestion.get("content"))
        or _optional_text(suggestion.get("note")),
        "micro_habits": _string_list(suggestion.get("micro_habits")),
        "abilities": suggestion.get("abilities") if isinstance(suggestion.get("abilities"), dict) else {},
        "relationships": [],
        "status": _optional_text(suggestion.get("status")) or "active",
        "arc_stage": _optional_text(suggestion.get("arc_stage")) or "initial",
        "arc_boundaries": [],
    }
    update_payload = {
        "appearance": create_payload["appearance"],
        "personality": create_payload["personality"],
        "status": create_payload["status"] if suggestion.get("status") else None,
        "arc_stage": create_payload["arc_stage"] if suggestion.get("arc_stage") else None,
    }
    if create_payload["micro_habits"]:
        update_payload["micro_habits"] = create_payload["micro_habits"]
    if create_payload["abilities"]:
        update_payload["abilities"] = create_payload["abilities"]
    existing = await _find_entity_by_field(
        session,
        model=StoryCharacter,
        project_id=project_id,
        field_name="name",
        field_value=name,
    )
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="characters",
            payload=create_payload,
            source_workflow="kb_update_resolution",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="characters",
        entity_id=existing.character_id,
        payload={key: value for key, value in update_payload.items() if value is not None},
        source_workflow="kb_update_resolution",
    )


async def _upsert_item(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    suggestion: dict[str, Any],
):
    name = _required_text(
        suggestion,
        fields=("name", "title"),
        error_message="这条物品更新缺少名字，暂时不能自动记入。",
    )
    create_payload = {
        "name": name,
        "features": _optional_text(suggestion.get("features"))
        or _optional_text(suggestion.get("content"))
        or _optional_text(suggestion.get("note")),
        "owner": _optional_text(suggestion.get("owner")),
        "location": _optional_text(suggestion.get("location")),
        "special_rules": _string_list(
            suggestion.get("special_rules") or suggestion.get("effects") or suggestion.get("rules")
        ),
    }
    update_payload = {
        key: value
        for key, value in create_payload.items()
        if value not in (None, [], {})
    }
    existing = await _find_entity_by_field(
        session,
        model=StoryItem,
        project_id=project_id,
        field_name="name",
        field_value=name,
    )
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="items",
            payload=create_payload,
            source_workflow="kb_update_resolution",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="items",
        entity_id=existing.item_id,
        payload=update_payload,
        source_workflow="kb_update_resolution",
    )


async def _upsert_world_rule(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    suggestion: dict[str, Any],
):
    rule_name = _required_text(
        suggestion,
        fields=("rule_name", "title", "name"),
        error_message="这条规则更新缺少规则名，暂时不能自动记入。",
    )
    create_payload = {
        "rule_name": rule_name,
        "rule_content": _required_text(
            suggestion,
            fields=("rule_content", "content", "note", "summary"),
            error_message="这条规则更新缺少规则内容，暂时不能自动记入。",
        ),
        "negative_list": _string_list(suggestion.get("negative_list")),
        "scope": _optional_text(suggestion.get("scope")) or "global",
    }
    update_payload = {
        "rule_content": create_payload["rule_content"],
        "scope": create_payload["scope"] if suggestion.get("scope") else None,
    }
    if create_payload["negative_list"]:
        update_payload["negative_list"] = create_payload["negative_list"]
    existing = await _find_entity_by_field(
        session,
        model=StoryWorldRule,
        project_id=project_id,
        field_name="rule_name",
        field_value=rule_name,
    )
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="world_rules",
            payload=create_payload,
            source_workflow="kb_update_resolution",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="world_rules",
        entity_id=existing.rule_id,
        payload={key: value for key, value in update_payload.items() if value is not None},
        source_workflow="kb_update_resolution",
    )


async def _upsert_foreshadow(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    suggestion: dict[str, Any],
):
    content = _required_text(
        suggestion,
        fields=("content", "note", "title", "core_event"),
        error_message="这条伏笔更新缺少内容，暂时不能自动记入。",
    )
    create_payload = {
        "content": content,
        "chapter_planted": _integer_value(
            suggestion.get("chapter_planted"),
            default=_integer_value(suggestion.get("chapter_number")),
        ),
        "chapter_planned_reveal": _integer_value(suggestion.get("chapter_planned_reveal")),
        "status": _optional_text(suggestion.get("foreshadow_status"))
        or _optional_text(suggestion.get("status"))
        or "pending",
        "related_characters": _string_list(suggestion.get("related_characters")),
        "related_items": _string_list(suggestion.get("related_items")),
    }
    update_payload = {
        "chapter_planted": create_payload["chapter_planted"],
        "chapter_planned_reveal": create_payload["chapter_planned_reveal"],
        "status": create_payload["status"] if suggestion.get("status") else None,
    }
    if create_payload["related_characters"]:
        update_payload["related_characters"] = create_payload["related_characters"]
    if create_payload["related_items"]:
        update_payload["related_items"] = create_payload["related_items"]
    existing = await _find_entity_by_field(
        session,
        model=StoryForeshadow,
        project_id=project_id,
        field_name="content",
        field_value=content,
    )
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="foreshadows",
            payload=create_payload,
            source_workflow="kb_update_resolution",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="foreshadows",
        entity_id=existing.foreshadow_id,
        payload={key: value for key, value in update_payload.items() if value is not None},
        source_workflow="kb_update_resolution",
    )


async def _upsert_timeline_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    suggestion: dict[str, Any],
):
    chapter_number = _integer_value(suggestion.get("chapter_number"))
    core_event = _required_text(
        suggestion,
        fields=("core_event", "content", "note", "title", "summary"),
        error_message="这条时间线更新缺少核心事件，暂时不能自动记入。",
    )
    create_payload = {
        "chapter_number": chapter_number,
        "in_universe_time": _optional_text(suggestion.get("in_universe_time")),
        "location": _optional_text(suggestion.get("location")),
        "weather": _optional_text(suggestion.get("weather")),
        "core_event": core_event,
        "character_states": _dict_list(suggestion.get("character_states")),
    }
    update_payload = {
        key: value
        for key, value in create_payload.items()
        if value not in (None, [], {})
    }
    existing = await _find_timeline_event(
        session,
        project_id=project_id,
        chapter_number=chapter_number,
        core_event=core_event,
    )
    if existing is None:
        return await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type="timeline_events",
            payload=create_payload,
            source_workflow="kb_update_resolution",
        )
    return await update_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="timeline_events",
        entity_id=existing.event_id,
        payload=update_payload,
        source_workflow="kb_update_resolution",
    )


async def _upsert_story_bible_section(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    section_key: str,
    branch_id: UUID,
    suggestion: dict[str, Any],
) -> tuple[str, str]:
    item = _build_story_bible_payload(section_key, suggestion)
    await save_story_knowledge(
        session,
        project_id=project_id,
        user_id=user_id,
        section_key=section_key,
        item=item,
        branch_id=branch_id,
    )
    if section_key == "locations":
        return f"name:{item['name']}", str(item["name"])
    if section_key == "plot_threads":
        return f"title:{item['title']}", str(item["title"])
    return f"key:{item['key']}", str(item["name"])


def _build_story_bible_payload(section_key: str, suggestion: dict[str, Any]) -> dict[str, Any]:
    if section_key == "locations":
        name = _required_text(
            suggestion,
            fields=("name", "title", "location"),
            error_message="这条地点更新缺少地点名，暂时不能自动记入。",
        )
        return {
            "name": name,
            "data": {
                "type": _optional_text(suggestion.get("type")),
                "climate": _optional_text(suggestion.get("climate")),
                "population": _optional_text(suggestion.get("population")),
                "description": _optional_text(suggestion.get("description"))
                or _optional_text(suggestion.get("content"))
                or _optional_text(suggestion.get("note")),
                "features": _string_list(suggestion.get("features")),
                "notable_residents": _string_list(suggestion.get("notable_residents")),
                "history": _optional_text(suggestion.get("history")),
            },
            "version": 1,
        }
    if section_key == "factions":
        name = _required_text(
            suggestion,
            fields=("name", "title"),
            error_message="这条势力更新缺少势力名，暂时不能自动记入。",
        )
        return {
            "key": _build_faction_key(name),
            "name": name,
            "type": _optional_text(suggestion.get("type")),
            "scale": _optional_text(suggestion.get("scale")),
            "description": _optional_text(suggestion.get("description"))
            or _optional_text(suggestion.get("content"))
            or _optional_text(suggestion.get("note")),
            "goals": _optional_text(suggestion.get("goals")),
            "leader": _optional_text(suggestion.get("leader")),
            "members": _string_list(suggestion.get("members")),
            "territory": _optional_text(suggestion.get("territory")),
            "resources": _string_list(suggestion.get("resources")),
            "ideology": _optional_text(suggestion.get("ideology")),
            "version": 1,
        }
    if section_key == "plot_threads":
        title = _required_text(
            suggestion,
            fields=("title", "name"),
            error_message="这条剧情线更新缺少标题，暂时不能自动记入。",
        )
        return {
            "title": title,
            "status": _optional_text(suggestion.get("status")) or "planned",
            "importance": _integer_value(suggestion.get("importance"), default=1) or 1,
            "data": {
                "type": _optional_text(suggestion.get("type")),
                "description": _optional_text(suggestion.get("description"))
                or _optional_text(suggestion.get("content"))
                or _optional_text(suggestion.get("note")),
                "main_characters": _string_list(suggestion.get("main_characters")),
                "locations": _string_list(suggestion.get("locations")),
                "stages": _string_list(suggestion.get("stages")),
                "tension_arc": _optional_text(suggestion.get("tension_arc")),
                "resolution": _optional_text(suggestion.get("resolution")),
            },
        }
    raise AppError(
        code="story_engine.story_bible_section_unsupported",
        message="这条主设定更新暂时还不能自动记入。",
        status_code=422,
    )


async def _find_entity_by_field(
    session: AsyncSession,
    *,
    model: Any,
    project_id: UUID,
    field_name: str,
    field_value: str,
):
    statement = select(model).where(
        model.project_id == project_id,
        getattr(model, field_name) == field_value,
    )
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def _find_timeline_event(
    session: AsyncSession,
    *,
    project_id: UUID,
    chapter_number: Optional[int],
    core_event: str,
):
    statement = select(StoryTimelineMapEvent).where(
        StoryTimelineMapEvent.project_id == project_id,
        StoryTimelineMapEvent.core_event == core_event,
    )
    if chapter_number is None:
        statement = statement.where(StoryTimelineMapEvent.chapter_number.is_(None))
    else:
        statement = statement.where(StoryTimelineMapEvent.chapter_number == chapter_number)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


def _required_text(
    suggestion: dict[str, Any],
    *,
    fields: tuple[str, ...],
    error_message: str,
) -> str:
    for field in fields:
        value = suggestion.get(field)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    raise AppError(
        code="story_engine.kb_suggestion_field_missing",
        message=error_message,
        status_code=422,
    )


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _integer_value(value: Any, *, default: Optional[int] = None) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[、,/，；;\n]+", value)
        return [item.strip() for item in parts if item and item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _build_faction_key(name: str) -> str:
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff_-]+", "-", name.strip().lower())
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return f"faction:{normalized or 'entry'}"[:100]
