from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.task_event import TaskEvent
from models.task_run import TaskRun
from tasks.schemas import TaskState


async def create_task_run(
    session: AsyncSession,
    *,
    task_state: TaskState,
    chapter_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    commit: bool = True,
) -> TaskRun:
    task_run = TaskRun(
        task_id=task_state.task_id,
        task_type=task_state.task_type,
        status=task_state.status,
        progress=task_state.progress,
        message=task_state.message,
        result=task_state.result,
        error=task_state.error,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
    )
    session.add(task_run)
    if commit:
        await session.commit()
        await session.refresh(task_run)
    else:
        await session.flush()
    return task_run


async def update_task_run(
    session: AsyncSession,
    *,
    task_state: TaskState,
    commit: bool = True,
) -> Optional[TaskRun]:
    result = await session.execute(select(TaskRun).where(TaskRun.task_id == task_state.task_id))
    task_run = result.scalar_one_or_none()
    if task_run is None:
        return None

    task_run.status = task_state.status
    task_run.progress = task_state.progress
    task_run.message = task_state.message
    task_run.result = task_state.result
    task_run.error = task_state.error
    if commit:
        await session.commit()
        await session.refresh(task_run)
    else:
        await session.flush()
    return task_run


async def get_task_run_by_task_id(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: Optional[UUID] = None,
) -> Optional[TaskRun]:
    statement = select(TaskRun).where(TaskRun.task_id == task_id)
    if user_id is not None:
        statement = statement.where(TaskRun.user_id == user_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def list_task_runs_for_chapter(
    session: AsyncSession,
    chapter_id: UUID,
    *,
    user_id: Optional[UUID] = None,
    limit: int = 10,
) -> list[TaskRun]:
    statement = select(TaskRun).where(TaskRun.chapter_id == chapter_id)
    if user_id is not None:
        statement = statement.where(TaskRun.user_id == user_id)
    result = await session.execute(
        statement.order_by(TaskRun.created_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def list_task_runs_for_project(
    session: AsyncSession,
    project_id: UUID,
    *,
    user_id: Optional[UUID] = None,
    limit: int = 20,
    task_type_prefix: Optional[str] = None,
) -> list[TaskRun]:
    statement = select(TaskRun).where(TaskRun.project_id == project_id)
    if user_id is not None:
        statement = statement.where(TaskRun.user_id == user_id)
    if task_type_prefix:
        statement = statement.where(TaskRun.task_type.like(f"{task_type_prefix}%"))
    result = await session.execute(
        statement.order_by(TaskRun.updated_at.desc()).limit(limit)
    )
    return list(result.scalars().all())


async def create_task_event(
    session: AsyncSession,
    *,
    task_state: TaskState,
    event_type: str,
    payload: Optional[dict] = None,
    chapter_id: Optional[UUID] = None,
    project_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    commit: bool = True,
) -> TaskEvent:
    task_event = TaskEvent(
        task_id=task_state.task_id,
        task_type=task_state.task_type,
        event_type=event_type,
        status=task_state.status,
        progress=task_state.progress,
        message=task_state.message,
        payload=payload,
        chapter_id=chapter_id,
        project_id=project_id,
        user_id=user_id,
    )
    session.add(task_event)
    if commit:
        await session.commit()
        await session.refresh(task_event)
    else:
        await session.flush()
    return task_event


async def list_task_events_for_task(
    session: AsyncSession,
    task_id: str,
    *,
    user_id: Optional[UUID] = None,
    limit: int = 50,
) -> list[TaskEvent]:
    statement = select(TaskEvent).where(TaskEvent.task_id == task_id)
    if user_id is not None:
        statement = statement.where(TaskEvent.user_id == user_id)
    result = await session.execute(
        statement.order_by(TaskEvent.created_at.desc()).limit(limit)
    )
    events = list(result.scalars().all())
    events.reverse()
    return events
