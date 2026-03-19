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

export interface StoryBible {
  project: Project;
  characters: CharacterItem[];
  world_settings: WorldSettingItem[];
  locations: LocationItem[];
  plot_threads: PlotThreadItem[];
  foreshadowing: ForeshadowingItem[];
  timeline_events: TimelineEventItem[];
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
  status: string;
  quality_metrics: Record<string, unknown> | null;
  pending_checkpoint_count: number;
  rejected_checkpoint_count: number;
  latest_checkpoint_status: string | null;
  latest_checkpoint_title: string | null;
  latest_review_verdict: string | null;
  latest_review_summary: string | null;
  review_gate_blocked: boolean;
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
  resolved_by_user_id: string | null;
  resolved_by_email: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
  reply_count: number;
  can_edit: boolean;
  can_change_status: boolean;
  can_delete: boolean;
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
  can_decide: boolean;
  can_request_checkpoint: boolean;
  can_decide_checkpoint: boolean;
  open_comment_count: number;
  resolved_comment_count: number;
  pending_checkpoint_count: number;
  latest_decision: ChapterReviewDecision | null;
  latest_pending_checkpoint: ChapterCheckpoint | null;
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

export interface EvaluationIssue {
  dimension: string;
  severity: string;
  message: string;
}

export interface EvaluationReport {
  chapter_id: string;
  overall_score: number;
  ai_taste_score: number;
  metrics: Record<string, number>;
  issues: EvaluationIssue[];
  summary: string;
  context_snapshot: Record<string, unknown>;
}

export interface ApiErrorPayload {
  error: {
    code: string;
    message: string;
    metadata: Record<string, unknown>;
  };
}
