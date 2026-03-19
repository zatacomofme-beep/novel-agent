from uuid import UUID

from fastapi import APIRouter, Depends

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
)
from tasks.schemas import TaskEventRead, TaskState
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
        return state

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
