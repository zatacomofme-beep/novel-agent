from __future__ import annotations

from kombu import Exchange, Queue


generation_exchange = Exchange("generation", type="direct", durable=True)
critical_exchange = Exchange("critical", type="direct", durable=True)
bulk_exchange = Exchange("bulk", type="direct", durable=True)

CELERY_TASK_QUEUES = [
    Queue(
        "critical",
        critical_exchange,
        routing_key="critical",
        durable=True,
        max_priority=10,
        queue_arguments={"x-max-priority": 10},
    ),
    Queue(
        "generation",
        generation_exchange,
        routing_key="generation",
        durable=True,
        max_priority=7,
        queue_arguments={"x-max-priority": 7},
    ),
    Queue(
        "indexing",
        generation_exchange,
        routing_key="indexing",
        durable=True,
        max_priority=5,
        queue_arguments={"x-max-priority": 5},
    ),
    Queue(
        "bulk",
        bulk_exchange,
        routing_key="bulk",
        durable=True,
        max_priority=2,
        queue_arguments={"x-max-priority": 2},
    ),
]

CELERY_TASK_ROUTES = {
    "tasks.generate_chapter": {"queue": "generation", "routing_key": "generation"},
    "tasks.revise_chapter": {"queue": "generation", "routing_key": "generation"},
    "tasks.approve_chapter": {"queue": "critical", "routing_key": "critical"},
    "tasks.index_chapters": {"queue": "indexing", "routing_key": "indexing"},
    "tasks.generate_batch_chapters": {"queue": "bulk", "routing_key": "bulk"},
}


def get_task_routing_key(task_name: str) -> tuple[str, str]:
    route = CELERY_TASK_ROUTES.get(task_name, {"queue": "generation", "routing_key": "generation"})
    return route["queue"], route["routing_key"]
