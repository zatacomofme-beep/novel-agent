from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from schemas.base import ORMModel
from schemas.preferences import UserPreferenceRead


class DashboardProjectSummaryRead(ORMModel):
    project_id: UUID
    title: str
    genre: Optional[str] = None
    status: str
    access_role: str = "owner"
    owner_email: Optional[str] = None
    collaborator_count: int = 0
    has_bootstrap_profile: bool = False
    has_novel_blueprint: bool = False
    updated_at: datetime
    chapter_count: int
    word_count: int
    review_ready_chapters: int
    final_chapters: int
    risk_chapter_count: int
    active_task_count: int
    average_overall_score: Optional[float] = None
    average_ai_taste_score: Optional[float] = None
    score_delta: Optional[float] = None
    trend_direction: str = "insufficient_data"


class DashboardProjectTrendPointRead(ORMModel):
    chapter_id: UUID
    chapter_number: int
    title: Optional[str] = None
    status: str
    overall_score: Optional[float] = None
    ai_taste_score: Optional[float] = None
    word_count: int
    updated_at: datetime


class DashboardProjectQualityTrendRead(ORMModel):
    project_id: UUID
    title: str
    status: str
    access_role: str = "owner"
    owner_email: Optional[str] = None
    collaborator_count: int = 0
    updated_at: datetime
    latest_overall_score: Optional[float] = None
    latest_ai_taste_score: Optional[float] = None
    score_delta: Optional[float] = None
    ai_taste_delta: Optional[float] = None
    trend_direction: str = "insufficient_data"
    evaluated_chapter_count: int
    chapter_count: int
    visible_chapter_count: int
    coverage_ratio: float
    average_overall_score: Optional[float] = None
    average_ai_taste_score: Optional[float] = None
    review_ready_chapters: int
    final_chapters: int
    status_breakdown: dict[str, int]
    range_start_chapter_number: Optional[int] = None
    range_end_chapter_number: Optional[int] = None
    strongest_chapter: Optional[DashboardProjectTrendPointRead] = None
    weakest_chapter: Optional[DashboardProjectTrendPointRead] = None
    risk_chapter_numbers: list[int]
    chapter_points: list[DashboardProjectTrendPointRead]


class DashboardRecentTaskRead(ORMModel):
    task_id: str
    task_type: str
    status: str
    progress: int
    message: Optional[str] = None
    project_id: Optional[UUID] = None
    chapter_id: Optional[UUID] = None
    chapter_number: Optional[int] = None
    updated_at: datetime


class DashboardActivitySnapshotRead(ORMModel):
    active_projects_last_7_days: int = 0
    chapters_updated_last_7_days: int = 0
    active_words_last_7_days: int = 0
    new_projects_last_30_days: int = 0
    final_chapters_last_30_days: int = 0
    stale_projects_last_14_days: int = 0


class DashboardQualitySnapshotRead(ORMModel):
    risk_chapter_count: int = 0
    projects_with_risk_count: int = 0
    low_score_chapter_count: int = 0
    high_ai_taste_chapter_count: int = 0
    improving_project_count: int = 0
    declining_project_count: int = 0
    stable_project_count: int = 0
    average_coverage_ratio: float = 0.0


class DashboardTaskHealthRead(ORMModel):
    total_task_count: int = 0
    queued_count: int = 0
    running_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    stalled_active_task_count: int = 0
    recent_failed_task_count: int = 0
    status_breakdown: dict[str, int]


class DashboardPipelineSnapshotRead(ORMModel):
    outline_pending_projects: int = 0
    ready_for_first_chapter_projects: int = 0
    writing_in_progress_projects: int = 0
    awaiting_finalization_projects: int = 0
    stable_output_projects: int = 0


class DashboardGenreDistributionItemRead(ORMModel):
    genre: str
    project_count: int


class DashboardFocusItemRead(ORMModel):
    project_id: UUID
    title: str
    genre: Optional[str] = None
    focus_type: str
    stage: str
    action_label: str
    reason: str
    chapter_number: Optional[int] = None
    priority: int
    risk_level: str = "low"
    updated_at: datetime


class DashboardOverviewRead(ORMModel):
    total_projects: int
    total_chapters: int
    total_words: int
    active_task_count: int
    review_ready_chapters: int
    final_chapters: int
    average_overall_score: Optional[float] = None
    average_ai_taste_score: Optional[float] = None
    chapters_by_status: dict[str, int]
    preference_profile: UserPreferenceRead
    project_summaries: list[DashboardProjectSummaryRead]
    project_quality_trends: list[DashboardProjectQualityTrendRead]
    recent_tasks: list[DashboardRecentTaskRead]
    activity_snapshot: DashboardActivitySnapshotRead
    quality_snapshot: DashboardQualitySnapshotRead
    task_health: DashboardTaskHealthRead
    pipeline_snapshot: DashboardPipelineSnapshotRead
    genre_distribution: list[DashboardGenreDistributionItemRead]
    focus_queue: list[DashboardFocusItemRead]
