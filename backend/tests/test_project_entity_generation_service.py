from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from schemas.project import CharacterGenerationRequest
from services.project_entity_generation_service import dispatch_project_entity_generation
from tasks.schemas import TaskState


class ProjectEntityGenerationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_project_entity_generation_returns_created_task(self) -> None:
        project = SimpleNamespace(
            id=uuid4(),
            user_id=uuid4(),
        )
        session = SimpleNamespace()

        with patch(
            "tasks.entity_generation.enqueue_entity_generation_task",
            AsyncMock(
                return_value=TaskState(
                    task_id="task-entity-1",
                    task_type="entity_generation.characters",
                    status="queued",
                    progress=0,
                    message="queued",
                    result={},
                )
            ),
        ), patch(
            "tasks.entity_generation.dispatch_entity_generation_task",
            AsyncMock(
                return_value=TaskState(
                    task_id="task-entity-1",
                    task_type="entity_generation.characters",
                    status="queued",
                    progress=5,
                    message="dispatched",
                    result={"dispatch_strategy": "celery"},
                )
            ),
        ):
            result = await dispatch_project_entity_generation(
                session,
                project,
                actor_user_id=project.user_id,
                generation_type="characters",
                payload=CharacterGenerationRequest(
                    character_type="supporting",
                    count=2,
                    genre="悬疑奇幻",
                ),
            )

        self.assertEqual(result.generation_type, "characters")
        self.assertEqual(result.task_id, "task-entity-1")
        self.assertEqual(result.task.status, "queued")
