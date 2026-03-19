from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.dashboard import DashboardOverviewRead, DashboardProjectQualityTrendRead
from services.dashboard_service import get_dashboard_overview, get_project_quality_trend


router = APIRouter()


@router.get("/overview", response_model=DashboardOverviewRead)
async def dashboard_overview(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardOverviewRead:
    payload = await get_dashboard_overview(session, current_user.id)
    return DashboardOverviewRead(**payload)


@router.get("/projects/{project_id}/quality-trend", response_model=DashboardProjectQualityTrendRead)
async def dashboard_project_quality_trend(
    project_id: UUID,
    chapter_limit: int = Query(default=8, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> DashboardProjectQualityTrendRead:
    payload = await get_project_quality_trend(
        session,
        current_user.id,
        project_id,
        chapter_limit=chapter_limit,
    )
    return DashboardProjectQualityTrendRead(**payload)
