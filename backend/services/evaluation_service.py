from __future__ import annotations

from uuid import UUID

from canon.service import (
    calculate_canon_penalty,
    count_blocking_canon_issues,
    extract_canon_issue_payloads,
    validate_story_bible_integrity,
    validate_story_canon,
)
from sqlalchemy.ext.asyncio import AsyncSession

from evaluation.evaluator import evaluate_chapter_text
from memory.story_bible import load_story_bible_context
from models.chapter import Chapter
from models.evaluation import Evaluation
from schemas.evaluation import EvaluationIssue, EvaluationReport
from schemas.quality import ChapterQualityMetricsSnapshot
from services.chapter_service import get_owned_chapter
from services.chapter_gate_service import mark_quality_metrics_fresh
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
    context = await load_story_bible_context(
        session,
        chapter.project_id,
        user_id,
        branch_id=chapter.branch_id,
    )
    metrics, heuristic_issues, summary = evaluate_chapter_text(chapter.content, context)
    heuristic_overall_score = metrics.calculate_overall_score()
    integrity_report = validate_story_bible_integrity(context)
    serialized_integrity_report = integrity_report.model_dump(mode="json")
    canon_report = validate_story_canon(
        context,
        content=chapter.content,
        chapter_number=chapter.chapter_number,
        chapter_title=chapter.title,
    )
    canon_issues = extract_canon_issue_payloads(canon_report)
    canon_blocking_issue_count = count_blocking_canon_issues(canon_issues)
    overall_score = max(
        0.0,
        min(
            1.0,
            heuristic_overall_score - calculate_canon_penalty(canon_issues),
        ),
    )
    if integrity_report.summary:
        summary = f"{summary} {integrity_report.summary}"
    if canon_report.summary:
        summary = f"{summary} {canon_report.summary}"
    serialized_canon_report = canon_report.model_dump(mode="json")

    evaluation = Evaluation(
        chapter_id=chapter.id,
        metrics={
            "scores": metrics.model_dump(),
            "heuristic_overall_score": heuristic_overall_score,
            "story_bible_integrity_issue_count": integrity_report.issue_count,
            "story_bible_integrity_blocking_issue_count": (
                integrity_report.blocking_issue_count
            ),
            "story_bible_integrity_report": serialized_integrity_report,
            "canon_issue_count": len(canon_issues),
            "canon_blocking_issue_count": canon_blocking_issue_count,
            "canon_report": serialized_canon_report,
        },
        overall_score=overall_score,
        ai_taste_score=metrics.ai_taste_score,
    )
    session.add(evaluation)
    chapter.quality_metrics = mark_quality_metrics_fresh(
        ChapterQualityMetricsSnapshot(
            overall_score=overall_score,
            heuristic_overall_score=heuristic_overall_score,
            ai_taste_score=metrics.ai_taste_score,
            summary=summary,
            story_bible_integrity_issue_count=integrity_report.issue_count,
            story_bible_integrity_blocking_issue_count=integrity_report.blocking_issue_count,
            story_bible_integrity_summary=integrity_report.summary,
            story_bible_integrity_report=serialized_integrity_report,
            canon_issue_count=len(canon_issues),
            canon_blocking_issue_count=canon_blocking_issue_count,
            canon_summary=canon_report.summary,
            canon_plugin_breakdown=canon_report.plugin_breakdown,
            canon_report=serialized_canon_report,
        )
    )
    await session.commit()

    issues = [
        EvaluationIssue(source="heuristic", **issue)
        for issue in heuristic_issues
    ]
    issues.extend(
        EvaluationIssue(
            dimension=str(issue.get("dimension") or "story_bible_integrity"),
            severity=str(issue.get("severity") or "medium"),
            message=str(issue.get("message") or ""),
            blocking=bool(issue.get("blocking")),
            source="story_bible_integrity",
            code=str(issue.get("code")) if issue.get("code") is not None else None,
        )
        for issue in integrity_report.model_dump(mode="json").get("issues", [])
        if isinstance(issue, dict)
    )
    issues.extend(
        EvaluationIssue(
            dimension=str(issue.get("dimension") or "canon"),
            severity=str(issue.get("severity") or "medium"),
            message=str(issue.get("message") or ""),
            blocking=bool(issue.get("blocking")),
            source="canon",
            code=str(issue.get("code")) if issue.get("code") is not None else None,
        )
        for issue in canon_issues
    )

    return EvaluationReport(
        chapter_id=chapter.id,
        overall_score=overall_score,
        heuristic_overall_score=heuristic_overall_score,
        ai_taste_score=metrics.ai_taste_score,
        metrics={key: float(value) for key, value in metrics.model_dump().items()},
        issues=issues,
        summary=summary,
        story_bible_integrity_issue_count=integrity_report.issue_count,
        story_bible_integrity_blocking_issue_count=integrity_report.blocking_issue_count,
        story_bible_integrity_report=integrity_report,
        canon_issue_count=len(canon_issues),
        canon_blocking_issue_count=canon_blocking_issue_count,
        canon_report=canon_report,
        context_snapshot={
            "project_id": str(context.project_id),
            "title": context.title,
            "scope_kind": context.scope_kind,
            "branch_id": str(context.branch_id) if context.branch_id is not None else None,
            "branch_key": context.branch_key,
            "base_scope_kind": context.base_scope_kind,
            "base_branch_id": (
                str(context.base_branch_id) if context.base_branch_id is not None else None
            ),
            "base_branch_key": context.base_branch_key,
            "has_snapshot": context.has_snapshot,
            "changed_sections": context.changed_sections,
            "total_override_count": context.total_override_count,
            "character_count": len(context.characters),
            "world_setting_count": len(context.world_settings),
            "chapter_count": len(context.chapter_summaries),
        },
    )
