from __future__ import annotations

import unittest

from agents.editor import EditorAgent


class EditorAgentFallbackTests(unittest.TestCase):
    def test_fallback_revision_respects_truth_layer_targets_and_story_bible_followups(
        self,
    ) -> None:
        agent = EditorAgent()

        revised = agent._fallback_revision(
            content="原始正文",
            issues=[],
            context_brief={"characters": ["林舟"], "locations": ["雾港"]},
            revision_plan={},
            style_preferences={"banned_patterns": []},
            truth_layer_context={
                "chapter_revision_targets": [
                    {
                        "dimension": "canon.timeline_order",
                        "fix_hint": "Move the reveal back behind the established chapter order.",
                    }
                ],
                "story_bible_followups": [
                    {
                        "dimension": "canon.relationship_integrity",
                        "fix_hint": "Bind the relationship target to an existing character profile.",
                    }
                ],
            },
        )

        self.assertIn("连续性修订重点", revised)
        self.assertIn("Move the reveal back behind the established chapter order.", revised)
        self.assertIn("需要先回写 Story Bible 基座", revised)
        self.assertIn(
            "Bind the relationship target to an existing character profile.",
            revised,
        )


if __name__ == "__main__":
    unittest.main()
