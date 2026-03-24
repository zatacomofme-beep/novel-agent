from __future__ import annotations

from collections import Counter
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.project import Project
from models.task_run import TaskRun
from schemas.quality import ChapterQualityMetricsSnapshot
from services.preference_service import (
    get_preference_learning_snapshot,
    get_or_create_user_preference,
    to_user_preference_read,
)
from services.project_service import get_owned_project, list_project_accesses


ACTIVE_TASK_STATUSES = ("queued", "running")
QUALITY_TREND_PROJECT_LIMIT = 4
QUALITY_TREND_CHAPTER_LIMIT = 8


async def get_dashboard_overview(
    session: AsyncSession,
    user_id: UUID,
) -> dict[str, Any]:
    project_accesses = await list_project_accesses(session, user_id)
    project_map = {access.project.id: access for access in project_accesses}
    project_ids = list(project_map.keys())
    projects: list[Project] = []
    active_tasks: list[TaskRun] = []
    recent_tasks: list[TaskRun] = []
    if project_ids:
        projects_result = await session.execute(
            select(Project)
            .options(
                selectinload(Project.chapters),
                selectinload(Project.user),
                selectinload(Project.collaborators),
            )
            .where(Project.id.in_(project_ids))
            .order_by(Project.updated_at.desc())
        )
        projects = list(projects_result.scalars().all())
        for project in projects:
            access = project_map.get(project.id)
            if access is not None:
                setattr(project, "access_role", access.role)

        active_tasks_result = await session.execute(
            select(TaskRun)
            .where(
                TaskRun.status.in_(ACTIVE_TASK_STATUSES),
                TaskRun.project_id.in_(project_ids),
            )
            .order_by(TaskRun.updated_at.desc())
        )
        active_tasks = list(active_tasks_result.scalars().all())

        recent_tasks_result = await session.execute(
            select(TaskRun)
            .where(TaskRun.project_id.in_(project_ids))
            .order_by(TaskRun.updated_at.desc())
            .limit(6)
        )
        recent_tasks = list(recent_tasks_result.scalars().all())
    preference = await get_or_create_user_preference(session, user_id)
    learning_snapshot = await get_preference_learning_snapshot(session, user_id)

    return build_dashboard_overview_payload(
        projects=projects,
        active_tasks=active_tasks,
        recent_tasks=recent_tasks,
        preference_profile=preference,
        learning_snapshot=learning_snapshot,
    )


async def get_project_quality_trend(
    session: AsyncSession,
    user_id: UUID,
    project_id: UUID,
    *,
    chapter_limit: int = QUALITY_TREND_CHAPTER_LIMIT,
) -> dict[str, Any]:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=False,
    )
    access_role = str(getattr(project, "access_role", "owner"))
    result = await session.execute(
        select(Project)
        .options(
            selectinload(Project.chapters),
            selectinload(Project.user),
            selectinload(Project.collaborators),
        )
        .where(Project.id == project.id)
    )
    project = result.scalar_one()
    setattr(project, "access_role", access_role)
    return build_project_quality_trend_payload(
        project,
        chapter_limit=chapter_limit,
    )


