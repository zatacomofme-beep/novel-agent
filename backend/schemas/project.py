from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Literal
from typing import Optional
from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel
from schemas.chapter import ChapterRead
from tasks.schemas import TaskState


class ProjectCreate(ORMModel):
    title: str = Field(min_length=1, max_length=255)
    genre: Optional[str] = Field(default=None, max_length=100)
    theme: Optional[str] = None
    tone: Optional[str] = Field(default=None, max_length=100)
    status: str = Field(default="draft", max_length=50)
    story_engine_preset_key: Optional[str] = Field(default=None, max_length=100)


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
    has_bootstrap_profile: bool = False
    has_novel_blueprint: bool = False
    initial_idea: Optional[str] = None
    world_building_completed: bool = False
    current_phase: str = "world-building"


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


class ProjectSeedCharacter(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="supporting", max_length=50)
    summary: Optional[str] = None
    motivation: Optional[str] = None
    conflict: Optional[str] = None


class ProjectBootstrapProfileUpdate(ORMModel):
    genre: Optional[str] = Field(default=None, max_length=100)
    theme: Optional[str] = None
    tone: Optional[str] = Field(default=None, max_length=100)
    protagonist_name: Optional[str] = Field(default=None, max_length=255)
    protagonist_summary: Optional[str] = None
    supporting_cast: Optional[list[ProjectSeedCharacter]] = None
    world_background: Optional[str] = None
    core_story: Optional[str] = None
    novel_style: Optional[str] = Field(default=None, max_length=255)
    prose_style: Optional[str] = Field(default=None, max_length=255)
    target_total_words: Optional[int] = Field(default=None, ge=1000, le=2_000_000)
    target_chapter_words: Optional[int] = Field(default=None, ge=500, le=50_000)
    planned_chapter_count: Optional[int] = Field(default=None, ge=1, le=200)
    special_requirements: Optional[str] = None


class ProjectBootstrapProfileRead(ORMModel):
    genre: Optional[str] = Field(default=None, max_length=100)
    theme: Optional[str] = None
    tone: Optional[str] = Field(default=None, max_length=100)
    protagonist_name: Optional[str] = Field(default=None, max_length=255)
    protagonist_summary: Optional[str] = None
    supporting_cast: list[ProjectSeedCharacter] = Field(default_factory=list)
    world_background: Optional[str] = None
    core_story: Optional[str] = None
    novel_style: Optional[str] = Field(default=None, max_length=255)
    prose_style: Optional[str] = Field(default=None, max_length=255)
    target_total_words: Optional[int] = Field(default=None, ge=1000, le=2_000_000)
    target_chapter_words: Optional[int] = Field(default=None, ge=500, le=50_000)
    planned_chapter_count: Optional[int] = Field(default=None, ge=1, le=200)
    special_requirements: Optional[str] = None


class ProjectBlueprintCharacter(ORMModel):
    name: str
    role: str
    summary: Optional[str] = None
    motivation: Optional[str] = None
    conflict: Optional[str] = None


class ProjectBlueprintPlotThread(ORMModel):
    title: str
    summary: str
    scope: str = Field(default="main", max_length=50)
    focus_characters: list[str] = Field(default_factory=list)
    planned_turns: list[str] = Field(default_factory=list)


class ProjectBlueprintForeshadowing(ORMModel):
    content: str
    planted_chapter: Optional[int] = None
    payoff_chapter: Optional[int] = None
    status: str = Field(default="pending", max_length=50)


class ProjectBlueprintTimelineBeat(ORMModel):
    chapter_number: Optional[int] = None
    title: str
    summary: Optional[str] = None


class ProjectBlueprintVolumePlan(ORMModel):
    volume_number: int = Field(ge=1)
    title: str
    summary: str
    narrative_goal: str
    planned_chapter_count: int = Field(default=1, ge=1)


class ProjectChapterBlueprint(ORMModel):
    volume_number: int = Field(default=1, ge=1)
    chapter_number: int = Field(ge=1)
    title: str
    objective: str
    summary: str
    expected_word_count: Optional[int] = Field(default=None, ge=500, le=50_000)
    focus_characters: list[str] = Field(default_factory=list)
    key_locations: list[str] = Field(default_factory=list)
    plot_thread_titles: list[str] = Field(default_factory=list)
    foreshadowing_to_plant: list[str] = Field(default_factory=list)


