from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from db.session import AsyncSessionLocal
from schemas.story_engine import (
    FinalOptimizeRequest,
    OutlineStressTestRequest,
    StoryBulkImportPayload,
)
from services.story_engine_import_service import bulk_import_story_payload
from services.story_engine_workflow_service import (
    run_final_optimize,
)
from services.story_engine_workflows._shared import (
    _build_workflow_id,
    _build_workflow_task_base_result,
    _resolve_workflow_task_type,
)
from services.story_engine_workflows import (
    run_outline_stress_test,
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


def _set_task_state(state: TaskState) -> TaskState:
    return task_state_store.set(state)


def _build_story_engine_task_state(
    *,
    workflow_id: str,
    workflow_type: str,
    project_id: str,
    user_id: str,
    chapter_id: UUID | None,
    chapter_number: int | None,
    chapter_title: str | None,
    branch_id: UUID | None,
    message: str,
    request_payload: dict[str, Any],
    result_patch: dict[str, Any] | None = None,
) -> TaskState:
    result = {
        **_build_workflow_task_base_result(
            workflow_id=workflow_id,
            workflow_type=workflow_type,
            workflow_status="queued",
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            branch_id=branch_id,
        ),
        "request_payload": request_payload,
        "project_id": project_id,
        "user_id": user_id,
    }
    if result_patch:
        result.update(result_patch)
    return TaskState(
        task_id=workflow_id,
        task_type=_resolve_workflow_task_type(workflow_type),
        status="queued",
        progress=0,
        message=message,
        result=result,
        project_id=UUID(project_id),
        chapter_id=chapter_id,
        chapter_number=chapter_number,
    )


async def enqueue_outline_stress_task(
    *,
    project_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> TaskState:
    request = OutlineStressTestRequest.model_validate(payload)
    workflow_id = _build_workflow_id("outline_stress_test")
    task_state = _build_story_engine_task_state(
        workflow_id=workflow_id,
        workflow_type="outline_stress_test",
        project_id=project_id,
        user_id=user_id,
        chapter_id=None,
        chapter_number=None,
        chapter_title=None,
        branch_id=request.branch_id,
        message="已加入队列，准备拆脑洞并测大纲漏洞。",
        request_payload=request.model_dump(mode="json"),
        result_patch={
            "target_chapter_count": request.target_chapter_count,
            "target_total_words": request.target_total_words,
        },
    )
    return await _persist_enqueued_task(
        task_state,
        project_id=project_id,
        user_id=user_id,
        event_payload={
            "phase": "enqueue",
            "workflow_type": "outline_stress_test",
            "target_chapter_count": request.target_chapter_count,
            "target_total_words": request.target_total_words,
        },
    )


async def enqueue_bulk_import_task(
    *,
    project_id: str,
    user_id: str,
    payload: dict[str, Any],
    replace_existing_sections: list[str],
    branch_id: UUID | None,
    model_preset_key: str | None,
) -> TaskState:
    normalized_payload = StoryBulkImportPayload.model_validate(payload)
    workflow_id = _build_workflow_id("bulk_import")
    payload_data = normalized_payload.model_dump(mode="json")
    task_state = _build_story_engine_task_state(
        workflow_id=workflow_id,
        workflow_type="bulk_import",
        project_id=project_id,
        user_id=user_id,
        chapter_id=None,
        chapter_number=None,
        chapter_title=None,
        branch_id=branch_id,
        message="已加入队列，准备导入起盘设定和三级大纲。",
        request_payload={
            "payload": payload_data,
            "replace_existing_sections": replace_existing_sections,
            "branch_id": str(branch_id) if branch_id is not None else None,
            "model_preset_key": model_preset_key,
        },
        result_patch={
            "incoming_counts": {
                section: len(items)
                for section, items in payload_data.items()
                if isinstance(items, list)
            },
            "replace_existing_sections": replace_existing_sections,
            "model_preset_key": model_preset_key,
        },
    )
    return await _persist_enqueued_task(
        task_state,
        project_id=project_id,
        user_id=user_id,
        event_payload={
            "phase": "enqueue",
            "workflow_type": "bulk_import",
            "replace_section_count": len(replace_existing_sections),
            "model_preset_key": model_preset_key,
        },
    )


async def enqueue_final_optimize_task(
    *,
    project_id: str,
    user_id: str,
    payload: dict[str, Any],
) -> TaskState:
    request = FinalOptimizeRequest.model_validate(payload)
    workflow_id = _build_workflow_id("final_optimize")
    task_state = _build_story_engine_task_state(
        workflow_id=workflow_id,
        workflow_type="final_optimize",
        project_id=project_id,
        user_id=user_id,
        chapter_id=request.chapter_id,
        chapter_number=request.chapter_number,
        chapter_title=request.chapter_title,
        branch_id=request.branch_id,
        message="已加入队列，准备深度收口这一章。",
        request_payload=request.model_dump(mode="json"),
        result_patch={
            "chapter_number": request.chapter_number,
            "chapter_title": request.chapter_title,
        },
    )
    return await _persist_enqueued_task(
        task_state,
        project_id=project_id,
        user_id=user_id,
        event_payload={
            "phase": "enqueue",
            "workflow_type": "final_optimize",
            "chapter_number": request.chapter_number,
        },
    )


async def dispatch_outline_stress_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    return await _dispatch_story_engine_task(
        task_id=task_id,
        project_id=project_id,
        user_id=user_id,
        local_coro_factory=lambda: process_outline_stress_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        ),
        celery_task=process_outline_stress_task_celery,
        dispatch_message="大纲压力测试任务已发出，准备开始处理。",
        workflow_type="outline_stress_test",
    )


async def dispatch_bulk_import_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    return await _dispatch_story_engine_task(
        task_id=task_id,
        project_id=project_id,
        user_id=user_id,
        local_coro_factory=lambda: process_bulk_import_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        ),
        celery_task=process_bulk_import_task_celery,
        dispatch_message="导入任务已发出，准备开始处理。",
        workflow_type="bulk_import",
    )


