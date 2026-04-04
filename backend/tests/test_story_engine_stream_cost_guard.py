from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from core.circuit_breaker import token_circuit_breaker
from services.story_engine_workflow_service import run_chapter_stream_generate


class StoryEngineStreamCostGuardTests(unittest.IsolatedAsyncioTestCase):
    def tearDown(self) -> None:
        token_circuit_breaker.reset_all()

    async def test_stream_done_metadata_includes_cost_report(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        paragraph_result = SimpleNamespace(
            content="first paragraph",
            provider="openai-compatible",
            model="gpt-5.4",
            used_fallback=False,
            metadata={},
            cost=0.01,
        )
        generate_mock = AsyncMock(return_value=paragraph_result)

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
            AsyncMock(return_value="First beat"),
        ), patch(
            "services.story_engine_workflow_service._build_stream_beats",
            return_value=["First beat"],
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
        ):
            events: list[dict] = []
            async for event in run_chapter_stream_generate(
                SimpleNamespace(),
                project_id=project_id,
                user_id=user_id,
                chapter_number=7,
                chapter_title="Storm Pier",
                outline_id=None,
                current_outline="First beat",
                recent_chapters=[],
                existing_text="",
                style_sample=None,
                target_word_count=2000,
                target_paragraph_count=1,
            ):
                events.append(event)

        done_event = next(item for item in events if item["event"] == "done")
        self.assertIn("cost_report", done_event["metadata"])
        self.assertEqual(done_event["metadata"]["stream_cost_total"], 0.01)
        self.assertGreater(done_event["metadata"]["stream_token_total"], 0)

    async def test_stream_pauses_when_cost_guard_trips(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        original_budget = token_circuit_breaker.chapter_budget
        token_circuit_breaker.chapter_budget = 0.000001
        paragraph_result = SimpleNamespace(
            content="first paragraph",
            provider="openai-compatible",
            model="gpt-5.4",
            used_fallback=False,
            metadata={},
            cost=0.01,
        )
        generate_mock = AsyncMock(return_value=paragraph_result)

        try:
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
            ):
                events: list[dict] = []
                async for event in run_chapter_stream_generate(
                    SimpleNamespace(),
                    project_id=project_id,
                    user_id=user_id,
                    chapter_number=7,
                    chapter_title="Storm Pier",
                    outline_id=None,
                    current_outline="First beat\nSecond beat",
                    recent_chapters=[],
                    existing_text="",
                    style_sample=None,
                    target_word_count=2000,
                    target_paragraph_count=2,
                ):
                    events.append(event)

            guard_event = events[-1]
            self.assertEqual(guard_event["event"], "guard")
            self.assertTrue(guard_event["metadata"]["breaker_tripped"])
            self.assertEqual(guard_event["workflow_event"]["stage"], "stream_cost_guard_paused")
        finally:
            token_circuit_breaker.chapter_budget = original_budget
            token_circuit_breaker.reset_all()


if __name__ == "__main__":
    unittest.main()
