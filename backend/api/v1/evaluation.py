from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from models.user import User
from schemas.evaluation import EvaluationReport
from services.evaluation_service import evaluate_chapter


router = APIRouter()


@router.post("/chapters/{chapter_id}/evaluate", response_model=EvaluationReport)
async def chapter_evaluate(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationReport:
    return await evaluate_chapter(session, chapter_id, current_user.id)