def build_dashboard_overview_payload(
    *,
    projects: list[Any],
    active_tasks: list[Any],
    recent_tasks: list[Any],
    preference_profile: Any,
    learning_snapshot: Optional[Any] = None,
) -> dict[str, Any]:
    total_projects = len(projects)
    total_chapters = 0
    total_words = 0
    review_ready_chapters = 0
    final_chapters = 0
    chapters_by_status: Counter[str] = Counter()
    overall_scores: list[float] = []
    ai_taste_scores: list[float] = []
    active_tasks_by_project: Counter[str] = Counter()

    for task in active_tasks:
        project_id = getattr(task, "project_id", None)
        if project_id is not None:
            active_tasks_by_project[str(project_id)] += 1

    quality_trends_by_project = {
        str(getattr(project, "id")): build_project_quality_trend_payload(project)
        for project in projects
    }

    project_summaries = []
    for project in projects:
        chapters = list(getattr(project, "chapters", []) or [])
        total_chapters += len(chapters)

        project_words = 0
        project_scores: list[float] = []
        project_ai_scores: list[float] = []
        project_review_ready = 0
        project_final = 0
        project_risks = 0

        for chapter in chapters:
            status = str(getattr(chapter, "status", "draft"))
            chapters_by_status[status] += 1
            word_count = int(getattr(chapter, "word_count", 0) or 0)
            total_words += word_count
            project_words += word_count

            if status in {"review", "final"}:
                review_ready_chapters += 1
                project_review_ready += 1
            if status == "final":
                final_chapters += 1
                project_final += 1

            overall_score = _quality_metric(chapter, "overall_score")
            ai_taste_score = _quality_metric(chapter, "ai_taste_score")
            if overall_score is not None:
                overall_scores.append(overall_score)
                project_scores.append(overall_score)
            if ai_taste_score is not None:
                ai_taste_scores.append(ai_taste_score)
                project_ai_scores.append(ai_taste_score)
            if (
                (overall_score is not None and overall_score < 0.75)
                or (ai_taste_score is not None and ai_taste_score > 0.35)
            ):
                project_risks += 1

        trend_payload = quality_trends_by_project.get(str(getattr(project, "id")), {})
        project_summaries.append(
            {
                "project_id": getattr(project, "id"),
                "title": getattr(project, "title"),
                "genre": getattr(project, "genre", None),
                "status": getattr(project, "status", "draft"),
                "access_role": getattr(project, "access_role", "owner"),
                "owner_email": getattr(getattr(project, "user", None), "email", None),
                "collaborator_count": len(getattr(project, "collaborators", []) or []),
                "updated_at": getattr(project, "updated_at"),
                "chapter_count": len(chapters),
                "word_count": project_words,
                "review_ready_chapters": project_review_ready,
                "final_chapters": project_final,
                "risk_chapter_count": project_risks,
                "active_task_count": active_tasks_by_project.get(str(getattr(project, "id")), 0),
                "average_overall_score": _mean(project_scores),
                "average_ai_taste_score": _mean(project_ai_scores),
                "score_delta": trend_payload.get("score_delta"),
                "trend_direction": trend_payload.get("trend_direction", "insufficient_data"),
            }
        )

    return {
        "total_projects": total_projects,
        "total_chapters": total_chapters,
        "total_words": total_words,
        "active_task_count": len(active_tasks),
        "review_ready_chapters": review_ready_chapters,
        "final_chapters": final_chapters,
        "average_overall_score": _mean(overall_scores),
        "average_ai_taste_score": _mean(ai_taste_scores),
        "chapters_by_status": dict(chapters_by_status),
        "preference_profile": to_user_preference_read(
            preference_profile,
            learning_snapshot,
        ),
        "project_summaries": project_summaries,
        "project_quality_trends": [
            quality_trends_by_project[str(getattr(project, "id"))]
            for project in projects[:QUALITY_TREND_PROJECT_LIMIT]
            if quality_trends_by_project[str(getattr(project, "id"))]["chapter_points"]
        ],
        "recent_tasks": [
            {
                "task_id": getattr(task, "task_id"),
                "task_type": getattr(task, "task_type"),
                "status": getattr(task, "status"),
                "progress": getattr(task, "progress", 0),
                "message": getattr(task, "message", None),
                "project_id": getattr(task, "project_id", None),
                "chapter_id": getattr(task, "chapter_id", None),
                "updated_at": getattr(task, "updated_at"),
            }
            for task in recent_tasks
        ],
    }


