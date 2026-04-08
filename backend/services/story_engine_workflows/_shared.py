from __future__ import annotations

import asyncio
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional, TypedDict
from uuid import UUID, uuid4

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.story_agents import build_agent_report, export_agent_specs
from core.circuit_breaker import token_circuit_breaker
from core.config import get_settings
from core.errors import AppError
from models.story_engine import StoryChapterSummary, StoryOutline
from schemas.story_engine import (
    StoryCharacterRead,
    StoryForeshadowRead,
    StoryItemRead,
    StoryOutlineRead,
    StoryTimelineMapEventRead,
    StoryWorldRuleRead,
)
from services.chapter_service import get_owned_chapter
from services.checkpoint_service import CheckpointService
from services.foreshadowing_lifecycle_service import foreshadowing_lifecycle_service
from services.neo4j_service import neo4j_service
from services.social_topology_service import social_topology_service
from services.story_engine_kb_service import (
    build_workspace,
    create_entity,
    get_entity,
    get_story_engine_project,
    list_entities,
    search_knowledge,
    update_entity,
)
from services.story_engine_model_service import (
    build_outline_context_text,
    build_realtime_guard_context_text,
    build_workspace_context_text,
    generate_story_agent_report,
    generate_story_anchor_payload,
    generate_story_outline_blueprint,
    generate_story_realtime_arbitration,
    generate_story_stream_paragraph,
    get_story_engine_role_model,
    revise_story_final_draft,
)
from services.story_engine_settings_service import (
    get_story_engine_guardian_consensus_config,
    resolve_story_engine_model_routing,
)
from services.task_service import (
    create_task_event,
    create_task_run,
    get_task_run_by_task_id,
    update_task_run,
)
from tasks.schemas import TaskState
from tasks.state_store import task_state_store

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - 开发环境缺依赖时走本地串行兜底
    END = "__end__"
    START = "__start__"
    StateGraph = None
    LANGGRAPH_AVAILABLE = False


_STORY_ENGINE_READ_SCHEMAS = {
    "characters": StoryCharacterRead,
    "foreshadows": StoryForeshadowRead,
    "items": StoryItemRead,
    "world_rules": StoryWorldRuleRead,
    "timeline_events": StoryTimelineMapEventRead,
    "outlines": StoryOutlineRead,
}


class OutlineStressState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    idea: str
    source_material: Optional[str]
    source_material_name: Optional[str]
    genre: Optional[str]
    tone: Optional[str]
    target_chapter_count: int
    target_total_words: int
    model_routing: dict[str, dict[str, Any]]
    outline_draft: dict[str, list[dict[str, Any]]]
    initial_kb: dict[str, list[dict[str, Any]]]
    guardian_report: dict[str, Any]
    commercial_report: dict[str, Any]
    logic_report: dict[str, Any]
    debate_round: int
    unresolved_issues: list[dict[str, Any]]
    optimization_plan: list[str]
    debate_history: list[dict[str, Any]]
    arbitrated_report: dict[str, Any]


class RealtimeGuardState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    chapter_number: int
    chapter_title: Optional[str]
    outline_id: Optional[UUID]
    current_outline: Optional[str]
    recent_chapters: list[str]
    draft_text: str
    latest_paragraph: Optional[str]
    model_routing: dict[str, dict[str, Any]]
    workspace: dict[str, Any]
    guardian_report: dict[str, Any]
    commercial_report: dict[str, Any]
    alerts: list[dict[str, Any]]
    repair_options: list[str]
    arbitration_note: Optional[str]
    should_pause: bool


class FinalVerifyState(TypedDict, total=False):
    session: AsyncSession
    project_id: UUID
    user_id: UUID
    branch_id: Optional[UUID]
    chapter_number: int
    chapter_title: Optional[str]
    draft_text: str
    style_sample: Optional[str]
    model_routing: dict[str, dict[str, Any]]
    guardian_report: dict[str, Any]
    logic_report: dict[str, Any]
    commercial_report: dict[str, Any]
    style_report: dict[str, Any]
    anchor_payload: dict[str, Any]
    final_package: dict[str, Any]
    finalize_output: bool
    output_finalized: bool


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _build_workflow_id(workflow_type: str) -> str:
    return f"{workflow_type}:{uuid4().hex}"


_WORKFLOW_TASK_TYPE_MAP = {
    "outline_stress_test": "story_engine.outline_stress_test",
    "bulk_import": "story_engine.bulk_import",
    "realtime_guard": "story_engine.realtime_guard",
    "chapter_stream": "story_engine.chapter_stream",
    "final_optimize": "story_engine.final_optimize",
}


def _supports_workflow_task_persistence(session: Any) -> bool:
    return all(hasattr(session, attr) for attr in ("add", "flush", "commit"))


def _to_jsonable_payload(value: Any) -> Any:
    return jsonable_encoder(value)


async def _resolve_workflow_chapter_id(
    session: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
) -> Optional[UUID]:
    if chapter_id is None:
        return None
    chapter = await get_owned_chapter(
        session,
        chapter_id,
        user_id,
    )
    if chapter.project_id != project_id:
        raise AppError(
            code="story_engine.chapter_project_mismatch",
            message="当前章节不属于这个项目，暂时不能挂到这次流程里。",
            status_code=400,
        )
    return chapter.id


def _resolve_workflow_task_type(workflow_type: str) -> str:
    return _WORKFLOW_TASK_TYPE_MAP.get(workflow_type, f"story_engine.{workflow_type}")


def _build_workflow_task_base_result(
    *,
    workflow_id: str,
    workflow_type: str,
    workflow_status: str,
    chapter_number: Optional[int],
    chapter_title: Optional[str],
    branch_id: Optional[UUID],
    workflow_timeline: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "workflow_status": workflow_status,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": str(branch_id) if branch_id is not None else None,
        "workflow_timeline": _to_jsonable_payload(workflow_timeline or []),
    }