class ProjectNovelBlueprintRead(ORMModel):
    premise: str
    story_engine: str
    opening_hook: Optional[str] = None
    writing_rules: list[str] = Field(default_factory=list)
    cast: list[ProjectBlueprintCharacter] = Field(default_factory=list)
    plot_threads: list[ProjectBlueprintPlotThread] = Field(default_factory=list)
    foreshadowing: list[ProjectBlueprintForeshadowing] = Field(default_factory=list)
    timeline_beats: list[ProjectBlueprintTimelineBeat] = Field(default_factory=list)
    volume_plans: list[ProjectBlueprintVolumePlan] = Field(default_factory=list)
    chapter_blueprints: list[ProjectChapterBlueprint] = Field(default_factory=list)
    generated_at: Optional[datetime] = None


class ProjectBootstrapStoryStateSummaryRead(ORMModel):
    branch_id: Optional[UUID] = None
    branch_title: Optional[str] = None
    branch_key: Optional[str] = None
    character_count: int = 0
    plot_thread_count: int = 0
    foreshadowing_count: int = 0
    timeline_count: int = 0
    chapter_blueprint_count: int = 0
    created_chapter_count: int = 0


class ProjectBootstrapRead(ORMModel):
    project: ProjectRead
    profile: ProjectBootstrapProfileRead = Field(default_factory=ProjectBootstrapProfileRead)
    blueprint: Optional[ProjectNovelBlueprintRead] = None
    story_state: ProjectBootstrapStoryStateSummaryRead = Field(
        default_factory=ProjectBootstrapStoryStateSummaryRead
    )
    next_chapter: Optional["ProjectNextChapterCandidateRead"] = None


class ProjectNextChapterCandidateRead(ORMModel):
    chapter_id: Optional[UUID] = None
    chapter_number: int = Field(ge=1)
    title: Optional[str] = None
    branch_id: Optional[UUID] = None
    branch_title: Optional[str] = None
    volume_id: Optional[UUID] = None
    volume_title: Optional[str] = None
    generation_mode: Literal[
        "existing_draft",
        "blueprint_seed",
        "dynamic_continuation",
    ] = "existing_draft"
    based_on_blueprint: bool = False
    has_existing_content: bool = False


class ProjectChapterGenerationDispatchRead(ORMModel):
    chapter: ChapterRead
    next_chapter: ProjectNextChapterCandidateRead
    task_id: str
    task_status: str
    task: TaskState


class ProjectEntityGenerationDispatchRead(ORMModel):
    generation_type: str
    task_id: str
    task_status: str
    task: TaskState


class ProjectBlueprintGenerateRequest(ORMModel):
    create_missing_chapters: bool = True


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


class CharacterGenerationRequest(ORMModel):
    character_type: str = Field(default="protagonist", max_length=50)
    count: int = Field(default=1, ge=1, le=10)
    genre: Optional[str] = None
    existing_characters: Optional[str] = None
    tone: Optional[str] = None
    theme: Optional[str] = None


class GeneratedCharacter(ORMModel):
    name: str
    role: str
    age: Optional[int] = None
    gender: Optional[str] = None
    appearance: Optional[str] = None
    personality: Optional[str] = None
    background: Optional[str] = None
    motivation: Optional[str] = None
    conflict: Optional[str] = None
    relationships: list[str] = Field(default_factory=list)


class CharacterGenerationResponse(ORMModel):
    characters: list[GeneratedCharacter]


class ItemGenerationRequest(ORMModel):
    item_type: str = Field(default="weapon", max_length=50)
    count: int = Field(default=1, ge=1, le=10)
    genre: Optional[str] = None
    tone: Optional[str] = None
    existing_items: Optional[str] = None


class GeneratedItem(ORMModel):
    name: str
    type: str
    rarity: Optional[str] = None
    description: Optional[str] = None
    effects: list[str] = Field(default_factory=list)
    owner: Optional[str] = None


class ItemGenerationResponse(ORMModel):
    items: list[GeneratedItem]


class LocationGenerationRequest(ORMModel):
    location_type: str = Field(default="city", max_length=50)
    count: int = Field(default=1, ge=1, le=10)
    genre: Optional[str] = None
    tone: Optional[str] = None
    existing_locations: Optional[str] = None


class GeneratedLocation(ORMModel):
    name: str
    type: str
    climate: Optional[str] = None
    population: Optional[str] = None
    description: Optional[str] = None
    features: list[str] = Field(default_factory=list)
    notable_residents: list[str] = Field(default_factory=list)
    history: Optional[str] = None


class LocationGenerationResponse(ORMModel):
    locations: list[GeneratedLocation]


class FactionGenerationRequest(ORMModel):
    faction_type: str = Field(default="guild", max_length=50)
    count: int = Field(default=1, ge=1, le=10)
    genre: Optional[str] = None
    tone: Optional[str] = None
    existing_factions: Optional[str] = None


