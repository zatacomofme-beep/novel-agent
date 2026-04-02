from __future__ import annotations

from uuid import UUID

from pydantic import Field

from schemas.base import ORMModel


class WritingIntentGenerateResponse(ORMModel):
    chapter_id: UUID
    writing_intent: str


class WritingIntentApproveRequest(ORMModel):
    pass


class WritingIntentUpdateRequest(ORMModel):
    writing_intent: str = Field(min_length=10, max_length=5000)


class WritingIntentRead(ORMModel):
    chapter_id: UUID
    writing_intent: str | None
    writing_intent_approved: bool
