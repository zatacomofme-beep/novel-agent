from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from agents.approver import ApproverAgent
from agents.base import AgentRunContext
from agents.model_gateway import GenerationResult


class ApproverAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_returns_approval_summary_and_blocking_issues(self) -> None:
        agent = ApproverAgent()
        context = AgentRunContext(
            chapter_id="chapter-1",
            project_id="project-1",
            task_id="task-1",
            payload={},
        )

        with patch(
            "agents.approver.model_gateway.generate_text",
            new=AsyncMock(
                return_value=GenerationResult(
                    content="终审结论：仍需修订。",
                    provider="openai",
                    model="gpt-test",
                    metadata={"source": "unit-test"},
                )
            ),
        ):
            response = await agent.run(
                context,
                {
                    "outline": {
                        "title": "雾港",
                        "objective": "让主角完成第一次潜入",
                    },
                    "initial_review": {
                        "overall_score": 0.51,
                        "needs_revision": True,
                        "issues": [
                            {
                                "dimension": "plot_tightness",
                                "severity": "high",
                                "message": "推进不足",
                            }
                        ],
                    },
                    "final_review": {
                        "overall_score": 0.71,
                        "needs_revision": False,
                        "issues": [
                            {
                                "dimension": "plot_tightness",
                                "severity": "high",
                                "message": "高潮仍未落地",
                            },
                            {
                                "dimension": "sentence_variation",
                                "severity": "medium",
                                "message": "句式略单一",
                            },
                        ],
                    },
                    "revision_plan": {
                        "priorities": [
                            {"dimension": "plot_tightness"},
                            {"dimension": "sentence_variation"},
                        ]
                    },
                },
            )

        self.assertTrue(response.success)
        approval = response.data["approval"]
        self.assertFalse(approval["approved"])
        self.assertEqual(approval["target"], "让主角完成第一次潜入")
        self.assertAlmostEqual(approval["score_delta"], 0.20, places=6)
        self.assertEqual(approval["revision_plan_steps"], 2)
        self.assertEqual(approval["release_recommendation"], "建议继续修订后再进入 review/final")
        self.assertEqual(approval["summary"], "终审结论：仍需修订。")
        self.assertEqual(len(approval["blocking_issues"]), 1)
        self.assertEqual(approval["blocking_issues"][0]["dimension"], "plot_tightness")
        self.assertEqual(approval["generation"]["provider"], "openai")
        self.assertEqual(context.trace[-1]["agent"], "approver")
