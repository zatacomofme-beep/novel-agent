from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import ConfigDict, Field

from schemas.base import ORMModel


class WorldBuildingStepData(ORMModel):
    model_config = ConfigDict(protected_namespaces=())
    
    user_input: str
    model_summary: Optional[str] = None
    model_expansion: Optional[str] = None
    follow_up_input: Optional[str] = None


class WorldBuildingSessionCreate(ORMModel):
    initial_idea: Optional[str] = Field(default="", max_length=2000)


class WorldBuildingSessionRead(ORMModel):
    id: UUID
    project_id: UUID
    user_id: UUID
    current_step: int
    last_active_step: int
    session_data: dict
    status: str
    completed_steps: list[int]


class WorldBuildingSessionUpdate(ORMModel):
    current_step: Optional[int] = None
    last_active_step: Optional[int] = None
    session_data: Optional[dict] = None
    status: Optional[str] = None
    completed_steps: Optional[list[int]] = None


class WorldBuildingStepResponse(ORMModel):
    model_config = ConfigDict(protected_namespaces=())
    
    step: int
    step_title: str
    model_summary: str
    model_expansion: str
    is_awaiting_follow_up: bool
    suggested_next_step: int
    can_skip: bool
    is_complete: bool
    generation_failed: bool = Field(default=False)


class WorldBuildingStepSubmit(ORMModel):
    user_input: str = Field(min_length=1, max_length=5000)
    skip_to_next: bool = Field(default=False)


class WorldBuildingStartResponse(ORMModel):
    session: WorldBuildingSessionRead
    first_question: str
    step: int
    step_title: str
