from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

try:
    import celery as celery_module

    CELERY_AVAILABLE = True
except ModuleNotFoundError:
    celery_module = None
    CELERY_AVAILABLE = False

from tasks.celery_app import celery_app
from tasks.chapter_generation import process_generation_task_celery
from tasks.schemas import TaskState


@unittest.skipUnless(CELERY_AVAILABLE, "celery is not installed")
class CelerySmokeTests(unittest.TestCase):
    def test_chapter_generation_task_executes_in_eager_mode(self) -> None:
        original_broker = celery_app.conf.broker_url
        original_backend = celery_app.conf.result_backend
        original_task_always_eager = celery_app.conf.task_always_eager
        original_task_store_eager_result = celery_app.conf.task_store_eager_result
        celery_app.conf.update(
            broker_url="memory://",
            result_backend="cache+memory://",
            task_always_eager=True,
            task_store_eager_result=True,
        )
        self.addCleanup(
            celery_app.conf.update,
            broker_url=original_broker,
            result_backend=original_backend,
            task_always_eager=original_task_always_eager,
            task_store_eager_result=original_task_store_eager_result,
        )

        mocked_state = TaskState(
            task_id="task-smoke",
            task_type="chapter_generation",
            status="succeeded",
            progress=100,
            message="smoke ok",
            result={"dispatch_strategy": "celery"},
        )

        with patch(
            "tasks.chapter_generation.process_generation_task",
            AsyncMock(return_value=mocked_state),
        ) as mocked_process:
            result = process_generation_task_celery.delay(
                task_id="task-smoke",
                chapter_id="chapter-1",
                project_id="project-1",
                user_id="user-1",
            )
            payload = result.get(timeout=10)

        mocked_process.assert_awaited_once()
        self.assertEqual(payload["task_id"], "task-smoke")
        self.assertEqual(payload["status"], "succeeded")
        self.assertEqual(payload["message"], "smoke ok")
