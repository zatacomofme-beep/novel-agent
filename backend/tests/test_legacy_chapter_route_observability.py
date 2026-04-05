from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from api.v1.chapters import chapter_generate, get_beta_reader_feedback


class LegacyChapterRouteObservabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_beta_reader_emits_legacy_usage_log(self) -> None:
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()
        chapter = SimpleNamespace(project_id=uuid4())
        beta_result = SimpleNamespace(success=True, data={"summary": "ok"}, error=None)

        with patch(
            "api.v1.chapters.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ) as mocked_get_chapter, patch(
            "agents.beta_reader.BetaReaderAgent",
        ) as mocked_beta_reader_cls, patch(
            "agents.base.AgentRunContext",
        ) as mocked_context_cls, patch(
            "api.v1.chapters.logger.warning",
        ) as mocked_warning:
            mocked_beta_reader = mocked_beta_reader_cls.return_value
            mocked_beta_reader.run = AsyncMock(return_value=beta_result)
            result = await get_beta_reader_feedback(
                chapter_id=chapter_id,
                body={"content": "片段", "genre": "悬疑", "target_audience": "adult"},
                current_user=current_user,
                session=session,
            )

        self.assertEqual(result, {"success": True, "beta_feedback": {"summary": "ok"}})
        mocked_warning.assert_called_once()
        warning_args, warning_kwargs = mocked_warning.call_args
        self.assertEqual(warning_args[0], "legacy_chapter_endpoint_used")
        self.assertEqual(warning_kwargs["extra"]["endpoint_name"], "chapter_beta_reader")
        self.assertEqual(warning_kwargs["extra"]["chapter_id"], str(chapter_id))
        self.assertEqual(warning_kwargs["extra"]["user_id"], str(current_user.id))
        mocked_get_chapter.assert_awaited_once_with(
            session,
            chapter_id,
            current_user.id,
            permission="read",
        )
        mocked_context_cls.assert_called_once()
        mocked_beta_reader.run.assert_awaited_once()

    async def test_chapter_generate_emits_legacy_usage_log(self) -> None:
        chapter_id = uuid4()
        current_user = SimpleNamespace(id=uuid4())
        session = SimpleNamespace()
        chapter = SimpleNamespace(id=chapter_id, project_id=uuid4())
        expected_task = SimpleNamespace(task_id=str(uuid4()))

        with patch(
            "api.v1.chapters.get_owned_chapter",
            AsyncMock(return_value=chapter),
        ) as mocked_get_chapter, patch(
            "api.v1.chapters.dispatch_legacy_generation_for_chapter",
            AsyncMock(return_value=expected_task),
        ) as mocked_dispatch, patch(
            "api.v1.chapters.logger.warning",
        ) as mocked_warning:
            result = await chapter_generate(
                chapter_id=chapter_id,
                current_user=current_user,
                session=session,
            )

        self.assertIs(result, expected_task)
        mocked_warning.assert_called_once()
        warning_args, warning_kwargs = mocked_warning.call_args
        self.assertEqual(warning_args[0], "legacy_chapter_endpoint_used")
        self.assertEqual(warning_kwargs["extra"]["endpoint_name"], "chapter_generate")
        self.assertEqual(warning_kwargs["extra"]["chapter_id"], str(chapter_id))
        self.assertEqual(warning_kwargs["extra"]["user_id"], str(current_user.id))
        mocked_get_chapter.assert_awaited_once_with(
            session,
            chapter_id,
            current_user.id,
            permission="edit",
        )
        mocked_dispatch.assert_awaited_once_with(
            session,
            chapter=chapter,
            user_id=current_user.id,
        )


if __name__ == "__main__":
    unittest.main()
