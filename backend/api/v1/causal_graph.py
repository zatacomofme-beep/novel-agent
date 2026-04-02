from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from services.neo4j_service import neo4j_service


router = APIRouter(prefix="/projects/{project_id}/causal-graph", tags=["causal-graph"])


class EventCreate(BaseModel):
    chapter: int
    name: str
    summary: str
    event_type: str = "generic"


class CausalLinkCreate(BaseModel):
    from_event_id: str
    to_event_id: str
    cause_type: str = "direct"
    confidence: float = 1.0


class CausalPathQuery(BaseModel):
    from_chapter: int
    to_chapter: int
    max_hops: int = Query(default=10, ge=1, le=20)


class CausalPathResult(BaseModel):
    nodes: list[dict]
    hops: int


@router.post("/events")
async def create_causal_event(
    project_id: UUID,
    body: EventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    result = await neo4j_service.create_event_node(
        project_id=project_id,
        chapter=body.chapter,
        name=body.name,
        summary=body.summary,
        event_type=body.event_type,
    )
    if result is None:
        return {"success": False, "message": "Neo4j unavailable or error"}
    return {"success": True, "event": result}


@router.post("/causal-links")
async def create_causal_link(
    project_id: UUID,
    body: CausalLinkCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    success = await neo4j_service.create_causal_link(
        from_event_id=body.from_event_id,
        to_event_id=body.to_event_id,
        cause_type=body.cause_type,
        confidence=body.confidence,
    )
    return {"success": success}


@router.post("/foreshadow-link")
async def link_foreshadow_to_payoff(
    project_id: UUID,
    foreshadow_event_id: str,
    payoff_event_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    success = await neo4j_service.link_foreshadow_to_payoff(
        foreshadow_event_id=foreshadow_event_id,
        payoff_event_id=payoff_event_id,
    )
    return {"success": success}


@router.get("/paths", response_model=list[dict])
async def query_causal_paths(
    project_id: UUID,
    from_chapter: int = Query(...),
    to_chapter: int = Query(...),
    max_hops: int = Query(default=10, ge=1, le=20),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    paths = await neo4j_service.query_causal_paths(
        project_id=project_id,
        from_chapter=from_chapter,
        to_chapter=to_chapter,
        max_hops=max_hops,
    )
    return paths


@router.get("/character-influence", response_model=list[dict])
async def compute_character_influence(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    influence = await neo4j_service.compute_character_influence(project_id)
    return influence


@router.get("/story-structure", response_model=list[dict])
async def detect_story_structure(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict]:
    structures = await neo4j_service.detect_story_structure(project_id)
    return structures


@router.get("/status")
async def get_causal_graph_status(
    project_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    return {
        "neo4j_available": neo4j_service.is_available,
        "url": neo4j_service._url if hasattr(neo4j_service, "_url") else "bolt://localhost:7687",
    }
