from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import Field, model_validator

from schemas.base import ORMModel
from schemas.project import StoryBibleRead


OutlineLevel = Literal["level_1", "level_2", "level_3"]
OutlineStatus = Literal["todo", "written"]
ForeshadowStatus = Literal["pending", "revealed", "abandoned"]
StoryKnowledgeSectionKey = Literal[
    "characters",
    "foreshadows",
    "items",
    "locations",
    "factions",
    "plot_threads",
    "world_rules",
    "timeline_events",
    "outlines",
    "chapter_summaries",
]


class StoryCharacterCreate(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    appearance: Optional[str] = None
    personality: Optional[str] = None
    micro_habits: list[str] = Field(default_factory=list)
    abilities: dict = Field(default_factory=dict)
    relationships: list[dict] = Field(default_factory=list)
    status: str = Field(default="active", max_length=100)
    arc_stage: str = Field(default="initial", max_length=100)
    arc_boundaries: list[dict] = Field(default_factory=list)


class StoryCharacterUpdate(ORMModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    appearance: Optional[str] = None
    personality: Optional[str] = None
    micro_habits: Optional[list[str]] = None
    abilities: Optional[dict] = None
    relationships: Optional[list[dict]] = None
    status: Optional[str] = Field(default=None, max_length=100)
    arc_stage: Optional[str] = Field(default=None, max_length=100)
    arc_boundaries: Optional[list[dict]] = None


class StoryCharacterRead(ORMModel):
    character_id: UUID
    project_id: UUID
    name: str
    appearance: Optional[str] = None
    personality: Optional[str] = None
    micro_habits: list[str]
    abilities: dict
    relationships: list[dict]
    status: str
    arc_stage: str
    arc_boundaries: list[dict]
    version: int
    created_at: datetime
    updated_at: datetime


class StoryForeshadowCreate(ORMModel):
    content: str = Field(min_length=1)
    chapter_planted: Optional[int] = Field(default=None, ge=1)
    chapter_planned_reveal: Optional[int] = Field(default=None, ge=1)
    status: ForeshadowStatus = "pending"
    related_characters: list[str] = Field(default_factory=list)
    related_items: list[str] = Field(default_factory=list)


class StoryForeshadowUpdate(ORMModel):
    content: Optional[str] = None
    chapter_planted: Optional[int] = Field(default=None, ge=1)
    chapter_planned_reveal: Optional[int] = Field(default=None, ge=1)
    status: Optional[ForeshadowStatus] = None
    related_characters: Optional[list[str]] = None
    related_items: Optional[list[str]] = None


class StoryForeshadowRead(ORMModel):
    foreshadow_id: UUID
    project_id: UUID
    content: str
    chapter_planted: Optional[int] = None
    chapter_planned_reveal: Optional[int] = None
    status: str
    related_characters: list[str]
    related_items: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class StoryItemCreate(ORMModel):
    name: str = Field(min_length=1, max_length=255)
    features: Optional[str] = None
    owner: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    special_rules: list[str] = Field(default_factory=list)


class StoryItemUpdate(ORMModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    features: Optional[str] = None
    owner: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    special_rules: Optional[list[str]] = None


class StoryItemRead(ORMModel):
    item_id: UUID
    project_id: UUID
    name: str
    features: Optional[str] = None
    owner: Optional[str] = None
    location: Optional[str] = None
    special_rules: list[str]
    version: int
    created_at: datetime
    updated_at: datetime


class StoryWorldRuleCreate(ORMModel):
    rule_name: str = Field(min_length=1, max_length=255)
    rule_content: str = Field(min_length=1)
    negative_list: list[str] = Field(default_factory=list)
    scope: str = Field(default="global", max_length=100)


class StoryWorldRuleUpdate(ORMModel):
    rule_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    rule_content: Optional[str] = None
    negative_list: Optional[list[str]] = None
    scope: Optional[str] = Field(default=None, max_length=100)


class StoryWorldRuleRead(ORMModel):
    rule_id: UUID
    project_id: UUID
    rule_name: str
    rule_content: str
    negative_list: list[str]
    scope: str
    version: int
    created_at: datetime
    updated_at: datetime


class StoryTimelineMapEventCreate(ORMModel):
    chapter_number: Optional[int] = Field(default=None, ge=1)
    in_universe_time: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    weather: Optional[str] = Field(default=None, max_length=100)
    core_event: str = Field(min_length=1)
    character_states: list[dict] = Field(default_factory=list)


class StoryTimelineMapEventUpdate(ORMModel):
    chapter_number: Optional[int] = Field(default=None, ge=1)
    in_universe_time: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = Field(default=None, max_length=255)
    weather: Optional[str] = Field(default=None, max_length=100)
    core_event: Optional[str] = None
    character_states: Optional[list[dict]] = None


class StoryTimelineMapEventRead(ORMModel):
    event_id: UUID
    project_id: UUID
    chapter_number: Optional[int] = None
    in_universe_time: Optional[str] = None
    location: Optional[str] = None
    weather: Optional[str] = None
    core_event: str
    character_states: list[dict]
    version: int
    created_at: datetime
    updated_at: datetime


class StoryOutlineCreate(ORMModel):
    level: OutlineLevel
    parent_id: Optional[UUID] = None
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    status: OutlineStatus = "todo"
    node_order: int = Field(default=1, ge=1)
    locked: bool = False
    immutable_reason: Optional[str] = None


class StoryOutlineUpdate(ORMModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    content: Optional[str] = None
    status: Optional[OutlineStatus] = None
    node_order: Optional[int] = Field(default=None, ge=1)
    parent_id: Optional[UUID] = None


class StoryOutlineRead(ORMModel):
    outline_id: UUID
    project_id: UUID
    branch_id: UUID
    parent_id: Optional[UUID] = None
    level: str
    title: str
    content: str
    status: str
    version: int
    node_order: int
    locked: bool
    immutable_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class StoryChapterSummaryCreate(ORMModel):
    chapter_number: int = Field(ge=1)
    content: str = Field(min_length=20, max_length=600)
    core_progress: list[str] = Field(default_factory=list)
    character_changes: list[dict] = Field(default_factory=list)
    foreshadow_updates: list[dict] = Field(default_factory=list)
    kb_update_suggestions: list[dict] = Field(default_factory=list)


class StoryChapterSummaryUpdate(ORMModel):
    content: Optional[str] = Field(default=None, min_length=20, max_length=600)
    core_progress: Optional[list[str]] = None
    character_changes: Optional[list[dict]] = None
    foreshadow_updates: Optional[list[dict]] = None
    kb_update_suggestions: Optional[list[dict]] = None


class StoryChapterSummaryRead(ORMModel):
    summary_id: UUID
    project_id: UUID
    branch_id: UUID
    chapter_number: int
    content: str
    core_progress: list[str]
    character_changes: list[dict]
    foreshadow_updates: list[dict]
    kb_update_suggestions: list[dict]
    version: int
    created_at: datetime
    updated_at: datetime


class StoryKnowledgeVersionRead(ORMModel):
    version_record_id: UUID
    project_id: UUID
    entity_type: str
    entity_id: UUID
    version_number: int
    action: str
    snapshot: dict
    summary: Optional[str] = None
    source_workflow: Optional[str] = None
    created_by: Optional[UUID] = None
    created_at: datetime


class StoryKnowledgeRollbackResponse(ORMModel):
    restored_entity_type: str
    restored_entity_id: UUID
    restored_version_number: int
    snapshot: dict


class StorySearchResultRead(ORMModel):
    entity_type: str
    entity_id: str
    score: float
    content: str
    metadata: dict = Field(default_factory=dict)


class StoryCharacterGraphNode(ORMModel):
    id: str
    label: str
    status: Optional[str] = None
    arc_stage: Optional[str] = None


class StoryCharacterGraphEdge(ORMModel):
    source: str
    target: str
    relation: str
    intensity: Optional[str] = None


class StoryCharacterGraphRead(ORMModel):
    nodes: list[StoryCharacterGraphNode] = Field(default_factory=list)
    edges: list[StoryCharacterGraphEdge] = Field(default_factory=list)


class StoryEngineProjectInfo(ORMModel):
    project_id: UUID
    title: str
    genre: Optional[str] = None
    theme: Optional[str] = None
    tone: Optional[str] = None


class StoryKnowledgeRelationRead(ORMModel):
    relation_type: str
    section_key: str
    entity_key: str
    entity_id: Optional[str] = None
    label: str
    detail: Optional[str] = None


class StoryKnowledgeProvenanceRead(ORMModel):
    section_key: str
    entity_key: str
    entity_id: Optional[str] = None
    label: str
    scope_origin: str
    last_source_workflow: Optional[str] = None
    last_action: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    recent_chapters: list[int] = Field(default_factory=list)
    inbound_relations: list[StoryKnowledgeRelationRead] = Field(default_factory=list)
    outbound_relations: list[StoryKnowledgeRelationRead] = Field(default_factory=list)


class StoryEngineWorkspaceRead(ORMModel):
    project: StoryEngineProjectInfo
    outlines: list[StoryOutlineRead] = Field(default_factory=list)
    characters: list[StoryCharacterRead] = Field(default_factory=list)
    foreshadows: list[StoryForeshadowRead] = Field(default_factory=list)
    items: list[StoryItemRead] = Field(default_factory=list)
    world_rules: list[StoryWorldRuleRead] = Field(default_factory=list)
    timeline_events: list[StoryTimelineMapEventRead] = Field(default_factory=list)
    chapter_summaries: list[StoryChapterSummaryRead] = Field(default_factory=list)
    relationship_graph: StoryCharacterGraphRead = Field(default_factory=StoryCharacterGraphRead)
    latest_guardian_alerts: list[dict] = Field(default_factory=list)
    latest_final_package: Optional[dict] = None
    story_bible: Optional[StoryBibleRead] = None
    knowledge_provenance: list[StoryKnowledgeProvenanceRead] = Field(default_factory=list)


class StoryRoomCloudDraftUpsertRequest(ORMModel):
    branch_id: Optional[UUID] = None
    volume_id: Optional[UUID] = None
    chapter_number: int = Field(ge=1)
    chapter_title: str = ""
    draft_text: str = ""
    outline_id: Optional[UUID] = None
    source_chapter_id: Optional[UUID] = None
    source_version_number: Optional[int] = Field(default=None, ge=1)


class StoryRoomCloudDraftSummaryRead(ORMModel):
    draft_snapshot_id: UUID
    project_id: UUID
    branch_id: Optional[UUID] = None
    volume_id: Optional[UUID] = None
    scope_key: str
    chapter_number: int
    chapter_title: str
    outline_id: Optional[UUID] = None
    source_chapter_id: Optional[UUID] = None
    source_version_number: Optional[int] = None
    excerpt: str
    char_count: int
    created_at: datetime
    updated_at: datetime


class StoryRoomCloudDraftRead(StoryRoomCloudDraftSummaryRead):
    draft_text: str


class StoryKnowledgeUpsertRequest(ORMModel):
    entity_id: Optional[str] = None
    branch_id: Optional[UUID] = None
    previous_entity_key: Optional[str] = None
    item: dict = Field(default_factory=dict)


class StoryKnowledgeDeleteRequest(ORMModel):
    entity_id: str = Field(min_length=1)
    branch_id: Optional[UUID] = None


class StoryKnowledgeMutationResponse(ORMModel):
    passed: bool
    blocked: bool
    message: str
    alerts: list["StoryEngineIssueRead"] = Field(default_factory=list)
    blocking_issue_count: int = 0
    warning_count: int = 0
    entity_locator: Optional[dict] = None


class StoryEngineRoleCatalogRead(ORMModel):
    role_key: str
    label: str
    description: str


class StoryEngineModelOptionRead(ORMModel):
    id: str
    label: str
    provider: str
    description: Optional[str] = None
    supports_reasoning_effort: bool = True
    recommended_roles: list[str] = Field(default_factory=list)


class StoryEngineRoleRoutingRead(ORMModel):
    role_key: str
    label: str
    description: str
    model: str
    reasoning_effort: Optional[Literal["minimal", "low", "medium", "high"]] = None
    is_override: bool = False


class StoryEngineRoutingPresetRead(ORMModel):
    key: str
    label: str
    description: Optional[str] = None
    routing: dict[str, StoryEngineRoleRoutingRead] = Field(default_factory=dict)


class StoryEnginePresetSummaryRead(ORMModel):
    key: str
    label: str
    description: Optional[str] = None


class StoryEnginePresetCatalogRead(ORMModel):
    default_preset_key: str
    presets: list[StoryEnginePresetSummaryRead] = Field(default_factory=list)


class StoryEngineModelRoutingProjectSummaryRead(ORMModel):
    project_id: UUID
    title: str
    owner_email: Optional[str] = None
    genre: Optional[str] = None
    tone: Optional[str] = None
    status: str
    updated_at: datetime
    active_preset_key: str
    active_preset_label: Optional[str] = None
    manual_override_count: int = 0


class StoryEngineModelRoutingRead(ORMModel):
    project: StoryEngineProjectInfo
    default_preset_key: str
    active_preset_key: str
    available_models: list[StoryEngineModelOptionRead] = Field(default_factory=list)
    available_reasoning_efforts: list[Literal["minimal", "low", "medium", "high"]] = Field(
        default_factory=list
    )
    role_catalog: list[StoryEngineRoleCatalogRead] = Field(default_factory=list)
    presets: list[StoryEngineRoutingPresetRead] = Field(default_factory=list)
    manual_overrides: dict[str, StoryEngineRoleRoutingRead] = Field(default_factory=dict)
    effective_routing: dict[str, StoryEngineRoleRoutingRead] = Field(default_factory=dict)


class StoryEngineRouteUpdate(ORMModel):
    model: str = Field(min_length=1)
    reasoning_effort: Optional[Literal["minimal", "low", "medium", "high"]] = None


class StoryEngineModelRoutingUpdateRequest(ORMModel):
    active_preset_key: str = Field(min_length=1)
    manual_overrides: dict[str, StoryEngineRouteUpdate] = Field(default_factory=dict)


class StoryEngineIssueRead(ORMModel):
    severity: Literal["critical", "high", "medium", "low"]
    title: str
    detail: str
    source: str
    suggestion: Optional[str] = None


class StoryEngineAgentReportRead(ORMModel):
    agent_name: str
    role: str
    priority: int
    summary: str
    issues: list[StoryEngineIssueRead] = Field(default_factory=list)
    proposed_actions: list[str] = Field(default_factory=list)
    raw_output: dict = Field(default_factory=dict)


class StoryEngineDeliberationEntryRead(ORMModel):
    actor_key: str
    actor_label: str
    role: str
    stance: Literal["review", "challenge", "revise", "arbitrate", "anchor"] = "review"
    summary: str
    evidence: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    issues: list[StoryEngineIssueRead] = Field(default_factory=list)


class StoryEngineDeliberationRoundRead(ORMModel):
    round_number: int = Field(ge=1)
    title: str
    summary: str
    resolution: Optional[str] = None
    entries: list[StoryEngineDeliberationEntryRead] = Field(default_factory=list)


class StoryEngineWorkflowEventRead(ORMModel):
    workflow_id: str
    workflow_type: str
    sequence: int = Field(ge=1)
    stage: str
    status: Literal["started", "completed", "paused", "skipped", "failed"]
    label: str
    message: Optional[str] = None
    chapter_number: Optional[int] = None
    chapter_title: Optional[str] = None
    branch_id: Optional[UUID] = None
    round_number: Optional[int] = Field(default=None, ge=1)
    paragraph_index: Optional[int] = Field(default=None, ge=1)
    paragraph_total: Optional[int] = Field(default=None, ge=1)
    agent_keys: list[str] = Field(default_factory=list)
    details: dict = Field(default_factory=dict)
    emitted_at: datetime


class OutlineStressTestRequest(ORMModel):
    branch_id: Optional[UUID] = None
    idea: Optional[str] = Field(default=None, min_length=1)
    genre: Optional[str] = Field(default=None, max_length=100)
    tone: Optional[str] = Field(default=None, max_length=100)
    target_chapter_count: Optional[int] = Field(default=120, ge=10, le=2000)
    target_total_words: Optional[int] = Field(default=1_000_000, ge=50_000, le=20_000_000)
    source_material: Optional[str] = None
    source_material_name: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_outline_source(self) -> "OutlineStressTestRequest":
        idea = (self.idea or "").strip()
        source_material = (self.source_material or "").strip()
        if not idea and not source_material:
            raise ValueError("idea or source_material must be provided")
        self.idea = idea or None
        self.source_material = source_material or None
        self.source_material_name = (self.source_material_name or "").strip() or None
        return self


class OutlineStressTestResponse(ORMModel):
    locked_level_1_outlines: list[StoryOutlineRead] = Field(default_factory=list)
    editable_level_2_outlines: list[StoryOutlineRead] = Field(default_factory=list)
    editable_level_3_outlines: list[StoryOutlineRead] = Field(default_factory=list)
    initial_knowledge_base: dict = Field(default_factory=dict)
    risk_report: list[StoryEngineIssueRead] = Field(default_factory=list)
    optimization_plan: list[str] = Field(default_factory=list)
    debate_rounds_completed: int = 0
    agent_reports: list[StoryEngineAgentReportRead] = Field(default_factory=list)
    deliberation_rounds: list[StoryEngineDeliberationRoundRead] = Field(default_factory=list)
    workflow_timeline: list[StoryEngineWorkflowEventRead] = Field(default_factory=list)


class RealtimeGuardRequest(ORMModel):
    branch_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    chapter_number: int = Field(ge=1)
    chapter_title: Optional[str] = None
    outline_id: Optional[UUID] = None
    current_outline: Optional[str] = None
    recent_chapters: list[str] = Field(default_factory=list)
    draft_text: str = Field(min_length=1)
    latest_paragraph: Optional[str] = None


class RealtimeGuardResponse(ORMModel):
    passed: bool
    should_pause: bool
    alerts: list[StoryEngineIssueRead] = Field(default_factory=list)
    repair_options: list[str] = Field(default_factory=list)
    arbitration_note: Optional[str] = None
    workflow_timeline: list[StoryEngineWorkflowEventRead] = Field(default_factory=list)


class FinalOptimizeRequest(ORMModel):
    branch_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    chapter_number: int = Field(ge=1)
    chapter_title: Optional[str] = None
    draft_text: str = Field(min_length=1)
    style_sample: Optional[str] = None


class FinalOptimizeResponse(ORMModel):
    final_draft: str
    revision_notes: list[str] = Field(default_factory=list)
    chapter_summary: StoryChapterSummaryRead
    kb_update_list: list[dict] = Field(default_factory=list)
    agent_reports: list[StoryEngineAgentReportRead] = Field(default_factory=list)
    deliberation_rounds: list[StoryEngineDeliberationRoundRead] = Field(default_factory=list)
    original_draft: str
    consensus_rounds: int = 1
    consensus_reached: bool = False
    remaining_issue_count: int = 0
    ready_for_publish: bool = False
    quality_summary: Optional[str] = None
    workflow_timeline: list[StoryEngineWorkflowEventRead] = Field(default_factory=list)


class StoryKnowledgeSuggestionResolveRequest(ORMModel):
    action: Literal["apply", "ignore"]


class StoryKnowledgeSuggestionResolveResponse(ORMModel):
    chapter_summary: StoryChapterSummaryRead
    resolved_suggestion: dict
    applied_entity_type: Optional[str] = None
    applied_entity_id: Optional[UUID] = None
    applied_entity_key: Optional[str] = None
    applied_entity_label: Optional[str] = None
    message: str


class ChapterStreamGenerateRequest(ORMModel):
    branch_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    chapter_number: int = Field(ge=1)
    chapter_title: Optional[str] = None
    outline_id: Optional[UUID] = None
    current_outline: Optional[str] = None
    recent_chapters: list[str] = Field(default_factory=list)
    existing_text: str = ""
    style_sample: Optional[str] = None
    target_word_count: int = Field(default=2500, ge=500, le=8000)
    target_paragraph_count: int = Field(default=5, ge=3, le=10)
    resume_from_paragraph: Optional[int] = Field(default=None, ge=1)
    repair_instruction: Optional[str] = None
    rewrite_latest_paragraph: bool = False


class ChapterStreamEventRead(ORMModel):
    event: Literal["start", "plan", "chunk", "guard", "done", "error"]
    message: Optional[str] = None
    delta: Optional[str] = None
    text: Optional[str] = None
    paragraph_index: Optional[int] = None
    paragraph_total: Optional[int] = None
    guard_result: Optional[RealtimeGuardResponse] = None
    metadata: dict = Field(default_factory=dict)
    workflow_event: Optional[StoryEngineWorkflowEventRead] = None


class StoryOutlineImportItem(ORMModel):
    level: OutlineLevel
    title: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1)
    status: OutlineStatus = "todo"
    node_order: int = Field(default=1, ge=1)
    parent_title: Optional[str] = None
    locked: bool = False
    immutable_reason: Optional[str] = None


class StoryBulkImportPayload(ORMModel):
    characters: list[StoryCharacterCreate] = Field(default_factory=list)
    foreshadows: list[StoryForeshadowCreate] = Field(default_factory=list)
    items: list[StoryItemCreate] = Field(default_factory=list)
    world_rules: list[StoryWorldRuleCreate] = Field(default_factory=list)
    timeline_events: list[StoryTimelineMapEventCreate] = Field(default_factory=list)
    outlines: list[StoryOutlineImportItem] = Field(default_factory=list)
    chapter_summaries: list[StoryChapterSummaryCreate] = Field(default_factory=list)


class StoryImportTemplateRead(ORMModel):
    key: str
    label: str
    description: str
    usage_notes: list[str] = Field(default_factory=list)
    recommended_model_preset_key: Optional[str] = None
    recommended_model_preset_label: Optional[str] = None
    payload: StoryBulkImportPayload


class StoryBulkImportRequest(ORMModel):
    branch_id: Optional[UUID] = None
    template_key: Optional[str] = None
    apply_template_model_routing: bool = False
    replace_existing_sections: list[str] = Field(default_factory=list)
    payload: Optional[StoryBulkImportPayload] = None


class StoryBulkImportResponse(ORMModel):
    imported_counts: dict[str, int] = Field(default_factory=dict)
    replaced_sections: list[str] = Field(default_factory=list)
    applied_model_preset_key: Optional[str] = None
    applied_model_preset_label: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    workflow_timeline: list[StoryEngineWorkflowEventRead] = Field(default_factory=list)


class StoryGeneratedCandidateAcceptRequest(ORMModel):
    task_id: str = Field(min_length=1)
    candidate_index: int = Field(ge=0)
    branch_id: Optional[UUID] = None


class StoryGeneratedCandidateAcceptResponse(ORMModel):
    accepted_entity_type: str
    accepted_entity_id: Optional[UUID] = None
    accepted_entity_key: Optional[str] = None
    accepted_entity_label: str
    source_task_id: str
    candidate_index: int
    branch_id: Optional[UUID] = None
    message: str
