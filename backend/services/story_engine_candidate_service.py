from __future__ import annotations

import re
from typing import Any
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.errors import AppError
from models.story_engine import StoryCharacter, StoryItem
from schemas.project import StoryBibleBranchItemUpsert
from schemas.story_engine import StoryCharacterCreate, StoryItemCreate
from services.story_engine_kb_service import create_entity, get_story_engine_project
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    get_owned_project,
    upsert_story_bible_branch_item,
)
from services.task_service import get_task_run_by_task_id
from tasks.state_store import task_state_store


SUPPORTED_ACCEPT_GENERATION_TYPES = frozenset(
    {
        "characters",
        "supporting",
        "items",
        "locations",
        "factions",
        "plot_threads",
    }
)


async def accept_generated_candidate(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    task_id: str,
    candidate_index: int,
    branch_id: Optional[UUID] = None,
) -> dict[str, Any]:
    task_run = await get_task_run_by_task_id(session, task_id)
    if task_run is None:
        raise AppError(
            code="story_engine.generation_task_not_found",
            message="这轮补全任务不存在。",
            status_code=404,
        )
    if getattr(task_run, "project_id", None) != project_id:
        raise AppError(
            code="story_engine.generation_task_project_mismatch",
            message="这轮补全任务不属于当前项目。",
            status_code=404,
        )

    task_state = task_state_store.get(task_id)
    task_result = dict(task_state.result or {}) if task_state and task_state.result else dict(task_run.result or {})
    generation_type = str(task_result.get("generation_type") or "").strip()
    if generation_type not in SUPPORTED_ACCEPT_GENERATION_TYPES:
        raise AppError(
            code="story_engine.generation_type_accept_unsupported",
            message="这类候选暂时只提供灵感预览，还不能直接采纳进当前设定面板。",
            status_code=400,
        )

    result_key = "characters" if generation_type in {"characters", "supporting"} else generation_type
    raw_candidates = task_result.get(result_key)
    if not isinstance(raw_candidates, list):
        raise AppError(
            code="story_engine.generation_candidates_missing",
            message="这轮补全结果里没有可采纳的候选。",
            status_code=409,
        )
    if candidate_index < 0 or candidate_index >= len(raw_candidates):
        raise AppError(
            code="story_engine.generation_candidate_not_found",
            message="没有找到对应的候选条目。",
            status_code=404,
        )

    candidate = raw_candidates[candidate_index]
    if not isinstance(candidate, dict):
        raise AppError(
            code="story_engine.generation_candidate_invalid",
            message="这条候选格式不完整，暂时不能采纳。",
            status_code=409,
        )

    if generation_type in {"characters", "supporting", "items"}:
        await get_story_engine_project(
            session,
            project_id,
            user_id,
            permission=PROJECT_PERMISSION_EDIT,
        )
        entity_type = "characters" if generation_type in {"characters", "supporting"} else "items"
        payload = await _build_accept_payload(
            session,
            project_id=project_id,
            entity_type=entity_type,
            candidate=candidate,
        )
        entity = await create_entity(
            session,
            project_id=project_id,
            user_id=user_id,
            entity_type=entity_type,
            payload=payload,
            source_workflow="entity_generation_accept",
        )
        accepted_entity_id = getattr(entity, "character_id", None) or getattr(entity, "item_id", None)
        accepted_entity_label = getattr(entity, "name", None) or "已采纳条目"
        accepted_entity_key = str(accepted_entity_id) if accepted_entity_id is not None else None
        resolved_branch_id = None
    else:
        if branch_id is None:
            raise AppError(
                code="story_engine.branch_id_required",
                message="当前项目还没有主线分支，暂时不能把这类候选收进主设定。",
                status_code=400,
            )
        project = await get_owned_project(
            session,
            project_id,
            user_id,
            with_relations=True,
            permission=PROJECT_PERMISSION_EDIT,
        )
        section_key, payload, accepted_entity_label, accepted_entity_key = _build_story_bible_accept_payload(
            generation_type=generation_type,
            candidate=candidate,
        )
        await upsert_story_bible_branch_item(
            session,
            project,
            StoryBibleBranchItemUpsert(
                section_key=section_key,
                item=payload,
            ),
            actor_user_id=user_id,
            branch_id=branch_id,
        )
        entity_type = generation_type
        accepted_entity_id = None
        resolved_branch_id = branch_id

    return {
        "accepted_entity_type": entity_type,
        "accepted_entity_id": accepted_entity_id,
        "accepted_entity_key": accepted_entity_key,
        "accepted_entity_label": accepted_entity_label,
        "source_task_id": task_id,
        "candidate_index": candidate_index,
        "branch_id": resolved_branch_id,
        "message": f"{accepted_entity_label} 已收入设定库。",
    }


