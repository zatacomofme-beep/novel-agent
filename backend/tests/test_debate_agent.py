from __future__ import annotations

import unittest

from agents.debate import DebateAgent


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
        )

        self.assertEqual(plan["chapter_title"], "Fog Harbor")
        self.assertEqual(
            plan["focus_dimensions"],
            ["sentence_variation", "plot_tightness"],
        )
        self.assertEqual(plan["priorities"][0]["dimension"], "plot_tightness")
        self.assertIn("Push the map hunt forward", plan["priorities"][0]["action"])
        self.assertIn("读完后能明确感到本章", plan["priorities"][0]["acceptance_criteria"])
