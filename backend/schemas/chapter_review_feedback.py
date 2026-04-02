from __future__ import annotations

from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel


class ChapterReviewFeedbackRequest(ORMModel):
    feedback: str = Field(min_length=5, max_length=5000)


class ChapterReviewFeedbackResponse(ORMModel):
    chapter_id: UUID
    processed_feedback: str


class ChapterRegenerateRequest(ORMModel):
    feedback: str = Field(min_length=5, max_length=5000)