async def dispatch_final_optimize_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    return await _dispatch_story_engine_task(
        task_id=task_id,
        project_id=project_id,
        user_id=user_id,
        local_coro_factory=lambda: process_final_optimize_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        ),
        celery_task=process_final_optimize_task_celery,
        dispatch_message="终稿收口任务已发出，准备开始处理。",
        workflow_type="final_optimize",
    )


async def process_outline_stress_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    state = await hydrate_task_state(task_id)
    payload_data = dict((state.result or {}).get("request_payload") or {})
    try:
        request = OutlineStressTestRequest.model_validate(payload_data)
    except ValidationError as exc:
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="大纲压力测试参数不完整，暂时不能继续。",
            error=exc,
            result_patch={"validation_error": exc.errors()},
            workflow_type="outline_stress_test",
            phase="payload_validation",
        )

    try:
        async with AsyncSessionLocal() as session:
            await run_outline_stress_test(
                session,
                project_id=UUID(project_id),
                user_id=UUID(user_id),
                branch_id=request.branch_id,
                idea=request.idea,
                source_material=request.source_material,
                source_material_name=request.source_material_name,
                genre=request.genre,
                tone=request.tone,
                target_chapter_count=request.target_chapter_count or 120,
                target_total_words=request.target_total_words or 1_000_000,
                workflow_id=task_id,
            )
    except Exception as exc:  # pragma: no cover - 运行期失败由任务状态记录
        current_state = task_state_store.get(task_id)
        if current_state is not None and current_state.status == "failed":
            return current_state
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="大纲压力测试执行失败。",
            error=exc,
            workflow_type="outline_stress_test",
            phase="workflow_execution",
        )

    return await hydrate_task_state(task_id)


async def process_bulk_import_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    state = await hydrate_task_state(task_id)
    payload_container = dict((state.result or {}).get("request_payload") or {})
    try:
        import_payload = StoryBulkImportPayload.model_validate(payload_container.get("payload") or {})
    except ValidationError as exc:
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="导入参数不完整，暂时不能继续。",
            error=exc,
            result_patch={"validation_error": exc.errors()},
            workflow_type="bulk_import",
            phase="payload_validation",
        )

    replace_existing_sections = list(payload_container.get("replace_existing_sections") or [])
    raw_branch_id = payload_container.get("branch_id")
    branch_id = UUID(raw_branch_id) if raw_branch_id else None
    model_preset_key = payload_container.get("model_preset_key")

    try:
        async with AsyncSessionLocal() as session:
            await bulk_import_story_payload(
                session,
                project_id=UUID(project_id),
                user_id=UUID(user_id),
                payload=import_payload,
                replace_existing_sections=replace_existing_sections,
                branch_id=branch_id,
                model_preset_key=model_preset_key,
                workflow_id=task_id,
            )
    except Exception as exc:  # pragma: no cover - 运行期失败由任务状态记录
        current_state = task_state_store.get(task_id)
        if current_state is not None and current_state.status == "failed":
            return current_state
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="导入任务执行失败。",
            error=exc,
            workflow_type="bulk_import",
            phase="workflow_execution",
        )

    return await hydrate_task_state(task_id)


async def process_final_optimize_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
) -> TaskState:
    state = await hydrate_task_state(task_id)
    payload_data = dict((state.result or {}).get("request_payload") or {})
    try:
        request = FinalOptimizeRequest.model_validate(payload_data)
    except ValidationError as exc:
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="终稿收口参数不完整，暂时不能继续。",
            error=exc,
            result_patch={"validation_error": exc.errors()},
            workflow_type="final_optimize",
            phase="payload_validation",
        )

    try:
        async with AsyncSessionLocal() as session:
            await run_final_optimize(
                session,
                project_id=UUID(project_id),
                user_id=UUID(user_id),
                branch_id=request.branch_id,
                chapter_id=request.chapter_id,
                chapter_number=request.chapter_number,
                chapter_title=request.chapter_title,
                draft_text=request.draft_text,
                style_sample=request.style_sample,
                workflow_id=task_id,
            )
    except Exception as exc:  # pragma: no cover - 运行期失败由任务状态记录
        current_state = task_state_store.get(task_id)
        if current_state is not None and current_state.status == "failed":
            return current_state
        return await _fail_story_engine_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
            message="终稿收口执行失败。",
            error=exc,
            workflow_type="final_optimize",
            phase="workflow_execution",
        )

    return await hydrate_task_state(task_id)