def _resolve_workflow_task_message(
    workflow_event: Optional[dict[str, Any]],
    *,
    fallback: Optional[str] = None,
) -> Optional[str]:
    if isinstance(workflow_event, dict):
        message = str(workflow_event.get("message") or "").strip()
        if message:
            return message
        label = str(workflow_event.get("label") or "").strip()
        if label:
            return label
    return str(fallback or "").strip() or None


def _resolve_workflow_task_progress(
    workflow_type: str,
    workflow_event: Optional[dict[str, Any]],
) -> int:
    if not isinstance(workflow_event, dict):
        return 0

    stage = str(workflow_event.get("stage") or "").strip()
    if workflow_type == "realtime_guard":
        progress_map = {
            "guard_initialized": 15,
            "guardian_review": 55,
            "commercial_repair": 78,
            "guard_arbitration": 100,
        }
        return progress_map.get(stage, 0)

    if workflow_type == "chapter_stream":
        if stage == "stream_started":
            return 5
        if stage == "plan_prepared":
            return 12
        if stage == "paragraph_generated":
            paragraph_index = workflow_event.get("paragraph_index")
            paragraph_total = workflow_event.get("paragraph_total")
            if (
                isinstance(paragraph_index, int)
                and isinstance(paragraph_total, int)
                and paragraph_total > 0
            ):
                return min(92, 12 + round((paragraph_index / paragraph_total) * 76))
            return 45
        if stage == "stream_guard_paused":
            paragraph_index = workflow_event.get("paragraph_index")
            paragraph_total = workflow_event.get("paragraph_total")
            if (
                isinstance(paragraph_index, int)
                and isinstance(paragraph_total, int)
                and paragraph_total > 0
            ):
                return min(96, 18 + round((paragraph_index / paragraph_total) * 78))
            return 88
        if stage == "stream_completed":
            return 100
        return 0

    if workflow_type == "outline_stress_test":
        progress_map = {
            "outline_stress_started": 5,
            "outline_blueprint_prepared": 24,
            "guardian_review": 42,
            "commercial_review": 56,
            "logic_review": 70,
            "debate_patch_applied": 82,
            "outline_arbitration": 90,
            "outline_persisted": 96,
            "outline_stress_completed": 100,
        }
        return progress_map.get(stage, 0)

    if workflow_type == "bulk_import":
        progress_map = {
            "bulk_import_started": 5,
            "bulk_import_preflight_checked": 18,
            "bulk_import_replace_scope_prepared": 26,
            "bulk_import_world_rules": 38,
            "bulk_import_characters": 50,
            "bulk_import_foreshadows": 60,
            "bulk_import_items": 68,
            "bulk_import_timeline_events": 76,
            "bulk_import_outlines": 86,
            "bulk_import_chapter_summaries": 92,
            "bulk_import_model_preset_applied": 96,
            "bulk_import_completed": 100,
        }
        return progress_map.get(stage, 0)

    if workflow_type == "final_optimize":
        progress_map = {
            "final_optimize_started": 5,
            "review_round_started": 10,
            "guardian_review": 24,
            "logic_review": 36,
            "commercial_review": 48,
            "style_review": 60,
            "anchor_summary_prepared": 70,
            "final_arbitration": 78,
            "round_resolution": 82,
            "final_output_finalized": 88,
            "final_verify_concluded": 92,
            "kb_updates_normalized": 95,
            "chapter_summary_persisted": 98,
            "final_optimize_completed": 100,
        }
        return progress_map.get(stage, 0)

    return 0


def _build_workflow_task_event_payload(workflow_event: dict[str, Any]) -> dict[str, Any]:
    return {
        "workflow_key": "story_engine",
        "workflow_id": workflow_event.get("workflow_id"),
        "workflow_type": workflow_event.get("workflow_type"),
        "workflow_stage": workflow_event.get("stage"),
        "workflow_status": workflow_event.get("status"),
        "workflow_label": workflow_event.get("label"),
        "workflow_message": workflow_event.get("message"),
        "workflow_event": _to_jsonable_payload(workflow_event),
        "chapter_number": workflow_event.get("chapter_number"),
        "chapter_title": workflow_event.get("chapter_title"),
    }


async def _create_workflow_task_state(
    session: AsyncSession,
    *,
    workflow_id: str,
    workflow_type: str,
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    chapter_number: Optional[int],
    initial_message: str,
    initial_result: Optional[dict[str, Any]] = None,
) -> Optional[TaskState]:
    if not _supports_workflow_task_persistence(session):
        return None

    existing_task_run = None
    try:
        existing_task_run = await get_task_run_by_task_id(
            session,
            workflow_id,
            user_id=user_id,
        )
    except AttributeError:
        existing_task_run = None
    if existing_task_run is not None:
        task_state = TaskState.from_task_run(existing_task_run)
        next_result = dict(existing_task_run.result or {})
        next_result.update(_to_jsonable_payload(initial_result or {}))
        task_state.status = "running"
        task_state.progress = max(int(task_state.progress or 0), 5)
        task_state.message = initial_message
        task_state.result = next_result
        task_state.error = None
        task_state.project_id = project_id
        task_state.chapter_id = chapter_id
        task_state.chapter_number = chapter_number
        task_state_store.set(task_state)
        await update_task_run(
            session,
            task_state=task_state,
            commit=False,
        )
        await session.commit()
        return task_state

    task_state = TaskState(
        task_id=workflow_id,
        task_type=_resolve_workflow_task_type(workflow_type),
        status="running",
        progress=0,
        message=initial_message,
        result=_to_jsonable_payload(initial_result or {}),
        project_id=project_id,
        chapter_id=chapter_id,
        chapter_number=chapter_number,
    )
    task_state_store.set(task_state)
    await create_task_run(
        session,
        task_state=task_state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        commit=False,
    )
    await session.commit()
    return task_state


