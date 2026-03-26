from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Optional, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, ValidationError

from db.session import AsyncSessionLocal
from schemas.project import (
    CharacterGenerationRequest,
    FactionGenerationRequest,
    ItemGenerationRequest,
    LocationGenerationRequest,
    PlotThreadGenerationRequest,
)
from services.entity_generation_service import run_entity_generation_pipeline
from services.task_service import (
    create_task_event,
    create_task_run,
    get_task_run_by_task_id,
    update_task_run,
)
from tasks.celery_app import celery_app
from tasks.schemas import TaskState
from tasks.state_store import task_state_store


@dataclass(frozen=True)
class EntityGenerationConfig:
    generation_type: str
    task_type: str
    result_key: str
    request_model: Type[BaseModel]
    display_label: str


ENTITY_GENERATION_CONFIGS: dict[str, EntityGenerationConfig] = {
    "characters": EntityGenerationConfig(
        generation_type="characters",
        task_type="entity_generation.characters",
        result_key="characters",
        request_model=CharacterGenerationRequest,
        display_label="人物候选",
    ),
    "supporting": EntityGenerationConfig(
        generation_type="supporting",
        task_type="entity_generation.supporting",
        result_key="characters",
        request_model=CharacterGenerationRequest,
        display_label="配角候选",
    ),
    "items": EntityGenerationConfig(
        generation_type="items",
        task_type="entity_generation.items",
        result_key="items",
        request_model=ItemGenerationRequest,
        display_label="物品候选",
    ),
    "locations": EntityGenerationConfig(
        generation_type="locations",
        task_type="entity_generation.locations",
        result_key="locations",
        request_model=LocationGenerationRequest,
        display_label="地点候选",
    ),
    "factions": EntityGenerationConfig(
        generation_type="factions",
        task_type="entity_generation.factions",
        result_key="factions",
        request_model=FactionGenerationRequest,
        display_label="势力候选",
    ),
    "plot_threads": EntityGenerationConfig(
        generation_type="plot_threads",
        task_type="entity_generation.plot_threads",
        result_key="plot_threads",
        request_model=PlotThreadGenerationRequest,
        display_label="剧情线候选",
    ),
}


async def enqueue_entity_generation_task(
    project_id: str,
    user_id: str,
    generation_type: str,
    payload: dict[str, Any],
) -> TaskState:
    config = _get_entity_generation_config(generation_type)
    requested_count = payload.get("count") if isinstance(payload, dict) else None
    task_state = TaskState(
        task_id=str(uuid4()),
        task_type=config.task_type,
        status="queued",
        progress=0,
        message=f"已进入队列，准备补一批{config.display_label}。",
        result={
            "project_id": project_id,
            "user_id": user_id,
            "generation_type": generation_type,
            "request_payload": payload,
            "workflow": _build_entity_generation_workflow_payload(
                generation_type=generation_type,
                display_label=config.display_label,
            ),
        },
    )
    task_state_store.set(task_state)
    async with AsyncSessionLocal() as session:
        await create_task_run(
            session,
            task_state=task_state,
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
                "generation_type": generation_type,
                "requested_count": requested_count,
                "workflow_key": "entity_generation",
            },
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
    state.message = "这轮补设定没跑通。"
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return task_state_store.set(state)


def mark_task_succeeded(task_id: str, result: dict[str, Any], message: str) -> TaskState:
    state = _require_task(task_id)
    state.status = "succeeded"
    state.progress = 100
    state.message = message
    state.result = result
    state.error = None
    return task_state_store.set(state)