def build_project_quality_trend_payload(
    project: Any,
    *,
    chapter_limit: int = QUALITY_TREND_CHAPTER_LIMIT,
) -> dict[str, Any]:
    chapters = sorted(
        list(getattr(project, "chapters", []) or []),
        key=lambda chapter: int(getattr(chapter, "chapter_number", 0) or 0),
    )
    if chapter_limit > 0:
        visible_chapters = chapters[-chapter_limit:]
    else:
        visible_chapters = chapters
    chapter_points = []
    scored_points: list[tuple[int, float]] = []
    ai_points: list[tuple[int, float]] = []
    risk_chapter_numbers: list[int] = []
    status_breakdown: Counter[str] = Counter()
    review_ready_chapters = 0
    final_chapters = 0

    for chapter in visible_chapters:
        chapter_number = int(getattr(chapter, "chapter_number", 0) or 0)
        status = str(getattr(chapter, "status", "draft"))
        status_breakdown[status] += 1
        if status in {"review", "final"}:
            review_ready_chapters += 1
        if status == "final":
            final_chapters += 1
        overall_score = _quality_metric(chapter, "overall_score")
        ai_taste_score = _quality_metric(chapter, "ai_taste_score")
        if overall_score is not None:
            scored_points.append((chapter_number, overall_score))
        if ai_taste_score is not None:
            ai_points.append((chapter_number, ai_taste_score))
        if _is_risk_chapter(overall_score, ai_taste_score):
            risk_chapter_numbers.append(chapter_number)

        chapter_points.append(
            {
                "chapter_id": getattr(chapter, "id"),
                "chapter_number": chapter_number,
                "title": getattr(chapter, "title", None),
                "status": status,
                "overall_score": overall_score,
                "ai_taste_score": ai_taste_score,
                "word_count": int(getattr(chapter, "word_count", 0) or 0),
                "updated_at": getattr(chapter, "updated_at"),
            }
        )

    latest_overall_score = scored_points[-1][1] if scored_points else None
    latest_ai_taste_score = ai_points[-1][1] if ai_points else None
    score_delta = _delta(scored_points)
    ai_taste_delta = _delta(ai_points)
    coverage_ratio = 0.0
    if chapter_points:
        coverage_ratio = round(len(scored_points) / len(chapter_points), 2)
    strongest_chapter = _select_chapter_point(chapter_points, highest=True)
    weakest_chapter = _select_chapter_point(chapter_points, highest=False)
    average_overall_score = _mean([score for _, score in scored_points])
    average_ai_taste_score = _mean([score for _, score in ai_points])
    range_start_chapter_number = chapter_points[0]["chapter_number"] if chapter_points else None
    range_end_chapter_number = chapter_points[-1]["chapter_number"] if chapter_points else None

    return {
        "project_id": getattr(project, "id"),
        "title": getattr(project, "title"),
        "status": getattr(project, "status", "draft"),
        "access_role": getattr(project, "access_role", "owner"),
        "owner_email": getattr(getattr(project, "user", None), "email", None),
        "collaborator_count": len(getattr(project, "collaborators", []) or []),
        "updated_at": getattr(project, "updated_at"),
        "latest_overall_score": latest_overall_score,
        "latest_ai_taste_score": latest_ai_taste_score,
        "score_delta": score_delta,
        "ai_taste_delta": ai_taste_delta,
        "trend_direction": _trend_direction(score_delta),
        "evaluated_chapter_count": len(scored_points),
        "chapter_count": len(chapters),
        "visible_chapter_count": len(chapter_points),
        "coverage_ratio": coverage_ratio,
        "average_overall_score": average_overall_score,
        "average_ai_taste_score": average_ai_taste_score,
        "review_ready_chapters": review_ready_chapters,
        "final_chapters": final_chapters,
        "status_breakdown": dict(status_breakdown),
        "range_start_chapter_number": range_start_chapter_number,
        "range_end_chapter_number": range_end_chapter_number,
        "strongest_chapter": strongest_chapter,
        "weakest_chapter": weakest_chapter,
        "risk_chapter_numbers": risk_chapter_numbers,
        "chapter_points": chapter_points,
    }


def _quality_metric(chapter: Any, key: str) -> Optional[float]:
    quality_metrics = ChapterQualityMetricsSnapshot.from_payload(
        getattr(chapter, "quality_metrics", None),
    )
    return quality_metrics.metric_float(key)


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _delta(points: list[tuple[int, float]]) -> Optional[float]:
    if len(points) < 2:
        return None
    return round(points[-1][1] - points[0][1], 4)


def _trend_direction(score_delta: Optional[float]) -> str:
    if score_delta is None:
        return "insufficient_data"
    if score_delta >= 0.05:
        return "improving"
    if score_delta <= -0.05:
        return "declining"
    return "stable"


def _is_risk_chapter(
    overall_score: Optional[float],
    ai_taste_score: Optional[float],
) -> bool:
    return bool(
        (overall_score is not None and overall_score < 0.75)
        or (ai_taste_score is not None and ai_taste_score > 0.35)
    )


def _select_chapter_point(
    chapter_points: list[dict[str, Any]],
    *,
    highest: bool,
) -> Optional[dict[str, Any]]:
    scored_points = [
        point for point in chapter_points if isinstance(point.get("overall_score"), (int, float))
    ]
    if not scored_points:
        return None
    return dict(
        max(scored_points, key=lambda point: float(point["overall_score"]))
        if highest
        else min(scored_points, key=lambda point: float(point["overall_score"]))
    )
