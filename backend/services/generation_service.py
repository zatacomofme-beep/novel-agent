from __future__ import annotations

"""Legacy chapter generation core.

This module is frozen except for compatibility fixes.
Current product mainline should prefer Story Engine workflows instead of adding
new behavior here.
"""

from functools import partial
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agents.base import AgentRunContext
from agents.coordinator import CoordinatorAgent
from canon.base import CanonIntegrityReport
from canon.service import validate_story_bible_integrity
from memory.story_bible import load_story_bible_context
from models.project import Project
from schemas.chapter import ChapterUpdate
from schemas.evaluation import EvaluationReport
from services.chapter_service import get_owned_chapter, update_chapter
from services.checkpoint_service import CheckpointService
from services.neo4j_service import Neo4jService
from services.evaluation_service import evaluate_existing_chapter
from services.preference_service import (
    build_style_guidance,
    get_preference_learning_snapshot,
    get_or_create_user_preference,
    resolve_generation_preference_payload,
)
from services.project_generation_service import propose_story_bible_updates_from_generation
from services.project_service import PROJECT_PERMISSION_EDIT
from services.social_topology_service import SocialTopologyService
from core.circuit_breaker import (
    CircuitBreakerReason,
    TokenCircuitBreaker,
    token_circuit_breaker,
)


class CheckpointManager:
    def __init__(self, session: AsyncSession) -> None:
        self._svc = CheckpointService(session)

    async def save(
        self,
        *,
        chapter_id: str,
        user_id: str,
        chapter_version_number: int,
        title: str,
        generation_payload: dict[str, Any],
        generated_content: str,
        progress: int,
        segments_completed: int,
        segments_total: int,
    ) -> None:
        await self._svc.save_generation_checkpoint(
            chapter_id=UUID(chapter_id),
            user_id=UUID(user_id),
            chapter_version_number=chapter_version_number,
            title=title,
            generation_payload=generation_payload,
            generated_content=generated_content,
            progress=progress,
            segments_completed=segments_completed,
            segments_total=segments_total,
        )
from services.truth_layer_service import build_truth_layer_context
from services.foreshadowing_lifecycle_service import foreshadowing_lifecycle_service
from models.open_thread import ThreadStatus


class StoryBibleIntegrityError(RuntimeError):
    def __init__(self, report: CanonIntegrityReport) -> None:
        self.report = report
        super().__init__(f"Story Bible integrity blocked generation. {report.summary}")


async def build_generation_payload(
    session: AsyncSession,
    chapter_id: UUID,
    user_id: UUID,
) -> dict:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    context = await load_story_bible_context(
        session,
        chapter.project_id,
        user_id,
        branch_id=chapter.branch_id,
    )
    preference = await get_or_create_user_preference(session, user_id)
    learning_snapshot = await get_preference_learning_snapshot(session, user_id)
    style_preferences = resolve_generation_preference_payload(
        preference,
        learning_snapshot,
    )
    project = await session.get(Project, chapter.project_id)
    project_bootstrap_profile = (
        project.bootstrap_profile
        if project is not None and isinstance(project.bootstrap_profile, dict)
        else None
    )
    novel_blueprint = (
        project.novel_blueprint
        if project is not None and isinstance(project.novel_blueprint, dict)
        else None
    )
    chapter_outline_seed = chapter.outline if isinstance(chapter.outline, dict) else None
    style_guidance = _build_project_aware_style_guidance(
        build_style_guidance(style_preferences, learning_snapshot),
        project_bootstrap_profile=project_bootstrap_profile,
        novel_blueprint=novel_blueprint,
        chapter_outline_seed=chapter_outline_seed,
    )

    base = {
        "chapter_id": str(chapter.id),
        "project_id": str(chapter.project_id),
        "volume_id": str(chapter.volume_id) if chapter.volume_id is not None else None,
        "volume_title": chapter.volume.title if chapter.volume is not None else None,
        "volume_number": chapter.volume.volume_number if chapter.volume is not None else None,
        "branch_id": str(chapter.branch_id) if chapter.branch_id is not None else None,
        "branch_title": chapter.branch.title if chapter.branch is not None else None,
        "branch_key": chapter.branch.key if chapter.branch is not None else None,
        "branch_description": (
            chapter.branch.description if chapter.branch is not None else None
        ),
        "chapter_number": chapter.chapter_number,
        "chapter_title": chapter.title,
        "project_title": context.title,
        "genre": context.genre,
        "theme": context.theme,
        "tone": context.tone,
        "character_names": [item["name"] for item in context.characters[:12]],
        "location_names": [item["name"] for item in context.locations[:12]],
        "plot_threads": [item["title"] for item in context.plot_threads[:12]],
        "foreshadowing_count": len(context.foreshadowing),
        "timeline_count": len(context.timeline_events),
        "style_preferences": style_preferences,
        "style_learning_snapshot": learning_snapshot.model_dump(),
        "style_guidance": style_guidance,
        "project_bootstrap_profile": project_bootstrap_profile,
        "novel_blueprint": novel_blueprint,
        "chapter_outline_seed": chapter_outline_seed,
    }

    social_svc = SocialTopologyService()
    try:
        social_topology = await social_svc.build_social_topology(session, chapter.project_id)
        base["social_topology"] = {
            "centrality_scores": social_topology.centrality_scores or {},
            "influence_graph": social_topology.influence_graph or {},
            "social_dynamics": social_topology.social_dynamics or {},
            "cluster_data": social_topology.cluster_data or {},
        }
    except Exception:
        base["social_topology"] = {}

    return base