async def process_entity_generation_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
    generation_type: str,
) -> TaskState:
    config = _get_entity_generation_config(generation_type)
    state = await hydrate_task_state(task_id)
    state = mark_task_running(task_id, f"正在读取现有设定，准备补{config.display_label}。")
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="started",
        event_payload={
            "phase": "bootstrap",
            "generation_type": generation_type,
            "workflow_key": "entity_generation",
        },
    )

    payload_data = dict((state.result or {}).get("request_payload") or {})

    try:
        request_payload = config.request_model.model_validate(payload_data)
    except ValidationError as exc:
        state = mark_task_failed(
            task_id,
            "生成参数不完整，暂时没法继续补设定。",
            result_patch={
                "generation_type": generation_type,
                "validation_error": exc.errors(),
            },
        )
        await persist_task_state(
            state,
            project_id=project_id,
            user_id=user_id,
            event_type="failed",
            event_payload={
                "phase": "payload_validation",
                "generation_type": generation_type,
                "error_type": exc.__class__.__name__,
                "workflow_key": "entity_generation",
            },
        )
        return state

    requested_count = getattr(request_payload, "count", None)
    state = mark_task_progress(
        task_id,
        progress=25,
        message="已整理当前项目的设定上下文。",
        result_patch={
            "requested_count": requested_count,
        },
    )
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="context_loaded",
        event_payload={
            "phase": "context",
            "generation_type": generation_type,
            "requested_count": requested_count,
            "workflow_key": "entity_generation",
        },
    )

    state = mark_task_progress(
        task_id,
        progress=55,
        message=f"正在生成{config.display_label}。",
    )
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="generation_started",
        event_payload={
            "phase": "generation",
            "generation_type": generation_type,
            "requested_count": requested_count,
            "workflow_key": "entity_generation",
        },
    )

    async with AsyncSessionLocal() as session:
        try:
            pipeline_result = await run_entity_generation_pipeline(
                session,
                project_id=UUID(project_id),
                user_id=UUID(user_id),
                generation_type=generation_type,
                payload=request_payload,
            )
        except Exception as exc:  # pragma: no cover - 运行时仍需要保留失败分支
            state = mark_task_failed(
                task_id,
                str(exc),
                result_patch={
                    "generation_type": generation_type,
                    "error_type": exc.__class__.__name__,
                },
            )
            await persist_task_state(
                state,
                project_id=project_id,
                user_id=user_id,
                event_type="failed",
                event_payload={
                    "phase": "generation",
                    "generation_type": generation_type,
                    "error_type": exc.__class__.__name__,
                    "workflow_key": "entity_generation",
                },
            )
            return state

    response_payload = pipeline_result.response.model_dump(mode="json")
    candidates = list(response_payload.get(config.result_key) or [])
    result = {
        "project_id": project_id,
        "user_id": user_id,
        "generation_type": generation_type,
        "request_payload": request_payload.model_dump(mode="json"),
        config.result_key: candidates,
        "candidate_count": len(candidates),
        "entity_preview": _collect_entity_preview(candidates),
        "workflow": _build_entity_generation_workflow_payload(
            generation_type=generation_type,
            display_label=config.display_label,
        ),
        "generation_trace": pipeline_result.trace,
        "requested_count": requested_count,
    }

    state = mark_task_progress(
        task_id,
        progress=72,
        message="已完成这一轮候选生成，正在整理可采纳结果。",
        result_patch={
            "generation_trace": pipeline_result.trace,
        },
    )
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="generation_completed",
        event_payload=_build_generation_trace_event_payload(
            generation_type=generation_type,
            requested_count=requested_count,
            trace=pipeline_result.trace,
        ),
    )

    state = mark_task_progress(
        task_id,
        progress=85,
        message=f"已整理出 {len(candidates)} 条{config.display_label}，准备回传。",
        result_patch=result,
    )
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="outputs_ready",
        event_payload=_build_result_event_payload(result),
    )

    state = mark_task_succeeded(
        task_id,
        result,
        f"{config.display_label}已经整理好了。",
    )
    await persist_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="succeeded",
        event_payload=_build_result_event_payload(result),
    )
    return state


