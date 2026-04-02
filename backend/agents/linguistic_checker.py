from __future__ import annotations

from typing import Any

from agents.base import AgentRunContext, BaseAgent
from agents.model_gateway import model_gateway
from bus.protocol import AgentResponse
from models.character_linguistic import CharacterLinguisticProfile


class LinguisticCheckerAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="linguistic_checker", role="linguistic_checker")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        content = payload["content"]
        characters = payload.get("characters", [])
        profiles: list[dict[str, Any]] = payload.get("profiles", [])

        if not characters or not content:
            return AgentResponse(
                success=True,
                data={"issues": [], "consistency_scores": {}},
                reasoning="No characters or content to check.",
            )

        profile_map = {p.get("character_id"): p for p in profiles}

        analysis_prompt = self._build_analysis_prompt(content, characters, profile_map)
        result = await model_gateway.generate_text_async(
            self._make_request(analysis_prompt)
        )

        try:
            import json

            parsed = json.loads(result.content)
            issues = parsed.get("issues", [])
            scores = parsed.get("consistency_scores", {})
        except Exception:
            issues = []
            scores = {}

        return AgentResponse(
            success=True,
            data={
                "issues": issues,
                "consistency_scores": scores,
                "content_hash": hash(content),
            },
            reasoning=f"Linguistic check completed for {len(characters)} characters.",
        )

    def _build_analysis_prompt(
        self,
        content: str,
        characters: list[dict[str, Any]],
        profile_map: dict[str, dict[str, Any]],
    ) -> str:
        char_descriptions = []
        for char in characters:
            char_id = str(char.get("id", ""))
            profile = profile_map.get(char_id, {})
            char_descriptions.append(
                f"- {char.get('name', 'Unknown')} (ID: {char_id}): "
                f"vocabulary_level={profile.get('vocabulary_level', 'N/A')}, "
                f"dialogue_ratio={profile.get('dialogue_ratio', 'N/A')}, "
                f"speech_patterns={profile.get('speech_patterns', [])}, "
                f"personality_tags={profile.get('personality_tags', [])}"
            )

        return f"""You are a linguistic consistency checker for a novel.

Analyze the following content and check if each character's dialogue and narration remain consistent with their established linguistic profile.

CHARACTER PROFILES:
{chr(10).join(char_descriptions)}

CONTENT TO ANALYZE:
{content[:4000]}

For each character detected in the content, identify:
1. Dialogue that sounds inconsistent with their personality or speech patterns
2. Narration style that deviates from their established voice
3. Vocabulary level mismatches

Output a JSON object with:
{{
  "issues": [
    {{
      "character_id": "uuid",
      "character_name": "name",
      "type": "vocabulary|dialogue_style|personality_mismatch",
      "description": "what was said and why it violates the profile",
      "line_preview": "the problematic text excerpt"
    }}
  ],
  "consistency_scores": {{
    "character_uuid": 0.85,
    ...
  }}
}}

Only report significant deviations (score < 0.7). If all characters are consistent, return empty issues list."""

    def _make_request(self, prompt: str) -> Any:
        from agents.model_gateway import GenerationRequest

        return GenerationRequest(
            task_name="linguistic_check",
            prompt=prompt,
            system_prompt="You are a precise linguistic analysis assistant.",
            max_tokens=1024,
            temperature=0.1,
        )
