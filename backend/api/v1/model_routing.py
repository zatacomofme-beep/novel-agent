from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db_session, get_model_routing_admin_user
from models.user import User
from schemas.story_engine import (
    StoryEngineModelRoutingProjectSummaryRead,
    StoryEngineModelRoutingRead,
    StoryEngineModelRoutingUpdateRequest,
    StoryEnginePresetCatalogRead,
)
from services.story_engine_settings_service import (
    get_story_engine_model_routing_for_admin,
    list_story_engine_model_preset_catalog,
    list_story_engine_model_routing_projects,
    update_story_engine_model_routing_for_admin,
)


router = APIRouter(prefix="/admin/model-routing")


@router.get("/preset-catalog", response_model=StoryEnginePresetCatalogRead)
async def admin_model_routing_preset_catalog(
    current_user: User = Depends(get_model_routing_admin_user),
) -> StoryEnginePresetCatalogRead:
    del current_user
    payload = list_story_engine_model_preset_catalog()
    return StoryEnginePresetCatalogRead.model_validate(payload)


@router.get(
    "/projects",
    response_model=list[StoryEngineModelRoutingProjectSummaryRead],
)
async def admin_model_routing_project_list(
    query: Optional[str] = Query(default=None),
    limit: int = Query(default=40, ge=1, le=200),
    current_user: User = Depends(get_model_routing_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[StoryEngineModelRoutingProjectSummaryRead]:
    del current_user
    payload = await list_story_engine_model_routing_projects(
        session,
        query=query,
        limit=limit,
    )
    return [
        StoryEngineModelRoutingProjectSummaryRead.model_validate(item)
        for item in payload
    ]


@router.get(
    "/projects/{project_id}",
    response_model=StoryEngineModelRoutingRead,
)
async def admin_model_routing_project_detail(
    project_id: UUID,
    current_user: User = Depends(get_model_routing_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryEngineModelRoutingRead:
    del current_user
    payload = await get_story_engine_model_routing_for_admin(
        session,
        project_id=project_id,
    )
    return StoryEngineModelRoutingRead.model_validate(payload)


@router.put(
    "/projects/{project_id}",
    response_model=StoryEngineModelRoutingRead,
)
async def admin_model_routing_project_update(
    project_id: UUID,
    payload: StoryEngineModelRoutingUpdateRequest,
    current_user: User = Depends(get_model_routing_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> StoryEngineModelRoutingRead:
    del current_user
    result = await update_story_engine_model_routing_for_admin(
        session,
        project_id=project_id,
        active_preset_key=payload.active_preset_key,
        manual_overrides={
            role_key: route.model_dump(mode="json")
            for role_key, route in payload.manual_overrides.items()
        },
    )
    return StoryEngineModelRoutingRead.model_validate(result)
