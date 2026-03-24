from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from canon.base import CanonIntegrityReport
from services.generation_service import StoryBibleIntegrityError
from tasks.chapter_generation import dispatch_generation_task, hydrate_task_state
from tasks.schemas import TaskState
from tasks.state_store import task_state_store


class ChapterGenerationDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.task_id = "task-dispatch"
        self.chapter_id = "11111111-1111-1111-1111-111111111111"
        self.project_id = "22222222-2222-2222-2222-222222222222"
        self.user_id = "33333333-3333-3333-3333-333333333333"
        task_state_store.set(
            TaskState(
                task_id=self.task_id,
                task_type="chapter_generation",
                status="queued",
                progress=0,
                message="queued",
                result={},
            )
        )

    async def test_dispatch_generation_task_prefers_celery(self) -> None:
        mocked_apply_async = MagicMock()

        with patch(
            "tasks.chapter_generation.process_generation_task_celery.apply_async",
            mocked_apply_async,
        ), patch(
            "tasks.chapter_generation.persist_task_state",
            AsyncMock(),
        ):
            state = await dispatch_generation_task(
                task_id=self.task_id,
                chapter_id=self.chapter_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "celery")
        self.assertEqual(state.result["celery_task_id"], self.task_id)

    async def test_dispatch_generation_task_falls_back_to_local_async(self) -> None:
        mocked_create_task = MagicMock()

        def _capture_task(coro):
            coro.close()
            return mocked_create_task()

        with patch(
            "tasks.chapter_generation.process_generation_task_celery.apply_async",
            side_effect=ConnectionError("broker offline"),
        ), patch(
            "tasks.chapter_generation.persist_task_state",
            AsyncMock(),
        ), patch(
            "tasks.chapter_generation.asyncio.create_task",
            side_effect=_capture_task,
        ):
            state = await dispatch_generation_task(
                task_id=self.task_id,
                chapter_id=self.chapter_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        mocked_create_task.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "local_async_fallback")
        self.assertEqual(state.result["dispatch_error"], "ConnectionError")

    async def test_hydrate_task_state_restores_state_from_database(self) -> None:
        task_id = "task-hydrate"
        task_run = SimpleNamespace(
            task_id=task_id,
            task_type="chapter_generation",
            status="queued",
            progress=5,
            message="hydrated",
            result={"dispatch_strategy": "celery"},
            error=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.chapter_generation.task_state_store.get",
            return_value=None,
        ), patch(
            "tasks.chapter_generation.task_state_store.set",
            side_effect=lambda state: state,
        ) as mocked_set, patch(
            "tasks.chapter_generation.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.chapter_generation.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ):
            state = await hydrate_task_state(task_id)

        self.assertEqual(state.task_id, task_id)
        self.assertEqual(state.message, "hydrated")
        mocked_set.assert_called_once()

    async def test_process_generation_task_persists_story_bible_integrity_report_on_failure(
        self,
    ) -> None:
        from tasks.chapter_generation import process_generation_task

        integrity_report = CanonIntegrityReport(
            issue_count=1,
            blocking_issue_count=1,
            plugin_breakdown={"relationship": 1},
            issues=[],
            summary="Story Bible 自校验发现 1 个问题，其中 1 个会破坏规范真相层。",
        )

        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.chapter_generation.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.chapter_generation.persist_task_state",
            AsyncMock(),
        ), patch(
            "tasks.chapter_generation.run_generation_pipeline",
            AsyncMock(side_effect=StoryBibleIntegrityError(integrity_report)),
        ):
            state = await process_generation_task(
                task_id=self.task_id,
                chapter_id=self.chapter_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        self.assertEqual(state.status, "failed")
        self.assertIn("story_bible_integrity_report", state.result or {})
        self.assertEqual(
            state.result["story_bible_integrity_report"]["blocking_issue_count"],
            1,
        )