async def _persist_workflow_task_event(
    session: AsyncSession,
    *,
    task_state: Optional[TaskState],
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    workflow_type: str,
    workflow_event: dict[str, Any],
    result_patch: Optional[dict[str, Any]] = None,
    finalize: bool = False,
    failed: bool = False,
    error: Optional[str] = None,
) -> None:
    if task_state is None or not _supports_workflow_task_persistence(session):
        return

    next_result = dict(task_state.result or {})
    if result_patch:
        next_result.update(_to_jsonable_payload(result_patch))
    next_result["workflow_status"] = str(workflow_event.get("status") or "").strip() or None
    task_state.result = next_result
    task_state.message = _resolve_workflow_task_message(
        workflow_event,
        fallback=task_state.message,
    )
    task_state.progress = max(
        int(task_state.progress or 0),
        _resolve_workflow_task_progress(workflow_type, workflow_event),
    )
    if failed:
        task_state.status = "failed"
        task_state.error = error
    elif finalize:
        task_state.status = "succeeded"
        task_state.progress = 100
        task_state.error = None
    else:
        task_state.status = "running"

    task_state_store.set(task_state)
    await update_task_run(
        session,
        task_state=task_state,
        commit=False,
    )
    await create_task_event(
        session,
        task_state=task_state,
        event_type=str(workflow_event.get("stage") or "workflow_event"),
        payload=_build_workflow_task_event_payload(workflow_event),
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        commit=False,
    )
    await session.commit()


async def _persist_workflow_task_failure(
    session: AsyncSession,
    *,
    task_state: Optional[TaskState],
    project_id: UUID,
    user_id: UUID,
    chapter_id: Optional[UUID],
    workflow_id: str,
    workflow_type: str,
    chapter_number: Optional[int],
    chapter_title: Optional[str],
    branch_id: Optional[UUID],
    error: Exception,
    workflow_timeline: Optional[list[dict[str, Any]]] = None,
) -> None:
    if task_state is None or not _supports_workflow_task_persistence(session):
        return

    failure_event = {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "sequence": len(workflow_timeline or []) + 1,
        "stage": "workflow_failed",
        "status": "failed",
        "label": "流程执行失败",
        "message": str(error),
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": branch_id,
        "round_number": None,
        "paragraph_index": None,
        "paragraph_total": None,
        "agent_keys": [],
        "details": {
            "error_type": error.__class__.__name__,
        },
        "emitted_at": _utcnow(),
    }
    next_timeline = list(workflow_timeline or [])
    next_timeline.append(failure_event)
    await _persist_workflow_task_event(
        session,
        task_state=task_state,
        project_id=project_id,
        user_id=user_id,
        chapter_id=chapter_id,
        workflow_type=workflow_type,
        workflow_event=failure_event,
        result_patch={
            "workflow_status": "failed",
            "workflow_timeline": next_timeline,
        },
        finalize=False,
        failed=True,
        error=str(error),
    )


