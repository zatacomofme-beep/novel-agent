from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from api.v1.story_engine import (
    story_engine_chapter_checkpoint_create,
    story_engine_chapter_checkpoint_update,
    story_engine_chapter_comment_create,
    story_engine_chapter_comment_delete,
    story_engine_chapter_comment_update,
    story_engine_chapter_create,
    story_engine_chapter_detail,
    story_engine_chapter_export,
    story_engine_chapter_patch,
    story_engine_chapter_rewrite_selection,
    story_engine_chapter_review_create,
    story_engine_chapter_review_workspace,
    story_engine_chapter_rollback,
    story_engine_chapter_versions,
)
from models.user import User
from schemas.chapter import (
    ChapterCheckpointCreate,
    ChapterCheckpointRead,
    ChapterCheckpointUpdate,
    ChapterCreate,
    ChapterRead,
    ChapterReviewCommentCreate,
    ChapterReviewCommentRead,
    ChapterReviewCommentUpdate,
    ChapterReviewDecisionCreate,
    ChapterReviewDecisionRead,
    ChapterReviewWorkspaceRead,
    ChapterSelectionRewriteRequest,
    ChapterSelectionRewriteResponse,
    ChapterUpdate,
    ChapterVersionRead,
    RollbackResponse,
)
from services.chapter_service import (
    get_owned_chapter,
    list_project_chapters,
)
from services.export_service import ExportFormat
from services.legacy_generation_dispatch_service import (
    dispatch_legacy_generation_for_chapter,
)
from services.project_service import (
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
)
from tasks.schemas import TaskState


router = APIRouter()


async def _resolve_legacy_chapter_project_id(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    user_id: UUID,
) -> UUID:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_READ,
    )
    return chapter.project_id


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


@router.get(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_detail(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_detail(
        project_id=project_id,
        chapter_id=chapter_id,
        current_user=current_user,
        session=session,
    )


@router.patch(
    "/chapters/{chapter_id}",
    response_model=ChapterRead,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_patch(
    chapter_id: UUID,
    payload: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_patch(
        project_id=project_id,
        chapter_id=chapter_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.get(
    "/chapters/{chapter_id}/versions",
    response_model=list[ChapterVersionRead],
    deprecated=True,
    include_in_schema=False,
)
async def chapter_versions(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChapterVersionRead]:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_versions(
        project_id=project_id,
        chapter_id=chapter_id,
        current_user=current_user,
        session=session,
    )


@router.get(
    "/chapters/{chapter_id}/review-workspace",
    response_model=ChapterReviewWorkspaceRead,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_review_workspace(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewWorkspaceRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_review_workspace(
        project_id=project_id,
        chapter_id=chapter_id,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/checkpoints",
    response_model=ChapterCheckpointRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_checkpoint_create(
    chapter_id: UUID,
    payload: ChapterCheckpointCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_checkpoint_create(
        project_id=project_id,
        chapter_id=chapter_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.patch(
    "/chapters/{chapter_id}/checkpoints/{checkpoint_id}",
    response_model=ChapterCheckpointRead,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_checkpoint_patch(
    chapter_id: UUID,
    checkpoint_id: UUID,
    payload: ChapterCheckpointUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_checkpoint_update(
        project_id=project_id,
        chapter_id=chapter_id,
        checkpoint_id=checkpoint_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/comments",
    response_model=ChapterReviewCommentRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_comment_create(
    chapter_id: UUID,
    payload: ChapterReviewCommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_comment_create(
        project_id=project_id,
        chapter_id=chapter_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.patch(
    "/chapters/{chapter_id}/comments/{comment_id}",
    response_model=ChapterReviewCommentRead,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_comment_patch(
    chapter_id: UUID,
    comment_id: UUID,
    payload: ChapterReviewCommentUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_comment_update(
        project_id=project_id,
        chapter_id=chapter_id,
        comment_id=comment_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.delete(
    "/chapters/{chapter_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_comment_delete(
    chapter_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_comment_delete(
        project_id=project_id,
        chapter_id=chapter_id,
        comment_id=comment_id,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/reviews",
    response_model=ChapterReviewDecisionRead,
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_review_create(
    chapter_id: UUID,
    payload: ChapterReviewDecisionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewDecisionRead:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_review_create(
        project_id=project_id,
        chapter_id=chapter_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/rewrite-selection",
    response_model=ChapterSelectionRewriteResponse,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_rewrite_selection(
    chapter_id: UUID,
    payload: ChapterSelectionRewriteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterSelectionRewriteResponse:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_rewrite_selection(
        project_id=project_id,
        chapter_id=chapter_id,
        payload=payload,
        current_user=current_user,
        session=session,
    )


@router.post(
    "/chapters/{chapter_id}/rollback/{version_id}",
    response_model=RollbackResponse,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_rollback(
    chapter_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RollbackResponse:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_rollback(
        project_id=project_id,
        chapter_id=chapter_id,
        version_id=version_id,
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


@router.get(
    "/chapters/{chapter_id}/export",
    deprecated=True,
    include_in_schema=False,
)
async def chapter_export(
    chapter_id: UUID,
    export_format: ExportFormat = Query(default="md", alias="format"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    project_id = await _resolve_legacy_chapter_project_id(
        session,
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await story_engine_chapter_export(
        project_id=project_id,
        chapter_id=chapter_id,
        export_format=export_format,
        current_user=current_user,
        session=session,
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
    from agents.beta_reader import BetaReaderAgent
    from agents.base import AgentRunContext

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
