from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.errors import AppError
from api.v1.evaluation import chapter_evaluate, story_engine_chapter_evaluate
from api.v1.tasks import tasks_for_chapter, tasks_for_story_engine_chapter


class LegacyTaskEvaluateRouteObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_tasks_route_emits_usage_log(self) -> None:
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()

        with patch(
            "api.v1.tasks.get_owned_chapter",
            AsyncMock(return_value=SimpleNamespace()),
        ) as mocked_get_chapter, patch(
            "api.v1.tasks.list_task_runs_for_chapter",
            AsyncMock(return_value=[]),
        ) as mocked_list_runs, patch(
            "api.v1.tasks.logger.warning",
        ) as mocked_warning:
            result = await tasks_for_chapter(
                chapter_id=chapter_id,
                current_user=current_user,
                session=session,
            )

        self.assertEqual(result, [])
        mocked_warning.assert_called_once()
        warning_args, warning_kwargs = mocked_warning.call_args
        self.assertEqual(warning_args[0], "legacy_chapter_endpoint_used")
        self.assertEqual(warning_kwargs["extra"]["endpoint_name"], "chapter_tasks")
        mocked_get_chapter.assert_awaited_once()
        mocked_list_runs.assert_awaited_once_with(session, chapter_id)

    async def test_project_scoped_tasks_route_rejects_project_mismatch(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()

        with patch(
            "api.v1.tasks.get_owned_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "api.v1.tasks.get_owned_chapter",
            AsyncMock(return_value=SimpleNamespace(project_id=uuid4())),
        ):
            with self.assertRaises(AppError) as raised:
                await tasks_for_story_engine_chapter(
                    project_id=project_id,
                    chapter_id=chapter_id,
                    current_user=current_user,
                    session=session,
                )

        self.assertEqual(raised.exception.code, "story_engine.chapter_project_mismatch")

    async def test_legacy_evaluate_route_emits_usage_log(self) -> None:
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()
        expected = SimpleNamespace(summary="ok")

        with patch(
            "api.v1.evaluation.evaluate_chapter",
            AsyncMock(return_value=expected),
        ) as mocked_evaluate, patch(
            "api.v1.evaluation.logger.warning",
        ) as mocked_warning:
            result = await chapter_evaluate(
                chapter_id=chapter_id,
                current_user=current_user,
                session=session,
            )

        self.assertIs(result, expected)
        mocked_warning.assert_called_once()
        warning_args, warning_kwargs = mocked_warning.call_args
        self.assertEqual(warning_args[0], "legacy_chapter_endpoint_used")
        self.assertEqual(warning_kwargs["extra"]["endpoint_name"], "chapter_evaluate")
        mocked_evaluate.assert_awaited_once_with(session, chapter_id, current_user.id)

    async def test_project_scoped_evaluate_route_rejects_project_mismatch(self) -> None:
        project_id = uuid4()
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()

        with patch(
            "api.v1.evaluation.get_owned_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "api.v1.evaluation.get_owned_chapter",
            AsyncMock(return_value=SimpleNamespace(project_id=uuid4())),
        ):
            with self.assertRaises(AppError) as raised:
                await story_engine_chapter_evaluate(
                    project_id=project_id,
                    chapter_id=chapter_id,
                    current_user=current_user,
                    session=session,
                )

        self.assertEqual(raised.exception.code, "story_engine.chapter_project_mismatch")


if __name__ == "__main__":
    unittest.main()
