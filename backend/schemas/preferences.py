from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel


class PreferenceLearningSignal(ORMModel):
    field: str
    value: str
    confidence: float
    source_count: int


class PreferenceLearningSnapshot(ORMModel):
    observation_count: int = 0
    last_observed_at: Optional[datetime] = None
    source_breakdown: dict[str, int] = Field(default_factory=dict)
    stable_preferences: list[PreferenceLearningSignal] = Field(default_factory=list)
    favored_elements: list[str] = Field(default_factory=list)
    summary: Optional[str] = None


class ActiveStyleTemplateRead(ORMModel):
    key: str
    name: str
    tagline: str


class StyleTemplateRead(ORMModel):
    key: str
    name: str
    tagline: str
    description: str
    category: str
    recommended_for: list[str] = Field(default_factory=list)
    prose_style: str
    narrative_mode: str
    pacing_preference: str
    dialogue_preference: str
    tension_preference: str
    sensory_density: str
    favored_elements: list[str] = Field(default_factory=list)
    banned_patterns: list[str] = Field(default_factory=list)
    custom_style_notes: Optional[str] = None
    is_active: bool = False


class StyleTemplateApplyRequest(ORMModel):
    mode: str = Field(default="replace", max_length=20)


class UserPreferenceUpdate(ORMModel):
    prose_style: Optional[str] = Field(default=None, max_length=50)
    narrative_mode: Optional[str] = Field(default=None, max_length=50)
    pacing_preference: Optional[str] = Field(default=None, max_length=50)
    dialogue_preference: Optional[str] = Field(default=None, max_length=50)
    tension_preference: Optional[str] = Field(default=None, max_length=50)
    sensory_density: Optional[str] = Field(default=None, max_length=50)
    favored_elements: Optional[list[str]] = None
    banned_patterns: Optional[list[str]] = None
    custom_style_notes: Optional[str] = None


class UserPreferenceRead(ORMModel):
    id: UUID
    user_id: UUID
    active_template_key: Optional[str] = None
    active_template: Optional[ActiveStyleTemplateRead] = None
    prose_style: str
    narrative_mode: str
    pacing_preference: str
    dialogue_preference: str
    tension_preference: str
    sensory_density: str
    favored_elements: list[str]
    banned_patterns: list[str]
    custom_style_notes: Optional[str] = None
    completion_score: float
    learning_snapshot: PreferenceLearningSnapshot
    updated_at: datetime