@celery_app.task(name="story_engine.outline_stress_test.process")
def process_outline_stress_task_celery(
    task_id: str,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    state = asyncio.run(
        process_outline_stress_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return state.model_dump(mode="json")


@celery_app.task(name="story_engine.bulk_import.process")
def process_bulk_import_task_celery(
    task_id: str,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    state = asyncio.run(
        process_bulk_import_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return state.model_dump(mode="json")


@celery_app.task(name="story_engine.final_optimize.process")
def process_final_optimize_task_celery(
    task_id: str,
    project_id: str,
    user_id: str,
) -> dict[str, Any]:
    state = asyncio.run(
        process_final_optimize_task(
            task_id=task_id,
            project_id=project_id,
            user_id=user_id,
        )
    )
    return state.model_dump(mode="json")


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


async def _persist_enqueued_task(
    task_state: TaskState,
    *,
    project_id: str,
    user_id: str,
    event_payload: dict[str, Any],
) -> TaskState:
    _set_task_state(task_state)
    async with AsyncSessionLocal() as session:
        await create_task_run(
            session,
            task_state=task_state,
            chapter_id=task_state.chapter_id,
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await create_task_event(
            session,
            task_state=task_state,
            event_type="queued",
            payload=event_payload,
            chapter_id=task_state.chapter_id,
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()
    return task_state


async def _dispatch_story_engine_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
    local_coro_factory,
    celery_task,
    dispatch_message: str,
    workflow_type: str,
) -> TaskState:
    try:
        celery_task.apply_async(
            kwargs={
                "task_id": task_id,
                "project_id": project_id,
                "user_id": user_id,
            },
            task_id=task_id,
        )
        state = _mark_task_dispatched(
            task_id,
            message=dispatch_message,
            result_patch={"dispatch_strategy": "celery", "celery_task_id": task_id},
        )
        await _persist_story_engine_task_state(
            state,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "workflow_type": workflow_type,
                "dispatch_strategy": "celery",
                "celery_task_id": task_id,
            },
        )
        return state
    except Exception as exc:  # pragma: no cover - 依赖 broker 是否可用
        state = _mark_task_dispatched(
            task_id,
            message="Celery 不可用，已切到本地异步兜底。",
            result_patch={
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
            },
        )
        await _persist_story_engine_task_state(
            state,
            project_id=project_id,
            user_id=user_id,
            event_type="dispatched",
            event_payload={
                "phase": "dispatch",
                "workflow_type": workflow_type,
                "dispatch_strategy": "local_async_fallback",
                "dispatch_error": exc.__class__.__name__,
            },
        )
        asyncio.create_task(local_coro_factory())
        return state


def _mark_task_dispatched(
    task_id: str,
    *,
    message: str,
    result_patch: dict[str, Any] | None = None,
) -> TaskState:
    state = _require_task(task_id)
    state.message = message
    state.progress = max(state.progress, 5)
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return _set_task_state(state)


def _mark_task_failed(
    task_id: str,
    *,
    message: str,
    error: str,
    result_patch: dict[str, Any] | None = None,
) -> TaskState:
    state = _require_task(task_id)
    state.status = "failed"
    state.message = message
    state.error = error
    if result_patch:
        next_result = dict(state.result or {})
        next_result.update(result_patch)
        state.result = next_result
    return _set_task_state(state)


async def _fail_story_engine_task(
    *,
    task_id: str,
    project_id: str,
    user_id: str,
    message: str,
    error: Exception,
    workflow_type: str,
    phase: str,
    result_patch: dict[str, Any] | None = None,
) -> TaskState:
    state = _mark_task_failed(
        task_id,
        message=message,
        error=str(error),
        result_patch={
            "error_type": error.__class__.__name__,
            **(result_patch or {}),
        },
    )
    await _persist_story_engine_task_state(
        state,
        project_id=project_id,
        user_id=user_id,
        event_type="failed",
        event_payload={
            "phase": phase,
            "workflow_type": workflow_type,
            "error_type": error.__class__.__name__,
        },
    )
    return state


async def _persist_story_engine_task_state(
    task_state: TaskState,
    *,
    project_id: str,
    user_id: str,
    event_type: str,
    event_payload: dict[str, Any] | None = None,
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
            chapter_id=task_state.chapter_id,
            project_id=UUID(project_id),
            user_id=UUID(user_id),
            commit=False,
        )
        await session.commit()


def _require_task(task_id: str) -> TaskState:
    state = task_state_store.get(task_id)
    if state is None:
        raise KeyError(f"Task {task_id} not found")
    return state
