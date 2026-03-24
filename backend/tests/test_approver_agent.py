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

    async def test_blocking_flag_in_final_review_prevents_approval(self) -> None:
        agent = ApproverAgent()
        context = AgentRunContext(
            chapter_id="chapter-2",
            project_id="project-2",
            task_id="task-2",
            payload={},
        )

        with patch(
            "agents.approver.model_gateway.generate_text",
            new=AsyncMock(
                return_value=GenerationResult(
                    content="终审结论：规范冲突需要先修复。",
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
                        "title": "回潮",
                        "objective": "让主角安全撤离",
                    },
                    "initial_review": {
                        "overall_score": 0.74,
                        "needs_revision": True,
                        "issues": [],
                    },
                    "final_review": {
                        "overall_score": 0.81,
                        "needs_revision": False,
                        "issues": [
                            {
                                "dimension": "canon.timeline_order",
                                "severity": "medium",
                                "blocking": True,
                                "message": "未来事件被提前写成既成事实。",
                                "source": "canon",
                                "action_scope": "chapter_content",
                                "plugin_key": "timeline",
                                "code": "timeline.future_event_claimed_as_past",
                                "fix_hint": "把未来事件改成传闻或预测，不要写成已发生。",
                                "entity_labels": ["雾港回潮"],
                            }
                        ],
                    },
                    "revision_plan": {"priorities": []},
                },
            )

        self.assertTrue(response.success)
        approval = response.data["approval"]
        self.assertFalse(approval["approved"])
        self.assertEqual(len(approval["blocking_issues"]), 1)
        self.assertTrue(approval["blocking_issues"][0]["blocking"])
        self.assertEqual(approval["blocking_issues"][0]["plugin_key"], "timeline")
        self.assertEqual(
            approval["blocking_issues"][0]["code"],
            "timeline.future_event_claimed_as_past",
        )
        self.assertEqual(
            approval["blocking_issues"][0]["entity_labels"],
            ["雾港回潮"],
        )

    async def test_truth_layer_blockers_prevent_approval(self) -> None:
        agent = ApproverAgent()
        context = AgentRunContext(
            chapter_id="chapter-3",
            project_id="project-3",
            task_id="task-3",
            payload={},
        )

        with patch(
            "agents.approver.model_gateway.generate_text",
            new=AsyncMock(
                return_value=GenerationResult(
                    content="终审结论：真相层阻塞需要先修复。",
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
                        "title": "回潮",
                        "objective": "让主角安全撤离",
                    },
                    "initial_review": {
                        "overall_score": 0.74,
                        "needs_revision": True,
                        "issues": [],
                    },
                    "final_review": {
                        "overall_score": 0.84,
                        "needs_revision": False,
                        "issues": [],
                    },
                    "revision_plan": {"priorities": []},
                    "final_truth_layer_context": {
                        "status": "blocked",
                        "blocking_sources": ["story_bible_integrity"],
                        "story_bible_followups": [
                            {
                                "dimension": "canon.item_ownership",
                                "message": "Item owner is unknown.",
                            }
                        ],
                        "priority_findings": [
                            {
                                "dimension": "canon.item_ownership",
                                "severity": "high",
                                "blocking": True,
                                "message": "Item owner is unknown.",
                                "source": "story_bible_integrity",
                                "action_scope": "story_bible",
                                "plugin_key": "item",
                                "code": "item.owner_missing",
                                "fix_hint": "补充该物品的持有者或归属关系。",
                                "entity_labels": ["潮汐钥匙"],
                            }
                        ],
                    },
                },
            )

        self.assertTrue(response.success)
        approval = response.data["approval"]
        self.assertFalse(approval["approved"])
        self.assertEqual(approval["truth_layer_status"], "blocked")
        self.assertEqual(
            approval["truth_layer_blocking_sources"],
            ["story_bible_integrity"],
        )
        self.assertEqual(len(approval["blocking_issues"]), 1)
        self.assertEqual(
            approval["blocking_issues"][0]["source"],
            "story_bible_integrity",
        )
        self.assertEqual(approval["blocking_issues"][0]["plugin_key"], "item")
        self.assertEqual(
            approval["blocking_issues"][0]["code"],
            "item.owner_missing",
        )
        self.assertEqual(
            approval["blocking_issues"][0]["fix_hint"],
            "补充该物品的持有者或归属关系。",
        )
        self.assertEqual(
            approval["blocking_issues"][0]["entity_labels"],
            ["潮汐钥匙"],
        )