async def run_generation_pipeline(
    session: AsyncSession,
    *,
    chapter_id: UUID,
    user_id: UUID,
    task_id: str,
) -> dict[str, Any]:
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
        permission=PROJECT_PERMISSION_EDIT,
    )
    story_bible = await load_story_bible_context(
        session,
        chapter.project_id,
        user_id,
        branch_id=chapter.branch_id,
    )
    integrity_report = validate_story_bible_integrity(story_bible)
    if integrity_report.blocking_issue_count > 0:
        raise StoryBibleIntegrityError(integrity_report)
    base_payload = await build_generation_payload(session, chapter.id, user_id)

    open_threads = await foreshadowing_lifecycle_service.get_active_threads(
        session,
        project_id=chapter.project_id,
        chapter_num=chapter.chapter_number,
        lookback=10,
    )
    open_threads_data = [
        {
            "id": str(t.id),
            "planted_chapter": t.planted_chapter,
            "entity_ref": t.entity_ref,
            "entity_type": t.entity_type,
            "potential_tags": t.potential_tags or [],
            "status": t.status,
            "payoff_priority": t.payoff_priority,
            "planted_content": t.planted_content,
        }
        for t in open_threads
    ]

    checkpoint_mgr = CheckpointManager(session)

    neo4j_svc = Neo4jService()
    causal_context: dict[str, Any] = {}
    try:
        prev_chapter = chapter.chapter_number - 1
        if prev_chapter >= 1:
            paths = await neo4j_svc.query_causal_paths(
                chapter.project_id,
                from_chapter=prev_chapter,
                to_chapter=chapter.chapter_number,
                max_hops=5,
            )
            causal_context["causal_paths"] = paths
        influence = await neo4j_svc.compute_character_influence(chapter.project_id)
        causal_context["character_influence"] = influence
    except Exception:
        causal_context = {}

    latest_cp = await checkpoint_mgr._svc.get_latest_generation_checkpoint(chapter.id)
    can_resume = latest_cp is not None and checkpoint_mgr._svc.can_resume(latest_cp)
    resume_from: dict[str, Any] | None = None
    if can_resume and latest_cp is not None:
        resume_from = {
            "checkpoint_id": str(latest_cp.id),
            "generated_content": latest_cp.generated_content or "",
            "segments_completed": latest_cp.segments_completed or 0,
            "segments_total": latest_cp.segments_total or 0,
            "chapter_version_number": latest_cp.chapter_version_number,
        }

    coordinator = CoordinatorAgent()
    run_context = AgentRunContext(
        chapter_id=str(chapter.id),
        project_id=str(chapter.project_id),
        task_id=task_id,
        payload=base_payload,
    )
    response = await coordinator.run(
        run_context,
        {
            **base_payload,
            "story_bible": story_bible,
            "story_bible_integrity_report": integrity_report.model_dump(mode="json"),
            "open_threads": open_threads_data,
            "causal_context": causal_context,
            "resume_from": resume_from,
            "save_checkpoint": checkpoint_mgr.save,
        },
    )
    if not response.success:
        raise RuntimeError(response.error or "Generation pipeline failed.")

    final_outline = response.data["outline"]
    final_content = response.data["content"]
    approval = response.data.get("approval")
    chapter_status = "review"
    if isinstance(approval, dict) and approval.get("approved") is False:
        chapter_status = "writing"

    updated_chapter = await update_chapter(
        session,
        chapter,
        ChapterUpdate(
            title=chapter.title or final_outline["title"],
            content=final_content,
            outline=final_outline,
            status=chapter_status,
            change_reason="Generated by coordinator pipeline",
            create_version=True,
        ),
        preference_learning_user_id=None,
    )

    from memory.l2_episodic import L2EpisodicMemory
    l2_mem = L2EpisodicMemory(session)
    await l2_mem.save_episode(
        project_id=updated_chapter.project_id,
        chapter_id=updated_chapter.id,
        chapter_number=updated_chapter.chapter_number,
        summary=final_outline.get("summary", ""),
        content=final_content,
        key_events=[],
        characters=[],
        locations=[],
        emotional_tone="neutral",
        themes=[],
        open_threads=[],
        importance_score=0.6,
    )

    try:
        await neo4j_svc.create_event_node(
            project_id=updated_chapter.project_id,
            chapter=updated_chapter.chapter_number,
            name=final_outline.get("title", f"Chapter {updated_chapter.chapter_number}"),
            summary=final_outline.get("summary", "")[:500],
            event_type="chapter_event",
        )
    except Exception:
        pass

    report = await evaluate_existing_chapter(session, updated_chapter, user_id)

    await foreshadowing_lifecycle_service.scan_and_plant(
        session,
        project_id=updated_chapter.project_id,
        chapter_num=updated_chapter.chapter_number,
        content=final_content,
    )

    project_for_followups = await session.get(Project, updated_chapter.project_id)
    if project_for_followups is not None:
        story_bible_followup_proposals = await propose_story_bible_updates_from_generation(
            session,
            project=project_for_followups,
            chapter=updated_chapter,
            story_bible=story_bible,
            chapter_outline_seed=base_payload.get("chapter_outline_seed"),
            final_outline=final_outline,
            agent_name="project_generation",
        )
    else:
        story_bible_followup_proposals = []
    final_truth_layer_context = build_truth_layer_context(
        integrity_report=integrity_report.model_dump(mode="json"),
        canon_report=response.data.get("final_canon_report")
        if isinstance(response.data.get("final_canon_report"), dict)
        else None,
    )

    return {
        "chapter_id": str(updated_chapter.id),
        "project_id": str(updated_chapter.project_id),
        "outline": final_outline,
        "content": final_content,
        "chapter_status": updated_chapter.status,
        "quality_metrics": updated_chapter.quality_metrics,
        "evaluation": _serialize_evaluation_report(report),
        "story_bible_integrity_report": integrity_report.model_dump(mode="json"),
        "truth_layer_context": response.data.get("truth_layer_context")
        if isinstance(response.data.get("truth_layer_context"), dict)
        else final_truth_layer_context,
        "initial_truth_layer_context": response.data.get("initial_truth_layer_context"),
        "final_truth_layer_context": response.data.get("final_truth_layer_context")
        if isinstance(response.data.get("final_truth_layer_context"), dict)
        else final_truth_layer_context,
        "context_bundle": response.data.get("context_bundle"),
        "review": response.data.get("review"),
        "initial_review": response.data.get("initial_review"),
        "final_review": response.data.get("final_review"),
        "canon_report": response.data.get("canon_report"),
        "initial_canon_report": response.data.get("initial_canon_report"),
        "final_canon_report": response.data.get("final_canon_report"),
        "revision_focus": response.data.get("revision_focus"),
        "revision_plan": response.data.get("revision_plan"),
        "debate_summary": response.data.get("debate_summary"),
        "approval": approval,
        "agent_trace": run_context.trace,
        "revised": response.data.get("revised", False),
        "story_bible_followup_proposals": story_bible_followup_proposals,
        "story_bible_followup_proposal_count": len(story_bible_followup_proposals),
        "cost_report": token_circuit_breaker.get_report(str(chapter.id)),
    }


