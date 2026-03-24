from __future__ import annotations

from typing import Any
from typing import Optional
from uuid import UUID

from canon.base import CanonIntegrityReport
from canon.base import CanonValidationReport
from pydantic import BaseModel


class EvaluationIssue(BaseModel):
    dimension: str
    severity: str
    message: str
    blocking: bool = False
    source: str = "heuristic"
    code: Optional[str] = None


class EvaluationReport(BaseModel):
    chapter_id: UUID
    overall_score: float
    heuristic_overall_score: float
    ai_taste_score: float
    metrics: dict[str, float]
    issues: list[EvaluationIssue]
    summary: str
    story_bible_integrity_issue_count: int = 0
    story_bible_integrity_blocking_issue_count: int = 0
    story_bible_integrity_report: Optional[CanonIntegrityReport] = None
    canon_issue_count: int = 0
    canon_blocking_issue_count: int = 0
    canon_report: Optional[CanonValidationReport] = None
    context_snapshot: dict[str, Any]
