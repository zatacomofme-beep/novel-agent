from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from services.project_service import (
    build_public_story_bible_sections,
    build_story_bible_scope,
    get_owned_project,
    resolve_story_bible_resolution,
    serialize_story_bible_chapter_summaries,
)


class StoryBibleContext(BaseModel):
    project_id: UUID
    title: str
    genre: Optional[str] = None
    theme: Optional[str] = None
    tone: Optional[str] = None
    status: str
    branch_id: Optional[UUID] = None
    branch_title: Optional[str] = None
    branch_key: Optional[str] = None
    scope_kind: str = "project"
    inherits_from_project: bool = False
    base_scope_kind: str = "project"
    base_branch_id: Optional[UUID] = None
    base_branch_title: Optional[str] = None
    base_branch_key: Optional[str] = None
    has_snapshot: bool = False
    changed_sections: list[str] = Field(default_factory=list)
    section_override_counts: dict[str, int] = Field(default_factory=dict)
    total_override_count: int = 0
    characters: list[dict[str, Any]] = Field(default_factory=list)
    world_settings: list[dict[str, Any]] = Field(default_factory=list)
    items: list[dict[str, Any]] = Field(default_factory=list)
    factions: list[dict[str, Any]] = Field(default_factory=list)
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
    *,
    branch_id: Optional[UUID] = None,
) -> StoryBibleContext:
    project = await get_owned_project(
        session,
        project_id,
        user_id,
        with_relations=True,
    )
    resolution = await resolve_story_bible_resolution(
        session,
        project,
        branch_id=branch_id,
    )
    scope = build_story_bible_scope(resolution)
    branch = resolution.branch
    public_sections = build_public_story_bible_sections(resolution.sections)

    return StoryBibleContext(
        project_id=project.id,
        title=project.title,
        genre=project.genre,
        theme=project.theme,
        tone=project.tone,
        status=project.status,
        branch_id=scope.branch_id,
        branch_title=scope.branch_title,
        branch_key=scope.branch_key,
        scope_kind=scope.scope_kind,
        inherits_from_project=scope.inherits_from_project,
        base_scope_kind=scope.base_scope_kind,
        base_branch_id=scope.base_branch_id,
        base_branch_title=scope.base_branch_title,
        base_branch_key=scope.base_branch_key,
        has_snapshot=scope.has_snapshot,
        changed_sections=scope.changed_sections,
        section_override_counts=scope.section_override_counts,
        total_override_count=scope.total_override_count,
        characters=public_sections["characters"],
        world_settings=public_sections["world_settings"],
        items=public_sections["items"],
        factions=public_sections["factions"],
        locations=public_sections["locations"],
        plot_threads=public_sections["plot_threads"],
        foreshadowing=public_sections["foreshadowing"],
        timeline_events=public_sections["timeline_events"],
        chapter_summaries=serialize_story_bible_chapter_summaries(
            project,
            branch=branch,
        ),
    )
