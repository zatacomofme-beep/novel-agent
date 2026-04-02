from __future__ import annotations
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateVariable(BaseModel):
    name: str
    description: str
    default: Optional[str] = None
    required: bool = True


class PromptTemplateBase(BaseModel):
    name: str = Field(max_length=200)
    tagline: str = Field(max_length=300)
    description: str
    category: str = Field(max_length=50)
    sub_category: Optional[str] = Field(default=None, max_length=50)
    tags: list[str] = Field(default_factory=list)
    content: str
    variables: list[PromptTemplateVariable] = Field(default_factory=list)
    recommended_scenes: list[str] = Field(default_factory=list)
    difficulty_level: str = Field(default="intermediate", max_length=20)


class PromptTemplateCreate(PromptTemplateBase):
    pass


class PromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    tagline: Optional[str] = Field(default=None, max_length=300)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=50)
    sub_category: Optional[str] = Field(default=None, max_length=50)
    tags: Optional[list[str]] = None
    content: Optional[str] = None
    variables: Optional[list[PromptTemplateVariable]] = None
    recommended_scenes: Optional[list[str]] = None
    difficulty_level: Optional[str] = Field(default=None, max_length=20)
    is_active: Optional[bool] = None


class PromptTemplateRead(PromptTemplateBase):
    id: UUID
    use_count: int
    is_system: bool
    is_active: bool
    user_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PromptTemplateApplyRequest(BaseModel):
    project_id: str
    chapter_id: Optional[str] = None
    variables: dict[str, str] = Field(default_factory=dict)


class PromptTemplateApplyResponse(BaseModel):
    success: bool
    content: str
    chapter_id: Optional[str] = None
    message: Optional[str] = None


class PromptTemplateListResponse(BaseModel):
    templates: list[PromptTemplateRead]
    total: int
    categories: list[str]


class PromptTemplateRecommendRequest(BaseModel):
    project_id: str
    chapter_id: Optional[str] = None
    chapter_content: Optional[str] = None
    context: Optional[str] = None


class PromptTemplateRecommendResponse(BaseModel):
    templates: list[PromptTemplateRead]
    reason: Optional[str] = None
