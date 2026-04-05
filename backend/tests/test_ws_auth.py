from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from api.ws import (
    verify_project_access,
    verify_task_access,
    verify_task_event_subscription_access,
)


class TaskWebSocketAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_task_access_allows_project_collaborator(self) -> None:
        task_id = "task-1"
        project_id = uuid4()
        collaborator_id = uuid4()
        session = MagicMock()

        with patch(
            "api.ws.get_task_run_by_task_id",
            AsyncMock(return_value=SimpleNamespace(project_id=project_id, user_id=uuid4())),
        ), patch(
            "api.ws.get_owned_project",
            AsyncMock(return_value=SimpleNamespace(id=project_id)),
        ) as mocked_get_project:
            allowed = await verify_task_access(task_id, str(collaborator_id), session)

        self.assertTrue(allowed)
        mocked_get_project.assert_awaited_once()

    async def test_verify_task_access_falls_back_to_task_owner_for_non_project_task(self) -> None:
        task_id = "task-2"
        user_id = uuid4()
        session = MagicMock()

        with patch(
            "api.ws.get_task_run_by_task_id",
            AsyncMock(return_value=SimpleNamespace(project_id=None, user_id=user_id)),
        ):
            allowed = await verify_task_access(task_id, str(user_id), session)

        self.assertTrue(allowed)

    async def test_verify_project_access_allows_project_collaborator(self) -> None:
        project_id = uuid4()
        collaborator_id = uuid4()
        session = MagicMock()

        with patch(
            "api.ws.get_owned_project",
            AsyncMock(return_value=SimpleNamespace(id=project_id)),
        ):
            allowed = await verify_project_access(project_id, str(collaborator_id), session)

        self.assertTrue(allowed)

    async def test_verify_task_event_subscription_access_requires_all_targets_accessible(self) -> None:
        project_id = uuid4()
        blocked_task_id = "task-blocked"
        session = MagicMock()
        user_id = str(uuid4())

        with patch(
            "api.ws.verify_task_access",
            AsyncMock(side_effect=[True, False]),
        ), patch(
            "api.ws.verify_project_access",
            AsyncMock(return_value=True),
        ):
            allowed = await verify_task_event_subscription_access(
                task_ids={"task-allowed", blocked_task_id},
                project_ids={project_id},
                user_id=user_id,
                session=session,
            )

        self.assertFalse(allowed)
