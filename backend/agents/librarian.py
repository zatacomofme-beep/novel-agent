from __future__ import annotations

from bus.protocol import AgentResponse
from memory.story_bible import StoryBibleContext
from memory.context_builder import build_context_bundle

from agents.base import AgentRunContext, BaseAgent


class LibrarianAgent(BaseAgent):
    def __init__(self) -> None:
        super().__init__(name="librarian", role="memory_curator")

    async def _run(
        self,
        context: AgentRunContext,
        payload: dict,
    ) -> AgentResponse:
        from db.session import AsyncSessionLocal

        story_bible: StoryBibleContext = payload["story_bible"]
        async with AsyncSessionLocal() as session:
            context_bundle = await build_context_bundle(
                story_bible,
                session,
                project_id=str(story_bible.project_id),
                chapter_number=payload.get("chapter_number", 1),
                chapter_title=payload.get("chapter_title"),
            )
            brief = {
                "project_title": story_bible.title,
                "genre": story_bible.genre,
                "theme": story_bible.theme,
                "tone": story_bible.tone,
                "characters": [item["name"] for item in story_bible.characters[:8]],
                "locations": [item["name"] for item in story_bible.locations[:6]],
                "active_plot_threads": [item["title"] for item in story_bible.plot_threads[:6]],
                "timeline_beats": [item["title"] for item in story_bible.timeline_events[:6]],
                "foreshadowing_items": [
                    item["content"] for item in story_bible.foreshadowing[:4]
                ],
            }
        return AgentResponse(
            success=True,
            data={
                "context_brief": brief,
                "context_bundle": context_bundle,
            },
            confidence=0.86,
            reasoning="聚合 Story Bible 的核心实体，并基于章节查询构建一份受预算约束的检索上下文。",
        )
