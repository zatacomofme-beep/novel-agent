from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
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
from services.rewrite_service import rewrite_chapter_selection
from services.review_service import (
    create_chapter_checkpoint,
    create_chapter_comment,
    create_chapter_review_decision,
    delete_chapter_comment,
    get_chapter_review_workspace,
    update_chapter_checkpoint,
    update_chapter_comment,
)
from services.chapter_service import (
    create_chapter,
    get_owned_chapter,
    list_project_chapters,
    list_versions,
    rollback_to_version,
    update_chapter,
)
from services.export_service import (
    ExportFormat,
    build_chapter_export_filename,
    build_export_response,
    render_chapter_export,
)
from services.generation_service import build_generation_payload
from services.project_service import (
    get_owned_project,
    PROJECT_PERMISSION_EDIT,
    PROJECT_PERMISSION_READ,
)
from tasks.chapter_generation import dispatch_generation_task, enqueue_chapter_generation_task
from tasks.schemas import TaskState


router = APIRouter()


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
    chapter = await create_chapter(session, project_id, current_user.id, payload)
    return ChapterRead.model_validate(chapter)


@router.get("/chapters/{chapter_id}", response_model=ChapterRead)
async def chapter_detail(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return ChapterRead.model_validate(chapter)


@router.patch("/chapters/{chapter_id}", response_model=ChapterRead)
async def chapter_patch(
    chapter_id: UUID,
    payload: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterRead:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    updated = await update_chapter(
        session,
        chapter,
        payload,
        preference_learning_user_id=current_user.id,
        preference_learning_source="manual_update",
    )
    return ChapterRead.model_validate(updated)


@router.get("/chapters/{chapter_id}/versions", response_model=list[ChapterVersionRead])
async def chapter_versions(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[ChapterVersionRead]:
    versions = await list_versions(session, chapter_id, current_user.id)
    return [ChapterVersionRead.model_validate(version) for version in versions]


@router.get(
    "/chapters/{chapter_id}/review-workspace",
    response_model=ChapterReviewWorkspaceRead,
)
async def chapter_review_workspace(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewWorkspaceRead:
    return await get_chapter_review_workspace(session, chapter_id, current_user.id)


@router.post(
    "/chapters/{chapter_id}/checkpoints",
    response_model=ChapterCheckpointRead,
    status_code=status.HTTP_201_CREATED,
)
async def chapter_checkpoint_create(
    chapter_id: UUID,
    payload: ChapterCheckpointCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    return await create_chapter_checkpoint(session, chapter_id, current_user.id, payload)


@router.patch(
    "/chapters/{chapter_id}/checkpoints/{checkpoint_id}",
    response_model=ChapterCheckpointRead,
)
async def chapter_checkpoint_patch(
    chapter_id: UUID,
    checkpoint_id: UUID,
    payload: ChapterCheckpointUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterCheckpointRead:
    return await update_chapter_checkpoint(
        session,
        chapter_id,
        checkpoint_id,
        current_user.id,
        payload,
    )


@router.post(
    "/chapters/{chapter_id}/comments",
    response_model=ChapterReviewCommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def chapter_comment_create(
    chapter_id: UUID,
    payload: ChapterReviewCommentCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    return await create_chapter_comment(session, chapter_id, current_user.id, payload)


@router.patch(
    "/chapters/{chapter_id}/comments/{comment_id}",
    response_model=ChapterReviewCommentRead,
)
async def chapter_comment_patch(
    chapter_id: UUID,
    comment_id: UUID,
    payload: ChapterReviewCommentUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewCommentRead:
    return await update_chapter_comment(
        session,
        chapter_id,
        comment_id,
        current_user.id,
        payload,
    )


@router.delete(
    "/chapters/{chapter_id}/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def chapter_comment_delete(
    chapter_id: UUID,
    comment_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    await delete_chapter_comment(session, chapter_id, comment_id, current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/chapters/{chapter_id}/reviews",
    response_model=ChapterReviewDecisionRead,
    status_code=status.HTTP_201_CREATED,
)
async def chapter_review_create(
    chapter_id: UUID,
    payload: ChapterReviewDecisionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterReviewDecisionRead:
    return await create_chapter_review_decision(
        session,
        chapter_id,
        current_user.id,
        payload,
    )


@router.post(
    "/chapters/{chapter_id}/rewrite-selection",
    response_model=ChapterSelectionRewriteResponse,
)
async def chapter_rewrite_selection(
    chapter_id: UUID,
    payload: ChapterSelectionRewriteRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ChapterSelectionRewriteResponse:
    return await rewrite_chapter_selection(
        session,
        chapter_id,
        current_user.id,
        payload,
    )


@router.post(
    "/chapters/{chapter_id}/rollback/{version_id}",
    response_model=RollbackResponse,
)
async def chapter_rollback(
    chapter_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> RollbackResponse:
    chapter, restored_version = await rollback_to_version(
        session,
        chapter_id,
        version_id,
        current_user.id,
    )
    return RollbackResponse(
        chapter=ChapterRead.model_validate(chapter),
        restored_version=ChapterVersionRead.model_validate(restored_version),
    )


@router.post("/chapters/{chapter_id}/generate", response_model=TaskState)
async def chapter_generate(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    payload = await build_generation_payload(session, chapter.id, current_user.id)
    task_state = await enqueue_chapter_generation_task(
        str(chapter.id),
        str(current_user.id),
        str(chapter.project_id),
        payload,
    )
    task_state = await dispatch_generation_task(
        task_id=task_state.task_id,
        chapter_id=str(chapter.id),
        project_id=str(chapter.project_id),
        user_id=str(current_user.id),
    )
    return task_state


@router.get("/chapters/{chapter_id}/export")
async def chapter_export(
    chapter_id: UUID,
    export_format: ExportFormat = Query(default="md", alias="format"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    project = await get_owned_project(
        session,
        chapter.project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    return build_export_response(
        content=render_chapter_export(
            project_title=project.title,
            chapter=chapter,
            export_format=export_format,
        ),
        filename=build_chapter_export_filename(project.title, chapter, export_format),
    )
