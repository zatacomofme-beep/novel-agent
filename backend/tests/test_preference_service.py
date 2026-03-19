from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from schemas.preferences import PreferenceLearningSnapshot
from services.preference_service import (
    apply_style_template_values,
    build_style_guidance,
    build_preference_learning_snapshot,
    calculate_preference_completion,
    infer_preference_observation,
    list_style_templates,
    resolve_generation_preference_payload,
)


class PreferenceServiceTests(unittest.TestCase):
    def test_build_style_guidance_includes_custom_constraints(self) -> None:
        guidance = build_style_guidance(
            SimpleNamespace(
                prose_style="lyrical",
                narrative_mode="first_person",
                pacing_preference="fast",
                dialogue_preference="dialogue_forward",
                tension_preference="high_tension",
                sensory_density="immersive",
                favored_elements=["身体感", "潜台词"],
                banned_patterns=["总结式结尾"],
                custom_style_notes="避免解释性说教。",
            )
        )

        self.assertIn("第一人称", guidance)
        self.assertIn("快推进", guidance)
        self.assertIn("身体感", guidance)
        self.assertIn("总结式结尾", guidance)
        self.assertIn("避免解释性说教", guidance)

    def test_build_style_guidance_includes_learning_summary_when_available(self) -> None:
        guidance = build_style_guidance(
            SimpleNamespace(
                active_template_key="cold_thriller",
                prose_style="precise",
                narrative_mode="close_third",
                pacing_preference="balanced",
                dialogue_preference="balanced",
                tension_preference="balanced",
                sensory_density="focused",
                favored_elements=[],
                banned_patterns=[],
                custom_style_notes=None,
            ),
            PreferenceLearningSnapshot(
                observation_count=3,
                last_observed_at=datetime.now(timezone.utc),
                source_breakdown={"manual_update": 2, "rollback": 1},
                stable_preferences=[],
                favored_elements=["动作链"],
                summary="来自最近 3 次人工内容变更。高频保留元素：动作链。",
            ),
        )

        self.assertIn("隐式学习信号", guidance)
        self.assertIn("动作链", guidance)
        self.assertIn("冷锋追缉", guidance)

    def test_calculate_preference_completion_counts_only_configured_fields(self) -> None:
        score = calculate_preference_completion(
            SimpleNamespace(
                prose_style="precise",
                narrative_mode="close_third",
                pacing_preference="balanced",
                dialogue_preference="balanced",
                tension_preference="balanced",
                sensory_density="focused",
                favored_elements=["潜台词"],
                banned_patterns=[],
                custom_style_notes="",
            )
        )

        self.assertAlmostEqual(score, 0.11, places=2)

    def test_infer_preference_observation_extracts_dialogue_and_first_person_signals(self) -> None:
        observation = infer_preference_observation(
            "\n".join(
                [
                    "“你来晚了。”我把门推开，雨水顺着指尖往下滴。",
                    "我盯着他，听见走廊尽头的脚步声越来越近，心跳一下下砸在喉咙口。",
                    "“别解释。”我说，“先跟我走。”",
                    "他沉默了一秒，只是看着我，像是还有话没说。",
                    "我转身就跑，风从楼道里猛地灌进来，脚步和呼吸都在发颤。",
                ]
            )
        )

        observed_preferences = observation["observed_preferences"]

        self.assertEqual(observed_preferences["narrative_mode"]["value"], "first_person")
        self.assertEqual(
            observed_preferences["dialogue_preference"]["value"],
            "dialogue_forward",
        )
        self.assertIn("对话推进", observation["favored_elements"])

    def test_build_preference_learning_snapshot_aggregates_stable_signals(self) -> None:
        now = datetime.now(timezone.utc)
        snapshot = build_preference_learning_snapshot(
            [
                SimpleNamespace(
                    source_type="manual_update",
                    created_at=now - timedelta(hours=2),
                    observed_preferences={
                        "pacing_preference": {"value": "fast", "confidence": 0.82},
                        "dialogue_preference": {
                            "value": "dialogue_forward",
                            "confidence": 0.8,
                        },
                    },
                    favored_elements=["动作链", "对话推进"],
                ),
                SimpleNamespace(
                    source_type="rollback",
                    created_at=now,
                    observed_preferences={
                        "pacing_preference": {"value": "fast", "confidence": 0.88},
                        "dialogue_preference": {
                            "value": "dialogue_forward",
                            "confidence": 0.74,
                        },
                    },
                    favored_elements=["动作链"],
                ),
            ]
        )

        stable_fields = {item.field: item.value for item in snapshot.stable_preferences}

        self.assertEqual(snapshot.observation_count, 2)
        self.assertEqual(stable_fields["pacing_preference"], "fast")
        self.assertEqual(stable_fields["dialogue_preference"], "dialogue_forward")
        self.assertIn("动作链", snapshot.favored_elements)
        self.assertIn("人工内容变更", snapshot.summary or "")

    def test_resolve_generation_preference_payload_uses_learned_defaults(self) -> None:
        payload = resolve_generation_preference_payload(
            SimpleNamespace(
                active_template_key=None,
                prose_style="precise",
                narrative_mode="close_third",
                pacing_preference="balanced",
                dialogue_preference="balanced",
                tension_preference="balanced",
                sensory_density="focused",
                favored_elements=[],
                banned_patterns=[],
                custom_style_notes=None,
            ),
            PreferenceLearningSnapshot(
                observation_count=3,
                last_observed_at=datetime.now(timezone.utc),
                source_breakdown={"manual_update": 2, "rollback": 1},
                stable_preferences=[
                    SimpleNamespace(
                        field="pacing_preference",
                        value="fast",
                        confidence=0.81,
                        source_count=3,
                    ),
                    SimpleNamespace(
                        field="dialogue_preference",
                        value="dialogue_forward",
                        confidence=0.78,
                        source_count=2,
                    ),
                ],
                favored_elements=["动作链"],
                summary="来自最近 3 次人工内容变更。",
            ),
        )

        self.assertEqual(payload["pacing_preference"], "fast")
        self.assertEqual(payload["dialogue_preference"], "dialogue_forward")
        self.assertEqual(payload["favored_elements"], ["动作链"])

    def test_list_style_templates_marks_active_template(self) -> None:
        templates = list_style_templates("dialogue_mystery")

        active = next((item for item in templates if item.is_active), None)

        self.assertIsNotNone(active)
        self.assertEqual(active.key, "dialogue_mystery")
        self.assertEqual(active.name, "对白迷局")

    def test_apply_style_template_values_replace_mode_overwrites_profile(self) -> None:
        payload = apply_style_template_values(
            SimpleNamespace(
                active_template_key=None,
                prose_style="precise",
                narrative_mode="close_third",
                pacing_preference="balanced",
                dialogue_preference="balanced",
                tension_preference="balanced",
                sensory_density="focused",
                favored_elements=[],
                banned_patterns=[],
                custom_style_notes=None,
            ),
            "cold_thriller",
            mode="replace",
        )

        self.assertEqual(payload["active_template_key"], "cold_thriller")
        self.assertEqual(payload["prose_style"], "sharp")
        self.assertEqual(payload["pacing_preference"], "fast")
        self.assertIn("动作链", payload["favored_elements"])

    def test_apply_style_template_values_fill_defaults_preserves_manual_overrides(self) -> None:
        payload = apply_style_template_values(
            SimpleNamespace(
                active_template_key=None,
                prose_style="lyrical",
                narrative_mode="close_third",
                pacing_preference="balanced",
                dialogue_preference="balanced",
                tension_preference="balanced",
                sensory_density="focused",
                favored_elements=["身体感"],
                banned_patterns=["解释性说教"],
                custom_style_notes="保留我自己的说明。",
            ),
            "epic_chronicle",
            mode="fill_defaults",
        )

        self.assertEqual(payload["active_template_key"], "epic_chronicle")
        self.assertEqual(payload["prose_style"], "lyrical")
        self.assertEqual(payload["narrative_mode"], "omniscient")
        self.assertEqual(payload["favored_elements"], ["身体感"])
        self.assertEqual(payload["custom_style_notes"], "保留我自己的说明。")
