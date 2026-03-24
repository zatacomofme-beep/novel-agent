from __future__ import annotations

import unittest

from tasks.chapter_generation import _build_result_event_payload


class TaskPayloadTests(unittest.TestCase):
    def test_build_result_event_payload_collects_observability_fields(self) -> None:
        payload = _build_result_event_payload(
            {
                "chapter_id": "chapter-1",
                "chapter_status": "review",
                "revised": True,
                "evaluation": {
                    "overall_score": 0.84,
                    "ai_taste_score": 0.23,
                    "issues": [{"dimension": "pace"}, {"dimension": "tone"}],
                },
                "initial_review": {
                    "overall_score": 0.62,
                    "needs_revision": True,
                    "issues": [
                        {"dimension": "ai_taste_score"},
                        {"dimension": "plot_tightness"},
                        {"dimension": "sentence_variation"},
                    ],
                },
                "final_review": {
                    "overall_score": 0.79,
                    "needs_revision": False,
                    "issues": [{"dimension": "sentence_variation"}],
                },
                "canon_report": {
                    "issue_count": 3,
                    "blocking_issue_count": 1,
                    "plugin_breakdown": {
                        "character": 1,
                        "timeline": 2,
                    },
                    "referenced_entities": [{"label": "林舟"}, {"label": "雾港爆炸"}],
                },
                "initial_canon_report": {
                    "issue_count": 4,
                    "blocking_issue_count": 2,
                },
                "story_bible_integrity_report": {
                    "issue_count": 2,
                    "blocking_issue_count": 0,
                    "plugin_breakdown": {
                        "relationship": 1,
                        "item": 1,
                    },
                },
                "revision_plan": {
                    "focus_dimensions": ["ai_taste_score", "plot_tightness"],
                    "priorities": [
                        {"dimension": "ai_taste_score"},
                        {"dimension": "plot_tightness"},
                    ],
                },
                "truth_layer_context": {
                    "status": "blocked",
                    "blocking_sources": ["canon"],
                    "chapter_revision_targets": [
                        {"dimension": "canon.timeline_order"},
                        {"dimension": "canon.character_introduction"},
                    ],
                    "story_bible_followups": [
                        {"dimension": "canon.relationship_integrity"},
                    ],
                },
                "story_bible_followup_proposals": [
                    {
                        "trigger_type": "plot_thread_progressed",
                        "changed_section": "plot_threads",
                        "entity_key": "title:雾港爆炸",
                    },
                    {
                        "trigger_type": "timeline_event_occurred",
                        "changed_section": "timeline_events",
                        "entity_key": "title:雾港爆炸",
                    },
                ],
                "approval": {
                    "approved": True,
                    "release_recommendation": "可进入 review 阶段",
                    "score_delta": 0.17,
                    "blocking_issues": [],
                },
                "context_bundle": {
                    "query": "fog harbor chapter 2",
                    "retrieval_backends": ["lexical", "qdrant"],
                    "retrieved_items": [{"type": "character"}, {"type": "location"}],
                },
                "agent_trace": [
                    {
                        "agent": "architect",
                        "data": {
                            "chapter_plan": {
                                "generation": {
                                    "provider": "openai",
                                    "used_fallback": False,
                                    "metadata": {},
                                }
                            }
                        },
                    },
                    {
                        "agent": "writer",
                        "data": {
                            "generation": {
                                "provider": "openai",
                                "used_fallback": False,
                                "metadata": {},
                            }
                        },
                    },
                    {
                        "agent": "editor",
                        "data": {
                            "generation": {
                                "provider": "local-fallback",
                                "used_fallback": True,
                                "metadata": {
                                    "remote_error": {
                                        "error_type": "rate_limit",
                                    }
                                },
                            }
                        },
                    },
                ],
            }
        )

        self.assertEqual(payload["chapter_id"], "chapter-1")
        self.assertEqual(payload["chapter_status"], "review")
        self.assertTrue(payload["revised"])
        self.assertEqual(payload["agent_count"], 3)
        self.assertEqual(payload["issue_count"], 2)
        self.assertEqual(payload["initial_issue_count"], 3)
        self.assertEqual(payload["final_issue_count"], 1)
        self.assertTrue(payload["initial_needs_revision"])
        self.assertFalse(payload["final_needs_revision"])
        self.assertEqual(payload["initial_canon_issue_count"], 4)
        self.assertEqual(payload["initial_canon_blocking_issue_count"], 2)
        self.assertEqual(payload["integrity_issue_count"], 2)
        self.assertEqual(payload["integrity_blocking_issue_count"], 0)
        self.assertEqual(payload["integrity_plugins"], ["item", "relationship"])
        self.assertEqual(payload["canon_issue_count"], 3)
        self.assertEqual(payload["canon_blocking_issue_count"], 1)
        self.assertEqual(payload["canon_plugins"], ["character", "timeline"])
        self.assertEqual(payload["canon_referenced_entities"], 2)
        self.assertEqual(payload["truth_layer_status"], "blocked")
        self.assertEqual(payload["truth_layer_blocking_sources"], ["canon"])
        self.assertEqual(payload["truth_layer_chapter_target_count"], 2)
        self.assertEqual(payload["truth_layer_story_bible_followup_count"], 1)
        self.assertEqual(payload["story_bible_followup_proposal_count"], 2)
        self.assertEqual(
            payload["story_bible_followup_trigger_types"],
            ["plot_thread_progressed", "timeline_event_occurred"],
        )
        self.assertEqual(payload["revision_plan_steps"], 2)
        self.assertEqual(
            payload["revision_focus_dimensions"],
            ["ai_taste_score", "plot_tightness"],
        )
        self.assertTrue(payload["approved"])
        self.assertEqual(payload["blocking_issue_count"], 0)
        self.assertEqual(payload["retrieval_items"], 2)
        self.assertEqual(payload["retrieval_backends"], ["lexical", "qdrant"])
        self.assertIn("architect:openai", payload["providers"])
        self.assertIn("editor:local-fallback", payload["providers"])
        self.assertEqual(payload["fallback_agents"], ["editor"])
        self.assertEqual(payload["remote_error_types"], ["rate_limit"])
