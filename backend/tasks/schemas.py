from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


TaskStatus = Literal["queued", "running", "succeeded", "failed"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskState(BaseModel):
    task_id: str
    task_type: str
    status: TaskStatus
    progress: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    project_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    chapter_number: Optional[int] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @classmethod
    def from_task_run(cls, task_run) -> "TaskState":
        task_result = task_run.result if isinstance(task_run.result, dict) else {}
        chapter_number = getattr(getattr(task_run, "chapter", None), "chapter_number", None)
        if chapter_number is None:
            raw_chapter_number = task_result.get("chapter_number")
            chapter_number = raw_chapter_number if isinstance(raw_chapter_number, int) else None
        return cls(
            task_id=task_run.task_id,
            task_type=task_run.task_type,
            status=task_run.status,
            progress=task_run.progress,
            message=task_run.message,
            result=task_run.result,
            error=task_run.error,
            project_id=task_run.project_id,
            chapter_id=task_run.chapter_id,
            chapter_number=chapter_number,
            created_at=task_run.created_at,
            updated_at=task_run.updated_at,
        )


class TaskEventRead(BaseModel):
    id: str
    task_id: str
    task_type: str
    event_type: str
    status: TaskStatus
    progress: int = Field(default=0, ge=0, le=100)
    message: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    created_at: datetime

    @classmethod
    def from_task_event(cls, task_event) -> "TaskEventRead":
        return cls(
            id=str(task_event.id),
            task_id=task_event.task_id,
            task_type=task_event.task_type,
            event_type=task_event.event_type,
            status=task_event.status,
            progress=task_event.progress,
            message=task_event.message,
            payload=task_event.payload,
            created_at=task_event.created_at,
        )


class TaskPlaybackRead(TaskState):
    recent_events: list[TaskEventRead] = Field(default_factory=list)
