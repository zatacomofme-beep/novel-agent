from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from models.story_bible_version import (
    StoryBibleChangeSource,
    StoryBibleChangeType,
    StoryBiblePendingChangeStatus,
    StoryBibleSection,
)


class StoryBibleVersionBase(BaseModel):
    version_number: int
    change_type: StoryBibleChangeType
    change_source: StoryBibleChangeSource
    changed_section: StoryBibleSection
    changed_entity_id: UUID | None = None
    changed_entity_key: str | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    snapshot: dict[str, Any] = Field(default_factory=dict)
    note: str | None = None


class StoryBibleVersionRead(StoryBibleVersionBase):
    id: UUID
    project_id: UUID
    branch_id: UUID
    created_by: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryBibleVersionList(BaseModel):
    items: list[StoryBibleVersionRead]
    total: int
    page: int
    page_size: int


class StoryBiblePendingChangeBase(BaseModel):
    change_type: StoryBibleChangeType
    change_source: StoryBibleChangeSource
    changed_section: StoryBibleSection
    changed_entity_id: UUID | None = None
    changed_entity_key: str | None = None
    old_value: dict[str, Any] | None = None
    new_value: dict[str, Any] | None = None
    reason: str | None = None
    triggered_by_chapter_id: UUID | None = None
    proposed_by_agent: str | None = None


class StoryBiblePendingChangeCreate(StoryBiblePendingChangeBase):
    project_id: UUID
    branch_id: UUID


class StoryBiblePendingChangeRead(StoryBiblePendingChangeBase):
    id: UUID
    project_id: UUID
    branch_id: UUID
    status: StoryBiblePendingChangeStatus
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    rejected_by: UUID | None = None
    rejected_at: datetime | None = None
    rejection_reason: str | None = None
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StoryBiblePendingChangeList(BaseModel):
    items: list[StoryBiblePendingChangeRead]
    total: int
    pending_count: int


class StoryBibleApprovalRequest(BaseModel):
    approved: bool
    comment: str | None = None


class StoryBibleRollbackRequest(BaseModel):
    target_version_id: UUID
    reason: str | None = None


class ConflictCheckRequest(BaseModel):
    section: StoryBibleSection
    entity_key: str
    proposed_value: dict[str, Any]


class ConflictCheckResult(BaseModel):
    has_conflict: bool
    conflicting_items: list[dict[str, Any]] = Field(default_factory=list)
    suggestion: str | None = None
