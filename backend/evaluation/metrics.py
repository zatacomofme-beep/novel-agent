from __future__ import annotations

from pydantic import BaseModel


class QualityMetrics(BaseModel):
    fluency: float = 0.0
    vocabulary_richness: float = 0.0
    sentence_variation: float = 0.0
    plot_tightness: float = 0.0
    conflict_intensity: float = 0.0
    suspense: float = 0.0
    character_consistency: float = 0.0
    world_consistency: float = 0.0
    logic_coherence: float = 0.0
    timeline_consistency: float = 0.0
    emotional_resonance: float = 0.0
    imagery: float = 0.0
    dialogue_quality: float = 0.0
    theme_depth: float = 0.0
    ai_taste_score: float = 0.0

    def calculate_overall_score(self) -> float:
        basic = (
            self.fluency + self.vocabulary_richness + self.sentence_variation
        ) / 3
        narrative = (
            self.plot_tightness + self.conflict_intensity + self.suspense
        ) / 3
        consistency = (
            self.character_consistency
            + self.world_consistency
            + self.logic_coherence
            + self.timeline_consistency
        ) / 4
        artistic = (
            self.emotional_resonance
            + self.imagery
            + self.dialogue_quality
            + self.theme_depth
        ) / 4

        weighted = (
            0.15 * basic
            + 0.20 * narrative
            + 0.35 * consistency
            + 0.30 * artistic
        )
        ai_penalty = max(0.0, self.ai_taste_score - 0.3) * 0.5
        return max(0.0, min(1.0, weighted - ai_penalty))
