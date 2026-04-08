from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from realtime.task_events import task_event_broker
from tasks.schemas import TaskState


class TaskStateStore:
    MAX_STATES = 10000

    def __init__(self) -> None:
        self._lock = Lock()
        self._states: OrderedDict[str, TaskState] = OrderedDict()

    def set(self, state: TaskState) -> TaskState:
        with self._lock:
            state.updated_at = datetime.now(timezone.utc)
            if state.task_id in self._states:
                self._states.move_to_end(state.task_id)
            else:
                if len(self._states) >= self.MAX_STATES:
                    self._states.popitem(last=False)
            self._states[state.task_id] = state
            task_event_broker.publish(state)
            return state

    def get(self, task_id: str) -> Optional[TaskState]:
        with self._lock:
            if task_id in self._states:
                self._states.move_to_end(task_id)
            return self._states.get(task_id)


task_state_store = TaskStateStore()
