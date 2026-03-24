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
    )


class StoryEngineChapterStreamServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_pause_event_contains_resume_metadata(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(return_value=_mock_generation("第一段正文"))

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
            AsyncMock(return_value="开场推进\n结尾钩子"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["开场推进", "结尾钩子"],
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            AsyncMock(
                return_value={
                    "passed": False,
                    "should_pause": True,
                    "alerts": [
                        {
                            "severity": "high",
                            "title": "人设冲突",
                            "detail": "主角明明怕水，这里却毫无迟疑地跳海。",
                            "source": "guardian",
                            "suggestion": "补出迟疑和代价。",
                        }
                    ],
                    "repair_options": ["补出主角对水的本能恐惧，再安排他硬着头皮下水。"],
                    "arbitration_note": "这一处如果不修，后面的人设会直接崩。",
                }
            ),
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="开场推进\n结尾钩子",
                recent_chapters=[],
                existing_text="",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=2,
            ):
                events.append(event)

        guard_event = next(item for item in events if item["event"] == "guard")
        self.assertEqual(guard_event["paragraph_index"], 1)
        self.assertEqual(guard_event["paragraph_total"], 2)
        self.assertEqual(guard_event["metadata"]["paused_at_paragraph"], 1)
        self.assertEqual(guard_event["metadata"]["next_paragraph_index"], 2)
        self.assertEqual(guard_event["metadata"]["current_beat"], "开场推进")
        self.assertEqual(guard_event["metadata"]["remaining_beats"], ["结尾钩子"])
        self.assertEqual(
            guard_event["guard_result"]["repair_options"],
            ["补出主角对水的本能恐惧，再安排他硬着头皮下水。"],
        )

    async def test_resume_rewrites_latest_paragraph_and_continues_from_next_beat(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(
            side_effect=[
                _mock_generation("修正版第二段"),
                _mock_generation("第三段正文"),
            ]
        )
        guard_mock = AsyncMock(
            side_effect=[
                {
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                },
                {
                    "passed": True,
                    "should_pause": False,
                    "alerts": [],
                    "repair_options": [],
                    "arbitration_note": None,
                },
            ]
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
            AsyncMock(return_value="第一段推进\n第二段推进\n第三段推进"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["第一段推进", "第二段推进", "第三段推进"],
        ), patch(
            "services.story_engine_workflow_service.generate_story_stream_paragraph",
            generate_mock,
        ), patch(
            "services.story_engine_workflow_service.run_realtime_guard",
            guard_mock,
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="海上夜奔",
                outline_id=None,
                current_outline="第一段推进\n第二段推进\n第三段推进",
                recent_chapters=[],
                existing_text="第一段旧稿\n\n第二段旧稿",
                style_sample=None,
                target_word_count=2400,
                target_paragraph_count=3,
                resume_from_paragraph=3,
                repair_instruction="把主角怕水的迟疑和代价写回来",
                rewrite_latest_paragraph=True,
            ):
                events.append(event)

        start_event = next(item for item in events if item["event"] == "start")
        chunk_event = next(item for item in events if item["event"] == "chunk")
        done_event = next(item for item in events if item["event"] == "done")

        self.assertEqual(start_event["metadata"]["status"], "resumed")
        self.assertEqual(start_event["metadata"]["rewritten_paragraph_index"], 2)
        self.assertIn("修正版第二段", start_event["text"])
        self.assertNotIn("第二段旧稿", start_event["text"])
        self.assertEqual(chunk_event["paragraph_index"], 3)
        self.assertIn("第三段正文", chunk_event["text"])
        self.assertTrue(done_event["metadata"]["resume_mode"])

        self.assertEqual(generate_mock.await_args_list[0].kwargs["paragraph_index"], 2)
        self.assertEqual(
            generate_mock.await_args_list[0].kwargs["repair_instruction"],
            "把主角怕水的迟疑和代价写回来",
        )
        self.assertEqual(generate_mock.await_args_list[1].kwargs["paragraph_index"], 3)
        self.assertEqual(
            generate_mock.await_args_list[1].kwargs["draft_text"],
            "第一段旧稿\n\n修正版第二段",
        )
        self.assertEqual(guard_mock.await_args_list[0].kwargs["latest_paragraph"], "修正版第二段")
        self.assertEqual(guard_mock.await_args_list[1].kwargs["latest_paragraph"], "第三段正文")
