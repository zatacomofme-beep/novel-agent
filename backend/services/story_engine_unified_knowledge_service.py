from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from schemas.project import (
    LocationItem,
    PlotThreadItem,
    StoryBibleBranchItemDelete,
    StoryBibleBranchItemUpsert,
    StoryBibleFactionEntry,
)
from schemas.story_engine import (
    StoryChapterSummaryCreate,
    StoryChapterSummaryUpdate,
    StoryCharacterCreate,
    StoryCharacterUpdate,
    StoryForeshadowCreate,
    StoryForeshadowUpdate,
    StoryItemCreate,
    StoryItemUpdate,
    StoryOutlineCreate,
    StoryOutlineUpdate,
    StoryTimelineMapEventCreate,
    StoryTimelineMapEventUpdate,
    StoryWorldRuleCreate,
    StoryWorldRuleUpdate,
)
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    delete_story_bible_branch_item,
    get_owned_project,
    upsert_story_bible_branch_item,
)
from services.story_engine_kb_service import create_entity, delete_entity, update_entity
from services.story_engine_workflow_service import run_story_knowledge_guard


@dataclass(frozen=True)
class StructuredKnowledgeSectionSpec:
    section_key: str
    entity_type: str
    create_schema: type
    update_schema: type


# 前台虽然只看见“设定圣经”，后台仍需要把不同存储形态路由到正确的数据层。
STRUCTURED_KNOWLEDGE_SECTION_SPECS: dict[str, StructuredKnowledgeSectionSpec] = {
    "characters": StructuredKnowledgeSectionSpec(
        section_key="characters",
        entity_type="characters",
        create_schema=StoryCharacterCreate,
        update_schema=StoryCharacterUpdate,
    ),
    "foreshadows": StructuredKnowledgeSectionSpec(
        section_key="foreshadows",
        entity_type="foreshadows",
        create_schema=StoryForeshadowCreate,
        update_schema=StoryForeshadowUpdate,
    ),
    "items": StructuredKnowledgeSectionSpec(
        section_key="items",
        entity_type="items",
        create_schema=StoryItemCreate,
        update_schema=StoryItemUpdate,
    ),
    "world_rules": StructuredKnowledgeSectionSpec(
        section_key="world_rules",
        entity_type="world_rules",
        create_schema=StoryWorldRuleCreate,
        update_schema=StoryWorldRuleUpdate,
    ),
    "timeline_events": StructuredKnowledgeSectionSpec(
        section_key="timeline_events",
        entity_type="timeline_events",
        create_schema=StoryTimelineMapEventCreate,
        update_schema=StoryTimelineMapEventUpdate,
    ),
    "outlines": StructuredKnowledgeSectionSpec(
        section_key="outlines",
        entity_type="outlines",
        create_schema=StoryOutlineCreate,
        update_schema=StoryOutlineUpdate,
    ),
    "chapter_summaries": StructuredKnowledgeSectionSpec(
        section_key="chapter_summaries",
        entity_type="chapter_summaries",
        create_schema=StoryChapterSummaryCreate,
        update_schema=StoryChapterSummaryUpdate,
    ),
}

STORY_BIBLE_SECTION_SCHEMAS: dict[str, type] = {
    "locations": LocationItem,
    "factions": StoryBibleFactionEntry,
    "plot_threads": PlotThreadItem,
}


def _parse_entity_uuid(entity_id: str, *, action_label: str) -> UUID:
    try:
        return UUID(str(entity_id))
    except (TypeError, ValueError, AttributeError) as exc:
        raise AppError(
            code="story_engine.knowledge_entity_id_invalid",
            message=f"这条设定的标识不合法，暂时无法完成{action_label}。",
            status_code=400,
        ) from exc


def _require_branch_id(branch_id: UUID | None, *, action_label: str) -> UUID:
    if branch_id is None:
        raise AppError(
            code="story_engine.branch_id_required",
            message=f"当前主线还没准备好，暂时无法完成这条设定的{action_label}。",
            status_code=400,
        )
    return branch_id


def _resolve_story_bible_entity_key(item: dict[str, Any]) -> str | None:
    for field in ("id", "key", "name", "title", "content"):
        value = item.get(field)
        if value is None:
            continue
        value_text = str(value).strip()
        if value_text:
            return f"{field}:{value_text}"
    return None


def _get_structured_section_spec(section_key: str) -> StructuredKnowledgeSectionSpec | None:
    return STRUCTURED_KNOWLEDGE_SECTION_SPECS.get(section_key)


