from __future__ import annotations

import asyncio
from typing import Any
from typing import Optional
from uuid import UUID, uuid4

from db.session import AsyncSessionLocal
from services.generation_service import run_generation_pipeline
from services.task_service import create_task_event, create_task_run, update_task_run
from tasks.celery_app import celery_app
from tasks.schemas import TaskState
from tasks.state_store import task_state_store


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
            },
            chapter_id=UUID(chapter_id),
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()
    return task_state


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


def mark_task_failed(task_id: str, error: str) -> TaskState:
    state = _require_task(task_id)
    state.status = "failed"
    state.error = error
    state.message = "Generation pipeline failed."
    return task_state_store.set(state)


def mark_task_succeeded(task_id: str, result: dict[str, Any]) -> TaskState:
    state = _require_task(task_id)
    state.status = "succeeded"
    state.progress = 100
    state.message = "Generation pipeline completed."
    state.result = result
    state.error = None
    return task_state_store.set(state)


async def process_generation_task(
    *,
    task_id: str,
    chapter_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
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
            state = mark_task_failed(task_id, str(exc))
            await persist_task_state(
                state,
                chapter_id=chapter_id,
                project_id=project_id,
                user_id=user_id,
                event_type="failed",
                event_payload={
                    "phase": "agent_pipeline",
                    "error_type": exc.__class__.__name__,
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


@celery_app.task(name="chapter_generation.process")
def process_generation_task_celery(
    task_id: str,
    chapter_id: str,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    state = asyncio.run(
        process_generation_task(
            task_id=task_id,
            chapter_id=chapter_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return state.model_dump()


def _require_task(task_id: str) -> TaskState:
    state = task_state_store.get(task_id)
    if state is None:
        raise KeyError(f"Task {task_id} not found")
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
    revision_plan = result.get("revision_plan")
    approval = result.get("approval")
    agent_trace = result.get("agent_trace")

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

    if isinstance(revision_plan, dict):
        priorities = revision_plan.get("priorities")
        focus_dimensions = revision_plan.get("focus_dimensions")
        if isinstance(priorities, list):
            payload["revision_plan_steps"] = len(priorities)
        if isinstance(focus_dimensions, list):
            payload["revision_focus_dimensions"] = focus_dimensions

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
