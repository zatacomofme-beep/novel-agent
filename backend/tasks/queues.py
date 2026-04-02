from __future__ import annotations

from enum import Enum
from celery_app import celery_app


class QueuePriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


QUEUE_ROUTES: dict[str, QueuePriority] = {
    "chapter_generation.process": QueuePriority.CRITICAL,
    "entity_generation.process": QueuePriority.HIGH,
    "story_engine_workflows.generate_outline": QueuePriority.HIGH,
    "story_engine_workflows.continue_story": QueuePriority.NORMAL,
    "story_engine_workflows.regenerate_segment": QueuePriority.NORMAL,
    "story_engine_workflows.archive_project": QueuePriority.LOW,
    "entity_generation.batch": QueuePriority.LOW,
}

CELERY_QUEUE_NAMES = [q.value for q in QueuePriority]

celery_app.conf.task_queues = [
    celery_app.amqp.queues["critical"],
    celery_app.amqp.queues["high"],
    celery_app.amqp.queues["normal"],
    celery_app.amqp.queues["low"],
] if hasattr(celery_app.amqp, "queues") else []

celery_app.conf.task_default_queue = QueuePriority.NORMAL.value


def get_queue_for_task(task_name: str) -> str:
    priority = QUEUE_ROUTES.get(task_name, QueuePriority.NORMAL)
    return priority.value


def route_task(task_name: str) -> dict[str, str]:
    queue = get_queue_for_task(task_name)
    return {"queue": queue}
