from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from realtime.task_events import task_event_broker
from tasks.schemas import TaskState


class TaskStateStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._states: dict[str, TaskState] = {}

    def set(self, state: TaskState) -> TaskState:
        with self._lock:
            state.updated_at = datetime.now(timezone.utc)
            self._states[state.task_id] = state
            task_event_broker.publish(state)
            return state

    def get(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            return self._states.get(task_id)


task_state_store = TaskStateStore()
