from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user, get_db_session
from core.errors import AppError
from models.user import User
from services.chapter_service import get_owned_chapter
from services.project_service import get_owned_project, PROJECT_PERMISSION_READ
from services.task_service import (
    get_task_run_by_task_id,
    list_task_events_for_task,
    list_task_runs_for_chapter,
    list_task_runs_for_project,
)
from tasks.schemas import TaskEventRead, TaskPlaybackRead, TaskState
from tasks.state_store import task_state_store


router = APIRouter()


@router.get("/tasks/{task_id}", response_model=TaskState)
async def task_detail(
    task_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> TaskState:
    task_run = await get_task_run_by_task_id(
        session,
        task_id,
    )
    if task_run is None:
        raise AppError(
            code="task.not_found",
            message="Task not found.",
            status_code=404,
        )
    await _assert_task_access(session, task_run, current_user.id)

    state = task_state_store.get(task_id)
    if state is not None:
        chapter_number = getattr(getattr(task_run, "chapter", None), "chapter_number", None)
        if chapter_number is None and isinstance(getattr(task_run, "result", None), dict):
            raw_chapter_number = task_run.result.get("chapter_number")
            chapter_number = raw_chapter_number if isinstance(raw_chapter_number, int) else None
        return state.model_copy(
            update={
                "project_id": task_run.project_id,
                "chapter_id": task_run.chapter_id,
                "chapter_number": chapter_number,
            }
        )

    state = TaskState.from_task_run(task_run)
    task_state_store.set(state)
    return state


@router.get("/tasks/{task_id}/events", response_model=list[TaskEventRead])
async def task_events(
    task_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskEventRead]:
    task_run = await get_task_run_by_task_id(
        session,
        task_id,
    )
    if task_run is None:
        raise AppError(
            code="task.not_found",
            message="Task not found.",
            status_code=404,
        )
    await _assert_task_access(session, task_run, current_user.id)

    events = await list_task_events_for_task(
        session,
        task_id,
    )
    return [TaskEventRead.from_task_event(event) for event in events]


@router.get("/chapters/{chapter_id}/tasks", response_model=list[TaskState])
async def tasks_for_chapter(
    chapter_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskState]:
    await get_owned_chapter(
        session,
        chapter_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    task_runs = await list_task_runs_for_chapter(
        session,
        chapter_id,
    )
    states = [TaskState.from_task_run(task_run) for task_run in task_runs]
    for state in states:
        task_state_store.set(state)
    return states


@router.get("/projects/{project_id}/tasks", response_model=list[TaskState])
async def tasks_for_project(
    project_id: UUID,
    task_type_prefix: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskState]:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    task_runs = await list_task_runs_for_project(
        session,
        project_id,
        limit=limit,
        task_type_prefix=task_type_prefix,
    )
    states = [TaskState.from_task_run(task_run) for task_run in task_runs]
    for state in states:
        task_state_store.set(state)
    return states


@router.get("/projects/{project_id}/task-playback", response_model=list[TaskPlaybackRead])
async def task_playback_for_project(
    project_id: UUID,
    task_type_prefix: Optional[str] = Query(default=None),
    limit: int = Query(default=8, ge=1, le=20),
    event_limit: int = Query(default=5, ge=1, le=10),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> list[TaskPlaybackRead]:
    await get_owned_project(
        session,
        project_id,
        current_user.id,
        permission=PROJECT_PERMISSION_READ,
    )
    task_runs = await list_task_runs_for_project(
        session,
        project_id,
        limit=limit,
        task_type_prefix=task_type_prefix,
    )
    playback_items: list[TaskPlaybackRead] = []
    for task_run in task_runs:
        recent_events = await list_task_events_for_task(
            session,
            task_run.task_id,
            limit=event_limit,
        )
        state = TaskState.from_task_run(task_run)
        task_state_store.set(state)
        playback_items.append(
            TaskPlaybackRead(
                **state.model_dump(),
                recent_events=[TaskEventRead.from_task_event(event) for event in recent_events],
            )
        )
    return playback_items


async def _assert_task_access(session: AsyncSession, task_run, user_id: UUID) -> None:
    project_id = getattr(task_run, "project_id", None)
    if project_id is not None:
        await get_owned_project(
            session,
            project_id,
            user_id,
            permission=PROJECT_PERMISSION_READ,
        )
        return

    if getattr(task_run, "user_id", None) != user_id:
        raise AppError(
            code="task.not_found",
            message="Task not found.",
            status_code=404,
        )
