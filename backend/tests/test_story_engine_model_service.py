from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from agents.model_gateway import GenerationResult
from services.story_engine_model_service import generate_story_stream_paragraph


class StoryEngineModelServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_story_stream_paragraph_fails_over_to_backup_model(self) -> None:
        gateway_mock = AsyncMock(
            side_effect=[
                GenerationResult(
                    content="本地兜底正文",
                    provider="local-fallback",
                    model="heuristic-v1",
                    used_fallback=True,
                    metadata={
                        "selected_provider": "openai-compatible",
                        "remote_error": {
                            "error_type": "auth",
                            "status_code": 403,
                            "message": "user quota is not enough",
                        },
                    },
                ),
                GenerationResult(
                    content="海风压低了船舷，陆沉把发白的指节从栏杆上松开，先盯住浪头，再盯住对面的人。",
                    provider="openai-compatible",
                    model="deepseek-v3.2",
                    used_fallback=False,
                    metadata={
                        "selected_provider": "openai-compatible",
                    },
                ),
            ]
        )

        with patch(
            "services.story_engine_model_service.model_gateway.generate_text",
            gateway_mock,
        ):
            result = await generate_story_stream_paragraph(
                chapter_number=7,
                chapter_title="海上夜奔",
                beat="逼主角在众人面前接下危险任务",
                paragraph_index=1,
                paragraph_total=4,
                draft_text="",
                outline_text="开场逼迫主角表态，结尾抛出更深海域的异常。",
                style_sample="海风从巷口灌进来，他只抬了抬眼，没有让半步。",
                workspace={
                    "characters": [SimpleNamespace(name="陆沉")],
                    "world_rules": [SimpleNamespace(rule_name="代价规则", rule_content="越级爆发必须付出代价")],
                    "foreshadows": [SimpleNamespace(content="海面下方像是有什么东西睁开了眼")],
                    "items": [SimpleNamespace(name="镇潮玉")],
                },
                recent_chapters=["上一章末尾，他刚刚承认自己其实怕水。"],
                fallback="本地兜底正文",
                model_routing={
                    "stream_writer": {"model": "gpt-5.4", "reasoning_effort": "medium"},
                    "commercial": {"model": "deepseek-v3.2", "reasoning_effort": "medium"},
                    "style_guardian": {
                        "model": "gemini-3.1-pro-preview",
                        "reasoning_effort": "medium",
                    },
                },
                repair_instruction="补出主角怕水却不得不接下任务的迟疑",
            )

        self.assertEqual(result.model, "deepseek-v3.2")
        self.assertFalse(result.used_fallback)
        self.assertTrue(result.metadata["stream_failover_triggered"])
        self.assertEqual(result.metadata["stream_selected_role"], "commercial")
        self.assertEqual(len(result.metadata["stream_failover_attempts"]), 1)
        self.assertEqual(
            result.metadata["stream_failover_attempts"][0]["error_type"],
            "auth",
        )
        self.assertEqual(
            [call.args[0].model for call in gateway_mock.await_args_list],
            ["gpt-5.4", "deepseek-v3.2"],
        )

    async def test_generate_story_stream_paragraph_does_not_failover_for_unknown_error(self) -> None:
        gateway_mock = AsyncMock(
            return_value=GenerationResult(
                content="本地兜底正文",
                provider="local-fallback",
                model="heuristic-v1",
                used_fallback=True,
                metadata={
                    "selected_provider": "openai-compatible",
                    "remote_error": {
                        "error_type": "unknown",
                        "status_code": 400,
                        "message": "schema mismatch",
                    },
                },
            )
        )

        with patch(
            "services.story_engine_model_service.model_gateway.generate_text",
            gateway_mock,
        ):
            result = await generate_story_stream_paragraph(
                chapter_number=7,
                chapter_title="海上夜奔",
                beat="逼主角在众人面前接下危险任务",
                paragraph_index=1,
                paragraph_total=4,
                draft_text="",
                outline_text="开场逼迫主角表态，结尾抛出更深海域的异常。",
                style_sample=None,
                workspace={"characters": [], "world_rules": [], "foreshadows": [], "items": []},
                recent_chapters=[],
                fallback="本地兜底正文",
                model_routing={
                    "stream_writer": {"model": "gpt-5.4", "reasoning_effort": "medium"},
                    "commercial": {"model": "deepseek-v3.2", "reasoning_effort": "medium"},
                },
            )

        self.assertTrue(result.used_fallback)
        self.assertFalse(result.metadata["stream_failover_triggered"])
        self.assertEqual(gateway_mock.await_count, 1)

    async def test_generate_story_stream_paragraph_includes_enrichment_hints(self) -> None:
        gateway_mock = AsyncMock(
            return_value=GenerationResult(
                content="Alice kept moving.",
                provider="openai-compatible",
                model="gpt-5.4",
                used_fallback=False,
                metadata={},
            )
        )

        with patch(
            "services.story_engine_model_service.model_gateway.generate_text",
            gateway_mock,
        ):
            await generate_story_stream_paragraph(
                chapter_number=7,
                chapter_title="Storm Pier",
                beat="Push the protagonist into the next choice",
                paragraph_index=2,
                paragraph_total=4,
                draft_text="Existing draft",
                outline_text="Outline",
                style_sample=None,
                workspace={
                    "characters": [
                        SimpleNamespace(name="Alice", character_id="char-1"),
                        SimpleNamespace(name="Bob", character_id="char-2"),
                    ],
                    "world_rules": [SimpleNamespace(rule_name="Cost Rule", rule_content="Every surge has a price")],
                    "foreshadows": [SimpleNamespace(content="The gate was already open")],
                    "items": [SimpleNamespace(name="rusted key")],
                },
                recent_chapters=["Alice discovered the gate was tampered with."],
                fallback="fallback",
                model_routing={"stream_writer": {"model": "gpt-5.4", "reasoning_effort": "medium"}},
                social_topology={"centrality_scores": {"char-1": 0.9, "char-2": 0.4}},
                causal_context={
                    "causal_paths": [{"nodes": [{"name": "Harbor Alarm"}, {"name": "Pier Clash"}]}],
                    "character_influence": [{"name": "Alice"}],
                },
                open_threads=[{"entity_ref": "rusted key", "entity_type": "item"}],
            )

        request = gateway_mock.await_args.args[0]
        self.assertIn("Alice", request.prompt)
        self.assertIn("Harbor Alarm", request.prompt)
        self.assertIn("rusted key", request.prompt)

