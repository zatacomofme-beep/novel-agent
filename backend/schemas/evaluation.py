from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class EvaluationIssue(BaseModel):
    dimension: str
    severity: str
    message: str


class EvaluationReport(BaseModel):
    chapter_id: UUID
    overall_score: float
    ai_taste_score: float
    metrics: dict[str, float]
    issues: list[EvaluationIssue]
    summary: str
    context_snapshot: dict[str, Any]
