from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from services.undo_redo_service import undo_redo_service


router = APIRouter(prefix="/chapters/{chapter_id}/history", tags=["chapter-history"])


class SnapshotResponse(BaseModel):
    id: str
    version_number: int
    content: str
    action_type: str
    trigger_agent: str | None
    revision_round: int | None
    content_length: int
    created_at: str


class UndoRedoStatusResponse(BaseModel):
    can_undo: bool
    can_redo: bool
    current_version: int
    total_versions: int


@router.get("/snapshots", response_model=list[SnapshotResponse])
async def list_snapshots(
    chapter_id: UUID,
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[SnapshotResponse]:
    snapshots = await undo_redo_service.get_snapshot_history(
        session, chapter_id, limit=limit
    )
    return [
        SnapshotResponse(
            id=str(s.id),
            version_number=s.version_number,
            content=s.content,
            action_type=s.action_type,
            trigger_agent=s.trigger_agent,
            revision_round=s.revision_round,
            content_length=s.content_length,
            created_at=s.created_at.isoformat(),
        )
        for s in snapshots
    ]


@router.get("/status", response_model=UndoRedoStatusResponse)
async def get_undo_redo_status(
    chapter_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> UndoRedoStatusResponse:
    can_undo = await undo_redo_service.can_undo(session, chapter_id)
    can_redo = await undo_redo_service.can_redo(session, chapter_id)

    from sqlalchemy import select
    from models.chapter_snapshot import ChapterUndoStack

    result = await session.execute(
        select(ChapterUndoStack).where(ChapterUndoStack.chapter_id == chapter_id)
    )
    stack = result.scalar_one_or_none()

    return UndoRedoStatusResponse(
        can_undo=can_undo,
        can_redo=can_redo,
        current_version=(stack.current_pointer if stack else -1),
        total_versions=(stack.total_snapshots if stack else 0),
    )


@router.post("/undo")
async def undo_version(
    chapter_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    snapshot = await undo_redo_service.undo(session, chapter_id)
    if snapshot is None:
        return {"success": False, "message": "Nothing to undo"}
    return {
        "success": True,
        "snapshot": SnapshotResponse(
            id=str(snapshot.id),
            version_number=snapshot.version_number,
            content=snapshot.content,
            action_type=snapshot.action_type,
            trigger_agent=snapshot.trigger_agent,
            revision_round=snapshot.revision_round,
            content_length=snapshot.content_length,
            created_at=snapshot.created_at.isoformat(),
        ),
    }


@router.post("/redo")
async def redo_version(
    chapter_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    snapshot = await undo_redo_service.redo(session, chapter_id)
    if snapshot is None:
        return {"success": False, "message": "Nothing to redo"}
    return {
        "success": True,
        "snapshot": SnapshotResponse(
            id=str(snapshot.id),
            version_number=snapshot.version_number,
            content=snapshot.content,
            action_type=snapshot.action_type,
            trigger_agent=snapshot.trigger_agent,
            revision_round=snapshot.revision_round,
            content_length=snapshot.content_length,
            created_at=snapshot.created_at.isoformat(),
        ),
    }
