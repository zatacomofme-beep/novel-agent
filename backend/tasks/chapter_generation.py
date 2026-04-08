from __future__ import annotations

import asyncio
from typing import Any
from typing import Optional
from uuid import UUID, uuid4

from db.session import AsyncSessionLocal
from services.legacy_generation_service import (
    StoryBibleIntegrityError,
    run_generation_pipeline,
)
from services.task_service import (
    create_task_event,
    create_task_run,
    get_task_run_by_task_id,
    update_task_run,
)
from tasks.celery_app import celery_app
from tasks.schemas import TaskState
from tasks.state_store import task_state_store


LEGACY_CHAPTER_GENERATION_METADATA = {
    "legacy_entrypoint": True,
    "entrypoint_surface": "legacy_chapter_pipeline",
    "preferred_surface": "story_engine",
}


async def enqueue_chapter_generation_task(
    chapter_id: str,
    user_id: str,
    project_id: str,
    payload: Optional[dict] = None,
) -> TaskState:
    task_state = TaskState(
        task_id=str(uuid4()),
        task_type="chapter_generation",
        status="queued",
        progress=0,
        message="Generation pipeline bootstrap task created.",
        result={
            "chapter_id": chapter_id,
            "user_id": user_id,
            "project_id": project_id,
            "generation_payload": payload or {},
            **LEGACY_CHAPTER_GENERATION_METADATA,
        },
    )
    task_state_store.set(task_state)
    async with AsyncSessionLocal() as session:
        await create_task_run(
            session,
            task_state=task_state,
            chapter_id=UUID(chapter_id),
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await create_task_event(
            session,
            task_state=task_state,
            event_type="queued",
            payload={
                "phase": "enqueue",
                "generation_payload": payload or {},
                **LEGACY_CHAPTER_GENERATION_METADATA,
            },
            chapter_id=UUID(chapter_id),
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()
    return task_state


def mark_task_dispatched(
    task_id: str,
    *,
    message: str,
    result_patch: Optional[dict[str, Any]] = None,
) -> TaskState:
    state = _require_task(task_id)
    state.message = message
    state.progress = max(state.progress, 5)
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return task_state_store.set(state)


def mark_task_running(task_id: str, message: str) -> TaskState:
    state = _require_task(task_id)
    state.status = "running"
    state.message = message
    state.progress = max(state.progress, 10)
    return task_state_store.set(state)


def mark_task_progress(
    task_id: str,
    *,
    progress: int,
    message: str,
    result_patch: Optional[dict[str, Any]] = None,
) -> TaskState:
    state = _require_task(task_id)
    state.progress = progress
    state.message = message
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return task_state_store.set(state)


def mark_task_failed(
    task_id: str,
    error: str,
    *,
    result_patch: Optional[dict[str, Any]] = None,
) -> TaskState:
    state = _require_task(task_id)
    state.status = "failed"
    state.error = error
    state.message = "Generation pipeline failed."
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return task_state_store.set(state)


def mark_task_succeeded(task_id: str, result: dict[str, Any]) -> TaskState:
    state = _require_task(task_id)
    state.status = "succeeded"
    state.progress = 100
    state.message = "Generation pipeline completed."
    state.result = {
        **result,
        **LEGACY_CHAPTER_GENERATION_METADATA,
    }
    state.error = None
    return task_state_store.set(state)


async def process_generation_task(
    *,
    task_id: str,
    chapter_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    await hydrate_task_state(task_id)
    state = mark_task_running(task_id, "Loading chapter and Story Bible context.")
    await persist_task_state(
        state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        event_type="started",
        event_payload={"phase": "bootstrap"},
    )
    state = mark_task_progress(
        task_id,
        progress=20,
        message="Building generation payload.",
    )
    await persist_task_state(
        state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        event_type="payload_built",
        event_payload={"phase": "context"},
    )
    state = mark_task_progress(
        task_id,
        progress=45,
        message="Running coordinator, architect, writer and critic agents.",
    )
    await persist_task_state(
        state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        event_type="generation_started",
        event_payload={"phase": "agent_pipeline"},
    )

    async with AsyncSessionLocal() as session:
        try:
            result = await run_generation_pipeline(
                session,
                chapter_id=UUID(chapter_id),
                user_id=UUID(user_id),
                task_id=task_id,
            )
        except Exception as exc:  # pragma: no cover - error path still useful in runtime
            result_patch: dict[str, Any] | None = None
            failure_phase = "agent_pipeline"
            event_payload: dict[str, Any] = {
                "error_type": exc.__class__.__name__,
            }
            if isinstance(exc, StoryBibleIntegrityError):
                failure_phase = "story_bible_integrity"
                integrity_report = exc.report.model_dump(mode="json")
                result_patch = {
                    "story_bible_integrity_report": integrity_report,
                }
                event_payload.update(
                    {
                        "integrity_issue_count": integrity_report["issue_count"],
                        "integrity_blocking_issue_count": integrity_report["blocking_issue_count"],
                        "integrity_plugins": sorted(
                            integrity_report["plugin_breakdown"].keys()
                        ),
                    }
                )
            state = mark_task_failed(
                task_id,
                str(exc),
                result_patch=result_patch,
            )
            await persist_task_state(
                state,
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=user_id,
                event_type="failed",
                event_payload={
                    "phase": failure_phase,
                    **event_payload,
                },
            )
            return state

    state = mark_task_progress(
        task_id,
        progress=85,
        message="Persisting generated content and evaluation result.",
        result_patch={
            "outline": result.get("outline"),
            "revised": result.get("revised"),
        },
    )
    await persist_task_state(
        state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        event_type="outputs_persisting",
        event_payload=_build_result_event_payload(result),
    )
    state = mark_task_succeeded(task_id, result)
    await persist_task_state(
        state,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
        event_type="succeeded",
        event_payload=_build_result_event_payload(result),
    )
    return state


async def dispatch_generation_task(
    *,
    task_id: str,
    chapter_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    try:
        process_generation_task_celery.apply_async(
            kwargs={
                "task_id": task_id,
                "chapter_id": chapter_id,
                "project_id": project_id,
                "user_id": user_id,
            },
            task_id=task_id,
        )
        state = mark_task_dispatched(
            task_id,
            message="Generation task queued for Celery worker.",
            result_patch={"dispatch_strategy": "celery", "celery_task_id": task_id},
        )
        await persist_task_state(
            state,
            chapter_id=chapter_id,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "dispatch_strategy": "celery",
                "celery_task_id": task_id,
            },
        )
        return state
    except Exception as exc:  # pragma: no cover - depends on broker availability
        state = mark_task_dispatched(
            task_id,
            message="Celery dispatch unavailable; running in local async fallback.",
            result_patch={
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
            },
        )
        await persist_task_state(
            state,
            chapter_id=chapter_id,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
            },
        )
        asyncio.create_task(
            process_generation_task(
                task_id=task_id,
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=user_id,
            )
        )
        return state


@celery_app.task(
    name="chapter_generation.process",
    bind=True,
    max_retries=3,
    default_retry_delay=5,
    retry_backoff=2,
    retry_backoff_max=120,
    retry_jitter=True,
)
def process_generation_task_celery(
    self,
    task_id: str,
    chapter_id: str,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    import asyncio
    try:
        state = asyncio.run(
            process_generation_task(
                task_id=task_id,
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=user_id,
            )
        )
        return state.model_dump()
    except (ConnectionError, TimeoutError, OSError) as exc:
        from core.logging import get_logger
        logger = get_logger(__name__)
        logger.warning(
            "chapter_generation_retryable_error",
            extra={
                "task_id": task_id,
                "chapter_id": chapter_id,
                "error": str(exc),
                "retry_count": self.request.retries,
            },
        )
        raise self.retry(exc=exc, countdown=min(2 ** self.request.retries * 5, 120))
    except Exception as exc:
        raise


def _require_task(task_id: str) -> TaskState:
    state = task_state_store.get(task_id)
    if state is None:
        raise KeyError(f"Task {task_id} not found")
    return state


async def hydrate_task_state(task_id: str) -> TaskState:
    state = task_state_store.get(task_id)
    if state is not None:
        return state

    async with AsyncSessionLocal() as session:
        task_run = await get_task_run_by_task_id(session, task_id)

    if task_run is None:
        raise KeyError(f"Task {task_id} not found")

    state = TaskState.from_task_run(task_run)
    task_state_store.set(state)
    return state


async def persist_task_state(
    task_state: TaskState,
    *,
    chapter_id: str,
    project_id: str,
    user_id: str,
    event_type: str,
    event_payload: Optional[dict[str, Any]] = None,
) -> None:
    async with AsyncSessionLocal() as session:
        await update_task_run(
            session,
            task_state=task_state,
            commit=False,
        )
        await create_task_event(
            session,
            task_state=task_state,
            event_type=event_type,
            payload=event_payload,
            chapter_id=UUID(chapter_id),
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()


def _build_result_event_payload(result: dict[str, Any]) -> dict[str, Any]:
    evaluation = result.get("evaluation")
    context_bundle = result.get("context_bundle")
    initial_review = result.get("initial_review")
    final_review = result.get("final_review") or result.get("review")
    canon_report = result.get("canon_report") or result.get("final_canon_report")
    initial_canon_report = result.get("initial_canon_report")
    integrity_report = result.get("story_bible_integrity_report")
    revision_plan = result.get("revision_plan")
    approval = result.get("approval")
    agent_trace = result.get("agent_trace")
    truth_layer_context = result.get("truth_layer_context") or result.get("final_truth_layer_context")
    story_bible_followup_proposals = result.get("story_bible_followup_proposals")

    payload: dict[str, Any] = {
        "chapter_id": result.get("chapter_id"),
        "chapter_status": result.get("chapter_status"),
        "revised": result.get("revised"),
    }

    if isinstance(agent_trace, list):
        payload["agent_count"] = len(agent_trace)
        payload["agents"] = [
            str(item.get("agent"))
            for item in agent_trace
            if isinstance(item, dict) and item.get("agent")
        ]
        providers = []
        fallback_agents = []
        remote_error_types = []
        for item in agent_trace:
            if not isinstance(item, dict):
                continue
            generation = _extract_generation(item)
            if not generation:
                continue

            agent_name = str(item.get("agent") or "unknown")
            provider = generation.get("provider")
            if provider:
                providers.append(f"{agent_name}:{provider}")
            if generation.get("used_fallback"):
                fallback_agents.append(agent_name)

            metadata = generation.get("metadata")
            if isinstance(metadata, dict):
                remote_error = metadata.get("remote_error")
                if isinstance(remote_error, dict) and remote_error.get("error_type"):
                    remote_error_types.append(str(remote_error["error_type"]))

        if providers:
            payload["providers"] = providers
        if fallback_agents:
            payload["fallback_agents"] = fallback_agents
        if remote_error_types:
            payload["remote_error_types"] = sorted(set(remote_error_types))

    if isinstance(evaluation, dict):
        issues = evaluation.get("issues")
        payload["overall_score"] = evaluation.get("overall_score")
        payload["ai_taste_score"] = evaluation.get("ai_taste_score")
        if isinstance(issues, list):
            payload["issue_count"] = len(issues)

    if isinstance(initial_review, dict):
        initial_issues = initial_review.get("issues")
        payload["initial_needs_revision"] = initial_review.get("needs_revision")
        payload["initial_overall_score"] = initial_review.get("overall_score")
        if isinstance(initial_issues, list):
            payload["initial_issue_count"] = len(initial_issues)

    if isinstance(final_review, dict):
        final_issues = final_review.get("issues")
        payload["final_needs_revision"] = final_review.get("needs_revision")
        payload["final_overall_score"] = final_review.get("overall_score")
        if isinstance(final_issues, list):
            payload["final_issue_count"] = len(final_issues)

    if isinstance(initial_canon_report, dict):
        payload["initial_canon_issue_count"] = initial_canon_report.get("issue_count")
        payload["initial_canon_blocking_issue_count"] = initial_canon_report.get("blocking_issue_count")

    if isinstance(integrity_report, dict):
        payload["integrity_issue_count"] = integrity_report.get("issue_count")
        payload["integrity_blocking_issue_count"] = integrity_report.get("blocking_issue_count")
        plugin_breakdown = integrity_report.get("plugin_breakdown")
        if isinstance(plugin_breakdown, dict):
            payload["integrity_plugins"] = sorted(plugin_breakdown.keys())

    if isinstance(canon_report, dict):
        payload["canon_issue_count"] = canon_report.get("issue_count")
        payload["canon_blocking_issue_count"] = canon_report.get("blocking_issue_count")
        plugin_breakdown = canon_report.get("plugin_breakdown")
        referenced_entities = canon_report.get("referenced_entities")
        if isinstance(plugin_breakdown, dict):
            payload["canon_plugins"] = sorted(plugin_breakdown.keys())
        if isinstance(referenced_entities, list):
            payload["canon_referenced_entities"] = len(referenced_entities)

    if isinstance(revision_plan, dict):
        priorities = revision_plan.get("priorities")
        focus_dimensions = revision_plan.get("focus_dimensions")
        if isinstance(priorities, list):
            payload["revision_plan_steps"] = len(priorities)
        if isinstance(focus_dimensions, list):
            payload["revision_focus_dimensions"] = focus_dimensions

    if isinstance(truth_layer_context, dict):
        payload["truth_layer_status"] = truth_layer_context.get("status")
        blocking_sources = truth_layer_context.get("blocking_sources")
        if isinstance(blocking_sources, list):
            payload["truth_layer_blocking_sources"] = blocking_sources
        chapter_targets = truth_layer_context.get("chapter_revision_targets")
        if isinstance(chapter_targets, list):
            payload["truth_layer_chapter_target_count"] = len(chapter_targets)
        story_bible_followups = truth_layer_context.get("story_bible_followups")
        if isinstance(story_bible_followups, list):
            payload["truth_layer_story_bible_followup_count"] = len(story_bible_followups)

    if isinstance(story_bible_followup_proposals, list):
        payload["story_bible_followup_proposal_count"] = len(story_bible_followup_proposals)
        payload["story_bible_followup_trigger_types"] = [
            str(item.get("trigger_type"))
            for item in story_bible_followup_proposals
            if isinstance(item, dict) and item.get("trigger_type")
        ]

    if isinstance(approval, dict):
        payload["approved"] = approval.get("approved")
        payload["release_recommendation"] = approval.get("release_recommendation")
        payload["score_delta"] = approval.get("score_delta")
        blocking_issues = approval.get("blocking_issues")
        if isinstance(blocking_issues, list):
            payload["blocking_issue_count"] = len(blocking_issues)

    if isinstance(context_bundle, dict):
        retrieved_items = context_bundle.get("retrieved_items")
        retrieval_backends = context_bundle.get("retrieval_backends")
        payload["query"] = context_bundle.get("query")
        if isinstance(retrieved_items, list):
            payload["retrieval_items"] = len(retrieved_items)
        if isinstance(retrieval_backends, list):
            payload["retrieval_backends"] = retrieval_backends

    return {key: value for key, value in payload.items() if value is not None}


def _extract_generation(trace_item: dict[str, Any]) -> Optional[dict[str, Any]]:
    data = trace_item.get("data")
    if not isinstance(data, dict):
        return None

    generation = data.get("generation")
    if isinstance(generation, dict):
        return generation

    chapter_plan = data.get("chapter_plan")
    if isinstance(chapter_plan, dict):
        nested_generation = chapter_plan.get("generation")
        if isinstance(nested_generation, dict):
            return nested_generation

    return None
