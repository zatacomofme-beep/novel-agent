from __future__ import annotations

import unittest
from types import SimpleNamespace
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from schemas.project import CharacterGenerationResponse, GeneratedCharacter
from services.entity_generation_service import EntityGenerationPipelineResult
from tasks.entity_generation import dispatch_entity_generation_task, hydrate_task_state
from tasks.schemas import TaskState
from tasks.state_store import task_state_store


class EntityGenerationDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.task_id = "task-entity-dispatch"
        self.project_id = "22222222-2222-2222-2222-222222222222"
        self.user_id = "33333333-3333-3333-3333-333333333333"
        self.generation_type = "characters"
        task_state_store.set(
            TaskState(
                task_id=self.task_id,
                task_type="entity_generation.characters",
                status="queued",
                progress=0,
                message="queued",
                result={
                    "project_id": self.project_id,
                    "user_id": self.user_id,
                    "generation_type": self.generation_type,
                    "request_payload": {"count": 2, "character_type": "supporting"},
                },
            )
        )

    async def test_dispatch_entity_generation_task_prefers_celery(self) -> None:
        mocked_apply_async = MagicMock()

        with patch(
            "tasks.entity_generation.process_entity_generation_task_celery.apply_async",
            mocked_apply_async,
        ), patch(
            "tasks.entity_generation.persist_task_state",
            AsyncMock(),
        ):
            state = await dispatch_entity_generation_task(
                task_id=self.task_id,
                project_id=self.project_id,
                user_id=self.user_id,
                generation_type=self.generation_type,
            )

        mocked_apply_async.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "celery")
        self.assertEqual(state.result["celery_task_id"], self.task_id)

    async def test_dispatch_entity_generation_task_falls_back_to_local_async(self) -> None:
        mocked_create_task = MagicMock()

        def _capture_task(coro):
            coro.close()
            return mocked_create_task()

        with patch(
            "tasks.entity_generation.process_entity_generation_task_celery.apply_async",
            side_effect=ConnectionError("broker offline"),
        ), patch(
            "tasks.entity_generation.persist_task_state",
            AsyncMock(),
        ), patch(
            "tasks.entity_generation.asyncio.create_task",
            side_effect=_capture_task,
        ):
            state = await dispatch_entity_generation_task(
                task_id=self.task_id,
                project_id=self.project_id,
                user_id=self.user_id,
                generation_type=self.generation_type,
            )

        mocked_create_task.assert_called_once()
        self.assertEqual(state.result["dispatch_strategy"], "local_async_fallback")
        self.assertEqual(state.result["dispatch_error"], "ConnectionError")

    async def test_hydrate_task_state_restores_state_from_database(self) -> None:
        task_id = "task-entity-hydrate"
        task_run = SimpleNamespace(
            task_id=task_id,
            task_type="entity_generation.characters",
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
            "tasks.entity_generation.task_state_store.get",
            return_value=None,
        ), patch(
            "tasks.entity_generation.task_state_store.set",
            side_effect=lambda state: state,
        ) as mocked_set, patch(
            "tasks.entity_generation.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.entity_generation.get_task_run_by_task_id",
            AsyncMock(return_value=task_run),
        ):
            state = await hydrate_task_state(task_id)

        self.assertEqual(state.task_id, task_id)
        self.assertEqual(state.message, "hydrated")
        mocked_set.assert_called_once()

    async def test_process_entity_generation_task_persists_generated_candidates(self) -> None:
        from tasks.entity_generation import process_entity_generation_task

        class FakeSessionContext:
            async def __aenter__(self):
                return MagicMock()

            async def __aexit__(self, exc_type, exc, tb):
                return False

        with patch(
            "tasks.entity_generation.AsyncSessionLocal",
            return_value=FakeSessionContext(),
        ), patch(
            "tasks.entity_generation.persist_task_state",
            AsyncMock(),
        ), patch(
            "tasks.entity_generation.run_entity_generation_pipeline",
            AsyncMock(
                return_value=EntityGenerationPipelineResult(
                    generation_type="characters",
                    result_key="characters",
                    response=CharacterGenerationResponse(
                        characters=[
                            GeneratedCharacter(
                                name="沈遥",
                                role="supporting",
                                personality="冷静克制",
                            )
                        ]
                    ),
                    trace={
                        "generation_type": "characters",
                        "selected_role": "guardian",
                        "selected_model": "gpt-5.4",
                        "selected_provider": "openai-compatible",
                        "response_source": "model_response",
                        "used_fallback": False,
                        "failover_triggered": False,
                        "context_snapshot": {
                            "scope_kind": "branch",
                            "branch_title": "主线",
                        },
                    },
                )
            ),
        ):
            state = await process_entity_generation_task(
                task_id=self.task_id,
                project_id=self.project_id,
                user_id=self.user_id,
                generation_type=self.generation_type,
            )

        self.assertEqual(state.status, "succeeded")
        self.assertEqual(state.result["candidate_count"], 1)
        self.assertEqual(state.result["entity_preview"], ["沈遥"])
        self.assertEqual(state.result["generation_trace"]["selected_role"], "guardian")
