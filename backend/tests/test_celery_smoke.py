from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from celery.contrib.testing.worker import start_worker

from tasks.celery_app import celery_app
from tasks.chapter_generation import process_generation_task_celery
from tasks.schemas import TaskState


class CelerySmokeTests(unittest.TestCase):
    def test_chapter_generation_task_executes_through_worker(self) -> None:
        original_broker = celery_app.conf.broker_url
        original_backend = celery_app.conf.result_backend
        celery_app.conf.update(
            broker_url="memory://",
            result_backend="cache+memory://",
        )
        self.addCleanup(
            celery_app.conf.update,
            broker_url=original_broker,
            result_backend=original_backend,
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
            with start_worker(
                celery_app,
                perform_ping_check=False,
                pool="solo",
                loglevel="INFO",
            ):
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
