from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from evaluation.evaluator import evaluate_chapter_text
from memory.story_bible import load_story_bible_context
from models.chapter import Chapter
from models.evaluation import Evaluation
from schemas.evaluation import EvaluationIssue, EvaluationReport
from services.chapter_service import get_owned_chapter
from services.project_service import PROJECT_PERMISSION_EVALUATE


async def evaluate_chapter(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> EvaluationReport:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EVALUATE,
    )
    return await evaluate_existing_chapter(session, chapter, user_id)


async def evaluate_existing_chapter(
    session: AsyncSession,
    chapter: Chapter,
    user_id: UUID,
) -> EvaluationReport:
    context = await load_story_bible_context(session, chapter.project_id, user_id)
    metrics, issues, summary = evaluate_chapter_text(chapter.content, context)
    overall_score = metrics.calculate_overall_score()

    evaluation = Evaluation(
        chapter_id=chapter.id,
        metrics=metrics.model_dump(),
        overall_score=overall_score,
        ai_taste_score=metrics.ai_taste_score,
    )
    session.add(evaluation)
    chapter.quality_metrics = {
        "overall_score": overall_score,
        "ai_taste_score": metrics.ai_taste_score,
        "summary": summary,
    }
    await session.commit()

    return EvaluationReport(
        chapter_id=chapter.id,
        overall_score=overall_score,
        ai_taste_score=metrics.ai_taste_score,
        metrics={key: float(value) for key, value in metrics.model_dump().items()},
        issues=[EvaluationIssue(**issue) for issue in issues],
        summary=summary,
        context_snapshot={
            "project_id": str(context.project_id),
            "title": context.title,
            "character_count": len(context.characters),
            "world_setting_count": len(context.world_settings),
            "chapter_count": len(context.chapter_summaries),
        },
    )
