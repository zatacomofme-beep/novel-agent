from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.story_engine_kb_resolution_service import (
    resolve_chapter_summary_kb_suggestion,
)


class StoryEngineKBResolutionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_apply_kb_suggestion_updates_status_and_returns_entity_meta(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        summary_id = uuid4()
        applied_entity_id = uuid4()
        summary = SimpleNamespace(
            summary_id=summary_id,
            chapter_number=12,
            kb_update_suggestions=[
                {
                    "suggestion_id": "sg-1",
                    "entity_type": "timeline_events",
                    "action": "upsert",
                    "status": "pending",
                    "chapter_number": 12,
                    "core_event": "雾海在夜里突然倒涌。",
                }
            ],
        )
        updated_summary = SimpleNamespace(
            summary_id=summary_id,
            chapter_number=12,
            kb_update_suggestions=[
                {
                    "suggestion_id": "sg-1",
                    "entity_type": "timeline_events",
                    "action": "upsert",
                    "status": "applied",
                }
            ],
        )

        with patch(
            "services.story_engine_kb_resolution_service.get_entity",
            AsyncMock(return_value=summary),
        ), patch(
            "services.story_engine_kb_resolution_service._apply_pending_kb_suggestion",
            AsyncMock(
                return_value={
                    "applied_entity_type": "timeline_events",
                    "applied_entity_id": applied_entity_id,
                    "applied_entity_label": "雾海在夜里突然倒涌。",
                    "message": "已记入时间线。",
                }
            ),
        ), patch(
            "services.story_engine_kb_resolution_service.update_entity",
            AsyncMock(return_value=updated_summary),
        ) as mocked_update:
            result = await resolve_chapter_summary_kb_suggestion(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                summary_id=summary_id,
                suggestion_id="sg-1",
                action="apply",
            )

        saved_suggestions = mocked_update.await_args.kwargs["payload"]["kb_update_suggestions"]
        self.assertEqual(saved_suggestions[0]["status"], "applied")
        self.assertEqual(result["resolved_suggestion"]["status"], "applied")
        self.assertEqual(result["applied_entity_type"], "timeline_events")
        self.assertEqual(result["applied_entity_id"], applied_entity_id)

    async def test_ignore_kb_suggestion_marks_it_ignored_without_apply_side_effect(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        summary_id = uuid4()
        summary = SimpleNamespace(
            summary_id=summary_id,
            chapter_number=3,
            kb_update_suggestions=[
                {
                    "suggestion_id": "sg-ignore",
                    "entity_type": "foreshadows",
                    "action": "upsert",
                    "status": "pending",
                    "chapter_number": 3,
                    "content": "窗台上多了一枚陌生指纹。",
                }
            ],
        )
        updated_summary = SimpleNamespace(
            summary_id=summary_id,
            chapter_number=3,
            kb_update_suggestions=[
                {
                    "suggestion_id": "sg-ignore",
                    "entity_type": "foreshadows",
                    "action": "upsert",
                    "status": "ignored",
                }
            ],
        )

        with patch(
            "services.story_engine_kb_resolution_service.get_entity",
            AsyncMock(return_value=summary),
        ), patch(
            "services.story_engine_kb_resolution_service._apply_pending_kb_suggestion",
            AsyncMock(),
        ) as mocked_apply, patch(
            "services.story_engine_kb_resolution_service.update_entity",
            AsyncMock(return_value=updated_summary),
        ) as mocked_update:
            result = await resolve_chapter_summary_kb_suggestion(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                summary_id=summary_id,
                suggestion_id="sg-ignore",
                action="ignore",
            )

        mocked_apply.assert_not_awaited()
        saved_suggestions = mocked_update.await_args.kwargs["payload"]["kb_update_suggestions"]
        self.assertEqual(saved_suggestions[0]["status"], "ignored")
        self.assertEqual(result["resolved_suggestion"]["status"], "ignored")
        self.assertIn("忽略", result["message"])
