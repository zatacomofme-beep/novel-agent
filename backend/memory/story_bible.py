from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from services.project_service import get_owned_project


class StoryBibleContext(BaseModel):
    project_id: UUID
    title: str
    genre: Optional[str] = None
    theme: Optional[str] = None
    tone: Optional[str] = None
    status: str
    characters: list[dict[str, Any]] = Field(default_factory=list)
    world_settings: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
    plot_threads: list[dict[str, Any]] = Field(default_factory=list)
    foreshadowing: list[dict[str, Any]] = Field(default_factory=list)
    timeline_events: list[dict[str, Any]] = Field(default_factory=list)
    chapter_summaries: list[dict[str, Any]] = Field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        return self.model_dump()


async def load_story_bible_context(
    session: AsyncSession,
    project_id: UUID,
    user_id: UUID,
) -> StoryBibleContext:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
    )

    return StoryBibleContext(
        project_id=project.id,
        title=project.title,
        genre=project.genre,
        theme=project.theme,
        tone=project.tone,
        status=project.status,
        characters=[
            {
                "id": str(character.id),
                "name": character.name,
                "data": character.data,
                "version": character.version,
                "created_chapter": character.created_chapter,
            }
            for character in project.characters
        ],
        world_settings=[
            {
                "id": str(item.id),
                "key": item.key,
                "title": item.title,
                "data": item.data,
                "version": item.version,
            }
            for item in project.world_settings
        ],
        locations=[
            {
                "id": str(item.id),
                "name": item.name,
                "data": item.data,
                "version": item.version,
            }
            for item in project.locations
        ],
        plot_threads=[
            {
                "id": str(item.id),
                "title": item.title,
                "status": item.status,
                "importance": item.importance,
                "data": item.data,
            }
            for item in project.plot_threads
        ],
        foreshadowing=[
            {
                "id": str(item.id),
                "content": item.content,
                "planted_chapter": item.planted_chapter,
                "payoff_chapter": item.payoff_chapter,
                "status": item.status,
                "importance": item.importance,
            }
            for item in project.foreshadowing_items
        ],
        timeline_events=[
            {
                "id": str(item.id),
                "chapter_number": item.chapter_number,
                "title": item.title,
                "data": item.data,
            }
            for item in project.timeline_events
        ],
        chapter_summaries=[
            {
                "id": str(chapter.id),
                "volume_id": str(chapter.volume_id) if chapter.volume_id is not None else None,
                "volume_title": chapter.volume.title if chapter.volume is not None else None,
                "volume_number": (
                    chapter.volume.volume_number if chapter.volume is not None else None
                ),
                "branch_id": str(chapter.branch_id) if chapter.branch_id is not None else None,
                "branch_title": chapter.branch.title if chapter.branch is not None else None,
                "branch_key": chapter.branch.key if chapter.branch is not None else None,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "status": chapter.status,
                "word_count": chapter.word_count,
            }
            for chapter in project.chapters
        ],
    )
