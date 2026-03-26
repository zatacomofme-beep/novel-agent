from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

for key, value in {
    "DATABASE_URL": "sqlite+aiosqlite:///./test.db",
    "REDIS_URL": "redis://localhost:6379/0",
    "CELERY_BROKER_URL": "redis://localhost:6379/1",
    "CELERY_RESULT_BACKEND": "redis://localhost:6379/2",
    "QDRANT_URL": "http://localhost:6333",
    "JWT_SECRET_KEY": "test-secret",
}.items():
    os.environ.setdefault(key, value)

from tasks.schemas import TaskState
from tasks.state_store import task_state_store
from tasks.story_engine_workflows import (
    dispatch_bulk_import_task,
    dispatch_final_optimize_task,
    dispatch_outline_stress_task,
    hydrate_task_state,
    process_bulk_import_task,
    process_final_optimize_task,
    process_outline_stress_task,
)


class StoryEngineWorkflowDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.project_id = "11111111-1111-1111-1111-111111111111"
        self.user_id = "22222222-2222-2222-2222-222222222222"
        self.outline_task_id = "outline_stress_test:test-dispatch"
        self.bulk_task_id = "bulk_import:test-dispatch"
        self.final_task_id = "final_optimize:test-dispatch"
        task_state_store.set(
            TaskState(
                task_id=self.outline_task_id,
                task_type="story_engine.outline_stress_test",
                status="queued",
                progress=0,
                message="queued",
                result={
                    "request_payload": {
                        "idea": "主角每次爆发都要付代价。",
                        "genre": "玄幻",
                        "tone": "压迫感",
                        "target_chapter_count": 120,
                        "target_total_words": 1000000,
                    }
                },
            )
        )
        task_state_store.set(
            TaskState(
                task_id=self.bulk_task_id,
                task_type="story_engine.bulk_import",
                status="queued",
                progress=0,
                message="queued",
                result={
                    "request_payload": {
                        "payload": {
                            "characters": [],
                            "foreshadows": [],
                            "items": [],
                            "world_rules": [],
                            "timeline_events": [],
                            "outlines": [],
                            "chapter_summaries": [],
                        },
                        "replace_existing_sections": ["characters"],
                        "branch_id": None,
                        "model_preset_key": "balanced",
                    }
                },
            )
        )
        task_state_store.set(
            TaskState(
                task_id=self.final_task_id,
                task_type="story_engine.final_optimize",
                status="queued",
                progress=0,
                message="queued",
                result={
                    "request_payload": {
                        "chapter_number": 1,
                        "chapter_title": "第一章",
                        "draft_text": "初稿正文",
                        "style_sample": "风格样文",
                    }
                },
            )
        )

    async def test_dispatch_outline_stress_task_prefers_celery(self) -> None:
        mocked_apply_async = MagicMock()

        with patch(
            "tasks.story_engine_workflows.process_outline_stress_task_celery.apply_async",
            mocked_apply_async,
        ), patch(
            "tasks.story_engine_workflows._persist_story_engine_task_state",
            AsyncMock(),
        ):
            state = await dispatch_outline_stress_task(
                task_id=self.outline_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "celery")
        self.assertEqual(state.result["celery_task_id"], self.outline_task_id)

    async def test_dispatch_bulk_import_task_falls_back_to_local_async(self) -> None:
        mocked_create_task = MagicMock()

        def _capture_task(coro):
            coro.close()
            return mocked_create_task()

        with patch(
            "tasks.story_engine_workflows.process_bulk_import_task_celery.apply_async",
            side_effect=ConnectionError("broker offline"),
        ), patch(
            "tasks.story_engine_workflows._persist_story_engine_task_state",
            AsyncMock(),
        ), patch(
            "tasks.story_engine_workflows.asyncio.create_task",
            side_effect=_capture_task,
        ):
            state = await dispatch_bulk_import_task(
                task_id=self.bulk_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        mocked_create_task.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "local_async_fallback")
        self.assertEqual(state.result["dispatch_error"], "ConnectionError")

    async def test_dispatch_final_optimize_task_prefers_celery(self) -> None:
        mocked_apply_async = MagicMock()

        with patch(
            "tasks.story_engine_workflows.process_final_optimize_task_celery.apply_async",
            mocked_apply_async,
        ), patch(
            "tasks.story_engine_workflows._persist_story_engine_task_state",
            AsyncMock(),
        ):
            state = await dispatch_final_optimize_task(
                task_id=self.final_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "celery")

    async def test_hydrate_task_state_restores_workflow_task_from_database(self) -> None:
        task_id = "outline_stress_test:hydrated"
        task_run = SimpleNamespace(
            task_id=task_id,
            task_type="story_engine.outline_stress_test",
            status="queued",
            progress=5,
            message="hydrated",
            result={"dispatch_strategy": "celery"},
            error=None,
            project_id=uuid4(),
            chapter_id=None,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.story_engine_workflows.task_state_store.get",
            return_value=None,
        ), patch(
            "tasks.story_engine_workflows.task_state_store.set",
            side_effect=lambda state: state,
        ) as mocked_set, patch(
            "tasks.story_engine_workflows.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.story_engine_workflows.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ):
            state = await hydrate_task_state(task_id)

        self.assertEqual(state.task_id, task_id)
        self.assertEqual(state.message, "hydrated")
        mocked_set.assert_called_once()

    async def test_process_outline_stress_task_passes_fixed_workflow_id(self) -> None:
        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.story_engine_workflows.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.story_engine_workflows.run_outline_stress_test",
            AsyncMock(return_value={"ok": True}),
        ) as mocked_run:
            await process_outline_stress_task(
                task_id=self.outline_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        self.assertEqual(mocked_run.await_args.kwargs["workflow_id"], self.outline_task_id)

    async def test_process_bulk_import_task_passes_fixed_workflow_id(self) -> None:
        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.story_engine_workflows.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.story_engine_workflows.bulk_import_story_payload",
            AsyncMock(return_value={"ok": True}),
        ) as mocked_run:
            await process_bulk_import_task(
                task_id=self.bulk_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        self.assertEqual(mocked_run.await_args.kwargs["workflow_id"], self.bulk_task_id)

    async def test_process_final_optimize_task_passes_fixed_workflow_id(self) -> None:
        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.story_engine_workflows.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.story_engine_workflows.run_final_optimize",
            AsyncMock(return_value={"ok": True}),
        ) as mocked_run:
            await process_final_optimize_task(
                task_id=self.final_task_id,
                project_id=self.project_id,
                user_id=self.user_id,
            )

        self.assertEqual(mocked_run.await_args.kwargs["workflow_id"], self.final_task_id)
