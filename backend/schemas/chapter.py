from __future__ import annotations

from datetime import datetime
from typing import Any
from typing import Optional
from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel


class ChapterCreate(ORMModel):
    chapter_number: int = Field(ge=1)
    volume_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, max_length=255)
    content: str = ""
    outline: Optional[dict[str, Any]] = None
    status: str = Field(default="draft", max_length=50)
    change_reason: Optional[str] = None


class ChapterUpdate(ORMModel):
    volume_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    title: Optional[str] = Field(default=None, max_length=255)
    content: Optional[str] = None
    outline: Optional[dict[str, Any]] = None
    status: Optional[str] = Field(default=None, max_length=50)
    quality_metrics: Optional[dict[str, Any]] = None
    change_reason: Optional[str] = None
    create_version: bool = True


class ChapterRead(ORMModel):
    id: UUID
    project_id: UUID
    volume_id: Optional[UUID] = None
    branch_id: Optional[UUID] = None
    chapter_number: int
    title: Optional[str] = None
    content: str
    outline: Optional[dict[str, Any]] = None
    word_count: Optional[int] = None
    status: str
    quality_metrics: Optional[dict[str, Any]] = None
    pending_checkpoint_count: int = 0
    rejected_checkpoint_count: int = 0
    latest_checkpoint_status: Optional[str] = None
    latest_checkpoint_title: Optional[str] = None
    latest_review_verdict: Optional[str] = None
    latest_review_summary: Optional[str] = None
    review_gate_blocked: bool = False
    final_ready: bool = True
    final_gate_status: str = "ready"
    final_gate_reason: Optional[str] = None


class ChapterVersionRead(ORMModel):
    id: UUID
    chapter_id: UUID
    version_number: int
    content: str
    change_reason: Optional[str] = None


class RollbackResponse(ORMModel):
    chapter: ChapterRead
    restored_version: ChapterVersionRead


class ChapterReviewCommentCreate(ORMModel):
    body: str = Field(min_length=1)
    parent_comment_id: Optional[UUID] = None
    assignee_user_id: Optional[UUID] = None
    selection_start: Optional[int] = Field(default=None, ge=0)
    selection_end: Optional[int] = Field(default=None, ge=0)
    selection_text: Optional[str] = None


class ChapterReviewCommentUpdate(ORMModel):
    body: Optional[str] = Field(default=None, min_length=1)
    status: Optional[str] = Field(default=None, max_length=50)
    assignee_user_id: Optional[UUID] = None


class ChapterReviewCommentRead(ORMModel):
    id: UUID
    chapter_id: UUID
    user_id: UUID
    parent_comment_id: Optional[UUID] = None
    chapter_version_number: int
    author_email: str
    body: str
    status: str
    selection_start: Optional[int] = None
    selection_end: Optional[int] = None
    selection_text: Optional[str] = None
    assignee_user_id: Optional[UUID] = None
    assignee_email: Optional[str] = None
    assigned_by_user_id: Optional[UUID] = None
    assigned_by_email: Optional[str] = None
    assigned_at: Optional[datetime] = None
    resolved_by_user_id: Optional[UUID] = None
    resolved_by_email: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    reply_count: int = 0
    can_edit: bool = False
    can_assign: bool = False
    can_change_status: bool = False
    can_delete: bool = False


class ChapterReviewAssignableMemberRead(ORMModel):
    user_id: UUID
    email: str
    role: str
    is_owner: bool = False


class ChapterReviewDecisionCreate(ORMModel):
    verdict: str = Field(max_length=50)
    summary: str = Field(min_length=1)
    focus_points: list[str] = Field(default_factory=list)


class ChapterReviewDecisionRead(ORMModel):
    id: UUID
    chapter_id: UUID
    user_id: UUID
    chapter_version_number: int
    reviewer_email: str
    verdict: str
    summary: str
    focus_points: list[str] = Field(default_factory=list)
    created_at: datetime


class ChapterCheckpointCreate(ORMModel):
    checkpoint_type: str = Field(default="story_turn", max_length=50)
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None


class ChapterCheckpointUpdate(ORMModel):
    status: str = Field(max_length=50)
    decision_note: Optional[str] = None


class ChapterCheckpointRead(ORMModel):
    id: UUID
    chapter_id: UUID
    requester_user_id: UUID
    chapter_version_number: int
    checkpoint_type: str
    title: str
    description: Optional[str] = None
    status: str
    decision_note: Optional[str] = None
    requester_email: str
    decided_by_user_id: Optional[UUID] = None
    decided_by_email: Optional[str] = None
    decided_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    can_decide: bool = False
    can_cancel: bool = False


class ChapterReviewWorkspaceRead(ORMModel):
    chapter_id: UUID
    current_role: str
    owner_email: Optional[str] = None
    can_edit_chapter: bool = False
    can_run_generation: bool = False
    can_run_evaluation: bool = False
    can_comment: bool = False
    can_assign_comment: bool = False
    can_decide: bool = False
    can_request_checkpoint: bool = False
    can_decide_checkpoint: bool = False
    open_comment_count: int = 0
    resolved_comment_count: int = 0
    pending_checkpoint_count: int = 0
    latest_decision: Optional[ChapterReviewDecisionRead] = None
    latest_pending_checkpoint: Optional[ChapterCheckpointRead] = None
    assignable_members: list[ChapterReviewAssignableMemberRead] = Field(default_factory=list)
    comments: list[ChapterReviewCommentRead] = Field(default_factory=list)
    decisions: list[ChapterReviewDecisionRead] = Field(default_factory=list)
    checkpoints: list[ChapterCheckpointRead] = Field(default_factory=list)


class ChapterSelectionRewriteRequest(ORMModel):
    selection_start: int = Field(ge=0)
    selection_end: int = Field(ge=1)
    instruction: str = Field(min_length=1)
    create_version: bool = True


class ChapterSelectionRewriteResponse(ORMModel):
    chapter: ChapterRead
    selection_start: int
    selection_end: int
    rewritten_selection_end: int
    original_text: str
    rewritten_text: str
    instruction: str
    change_reason: str
    related_comment_count: int = 0
    generation: dict[str, Any] = Field(default_factory=dict)
