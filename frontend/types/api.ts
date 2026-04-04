export interface User {
  id: string;
  email: string;
}

export interface PreferenceLearningSignal {
  field: string;
  value: string;
  confidence: number;
  source_count: number;
}

export interface PreferenceLearningSnapshot {
  observation_count: number;
  last_observed_at: string | null;
  source_breakdown: Record<string, number>;
  stable_preferences: PreferenceLearningSignal[];
  favored_elements: string[];
  summary: string | null;
}

export interface ActiveStyleTemplate {
  key: string;
  name: string;
  tagline: string;
}

export interface StyleTemplate {
  key: string;
  name: string;
  tagline: string;
  description: string;
  category: string;
  recommended_for: string[];
  prose_style: string;
  narrative_mode: string;
  pacing_preference: string;
  dialogue_preference: string;
  tension_preference: string;
  sensory_density: string;
  favored_elements: string[];
  banned_patterns: string[];
  custom_style_notes: string | null;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Project {
  id: string;
  user_id: string;
  title: string;
  genre: string | null;
  theme: string | null;
  tone: string | null;
  status: string;
  access_role: string;
  owner_email: string | null;
  collaborator_count: number;
  has_bootstrap_profile: boolean;
  has_novel_blueprint: boolean;
}


export interface StoryEnginePresetSummary {
  key: string;
  label: string;
  description: string | null;
}

export interface StoryEnginePresetCatalog {
  default_preset_key: string;
  presets: StoryEnginePresetSummary[];
}

export interface StoryEngineModelRoutingProjectSummary {
  project_id: string;
  title: string;
  owner_email: string | null;
  genre: string | null;
  tone: string | null;
  status: string;
  updated_at: string;
  active_preset_key: string;
  active_preset_label: string | null;
  manual_override_count: number;
}

export interface ProjectVolume {
  id: string;
  project_id: string;
  volume_number: number;
  title: string;
  summary: string | null;
  status: string;
  is_default: boolean;
  chapter_count: number;
}

export interface ProjectBranch {
  id: string;
  project_id: string;
  source_branch_id: string | null;
  key: string;
  title: string;
  description: string | null;
  status: string;
  is_default: boolean;
  chapter_count: number;
}

export interface ProjectStructure {
  project: Project;
  default_volume_id: string | null;
  default_branch_id: string | null;
  volumes: ProjectVolume[];
  branches: ProjectBranch[];
}

export interface ProjectSeedCharacter {
  name: string;
  role: string;
  summary: string | null;
  motivation: string | null;
  conflict: string | null;
}

export interface ProjectBootstrapProfile {
  genre: string | null;
  theme: string | null;
  tone: string | null;
  protagonist_name: string | null;
  protagonist_summary: string | null;
  supporting_cast: ProjectSeedCharacter[];
  world_background: string | null;
  core_story: string | null;
  novel_style: string | null;
  prose_style: string | null;
  target_total_words: number | null;
  target_chapter_words: number | null;
  planned_chapter_count: number | null;
  special_requirements: string | null;
}

export interface ProjectBlueprintCharacter {
  name: string;
  role: string;
  summary: string | null;
  motivation: string | null;
  conflict: string | null;
}

export interface ProjectBlueprintPlotThread {
  title: string;
  summary: string;
  scope: string;
  focus_characters: string[];
  planned_turns: string[];
}

export interface ProjectBlueprintForeshadowing {
  content: string;
  planted_chapter: number | null;
  payoff_chapter: number | null;
  status: string;
}

export interface ProjectBlueprintTimelineBeat {
  chapter_number: number | null;
  title: string;
  summary: string | null;
}

export interface ProjectBlueprintVolumePlan {
  volume_number: number;
  title: string;
  summary: string;
  narrative_goal: string;
  planned_chapter_count: number;
}

export interface ProjectChapterBlueprint {
  volume_number: number;
  chapter_number: number;
  title: string;
  objective: string;
  summary: string;
  expected_word_count: number | null;
  focus_characters: string[];
  key_locations: string[];
  plot_thread_titles: string[];
  foreshadowing_to_plant: string[];
}

export interface ProjectNovelBlueprint {
  premise: string;
  story_engine: string;
  opening_hook: string | null;
  writing_rules: string[];
  cast: ProjectBlueprintCharacter[];
  plot_threads: ProjectBlueprintPlotThread[];
  foreshadowing: ProjectBlueprintForeshadowing[];
  timeline_beats: ProjectBlueprintTimelineBeat[];
  volume_plans: ProjectBlueprintVolumePlan[];
  chapter_blueprints: ProjectChapterBlueprint[];
  generated_at: string | null;
}

export interface ProjectBootstrapStoryState {
  branch_id: string | null;
  branch_title: string | null;
  branch_key: string | null;
  character_count: number;
  plot_thread_count: number;
  foreshadowing_count: number;
  timeline_count: number;
  chapter_blueprint_count: number;
  created_chapter_count: number;
}

export type ProjectNextChapterGenerationMode =
  | "existing_draft"
  | "blueprint_seed"
  | "dynamic_continuation";

export interface ProjectNextChapterCandidate {
  chapter_id: string | null;
  chapter_number: number;
  title: string | null;
  branch_id: string | null;
  branch_title: string | null;
  volume_id: string | null;
  volume_title: string | null;
  generation_mode: ProjectNextChapterGenerationMode;
  based_on_blueprint: boolean;
  has_existing_content: boolean;
}

export interface ProjectBootstrapState {
  project: Project;
  profile: ProjectBootstrapProfile;
  blueprint: ProjectNovelBlueprint | null;
  story_state: ProjectBootstrapStoryState;
  next_chapter: ProjectNextChapterCandidate | null;
}

export interface ProjectBlueprintGenerateRequest {
  create_missing_chapters: boolean;
}

export interface ProjectChapterGenerationDispatch {
  chapter: Chapter;
  next_chapter: ProjectNextChapterCandidate;
  task_id: string;
  task_status: string;
  task: TaskState;
}

export interface ProjectEntityGenerationDispatch {
  generation_type: string;
  task_id: string;
  task_status: string;
  task: TaskState;
}

export interface StoryGeneratedCandidateAcceptResponse {
  accepted_entity_type: string;
  accepted_entity_id: string | null;
  accepted_entity_key: string | null;
  accepted_entity_label: string;
  source_task_id: string;
  candidate_index: number;
  branch_id: string | null;
  message: string;
}

export interface UserPreferenceProfile {
  id: string;
  user_id: string;
  active_template_key: string | null;
  active_template: ActiveStyleTemplate | null;
  prose_style: string;
  narrative_mode: string;
  pacing_preference: string;
  dialogue_preference: string;
  tension_preference: string;
  sensory_density: string;
  favored_elements: string[];
  banned_patterns: string[];
  custom_style_notes: string | null;
  completion_score: number;
  learning_snapshot: PreferenceLearningSnapshot;
  updated_at: string;
}

export interface DashboardProjectSummary {
  project_id: string;
  title: string;
  genre: string | null;
  status: string;
  access_role: string;
  owner_email: string | null;
  collaborator_count: number;
  has_bootstrap_profile: boolean;
  has_novel_blueprint: boolean;
  updated_at: string;
  chapter_count: number;
  word_count: number;
  review_ready_chapters: number;
  final_chapters: number;
  risk_chapter_count: number;
  active_task_count: number;
  average_overall_score: number | null;
  average_ai_taste_score: number | null;
  score_delta: number | null;
  trend_direction: string;
}

export interface DashboardProjectTrendPoint {
  chapter_id: string;
  chapter_number: number;
  title: string | null;
  status: string;
  overall_score: number | null;
  ai_taste_score: number | null;
  word_count: number;
  updated_at: string;
}

export interface DashboardProjectQualityTrend {
  project_id: string;
  title: string;
  status: string;
  access_role: string;
  owner_email: string | null;
  collaborator_count: number;
  updated_at: string;
  latest_overall_score: number | null;
  latest_ai_taste_score: number | null;
  score_delta: number | null;
  ai_taste_delta: number | null;
  trend_direction: string;
  evaluated_chapter_count: number;
  chapter_count: number;
  visible_chapter_count: number;
  coverage_ratio: number;
  average_overall_score: number | null;
  average_ai_taste_score: number | null;
  review_ready_chapters: number;
  final_chapters: number;
  status_breakdown: Record<string, number>;
  range_start_chapter_number: number | null;
  range_end_chapter_number: number | null;
  strongest_chapter: DashboardProjectTrendPoint | null;
  weakest_chapter: DashboardProjectTrendPoint | null;
  risk_chapter_numbers: number[];
  chapter_points: DashboardProjectTrendPoint[];
}

export interface DashboardRecentTask {
  task_id: string;
  task_type: string;
  status: string;
  progress: number;
  message: string | null;
  project_id: string | null;
  chapter_id: string | null;
  chapter_number: number | null;
  workflow_status?: string | null;
  updated_at: string;
}

export interface DashboardActivitySnapshot {
  active_projects_last_7_days: number;
  chapters_updated_last_7_days: number;
  active_words_last_7_days: number;
  new_projects_last_30_days: number;
  final_chapters_last_30_days: number;
  stale_projects_last_14_days: number;
}

export interface DashboardQualitySnapshot {
  risk_chapter_count: number;
  projects_with_risk_count: number;
  low_score_chapter_count: number;
  high_ai_taste_chapter_count: number;
  improving_project_count: number;
  declining_project_count: number;
  stable_project_count: number;
  average_coverage_ratio: number;
}

export interface DashboardTaskHealth {
  total_task_count: number;
  queued_count: number;
  running_count: number;
  succeeded_count: number;
  failed_count: number;
  cancelled_count: number;
  stalled_active_task_count: number;
  recent_failed_task_count: number;
  status_breakdown: Record<string, number>;
}

export interface DashboardPipelineSnapshot {
  outline_pending_projects: number;
  ready_for_first_chapter_projects: number;
  writing_in_progress_projects: number;
  awaiting_finalization_projects: number;
  stable_output_projects: number;
}

export interface DashboardGenreDistributionItem {
  genre: string;
  project_count: number;
}

export interface DashboardFocusItem {
  project_id: string;
  title: string;
  genre: string | null;
  focus_type: string;
  stage: string;
  action_label: string;
  reason: string;
  chapter_number: number | null;
  priority: number;
  risk_level: string;
  updated_at: string;
}

export interface DashboardOverview {
  total_projects: number;
  total_chapters: number;
  total_words: number;
  active_task_count: number;
  review_ready_chapters: number;
  final_chapters: number;
  average_overall_score: number | null;
  average_ai_taste_score: number | null;
  chapters_by_status: Record<string, number>;
  preference_profile: UserPreferenceProfile;
  project_summaries: DashboardProjectSummary[];
  project_quality_trends: DashboardProjectQualityTrend[];
  recent_tasks: DashboardRecentTask[];
  activity_snapshot: DashboardActivitySnapshot;
  quality_snapshot: DashboardQualitySnapshot;
  task_health: DashboardTaskHealth;
  pipeline_snapshot: DashboardPipelineSnapshot;
  genre_distribution: DashboardGenreDistributionItem[];
  focus_queue: DashboardFocusItem[];
}

export interface CharacterItem {
  id?: string | null;
  name: string;
  data: Record<string, unknown>;
  version: number;
  created_chapter?: number | null;
}

export interface WorldSettingItem {
  id?: string | null;
  key: string;
  title: string;
  data: Record<string, unknown>;
  version: number;
}

export interface StoryBibleItemEntry {
  key: string;
  name: string;
  type: string | null;
  rarity: string | null;
  description: string | null;
  effects: string[];
  owner: string | null;
  location: string | null;
  status: string | null;
  introduced_chapter: number | null;
  forbidden_holders: string[];
  version: number;
}

export interface StoryBibleFactionEntry {
  key: string;
  name: string;
  type: string | null;
  scale: string | null;
  description: string | null;
  goals: string | null;
  leader: string | null;
  members: string[];
  territory: string | null;
  resources: string[];
  ideology: string | null;
  version: number;
}

export interface LocationItem {
  id?: string | null;
  name: string;
  data: Record<string, unknown>;
  version: number;
}

export interface PlotThreadItem {
  id?: string | null;
  title: string;
  status: string;
  importance: number;
  data: Record<string, unknown>;
}

export interface ForeshadowingItem {
  id?: string | null;
  content: string;
  planted_chapter?: number | null;
  payoff_chapter?: number | null;
  status: string;
  importance: number;
}

export interface TimelineEventItem {
  id?: string | null;
  chapter_number?: number | null;
  title: string;
  data: Record<string, unknown>;
}

export type StoryBibleSectionKey =
  | "characters"
  | "world_settings"
  | "items"
  | "factions"
  | "locations"
  | "plot_threads"
  | "foreshadowing"
  | "timeline_events";

export type StoryBibleSectionItem =
  | CharacterItem
  | WorldSettingItem
  | StoryBibleItemEntry
  | StoryBibleFactionEntry
  | LocationItem
  | PlotThreadItem
  | ForeshadowingItem
  | TimelineEventItem;

export interface StoryBibleScope {
  scope_kind: string;
  branch_id: string | null;
  branch_title: string | null;
  branch_key: string | null;
  inherits_from_project: boolean;
  base_scope_kind: string;
  base_branch_id: string | null;
  base_branch_title: string | null;
  base_branch_key: string | null;
  has_snapshot: boolean;
  changed_sections: string[];
  section_override_counts: Record<string, number>;
  total_override_count: number;
  section_override_details: StoryBibleSectionOverride[];
}

export interface StoryBible {
  project: Project;
  scope: StoryBibleScope;
  characters: CharacterItem[];
  world_settings: WorldSettingItem[];
  items: StoryBibleItemEntry[];
  factions: StoryBibleFactionEntry[];
  locations: LocationItem[];
  plot_threads: PlotThreadItem[];
  foreshadowing: ForeshadowingItem[];
  timeline_events: TimelineEventItem[];
}

export interface StoryBibleBranchItemUpsertPayload {
  section_key: StoryBibleSectionKey;
  item: Record<string, unknown>;
}

export interface StoryBibleBranchItemDeletePayload {
  section_key: StoryBibleSectionKey;
  entity_key: string;
}

export interface StoryBibleOverrideItem {
  entity_key: string;
  entity_label: string;
  operation: string;
  changed_fields: string[];
}

export interface StoryBibleSectionOverride {
  section_key: string;
  item_count: number;
  items: StoryBibleOverrideItem[];
}

export type StoryBibleChangeType = "added" | "updated" | "removed";
export type StoryBibleChangeSource = "user" | "ai_proposed" | "auto_trigger";
export type StoryBibleSection =
  | "characters"
  | "world_settings"
  | "items"
  | "factions"
  | "locations"
  | "plot_threads"
  | "foreshadowing"
  | "timeline_events";
export type StoryBiblePendingChangeStatus = "pending" | "approved" | "rejected" | "expired";

export interface StoryBibleVersion {
  id: string;
  project_id: string;
  branch_id: string;
  version_number: number;
  change_type: StoryBibleChangeType;
  change_source: StoryBibleChangeSource;
  changed_section: StoryBibleSection;
  changed_entity_id: string | null;
  changed_entity_key: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  snapshot: Record<string, unknown>;
  note: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryBibleVersionList {
  items: StoryBibleVersion[];
  total: number;
  page: number;
  page_size: number;
}

export interface StoryBiblePendingChange {
  id: string;
  project_id: string;
  branch_id: string;
  status: StoryBiblePendingChangeStatus;
  change_type: StoryBibleChangeType;
  change_source: StoryBibleChangeSource;
  changed_section: StoryBibleSection;
  changed_entity_id: string | null;
  changed_entity_key: string | null;
  old_value: Record<string, unknown> | null;
  new_value: Record<string, unknown> | null;
  reason: string | null;
  triggered_by_chapter_id: string | null;
  proposed_by_agent: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejected_by: string | null;
  rejected_at: string | null;
  rejection_reason: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryBiblePendingChangeList {
  items: StoryBiblePendingChange[];
  total: number;
  pending_count: number;
}

export interface ConflictCheckRequest {
  section: StoryBibleSection;
  entity_key: string;
  proposed_value: Record<string, unknown>;
}

export interface ConflictCheckResult {
  has_conflict: boolean;
  conflicting_items: Array<{
    entity_id: string;
    entity_key: string;
    field: string;
    existing_value: unknown;
    proposed_value: unknown;
  }>;
  suggestion: string | null;
}

export interface ChapterQualityMetricsSnapshot {
  evaluation_status?: string;
  evaluation_stale_reason?: string | null;
  evaluation_updated_at?: string | null;
  overall_score?: number;
  heuristic_overall_score?: number;
  ai_taste_score?: number;
  summary?: string | null;
  story_bible_integrity_issue_count?: number;
  story_bible_integrity_blocking_issue_count?: number;
  story_bible_integrity_summary?: string | null;
  story_bible_integrity_report?: CanonIntegrityReport | null;
  canon_issue_count?: number;
  canon_blocking_issue_count?: number;
  canon_summary?: string | null;
  canon_plugin_breakdown?: Record<string, number>;
  canon_report?: CanonValidationReport | null;
  [key: string]: unknown;
}

export interface ProjectCollaborator {
  id: string;
  project_id: string;
  user_id: string;
  added_by_user_id: string | null;
  email: string;
  role: string;
  is_owner: boolean;
}

export interface ProjectCollaboration {
  project: Project;
  current_role: string;
  members: ProjectCollaborator[];
}

export interface ProjectStats {
  total_word_count: number;
  chapter_count: number;
  character_count: number;
  item_count: number;
  faction_count: number;
  location_count: number;
  plot_thread_count: number;
  volume_count: number;
  branch_count: number;
}

export interface Chapter {
  id: string;
  project_id: string;
  volume_id: string | null;
  branch_id: string | null;
  chapter_number: number;
  title: string | null;
  content: string;
  outline: Record<string, unknown> | null;
  word_count: number | null;
  current_version_number: number;
  status: string;
  quality_metrics: ChapterQualityMetricsSnapshot | null;
  pending_checkpoint_count: number;
  rejected_checkpoint_count: number;
  latest_checkpoint_status: string | null;
  latest_checkpoint_title: string | null;
  latest_review_verdict: string | null;
  latest_review_summary: string | null;
  review_gate_blocked: boolean;
  evaluation_gate_blocked: boolean;
  latest_evaluation_status: string;
  latest_evaluation_stale_reason: string | null;
  integrity_gate_blocked: boolean;
  latest_story_bible_integrity_issue_count: number;
  latest_story_bible_integrity_blocking_issue_count: number;
  latest_story_bible_integrity_summary: string | null;
  canon_gate_blocked: boolean;
  latest_canon_issue_count: number;
  latest_canon_blocking_issue_count: number;
  latest_canon_summary: string | null;
  final_ready: boolean;
  final_gate_status: string;
  final_gate_reason: string | null;
}

export interface ChapterVersion {
  id: string;
  chapter_id: string;
  version_number: number;
  content: string;
  change_reason: string | null;
}

export interface ChapterReviewComment {
  id: string;
  chapter_id: string;
  user_id: string;
  parent_comment_id: string | null;
  chapter_version_number: number;
  author_email: string;
  body: string;
  status: string;
  selection_start: number | null;
  selection_end: number | null;
  selection_text: string | null;
  assignee_user_id: string | null;
  assignee_email: string | null;
  assigned_by_user_id: string | null;
  assigned_by_email: string | null;
  assigned_at: string | null;
  resolved_by_user_id: string | null;
  resolved_by_email: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  reply_count: number;
  can_edit: boolean;
  can_assign: boolean;
  can_change_status: boolean;
  can_delete: boolean;
}

export interface ChapterReviewAssignableMember {
  user_id: string;
  email: string;
  role: string;
  is_owner: boolean;
}

export interface ChapterReviewDecision {
  id: string;
  chapter_id: string;
  user_id: string;
  chapter_version_number: number;
  reviewer_email: string;
  verdict: string;
  summary: string;
  focus_points: string[];
  created_at: string;
}

export interface ChapterCheckpoint {
  id: string;
  chapter_id: string;
  requester_user_id: string;
  chapter_version_number: number;
  checkpoint_type: string;
  title: string;
  description: string | null;
  status: string;
  decision_note: string | null;
  requester_email: string;
  decided_by_user_id: string | null;
  decided_by_email: string | null;
  decided_at: string | null;
  created_at: string;
  updated_at: string;
  can_decide: boolean;
  can_cancel: boolean;
}

export interface ChapterReviewWorkspace {
  chapter_id: string;
  current_role: string;
  owner_email: string | null;
  can_edit_chapter: boolean;
  can_run_generation: boolean;
  can_run_evaluation: boolean;
  can_comment: boolean;
  can_assign_comment: boolean;
  can_decide: boolean;
  can_request_checkpoint: boolean;
  can_decide_checkpoint: boolean;
  open_comment_count: number;
  resolved_comment_count: number;
  pending_checkpoint_count: number;
  latest_decision: ChapterReviewDecision | null;
  latest_pending_checkpoint: ChapterCheckpoint | null;
  assignable_members: ChapterReviewAssignableMember[];
  comments: ChapterReviewComment[];
  decisions: ChapterReviewDecision[];
  checkpoints: ChapterCheckpoint[];
}

export interface ChapterSelectionRewriteResponse {
  chapter: Chapter;
  selection_start: number;
  selection_end: number;
  rewritten_selection_end: number;
  original_text: string;
  rewritten_text: string;
  instruction: string;
  change_reason: string;
  related_comment_count: number;
  generation: {
    provider: string;
    model: string;
    used_fallback: boolean;
    metadata: Record<string, unknown>;
  };
}

export interface RollbackResponse {
  chapter: Chapter;
  restored_version: ChapterVersion;
}

export interface TaskState {
  task_id: string;
  task_type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  message: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  project_id: string | null;
  chapter_id: string | null;
  chapter_number: number | null;
  created_at: string;
  updated_at: string;
}

export interface TaskEvent {
  id: string;
  task_id: string;
  task_type: string;
  event_type: string;
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  message: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface TaskPlayback extends TaskState {
  recent_events: TaskEvent[];
}

export interface EvaluationIssue {
  dimension: string;
  severity: string;
  message: string;
  blocking: boolean;
  source: string;
  code: string | null;
}

export interface CanonEntityRef {
  plugin_key: string;
  entity_type: string;
  entity_id: string;
  label: string;
}

export interface TruthLayerFinding {
  source: string;
  action_scope: string;
  plugin_key: string | null;
  code: string | null;
  dimension: string | null;
  severity: string;
  blocking: boolean;
  message: string;
  fix_hint: string | null;
  evidence_text: string | null;
  entity_labels: string[];
}

export interface TruthLayerReferencedEntity {
  plugin_key: string | null;
  entity_type: string | null;
  entity_id: string | null;
  label: string | null;
}

export interface TruthLayerReportSection {
  source: string;
  issue_count: number;
  blocking_issue_count: number;
  summary: string | null;
  plugin_breakdown: Record<string, number>;
  top_issues: TruthLayerFinding[];
  referenced_entities: TruthLayerReferencedEntity[];
}

export interface TruthLayerContext {
  status: string;
  blocking: boolean;
  blocking_sources: string[];
  total_issue_count: number;
  total_blocking_issue_count: number;
  summary: string;
  blocking_policy: Record<string, boolean>;
  integrity: TruthLayerReportSection;
  canon: TruthLayerReportSection;
  priority_findings: TruthLayerFinding[];
  chapter_revision_targets: TruthLayerFinding[];
  story_bible_followups: TruthLayerFinding[];
}

export interface ReviewIssue {
  dimension: string;
  severity: string;
  message: string;
  blocking?: boolean;
  source?: string | null;
  code?: string | null;
}

export interface ChapterReviewSnapshot {
  overall_score: number;
  needs_revision: boolean;
  issues: ReviewIssue[];
  summary?: string | null;
  ai_taste_score?: number;
}

export interface RevisionFocusItem {
  dimension: string | null;
  severity: string;
  message: string;
  problem?: string | null;
  action: string | null;
  acceptance_criteria: string | null;
  source?: string | null;
  action_scope?: string | null;
  plugin_key?: string | null;
  code?: string | null;
  fix_hint?: string | null;
  entity_labels: string[];
}

export interface RevisionPlan {
  chapter_title?: string | null;
  objective?: string | null;
  focus_dimensions: string[];
  priorities: RevisionFocusItem[];
  truth_layer_status?: string | null;
  chapter_revision_targets?: TruthLayerFinding[];
  story_bible_followups?: TruthLayerFinding[];
  architect_position?: string | null;
  critic_position?: string | null;
  resolution?: string | null;
}

export interface DebateSummary {
  summary: string | null;
  architect_position?: string | null;
  critic_position?: string | null;
  resolution?: string | null;
  truth_layer_status?: string | null;
  truth_layer_blocking_sources?: string[];
  round_count?: number;
  final_verdict?: string | null;
}

export interface ApprovalBlockingIssue {
  dimension: string | null;
  severity: string | null;
  blocking?: boolean;
  message: string | null;
  source?: string | null;
  action_scope?: string | null;
  plugin_key?: string | null;
  code?: string | null;
  fix_hint?: string | null;
  entity_labels?: string[];
}

export interface ApprovalSummary {
  approved: boolean;
  summary?: string | null;
  release_recommendation?: string | null;
  score_delta?: number;
  final_score?: number;
  blocking_issues: ApprovalBlockingIssue[];
  truth_layer_status?: string | null;
  truth_layer_blocking_sources?: string[];
  truth_layer_followup_count?: number;
  revision_plan_steps?: number;
  target?: string | null;
}

export interface CanonIssue {
  plugin_key: string;
  code: string;
  dimension: string;
  severity: string;
  blocking: boolean;
  message: string;
  expected: string | null;
  actual: string | null;
  evidence_text: string | null;
  fix_hint: string | null;
  entity_refs: CanonEntityRef[];
  metadata: Record<string, unknown>;
}

export interface CanonValidationReport {
  chapter_number: number;
  chapter_title: string | null;
  issue_count: number;
  blocking_issue_count: number;
  plugin_breakdown: Record<string, number>;
  referenced_entities: CanonEntityRef[];
  issues: CanonIssue[];
  summary: string;
}

export interface CanonIntegrityReport {
  issue_count: number;
  blocking_issue_count: number;
  plugin_breakdown: Record<string, number>;
  issues: CanonIssue[];
  summary: string;
}

export interface CanonSnapshotEntity {
  plugin_key: string;
  entity_type: string;
  entity_id: string;
  label: string;
  aliases: string[];
  data: Record<string, unknown>;
  source_payload: Record<string, unknown>;
}

export interface CanonPluginSnapshot {
  plugin_key: string;
  entity_type: string;
  entity_count: number;
  entities: CanonSnapshotEntity[];
}

export interface CanonSnapshot {
  project_id: string;
  title: string;
  branch_id: string | null;
  branch_title: string | null;
  branch_key: string | null;
  scope: StoryBibleScope;
  plugin_snapshots: CanonPluginSnapshot[];
  total_entity_count: number;
  integrity_report: CanonIntegrityReport;
}

export interface EvaluationReport {
  chapter_id: string;
  overall_score: number;
  heuristic_overall_score: number;
  ai_taste_score: number;
  metrics: Record<string, number>;
  issues: EvaluationIssue[];
  summary: string;
  story_bible_integrity_issue_count: number;
  story_bible_integrity_blocking_issue_count: number;
  story_bible_integrity_report: CanonIntegrityReport | null;
  canon_issue_count: number;
  canon_blocking_issue_count: number;
  canon_report: CanonValidationReport | null;
  context_snapshot: Record<string, unknown>;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    metadata: Record<string, unknown>;
  };
}

export interface StoryCharacter {
  character_id: string;
  project_id: string;
  name: string;
  appearance: string | null;
  personality: string | null;
  micro_habits: string[];
  abilities: Record<string, unknown>;
  relationships: Array<Record<string, unknown>>;
  status: string;
  arc_stage: string;
  arc_boundaries: Array<Record<string, unknown>>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryForeshadow {
  foreshadow_id: string;
  project_id: string;
  content: string;
  chapter_planted: number | null;
  chapter_planned_reveal: number | null;
  status: string;
  related_characters: string[];
  related_items: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryItem {
  item_id: string;
  project_id: string;
  name: string;
  features: string | null;
  owner: string | null;
  location: string | null;
  special_rules: string[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryWorldRule {
  rule_id: string;
  project_id: string;
  rule_name: string;
  rule_content: string;
  negative_list: string[];
  scope: string;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryTimelineMapEvent {
  event_id: string;
  project_id: string;
  chapter_number: number | null;
  in_universe_time: string | null;
  location: string | null;
  weather: string | null;
  core_event: string;
  character_states: Array<Record<string, unknown>>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryOutline {
  outline_id: string;
  project_id: string;
  branch_id: string;
  parent_id: string | null;
  level: "level_1" | "level_2" | "level_3" | string;
  title: string;
  content: string;
  status: string;
  version: number;
  node_order: number;
  locked: boolean;
  immutable_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface StoryChapterSummary {
  summary_id: string;
  project_id: string;
  branch_id: string;
  chapter_number: number;
  content: string;
  core_progress: string[];
  character_changes: Array<Record<string, unknown>>;
  foreshadow_updates: Array<Record<string, unknown>>;
  kb_update_suggestions: StoryKnowledgeSuggestion[];
  version: number;
  created_at: string;
  updated_at: string;
}

export interface StoryKnowledgeVersion {
  version_record_id: string;
  project_id: string;
  entity_type: string;
  entity_id: string;
  version_number: number;
  action: string;
  snapshot: Record<string, unknown>;
  summary: string | null;
  source_workflow: string | null;
  created_by: string | null;
  created_at: string;
}

export interface StorySearchResult {
  entity_type: string;
  entity_id: string;
  score: number;
  content: string;
  metadata: Record<string, unknown>;
}

export interface StoryCharacterGraphNode {
  id: string;
  label: string;
  status: string | null;
  arc_stage: string | null;
}

export interface StoryCharacterGraphEdge {
  source: string;
  target: string;
  relation: string;
  intensity: string | null;
}

export interface StoryCharacterGraph {
  nodes: StoryCharacterGraphNode[];
  edges: StoryCharacterGraphEdge[];
}

export interface StoryEngineIssue {
  severity: "critical" | "high" | "medium" | "low";
  title: string;
  detail: string;
  source: string;
  suggestion: string | null;
}

export interface StoryEngineAgentReport {
  agent_name: string;
  role: string;
  priority: number;
  summary: string;
  issues: StoryEngineIssue[];
  proposed_actions: string[];
  raw_output: Record<string, unknown>;
}

export interface StoryEngineDeliberationEntry {
  actor_key: string;
  actor_label: string;
  role: string;
  stance: "review" | "challenge" | "revise" | "arbitrate" | "anchor";
  summary: string;
  evidence: string[];
  actions: string[];
  issues: StoryEngineIssue[];
}

export interface StoryEngineDeliberationRound {
  round_number: number;
  title: string;
  summary: string;
  resolution: string | null;
  entries: StoryEngineDeliberationEntry[];
}

export interface StoryEngineWorkspace {
  project: {
    project_id: string;
    title: string;
    genre: string | null;
    theme: string | null;
    tone: string | null;
  };
  outlines: StoryOutline[];
  characters: StoryCharacter[];
  foreshadows: StoryForeshadow[];
  items: StoryItem[];
  world_rules: StoryWorldRule[];
  timeline_events: StoryTimelineMapEvent[];
  chapter_summaries: StoryChapterSummary[];
  relationship_graph: StoryCharacterGraph;
  latest_guardian_alerts: Array<Record<string, unknown>>;
  latest_final_package: Record<string, unknown> | null;
  story_bible: StoryBible | null;
}

export interface StoryRoomCloudDraftSummary {
  draft_snapshot_id: string;
  project_id: string;
  branch_id: string | null;
  volume_id: string | null;
  scope_key: string;
  chapter_number: number;
  chapter_title: string;
  outline_id: string | null;
  source_chapter_id: string | null;
  source_version_number: number | null;
  excerpt: string;
  char_count: number;
  created_at: string;
  updated_at: string;
}

export interface StoryRoomCloudDraft extends StoryRoomCloudDraftSummary {
  draft_text: string;
}

export interface StoryRoomCloudDraftUpsertRequest {
  branch_id?: string | null;
  volume_id?: string | null;
  chapter_number: number;
  chapter_title: string;
  draft_text: string;
  outline_id?: string | null;
  source_chapter_id?: string | null;
  source_version_number?: number | null;
}

export type StoryEngineReasoningEffort = "minimal" | "low" | "medium" | "high";

export interface StoryEngineRoleCatalogItem {
  role_key: string;
  label: string;
  description: string;
}

export interface StoryEngineModelOption {
  id: string;
  label: string;
  provider: string;
  description: string | null;
  supports_reasoning_effort: boolean;
  recommended_roles: string[];
}

export interface StoryEngineRoleRouting {
  role_key: string;
  label: string;
  description: string;
  model: string;
  reasoning_effort: StoryEngineReasoningEffort | null;
  is_override: boolean;
}

export interface StoryEngineRoutingPreset {
  key: string;
  label: string;
  description: string | null;
  routing: Record<string, StoryEngineRoleRouting>;
}

export interface StoryEngineModelRouting {
  project: {
    project_id: string;
    title: string;
    genre: string | null;
    theme: string | null;
    tone: string | null;
  };
  default_preset_key: string;
  active_preset_key: string;
  available_models: StoryEngineModelOption[];
  available_reasoning_efforts: StoryEngineReasoningEffort[];
  role_catalog: StoryEngineRoleCatalogItem[];
  presets: StoryEngineRoutingPreset[];
  manual_overrides: Record<string, StoryEngineRoleRouting>;
  effective_routing: Record<string, StoryEngineRoleRouting>;
}

export interface StoryEngineModelRoutingUpdateRequest {
  active_preset_key: string;
  manual_overrides: Record<
    string,
    {
      model: string;
      reasoning_effort: StoryEngineReasoningEffort | null;
    }
  >;
}

export interface PortableStoryEngineRoleOverride {
  model?: string;
  reasoning_effort?: StoryEngineReasoningEffort | string | null;
}

export interface PortableStoryEngineRoutingPayload {
  version?: number;
  exported_at?: string;
  source_project_title?: string;
  active_preset_key?: string;
  manual_overrides?: Record<string, PortableStoryEngineRoleOverride>;
  effective_routing?: Record<string, PortableStoryEngineRoleOverride>;
}

export interface OutlineStressTestRequest {
  branch_id?: string | null;
  idea: string | null;
  genre: string | null;
  tone: string | null;
  target_chapter_count: number | null;
  target_total_words: number | null;
  source_material: string | null;
  source_material_name: string | null;
}

export interface OutlineStressTestResponse {
  locked_level_1_outlines: StoryOutline[];
  editable_level_2_outlines: StoryOutline[];
  editable_level_3_outlines: StoryOutline[];
  initial_knowledge_base: Record<string, unknown>;
  risk_report: StoryEngineIssue[];
  optimization_plan: string[];
  debate_rounds_completed: number;
  agent_reports: StoryEngineAgentReport[];
  deliberation_rounds: StoryEngineDeliberationRound[];
  workflow_timeline: StoryEngineWorkflowEvent[];
}

export interface StoryEngineWorkflowEvent {
  workflow_id: string;
  workflow_type: string;
  sequence: number;
  stage: string;
  status: "started" | "completed" | "paused" | "skipped" | "failed";
  label: string;
  message: string | null;
  chapter_number: number | null;
  chapter_title: string | null;
  branch_id: string | null;
  round_number: number | null;
  paragraph_index: number | null;
  paragraph_total: number | null;
  agent_keys: string[];
  details: Record<string, unknown>;
  emitted_at: string;
}

export interface RealtimeGuardRequest {
  branch_id?: string | null;
  chapter_id?: string | null;
  chapter_number: number;
  chapter_title: string | null;
  outline_id: string | null;
  current_outline: string | null;
  recent_chapters: string[];
  draft_text: string;
  latest_paragraph: string | null;
}

export interface RealtimeGuardResponse {
  passed: boolean;
  should_pause: boolean;
  alerts: StoryEngineIssue[];
  repair_options: string[];
  arbitration_note: string | null;
  workflow_timeline: StoryEngineWorkflowEvent[];
}

export interface FinalOptimizeRequest {
  branch_id?: string | null;
  chapter_id?: string | null;
  chapter_number: number;
  chapter_title: string | null;
  draft_text: string;
  style_sample: string | null;
}

export interface StoryKnowledgeSuggestion {
  suggestion_id: string;
  entity_type: string;
  action: string;
  status: "pending" | "applied" | "ignored";
  resolved_at?: string | null;
  applied_entity_type?: string | null;
  applied_entity_id?: string | null;
  applied_entity_key?: string | null;
  applied_entity_label?: string | null;
  [key: string]: unknown;
}

export interface FinalOptimizeResponse {
  final_draft: string;
  revision_notes: string[];
  chapter_summary: StoryChapterSummary;
  kb_update_list: StoryKnowledgeSuggestion[];
  agent_reports: StoryEngineAgentReport[];
  deliberation_rounds: StoryEngineDeliberationRound[];
  original_draft: string;
  consensus_rounds: number;
  consensus_reached: boolean;
  remaining_issue_count: number;
  ready_for_publish: boolean;
  quality_summary: string | null;
  workflow_timeline: StoryEngineWorkflowEvent[];
}

export interface StoryKnowledgeSuggestionResolveRequest {
  action: "apply" | "ignore";
}

export interface StoryKnowledgeSuggestionResolveResponse {
  chapter_summary: StoryChapterSummary;
  resolved_suggestion: StoryKnowledgeSuggestion;
  applied_entity_type: string | null;
  applied_entity_id: string | null;
  applied_entity_key: string | null;
  applied_entity_label: string | null;
  message: string;
}

export interface StoryKnowledgeMutationResponse {
  passed: boolean;
  blocked: boolean;
  message: string;
  alerts: StoryEngineIssue[];
  blocking_issue_count: number;
  warning_count: number;
}

export interface ChapterStreamGenerateRequest {
  branch_id?: string | null;
  chapter_id?: string | null;
  chapter_number: number;
  chapter_title: string | null;
  outline_id: string | null;
  current_outline: string | null;
  recent_chapters: string[];
  existing_text: string;
  style_sample: string | null;
  target_word_count: number;
  target_paragraph_count: number;
  resume_from_paragraph?: number | null;
  repair_instruction?: string | null;
  rewrite_latest_paragraph?: boolean;
}

export interface ChapterStreamEvent {
  event: "start" | "plan" | "chunk" | "guard" | "done" | "error";
  message: string | null;
  delta: string | null;
  text: string | null;
  paragraph_index: number | null;
  paragraph_total: number | null;
  guard_result: RealtimeGuardResponse | null;
  metadata: Record<string, unknown>;
  workflow_event: StoryEngineWorkflowEvent | null;
}

export interface StoryOutlineImportItem {
  level: "level_1" | "level_2" | "level_3";
  title: string;
  content: string;
  status: "todo" | "written";
  node_order: number;
  parent_title: string | null;
  locked: boolean;
  immutable_reason: string | null;
}

export interface StoryBulkImportCharacter {
  name: string;
  appearance: string | null;
  personality: string | null;
  micro_habits: string[];
  abilities: Record<string, unknown>;
  relationships: Array<Record<string, unknown>>;
  status: string;
  arc_stage: string;
  arc_boundaries: Array<Record<string, unknown>>;
}

export interface StoryBulkImportForeshadow {
  content: string;
  chapter_planted: number | null;
  chapter_planned_reveal: number | null;
  status: string;
  related_characters: string[];
  related_items: string[];
}

export interface StoryBulkImportItem {
  name: string;
  features: string | null;
  owner: string | null;
  location: string | null;
  special_rules: string[];
}

export interface StoryBulkImportWorldRule {
  rule_name: string;
  rule_content: string;
  negative_list: string[];
  scope: string;
}

export interface StoryBulkImportTimelineEvent {
  chapter_number: number | null;
  in_universe_time: string | null;
  location: string | null;
  weather: string | null;
  core_event: string;
  character_states: Array<Record<string, unknown>>;
}

export interface StoryBulkImportChapterSummary {
  chapter_number: number;
  content: string;
  core_progress: string[];
  character_changes: Array<Record<string, unknown>>;
  foreshadow_updates: Array<Record<string, unknown>>;
  kb_update_suggestions: Array<Record<string, unknown>>;
}

export interface StoryBulkImportPayload {
  characters: StoryBulkImportCharacter[];
  foreshadows: StoryBulkImportForeshadow[];
  items: StoryBulkImportItem[];
  world_rules: StoryBulkImportWorldRule[];
  timeline_events: StoryBulkImportTimelineEvent[];
  outlines: StoryOutlineImportItem[];
  chapter_summaries: StoryBulkImportChapterSummary[];
}

export interface StoryImportTemplate {
  key: string;
  label: string;
  description: string;
  usage_notes: string[];
  recommended_model_preset_key: string | null;
  recommended_model_preset_label: string | null;
  payload: StoryBulkImportPayload;
}

export interface StoryBulkImportRequest {
  branch_id?: string | null;
  template_key: string | null;
  apply_template_model_routing: boolean;
  replace_existing_sections: string[];
  payload: StoryBulkImportPayload | null;
}

export interface StoryBulkImportResponse {
  imported_counts: Record<string, number>;
  replaced_sections: string[];
  applied_model_preset_key: string | null;
  applied_model_preset_label: string | null;
  warnings: string[];
  workflow_timeline: StoryEngineWorkflowEvent[];
}
