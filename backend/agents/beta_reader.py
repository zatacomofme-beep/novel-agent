from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agents.base import AgentRunContext, BaseAgent
from agents.model_gateway import model_gateway
from bus.protocol import AgentResponse


@dataclass
class PersonaWeight:
    engagement_focus: float = 1.0
    pacing_focus: float = 1.0
    emotional_focus: float = 1.0
    dialogue_focus: float = 1.0
    clarity_focus: float = 1.0
    style_notes: str = ""

    def to_prompt_suffix(self) -> str:
        parts = []
        if self.engagement_focus > 1.2:
            parts.append("Prioritize engagement and hook strength above all else.")
        if self.pacing_focus > 1.2:
            parts.append("Pay extra attention to pacing — flag any slow passages.")
        if self.emotional_focus > 1.2:
            parts.append("Focus heavily on emotional resonance and reader gut reactions.")
        if self.dialogue_focus > 1.2:
            parts.append("Examine dialogue closely — authenticity and subtext matter most here.")
        if self.clarity_focus > 1.2:
            parts.append("Be strict about clarity — note anything that caused you to re-read.")
        if self.style_notes:
            parts.append(f"Reader profile notes: {self.style_notes}")
        return " ".join(parts) if parts else ""


class BetaReaderAgent(BaseAgent):
    PERSONA_ARCHETYPES: dict[str, PersonaWeight] = {
        "idealist": PersonaWeight(
            engagement_focus=1.3,
            emotional_focus=1.3,
            pacing_focus=1.0,
            dialogue_focus=1.1,
            clarity_focus=1.0,
            style_notes="Values emotional truth and immersion.",
        ),
        "critic": PersonaWeight(
            engagement_focus=0.8,
            pacing_focus=1.3,
            dialogue_focus=1.2,
            clarity_focus=1.4,
            style_notes="Prioritizes structural clarity and pacing discipline.",
        ),
        "casual": PersonaWeight(
            engagement_focus=1.4,
            pacing_focus=0.9,
            emotional_focus=1.1,
            dialogue_focus=0.9,
            clarity_focus=0.8,
            style_notes="Reads as a general consumer, not a craft analyst.",
        ),
        "genre_expert": PersonaWeight(
            engagement_focus=1.1,
            pacing_focus=1.2,
            dialogue_focus=1.0,
            clarity_focus=1.2,
            style_notes="Deep knowledge of genre conventions — holds to genre standards.",
        ),
    }

    def __init__(self) -> None:
        super().__init__(name="beta_reader", role="beta_reader")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        content = payload["content"]
        genre = payload.get("genre", "general")
        target_audience = payload.get("target_audience", "adult")
        tension_data: dict[str, Any] = payload.get("tension_data", {})
        beta_history: list[dict[str, Any]] = payload.get("beta_history", [])
        archetype = payload.get("persona_archetype", "idealist")
        chapter_number = payload.get("chapter_number")

        persona = self._compute_persona_weights(
            archetype=archetype,
            tension_data=tension_data,
            beta_history=beta_history,
            chapter_number=chapter_number,
        )

        prompt = self._build_feedback_prompt(content, genre, target_audience, persona)
        result = await model_gateway.generate_text_async(
            self._make_request(prompt)
        )

        feedback = self._parse_feedback(result.content)

        return AgentResponse(
            success=True,
            data={
                "beta_feedback": feedback,
                "overall_reaction": feedback.get("overall_reaction", ""),
                "pacing_issues": feedback.get("pacing_issues", []),
                "emotional_response": feedback.get("emotional_response", ""),
                "suggestions": feedback.get("suggestions", []),
                "engagement_score": feedback.get("engagement_score", 0.0),
                "persona_archetype": archetype,
                "persona_weights": {
                    "engagement_focus": persona.engagement_focus,
                    "pacing_focus": persona.pacing_focus,
                    "emotional_focus": persona.emotional_focus,
                    "dialogue_focus": persona.dialogue_focus,
                    "clarity_focus": persona.clarity_focus,
                },
            },
            reasoning=f"Beta reader feedback generated for {len(content)} characters of content.",
        )

    def _compute_persona_weights(
        self,
        *,
        archetype: str,
        tension_data: dict[str, Any],
        beta_history: list[dict[str, Any]],
        chapter_number: int | None,
    ) -> PersonaWeight:
        base = self.PERSONA_ARCHETYPES.get(archetype, self.PERSONA_ARCHETYPES["idealist"])

        import copy
        persona = copy.deepcopy(base)

        tension_score = tension_data.get("tension_score", 0.5)
        if tension_data.get("tension_level") == "high":
            persona.engagement_focus = min(persona.engagement_focus * 1.2, 2.0)
            persona.pacing_focus = min(persona.pacing_focus * 1.3, 2.0)
        elif tension_data.get("tension_level") == "low":
            persona.emotional_focus = min(persona.emotional_focus * 1.25, 2.0)

        if len(beta_history) >= 3:
            recent_scores = [b.get("engagement_score", 0.5) for b in beta_history[-3:]]
            avg_score = sum(recent_scores) / len(recent_scores)
            if avg_score < 0.4:
                persona.engagement_focus = min(persona.engagement_focus * 1.4, 2.0)
                persona.pacing_focus = min(persona.pacing_focus * 1.2, 2.0)
                persona.style_notes += " (Historical: low engagement — be extra demanding on hook strength.)"
            elif avg_score > 0.8:
                persona.dialogue_focus = min(persona.dialogue_focus * 1.15, 2.0)
                persona.clarity_focus = min(persona.clarity_focus * 1.1, 2.0)

        if chapter_number is not None and chapter_number <= 3:
            persona.clarity_focus = min(persona.clarity_focus * 1.3, 2.0)
            persona.style_notes += " (Early chapter — hold stronger standards for hook and setup clarity.)"

        return persona

    def _build_feedback_prompt(
        self,
        content: str,
        genre: str,
        target_audience: str,
        persona: PersonaWeight,
    ) -> str:
        persona_suffix = persona.to_prompt_suffix()
        return f"""You are a beta reader reviewing a {genre} novel for a {target_audience} audience.
{persona_suffix}

Read the following chapter and provide honest, actionable feedback in the style of a thoughtful beta reader.

CHAPTER CONTENT:
{content[:5000]}

Provide feedback in the following JSON format:
{{
  "overall_reaction": "Your gut reaction to this chapter in 2-3 sentences",
  "pacing_issues": [
    "Specific pacing problem 1",
    "Specific pacing problem 2"
  ],
  "emotional_response": "What emotions did you feel while reading?",
  "engagement_score": 0.0-1.0,
  "dialogue_issues": [
    "Any dialogue that felt unnatural or out of character"
  ],
  "confusion_points": [
    "Anything you found confusing or needed re-reading"
  ],
  "strengths": [
    "What worked well"
  ],
  "suggestions": [
    "Specific actionable suggestions for improvement"
  ]
}}

Be honest but constructive. Focus on reader experience over technical writing quality."""

    def _parse_feedback(self, content: str) -> dict[str, Any]:
        import json
        import re

        content = content.strip()
        match = re.search(r"\{[\s\S]*\}", content)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass

        return {
            "overall_reaction": content[:500],
            "pacing_issues": [],
            "emotional_response": "",
            "engagement_score": 0.5,
            "dialogue_issues": [],
            "confusion_points": [],
            "strengths": [],
            "suggestions": [],
        }

    def _make_request(self, prompt: str) -> Any:
        from agents.model_gateway import GenerationRequest

        return GenerationRequest(
            task_name="beta_reader_review",
            prompt=prompt,
            system_prompt="You are a thoughtful beta reader with expertise in narrative craft.",
            max_tokens=1536,
            temperature=0.7,
        )