def _append_workflow_event(
    timeline: list[dict[str, Any]],
    *,
    workflow_id: str,
    workflow_type: str,
    stage: str,
    status: str,
    label: str,
    message: Optional[str] = None,
    chapter_number: Optional[int] = None,
    chapter_title: Optional[str] = None,
    branch_id: Optional[UUID] = None,
    round_number: Optional[int] = None,
    paragraph_index: Optional[int] = None,
    paragraph_total: Optional[int] = None,
    agent_keys: Optional[list[str]] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    event = {
        "workflow_id": workflow_id,
        "workflow_type": workflow_type,
        "sequence": len(timeline) + 1,
        "stage": stage,
        "status": status,
        "label": label,
        "message": message,
        "chapter_number": chapter_number,
        "chapter_title": chapter_title,
        "branch_id": branch_id,
        "round_number": round_number,
        "paragraph_index": paragraph_index,
        "paragraph_total": paragraph_total,
        "agent_keys": list(agent_keys or []),
        "details": dict(details or {}),
        "emitted_at": _utcnow(),
    }
    timeline.append(event)
    return event


def _clone_workflow_timeline(timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in timeline]


def _build_report_workflow_details(report: dict[str, Any]) -> dict[str, Any]:
    raw_output = dict(report.get("raw_output") or {})
    issues = list(report.get("issues") or [])
    return {
        "summary": str(report.get("summary") or "").strip() or None,
        "issue_count": len(issues),
        "issue_titles": [
            str(item.get("title") or "").strip()
            for item in issues[:3]
            if str(item.get("title") or "").strip()
        ],
        "proposed_action_count": len(report.get("proposed_actions") or []),
        "provider": raw_output.get("provider"),
        "model": raw_output.get("model"),
        "used_fallback": raw_output.get("used_fallback"),
    }


def _build_anchor_workflow_details(anchor_payload: dict[str, Any]) -> dict[str, Any]:
    chapter_summary = dict(anchor_payload.get("chapter_summary") or {})
    kb_updates = list(anchor_payload.get("kb_updates") or [])
    return {
        "summary_excerpt": _truncate_deliberation_text(chapter_summary.get("content"), 120),
        "core_progress_count": len(chapter_summary.get("core_progress") or []),
        "kb_update_count": len(kb_updates),
        "kb_update_titles": [
            str(item.get("title") or item.get("name") or item.get("content") or "").strip()
            for item in kb_updates[:3]
            if str(item.get("title") or item.get("name") or item.get("content") or "").strip()
        ],
    }


def _truncate_deliberation_text(text: Any, limit: int = 96) -> str:
    value = str(text or "") if text is not None else ""
    if len(value) <= limit:
        return value
    return value[:limit] + "..."


def _format_deliberation_actor_label(report: dict[str, Any]) -> str:
    agent_key = str(report.get("agent_key") or report.get("source") or "").strip()
    if agent_key:
        return agent_key
    summary = str(report.get("summary") or "").strip()
    if summary:
        return summary.split("，")[0].split(",")[0][:16]
    return "unknown"


def _build_deliberation_entry_from_report(
    report: dict[str, Any],
    *,
    round_number: Optional[int] = None,
) -> dict[str, Any]:
    issues = list(report.get("issues") or [])
    blocking_count = sum(
        1
        for issue in issues
        if str(issue.get("severity") or "").strip().lower() in {"critical", "high"}
    )
    return {
        "actor": _format_deliberation_actor_label(report),
        "round_number": round_number,
        "summary": str(report.get("summary") or "").strip() or None,
        "issue_count": len(issues),
        "blocking_issue_count": blocking_count,
        "action_count": len(list(report.get("proposed_actions") or [])),
        "raw_output": dict(report.get("raw_output") or {}),
    }


def _merge_reports(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged_issues = _merge_issue_lists(
        list(primary.get("issues") or []),
        list(fallback.get("issues") or []),
    )
    merged_actions = _merge_action_lists(
        list(primary.get("proposed_actions") or []),
        list(fallback.get("proposed_actions") or []),
    )
    summary = primary.get("summary") or fallback.get("summary") or ""
    return {
        **fallback,
        **primary,
        "summary": summary,
        "issues": merged_issues,
        "proposed_actions": merged_actions,
    }


def _merge_issue_lists(*issue_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for group in issue_groups:
        for item in group:
            title = str(item.get("title") or "").strip()
            detail = str(item.get("detail") or "").strip()
            if not title or not detail:
                continue
            key = (title, detail)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)
    return merged


def _merge_action_lists(*action_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in action_groups:
        for item in group:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            merged.append(text)
    return merged


def _with_overridden_role_route(
    model_routing: Optional[dict[str, dict[str, Any]]],
    *,
    role_key: str,
    model: str,
    reasoning_effort: str,
) -> dict[str, dict[str, Any]]:
    routing = {
        key: dict(value)
        for key, value in (model_routing or {}).items()
        if isinstance(value, dict)
    }
    routing[role_key] = {
        "model": model,
        "reasoning_effort": reasoning_effort,
    }
    return routing


def _issue_title_signature(issue: dict[str, Any]) -> str:
    return str(issue.get("title") or "").strip().lower()


def _blocking_issue_count(issues: list[dict[str, Any]]) -> int:
    return sum(
        1
        for item in issues
        if str(item.get("severity") or "").strip().lower() in {"critical", "high"}
    )


def _guardian_reports_disagree(
    primary_report: dict[str, Any],
    shadow_report: dict[str, Any],
) -> bool:
    primary_issues = list(primary_report.get("issues") or [])
    shadow_issues = list(shadow_report.get("issues") or [])
    if bool(primary_issues) != bool(shadow_issues):
        return True

    primary_blocking = _blocking_issue_count(primary_issues)
    shadow_blocking = _blocking_issue_count(shadow_issues)
    if primary_blocking != shadow_blocking:
        return True

    primary_titles = {_issue_title_signature(item) for item in primary_issues if _issue_title_signature(item)}
    shadow_titles = {_issue_title_signature(item) for item in shadow_issues if _issue_title_signature(item)}
    if primary_titles and shadow_titles and primary_titles.isdisjoint(shadow_titles):
        return True
    return False


def _overlap_guardian_issues(
    primary_report: dict[str, Any],
    shadow_report: dict[str, Any],
) -> list[dict[str, Any]]:
    shadow_titles = {
        _issue_title_signature(item)
        for item in shadow_report.get("issues") or []
        if _issue_title_signature(item)
    }
    overlap = [
        item
        for item in primary_report.get("issues") or []
        if _issue_title_signature(item) in shadow_titles
    ]
    return _merge_issue_lists(overlap)


def _select_guardian_shadow_route(
    *,
    model_routing: Optional[dict[str, dict[str, Any]]],
) -> Optional[dict[str, str]]:
    consensus_config = get_story_engine_guardian_consensus_config()
    if not consensus_config.get("enabled", True):
        return None

    primary_model = get_story_engine_role_model("guardian", model_routing)
    preferred_shadow_model = str(consensus_config.get("shadow_model") or "").strip()
    candidate_models = [
        preferred_shadow_model,
        "gemini-3.1-pro-preview",
        "gpt-5.4",
        "claude-opus-4-6",
    ]
    shadow_model = next(
        (item for item in candidate_models if item and item != primary_model),
        "",
    )
    if not shadow_model:
        return None
    return {
        "model": shadow_model,
        "reasoning_effort": str(
            consensus_config.get("shadow_reasoning_effort") or "high"
        ).strip()
        or "high",
    }


async def _run_guardian_consensus_report(
    *,
    task_name: str,
    task_goal: str,
    context: str,
    fallback_report: dict[str, Any],
    model_routing: Optional[dict[str, dict[str, Any]]],
    workflow_key: str,
    workflow_label: str,
) -> dict[str, Any]:
    consensus_config = get_story_engine_guardian_consensus_config()
    workflow_enabled = bool(consensus_config.get(f"{workflow_key}_enabled", True))
    shadow_route = (
        _select_guardian_shadow_route(model_routing=model_routing)
        if workflow_enabled
        else None
    )
    primary_model = get_story_engine_role_model("guardian", model_routing)

    primary_task = generate_story_agent_report(
        agent_key="guardian",
        task_name=task_name,
        task_goal=task_goal,
        context=context,
        fallback_report=fallback_report,
        model_routing=model_routing,
    )
    if shadow_route is None:
        primary_report = await primary_task
        primary_report["raw_output"] = {
            **dict(primary_report.get("raw_output") or {}),
            "guardian_consensus_mode": "single",
            "guardian_primary_model": primary_model,
        }
        return primary_report

    shadow_task = generate_story_agent_report(
        agent_key="guardian",
        task_name=f"{task_name}.shadow",
        task_goal=task_goal,
        context=context,
        fallback_report=fallback_report,
        model_routing=_with_overridden_role_route(
            model_routing,
            role_key="guardian",
            model=shadow_route["model"],
            reasoning_effort=shadow_route["reasoning_effort"],
        ),
    )
    primary_report, shadow_report = await asyncio.gather(primary_task, shadow_task)
    disagreement = _guardian_reports_disagree(primary_report, shadow_report)

    if not disagreement:
        return build_agent_report(
            "guardian",
            summary=f"双模型设定守护已完成交叉校验，{workflow_label}阶段结论一致。",
            issues=_merge_issue_lists(
                list(primary_report.get("issues") or []),
                list(shadow_report.get("issues") or []),
            ),
            proposed_actions=_merge_action_lists(
                list(primary_report.get("proposed_actions") or []),
                list(shadow_report.get("proposed_actions") or []),
            ),
            raw_output={
                "guardian_consensus_mode": "dual",
                "disagreement": False,
                "guardian_primary_model": primary_model,
                "guardian_shadow_model": shadow_route["model"],
                "primary_report": primary_report,
                "shadow_report": shadow_report,
            },
        )

    tiebreak_report = await generate_story_agent_report(
        agent_key="logic_debunker",
        task_name=f"{task_name}.tiebreak",
        task_goal=(
            f"当两个设定守护模型在{workflow_label}阶段意见不一致时，"
            "请作为第三方裁判，只保留真正会导致后续崩坏的设定/逻辑硬风险。"
        ),
        context=(
            f"{context}\n\n"
            f"Guardian主校验报告：{primary_report}\n"
            f"Guardian副校验报告：{shadow_report}\n"
            "请给出最终应保留的问题清单。"
        ),
        fallback_report=build_agent_report(
            "logic_debunker",
            summary="双模型守护存在分歧，已执行第三方复核。",
            issues=[],
            proposed_actions=["只保留真正会导致后续崩坏的风险。"],
        ),
        model_routing=model_routing,
    )
    consensus_issues = _merge_issue_lists(
        _overlap_guardian_issues(primary_report, shadow_report),
        list(tiebreak_report.get("issues") or []),
    )
    consensus_actions = _merge_action_lists(
        [
            str(item.get("suggestion") or "").strip()
            for item in consensus_issues
            if str(item.get("suggestion") or "").strip()
        ],
        list(tiebreak_report.get("proposed_actions") or []),
        list(primary_report.get("proposed_actions") or []),
        list(shadow_report.get("proposed_actions") or []),
    )
    return build_agent_report(
        "guardian",
        summary=(
            f"双模型设定守护在{workflow_label}阶段出现分歧，已由逻辑挑刺复核并收敛结论。"
            if consensus_issues
            else f"双模型设定守护在{workflow_label}阶段出现分歧，但第三方复核后未保留硬冲突。"
        ),
        issues=consensus_issues,
        proposed_actions=consensus_actions,
        raw_output={
            "guardian_consensus_mode": "dual",
            "disagreement": True,
            "guardian_primary_model": primary_model,
            "guardian_shadow_model": shadow_route["model"],
            "primary_report": primary_report,
            "shadow_report": shadow_report,
            "tiebreak_report": tiebreak_report,
        },
    )


async def _resolve_stream_outline_text(
    *,
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
    outline_id: Optional[UUID],
    current_outline: Optional[str],
) -> Optional[str]:
    if current_outline and current_outline.strip():
        return current_outline.strip()
    if outline_id is None:
        return None
    outline = await get_entity(
        session,
        project_id=project_id,
        user_id=user_id,
        entity_type="outlines",
        entity_id=outline_id,
    )
    return getattr(outline, "content", None)


def _build_stream_beats(
    outline_text: Optional[str],
    *,
    target_paragraph_count: int,
) -> list[str]:
    if outline_text:
        parts = [
            part.strip(" -\t")
            for part in re.split(r"[\n；;]+", outline_text)
            if part.strip()
        ]
    else:
        parts = []

    if len(parts) == 1:
        parts = [
            item.strip()
            for item in re.split(r"[。！？!?.]+", parts[0])
            if item.strip()
        ]

    fallback_beats = [
        "用当前局面的压迫感开场，把人物困境先立住。",
        "让主角在限制条件下做出第一个选择。",
        "把人物关系、代价或世界规则往前推进一步。",
        "兑现一个阶段性收获，再抬高新的风险。",
        "在结尾留一个会逼读者点下一章的钩子。",
    ]
    beats = parts[:target_paragraph_count]
    for beat in fallback_beats:
        if len(beats) >= target_paragraph_count:
            break
        beats.append(beat)
    return beats[:target_paragraph_count]


def _split_stream_paragraphs(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").strip()
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"\n\s*\n", normalized) if part.strip()]


def _join_stream_paragraphs(paragraphs: list[str]) -> str:
    return "\n\n".join(part.strip() for part in paragraphs if part.strip()).strip()


def _extract_latest_stream_paragraph(text: str) -> Optional[str]:
    paragraphs = _split_stream_paragraphs(text)
    return paragraphs[-1] if paragraphs else None


def _build_stream_pause_metadata(
    *,
    beats: list[str],
    paused_at_paragraph: int,
    paragraph_total: int,
    current_beat: Optional[str],
) -> dict[str, Any]:
    next_paragraph_index = min(paused_at_paragraph + 1, paragraph_total + 1)
    return {
        "status": "paused",
        "paused_at_paragraph": paused_at_paragraph,
        "next_paragraph_index": next_paragraph_index,
        "current_beat": current_beat,
        "remaining_beats": beats[paused_at_paragraph:],
        "rewritable_paragraph_index": paused_at_paragraph,
        "paragraph_total": paragraph_total,
    }


def _build_style_hint(style_sample: Optional[str]) -> dict[str, Any]:
    if not style_sample or not style_sample.strip():
        return {
            "sentence_rhythm": "medium",
            "tone": "稳中带压迫感",
            "dialogue_density": "medium",
        }

    normalized = style_sample.strip()
    sentence_count = max(
        1,
        normalized.count("。") + normalized.count("！") + normalized.count("？"),
    )
    avg_sentence_length = len(normalized) / sentence_count
    if avg_sentence_length < 18:
        rhythm = "fast"
    elif avg_sentence_length > 36:
        rhythm = "dense"
    else:
        rhythm = "medium"
    dialogue_density = "high" if "“" in normalized or "\"" in normalized else "low"
    return {
        "sentence_rhythm": rhythm,
        "tone": "贴近写手样文气口",
        "dialogue_density": dialogue_density,
    }


def _extract_stream_character_name(candidate: Any) -> str:
    if isinstance(candidate, dict):
        return str(candidate.get("name") or "").strip()
    return str(getattr(candidate, "name", "") or "").strip()


def _pick_stream_character_name(
    characters: list[Any],
    *,
    preferred_markers: tuple[str, ...],
    excluded_names: Optional[set[str]] = None,
) -> Optional[str]:
    excluded_names = excluded_names or set()
    normalized: list[str] = [
        name
        for name in (_extract_stream_character_name(item) for item in characters)
        if name and name not in excluded_names
    ]
    for marker in preferred_markers:
        for name in normalized:
            if marker in name:
                return name
    return normalized[0] if normalized else None


def _build_stream_beat_sentence(beat: str, *, stage: str) -> str:
    normalized = re.sub(r"\s+", " ", str(beat or "").strip())
    normalized = normalized.rstrip("。！？；，,. ")
    if not normalized:
        normalized = "把局面继续往前推一步"

    if stage == "opening":
        if normalized.startswith("先"):
            return f"眼下第一步得{normalized}。"
        if normalized.startswith("用"):
            return f"眼下只能先{normalized}。"
        return f"眼下最要紧的，就是{normalized}。"

    if stage == "ending":
        if normalized.startswith("把"):
            return f"可这一线喘息还没落稳，接下来还得{normalized}。"
        if normalized.startswith("让"):
            return f"可这一线喘息还没落稳，更大的麻烦已经逼着他们去{normalized[1:]}。"
        return f"可这一线喘息还没落稳，{normalized}的余波就已经把下一层麻烦顶了上来。"

    if normalized.startswith("让"):
        return f"眼下最难的，就是{normalized}。"
    if normalized.startswith("把"):
        return f"真正决定走向的，是能不能{normalized}。"
    if normalized.startswith("用"):
        return f"眼下只能先{normalized}。"
    return f"这一步最要紧的，就是{normalized}。"


def _build_stream_context(
    *,
    workspace: dict[str, Any],
    recent_chapters: list[str],
    chapter_number: int,
    chapter_title: Optional[str],
    social_topology: Optional[dict[str, Any]] = None,
    causal_context: Optional[dict[str, Any]] = None,
    open_threads: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    characters = workspace.get("characters", [])
    items = workspace.get("items", [])
    world_rules = workspace.get("world_rules", [])
    foreshadows = workspace.get("foreshadows", [])
    lead_name = _pick_stream_character_name(
        characters,
        preferred_markers=("主角", "男主", "女主", "主人公"),
    ) or "主角"
    foil_name = _pick_stream_character_name(
        characters,
        preferred_markers=("宿敌", "反派", "对手", "敌", "boss"),
        excluded_names={lead_name},
    ) or "对手"
    support_name = _pick_stream_character_name(
        characters,
        preferred_markers=("盟友", "伙伴", "同伴", "朋友", "师父"),
        excluded_names={lead_name, foil_name},
    ) or "盟友"

    return {
        "chapter_label": chapter_title or f"第{chapter_number}章",
        "lead_name": lead_name,
        "foil_name": foil_name,
        "support_name": support_name,
        "anchor_item": items[0].name if items else "关键线索",
        "world_rule": world_rules[0].rule_name if world_rules else "代价规则",
        "foreshadow_hint": foreshadows[0].content if foreshadows else "一个尚未解释清楚的异常细节",
        "recent_context": " ".join(item.strip() for item in recent_chapters[-2:] if item.strip())[:get_settings().summary_truncate_length],
        "social_topology": social_topology if isinstance(social_topology, dict) else {},
        "causal_context": causal_context if isinstance(causal_context, dict) else {},
        "open_threads": open_threads if isinstance(open_threads, list) else [],
    }


async def _load_stream_enrichment(
    session: AsyncSession,
    *,
    project_id: UUID,
    chapter_number: int,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    open_threads_payload: list[dict[str, Any]] = []
    social_topology_payload: dict[str, Any] = {}
    causal_context_payload: dict[str, Any] = {}

    try:
        open_threads = await foreshadowing_lifecycle_service.get_active_threads(
            session,
            project_id=project_id,
            chapter_num=chapter_number,
            lookback=10,
        )
        open_threads_payload = [
            {
                "id": str(item.id),
                "planted_chapter": item.planted_chapter,
                "entity_ref": item.entity_ref,
                "entity_type": item.entity_type,
                "potential_tags": item.potential_tags or [],
                "status": item.status,
                "payoff_priority": item.payoff_priority,
            }
            for item in open_threads
        ]
    except (ConnectionError, TimeoutError, OSError) as exc:
        from core.logging import get_logger
        get_logger(__name__).warning(
            "enrichment_open_threads_degraded",
            extra={"error": str(exc), "project_id": str(project_id)},
        )
        open_threads_payload = []

    try:
        social_topology = await social_topology_service.build_social_topology(
            session,
            project_id=project_id,
        )
        social_topology_payload = {
            "centrality_scores": social_topology.centrality_scores or {},
            "influence_graph": social_topology.influence_graph or {},
            "social_dynamics": social_topology.social_dynamics or {},
            "cluster_data": social_topology.cluster_data or {},
        }
    except (ConnectionError, TimeoutError, OSError) as exc:
        from core.logging import get_logger
        get_logger(__name__).warning(
            "enrichment_social_topology_degraded",
            extra={"error": str(exc), "project_id": str(project_id)},
        )
        social_topology_payload = {}

    try:
        if chapter_number > 1:
            causal_paths = await neo4j_service.query_causal_paths(
                project_id,
                from_chapter=chapter_number - 1,
                to_chapter=chapter_number,
                max_hops=get_settings().stream_enrichment_max_hops,
            )
            if causal_paths:
                causal_context_payload["causal_paths"] = causal_paths
        influence = await neo4j_service.compute_character_influence(project_id)
        if influence:
            causal_context_payload["character_influence"] = influence
    except (ConnectionError, TimeoutError, OSError) as exc:
        from core.logging import get_logger
        get_logger(__name__).warning(
            "enrichment_causal_context_degraded",
            extra={"error": str(exc), "project_id": str(project_id)},
        )
        causal_context_payload = {}

    return open_threads_payload, social_topology_payload, causal_context_payload


async def _load_legacy_checkpoint_resume(
    session: AsyncSession,
    *,
    chapter_id: UUID | None,
    existing_text: str,
    resume_from_paragraph: Optional[int],
) -> tuple[str, Optional[int], dict[str, Any] | None]:
    if chapter_id is None:
        return existing_text, resume_from_paragraph, None
    if existing_text.strip() or resume_from_paragraph is not None:
        return existing_text, resume_from_paragraph, None

    checkpoint_service = CheckpointService(session)
    checkpoint = await checkpoint_service.get_latest_generation_checkpoint(chapter_id)
    if checkpoint is None or not checkpoint_service.can_resume(checkpoint):
        return existing_text, resume_from_paragraph, None

    generated_content = str(getattr(checkpoint, "generated_content", "") or "").strip()
    if not generated_content:
        return existing_text, resume_from_paragraph, None

    next_paragraph = int(getattr(checkpoint, "segments_completed", 0) or 0) + 1
    metadata = {
        "checkpoint_id": str(checkpoint.id),
        "checkpoint_version_number": checkpoint.chapter_version_number,
        "segments_completed": checkpoint.segments_completed,
        "segments_total": checkpoint.segments_total,
        "progress": checkpoint.progress,
        "source": "legacy_generation_checkpoint",
    }
    return generated_content, next_paragraph, metadata


def _compose_stream_paragraph(
    *,
    beat: str,
    paragraph_index: int,
    paragraph_total: int,
    target_word_count: int,
    existing_text: str,
    style_hint: dict[str, Any],
    stream_context: dict[str, Any],
    repair_instruction: Optional[str] = None,
) -> str:
    lead_name = stream_context["lead_name"]
    foil_name = stream_context["foil_name"]
    support_name = stream_context["support_name"]
    anchor_item = stream_context["anchor_item"]
    world_rule = stream_context["world_rule"]
    foreshadow_hint = stream_context["foreshadow_hint"]
    recent_context = stream_context["recent_context"]
    chapter_label = stream_context["chapter_label"]
    target_length = max(160, min(260, target_word_count // max(1, paragraph_total)))
    max_length = max(240, min(360, target_length + 90))

    sentences: list[str] = []
    seen_sentences: set[str] = set()

    def append_sentence(text: str) -> None:
        normalized = str(text or "").strip()
        if not normalized or normalized in seen_sentences:
            return
        seen_sentences.add(normalized)
        sentences.append(normalized)

    if paragraph_index == 1 and not existing_text.strip():
        append_sentence(f"{chapter_label}刚起势，{lead_name}就被新的局面推到了必须开口、也必须站队的位置。")
        append_sentence(_build_stream_beat_sentence(beat, stage="opening"))
        append_sentence(f"{foil_name}把试探压得很轻，却又轻得刚好能逼出{lead_name}最不能退的那一步。")
        append_sentence(f"{anchor_item}偏偏在这个节骨眼上被重新牵出来，让这场冲突一下子带上了旧账翻卷的味道。")
    elif paragraph_index >= paragraph_total:
        append_sentence(f"{lead_name}硬是把最危险的一步撑了过去，连{support_name}都看出了局势被扳回了一线。")
        append_sentence(_build_stream_beat_sentence(beat, stage="ending"))
        append_sentence(f"{foreshadow_hint}在这一刻冒了头，像有人故意把更大的风暴先掀开了一角。")
    else:
        append_sentence(f"{lead_name}没有立刻出手，而是先把眼前能踩和不能踩的地方在心里过了一遍。")
        append_sentence(_build_stream_beat_sentence(beat, stage="middle"))
        append_sentence(f"{foil_name}故意把局面让出一线松动，看着像给机会，实际上是在逼{lead_name}自己挑代价。")

    append_sentence(f"{lead_name}比谁都清楚，只要碰穿《{world_rule}》这条线，眼前占到的便宜迟早都得连本带利吐回来。")

    if repair_instruction:
        append_sentence(f"更棘手的是，{repair_instruction}这道口子必须在这一段里补平，不然前后的设定都会发虚。")
    if recent_context:
        append_sentence(f"前面埋下的余波还没散，{recent_context[:48]}像倒刺一样扎在这次推进里，让人怎么都不可能轻松落脚。")

    if style_hint.get("dialogue_density") == "high":
        append_sentence(f"“你现在收手，还来得及。”{foil_name}语气平得近乎冷，可那份平静本身就像是在逼人低头。")

    rhythm = style_hint.get("sentence_rhythm")
    if rhythm == "fast":
        rhythm_pool = [
            f"{lead_name}没再给自己犹豫的空当，抬手、试探、确认、逼近，动作一环压着一环。",
            f"局势根本不给人回头看的一秒空闲，所有选择都得在心跳落下之前做完。",
        ]
    elif rhythm == "dense":
        rhythm_pool = [
            f"{lead_name}甚至把每一步可能带出的后果都提前想了一遍，确认这条路虽然险，却仍旧比僵在原地更值得赌。",
            f"他不是在碰运气，而是在拿自己能承受的代价，去换这一线必须抢下来的主动。",
        ]
    else:
        rhythm_pool = [
            f"{lead_name}把呼吸压稳，先让局势顺着自己的判断走，再决定哪里该硬、哪里该藏。",
            f"这一回他没打算靠侥幸过关，而是准备把每个动作都落在能解释得通的因果上。",
        ]

    general_pool = [
        f"{support_name}没有插手，只在一旁盯着{lead_name}的反应，因为谁都知道这一步一旦走错，后面整章都会变味。",
        f"{anchor_item}在视线里安静得过分，反倒显得像一枚还没被真正引爆的钉子，随时可能把局面重新钉死。",
        f"{lead_name}表面上仍旧稳着，指节却已经一点点收紧，显然这一步要付的代价并不比旁人看见的少。",
        f"真正麻烦的从来不是眼前这一刀，而是这一刀落下去以后，会不会把后面所有退路一起斩断。",
    ]

    for extra_sentence in rhythm_pool + general_pool:
        if len("".join(sentences)) >= target_length:
            break
        append_sentence(extra_sentence)

    paragraph = "".join(sentences)
    if len(paragraph) < target_length:
        append_sentence(
            f"所以{lead_name}最后还是把那口气咽了回去，宁可把动作放慢半拍，也要确保这一步既能推进，又不会把后面的逻辑写塌。"
        )
        paragraph = "".join(sentences)

    return paragraph[:max_length]


def _read_story_knowledge_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)


def _read_story_knowledge_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {}


def _serialize_story_knowledge_item(item: Any) -> dict[str, Any]:
    d = _read_story_knowledge_dict(item)
    return {k: v for k, v in d.items() if v is not None}


def _story_knowledge_json_snippet(payload: Any, limit: int = 1200) -> str:
    text = json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else ""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _compact_prompt_text(text: str, limit: int = 5000) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + "\n\n... (中间内容已省略以控制 prompt 长度) ...\n\n" + text[-half:]


def _build_agent_report_prompt_snapshot(
    report: dict[str, Any],
    max_issues: int = 5,
) -> str:
    lines: list[str] = []
    source = str(report.get("agent_key") or report.get("source") or "?").strip()
    summary = str(report.get("summary") or "").strip()
    if summary:
        lines.append(f"[{source}] {summary}")
    issues = list(report.get("issues") or [])[:max_issues]
    for idx, issue in enumerate(issues, 1):
        severity = str(issue.get("severity") or "?").strip()
        title = str(issue.get("title") or "?").strip()
        detail = str(issue.get("detail") or "").strip()
        lines.append(f"  {idx}. [{severity}] {title}: {detail[:200]}")
    actions = list(report.get("proposed_actions") or [])[:3]
    if actions:
        lines.append("  建议:")
        for action in actions:
            lines.append(f"    - {str(action).strip()}")
    return "\n".join(lines)


def _count_blocking_alerts(alerts: list[dict[str, Any]]) -> int:
    return sum(
        1
        for alert in alerts
        if str(alert.get("severity") or "").strip().lower() in {"critical", "high"}
    )


def _apply_revision_actions(
    *,
    draft_text: str,
    issues: list[dict[str, Any]],
) -> str:
    revised = draft_text.strip()
    issue_titles = Counter(issue["title"] for issue in issues)
    if issue_titles.get("章末钩子偏弱"):
        revised = revised.rstrip("。！？\n") + "\n\n可他还没来得及松口气，就意识到真正的代价现在才开始。"
    if issue_titles.get("章节层次偏薄"):
        revised += "\n\n他短暂地停了一下，把刚才的胜负重新在脑子里过了一遍，终于明白自己到底赌上了什么。"
    return revised


def _get_outline_debate_max_rounds() -> int:
    settings = get_settings()
    return max(1, settings.story_engine_outline_max_debate_rounds)


def _get_final_verify_max_rounds() -> int:
    settings = get_settings()
    return max(1, settings.story_engine_final_verify_max_rounds)


def _build_outline_outline_counts(outline_draft: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        "level_1_count": len(outline_draft.get("level_1") or []),
        "level_2_count": len(outline_draft.get("level_2") or []),
        "level_3_count": len(outline_draft.get("level_3") or []),
    }


def _build_outline_kb_counts(initial_kb: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        "character_count": len(initial_kb.get("characters") or []),
        "foreshadow_count": len(initial_kb.get("foreshadows") or []),
        "item_count": len(initial_kb.get("items") or []),
        "world_rule_count": len(initial_kb.get("world_rules") or []),
        "timeline_event_count": len(initial_kb.get("timeline_events") or []),
    }