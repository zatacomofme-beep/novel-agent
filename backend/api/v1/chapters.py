from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from api.v1.story_engine import story_engine_chapter_create
from core.logging import get_logger
from models.user import User
from schemas.chapter import ChapterCreate, ChapterRead
from services.chapter_service import get_owned_chapter, list_project_chapters
from services.legacy_generation_dispatch_service import (
    dispatch_legacy_generation_for_chapter,
)
from services.project_service import PROJECT_PERMISSION_EDIT, PROJECT_PERMISSION_READ
from tasks.schemas import TaskState


router = APIRouter()
logger = get_logger(__name__)


def _emit_legacy_chapter_endpoint_used(
    endpoint_name: str,
    *,
    chapter_id: UUID,
    user_id: UUID,
) -> None:
    logger.warning(
        "legacy_chapter_endpoint_used",
        extra={
            "endpoint_name": endpoint_name,
            "chapter_id": str(chapter_id),
            "user_id": str(user_id),
        },
    )


@router.get("/projects/{project_id}/chapters", response_model=list[ChapterRead])
async def chapter_list(
    project_id: UUID,
    volume_id: Optional[UUID] = Query(default=None),
    branch_id: Optional[UUID] = Query(default=None),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChapterRead]:
    chapters = await list_project_chapters(
        session,
        project_id,
        current_user.id,
        volume_id=volume_id,
        branch_id=branch_id,
    )
    return [ChapterRead.model_validate(chapter) for chapter in chapters]


@router.post(
    "/projects/{project_id}/chapters",
    response_model=ChapterRead,
    status_code=status.HTTP_201_CREATED,
)
async def chapter_create(
    project_id: UUID,
    payload: ChapterCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    return await story_engine_chapter_create(
        project_id=project_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/generate",
    response_model=TaskState,
    deprecated=True,
    include_in_schema=False,
    summary="Legacy chapter generation entrypoint",
)
async def chapter_generate(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    """Legacy generation pipeline kept for compatibility.

    Current product mainline uses Story Engine workflows from `story-room`.
    """
    _emit_legacy_chapter_endpoint_used(
        "chapter_generate",
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    return await dispatch_legacy_generation_for_chapter(
        session,
        chapter=chapter,
        user_id=current_user.id,
    )


@router.post(
    "/chapters/{chapter_id}/beta-reader",
    deprecated=True,
    include_in_schema=False,
    summary="Legacy beta reader entrypoint",
)
async def get_beta_reader_feedback(
    chapter_id: UUID,
    body: dict,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Legacy sidecar analysis kept for compatibility."""
    from agents.base import AgentRunContext
    from agents.beta_reader import BetaReaderAgent

    _emit_legacy_chapter_endpoint_used(
        "chapter_beta_reader",
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )

    beta_reader = BetaReaderAgent()
    context = AgentRunContext(
        chapter_id=str(chapter_id),
        project_id=str(chapter.project_id),
        task_id=f"beta-{chapter_id}",
        payload={},
    )

    result = await beta_reader.run(
        context,
        {
            "content": body.get("content", ""),
            "genre": body.get("genre", "fantasy"),
            "target_audience": body.get("target_audience", "adult"),
        },
    )

    if not result.success:
        return {"success": False, "error": result.error}
    return {"success": True, "beta_feedback": result.data}
