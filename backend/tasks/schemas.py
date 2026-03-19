from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

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
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @classmethod
    def from_task_run(cls, task_run) -> "TaskState":
        return cls(
            task_id=task_run.task_id,
            task_type=task_run.task_type,
            status=task_run.status,
            progress=task_run.progress,
            message=task_run.message,
            result=task_run.result,
            error=task_run.error,
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