async def _build_accept_payload(
    session: AsyncSession,
    *,
    project_id: UUID,
    entity_type: str,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    if entity_type == "characters":
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise AppError(
                code="story_engine.accept_character_name_required",
                message="人物候选缺少名字，不能采纳。",
                status_code=422,
            )
        await _ensure_name_not_exists(
            session,
            model=StoryCharacter,
            project_id=project_id,
            field_name="name",
            value=name,
            duplicate_message="同名人物已经在设定库里了，不需要重复采纳。",
        )
        payload = StoryCharacterCreate(
            name=name,
            appearance=_optional_text(candidate.get("appearance")),
            personality=_optional_text(candidate.get("personality")),
            micro_habits=[],
            abilities=_compact_dict(
                {
                    "seed_role": _optional_text(candidate.get("role")),
                    "age": candidate.get("age"),
                    "gender": _optional_text(candidate.get("gender")),
                    "background": _optional_text(candidate.get("background")),
                    "motivation": _optional_text(candidate.get("motivation")),
                    "conflict": _optional_text(candidate.get("conflict")),
                    "suggested_relationships": _string_list(candidate.get("relationships")),
                }
            ),
            relationships=[],
            status="active",
            arc_stage="initial",
            arc_boundaries=[],
        )
        return payload.model_dump(mode="json")

    if entity_type == "items":
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise AppError(
                code="story_engine.accept_item_name_required",
                message="物品候选缺少名字，不能采纳。",
                status_code=422,
            )
        await _ensure_name_not_exists(
            session,
            model=StoryItem,
            project_id=project_id,
            field_name="name",
            value=name,
            duplicate_message="同名物品已经在设定库里了，不需要重复采纳。",
        )
        features = _optional_text(candidate.get("description"))
        type_label = _optional_text(candidate.get("type"))
        rarity_label = _optional_text(candidate.get("rarity"))
        feature_parts = [part for part in [features, f"类型：{type_label}" if type_label else None, f"稀有度：{rarity_label}" if rarity_label else None] if part]
        payload = StoryItemCreate(
            name=name,
            features="；".join(feature_parts) if feature_parts else None,
            owner=_optional_text(candidate.get("owner")),
            location=None,
            special_rules=_string_list(candidate.get("effects")),
        )
        return payload.model_dump(mode="json")

    raise AppError(
        code="story_engine.accept_entity_type_unsupported",
        message="当前候选类型还不能直接采纳。",
        status_code=400,
    )


def _build_story_bible_accept_payload(
    *,
    generation_type: str,
    candidate: dict[str, Any],
) -> tuple[str, dict[str, Any], str, str]:
    if generation_type == "locations":
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise AppError(
                code="story_engine.accept_location_name_required",
                message="地点候选缺少名字，不能采纳。",
                status_code=422,
            )
        payload = {
            "name": name,
            "data": _compact_dict(
                {
                    "type": _optional_text(candidate.get("type")),
                    "climate": _optional_text(candidate.get("climate")),
                    "population": _optional_text(candidate.get("population")),
                    "description": _optional_text(candidate.get("description")),
                    "features": _string_list(candidate.get("features")),
                    "notable_residents": _string_list(candidate.get("notable_residents")),
                    "history": _optional_text(candidate.get("history")),
                }
            ),
            "version": 1,
        }
        return "locations", payload, name, f"name:{name}"

    if generation_type == "factions":
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise AppError(
                code="story_engine.accept_faction_name_required",
                message="势力候选缺少名字，不能采纳。",
                status_code=422,
            )
        key = _stable_story_bible_key("faction", name)
        payload = {
            "key": key,
            "name": name,
            "type": _optional_text(candidate.get("type")),
            "scale": _optional_text(candidate.get("scale")),
            "description": _optional_text(candidate.get("description")),
            "goals": _optional_text(candidate.get("goals")),
            "leader": _optional_text(candidate.get("leader")),
            "members": _string_list(candidate.get("members")),
            "territory": _optional_text(candidate.get("territory")),
            "resources": _string_list(candidate.get("resources")),
            "ideology": _optional_text(candidate.get("ideology")),
            "version": 1,
        }
        return "factions", payload, name, f"key:{key}"

    if generation_type == "plot_threads":
        title = str(candidate.get("title") or "").strip()
        if not title:
            raise AppError(
                code="story_engine.accept_plot_thread_title_required",
                message="剧情线候选缺少标题，不能采纳。",
                status_code=422,
            )
        payload = {
            "title": title,
            "status": _optional_text(candidate.get("status")) or "planned",
            "importance": 1,
            "data": _compact_dict(
                {
                    "type": _optional_text(candidate.get("type")),
                    "description": _optional_text(candidate.get("description")),
                    "main_characters": _string_list(candidate.get("main_characters")),
                    "locations": _string_list(candidate.get("locations")),
                    "stages": _string_list(candidate.get("stages")),
                    "tension_arc": _optional_text(candidate.get("tension_arc")),
                    "resolution": _optional_text(candidate.get("resolution")),
                }
            ),
        }
        return "plot_threads", payload, title, f"title:{title}"

    raise AppError(
        code="story_engine.accept_story_bible_type_unsupported",
        message="当前候选类型还不能写入主设定。",
        status_code=400,
    )


async def _ensure_name_not_exists(
    session: AsyncSession,
    *,
    model: Any,
    project_id: UUID,
    field_name: str,
    value: str,
    duplicate_message: str,
) -> None:
    statement = select(model).where(
        model.project_id == project_id,
        getattr(model, field_name) == value,
    )
    result = await session.execute(statement)
    if result.scalar_one_or_none() is not None:
        raise AppError(
            code="story_engine.accept_duplicate_entity",
            message=duplicate_message,
            status_code=409,
        )


def _optional_text(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _compact_dict(value: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item
        for key, item in value.items()
        if item not in (None, "", [], {})
    }


def _stable_story_bible_key(prefix: str, value: str) -> str:
    normalized = re.sub(r"\s+", "-", value.strip().lower())
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff_-]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    if not normalized:
        normalized = "entry"
    return f"{prefix}:{normalized}"[:100]
