from __future__ import annotations

import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from agents.base import AgentRunContext
from agents.coordinator import CoordinatorAgent
from bus.protocol import AgentResponse


class CoordinatorAgentTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_propagates_truth_layer_context_through_revision_loop(self) -> None:
        agent = CoordinatorAgent(max_revision_rounds=2)
        context = AgentRunContext(
            chapter_id=str(uuid4()),
            project_id=str(uuid4()),
            task_id=str(uuid4()),
            payload={},
        )

        integrity_report = {
            "issue_count": 1,
            "blocking_issue_count": 0,
            "plugin_breakdown": {"relationship": 1},
            "summary": "Story Bible relationship metadata is incomplete.",
            "issues": [
                {
                    "plugin_key": "relationship",
                    "code": "relationship.unknown_character",
                    "dimension": "canon.relationship_integrity",
                    "severity": "medium",
                    "blocking": False,
                    "message": "Relationship references an unknown character.",
                    "fix_hint": "Bind the relationship target to an existing character profile.",
                    "entity_refs": [{"label": "林舟"}],
                }
            ],
        }
        first_canon_report = {
            "chapter_number": 6,
            "chapter_title": "雾港回潮",
            "issue_count": 1,
            "blocking_issue_count": 1,
            "plugin_breakdown": {"timeline": 1},
            "referenced_entities": [{"label": "雾港爆炸"}],
            "summary": "A future event appears as if it already happened.",
            "issues": [
                {
                    "plugin_key": "timeline",
                    "code": "timeline.future_event_leak",
                    "dimension": "canon.timeline_order",
                    "severity": "high",
                    "blocking": True,
                    "message": "Future event surfaced too early.",
                    "fix_hint": "Move the reveal back behind the established chapter order.",
                    "entity_refs": [{"label": "雾港爆炸"}],
                }
            ],
        }
        second_canon_report = {
            "chapter_number": 6,
            "chapter_title": "雾港回潮",
            "issue_count": 0,
            "blocking_issue_count": 0,
            "plugin_breakdown": {},
            "referenced_entities": [{"label": "雾港爆炸"}],
            "summary": "Canon validation is now clean for this round.",
            "issues": [],
        }

        agent.librarian.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "context_brief": {
                        "characters": ["林舟"],
                        "locations": ["雾港"],
                    },
                    "context_bundle": {
                        "query": "雾港 chapter 6",
                        "retrieval_backends": ["lexical"],
                        "retrieved_items": [{"type": "character"}],
                    },
                },
            )
        )
        agent.architect.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "chapter_plan": {
                        "title": "雾港回潮",
                        "objective": "让林舟确认爆炸真相的时间节点",
                    }
                },
            )
        )
        agent.writer.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "content": "初稿内容",
                    "outline": {
                        "title": "雾港回潮",
                        "objective": "让林舟确认爆炸真相的时间节点",
                    },
                },
            )
        )
        agent.canon_guardian.run = AsyncMock(
            side_effect=[
                AgentResponse(
                    success=True,
                    data={"canon_report": second_canon_report},
                ),
                AgentResponse(
                    success=True,
                    data={"canon_report": first_canon_report},
                ),
                AgentResponse(
                    success=True,
                    data={"canon_report": second_canon_report},
                ),
            ]
        )
        agent.critic.run = AsyncMock(
            side_effect=[
                AgentResponse(
                    success=True,
                    data={
                        "overall_score": 0.62,
                        "ai_taste_score": 0.21,
                        "needs_revision": True,
                        "issues": [
                            {
                                "dimension": "canon.timeline_order",
                                "severity": "high",
                                "message": "Future event surfaced too early.",
                                "blocking": True,
                            }
                        ],
                    },
                ),
                AgentResponse(
                    success=True,
                    data={
                        "overall_score": 0.83,
                        "ai_taste_score": 0.18,
                        "needs_revision": False,
                        "issues": [],
                    },
                ),
            ]
        )
        agent.debate.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "revision_plan": {
                        "objective": "让林舟确认爆炸真相的时间节点",
                        "focus_dimensions": ["canon.timeline_order"],
                        "priorities": [
                            {
                                "dimension": "canon.timeline_order",
                                "severity": "high",
                                "problem": "Future event surfaced too early.",
                                "action": "校正时间线顺序，避免未来事件提前发生或被误写成既成事实。",
                                "acceptance_criteria": "事件顺序与章节时间锚点一致，未来事件不再被提前写成既成事实。",
                                "source": "canon",
                                "action_scope": "chapter_content",
                                "plugin_key": "timeline",
                                "code": "timeline.future_event_leak",
                                "fix_hint": "Move the reveal back behind the established chapter order.",
                                "entity_labels": ["雾港爆炸"],
                            }
                        ],
                        "truth_layer_status": "blocked",
                        "chapter_revision_targets": [
                            {
                                "source": "canon",
                                "action_scope": "chapter_content",
                                "plugin_key": "timeline",
                                "code": "timeline.future_event_leak",
                                "dimension": "canon.timeline_order",
                                "severity": "high",
                                "blocking": True,
                                "message": "Future event surfaced too early.",
                                "fix_hint": "Move the reveal back behind the established chapter order.",
                                "entity_labels": ["雾港爆炸"],
                            }
                        ],
                        "story_bible_followups": [
                            {
                                "source": "story_bible_integrity",
                                "action_scope": "story_bible",
                                "plugin_key": "relationship",
                                "code": "relationship.unknown_character",
                                "dimension": "canon.relationship_integrity",
                                "severity": "medium",
                                "blocking": False,
                                "message": "Relationship references an unknown character.",
                                "fix_hint": "Bind the relationship target to an existing character profile.",
                                "entity_labels": ["林舟"],
                            }
                        ],
                    },
                    "debate_summary": {
                        "summary": "先修正文时间线，再回写 Story Bible 关系目标。",
                        "truth_layer_status": "blocked",
                        "truth_layer_blocking_sources": ["canon"],
                    },
                    "final_verdict": "needs_minor_revision",
                },
            )
        )
        agent.editor.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={"content": "修订后内容"},
            )
        )
        agent.linguistic_checker.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={"issues": []},
            )
        )
        agent.chaos_agent.run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "chaos_interventions": [],
                    "overall_chaos_score": 0.2,
                },
            )
        )
        approver_run = AsyncMock(
            return_value=AgentResponse(
                success=True,
                data={
                    "approval": {
                        "approved": False,
                        "truth_layer_status": "degraded",
                        "truth_layer_blocking_sources": [],
                    }
                },
            )
        )
        agent.approver.run = approver_run

        response = await agent.run(
            context,
            {
                "story_bible": object(),
                "chapter_number": 6,
                "chapter_title": "雾港回潮",
                "style_guidance": "压低说明句",
                "style_preferences": {"banned_patterns": []},
                "story_bible_integrity_report": integrity_report,
            },
        )

        self.assertTrue(response.success)
        self.assertEqual(response.data["initial_truth_layer_context"]["status"], "blocked")
        self.assertEqual(response.data["final_truth_layer_context"]["status"], "degraded")
        self.assertEqual(response.data["truth_layer_context"]["status"], "degraded")
        self.assertEqual(
            response.data["final_truth_layer_context"]["story_bible_followups"][0]["source"],
            "story_bible_integrity",
        )
        self.assertEqual(
            response.data["revision_focus"][0]["plugin_key"],
            "timeline",
        )
        self.assertTrue(response.data["revised"])

        debate_payload = agent.debate.run.await_args.args[1]
        self.assertEqual(debate_payload["truth_layer_context"]["status"], "blocked")

        editor_payload = agent.editor.run.await_args.args[1]
        self.assertEqual(editor_payload["truth_layer_context"]["status"], "blocked")
        self.assertEqual(
            editor_payload["truth_layer_context"]["story_bible_followups"][0]["source"],
            "story_bible_integrity",
        )

        approver_payload = approver_run.await_args.args[1]
        self.assertEqual(
            approver_payload["final_truth_layer_context"]["status"],
            "degraded",
        )


if __name__ == "__main__":
    unittest.main()
