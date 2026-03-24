from __future__ import annotations

from typing import Any
from typing import Optional

from pydantic import ConfigDict
from pydantic import Field

from schemas.base import ORMModel


class ChapterQualityMetricsSnapshot(ORMModel):
    model_config = ConfigDict(from_attributes=True, extra="allow")

    evaluation_status: Optional[str] = None
    evaluation_stale_reason: Optional[str] = None
    evaluation_updated_at: Optional[str] = None
    overall_score: Optional[float] = None
    heuristic_overall_score: Optional[float] = None
    ai_taste_score: Optional[float] = None
    summary: Optional[str] = None
    story_bible_integrity_issue_count: int = 0
    story_bible_integrity_blocking_issue_count: int = 0
    story_bible_integrity_summary: Optional[str] = None
    story_bible_integrity_report: Optional[dict[str, Any]] = None
    canon_issue_count: int = 0
    canon_blocking_issue_count: int = 0
    canon_summary: Optional[str] = None
    canon_plugin_breakdown: dict[str, int] = Field(default_factory=dict)
    canon_report: Optional[dict[str, Any]] = None

    @classmethod
    def from_payload(
        cls,
        value: Optional[object],
    ) -> "ChapterQualityMetricsSnapshot":
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls.model_validate(value)
        return cls()

    def to_payload(self) -> dict[str, Any]:
        return self.model_dump(
            mode="json",
            exclude_none=True,
            exclude_defaults=True,
        )

    def has_evaluation_payload(self) -> bool:
        return any(
            value is not None
            for value in (
                self.overall_score,
                self.heuristic_overall_score,
                self.ai_taste_score,
                self.summary,
                self.story_bible_integrity_summary,
                self.story_bible_integrity_report,
                self.canon_summary,
                self.canon_report,
            )
        )

    def metric_float(self, key: str) -> Optional[float]:
        value = self.model_dump(exclude_none=False).get(key)
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        return None
