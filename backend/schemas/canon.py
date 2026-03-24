from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from canon.base import CanonIntegrityReport
from pydantic import Field

from schemas.base import ORMModel
from schemas.project import StoryBibleScopeRead


class CanonEntityRead(ORMModel):
    plugin_key: str
    entity_type: str
    entity_id: str
    label: str
    aliases: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    source_payload: dict[str, Any] = Field(default_factory=dict)


class CanonPluginSnapshotRead(ORMModel):
    plugin_key: str
    entity_type: str
    entity_count: int = 0
    entities: list[CanonEntityRead] = Field(default_factory=list)


class CanonSnapshotRead(ORMModel):
    project_id: UUID
    title: str
    branch_id: Optional[UUID] = None
    branch_title: Optional[str] = None
    branch_key: Optional[str] = None
    scope: StoryBibleScopeRead = Field(default_factory=StoryBibleScopeRead)
    plugin_snapshots: list[CanonPluginSnapshotRead] = Field(default_factory=list)
    total_entity_count: int = 0
    integrity_report: CanonIntegrityReport = Field(
        default_factory=lambda: CanonIntegrityReport(
            issue_count=0,
            blocking_issue_count=0,
            plugin_breakdown={},
            issues=[],
            summary="Story Bible 规范层结构自洽，当前没有发现坏引用、坏时序或实体身份冲突。",
        )
    )