def _serialize_evaluation_report(report: EvaluationReport) -> dict[str, Any]:
    return {
        "chapter_id": str(report.chapter_id),
        "overall_score": report.overall_score,
        "heuristic_overall_score": report.heuristic_overall_score,
        "ai_taste_score": report.ai_taste_score,
        "metrics": report.metrics,
        "issues": [issue.model_dump() for issue in report.issues],
        "summary": report.summary,
        "story_bible_integrity_issue_count": report.story_bible_integrity_issue_count,
        "story_bible_integrity_blocking_issue_count": (
            report.story_bible_integrity_blocking_issue_count
        ),
        "story_bible_integrity_report": (
            report.story_bible_integrity_report.model_dump(mode="json")
            if report.story_bible_integrity_report is not None
            else None
        ),
        "canon_issue_count": report.canon_issue_count,
        "canon_blocking_issue_count": report.canon_blocking_issue_count,
        "canon_report": (
            report.canon_report.model_dump(mode="json")
            if report.canon_report is not None
            else None
        ),
        "context_snapshot": report.context_snapshot,
    }


def _build_project_aware_style_guidance(
    base_guidance: str,
    *,
    project_bootstrap_profile: dict[str, Any] | None,
    novel_blueprint: dict[str, Any] | None,
    chapter_outline_seed: dict[str, Any] | None,
) -> str:
    parts = [base_guidance.strip()]

    if isinstance(project_bootstrap_profile, dict):
        project_notes: list[str] = []
        novel_style = str(project_bootstrap_profile.get("novel_style") or "").strip()
        prose_style = str(project_bootstrap_profile.get("prose_style") or "").strip()
        core_story = str(project_bootstrap_profile.get("core_story") or "").strip()
        target_chapter_words = project_bootstrap_profile.get("target_chapter_words")
        special_requirements = str(
            project_bootstrap_profile.get("special_requirements") or ""
        ).strip()
        if novel_style:
            project_notes.append(f"项目级小说风格={novel_style}")
        if prose_style:
            project_notes.append(f"项目级行文风格={prose_style}")
        if core_story:
            project_notes.append(f"核心故事={core_story}")
        if isinstance(target_chapter_words, int) and target_chapter_words > 0:
            project_notes.append(f"单章目标字数约={target_chapter_words}")
        if special_requirements:
            project_notes.append(f"额外约束={special_requirements}")
        if project_notes:
            parts.append("项目启动约束：" + "；".join(project_notes) + "。")

    if isinstance(novel_blueprint, dict):
        premise = str(novel_blueprint.get("premise") or "").strip()
        story_engine = str(novel_blueprint.get("story_engine") or "").strip()
        if premise or story_engine:
            parts.append(
                "项目蓝图：" + "；".join(
                    item
                    for item in (
                        f"命题={premise}" if premise else "",
                        f"推进引擎={story_engine}" if story_engine else "",
                    )
                    if item
                ) + "。"
            )

    if isinstance(chapter_outline_seed, dict):
        chapter_seed_notes: list[str] = []
        objective = str(chapter_outline_seed.get("objective") or "").strip()
        summary = str(chapter_outline_seed.get("summary") or "").strip()
        expected_word_count = chapter_outline_seed.get("expected_word_count")
        if objective:
            chapter_seed_notes.append(f"当前章目标={objective}")
        if summary:
            chapter_seed_notes.append(f"当前章摘要={summary}")
        if isinstance(expected_word_count, int) and expected_word_count > 0:
            chapter_seed_notes.append(f"当前章期望字数={expected_word_count}")
        if chapter_seed_notes:
            parts.append("章节蓝图种子：" + "；".join(chapter_seed_notes) + "。")

    return " ".join(part for part in parts if part)
