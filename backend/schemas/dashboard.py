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
