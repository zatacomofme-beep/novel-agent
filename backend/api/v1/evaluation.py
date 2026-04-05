from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from core.errors import AppError
from core.logging import get_logger
from models.user import User
from schemas.evaluation import EvaluationReport
from services.chapter_service import get_owned_chapter
from services.evaluation_service import evaluate_chapter
from services.project_service import get_owned_project, PROJECT_PERMISSION_READ


router = APIRouter()
logger = get_logger(__name__)


def _emit_legacy_chapter_evaluate_endpoint_used(
    *,
    chapter_id: UUID,
    user_id: UUID,
) -> None:
    logger.warning(
        "legacy_chapter_endpoint_used",
        extra={
            "endpoint_name": "chapter_evaluate",
            "chapter_id": str(chapter_id),
            "user_id": str(user_id),
        },
    )


@router.post(
    "/projects/{project_id}/story-engine/chapters/{chapter_id}/evaluate",
    response_model=EvaluationReport,
)
async def story_engine_chapter_evaluate(
    project_id: UUID,
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationReport:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    if chapter.project_id != project_id:
        raise AppError(
            code="story_engine.chapter_project_mismatch",
            message="Chapter does not belong to project.",
            status_code=404,
        )
    return await evaluate_chapter(session, chapter_id, current_user.id)


@router.post(
    "/chapters/{chapter_id}/evaluate",
    response_model=EvaluationReport,
    deprecated=True,
    include_in_schema=False,
)
async def chapter_evaluate(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationReport:
    _emit_legacy_chapter_evaluate_endpoint_used(
        chapter_id=chapter_id,
        user_id=current_user.id,
    )
    return await evaluate_chapter(session, chapter_id, current_user.id)
