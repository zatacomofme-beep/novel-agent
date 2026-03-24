from __future__ import annotations

from typing import Any

from bus.protocol import AgentResponse
from canon.service import validate_story_canon
from memory.story_bible import StoryBibleContext

from agents.base import AgentRunContext, BaseAgent


class CanonGuardianAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="canon_guardian", role="continuity_validator")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict[str, Any],
    ) -> AgentResponse:
        story_bible: StoryBibleContext = payload["story_bible"]
        content: str = payload["content"]
        chapter_number = int(payload.get("chapter_number") or 1)
        chapter_title = payload.get("chapter_title")
        report = validate_story_canon(
            story_bible,
            content=content,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
        )
        return AgentResponse(
            success=True,
            data={
                "canon_report": report.model_dump(),
            },
            confidence=0.9 if report.blocking_issue_count == 0 else 0.82,
            reasoning="先对章节中的人物、关系、物品、时间线与伏笔做规范校验，再把结果交给后续评审与辩论流程。",
        )
