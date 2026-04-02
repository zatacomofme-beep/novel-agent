from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from models.open_thread import ThreadStatus
from services.foreshadowing_lifecycle_service import foreshadowing_lifecycle_service


router = APIRouter(prefix="/projects/{project_id}/open-threads", tags=["open-threads"])


class OpenThreadRead(BaseModel):
    id: str
    project_id: str
    planted_chapter: int
    entity_ref: str
    entity_type: str
    potential_tags: list[str]
    status: str
    payoff_chapter: Optional[int]
    payoff_priority: float
    resolution_summary: Optional[str]
    planted_content: Optional[str]
    planted_entity_id: Optional[str]
    last_tracked_chapter: Optional[int]
    version: int

    class Config:
        from_attributes = True


class OpenThreadStats(BaseModel):
    open: int
    tracking: int
    resolution_pending: int
    resolved: int
    abandoned: int
    total: int
    resolved_rate_pct: float


class OpenThreadHistoryRead(BaseModel):
    id: str
    thread_id: str
    chapter: int
    event_type: str
    old_status: Optional[str]
    new_status: Optional[str]
    delta_priority: Optional[float]
    note: Optional[str]

    class Config:
        from_attributes = True


class ThreadResolveRequest(BaseModel):
    thread_id: UUID
    summary: str


class ThreadAbandonRequest(BaseModel):
    thread_id: UUID
    reason: str


@router.get("", response_model=list[OpenThreadRead])
async def list_open_threads(
    project_id: UUID,
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[OpenThreadRead]:
    threads = await foreshadowing_lifecycle_service.list_project_threads(
        session, project_id, status=status_filter
    )
    return [
        OpenThreadRead(
            id=str(t.id),
            project_id=str(t.project_id),
            planted_chapter=t.planted_chapter,
            entity_ref=t.entity_ref,
            entity_type=t.entity_type,
            potential_tags=t.potential_tags or [],
            status=t.status,
            payoff_chapter=t.payoff_chapter,
            payoff_priority=t.payoff_priority,
            resolution_summary=t.resolution_summary,
            planted_content=t.planted_content,
            planted_entity_id=str(t.planted_entity_id) if t.planted_entity_id else None,
            last_tracked_chapter=t.last_tracked_chapter,
            version=t.version,
        )
        for t in threads
    ]


@router.get("/stats", response_model=OpenThreadStats)
async def get_open_thread_stats(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> OpenThreadStats:
    stats = await foreshadowing_lifecycle_service.get_thread_stats(session, project_id)
    return OpenThreadStats(**stats)


@router.get("/candidates", response_model=list[OpenThreadRead])
async def get_resolution_candidates(
    project_id: UUID,
    current_chapter: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[OpenThreadRead]:
    threads = await foreshadowing_lifecycle_service.get_resolution_candidates(
        session, project_id, current_chapter
    )
    return [
        OpenThreadRead(
            id=str(t.id),
            project_id=str(t.project_id),
            planted_chapter=t.planted_chapter,
            entity_ref=t.entity_ref,
            entity_type=t.entity_type,
            potential_tags=t.potential_tags or [],
            status=t.status,
            payoff_chapter=t.payoff_chapter,
            payoff_priority=t.payoff_priority,
            resolution_summary=t.resolution_summary,
            planted_content=t.planted_content,
            planted_entity_id=str(t.planted_entity_id) if t.planted_entity_id else None,
            last_tracked_chapter=t.last_tracked_chapter,
            version=t.version,
        )
        for t in threads
    ]


@router.post("/resolve")
async def resolve_thread(
    project_id: UUID,
    body: ThreadResolveRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await foreshadowing_lifecycle_service.resolve(
        session, body.thread_id, 0, body.summary
    )
    await session.commit()
    return {"success": True, "thread_id": str(body.thread_id)}


@router.post("/abandon")
async def abandon_thread(
    project_id: UUID,
    body: ThreadAbandonRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    await foreshadowing_lifecycle_service.abandon(
        session, body.thread_id, body.reason
    )
    await session.commit()
    return {"success": True, "thread_id": str(body.thread_id)}
