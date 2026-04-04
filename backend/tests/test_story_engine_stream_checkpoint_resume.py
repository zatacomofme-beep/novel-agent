from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from services.story_engine_workflow_service import run_chapter_stream_generate


def _mock_generation(text: str) -> SimpleNamespace:
    return SimpleNamespace(
        content=text,
        provider="mock",
        model="mock-model",
        used_fallback=False,
        metadata={},
        cost=0.0,
    )


class StoryEngineStreamCheckpointResumeTests(unittest.IsolatedAsyncioTestCase):
    async def test_stream_uses_legacy_generation_checkpoint_when_no_existing_text(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        chapter_id = uuid4()
        generate_mock = AsyncMock(return_value=_mock_generation("next paragraph"))
        checkpoint = SimpleNamespace(
            id=uuid4(),
            chapter_version_number=3,
            generated_content="para one\n\npara two",
            segments_completed=2,
            segments_total=4,
            progress=50,
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [],
                    "items": [],
                    "world_rules": [],
                    "foreshadows": [],
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="First beat\nSecond beat\nThird beat"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["First beat", "Second beat", "Third beat"],
        ), patch(
            "services.story_engine_workflow_service._resolve_workflow_chapter_id",
            AsyncMock(return_value=chapter_id),
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            AsyncMock(
                return_value={
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.CheckpointService.get_latest_generation_checkpoint",
            AsyncMock(return_value=checkpoint),
        ), patch(
            "services.story_engine_workflow_service.CheckpointService.can_resume",
            return_value=True,
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_id=chapter_id,
                chapter_number=7,
                chapter_title="Storm Pier",
                outline_id=None,
                current_outline="First beat\nSecond beat\nThird beat",
                recent_chapters=[],
                existing_text="",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=3,
            ):
                events.append(event)

        start_event = next(item for item in events if item["event"] == "start")
        self.assertEqual(start_event["metadata"]["status"], "resumed")
        self.assertEqual(start_event["metadata"]["resume_from_paragraph"], 3)
        self.assertEqual(
            start_event["metadata"]["legacy_checkpoint_resume"]["checkpoint_version_number"],
            3,
        )
        self.assertIn("para one", start_event["text"])
        self.assertEqual(generate_mock.await_args_list[0].kwargs["paragraph_index"], 3)
        self.assertEqual(generate_mock.await_args_list[0].kwargs["draft_text"], "para one\n\npara two")

    async def test_stream_ignores_legacy_checkpoint_when_existing_text_present(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        chapter_id = uuid4()
        generate_mock = AsyncMock(return_value=_mock_generation("next paragraph"))

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [],
                    "items": [],
                    "world_rules": [],
                    "foreshadows": [],
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.resolve_story_engine_model_routing",
            return_value={},
        ), patch(
            "services.story_engine_workflow_service._resolve_stream_outline_text",
            AsyncMock(return_value="First beat\nSecond beat"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["First beat", "Second beat"],
        ), patch(
            "services.story_engine_workflow_service._resolve_workflow_chapter_id",
            AsyncMock(return_value=chapter_id),
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            AsyncMock(
                return_value={
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                }
            ),
        ), patch(
            "services.story_engine_workflow_service.CheckpointService.get_latest_generation_checkpoint",
            AsyncMock(),
        ) as mocked_checkpoint:
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_id=chapter_id,
                chapter_number=7,
                chapter_title="Storm Pier",
                outline_id=None,
                current_outline="First beat\nSecond beat",
                recent_chapters=[],
                existing_text="manual draft",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=2,
            ):
                events.append(event)

        start_event = next(item for item in events if item["event"] == "start")
        mocked_checkpoint.assert_not_awaited()
        self.assertIsNone(start_event["metadata"].get("legacy_checkpoint_resume"))


if __name__ == "__main__":
    unittest.main()
