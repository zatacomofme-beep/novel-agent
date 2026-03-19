from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel


class ProjectCreate(ORMModel):
    title: str = Field(min_length=1, max_length=255)
    genre: Optional[str] = Field(default=None, max_length=100)
    theme: Optional[str] = None
    tone: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="draft", max_length=50)


class ProjectUpdate(ORMModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    genre: Optional[str] = Field(default=None, max_length=100)
    theme: Optional[str] = None
    tone: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(default=None, max_length=50)


class ProjectRead(ORMModel):
    id: UUID
    user_id: UUID
    title: str
    genre: Optional[str] = None
    theme: Optional[str] = None
    tone: Optional[str] = None
    status: str
    access_role: str = "owner"
    owner_email: Optional[str] = None
    collaborator_count: int = 0


class ProjectVolumeCreate(ORMModel):
    volume_number: Optional[int] = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=255)
    summary: Optional[str] = None
    status: str = Field(default="planning", max_length=50)


class ProjectVolumeUpdate(ORMModel):
    volume_number: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    summary: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=50)


class ProjectVolumeRead(ORMModel):
    id: UUID
    project_id: UUID
    volume_number: int
    title: str
    summary: Optional[str] = None
    status: str
    is_default: bool = False
    chapter_count: int = 0


class ProjectBranchCreate(ORMModel):
    key: Optional[str] = Field(default=None, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    status: str = Field(default="active", max_length=50)
    source_branch_id: Optional[UUID] = None
    copy_chapters: bool = True
    is_default: bool = False


class ProjectBranchUpdate(ORMModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(default=None, max_length=50)
    is_default: Optional[bool] = None


class ProjectBranchRead(ORMModel):
    id: UUID
    project_id: UUID
    source_branch_id: Optional[UUID] = None
    key: str
    title: str
    description: Optional[str] = None
    status: str
    is_default: bool = False
    chapter_count: int = 0


class ProjectStructureRead(ORMModel):
    project: ProjectRead
    default_volume_id: Optional[UUID] = None
    default_branch_id: Optional[UUID] = None
    volumes: list[ProjectVolumeRead]
    branches: list[ProjectBranchRead]


class ProjectCollaboratorCreate(ORMModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = Field(default="editor", max_length=50)


class ProjectCollaboratorUpdate(ORMModel):
    role: str = Field(max_length=50)


class ProjectCollaboratorRead(ORMModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    added_by_user_id: Optional[UUID] = None
    email: str
    role: str
    is_owner: bool = False


class ProjectCollaborationRead(ORMModel):
    project: ProjectRead
    current_role: str
    members: list[ProjectCollaboratorRead]


class CharacterItem(ORMModel):
    id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=255)
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    created_chapter: Optional[int] = None


class WorldSettingItem(ORMModel):
    id: Optional[UUID] = None
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class LocationItem(ORMModel):
    id: Optional[UUID] = None
    name: str = Field(min_length=1, max_length=255)
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class PlotThreadItem(ORMModel):
    id: Optional[UUID] = None
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="planned", max_length=50)
    importance: int = 1
    data: dict[str, Any] = Field(default_factory=dict)


class ForeshadowingItem(ORMModel):
    id: Optional[UUID] = None
    content: str = Field(min_length=1)
    planted_chapter: Optional[int] = None
    payoff_chapter: Optional[int] = None
    status: str = Field(default="pending", max_length=50)
    importance: int = 1


class TimelineEventItem(ORMModel):
    id: Optional[UUID] = None
    chapter_number: Optional[int] = None
    title: str = Field(min_length=1, max_length=255)
    data: dict[str, Any] = Field(default_factory=dict)


class StoryBibleRead(ORMModel):
    project: ProjectRead
    characters: list[CharacterItem]
    world_settings: list[WorldSettingItem]
    locations: list[LocationItem]
    plot_threads: list[PlotThreadItem]
    foreshadowing: list[ForeshadowingItem]
    timeline_events: list[TimelineEventItem]


class StoryBibleUpdate(ORMModel):
    project: Optional[ProjectUpdate] = None
    characters: list[CharacterItem] = Field(default_factory=list)
    world_settings: list[WorldSettingItem] = Field(default_factory=list)
    locations: list[LocationItem] = Field(default_factory=list)
    plot_threads: list[PlotThreadItem] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = Field(default_factory=list)
    timeline_events: list[TimelineEventItem] = Field(default_factory=list)
