from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from agents.base import AgentRunContext
from agents.debate import DebateAgent
from agents.model_gateway import GenerationResult


class DebateAgentTests(unittest.TestCase):
    def test_build_revision_plan_orders_high_severity_first(self) -> None:
        agent = DebateAgent()

        plan = agent._build_revision_plan(
            issues=[
                {
                    "dimension": "sentence_variation",
                    "severity": "medium",
                    "message": "Too uniform.",
                },
                {
                    "dimension": "plot_tightness",
                    "severity": "high",
                    "message": "Not enough movement.",
                },
            ],
            chapter_plan={
                "title": "Fog Harbor",
                "objective": "Push the map hunt forward",
            },
            context_brief={
                "characters": ["Lin"],
                "locations": ["Harbor"],
            },
            truth_layer_context={},
        )

        self.assertEqual(plan["chapter_title"], "Fog Harbor")
        self.assertEqual(
            plan["focus_dimensions"],
            ["sentence_variation", "plot_tightness"],
        )
        self.assertEqual(plan["priorities"][0]["dimension"], "plot_tightness")
        self.assertEqual(plan["priorities"][0]["message"], "Not enough movement.")
        self.assertIn("Push the map hunt forward", plan["priorities"][0]["action"])
        self.assertIn("读完后能明确感到本章", plan["priorities"][0]["acceptance_criteria"])

    def test_build_revision_plan_carries_story_bible_followups(self) -> None:
        agent = DebateAgent()

        plan = agent._build_revision_plan(
            issues=[
                {
                    "dimension": "canon.timeline_order",
                    "severity": "high",
                    "message": "Future event surfaced too early.",
                }
            ],
            chapter_plan={
                "title": "Fog Harbor",
                "objective": "Push the map hunt forward",
            },
            context_brief={
                "characters": ["Lin"],
                "locations": ["Harbor"],
            },
            truth_layer_context={
                "status": "degraded",
                "chapter_revision_targets": [
                    {
                        "dimension": "canon.timeline_order",
                        "message": "Future event surfaced too early.",
                    }
                ],
                "story_bible_followups": [
                    {
                        "dimension": "canon.relationship_integrity",
                        "message": "Relationship references unknown character.",
                    }
                ],
            },
        )

        self.assertEqual(plan["truth_layer_status"], "degraded")
        self.assertEqual(len(plan["chapter_revision_targets"]), 1)
        self.assertEqual(len(plan["story_bible_followups"]), 1)


class DebateAgentRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_awaits_generation_calls_and_returns_summary(self) -> None:
        agent = DebateAgent(max_rounds=1)
        context = AgentRunContext(
            chapter_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={},
        )
        payload = {
            "review": {
                "ai_taste_score": 0.6,
                "issues": [
                    {
                        "dimension": "ai_taste_score",
                        "severity": "high",
                        "message": "Too templated.",
                    }
                ],
            },
            "chapter_plan": {
                "title": "Fog Harbor",
                "objective": "Push the map hunt forward",
            },
            "context_brief": {
                "characters": ["Lin"],
                "locations": ["Harbor"],
            },
            "content": "Current draft",
            "truth_layer_context": {
                "status": "degraded",
                "chapter_revision_targets": [
                    {
                        "dimension": "canon.timeline_order",
                        "message": "Future event surfaced too early.",
                    }
                ],
                "story_bible_followups": [
                    {
                        "dimension": "canon.relationship_integrity",
                        "message": "Relationship references unknown character.",
                    }
                ],
                "blocking_sources": [],
            },
        }

        mocked_generation = AsyncMock(
            side_effect=[
                GenerationResult(
                    content="Architect argument",
                    provider="local-fallback",
                    model="heuristic-v1",
                    used_fallback=True,
                ),
                GenerationResult(
                    content="Revision summary",
                    provider="local-fallback",
                    model="heuristic-v1",
                    used_fallback=True,
                ),
            ]
        )

        with patch("agents.debate.model_gateway.generate_text", mocked_generation):
            response = await agent.run(context, payload)

        self.assertTrue(response.success)
        self.assertEqual(response.data["debate_summary"]["summary"], "Revision summary")
        self.assertEqual(mocked_generation.await_count, 2)
