from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select
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
RECENT_TASK_LIMIT = 8
FOCUS_QUEUE_LIMIT = 6
GENRE_DISTRIBUTION_LIMIT = 6
ACTIVE_PROJECT_WINDOW_DAYS = 7
NEW_PROJECT_WINDOW_DAYS = 30
STALE_PROJECT_WINDOW_DAYS = 14
FINAL_CHAPTER_WINDOW_DAYS = 30
STALLED_TASK_WINDOW_MINUTES = 30


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
    task_status_counts: dict[str, int] = {}
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
            .options(selectinload(TaskRun.chapter))
            .where(TaskRun.project_id.in_(project_ids))
            .order_by(TaskRun.updated_at.desc())
            .limit(RECENT_TASK_LIMIT)
        )
        recent_tasks = list(recent_tasks_result.scalars().all())

        task_status_counts_result = await session.execute(
            select(TaskRun.status, func.count(TaskRun.id))
            .where(TaskRun.project_id.in_(project_ids))
            .group_by(TaskRun.status)
        )
        task_status_counts = {
            str(status): int(count or 0)
            for status, count in task_status_counts_result.all()
        }
    preference = await get_or_create_user_preference(session, user_id)
    learning_snapshot = await get_preference_learning_snapshot(session, user_id)

    return build_dashboard_overview_payload(
        projects=projects,
        active_tasks=active_tasks,
        recent_tasks=recent_tasks,
        task_status_counts=task_status_counts,
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
    task_status_counts: Optional[dict[str, int]] = None,
    preference_profile: Any,
    learning_snapshot: Optional[Any] = None,
) -> dict[str, Any]:
    now = _utcnow()
    active_project_threshold = now - timedelta(days=ACTIVE_PROJECT_WINDOW_DAYS)
    new_project_threshold = now - timedelta(days=NEW_PROJECT_WINDOW_DAYS)
    stale_project_threshold = now - timedelta(days=STALE_PROJECT_WINDOW_DAYS)
    final_chapter_threshold = now - timedelta(days=FINAL_CHAPTER_WINDOW_DAYS)
    stalled_task_threshold = now - timedelta(minutes=STALLED_TASK_WINDOW_MINUTES)

    total_projects = len(projects)
    total_chapters = 0
    total_words = 0
    review_ready_chapters = 0
    final_chapters = 0
    chapters_by_status: Counter[str] = Counter()
    overall_scores: list[float] = []
    ai_taste_scores: list[float] = []
    coverage_ratios: list[float] = []
    active_tasks_by_project: Counter[str] = Counter()
    genre_counter: Counter[str] = Counter()
    project_stage_counts: Counter[str] = Counter()
    focus_queue: list[dict[str, Any]] = []

    active_projects_last_7_days = 0
    chapters_updated_last_7_days = 0
    active_words_last_7_days = 0
    new_projects_last_30_days = 0
    final_chapters_last_30_days = 0
    stale_projects_last_14_days = 0

    risk_chapter_count = 0
    projects_with_risk_count = 0
    low_score_chapter_count = 0
    high_ai_taste_chapter_count = 0
    improving_project_count = 0
    declining_project_count = 0
    stable_project_count = 0

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
        project_id = str(getattr(project, "id"))
        project_updated_at = _coerce_datetime(getattr(project, "updated_at", None), now)
        project_created_at = _coerce_datetime(
            getattr(project, "created_at", None),
            project_updated_at,
        )
        project_trend = quality_trends_by_project.get(project_id, {})
        project_status_breakdown: Counter[str] = Counter()
        total_chapters += len(chapters)

        project_words = 0
        project_scores: list[float] = []
        project_ai_scores: list[float] = []
        project_review_ready = 0
        project_final = 0
        project_risks = 0
        review_only_chapters: list[int] = []
        writing_chapters: list[int] = []
        draft_chapters: list[int] = []

        for chapter in chapters:
            status = str(getattr(chapter, "status", "draft"))
            chapters_by_status[status] += 1
            project_status_breakdown[status] += 1
            word_count = int(getattr(chapter, "word_count", 0) or 0)
            total_words += word_count
            project_words += word_count

            if status in {"review", "final"}:
                review_ready_chapters += 1
                project_review_ready += 1
            if status == "final":
                final_chapters += 1
                project_final += 1
                if _coerce_datetime(getattr(chapter, "updated_at", None), now) >= final_chapter_threshold:
                    final_chapters_last_30_days += 1
            if status == "review":
                review_only_chapters.append(int(getattr(chapter, "chapter_number", 0) or 0))
            if status == "writing":
                writing_chapters.append(int(getattr(chapter, "chapter_number", 0) or 0))
            if status == "draft":
                draft_chapters.append(int(getattr(chapter, "chapter_number", 0) or 0))

            chapter_updated_at = _coerce_datetime(getattr(chapter, "updated_at", None), now)
            if chapter_updated_at >= active_project_threshold:
                chapters_updated_last_7_days += 1
                active_words_last_7_days += word_count

            overall_score = _quality_metric(chapter, "overall_score")
            ai_taste_score = _quality_metric(chapter, "ai_taste_score")
            if overall_score is not None:
                overall_scores.append(overall_score)
                project_scores.append(overall_score)
                if overall_score < 0.75:
                    low_score_chapter_count += 1
            if ai_taste_score is not None:
                ai_taste_scores.append(ai_taste_score)
                project_ai_scores.append(ai_taste_score)
                if ai_taste_score > 0.35:
                    high_ai_taste_chapter_count += 1
            if (
                (overall_score is not None and overall_score < 0.75)
                or (ai_taste_score is not None and ai_taste_score > 0.35)
            ):
                project_risks += 1
                risk_chapter_count += 1

        if project_updated_at >= active_project_threshold:
            active_projects_last_7_days += 1
        if project_created_at >= new_project_threshold:
            new_projects_last_30_days += 1
        if project_updated_at < stale_project_threshold:
            stale_projects_last_14_days += 1

        normalized_genre = str(getattr(project, "genre", "") or "").strip() or "未设置题材"
        genre_counter[normalized_genre] += 1

        if project_risks > 0:
            projects_with_risk_count += 1

        trend_payload = project_trend
        trend_direction = str(trend_payload.get("trend_direction", "insufficient_data"))
        if trend_direction == "improving":
            improving_project_count += 1
        elif trend_direction == "declining":
            declining_project_count += 1
        elif trend_direction == "stable":
            stable_project_count += 1
        coverage_ratio = trend_payload.get("coverage_ratio")
        if isinstance(coverage_ratio, (int, float)):
            coverage_ratios.append(float(coverage_ratio))

        pipeline_stage = _classify_project_pipeline_stage(
            has_novel_blueprint=bool(getattr(project, "novel_blueprint", None)),
            chapter_count=len(chapters),
            project_status_breakdown=project_status_breakdown,
        )
        project_stage_counts[pipeline_stage] += 1

        project_active_task_count = active_tasks_by_project.get(project_id, 0)
        focus_item = _build_dashboard_focus_item(
            project=project,
            project_id=project_id,
            chapter_count=len(chapters),
            project_risks=project_risks,
            pipeline_stage=pipeline_stage,
            review_only_chapters=review_only_chapters,
            writing_chapters=writing_chapters,
            draft_chapters=draft_chapters,
            trend_payload=trend_payload,
            active_task_count=project_active_task_count,
            stale_threshold=stale_project_threshold,
            now=now,
        )
        if focus_item is not None:
            focus_queue.append(focus_item)

        project_summaries.append(
            {
                "project_id": getattr(project, "id"),
                "title": getattr(project, "title"),
                "genre": getattr(project, "genre", None),
                "status": getattr(project, "status", "draft"),
                "access_role": getattr(project, "access_role", "owner"),
                "owner_email": getattr(getattr(project, "user", None), "email", None),
                "collaborator_count": len(getattr(project, "collaborators", []) or []),
                "has_bootstrap_profile": bool(getattr(project, "bootstrap_profile", None)),
                "has_novel_blueprint": bool(getattr(project, "novel_blueprint", None)),
                "updated_at": project_updated_at,
                "chapter_count": len(chapters),
                "word_count": project_words,
                "review_ready_chapters": project_review_ready,
                "final_chapters": project_final,
                "risk_chapter_count": project_risks,
                "active_task_count": project_active_task_count,
                "average_overall_score": _mean(project_scores),
                "average_ai_taste_score": _mean(project_ai_scores),
                "score_delta": trend_payload.get("score_delta"),
                "trend_direction": trend_direction,
            }
        )

    status_counts = dict(task_status_counts or {})
    stalled_active_task_count = sum(
        1
        for task in active_tasks
        if _coerce_datetime(getattr(task, "updated_at", None), now) < stalled_task_threshold
    )
    recent_failed_task_count = sum(
        1 for task in recent_tasks if str(getattr(task, "status", "")).strip() == "failed"
    )
    total_task_count = sum(int(value or 0) for value in status_counts.values())

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
                "chapter_number": getattr(getattr(task, "chapter", None), "chapter_number", None),
                "updated_at": getattr(task, "updated_at"),
            }
            for task in recent_tasks
        ],
        "activity_snapshot": {
            "active_projects_last_7_days": active_projects_last_7_days,
            "chapters_updated_last_7_days": chapters_updated_last_7_days,
            "active_words_last_7_days": active_words_last_7_days,
            "new_projects_last_30_days": new_projects_last_30_days,
            "final_chapters_last_30_days": final_chapters_last_30_days,
            "stale_projects_last_14_days": stale_projects_last_14_days,
        },
        "quality_snapshot": {
            "risk_chapter_count": risk_chapter_count,
            "projects_with_risk_count": projects_with_risk_count,
            "low_score_chapter_count": low_score_chapter_count,
            "high_ai_taste_chapter_count": high_ai_taste_chapter_count,
            "improving_project_count": improving_project_count,
            "declining_project_count": declining_project_count,
            "stable_project_count": stable_project_count,
            "average_coverage_ratio": round(_mean(coverage_ratios) or 0.0, 4),
        },
        "task_health": {
            "total_task_count": total_task_count,
            "queued_count": int(status_counts.get("queued", 0)),
            "running_count": int(status_counts.get("running", 0)),
            "succeeded_count": int(status_counts.get("succeeded", 0)),
            "failed_count": int(status_counts.get("failed", 0)),
            "cancelled_count": int(status_counts.get("cancelled", 0)),
            "stalled_active_task_count": stalled_active_task_count,
            "recent_failed_task_count": recent_failed_task_count,
            "status_breakdown": status_counts,
        },
        "pipeline_snapshot": {
            "outline_pending_projects": int(project_stage_counts.get("outline_pending", 0)),
            "ready_for_first_chapter_projects": int(
                project_stage_counts.get("ready_for_first_chapter", 0)
            ),
            "writing_in_progress_projects": int(
                project_stage_counts.get("writing_in_progress", 0)
            ),
            "awaiting_finalization_projects": int(
                project_stage_counts.get("awaiting_finalization", 0)
            ),
            "stable_output_projects": int(project_stage_counts.get("stable_output", 0)),
        },
        "genre_distribution": [
            {"genre": genre, "project_count": count}
            for genre, count in genre_counter.most_common(GENRE_DISTRIBUTION_LIMIT)
        ],
        "focus_queue": sorted(
            focus_queue,
            key=lambda item: (
                -int(item.get("priority", 0)),
                -_coerce_datetime(item.get("updated_at"), now).timestamp(),
                str(item.get("title") or ""),
            ),
        )[:FOCUS_QUEUE_LIMIT],
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_datetime(value: Any, fallback: datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return fallback


def _classify_project_pipeline_stage(
    *,
    has_novel_blueprint: bool,
    chapter_count: int,
    project_status_breakdown: Counter[str],
) -> str:
    if not has_novel_blueprint:
        return "outline_pending"
    if chapter_count <= 0:
        return "ready_for_first_chapter"
    if int(project_status_breakdown.get("review", 0)) > 0:
        return "awaiting_finalization"
    if int(project_status_breakdown.get("draft", 0)) > 0 or int(
        project_status_breakdown.get("writing", 0)
    ) > 0:
        return "writing_in_progress"
    if int(project_status_breakdown.get("final", 0)) == chapter_count:
        return "stable_output"
    return "writing_in_progress"


def _build_dashboard_focus_item(
    *,
    project: Any,
    project_id: str,
    chapter_count: int,
    project_risks: int,
    pipeline_stage: str,
    review_only_chapters: list[int],
    writing_chapters: list[int],
    draft_chapters: list[int],
    trend_payload: dict[str, Any],
    active_task_count: int,
    stale_threshold: datetime,
    now: datetime,
) -> Optional[dict[str, Any]]:
    project_updated_at = _coerce_datetime(getattr(project, "updated_at", None), now)
    title = str(getattr(project, "title", "") or "").strip()
    if not title:
        return None

    trend_points = list(trend_payload.get("chapter_points") or [])
    weakest_chapter = trend_payload.get("weakest_chapter") or {}
    weakest_chapter_number = weakest_chapter.get("chapter_number")
    weakest_score = weakest_chapter.get("overall_score")

    base_payload = {
        "project_id": getattr(project, "id"),
        "title": title,
        "genre": getattr(project, "genre", None),
        "updated_at": project_updated_at,
    }

    if pipeline_stage == "outline_pending":
        return {
            **base_payload,
            "focus_type": "outline",
            "stage": "outline",
            "action_label": "先定三级大纲",
            "reason": "这本书还没有锁定三级大纲，先把主线和章纲定住。",
            "chapter_number": None,
            "priority": 100,
            "risk_level": "high",
        }

    if pipeline_stage == "ready_for_first_chapter":
        return {
            **base_payload,
            "focus_type": "first_chapter",
            "stage": "draft",
            "action_label": "开始第一章",
            "reason": "大纲已经就绪，但正文还没开始，先把第一章写出来。",
            "chapter_number": 1,
            "priority": 92,
            "risk_level": "medium",
        }

    if project_risks > 0 and isinstance(weakest_chapter_number, int):
        score_text = (
            f"当前评分 {weakest_score:.2f}"
            if isinstance(weakest_score, (int, float))
            else "当前需要先做回看"
        )
        return {
            **base_payload,
            "focus_type": "risk_review",
            "stage": "draft",
            "action_label": f"先处理 Ch{weakest_chapter_number}",
            "reason": f"这本书最近有风险章节，先回看最低分章节。{score_text}",
            "chapter_number": weakest_chapter_number,
            "priority": 88,
            "risk_level": "high",
        }

    if review_only_chapters:
        target_chapter = min(review_only_chapters)
        return {
            **base_payload,
            "focus_type": "finalize",
            "stage": "final",
            "action_label": f"确认 Ch{target_chapter} 终稿",
            "reason": "这本书已经有章节进入收口阶段，先确认终稿再继续往后推。",
            "chapter_number": target_chapter,
            "priority": 82,
            "risk_level": "medium",
        }

    if active_task_count > 0:
        latest_chapter_number = _resolve_latest_chapter_number(trend_points, chapter_count)
        return {
            **base_payload,
            "focus_type": "active_task",
            "stage": "draft",
            "action_label": "回工作台看结果",
            "reason": f"这本书后台还有 {active_task_count} 个任务在跑，先回去看进度和结果。",
            "chapter_number": latest_chapter_number,
            "priority": 74,
            "risk_level": "low",
        }

    if draft_chapters or writing_chapters:
        current_chapter = max(draft_chapters + writing_chapters)
        stale_boost = 8 if project_updated_at < stale_threshold else 0
        return {
            **base_payload,
            "focus_type": "continue_draft",
            "stage": "draft",
            "action_label": f"继续 Ch{current_chapter}",
            "reason": (
                "这本书已经起稿，继续把当前章节往下顺。"
                if stale_boost <= 0
                else "这本书已经停了一段时间，先把当前章节重新接上。"
            ),
            "chapter_number": current_chapter,
            "priority": 66 + stale_boost,
            "risk_level": "low",
        }

    next_chapter = _resolve_latest_chapter_number(trend_points, chapter_count) + 1
    return {
        **base_payload,
        "focus_type": "next_chapter",
        "stage": "draft",
        "action_label": f"继续下一章",
        "reason": "当前没有明显风险，可以直接推进下一章。",
        "chapter_number": next_chapter,
        "priority": 58,
        "risk_level": "low",
    }


def _resolve_latest_chapter_number(chapter_points: list[dict[str, Any]], chapter_count: int) -> int:
    visible_numbers = [
        int(point.get("chapter_number") or 0)
        for point in chapter_points
        if int(point.get("chapter_number") or 0) > 0
    ]
    if visible_numbers:
        return max(visible_numbers)
    return max(chapter_count, 0)


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
