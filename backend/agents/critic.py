from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from evaluation.evaluator import evaluate_chapter_text
from memory.story_bible import StoryBibleContext

from agents.base import AgentRunContext, BaseAgent


class CriticAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="critic", role="quality_reviewer")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        story_bible: StoryBibleContext = payload["story_bible"]
        content: str = payload["content"]
        metrics, issues, summary = evaluate_chapter_text(content, story_bible)
        overall_score = metrics.calculate_overall_score()

        return AgentResponse(
            success=True,
            data={
                "metrics": metrics.model_dump(),
                "issues": issues,
                "summary": summary,
                "overall_score": overall_score,
                "needs_revision": overall_score < 0.75 or metrics.ai_taste_score > 0.35,
            },
            confidence=0.84,
            reasoning="基于启发式评估器检查本章在一致性、语言变化、AI 痕迹和叙事密度上的基础质量。",
        )