class GeneratedFaction(ORMModel):
    name: str
    type: str
    scale: Optional[str] = None
    description: Optional[str] = None
    goals: Optional[str] = None
    leader: Optional[str] = None
    members: list[str] = Field(default_factory=list)
    territory: Optional[str] = None
    resources: list[str] = Field(default_factory=list)
    ideology: Optional[str] = None


class FactionGenerationResponse(ORMModel):
    factions: list[GeneratedFaction]


class PlotThreadGenerationRequest(ORMModel):
    plot_type: str = Field(default="main", max_length=50)
    count: int = Field(default=1, ge=1, le=10)
    genre: Optional[str] = None
    tone: Optional[str] = None
    existing_plots: Optional[str] = None


class GeneratedPlotThread(ORMModel):
    title: str
    type: str
    description: Optional[str] = None
    main_characters: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    tension_arc: Optional[str] = None
    resolution: Optional[str] = None


class PlotThreadGenerationResponse(ORMModel):
    plot_threads: list[GeneratedPlotThread]


class WorldSettingItem(ORMModel):
    id: Optional[UUID] = None
    key: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=255)
    data: dict[str, Any] = Field(default_factory=dict)
    version: int = 1


class StoryBibleItemEntry(ORMModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    type: Optional[str] = Field(default=None, max_length=100)
    rarity: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    effects: list[str] = Field(default_factory=list)
    owner: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    status: Optional[str] = Field(default=None, max_length=100)
    introduced_chapter: Optional[int] = None
    forbidden_holders: list[str] = Field(default_factory=list)
    version: int = 1


class StoryBibleFactionEntry(ORMModel):
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    type: Optional[str] = Field(default=None, max_length=100)
    scale: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    goals: Optional[str] = None
    leader: Optional[str] = Field(default=None, max_length=255)
    members: list[str] = Field(default_factory=list)
    territory: Optional[str] = Field(default=None, max_length=255)
    resources: list[str] = Field(default_factory=list)
    ideology: Optional[str] = None
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


class StoryBibleOverrideItemRead(ORMModel):
    entity_key: str
    entity_label: str
    operation: str = Field(default="updated", max_length=50)
    changed_fields: list[str] = Field(default_factory=list)


class StoryBibleSectionOverrideRead(ORMModel):
    section_key: str
    item_count: int = 0
    items: list[StoryBibleOverrideItemRead] = Field(default_factory=list)


class StoryBibleScopeRead(ORMModel):
    scope_kind: str = Field(default="project", max_length=50)
    branch_id: Optional[UUID] = None
    branch_title: Optional[str] = None
    branch_key: Optional[str] = None
    inherits_from_project: bool = False
    base_scope_kind: str = Field(default="project", max_length=50)
    base_branch_id: Optional[UUID] = None
    base_branch_title: Optional[str] = None
    base_branch_key: Optional[str] = None
    has_snapshot: bool = False
    changed_sections: list[str] = Field(default_factory=list)
    section_override_counts: dict[str, int] = Field(default_factory=dict)
    total_override_count: int = 0
    section_override_details: list[StoryBibleSectionOverrideRead] = Field(default_factory=list)


class StoryBibleRead(ORMModel):
    project: ProjectRead
    scope: StoryBibleScopeRead = Field(default_factory=StoryBibleScopeRead)
    characters: list[CharacterItem]
    world_settings: list[WorldSettingItem]
    items: list[StoryBibleItemEntry] = Field(default_factory=list)
    factions: list[StoryBibleFactionEntry] = Field(default_factory=list)
    locations: list[LocationItem]
    plot_threads: list[PlotThreadItem]
    foreshadowing: list[ForeshadowingItem]
    timeline_events: list[TimelineEventItem]


class StoryBibleUpdate(ORMModel):
    project: Optional[ProjectUpdate] = None
    characters: list[CharacterItem] = Field(default_factory=list)
    world_settings: list[WorldSettingItem] = Field(default_factory=list)
    items: list[StoryBibleItemEntry] = Field(default_factory=list)
    factions: list[StoryBibleFactionEntry] = Field(default_factory=list)
    locations: list[LocationItem] = Field(default_factory=list)
    plot_threads: list[PlotThreadItem] = Field(default_factory=list)
    foreshadowing: list[ForeshadowingItem] = Field(default_factory=list)
    timeline_events: list[TimelineEventItem] = Field(default_factory=list)


StoryBibleSectionKey = Literal[
    "characters",
    "world_settings",
    "items",
    "factions",
    "locations",
    "plot_threads",
    "foreshadowing",
    "timeline_events",
]


class StoryBibleBranchItemUpsert(ORMModel):
    section_key: StoryBibleSectionKey
    item: dict[str, Any] = Field(default_factory=dict)


class StoryBibleBranchItemDelete(ORMModel):
    section_key: StoryBibleSectionKey
    entity_key: str = Field(min_length=1)