async def dispatch_entity_generation_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
    generation_type: str,
) -> TaskState:
    try:
        process_entity_generation_task_celery.apply_async(
            kwargs={
                "task_id": task_id,
                "project_id": project_id,
                "user_id": user_id,
                "generation_type": generation_type,
            },
            task_id=task_id,
        )
        state = mark_task_dispatched(
            task_id,
            message="补设定任务已发出，马上开始处理。",
            result_patch={"dispatch_strategy": "celery", "celery_task_id": task_id},
        )
        await persist_task_state(
            state,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "generation_type": generation_type,
                "dispatch_strategy": "celery",
                "celery_task_id": task_id,
                "workflow_key": "entity_generation",
            },
        )
        return state
    except Exception as exc:  # pragma: no cover - 依赖 broker 可用性
        state = mark_task_dispatched(
            task_id,
            message="队列暂时不可用，已经改成当前进程直接处理。",
            result_patch={
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
            },
        )
        await persist_task_state(
            state,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "generation_type": generation_type,
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
                "workflow_key": "entity_generation",
            },
        )
        asyncio.create_task(
            process_entity_generation_task(
                task_id=task_id,
                project_id=project_id,
                user_id=user_id,
                generation_type=generation_type,
            )
        )
        return state


@celery_app.task(name="entity_generation.process")
def process_entity_generation_task_celery(
    task_id: str,
    project_id: str,
    user_id: str,
    generation_type: str,
) -> dict[str, Any]:
    state = asyncio.run(
        process_entity_generation_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            generation_type=generation_type,
        )
    )
    return state.model_dump()


def _get_entity_generation_config(generation_type: str) -> EntityGenerationConfig:
    config = ENTITY_GENERATION_CONFIGS.get(generation_type)
    if config is None:
        raise KeyError(f"Unsupported entity generation type: {generation_type}")
    return config


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
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()


def _build_result_event_payload(result: dict[str, Any]) -> dict[str, Any]:
    trace = result.get("generation_trace") if isinstance(result.get("generation_trace"), dict) else {}
    return {
        "workflow_key": "entity_generation",
        "generation_type": result.get("generation_type"),
        "requested_count": result.get("requested_count"),
        "candidate_count": result.get("candidate_count"),
        "entity_preview": result.get("entity_preview"),
        "response_source": trace.get("response_source"),
        "used_fallback": trace.get("used_fallback"),
        "failover_triggered": trace.get("failover_triggered"),
    }


def _build_generation_trace_event_payload(
    *,
    generation_type: str,
    requested_count: Any,
    trace: dict[str, Any],
) -> dict[str, Any]:
    context_snapshot = trace.get("context_snapshot")
    return {
        "workflow_key": "entity_generation",
        "phase": "generation_completed",
        "generation_type": generation_type,
        "requested_count": requested_count,
        "selected_role": trace.get("selected_role"),
        "used_fallback": trace.get("used_fallback"),
        "failover_triggered": trace.get("failover_triggered"),
        "response_source": trace.get("response_source"),
        "raw_candidate_count": trace.get("raw_candidate_count"),
        "returned_count": trace.get("returned_count"),
        "scope_kind": context_snapshot.get("scope_kind") if isinstance(context_snapshot, dict) else None,
        "branch_title": context_snapshot.get("branch_title") if isinstance(context_snapshot, dict) else None,
    }


def _build_entity_generation_workflow_payload(
    *,
    generation_type: str,
    display_label: str,
) -> dict[str, Any]:
    return {
        "key": "entity_generation",
        "generation_type": generation_type,
        "label": f"补全{display_label}",
        "steps": [
            "读取当前设定",
            "选择补全方案",
            "生成候选",
            "整理结果",
            "等待采纳",
        ],
    }


def _collect_entity_preview(candidates: list[dict[str, Any]]) -> list[str]:
    preview: list[str] = []
    for item in candidates[:5]:
        if not isinstance(item, dict):
            continue
        label = item.get("name") or item.get("title")
        if isinstance(label, str) and label.strip():
            preview.append(label.strip())
    return preview
