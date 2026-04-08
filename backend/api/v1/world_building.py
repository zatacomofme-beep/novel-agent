from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.world_building import (
    WorldBuildingSessionCreate,
    WorldBuildingSessionRead,
    WorldBuildingStartResponse,
    WorldBuildingStepSubmit,
    WorldBuildingStepResponse,
)
from services.project_service import get_owned_project
from services.world_building_service import WorldBuildingService

router = APIRouter(tags=["world-building"])

_world_building_service = WorldBuildingService()


@router.post(
    "/projects/{project_id}/world-building/sessions",
    response_model=WorldBuildingStartResponse,
)
async def start_world_building_session(
    project_id: UUID,
    body: WorldBuildingSessionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> WorldBuildingStartResponse:
    project = await get_owned_project(session, project_id, current_user.id)
    return await _world_building_service.start_session(
        session, project, current_user.id, body.initial_idea or ""
    )


@router.get(
    "/projects/{project_id}/world-building/sessions",
    response_model=WorldBuildingSessionRead | None,
)
async def get_active_world_building_session(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
):
    await get_owned_project(session, project_id, current_user.id)
    from models.world_building_session import WorldBuildingSession
    from sqlalchemy import select

    result = await session.execute(
        select(WorldBuildingSession).where(
            WorldBuildingSession.project_id == project_id,
            WorldBuildingSession.user_id == current_user.id,
            WorldBuildingSession.status.in_(["in_progress", "completed"]),
        )
        .order_by(WorldBuildingSession.created_at.desc())
        .limit(1)
    )
    wb_session = result.scalar_one_or_none()
    if not wb_session:
        return None
    return WorldBuildingSessionRead.model_validate(wb_session)


@router.post(
    "/projects/{project_id}/world-building/sessions/{session_id}/steps",
    response_model=WorldBuildingStepResponse,
)
async def process_world_building_step(
    project_id: UUID,
    session_id: UUID,
    body: WorldBuildingStepSubmit,
    current_user: User = Depends(get_current_user),
    db_session: AsyncSession = Depends(get_db_session),
) -> WorldBuildingStepResponse:
    await get_owned_project(db_session, project_id, current_user.id)
    return await _world_building_service.process_step(
        db_session, session_id, current_user.id, body.user_input, body.skip_to_next
    )
