from __future__ import annotations

from typing import Any

from agents.base import AgentRunContext, BaseAgent
from agents.model_gateway import model_gateway
from bus.protocol import AgentResponse


class ChaosAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="chaos", role="chaos_injector")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        content = payload["content"]
        chapter_plan = payload.get("chapter_plan", {})
        existing_threads = payload.get("existing_threads", [])
        characters = payload.get("characters", [])
        story_bible = payload.get("story_bible", {})

        prompt = self._build_chaos_prompt(
            content, chapter_plan, existing_threads, characters, story_bible
        )
        result = await model_gateway.generate_text_async(
            self._make_request(prompt)
        )

        chaos_suggestions = self._parse_chaos_output(result.content)

        return AgentResponse(
            success=True,
            data={
                "chaos_interventions": chaos_suggestions.get("interventions", []),
                "twist_suggestions": chaos_suggestions.get("twists", []),
                "conflict_opportunities": chaos_suggestions.get("conflicts", []),
                "safe_points": chaos_suggestions.get("safe_points", []),
                "overall_chaos_score": chaos_suggestions.get("chaos_score", 0.5),
            },
            reasoning=f"Chaos analysis produced {len(chaos_suggestions.get('interventions', []))} interventions.",
        )

    def _build_chaos_prompt(
        self,
        content: str,
        chapter_plan: dict[str, Any],
        existing_threads: list[dict],
        characters: list[dict],
        story_bible: dict[str, Any],
    ) -> str:
        active_foreshadowing = [
            {"id": str(t.get("id", "")), "planted_chapter": t.get("planted_chapter")}
            for t in existing_threads
            if t.get("status") in ("open", "tracking")
        ]

        return f"""You are a narrative chaos designer. Your job is to identify opportunities to inject tension, conflict, and unexpected twists into a chapter WITHOUT violating canon consistency.

CHAPTER CONTENT:
{content[:3500]}

CHAPTER PLAN:
{str(chapter_plan)[:500]}

ACTIVE FORESHADOWING THREADS:
{str(active_foreshadowing)[:500]}

CHARACTERS:
{str(characters[:10])[:500]}

Analyze the content and identify:

1. **Safe zones** (low-tension moments where drama could be introduced)
2. **Conflict opportunities** (situations where characters could clash)
3. **Twist possibilities** (revelations or events that would surprise readers)
4. **Foreshadowing payoffs** (threads that could be activated)

Output a JSON object:
{{
  "chaos_score": 0.0-1.0,
  "interventions": [
    {{
      "location": "where in the chapter (scene index or description)",
      "type": "conflict|revelation|complication|surprise|death|betrayal|choice",
      "description": "what should happen",
      "affected_characters": ["char1", "char2"],
      "risk_level": "low|medium|high|critical",
      "canon_safe": true
    }}
  ],
  "twists": [
    {{
      "type": "identity|motivation|relationship|prophecy|secret",
      "description": "twist description",
      "setup_required": "what needs to be established first"
    }}
  ],
  "conflicts": [
    {{
      "character_a": "name",
      "character_b": "name",
      "type": "ideological|personal|professional|romantic",
      "trigger_event": "what starts the conflict"
    }}
  ],
  "safe_points": [
    {{
      "location": "where calm is appropriate",
      "reason": "why tension should stay low here"
    }}
  ]
}}

Only suggest interventions with canon_safe=true unless the chaos is dramatic enough to justify canon violation. Prioritize quality over quantity."""

    def _parse_chaos_output(self, content: str) -> dict[str, Any]:
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
            "chaos_score": 0.5,
            "interventions": [],
            "twists": [],
            "conflicts": [],
            "safe_points": [],
        }

    def _make_request(self, prompt: str) -> Any:
        from agents.model_gateway import GenerationRequest

        return GenerationRequest(
            task_name="chaos_analysis",
            prompt=prompt,
            system_prompt="You are a narrative design expert specializing in dramatic tension management.",
            max_tokens=1536,
            temperature=0.8,
        )
