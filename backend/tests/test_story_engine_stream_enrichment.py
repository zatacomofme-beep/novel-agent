from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.model_gateway import GenerationResult
from services.story_engine_model_service import generate_story_stream_paragraph
from services.story_engine_workflow_service import run_chapter_stream_generate


class StoryEngineStreamEnrichmentTests(unittest.IsolatedAsyncioTestCase):
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

    async def test_stream_generation_receives_social_and_causal_enrichment(self) -> None:
        project_id = uuid4()
        user_id = uuid4()
        generate_mock = AsyncMock(
            return_value=SimpleNamespace(
                content="first paragraph",
                provider="mock",
                model="mock-model",
                used_fallback=False,
                metadata={},
            )
        )

        with patch(
            "services.story_engine_workflow_service.get_story_engine_project",
            AsyncMock(return_value=SimpleNamespace()),
        ), patch(
            "services.story_engine_workflow_service.build_workspace",
            AsyncMock(
                return_value={
                    "characters": [
                        SimpleNamespace(name="Alice", character_id="char-1"),
                        SimpleNamespace(name="Bob", character_id="char-2"),
                    ],
                    "items": [SimpleNamespace(name="rusted key")],
                    "world_rules": [SimpleNamespace(rule_name="Cost Rule")],
                    "foreshadows": [SimpleNamespace(content="The gate was already open")],
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
        ), patch(
            "services.story_engine_workflow_service.foreshadowing_lifecycle_service.get_active_threads",
            AsyncMock(
                return_value=[
                    SimpleNamespace(
                        id=uuid4(),
                        planted_chapter=3,
                        entity_ref="rusted key",
                        entity_type="item",
                        potential_tags=["payoff"],
                        status="open",
                        payoff_priority=0.8,
                    )
                ]
            ),
        ), patch(
            "services.story_engine_workflow_service.social_topology_service.build_social_topology",
            AsyncMock(
                return_value=SimpleNamespace(
                    centrality_scores={"char-1": 0.9},
                    influence_graph={"char-1": ["char-2"]},
                    social_dynamics={"total_relationships": 1},
                    cluster_data={},
                )
            ),
        ), patch(
            "services.story_engine_workflow_service.neo4j_service.query_causal_paths",
            AsyncMock(return_value=[{"nodes": [{"name": "Harbor Alarm"}, {"name": "Pier Clash"}], "hops": 1}]),
        ), patch(
            "services.story_engine_workflow_service.neo4j_service.compute_character_influence",
            AsyncMock(return_value=[{"name": "Alice", "influence_score": 1.0}]),
        ):
            async for _ in run_chapter_stream_generate(
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
                pass

        kwargs = generate_mock.await_args_list[0].kwargs
        self.assertEqual(kwargs["open_threads"][0]["entity_ref"], "rusted key")
        self.assertIn("char-1", kwargs["social_topology"]["centrality_scores"])
        self.assertEqual(kwargs["causal_context"]["character_influence"][0]["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