async def save_story_knowledge(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    section_key: str,
    item: dict[str, Any],
    entity_id: str | None = None,
    branch_id: UUID | None = None,
    previous_entity_key: str | None = None,
    source_workflow: str = "manual",
    guard_operation: str = "保存",
) -> dict[str, Any]:
    structured_spec = _get_structured_section_spec(section_key)
    if structured_spec is not None:
        validated_payload: dict[str, Any]
        if entity_id:
            validated_payload = structured_spec.update_schema.model_validate(item).model_dump(
                exclude_unset=True
            )
        else:
            validated_payload = structured_spec.create_schema.model_validate(item).model_dump()

        guard_result = await run_story_knowledge_guard(
            session,
            project_id=project_id,
            user_id=user_id,
            section_key=section_key,
            operation=guard_operation,
            candidate_item=validated_payload,
            entity_id=entity_id,
        )
        _raise_when_story_knowledge_guard_blocks(guard_result, action_label=guard_operation)

        if entity_id:
            await update_entity(
                session,
                project_id=project_id,
                user_id=user_id,
                entity_type=structured_spec.entity_type,
                entity_id=_parse_entity_uuid(entity_id, action_label="保存"),
                payload=validated_payload,
                source_workflow=source_workflow,
            )
        else:
            await create_entity(
                session,
                project_id=project_id,
                user_id=user_id,
                entity_type=structured_spec.entity_type,
                payload=validated_payload,
                source_workflow=source_workflow,
            )
        return _build_story_knowledge_mutation_response(
            guard_result,
            action_completed_message="这条设定已保存，并通过守护校验。"
            if not guard_result["warning_count"]
            else (
                f"这条设定已保存，但还带出 {guard_result['warning_count']} 条连续性提醒，"
                "最好顺手修一下。"
            ),
        )

    story_bible_schema = STORY_BIBLE_SECTION_SCHEMAS.get(section_key)
    if story_bible_schema is None:
        raise AppError(
            code="story_engine.knowledge_section_unsupported",
            message="当前设定分类暂时还没有接入统一入口。",
            status_code=404,
        )

    validated_item = story_bible_schema.model_validate(item).model_dump(mode="json")
    guard_result = await run_story_knowledge_guard(
        session,
        project_id=project_id,
        user_id=user_id,
        section_key=section_key,
        operation=guard_operation,
        candidate_item=validated_item,
        entity_id=entity_id,
    )
    _raise_when_story_knowledge_guard_blocks(guard_result, action_label=guard_operation)
    next_entity_key = _resolve_story_bible_entity_key(validated_item)
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    resolved_branch_id = _require_branch_id(branch_id, action_label="保存")
    await upsert_story_bible_branch_item(
        session,
        project,
        StoryBibleBranchItemUpsert(section_key=section_key, item=validated_item),
        actor_user_id=user_id,
        branch_id=resolved_branch_id,
    )

    # 允许前端在“改名/换 key”时一次走统一入口，后台自动清理旧身份。
    if previous_entity_key and next_entity_key and previous_entity_key != next_entity_key:
        await delete_story_bible_branch_item(
            session,
            project,
            StoryBibleBranchItemDelete(
                section_key=section_key,
                entity_key=previous_entity_key,
            ),
            actor_user_id=user_id,
            branch_id=resolved_branch_id,
        )
    return _build_story_knowledge_mutation_response(
        guard_result,
        action_completed_message="这条主设定已保存，当前主线会立刻按新设定生效。"
        if not guard_result["warning_count"]
        else (
            f"这条主设定已保存，但还带出 {guard_result['warning_count']} 条连续性提醒，"
            "最好顺手修一下。"
        ),
    )


async def delete_story_knowledge(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    section_key: str,
    entity_id: str,
    branch_id: UUID | None = None,
    source_workflow: str = "manual",
    guard_operation: str = "删除",
) -> dict[str, Any]:
    guard_result = await run_story_knowledge_guard(
        session,
        project_id=project_id,
        user_id=user_id,
        section_key=section_key,
        operation=guard_operation,
        candidate_item={},
        entity_id=entity_id,
    )
    _raise_when_story_knowledge_guard_blocks(guard_result, action_label=guard_operation)

    structured_spec = _get_structured_section_spec(section_key)
    if structured_spec is not None:
        await delete_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type=structured_spec.entity_type,
            entity_id=_parse_entity_uuid(entity_id, action_label="删除"),
            source_workflow=source_workflow,
        )
        return _build_story_knowledge_mutation_response(
            guard_result,
            action_completed_message="这条设定已删除，并通过守护校验。"
            if not guard_result["warning_count"]
            else (
                f"这条设定已删除，但还带出 {guard_result['warning_count']} 条后续影响提醒，"
                "最好尽快补一下。"
            ),
        )

    if section_key not in STORY_BIBLE_SECTION_SCHEMAS:
        raise AppError(
            code="story_engine.knowledge_section_unsupported",
            message="当前设定分类暂时还没有接入统一入口。",
            status_code=404,
        )

    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
        permission=PROJECT_PERMISSION_EDIT,
    )
    await delete_story_bible_branch_item(
        session,
        project,
        StoryBibleBranchItemDelete(section_key=section_key, entity_key=entity_id),
        actor_user_id=user_id,
        branch_id=_require_branch_id(branch_id, action_label="删除"),
    )
    return _build_story_knowledge_mutation_response(
        guard_result,
        action_completed_message="这条主设定已删除，并通过守护校验。"
        if not guard_result["warning_count"]
        else (
            f"这条主设定已删除，但还带出 {guard_result['warning_count']} 条后续影响提醒，"
            "最好尽快补一下。"
        ),
    )


def _raise_when_story_knowledge_guard_blocks(
    guard_result: dict[str, Any],
    *,
    action_label: str,
) -> None:
    if not guard_result.get("blocked"):
        return
    raise AppError(
        code="story_engine.knowledge_guard_blocked",
        message=str(guard_result.get("message") or f"这条设定暂时不能{action_label}。"),
        status_code=409,
        metadata={
            "alerts": guard_result.get("alerts") or [],
            "blocking_issue_count": guard_result.get("blocking_issue_count") or 0,
            "warning_count": guard_result.get("warning_count") or 0,
        },
    )


def _build_story_knowledge_mutation_response(
    guard_result: dict[str, Any],
    *,
    action_completed_message: str,
) -> dict[str, Any]:
    return {
        "passed": bool(guard_result.get("passed", True)),
        "blocked": bool(guard_result.get("blocked", False)),
        "message": action_completed_message,
        "alerts": list(guard_result.get("alerts") or []),
        "blocking_issue_count": int(guard_result.get("blocking_issue_count") or 0),
        "warning_count": int(guard_result.get("warning_count") or 0),
    }
